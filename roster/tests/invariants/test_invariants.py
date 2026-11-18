"""Phase 1 invariant suite (WP1-F): the build plan's invariants, checked on the real modules wired by trader/loop.py
with a fake market-data feed (no network). Run: python -m pytest tests/invariants -q"""
import dataclasses
import json
import pathlib
import random
import re

import pytest

import common
from tools.clearance_cli import write as sign_record
from trader import fees
from trader.contracts import Book, Intent, MarketInfo, TradingState
from trader.engines import ladder, speed
from trader.kernel import RiskKernel, clearance_key
from trader.loop import Trader
from trader.router import PaperRouter, replay, round_price, round_size

KEY = "test-human-key"
T = 1_790_843_000_000                      # 2026-10-01 08:23 UTC
LAD = MarketInfo("L1", "L1Y", "L1N", "crypto-term", "Will the price of Bitcoin be above $84,000 on October 1?", "r1",
                 0.01, 5.0, 0.07, False, T + 6 * 3_600_000, "BTC@2026-10-01T16:00Z", "BTC", 84000.0, "strike",
                 "binance:BTC/USDT")
SPD = MarketInfo("S5", "S5U", "S5D", "crypto-fast", "Bitcoin Up or Down - October 1, 4:22AM-4:27AM ET", "r2",
                 0.01, 5.0, 0.07, False, T + 4 * 60_000, "BTC-5m@2026-10-01T08:22Z", "BTC", None, "updown",
                 "chainlink:BTC/USD")


class FakeMD:
    def __init__(self):
        self.markets = {m.cid: m for m in (LAD, SPD)}
        self.books, self.rtt_ms = {}, 200.0
        self.ref = {a: {"price": p, "ts_ms": T, "recv_ms": T, "dvol": 35.0, "final": {}} for a, p in
                    (("BTC", 84000.0), ("ETH", 2680.0))}
        self.on_book = self.on_trade = self.on_ref = None

    def feed_age_ms(self, now):
        return {f: 0 for f in ("polymarket", "binance:BTC", "binance:ETH", "dvol:BTC", "dvol:ETH", "basis:USDT")}

    def book(self, token, bids, asks, now):
        self.books[token] = Book(token, bids, asks, now)
        self.on_book(self.books[token], now)

    def tick(self, asset, price, now):
        self.ref[asset].update(price=price, ts_ms=now, recv_ms=now)
        self.on_ref(asset, now)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTER_HUMAN_KEY", KEY)
    for m in (LAD, SPD):
        sign_record(tmp_path / "advice.db", {"type": "clearance", "key": clearance_key(m), "signer": "test",
                                             "expiry_ms": T + 86_400_000}, KEY)
    return tmp_path


def books(md, now):
    for tok, bids, asks in (("L1Y", [(0.48, 100)], [(0.52, 100)]), ("L1N", [(0.48, 100)], [(0.52, 100)]),
                            ("S5U", [(0.58, 50)], [(0.60, 50)]), ("S5D", [(0.40, 50)], [(0.42, 50)])):
        md.book(tok, bids, asks, now)


def boot(d, now=T):
    md = FakeMD()
    tr = Trader(md, d, fetch=lambda cid: None)
    tr.start(now)
    books(md, now)
    return md, tr


def speed_event(md, tr, t0=T):
    """BTC flat for 7 s, then +15 bp: one btc-speed event, a taker on the 5m Up token (books fresh at the event)."""
    for s in range(7):
        md.tick("BTC", 84000.0, t0 + s * 1000)
    books(md, t0 + 7000)
    md.tick("BTC", 84000.0 * 1.0015, t0 + 7000)
    return t0 + 7000


def ladder_orders(tr):
    return [o for o in tr.router.open_orders() if o.intent.strategy == ladder.NAME]


