"""WP2-A tests (A1-A12): heartbeat warden, freeze / network-cut / clock-skew / failed-audit-write drills, dead-man,
SNTP clock gate, home-PC kill script. No network: the autouse guard lets sockets reach loopback only (the kill script's
local fake CLOB). `python -m tests.phase2.test_heartbeat` prints the drill numbers quoted in reports/phase2_safety.md."""
import ast
import base64
import json
import logging
import pathlib
import re
import socket
import struct
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

from tools.live_tools import kill_all
from trader.audit import AuditLog, AuditWriteError
from trader.contracts import Book, Decision, Intent, KernelContext, MarketInfo, Order, TradingState
from trader.kernel import PRIVILEGED, RiskKernel
from trader.live import clock
from trader.live.clock import ClockGate, clock_gate, measure, offset_from_packet, sntp_offset
from trader.live.heartbeat import DeadMan, HeartbeatWarden, freeze_drill, health_failures

A, R, H = TradingState.ACTIVE, TradingState.REDUCING, TradingState.HALTED
ROOT = pathlib.Path(__file__).resolve().parents[2]
NOW = 1_700_000_000_000
LOOPBACK = ("127.0.0.1", "::1", "localhost")
_connect, _sendto = socket.socket.connect, socket.socket.sendto


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def connect(self, addr):
        if addr[0] not in LOOPBACK:
            raise RuntimeError(f"network disabled in unit tests ({addr[0]})")
        return _connect(self, addr)

    def sendto(self, data, *rest):  # UDP (SNTP) never calls connect
        if rest[-1][0] not in LOOPBACK:
            raise RuntimeError(f"network disabled in unit tests ({rest[-1][0]})")
        return _sendto(self, data, *rest)
    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "sendto", sendto)


# ---- A1 health_failures --------------------------------------------------------------------------------------------
def order(tok, status="open"):
    return Order(f"o-{tok}", Intent("ladder-maker", "0xc", tok, "BUY", 0.4, 5, "maker", NOW + 3_600_000, 0.45, "t"),
                 status)


def healthy(**over):
    kw = dict(now_ms=NOW, tick_ms=150, ws_connected=True, reconcile_clean=True,
              open_orders=[order("Y"), order("N", "filled")],  # a terminal order needs no book
              books={"Y": Book("Y", [(0.4, 10)], [(0.6, 10)], NOW - 1_000)},
              feed_age_ms={"polymarket": 500, "binance:BTC": 200, "dvol:BTC": 60_000},
              journal_ok=True, audit_ok=True, clock_offset_ms=12.0, state=A)
    return {**kw, **over}


def test_a1_healthy_and_boundaries_pass():
    assert health_failures(**healthy()) == []
    assert health_failures(**healthy(tick_ms=2_000, clock_offset_ms=-1_000, state=R, feed_age_ms={"new-feed": 10_000},
                                     books={"Y": Book("Y", [], [], NOW - 30_000)})) == []


@pytest.mark.parametrize("over, check", [
    (dict(tick_ms=2_001), "tick"),
    (dict(ws_connected=False), "user_ws"),
    (dict(reconcile_clean=False), "reconcile"),
    (dict(books={"Y": Book("Y", [(0.4, 10)], [(0.6, 10)], NOW - 30_001)}), "book"),
    (dict(books={}), "book"),
    (dict(open_orders=[order("Z", "unknown")]), "book"),
    (dict(feed_age_ms={"binance:BTC": 5_001}), "feed"),
    (dict(feed_age_ms={"new-feed": 10_001}), "feed"),
    (dict(journal_ok=False), "journal"),
    (dict(audit_ok=False), "audit"),
    (dict(clock_offset_ms=1_001), "clock"),
    (dict(clock_offset_ms=-1_500), "clock"),
    (dict(clock_offset_ms=None), "clock"),
    (dict(state=H), "halted"),
], ids=["tick>2s", "ws-down", "reconcile-dirty", "book-stale", "no-book", "unknown-order-no-book", "feed-stale",
        "unknown-feed-10s", "journal-failed", "audit-failed", "clock>1s", "clock<-1s", "clock-unknown", "halted"])
