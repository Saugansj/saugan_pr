"""Nightly learning run (WW-E): canary, analyst, outcome-blind postmortems, CUSUM scans, Loop A refits and replay.

  python -m nightly.run --dir data/trader/<run> [--out-dir data/nightly] [--live-journal data/trader/live_journal.jsonl]
                        [--replay-hour 2026-09-30T14 --replay-engine speed] [--cusum-h 4.0]

Read-only on the run dir and offline: outcomes come from the ledger's settlements and the outcomes.json cache that
nightly.report keeps (no GET here). Writes only under --out-dir: nightly_<date>.md, candidates.jsonl (registry
candidates, never registered or promoted here) and replay_trials.jsonl (every replay trial, failed ones included).
CUSUM trips are reported as the action they would raise ("lock"/"alarm"); nothing here calls the kernel.

Rows built from the Phase 1 ledger (one position per (cid, token) held, all its fills):
- clv = side x (last per-minute mid_ex_own at or before the market's end - entry VWAP), the only closing line we have;
- markout_5m = size-weighted 5 m markout of its fills; primary = fee-net P&L held to resolution (None if unresolved);
- forecasts / Loop A rows = ladder-maker universe checkpoints (p = fair) with a known outcome.
"""
import argparse
import bisect
import datetime as dt
import json
import math
import pathlib
import statistics
import types
from collections import Counter

import numpy as np
from scipy.special import expit

import common
from learning import analyst, cusum, loop_a, postmortem
from nightly import scorer
from trader.engines import ladder
from trader.kernel import STRATEGIES
from trader.live import canary

MARK_MAX_MS = 120_000  # a per-minute mark further than this past the asked time is no mark


def _f(x, nd=4) -> str:
    return "-" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _pm(m, se) -> str:
    return f"{_f(m)} +/- {_f(se)}"


def mode_of(strategy: str) -> str:
    return STRATEGIES.get(strategy, {}).get("modes", ("unknown",))[0]


class Marks:
    """mid_ex_own per token from the ledger's per-minute `marks` rows."""

    def __init__(self, rows):
        self.rows = sorted(((r["event_ms"], r) for r in rows), key=lambda x: x[0])
        self.t = [t for t, _ in self.rows]

    def after(self, tok, ts):
        """First mark of tok at or after ts (within MARK_MAX_MS), else None: the canary's mid 5 min after a fill."""
        for t, r in self.rows[bisect.bisect_left(self.t, ts):]:
            if t - ts > MARK_MAX_MS:
                return None
            if r.get(tok) is not None:
                return r[tok]
        return None

    def before(self, tok, ts):
        """Last mark of tok at or before ts, else None: the closing line."""
        for t, r in reversed(self.rows[:bisect.bisect_right(self.t, ts)]):
            if r.get(tok) is not None:
                return r[tok]
        return None


