"""WP5-B replay lab (role 35): event store, look-ahead tripwire, fill model, runner and validation. Offline."""
import inspect
import itertools
import json
import math
import random
from collections import Counter

import numpy as np
import pytest

import common
import learning.replay.__main__ as cli
from learning.replay import validate
from learning.replay.events import MIN_MS, State, Store, load_pm
from learning.replay.fills import FillModel
from learning.replay.run import LookAheadError, replay, tripwire
from learning.replay.validate import (TrialLog, cpcv, deflated_sharpe, dsr, nested_select, pbo, random_entry,
                                      walk_forward)
from trader.contracts import Book, Decision, Intent, KernelContext, MarketInfo
from trader.fees import fee
from trader.marketdata import Books
from trader.router import PaperRouter

T0 = 1_790_000_000_000
END = T0 + 10 * 86_400_000
Y, N = "tokY" * 4, "tokN" * 4
M = MarketInfo("c1", Y, N, "crypto-term", "q", "h", 0.01, 5.0, 0.07, False, END, "BTC@x", "BTC", 100_000.0, "strike")
MK = {"c1": M}
RTT = 50


def lv(levels):
    return [{"price": str(p), "size": str(s)} for p, s in levels]


def book_msg(tok, bids, asks):
    return json.dumps({"event_type": "book", "asset_id": tok, "bids": lv(bids), "asks": lv(asks)})


def pc_msg(tok, side, price, size):
    return json.dumps({"event_type": "price_change",
                       "price_changes": [{"asset_id": tok, "side": side, "price": str(price), "size": str(size)}]})


def trade_msg(tok, price, size, side, ts):
    return json.dumps({"event_type": "last_trade_price", "asset_id": tok, "price": str(price), "size": str(size),
                       "side": side, "timestamp": str(ts)})


def bk(bids, asks, ts, tok=Y):
    return Book(tok, list(bids), list(asks), ts)


def maker(price, size=10.0, exp=T0 + 3_600_000, side="BUY", tok=Y):
    return Intent("s", "c1", tok, side, price, size, "maker", exp, 0.5, "t")


def taker(price, size, exp=T0 + 10_000, side="BUY", tok=Y):
    return Intent("s", "c1", tok, side, price, size, "taker", exp, 0.5, "t")


# ---- B1 / B2: event store ---------------------------------------------------------------------------------------

PM = [(T0, book_msg(Y, [(0.44, 100), (0.43, 50)], [(0.52, 50)]), "crypto-term"),
      (T0 + 10, pc_msg(Y, "BUY", 0.45, 20), "crypto-term"),
      (T0 + 20, trade_msg(Y, 0.52, 5, "BUY", T0 + 15), "crypto-term"),
      (T0 + 30, pc_msg(Y, "SELL", 0.52, 0), "crypto-term"),
      (T0 + 30, pc_msg(Y, "SELL", 0.53, 70), "crypto-term"),
      # late: the message happened at T0 + 35 but this PC received it at T0 + 500
      (T0 + 500, trade_msg(Y, 0.45, 3, "SELL", T0 + 35), "crypto-term"),
      (T0 + 600, pc_msg(Y, "BUY", 0.44, 0), "crypto-term")]


def test_b1_store_books_equal_direct_books():
    store = Store(pm=PM)
    for t in sorted({r[0] for r in PM} | {T0 + 5, T0 + 499, T0 + 1000}):
        direct = Books()
        for rt, raw, _ in PM:
            if rt <= t:
                direct.apply(raw, rt)
        got = store.as_of(t).books.books
        assert got.keys() == direct.books.keys()
        for k, b in got.items():
            d = direct.books[k]
            assert (b.bids, b.asks, b.ts_ms) == (d.bids, d.asks, d.ts_ms)


REAL = common.DATA / "recordings" / "parquet" / "stream=crypto-term" / "date=2026-09-30" / "14.parquet"