def test_end_to_end_paper_loop(env):
    md, tr = boot(env)
    md.tick("BTC", 84000.0, T)                         # first reference tick: the ladder quotes
    resting = {o.order_id for o in ladder_orders(tr)}
    assert len(resting) == 2                           # a bid on each outcome of the one cleared ladder market
    tr.ladder_round(T + 1000)                          # same state: the diff keeps both, nothing re-sent
    assert {o.order_id for o in ladder_orders(tr)} == resting and len(tr.router.state.orders) == 2
    t = speed_event(md, tr, T + 2000)                  # the 15 bp move also pulls the ladder (sharp move)
    assert not ladder_orders(tr)
    taker = [o for o in tr.router.state.orders.values() if o.intent.strategy == speed.NAME]
    assert len(taker) == 1 and taker[0].intent.token_id == "S5U" and taker[0].intent.size == 5.0
    tr.tick(t + 400)                                   # arrival = decision + 150 ms + 200 ms rtt
    f = tr.router.state.fills[0]
    assert (f.price, f.size, f.maker) == (0.60, 5.0, False)
    assert f.fee == pytest.approx(fees.fee(5, 0.60, 0.07)) == pytest.approx(0.084)
    rows = tr.ledger.as_of("speed_trades", 2 ** 62)
    assert rows[0]["approved"] and all(rows[0][k] for k in ("binance_ms", "recv_ms", "decision_ms", "arrival_ms"))
    for h in (5, 60, 300):
        tr.tick(f.ts_ms + h * 1000 + 1)
    marks = tr.ledger.as_of("markouts", 2 ** 62)
    assert sorted(m["horizon_s"] for m in marks) == [5, 60, 300]
    assert marks[0]["mid"] == 0.59 and marks[0]["markout"] == pytest.approx(-0.01)
    assert tr.reconcile(t + 400_000, "test") == [] and tr.violations == 0
    out = tr.shutdown(t + 400_001)
    assert out["violations"] == 0 and out["mismatches"] == [] and out["open_orders"] == 0 and out["audit_records"] > 0


def test_preregistrations_written_once_and_immutable(env):
    _, tr = boot(env)
    for p in (ladder.PREREG, speed.PREREG):
        assert tr.ledger.preregistration(p["test_id"])["statistic"] == p["statistic"]
        with pytest.raises(ValueError):
            tr.ledger.preregister({**p, "name": p["test_id"], "n": 1})
        with pytest.raises(Exception):
            tr.ledger.db.execute("DELETE FROM prereg")
    tr.ledger.close()
    _, tr2 = boot(env)                                 # a restart re-writes the identical dicts: a no-op
    assert {v["state"] for v in tr2.ledger.versions(speed.NAME)} == {"candidate"}


def test_halt_means_cancel_all_confirmed_by_reconciler(env):
    md, tr = boot(env)
    tr.ladder_round(T + 1000)
    assert ladder_orders(tr)
    tr.kernel.trip("global", "manual halt", "human")
    tr.tick(T + 2000)
    assert tr.recon.confirm_zero_open() and tr.ledger.as_of("halt_confirmed", 2 ** 62)
    speed_event(md, tr, T + 3000)
    assert not [o for o in tr.router.state.orders.values() if o.intent.strategy == speed.NAME]
    assert tr.counts["decision:btc-speed:HALTED"] == 1 and tr.violations == 0


def test_ai_cannot_raise_state_or_size(env):
    md, tr = boot(env)
    k = tr.kernel
    k.trip("global", "advisor thinks so", "ai:advisor")           # asks for HALTED, gets REDUCING
    assert k.state == TradingState.REDUCING
    fake_reducer = Intent("ladder-maker", "L1", "L1Y", "BUY", 0.40, 10, "maker", T + 600_000, 0.5,
                          "quote f=0.5 m=0.5 q=0.5", reduces_exposure=True)  # claims to reduce; holds nothing
    assert not k.check(fake_reducer, tr.ctx(T)).approved
    k.trip("global", "halt", "human")
    k.trip("global", "relax", "ai:advisor", TradingState.ACTIVE)  # a trip never lowers a state
    assert k.state == TradingState.HALTED
    rng = random.Random(1)                                        # the router never makes an order bigger or bolder
    md.book("L1Y", [(0.30, 100)], [(0.90, 100)], T)
    r = PaperRouter(md.markets, 200, journal=env / "j2.jsonl")
    r.books = tr.router.books
    for _ in range(300):
        i = Intent("x", "L1", "L1Y", "BUY", rng.uniform(0.31, 0.89), rng.uniform(5, 50), "maker", T + 600_000, 0.5, "")
        o = r.submit(i, T)
        assert o.intent.size <= i.size and o.intent.price <= i.price


def test_never_round_up():
    rng = random.Random(7)
    for _ in range(10_000):
        x, p = rng.uniform(0, 100), rng.uniform(0.001, 0.999)
        tick = rng.choice((0.01, 0.001))
        assert round_size(x) <= x and ladder.floor_to(x, 0.01) <= x
        assert round_price(p, tick, "BUY") <= p + 1e-12 and round_price(p, tick, "SELL") >= p - 1e-12
        n = ladder.taker_shares(rng.random() * 0.25, 50, max(p, 0.01), rng.uniform(0, 20), 5)
        assert n == 0 or 5 <= n


