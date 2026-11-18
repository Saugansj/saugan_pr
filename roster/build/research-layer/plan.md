# Research-layer fix plan (8 Oct 2026)

Why: the lessons in `reports/notes/2026-10-08_lessons.md`. Paper trading answers too slowly. Each test needs 200 trades, and btc-speed v2 has 3 after two days. Whether to hold or exit flips with the market regime. We record almost none of the feed, so skipped signals often can't be valued.

## The three gaps

| Gap | Now | Target |
|---|---|---|
| G1 data | per-minute marks and our own fills only | months of BTC ticks + Polymarket top of book for every BTC 5m/15m market, history and going forward |
| G2 replay | none; every question waits for paper fills | replay every btc-speed signal over the history under any rule set, in minutes |
| G3 regime | none | features at signal time that separate trending from reverting stretches; results split by them |
| G4 (ladder) queue | bids rarely fill (about 125 shares ahead) | a fill-probability model from queue position, before ladder changes |

## Open-source parts used, and why

| Part | Role here | Why this one |
|---|---|---|
| [binance/binance-public-data](https://github.com/binance/binance-public-data) (data.binance.vision) | BTC aggTrades history, checksum-verified | free, official, the same trades our live detector sees; `history/binance.py` already used it for klines |
| [pmxt archive v2](https://archive.pmxt.dev/docs/v2-data-overview) ([pmxt-dev/pmxt](https://github.com/pmxt-dev/pmxt)) | Polymarket CLOB WebSocket events, hourly Parquet, 2026-04-13 to about 2026-08-10 | free. Files are sorted by market, so a market filter fetches only its row groups (about 70 s per hour for the 5m/15m set). **Check its terms before sharing any derived data.** |
| [DuckDB](https://github.com/duckdb/duckdb) (installed) | remote Parquet reads with row-group pruning, de-duplication, as-of joins | already a dependency; no server |
| Gamma API | market catalog: cid, tokens, start, end, winner | one GET per slug |
| [skfolio](https://github.com/skfolio/skfolio) `CombinatorialPurgedCV` | choosing a rule without overfitting (R4) | added when R4 starts, not before |
| [nkaz001/hftbacktest](https://github.com/nkaz001/hftbacktest) | queue-position fill models for the ladder (G4) | the reference implementation of probabilistic queue models; we feed it our data |
| [evan-kolberg/prediction-market-backtesting](https://github.com/evan-kolberg/prediction-market-backtesting) on [NautilusTrader](https://github.com/nautechsystems/nautilus_trader) | **cross-check only**: replay a sample of our signals in its engine and compare fills | adopting a full engine to join two tables is more than the job needs. Our replay reuses the trader's own detector code, so research and live can't drift apart |
| [warproxxx/poly_data](https://github.com/warproxxx/poly_data) | on-chain fills, for G4 (who took liquidity at our price level) | GPL-3.0: run it as a separate tool, never import it |

Not used now: vectorbt or Optuna (a grid over about 30 rule sets is a loop), tardis.dev (paid; only if the pmxt archive has gaps), and timesfm or chronos (no price-direction models; rule 1).

## Work packages

**R1 data**
- R1a `history/binance.py --aggtrades`: daily BTCUSDT aggTrades, checksum-verified → `data/history/binance/BTCUSDT/aggTrades/`. AC: one Parquet per day; ts in ms; rerun skips existing days. **Done; 2026-04-13 → 08-10 downloading.**
- R1b `history/pm_fast.py`: Gamma catalog per day + pmxt top of book and trades per hour → `data/history/pm_fast/`. AC: 384 markets per day, all with a winner; per hour, top of book kept only when it changes; rerun resumes. **Done; 2026-07-27 → 08-09 downloading (about 30 min per day).**
- R1c forward recording: flag `record_tob` on the paper_v3 trader writes top-of-book changes of its subscribed tokens to `data/trader/<run>/tob/<UTC hour>.csv.gz`, plus Binance ticks. AC: no effect with the flag off; files rotate hourly; under 1 ms per tick added. The archive stops in August; this covers from now on.

**R2 replay** (`research/replay/replay.py`)
- Detector: `trader.engines.speed.MoveDetector` on Binance trades, the same code as live.
- Entry: decision + 150 ms + RTT (default 200 ms) + a feed lag (default 0). The ask is the last top of book at or before arrival. v2/v3 skip rules apply: already holding, ends too soon, cap, stale book.
- Exits: hold to the winner; or sell at the bid N s after arrival (N in 5, 8, 15, 30, 60), with taker fees on both legs.
- Output: one row per (signal, market, rule) → `data/research/replay/trades.parquet`, plus a summary report `reports/research/replay_<range>.md` with mean, cluster SE and n per rule.
- AC:
  1. Replaying the paper days reproduces the live signals within ±1 s (where we have both).
  2. Fee and outcome maths match the scorer.
  3. No look-ahead (asserted in a test).

**R2b system backtest** (`research/backtest/system.py`, built 9 Oct)
- The real `Trader` (kernel, router, breakers, ledger, audit, btc-speed v2/v3) on a sim clock.
- Fed by the Binance ticks and the archive's top of book, with one-level books of `--depth` shares.
- Settles from the catalog; the 08:15 IST breaker reset runs as live.
- Output: the nightly report over the range plus a per-day table → `reports/research/backtest_<name>.md`.
- Polymarket trades count as feed liveness, because the archive drops book events that don't move the top.
- Tests: 6 (question parsing; a synthetic day end to end for v2 hold and v3 exit).

**R3 regime features** (in the replay)
- At each signal, from data before it:
  - BTC return over the last 5, 15 and 60 minutes, signed by the signal's direction;
  - realised volatility over the last 30 minutes;
  - the number of signals in the last 30 minutes.
- Split results by tercile and report hold vs exit per bucket.
- AC: features use only data before the signal (test).

**R4 choose a rule**
- Use purged walk-forward with skfolio over the days.
- Pre-register the winner as btc-speed v4 before any paper run.
- AC: an out-of-sample result is reported next to the in-sample one.

**R5 ladder queue (G4)**
- Feed the pmxt archive's levels and trades for the daily markets into hftbacktest's queue models.
- Estimate the fill probability at our usual depth.
- Feeds a ladder pricing change; nothing is changed before then.

## Order and status

0. **9 Oct 15:30 IST:** R1b finished (336 of 336 hours). The first replay report is written: `reports/research/replay_2026-07-27_2026-08-09.md`; findings are in the lessons addendum. A report formatting bug was fixed. Next: R4. History from earlier: (paused 9 Oct 00:36 IST at the user's request: R1b has 58 of 336 hours (to 2026-07-29T09) and the queued replay is stopped. To resume, from `roster/` run `.venv\Scripts\python.exe -m history.pm_fast 2026-07-27 2026-08-09` (saved hours are skipped), then `.venv\Scripts\python.exe -m research.replay.replay 2026-07-27 2026-08-09`.
1. R1a: **done** (120 days, checksums logged). R1b: **paused**, see 0. (detached processes, logs in `data/history/logs/`). About 65 s per archive hour, so about 6 h for 14 days.
2. R2 + R3: **built** (`research/replay/`, 5 tests; a test caught one look-ahead in the volatility feature, now fixed).
   - Detector parity on 7 Oct: 9 of 10 live signals reproduced within 1 s.
   - The 14-day run is queued to start by itself when R1b finishes: report at `reports/research/replay_2026-07-27_2026-08-09.md`, log at `data/history/logs/replay.log`.
3. R1c: **built and running** on paper_v3 (`--enable record_tob`, restarted 23:42 IST) → `data/trader/paper_v3/tob/`.
4. Independent audit of R1–R3: **done** (8 Oct 23:50). 1 blocker, 3 majors and 9 minors; all fixed except where noted. 787 tests pass.
   - **Blocker:** events in the same millisecond had no defined order. 94% of top-of-book rows shared a timestamp, so the ask at arrival was arbitrary. Now the archive's file order decides and the last state per millisecond is kept. Hours already downloaded were deleted and are being re-extracted (top-of-book rows fell from 64k to 10k for 27 Jul 05:00).
   - **Majors fixed:**
     - Days missing archive hours are skipped.
     - The recorder writes one plain file per process, gzipped at rotation; a kill no longer corrupts the hour.
     - The lag grid now uses the ask seen at signal + lag.
   - **Minors fixed:**
     - The 2c limit is rounded as live.
     - SE is clustered by market.
     - The exit sale arrives 150 ms + RTT after it is sent.
     - The 30-minute signal count includes the previous day.
     - The catalog is saved only when complete, and one failed GET no longer aborts the day.
     - Logging alone no longer turns on `liquidity_once`, and a recorder error can't stop the feeds.
     - Line endings are LF.
     - aggTrades checksums are logged.
   - **Open:**
     - No stale-book rule in the replay; the archive keeps only top-of-book changes.
     - Binance ticks are not recorded live (the daily history covers them).
     - The detector runs on trade time T; live uses event time E, a few ms later.
   - **R2 AC1:** detector parity on 7 Oct, 9 of 10 live signals within 1 s.
5. R4, R5: after the 14-day replay report.
