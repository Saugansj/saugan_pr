"""WP2-B tests (B1-B14): three-flag guard, L2 client, write-ahead live router, dropped-ack and kill -9 drills, user
channel, reconciliation, preflight doctor. Every venue is a fake: L2Client runs with an injected transport (Venue
below) and the user channel against a local websocket server. No network: the autouse guard allows loopback only."""
import ast
import asyncio
import base64
import collections
import hashlib
import itertools
import json
import pathlib
import re
import socket
from urllib.parse import urlsplit

import pytest

from tools.live_tools import doctor
from trader.contracts import Book, Intent, MarketInfo
from trader.fees import fee
from trader.kernel import RiskKernel
from trader.live import clob
from trader.live.clob import (CredentialsMissing, Creds, L2Client, LiveGuardError, LiveUnavailable, SdkSigner, UserWS,
                              l2_headers, live_enabled)
from trader.live.router import LiveRouter, gtd_expiry_ms
from trader.router import replay

ROOT = pathlib.Path(__file__).resolve().parents[2]
NOW = 1_700_000_000_000
MIN = 60_000
LOOPBACK = ("127.0.0.1", "::1", "localhost")
_connect = socket.socket.connect
SECRET = base64.b64encode(b"roster-phase2-test-secret-000000").decode()  # the orchestrator's test vector, not a key
CREDS = dict(zip(clob.L2, ("0xunit-test-address", "unit-test-key-id", SECRET, "unit-test-pass")))
HUMAN_KEY = "unit-test-human-key"  # the kernel's reset-token key; no reset is signed here
VEC_CANCEL_ALL = "qFXxB7_xYdSIihsVXzMqNm2Mr246XAiifhdxm1qQmPE="
VEC_HEARTBEAT = "avX2p-Efrs7FeFL6flN3GEvFYz3AMGKeM2JDLKIbkcY="
MARKET = MarketInfo("0xcid", "Y", "N", "crypto-term", "Will BTC be above $100,000?", "rules", 0.01, 5.0, 0.07, False,
                    NOW + 6 * 3_600_000, "BTC@2023-11-15T04:13Z", "BTC", 100_000.0, "strike", "binance:BTC/USDT")
BOOK = Book("Y", [(0.50, 100.0)], [(0.51, 100.0)], NOW)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def connect(self, addr):
        if addr[0] not in LOOPBACK:
            raise RuntimeError(f"network disabled in unit tests ({addr[0]})")
        return _connect(self, addr)
    monkeypatch.setattr(socket.socket, "connect", connect)


# ---- fakes ----------------------------------------------------------------------------------------------------------
class FakeSigner:
    def __init__(self):
        self.n = 0

    def address(self):
        return CREDS["POLY_ADDRESS"]

    def sign(self, intent, market, expiration_s, order_type):
        self.n += 1
        oid = "0x" + hashlib.sha256(f"{self.n}|{intent}".encode()).hexdigest()
        return oid, {"fake_id": oid, "tokenId": intent.token_id, "side": intent.side, "price": intent.price,
                     "size": intent.size, "expiration": str(expiration_s)}


class Venue:
    """Fake CLOB behind L2Client's transport. Records every call; with `journal` set, every post asserts that the
    orders' `new` lines are already on disk (write-ahead)."""

    def __init__(self, journal=None):
        self.calls, self.orders, self.journal, self.wal_checked = [], {}, journal, 0
        self.post = "ack"  # ack | reject | timeout (venue has it, answer lost) | swallow (never got it) | http400 | http500
        self.dead = False  # cancel-by-id and order queries time out
        self.maker_fill = 0.0
        self.taker_fill = {"BUY": 1.0, "SELL": 1.0}

    def n(self, method, path=None):
        return sum(1 for c in self.calls if c[0] == method and (path is None or c[1] == path))

    def posted_ids(self):
        return [it["order"]["fake_id"] for m, p, b in self.calls if (m, p) == ("POST", "/orders") for it in b]

    def __call__(self, method, url, headers, body, timeout):
        assert tuple(headers) == clob.HEADERS and timeout == 5.0
        path, b = urlsplit(url).path, json.loads(body) if body else None
        self.calls.append((method, path, b))
        if (method, path) == ("POST", "/orders"):
            if self.journal is not None:
                lines = [json.loads(x) for x in self.journal.read_text().splitlines()]
                assert {it["order"]["fake_id"] for it in b} <= {e["id"] for e in lines if e["op"] == "new"}
                self.wal_checked += 1
            if self.post == "swallow":
                raise TimeoutError("timed out")
            if self.post in ("http400", "http500"):
                return (400 if self.post == "http400" else 500), {"error": "invalid payload"}
            out = []
            for it in b:
                o, fak = it["order"], it["orderType"] == "FAK"
                assert it["postOnly"] is (not fak) and it["owner"] == CREDS["POLY_API_KEY"]
                if self.post == "reject":
                    out.append({"success": False, "errorMsg": "INVALID_ORDER_MIN_TICK_SIZE", "orderID": ""})
                    continue
                matched = round(o["size"] * (self.taker_fill[o["side"]] if fak else self.maker_fill), 2)
                status = "MATCHED" if matched >= o["size"] else "CANCELED" if fak else "LIVE"
                self.orders[o["fake_id"]] = {"id": o["fake_id"], "status": status, "size_matched": str(matched),
                                             "price": str(o["price"]), "original_size": str(o["size"]),
                                             "associate_trades": [f"t-{o['fake_id'][-6:]}"] if matched else []}
                out.append({"success": True, "errorMsg": "", "orderID": o["fake_id"], "status": status.lower()})
            if self.post == "timeout":
                raise TimeoutError("timed out")
            return 200, out
        if (method, path) == ("DELETE", "/order"):
            if self.dead:
                raise TimeoutError("timed out")
            o = self.orders.get(b["orderID"])
            if o and o["status"] == "LIVE":
                o["status"] = "CANCELED"
                return 200, {"canceled": [b["orderID"]], "not_canceled": {}}
            return 200, {"canceled": [], "not_canceled": {b["orderID"]: "order not found or already canceled"}}
        if (method, path) == ("DELETE", "/cancel-all"):
            ids = [i for i, o in self.orders.items() if o["status"] == "LIVE"]
            for i in ids:
                self.orders[i]["status"] = "CANCELED"
            return 200, {"canceled": ids, "not_canceled": {}}
        if method == "GET" and path.startswith("/data/order/"):
            if self.dead:
                raise TimeoutError("timed out")
            o = self.orders.get(path.rsplit("/", 1)[1])
            return (200, dict(o)) if o else (404, {"error": "order not found"})
        if (method, path) == ("GET", "/data/orders"):
            return 200, {"data": [{"id": i} for i, o in self.orders.items() if o["status"] == "LIVE"], "next_cursor": "LTE="}
        if (method, path) == ("GET", "/balance-allowance"):
            return 200, {"balance": "50000000", "allowances": {"0xexchange": "1000000"}}
        if (method, path) == ("POST", "/v1/heartbeats"):
            return 200, {"heartbeat_id": "hb-1"}
        if (method, path) == ("GET", "/time"):
            return 200, 1_700_000_000
        raise AssertionError(f"unexpected {method} {path}")