def test_unknown_never_retried_and_journal_replay_after_crash(env):
    md, tr = boot(env)
    tr.ladder_round(T + 1000)
    t = speed_event(md, tr, T + 2000)
    tr.router.poll(t + 400)           # the fill reaches the journal; the "crash" comes before the ledger write
    j = env / "journal.jsonl"
    before = replay(j)
    ghost = dataclasses.asdict(Intent("ladder-maker", "L1", "L1N", "BUY", 0.40, 10, "maker", T + 600_000, 0.6,
                                      "quote f=0.6 m=0.6 q=0.6"))
    with j.open("a", encoding="utf-8") as f:   # kill -9 mid-batch: one order journaled, no ack, then a torn line
        f.write(json.dumps({"op": "new", "id": "ghost", "ts": t + 500, "intent": ghost, "queue_ahead": 0}) + "\n")
        f.write('{"op": "new", "id": "torn", "ts"')
    tr.ledger.close()
    (env / "copy.jsonl").write_bytes(j.read_bytes())
    md2 = FakeMD()
    r = PaperRouter(md2.markets, 200, journal=env / "copy.jsonl")
    r.books["L1N"] = ([(0.30, 9)], [(0.9, 9)], T)
    assert r.state.orders["ghost"].status == "unknown"   # it may have reached the venue: its token/side is blocked
    assert r.submit(Intent("x", "L1", "L1N", "BUY", 0.40, 10, "maker", T + 600_000, 0.5, ""), T).status == "rejected"
    tr2 = Trader(md2, env, fetch=lambda cid: None)
    assert tr2.start(t + 1000) == [] and tr2.violations == 0
    st = tr2.router.state
    assert st.orders["ghost"].status == "cancelled" and "torn" not in st.orders   # resolved by id, never re-sent
    assert all(st.orders[oid].filled == o.filled for oid, o in before.orders.items()) and st.positions == before.positions
    assert len(tr2.ledger.as_of("fills", 2 ** 62)) == 1   # the journaled fill was backfilled into the ledger
    assert tr2.ledger.as_of("reconciles", 2 ** 62)[-1]["fills_backfilled"] == 1


def test_trip_survives_restart_until_human_reset(env):
    _, tr = boot(env)
    tr.kernel.trip("global", "manual halt", "human")
    tr.log_trips(T)
    tr.ledger.close()
    _, tr2 = boot(env)
    assert tr2.kernel.state == TradingState.HALTED
    sign_record(env / "advice.db", {"type": "reset", "scope": "global", "signer": "test",
                                    "expiry_ms": common.now_ms() + 600_000}, KEY)
    tr2.reload_advice(common.now_ms())
    assert tr2.kernel.state == TradingState.ACTIVE
    tr2.log_trips(T)
    tr2.ledger.close()
    _, tr3 = boot(env)
    assert tr3.kernel.state == TradingState.ACTIVE


def test_settlement_redeems_on_paper(env):
    md, tr = boot(env)
    t = speed_event(md, tr)
    tr.tick(t + 400)
    assert tr.unsettled(SPD.end_ms + 1) == ["S5"]
    cash = tr.cash()
    tr.settle({"S5": "S5U"}, SPD.end_ms + 60_000)
    assert "S5U" not in tr.positions() and tr.cash() == pytest.approx(cash + 5.0)
    assert tr.reconcile(SPD.end_ms + 60_000, "test") == []


def test_fee_values():
    for rate in (0.07, 0.05):
        for p in (0.1, 0.5, 0.9):
            assert fees.fee(100, p, rate) == pytest.approx(100 * rate * p * (1 - p))
    assert fees.fee(100, 0.5, 0.07) == pytest.approx(1.75) and fees.fee(10, 0.1, 0.05) == pytest.approx(0.045)
    with pytest.raises(fees.UnmodelledFee):
        fees.fee(10, 0.5, {"rate": 0.07, "exponent": 1, "takerOnly": True, "surcharge": 0.01})