def test_a1_each_check_fails_alone(over, check):
    f = health_failures(**healthy(**over))
    assert len(f) == 1 and f[0].startswith(check + ":"), f


# ---- A2 / A3 warden --------------------------------------------------------------------------------------------------
def test_a2_sends_only_when_healthy_and_chains_ids():
    calls = []

    def send(hb_id):
        calls.append(hb_id)
        return {"heartbeat_id": f"hb{len(calls)}"}

    def down(hb_id):
        raise ConnectionError("venue down")
    w = HeartbeatWarden(send, lambda: None, lambda: True)
    assert w.end_of_tick(0, []) is True
    assert w.end_of_tick(1_000, ["user_ws: disconnected"]) is False
    assert w.end_of_tick(2_000, []) is True and calls == ["", "hb1"]
    w.send = down
    assert w.end_of_tick(3_000, []) is False and w.errors == 1 and w.last_error == "send: ConnectionError"
    w.send = send
    assert w.end_of_tick(4_000, []) is True and calls[-1] == "hb2" and w.sent == 3


def test_a3_halt_cancels_every_2s_until_confirmed():
    cancels, confirms = [], []
    w = HeartbeatWarden(lambda i: {}, lambda: cancels.append(t), lambda: confirms.append(t) or len(cancels) >= 3)
    for t in range(0, 12_001, 500):
        w.on_halted(t)
    assert cancels == [0, 2_000, 4_000]
    assert confirms == list(range(0, 4_001, 500))  # on every call until True, then never again
    assert not w.stopped


def test_a3_unconfirmed_halt_latches_stopped_at_10s_until_rearm():
    cancels, sent = [], []
    w = HeartbeatWarden(lambda i: sent.append(i) or {"heartbeat_id": "x"}, lambda: cancels.append(t), lambda: False)
    for t in range(0, 9_501, 500):
        w.on_halted(t)
    assert not w.stopped
    t = 10_000
    w.on_halted(t)
    assert w.stopped and cancels == [0, 2_000, 4_000, 6_000, 8_000, 10_000]
    assert w.end_of_tick(10_500, []) is False and sent == []  # all-healthy input, still no heartbeat
    w.rearm()
    assert w.end_of_tick(11_000, []) is True and sent == [""]


def test_a3_cancel_all_error_counts_as_not_confirmed():
    calls = []

    def cancel_all():
        calls.append(t)
        raise TimeoutError("venue")
    w = HeartbeatWarden(lambda i: {}, cancel_all, lambda: True)
    t = 0
    assert w.on_halted(0) is False and w.errors == 1 and w.last_error == "halt: TimeoutError"
    w2 = HeartbeatWarden(lambda i: {}, cancel_all, lambda: False)
    calls.clear()
    for t in range(0, 10_001, 500):
        w2.on_halted(t)
    assert w2.stopped and calls == list(range(0, 10_001, 2_000))


def test_a3_next_halt_episode_cancels_again():
    cancels = []
    w = HeartbeatWarden(lambda i: {}, lambda: cancels.append(1), lambda: True)
    assert w.on_halted(0) and w.on_halted(500) and len(cancels) == 1
    w.end_of_tick(60_000, [])  # a tick outside HALTED (after the human reset) ends the episode
    assert w.on_halted(61_000) and len(cancels) == 2


# ---- A4 drills on a fake venue ----------------------------------------------------------------------------------------
class Clock:
    def __init__(self):
        self.t = 0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += round(s * 1000)


