# Where btc-speed leaves money on the table, and a v4 candidate (9 Oct 2026)

Data: Binance BTCUSDT ticks + Polymarket top of book for every BTC 5m/15m market, 27 Jul – 9 Aug (13 usable days; 5 Aug skipped, incomplete), Deribit DVOL hourly, and the live ledgers of paper14 and paper_v3. Every number is paper, 5 shares per trade, taker fees on every leg, SE clustered by market. Replays are an **upper bound**: top of book only, no queueing behind other bots, and the archive's own clock.

Method: a wide replay of every signal × every open market × 7 delays × 9 detector settings, with no skip rule applied. Skipped trades were then valued counterfactually. It reproduces the existing replay (5s/10bp, cap 0.75, exit 8 s: +0.503 per trade over 93 trades, against +0.503 over 92).

## 1. Ranked leaks

| # | Leak | Evidence | Size |
|---|---|---|---|
| 1 | **Detector too slow and too strict** | 10 bp in 5 s fires after the move is mostly priced in. 6 bp in 2 s fires earlier and more often | v3 rule: 5.7 trades/day, +$0.43 per trade (lag 200). 2s/6bp: 15.7/day, +$0.69 held. **About 3x the daily P&L** |
| 2 | **2c slippage limit throws away the best trades** | When the ask jumps more than 2c between signal and arrival, the move is real and we refuse it | 38 refused trades over 13 days would have made +$32.5 held (+$0.86 each) |
| 3 | **Account lockout after winning** | The kernel refuses all new risk once equity > 1.1 x the $50 cap ($55) | System backtest: v2 +$5.70 capped vs +$37.38 uncapped; v4 candidate +$5.35 capped vs +$132.82 uncapped (301 trades refused) |
| 4 | **Speed: every 100 ms costs about 6c a trade** | Exit 8 s per trade by extra delay: 0 ms +0.50, 200 ms +0.43, 300 ms +0.35, 500 ms +0.16, 1000 ms +0.05 | Live arrival is about 350 ms (paper14) to 500 ms (paper_v3) after the Binance trade, before clock error |
| 5 | ~~paper_v3 slower than paper14~~ **(not confirmed)** | The per-event medians were mostly 8 Oct, before the event-loop fix. Over 667 minutes on 9 Oct, v3's median delay was 17 ms *lower*, and in the 437 busiest minutes v3's worst delay was lower too (median −97 ms) | Both runs have occasional 4–7 s stalls in the same minutes: the PC or network, not the recorder |
| 6 | **PC clock out of step with Binance** | Receive lags as low as −690 ms. The 1 s stale-signal guard runs on that clock | Most live market decisions were "stale signal": v3 30 of 56, paper14 22 of 87, mostly 8 Oct 20:50–22:55 (before the event-loop fix) |
| 7 | **One feed gap pauses trading until next morning** | The stale-feed breaker goes REDUCING; only the 08:15 IST reset lifts it | 20 trips in each 14-day backtest; 28 Jul lost most of the day |
| 8 | 15m markets earn much less than 5m | Hold per trade: 5m +0.96, 15m +0.16 | A filter candidate, not yet in v4 |
| 9 | Calm markets earn more | Out of sample, "no signal in the last 30 min": +$1.10 to +$1.32 per trade, but half the trades. DVOL low tercile +0.80 vs high +0.25 (exit 8 s) | Raises per-trade P&L, lowers the daily total for v4 |

**Not leaks:**
- Asks above 0.85: negative (−0.13 held).
- 0.75–0.85: small (+0.15 exit 8 s).
- "Ends in < 60 s": positive but only 11 trades.
- "Hold if the 15-min trend agrees, else exit": **worse** than either rule alone (+0.45 vs +0.52 / +0.50). Drop it from the plan.
- The market had not repriced before our signal: median ask change in the second before it was 0c, so we are not systematically last.

## 2. v4 candidate, chosen honestly

