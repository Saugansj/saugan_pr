"""WW-D acceptance tests: trader/loop.py wiring behind trader/features.py flags. Fake market data, no network,
files only under tmp_path. D1 (flags off = Phase 1) is checked against the audited loop frozen before WW-D edited it
(data/trader/wiring_D/loop_phase1_before.py)."""
import importlib.util
import json
import math
import random
import socket

import pytest

import common
from tools.clearance_cli import write as sign_record
from trader import features
from trader.contracts import Book, Intent, MarketInfo, TradingState
from trader.engines import ladder
from trader.kernel import STRATEGIES, clearance_key
from trader.loop import Trader, main, registrations

KEY = "test-human-key"
T = 1_790_843_000_000                      # 2026-10-01 08:23 UTC
LAD = MarketInfo("L1", "L1Y", "L1N", "crypto-term", "Will the price of Bitcoin be above $84,000 on October 1?", "r1",
                 0.01, 5.0, 0.07, False, T + 6 * 3_600_000, "BTC@2026-10-01T16:00Z", "BTC", 84000.0, "strike",
                 "binance:BTC/USDT")
SPD = MarketInfo("S5", "S5U", "S5D", "crypto-fast", "Bitcoin Up or Down - October 1, 4:22AM-4:27AM ET", "r2",
                 0.01, 5.0, 0.07, False, T + 4 * 60_000, "BTC-5m@2026-10-01T08:22Z", "BTC", None, "updown",
                 "chainlink:BTC/USD")
SPO = MarketInfo("P1", "P1Y", "P1N", "sports-pregame", "Will Arsenal win?", "r3", 0.01, 5.0, 0.0, False,
                 T + 30 * 3_600_000, "E0:arsenal:chelsea:2026-10-02", None, None, "moneyline", "")
FRONTIER = common.DATA / "trader" / "wiring_D" / "loop_phase1_before.py"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("network call attempted")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


class FakeMD:
    def __init__(self):
        self.markets = {m.cid: m for m in (LAD, SPD)}
        self.books, self.rtt_ms, self.rows, self.sports_maps = {}, 200.0, {}, {}
        self.ref = {a: {"price": p, "ts_ms": T, "recv_ms": T, "dvol": 35.0, "final": {}} for a, p in
                    (("BTC", 84000.0), ("ETH", 2680.0))}
        self.on_book = self.on_trade = self.on_ref = None
        self.age = 0

    def feed_age_ms(self, now):
        return {f: self.age for f in ("polymarket", "binance:BTC", "binance:ETH", "dvol:BTC", "dvol:ETH", "basis:USDT")}

    def book(self, token, bids, asks, now):
        self.books[token] = Book(token, bids, asks, now)
        self.on_book(self.books[token], now)

    def tick(self, asset, price, now):
        self.ref[asset].update(price=price, ts_ms=now, recv_ms=now)
        self.on_ref(asset, now)

    def set_sports(self, events):
        self.markets[SPO.cid] = SPO
        self.sports_maps = {SPO.cid: {"cid": SPO.cid, "token_yes": SPO.token_yes, "token_no": SPO.token_no,
                                      "event_key": SPO.event_group, "start_ms": T + 28 * 3_600_000, "league": "E0"}}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTER_HUMAN_KEY", KEY)
    for m in (LAD, SPD, SPO):
        sign_record(tmp_path / "advice.db", {"type": "clearance", "key": clearance_key(m), "signer": "test",
                                             "expiry_ms": T + 86_400_000}, KEY)
    return tmp_path


def books(md, now, m=0.50, s=0.58):
    for tok, mid in (("L1Y", m), ("L1N", 1 - m), ("S5U", s), ("S5D", 1 - s)):
        md.book(tok, [(round(mid - 0.02, 2), 100)], [(round(mid + 0.02, 2), 100)], now)


def boot(d, flags=(), cls=Trader, now=T):
    md = FakeMD()
    tr = cls(md, d, fetch=lambda cid: None, **({"features": flags} if flags else {}))
    tr.now = lambda: now
    tr.start(now)
    books(md, now)
    return md, tr


