# Wiring smoke (WW-D): Phases 2-5 connected to the paper trader behind feature flags

Paper only, live public feeds, this PC, 2026-10-07. Data in `data/trader/wiring_off/`, `data/trader/wiring_on/`,
`data/trader/wiring_drills/` and `data/trader/wiring_D/`. The 14-day run in `data/trader/paper14/` was not touched (D5).

## Verdict per acceptance criterion

| AC | Result | Evidence |
|---|---|---|
| D1 flags off = Phase 1 | met | `test_d1_flags_off_identical_to_phase1_loop`: on a 7.5-minute scripted session (ladder quotes and maker fills, two btc-speed events, merges), the new loop writes exactly the same ledger rows, journal and counts as the audited loop frozen before WW-D (`data/trader/wiring_D/loop_phase1_before.py`). Live 20-minute run `wiring_off`: 748 ladder intents, 748 approved, 0 "over group" rejections (what the audited `fit_to_caps` fix produces), 0 violations, 0 mismatches, 0 trips, exit 0. |
| D2 paper-safe flags on | met | `wiring_on` run `1791366707170-11888`: 20 minutes, exit 0, clean shutdown, 0 invariant violations, 0 reconcile mismatches, 0 trips. What each flag did is below. |
| D3 crash drills, flags on | met | `nightly.drills` in `data/trader/wiring_drills/` (all 10 paper-safe flags; every child printed the `FEATURES` line): **PASS**, 5 forced restarts (2 kill -9 at random, 2 kill -9 mid-batch, 1 clean stop), each next startup reconciled with 0 mismatches, 0 violations. Report: `data/trader/wiring_drills/drills.md`. |
| D4 full suite | met | `trader/tests tests/invariants tests/phase2-5 tests/wiring`: 725 passed (14 new WW-D tests). Two Phase 3 tests depend on live data and fail while the newest market snapshot is an extended crawl (open issue 6). |
| D5 paper14 untouched | met | See the last section. |

## Flags off vs flags on (live, 20 minutes each)

The two runs were not at the same time (off 08:59-09:19 UTC, on 09:51-10:11 UTC), so market-driven numbers differ.

| | flags off (`wiring_off`) | all paper-safe flags (`wiring_on`) |
|---|---|---|
| markets loaded | 190 | 614 (touch templates, SOL/XRP ladders) |
| ladder-maker intents / approved / orders | 748 / 748 / 748 | 781 / 593 / 593 |
| ladder-maker rejections | none | 188 `stress` (live_risk) |
| resting quotes pulled on re-check | 0 | 26 (`stress`) |
| btc-speed events / intents / approved | 0 / 0 / 0 | 1 / 2 / 0 (both `stress`) |
| fills | 0 | 0 |
| invariant violations / mismatches / trips | 0 / 0 / 0 | 0 / 0 / 0 |
| decision latency p99 (median of minutes, max) | 6 ms, 12 ms | 22 ms, 37 ms |
| event-loop lag p99 (median of minutes, max) | 17 ms, 102 ms | 21 ms, 195 ms |

## What each flag did in `wiring_on`

- **live_risk**: the Phase 2 stress cap (worst loss at most 5% of bankroll under +-5/10% shocks with vol x1.5) rejected 24% of
  ladder intents and both btc-speed takers. On a $50 bankroll the cap is $2.50: a 10-share ladder bid above about 0.25,
  or a 5-share btc-speed taker at 0.90, cannot pass. 26 resting quotes were cancelled when a re-check failed the cap.
  Pull-on-REDUCING found nothing to pull (no scope entered REDUCING). Up/Down opens are fed to the stress cap each minute.
- **dd7**: 7-day drawdown samples persisted to `wiring_on/dd7_samples.json`; no trip (equity flat, no fills).
- **heartbeat**: 10,763 paper heartbeats "sent" (a counted no-op) out of about 11,500 ticks (93.6%). Withheld on 533
  ticks because a resting order's book had no update for over 30 s (the health check's `book` rule; quiet books, not
  outages), 195 for a stale feed, 2 for no clock reading yet. No HALTED episode. No dead-man URL is set, so no pings.