class FakeVenue:
    """Cancels every order once no heartbeat has arrived for cancel_after_ms (the venue's heartbeat contract)."""

    def __init__(self, clk, orders=3, auto_cancel=True, cancel_after_ms=10_000):
        self.clk, self.orders, self.auto_cancel, self.after = clk, orders, auto_cancel, cancel_after_ms
        self.last_hb, self.cut, self.ids = None, False, []

    def heartbeat(self, hb_id):
        if self.cut:
            raise ConnectionError("network cut")
        self.open_count()  # a late heartbeat does not undo a cancel already due
        self.last_hb = self.clk.t
        self.ids.append(hb_id)
        return {"heartbeat_id": f"hb-{len(self.ids)}"}

    def open_count(self):
        if self.auto_cancel and self.last_hb is not None and self.clk.t - self.last_hb >= self.after:
            self.orders = 0
        return self.orders


def run_freeze(auto_cancel=True, cancel_after_ms=10_000):
    clk = Clock()
    v = FakeVenue(clk, auto_cancel=auto_cancel, cancel_after_ms=cancel_after_ms)
    w = HeartbeatWarden(v.heartbeat, lambda: None, lambda: v.open_count() == 0)
    return freeze_drill(w, [], v.open_count, clk.now, clk.sleep, ticks_before_freeze=5)


def run_network_cut(cancel_after_ms=10_000, budget_ms=15_000):
    """The loop keeps ticking healthy, but every heartbeat send raises from t0 (cable pulled)."""
    clk = Clock()
    v = FakeVenue(clk, cancel_after_ms=cancel_after_ms)
    w = HeartbeatWarden(v.heartbeat, lambda: None, lambda: v.open_count() == 0)
    for _ in range(5):
        w.end_of_tick(clk.now(), [])
        clk.sleep(1)
    v.cut, t0, sent = True, clk.now(), 0
    while v.open_count() and clk.now() - t0 <= budget_ms:
        sent += w.end_of_tick(clk.now(), [])
        clk.sleep(0.5)
    zero = clk.now() - t0 if v.open_count() == 0 else None
    return {"passed": zero is not None and zero <= budget_ms, "zero_after_ms": zero, "send_errors": w.errors,
            "heartbeats_sent_after_cut": sent}


@pytest.mark.parametrize("after", [10_000, 15_000])
def test_a4_freeze_zero_open_within_15s(after):
    r = run_freeze(cancel_after_ms=after)
    assert r["passed"] and r["heartbeats_sent"] == 5 and r["zero_after_ms"] <= 15_000, r


def test_a4_freeze_negative_control_fails():
    r = run_freeze(auto_cancel=False)
    assert r["passed"] is False and r["zero_after_ms"] is None, r


def test_a4_freeze_with_nothing_open_proves_nothing():
    clk = Clock()
    w = HeartbeatWarden(lambda i: {}, lambda: None, lambda: True)
    assert freeze_drill(w, lambda: [], lambda: 0, clk.now, clk.sleep, 3)["passed"] is False


@pytest.mark.parametrize("after", [10_000, 15_000])
def test_a4_network_cut_zero_open_within_15s(after):
    r = run_network_cut(cancel_after_ms=after)
    assert r["passed"] and r["send_errors"] > 0 and r["heartbeats_sent_after_cut"] == 0, r


# ---- A5 dead-man -------------------------------------------------------------------------------------------------------
PING = "https://hc-ping.example/unit-test-check-uuid"


def test_a5_deadman(monkeypatch, caplog):
    calls = []
    monkeypatch.delenv("ROSTER_DEADMAN_URL", raising=False)
    off = DeadMan(get=lambda u, t: calls.append(u))
    assert off.maybe_ping(0, True) is False and calls == []

    monkeypatch.setenv("ROSTER_DEADMAN_URL", PING)
    d = DeadMan(get=lambda u, t: calls.append((u, t)))
    ticks = [(0, True), (30_000, True), (59_999, True), (60_000, False), (61_000, True), (100_000, True),
             (121_000, True)]
    got = [d.maybe_ping(t, sent) for t, sent in ticks]
    assert got == [True, False, False, False, True, False, True] and calls == [(PING, 5)] * 3

    def unreachable(u, t):
        raise OSError(f"cannot reach {u}")
    with caplog.at_level(logging.DEBUG):
        e = DeadMan(get=unreachable)
        assert e.maybe_ping(0, True) is False and e.errors == 1
        assert e.maybe_ping(1_000, True) is False and e.errors == 1  # an error still spends the 60 s slot
    assert "hc-ping.example" in caplog.text
    assert PING not in caplog.text + repr(d) + str(d) + repr(e) + repr(got)


