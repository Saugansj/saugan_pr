"""WX-C counterfactual exit study: would an exit rule have beaten holding to settlement on the paper runs' real positions?

- Positions: every BUY fill is a lot (token, cost, shares, fill time), reduced FIFO by SELL fills and by merges (a merge
  removes `size` shares from both its yes and no token). What is left was held to settlement; a lot counts once its
  outcome is known (ledger `settlements`, else public CLOB GET /markets/<cid>, cached in data/exits/outcomes.json).
- Path: per-minute mids from the ledger's `marks`. Exit price at minute t = max(0, mid - h) for half-spread h in
  HALF_SPREADS, less the taker fee rate x p(1-p) (trader.fees). Only minutes after the fill and before the ladder's
  pull window (end - 10 min) are eligible.
- Fair: the ladder's own fair for that token, parsed from its `orders` reasons ("f=... half=..."), or 1 - the other
  token's fair in a two-token market; used only if at most FAIR_MAX_AGE_MS old at t. Uncertainty is not logged per tick,
  so unc is bounded from the quote's half-spread: (half - half_min) / ladder k_unc (>= the true unc, so R1 here fires at
  most as often as live R1). A lot without any fair while held is "not evaluable" for R1/R3 variants.
- Rules (first eligible minute that fires, using only data up to t): R1 sell > f + max(fv_margin, k_unc x unc);
  R2 (bid - cost)/cost >= tp and tau_h >= tp_min_tau_h; R3 f < cost - drop and sell >= f - sl_tolerance;
  R4 bid >= release and tau_h >= 1 (free-capital condition not reconstructable: assumed always true, an upper bound).
- Statistic (pre-registration exit-manager-v1): per closed position, shares x (exit value - settlement value), entry
  fees cancel; mean, CR0 cluster-robust SE by event group; PASS if mean > 2 SE with n >= 100, futility if mean < -1 SE
  after 50, and INCONCLUSIVE below 100.

Ledgers are opened read-only (nightly.scorer.tables, SQLite mode=ro); nothing is written under data/trader/.
Run: python -m research.exits.study [--offline]   (idempotent: same ledgers and outcomes give the same report)
"""
import argparse
import bisect
import json
import pathlib
import re
import statistics

import common
from nightly import scorer
from trader import fees
from trader.engines import exits, ladder

ROOT = common.DATA / "trader"
OUT = common.DATA / "exits"
REPORT = common.REPORTS / "exits_counterfactual.md"
HALF_SPREADS = (0.005, 0.01, 0.02)
PRIMARY_H = 0.01
P = {**{k: exits.PARAMS[k] for k in ("fv_margin", "k_unc", "tp_min_tau_h", "sl_tolerance")},  # as the live rules
     "release_min_tau_h": 1.0}
FAIR_MAX_AGE_MS = 5 * 60_000  # ponytail: one ladder GTD step; a fair older than that is treated as missing
PULL_MS = ladder.PARAMS["pull_before_close_ms"]
PREREG = {"n": 100, "pass_z": 2.0, "futility_n": 50, "futility_z": -1.0}
VARIANTS = {
    "hold (baseline)": {},
    "R1 fair-value": {"r1": True},
    "R2 tp 10%": {"tp": 0.10}, "R2 tp 15%": {"tp": 0.15}, "R2 tp 25%": {"tp": 0.25},
    "R3 drop 0.10": {"sl": 0.10}, "R3 drop 0.15": {"sl": 0.15},
    "R4 bid 0.95": {"rel": 0.95}, "R4 bid 0.97": {"rel": 0.97},
    "R1+R2 tp 15%": {"r1": True, "tp": 0.15}, "R1+R3 drop 0.10": {"r1": True, "sl": 0.10},
}
FAIR_RE = re.compile(r"\bf=(\S+) .*\bhalf=(\S+)")


def lots(t: dict) -> list[dict]:
    """Lots still held after FIFO sells and merges, oldest first."""
    ev = [(f["ts_ms"], 0 if f["side"] == "BUY" else 1, "fill", f) for f in t.get("fills", [])]
    ev += [(m["ts_ms"], 1, "merge", m) for m in t.get("merges", [])]
    held: dict[str, list[dict]] = {}

    def reduce(token, n):
        for lot in held.get(token, []):
            take = min(lot["shares"], n)
            lot["shares"] -= take
            n -= take
    for _, _, kind, r in sorted(ev, key=lambda e: e[:2]):
        if kind == "merge":
            reduce(r["yes"], r["size"])
            reduce(r["no"], r["size"])
        elif r["side"] == "SELL":
            reduce(r["token_id"], r["size"])
        else:
            held.setdefault(r["token_id"], []).append(
                {"token": r["token_id"], "cid": r["cid"], "cost": r["price"], "shares": r["size"], "ts_ms": r["ts_ms"],
                 "end_ms": r["end_ms"], "fee_rate": r["fee_rate"], "cluster": r["cluster_id"],
                 "strategy": r.get("strategy")})
    return sorted((x for v in held.values() for x in v if x["shares"] > 1e-9), key=lambda x: (x["ts_ms"], x["token"]))