def build_rows(cum: dict, oc: dict) -> tuple[list, list, list, list]:
    """(positions, fills, forecasts, loop_a rows) in learning/'s shapes."""
    marks = Marks(cum.get("marks", []))
    asset = {r["cid"]: r.get("asset") for r in cum.get("universe_checkpoint", [])}
    mo = {(r["order_id"], r["fill_ms"], r["horizon_s"]): r["markout"] for r in cum.get("markouts", [])}
    fills, pos = [], {}
    for f in cum.get("fills", []):
        m5 = mo.get((f["order_id"], f["ts_ms"], 300))
        rebate = (ladder.PARAMS["rebate_rate"] * (f.get("fee_rate") or 0.0) * f["price"] * (1 - f["price"]) * f["size"]
                  if f["maker"] else 0.0)
        und = asset.get(f["cid"]) or ("BTC" if f["strategy"] == "btc-speed" else None)
        row = dict(cid=f["cid"], cluster_id=f["cluster_id"], mode=mode_of(f["strategy"]), strategy=f["strategy"],
                   underlying=und, league=None, token_id=f["token_id"], side=f["side"], price=f["price"],
                   size=f["size"], maker=f["maker"], fee=f["fee"], rebate=rebate, reward=0.0, ts_ms=f["ts_ms"],
                   mid_ex_own=None, markout_5s=mo.get((f["order_id"], f["ts_ms"], 5)),
                   markout_1m=mo.get((f["order_id"], f["ts_ms"], 60)), markout_5m=m5)
        fills.append(row)
        p = pos.setdefault((f["cid"], f["token_id"]), {"row": row, "end_ms": f.get("end_ms"), "first": f["ts_ms"],
                                                         "net": 0.0, "cash": 0.0, "fee": 0.0, "bought": 0.0,
                                                         "cost": 0.0, "mo": [0.0, 0.0]})
        s = 1 if f["side"] == "BUY" else -1
        p["net"] += s * f["size"]
        p["cash"] -= s * f["size"] * f["price"]
        p["fee"] += f["fee"]
        if s > 0:
            p["bought"] += f["size"]
            p["cost"] += f["size"] * f["price"]
        if m5 is not None:
            p["mo"][0] += m5 * f["size"]
            p["mo"][1] += f["size"]
    positions = []
    for (cid, tok), p in pos.items():
        r, held = p["row"], abs(p["net"]) > 1e-9
        side = "BUY" if p["net"] >= 0 else "SELL"
        entry = p["cost"] / p["bought"] if p["bought"] else r["price"]
        close = marks.before(tok, p["end_ms"]) if p["end_ms"] else None
        o = (oc.get(cid) or {}).get("winner")
        outcome = None if o is None else int(o == tok)
        pnl = None if outcome is None else p["net"] * outcome + p["cash"] - p["fee"]
        size = abs(p["net"]) if held else p["bought"]
        positions.append(dict(
            pos_id=f"{cid}:{tok}", cid=cid, cluster_id=r["cluster_id"], mode=r["mode"], strategy=r["strategy"],
            underlying=r["underlying"], league=None,
            horizon_h=(p["end_ms"] - p["first"]) / 3_600_000 if p["end_ms"] else None, side=side, size=size,
            entry_price=entry, clv=None if close is None else (1 if side == "BUY" else -1) * (close - entry),
            markout_5m=p["mo"][0] / p["mo"][1] if p["mo"][1] else None,
            fee_per_share=p["fee"] / size if size else 0.0, flags=[], outcome=outcome, pnl=pnl, primary=pnl,
            close_ms=p["end_ms"] or p["first"]))
    traded = {f["cid"] for f in fills}
    forecasts, la = [], []
    for c in cum.get("universe_checkpoint", []):
        y = (oc.get(c["cid"]) or {}).get("yes")
        if c.get("fair") is None or c.get("mid_ex_own") is None:
            continue
        forecasts.append(dict(p=c["fair"], mid_ex_own=c["mid_ex_own"], outcome=None if y is None else int(y),
                              cluster_id=c["cluster"], mode="crypto-term", underlying=c.get("asset"), league=None,
                              horizon_h=c.get("tau_h") or c.get("bucket_h"), traded=c["cid"] in traded,
                              strategy=ladder.NAME, event_ms=c["event_ms"]))
        if y is not None:
            la.append(dict(y=int(y), m=c["mid_ex_own"], f=c["fair"], cluster_id=c["cluster"], resolved_ms=c["end_ms"]))
    return positions, fills, forecasts, la


# ---------------------------------------------------------------- sections

def canary_section(d: pathlib.Path, cum: dict, live_journal: pathlib.Path | None) -> list[str]:
    markets = {f["cid"]: types.SimpleNamespace(event_group=f["cluster_id"]) for f in cum.get("fills", [])}
    marks = Marks(cum.get("marks", []))
    paper = canary.rows_from_journal(d / "journal.jsonl", markets, marks.after)
    L = ["## Canary (2.8): live maker fills vs the paper/replay simulator", "",
         f"- Paper journal rows (terminal maker orders): {len(paper)}, clusters {len({r['cluster'] for r in paper})}, "
         f"with a fill {sum(r['filled'] > 0 for r in paper)}."]
    if not (live_journal and live_journal.exists()):
        return L + ["- **Not evaluated**: no live journal (paper only). It runs once "
                    "`data/trader/live_journal.jsonl` exists (pass `--live-journal`).", ""]
    res = canary.evaluate(canary.rows_from_journal(live_journal, markets, marks.after), paper)
    L += [f"- Live journal `{live_journal}`: verdict **{res['verdict']}**: {res['reason']}", "",
          "| bucket | live orders | live clusters | fill rate | replay 90% PI | outside |", "|---|---|---|---|---|---|"]
    L += [f"| {b['bucket']} | {b['live_orders']} | {b['live_clusters']} | {_f(b['fill_rate'])} | "
          f"{b['fill_rate_pi'] and [round(x, 4) for x in b['fill_rate_pi']]} | {', '.join(b['outside']) or '-'} |"
          for b in res["buckets"]]
    return L + [""]


