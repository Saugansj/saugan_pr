"""WP5-C: quote-engine full objective (learning/quote_objective.py). Offline; every random draw is seeded."""
import math
import pathlib
import re

import numpy as np
import pytest

from learning import quote_objective as qo
from trader.contracts import Book, MarketInfo
from trader.engines.ladder import floor_to

M = MarketInfo("c1", "Y", "N", "crypto-term", "q", "h", 0.001, 5.0, 0.07, False, 10 ** 13, "g")
FIT = {**qo.PRIOR}                       # A = 0.01/s, k = 100, a = 0
ASKS = (0.52, 0.52)


def dist(quotes, mid):
    """{token: (distance from that token's mid, size)}"""
    return {t: (round((mid if t == "Y" else 1 - mid) - px, 6), sz) for t, px, sz, _ in quotes}


# ---------- C1-C3 reward ----------

def test_c1_score():
    from research.measure.reward_income import order_score  # Phase 0's scorer: same S(v, s)
    assert float(qo.score(4.5, 1.5, 1, 0)) == pytest.approx((3 / 4.5) ** 2) == pytest.approx(0.4444, abs=1e-4)
    assert float(qo.score(4.5, 1.5, 60, 50)) == pytest.approx(60 * 0.444444, rel=1e-5)
    assert float(qo.score(4.5, 4.5, 100, 0)) == 0 and float(qo.score(4.5, 6, 100, 0)) == 0
    assert float(qo.score(4.5, 1.5, 49.99, 50)) == 0                      # below reward_min_size
    for s in (0, 1, 2.5, 4.4):
        assert float(qo.score(4.5, s, 1, 0)) == pytest.approx(order_score(s, 4.5))


def test_c2_q_min():
    assert float(qo.q_min(9, 0, 0.5)) == pytest.approx(3) and float(qo.q_min(0, 9, 0.10)) == pytest.approx(3)
    assert float(qo.q_min(10, 4, 0.5)) == pytest.approx(4)                # max(min, max/3) = max(4, 3.33)
    assert float(qo.q_min(10, 2, 0.9)) == pytest.approx(10 / 3)           # max(2, 3.33)
    assert float(qo.q_min(9, 0, 0.05)) == 0 and float(qo.q_min(0, 9, 0.95)) == 0
    assert float(qo.q_min(10, 4, 0.05)) == 4


def test_c3_reward_term():
    yes = Book("Y", [(0.49, 100.0), (0.40, 1000.0)], [(0.51, 50.0)], 0, own={0.49: 40.0})
    v = 4.5
    s1 = (3.5 / 4.5) ** 2
    assert qo.q_others(yes, 0.5, v) == pytest.approx(s1 * (60 + 50))     # own size and the 10c level excluded
    rew = {"min_size": 50, "max_spread": v, "daily_rate": 100.0}
    quotes = [("Y", 0.48, 60.0, False), ("N", 0.49, 60.0, False)]       # NO bid 0.49 = YES ask 0.51
    q1, q2 = (2.5 / 4.5) ** 2 * 60, s1 * 60
    ours = max(min(q1, q2), max(q1, q2) / 3)
    b = qo.evaluate(M, quotes, 0.5, 0.5, 0.0, FIT, 0.0005, 864.0, rew, s1 * 110)
    assert b["reward"] == pytest.approx(100 * 864 / 86_400 * ours / (ours + s1 * 110))
    assert qo.evaluate(M, quotes, 0.5, 0.5, 0.0, FIT, 0.0005, 864.0, {**rew, "daily_rate": 0.0}, 5.0)["reward"] == 0
    assert qo.evaluate(M, [(t, p, 49.0, r) for t, p, _, r in quotes], 0.5, 0.5, 0.0, FIT, 0.0005, 864.0, rew,
                       5.0)["reward"] == 0                                  # under reward_min_size scores nothing
    _, b0 = qo.optimise(M, 0.5, 0.5, ASKS, 0.0, {}, FIT, 0.0005, 60, {**rew, "daily_rate": 0.0}, 50.0)
    assert b0["reward"] == 0


# ---------- C4-C5 fits ----------

