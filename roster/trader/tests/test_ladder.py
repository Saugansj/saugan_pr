"""WP1-D acceptance tests (D1-D7) for trader/engines/ladder.py. Fakes only: no other work package is imported."""
import datetime as dt
import math
import random
from statistics import NormalDist

import pytest

from trader.contracts import Book, Fill, MarketInfo
from trader.engines import ladder as L

H = L.H_MS
E = int(dt.datetime(2026, 10, 2, 16, tzinfo=dt.timezone.utc).timestamp() * 1000)   # 12:00 ET print
P = L.PARAMS
N = NormalDist().cdf


def mk(cid, strike=80_000.0, kind="strike", asset="BTC", mode="crypto-term", end=E, tick=0.01):
    return MarketInfo(cid=cid, token_yes=cid + "Y", token_no=cid + "N", mode=mode, question="", rules_sha256="r",
                      tick_size=tick, min_size=5.0, fee_rate=0.07, neg_risk=False, end_ms=end,
                      event_group=f"{asset}@{end}", asset=asset, strike=strike, kind=kind, source_id="binance")


def books_for(m, mid, ts, half=0.01, size=100.0):
    """Mirrored YES/NO books around a YES mid, as Polymarket shows them."""
    return {m.token_yes: Book(m.token_yes, [(round(mid - half, 4), size)], [(round(mid + half, 4), size)], ts),
            m.token_no: Book(m.token_no, [(round(1 - mid - half, 4), size)], [(round(1 - mid + half, 4), size)], ts)}


def ref_at(now, price=80_000.0, dvol=50.0, **kw):
    return {"BTC": {"price": price, "ts_ms": now, "dvol": dvol, "final": {}, **kw}}


def fv(f, unc=0.01, vol=0.01):
    return {"f": f, "unc": unc, "vol": vol, "tau_h": 6.0}


def bids(intents, m):
    return {("Y" if i.token_id == m.token_yes else "N"): i for i in intents}


# ---------- D1 pricer ----------

def test_digital_matches_closed_form():
    assert L.digital(100, 100, 0.5, L.YEAR_H) == pytest.approx(0.4012937, abs=1e-7)   # N(-0.25), by hand
    s = 0.4 * math.sqrt(0.25)
    assert L.digital(110, 100, 0.4, 0.25 * L.YEAR_H) == pytest.approx(N((math.log(1.1) - s * s / 2) / s), abs=1e-12)
    # Phase 0's numpy pricer (research/kappa, read-only)
    kp = pytest.importorskip("research.kappa.kappa")
    for S, K, sig, h in [(84_000, 86_000, 0.36, 9.0), (2_700, 2_600, 0.5, 1.0), (80_000, 80_000, 0.3, 24)]:
        assert L.digital(S, K, sig, h) == pytest.approx(float(kp.digital(S, K, sig, h / L.YEAR_H)), abs=1e-12)


def test_digital_reproduces_phase0_on_a_replayed_day():
    pd = pytest.importorskip("pandas")
    path = L.__file__.replace("trader\\engines\\ladder.py", "research\\kappa\\out\\binary.parquet") \
        .replace("trader/engines/ladder.py", "research/kappa/out/binary.parquet")
    try:
        b = pd.read_parquet(path)
    except (FileNotFoundError, OSError):
        pytest.skip("Phase 0 output not present")
    day = b[b["day"] == b["day"].max()]
    assert len(day) > 10
    for r in day.itertuples():
        assert L.digital(r.S_t, r.K, r.kappa * r.sigma_q, r.bucket) == pytest.approx(r.p_k, abs=1e-9)


def test_complement_and_decreasing_in_strike():
    S, sig, h = 80_000, 0.45, 6.0
    s = sig * math.sqrt(h / L.YEAR_H)
    prev = 1.0
    for K in range(77_000, 83_001, 50):                       # +/- 3 SD: p strictly inside (0, 1)
        p_gt = L.digital(S, K, sig, h)
        p_le = N((math.log(K / S) + s * s / 2) / s)          # model CDF at K, computed independently
        assert p_gt + p_le == pytest.approx(1.0, abs=1e-12)
        assert p_gt < prev
        prev = p_gt


