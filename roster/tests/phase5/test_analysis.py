"""WP5-A: calibration analyst (32), postmortems (33), drift and CUSUM triggers (34, 02). Offline, seeded."""
import math
import pathlib

import numpy as np
import pytest

import research.kappa.kappa as kappa
from learning import analyst, cusum, postmortem
from learning.analyst import breakdown, budget_candidate, reliability
from learning.postmortem import BLIND_FIELDS, classify, classify_all, importance, lessons
from trader.contracts import MarketInfo

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = [ROOT / "learning" / f for f in ("analyst.py", "postmortem.py", "cusum.py")]


def _same(a, b):
    """Lists of dicts equal, NaN == NaN."""
    assert len(a) == len(b)
    for x, y in zip(a, b):
        assert x.keys() == y.keys()
        for k in x:
            if isinstance(x[k], float) and math.isnan(x[k]):
                assert math.isnan(y[k]), k
            elif isinstance(x[k], list):
                _same(x[k], y[k])
            else:
                assert x[k] == pytest.approx(y[k]), k


def _pos(mode="m", strategy="s", cl="c0", **kw):
    r = dict(pos_id="p", cid=f"{cl}:x", cluster_id=cl, mode=mode, strategy=strategy, underlying="BTC", league=None,
             horizon_h=3.0, side="BUY", size=1.0, entry_price=0.5, clv=0.0, markout_5m=0.0, fee_per_share=0.0,
             flags=[], outcome=1, pnl=0.0, primary=0.0)
    r.update(kw)
    return r


def _fill(mode="m", strategy="s", cl="c0", **kw):
    r = dict(cid=f"{cl}:x", cluster_id=cl, mode=mode, strategy=strategy, underlying="BTC", league=None, token_id="t",
             side="BUY", price=0.5, size=1.0, maker=True, fee=0.0, rebate=0.001, reward=0.0, ts_ms=0, mid_ex_own=0.5,
             markout_5s=0.0, markout_1m=0.0, markout_5m=0.0)
    r.update(kw)
    return r


def _rand_book(rng, mode, n_cl=30):
    ps, fs = [], []
    for i in range(n_cl):
        cl = f"{mode}{i}"
        for j in range(rng.integers(1, 4)):
            s = ("a", "b")[j % 2]
            ps.append(_pos(mode, s, cl, cid=f"{cl}:{j}", clv=rng.normal(), primary=rng.normal(),
                           horizon_h=float(rng.choice([0.5, 3, 12, 48])), underlying=("BTC", "ETH")[j % 2]))
            fs.append(_fill(mode, s, cl, cid=f"{cl}:{j}", markout_5m=rng.normal(), markout_1m=rng.normal(),
                            markout_5s=rng.normal(), reward=rng.random(), underlying=("BTC", "ETH")[j % 2]))
    return ps, fs


# ---------------------------------------------------------------- A1, A2: analyst SEs and modes

def test_a1_clustered_se_from_kappa_and_duplicates():
    assert analyst.clustered_mean is kappa.clustered_mean and postmortem.clustered_mean is kappa.clustered_mean
    rng = np.random.default_rng(1)
    ps, fs = _rand_book(rng, "m")
    base = {(c["dim"], c["key"]): c for c in breakdown(ps, fs)}
    dup_in = {(c["dim"], c["key"]): c for c in breakdown(ps + [dict(p) for p in ps], fs + [dict(f) for f in fs])}
    dup_new = {(c["dim"], c["key"]): c for c in breakdown(
        ps + [dict(p, cluster_id=p["cluster_id"] + "'") for p in ps],
        fs + [dict(f, cluster_id=f["cluster_id"] + "'") for f in fs])}
    for k, c in base.items():
        for m in ("clv", "primary", "markout_5m", "reward"):
            assert dup_in[k][m] == pytest.approx(c[m]) and dup_in[k][m + "_se"] == pytest.approx(c[m + "_se"])
            assert dup_new[k][m + "_se"] < c[m + "_se"]