def session(md, tr, seed=7, steps=900):
    """7.5 simulated minutes: a random-walk BTC price with a few 15 bp jumps (btc-speed), drifting books, trades on
    the ladder tokens (maker fills), the loop's 100 ms housekeeping every 500 ms."""
    rng, px, m, s, now = random.Random(seed), 84000.0, 0.50, 0.58, T
    for k in range(steps):
        now = T + k * 500
        tr.now = lambda now=now: now
        if rng.random() < 0.2:
            m, s = min(0.9, max(0.1, m + rng.choice((-0.01, 0.01)))), min(0.9, max(0.1, s + rng.choice((-0.01, 0.01))))
        books(md, now, m, s)  # fresh books every step (the kernel and engines want them < 30-60 s old)
        px *= math.exp(rng.gauss(0, 2e-5)) * (1.0015 if k in (100, 300) else 1.0)
        md.tick("BTC", px, now)
        if rng.random() < 0.3:
            tok = rng.choice(("L1Y", "L1N"))
            md.on_trade(tok, round(rng.uniform(0.3, 0.7), 2), rng.choice((5.0, 50.0)), "SELL", now)
        tr.tick(now)
    return tr.shutdown(now + 1)


def ledger_rows(tr) -> list:
    out = []
    for tbl, body, ev in tr.ledger.db.execute("SELECT tbl, body, event_ms FROM rows ORDER BY id"):
        b = {k: v for k, v in json.loads(body).items() if k not in ("run_id", "pid", "audit_head", "head")}
        out.append((tbl, json.dumps(b, sort_keys=True), None if tbl == "registry" else ev))
    return out


# ---------- flags ----------

def test_features_default_off_file_and_cli(tmp_path):
    assert features.load(tmp_path) == frozenset()
    (tmp_path / "features.json").write_text(json.dumps(["dd7", "touch"]))
    assert features.load(tmp_path, ["heartbeat"]) == {"dd7", "touch", "heartbeat"}
    (tmp_path / "features.json").write_text(json.dumps({"dd7": True, "touch": False}))
    assert features.load(tmp_path) == {"dd7"}
    (tmp_path / "features.json").write_text(json.dumps(["dd8"]))
    with pytest.raises(ValueError, match="dd8"):
        features.load(tmp_path)
    with pytest.raises(SystemExit):
        main(["--paper", "--minutes", "1", "--dir", str(tmp_path), "--enable", "nope"])
    assert set(features.PAPER_SAFE) < set(features.FLAGS)


# ---------- D1: flags off = the audited Phase 1 loop ----------

def test_d1_flags_off_identical_to_phase1_loop(env, tmp_path_factory, monkeypatch):
    if not FRONTIER.exists():
        pytest.skip(f"frozen Phase 1 loop missing: {FRONTIER}")
    spec = importlib.util.spec_from_file_location("loop_phase1_before", FRONTIER)
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    clock = [T]
    monkeypatch.setattr(common, "now_ms", lambda: clock[0])
    res = {}
    for name, cls in (("old", old.Trader), ("new", Trader)):
        d = tmp_path_factory.mktemp(name)
        (d / "advice.db").write_bytes((env / "advice.db").read_bytes())
        md, tr = boot(d, cls=cls)
        out = session(md, tr)
        res[name] = (ledger_rows(tr), (d / "journal.jsonl").read_text(), {k: v for k, v in out.items()
                                                                          if k not in ("run_id", "audit_head")})
    assert res["new"] == res["old"]
    rows, journal, out = res["new"]
    assert out["violations"] == 0 and out["mismatches"] == []
    assert out["counts"].get("order:ladder-maker:maker", 0) > 5 and out["counts"].get("fill:ladder-maker:maker", 0) > 0
    assert out["counts"].get("intent:btc-speed", 0) > 0  # both strategies exercised, not an empty comparison


def test_flags_off_builds_no_wiring(env):
    _, tr = boot(env)
    assert tr.kernel.strategies is STRATEGIES and tr.kernel.features == frozenset() and not tr.ladder.flags
    assert not tr.router.liquidity_once and tr.makers == [] and tr.workers() == []
    assert (tr.warden, tr.keeper, tr.scanner, tr.sports) == (None,) * 4
    assert registrations(frozenset()) == ({}, [])


# ---------- D2 in miniature: every paper-safe flag on, the same session ----------

def test_all_paper_safe_flags_session(env):
    md, tr = boot(env, features.PAPER_SAFE)
    tr.clock_off = 5.0  # the SNTP worker is not run offline
    out = session(md, tr)
    assert out["violations"] == 0 and out["mismatches"] == []
    assert out["counts"]["heartbeat:sent"] > 0
    assert (env / "dd7_samples.json").exists()
    reg, pre = registrations(frozenset(features.PAPER_SAFE))
    assert {"touch", "negrisk-arb", "quote-objective", "markout-cusum", "universe-vol"} <= set(reg)
    for p in pre:
        assert tr.ledger.preregistration(p.get("name") or p["test_id"]) is not None
    tr2 = Trader(FakeMD(), env, fetch=lambda cid: None, features=features.PAPER_SAFE)
    assert tr2.start(T + 600_000) == []  # restart: same registrations, no immutability error, clean reconcile