def test_kappa_applied_per_bucket():
    assert [L.kappa_for(h) for h in (48, 24, 12.5, 11.5, 6, 2.5, 2.4, 1, 0.1)] == \
           [0.905, 0.905, 0.905, 1.034, 1.034, 1.034, 1.150, 1.150, 1.150]
    m = mk("a")
    for bucket, k in ((24, 0.905), (6, 1.034), (1, 1.150)):
        now = E + 60_000 - bucket * H                         # tau to the settlement candle's close
        v = L.fair_value(m, ref_at(now)["BTC"], now, P)
        assert v["kappa"] == k and v["sigma_p"] == pytest.approx(k * 0.50)
        assert v["f"] == pytest.approx(L.digital(80_000, 80_000, k * 0.5, bucket))


def test_updown_open_and_ties():
    m = mk("u", strike=None, kind="updown")
    start = L.prev_noon_ms(E)
    assert start == E - 24 * H
    # DST ends 2026-11-01: noon Oct 31 (EDT, 16:00Z) to noon Nov 1 (EST, 17:00Z) is 25 h, then 24 h again
    nov1 = int(dt.datetime(2026, 11, 1, 17, tzinfo=dt.timezone.utc).timestamp() * 1000)
    assert L.prev_noon_ms(nov1) == nov1 - 25 * H and L.prev_noon_ms(nov1 + 24 * H) == nov1
    before = start - 2 * H                                    # open not printed: p = N(-s/2) over the 24 h window
    s = 0.905 * 0.5 * math.sqrt(24 / L.YEAR_H)
    assert L.fair_value(m, ref_at(before)["BTC"], before, P)["f"] == pytest.approx(N(-s / 2))
    now = E + 60_000 - 6 * H
    r = ref_at(now, price=81_000, final={start: 80_000.0})["BTC"]
    assert L.fair_value(m, r, now, P)["f"] == pytest.approx(L.digital(81_000, 80_000, 1.034 * 0.5, 6))
    r = ref_at(now, price=81_000, final={start + 60_000: 80_000.0})["BTC"]   # keyed by the candle's close time
    assert L.fair_value(m, r, now, P)["K"] == 80_000.0
    assert "err" in L.fair_value(m, ref_at(now)["BTC"], now, P)              # open missing after the print


# ---------- D2 universe checkpoints ----------

def test_checkpoint_rows_for_every_ladder_market():
    ladder = [mk("s1", 78_000), mk("s2", 80_000), mk("s3", 82_000), mk("u1", None, "updown"),
              mk("e1", 2_600, asset="ETH")]
    other = [mk("f1", None, "updown", mode="crypto-fast"), mk("h1", None, "updown", mode="crypto-hourly")]
    markets = {m.cid: m for m in ladder + other}
    eng = L.LadderEngine()
    seen = []
    for bucket in (24, 12, 6, 1):
        now = E + 60_000 - bucket * H
        books = books_for(ladder[1], 0.5, now)                # only one market has a book: rows are for all
        ref = {**ref_at(now, final={E - 24 * H: 80_000.0}), "ETH": {"price": 2_650, "ts_ms": now, "dvol": 60}}
        eng.on_tick(now, markets, books, ref, {})
        eng.on_tick(now + 1_000, markets, books, ref, {})     # a second tick at the same checkpoint: no duplicates
        rows = [r for t, r, _ in eng.records if t == "universe_checkpoint"]
        eng.records.clear()
        seen += rows
        if bucket == 12:
            assert rows == []
            continue
        assert sorted(r["cid"] for r in rows) == sorted(m.cid for m in ladder)
        assert all(r["bucket_h"] == bucket and r["fair"] is not None and r["cluster"] == f"crypto-term@{E}"
                   for r in rows)
    assert len({r["id"] for r in seen}) == len(seen) == 15
    assert any(r["mid_ex_own"] == 0.5 for r in seen) and any(r["mid_ex_own"] is None for r in seen)


def test_checkpoint_not_written_late():
    eng = L.LadderEngine()
    now = E + 60_000 - 5 * H                                  # started after the 6h checkpoint window
    eng.on_tick(now, {"s": mk("s")}, {}, ref_at(now), {})
    assert not [r for t, r, _ in eng.records if t == "universe_checkpoint"]


# ---------- D3 selector ----------