def test_a2_breakdown_and_reliability_never_pool_modes():
    rng = np.random.default_rng(2)
    p1, f1 = _rand_book(rng, "x")
    p2, f2 = _rand_book(rng, "y")
    p2 = [dict(p, clv=p["clv"] + 5) for p in p2]  # very different second mode
    both = breakdown(p1 + p2, f1 + f2)
    assert all(isinstance(c["mode"], str) and c["mode"] in ("x", "y") for c in both)
    _same([c for c in both if c["mode"] == "x"], breakdown(p1, f1))
    _same([c for c in both if c["mode"] == "y"], breakdown(p2, f2))
    assert {c["dim"] for c in both} == {"all", "underlying", "horizon", "strategy"}  # league is None here

    fc = _forecasts(rng, 2000, "x") + _forecasts(rng, 2000, "y")
    rel = reliability(fc)
    _same([r for r in rel if r["mode"] == "x"], reliability([r for r in fc if r["mode"] == "x"]))


def test_horizon_buckets():
    assert [analyst.horizon_bucket(h) for h in (0.5, 1, 1.01, 6, 24, 24.5, None)] == \
        ["<=1h", "<=1h", "<=6h", "<=6h", "<=24h", ">24h", None]


# ---------------------------------------------------------------- A3: reliability

def _forecasts(rng, n, mode="m", per_cluster=10):
    out = []
    for i in range(n):
        p = rng.uniform(0.02, 0.98)
        out.append(dict(cid=f"{mode}{i}", cluster_id=f"{mode}c{i // per_cluster}", mode=mode, traded=rng.random() < .3,
                        strategy=None, underlying="BTC", league=None, horizon_h=float(rng.choice([0.5, 30])), p=p,
                        mid_ex_own=float(np.clip(p + rng.normal(0, .05), .01, .99)), outcome=int(rng.random() < p),
                        event_ms=i, recorded_ms=i))
    return out


def test_a3_reliability_calibrated_identical_rows_and_subsets():
    rng = np.random.default_rng(3)
    fc = _forecasts(rng, 20000)
    fc[0]["mid_ex_own"] = None
    fc[1]["p"] = None
    fc[2]["outcome"] = None
    rel = reliability(fc)
    u = next(r for r in rel if r["dim"] == "all" and r["subset"] == "universe")
    assert len(u["bins"]) == 10
    for b in u["bins"]:
        assert abs(b["freq"] - b["mean_p"]) <= 3 * b["freq_se"], b
    ok = fc[3:]
    p, m, y = (np.array([r[f] for r in ok]) for f in ("p", "mid_ex_own", "outcome"))
    assert u["rows"] == len(ok)
    assert u["brier_p"] == pytest.approx(((p - y) ** 2).mean()) and u["brier_m"] == pytest.approx(((m - y) ** 2).mean())
    assert u["logloss_diff"] == pytest.approx((kappa.log_loss(p, y) - kappa.log_loss(m, y)).mean())
    assert u["brier_diff_se"] > 0
    for key in {(r["dim"], r["key"]) for r in rel}:
        subs = {r["subset"]: r for r in rel if (r["dim"], r["key"]) == key}
        assert set(subs) == {"universe", "traded", "gap"}
        for s in analyst.SCORES:
            assert subs["gap"][s] == pytest.approx(subs["traded"][s] - subs["universe"][s])
    t = next(r for r in rel if r["dim"] == "all" and r["subset"] == "traded")
    assert t["rows"] == sum(1 for r in ok if r["traded"])


# ---------------------------------------------------------------- A4: budgets

def _cell(key, mean, se, clusters, mode="m"):
    return {"mode": mode, "dim": "strategy", "key": key, "primary": mean, "primary_se": se,
            "primary_clusters": clusters}


