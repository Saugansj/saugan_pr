"""Calibration analyst (WP5-A, task 5.1; role 32). Pure functions on scorer rows (the shape Ledger.as_of returns).

Every statistic is computed within one mode; every SE is research.kappa.kappa.clustered_mean (CR1, clusters =
event groups); sample thresholds count clusters. budget_candidate only proposes a registry candidate.

    python -m learning.analyst --smoke        # from roster/; writes reports/phase5_analysis_smoke.md
"""
import argparse
import math
import pathlib

import numpy as np

from common import REPORTS, sha256_text
from research.kappa.kappa import clustered_mean, log_loss

DIMS = ("all", "league", "underlying", "horizon", "strategy")
REL_DIMS = ("all", "league", "underlying", "horizon")
SCORES = ("brier_p", "brier_m", "brier_diff", "logloss_p", "logloss_m", "logloss_diff")
NAN = math.nan


def horizon_bucket(h):
    return None if h is None else "<=1h" if h <= 1 else "<=6h" if h <= 6 else "<=24h" if h <= 24 else ">24h"


def _cm(v, cl):
    """(mean, CR1 SE); SE is NaN below 2 clusters, both NaN when empty."""
    if not len(v):
        return NAN, NAN
    if len(set(cl)) < 2:
        return float(np.mean(v)), NAN
    return clustered_mean(v, cl)


def _stat(rows, f):
    vals = [(r[f], r["cluster_id"]) for r in rows if r.get(f) is not None]
    return _cm([v for v, _ in vals], [c for _, c in vals])


def _clusters(rows, f=None):
    return len({r["cluster_id"] for r in rows if f is None or r.get(f) is not None})


def _key(r, dim, hz=None):
    if dim == "all":
        return "all"
    if dim == "horizon":
        return horizon_bucket(r["horizon_h"] if "horizon_h" in r else (hz or {}).get(r["cid"]))
    return r.get(dim)


def _groups(rows, mode, dim, hz=None):
    g = {}
    for r in rows:
        if r["mode"] == mode and (k := _key(r, dim, hz)) is not None:
            g.setdefault(k, []).append(r)
    return g


def breakdown(positions, fills):
    """One row per (mode, dim, key): dim "all" plus league, underlying, horizon bucket and strategy within the mode.
    Means with CR1 SEs of CLV and primary (per position) and of markouts, reward and rebate (per fill), plus income
    totals. Fills take their horizon from the position with the same cid."""
    hz = {p["cid"]: p.get("horizon_h") for p in positions}
    out = []
    for mode in sorted({r["mode"] for r in positions + fills}):
        for dim in DIMS:
            gp, gf = _groups(positions, mode, dim), _groups(fills, mode, dim, hz)
            for key in sorted(gp.keys() | gf.keys(), key=str):
                ps, fs = gp.get(key, []), gf.get(key, [])
                c = {"mode": mode, "dim": dim, "key": key, "positions": len(ps), "fills": len(fs),
                     "clusters": _clusters(ps), "fill_clusters": _clusters(fs),
                     "primary_clusters": _clusters(ps, "primary")}
                for name, rows in (("clv", ps), ("primary", ps), ("markout_5s", fs), ("markout_1m", fs),
                                   ("markout_5m", fs), ("reward", fs), ("rebate", fs)):
                    c[name], c[name + "_se"] = _stat(rows, name)
                c["reward_total"] = sum(f.get("reward") or 0.0 for f in fs)
                c["rebate_total"] = sum(f.get("rebate") or 0.0 for f in fs)
                out.append(c)
    return out


def _scores(rows, bins):
    if not rows:
        return {"rows": 0, "clusters": 0, "bins": [], **{s: NAN for s in SCORES}, "brier_diff_se": NAN,
                "logloss_diff_se": NAN}
    p, m, y = (np.array([r[f] for r in rows], float) for f in ("p", "mid_ex_own", "outcome"))
    cl = [r["cluster_id"] for r in rows]
    idx = np.minimum((p * bins).astype(int), bins - 1)
    out = {"rows": len(rows), "clusters": len(set(cl)), "bins": []}
    for b in np.unique(idx):
        s = np.flatnonzero(idx == b)
        freq, se = _cm(y[s], [cl[i] for i in s])
        out["bins"].append({"lo": b / bins, "hi": (b + 1) / bins, "mean_p": float(p[s].mean()), "freq": freq,
                            "freq_se": se, "rows": len(s), "clusters": len({cl[i] for i in s})})
    for name, fp, fm in (("brier", (p - y) ** 2, (m - y) ** 2), ("logloss", log_loss(p, y), log_loss(m, y))):
        out[name + "_p"], out[name + "_m"] = float(fp.mean()), float(fm.mean())
        out[name + "_diff"], out[name + "_diff_se"] = _cm(fp - fm, cl)
    return out