def analysis_section(positions, fills, forecasts, now: int, cands: list) -> list[str]:
    bd = analyst.breakdown(positions, fills)
    L = ["## Analyst (role 32): per-mode breakdown and calibration", "",
         f"Positions {len(positions)} (resolved {sum(p['outcome'] is not None for p in positions)}), fills {len(fills)}, "
         f"checkpoint forecasts {len(forecasts)} (resolved {sum(r['outcome'] is not None for r in forecasts)}).", "",
         "| Mode | Dim | Key | Positions | Fills | Clusters | CLV | Primary (fee-net) | Markout 5m |",
         "|---|---|---|---|---|---|---|---|---|"]
    L += [f"| {c['mode']} | {c['dim']} | {c['key']} | {c['positions']} | {c['fills']} | {c['clusters']} | "
          f"{_pm(c['clv'], c['clv_se'])} | {_pm(c['primary'], c['primary_se'])} | {_pm(c['markout_5m'], c['markout_5m_se'])} |"
          for c in bd if c["dim"] in ("all", "strategy")] or ["| - | - | - | 0 | 0 | 0 | - | - | - |"]
    rel = [r for r in analyst.reliability(forecasts) if r["dim"] == "all"]
    L += ["", "| Mode | Subset | Rows | Clusters | Brier fair | Brier mid | Fair - mid |", "|---|---|---|---|---|---|---|"]
    L += [f"| {r['mode']} | {r['subset']} | {r['rows']} | {r['clusters']} | {_f(r['brier_p'])} | {_f(r['brier_m'])} | "
          f"{_pm(r['brier_diff'], r.get('brier_diff_se'))} |" for r in rel] or ["| - | - | 0 | 0 | - | - | - |"]
    for mode in sorted({c["mode"] for c in bd}):
        budgets = {s: v["budget_usd"] for s, v in STRATEGIES.items() if mode in v["modes"]}
        c = analyst.budget_candidate([r for r in bd if r["mode"] == mode], budgets)
        if c:
            cands.append(c)
        L.append(f"\nBudget candidate for {mode}: " + (f"`{c['name']}` {c['params']} (candidate only)" if c else "none "
                                                       "(no strategy 2 SE below 0 over >= 20 clusters)") + ".")
    classes = postmortem.classify_all(positions)
    les = postmortem.lessons(positions, classes, now)
    cands += les
    L += ["", "## Postmortems (role 33, outcome-blind)", "",
          "Classes (from CLV, markout, fees and flags only; outcome never read): "
          + (", ".join(f"{k} {v}" for k, v in sorted(Counter(classes).items())) or "no positions") + ".",
          "Lessons (candidates only): " + (", ".join(f"`{x['name']}`" for x in les) or "none (needs >= 20 clusters "
                                                                                   "significantly below 0)") + ".", ""]
    return L


def cusum_section(positions, fills, forecasts, h: float) -> list[str]:
    scans = [("role 02 markout lock, per (strategy, underlying) series",
              cusum.Monitor("02-cusum", "lock", "markout", h), fills, "markout_5m", ("strategy", "underlying"), "ts_ms"),
             ("role 02 CLV lock, per (mode, strategy)",
              cusum.Monitor("02-cusum", "lock", "clv", h), positions, "clv", ("mode", "strategy"), "close_ms"),
             ("role 34 bias drift (fair - outcome), per underlying",
              cusum.Monitor("34-drift", "alarm", "bias", h, ("low", "high")),
              [r for r in forecasts if r["outcome"] is not None], lambda r: r["p"] - r["outcome"], "underlying", "event_ms")]
    L = ["## CUSUM scans (roles 02 and 34)", "",
         f"h = {h} (default until a calibrated h is registered via cusum.calibrate_h on the real series); a key needs "
         "20 clusters of burn-in. Actions are what the monitor would raise; nothing is sent to the kernel here.", "",
         "| Scan | Keys | Keys with >= 20 clusters | Trips |", "|---|---|---|---|"]
    for name, mon, rows, value, key, time in scans:
        ser = cusum.per_cluster(rows, value, key, time)
        trips = cusum.scan(mon, rows, value, key, time)
        L.append(f"| {name} | {len(ser)} | {sum(len(s) >= 20 for s in ser.values())} | "
                 + ("; ".join(f"{a['action']} {a['scope']} ({a['reason']})" for a, _, _ in trips) or "none") + " |")
    return L + [""]