def test_a4_budget_candidate():
    stats = [_cell("A", -0.1, 0.01, 30), _cell("B", 0.1, 0.01, 30), _cell("C", -0.1, 0.01, 10),
             _cell("D", 0.01, 0.01, 30), {"mode": "m", "dim": "all", "key": "all"}]
    c = budget_candidate(stats, {"A": 1.0, "B": 2.0, "C": 1.0, "D": 1.0})
    assert set(c) == {"name", "version", "params", "evidence"} and c["name"] == "budgets:m"
    assert c["params"]["budgets"] == {"A": 0.5, "B": 2.5, "C": 1.0, "D": 1.0} and c["params"]["unallocated"] == 0
    c = budget_candidate(stats[:1] + stats[2:], {"A": 1.0, "C": 1.0, "D": 1.0})  # no winner: freed stays unallocated
    assert c["params"] == {"budgets": {"A": 0.5, "C": 1.0, "D": 1.0}, "unallocated": 0.5}
    assert budget_candidate([_cell("D", 0.01, 0.01, 30)], {"D": 1.0}) is None
    with pytest.raises(ValueError):
        budget_candidate(stats + [_cell("A", -1, 0.01, 30, mode="other")], {"A": 1.0})

    rng = np.random.default_rng(4)
    for _ in range(300):
        names = [f"s{i}" for i in range(rng.integers(1, 6))]
        st = [_cell(s, rng.normal(0, 0.1), rng.uniform(0.001, 0.05), int(rng.integers(5, 40))) for s in names]
        bud = {s: float(rng.choice([0.0, rng.uniform(0, 3)])) for s in names}
        c = budget_candidate(st, bud, step=float(rng.uniform(0, 1)))
        if c is None:
            continue
        new = c["params"]["budgets"]
        assert sum(new.values()) <= sum(bud.values()) + 1e-12
        assert sum(new.values()) + c["params"]["unallocated"] == pytest.approx(sum(bud.values()))
        assert all(v >= 0 for v in new.values())
        for s in st:
            if s["primary_clusters"] < 20:
                assert new[s["key"]] == bud[s["key"]]


def test_a4_no_promote_anywhere():
    for f in SRC:
        assert "promote(" not in f.read_text(encoding="utf-8"), f


# ---------------------------------------------------------------- A5, A6: postmortem classes

class Guarded(dict):
    """A position that fails the test if anything outside BLIND_FIELDS is read."""

    def __getitem__(self, k):
        assert k in BLIND_FIELDS, k
        return super().__getitem__(k)

    def get(self, k, d=None):
        assert k in BLIND_FIELDS, k
        return super().get(k, d)


def test_a5_outcome_blind():
    rng = np.random.default_rng(5)
    flags = [[], [], [], ["resolution:x"], ["wording:y"], ["data:z"]]
    pos = [_pos(mode=str(rng.choice(["m1", "m2"])), strategy=str(rng.choice(["a", "b"])), cl=f"c{i % 50}",
                clv=float(rng.normal(0, .02)), markout_5m=float(rng.normal(0, .01)),
                fee_per_share=float(rng.choice([0, 0.0175])), flags=flags[rng.integers(0, len(flags))],
                outcome=int(rng.integers(0, 2)), pnl=float(rng.normal()), primary=float(rng.normal()))
           for i in range(1000)]
    flipped = [dict(p, outcome=1 - p["outcome"], pnl=-p["pnl"], primary=-p["primary"]) for p in pos]
    a, b = classify_all(pos), classify_all(flipped)
    assert a == b and len(set(a)) == 6
    sd = postmortem.sd_by_group(pos)
    assert [classify(Guarded(p), sd) for p in pos] == a


@pytest.mark.parametrize("kw,cls", [
    (dict(flags=["resolution:tie"], clv=-0.05), "resolution_wording"),       # beats negative CLV
    (dict(flags=["wording:x", "data:y"], clv=0.05), "resolution_wording"),
    (dict(flags=["data:stale"], clv=-0.05), "data_provenance"),
    (dict(clv=0.005, markout_5m=-0.05), "indeterminate"),
    (dict(clv=-0.02), "model"),
    (dict(clv=0.02, markout_5m=-0.02), "execution"),
    (dict(clv=0.02, markout_5m=0.05, fee_per_share=0.03), "execution"),       # positive CLV, fee not covered
    (dict(clv=0.02, markout_5m=0.005), "indeterminate"),
    (dict(clv=0.02, markout_5m=0.02, fee_per_share=0.01), "variance"),
    (dict(clv=None), "indeterminate"),
])
def test_a6_truth_table(kw, cls):
    assert classify(_pos(**kw), {("m", "s"): (0.01, 0.01)}) == cls


