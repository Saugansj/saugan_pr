"""Anomaly watch for the paper runs (read-only, stdlib only).

Tracks the things that quietly cost us sample and money across the roster, and prints one compact report:

  1. coverage gaps   - minutes missing from a run's own latency heartbeats (PC sleep, a hung loop)
  2. halts           - REDUCING blocks >= 20 min, by cause, and how much of the 18-22 IST session they ate
  3. loop lag        - recorded event-loop lag that is physically impossible (clock jump or sleep, not a blocked loop)
  4. trade pace      - resolved trades per IST day, and calendar days inside the run's span with no trade at all
  5. fill model      - traded signals that the live estimate books at $0 (no fill) split by win/loss, and days where
                       the live estimate exceeds its own optimistic bound (real best)
  6. duplicate risk  - how much of a run's trade set is the same market+second as another run's (runs are not independent)
  7. feed health     - clock-offset warnings in the feed hub log on the last day, and today's hub data volume

Nothing here writes to a run. Use it before trusting a day's number, or nightly next to the reports.

  .venv\\Scripts\\python.exe ops\\anomaly_watch.py [run ...] [--days N]     # the last N days, per run
  .venv\\Scripts\\python.exe ops\\anomaly_watch.py --history               # whole history, every run in the tape file
"""
import collections
import datetime as dt
import json
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
CSV = ROOT / "reports" / "research" / "real_outcomes_trades.csv"
HUB_LOG = ROOT / "data" / "trader" / "feedhub_console.log"
HUB_KEY = "today "
# keeper.ACTIVE plus the retired runs still quoted in the reports: a silent run is the thing to see
DEFAULT = ["paper_v4b", "paper_ethb", "paper_v6b", "paper_v7b", "paper_v8b", "paper_mk", "paper_ethmk", "paper_v4add",
           "paper_v4sz50", "paper_v4sz100", "paper_v9fix"]
EVENING = (18, 22)   # IST hours of the one session with a visibly positive live estimate
ETH_RUNS = {"paper_eth", "paper_ethb", "paper_ethc", "paper_eth6b", "paper_eth7c", "paper_ethmk"}


def db(run: str) -> sqlite3.Connection | None:
    p = ROOT / "data" / "trader" / run / "trader.db"
    return sqlite3.connect(f"{p.as_uri()}?mode=ro", uri=True) if p.exists() else None


def rows(con: sqlite3.Connection, tbl: str) -> list[tuple[int, dict]]:
    return [(e, json.loads(b)) for e, b in con.execute(
        "select event_ms, body from rows where tbl=? order by event_ms", (tbl,))]


def ist(ms: float) -> dt.datetime:
    return dt.datetime.fromtimestamp(ms / 1000, IST)


def gaps(minutes: list[dt.datetime], tol_min: int = 2) -> list[tuple[dt.datetime, dt.datetime, float]]:
    out, prev = [], None
    for t in sorted(minutes):
        if prev and (t - prev).total_seconds() > tol_min * 60:
            out.append((prev, t, (t - prev).total_seconds() / 60))
        prev = t
    return out


def halts(trips: list[tuple[int, dict]]) -> list[tuple[int, int, str]]:
    out, since, why = [], None, ""
    for e, b in trips:
        state = b.get("state") or b.get("level")
        if state == "REDUCING":
            if since is None:
                since, why = e, b.get("reason", "")
        elif since is not None:
            out.append((since, e, why))
            since = None
    if since is not None:
        out.append((since, e, why + " (still halted)"))
    return out