# ---- A6 SNTP ---------------------------------------------------------------------------------------------------------
T1 = 1_700_000_000.0


def ntp(t):
    t += 2_208_988_800
    return struct.pack("!II", int(t), int(t % 1 * 2 ** 32))


def packet(t2, t3, stratum=2, mode=4, origin=bytes(8)):
    return bytes([4 << 3 | mode, stratum, 6, 0xEC]) + bytes(20) + origin + ntp(t2) + ntp(t3)


def ticks():
    it = iter((T1, T1 + 0.020))
    return lambda: next(it)


def fake_udp(skew=None, stratum=2, echo=True):
    """Socket factory for a server whose clock runs `skew` s ahead (None: the query times out)."""
    class S:
        def __init__(self, *a):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def settimeout(self, t):
            pass

        def sendto(self, data, addr):
            self.req = data

        def recvfrom(self, n):
            if skew is None:
                raise socket.timeout("timed out")
            t2 = T1 + skew + 0.010
            return packet(t2, t2 + 0.001, stratum, origin=self.req[40:48] if echo else bytes(8)), ("192.0.2.1", 123)
    return S


def test_a6_offset_from_packet_and_rejects():
    off, delay = offset_from_packet(packet(T1 + 0.150, T1 + 0.152), T1, T1 + 0.010)
    assert abs(off - 146) < 1 and abs(delay - 8) < 1
    with pytest.raises(ValueError, match="Kiss"):
        offset_from_packet(packet(T1, T1, stratum=0), T1, T1)
    with pytest.raises(ValueError, match="mode"):
        offset_from_packet(packet(T1, T1, mode=3), T1, T1)
    with pytest.raises(ValueError, match="transmit"):
        offset_from_packet(packet(T1, T1)[:40] + bytes(8), T1, T1)


def test_a6_sntp_query_and_measure():
    off, delay = sntp_offset("x", sock=fake_udp(0.250), clock=ticks())
    assert abs(off - 250.5) < 1 and abs(delay - 19) < 1
    with pytest.raises(ValueError, match="echo"):
        sntp_offset("x", sock=fake_udp(0.250, echo=False), clock=ticks())
    cfg = {"a": dict(skew=0.1), "b": dict(skew=None), "c": dict(skew=0.3), "d": dict(skew=0.0, stratum=0)}

    def q(s):
        return sntp_offset(s, sock=fake_udp(**cfg[s]), clock=ticks())
    assert abs(measure(("a", "b", "c", "d"), query=q) - 200.5) < 1  # median of the two that answered
    assert measure(("b", "d"), query=q) is None
    assert measure(query=lambda s: sntp_offset(s, sock=fake_udp(None), clock=ticks())) is None  # default servers


def test_clob_offset_ms():
    urls, t = [], iter((NOW, NOW + 100))

    def get(url, **kw):
        urls.append(url)
        return NOW // 1000 + 1
    assert clock.clob_offset_ms(get=get, clock=lambda: next(t)) == (NOW + 1_500) - (NOW + 50)
    assert urls == ["https://clob.polymarket.com/time"]


# ---- A7 clock gate and the real kernel -------------------------------------------------------------------------------
M = MarketInfo("0xc", "Y", "N", "crypto-term", "BTC above 100k?", "r", 0.01, 5, 0.0, False, NOW + 86_400_000,
               "BTC@x", "BTC", 100_000.0, "strike", "binance:BTC/USDT")