def test_expired_maker_never_fills_and_trades_use_local_clock(env):
    md, tr = boot(env)
    tr.ladder_round(T + 1000)
    y, n = (next(o for o in ladder_orders(tr) if o.intent.token_id == t) for t in ("L1Y", "L1N"))
    tr.now = lambda: T + 1100                                     # resting from T + 1000 + 200 ms rtt: not yet
    tr.on_trade("L1Y", y.intent.price - 0.01, 50, "SELL", T + 9000)  # the venue's clock would say it was
    assert not tr.router.state.fills
    tr.now = lambda: T + 1300
    tr.on_trade("L1Y", y.intent.price - 0.01, 50, "SELL", T + 1300)
    assert [f.order_id for f in tr.router.state.fills] == [y.order_id]
    tr.now = lambda: n.intent.expiry_ms + 1                       # the trade reaches us after our GTD expiry
    tr.on_trade("L1N", n.intent.price - 0.01, 50, "SELL", T + 2000)  # venue ts says "before expiry": ignored
    assert n.status == "expired" and len(tr.router.state.fills) == 1 and tr.violations == 0


def take(i_ms, tok="S5U"):
    return Intent("btc-speed", "S5", tok, "BUY", 0.90, 5.0, "taker", i_ms + 2000, 0.6, "test", ((speed.NAME, 1),))


def test_taker_guards_no_book_and_no_reused_liquidity(env):
    md = FakeMD()
    tr = Trader(md, env, fetch=lambda cid: None)
    tr.start(T)
    i = take(T)
    d, o = tr.submit([i], T)[id(i)]
    assert (d.approved, d.reason, o) == (False, "no book for a taker", None)
    books(md, T)
    a, b = take(T), take(T)                                       # two takers on one token in one batch
    res = tr.submit([a, b], T)
    assert res[id(a)][0].approved and res[id(b)][0].reason == "own order already live on this token and side"
    c = take(T + 100)                                             # and while the first is in flight
    assert tr.submit([c], T + 100)[id(c)][0].reason == "own order already live on this token and side"
    tr.tick(T + 400)                                              # arrival T + 350: fills 5 of the 50 shown
    assert len(tr.router.state.fills) == 1
    e = take(T + 500)                                             # same snapshot: its size was ours already
    assert tr.submit([e], T + 500)[id(e)][0].reason == "book snapshot already taken by our last taker"
    md.book("S5U", [(0.58, 50)], [(0.60, 45)], T + 600)          # the next book update frees the token
    g = take(T + 700)
    assert tr.submit([g], T + 700)[id(g)][0].approved and tr.violations == 0


def test_ledger_replace_cannot_rewrite_history(env):
    _, tr = boot(env)
    with pytest.raises(Exception):
        tr.ledger.db.execute("INSERT OR REPLACE INTO prereg VALUES (?, '{}', 0)", (speed.PREREG["test_id"],))
    with pytest.raises(Exception):
        tr.ledger.db.execute("INSERT OR REPLACE INTO rows (id, tbl, event_ms, recorded_ms, body) VALUES (1, 'x', 0, 0, '{}')")
    want = json.loads(json.dumps({**speed.PREREG, "name": speed.PREREG["test_id"]}))
    assert tr.ledger.preregistration(speed.PREREG["test_id"]) == want


def test_scorer_and_daily_report(env):
    from nightly import report, scorer
    md, tr = boot(env)
    t = speed_event(md, tr)
    tr.tick(t + 400)                                              # 5 Up at 0.60, fee 0.084
    f = tr.router.state.fills[0]
    for h in (5, 60, 300):
        tr.tick(f.ts_ms + h * 1000 + 1)
    tr.settle({"S5": "S5U"}, SPD.end_ms + 60_000)                 # Up won: 5 shares redeemed at 1
    tr.shutdown(SPD.end_ms + 60_001)
    tr.ledger.close()
    now = SPD.end_ms + 120_000
    sc = scorer.score(env, fetch=None, now_ms=now)
    assert sc["speed"]["n"] == 1 and sc["speed"]["trades"][0]["pnl"] == pytest.approx(5 * (1 - 0.60) - 0.084)
    assert sc["markouts"]["btc-speed"][300] == {"n": 1, "mean": pytest.approx(-0.01), "se": None, "missing": 0}
    text, summary = report.build(env, 0, scorer.ALL, "test", fetch=None, now_ms=now)
    for h in ("Paper P&L per strategy", "Intents and kernel decisions", "Orders and fills", "Markouts", "Pre-registered",
              "Universe vs traded", "btc-speed events and trades", "Latency", "Invariant violations: 0", "Time to evidence"):
        assert h in text, h
    assert report.pnl(scorer.tables(env))["btc-speed"]["pnl"] == pytest.approx(1.916)
    assert "Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 8," in text
    assert "btc-speed +1.92" in summary and ladder.PREREG["test_id"] in text and speed.PREREG["test_id"] in text
    # the statistics' own rules
    assert scorer.cluster_se([1, 1, -1, -1], ["a", "a", "b", "b"]) == pytest.approx(8 ** 0.5 / 4)
    assert scorer.verdict(1.0, 0.4, 200, speed.PREREG) == "PASS"
    assert scorer.verdict(1.0, 0.4, 150, speed.PREREG).startswith("running")
    assert scorer.verdict(-0.5, 0.4, 100, speed.PREREG) == "FAIL (futility)"


