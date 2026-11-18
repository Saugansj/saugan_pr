"""Outcome-blind postmortems (WP5-A, task 5.2; role 33). Never reaches the sizing or gating path.

classify() reads only BLIND_FIELDS (never outcome, pnl or primary). lessons() reads `primary` only after
classification, as the group statistic, and proposes registry candidates; it never applies or promotes them.
"""
import math

import numpy as np

from common import sha256_text
from research.kappa.kappa import clustered_mean

BLIND_FIELDS = ("clv", "markout_5m", "fee_per_share", "flags", "mode", "strategy")
MISTAKES = ("resolution_wording", "data_provenance", "model", "execution")
DAY_MS = 86_400_000


def sd_by_group(positions):
    """{(mode, strategy): (sd_clv, sd_markout)}: sample SDs (ddof 1) over the batch; NaN with fewer than 2 values."""
    acc = {}
    for p in positions:
        a = acc.setdefault((p["mode"], p["strategy"]), ([], []))
        if p.get("clv") is not None:
            a[0].append(p["clv"])
        if p.get("markout_5m") is not None:
            a[1].append(p["markout_5m"])
    sd = lambda v: float(np.std(v, ddof=1)) if len(v) > 1 else math.nan
    return {g: (sd(c), sd(m)) for g, (c, m) in acc.items()}


def classify(pos, sd):
    """First matching class. sd = {(mode, strategy): (sd_clv, sd_markout)}. Unknown CLV or SD -> indeterminate."""
    p = {f: pos.get(f) for f in BLIND_FIELDS}  # the only read of the position
    flags = p["flags"] or []
    if any(f.startswith(("resolution:", "wording:")) for f in flags):
        return "resolution_wording"
    if any(f.startswith("data:") for f in flags):
        return "data_provenance"
    sd_clv, sd_mo = sd.get((p["mode"], p["strategy"]), (math.nan, math.nan))
    clv, mo, fee = p["clv"], p["markout_5m"], p["fee_per_share"] or 0.0
    if clv is None or not math.isfinite(sd_clv) or abs(clv) <= sd_clv:
        return "indeterminate"
    if clv < -sd_clv:
        return "model"
    if (mo is not None and math.isfinite(sd_mo) and mo < -sd_mo) or clv - fee < 0:
        return "execution"
    if mo is None or not math.isfinite(sd_mo) or abs(mo) <= sd_mo:
        return "indeterminate"
    return "variance"


def classify_all(positions, sd=None):
    sd = sd_by_group(positions) if sd is None else sd
    return [classify(p, sd) for p in positions]


def lessons(positions, classes, now_ms, min_clusters=20, z=1.645, by=None, half_life_days=30):
    """Registry candidates for mistake groups (mode, strategy, class[, by]) with >= min_clusters clusters and a
    fee-net primary statistic significantly below 0 (mean + z SE < 0, CR1 SE by cluster)."""
    groups = {}
    for p, c in zip(positions, classes):
        if c in MISTAKES:
            groups.setdefault((p["mode"], p["strategy"], c) + ((p.get(by),) if by else ()), []).append(p)
    out = []
    for g, rows in sorted(groups.items(), key=lambda kv: tuple(map(str, kv[0]))):
        rows = [r for r in rows if r.get("primary") is not None]  # primary is read here, after classification
        n = len({r["cluster_id"] for r in rows})
        if n < max(min_clusters, 2):
            continue
        mean, se = clustered_mean([r["primary"] for r in rows], [r["cluster_id"] for r in rows])
        if not mean + z * se < 0:
            continue
        name = "lesson:" + ":".join(map(str, g[:3])) + (f":{by}={g[3]}" if by else "")
        params = {"class": g[2], "clusters": n, "mean": mean, "se": se, "importance": -mean / se if se else math.inf,
                  "created_ms": int(now_ms), "half_life_days": half_life_days}
        out.append({"name": name, "version": sha256_text(repr(sorted(params.items())))[:12], "params": params,
                    "evidence": {"statistic": "primary", "rows": len(rows), "z": z, "min_clusters": min_clusters}})
    return out


def importance(lesson, now_ms):
    p = lesson["params"]
    return p["importance"] * 0.5 ** ((now_ms - p["created_ms"]) / DAY_MS / p["half_life_days"])