def live(tmp_path, on=True):
    cfg = tmp_path / "live.json"
    cfg.write_text(json.dumps({"live": on}))
    return cfg, {**CREDS, "ROSTER_LIVE": "1"}


def make(tmp_path, venue=None, trip=None, journal=None):
    cfg, env = live(tmp_path)
    venue = venue if venue is not None else Venue()
    client = L2Client(transport=venue, config_path=cfg, env=env, cli_live=True)
    trips = []
    r = LiveRouter({MARKET.cid: MARKET}, client, FakeSigner(), trip or (lambda *a: trips.append(a)),
                   journal or tmp_path / "journal.jsonl")
    r.trips_seen = trips
    return r, venue


def intent(token="Y", side="BUY", price=0.40, size=5.0, kind="maker", expiry=NOW + 3_600_000):
    return Intent("ladder-maker", MARKET.cid, token, side, price, size, kind, expiry, 0.45, "test")


def journal_ops(path):
    return [json.loads(x) for x in pathlib.Path(path).read_text().splitlines() if x.startswith("{") and x.endswith("}")]


def same_as_replay(r):
    return {i: o.status for i, o in replay(r.path).orders.items()} == {i: o.status for i, o in r.state.orders.items()}


# ---- B1 guard -------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("cfg_on, env_on, cli_on", list(itertools.product((True, False), repeat=3)))
def test_b1_three_flags(tmp_path, cfg_on, env_on, cli_on):
    cfg = tmp_path / "live.json"
    cfg.write_text(json.dumps({"live": cfg_on}))
    on, missing = live_enabled(cfg, {"ROSTER_LIVE": "1" if env_on else "0"}, cli_on)
    assert on is (cfg_on and env_on and cli_on)
    assert len(missing) == 3 - sum((cfg_on, env_on, cli_on))
    assert ('"live": true in live.json' in missing) is (not cfg_on) and ("ROSTER_LIVE=1" in missing) is (not env_on) \
        and ("--live" in missing) is (not cli_on)


@pytest.mark.parametrize("cfg_text, roster_live", [('{"live": "true"}', "1"), ('{"live": 1}', "1"), ('{"live": true}', "true"),
                                                   ('{"live": true}', "yes"), (None, "1"), ("not json", "1")])
def test_b1_near_misses_are_off(tmp_path, cfg_text, roster_live):
    cfg = tmp_path / "live.json"
    if cfg_text is not None:
        cfg.write_text(cfg_text)
    on, missing = live_enabled(cfg, {"ROSTER_LIVE": roster_live}, True)
    assert not on and missing


def test_b1_live_json_ships_off():
    assert json.loads((ROOT / "trader/live/live.json").read_text()) == {"live": False}
    assert live_enabled(env={"ROSTER_LIVE": "1"}, cli_live=True) == (False, ['"live": true in live.json'])


# ---- B2 every authenticated call is guarded at call time ------------------------------------------------------------
CALLS = [("heartbeat", ("",)), ("post_order", ({}, "GTD", True)), ("post_orders", ([], True)), ("cancel", ("x",)),
         ("cancel_all", ()), ("get_order", ("x",)), ("open_orders", ()), ("balance_allowance", ()), ("server_time", ())]


@pytest.mark.parametrize("off", ["config", "env", "cli"])
def test_b2_flag_off_blocks_every_call(tmp_path, off):
    cfg, env = live(tmp_path, on=off != "config")
    if off == "env":
        env["ROSTER_LIVE"] = "0"
    venue = Venue()
    c = L2Client(transport=venue, config_path=cfg, env=env, cli_live=off != "cli")
    for name, args in CALLS:
        with pytest.raises(LiveGuardError):
            getattr(c, name)(*args)
    assert venue.calls == []
    with pytest.raises(LiveGuardError):
        LiveRouter({}, c, FakeSigner(), print, tmp_path / "j.jsonl")
    assert not (tmp_path / "j.jsonl").exists()


def test_b2_flag_turned_off_after_construction(tmp_path):
    cfg, env = live(tmp_path)
    venue = Venue()
    c = L2Client(transport=venue, config_path=cfg, env=env, cli_live=True)
    assert c.heartbeat("") == {"heartbeat_id": "hb-1"} and venue.n("POST") == 1
    for flip, undo in ((lambda: env.update(ROSTER_LIVE="0"), lambda: env.update(ROSTER_LIVE="1")),
                       (lambda: cfg.write_text('{"live": false}'), lambda: cfg.write_text('{"live": true}')),
                       (lambda: setattr(c, "cli_live", False), lambda: setattr(c, "cli_live", True))):
        flip()
        with pytest.raises(LiveGuardError):
            c.cancel_all()
        undo()
    assert len(venue.calls) == 1
    r, _ = make(tmp_path, venue)
    r.client.env["ROSTER_LIVE"] = "0"  # off between construction and the post
    with pytest.raises(LiveGuardError):
        r.submit(intent(), NOW)
    assert venue.n("POST", "/orders") == 0
    assert [e["op"] for e in journal_ops(r.path)] == ["new", "cancel"]  # journaled, then marked never sent


def test_b2_code_read_one_transport_call_after_the_guard():
    src = (ROOT / "trader/live/clob.py").read_text(encoding="utf-8")
    assert src.count("self.transport(") == 1
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "_req")
    body = ast.get_source_segment(src, fn)
    assert body.index("self.require_live()") < body.index("Creds.from_env") < body.index("self.transport(")
    run = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.AsyncFunctionDef) and n.name == "run")
    seg = ast.get_source_segment(src, run)
    assert seg.index("require_live(") < seg.index("async with connect(")
    assert "urlopen" not in src.split("def http(")[0] and src.count("urlopen(") == 1  # only inside http(), the transport


# ---- B3 HMAC vectors, header names, masked creds --------------------------------------------------------------------
def test_b3_hmac_vectors_and_header_names(tmp_path):
    c = Creds.from_env(CREDS)
    h = l2_headers(c, "DELETE", "/cancel-all", "", 1_700_000_000)
    assert h["POLY_SIGNATURE"] == VEC_CANCEL_ALL and h["POLY_TIMESTAMP"] == "1700000000"
    assert tuple(h) == ("POLY_ADDRESS", "POLY_SIGNATURE", "POLY_TIMESTAMP", "POLY_API_KEY", "POLY_PASSPHRASE")
    assert l2_headers(c, "POST", "/v1/heartbeats", '{"heartbeat_id":""}', 1_700_000_000)["POLY_SIGNATURE"] == VEC_HEARTBEAT
    venue = Venue()
    cfg, env = live(tmp_path)
    L2Client(transport=venue, config_path=cfg, env=env, cli_live=True, wall=lambda: 1_700_000_000).heartbeat("")
    assert venue.calls[0][2] == {"heartbeat_id": ""}


