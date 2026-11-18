"""Paper-run standings: per run and strategy, P&L since start and per IST day (nightly.report.pnl at each day end).

  .venv\\Scripts\\python.exe ops\\status.py [run ...]
"""
import datetime as dt
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nightly import report, scorer  # noqa: E402

RUNS = {"paper14": 50.0, "paper_v3": 50.0, "paper_v4b": 50.0, "paper_v5b": 50.0, "paper_ethb": 50.0,
        "paper_ethc": 80.86, "paper_v6b": 50.0, "paper_eth6b": 50.0, "paper_eth": 50.0, "paper_v4": 50.0,
        "paper_v5": 50.0, "paper_mk": 50.0, "paper_ethmk": 50.0,
        "paper_v7b": 50.0, "paper_eth7b": 50.0, "paper_eth7c": 50.0, "paper_v8b": 50.0, "paper_v4add": 50.0,
        "paper_v4sz50": 50.0, "paper_v4sz100": 100.0, "paper_v9fix": 50.0}
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def day_end_ms(d: dt.date) -> int:
    return int(dt.datetime.combine(d + dt.timedelta(days=1), dt.time(), IST).timestamp() * 1000)


def standings(name: str, start: float) -> None:
    d = ROOT / "data" / "trader" / name
    fills = scorer.tables(d).get("fills", [])
    if not fills:
        print(f"{name}: no fills")
        return
    first = dt.datetime.fromtimestamp(min(f["ts_ms"] for f in fills) / 1000, IST).date()
    today, prev, rows = dt.datetime.now(IST).date(), {}, []
    for i in range((today - first).days + 1):
        day = first + dt.timedelta(days=i)
        cum = {s: o["pnl"] for s, o in report.pnl(scorer.tables(d, 0, day_end_ms(day))).items()}
        rows.append((day, {s: cum[s] - prev.get(s, 0.0) for s in cum}))
        prev = cum
    tot = sum(prev.values())
    print(f"\n{name}: start ${start:.2f} -> ${start + tot:.2f} ({tot:+.2f}, {100 * tot / start:+.1f}%)  "
          + "  ".join(f"{s} {v:+.2f}" for s, v in sorted(prev.items())))
    for day, by in rows:
        print(f"  {day:%d %b}  {sum(by.values()):+7.2f}" + ("  (" + ", ".join(f"{s} {v:+.2f}" for s, v in sorted(by.items())) + ")"
                                                          if len(by) > 1 else ""))


if __name__ == "__main__":
    for n in sys.argv[1:] or RUNS:
        standings(n, RUNS.get(n, 50.0))