def test_reward_zero_below_min_size():
    bids_ = [(0.52, 0.49), (0.48, 0.45)]
    rw = {"min_size": 50, "daily_rate": 20.0}
    base = L.income_per_dollar(bids_, 0.07, 6, 10, None, 0.0, P)
    assert L.income_per_dollar(bids_, 0.07, 6, 10, rw, 0.0, P) == base
    assert L.income_per_dollar(bids_, 0.07, 6, 60, rw, 0.0, P) > base
    # spread + rebate - markout - lockup, divided by capital, by hand
    lock = 0.2 * (6 + 2 + 0.01 * 72) / L.YEAR_H
    num = sum(f - px + 0.2 * 0.07 * px * (1 - px) - 0.01 - px * lock for f, px in bids_)
    assert L.income_per_dollar(bids_, 0.07, 6, 10, None, 0.01, P) == pytest.approx(num / 0.94)


def test_ties_go_to_shorter_dated():
    cands = [{"cid": "a", "income": 0.05, "end_ms": E + 24 * H}, {"cid": "b", "income": 0.05, "end_ms": E},
             {"cid": "c", "income": 0.06, "end_ms": E + 48 * H}]
    assert [c["cid"] for c in L.rank(cands)] == ["c", "b", "a"]
    # through the engine: identical markets except the date, no lockup term, one slot
    p = {"r_lock": 0.0, "max_markets": 1, "pull_before_close_ms": 0}
    near, far = mk("near", end=E), mk("far", end=E + 12 * H)
    now = E - 6 * H
    books = {**books_for(near, 0.5, now), **books_for(far, 0.5, now)}
    v = {"f": 0.5, "unc": 0.0, "vol": 0.0, "tau_h": 6.0}
    a, _ = L.market_intents(near, v, books[near.token_yes], books[near.token_no], {}, {}, now, {**P, **p})
    b, _ = L.market_intents(far, v, books[far.token_yes], books[far.token_no], {}, {}, now, {**P, **p})
    assert [(i.price, i.size) for i in a] == [(i.price, i.size) for i in b]
    eng = L.LadderEngine(p)
    out = eng.on_tick(now, {"far": far, "near": near}, books, ref_at(now, price=80_000), {})
    rank = [r for t, r, _ in eng.records if t == "selector_ranking"][0]
    assert rank["chosen"] == ["near"] and {i.cid for i in out} == {"near"}
    assert {"income", "bids", "size", "markout", "reward", "tau_h"} <= set(rank["ranking"][0])


# ---------- D4 quote engine ----------

def _intents(f=0.5, mid=0.5, unc=0.01, vol=0.01, positions=None, cost=None, now=E - 6 * H, m=None, p=None, half=0.01):
    m = m or mk("q")
    b = books_for(m, mid, now, half=half)
    out, err = L.market_intents(m, fv(f, unc, vol), b[m.token_yes], b[m.token_no], positions or {}, cost or {},
                                now, {**P, "max_book_width": 1.0, **(p or {})})   # wide test books: no post-only clip
    return bids(out, m), err


def test_spread_widens_with_uncertainty_and_vol():
    tight, _ = _intents(unc=0.0, vol=0.0, half=0.1)
    wide, _ = _intents(unc=0.05, vol=0.0, half=0.1)
    wider, _ = _intents(unc=0.05, vol=0.04, half=0.1)
    for k in "YN":
        assert tight[k].price > wide[k].price > wider[k].price
    assert 1 - tight["Y"].price - tight["N"].price < 1 - wide["Y"].price - wide["N"].price


def test_skew_follows_inventory():
    flat, _ = _intents(half=0.1)
    long_yes, _ = _intents(positions={"qY": 30.0}, cost={"qY": 0.40}, half=0.1)
    long_no, _ = _intents(positions={"qN": 30.0}, cost={"qN": 0.40}, half=0.1)
    assert long_yes["Y"].price < flat["Y"].price and long_yes["N"].price > flat["N"].price
    assert long_no["N"].price < flat["N"].price and long_no["Y"].price > flat["Y"].price
    assert long_yes["Y"].size == 10 and long_yes["Y"].reduces_exposure is False