def fair_paths(t: dict) -> dict[str, list[tuple]]:
    """{token: [(ms, f, unc_bound)]} from the ladder's order reasons, plus 1 - f for the other token of the market."""
    toks: dict[str, set] = {}
    for r in t.get("orders", []) + t.get("fills", []):
        toks.setdefault(r["cid"], set()).add(r["token_id"])
    out: dict[str, list] = {}
    for o in t.get("orders", []):
        m = FAIR_RE.search(str(o.get("reason")))
        if o.get("strategy") != "ladder-maker" or not m:
            continue
        f, half = float(m[1]), float(m[2])
        unc = max(0.0, (half - ladder.PARAMS["half_min"]) / ladder.PARAMS["k_unc"])
        out.setdefault(o["token_id"], []).append((o["event_ms"], f, unc))
        pair = toks.get(o["cid"], set())
        if len(pair) == 2:
            (other,) = pair - {o["token_id"]}
            out.setdefault(other, []).append((o["event_ms"], 1 - f, unc))
    return {k: sorted(v) for k, v in out.items()}


def price_paths(t: dict) -> dict[str, list[tuple]]:
    out: dict[str, list] = {}
    for r in t.get("marks", []):
        for k, v in r.items():
            if k not in ("event_ms", "recorded_ms") and isinstance(v, (int, float)):
                out.setdefault(k, []).append((r["event_ms"], float(v)))
    return {k: sorted(v) for k, v in out.items()}


def fair_at(fairs: list[tuple], ms: int):
    """(f, unc) of the latest fair at or before ms, if fresh; never looks past ms."""
    i = bisect.bisect_right(fairs, (ms, float("inf"), float("inf"))) - 1
    return fairs[i][1:] if i >= 0 and ms - fairs[i][0] <= FAIR_MAX_AGE_MS else (None, None)


def sell_value(mid: float, h: float, rate: float) -> tuple[float, float]:
    """(bid, bid - taker fee) per share for an exit at mid - h."""
    bid = max(0.0, mid - h)
    return bid, bid - fees.fee(1.0, bid, rate)


def fair_minutes(lot: dict) -> int:
    """Eligible minutes of the lot's path that have a fresh fair (0: R1/R3 cannot be evaluated on this lot)."""
    return sum(lot["ts_ms"] < ms < lot["end_ms"] - PULL_MS and fair_at(lot["fairs"], ms)[0] is not None
               for ms, _ in lot["path"])


def first_exit(lot: dict, path: list[tuple], fairs: list[tuple], rule: dict, h: float, p: dict = P):
    """(ms, sell value per share, rule) of the first minute the rule fires, or None (held to settlement)."""
    for ms, mid in path:
        if not lot["ts_ms"] < ms < lot["end_ms"] - PULL_MS:
            continue
        bid, sell = sell_value(mid, h, lot["fee_rate"])
        f, unc = fair_at(fairs, ms)
        tau_h = (lot["end_ms"] - ms) / 3_600_000
        if rule.get("r1") and f is not None and sell > f + max(p["fv_margin"], p["k_unc"] * unc):
            return ms, sell, "R1"
        if rule.get("tp") is not None and (bid - lot["cost"]) / lot["cost"] >= rule["tp"] and tau_h >= p["tp_min_tau_h"]:
            return ms, sell, "R2"
        if rule.get("sl") is not None and f is not None and f < lot["cost"] - rule["sl"] and sell >= f - p["sl_tolerance"]:
            return ms, sell, "R3"
        if rule.get("rel") is not None and bid >= rule["rel"] and tau_h >= p["release_min_tau_h"]:
            return ms, sell, "R4"
    return None


def improvement(lot: dict, ex, payout: float) -> float:
    """Exit value - hold-to-settlement value for the lot, in USD (entry cost and fee are the same in both)."""
    return 0.0 if ex is None else lot["shares"] * (ex[1] - payout)