def test_b3_venue_error_never_carries_credentials(tmp_path):
    cfg, env = live(tmp_path)
    c = L2Client(transport=lambda *a: (400, {"error": f"bad owner {CREDS['POLY_API_KEY']} / {SECRET}"}), config_path=cfg,
                 env=env, cli_live=True)
    with pytest.raises(clob.VenueError) as e:
        c.cancel_all()
    assert e.value.status == 400 and CREDS["POLY_API_KEY"] not in str(e.value) and SECRET not in str(e.value)


def test_b3_creds_repr_and_missing():
    c = Creds.from_env(CREDS)
    for text in (repr(c), str(c), repr([c])):
        assert all(v not in text for v in CREDS.values())
    with pytest.raises(CredentialsMissing) as e:
        Creds.from_env({k: v for k, v in CREDS.items() if k != "POLY_API_SECRET"})
    assert "POLY_API_SECRET" in str(e.value) and SECRET not in str(e.value)


# ---- B4 GTD ---------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("case, requested, end, start, want", [
    ("start unknown", NOW + 60 * MIN, NOW + 120 * MIN, None, NOW + 60 * MIN),
    ("start ahead", NOW + 60 * MIN, NOW + 120 * MIN, NOW + 30 * MIN, NOW + 25 * MIN),
    ("start passed", NOW + 60 * MIN, NOW + 120 * MIN, NOW - MIN, NOW + 60 * MIN),
    ("requested earliest", NOW + 10 * MIN, NOW + 120 * MIN, NOW + 30 * MIN, NOW + 10 * MIN),
    ("close earliest", NOW + 60 * MIN, NOW + 20 * MIN, NOW + 50 * MIN, NOW + 18 * MIN),
    ("whole seconds, floored", NOW + 10 * MIN + 999, NOW + 120 * MIN, None, NOW + 10 * MIN),
    ("2 min + margin exactly", NOW + 150_000, NOW + 120 * MIN, None, NOW + 150_000),
    ("under 2 min + margin", NOW + 149_000, NOW + 120 * MIN, None, None),
    ("close too near", NOW + 60 * MIN, NOW + 4 * MIN, None, None),
    ("start too near", NOW + 60 * MIN, NOW + 120 * MIN, NOW + 7 * MIN, None),
])
def test_b4_gtd(case, requested, end, start, want):
    assert gtd_expiry_ms(requested, end, start, NOW) == want, case