CTX = KernelContext(NOW, {"0xc": M}, {"Y": Book("Y", [(0.4, 50)], [(0.6, 50)], NOW)}, {"Y": 10.0}, [], {}, 20.0, {})
BUY = Intent("ladder-maker", "0xc", "Y", "BUY", 0.40, 5, "maker", NOW + 3_600_000, 0.45, "test")    # adds risk
SELL = Intent("ladder-maker", "0xc", "Y", "SELL", 0.60, 5, "maker", NOW + 3_600_000, 0.55, "test")  # reduces


@pytest.mark.parametrize("off, want", [(50, A), (100, A), (150, R), (1_000, R), (1_500, H)])
def test_a7_offset_levels(off, want):
    assert clock_gate(off, NOW, NOW)[0] == want and clock_gate(-off, NOW, NOW)[0] == want


def test_a7_missing_stale_and_clob():
    assert clock_gate(None, NOW, NOW)[0] == R
    assert clock_gate(float("nan"), NOW, NOW)[0] == R
    assert clock_gate(20, None, NOW)[0] == R
    assert clock_gate(20, NOW - 600_001, NOW)[0] == R
    assert clock_gate(20, NOW - 600_000, NOW)[0] == A
    assert clock_gate(20, NOW, NOW, clob_offset_ms=2_500)[0] == H
    assert clock_gate(20, NOW, NOW, clob_offset_ms=-2_000)[0] == A


def test_a7_clock_gate_trips_real_kernel_once_per_rise():
    k = RiskKernel(nonce_path=None)
    g = ClockGate(k)
    g.apply(*clock_gate(20, NOW, NOW))
    assert k.trips == []
    g.apply(*clock_gate(150, NOW, NOW))
    g.apply(*clock_gate(160, NOW, NOW))
    assert k.state == R and len(k.trips) == 1
    assert k.check(BUY, CTX).reason.startswith("REDUCING")
    assert not k.check(SELL, CTX).reason.startswith("REDUCING")
    g.apply(*clock_gate(1_500, NOW, NOW))
    g.apply(*clock_gate(-1_600, NOW, NOW))
    assert k.state == H and len(k.trips) == 2
    assert k.check(BUY, CTX) == k.check(SELL, CTX) == Decision(False, "HALTED: no new orders")
    g.apply(*clock_gate(20, NOW, NOW))  # clock recovered: the kernel stays latched (human reset only)
    assert k.state == H and len(k.trips) == 2
    assert [t["level"] for t in k.trips] == ["REDUCING", "HALTED"]
    assert all(t["source"] in PRIVILEGED for t in k.trips)


def run_clock_skew():
    """Skew injected at a fake SNTP server -> measure -> clock_gate -> ClockGate -> real kernel."""
    k = RiskKernel(nonce_path=None)
    g, rows = ClockGate(k), []
    for skew in (0.020, 0.250, 1.500, 0.020):
        off = measure(("a", "b", "c"), query=lambda s: sntp_offset(s, sock=fake_udp(skew), clock=ticks()))
        level, why = clock_gate(off, NOW, NOW)
        g.apply(level, why)
        rows.append({"skew_ms": round(skew * 1000), "measured_ms": round(off, 1), "gate": level.value,
                     "kernel": k.state.value, "buy": k.check(BUY, CTX).reason.split(":")[0]})
    return rows


def test_a7_clock_skew_injection_drill():
    assert [(r["gate"], r["kernel"]) for r in run_clock_skew()] == [
        ("ACTIVE", "ACTIVE"), ("REDUCING", "REDUCING"), ("HALTED", "HALTED"), ("ACTIVE", "HALTED")]