def test_all_flags_registrations_and_workers(env):
    _, tr = boot(env, set(features.FLAGS) - {"speed_v4", "speed_eth", "speed_v5", "speed_v6", "ref_bybit", "compound", "speed_maker", "speed_v7", "speed_cap70", "speed_v8", "speed_add", "speed_sz", "speed_v9"})  # v3, v4 (ETH is v4), v5, v6 and v7 refuse to share a run
    ws = tr.workers()  # clock, settlement, sports, negrisk (coroutines, not started: no network here)
    assert len(ws) == 4 and {w.cr_code.co_name for w in ws} == {"_worker"}
    for w in ws:
        w.close()
    assert len(tr.makers) == 2 and tr.warden and tr.keeper and tr.scanner
    assert tr.ledger.preregistration("soccer-maker") and tr.ledger.preregistration("latency-e6-v1")
    assert {v["name"] for v in tr.ledger.versions("fast-updown-maker")} == {"fast-updown-maker"}


# ---------- heartbeat ----------

def test_heartbeat_sent_only_when_healthy_and_halt_cancels(env):
    md, tr = boot(env, ("heartbeat",))
    tr.tick(T + 100)
    assert tr.counts["heartbeat:withheld:clock"] == 1 and not tr.counts["heartbeat:sent"]  # no clock reading yet
    tr._clock_measured(300.0, T + 150)
    tr.tick(T + 200)
    assert tr.counts["heartbeat:sent"] == 1
    assert tr.ledger.as_of("clock", 2 ** 62)[0]["offset_ms"] == 300.0
    assert tr.kernel.state == TradingState.ACTIVE  # clock_gate off: the measurement only feeds the health check
    md.age = 120_000
    tr.tick(T + 300)
    assert tr.counts["heartbeat:withheld:feed"] == 1
    md.age = 0
    md.tick("BTC", 84000.0, T + 1000)
    assert tr.router.open_orders()
    tr.kernel.trip("global", "test", "human")
    tr.tick(T + 1100)
    assert not tr.router.open_orders() and tr.counts["heartbeat:withheld:halted"] == 1 and tr.warden.sent == 1


def test_clock_gate_trips_reducing_on_offset(env):
    _, tr = boot(env, ("clock_gate",))
    tr._clock_measured(300.0, T + 100)
    assert tr.kernel.state == TradingState.REDUCING


# ---------- live_risk: pull-on-REDUCING, opens ----------

def test_pull_on_reducing_cancels_risk_increasing_orders(env):
    md, tr = boot(env, ("live_risk",))
    md.tick("BTC", 84000.0, T)
    assert not tr.router.open_orders()  # a 10-share bid is over the $2.50 stress cap on a $50 bankroll
    assert tr.counts["decision:ladder-maker:stress"] > 0
    before = tr.router.submit_batch([Intent(ladder.NAME, "L1", t, "BUY", 0.40, 5.0, "maker", T + 600_000, 0.45,
                                            "quote f=0.5 m=0.5 q=0.5") for t in ("L1Y", "L1N")], T)
    assert all(o.status == "open" for o in before)
    tr.kernel.trip(LAD.event_group, "test", "breaker:x", TradingState.REDUCING)
    tr.pull_reducing(T + 10)
    assert not [o for o in tr.router.open_orders() if o.intent.strategy == ladder.NAME]
    assert tr.counts["pulled:reducing:ladder-maker"] == len(before)
    assert tr.kernel.ref is md.ref and md.held == tr.positions


def test_live_risk_opens_from_prev_noon(env):
    md, tr = boot(env, ("live_risk",))
    ud = MarketInfo("U1", "U1Y", "U1N", "crypto-term", "Bitcoin Up or Down on October 1?", "r4", 0.01, 5.0, 0.07,
                    False, T + 6 * 3_600_000, "BTC@x", "BTC", None, "updown", "binance:BTC/USDT")
    md.markets[ud.cid] = ud
    md.ref["BTC"]["final"][ladder.prev_noon_ms(ud.end_ms) + 60_000] = 83000.0
    tr.wiring_minute(T)
    assert tr.kernel.opens == {"U1": 83000.0}


# ---------- settlement keeper ----------

def fill_yes_and_no(md, tr, merge=True):
    if not merge:
        tr.recon.merge_pairs = lambda now: []
    md.tick("BTC", 84000.0, T)
    for o in list(tr.router.open_orders()):
        if o.intent.strategy == ladder.NAME:
            md.on_trade(o.intent.token_id, round(o.intent.price - 0.05, 2), 50.0, "SELL", T + 1000)