SEND = re.compile(r"py_clob_client|post_order|create_order|place_order|sign_order|private_key|eth_account|web3|"
                  r"requests\.post|method=.POST|/order\b")
PAPER = ("trader.loop", "trader.marketdata", "nightly.scorer", "nightly.report", "nightly.drills", "tools.clearance_cli")


def test_no_order_send_path():
    """F6: nothing the paper trader, its nightly jobs or the clearance CLI import (the whole import closure, in a clean
    interpreter) can send, sign or post an order. The only POST is the optional ntfy alert in nightly/report.py (to
    ntfy.sh, never a venue). Later phases' live code (trader/live/, behind its own guard) is outside this closure."""
    import subprocess
    import sys
    code = (f"import sys, pathlib; import {', '.join(PAPER)}; r = pathlib.Path({str(common.ROOT)!r}); "
            "print('\\n'.join(sorted({m.__file__ for m in list(sys.modules.values()) if getattr(m, '__file__', None) "
            "and pathlib.Path(m.__file__).resolve().is_relative_to(r) and '.venv' not in pathlib.Path(m.__file__).parts})))")
    files = [pathlib.Path(f) for f in subprocess.run([sys.executable, "-c", code], cwd=common.ROOT, check=True,
                                                     capture_output=True, text=True).stdout.split("\n") if f]
    assert any(f.name == "router.py" for f in files) and not any("live" in f.parts for f in files)
    hits = [f"{p}:{n}" for p in files for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if SEND.search(line)]
    assert hits == []
    posts = [p.name for p in files if "data=" in (t := p.read_text(encoding="utf-8")) and "urlopen" in t]
    assert posts in ([], ["report.py"])
    with pytest.raises(Exception):
        PaperRouter({}, 200, journal=common.DATA / "trader" / "_never.jsonl", live=True)


def test_prefer_ipv4_orders_v4_first(monkeypatch):
    import socket
    from trader.loop import prefer_ipv4
    v6, v4 = (socket.AF_INET6, 1, 6, "", ("::1", 443, 0, 0)), (socket.AF_INET, 1, 6, "", ("127.0.0.1", 443))
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [v6, v4])
    prefer_ipv4()
    prefer_ipv4()                                                 # idempotent: wraps once
    assert socket.getaddrinfo("x", 443) == [v4, v6]


def test_untraded_fast_markets_left_out():
    from trader.loop import untraded
    eth = dataclasses.replace(SPD, cid="E5", token_yes="E5U", token_no="E5D", asset="ETH")
    eth_term = dataclasses.replace(LAD, cid="E1", asset="ETH")
    assert untraded({m.cid: m for m in (LAD, SPD, eth, eth_term)}) == ["E5"]
    assert untraded({m.cid: m for m in (LAD, SPD, eth, eth_term)}, ("ETH",)) == [SPD.cid]  # the speed_eth run


def test_speed_v3_side_run_exits_8s_after_the_fill(env):
    """Flags speed_v3 + speed_only: no ladder quotes; the btc-speed buy is sold at the bid about 8 s after its fill."""
    md = FakeMD()
    tr = Trader(md, env, fetch=lambda cid: None, features={"speed_v3", "speed_only"})
    tr.start(T)
    books(md, T)
    md.tick("BTC", 84000.0, T)
    assert not ladder_orders(tr)
    t = speed_event(md, tr, T + 2000)
    tr.tick(t + 400)
    [buy] = tr.router.state.fills
    for now in range(buy.ts_ms + 1000, buy.ts_ms + 11_000, 500):   # the loop's 100 ms tick, coarser
        books(md, now)
        tr.tick(now)
    sells = [f for f in tr.router.state.fills if f.side == "SELL"]
    assert len(sells) == 1 and sells[0].ts_ms - buy.ts_ms >= 8000
    assert (sells[0].strategy, sells[0].price, sells[0].size, sells[0].maker) == (speed.NAME, 0.58, 5.0, False)
    assert tr.positions() == {} and tr.violations == 0
    assert "btc-speed-v3" in {r[0] for r in tr.ledger.db.execute("select name from prereg")}


