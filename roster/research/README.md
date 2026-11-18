# Research layer: processes

How we test trading ideas on recorded history instead of waiting for paper trades. Each pre-registered test needs about 200 trades; btc-speed v2 had 3 after two days of paper trading. The research layer gets hundreds of trades from history in minutes, and paper trading then confirms the winner live.

Background: `reports/notes/2026-10-08_lessons.md` (why), `build/research-layer/plan.md` (work packages R1–R5 and status).

All commands run from the `roster/` folder with `.venv\Scripts\python.exe`. Paper only: nothing here can place an order.

## The pipeline at a glance

```
 1. DATA                          2. REPLAY (rules)               3. SYSTEM BACKTEST (our trader)
 Binance BTC ticks  ─┐            every btc-speed signal ×        the real Trader (kernel, router,
 (data.binance.vision)│           every rule (exit, cap, lag)     breakers, ledger, reports) on a
                      ├──────────► → per-trade table + report     sim clock → daily-style report
 Polymarket best      │            by regime                      per strategy version
 bid/ask + trades    ─┘
 (pmxt archive)                   4. CHOOSE A RULE (R4)           5. PAPER RUN
 Live recorder (v3 run) ─────────► walk-forward, pre-register  ──► side-by-side live check
```

| Step | Module | Output |
|---|---|---|
| 1a. BTC tick history | `history/binance.py --aggtrades` | `data/history/binance/BTCUSDT/aggTrades/BTCUSDT-aggTrades-<day>.parquet` |
| 1b. Polymarket history | `history/pm_fast.py` | `data/history/pm_fast/{catalog,tob,trades}/` |
| 1c. Live recorder | trader flag `record_tob` | `data/trader/<run>/tob/<UTC hour>.<pid>.csv(.gz)` |
| 2. Replay | `research/replay/replay.py` | `data/research/replay/trades_<range>.parquet`, `reports/research/replay_<range>.md` |
| 3. System backtest | `research/backtest/system.py` | `data/research/backtest/<name>/`, `reports/research/backtest_<name>.md` |
| Daily missed money | `research/missed/missed.py` | printed report |

## 1. Data