def test_c4_fits_recover_truth():
    orders, fills = qo.synthetic(1, "crypto-term", ["a", "b"], 60, 4000, 0.02, 60.0, -0.002, -0.3)
    fr = qo.fit_fill_rate(orders)
    assert fr["A"] == pytest.approx(0.02, rel=0.10) and fr["k"] == pytest.approx(60.0, rel=0.10)
    ad = qo.fit_adverse(fills)
    assert abs(ad["m0"] + 0.002) < 2 * ad["se_m0"] and abs(ad["m1"] + 0.3) < 2 * ad["se_m1"]
    # not one lucky seed (seed 0 draws m1 2.4 SE off): the CR1 SEs cover the truth at about the nominal 95%
    cover = np.zeros(2)
    for seed in range(100, 120):
        x = qo.fit_adverse(qo.synthetic(seed, "crypto-term", ["a", "b"], 60, 2000, 0.02, 60.0, -0.002, -0.3)[1])
        cover += [abs(x["m0"] + 0.002) < 2 * x["se_m0"], abs(x["m1"] + 0.3) < 2 * x["se_m1"]]
    assert (cover >= 16).all()
    # a fill row's markout includes the spread: the fit removes it (a SELL is signed the other way)
    sell = [{**f, "side": "SELL", "price": 1 - f["price"], "mid_ex_own": 0.5} for f in fills]
    ad2 = qo.fit_adverse(sell)
    assert ad2["m0"] == pytest.approx(ad["m0"]) and ad2["m1"] == pytest.approx(ad["m1"])
    assert qo.fit_fill_rate([{**o, "filled": False} for o in orders]) is None


def test_c5_market_falls_back_to_mode_and_no_pooling():
    big_o, big_f = qo.synthetic(1, "crypto-term", ["big"], 40, 3000, 0.02, 60.0, -0.002, -0.3)
    sm_o, sm_f = qo.synthetic(2, "crypto-term", ["small"], 10, 400, 0.05, 20.0, 0.01, 0.0)
    y_o, y_f = qo.synthetic(3, "sports-pregame", ["s1"], 40, 3000, 0.005, 30.0, 0.003, -0.1)
    c = {x["name"]: x for x in qo.fit_candidates(big_o + sm_o + y_o, big_f + sm_f + y_f)}
    mode, small = c["quote-objective:crypto-term"]["params"], c["quote-objective:small"]["params"]
    assert small["fill_source"] == small["adverse_source"] == "mode"
    assert all(small[k] == mode[k] for k in ("A", "k", "m0", "m1"))
    assert c["quote-objective:big"]["params"]["fill_source"] == "market"
    alone = {x["name"]: x for x in qo.fit_candidates(big_o + sm_o, big_f + sm_f)}
    assert alone["quote-objective:crypto-term"]["params"] == mode           # adding another mode changes nothing
    assert c["quote-objective:sports-pregame"]["params"]["mode"] == "sports-pregame"
    assert c["quote-objective:sports-pregame"]["params"]["k"] == pytest.approx(30, rel=0.15)
    assert c["quote-objective:s1"]["params"]["mode"] == "sports-pregame"
    # a mode under min_clusters uses its registered prior
    p = {x["name"]: x for x in qo.fit_candidates(sm_o, sm_f, priors={"crypto-term": {"k": 77.0}})}
    assert p["quote-objective:crypto-term"]["params"]["k"] == 77.0
    assert p["quote-objective:small"]["params"]["fill_source"] == "prior"


# ---------- C6-C7 objective ----------

@pytest.mark.parametrize("k", [100.0, 50.0])
def test_c6_distance_is_one_over_k(k):
    fit = {**FIT, "A": 0.001, "k": k}                                   # lambda tau <= 0.01
    quotes, b = qo.optimise(M, 0.5, 0.5, ASKS, 0.0, {}, fit, 0.0005, 10.0, p={"gamma": 0.0, "rebate_rate": 0.0})
    assert len(quotes) == 2
    for t, (d, _) in dist(quotes, 0.5).items():
        assert abs(d - 1 / k) <= M.tick_size + 1e-9


def test_c7_adverse_move_never_loosens():
    for m0, m1 in ((-0.002, 0.0), (-0.004, -0.2), (0.0, -0.5)):
        base, _ = qo.optimise(M, 0.5, 0.5, ASKS, 0.0, {}, FIT, 0.0005, 60.0)
        worse, _ = qo.optimise(M, 0.5, 0.5, ASKS, 0.0, {}, {**FIT, "m0": m0, "m1": m1}, 0.0005, 60.0)
        old = {t: (px, sz) for t, px, sz, _ in base}
        for t, px, sz, _ in worse:
            assert px <= old[t][0] + 1e-12 or sz <= old[t][1]