def test_speed_v3_restart_sells_a_position_left_open(env):
    """A crash between the buy and its exit: the next start replays the fill and sells at once."""
    md = FakeMD()
    tr = Trader(md, env, fetch=lambda cid: None, features={"speed_v3", "speed_only"})
    tr.start(T)
    books(md, T)
    t = speed_event(md, tr, T + 2000)
    tr.tick(t + 400)
    assert tr.positions() == {"S5U": 5.0}                     # bought; killed before the 8 s exit
    md2 = FakeMD()
    tr2 = Trader(md2, env, fetch=lambda cid: None, features={"speed_v3", "speed_only"})
    tr2.start(t + 20_000)
    books(md2, t + 20_000)
    for now in range(t + 21_000, t + 24_000, 500):
        books(md2, now)
        tr2.tick(now)
    assert tr2.positions() == {} and tr2.violations == 0



def test_speed_v4_side_run_holds_and_preregisters(env):
    md = FakeMD()
    tr = Trader(md, env, fetch=lambda cid: None, features={"speed_v4", "speed_only"})
    tr.start(T)
    books(md, T)
    t = speed_event(md, tr, T + 2000)
    tr.tick(t + 400)
    for now in range(t + 1000, t + 12_000, 500):
        books(md, now)
        tr.tick(now)
    assert [f.side for f in tr.router.state.fills] == ["BUY"] and tr.violations == 0   # no exit sale
    assert "btc-speed-v4" in {r[0] for r in tr.ledger.db.execute("select name from prereg")}


def test_closed_unsettled_position_keeps_its_last_bid_for_breakers(env):
    """10 Oct paper_eth: a held market's book vanished before settlement, its shares counted 0 and tripped a false
    daily loss. The breakers now value it at the last bid seen."""
    md = FakeMD()
    tr = Trader(md, env, fetch=lambda cid: None, features={"speed_v4", "speed_only"})
    tr.start(T)
    books(md, T)
    t = speed_event(md, tr, T + 2000)
    tr.tick(t + 400)
    [tok] = tr.positions()
    before = tr.strategy_values()[speed.NAME]
    del md.books[tok]                                    # market past its end: no book, not yet settled
    assert tr.strategy_values()[speed.NAME] == pytest.approx(before)
    tr.tick(t + 2000)
    assert speed.NAME not in {s["scope"] for s in tr.kernel.trips if s["level"] != "ACTIVE"}


def test_fast_market_bet_counts_at_its_price_until_settled(env):
    """12 Nov live: a 5-min bet's bid fell to 0.18 a minute before close and the 20% daily stop tripped on a bet
    that had not settled. The daily stops now value 5/15-min crypto shares at what was paid until settlement."""
    md = FakeMD()
    tr = Trader(md, env, fetch=lambda cid: None, features={"speed_v4", "speed_only"})
    tr.start(T)
    books(md, T)
    t = speed_event(md, tr, T + 2000)
    tr.tick(t + 400)
    [tok] = tr.positions()
    [f] = tr.router.state.fills
    assert tr.breaker_marks()[tok] == pytest.approx((f.price * f.size + f.fee) / f.size)
    before = tr.strategy_values()[speed.NAME]
    md.book(tok, [(0.01, 50)], [(0.99, 50)], t + 1000)  # pre-close: the bid collapses
    assert tr.held_marks()[tok] == 0.01 and tr.strategy_values()[speed.NAME] == pytest.approx(before)
    tr.tick(t + 2000)
    assert not [s for s in tr.kernel.trips if s["level"] != "ACTIVE"]


def test_speed_eth_side_run_trades_eth_and_preregisters(env):
    tr = Trader(FakeMD(), env, fetch=lambda cid: None, features={"speed_v4", "speed_eth", "speed_only"})
    tr.start(T)
    assert tr.speed.p["assets"] == ("ETH",) and set(tr.speed.det) == {"ETH"}
    assert "btc-speed-v4-eth" in {r[0] for r in tr.ledger.db.execute("select name from prereg")}
    with pytest.raises(ValueError):  # ETH only as its own v4 side run
        Trader(FakeMD(), env, fetch=lambda cid: None, features={"speed_eth", "speed_only"})