# ---------------------------------------------------------------- A7: lessons

def _lesson_rows(n_cl, vals, cls="model", rows_per=1):
    ps = [_pos(cl=f"c{i}", primary=vals[(i * rows_per + j) % len(vals)]) for i in range(n_cl) for j in range(rows_per)]
    return ps, [cls] * len(ps)


def test_a7_lessons():
    neg = [-0.10, -0.12, -0.08, -0.11]
    ps, cs = _lesson_rows(20, neg)
    les = lessons(ps, cs, now_ms=1000)
    assert len(les) == 1 and les[0]["name"] == "lesson:m:s:model"
    p = les[0]["params"]
    assert p["clusters"] == 20 and p["mean"] + 1.645 * p["se"] < 0 and p["importance"] == pytest.approx(-p["mean"] / p["se"])
    assert p["created_ms"] == 1000 and p["half_life_days"] == 30 and set(les[0]) == {"name", "version", "params", "evidence"}
    assert importance(les[0], 1000 + 30 * 86_400_000) == pytest.approx(p["importance"] / 2)
    assert importance(les[0], 1000 + 60 * 86_400_000) == pytest.approx(p["importance"] / 4)

    assert lessons(*_lesson_rows(19, neg), now_ms=0) == []
    weak = _lesson_rows(20, [-1.0, 0.98])
    m, se = kappa.clustered_mean([r["primary"] for r in weak[0]], [r["cluster_id"] for r in weak[0]])
    assert m < 0 and m + 1.645 * se >= 0 and lessons(*weak, now_ms=0) == []
    assert lessons(*_lesson_rows(5, neg, rows_per=12), now_ms=0) == []      # 60 rows, 5 clusters
    for cls in ("variance", "indeterminate"):
        assert lessons(*_lesson_rows(40, neg, cls=cls), now_ms=0) == []

    ps, cs = _lesson_rows(20, neg)
    les = lessons([dict(p, league="EPL") for p in ps], cs, now_ms=0, by="league")
    assert [x["name"] for x in les] == ["lesson:m:s:model:league=EPL"]


# ---------------------------------------------------------------- A8, A9: CUSUM ARL and threshold

def test_cusum_recursion():
    c = cusum.Cusum(h=1.0, k=0.5, direction="low")
    assert [c.update(z) for z in (-1.0, -0.6, 0.2)] == [False, False, False] and c.s == pytest.approx(0.0)
    assert [c.update(z) for z in (-1.0, -1.2)] == [False, True] and c.s == pytest.approx(1.2)
    hi = cusum.Cusum(h=1.0, direction="high")
    assert [hi.update(z) for z in (1.0, 1.1)] == [False, True]


def test_a8_arl_matches_siegmund():
    sg = cusum.siegmund_arl(0.5, 4.0)
    assert sg == pytest.approx(338, abs=1)
    assert abs(cusum.simulate_arl(0.5, 4.0, n=4000, seed=1) / sg - 1) < 0.10


def _ar1(rng, n, phi):
    x, e = np.zeros(n), rng.standard_normal(n)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + e[t]
    return x


def test_a9_threshold():
    rng = np.random.default_rng(9)
    iid = rng.standard_normal(5000)
    h, rate = cusum.calibrate_h(iid, [(50, 14)], seed=1)
    assert rate <= 1.0 and cusum.trip_rate(iid, [(50, 14)], round(h - 0.1, 1), seed=1) > 1.0  # smallest on the grid
    assert cusum.trip_rate(rng.standard_normal(5000), [(50, 14)], h, seed=7) <= 1.2      # fresh null, other seed
    assert cusum.calibrate_h(iid, [(500, 14)], seed=1)[0] > h
    assert cusum.calibrate_h(_ar1(rng, 5000, 0.5), [(50, 14)], seed=1)[0] > h


