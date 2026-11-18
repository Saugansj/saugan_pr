"""Canary evaluation (build-plan 2.8, roles 22 and 35): live maker fills against replay's 90% prediction interval.

Rows: one per terminal maker order, {order_id, cluster (event group), queue_ahead, size, filled, markout_5m}, for live
and for replay (the strict simulator, or the paper journal over the same markets and period). Per queue bucket
(queue_ahead / own size) the statistics are the fill rate (filled shares / offered shares) and the mean 5m markout
per filled share (filled orders only). Replay's interval for each: draw the live bucket's cluster count with
replacement from replay's clusters in that bucket, recompute, take the 5th and 95th percentiles.

    python -m trader.live.canary --live live.jsonl --replay replay.jsonl --out reports/phase2_canary.md
"""
import argparse
import json
import math
import pathlib

import numpy as np

from trader.router import OPEN, replay as replay_journal

BUCKETS = ((0, 1), (1, 5), (5, 20), (20, math.inf))   # queue_ahead / own size
FAIL_TEXT = "recalibrate the fill simulator and re-run replay before continuing"
MARKOUT_MS = 300_000


def bucket_name(i: int) -> str:
    lo, hi = BUCKETS[i]
    return f"[{lo}, {'inf' if hi == math.inf else hi})"


def bucket_of(r: dict) -> int:
    q = r["queue_ahead"] / r["size"]
    return next(i for i, (lo, hi) in enumerate(BUCKETS) if lo <= q < hi)


def rows_from_journal(path, markets: dict, mid_at) -> list[dict]:
    """Rows from a router journal (trader.router.replay): terminal maker orders only, queue_ahead from the `new`
    entries, cluster = the market's event group. mid_at(token, ts_ms) -> mid_ex_own at ts_ms (or None); it is asked
    for the mid 5 min after each fill. Markout per share: mid - price for a BUY, price - mid for a SELL."""
    st, out = replay_journal(path), []
    fills: dict[str, list] = {}
    for f in st.fills:
        fills.setdefault(f.order_id, []).append(f)
    for o in st.orders.values():
        i = o.intent
        if i.kind != "maker" or o.status in OPEN or i.size <= 0:
            continue  # still resting or unresolved: its fill outcome is not final
        mk, n = 0.0, 0.0
        for f in fills.get(o.order_id, ()):
            mid = mid_at(f.token_id, f.ts_ms + MARKOUT_MS)
            if mid is None:
                mk = None
                break
            mk, n = mk + ((mid - f.price) if f.side == "BUY" else (f.price - mid)) * f.size, n + f.size
        m = markets.get(i.cid)
        out.append({"order_id": o.order_id, "cluster": m.event_group if m else i.cid, "queue_ahead": o.queue_ahead,
                    "size": i.size, "filled": o.filled,
                    "markout_5m": (mk / n if mk is not None and n > 0 else None)})
    return out


def _sums(rows) -> dict:
    """cluster -> [offered shares, filled shares, filled shares with a markout, markout x filled]."""
    by = {}
    for r in rows:
        a = by.setdefault(r["cluster"], [0.0, 0.0, 0.0, 0.0])
        a[0] += r["size"]
        a[1] += r["filled"]
        if r["filled"] > 0 and r.get("markout_5m") is not None:
            a[2] += r["filled"]
            a[3] += r["markout_5m"] * r["filled"]
    return by


def _stats(a: np.ndarray):
    with np.errstate(invalid="ignore", divide="ignore"):
        return a[..., 1] / a[..., 0], np.where(a[..., 2] > 0, a[..., 3] / np.where(a[..., 2] > 0, a[..., 2], 1), np.nan)


def _inside(x, pi) -> bool:
    return pi is not None and pi[0] - 1e-12 <= x <= pi[1] + 1e-12