# ---- A8 failed audit write -------------------------------------------------------------------------------------------
def test_a8_failed_audit_write_stops_heartbeat(tmp_path):
    path = tmp_path / "audit.jsonl"
    audit = AuditLog(path, clock=lambda: NOW)
    audit.append("tick", {"n": 1})
    path.unlink()
    path.mkdir()  # the audit file can no longer be written
    try:
        audit.append("tick", {"n": 2})
        audit_ok = True
    except AuditWriteError:
        audit_ok = False
    assert audit_ok is False
    sent = []
    w = HeartbeatWarden(lambda i: sent.append(i) or {}, lambda: None, lambda: True)
    f = health_failures(**healthy(audit_ok=audit_ok))
    assert f == ["audit: last audit write failed"] and w.end_of_tick(NOW, f) is False and sent == []
    k = RiskKernel(nonce_path=None)  # Phase 1's AuditWriteError path trips HALTED (source "audit")
    k.trip("global", "audit write failed", "audit")
    f = health_failures(**healthy(audit_ok=False, state=k.state))
    assert k.state == H and w.end_of_tick(NOW + 1_000, f) is False and w.on_halted(NOW + 1_000) and sent == []


# ---- A9 kill script --------------------------------------------------------------------------------------------------
SECRET = base64.b64encode(b"roster-phase2-test-secret-000000").decode()  # the orchestrator's test vector, not a key
CREDS = dict(zip(kill_all.L2, ("0xunit-test-address", "unit-test-key-id", SECRET, "unit-test-pass")))
VECTOR = "qFXxB7_xYdSIihsVXzMqNm2Mr246XAiifhdxm1qQmPE="


def quiet(capsys):
    """stdout + stderr so far, asserting no credential value or signature leaked into them."""
    cap = capsys.readouterr()
    text = cap.out + cap.err
    assert not any(v in text for v in (*CREDS.values(), VECTOR)), text
    return text


@pytest.fixture
def live_cfg(tmp_path):
    p = tmp_path / "live.json"
    p.write_text('{"live": true}', encoding="utf-8")
    return p


def test_a9_dry_run_unless_all_three_flags(tmp_path, live_cfg, capsys):
    off, text = tmp_path / "off.json", tmp_path / "str.json"
    off.write_text('{"live": false}', encoding="utf-8")
    text.write_text('{"live": "true"}', encoding="utf-8")
    cases = [(["--config", str(live_cfg)], "1"), (["--live", "--config", str(live_cfg)], None),
             (["--live", "--config", str(live_cfg)], "true"), (["--live", "--config", str(off)], "1"),
             (["--live", "--config", str(text)], "1"), (["--live", "--config", str(tmp_path / "none.json")], "1")]
    calls = []
    for argv, flag in cases:
        env = dict(CREDS) if flag is None else {**CREDS, "ROSTER_LIVE": flag}
        assert kill_all.main(argv, env=env, transport=lambda *a: calls.append(a)) == 2
    assert calls == []
    out = quiet(capsys)
    assert out.count("DRY RUN") == 6 and "DELETE /cancel-all" in out and "POLY_SIGNATURE" in out


def test_a9_refusals_exit_3(live_cfg, capsys):
    calls, live = [], ["--live", "--config", str(live_cfg)]
    on = {**CREDS, "ROSTER_LIVE": "1"}
    partial = {k: v for k, v in on.items() if k != "POLY_API_PASSPHRASE"}
    for argv, env in [(live, {**on, "POLY_PRIVATE_KEY": "set"}), (live, {**on, "POLY_PRIVATE_KEY": ""}),
                      (live, partial), (live + ["--host", "http://clob.example"], on)]:
        assert kill_all.main(argv, env=env, transport=lambda *a: calls.append(a)) == 3
    assert calls == []
    err = quiet(capsys)
    assert "POLY_PRIVATE_KEY is set" in err and "POLY_API_PASSPHRASE" in err and "https" in err


@pytest.fixture
def clob():
    """Local fake CLOB on loopback: open orders until DELETE /cancel-all (unless sticky); GET /data/orders pages 2."""
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def reply(self, obj):
            body = json.dumps(obj).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_DELETE(self):
            self.server.seen.append(("DELETE", self.path, self.headers))
            gone = list(self.server.orders)
            if not self.server.sticky:
                self.server.orders = []
            self.reply({"canceled": gone, "not_canceled": {}})

        def do_GET(self):
            self.server.seen.append(("GET", self.path, self.headers))
            at = int(base64.b64decode(parse_qs(urlsplit(self.path).query)["next_cursor"][0]))
            nxt = at + 2 if at + 2 < len(self.server.orders) else -1
            self.reply({"data": self.server.orders[at:at + 2], "next_cursor": base64.b64encode(b"%d" % nxt).decode()})

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    srv.orders, srv.sticky, srv.seen = ["o1", "o2", "o3"], False, []
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    srv.url = f"http://127.0.0.1:{srv.server_address[1]}"
    yield srv
    srv.shutdown()
    srv.server_close()