def test_complement_bid_keeps_pair_below_one_minus_margin():
    # holding 20 YES bought at 0.60; the plain NO bid would be ~0.48, the cap is 1 - 0.60 - 0.01 = 0.39
    got, _ = _intents(f=0.5, positions={"qY": 20.0}, cost={"qY": 0.60}, half=0.1)
    no = got["N"]
    assert no.reduces_exposure and no.size == 10 and no.reason.startswith("complement")
    assert 0.60 + no.price < 1 - P["complement_margin"]
    # cap exactly on the tick grid (1 - 0.55 - 0.01 = 0.44): strictly below it
    got, _ = _intents(f=0.4, mid=0.4, positions={"qY": 7.0}, cost={"qY": 0.55}, half=0.1)
    assert got["N"].price == pytest.approx(0.43) and got["N"].size == 7
    # unknown cost of what we hold: no complement bid, the other side still quotes
    got, _ = _intents(positions={"qY": 20.0}, half=0.1)
    assert "N" not in got and "Y" in got
    # the engine learns the cost from fills
    eng = L.LadderEngine()
    eng.on_fill(Fill("o1", L.NAME, "q", "qY", "BUY", 0.60, 10, 0, True, 0.0))
    eng.on_fill(Fill("o2", L.NAME, "q", "qY", "BUY", 0.70, 10, 0, True, 0.0))
    eng.on_fill(Fill("o3", "btc-speed", "q", "qY", "BUY", 0.10, 10, 0, False, 0.0))   # other strategy: ignored
    assert eng.cost["qY"] == (20, pytest.approx(0.65))


def _engine_quotes(eng, now, m, books, ref, positions=None):
    return [i for i in eng.on_tick(now, {m.cid: m}, books, ref, positions or {}) if i.cid == m.cid]


def test_pull_rules():
    m = mk("p")
    now = E - 6 * H
    ok = books_for(m, 0.5, now)
    assert _engine_quotes(L.LadderEngine(), now, m, ok, ref_at(now)), "control: quotes when nothing is wrong"
    cases = {
        "close": (E - 9 * 60_000, None, None),               # 9 min before the print
        "near_close": (E - 59 * 60_000, None, None),         # v2: no quotes in the last hour
        "oracle gap": (E + 30 * 60_000, None, None),          # after the print, before settlement
        "stale_book": (now, books_for(m, 0.5, now - 120_000), None),
        "stale_feed": (now, None, ref_at(now - 10_000)),
    }
    for name, (t, b, r) in cases.items():
        b = b or books_for(m, 0.5, t)
        r = r or ref_at(t)
        assert _engine_quotes(L.LadderEngine(), t, m, b, r) == [], name
        if name != "oracle gap":
            assert L.pull_reason(m, b[m.token_yes], b[m.token_no], r["BTC"], t, 0, P) == name
    # sharp move: 4 sigma over 10 s at 50% vol is ~11 bp; a 30 bp jump in 2 s trips it, then a cooldown
    eng = L.LadderEngine()
    assert _engine_quotes(eng, now - 2_000, m, ok, ref_at(now - 2_000, 80_000))
    assert _engine_quotes(eng, now, m, ok, ref_at(now, 80_240)) == []
    assert [r for t, r, _ in eng.records if t == "sharp_move"]
    later = now + 30_000
    assert _engine_quotes(eng, later, m, books_for(m, 0.5, later), ref_at(later, 80_240)) == []   # cooling down
    later = now + 299_000
    assert _engine_quotes(eng, later, m, books_for(m, 0.5, later), ref_at(later, 80_240)) == []   # v2: 5 min quiet
    later = now + 301_000
    assert _engine_quotes(eng, later, m, books_for(m, 0.5, later), ref_at(later, 80_240))
    # a small move does not trip it
    eng = L.LadderEngine()
    _engine_quotes(eng, now - 2_000, m, ok, ref_at(now - 2_000, 80_000))
    assert _engine_quotes(eng, now, m, ok, ref_at(now, 80_040))


def test_requotes_on_reference_ticks():
    m = mk("r")
    now = E - 6 * H
    b = books_for(m, 0.5, now, half=0.1)
    eng = L.LadderEngine({"move_k": 1e9, "max_book_width": 1.0})
    first = bids(_engine_quotes(eng, now, m, b, ref_at(now, 80_000)), m)
    second = bids(_engine_quotes(eng, now + 1_000, m, b, ref_at(now + 1_000, 80_600)), m)
    assert second["Y"].price > first["Y"].price and second["N"].price < first["N"].price
    assert first["Y"].expiry_ms == second["Y"].expiry_ms <= m.end_ms - 3 * 60_000
    assert now + 5 * 60_000 <= first["Y"].expiry_ms <= now + 10 * 60_000


