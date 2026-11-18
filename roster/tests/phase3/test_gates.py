"""WP3-D: capital ladder (D1, D2) and the fast Up/Down maker-first engine (D3-D6). Temporary ledgers, no network."""
import ast
import builtins
import io
import itertools
import math
import pathlib
import random

import numpy as np
import pytest

from trader.contracts import Book, MarketInfo
from trader.engines.ladder import MIN_MS, invariant_ok, reason_fmq, shrink
from trader.growth import capital
from trader.growth import fast_updown as fu
from trader.growth.fast_updown import FastUpDownMaker, latency_gate, twap_up
from trader.kernel import RiskKernel
from trader.ledger import Ledger, human_token

KEY = "fake-human-key"
LATER = 10 ** 13                       # now_ms for ledger reads: after every row the counting clock writes


@pytest.fixture
def L(tmp_path):
    led = Ledger(path=tmp_path / "t.db", clock=itertools.count(1000, 1000).__next__)
    yield led
    led.close()


def pre(L, name, n=200, pass_z=2.0):
    L.preregister({"name": name, "n": n, "pass_z": pass_z, "statistic": "fee-net P&L per market"})


def result(L, name, n=250, mean=0.03, se=0.01, cap=50, **kw):
    L.record(capital.RESULTS, {"test": name, "n": n, "mean": mean, "se": se, "cap_usd": cap,
                               "evidence": f"replay:{name}", **kw}, 0)


# ---------- D1 test_passed ----------

def test_passed_refusals_and_valid_case(L):
    assert capital.test_passed(L, "nope", LATER) == (False, "no pre-registration 'nope'")
    pre(L, "t0")
    ok, why = capital.test_passed(L, "t0", LATER)
    assert not ok and "0 result rows" in why                                   # zero rows
    pre(L, "t2"), result(L, "t2"), result(L, "t2")
    ok, why = capital.test_passed(L, "t2", LATER)
    assert not ok and "2 result rows" in why                                   # two rows: test once
    pre(L, "small"), result(L, "small", n=199)
    ok, why = capital.test_passed(L, "small", LATER)
    assert not ok and "n 199 < pre-registered 200" in why
    pre(L, "weak"), result(L, "weak", mean=0.02, se=0.01, verdict="PASS")    # mean == 2 se, row says PASS
    ok, why = capital.test_passed(L, "weak", LATER)
    assert not ok and "<= 2 x se" in why
    pre(L, "zse"), result(L, "zse", se=0.0)
    assert not capital.test_passed(L, "zse", LATER)[0]
    result(L, "early"), pre(L, "early")                                        # recorded before the pre-registration
    ok, why = capital.test_passed(L, "early", LATER)
    assert not ok and "before its pre-registration" in why
    pre(L, "good"), result(L, "good", cap=50)
    assert capital.test_passed(L, "good", LATER) == (True, "passed")
    assert capital.test_passed(L, "good", LATER, cap_usd=50) == (True, "passed")
    ok, why = capital.test_passed(L, "good", LATER, cap_usd=250)              # cap mismatch
    assert not ok and "not 250" in why
    assert not capital.test_passed(L, "good", 0)[0]                            # as_of: not visible before recording


# ---------- D2 capital ladder ----------

def tok(version, nonce):
    return human_token(KEY, f"promote:{capital.NAME}:{version}:live", nonce)