### 1a. BTC ticks (Binance)
```
.venv\Scripts\python.exe -m history.binance --aggtrades 2026-04-13 2026-08-10 --symbols BTCUSDT
```
- **Source:** free daily aggTrades files from [binance-public-data](https://github.com/binance/binance-public-data). Each file is checked against its published SHA-256 and logged to `data/history/binance/checksums.jsonl`.
- **Format:** `ts_ms` (trade time, ms), `price`, `qty`, `buyer_maker`. About 4 MB per day.
- **Reruns:** days already saved are skipped. Binance publishes a day the morning after.
- **Have:** 13 Apr – 10 Aug 2026, plus 6–7 Oct for live comparison.

### 1b. Polymarket BTC 5m/15m markets (pmxt archive)
```
.venv\Scripts\python.exe -m history.pm_fast 2026-07-27 2026-08-09
```
- **Catalog:** one Gamma lookup per market slug (`btc-updown-5m-<start>`, `btc-updown-15m-<start>`) gives 384 markets a day: cid, Up/Down tokens, start, end, winner. A day is cached only when complete and resolved.
- **Best prices and trades:** per UTC hour, read from the free [pmxt archive](https://archive.pmxt.dev/docs/v2-data-overview), hourly Parquet files of the Polymarket market WebSocket. Files are sorted by market, so DuckDB fetches only our markets' parts, about 60 s per hour.
  - `tob/<day>T<HH>.parquet`: `ts_ms, asset_id, best_bid, best_ask`, written only when the best prices change. Updates within the same millisecond keep the archive's file order.
  - `trades/<day>T<HH>.parquet`: `ts_ms, asset_id, price, size, side`.
- **Coverage:** the archive runs 13 Apr to about 10 Aug 2026 (later files return 404). We have 27 Jul – 9 Aug.
- **Reruns:** saved hours are skipped, so a stopped download resumes. Progress: `data/history/logs/pm_fast.log`.
- **Cost:** about 25 minutes per day and heavy network use. **Run downloads outside trading hours**: on 9 Oct a daytime download delayed BTC prices to the live runs by up to 6.3 s.
- **Terms:** check the archive's terms of use before sharing anything derived from it.

### 1c. Live recorder (from 8 Oct 23:42 IST)
- The v3 paper run (`ops\start_paper_v3.bat`) runs with `--enable record_tob`. Every change in best bid or ask on its subscribed BTC 5m/15m tokens is appended to `data/trader/paper_v3/tob/<UTC hour>.<pid>.csv`, in the same columns as 1b.
- The file is plain text while the hour is open, so a crash loses at most a few KB. It is gzipped at the hour's end. One file per process.
- **Why:** the archive stops in August; this covers October onward, from our own connection and clock.

## 2. Replay: what would a rule earn?
```
.venv\Scripts\python.exe -m research.replay.replay 2026-07-27 2026-08-09 [--rtt 200]
```
- **Signals:** runs the live detector (`trader.engines.speed.MoveDetector`: 10 bp in 5 s, 60 s cooldown) on the BTC ticks.
- **Markets:** for each signal, every open BTC 5m/15m market (the move must start inside the window, and the market must have more than 60 s left).
- **Rule grid:**

| Setting | Values |
|---|---|
| cap (max entry price) | 0.75, 0.90 |
| lag (signal seen late) | 0, 1, 2, 5 s |
| exit | hold to settlement, or sell N s after the fill (N = 5, 8, 15, 30, 60) |

- **Entry:** buy 5 shares at the ask in force at arrival (signal + lag + 150 ms + RTT). The ask may be at most 2¢ above the ask seen at the signal (v2's limit, rounded as live). No second buy while that market is held.
- **Exit:** the sale arrives 150 ms + RTT after it is sent, at the bid then, with taker fees on both legs. An exit due within 15 s of the end holds instead.
- **Regime features**, using only data before the signal:
  - BTC return over 5 / 15 / 60 min, signed with the signal;
  - 30-min realised volatility;
  - number of signals in the last 30 min.
- **Report:** mean, cluster-robust SE (by market) and total per rule, a hold-vs-exit table by regime tercile, and a per-day table.
- **Limits:**
  - Best prices only: 5 shares are assumed available at the ask, and no other bot takes them first.
  - There is no stale-book rule.
  - The archive's clock runs about 135 ms (p50) to 320 ms (p99) behind exchange time.
  - Read results as an upper bound.
- **First result (27 Jul – 9 Aug, 10 usable days):**
  - About +$0.50 per trade at full speed.
  - The edge is gone within about 1 s.
  - It sits in calm markets and isolated signals.
  - Details are in the lessons addendum.

## 3. System backtest: what would our system have done?
```
.venv\Scripts\python.exe -m research.backtest.system 2026-07-27 2026-08-09 --name v2 --enable speed_only
.venv\Scripts\python.exe -m research.backtest.system 2026-07-27 2026-08-09 --name v3 --enable speed_only --enable speed_v3
```
- **What runs:** the real `trader.loop.Trader` (risk kernel, router and paper-fill simulator, breakers, ledger, audit chain, btc-speed engine) on a sim clock. Only the feeds are replaced.
- **Inputs:**
  - BTC ticks arrive `--lag-ms` (default 60) after trade time. Other options: `--rtt`, `--depth`, `--cash`, `--global-cap` (research only).
  - Each best-price change becomes a one-level book of `--depth` (default 100) shares per side.
  - Polymarket trades count as feed liveness.
  - Markets are listed 15 min before their window, and positions settle from the catalog.
- **Housekeeping as live:** the 100 ms tick, the per-minute advice reload, and the 08:15 IST reset of breaker pauses (never a halt). It runs 24 h a day, with no PC sleep.
- **Report:** the normal daily report over the whole range (P&L per strategy, decisions, fills, markouts, trips, invariants, latency, pre-registered statistics), plus a per-day P&L table.
- **Speed:** about 40 s per day.
- **What it finds that the replay can't:**
  - effects of the system's own rules: daily-loss pauses, account caps, stale-feed pauses, unfilled orders;
  - whether the code path behaves (violations, reconcile).
- **First full runs** (27 Jul – 9 Aug, $50, system defaults), both with 0 violations and a clean shutdown:

| Version | Fills | P&L | Stopped trading after |
|---|---|---|---|
| v2 (hold) | 28 | **+$5.70** | 31 Jul |
| v3 (sell after 8 s) | 51 | **+$6.24** | 30 Jul |

  Both stopped because the account grew past **1.1× the $50 global cap**. The kernel then refuses every buy ("bankroll 55.70 > 1.1 x global cap 50.00") until a person raises the cap, so most of the period was not traded. Use `--global-cap` to study the strategy past that point (research only).

  The same runs with `--global-cap 1000`, all 12 usable days:

| Version | Fills | P&L | Losing days | Worst day |
|---|---|---|---|---|
| v2 (hold, cap 0.90) | 73 | **+$37.38** | 2 of 9 trading days | −$5.35 |
| v3 (sell after 8 s, cap 0.75) | 146 (73 round trips) | **+$34.18** | 1 of 9 | −$0.09 |

  The total is about the same; v3 is much steadier. Both are upper bounds: depth is assumed, there's no competition for the ask, and latency is modelled.
- **System behaviours found:**
  - one feed outage pauses trading until the next 08:15 reset;
  - profit above 10% stops all buying until the cap is raised by hand.
- **Limits:** btc-speed only (no daily-market history for ladder-maker yet), and the same depth and latency caveats as the replay.

## 4. Choosing the next version (R4)
1. Calibrate:
   - measure live latency (signal to order arrival) from the paper runs;
   - replay October days from the live recorder and compare signal by signal with what the paper runs did.
2. Test a few candidate rules (speed cut-off, calm-market filter, hold-when-trend-agrees exit, cap) with leave-one-day-out / purged walk-forward ([skfolio](https://github.com/skfolio/skfolio)). Keep the rule to 2–3 filters, and report out-of-sample next to in-sample.
3. Pre-register the winner (e.g. `btc-speed-v4`) with its pass and futility rules before any paper trade.
4. Run it as a side paper run next to v2 and v3, and compare daily.

## 5. Daily missed-money check
```
.venv\Scripts\python.exe research\missed\missed.py paper14 --day 2026-10-09
.venv\Scripts\python.exe research\missed\missed.py paper_v3 --day 2026-10-09
```
- Lists, per run and IST day:
  - btc-speed fills (actual vs hold vs exit at 5 s / 60 s);
  - signals not traded, by reason, with how many would have won;
  - ladder-maker fills;
  - model edge at checkpoints;
  - two-sided arbitrage.

## Tests
```
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider research/replay research/backtest tests/invariants
```
- **Replay (6 tests):**
  - no look-ahead in the features;
  - hold and exit maths, the cap and 2¢ limit;
  - the lag semantics;
  - the same-market rule;
  - the live detector.
- **System backtest (6 tests):**
  - question parsing;
  - a synthetic day end to end (v3 sells about 8 s after the fill at the new bid; v2 holds and settles from the catalog).
- **Recorder:** `test_record_tob_logs_top_of_book_changes_only` (change-only rows, hourly rotation, gzip, LF line endings).

## Rules for running these
- Never run downloads or backtests against `data/trader/paper14` or `paper_v3`. They only read history and write under `data/history` and `data/research`.
- Heavy downloads go at night. Backtests use one CPU core each and are fine during the day.
- Results are an upper bound until R4's calibration says how far live falls short.
