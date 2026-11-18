"""Daily paper-trading report with catch-up: writes reports/daily/paper14_<UTC date>.md for today and every earlier day
since the run started that has no report yet. Safe to run any number of times (scheduled at 21:50 IST and at logon).
The trading day (08:00-21:45 IST) sits inside one UTC day, so the 21:50 run covers the day including the 21:30 settlement.

  .venv\\Scripts\\python.exe ops\\daily_report.py            # today (refreshed) + any missing earlier days
  .venv\\Scripts\\python.exe ops\\daily_report.py paper_v3  # the same for another run folder under data/trader
"""
import datetime as dt
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nightly import report  # noqa: E402

NAME = sys.argv[1] if len(sys.argv) > 1 else "paper14"
RUN = ROOT / "data" / "trader" / NAME
OUT = ROOT / "reports" / "daily"


def gate_progress(upto: dt.date, start: dt.date) -> str:
    """The plan's Phase 1 gate: 14 consecutive days with zero invariant violations and 5+ restarts whose startup
    reconcile was clean. Running time comes from rtt.jsonl, which the trader appends once per running minute."""
    import json
    import sqlite3
    end_ms = int(dt.datetime.combine(upto + dt.timedelta(days=1), dt.time(), dt.UTC).timestamp() * 1000)
    con = sqlite3.connect(f"{(RUN / 'trader.db').resolve().as_uri()}?mode=ro", uri=True)
    try:
        q = lambda t: [(json.loads(b), ev) for b, ev in con.execute(
            "SELECT body, event_ms FROM rows WHERE tbl = ? AND event_ms < ? ORDER BY id", (t, end_ms))]
        viol_days = {dt.datetime.fromtimestamp(ev / 1000, dt.UTC).date() for _, ev in q("invariant_violations")}
        boots = [r for r, _ in q("reconciles") if r.get("phase") == "startup"]
    finally:
        con.close()
    streak_from = max((d + dt.timedelta(days=1) for d in viol_days), default=start)
    streak = max(0, (upto - streak_from).days + 1)
    restarts = boots[1:]  # the first startup is the run's start, not a restart
    clean = sum(1 for r in restarts if not r.get("mismatches"))
    mins, per_day = 0, {}
    for line in (RUN / "rtt.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            d = dt.datetime.fromtimestamp(json.loads(line)["t"] / 1000, dt.UTC).date()
        except (ValueError, KeyError):
            continue
        if d <= upto:
            mins += 1
            per_day[d] = per_day.get(d, 0) + 1
    days = mins / 1440
    rows = "\n".join(f"| {d} | {n / 60:.1f} |" for d, n in sorted(per_day.items()))
    ok = streak >= 14 and clean >= 5 and clean == len(restarts)
    return (f"\n## Phase 1 gate progress\n\nGate (build plan v4): 14 consecutive days with zero invariant violations and "
            f"5+ restarts with a clean reconcile. **{'MET' if ok else 'not met yet'}.**\n\n"
            f"- Days without a violation: **{streak} of 14** (days with violations: {len(viol_days)})\n"
            f"- Restarts with a clean startup reconcile: **{clean} of {len(restarts)}** (need 5+, all clean)\n"
            f"- Running time: {mins / 60:.1f} hours ({days:.2f} days of 24 h)\n\n"
            f"| UTC day | Hours running |\n|---|---|\n{rows}\n")


def main() -> int:
    if not (RUN / "trader.db").exists():
        print("no paper run yet at", RUN)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    import json  # the run's first logged minute (keys.jsonl is rewritten at every start, so it can't date the run)
    with (RUN / "rtt.jsonl").open(encoding="utf-8") as f:
        start = dt.datetime.fromtimestamp(json.loads(f.readline())["t"] / 1000, dt.UTC).date()
    today = dt.datetime.now(dt.UTC).date()
    day, rc = start, 0
    while day <= today:
        out = OUT / f"{NAME}_{day}.md"
        if day == today or not out.exists():  # today is refreshed each run; past days are written once
            rc |= report.main(["--dir", str(RUN), "--date", str(day), "--out", str(out),
                               "--title", f"{NAME} day {(day - start).days + 1}: {day} (UTC)"])
            out.write_text(out.read_text(encoding="utf-8") + gate_progress(day, start), encoding="utf-8")
            print("wrote", out)
        day += dt.timedelta(days=1)
    return rc


if __name__ == "__main__":
    sys.exit(main())