def test_capital_ladder(L, monkeypatch):
    monkeypatch.setenv("ROSTER_HUMAN_KEY", KEY)
    cap = lambda: capital.current_cap(L)
    assert cap() == 50.0                                                       # fresh ledger
    pre(L, "t50"), result(L, "t50", cap=50)
    pre(L, "t-other"), result(L, "t-other", cap=250)
    with pytest.raises(ValueError, match="next step"):
        capital.promote_step(L, 500, "t50", "s1", tok("500", "s1"), LATER)    # skip 50 -> 500
    assert cap() == 50.0
    with pytest.raises(ValueError, match="run at cap"):
        capital.promote_step(L, 250, "t-other", "s2", tok("250", "s2"), LATER)  # passed at another cap
    assert cap() == 50.0
    with pytest.raises(PermissionError):
        capital.promote_step(L, 250, "t50", "n1", "bad-signature", LATER)     # bad token
    assert cap() == 50.0
    assert capital.promote_step(L, 250, "t50", "n1", tok("250", "n1"), LATER) == 250.0  # retry completes the step
    assert cap() == 250.0

    pre(L, "t250"), result(L, "t250", cap=250)
    with pytest.raises(PermissionError, match="already used"):
        capital.promote_step(L, 500, "t250", "n1", tok("500", "n1"), LATER)   # reused nonce
    assert cap() == 250.0
    with pytest.raises(ValueError):
        capital.promote_step(L, 50, "t250", "n2", tok("50", "n2"), LATER)     # no stepping down
    assert capital.promote_step(L, 500, "t250", "n2", tok("500", "n2"), LATER) == 500.0
    pre(L, "t500"), result(L, "t500", cap=500)
    assert capital.promote_step(L, 1000, "t500", "n3", tok("1000", "n3"), LATER) == 1000.0
    pre(L, "t1000"), result(L, "t1000", cap=1000)
    with pytest.raises(ValueError):
        capital.promote_step(L, 2000, "t1000", "n4", tok("2000", "n4"), LATER)  # past the last step
    assert cap() == 1000.0

    vs = {v["version"]: v for v in L.versions(capital.NAME)}                  # every step, with its evidence
    assert set(vs) == {"250", "500", "1000"}
    for v, frm, test in (("250", 50, "t50"), ("500", 250, "t250"), ("1000", 500, "t500")):
        p = vs[v]["params"]
        assert p["cap_usd"] == float(v) and p["from_usd"] == frm and p["test"] == test
        assert p["evidence"] == f"replay:{test}" and p["result"]["test"] == test
    assert vs["1000"]["state"] == "live" and vs["250"]["state"] == vs["500"]["state"] == "retired"

    L.promote(capital.NAME, "1000", "retired")                                # automatic demotion
    assert cap() == 50.0
    with pytest.raises(ValueError, match="retired"):
        capital.promote_step(L, 250, "t50", "n5", tok("250", "n5"), LATER)    # re-climb needs a new test
    pre(L, "t50b"), result(L, "t50b", cap=50)
    assert capital.promote_step(L, 250, "t50b", "n6", tok("250-2", "n6"), LATER) == 250.0
    assert L.registry_live(capital.NAME)["version"] == "250-2"


# ---------- D3 TWAP pricer ----------

def test_twap_properties():
    w, sig = 60, 0.5
    # continuity at tau = w (mean and variance from both branches meet) and variance > 0 at every tau > 0
    assert twap_up(100, 100.3, 100.3, w, sig) == pytest.approx(twap_up(100, 100.3, 100.3, w * (1 - 1e-12), sig),
                                                                abs=1e-9)
    for tau in np.logspace(-3, 4, 50):
        assert 0.5 < twap_up(100, 100 + 1e-7, 100 + 1e-7, tau, sig) < 1.0     # finite, positive variance
    for tau in (60, 61, 300, 900, 14_400):
        assert twap_up(100, 100, None, tau, sig) == 0.5                       # x = open, tau >= w
    for tau, avg in ((300, None), (30, 100.0), (5, 99.9)):
        ps = [twap_up(100, x, avg, tau, sig) for x in np.linspace(98, 102, 81)]
        assert all(b > a for a, b in zip(ps, ps[1:]) if 1e-12 < a < 1 - 1e-12)  # increases in x
        assert all(b >= a for a, b in zip(ps, ps[1:]))
    assert twap_up(100, 100, 100, 0, sig) == 1.0                               # tie at tau = 0 resolves Up
    assert twap_up(100, 99, 99.99, 0, sig) == 0.0