# ---------------------------------------------------------------- A10: trips

def test_a10_trip_is_sticky_until_reset():
    mon = cusum.Monitor("02-cusum", "lock", "markout", h=4.0)
    acts = [mon.update("mkt", -3.0, t) for t in range(3)]
    assert acts[:1] == [None] and acts[1]["action"] == "lock" and acts[1]["source"] == "02-cusum"
    assert acts[1]["scope"] == "mkt" and acts[1]["ts_ms"] == 1 and acts[2] is None
    s = mon.cusums[("mkt", "low")].s
    assert all(mon.update("mkt", 3.0, t) is None for t in range(100))
    assert mon.tripped("mkt") and mon.cusums[("mkt", "low")].s == s
    mon.reset("mkt")
    assert not mon.tripped("mkt") and mon.cusums[("mkt", "low")].s == 0


def test_a10_planted_shift_trips_at_calibrated_h():
    h, _ = cusum.calibrate_h(np.random.default_rng(0).standard_normal(5000), [(50, 14)], seed=1)
    rng = np.random.default_rng(0)
    rows = [dict(cluster_id=f"c{i:02d}", cid="m", ts_ms=i * 1000 + k,
                 markout_5m=rng.normal() - (1 / math.sqrt(3) if i >= 50 else 0)) for i in range(80) for k in range(3)]
    trips = cusum.scan(cusum.Monitor("02-cusum", "lock", "markout", h), rows, "markout_5m", "cid")
    assert len(trips) == 1
    act, idx, cid = trips[0]
    assert 50 <= idx <= 80 and cid == f"c{idx:02d}" and act["action"] == "lock" and act["ts_ms"] == idx * 1000 + 2


def test_a10_no_halt():
    assert cusum.ACTIONS == ("lock", "alarm")
    with pytest.raises(AssertionError):
        cusum.Monitor("02-cusum", "halt", "x", 4.0)
    for f in SRC:
        src = f.read_text(encoding="utf-8")
        assert '"halt"' not in src and "'halt'" not in src and "HALTED" not in src, f


# ---------------------------------------------------------------- A11: drift watch

def test_a11_bias_drift_only_on_planted_entity():
    rng = np.random.default_rng(11)
    rows = []
    for i in range(80):
        for ent in "ABCD":
            for n in range(10):
                q = rng.uniform(0.1, 0.9)
                p = min(0.99, q + 0.2) if ent == "C" and i >= 40 else float(np.clip(q + rng.normal(0, .03), .01, .99))
                rows.append(dict(cluster_id=f"{ent}{i:02d}", underlying=ent, p=p, outcome=int(rng.random() < q),
                                 event_ms=i * 1000))
    mon = cusum.Monitor("34-drift", "alarm", "bias", h=8.0, directions=("low", "high"))
    trips = cusum.scan(mon, rows, lambda r: r["p"] - r["outcome"], "underlying", time="event_ms")
    assert [a["scope"] for a, _, _ in trips] == ["C"]
    a, idx, _ = trips[0]
    assert a["action"] == "alarm" and a["source"] == "34-drift" and "high" in a["reason"] and idx >= 40


def test_a11_error_correlation_drift():
    rng = np.random.default_rng(12)
    W, n0, n1 = 30, 240, 150      # 4 reference windows + 4 monitored null windows, then 5 windows at corr 0.8
    a = rng.standard_normal(n0 + n1)
    b = rng.standard_normal(n0 + n1)
    b[n0:] = 0.8 * a[n0:] + 0.6 * rng.standard_normal(n1)  # corr 0 -> 0.8
    z = cusum.error_corr_z(a, b, W)
    assert len(z) == (n0 + n1) // W - 4
    assert cusum.error_corr_z(a, b, W, ref_fz=0.0)[0] == pytest.approx(np.arctanh(np.corrcoef(a[:W], b[:W])[0, 1]) * np.sqrt(W - 3))
    mon = cusum.Monitor("34-drift", "alarm", "error-corr", h=4.0, directions=("low", "high"))
    fired = [(i, x) for i, zi in enumerate(z) if (x := mon.update("est1~est2", zi, i))]
    first_high = n0 // W - 4
    assert len(fired) == 1 and fired[0][0] in (first_high, first_high + 1) and "high" in fired[0][1]["reason"]