# ---------- D5 sizer ----------

def test_sizer_invariant_on_10000_random_intents():
    rng = random.Random(7)
    n = 0
    while n < 10_000:
        tick = rng.choice((0.01, 0.001))
        m = mk("z", tick=tick)
        mid = round(rng.uniform(0.03, 0.97) / tick) * tick
        f = rng.uniform(0.0, 1.0)
        net = rng.choice((0.0, 0.0, rng.uniform(-80, 80)))
        pos = {m.token_yes: max(net, 0.0), m.token_no: max(-net, 0.0)}
        cost = {t: rng.uniform(0.05, 0.95) for t in pos if rng.random() < 0.8}
        b = books_for(m, mid, 0, half=rng.choice((tick, 2 * tick, 0.03)), size=50)
        p = {**P, "quote_size": rng.choice((5.0, 7.3, 10.0, 25.55)), "max_inv": rng.choice((20.0, 50.0))}
        out, err = L.market_intents(m, fv(f, rng.uniform(0, 0.05), rng.uniform(0, 0.05)), b[m.token_yes],
                                    b[m.token_no], pos, cost, 0, p)
        assert err is None or err == "no usable mid"
        for i in out:
            ff, mm, qq = L.reason_fmq(i.reason)
            assert L.invariant_ok(qq, ff, mm) and qq == i.fair, i.reason
            own = net if i.token_id == m.token_yes else -net
            cap = min(-own, p["quote_size"]) if i.reduces_exposure else min(p["quote_size"], p["max_inv"] - own)
            assert m.min_size <= i.size <= cap + 1e-12                          # never rounds up, never sub-minimum
            assert i.price >= tick and abs(i.price / tick - round(i.price / tick)) < 1e-6
            assert i.price < b[i.token_id].best_ask()                           # post-only
            if i.reduces_exposure:
                other = m.token_no if i.token_id == m.token_yes else m.token_yes
                assert cost[other] + i.price < 1 - p["complement_margin"]
            n += 1
    for _ in range(10_000):
        f, m_ = rng.random(), rng.random()
        assert L.invariant_ok(L.shrink(f, m_), f, m_)
    assert not L.invariant_ok(0.7, 0.6, 0.5) and not L.invariant_ok(0.4, 0.6, 0.5) and not L.invariant_ok(*[math.nan] * 3)


def test_never_rounds_up_and_refuses_sub_minimum():
    rng = random.Random(3)
    for _ in range(10_000):
        x, step = rng.uniform(0, 100), rng.choice((0.01, 0.001, 1.0))
        y = L.floor_to(x, step)
        assert y <= x and x - y < step + 1e-9
    assert L.floor_to(0.29, 0.01) == 0.29 and L.floor_to(4.999, 0.01) == 4.99
    assert L.taker_shares(0.25, 100.0, 0.5, 4.99, 5.0) == 0.0            # only 4.99 on offer: refused
    assert L.taker_shares(0.0249, 100.0, 0.5, 1_000, 5.0) == 0.0          # Kelly wants 4.98 shares: refused
    assert L.taker_shares(0.25, 100.0, 0.51, 1_000, 5.0) == 49.01         # 49.0196 floored
    # m below min_size: no quote at all
    m = mk("s")
    b = books_for(m, 0.5, 0)
    out, _ = L.market_intents(m, fv(0.5), b[m.token_yes], b[m.token_no], {}, {}, 0, {**P, "quote_size": 4.99})
    assert out == []


def test_taker_cost_kelly_and_group_cap():
    lock = 0.5 * 0.2 * (24 + 2.72) / L.YEAR_H
    assert L.taker_cost(0.5, 0.07, 24, P) == pytest.approx(0.5 + 0.0175 + lock)   # fee 1.75c at 0.50
    assert L.kelly(0.6, 0.5) == pytest.approx(0.2) and L.kelly(0.9, 0.5) == 0.25 and L.kelly(0.4, 0.5) == 0.0
    capped = L.group_cap([0.2, 0.1, 0.1])
    assert sum(capped) == pytest.approx(0.2) and capped[0] == pytest.approx(0.1)
    assert L.group_cap([0.2]) == [0.2] and L.group_cap([]) == []


