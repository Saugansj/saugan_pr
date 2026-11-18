# Day-wise and overall returns of the paper runs, for the paper-returns skill.
# Refreshes ops/real_outcomes.py (it re-prices every resolved trade at real Polymarket tape prices), then prints:
#   1. live estimate per run per IST day, with day totals and run totals  (the "real making")
#   2. per run: start, live-estimate balance and return, paper P&L, trades, per-trade live estimate
#   3. pre-registered test progress (resolved trades of 200, verdict)
# Read-only on the runs; the tape fetch is a public read-only GET.
#
#   roster\.venv\Scripts\python.exe .claude\skills\paper-returns\scripts\daywise.py [--all]   (--all: retired runs too)
import contextlib
import io
import pathlib
import sys

import pandas as pd

ROSTER = pathlib.Path(__file__).resolve().parents[4] / "roster"
sys.path.insert(0, str(ROSTER))
from nightly import scorer  # noqa: E402
from ops import real_outcomes  # noqa: E402
from ops.status import RUNS  # noqa: E402   start balance per run ($50, ethc $80.86)

ACTIVE = ["paper_ethb", "paper_eth6b", "paper_v4b", "paper_v6b", "paper_v5b", "paper14"]
names = list(RUNS) if "--all" in sys.argv else ACTIVE

# 1. Refresh the per-trade file; its own long printout is not needed here. Always every run: ops/dashboard.py
#    reads this same file, so a subset refresh would blank the other runs' columns there until its next pass.
with contextlib.redirect_stdout(io.StringIO()):
    real_outcomes.main([])
d = pd.read_csv(ROSTER / "reports" / "research" / "real_outcomes_trades.csv")

# Day x run matrix of the live estimate (USD); a blank cell = no resolved trade that day.
m = d.pivot_table(index="day_ist", columns="run", values="live_est_pnl", aggfunc="sum").reindex(columns=[n for n in names if n in set(d.run)])
m["DAY TOTAL"] = m.sum(axis=1)
m.loc["TOTAL"] = m.sum()
print("== Live estimate (real-price P&L, USD) per IST day\n")
print(m.round(2).to_string(na_rep=""))

# 2. Per-run summary. ladder-maker (paper14) is maker-only and cannot be live-estimated: shown as paper only.
print("\n== Per run\n")
rows = []
for n in names:
    x = d[d.run == n]
    if x.empty:
        continue
    live, start = x.live_est_pnl.sum(), RUNS.get(n, 50.0)
    rows.append({"run": n, "start": start, "live_balance": start + live, "live_return_%": 100 * live / start,
                 "paper_pnl": x.paper_pnl.sum(), "live_pnl": live, "trades": len(x),
                 "live_per_trade": live / len(x)})
print(pd.DataFrame(rows).set_index("run").round(2).to_string())

# 3. Pre-registered tests: n resolved since the version's pre-registration, of 200; PASS needs mean > 2 cluster SE.
print("\n== Pre-registered tests (paper statistic)\n")
for n in names:
    path = ROSTER / "data" / "trader" / n
    if not (path / "trader.db").exists():
        continue
    sp = scorer.score(path, fetch=None)["speed"]
    print(f"{n:12s} {sp['prereg']['test_id']:26s} {sp['n']:4d} of {sp['prereg']['n']} | mean {sp['mean'] or 0:+.3f} "
          f"se {sp['se'] or 0:.3f} | {sp['verdict']}")