def verdict(mean, se, n: int) -> str:
    fut = n >= PREREG["futility_n"] and se and mean < PREREG["futility_z"] * se
    if n < PREREG["n"]:
        return f"INCONCLUSIVE (n={n} < {PREREG['n']})" + ("; futility reached (pre-registered FAIL)" if fut else "")
    if se and mean > PREREG["pass_z"] * se:
        return "PASS"
    return "FAIL (futility)" if fut else "INCONCLUSIVE (running)"


def outcomes(cids: set, t_all: list[dict], cache_p: pathlib.Path, fetch, now_ms: int, ends: dict) -> dict:
    """{cid: winning token}: ledger settlements, then the cache, then (if fetch) a public CLOB GET for ended markets."""
    try:
        cache = json.loads(cache_p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    out = {c: o["winner"] for c, o in cache.items()}
    for t in t_all:
        out |= {s["cid"]: s["winner"] for s in t.get("settlements", []) if s.get("winner")}
    todo = sorted(c for c in cids if c not in out and ends.get(c, 2 ** 62) < now_ms)
    if fetch and todo:
        for cid in todo:
            try:
                o = fetch(cid)
            except Exception as e:  # noqa: BLE001 - a missed GET is retried on the next run
                print(f"outcome {cid[:12]}: {e!r}", flush=True)
                continue
            if o:
                cache[cid] = o
                out[cid] = o["winner"]
        cache_p.parent.mkdir(parents=True, exist_ok=True)
        cache_p.write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf-8")
    return out


def study(root=ROOT, out_dir=OUT, fetch=scorer.fetch_outcome, now_ms: int | None = None) -> dict:
    now_ms = common.now_ms() if now_ms is None else now_ms
    sources, pos, tabs = [], [], []
    for db in sorted(pathlib.Path(root).glob("*/trader.db")):
        t = scorer.tables(db.parent)  # read-only (mode=ro)
        groups = {c["cid"]: c["event_group"] for c in t.get("universe_checkpoint", []) if c.get("event_group")}
        fp, pp = fair_paths(t), price_paths(t)
        ls = lots(t)
        for lot in ls:
            lot |= {"source": db.parent.name, "group": groups.get(lot["cid"], lot["cluster"]),
                    "path": pp.get(lot["token"], []), "fairs": fp.get(lot["token"], [])}
        sources.append({"source": db.parent.name, "fills": len(t.get("fills", [])), "lots": len(ls)})
        pos += ls
        tabs.append(t)
    win = outcomes({x["cid"] for x in pos}, tabs, pathlib.Path(out_dir) / "outcomes.json", fetch, now_ms,
                   {x["cid"]: x["end_ms"] for x in pos})
    closed = [x | {"payout": 1.0 if win[x["cid"]] == x["token"] else 0.0} for x in pos if x["cid"] in win]
    for s in sources:
        s["closed"] = sum(x["source"] == s["source"] for x in closed)
    res = []
    for name, rule in VARIANTS.items():
        needs_f = rule.get("r1") or rule.get("sl") is not None
        for h in HALF_SPREADS:
            ev = [x for x in closed if not needs_f or fair_minutes(x)]
            exits = [first_exit(x, x["path"], x["fairs"], rule, h) for x in ev]
            d = [improvement(x, e, x["payout"]) for x, e in zip(ev, exits)]
            mean = statistics.fmean(d) if d else None
            se = scorer.cluster_se(d, [x["group"] for x in ev])
            res.append({"variant": name, "h": h, "n": len(d), "not_evaluable": len(closed) - len(ev),
                        "exited": sum(e is not None for e in exits), "mean": mean, "se": se,
                        "clusters": len({x["group"] for x in ev}), "verdict": verdict(mean, se, len(d))})
    return {"sources": sources, "positions": pos, "closed": closed, "results": res}


def _f(x, nd=4):
    return "n/a" if x is None else f"{x:+.{nd}f}"


def report(r: dict) -> str:
    n_closed = len(r["closed"])
    prim = [x for x in r["results"] if x["h"] == PRIMARY_H]
    small = n_closed < PREREG["n"]
    L = ["# Exit rules vs hold-to-settlement: counterfactual study (WX-C)", "",
         f"Closed positions: **{n_closed}** across {len(r['sources'])} paper ledgers "
         f"({len(r['positions'])} held lots found, {len(r['positions']) - n_closed} still open or unresolved).", ""]
    if small:
        L += [f"**The sample is too small to judge any exit rule: n = {n_closed} closed positions, the pre-registration "
              f"needs {PREREG['n']}. Every verdict below is INCONCLUSIVE; the numbers are descriptive only.**", ""]
    L += ["Statistic (pre-registration `exit-manager-v1`): per closed position, shares x (exit value - settlement "
          "value), net of the taker fee on the exit; mean in USD per position, CR0 cluster-robust SE by event group. "
          "PASS if mean > 2 SE with n >= 100; futility if mean < -1 SE after 50; INCONCLUSIVE while n < 100.", "",
          f"## Results at half-spread {PRIMARY_H}", "",
          "| Variant | n | not evaluable | exited | clusters | mean $/position | SE | verdict |",
          "|---|---|---|---|---|---|---|---|"]
    L += [f"| {x['variant']} | {x['n']} | {x['not_evaluable']} | {x['exited']} | {x['clusters']} | {_f(x['mean'])} | "
          f"{_f(x['se'])} | {x['verdict']} |" for x in prim]
    L += ["", "## Half-spread sensitivity (mean $/position, SE in brackets)", "",
          "| Variant | " + " | ".join(f"h = {h}" for h in HALF_SPREADS) + " |", "|---|" + "---|" * len(HALF_SPREADS)]
    for name in VARIANTS:
        cells = [x for x in r["results"] if x["variant"] == name]
        L.append(f"| {name} | " + " | ".join(f"{_f(x['mean'])} ({_f(x['se'])}), n={x['n']}" for x in cells) + " |")
    L += ["", "## Sources", "", "| Ledger | fills | held lots | closed |", "|---|---|---|---|"]
    L += [f"| {s['source']} | {s['fills']} | {s['lots']} | {s['closed']} |" for s in r["sources"]]
    L += ["", "## Closed positions", "",
          "| Source | strategy | cid | cost | shares | settled at | eligible minutes | minutes with fair | event group |",
          "|---|---|---|---|---|---|---|---|---|"]
    for x in r["closed"]:
        nm = sum(x["ts_ms"] < ms < x["end_ms"] - PULL_MS for ms, _ in x["path"])
        L.append(f"| {x['source']} | {x['strategy']} | {x['cid'][:10]} | {x['cost']} | {x['shares']} | "
                 f"{x['payout']:.0f} | {nm} | {fair_minutes(x)} | {x['group']} |")
    L += ["", "## Assumptions", "",
          "- Exit price = max(0, mid - h) from the per-minute `marks`; the real bid depth is not recorded, so fills at "
          "that price are assumed for the whole lot.",
          "- Merged shares are not studied (the merge happened in reality); only shares held to settlement are.",
          f"- Fair: the ladder's order-reason `f` (or 1 - the other token's), at most {FAIR_MAX_AGE_MS // 60000} min old. "
          "unc is bounded from the quote half-spread, so R1 here fires at most as often as live R1. Lots with no fresh "
          "fair while held (for example btc-speed trades) are not evaluable for R1/R3 and are left out of those n.",
          "- Ledgers are opened with SQLite `mode=ro`; SQLite itself may touch its WAL index file (-shm) next to a "
          "ledger, but no ledger row or other file under data/trader/ is written.",
          f"- Rule parameters: {json.dumps(P)}. R4's free-capital condition is assumed always true (an upper bound).",
          "- No exits inside the 10-minute pull window before close.", "",
          "## How to reproduce", "",
          "From `roster/`: `.venv\\Scripts\\python.exe -m research.exits.study` (add `--offline` to skip the public "
          "CLOB GET for unresolved markets). It reads every `data/trader/*/trader.db` read-only, caches outcomes in "
          "`data/exits/outcomes.json` and rewrites this report; re-running on the same data gives the same report. "
          "Tests: `.venv\\Scripts\\python.exe -m pytest tests/exits/test_study.py -q`.", ""]
    return "\n".join(L)


def main(argv=None) -> None:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--offline", action="store_true", help="no public CLOB GET; use ledger settlements and the cache")
    a.add_argument("--root", default=str(ROOT))
    a.add_argument("--out", default=str(OUT))
    a.add_argument("--report", default=str(REPORT))
    args = a.parse_args(argv)
    if not args.offline:
        from trader.loop import prefer_ipv4
        prefer_ipv4()
    r = study(args.root, args.out, None if args.offline else scorer.fetch_outcome)
    pathlib.Path(args.report).write_text(report(r), encoding="utf-8")
    print(f"{len(r['closed'])} closed positions from {len(r['sources'])} ledgers -> {args.report}")


if __name__ == "__main__":
    main()
