"""Phase C tracker (reports/research/phase_c_plan_2026-10-20.md): every active run's live estimate against the 2 SE bar,
its pace and estimated days to the bar, its trading-ready uptime over the last 7 days, and the Phase D gate.
Local data only (plus the live estimate's small tape lookups). Writes reports/research/phase_c_status.md.

  .venv\\Scripts\\python.exe ops\\phase_c.py
"""
import datetime as dt
import json
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import common  # noqa: E402
from nightly import scorer  # noqa: E402
from ops.keeper import ACTIVE  # noqa: E402
from ops.real_outcomes import run_trades  # noqa: E402
from ops.status import IST  # noqa: E402

OUT = ROOT / "reports" / "research" / "phase_c_status.md"
OOS = ROOT / "reports" / "research" / "oos" / "result.md"
MIN_N, UPTIME_MIN, WEEK_MS = 200, 0.90, 7 * 86_400_000
BTC = {"paper_v4b", "paper_v5b", "paper_v6b", "paper_v7b", "paper_mk", "paper_v8b", "paper_v4add",
       "paper_v4sz50", "paper_v4sz100", "paper_v9fix"}


def days_to_bar(n: int, mean, se, per_day: float) -> float | None:
    """Days until n reaches max(MIN_N, the n at which mean = 2 SE), if the mean and spread hold; None if mean <= 0."""
    if not n or mean is None or se is None or mean <= 0 or per_day <= 0:
        return None
    need = max(MIN_N, n * (2 * se / mean) ** 2)
    return max(0.0, (need - n) / per_day)


def awake_minutes(t0: int, t1: int, log=ROOT / "data" / "trader" / "clock_offsets.jsonl") -> set:
    """Minutes the PC was on: the feed hub logs a clock reading once a minute whenever it runs (the keeper restarts it),
    independent of the runs, so minutes when every run was down still count as on."""
    out = set()
    try:
        for line in pathlib.Path(log).read_text(encoding="utf-8").splitlines():
            ts = json.loads(line).get("ts_ms", 0) if line.strip() else 0
            if t0 <= ts < t1:
                out.add(ts // 60_000)
    except OSError:
        pass
    return out


def ready_share(db, t0: int, t1: int, awake: set | None = None) -> float:
    """Share of the minutes in [t0, t1) (or of the `awake` minutes in it) with a trading-loop latency row and no global
    pause. Without awake, sleep counts as down."""
    if not pathlib.Path(db).exists():
        return 0.0
    con = sqlite3.connect(f"{pathlib.Path(db).resolve().as_uri()}?mode=ro", uri=True)
    try:
        beats = {ev // 60_000 for (ev,) in con.execute(
            "SELECT event_ms FROM rows WHERE tbl='latency' AND event_ms >= ? AND event_ms < ?", (t0, t1))}
        trips = [(ev, json.loads(b)) for b, ev in con.execute(
            "SELECT body, event_ms FROM rows WHERE tbl='trips' AND event_ms < ? ORDER BY event_ms", (t1,))]
    finally:
        con.close()
    paused, state, i = set(), "ACTIVE", 0
    glob = [(ev, t.get("state") or t.get("level")) for ev, t in trips if t.get("scope") == "global"]
    for m in range(t0 // 60_000, t1 // 60_000):
        while i < len(glob) and glob[i][0] < (m + 1) * 60_000:
            state = glob[i][1]
            i += 1
        if state != "ACTIVE":
            paused.add(m)
    ready = beats - paused
    if awake is not None:
        return len(ready & awake) / len(awake) if awake else 0.0
    total = (t1 - t0) // 60_000
    return len(ready) / total if total else 0.0


def gate(rows: list[dict], oos_pass: bool) -> list[tuple[str, bool, str]]:
    """Phase D gate: (check, met, detail)."""
    ok = [r for r in rows if r["n"] >= MIN_N and r["mean"] is not None and r["se"] and r["mean"] > 2 * r["se"]]
    btc = [r for r in rows if r["run"] in BTC and r["n"]]
    btc_fwd = sum(r["mean"] * r["n"] for r in btc) / sum(r["n"] for r in btc) if btc else None
    up = [r for r in ok if r["uptime"] >= UPTIME_MIN]
    return [("a run passes 2 SE at the live estimate over 200+ trades", bool(ok), ", ".join(r["run"] for r in ok) or "none yet"),
            ("BTC: out-of-sample PASS and the forward BTC live estimate agrees (> 0)", oos_pass and (btc_fwd or 0) > 0,
             f"OOS {'PASS' if oos_pass else 'not passed'}, forward BTC {btc_fwd:+.3f}/trade" if btc_fwd is not None else "no BTC trades"),
            (f"that run was trading-ready >= {UPTIME_MIN:.0%} of the hours the PC was on (last 7 days)", bool(up),
             ", ".join(f"{r['run']} {r['uptime']:.0%}" for r in ok) or "no passing run")]


def main() -> int:
    now = common.now_ms()
    awake = awake_minutes(now - WEEK_MS, now)
    rows = []
    for run in ACTIVE:
        trades, _, _ = run_trades(run)
        xs, cids = [t["live_est_pnl"] for t in trades], [t["market"] for t in trades]
        mean = sum(xs) / len(xs) if xs else None
        se = scorer.cluster_se(xs, cids)
        per_day = len(xs) / max(1, len({t["day_ist"] for t in trades}))
        rows.append({"run": run, "n": len(xs), "mean": mean, "se": se, "per_day": per_day,
                     "eta": days_to_bar(len(xs), mean, se, per_day),
                     "uptime": ready_share(ROOT / "data" / "trader" / run / "trader.db", now - WEEK_MS, now, awake),
                     "uptime24": ready_share(ROOT / "data" / "trader" / run / "trader.db", now - WEEK_MS, now)})
    oos_pass = OOS.exists() and "**PASS**" in OOS.read_text(encoding="utf-8").split("## Secondary")[0]
    f = lambda x, d=3: "n/a" if x is None else f"{x:+.{d}f}"
    L = ["# Phase C status", "", f"Written {dt.datetime.now(IST):%d %b %Y %H:%M} IST by ops/phase_c.py "
         "(plan: phase_c_plan_2026-10-20.md). Live estimate per trade, cluster SE by market; days to the bar assume the "
         "mean, spread and pace so far hold. Uptime: share of the last 7 days' minutes with a running, unpaused loop, "
         f"counted over the {len(awake) / 60:.0f} h the PC was on (the gate) and over all 168 h (for reference).", "",
         "| Run | Trades | Live $/trade | SE | Over 2 SE? | Trades/day | Days to the bar | Uptime (PC on) | Uptime (24 h) |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        over = r["mean"] is not None and r["se"] is not None and r["mean"] > 2 * r["se"]
        L.append(f"| {r['run']} | {r['n']} | {f(r['mean'])} | {f(r['se'])[1:] if r['se'] else 'n/a'} | {'yes' if over else 'no'} | "
                 f"{r['per_day']:.0f} | {'n/a' if r['eta'] is None else f'{r['eta']:.1f}'} | {r['uptime']:.0%} | {r['uptime24']:.0%} |")
    L += ["", "## Phase D gate (all three needed)", ""]
    L += [f"- [{'x' if met else ' '}] {name}: {detail}" for name, met, detail in gate(rows, oos_pass)]
    L += ["", "Gate met is not a go-live: Phase D still needs the ToS check, a Dublin server, wallet funding and a 1-2 "
          "share canary, each decided by the user."]
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