@pytest.mark.skipif(not REAL.exists(), reason="recorded hour not on this machine")
def test_b1_real_recorded_hour():
    h0 = 1790776800000  # 2026-09-30 14:00 UTC
    pm = load_pm(("crypto-term",), h0, h0 + 3_600_000 - 1)
    assert pm
    lo, hi = pm[0][0], pm[-1][0]
    r = cli.b1_check(Store(pm=pm), pm, (lo + hi) // 2)
    assert r["equal"] and r["tokens"] > 0


def test_b2_as_of_never_returns_late_recorded_events():
    store = Store(pm=PM, ref=[{"asset": "BTC", "ts_ms": T0 + 60, "price": 1.0, "recorded_ms": T0 + 400}])
    st = store.as_of(T0 + 100)
    assert [x["event_ms"] for x in st.trades] == [T0 + 15]  # the late trade (event_ms T0+35) is not known yet
    assert st.ref.get("BTC", {}).get("price") is None       # nor the reference value recorded at T0+400
    assert all(e[0] <= T0 + 100 for e in store.until(T0 + 100))
    st = store.as_of(T0 + 500)
    assert [x["event_ms"] for x in st.trades] == [T0 + 15, T0 + 35]
    rng = random.Random(3)
    for _ in range(50):
        t = rng.randint(T0 - 10, T0 + 700)
        assert all(x["recorded_ms"] <= t for x in store.as_of(t).trades)
        assert all(e[0] <= t for e in store.until(t))
        assert all(b.ts_ms <= t for b in store.as_of(t).books.books.values())


# ---- B3: tripwire ------------------------------------------------------------------------------------------------

class ScriptEngine:
    """Maker target A until T0+5000, then B; one taker intent on the first tick at or after T0+6000."""
    name = "script"
    p = {"x": 1}

    def __init__(self):
        self.calls, self.fills, self.sent_taker = [], [], False

    def on_tick(self, now_ms, markets, books, ref, positions):
        self.calls.append((now_ms, markets, books, ref, positions))
        px = 0.45 if now_ms < T0 + 5000 else 0.46
        out = [maker(px, exp=now_ms + 3_600_000)]
        if now_ms >= T0 + 6000 and not self.sent_taker:
            self.sent_taker = True
            out.append(taker(0.53, 60, exp=now_ms + 2000))
        return out

    def on_fill(self, f):
        self.fills.append(f)


def script_store(ref_extra=(), finals=()):
    pm = [(T0, book_msg(Y, [(0.44, 100)], [(0.52, 50), (0.53, 40)]), "crypto-term"),
          (T0, book_msg(N, [(0.47, 100)], [(0.56, 100)]), "crypto-term"),
          (T0 + 7000, pc_msg(Y, "SELL", 0.52, 30), "crypto-term"),
          (T0 + 8000, trade_msg(Y, 0.45, 20, "SELL", T0 + 7990), "crypto-term")]
    ref = [{"asset": "BTC", "ts_ms": T0 + k, "price": 100_000.0 + k} for k in (1000, 5000, 6000)] + list(ref_extra)
    return Store(pm=pm, markets=[(T0 - 1000, MK)], ref=ref, finals=finals)


def test_b3_clean_run_zero_violations():
    res = replay(ScriptEngine(), script_store(), T0, T0 + 8000, RTT)
    assert res["violations"] == 0 and res["checks"] > 0 and res["ticks"] > 0


def test_b3_tripwire_book_from_the_future():
    st = State()
    st.books.books[Y] = Book(Y, [(0.4, 1)], [(0.6, 1)], T0 + 10)
    with pytest.raises(LookAheadError):
        tripwire(T0, st)
    st.books.books[Y].ts_ms = T0
    assert tripwire(T0, st) >= 1


@pytest.mark.parametrize("leak", ["ref", "final"])
def test_b3_leaky_feeder_raises(leak):
    if leak == "ref":  # a value whose timestamp is later than when the feeder claims it was recorded
        store = script_store(ref_extra=[{"asset": "BTC", "ts_ms": T0 + 9000, "price": 1.0, "recorded_ms": T0 + 900}])
    else:              # a final print whose candle closes after now
        store = script_store(finals=[{"asset": "BTC", "open_ms": T0 + 100_000, "price": 1.0, "recorded_ms": T0 + 500}])
    with pytest.raises(LookAheadError, match="recorded later"):
        replay(ScriptEngine(), store, T0, T0 + 8000, RTT)


def test_b3_b14_leaky_cli_run_writes_no_report_and_logs_failed_trial(tmp_path, monkeypatch):
    s = script_store(finals=[{"asset": "BTC", "open_ms": T0 + 100_000, "price": 1.0, "recorded_ms": T0 + 500}])
    pm = [(e[0], e[2][0], e[2][1]) for e in s.events if e[1] == "pm"]
    monkeypatch.setattr(cli, "ENGINES", {"fake": (ScriptEngine, "crypto-term", "trader/engines/ladder.py")})
    monkeypatch.setattr(cli, "load_pm", lambda *a: pm)
    monkeypatch.setattr(cli, "load_markets", lambda *a: [(T0 - 1000, MK)])
    monkeypatch.setattr(cli, "load_ref", lambda *a: [{"asset": "BTC", "ts_ms": T0 + 1000, "price": 1.0}])
    monkeypatch.setattr(cli, "load_dvol", lambda *a: [])
    monkeypatch.setattr(cli, "load_finals", lambda *a: [{"asset": "BTC", "open_ms": T0 + 100_000, "price": 1.0,
                                                         "recorded_ms": T0 + 500}])
    report = tmp_path / "report.md"
    with pytest.raises(LookAheadError):
        cli.main(["--engine", "fake", "--hour", "2026-09-21T13", "--no-fetch", "--out", str(tmp_path / "out"),
                  "--report", str(report)])
    assert not report.exists() and not list((tmp_path / "out").glob("smoke_*.json"))
    rows = TrialLog(tmp_path / "out" / "trials.jsonl").rows()
    assert [(r["family"], r["status"]) for r in rows] == [("replay:script", "failed")]


# ---- B4: strict-mode parity with PaperRouter ---------------------------------------------------------------------

def drive(sim, ops):
    fills = []
    for op in ops:
        if op[0] == "book":
            fills += sim.on_book(op[1], op[1].ts_ms)
        elif op[0] == "submit":
            sim.submit(op[1], op[2])
        elif op[0] == "trade":
            fills += sim.on_trade(*op[1:])
        elif op[0] == "poll":
            fills += sim.poll(op[1])
    return fills


PARITY = {
    "maker_through": [("book", bk([(0.50, 100)], [(0.52, 50)], T0)), ("submit", maker(0.50), T0),
                      ("trade", Y, 0.49, 5, "SELL", T0 + 10),    # before created + rtt: not resting yet
                      ("trade", Y, 0.49, 5, "SELL", T0 + 100)],
    "maker_queue": [("book", bk([(0.50, 100)], [(0.52, 50)], T0)), ("submit", maker(0.50), T0),
                    ("trade", Y, 0.50, 60, "SELL", T0 + 100), ("trade", Y, 0.50, 45, "SELL", T0 + 200),
                    ("trade", Y, 0.50, 7, "BUY", T0 + 250),      # same side as ours: does not count
                    ("trade", Y, 0.50, 5, "SELL", T0 + 300)],
    "taker_partial": [("book", bk([(0.50, 100)], [(0.52, 50), (0.53, 20), (0.54, 100)], T0)),
                      ("submit", taker(0.53, 80), T0 + 1000),
                      ("book", bk([(0.50, 100)], [(0.60, 5)], T0 + 1500))],
    "taker_poll": [("book", bk([(0.50, 100), (0.49, 30)], [(0.52, 50)], T0)),
                   ("submit", taker(0.49, 40, side="SELL"), T0 + 1000), ("poll", T0 + 1300)],
}


@pytest.mark.parametrize("case", sorted(PARITY))
def test_b4_strict_parity_with_paper_router(case, tmp_path):
    ops = PARITY[case]
    pr = PaperRouter(MK, RTT, journal=tmp_path / "journal.jsonl")
    if case == "taker_poll":  # PaperRouter refuses a SELL beyond the position held
        pr.state.positions[Y] = 100.0
    a, b = drive(pr, ops), drive(FillModel(MK, RTT), ops)
    assert a == b and a
    if case == "maker_queue":
        assert [(f.size, f.ts_ms) for f in a] == [(10.0, T0 + 300)]
    if case == "taker_partial":
        assert [(f.price, f.size) for f in a] == [(0.52, 50.0), (0.53, 20.0)]
        assert all(f.fee == pytest.approx(fee(f.size, f.price, M.fee_rate)) and f.fee > 0 for f in a)
        assert all(f.ts_ms == T0 + 1000 + 150 + RTT for f in a)


# ---- B5: the three fixes -----------------------------------------------------------------------------------------

def test_b5_no_maker_fill_at_or_after_expiry():
    fm = FillModel(MK, RTT)
    fm.on_book(bk([(0.50, 100)], [(0.52, 50)], T0), T0)
    o = fm.submit(maker(0.50, exp=T0 + 61_000), T0)
    assert o.status == "open"
    assert fm.on_trade(Y, 0.40, 50, "SELL", T0 + 61_000) == []
    assert o.status == "expired"


def test_b5_takers_use_liquidity_once():
    fm = FillModel(MK, RTT)
    fm.on_book(bk([(0.50, 100)], [(0.52, 50), (0.53, 20)], T0), T0)
    o1, o2 = fm.submit(taker(0.53, 40), T0 + 100), fm.submit(taker(0.53, 40), T0 + 100)
    fills = fm.on_book(bk([(0.50, 100)], [(0.52, 50), (0.53, 20)], T0 + 1000), T0 + 1000)
    assert [(f.order_id, f.price, f.size) for f in fills] == [(o1.order_id, 0.52, 40.0), (o2.order_id, 0.52, 10.0),
                                                             (o2.order_id, 0.53, 20.0)]
    # the next book update restores the displayed size for later takers
    o3 = fm.submit(taker(0.52, 40), T0 + 1100)
    assert [(f.order_id, f.size) for f in fm.poll(T0 + 2000)] == [(o3.order_id, 40.0)]


def test_b5_trade_volume_allocated_once_oldest_first():
    fm = FillModel(MK, RTT)
    fm.on_book(bk([(0.49, 100)], [(0.52, 50)], T0), T0)
    old, new = fm.submit(maker(0.50), T0), fm.submit(maker(0.50), T0 + 1)
    f = fm.on_trade(Y, 0.50, 15, "SELL", T0 + 1000)
    assert [(x.order_id, x.size) for x in f] == [(old.order_id, 10.0)]
    assert new.filled == 0
    assert [(x.order_id, x.size) for x in fm.on_trade(Y, 0.50, 5, "SELL", T0 + 2000)] == [(new.order_id, 10.0)]


def test_b5_taker_with_no_book_is_killed():
    fm = FillModel(MK, RTT)
    o = fm.submit(taker(0.60, 20), T0)
    assert fm.poll(T0 + 1000) == [] and o.status == "cancelled" and o.filled == 0
    assert fm.reasons[o.order_id] == "no book in force"
    # past its give-up time: also killed with zero fill
    fm.on_book(bk([(0.50, 100)], [(0.52, 50)], T0 + 2000), T0 + 2000)
    o = fm.submit(taker(0.60, 20, exp=T0 + 2100), T0 + 2000)
    assert fm.poll(T0 + 3000) == [] and o.status == "cancelled" and o.filled == 0


# ---- B6: queue mode ----------------------------------------------------------------------------------------------

def test_b6_queue_mode_cancel_ahead_and_partial():
    fm = FillModel(MK, RTT, mode="queue", cancel_ahead=0.5)
    fm.on_book(bk([(0.50, 100)], [(0.52, 50)], T0), T0)
    o = fm.submit(maker(0.50), T0)
    fm.on_book(bk([(0.50, 60)], [(0.52, 50)], T0 + 1000), T0 + 1000)  # 40 gone without a trade
    assert fm.meta[o.order_id]["ahead"] == pytest.approx(80)
    f = fm.on_trade(Y, 0.50, 85, "SELL", T0 + 2000)                  # 80 clears the queue, 5 fill us
    assert [x.size for x in f] == [5.0] and o.status == "partial"
    assert [x.size for x in fm.on_trade(Y, 0.50, 10, "SELL", T0 + 3000)] == [5.0] and o.status == "filled"
    # a displayed drop that trades explain does not advance the queue a second time
    fm2 = FillModel(MK, RTT, mode="queue", cancel_ahead=1.0)
    fm2.on_book(bk([(0.50, 100)], [(0.52, 50)], T0), T0)
    o2 = fm2.submit(maker(0.50), T0)
    fm2.on_trade(Y, 0.50, 30, "SELL", T0 + 500)
    fm2.on_book(bk([(0.50, 70)], [(0.52, 50)], T0 + 600), T0 + 600)
    assert fm2.meta[o2.order_id]["ahead"] == pytest.approx(70)


def test_b6_queue_mode_zero_cancel_ahead_matches_strict_total():
    totals = {}
    for mode in ("strict", "queue"):
        fm = FillModel(MK, RTT, mode=mode, cancel_ahead=0.0)
        fm.on_book(bk([(0.50, 100)], [(0.52, 50)], T0), T0)
        fm.submit(maker(0.50), T0)
        fm.on_book(bk([(0.50, 60)], [(0.52, 50)], T0 + 50), T0 + 50)
        for k, s in enumerate((60, 45, 5)):
            fm.on_trade(Y, 0.50, s, "SELL", T0 + 1000 * (k + 1))
        totals[mode] = sum(f.size for f in fm.fills)
    assert totals == {"strict": 10.0, "queue": 10.0}


# ---- B7: runner --------------------------------------------------------------------------------------------------

class RejectTakers:
    def __init__(self):
        self.ctx = []

    def check(self, intent, ctx):
        self.ctx.append(ctx)
        return Decision(False, "no takers") if intent.kind == "taker" else Decision(True, "ok")


def test_b7_runner_diff_submit_fill():
    eng = ScriptEngine()
    res = replay(eng, script_store(), T0, T0 + 8000, RTT, outcomes={"c1": 1})
    subs = [(t, i.kind, i.price) for t, i in res["intents"]]
    assert subs == [(T0, "maker", 0.45), (T0 + 5000, "maker", 0.46), (T0 + 6000, "taker", 0.53)]
    assert [t for t, _ in res["cancels"]] == [T0 + 5000]
    assert [(f.maker, f.price, f.size) for f in res["fills"]] == [(False, 0.52, 50.0), (False, 0.53, 10.0),
                                                                 (True, 0.46, 10.0)]
    assert eng.fills == res["fills"] and res["positions"] == {Y: 70.0}
    for now, markets, books, ref, positions in eng.calls:  # exactly the Engine protocol's arguments
        assert isinstance(now, int) and set(markets) == {"c1"} and isinstance(markets["c1"], MarketInfo)
        assert all(isinstance(b, Book) for b in books.values()) and isinstance(ref, dict)
        assert isinstance(positions, dict)
    assert list(inspect.signature(ScriptEngine.on_tick).parameters)[1:] == \
        ["now_ms", "markets", "books", "ref", "positions"]
    fees = sum(f.fee for f in res["fills"])
    want = 70 - (50 * 0.52 + 10 * 0.53 + 10 * 0.46) - fees
    assert res["clusters"] == [{"cluster_id": "BTC@x", "pnl": pytest.approx(want), "fees": pytest.approx(fees),
                                "unresolved": False}]
    assert res["label"] == res["stat"]["label"] == "exploratory"


def test_b7_kernel_rejection_stops_intent():
    k = RejectTakers()
    res = replay(ScriptEngine(), script_store(), T0, T0 + 8000, RTT, kernel=k)
    assert [d.approved for _, _, d in res["decisions"]] == [True, True, False]
    assert all(o.intent.kind == "maker" for o in res["orders"])
    assert [(f.maker, f.size) for f in res["fills"]] == [(True, 10.0)]
    assert all(isinstance(c, KernelContext) for c in k.ctx)


# ---- B8 - B10: walk-forward, nested selection, CPCV --------------------------------------------------------------

def rand_clusters(rng, n):
    out = []
    for i in range(n):
        f = rng.randint(0, 1_000_000)
        out.append((f"k{i}", f, None if rng.random() < 0.1 else f + rng.randint(0, 200_000)))
    return out


def test_b8_walk_forward_property():
    rng = random.Random(8)
    for _ in range(200):
        cl = rand_clusters(rng, rng.randint(5, 60))
        by = {c[0]: c for c in cl}
        emb = rng.choice([0, 1000, 50_000])
        folds = walk_forward(cl, rng.randint(2, 6), emb)
        assert folds
        prev = -math.inf
        for f in folds:
            assert not set(f["train"]) & set(f["test"])
            for c in f["train"]:
                assert by[c][2] is not None and by[c][2] < f["test_start"] - emb
            starts = [by[c][1] for c in f["test"]]
            assert min(starts) >= prev and f["test_start"] == min(starts)
            prev = max(starts)
        tested = [c for f in folds for c in f["test"]]
        assert len(tested) == len(set(tested))


def test_b9_nested_selection_never_sees_outer_test():
    cl = [(f"k{i}", i * 1000, i * 1000 + 500) for i in range(40)]
    last_test = set(walk_forward(cl, 4, 0)[-1]["test"])
    perf = {"good": {c[0]: 1.0 for c in cl}, "cheat": {c[0]: 5.0 if c[0] in last_test else -1.0 for c in cl}}
    calls = []

    def score(trial, train, test):
        calls.append((trial, list(train), list(test)))
        return float(np.mean([perf[trial][c] for c in test]))

    out = nested_select(cl, ["good", "cheat"], score, n_outer=4, n_inner=3)
    assert len(out) == 4 and all(f["selected"] == "good" for f in out)
    assert score("cheat", [], list(last_test)) > score("good", [], list(last_test))  # best only on outer test
    calls.pop(), calls.pop()
    i = 0
    for f in out:  # calls before each outer score are that fold's inner (selection) calls
        while calls[i][2] != f["test"]:
            _, tr, te = calls[i]
            assert set(tr) | set(te) <= set(f["train"]) and not (set(tr) | set(te)) & set(f["test"])
            i += 1
        assert calls[i][0] == f["selected"]
        i += 1
    assert i == len(calls)


def test_b10_cpcv():
    rng = random.Random(10)
    cl = [(f"k{i}", f, f + rng.randint(0, 30_000)) for i, f in enumerate(sorted(rng.sample(range(10**6), 60)))]
    emb = 5000
    splits = cpcv(cl, 6, 2, emb)
    assert len(splits) == 15
    assert Counter(g for s in splits for g in s["test_groups"]) == {g: 5 for g in range(6)}
    groups = np.array_split(np.arange(60), 6)
    by = {c[0]: c for c in cl}
    for s in splits:
        spans = [(cl[groups[g][0]][1], max(cl[i][2] for i in groups[g])) for g in s["test_groups"]]
        assert not set(s["train"]) & set(s["test"])
        for c in s["train"]:
            _, f, r = by[c]
            assert all(r < lo or f > hi for lo, hi in spans)
            assert all(not (hi < f <= hi + emb) for _, hi in spans)


# ---- B11 / B12: DSR and PBO --------------------------------------------------------------------------------------

def test_b11_dsr():
    d = dsr(0.10, 250, 0.0, 3.0, 10, 0.05 ** 2)
    assert d["sr0"] == pytest.approx(0.07873, abs=1e-4) and d["dsr"] == pytest.approx(0.6311, abs=1e-3)
    assert dsr(0.10, 250, 0.0, 3.0, 1, 0.0)["dsr"] == pytest.approx(0.9423, abs=1e-3)
    by_n = [dsr(0.10, 250, 0, 3, n, 0.0025)["dsr"] for n in (2, 10, 100, 1000)]
    by_v = [dsr(0.10, 250, 0, 3, 10, v)["dsr"] for v in (0.0001, 0.0025, 0.01)]
    assert by_n == sorted(by_n, reverse=True) and by_v == sorted(by_v, reverse=True)
    r = np.random.default_rng(1).normal(0.1, 1, 300)
    out = deflated_sharpe(r, [0.0, 0.05, 0.1])
    assert out["T"] == 300 and out["N"] == 3


def test_b12_pbo():
    rng = np.random.default_rng(12)
    X = rng.normal(0, 1, (1000, 50))
    assert 0.3 <= pbo(X, 16)["pbo"] <= 0.7
    X[:, 0] += 0.2
    assert pbo(X, 16)["pbo"] <= 0.1


# ---- B13: random-entry baselines ---------------------------------------------------------------------------------

def test_b13_random_entry():
    store = script_store()
    res = replay(ScriptEngine(), store, T0, T0 + 8000, RTT, outcomes={"c1": 1})
    want = sorted((e["cluster_id"], e["size"]) for e in res["entries"])
    assert want == [("BTC@x", 10.0), ("BTC@x", 60.0)]
    a = random_entry(store, res, R=30, seed=1)
    for run in a["intents"]:
        assert sorted((MK[cid].event_group, size) for _, cid, _, size in run) == want
        assert all(T0 <= t <= T0 + 8000 for t, *_ in run)
    assert a["fees"] > 0 and len(a["baseline"]) == 30 and 0 <= a["percentile"] <= 100
    assert a == random_entry(store, res, R=30, seed=1)
    assert a["intents"] != random_entry(store, res, R=30, seed=2)["intents"]


# ---- B14: trial log ----------------------------------------------------------------------------------------------

def test_b14_trial_log_append_only(tmp_path):
    log = TrialLog(tmp_path / "trials.jsonl")
    log.append("fam", {"a": 1}, {"d": 1}, statistic=0.1, sharpe=0.2, clusters=5, ts_ms=1)
    log.append("fam", {"a": 2}, {"d": 1}, status="failed", ts_ms=2)
    log.append("other", {"a": 1}, {"d": 1}, sharpe=0.0, ts_ms=3)
    before = log.path.read_bytes()
    log.append("fam", {"a": 3}, {"d": 1}, sharpe=-0.1, status="discarded", ts_ms=4)
    after = log.path.read_bytes()
    assert after.startswith(before) and after.count(b"\n") == 4
    assert log.count("fam") == 3 and log.sharpes("fam") == [0.2, -0.1]
    rows = log.rows()
    assert set(rows[0]) >= {"trial_id", "family", "params_hash", "dataset_hash", "statistic", "sharpe", "clusters",
                            "ts"}
    r = np.random.default_rng(0).normal(0.1, 1, 100)
    assert deflated_sharpe(r, log.sharpes("fam"), n_trials=log.count("fam"))["N"] == 3
    src = inspect.getsource(validate.TrialLog)
    assert "append_jsonl" in src and not any(s in src for s in ("write_text", "write_bytes", "unlink", '"w"', "'w'"))


def test_b16_no_order_path_imports():
    import pathlib
    import re
    pat = re.compile(r"^\s*(import|from)\s+(httpx|urllib|requests|websockets|socket|py_clob_client|eth_account|"
                     r"trader\.live|tools)", re.M)
    root = pathlib.Path(validate.__file__).parent
    assert not [p.name for p in root.glob("*.py") if pat.search(p.read_text(encoding="utf-8"))]
    assert "common.get_json" in inspect.getsource(cli.fetch_ref)