**Grid:** 720 rules = 5 detectors × 3 caps (0.65/0.75/0.85) × 3 slippage limits (2/5/10c) × 4 filters (none, quiet 30 min, DVOL ≤ 37, 5m only) × 4 exits (5 s, 8 s, 30 s, hold). One position per market.

**Leave-one-day-out:** choose the best rule on 12 days, score it on the 13th, for every day. **The same rule won all 13 folds:**

> **btc-speed v4 = v2's engine (buy the favoured side, hold to resolution) with window 2 s, 6 bp, cap 0.85, slippage limit 10c.**

It needs parameter changes only, no new logic.

| | delay 200 ms (optimistic) | delay 500 ms (realistic) |
|---|---|---|
| Out-of-sample total, 13 days | **+$204.6** | **+$103.7** |
| Per trade | +$0.72 ± 0.12 | +$0.43 ± 0.14 |
| Trades per day | 21.8 | 18.5 |
| Losing days | 1 of 13 | 3 of 13 |
| v3 rule, same days | +$32.0 | +$10.8 |
| v2-like rule (cap .75, hold) | +$34.8 | +$7.6 |

**Full system backtest** (real kernel, breakers, ledger; arrival about 400 ms after the trade; group cap $10; $5 strategy daily-loss breaker):

| Run | Trades | P&L | Per trade | 5 s markout | Losing days |
|---|---|---|---|---|---|
| v4 candidate, global cap raised to $1000 | 171 | **+$132.82** | +$0.78 ± 0.17 | +15.1c | 3 of 13 |
| v4 candidate, $50 cap | 13 | +$5.35 | locked out after 29 Jul | | |
| v2, cap raised | 73 | +$37.38 | +$0.51 ± 0.24 | +10.8c | |
| v3, cap raised | 73 round trips | +$34.18 | +$0.47 | +6.0c | |

0 invariant violations, clean shutdown.

**Same system backtest with 400 ms more delay** (`backtest_v4cand_nocap_slow.md`): 112 trades, **+$32.58**, +$0.29 ± 0.21 per trade, 5 s markout +7.3c, 7 losing days of 13. **v4's advantage depends heavily on speed.** At realistic live speed expect something between the two runs, not +$132.

**Grid caveat:** the grid accepted fills up to cap + slippage (0.95), while live caps the limit at the cap (0.85). The system backtests use the live rule, so they are the numbers to trust. The nightly loop (`research/loop/nightly.py`) uses the live rule.

**Risks:**
- 13 days from one summer regime.
- 5 shares assumed available at the ask.
- Holding gives volatile daily P&L, so the $5 daily-loss breaker will trip on some days.
- The 10c slippage limit means paying up, which only works while we are early.

Paper-test it before believing it.

## 3. What to do, in order

1. **Fix the lockout** (leak 3). `capital_ladder` doesn't do this: it raises the cap only after a passed test plus a human signature. **Done for paper:** `trader.loop --global-cap`, used by paper_v4 only. Live, a person sweeps the profit.
2. **Done, 9 Oct 21:04 IST:** btc-speed v4 is running as the third paper run, `paper_v4` (flag `speed_v4`, pre-registration `btc-speed-v4`, `ops/start_paper_v4.bat`, included in the 08:15 reset and the 21:50 report). At about 10–20 trades a day it reaches the 200-trade test in 10–20 days, not 86.
3. **Sync the PC clock** (leak 6) and look for the cause of the 4–7 s stalls that hit every run at once. The clock sync is a Windows setting: run `w32tm /resync` as admin, or use a better NTP source. Then re-check the stale guard.
4. **Auto-resume after a feed gap** (leak 7). **Built:** `ops/feed_resume.py` (`paper_tasks.ps1 resume`) lifts a pause whose every cause since the last reset was a stale feed at least 5 minutes ago. Loss, drawdown and mixed pauses still wait for 08:15. It needs a 10-minute scheduled task, which the user creates.
5. Later candidates for v5 (one change at a time): 5m-only, the quiet filter, DVOL.

The nightly loop that repeats this analysis every day is `research/loop/nightly.py`; its reports go in `reports/research/loop/`.