def _mk(cid, mode="crypto-term", fee=0.07, tick=0.01, src="binance"):
    return MarketInfo(cid=cid, token_yes=cid + "y", token_no=cid + "n", mode=mode, question="q", rules_sha256="r",
                      tick_size=tick, min_size=5.0, fee_rate=fee, neg_risk=False, end_ms=0, event_group="g",
                      source_id=src)


def test_a11_venue_changes():
    prev = [_mk(f"c{i}") for i in range(5)] + [_mk(f"s{i}", "sports-pregame", 0.0, src="espn") for i in range(3)]
    venue = {"taker_delay_ms": 250, "settlement": {"crypto-term": "uma", "sports-pregame": "uma"}}
    assert cusum.venue_changes(prev, prev, venue, venue) == []
    one_tick = [_mk("c0", tick=0.001)] + prev[1:]
    assert cusum.venue_changes(prev, one_tick, venue, venue) == []
    fee = [_mk(f"c{i}", fee=0.10) for i in range(5)] + prev[5:]
    acts = cusum.venue_changes(prev, fee, venue, venue, now_ms=7)
    assert [(a["scope"], a["action"], a["source"], a["ts_ms"]) for a in acts] == [("mode:crypto-term", "alarm", "34-drift", 7)]
    assert "fee_rate" in acts[0]["reason"]
    acts = cusum.venue_changes(prev, prev, venue, dict(venue, taker_delay_ms=500))
    assert [(a["scope"], a["action"]) for a in acts] == [("venue", "alarm")] and "taker_delay_ms" in acts[0]["reason"]
    acts = cusum.venue_changes(prev, prev, venue, dict(venue, settlement={"crypto-term": "chainlink",
                                                                          "sports-pregame": "uma"}))
    assert [a["scope"] for a in acts] == ["mode:crypto-term"]


def test_per_cluster_and_standardise():
    rows = [dict(cluster_id="b", k="x", v=1.0, ts_ms=20), dict(cluster_id="b", k="x", v=3.0, ts_ms=25),
            dict(cluster_id="a", k="x", v=5.0, ts_ms=30), dict(cluster_id="c", k="y", v=None, ts_ms=1)]
    assert cusum.per_cluster(rows, "v", "k") == {"x": [("b", 25, 2.0), ("a", 30, 5.0)]}
    z = cusum.standardise([1.0, 2.0, 3.0, 10.0], burn_in=3)
    assert z[:3] == pytest.approx([-1, 0, 1]) and z[3] == pytest.approx(8.0)
    assert cusum.standardise([4.0], ref_mean=2.0, ref_sd=2.0) == pytest.approx([1.0])


# ---------------------------------------------------------------- A12: smoke

def test_a12_smoke(tmp_path):
    out = tmp_path / "smoke.md"
    r = analyst.smoke(out, seed=0)
    text = out.read_text(encoding="utf-8")
    for sec in ("## 1. Breakdown", "### Budget candidates", "## 2. Reliability", "### Reliability bins",
                "## 3. Postmortem classes and lessons", "## 4. CUSUM threshold", "ARL check", "## 5. Planted drift"):
        assert sec in text, sec
    assert r["neg_found"] and not r["var_found"]
    assert r["drift_trip"] is not None and analyst.DRIFT_FROM <= r["drift_trip"] <= analyst.DRIFT_FROM + 30
    assert text.rstrip().splitlines()[0].startswith("# ") and "## How to reproduce" in text
    assert text.index("## How to reproduce") > text.index("## 5. Planted drift")