@pytest.mark.parametrize("tau, done", [(70.0, 0.0), (40.0, 20.0)])
def test_twap_monte_carlo(tau, done):
    """Seeded ABM paths; TWAP = mean over the last w s. done = seconds of the window already realised."""
    rng, w, sig, dt, n = np.random.default_rng(7), 60.0, 0.2, 0.5, 20_000
    open_px, x = 100.0, 100.4
    k = int(round(tau / dt))
    paths = x + sig * np.cumsum(rng.standard_normal((n, k)) * math.sqrt(dt), axis=1)
    avg = 100.6 if done else None
    future = paths[:, -int(round((w - done) / dt)):]                          # the unrealised part of the window
    twap = (done * avg + future.mean(axis=1) * (w - done)) / w if done else future.mean(axis=1)
    p_mc = float((twap >= open_px).mean())
    se = math.sqrt(p_mc * (1 - p_mc) / n)
    assert abs(p_mc - twap_up(open_px, x, avg, tau, sig, w)) < 3 * se + 0.005


# ---------- fast engine fixtures ----------

START = 1_800_000_000_000 // (15 * MIN_MS) * (15 * MIN_MS)
END = START + 15 * MIN_MS
NOW = START + 2 * MIN_MS
OPEN = 60_000.0
KERNEL = RiskKernel(secret="x", nonce_path=None)


def mkt(asset="BTC", end=END, dur="15m", min_size=5.0):
    c = f"{asset}-{dur}"
    return MarketInfo(c, f"{c}-up", f"{c}-down", "crypto-fast", f"{asset} Up or Down", "r", 0.01, min_size, 0.07,
                      False, end, f"{asset}-{dur}@2027-01-15T08:00Z", asset=asset, kind="updown")


def books_for(m, ts, up=(0.50, 0.54), down=(0.46, 0.50)):
    return {m.token_yes: Book(m.token_yes, [(up[0], 100.0)], [(up[1], 100.0)], ts),
            m.token_no: Book(m.token_no, [(down[0], 100.0)], [(down[1], 100.0)], ts)}


def ref(price, ts):
    return {a: {"price": price, "ts_ms": ts, "dvol": 50.0} for a in ("BTC", "ETH", "SOL")}


def engine(assets=("BTC",), params=None, edges=None, start=START):
    eng = FastUpDownMaker(assets, params, edges)
    for ts in (start - 70_000, start - 3_000):                              # crossing start - 4 s: the trailing TWAP open
        assert eng.on_tick(ts, {}, {}, ref(OPEN, ts), {}) == []
    return eng


def decide(eng, ms, now=NOW, x=OPEN + 60, ref_ts=None, books=None, positions=None):
    bk = books or {k: v for m in ms for k, v in books_for(m, now).items()}
    return eng.on_tick(now, {m.cid: m for m in ms}, bk, ref(x, now if ref_ts is None else ref_ts), positions or {})


def makers(out):
    return [i for i in out if i.kind == "maker"]


def takers(out):
    return [i for i in out if i.kind == "taker"]


# ---------- D4 gate ----------

def e6(L, by_asset, **top):
    L.preregister(fu.LATENCY_PREREG)
    L.record(capital.RESULTS, {"test": fu.LATENCY_PREREG["name"], "n": 400, "mean": 0.02, "se": 0.005,
                               "cap_usd": 50, "evidence": "e6 recordings", "by_asset": by_asset, **top}, 0)


def test_gate_closed_without_e6_row(L):
    assert latency_gate(L, LATER) == set()                                     # no pre-registration, no row
    L.preregister(fu.LATENCY_PREREG)
    assert latency_gate(L, LATER) == set()                                     # pre-registered, no row
    eng, rng = engine(latency_gate(L, LATER)), random.Random(1)
    for _ in range(300):
        ms = [mkt(a, dur=d, end=START + rng.choice((5, 15)) * MIN_MS) for a in ("BTC", "ETH") for d in ("5m", "15m")]
        now = START + rng.randrange(1, 15 * MIN_MS)
        assert decide(eng, ms, now, OPEN * rng.uniform(0.99, 1.01)) == []


def test_gate_pooled_pass_counts_for_nothing(L):
    L.preregister(fu.LATENCY_PREREG)
    L.record(capital.RESULTS, {"test": "latency-e6-v1", "n": 400, "mean": 0.02, "se": 0.005, "cap_usd": 50,
                               "evidence": "pooled only"}, 0)
    assert latency_gate(L, LATER) == set()