def loop_a_section(rows, cands: list) -> list[str]:
    n = len({r["cluster_id"] for r in rows})
    L = ["## Loop A anchored refits (roles 21, 23; candidates only)", "",
         f"Resolved checkpoint rows {len(rows)} in {n} clusters (a refit needs {loop_a.MIN_CLUSTERS})."]
    if n < 2:
        return L + ["Refit: not run (fewer than 2 resolved clusters). kelly-c candidate: none.", ""]
    t_split = statistics.median(r["resolved_ms"] for r in rows)
    train, test = loop_a.walk_forward(rows, t_split)
    fit = loop_a.fit_blend(train)
    if fit:
        cand = lambda r: float(expit(fit["a"] + fit["b"] * loop_a.logit(r["m"]) +  # noqa: E731
                                     fit["c"] * (loop_a.logit(r["f"]) - loop_a.logit(r["m"]))))
        cur = lambda r: r["f"]  # noqa: E731 - Phase 1 fair is both anchor and current
        won = loop_a.refit_step(cur, cur, cand, test) is cand
        if won:
            cands.append({"name": "ladder-blend", "params": fit, "state": "candidate"})
        L.append(f"Refit on {len(train)} train rows: {fit}; out of sample on {len(test)} unseen-cluster rows it "
                 f"{'beats current by > 2 SE: candidate written' if won else 'does not beat current: current kept'}.")
    else:
        L.append(f"Refit: train set below {loop_a.MIN_CLUSTERS} clusters, nothing fitted; current kept.")
    kc = loop_a.c_candidate(rows) if n >= loop_a.MIN_CLUSTERS else None
    if kc:
        cands.append(kc)
    return L + [f"kelly-c candidate: {kc['params'] if kc else 'none'} (live needs Ledger.promote with the human token).", ""]


def replay_job(engine, store, start: int, end: int, rtt: float, trials: pathlib.Path, outcomes: dict,
               modes=None) -> list[str]:
    """learning.replay.run.replay with the real kernel (no clearances: replay passes none), one TrialLog row per run."""
    from learning.replay.run import replay
    from learning.replay.validate import TrialLog
    from trader.kernel import RiskKernel
    family = f"replay:{engine.name}"
    params = {"engine": getattr(engine, "p", None), "rtt_ms": rtt, "fill_mode": "strict", "kernel": "RiskKernel"}
    dataset = {"start_ms": start, "end_ms": end, "events": dict(store.counts)}
    log = TrialLog(trials)
    try:
        res = replay(engine, store, start, end, rtt, kernel=RiskKernel(secret="", nonce_path=None),
                     outcomes=outcomes, modes=modes)
    except Exception:
        log.append(family, params, dataset, status="failed")  # failed runs count toward the DSR's N
        raise
    st = res["stat"]
    log.append(family, params, dataset, statistic=None if not math.isfinite(st["mean"]) else st["mean"],
               sharpe=st["sharpe"], clusters=st["clusters"])
    sh = log.sharpes(family)
    dec = Counter("approved" if d.approved else d.reason.split(":")[0] for _, _, d in res["decisions"])
    return [f"- Engine `{engine.name}`, window {start} to {end} ms, rtt {rtt} ms ({res['label']}).",
            f"- Ticks {res['ticks']}, look-ahead checks {res['checks']}, intents {len(res['intents'])}, kernel decisions "
            + (", ".join(f"{k} {v}" for k, v in dec.most_common(5)) or "none") + f", fills {len(res['fills'])}.",
            f"- Fee-net P&L per cluster: mean {_f(st['mean'])}, SE {_f(st['se'])}, clusters {st['clusters']}.",
            f"- Trial log `{trials}`: family N = {log.count(family)}, V(Sharpe) = "
            f"{_f(float(np.var(sh, ddof=1)) if len(sh) > 1 else None)} (the DSR's N and V)."]