def test_c7_inventory_skew():
    cost = {"Y": 0.40}                                                   # complement cap 0.59: not binding here
    for g in (0.5, 1.0):                                                 # both bids quoted: the skew is visible
        d = dist(qo.optimise(M, 0.5, 0.5, ASKS, 20.0, cost, FIT, 0.002, 60.0, p={"gamma": g})[0], 0.5)
        assert d["N"][0] < d["Y"][0]
    big, _ = qo.optimise(M, 0.5, 0.5, ASKS, 20.0, cost, FIT, 0.002, 60.0, p={"gamma": 1e6})
    assert "Y" not in {t for t, *_ in big} and "N" in {t for t, *_ in big}


def test_c7_sigma_tau_never_tighten():
    """Flat and symmetric: no quote tightens as sigma or tau grows. With expected inventory != 0 the side that ADDS
    to it never tightens; the side that sheds it may (that is what the inventory term is for)."""
    def check(quotes_seq, mid, adding=None):
        for a, b in zip(quotes_seq, quotes_seq[1:]):
            da, db = dist(a, mid), dist(b, mid)
            for t in (adding or db):
                if t in db and t in da:
                    assert db[t][0] >= da[t][0] - 1e-9 or db[t][1] < da[t][1]
    flat = lambda **kw: qo.optimise(M, 0.5, 0.5, ASKS, 0.0, {}, FIT, kw.get("s", 0.002), kw.get("tau", 60.0),
                                    p={"gamma": 5.0})[0]
    check([flat(s=s) for s in (0.0005, 0.002, 0.005, 0.01, 0.03)], 0.5)
    check([flat(tau=t) for t in (5, 30, 60, 300, 1000)], 0.5)
    rng = np.random.default_rng(4)
    for _ in range(4):
        q, net = 0.5 + rng.uniform(-0.02, 0.02), float(rng.choice([-15.0, 0.0, 20.0]))
        run = lambda s, tau: qo.optimise(M, q, 0.5, ASKS, net, {"Y": 0.4, "N": 0.4}, FIT, s, tau, p={"gamma": 5.0})
        for seq in ([run(s, 60.0) for s in (0.0005, 0.002, 0.005, 0.01)], [run(0.002, t) for t in (5, 30, 60, 300)]):
            for a, b in zip(seq, seq[1:]):
                e = a[1]["sides"]
                exp_inv = net + e["Y"]["P"] * e["Y"]["size"] - e["N"]["P"] * e["N"]["size"]
                check([a[0], b[0]], 0.5, adding=["Y"] if exp_inv > 1e-9 else ["N"] if exp_inv < -1e-9 else None)


def test_c7_no_double_count_when_a_is_zero():
    rew = {"min_size": 5, "max_spread": 4.5, "daily_rate": 50.0}
    quotes, b = qo.optimise(M, 0.505, 0.5, ASKS, 10.0, {"Y": 0.45}, FIT, 0.002, 60.0, rew, 300.0)
    fills = 0.0
    for s in b["sides"].values():
        assert s["adverse"] == 0
        assert s["fill"] == s["P"] * s["size"] * (s["edge"] + s["rebate"])
        fills += s["fill"]
    assert b["J"] == pytest.approx(b["reward"] + fills - b["inventory"])


def test_no_quote_when_j_never_positive():
    quotes, b = qo.optimise(M, 0.5, 0.5, ASKS, 0.0, {}, {**FIT, "m0": -0.05}, 0.0005, 60.0)
    assert quotes == [] and b["J"] == b["J0"] == 0


# ---------- C8 output ----------