def reliability(forecasts, bins=10):
    """Per (mode, dim, key): reliability bins and Brier / log loss of p and of the baseline mid_ex_own on identical
    rows (resolved rows with both p and mid_ex_own; any other row is dropped from both), with the CR1 SE of p minus
    baseline. Subsets: universe, traded, and gap = traded - universe (the selection effect)."""
    rows = [r for r in forecasts if all(r.get(f) is not None for f in ("p", "mid_ex_own", "outcome"))]
    out = []
    for mode in sorted({r["mode"] for r in rows}):
        for dim in REL_DIMS:
            for key, g in sorted(_groups(rows, mode, dim).items(), key=lambda kv: str(kv[0])):
                u, t = _scores(g, bins), _scores([r for r in g if r.get("traded")], bins)
                base = {"mode": mode, "dim": dim, "key": key}
                # ponytail: gap has no SE (traded is a subset of universe, so their SEs don't combine); add a
                # cluster bootstrap of the gap if role 36 needs to test the selection effect.
                out += [{**base, "subset": "universe", **u}, {**base, "subset": "traded", **t},
                        {**base, "subset": "gap", "rows": t["rows"], "clusters": t["clusters"],
                         **{s: t[s] - u[s] for s in SCORES}}]
    return out


def budget_candidate(stats, budgets, min_clusters=20, step=0.5):
    """Registry candidate {"name": "budgets:<mode>", ...} or None. stats = breakdown rows of ONE mode (its
    dim == "strategy" rows are used); budgets = {strategy: amount}. A strategy whose fee-net primary mean is below 0
    by more than 2 SE loses `step` of its budget; the freed amount goes pro rata to strategies above 0 by more than
    2 SE, else stays unallocated. Below min_clusters a strategy is unchanged. Never applied here."""
    modes = {r["mode"] for r in stats}
    if len(modes) != 1:
        raise ValueError(f"budget_candidate takes one mode, got {sorted(modes)} (never pool across modes)")
    assert 0 <= step <= 1 and all(b >= 0 for b in budgets.values())
    mode = modes.pop()
    cells = {r["key"]: r for r in stats if r["dim"] == "strategy"}

    def sig(s, sign):
        c = cells.get(s)
        return bool(c) and c["primary_clusters"] >= min_clusters and sign * c["primary"] > 2 * c["primary_se"]

    new, freed = dict(budgets), 0.0
    for s, b in budgets.items():
        if sig(s, -1):
            new[s], freed = b - step * b, freed + step * b
    if freed <= 0:
        return None
    win = [s for s in budgets if sig(s, 1)]
    base = sum(budgets[s] for s in win)
    for s in win:
        new[s] += freed * (budgets[s] / base if base > 0 else 1 / len(win))
    params = {"budgets": new, "unallocated": 0.0 if win else freed}
    evidence = {s: {k: cells[s][k] for k in ("primary", "primary_se", "primary_clusters")} | {"old": budgets[s]}
                for s in budgets if s in cells}
    return {"name": f"budgets:{mode}", "version": sha256_text(repr(sorted(new.items())))[:12], "params": params,
            "evidence": evidence | {"rule": f"2 SE, step {step}, min_clusters {min_clusters}"}}


# ---------------------------------------------------------------- smoke

MODES = ("crypto-term", "crypto-hourly", "sports-pregame")
STRATS = ("ladder-maker", "speed-taker")
N_CLUSTERS, DRIFT_FROM = 80, 50
NEG = ("crypto-hourly", "speed-taker")     # planted negative CLV, fee-net primary < 0 -> model mistakes
VAR = ("sports-pregame", "ladder-maker")   # planted variance: good CLV and markout, unlucky outcomes
DRIFT = ("crypto-term", "ETH")             # this market series' markouts drift -1 SD from cluster 50
T0, DAY = 1_780_000_000_000, 86_400_000
MO_SD = 0.01                               # per-fill markout_5m noise; 2 fills per cluster on DRIFT
SYSTEM = [("role 02 markout lock, daily market series", 40, 14),
          ("role 02 markout lock, hourly market series", 10, 336),
          ("role 02 CLV lock, (mode, strategy)", 8, 14),
          ("role 34 bias drift, 30 keys x 2 directions", 60, 14),
          ("role 34 error-corr drift, 3 pairs x 2 directions (W = 30)", 6, 1)]