def evening_minutes(a: int, b: int) -> float:
    """Minutes of [a, b) that fall in the 18:00-22:00 IST window, summed over days."""
    cur, total = ist(a), 0.0
    end = ist(b)
    while cur < end:
        lo = max(cur, cur.replace(hour=EVENING[0], minute=0, second=0, microsecond=0))
        hi = min(end, cur.replace(hour=EVENING[1], minute=0, second=0, microsecond=0))
        if hi > lo:
            total += (hi - lo).total_seconds() / 60
        cur = (cur + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return total


def load_outcomes() -> list[dict]:
    if not CSV.exists():
        return []
    import csv
    with open(CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def minutes_of(run: str) -> list[dt.datetime]:
    con = db(run)
    if con is None:
        return []
    try:
        return [ist(e) for e, _ in rows(con, "latency")]
    finally:
        con.close()


def load_outcomes() -> list[dict]:
    if not CSV.exists():
        return []
    import csv
    with open(CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def shared_gaps(all_minutes: dict[str, list[dt.datetime]], days: int) -> list[tuple]:
    """Gaps in the union of every run's heartbeats: the stretches when the whole roster was silent."""
    cut = dt.datetime.now(IST) - dt.timedelta(days=days)
    union = sorted({t for ms in all_minutes.values() for t in ms})
    return [(a, b, m) for a, b, m in gaps(union) if b >= cut and m >= 10]


def report(run: str, days: int, oc_by_run: dict[str, list[dict]], keys: dict[str, set],
           union: list[dt.datetime], pc_gaps: list[tuple]) -> list[str]:
    con = db(run)
    print(f"\n== {run}")
    if con is None:
        print("  WARN no trader.db")
        return ["no db"]
    warns = []
    try:
        lat = rows(con, "latency")
        trips = rows(con, "trips")
    finally:
        con.close()

    cut = dt.datetime.now(IST) - dt.timedelta(days=days)
    own = [ist(e) for e, _ in lat]
    # gaps the roster did not share: this run alone was down while the PC was up
    covered = [t for t in union if t >= cut]
    for a, b, m in gaps(own):
        if b < cut or m < 10 or any(g[0] <= a and b <= g[1] for g in pc_gaps):
            continue
        if any(a <= t <= b for t in covered):
            continue
        print(f"  WARN run-only gap {a:%d-%b %H:%M} -> {b:%H:%M} IST  {m / 60:.1f} h (this run dead, the PC up)")
        warns.append("run_down")

    hb = halts(trips)
    hb = [(a, b, w) for a, b, w in hb if ist(b) >= cut and (b - a) / 60000 >= 20]
    if hb:
        by = collections.Counter()
        eve = 0.0
        for a, b, w in hb:
            by["daily loss" if "daily loss" in w else "stale feed" if "stale feed" in w else "other"] += (b - a) / 3600000
            eve += evening_minutes(a, b)
        print(f"  WARN halted {sum(by.values()):.1f} h in {len(hb)} blocks: "
              + ", ".join(f"{k} {v:.1f} h" for k, v in sorted(by.items()))
              + f" | {eve / 60:.1f} h of the 18-22 IST session lost")
        for a, b, w in hb[-3:]:
            print(f"        {ist(a):%d-%b %H:%M} {((b - a) / 60000):6.0f} min  {w[:70]}")
        warns.append("halt")

    bad = [(ist(e), b["loop_ms"]["max"]) for e, b in lat if b.get("loop_ms", {}).get("max", 0) > 6 * 3600_000]
    if bad:
        t, v = bad[-1]
        print(f"  WARN loop lag {v / 3600000:.1f} h recorded at {t:%d-%b %H:%M} (a 100 ms timer cannot be that late: "
              f"the PC slept or the clock jumped)")
        warns.append("loop_lag")

    oc = oc_by_run.get(run, [])
    if oc:
        per = collections.Counter()
        for r in oc:
            per[dt.date.fromisoformat(r["day_ist"])] += 1
        span = (dt.datetime.now(IST).date() - min(per)).days + 1
        zero = [d for i in range(span) if (d := min(per) + dt.timedelta(days=i)) not in per and d <= dt.datetime.now(IST).date()]
        cut_d = (dt.datetime.now(IST) - dt.timedelta(days=days)).date()
        zero = [d for d in zero if d >= cut_d]
        txt = f"trades/day (resolved, {days} d): {[per.get(cut_d + dt.timedelta(days=i), 0) for i in range(days + 1)]}"
        silent = [f"{d.day:02d}-{d:%b}" for d in zero][:8]
        print("  " + txt + (f" | {len(zero)} silent days {silent}" if zero else ""))
        if zero:
            warns.append("silent")

        unf = [r for r in oc if float(r["live_shares"] or 0) == 0]
        wins = [r for r in unf if r["won"] in ("True", "1", "true")]
        if unf:
            lost = sum(float(r["paper_pnl"]) for r in unf if r not in wins)
            gave = sum(float(r["paper_pnl"]) for r in wins)
            print(f"  fill model (all history): {len(unf)}/{len(oc)} trades booked at $0 (no fill): {len(wins)} winners "
                  f"(+{gave:.1f} paper dropped), {len(unf) - len(wins)} losers ({lost:+.1f} paper avoided)")
        over = collections.Counter()
        over_sum = collections.defaultdict(float)
        for r in oc:
            ex = float(r["live_est_pnl"]) - float(r["real_best_pnl"])
            if ex > 1e-6:
                over[r["day_ist"]] += 1
                over_sum[r["day_ist"]] += ex
        if over:
            d0 = max(over_sum, key=over_sum.get)
            print(f"  WARN live > real best on {sum(over.values())} trades ({sum(over_sum.values()):+.1f} USD, all history); "
                  f"worst day {d0} {over[d0]} trades {over_sum[d0]:+.1f} USD: the day total is not a lower bound")
            warns.append("live_gt_best")

    peer = {k: len(keys.get(run, set()) & v) for k, v in list(keys.items()) if k != run and keys.get(run, set()) & v}
    if peer:
        top = sorted(peer.items(), key=lambda kv: -kv[1])[:2]
        print("  duplicate risk: same market+second as " + ", ".join(f"{k} {n} trades" for k, n in top)
              + f" (of {len(keys[run])} distinct)")
        warns.append("overlap")
    return warns


def history(days: int) -> None:
    """Whole-history view of every run in the tape file: what each run has actually established."""
    oc = load_outcomes()
    if not oc:
        print("\n== history\n  no real_outcomes_trades.csv")
        return
    num = ("shares", "paper_fill", "real_min", "paper_pnl", "live_est_pnl", "live_shares", "real_best_pnl")
    for r in oc:
        for k in num:
            r[k] = float(r[k]) if r[k] not in ("", "nan") else float("nan")
        r["wonb"] = r["won"] in ("True", "1", "true")
        r["asset"] = "ETH" if r["run"] in ETH_RUNS else "BTC"

    print("\n== history: every run the tape file knows (the file holds whatever the last refresh asked for)")
    print(f"  {'run':12s} {'first':>10s} {'last':>10s} {'days':>4s} {'trd':>4s} {'mkts':>5s} {'paper$':>8s} "
          f"{'live$':>8s} {'live/tr':>7s} {'keep%':>5s} {'fill%':>5s} {'win%':>5s} {'fee%gr':>6s}")
    for run in sorted({r["run"] for r in oc}):
        x = [r for r in oc if r["run"] == run]
        d0, d1 = min(r["day_ist"] for r in x), max(r["day_ist"] for r in x)
        span = (dt.date.fromisoformat(d1) - dt.date.fromisoformat(d0)).days + 1
        sh = sum(r["shares"] for r in x)
        paper = sum(r["paper_pnl"] for r in x)
        live = sum(r["live_est_pnl"] for r in x)
        fs = sum(r["live_shares"] for r in x if r["live_shares"])
        fees = sum(r["shares"] * 0.07 * r["paper_fill"] * (1 - r["paper_fill"]) for r in x)
        print(f"  {run:12s} {d0:>10s} {d1:>10s} {span:4d} {len(x):4d} {len({r['market'] for r in x}):5d} "
              f"{paper:8.2f} {live:8.2f} {live / len(x):7.3f} {100 * live / paper if paper else 0:5.0f} "
              f"{100 * fs / sh if sh else 0:5.0f} {100 * sum(r['wonb'] for r in x) / len(x):5.1f} "
              f"{100 * fees / (live + fees) if live + fees else 0:5.0f}%")
    print(f"  {'ROSTER':12s} {'':>10s} {'':>10s} {'':>4s} {len(oc):4d} {len({r['market'] for r in oc}):5d} "
          f"{sum(r['paper_pnl'] for r in oc):8.2f} {sum(r['live_est_pnl'] for r in oc):8.2f}   "
          f"{len({r['market'] + r['time_ist'] for r in oc})} distinct decisions, "
          f"BTC {sum(r['live_est_pnl'] for r in oc if r['asset'] == 'BTC'):+.2f} vs "
          f"ETH {sum(r['live_est_pnl'] for r in oc if r['asset'] == 'ETH'):+.2f}")

    print("\n== history: calibration, edge in cents per share (is the edge real, and where?)")
    print(f"  {'asset':5s} {'fill band':10s} {'n':>4s} {'avg fill':>8s} {'win%':>6s} {'paperC':>7s} {'liveC':>7s} {'verdict':>18s}")
    for asset in ("BTC", "ETH"):
        for lo, hi in [(0, .2), (.2, .35), (.35, .5), (.5, .6), (.6, .7), (.7, .8), (.8, 1.01)]:
            x = [r for r in oc if r["asset"] == asset and lo <= r["paper_fill"] < hi]
            if len(x) < 8:
                continue
            sh = sum(r["shares"] for r in x)
            fs = sum(r["live_shares"] for r in x if r["live_shares"])
            pc = sum(r["paper_pnl"] for r in x) / sh * 100 if sh else float("nan")
            lc = sum(r["live_est_pnl"] for r in x) / fs * 100 if fs else float("nan")
            print(f"  {asset:5s} {f'{lo:.2f}-{hi:.2f}':10s} {len(x):4d} {sum(r['paper_fill'] for r in x) / len(x):8.3f} "
                  f"{100 * sum(r['wonb'] for r in x) / len(x):6.1f} {pc:7.2f} {lc:7.2f} "
                  f"{'destroys value' if lc < -2 else 'thin' if abs(lc) <= 2 else 'pays':>18s}")

    print("\n== history: is the mean carried by a few trades?")
    for run in sorted({r["run"] for r in oc}):
        v = [r["live_est_pnl"] for r in oc if r["run"] == run]
        if len(v) < 20:
            continue
        tot, n, k = sum(v), len(v), max(1, len(v) // 20)
        top = sum(sorted(v)[-k:])
        print(f"  {run:12s} n {n:3d} mean {tot / n:+.3f} median {sorted(v)[n // 2]:+.2f} | "
              f"top 5% of trades = {100 * top / tot if tot else 0:+.0f}% of the total")


def feed_health(days: int) -> None:
    if not HUB_LOG.exists():
        print("\n== feed hub\n  no feedhub log")
        return
    print("\n== feed hub")
    tail = HUB_LOG.read_text(encoding="utf-8", errors="ignore").splitlines()[-40000:]
    clock = sum(1 for line in tail if line.startswith("clock offset over 300 ms"))
    recon = sum(1 for line in tail if "reconnect" in line.lower() or "TimeoutError" in line)
    mb = next((line.split(HUB_KEY, 1)[1].split(" MB")[0].strip() for line in reversed(tail)
               if HUB_KEY in line), "?")
    print(f"  clock offset > 300 ms: {clock} warnings in the last {len(tail)} lines; reconnects/timeouts: {recon}")
    print(f"  hub data today: {mb} MB")
    if clock > 200:
        print("  WARN the host clock is chronically off by > 300 ms: the tape window (+2..4 s) and arrival_ms both "
              "depend on it")


def main(argv: list[str]) -> int:
    days = 7
    if "--days" in argv:
        i = argv.index("--days")
        days = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    only_history = "--history" in argv
    argv = [a for a in argv if not a.startswith("--")]
    runs = argv or DEFAULT
    oc = load_outcomes()
    oc_by_run = collections.defaultdict(list)
    keys = collections.defaultdict(set)
    for r in oc:
        oc_by_run[r["run"]].append(r)
        keys[r["run"]].add(f'{r["market"]}|{r["time_ist"]}')
    if only_history:
        print(f"Anomaly watch (history), {dt.datetime.now(IST):%d %b %Y %H:%M} IST")
        history(days)
        return 0
    print(f"Anomaly watch, {dt.datetime.now(IST):%d %b %Y %H:%M} IST, last {days} days")
    all_minutes = {run: minutes_of(run) for run in runs}
    union = sorted({t for ms in all_minutes.values() for t in ms})
    pc_gaps = shared_gaps(all_minutes, days)
    print("\n== PC coverage (union of every run's 1-min heartbeat)")
    if not pc_gaps:
        print("  no gap over 10 min")
    for a, b, m in pc_gaps:
        print(f"  WARN {a:%d-%b %H:%M} -> {b:%d-%b %H:%M} IST  {m / 60:5.1f} h  nothing running on this PC")
    print(f"  total silent {sum(m for *_, m in pc_gaps) / 60:.1f} h of the last {days * 24} h")
    seen = set()
    for run in runs:
        for w in report(run, days, oc_by_run, keys, union, pc_gaps):
            seen.add(w)
    feed_health(days)
    print("\n== summary")
    print("  findings: " + (", ".join(sorted(seen)) or "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