def evaluate(live: list[dict], replay: list[dict], n_boot: int = 2000, seed: int = 0, min_clusters: int = 30) -> dict:
    rng = np.random.default_rng(seed)
    live, replay = [r for r in live if r["size"] > 0], [r for r in replay if r["size"] > 0]
    fill_clusters = len({r["cluster"] for r in live if r["filled"] > 0})
    rows, fails = [], []
    for b in range(len(BUCKETS)):
        lb, rb = [r for r in live if bucket_of(r) == b], _sums(r for r in replay if bucket_of(r) == b)
        if not lb:
            continue
        ls = np.array(list(_sums(lb).values()))
        k, has_fills = len(ls), ls[:, 1].sum() > 0
        fr, mk = (float(x) for x in _stats(ls.sum(axis=0)))
        row = {"bucket": bucket_name(b), "live_orders": len(lb), "live_clusters": k,
               "live_fill_clusters": len({r["cluster"] for r in lb if r["filled"] > 0}), "replay_clusters": len(rb),
               "fill_rate": fr, "fill_rate_pi": None, "markout_5m": None if math.isnan(mk) else mk,
               "markout_pi": None, "outside": []}
        if rb:
            draws = np.array(list(rb.values()))[rng.integers(0, len(rb), (n_boot, k))].sum(axis=1)
            bfr, bmk = _stats(draws)
            row["fill_rate_pi"] = [float(x) for x in np.percentile(bfr, [5, 95])]
            if not np.isnan(bmk).all():
                row["markout_pi"] = [float(x) for x in np.nanpercentile(bmk, [5, 95])]
            if not _inside(fr, row["fill_rate_pi"]):
                row["outside"].append("fill_rate")
            if has_fills and row["markout_5m"] is None:
                row["outside"].append("markout_5m missing")  # fills without a mid 5 min later: fail closed
            elif has_fills and not _inside(row["markout_5m"], row["markout_pi"]):
                row["outside"].append("markout_5m")
        elif has_fills:
            row["outside"].append("no replay clusters")
        fails += [f"{row['bucket']} {what}" for what in row["outside"]]
        rows.append(row)
    if fill_clusters < min_clusters:
        verdict, reason = "INSUFFICIENT", f"{fill_clusters} live clusters with a fill; need {min_clusters}"
    elif fails:
        verdict, reason = "FAIL", f"outside replay's 90% interval: {'; '.join(fails)}. {FAIL_TEXT}"
    else:
        verdict, reason = "PASS", "every bucket with live orders is inside replay's 90% interval"
    return {"verdict": verdict, "reason": reason, "live_fill_clusters": fill_clusters,
            "live_clusters": len({r["cluster"] for r in live}), "replay_clusters": len({r["cluster"] for r in replay}),
            "buckets": rows, "n_boot": n_boot, "seed": seed, "min_clusters": min_clusters}


def _f(x, nd=4) -> str:
    return "-" if x is None else f"{x:.{nd}f}"


def report(res: dict, live_path: str, replay_path: str, label: str = "") -> str:
    out = ["# Phase 2 canary evaluation (2.8)", ""]
    if label:
        out += [f"**{label}**", ""]
    out += [f"- live rows: `{live_path}`", f"- replay rows: `{replay_path}`",
            f"- live clusters: {res['live_clusters']} ({res['live_fill_clusters']} with a fill; need "
            f"{res['min_clusters']}); replay clusters: {res['replay_clusters']}",
            f"- bootstrap: {res['n_boot']} draws, seed {res['seed']}; interval = replay's 5th-95th percentile with the "
            "live bucket's cluster count", "",
            f"## Verdict: {res['verdict']}", "", res["reason"], "", "## Per queue bucket (queue_ahead / own size)", "",
            "| bucket | live orders | live clusters | with fill | replay clusters | fill rate | replay 90% PI "
            "| markout 5m | replay 90% PI | outside |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in res["buckets"]:
        pi = lambda p: "-" if p is None else f"[{_f(p[0])}, {_f(p[1])}]"
        out.append(f"| {r['bucket']} | {r['live_orders']} | {r['live_clusters']} | {r['live_fill_clusters']} | "
                   f"{r['replay_clusters']} | {_f(r['fill_rate'])} | {pi(r['fill_rate_pi'])} | {_f(r['markout_5m'])} | "
                   f"{pi(r['markout_pi'])} | {', '.join(r['outside']) or '-'} |")
    out += ["", "## How to reproduce", "", "From `roster/`:", "", "```",
            f"python -m trader.live.canary --live {live_path} --replay {replay_path} --seed {res['seed']} "
            f"--n-boot {res['n_boot']} --out <this file>", "```", ""]
    return "\n".join(out)


def _load(path) -> list[dict]:
    return [json.loads(x) for x in pathlib.Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--live", required=True)
    ap.add_argument("--replay", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--label", default="", help="banner line, e.g. 'SYNTHETIC rows'")
    a = ap.parse_args(argv)
    res = evaluate(_load(a.live), _load(a.replay), n_boot=a.n_boot, seed=a.seed)
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(a.out).write_text(report(res, a.live, a.replay, a.label), encoding="utf-8")
    print(f"{res['verdict']}: {res['reason']}")
    return res


if __name__ == "__main__":
    main()