def test_gate_btc_passes_eth_fails(L):
    e6(L, {"BTC": {"n": 250, "mean": 0.03, "se": 0.01},                      # 3 SE, n >= 200: pass
           "ETH": {"n": 250, "mean": 0.015, "se": 0.01},                     # 1.5 SE: fail
           "SOL": {"n": 150, "mean": 0.05, "se": 0.01}})                     # n < 200: fail
    assert latency_gate(L, LATER) == {"BTC"} and fu.e6_edges(L, LATER) == {"BTC": 0.03}
    out = decide(engine(latency_gate(L, LATER)), [mkt("BTC"), mkt("ETH"), mkt("SOL")])
    assert out and {i.cid for i in out} == {"BTC-15m"}


def test_engine_reads_no_files(L, monkeypatch):
    tree = ast.parse(pathlib.Path(fu.__file__).read_text(encoding="utf-8"))
    calls = {n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", "")
             for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert not calls & {"open", "read_text", "read_bytes", "loads", "load", "Path"}
    e6(L, {"BTC": {"n": 250, "mean": 0.03, "se": 0.01}})

    def no_files(*a, **k):
        raise AssertionError(f"file read: {a}")
    for target, attr in ((builtins, "open"), (io, "open"), (pathlib.Path, "open"), (pathlib.Path, "read_text")):
        monkeypatch.setattr(target, attr, no_files)
    assert decide(engine(latency_gate(L, LATER)), [mkt("BTC")])               # gate + engine, no file opened


# ---------- D5 maker ----------

def test_maker_bids_both_outcomes():
    m = mkt()
    out = decide(engine(), [m])
    up, down = (next(i for i in out if i.token_id == t) for t in (m.token_yes, m.token_no))
    assert len(out) == 2 and all(i.kind == "maker" and i.side == "BUY" for i in out)
    for i in out:
        assert i.size == m.min_size <= fu.MAX_SHARES
        assert round(i.price / m.tick_size, 9) == round(i.price / m.tick_size)   # on the tick grid
        assert i.price <= i.fair - fu.PARAMS["half"] + 1e-12
        f, mm, q = reason_fmq(i.reason)
        assert q == i.fair and invariant_ok(q, f, mm)
    assert up.price < 0.54 and down.price < 0.50                               # post-only: below the ask
    assert up.fair + down.fair == pytest.approx(1.0)
    assert up.fair > 0.52                                                      # x above the open: Up favoured
    assert decide(engine(), [mkt(min_size=6.0)]) == []                         # min_size above max_shares


def test_shrink_invariant_random():
    rng = random.Random(23)
    for _ in range(10_000):
        f, m = rng.random(), rng.random()
        assert invariant_ok(shrink(f, m, fu.PARAMS["c_shrink"]), f, m)


@pytest.mark.parametrize("why", ["close", "stale_book", "stale_feed", "sharp_move", "book_integrity"])
def test_pull_rules_remove_quotes(why):
    m = mkt()
    live = lambda: engine(edges={"BTC": 0.05}, params={"min_edge": -1.0})  # a taker fires when not pulled
    base = decide(live(), [m])
    assert makers(base) and takers(base)
    eng, now, kw = live(), NOW, {}
    if why == "close":
        now = END - 30_000
    elif why == "stale_book":
        kw["books"] = books_for(m, NOW - 6_000)
    elif why == "stale_feed":
        kw["ref_ts"] = NOW - 3_000
    elif why == "sharp_move":
        decide(eng, [], NOW - 5_000, OPEN)                                    # +1% in 5 s
        kw["x"] = OPEN * 1.01
    else:
        kw["books"] = books_for(m, NOW, up=(0.40, 0.45))                      # asks sum 0.95 < 1
    assert decide(eng, [m], now, **kw) == []


def test_empty_gtd_window_no_maker():
    m = mkt()
    now = END - 4 * MIN_MS                    # now + 2 min + 45 s > end - 2 min, yet not pulled (close is end - 1 min)
    assert fu.gtd_expiry(now, END, fu.PARAMS) is None
    assert decide(engine(), [m], now) == []
    out = decide(engine(edges={"BTC": 0.05}, params={"min_edge": -1.0}), [m], now)
    assert out and not makers(out)                                             # takers may still trade


def test_every_maker_expiry_meets_kernel_gtd():
    rng, n = random.Random(5), 0
    for _ in range(1_500):
        dur, mins = rng.choice((("5m", 5), ("15m", 15), ("4h", 240)))
        m = mkt(dur=dur, end=START + mins * MIN_MS)
        now = START + rng.randrange(1, mins * MIN_MS)
        b = rng.uniform(0.05, 0.85)
        a = b + rng.choice((0.01, 0.02, 0.04, 0.08))
        books = books_for(m, now, up=(round(b, 2), round(a, 2)), down=(round(1 - a, 2), round(1 - b, 2)))
        for i in makers(decide(engine(), [m], now, OPEN * rng.uniform(0.998, 1.002), books=books)):
            n += 1
            assert KERNEL.gtd(i, m, now) is None
            f, mm, q = reason_fmq(i.reason)
            assert invariant_ok(q, f, mm) and i.size == m.min_size
    assert n > 500                                                             # the property was exercised


# ---------- D6 taker ----------

def test_taker_rules():
    m, x = mkt(), OPEN + 400                                                   # f ~ 0.9, q ~ 0.64 vs ask 0.54
    eng = engine(edges={"BTC": 0.01})
    out = decide(eng, [m], x=x)
    (t,) = takers(out)
    assert (t.token_id, t.price, t.size, t.expiry_ms) == (m.token_yes, 0.54, m.min_size, NOW + fu.PARAMS["give_up_ms"])
    fmq = reason_fmq(t.reason)
    assert fmq[2] - 0.54 - 0.07 * 0.54 * 0.46 - fu.PARAMS["slippage"] > fu.PARAMS["min_edge"]
    assert sum(i.size for i in out if i.token_id == m.token_yes) <= fu.MAX_SHARES  # no Up bid on top of the taker
    later = decide(eng, [m], NOW + 1_000, x=x)
    assert not takers(later)                                                   # one at a time per market
    assert not [i for i in later if i.token_id == m.token_yes]                 # in-flight taker still counts
    assert takers(decide(eng, [m], NOW + 3_000, x=x))                          # after the give-up deadline

    assert not takers(decide(engine(), [m], x=x))                              # no measured E6 edge
    assert not takers(decide(engine(edges={"BTC": 0.0}), [m], x=x))
    assert not takers(decide(engine(edges={"BTC": -0.01}), [m], x=x))
    assert not takers(decide(engine(edges={"BTC": 0.01}, params={"min_edge": 0.2}), [m], x=x))  # edge <= min_edge
    assert decide(engine(edges={"BTC": 0.01}), [m], x=x, ref_ts=NOW - 3_000) == []           # pulled
    held = decide(engine(edges={"BTC": 0.01}), [m], x=x, positions={m.token_yes: 1.0})
    assert not [i for i in held if i.token_id == m.token_yes]                  # 1 held + 5 > max_shares
    with pytest.raises(ValueError):
        FastUpDownMaker({"BTC"}, {"max_shares": 6.0})


def test_open_is_the_trailing_twap_before_the_settlement_boundary():
    """16 Oct: priceToBeat is the Chainlink 60 s TWAP at the start (window [start - 64 s, start - 4 s] on spot)."""
    eng = FastUpDownMaker(("BTC",))
    for ts, px in ((START - 70_000, 100.0), (START - 34_000, 102.0), (START - 3_000, 999.0)):   # 30 s @100, 30 s @102
        eng.on_tick(ts, {}, {}, ref(px, ts), {})
    assert eng._opens[("BTC", START)] == pytest.approx(101.0)        # the crossing tick itself is not in the average
    late = FastUpDownMaker(("BTC",))
    for ts in (START - 70_000, START + 5_000):                        # first tick 9 s after the boundary: no open
        late.on_tick(ts, {}, {}, ref(100.0, ts), {})
    assert ("BTC", START) not in late._opens