def replay_section(hour: str | None, engine_name: str, rtt: float, trials: pathlib.Path, oc: dict) -> list[str]:
    L = ["## Replay job (role 35, exploratory)", ""]
    if not hour:
        return L + ["Not run: pass `--replay-hour YYYY-MM-DDTHH` (a recorded hour under data/recordings).", ""]
    from learning.replay.__main__ import ENGINES, WARM_MS
    from learning.replay.events import H_MS, Store, load_dvol, load_finals, load_markets, load_pm, load_ref
    cls, stream, _ = ENGINES[engine_name]
    h0 = int(dt.datetime.strptime(hour, "%Y-%m-%dT%H").replace(tzinfo=dt.UTC).timestamp() * 1000)
    pm = load_pm((stream,), h0, h0 + H_MS - 1)
    if not pm:
        return L + [f"No {stream} recording for {hour}.", ""]
    start, end = min(r[0] for r in pm), max(r[0] for r in pm)
    lo = start - WARM_MS
    store = Store(pm=pm, markets=load_markets((stream,), start, end), ref=load_ref(lo, end), dvol=load_dvol(lo, end),
                  finals=load_finals(lo, end))
    yes = {c: int(o["yes"]) for c, o in oc.items() if o.get("yes") is not None}
    return L + replay_job(cls(), store, start, end, rtt, trials, yes, modes={stream}) + [
        "- Reference: data/history/binance 1m closes (no fetch here; they may not cover the hour).", ""]


SECTIONS = ("canary", "analysis", "cusum", "loop_a", "replay")


def build(d, out_dir, now: int | None = None, live_journal=None, replay_hour=None, replay_engine="speed",
          rtt: float = 210.0, cusum_h: float = 4.0) -> tuple[str, list[dict]]:
    """(markdown, candidates). Every section is produced; a failing one says so instead of stopping the others."""
    d, out_dir = pathlib.Path(d), pathlib.Path(out_dir)
    now = common.now_ms() if now is None else now
    cum = scorer.tables(d)
    oc = scorer.outcomes(d, cum, now, fetch=None)  # offline: no GET, no write to the run dir
    positions, fills, forecasts, la = build_rows(cum, oc)
    cands: list[dict] = []
    run = {"canary": lambda: canary_section(d, cum, live_journal and pathlib.Path(live_journal)),
           "analysis": lambda: analysis_section(positions, fills, forecasts, now, cands),
           "cusum": lambda: cusum_section(positions, fills, forecasts, cusum_h),
           "loop_a": lambda: loop_a_section(la, cands),
           "replay": lambda: replay_section(replay_hour, replay_engine, rtt, out_dir / "replay_trials.jsonl", oc)}
    L = [f"# Nightly learning run {dt.datetime.fromtimestamp(now / 1000, dt.UTC):%Y-%m-%d %H:%M} UTC", "",
         f"Ledger `{d}` (read-only, offline). Nothing here promotes, registers or trips anything: candidates go to "
         f"`{out_dir / 'candidates.jsonl'}` for a human to review.", ""]
    for name in SECTIONS:
        try:
            L += run[name]()
        except Exception as e:  # noqa: BLE001 - one section's failure is reported, the rest still run
            L += [f"## {name}", "", f"**Section failed**: {type(e).__name__}: {e}", ""]
    L += [f"Candidates this run: {len(cands)}.", ""]
    return "\n".join(L), cands


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", type=pathlib.Path, default=common.DATA / "trader")
    ap.add_argument("--out-dir", type=pathlib.Path, default=common.DATA / "nightly")
    ap.add_argument("--live-journal", type=pathlib.Path, default=common.DATA / "trader" / "live_journal.jsonl")
    ap.add_argument("--replay-hour")
    ap.add_argument("--replay-engine", default="speed", choices=("ladder", "speed"))
    ap.add_argument("--rtt", type=float, default=210.0)
    ap.add_argument("--cusum-h", type=float, default=4.0)
    a = ap.parse_args(argv)
    now = common.now_ms()
    md, cands = build(a.dir.resolve(), a.out_dir, now, a.live_journal, a.replay_hour, a.replay_engine, a.rtt, a.cusum_h)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    for c in cands:
        common.append_jsonl(a.out_dir / "candidates.jsonl", {**c, "ts_ms": now, "dir": str(a.dir)})
    md += ("\n## How to reproduce\n\n```\ncd roster\n.venv\\Scripts\\python.exe -m nightly.run --dir "
           f"{a.dir.as_posix()} --out-dir {a.out_dir.as_posix()}"
           + (f" --replay-hour {a.replay_hour} --replay-engine {a.replay_engine}" if a.replay_hour else "") + "\n```\n")
    out = a.out_dir / f"nightly_{dt.datetime.fromtimestamp(now / 1000, dt.UTC):%Y-%m-%d}.md"
    out.write_text(md, encoding="utf-8")
    print(f"wrote {out}; candidates {len(cands)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