def synthetic(seed=0):
    """Seeded (positions, fills, forecasts): 3 modes x 2 strategies x 80 clusters with the planted effects above."""
    rng = np.random.default_rng(seed)
    positions, fills, forecasts = [], [], []
    for mode in MODES:
        sports = mode.startswith("sports")
        ents = ("EPL", "NBA") if sports else ("BTC", "ETH", "SOL")
        for i in range(N_CLUSTERS):
            cl, t = f"{mode}#{i:03d}", T0 + i * DAY
            shock = rng.normal(0, 0.03)
            for si, s in enumerate(STRATS):
                for j in range(2):
                    ent, maker = ents[(j + 2 * si) % len(ents)], s == "ladder-maker"
                    tag = dict(underlying=None if sports else ent, league=ent if sports else None)
                    cid, fee = f"{cl}:{s}:{j}", 0.0 if maker else 0.0175
                    clv = rng.normal(*{NEG: (-0.03, 0.015), VAR: (0.04, 0.01)}.get((mode, s), (0.004, 0.02)))
                    mo_mu = 0.02 if (mode, s) == VAR else 0.002
                    shift = -MO_SD / math.sqrt(2) if (mode, ent) == DRIFT and i >= DRIFT_FROM else 0.0
                    mos = []
                    for k in range(2):
                        mo = rng.normal(mo_mu, 0.005 if (mode, s) == VAR else MO_SD) + shift
                        mos.append(mo)
                        fills.append(dict(cid=cid, cluster_id=cl, mode=mode, strategy=s, **tag, token_id=f"{cid}:Y",
                                          side="BUY", price=0.5, size=10.0, maker=maker, fee=fee * 10,
                                          rebate=0.002 if maker else 0.0, reward=0.0, ts_ms=t + 3_600_000 * (k + 1),
                                          mid_ex_own=0.5, markout_5s=mo * 0.4 + rng.normal(0, 0.003),
                                          markout_1m=mo * 0.7 + rng.normal(0, 0.004), markout_5m=mo))
                    mu = {NEG: -0.06, VAR: -0.04}.get((mode, s), 0.02)
                    positions.append(dict(pos_id=cid, cid=cid, cluster_id=cl, mode=mode, strategy=s, **tag,
                                          horizon_h=float(rng.choice([0.5, 3, 12, 48])), side="BUY", size=10.0,
                                          entry_price=0.5, clv=clv, markout_5m=float(np.mean(mos)),
                                          fee_per_share=fee, flags=["data:stale-ref"] if rng.random() < 0.02 else [],
                                          outcome=int(rng.random() < 0.5), pnl=None,
                                          primary=mu + shock + rng.normal(0, 0.15)))
            for n in range(6):
                q = rng.uniform(0.05, 0.95)
                p, m = (float(np.clip(q + rng.normal(0, sd), 0.01, 0.99)) for sd in (0.03, 0.06))
                ent, traded = ents[n % len(ents)], abs(p - m) > 0.04
                forecasts.append(dict(cid=f"{cl}:f{n}", cluster_id=cl, mode=mode,
                                      strategy=STRATS[n % 2] if traded else None, traded=traded,
                                      underlying=None if sports else ent, league=ent if sports else None,
                                      horizon_h=float(rng.choice([0.5, 3, 12, 48])), p=p,
                                      mid_ex_own=None if rng.random() < 0.02 else m, outcome=int(rng.random() < q),
                                      event_ms=t, recorded_ms=t))
    for r in positions:
        r["pnl"] = r["primary"] * r["size"]
    return positions, fills, forecasts


def _f(x, d=4):
    return "" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{d}f}"


def _pm(m, se, d=4):
    return f"{_f(m, d)} ± {_f(se, d)}" if not math.isnan(se) else _f(m, d)