def test_settlement_apply_trips_gap_and_merges(env):
    from trader.live.settlement import Status
    md, tr = boot(env, ("settlement",))
    tr.now = lambda: T + 1000
    fill_yes_and_no(md, tr, merge=False)
    pos = tr.positions()
    assert pos.get("L1Y", 0) > 0 and pos.get("L1N", 0) > 0
    tr.keeper.statuses["X"] = Status(SPD, state="printed")
    tr.keeper._gap = {"X"}
    tr.keeper_trips.append(("X", "settlement mismatch", "breaker:settlement", TradingState.REDUCING))
    tr.settlement_apply(T + 2000)
    assert tr.kernel.scopes["X"] == TradingState.REDUCING and not tr.keeper_trips
    assert tr.ladder.oracle_gap == tr.kernel.printed == {"X"}
    assert tr.counts["fund:merge:approved"] == 1 and tr.ledger.as_of("merges", 2 ** 62)
    assert min(tr.positions().get("L1Y", 0), tr.positions().get("L1N", 0)) == 0  # pairs merged into pUSD
    assert tr.ledger.as_of("settlement_keeper", 2 ** 62)[0]["oracle_gap"] == ["X"]
    assert tr.reconcile(T + 3000, "test") == []


def test_settlement_redeem_is_logged_not_executed(env):
    from trader.live.settlement import Status
    md, tr = boot(env, ("settlement",))
    tr.now = lambda: T + 1000
    md.tick("BTC", 84000.0, T)
    yes = next(o for o in tr.router.open_orders() if o.intent.token_id == "L1Y")
    md.on_trade("L1Y", round(yes.intent.price - 0.05, 2), 50.0, "SELL", T + 1000)
    tr.keeper.statuses["L1"] = Status(LAD, state="resolved", outcome="YES")
    tr.settlement_apply(T + 2000)
    rows = tr.ledger.as_of("fund_intents", 2 ** 62)
    assert [(r["kind"], r["approved"]) for r in rows] == [("redeem", True)] and tr.positions()["L1Y"] > 0


# ---------- sports ----------

def test_sports_cancel_signal_cancels_that_game_only(env):
    md, tr = boot(env, ("sports",))
    tr.sports_apply([], [], T)
    assert tr.kernel.starts[SPO.cid] == T + 28 * 3_600_000 and md.sports_feeds == ("espn",)
    md.book("P1Y", [(0.40, 100)], [(0.44, 100)], T)
    md.tick("BTC", 84000.0, T)
    o = tr.router.submit(Intent("sports-maker", "P1", "P1Y", "BUY", 0.40, 5.0, "maker", T + 3_600_000, 0.42,
                                "f=0.5 m=0.42 q=0.44"), T)
    others = {x.order_id for x in tr.router.open_orders()} - {o.order_id}
    assert o.status == "open" and others
    gs = {"event_key": SPO.event_group, "status": "postponed", "scheduled_start_ms": T + 28 * 3_600_000,
          "recv_ms": T, "league": "E0", "home": "Arsenal", "away": "Chelsea"}
    tr.sports_apply([gs], [], T + 1000)
    assert o.status == "cancelled" and {x.order_id for x in tr.router.open_orders()} == others
    assert tr.ledger.as_of("sports_cancels", 2 ** 62)[0]["reason"] == "postponed"
    tr.ladder_round(T + 2000)  # no sharp odds (keyed SGO is not fetched): the engine pulls, so no sports intents
    assert tr.sports.last_pulls[SPO.cid] and not tr.counts["intent:sports-maker"]


# ---------- negRisk scan ----------

def test_negrisk_scan_rows_only_with_books_plus_one_break_row(env):
    md, tr = boot(env, ("negrisk_scan",))
    row = {"neg_risk": True, "event_slug": "ev", "fees_enabled": False, "end_time": "2026-10-03T00:00:00Z",
           "tick_size": 0.01, "min_order_size": 5, "rules_sha256": "r", "mode": "sports-pregame"}
    tr.scanner.on_snapshot([{**row, "condition_id": f"N{i}", "yes_token_id": f"N{i}Y", "no_token_id": f"N{i}N",
                             "question": f"leg {i}"} for i in range(3)])
    assert list(tr.scanner.events) == ["ev"]
    tr.negrisk_scan(T)
    assert not tr.ledger.as_of("negrisk_scan", 2 ** 62) and tr.counts["negrisk_scan:no_books"] == 1
    md.books["N0Y"] = Book("N0Y", [(0.3, 10)], [(0.32, 10)], T)
    tr.negrisk_scan(T + 60_000)
    del md.books["N0Y"]
    tr.negrisk_scan(T + 120_000)
    tr.negrisk_scan(T + 180_000)
    rows = tr.ledger.as_of("negrisk_scan", 2 ** 62)
    assert len(rows) == 2 and not any(r["eligible"] for r in rows)  # no confirmation: never eligible
    assert not [o for o in tr.router.state.orders.values() if "negrisk" in o.intent.strategy]


