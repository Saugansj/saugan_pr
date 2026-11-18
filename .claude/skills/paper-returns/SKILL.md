---
name: paper-returns
description: Day-wise and overall returns of the Polymarket paper runs (roster), led by the live estimate (what the run would have made trading live at real prices). Use when the user asks for day-wise returns, how much the paper runs made, the real making, the standings, or an overall analysis of the paper runs.
---

# Paper-run returns: day-wise and overall

The user wants the **live estimate** first (the "real making"), not paper P&L. Paper fills assume we win every
race for the cheapest ask; the live estimate re-prices each trade at real Polymarket tape prices, with our
order queued behind the real takers that beat us (`nightly/scorer.py` `tape_reprice`, RACE_AHEAD).
No real money is traded: say so if the user seems to think otherwise.

# 1. Get the numbers

```bash
cd roster && .venv/Scripts/python.exe ../.claude/skills/paper-returns/scripts/daywise.py
```

Add `--all` to include the retired runs (paper_v3, paper_eth, paper_ethc) in the printout. It refreshes every run in
`reports/research/real_outcomes.md` / `real_outcomes_trades.csv` (one small tape GET per new trade, ~1-3 min) — always
all runs, whatever is printed, because `ops/dashboard.py` reads the same file — and prints:
the day x run live-estimate matrix with day and run totals, the per-run balance / return / paper P&L / trades /
per-trade figure, and the pre-registered test progress (n of 200, verdict).

# 2. Present it

- A day x run table of the live estimate (USD), blank = no trades, with a day-total column and a run-total row.
- A balance table: start ($50 each; paper_ethc started at $80.86), live-estimate balance, return %, trades.
- 2-4 plain bullets: best and worst run, the trend of the last 2 days, BTC vs ETH, anything unusual.
- The pre-registered progress in one line per run when it changed (ethb has PASSED on the paper statistic;
  say that the live per-trade figure is far smaller).
- Paper P&L only as a side column or when asked.

# 3. Caveats to state (one or two lines)

- The live estimate is an estimate: RACE_AHEAD was fitted on BTC archive data at ~500 ms delay; trades with no
  real tape print in their window are left out (the "repriced / resolved" counts in real_outcomes.md).
- paper14's ladder-maker is maker-only and cannot be live-estimated: quote its paper figure separately.
- Live estimates from before 15 Oct used another method (mixed maker legs, median price): never compare them.
- A day is an IST day; today is partial until midnight, and trades count only once their market has settled.

# 4. Overall analysis (when asked for more than the numbers)

Also read, newest first: `reports/research/loop/<UTC day>.md` and `loop/eth/<UTC day>.md` (replay per rule,
missed money by skip reason), `reports/daily/<run>_<UTC day>.md` (pre-registered statistic, latency, trips),
and `reports/research/strategy_2026-10-14.md` / `anomaly_2026-10-15.md` for what was already concluded.