def smoke(out_path, seed=0):
    from learning import cusum, postmortem

    positions, fills, forecasts = synthetic(seed)
    now = T0 + N_CLUSTERS * DAY
    L = ["# Phase 5 analysis smoke (WP5-A: roles 32, 33, 34, 02)", "",
         f"Seeded synthetic set (seed {seed}): modes {', '.join(MODES)}; strategies {', '.join(STRATS)}; "
         f"{N_CLUSTERS} clusters per mode ({N_CLUSTERS * len(MODES)} total); {len(positions)} closed positions, "
         f"{len(fills)} fills, {len(forecasts)} forecast checkpoints. Planted: negative CLV and fee-net primary "
         f"in {NEG}; variance (good CLV, clean markout, unlucky outcomes, primary < 0) in {VAR}; markout_5m drift of "
         f"-1 SD of the per-cluster mean ({-MO_SD / math.sqrt(2):.5f}) on market series {DRIFT} from cluster "
         f"{DRIFT_FROM}. Every number is computed within one mode; SEs are CR1 by cluster (clustered_mean). "
         "Nothing here is applied: candidates are proposals only.", ""]

    L += ["## 1. Breakdown (role 32)", "",
          "| mode | dim | key | pos | fills | clusters | CLV | mo 5s | mo 1m | mo 5m | primary | reward | rebate |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    bd = breakdown(positions, fills)
    for c in bd:
        L.append(f"| {c['mode']} | {c['dim']} | {c['key']} | {c['positions']} | {c['fills']} | {c['clusters']} | "
                 + " | ".join(_pm(c[k], c[k + "_se"]) for k in ("clv", "markout_5s", "markout_1m", "markout_5m",
                                                                "primary"))
                 + f" | {_f(c['reward_total'], 2)} | {_f(c['rebate_total'], 2)} |")

    L += ["", "### Budget candidates (proposals only, budget 1.0 per strategy)", ""]
    for mode in MODES:
        cand = budget_candidate([c for c in bd if c["mode"] == mode], {s: 1.0 for s in STRATS})
        L.append(f"- {mode}: " + (f"`{cand['name']}` -> {cand['params']}" if cand else "no change (None)"))

    rel = reliability(forecasts)
    L += ["", "## 2. Reliability (role 32)", "",
          "Scores on identical rows (resolved, with both p and mid_ex_own). diff = p minus baseline (negative = p "
          "better); gap = traded minus universe (selection effect).", "",
          "| mode | dim | key | subset | rows | clusters | Brier p | Brier mid | Brier diff | LL p | LL mid | LL diff |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rel:
        L.append(f"| {r['mode']} | {r['dim']} | {r['key']} | {r['subset']} | {r['rows']} | {r['clusters']} | "
                 f"{_f(r['brier_p'])} | {_f(r['brier_m'])} | {_pm(r['brier_diff'], r.get('brier_diff_se', NAN))} | "
                 f"{_f(r['logloss_p'])} | {_f(r['logloss_m'])} | "
                 f"{_pm(r['logloss_diff'], r.get('logloss_diff_se', NAN))} |")
    L += ["", "### Reliability bins (universe, all keys)", "", "| mode | bin | mean p | freq ± SE | rows | clusters |",
          "|---|---|---|---|---|---|"]
    for r in rel:
        if r["dim"] == "all" and r["subset"] == "universe":
            L += [f"| {r['mode']} | {b['lo']:.1f}-{b['hi']:.1f} | {b['mean_p']:.3f} | {_pm(b['freq'], b['freq_se'], 3)}"
                  f" | {b['rows']} | {b['clusters']} |" for b in r["bins"]]

    classes = postmortem.classify_all(positions)
    names = ("resolution_wording", "data_provenance", "model", "execution", "indeterminate", "variance")
    L += ["", "## 3. Postmortem classes and lessons (role 33)", "",
          "Classification reads only " + ", ".join(postmortem.BLIND_FIELDS) + "; `primary` is read only by "
          "lessons(), after classification.", "", "| mode | strategy | " + " | ".join(names) + " |",
          "|---|---|" + "---|" * len(names)]
    for mode in MODES:
        for s in STRATS:
            cs = [c for p, c in zip(positions, classes) if p["mode"] == mode and p["strategy"] == s]
            L.append(f"| {mode} | {s} | " + " | ".join(str(cs.count(n)) for n in names) + " |")
    les = postmortem.lessons(positions, classes, now)
    L += ["", f"Lessons (clusters >= 20 and mean + 1.645 SE < 0): {len(les)}", "",
          "| name | clusters | mean | SE | importance now | importance +30 d |", "|---|---|---|---|---|---|"]
    L += [f"| `{x['name']}` | {x['params']['clusters']} | {x['params']['mean']:.4f} | {x['params']['se']:.4f} | "
          f"{postmortem.importance(x, now):.2f} | {postmortem.importance(x, now + 30 * DAY):.2f} |" for x in les]
    neg_found = any(x["name"].startswith(f"lesson:{NEG[0]}:{NEG[1]}:") for x in les)
    var_found = any(x["name"].startswith(f"lesson:{VAR[0]}:{VAR[1]}:") for x in les)
    vg = [p for p, c in zip(positions, classes) if (p["mode"], p["strategy"]) == VAR and c == "variance"]
    vm, vse = _cm([p["primary"] for p in vg], [p["cluster_id"] for p in vg])
    L += ["", f"- Planted negative group {NEG}: lesson found = **{neg_found}**.",
          f"- Planted variance group {VAR}: lesson found = **{var_found}** (its variance-class primary is "
          f"{vm:.4f} ± {vse:.4f}, significantly negative, and still produces no lesson: variance is not a mistake)."]

    rng = np.random.default_rng(seed + 100)
    null = rng.standard_normal(5000)
    fam = [(n, t) for _, n, t in SYSTEM]
    h, rate = cusum.calibrate_h(null, fam, seed=seed + 1)
    fresh = cusum.trip_rate(rng.standard_normal(5000), fam, h, seed=seed + 2)
    other = [cusum.calibrate_h(rng.standard_normal(5000), fam, seed=seed + 4 + i)[0] for i in range(3)]
    L += ["", "## 4. CUSUM threshold (roles 02 and 34)", "",
          "Stated system size (one-sided monitors x clusters per 2 weeks):", "",
          "| monitors | n_series | clusters / 2 weeks |", "|---|---|---|"]
    L += [f"| {lab} | {n} | {t} |" for lab, n, t in SYSTEM]
    L += ["", f"Null: seeded iid N(0, 1), 5,000 clusters (placeholder until real per-cluster series exist, A14 [ops]); "
          f"k = 0.5, block = 5, B = 2,000, budget 1 false trip per 2 weeks.", "",
          f"- Calibrated h = **{h}**, estimated system-wide false trips per 2 weeks = {rate:.3f}.",
          f"- Fresh simulation (new null sample, new seed) at h = {h}: {fresh:.3f} per 2 weeks.",
          f"- Sensitivity: h on three other 5,000-cluster null samples = {other} (the null sample's tails matter, "
          "most for the 336-cluster hourly family; calibrate on the real series, A14 [ops]).",
          "", "ARL check (one-sided, k = 0.5, iid N(0, 1), seeded paths):", "",
          "| h | paths | simulated ARL | Siegmund | ratio |", "|---|---|---|---|---|"]
    for hh, n in ((4.0, 4000), (h, 1000)):
        sim, sg = cusum.simulate_arl(0.5, hh, n=n, seed=seed + 3), float(cusum.siegmund_arl(0.5, hh))
        L.append(f"| {hh} | {n} | {sim:.1f} | {sg:.1f} | {sim / sg:.3f} |")

    mon = cusum.Monitor("02-cusum", "lock", "markout", h)
    trips = cusum.scan(mon, fills, "markout_5m", lambda r: (r["mode"], r["underlying"] or r["league"]))
    L += ["", "## 5. Planted drift (role 02 markout lock = role 34 per-market drift)", "",
          f"Per-cluster mean markout_5m per (mode, market series), standardised on the first 20 clusters, "
          f"low CUSUM at h = {h}. Trips:", "", "| scope | cluster index | cluster_id | action | reason |",
          "|---|---|---|---|---|"]
    L += [f"| {a['scope']} | {i} | {cid} | {a['action']} | {a['reason']} |" for a, i, cid in trips]
    hit = [i for a, i, _ in trips if a["scope"] == ":".join(DRIFT)]
    L += ["", f"- Planted drift on {DRIFT} from cluster {DRIFT_FROM}: "
          + (f"tripped at cluster **{hit[0]}** ({hit[0] - DRIFT_FROM} clusters after the shift)." if hit
             else "**not tripped**."),
          f"- Other trips (false alarms in this sample): {sum(1 for a, _, _ in trips if a['scope'] != ':'.join(DRIFT))}."
          , "- No action is `halt`; actions are only `lock` (role 02) and `alarm` (role 34).", ""]

    L += ["## How to reproduce", "", "From `roster/`:", "", "```",
          f".venv\\Scripts\\python.exe -m learning.analyst --smoke --seed {seed}",
          ".venv\\Scripts\\python.exe -m pytest tests/phase5/test_analysis.py -q", "```", "",
          "Offline and deterministic (seeded). Synthetic rows follow the dispatch's forecast, fill and "
          "closed-position shapes."]
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return {"h": h, "rate": rate, "fresh": fresh, "lessons": les, "neg_found": neg_found, "var_found": var_found,
            "drift_trip": hit[0] if hit else None, "trips": trips}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=str(REPORTS / "phase5_analysis_smoke.md"))
    a = ap.parse_args()
    if not a.smoke:
        ap.error("only --smoke is available until wiring")
    r = smoke(a.out, a.seed)
    print(f"wrote {a.out}: h={r['h']} lessons={len(r['lessons'])} neg={r['neg_found']} var={r['var_found']} "
          f"drift_trip={r['drift_trip']}")


if __name__ == "__main__":
    main()