# ---------- D6 book integrity, arbs ----------

def test_book_integrity_flags_crossed_complement_book():
    m = mk("x")
    now = E - 6 * H
    good = books_for(m, 0.5, now)
    assert L.book_fault(good[m.token_yes], good[m.token_no]) is None
    bad = {m.token_yes: Book(m.token_yes, [(0.38, 50)], [(0.40, 50)], now),
           m.token_no: Book(m.token_no, [(0.48, 50)], [(0.50, 50)], now)}          # asks 0.40 + 0.50 < 1
    assert "asks" in L.book_fault(bad[m.token_yes], bad[m.token_no])
    bad2 = {m.token_yes: Book(m.token_yes, [(0.60, 50)], [(0.62, 50)], now),
            m.token_no: Book(m.token_no, [(0.45, 50)], [(0.47, 50)], now)}         # bids 0.60 + 0.45 > 1
    assert "bids" in L.book_fault(bad2[m.token_yes], bad2[m.token_no])
    eng = L.LadderEngine()
    assert _engine_quotes(eng, now, m, bad, ref_at(now)) == []
    faults = [r for t, r, _ in eng.records if t == "data_fault"]
    assert faults and faults[0]["kind"] == "book_integrity" and faults[0]["cid"] == "x"
    eng.on_tick(now + 1_000, {m.cid: m}, bad, ref_at(now + 1_000), {})            # rate-limited, not every tick
    assert len([1 for t, _, _ in eng.records if t == "data_fault"]) == 1


def test_arb_scanner_is_log_only():
    lo, hi = mk("lo", 79_000), mk("hi", 81_000)
    now = E - 6 * H
    books = {**books_for(lo, 0.6, now), **books_for(hi, 0.4, now)}
    books[lo.token_yes] = Book(lo.token_yes, [(0.28, 40)], [(0.30, 40)], now)    # YES(79k) ask 0.30: incoherent
    found = L.ladder_arbs([(lo, books[lo.token_yes], books[lo.token_no]), (hi, books[hi.token_yes],
                                                                           books[hi.token_no])], 6, P)
    assert len(found) == 1 and found[0]["buy_yes"] == "lo" and found[0]["buy_no"] == "hi"
    assert found[0]["edge"] == pytest.approx(1 - L.taker_cost(0.30, 0.07, 6, P) - L.taker_cost(0.61, 0.07, 6, P))
    eng = L.LadderEngine()
    out = eng.on_tick(now, {"lo": lo, "hi": hi}, books, ref_at(now), {})
    assert [r for t, r, _ in eng.records if t == "arb_opportunity"]
    assert all(i.kind == "maker" and i.side == "BUY" for i in out)


def test_fit_to_caps_packs_targets_into_group_and_budget_room():
    """Targets beyond the kernel's per-group room (after holdings) are dropped; reducing bids always pass."""
    from trader.contracts import Book, Intent, MarketInfo
    from trader.engines.ladder import fit_to_caps
    def mk(cid, g):
        return MarketInfo(cid, cid + "Y", cid + "N", "crypto-term", "q", "h", 0.01, 5, 0.07, False, 0, g, "BTC", 1.0, "strike")
    mkts = {"a": mk("a", "G1"), "b": mk("b", "G1"), "c": mk("c", "G2")}
    bid = lambda c, px, sz, red=False: Intent("ladder-maker", c, c + "Y", "BUY", px, sz, "maker", 0, 0.5, "t", (), red)
    books = {"aY": Book("aY", [(0.40, 100)], [(0.45, 100)], 0)}
    held = {"aY": 10.0}                                   # 10 x 0.40 = $4 already used in G1
    out = fit_to_caps([bid("a", 0.5, 10), bid("b", 0.5, 10), bid("c", 0.5, 10), bid("b", 0.5, 10, True)],
                      mkts, books, held, {"group_cap_usd": 10.0, "budget_usd": 25.0})
    # G1 room = 10 - 4 = 6: first $5 bid fits, second $5 does not; G2 bid fits; the reducing bid always passes
    assert [(i.cid, i.reduces_exposure) for i in out] == [("a", False), ("c", False), ("b", True)]