def test_speed_v5_side_run_preregisters_and_refuses_another_version(env):
    tr = Trader(FakeMD(), env, fetch=lambda cid: None, features={"speed_v5", "speed_only"})
    tr.start(T)
    assert tr.speed.p["max_rv30"] == 5.5 and tr.speed.versions == ((speed.NAME, speed.VERSION_V5),)
    assert "btc-speed-v5" in {r[0] for r in tr.ledger.db.execute("select name from prereg")}
    with pytest.raises(ValueError):
        Trader(FakeMD(), env, fetch=lambda cid: None, features={"speed_v4", "speed_v5", "speed_only"})


def test_bybit_v5_side_run_preregisters_and_needs_v5_speed_only(env):
    tr = Trader(FakeMD(), env, fetch=lambda cid: None, features={"speed_v5", "ref_bybit", "speed_only"})
    tr.start(T)
    assert tr.speed.versions == ((speed.NAME, speed.VERSION_V5_BYBIT),) and tr.speed.p["max_rv30"] == 5.5
    assert "btc-speed-v5-bybit" in {r[0] for r in tr.ledger.db.execute("select name from prereg")}
    with pytest.raises(ValueError):
        Trader(FakeMD(), env, fetch=lambda cid: None, features={"speed_v5", "ref_bybit"})


def test_bybit_v4_and_eth_side_runs_preregister_their_own_versions(env):
    for flags, ver, test in (({"speed_v4"}, speed.VERSION_V4_BYBIT, "btc-speed-v4-bybit"),
                             ({"speed_v4", "speed_eth"}, speed.VERSION_V4_ETH_BYBIT, "btc-speed-v4-eth-bybit")):
        tr = Trader(FakeMD(), env / ver, fetch=lambda cid: None, features=flags | {"ref_bybit", "speed_only"})
        tr.start(T)
        assert tr.speed.versions == ((speed.NAME, ver),)
        assert test in {r[0] for r in tr.ledger.db.execute("select name from prereg")}


def test_compound_eth_run_preregisters_and_scales_size_and_daily_loss(env):
    md = FakeMD()
    tr = Trader(md, env, cash=80.86, fetch=lambda cid: None,
                features={"speed_v4", "speed_eth", "ref_bybit", "speed_only", "compound"})
    tr.start(T)
    assert tr.speed.versions == ((speed.NAME, speed.VERSION_V4_ETH_BYBIT_C),)
    assert "btc-speed-v4-eth-bybit-c" in {r[0] for r in tr.ledger.db.execute("select name from prereg")}
    tr.tick(T + 2000)                                  # the slow tick hands the account value to engine and breaker
    assert tr.speed.equity == pytest.approx(80.86) and tr.breakers.strategy_loss_usd == pytest.approx(5 * 80.86 / 50)
    assert tr.speed.size_for(100) == 8.0
    with pytest.raises(ValueError):                    # compounding only on the ETH-on-Bybit v4 rule
        Trader(FakeMD(), env, fetch=lambda cid: None, features={"speed_v5", "ref_bybit", "speed_only", "compound"})


def test_speed_v3_and_v4_never_share_a_run(env):
    with pytest.raises(ValueError):
        Trader(FakeMD(), env, fetch=lambda cid: None, features={"speed_v3", "speed_v4", "speed_only"})

def test_morning_reset_clears_breaker_pauses_but_never_a_halt(env):
    import importlib.util
    spec = importlib.util.spec_from_file_location("morning_reset", pathlib.Path(__file__).parents[2] / "ops" / "morning_reset.py")
    mr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mr)
    md, tr = boot(env)
    tr.kernel.trip("global", "daily drawdown", "breaker:drawdown", TradingState.REDUCING)
    tr.kernel.trip("btc-speed", "invariant", "kernel:invariant", TradingState.HALTED)
    tr.log_trips(T + 1)
    assert mr.paused_scopes(env) == ["global"]
    sign_record(env / "advice.db", {"type": "reset", "scope": "global", "signer": "test-auto",
                                    "expiry_ms": T + 1_800_000}, KEY)
    tr.reload_advice(T + 2)
    tr.log_trips(T + 2)
    assert tr.kernel.scopes.get("global", TradingState.ACTIVE) == TradingState.ACTIVE and mr.paused_scopes(env) == []