def test_b4_router_sends_gtd_seconds_and_refuses_short(tmp_path):
    r, venue = make(tmp_path)
    r.starts[MARKET.cid] = NOW + 30 * MIN
    o = r.submit(intent(expiry=NOW + 60 * MIN), NOW)
    assert o.status == "open" and o.intent.expiry_ms == NOW + 25 * MIN
    assert venue.calls[0][2][0]["order"]["expiration"] == str((NOW + 25 * MIN) // 1000)
    assert venue.calls[0][2][0]["orderType"] == "GTD"
    short = r.submit(intent(expiry=NOW + 2 * MIN), NOW)
    assert short.status == "rejected" and "2 min" in r.reasons[short.order_id] and venue.n("POST") == 1
    t = r.submit(intent(kind="taker", price=0.52, expiry=NOW + 5_000), NOW)
    assert venue.calls[-1][2][0]["orderType"] == "FAK" and venue.calls[-1][2][0]["order"]["expiration"] == "0"
    assert t.status == "open"


# ---- B5 write-ahead -------------------------------------------------------------------------------------------------
def test_b5_new_line_on_disk_before_the_post(tmp_path):
    j = tmp_path / "journal.jsonl"
    r, venue = make(tmp_path, Venue(journal=j), journal=j)
    r.submit_batch([intent(price=0.40 - k * 0.01) for k in range(3)], NOW)
    assert venue.wal_checked == 1 and len(venue.posted_ids()) == 3
    new = [e for e in journal_ops(j) if e["op"] == "new"]
    assert [e["id"] for e in new] == venue.posted_ids()
    assert all(e["queue_ahead"] == 0.0 and e["order_type"] == "GTD" and e["expiration"] > 0 for e in new)


def test_b5_queue_ahead_from_the_book(tmp_path):
    r, _ = make(tmp_path)
    r.on_book(Book("Y", [(0.45, 30.0), (0.40, 12.5)], [(0.51, 9.0)], NOW), NOW)
    r.submit(intent(price=0.40), NOW)
    assert next(e for e in journal_ops(r.path) if e["op"] == "new")["queue_ahead"] == 12.5
    cross = r.submit(intent(price=0.52), NOW)  # the post-only pre-check against the cached book
    assert cross.status == "rejected" and "cross" in r.reasons[cross.order_id]


def test_b5_failed_journal_write_raises_and_posts_nothing(tmp_path, monkeypatch):
    r, venue = make(tmp_path)

    def broken(fd):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr("os.fsync", broken)
    with pytest.raises(OSError):
        r.submit(intent(), NOW)
    assert venue.n("POST") == 0


# ---- B6 acks, rejections, timeouts, poll ----------------------------------------------------------------------------
def test_b6_ack_rejection_timeout(tmp_path):
    r, venue = make(tmp_path)
    assert r.submit(intent(price=0.40), NOW).status == "open"
    venue.post = "reject"
    rej = r.submit(intent(price=0.39), NOW)
    assert rej.status == "cancelled" and r.reasons[rej.order_id] == "INVALID_ORDER_MIN_TICK_SIZE"
    venue.post = "http400"
    bad = r.submit(intent(price=0.38), NOW)
    assert bad.status == "cancelled" and "HTTP 400" in r.reasons[bad.order_id]
    venue.post = "http500"
    assert r.submit(intent(side="BUY", token="N", price=0.30), NOW).status == "unknown"
    venue.post = "timeout"
    assert r.submit(intent(price=0.37), NOW).status == "unknown"
    for t in range(0, 40_000, 1_000):  # rejected orders are terminal: poll never touches them
        r.poll(NOW + t)
    assert max(collections.Counter(venue.posted_ids()).values()) == 1
    assert rej.order_id not in str([c for c in venue.calls if c[0] != "POST"])
    assert same_as_replay(r)


def test_b6_poll_at_5s_cancels_then_queries(tmp_path):
    r, venue = make(tmp_path)
    venue.post = "timeout"  # the venue has the order; the answer is lost
    o = r.submit(intent(), NOW)
    assert o.status == "unknown"
    n = len(venue.calls)
    r.poll(NOW + 4_999)
    assert len(venue.calls) == n
    r.poll(NOW + 5_000)
    assert venue.calls[n:] == [("DELETE", "/order", {"orderID": o.order_id}), ("GET", f"/data/order/{o.order_id}", None)]
    assert o.status == "cancelled"  # the cancel by id worked; the query answered CANCELED
    assert [e["op"] for e in journal_ops(r.path)] == ["new", "unknown", "cancel"]


def test_b6_query_matched_journals_fills(tmp_path):
    r, venue = make(tmp_path)
    venue.post, venue.maker_fill = "timeout", 1.0
    o = r.submit(intent(price=0.40, size=7), NOW)
    fills = r.poll(NOW + 5_000)
    assert [(f.size, f.price, f.maker, f.fee) for f in fills] == [(7.0, 0.40, True, 0.0)]
    assert o.status == "filled" and r.positions["Y"] == 7.0
    fill = next(e for e in journal_ops(r.path) if e["op"] == "fill")
    assert fill["trades"] == venue.orders[o.order_id]["associate_trades"]
    venue.post, venue.taker_fill["BUY"] = "timeout", 0.6  # a FAK partly matched, rest killed: venue CANCELED
    t = r.submit(intent(token="N", price=0.55, size=5, kind="taker", expiry=NOW + 10_000), NOW)
    tf = r.poll(NOW + 5_000)
    assert [(f.size, f.maker) for f in tf] == [(3.0, False)] and tf[0].fee == pytest.approx(fee(3.0, 0.55, 0.07))
    assert t.status == "cancelled" and t.filled == 3.0 and same_as_replay(r)


def test_b6_acked_taker_resolved_by_query(tmp_path):
    r, venue = make(tmp_path)
    t = r.submit(intent(price=0.51, kind="taker", expiry=NOW + 10_000), NOW)
    assert t.status == "open"
    assert r.poll(NOW + 4_000) == [] and t.status == "open"
    assert [f.size for f in r.poll(NOW + 5_000)] == [5.0] and t.status == "filled"


# ---- B7 dropped-ack drill -------------------------------------------------------------------------------------------
def test_b7_dropped_ack_drill(tmp_path):
    k = RiskKernel(secret=HUMAN_KEY, nonce_path=None)
    venue = Venue()
    r, _ = make(tmp_path, venue, trip=k.trip)
    venue.post, venue.dead = "swallow", True
    o = r.submit(intent(), NOW)
    assert o.status == "unknown"
    halted_at = None
    for t in range(0, 40_001, 500):
        r.poll(NOW + t)
        if halted_at is None and k.state.value == "HALTED":
            halted_at = t
    assert halted_at is not None and halted_at <= 30_000
    assert [(x["scope"], x["level"], x["source"]) for x in k.trips] == [("global", "HALTED", "router")]
    assert venue.n("DELETE", "/cancel-all") == 1
    again = r.submit(intent(price=0.39), NOW + 40_000)
    assert again.status == "rejected" and "unknown" in r.reasons[again.order_id]
    assert r.submit(intent(side="BUY", token="N", price=0.3), NOW + 40_000).status == "unknown"  # other token: allowed
    assert venue.posted_ids().count(o.order_id) == 1
    venue.dead = False  # reconcile after the cancel-all: absent at the venue -> resolved
    r.reconcile_venue(r.client.open_orders(), NOW + 41_000)
    assert o.status == "cancelled" and same_as_replay(r)


# ---- B8 kill -9 mid-batch drill -------------------------------------------------------------------------------------
@pytest.mark.parametrize("k", [1, 3, 5])
def test_b8_kill9_mid_batch(tmp_path, k):
    j = tmp_path / "journal.jsonl"
    r, _ = make(tmp_path, journal=j)
    r.submit_batch([intent(price=0.40 - n * 0.01) for n in range(5)], NOW)
    news = [x for x in j.read_text().splitlines() if '"op":"new"' in x]
    j.write_bytes(("".join(x + "\n" for x in news[:k - 1]) + news[k - 1][:len(news[k - 1]) // 2]).encode())
    venue2 = Venue()
    r2, _ = make(tmp_path, venue2, journal=j)
    assert [o.status for o in r2.state.orders.values()] == ["unknown"] * (k - 1)
    assert same_as_replay(r2)
    old = set(r2.state.orders)
    r2.poll(NOW + 6_000)  # cancel + query by id; the fake never saw them (404): still unknown
    again = r2.submit(intent(price=0.20), NOW + 6_000)  # same token and side
    assert again.status == ("rejected" if k > 1 else "open") and venue2.n("DELETE", "/order") == k - 1
    assert not old & set(venue2.posted_ids())  # never posted again
    assert same_as_replay(r2)
    lines = j.read_text().splitlines()
    with pytest.raises(ValueError):
        json.loads(lines[k - 1])  # the torn line stays ignored ...
    assert all(json.loads(x) for x in lines[k:])  # ... and was ended: every later entry is on its own line


def test_b8_restart_marks_inflight_taker_unknown(tmp_path):
    r, venue = make(tmp_path)
    t = r.submit(intent(price=0.51, kind="taker", expiry=NOW + 10_000), NOW)
    assert t.status == "open"
    r2, venue2 = make(tmp_path)
    assert r2.state.orders[t.order_id].status == "unknown" and venue2.calls == [] and same_as_replay(r2)


# ---- B9 user channel and reconciliation -----------------------------------------------------------------------------
def trade(tid, status="MATCHED", taker=None, makers=(), size="5", price="0.55"):
    """User-channel trade message, field names as docs.polymarket.com (user channel) documents them."""
    return {"event_type": "trade", "type": "TRADE", "id": tid, "status": status, "taker_order_id": taker or "0xsomeone",
            "market": "0xcid", "asset_id": "Y", "side": "BUY", "size": size, "price": price, "outcome": "YES",
            "matchtime": "1700000001", "timestamp": "1700000001", "last_update": "1700000001",
            "owner": "owner-uuid", "trade_owner": "owner-uuid",
            "maker_orders": [{"order_id": oid, "matched_amount": amt, "price": p, "asset_id": "Y", "outcome": "YES",
                              "owner": "owner-uuid"} for oid, amt, p in makers]}


def order_msg(oid, typ):
    return {"event_type": "order", "type": typ, "id": oid, "market": "0xcid", "asset_id": "Y", "side": "BUY",
            "price": "0.40", "original_size": "10", "size_matched": "0", "outcome": "YES", "owner": "owner-uuid",
            "associate_trades": None, "timestamp": "1700000001"}


def test_b9_user_events(tmp_path):
    k = RiskKernel(secret=HUMAN_KEY, nonce_path=None)
    r, _ = make(tmp_path, trip=k.trip)
    maker = r.submit(intent(price=0.40, size=10), NOW)
    taker = r.submit(intent(token="N", price=0.55, kind="taker", expiry=NOW + 10_000), NOW)
    f = r.on_user_event(trade("t1", makers=[(maker.order_id, "4", "0.40")]))
    assert [(x.order_id, x.size, x.price, x.maker, x.fee) for x in f] == [(maker.order_id, 4.0, 0.40, True, 0.0)]
    assert r.on_user_event(trade("t1", "MINED", makers=[(maker.order_id, "4", "0.40")])) == []
    assert r.on_user_event(trade("t1", "CONFIRMED", makers=[(maker.order_id, "4", "0.40")])) == []
    f2 = r.on_user_event(trade("t2", taker=taker.order_id))
    assert [(x.size, x.price, x.maker) for x in f2] == [(5.0, 0.55, False)] and f2[0].fee == pytest.approx(fee(5, 0.55, 0.07))
    assert maker.status == "partial" and maker.filled == 4.0 and taker.status == "filled"
    r.on_user_event(order_msg(maker.order_id, "CANCELLATION"))
    assert maker.status == "cancelled"
    fills = [e for e in journal_ops(r.path) if e["op"] == "fill"]
    assert [e["trades"] for e in fills] == [["t1"], ["t2"]]
    r2, _ = make(tmp_path)  # restart: trade ids survive, a replayed message adds nothing
    assert r2.on_user_event(trade("t2", "CONFIRMED", taker=taker.order_id)) == [] and r2.trades == {"t1", "t2"}
    assert k.state.value == "ACTIVE"
    r.on_user_event(trade("t3", "FAILED", makers=[(maker.order_id, "1", "0.40")]))
    assert k.state.value == "ACTIVE" and k.scopes[MARKET.cid].value == "HALTED"  # only its market, not everything
    assert k.trips[-1]["source"] == "reconciler"
    assert r.on_user_event(trade("t3", makers=[(maker.order_id, "1", "0.40")])) == []  # a MATCHED after FAILED books nothing
    r.on_user_event(trade("t9", "FAILED", taker="0xnotours"))
    assert k.state.value == "HALTED"  # a FAILED we cannot tie to our markets still halts globally
    assert same_as_replay(r)


def test_b9_failed_trade_reverts_its_fills(tmp_path):
    """A trade that matched off-chain then FAILED on-chain (ghost fill): position, cash and order back as before."""
    k = RiskKernel(secret=HUMAN_KEY, nonce_path=None)
    r, _ = make(tmp_path, trip=k.trip)
    maker = r.submit(intent(price=0.40, size=10), NOW)
    taker = r.submit(intent(token="N", price=0.55, kind="taker", expiry=NOW + 10_000), NOW)
    r.on_user_event(trade("t1", makers=[(maker.order_id, "4", "0.40")]))
    r.on_user_event(trade("t2", taker=taker.order_id))
    cash_after_t1 = r.state.cash + 5 * 0.55 + fee(5, 0.55, 0.07)
    r2, _ = make(tmp_path, trip=k.trip)  # the trade-id -> fills map survives a restart
    assert r2.on_user_event(trade("t2", "FAILED", taker=taker.order_id)) == []
    assert r2.positions["N"] == 0 and r2.positions["Y"] == 4.0
    assert r2.state.cash == pytest.approx(cash_after_t1) and r2.state.cost["N"] == pytest.approx(0)
    t = r2.state.orders[taker.order_id]
    assert t.filled == 0 and t.status == "cancelled" and r2.state.orders[maker.order_id].status == "partial"
    assert k.state.value == "ACTIVE" and k.scopes[MARKET.cid].value == "HALTED"
    assert r2.on_user_event(trade("t2", "FAILED", taker=taker.order_id)) == [] and r2.positions["N"] == 0  # once only
    assert [e["op"] for e in journal_ops(r2.path)].count("revert") == 1
    r3, _ = make(tmp_path)
    assert r3.positions == r2.positions and r3.state.cash == pytest.approx(r2.state.cash) and same_as_replay(r3)


def test_b9_placement_acks_an_unknown_order(tmp_path):
    r, venue = make(tmp_path)
    venue.post = "timeout"
    o = r.submit(intent(), NOW)
    r.on_user_event(order_msg(o.order_id, "PLACEMENT"))
    assert o.status == "open"


def test_b9_reconcile_and_confirm_zero_open(tmp_path):
    k = RiskKernel(secret=HUMAN_KEY, nonce_path=None)
    r, venue = make(tmp_path, trip=k.trip)
    a = r.submit(intent(price=0.40), NOW)
    b = r.submit(intent(price=0.39), NOW)
    venue.orders[b.order_id]["status"] = "CANCELED"  # gone at the venue, still open in our journal
    venue.orders["0xstranger"] = {"id": "0xstranger", "status": "LIVE", "size_matched": "0"}  # at the venue only
    n = len(venue.calls)
    out = r.reconcile_venue(r.client.open_orders(), NOW + 1_000)
    assert len(out) == 2 and "0xstranger" in out[0] and b.order_id in out[1]
    assert k.trips[-1]["source"] == "reconciler" and k.state.value == "HALTED"
    assert ("DELETE", "/order", {"orderID": "0xstranger"}) in venue.calls[n:]
    assert ("GET", f"/data/order/{b.order_id}", None) in venue.calls[n:] and b.status == "cancelled"
    assert r.confirm_zero_open() is False  # a: open at the venue and in the journal
    r.cancel(a.order_id, NOW + 2_000)
    assert a.status == "cancelled" and r.confirm_zero_open() is True
    venue.orders["0xlate"] = {"id": "0xlate", "status": "LIVE"}  # venue not empty, journal empty
    assert r.confirm_zero_open() is False
    venue.post, venue.dead = "swallow", True  # journal not empty (unknown, unresolvable), venue empty
    venue.orders["0xlate"]["status"] = "CANCELED"
    r.submit(intent(token="N", price=0.30), NOW + 3_000)
    assert r.confirm_zero_open() is False
    assert same_as_replay(r)


# ---- B10 paper rules carry over -------------------------------------------------------------------------------------
def test_b10_paper_rules(tmp_path):
    r, venue = make(tmp_path)
    o = r.submit(intent(price=0.4567, size=7.789), NOW)
    assert (o.intent.price, o.intent.size) == (0.45, 7.78) and venue.calls[-1][2][0]["order"]["size"] == 7.78
    s = r.submit(intent(side="SELL", price=0.4512, size=5), NOW)  # SELL rounds up (passive), and holds no shares
    assert s.intent.price == 0.46 and s.status == "rejected" and "sell exceeds" in r.reasons[s.order_id]
    assert r.submit(intent(size=5.009), NOW).intent.size == 5.0
    small = r.submit(intent(size=4.999), NOW)
    assert small.status == "rejected" and "minimum" in r.reasons[small.order_id]
    assert r.submit(intent(price=0.005), NOW).status == "rejected"  # rounds to 0.00: outside the tick range
    with pytest.raises(ValueError):
        r.submit_batch([intent()] * 16, NOW)
    assert len(r.submit_batch([intent(price=0.30)] * 15, NOW)) == 15
    posts = venue.n("POST")
    venue.post = "timeout"
    assert r.submit(intent(token="N", price=0.30), NOW).status == "unknown"
    venue.post = "ack"
    blocked = r.submit(intent(token="N", price=0.29), NOW)
    assert blocked.status == "rejected" and "unknown" in r.reasons[blocked.order_id]
    assert venue.n("POST") == posts + 1
    assert r.submit(intent(token="N", side="SELL", price=0.9, size=5), NOW).status == "rejected"  # no N held
    big = r.submit(intent(price=0.44, size=12), NOW)
    r.on_user_event(trade("tf", makers=[(big.order_id, "12", "0.44")]))  # hold 12 Y
    assert r.submit(intent(side="SELL", price=0.60, size=5), NOW).status == "open"
    over = r.submit(intent(side="SELL", price=0.61, size=7.01), NOW)
    assert over.status == "rejected" and "not already offered" in r.reasons[over.order_id]
    assert r.submit(intent(side="SELL", price=0.61, size=7), NOW).status == "open"
    assert r.submit(intent(side="SELL", price=0.62, size=5), NOW).status == "rejected"  # all 12 offered


def test_b10_batch_offers_count_within_the_batch(tmp_path):
    r, _ = make(tmp_path)
    o = r.submit(intent(price=0.45, size=10), NOW)
    r.on_user_event(trade("tf", makers=[(o.order_id, "10", "0.45")]))
    two = r.submit_batch([intent(side="SELL", price=0.62, size=6), intent(side="SELL", price=0.63, size=6)], NOW)
    assert [x.status for x in two] == ["open", "rejected"]


# ---- B11 doctor -----------------------------------------------------------------------------------------------------
def run_doctor(tmp_path, capsys, venue, args, on=True, book=BOOK):
    cfg, env = live(tmp_path, on)
    t = [NOW]
    client = L2Client(transport=venue, config_path=cfg, env=env, cli_live=True)
    signer = FakeSigner()
    code = doctor.main(["--live", "--cid", MARKET.cid, "--config", str(cfg), "--journal", str(tmp_path / "j.jsonl"),
                        *args], env=env, client=client, signer=signer, market=lambda cid: MARKET,
                       book=lambda tok: book, get=lambda *a, **k: {"blocked": False}, clock=lambda: t[0],
                       sleep=lambda s: t.__setitem__(0, t[0] + int(s * 1000)))
    return code, json.loads(capsys.readouterr().out), signer


def test_b11_no_flags_dry_run(tmp_path, capsys):
    venue = Venue()
    code, out, signer = run_doctor(tmp_path, capsys, venue, ["--step", "all"], on=False)
    assert code == 2 and out["dry_run"] and set(out["plan"]) == {"wallet", "deep", "roundtrip"}
    assert venue.calls == [] and signer.n == 0 and not (tmp_path / "j.jsonl").exists()


def test_b11_all_pass(tmp_path, capsys):
    venue = Venue()
    code, out, _ = run_doctor(tmp_path, capsys, venue, ["--step", "all"])
    assert code == 0 and out["pass"] and list(out["steps"]) == ["wallet", "deep", "roundtrip"]
    assert all(s["pass"] for s in out["steps"].values())
    assert out["steps"]["wallet"]["balance_usd"] == 50.0 and out["steps"]["deep"]["venue_after"] == "CANCELED"
    assert out["steps"]["roundtrip"]["residual"] == 0.0 and out["steps"]["roundtrip"]["buy"]["filled"] == 5.0
    assert venue.n("DELETE", "/cancel-all") == 0
    ops = [e["op"] for e in journal_ops(tmp_path / "j.jsonl")]
    assert ops.count("new") == 3 and ops.count("fill") == 2  # every order through the write-ahead journal


def test_b11_deep_order_that_fills_fails_and_cancels_all(tmp_path, capsys):
    venue = Venue()
    venue.maker_fill = 1.0
    code, out, _ = run_doctor(tmp_path, capsys, venue, ["--step", "all"])
    assert code == 1 and out["steps"]["deep"]["pass"] is False and out["steps"]["deep"]["venue_status"] == "MATCHED"
    assert venue.n("DELETE", "/cancel-all") == 1 and out["steps"]["roundtrip"]["skipped"]


def test_b11_round_trip_residual_fails(tmp_path, capsys):
    venue = Venue()
    venue.taker_fill["SELL"] = 0.0
    code, out, _ = run_doctor(tmp_path, capsys, venue, ["--step", "roundtrip"])
    rt = out["steps"]["roundtrip"]
    assert code == 1 and rt["pass"] is False and rt["residual"] == 5.0 and len(rt["sells"]) == 2


def test_b11_cost_above_max_refused_before_any_order(tmp_path, capsys):
    venue = Venue()
    code, out, signer = run_doctor(tmp_path, capsys, venue, ["--step", "roundtrip", "--max-cost", "0.10"])
    rt = out["steps"]["roundtrip"]
    assert code == 1 and "refused" in rt and rt["expected_cost"] == pytest.approx(0.05 + fee(5, 0.51, 0.07) + fee(5, 0.5, 0.07), abs=1e-4)
    assert venue.calls == [] and signer.n == 0


def test_b11_wallet_failures(tmp_path, capsys):
    venue = Venue()
    code, out, _ = run_doctor(tmp_path, capsys, venue, ["--step", "wallet", "--min-balance", "100"])
    assert code == 1 and out["steps"]["wallet"]["pass"] is False and out["steps"]["wallet"]["address_matches"]


def test_b11_snapshot_market_and_public_book(tmp_path):
    row = {"condition_id": "0xcid", "yes_token_id": "Y", "no_token_id": "N", "mode": "crypto-term", "question": "q",
           "rules_sha256": "r", "tick_size": "0.001", "min_order_size": 5, "fee_schedule": {"rate": 0.07},
           "neg_risk": False, "end_time": "2023-11-15T16:00:00Z", "event_slug": "bitcoin-above-on-november-15"}
    (tmp_path / "2023-11-15T000000Z.jsonl").write_text(json.dumps(row) + "\n")
    m = doctor.snapshot_market("0xcid", tmp_path)
    assert (m.tick_size, m.min_size, m.fee_rate, m.end_ms) == (0.001, 5.0, 0.07, 1_700_064_000_000)
    b = doctor.public_book("Y", get=lambda url, params: {"bids": [{"price": "0.1", "size": "1"}, {"price": "0.2", "size": "2"}],
                                                         "asks": [{"price": "0.9", "size": "1"}, {"price": "0.3", "size": "3"}]})
    assert (b.best_bid(), b.best_ask()) == (0.2, 0.3)


# ---- B12 signer -----------------------------------------------------------------------------------------------------
def test_b12_sdk_signer_unavailable_without_sdk(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "py_clob_client_v2.client", None)  # as if not installed
    with pytest.raises(LiveUnavailable, match=re.escape("py-clob-client-v2 not installed: [ops] install 1.2.0 into the "
                                                        "trader user's venv")):
        SdkSigner(env={}).sign(intent(), MARKET, 0, "GTD")


# ---- B13 user channel against a local websocket server --------------------------------------------------------------
def test_b13_user_ws(tmp_path):
    from websockets.asyncio.server import serve
    cfg, env = live(tmp_path)
    subs, events, seen = [], [], []

    async def handler(ws):
        subs.append(json.loads(await ws.recv()))
        await ws.send(json.dumps([order_msg("0xa", "PLACEMENT")]))
        if len(subs) == 1:
            await asyncio.sleep(0.3)
            return  # the server drops the first connection
        await ws.send(json.dumps(trade("t9")))
        await ws.wait_closed()

    async def scenario():
        async with serve(handler, "127.0.0.1", 0) as server:
            url = f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}"
            with pytest.raises(LiveGuardError):  # without the three flags it never connects
                await UserWS(events.append, url=url, config_path=cfg, env={**env, "ROSTER_LIVE": "0"}, cli_live=True).run()
            assert subs == []
            ws = UserWS(events.append, markets=["0xcid"], url=url, config_path=cfg, env=env, cli_live=True, backoff_s=(0.3,))
            task = asyncio.create_task(ws.run())
            for _ in range(500):
                if not seen or seen[-1] != ws.connected:
                    seen.append(ws.connected)
                if seen[-3:] == [True, False, True] and any(e["event_type"] == "trade" for e in events):
                    break
                await asyncio.sleep(0.01)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())
    assert seen[-3:] == [True, False, True]
    assert len(subs) == 2 and subs[0] == {"auth": {"apiKey": CREDS["POLY_API_KEY"], "secret": SECRET,
                                                   "passphrase": CREDS["POLY_API_PASSPHRASE"]},
                                          "markets": ["0xcid"], "type": "user"}
    assert [e["event_type"] for e in events][:2] == ["order", "order"] and any(e["event_type"] == "trade" for e in events)


# ---- B14 no secrets, no loop import ---------------------------------------------------------------------------------
OWNED = ("trader/live/clob.py", "trader/live/router.py", "trader/live/live.json", "tools/live_tools/doctor.py",
         "tests/phase2/test_live_exec.py", "reports/phase2_execution.md")


def test_b14_no_secret_in_owned_paths_and_no_loop_import():
    pat = re.compile(r"0x[0-9a-fA-F]{64}|(?i:(secret|passphrase|api_key)\w*['\"]?\s*[:=]\s*['\"][^'\"]+['\"])")
    for rel in OWNED:
        p = ROOT / rel
        if p.exists():
            assert not pat.search(p.read_text(encoding="utf-8")), rel
    for p in (ROOT / "trader/live").glob("*.py"):
        assert not re.search(r"^\s*(from trader\.loop|import trader\.loop|from trader import loop)", p.read_text(encoding="utf-8"), re.M), p


# ---- drill numbers for reports/phase2_execution.md: python -m tests.phase2.test_live_exec ---------------------------
if __name__ == "__main__":
    import contextlib
    import logging
    import io
    import tempfile

    logging.disable(logging.WARNING)  # the dead-venue drills log every failed poll call

    def tmp():
        return pathlib.Path(tempfile.mkdtemp())

    def drill_dropped_ack():
        k, venue = RiskKernel(secret=HUMAN_KEY, nonce_path=None), Venue()
        r, _ = make(tmp(), venue, trip=k.trip)
        venue.post, venue.dead = "swallow", True
        o = r.submit(intent(), NOW)
        halted = next(t for t in range(0, 40_001, 500) if r.poll(NOW + t) is not None and k.state.value == "HALTED")
        retry = r.submit(intent(price=0.39), NOW + halted)
        venue.dead = False
        r.reconcile_venue(r.client.open_orders(), NOW + 41_000)
        return {"status_after_post": "unknown", "halted_at_s": halted / 1000, "trips": k.trips,
                "cancel_all_sent": venue.n("DELETE", "/cancel-all"), "retry_same_token_side": retry.status,
                "posts_of_that_id": venue.posted_ids().count(o.order_id), "after_reconcile": o.status}

    def drill_kill9(k=3):
        d = tmp()
        j = d / "journal.jsonl"
        r, _ = make(d, journal=j)
        r.submit_batch([intent(price=0.40 - n * 0.01) for n in range(5)], NOW)
        news = [x for x in j.read_text().splitlines() if '"op":"new"' in x]
        j.write_bytes(("".join(x + "\n" for x in news[:k - 1]) + news[k - 1][:len(news[k - 1]) // 2]).encode())
        venue2 = Venue()
        r2, _ = make(d, venue2, journal=j)
        old = set(r2.state.orders)
        r2.poll(NOW + 6_000)
        again = r2.submit(intent(price=0.20), NOW + 6_000)
        return {"batch": 5, "new_lines_kept": k - 1, "torn": 1, "statuses_after_restart": sorted(
            o.status for o in r2.state.orders.values() if o.order_id in old), "reposted": len(old & set(venue2.posted_ids())),
            "posts_after_restart": venue2.n("POST"), "new_order_same_side": again.status, "replay_equals_memory": same_as_replay(r2)}

    def drill_rejection():
        r, venue = make(tmp())
        venue.post = "reject"
        o = r.submit(intent(), NOW)
        for t in range(0, 40_000, 1_000):
            r.poll(NOW + t)
        return {"status": o.status, "reason": r.reasons[o.order_id], "posts_of_that_id": venue.posted_ids().count(o.order_id)}

    def drill_doctor(setup, args):
        d, venue = tmp(), Venue()
        setup(venue)
        cfg, env = live(d)
        t = [NOW]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = doctor.main(["--live", "--cid", MARKET.cid, "--config", str(cfg), "--journal", str(d / "j.jsonl"), *args],
                               env=env, client=L2Client(transport=venue, config_path=cfg, env=env, cli_live=True),
                               signer=FakeSigner(), market=lambda cid: MARKET, book=lambda tok: BOOK,
                               get=lambda *a, **kw: {"blocked": False}, clock=lambda: t[0],
                               sleep=lambda s: t.__setitem__(0, t[0] + int(s * 1000)))
        out = json.loads(buf.getvalue())
        return {"exit": code, "steps": {s: v.get("pass") for s, v in out.get("steps", {}).items()},
                "cancel_all_sent": venue.n("DELETE", "/cancel-all"), "venue_calls": len(venue.calls), "detail": out}

    res = {"dropped_ack": drill_dropped_ack(), "kill9_mid_batch": drill_kill9(), "venue_rejection": drill_rejection(),
           "doctor_dry_run": drill_doctor(lambda v: None, ["--step", "all", "--config", "missing.json"]),
           "doctor_all_pass": drill_doctor(lambda v: None, ["--step", "all"]),
           "doctor_deep_fills": drill_doctor(lambda v: setattr(v, "maker_fill", 1.0), ["--step", "all"]),
           "doctor_residual": drill_doctor(lambda v: v.taker_fill.update(SELL=0.0), ["--step", "roundtrip"]),
           "doctor_cost_refused": drill_doctor(lambda v: None, ["--step", "roundtrip", "--max-cost", "0.10"])}
    for name, v in res.items():
        detail = v.pop("detail", None)
        print(f"{name}: {json.dumps(v, default=str)}")
        if name in ("doctor_all_pass", "doctor_residual", "doctor_cost_refused") and detail:
            print("  " + json.dumps(detail["steps"], default=str)[:900])


# ---- #8: one kept-open connection for live orders (13 Oct) ----------------------------------------------------------
class _Conn:
    def __init__(self, log, fail=False, close=False):
        self.log, self.fail, self.close_after, self.closed, self.sock = log, fail, close, False, self
        self.opts = []

    def connect(self):
        self.log.append("connect")

    def setsockopt(self, *a):
        self.opts.append(a)

    def settimeout(self, t):
        pass

    def request(self, method, path, body=None, headers=None):
        if self.fail:
            raise ConnectionResetError("reset")
        self.log.append((method, path, body))

    def getresponse(self):
        conn = self
        class R:
            status, will_close = 200, conn.close_after
            def read(self):
                return b'{"ok": true}'
        return R()

    def close(self):
        self.closed = True


def test_keepalive_reuses_one_connection_and_reconnects_when_idle_or_broken():
    log, now, fails = [], [0.0], []
    conns = []

    def connect(host, timeout):
        c = _Conn(log, fail=bool(fails and fails.pop()))
        conns.append(c)
        return c
    ka = clob.KeepAlive(connect=connect, clock=lambda: now[0])
    assert ka("POST", "https://clob.example/orders", {}, '{"a":1}') == (200, {"ok": True})
    assert ka("GET", "https://clob.example/time?x=1", {}) == (200, {"ok": True})
    assert log.count("connect") == 1 and log[-1] == ("GET", "/time?x=1", None)        # second call: no new handshake
    assert (socket.IPPROTO_TCP, socket.TCP_NODELAY, 1) in conns[0].opts
    now[0] += clob.KeepAlive.IDLE_S + 1                                                # idle: the server may have closed it
    ka("GET", "https://clob.example/time", {})
    assert log.count("connect") == 2 and conns[0].closed
    fails.append(True)
    now[0] += clob.KeepAlive.IDLE_S + 1
    with pytest.raises(ConnectionResetError):                                          # no retry: the router decides
        ka("POST", "https://clob.example/orders", {}, "{}")
    assert conns[2].closed and sum(1 for x in log if x[0] == "POST") == 1
    ka("GET", "https://clob.example/time", {})                                         # a fresh connection after the error
    assert log.count("connect") == 4


def test_keepalive_drops_a_connection_the_server_closes():
    log = []
    ka = clob.KeepAlive(connect=lambda h, t: _Conn(log, close=True))
    ka("GET", "https://clob.example/time", {})
    ka("GET", "https://clob.example/time", {})
    assert log.count("connect") == 2


def test_l2client_defaults_to_the_keepalive_transport():
    assert isinstance(L2Client().transport, clob.KeepAlive)


def test_b9_matchtime_seconds_or_milliseconds(tmp_path):
    r, _ = make(tmp_path)
    a = r.submit(intent(token="N", price=0.55, kind="taker", expiry=NOW + 10_000), NOW)
    b = r.submit(intent(token="Y", price=0.55, kind="taker", expiry=NOW + 10_000), NOW)
    secs = r.on_user_event({**trade("s1", taker=a.order_id), "matchtime": "1700000001"})
    ms = r.on_user_event({**trade("m1", taker=b.order_id), "matchtime": "1794494834585"})   # as sent on 12 Nov
    assert secs[0].ts_ms == 1_700_000_001_000 and ms[0].ts_ms == 1_794_494_834_585


def test_b9_reads_the_documented_match_time_field(tmp_path):
    r, _ = make(tmp_path)
    a = r.submit(intent(token="N", price=0.55, kind="taker", expiry=NOW + 10_000), NOW)
    msg = {k: v for k, v in trade("d1", taker=a.order_id).items() if k not in ("matchtime", "timestamp")}
    f = r.on_user_event({**msg, "match_time": "1794494834585"})
    assert f[0].ts_ms == 1_794_494_834_585


def test_order_timing_log_records_each_step_and_our_trade_events(tmp_path):
    r, _ = make(tmp_path)
    a = r.submit(intent(token="N", price=0.55, kind="taker", expiry=NOW + 10_000), NOW)
    r.on_user_event(trade("tm1", taker=a.order_id))
    r.on_user_event(trade("tm1", "CONFIRMED", taker=a.order_id))    # later statuses are timed too
    r.on_user_event(trade("other"))                                  # not ours: not logged
    rows = [json.loads(x) for x in (tmp_path / "order_timing.jsonl").read_text().splitlines()]
    post = rows[0]
    assert post["kind"] == "post" and post["decision_ms"] == NOW and len(post["sign_ms"]) == 1
    assert post["enter_ms"] <= post["signed_ms"] <= post["journaled_ms"] <= post["post_start_ms"] <= post["post_end_ms"]
    assert post["orders"][0]["id"] == a.order_id and post["orders"][0]["limit"] == 0.55 and post["response"] is not None
    assert [x["kind"] for x in rows[1:]] == ["trade_event", "trade_event"]


def test_sub_dollar_marketable_buy_is_refused_here_and_its_partner_still_posts(tmp_path):
    """16 Nov: the venue answers 400 for a whole batch when one marketable BUY is under $1 (size x limit), which used
    to cancel the valid other leg too. The router now refuses the small one itself; the other goes out alone."""
    r, venue = make(tmp_path)
    small = intent(token="N", price=0.14, kind="taker", expiry=NOW + 10_000)          # 5 x 0.14 = $0.70
    good = intent(token="Y", price=0.67, kind="taker", expiry=NOW + 10_000)           # 5 x 0.67 = $3.35
    a, b = r.submit_batch([small, good], NOW)
    assert a.status == "rejected" and "minimum" in r.reasons[a.order_id]
    assert b.status == "open" and [e["op"] for e in journal_ops(r.path)] == ["new", "ack"]
    # 18 Nov: $1.0005 is over the minimum but not whole cents: the venue refuses it ("maker amount supports a max
    # accuracy of 2 decimals"), so the router now refuses it here; 6.8 x 0.15 = $1.02 goes out
    bad = r.submit(intent(token="N", price=0.15, size=6.67, kind="taker", expiry=NOW + 10_000), NOW)   # $1.0005
    assert bad.status == "rejected" and "whole cents" in r.reasons[bad.order_id]
    ok = r.submit(intent(token="N", price=0.15, size=6.8, kind="taker", expiry=NOW + 10_000), NOW)    # $1.02
    assert ok.status == "open"