def test_a9_live_against_fake_server_confirms_zero(clob, live_cfg, capsys):
    argv = ["--live", "--config", str(live_cfg), "--host", clob.url]
    assert kill_all.main(argv, env={**CREDS, "ROSTER_LIVE": "1"}, wall=lambda: 1_700_000_000) == 0
    method, path, headers = clob.seen[0]
    assert (method, path) == ("DELETE", "/cancel-all") and headers["POLY_SIGNATURE"] == VECTOR
    assert headers["POLY_TIMESTAMP"] == "1700000000" and headers["POLY_API_KEY"] == CREDS["POLY_API_KEY"]
    assert headers["POLY_ADDRESS"] == CREDS["POLY_ADDRESS"] and headers["POLY_PASSPHRASE"] == CREDS["POLY_API_PASSPHRASE"]
    assert clob.seen[1][0] == "GET" and clob.seen[1][1].startswith("/data/orders?") and len(clob.seen) == 2
    out = quiet(capsys)
    assert "canceled 3" in out and "open orders: 0" in out and "CONFIRMED: zero open orders" in out


def test_a9_venue_never_empties_exit_1_within_15s(clob, live_cfg, capsys):
    clob.sticky = True
    clk = Clock()
    argv = ["--live", "--config", str(live_cfg), "--host", clob.url]
    rc = kill_all.main(argv, env={**CREDS, "ROSTER_LIVE": "1"}, mono=lambda: clk.t / 1000, sleep=clk.sleep)
    deletes = [s for s in clob.seen if s[0] == "DELETE"]
    assert rc == 1 and clk.t <= 15_000 and len(deletes) == 8  # cancel-all at 0, 2, ... 14 s
    out = quiet(capsys)
    assert "open orders: 3" in out and "NOT CONFIRMED" in out  # 3 orders counted over 2 pages


def test_a9_kill_all_is_stdlib_only():
    tree = ast.parse((ROOT / "tools/live_tools/kill_all.py").read_text(encoding="utf-8"))
    mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert mods and mods <= sys.stdlib_module_names, mods - sys.stdlib_module_names


# ---- A10 no secrets in the owned paths -------------------------------------------------------------------------------
OWNED = ("trader/live/heartbeat.py", "trader/live/clock.py", "tools/live_tools/kill_all.py",
         "tests/phase2/test_heartbeat.py", "reports/phase2_safety.md")


def test_a10_no_secret_in_owned_paths():
    pat = re.compile(r"0x[0-9a-fA-F]{64}|(?i:(secret|passphrase|api_key)\w*['\"]?\s*[:=]\s*['\"][^'\"]+['\"])")
    hits = [(p, m.group(0)) for p in OWNED if (ROOT / p).exists()
            for m in pat.finditer((ROOT / p).read_text(encoding="utf-8"))]
    assert hits == []


if __name__ == "__main__":
    for name, r in [("freeze, venue cancels 10 s after the last heartbeat", run_freeze()),
                    ("freeze, venue cancels 15 s after the last heartbeat", run_freeze(cancel_after_ms=15_000)),
                    ("freeze negative control (venue auto-cancel off)", run_freeze(auto_cancel=False)),
                    ("network cut, venue cancels after 10 s", run_network_cut()),
                    ("network cut, venue cancels after 15 s", run_network_cut(cancel_after_ms=15_000))]:
        print(f"{name}: {r}")
    for row in run_clock_skew():
        print(f"clock skew: {row}")