# ---------- quote_objective rewards ----------

def test_quote_objective_rewards_from_rows(env):
    md, tr = boot(env, ("quote_objective",))
    md.rows = {"L1": {"reward_min_size": 50, "reward_max_spread": 4.5, "reward_daily_rate": 2.0},
               "S5": {"reward_min_size": 50, "reward_max_spread": 4.5, "reward_daily_rate": 0.0}}
    tr.wiring_minute(T)
    assert tr.ladder.rewards == {"L1": {"min_size": 50, "max_spread": 4.5, "daily_rate": 2.0}}


# ---- speed_maker (20 Oct, profit plan B6) ----------------------------------------------------------------------------
S15 = MarketInfo("S15", "S15U", "S15D", "crypto-fast", "Bitcoin Up or Down - October 1, 4:15AM-4:30AM ET", "r4",
                 0.01, 5.0, 0.07, False, T + 7 * 60_000, "BTC-15m@2026-10-01T08:15Z", "BTC", None, "updown",
                 "chainlink:BTC/USD")
MK = {"speed_maker", "ref_bybit", "speed_only", "maker_realism"}


def maker_signal(env):
    sign_record(env / "advice.db", {"type": "clearance", "key": clearance_key(S15), "signer": "test",
                                    "expiry_ms": T + 86_400_000}, KEY)
    md, tr = boot(env, MK)
    md.markets[S15.cid] = S15
    tr.refresh_makers()
    for k, px in enumerate((84000.0, 84000.0, 84000.0, 84000.0 * math.exp(7e-4))):   # +7 bp in 2 s on the last tick
        now = T + 1000 * (k + 1)
        tr.now = lambda now=now: now
        md.book("S15U", [(0.58, 100)], [(0.62, 100)], now)
        md.book("S15D", [(0.38, 100)], [(0.42, 100)], now)
        md.tick("BTC", px, now)
    [o] = [o for o in tr.router.open_orders() if o.intent.strategy == "btc-speed"]
    return md, tr, o, T + 4000


def test_speed_maker_rests_a_post_only_bid_that_fills_on_a_mirrored_print(env):
    md, tr, o, t = maker_signal(env)
    assert (o.intent.kind, o.intent.token_id, o.intent.price, o.intent.size) == ("maker", "S15U", 0.61, 5.0)
    assert tr.maker_tokens == {"S15U"}
    tr.now = lambda: t + 1000
    md.on_trade("S15D", 0.39, 10.0, "BUY", t + 1000)          # a taker buying Down at 0.39 is selling Up at 0.61 to us
    [f] = tr.router.state.fills
    assert (f.token_id, f.price, f.size, f.maker, f.fee) == ("S15U", 0.61, 5.0, True, 0.0)


def test_speed_maker_ignores_a_late_reported_trade_from_before_it_rested(env):
    md, tr, o, t = maker_signal(env)
    tr.now = lambda: t + 4000                                 # the hub's poll mode reports fills ~2-5 s late
    md.on_trade("S15D", 0.39, 10.0, "BUY", t - 500)           # venue time: before our bid rested
    assert not tr.router.state.fills
    md.on_trade("S15D", 0.39, 10.0, "BUY", t + 1000)          # after it rested, reported 3 s late: it fills
    assert len(tr.router.state.fills) == 1


def test_speed_maker_cancels_after_the_hold_and_the_venue_drops_it_half_a_round_trip_later(env):
    md, tr, o, t = maker_signal(env)
    tr.tick(t + 4999)
    assert o.status == "open"
    tr.tick(t + 5000)                                         # hold over: cancel sent, still live for rtt/2 = 100 ms
    tr.now = lambda: t + 5050
    md.on_trade("S15U", 0.61, 10.0, "SELL", t + 5050)         # a fill inside that window still counts
    assert o.status == "filled" and tr.counts["cancel:speed-maker"] == 1


def test_speed_maker_needs_its_realism_flags(env):
    with pytest.raises(ValueError, match="maker_realism"):
        boot(env, MK - {"maker_realism"})