def test_feed_resume_lifts_a_feed_only_pause_and_nothing_else(env):
    import importlib.util
    import json as _json
    spec = importlib.util.spec_from_file_location("feed_resume", pathlib.Path(__file__).parents[2] / "ops" / "feed_resume.py")
    fr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fr)
    md, tr = boot(env)
    tr.kernel.trip("global", "stale feed polymarket: 61000 ms", "breaker:stale_feed", TradingState.REDUCING)
    tr.kernel.trip("btc-speed", "strategy daily loss 5.10 USD > 5.00", "breaker:strategy", TradingState.REDUCING)
    tr.kernel.trip("ladder-maker", "stale feed binance:BTC: 61000 ms", "breaker:stale_feed", TradingState.REDUCING)
    tr.kernel.trip("ladder-maker", "daily drawdown", "breaker:drawdown", TradingState.REDUCING)
    tr.log_trips(T + 1)
    rows = lambda: [(ts, _json.loads(b)) for ts, b in
                    tr.ledger.db.execute("SELECT event_ms, body FROM rows WHERE tbl = 'trips' ORDER BY id")]
    assert fr.resumable(rows(), T + 60_000) == []                           # too recent
    assert fr.resumable(rows(), T + 1 + fr.QUIET_MS) == ["global"]          # loss and mixed causes wait for 08:15
    sign_record(env / "advice.db", {"type": "reset", "scope": "global", "signer": "test-feed",
                                    "expiry_ms": T + fr.QUIET_MS + fr.TOKEN_MS}, KEY)
    tr.reload_advice(T + fr.QUIET_MS + 2)
    tr.log_trips(T + fr.QUIET_MS + 2)
    assert tr.kernel.scopes.get("global", TradingState.ACTIVE) == TradingState.ACTIVE
    assert tr.kernel.scopes["btc-speed"] == TradingState.REDUCING and fr.resumable(rows(), T + 10 * fr.QUIET_MS) == []

def test_record_tob_logs_top_of_book_changes_only(env):
    import gzip
    import time as _t
    md = FakeMD()
    tr = Trader(md, env, fetch=lambda cid: None, features={"record_tob"})
    assert tr.router.liquidity_once is False                    # logging alone changes nothing
    tr.start(T)
    books(md, T)
    books(md, T + 1000)                                         # same tops: nothing new
    md.book("S5U", [(0.59, 50)], [(0.60, 50)], T + 2000)        # bid moved
    h1 = (T // 3_600_000 + 1) * 3_600_000                       # next UTC hour: a new file
    md.book("S5U", [(0.58, 50)], [(0.60, 50)], h1)
    tr.shutdown(h1 + 1)
    for _ in range(50):                                         # gzip runs in a thread at rotation and close
        gz = sorted((env / "tob").glob("*.csv.gz"))
        if len(gz) == 2 and not list((env / "tob").glob("*.csv")):
            break
        _t.sleep(0.1)
    first, second = (gzip.open(p, "rt", newline="").read() for p in gz)
    assert len(first.splitlines()) == 5 and first.splitlines()[-1].split(",")[1:] == ["S5U", "0.59", "0.6"]
    assert chr(13) not in first and second.splitlines() == [f"{h1},S5U,0.58,0.6"]


def test_speed_size_cap_allows_only_the_live_dollar_floor(env):
    """16 Nov: live sizes cheap bets up to Polymarket's $1 minimum (6.67 shares at 0.15). The 5-share cap still
    flags any other oversized speed order."""
    from trader.contracts import Intent
    md = FakeMD()
    tr = Trader(md, env, fetch=lambda cid: None, features={"speed_v4", "speed_only"})
    tr.start(T)
    floor = Intent(speed.NAME, SPD.cid, SPD.token_yes, "BUY", 0.15, 6.67, "taker", T + 2000, 0.05, "BTC up 5m")
    big = Intent(speed.NAME, SPD.cid, SPD.token_yes, "BUY", 0.60, 6.67, "taker", T + 2000, 0.50, "BTC up 5m")
    tr.check_intent(floor, T)
    assert tr.violations == 1                         # paper: no floor, so 6.67 shares breaks the cap
    tr.speed.min_notional = 1.0
    tr.check_intent(floor, T)
    assert tr.violations == 1                         # live: the $1 floor is allowed
    tr.check_intent(big, T)
    assert tr.violations == 2                         # $4.00 at 6.67 shares is not a floor order