def test_c8_output_constraints():
    rng = np.random.default_rng(5)
    seen_comp = 0
    for i in range(30):
        tick = float(rng.choice([0.01, 0.001]))
        m = MarketInfo("c", "Y", "N", "crypto-term", "q", "h", tick, float(rng.choice([5.0, 15.0])), 0.07, False,
                       10 ** 13, "g")
        mid = round(float(rng.uniform(0.05, 0.95)) / tick) * tick + tick / 2 * int(rng.integers(0, 2))
        asks = (round(mid + tick * int(rng.integers(1, 4)), 10), round(1 - mid + tick * int(rng.integers(1, 4)), 10))
        net = float(rng.choice([0.0, 12.0, -30.0, 49.0]))
        cost = {"Y": float(rng.uniform(0.2, 0.8)), "N": float(rng.uniform(0.2, 0.8))}
        fit = {**FIT, "A": float(rng.uniform(0.002, 0.05)), "k": float(rng.uniform(30, 300)),
               "m0": float(rng.uniform(-0.003, 0.0))}
        q = mid + float(rng.uniform(-0.03, 0.03))
        quotes, _ = qo.optimise(m, q, mid, asks, net, cost, fit, 0.002, 60.0, p={"size_step": 3.0})
        for t, px, sz, comp in quotes:
            mid_s, ask, own, other = (mid, asks[0], net, "N") if t == "Y" else (1 - mid, asks[1], -net, "Y")
            assert abs(px / tick - round(px / tick)) < 1e-9 and tick <= px <= 1 - tick     # on the tick grid
            assert px <= floor_to(mid_s, tick) + 1e-12                                     # BUY rounded down
            assert px < ask - 1e-12                                                        # post-only
            assert sz >= m.min_size and sz == floor_to(sz, 0.01)
            after = net + sz if t == "Y" else net - sz
            assert abs(after) <= qo.PARAMS["max_inv"] + 1e-9
            if -own >= m.min_size:                                                         # complement bid
                assert comp and px < 1 - cost[other] - qo.PARAMS["complement_margin"] - 1e-12 and sz <= -own
                seen_comp += 1
    assert seen_comp > 0
    # complement cap binds: holding 20 YES bought at 0.52, the NO bid sits strictly below 1 - 0.52 - 0.01 = 0.47
    quotes, _ = qo.optimise(M, 0.5, 0.5, ASKS, 20.0, {"Y": 0.52}, FIT, 0.0005, 60.0)
    no = [x for x in quotes if x[0] == "N"]
    assert no and no[0][1] == pytest.approx(0.469) and no[0][3] is True and no[0][2] <= 20
    assert all(x[0] != "N" for x in qo.optimise(M, 0.5, 0.5, ASKS, 20.0, {}, FIT, 0.0005, 60.0)[0])  # cost unknown


# ---------- C9 anchor ----------

def test_c9_wider():
    rng = np.random.default_rng(6)
    for _ in range(200):
        a = [(t, round(float(rng.uniform(0.01, 0.99)), 3), float(rng.integers(5, 60)), bool(rng.integers(0, 2)))
             for t in ("Y", "N") if rng.random() < 0.8]
        b = [(t, round(float(rng.uniform(0.01, 0.99)), 3), float(rng.integers(5, 60)), bool(rng.integers(0, 2)))
             for t in ("Y", "N") if rng.random() < 0.8]
        w = qo.wider(a, b)
        A, B = {x[0]: x for x in a}, {x[0]: x for x in b}
        assert {x[0] for x in w} == set(A) & set(B)
        for t, px, sz, _ in w:
            assert px <= min(A[t][1], B[t][1]) and sz <= min(A[t][2], B[t][2])
    anchor, _ = qo.optimise(M, 0.5, 0.5, ASKS, 0.0, {}, FIT, 0.0005, 60.0, p={"max_inv": 20.0})
    anc = {t: (px, sz) for t, px, sz, _ in anchor}
    prev_d = math.inf
    for i in range(10):                                              # ever-tighter, ever-larger refits
        refit, _ = qo.optimise(M, 0.5, 0.5, ASKS, 0.0, {}, {**FIT, "k": 100 * 1.3 ** (i + 1)}, 0.0005, 60.0)
        d = min(dist(refit, 0.5).values())[0]
        assert d <= prev_d
        prev_d = d
        for t, px, sz, _ in qo.wider(refit, anchor):
            assert px <= anc[t][0] and sz <= anc[t][1]
    assert prev_d < min(dist(anchor, 0.5).values())[0]               # the refits really were tighter


# ---------- C10 no promotion ----------

def test_c10_candidates_only():
    src = pathlib.Path(qo.__file__).read_text(encoding="utf-8")
    assert not re.search(r"promote\(|\.register\(|\.record\(", src)
    orders, fills = qo.synthetic(9, "crypto-term", ["a"], 35, 1500, 0.02, 60.0, 0.0, 0.0)
    for c in qo.fit_candidates(orders, fills):
        assert set(c) == {"name", "version", "params", "evidence"} and c["name"].startswith("quote-objective:")