- **settlement**: the keeper stepped once a minute (public GETs only); 16 ended markets sat in the oracle gap and are
  pulled by the ladder and counted by the stress cap. No held position, so no outcome reads, no fund intents, no pages.
  The SNTP worker (started by `heartbeat`) read this PC's clock 175-380 ms off over 20 readings.
- **capital_ladder**: global cap read from `growth.capital.current_cap(ledger)` = $50 on this fresh ledger (unchanged); no 1.1x refusals.
- **touch**: touch markets loaded, cleared and subscribed, 20 book-integrity data-fault records came from touch books,
  but **no touch market was ever priced or quoted**: the integration defect below. Fails closed.
- **universe_ext**: SOL/XRP ladders loaded, subscribed and cleared (Binance SOLUSDT/XRPUSDT and realized sigma_Q in
  marketdata). Not quoted, by design: the ladder trades its `assets` (BTC, ETH) and every universe entry is a
  `candidate` (Phase 3: quote only once an entry's `universe-<id>` version is live).
- **quote_objective**: the ladder quotes through `wider(optimise(...), quotes(...))`. No crypto-term market had a
  positive reward pool (`reward_daily_rate` 0), so no reward term was used. Intent and order rates stayed close to flags-off.
- **negrisk_scan**: 96 negRisk events built from the crawler snapshot and scanned each minute (1,824 scans), but **0 rows
  recorded**: no leg book is subscribed (see open issues). Never an intent.
- **markout_cusum**: active in place of the count blacklist; no fills, so no series to update.
- Registry and pre-registrations written at start: `touch`, `universe-vol`, four `universe-*` entries, `negrisk-arb`,
  `quote-objective`, `markout-cusum` (all `candidate`), plus pre-registrations `touch-v1`, four `universe-*-v1` and
  `negrisk-arb-v1`. A restart re-writes them without an immutability error (test).

Wired and unit-tested, not part of D2: `clock_gate` (at 175-380 ms offset it holds global REDUCING, test),
`sports` (ESPN game states and Kalshi every 5 min, md.set_sports, sports-maker engine, cancel signals on update and each
minute; keyed SGO odds are not fetched, so the engine always pulls: fail closed) and `fast_maker` (no intents while its
latency gate is closed).

## Defects and open issues found while wiring

1. **Touch markets are never priced (WW-B and WW-C disagree; fix in `trader/engines/ladder.py`, WW-C).** marketdata
   keeps each window's running high/low in `ref[asset]["touch"][cid]` and documents `touch_ref(ref, m)` as the input;
   `LadderEngine.on_tick` passes `ref[asset]` to `touch_value`, which reads `r["high"]`/`r["low"]` and returns `err`.
   One-line fix: `r = touch_ref(ref, m)` for touch kinds. Offline proof: `touch_value(m, ref["BTC"], ...)` gives
   "non-finite touch input", `touch_value(m, touch_ref(ref, m), ...)` prices. The loop cannot build a per-cid view
   without editing the engine. Until fixed, `touch` fails closed.
2. **negRisk legs have no books.** marketdata subscribes only the tokens of its target modes, so the scanner sees no
   leg book and records nothing. Subscribing the legs (WW-B) is needed before `negrisk_scan` gathers evidence.
3. **live_risk blocks most risk at a $50 bankroll.** Engines do not size to the stress room: a ladder bid of 10 shares or
   a btc-speed taker of 5 shares is often over the $2.50 cap. Expected behaviour of the cap; engines that size to it
   (or a larger bankroll) are needed before live_risk-on evidence accumulates.
4. **Slow exit with touch/universe_ext.** The on-run took 2 min 37 s from SHUTDOWN to exit: `asyncio.run` waited for an
   in-flight market crawl thread. While paper14 (flags off) also crawls, the snapshot alternates between flags-off and
   extended rows, so the extended run re-crawls at nearly every 5-minute reload (WW-B's `_ext_missing` ponytail note).
5. **Heartbeat `book` rule on quiet books.** 4.6% of ticks would have withheld the venue heartbeat because a resting
   order's book had no update for 30 s, which the venue would answer by cancelling everything. It is
   `health_failures`' rule as audited (Phase 2). It needs a look before a live heartbeat: an order book with no
   activity is not a stale feed.
6. **Two Phase 3 tests depend on the live snapshot being a flags-off crawl.** `tests/phase3/test_universe.py::
   test_snapshot_slugs_match_crawler_mode` and `::test_btc_eth_rows_match_marketdata` read `data/markets`' latest file.
   Right after the flags-on smoke, that file was an extended crawl (touch, SOL/XRP rows) and both failed (723 passed,
   2 failed). One flags-off `recorder.crawler.crawl(MODES)` (public GETs, what the recorder and the trader do every
   hour) restored a flags-off latest snapshot and the full suite passed again (725). Any flags-on run with
   touch/universe_ext can flip them until the next flags-off crawl. They should skip, or filter to flags-off slugs.
7. `wiring_on/` also holds two earlier 20-minute runs (`1791363334253-10668`, `1791364817372-12856`) that started
   without `ROSTER_HUMAN_KEY` in their environment (a shell grouping mistake), so no clearance verified and every intent
   was "not cleared". They crashed nothing (0 violations, 0 mismatches) but are not D2 evidence; all D2 numbers above
   are scoped to run `1791366707170-11888`. They could not be deleted from this session.

## D5: paper14 untouched, no foreign process signalled

- `data/trader/wiring_D/d5_before.txt` (08:36 UTC) and `d5_after.txt` (10:15 UTC): the paper14 trader processes
  (PIDs 17464 and 3720, started 13:28:55 local) are alive with the same PIDs and start times before and after. Its
  files changed only through its own appends (journal, audit, ledger, rtt). The two files the run never writes after
  start are unchanged: `advice.db` (13:28:55) and `keys.jsonl` (13:28:54).
- Every run I started printed its directory: `wiring_off`, `wiring_on` and `wiring_drills` (6 drill children). No WW-D file
  (`trader/loop.py`, `trader/features.py`, `tests/wiring/test_ww_d.py`) names paper14. The only process I stopped was
  a stuck shell wait of my own; no Python process was killed or signalled.
- paper14 has no `features.json`, so a restart of it with the new loop runs with every flag off: the D1 parity test is
  the guarantee that it behaves as before.

## How to reproduce

```
cd roster
rem tests (offline)
.venv\Scripts\python.exe -m pytest trader/tests tests/invariants tests/phase2 tests/phase3 tests/phase4 tests/phase5 tests/wiring -q

rem throwaway signing key for paper folders, this shell only
set ROSTER_HUMAN_KEY=<any random string>
rem flags off
.venv\Scripts\python.exe -m nightly.drills keys > data\trader\wiring_off\keys.jsonl
.venv\Scripts\python.exe -m tools.clearance_cli --db data/trader/wiring_off/advice.db sign --keys data/trader/wiring_off/keys.jsonl --signer <you> --days 2
.venv\Scripts\python.exe -m trader.loop --paper --minutes 20 --dir data/trader/wiring_off

rem all paper-safe flags: data/trader/wiring_on/features.json =
rem ["live_risk","dd7","heartbeat","settlement","capital_ladder","touch","universe_ext","quote_objective","negrisk_scan","markout_cusum"]
rem keys for every market the flagged strategies trade (nightly.drills keys covers only the flags-off strategies):
rem   for m in load_markets(features=F): if any(m.mode in s["modes"] and m.asset in s["sources"] for s in kernel.strategies_for(F).values()):
rem   one key per tick size 0.01 and 0.001 = {**kernel.clearance_key(m), "tick_size": tick}
.venv\Scripts\python.exe -m tools.clearance_cli --db data/trader/wiring_on/advice.db sign --keys data/trader/wiring_on/keys.jsonl --signer <you> --days 2
.venv\Scripts\python.exe -m trader.loop --paper --minutes 20 --dir data/trader/wiring_on
rem (equivalently: --enable live_risk --enable dd7 ... instead of features.json)

rem crash drills with the same flags (features.json and signed advice.db in the drill folder)
.venv\Scripts\python.exe -m nightly.drills --dir data/trader/wiring_drills --out data/trader/wiring_drills/drills.md --seed 11
```
