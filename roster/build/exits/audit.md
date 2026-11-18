# Exit Manager Audit — Exit rules and counterfactual study

Contract: [dispatch.md](dispatch.md). Process: [../README.md](../README.md). Flag conventions: [../wiring/audit.md](../wiring/audit.md). Each acceptance criterion below was checked by an independent auditor agent that did not write the code. The orchestrator then re-ran the full suite.

## The gap

The trader is careful about entries (pricing, sizing, caps, audits) but had no rule for a position once it was open. It held every share to settlement, and the only exit was merging completed YES+NO pairs. On 7 Oct the paper account rose to $58.49 on open marks and fell back to about $39 before settlement, and nothing in the system could lock in a gain or cut a loss. The account-level breakers protect capital, but nothing managed a single position.

## The plan

1. **Build** an exit manager as a flagged module, `exits`, OFF by default, so the 14-day gate run (`paper14`) is unchanged.
2. **Prove** each exit rule on real paper positions: replay each held position's per-minute price path with and without the rule, against the actual settlement. The decision rule was fixed in advance (pre-registration `exit-manager-v1`).
3. **Adopt** only the rules that win, through the normal promotion gate and your token (rule 7). Until then `exits` stays off in `paper14`.

Rules: R1 fair-value exit (on by default: sell when `bid − fee(bid) > f + max(0.02, 1.0 × unc)`); R2 take-profit, R3 model stop and R4 capital release are candidates, off while their parameter is `None`.

## Summary

| Work package | Code audit | Fix rounds | Tests (orchestrator re-run) | Result |
|---|---|---|---|---|
| **WX-A** Exit rules and wiring | PASS | 0 | 768 passed (full suite) | Exit manager built and flagged off. With the flag off, the ladder output matches the audited WW-C baseline digest and the WW-D frozen-loop parity test passes. 20-min paper smoke with `--enable exits`: 0 violations, 0 trips, 43 `exit_decisions` rows, and one real R1 taker exit (bought 0.51, sold 0.54 with fair 0.4955; about −$0.02 after fees in and out) |
| **WX-C** Counterfactual exit study | PASS | 0 | 768 passed (full suite; 27 in `tests/exits/test_study.py`) | **INCONCLUSIVE for every rule**: only 2 closed positions across 16 ledgers (100 needed), and no rule could fire on either |

**Orchestrator re-run:** `.venv\Scripts\python.exe -m pytest -p no:cacheprovider trader/tests tests/invariants tests/phase2 tests/phase3 tests/phase4 tests/phase5 tests/wiring tests/exits -q` gives **768 passed in 78.45 s**.

## Counterfactual results so far: **INCONCLUSIVE**

From [reports/exits_counterfactual.md](../../reports/exits_counterfactual.md):

- **There is too little data to judge any exit rule.** n = 2 closed positions against the 100 the pre-registration needs. Every verdict is INCONCLUSIVE, and every mean improvement is +0.0000 because no rule fired.
- The two closed positions are both `paper14` btc-speed trades, and both lost. Each sat entirely inside the 10-minute pre-close pull window (a 5-minute market, and a 15-minute market filled about 7 minutes before close). **So no exit rule can act on btc-speed positions while the pull-window rule applies.**
- R1 and R3 are "not evaluable" on those two, because the ladder logs no fair value for speed trades.
- Three ladder lots are still open (from the 16:00Z ladder markets: `paper14` YES at 0.963, `smoke_v2` at 0.28, and one in `drills_v3`). They have per-minute fair values, so R1 and R3 become evaluable once those markets settle. The daily rerun picks them up.
- The committed report is stale by one source row: WX-A's `exits_on` ledger (started after the study ran) is now found. It adds no closed position yet, and the next run fixes it.

At the current rate (a few closed ladder positions per day) reaching n = 100 takes weeks. The study needs the second paper run below, with `exits` on, to produce exits it can measure.

## How to switch exits on in a second paper run

Run it in its **own** folder, alongside `paper14` and never inside it. `paper14` has no `features.json`, so it stays flags-off.

From `roster/`:

```
mkdir data\trader\exits_paper
echo ["exits"] > data\trader\exits_paper\features.json

rem own clearance (throwaway key for this shell only; not paper14's keys)
set ROSTER_HUMAN_KEY=<any random string>
.venv\Scripts\python.exe -m nightly.drills keys > data\trader\exits_paper\keys.jsonl
.venv\Scripts\python.exe -m tools.clearance_cli --db data/trader/exits_paper/advice.db sign --keys data/trader/exits_paper/keys.jsonl --signer <you> --days 14

.venv\Scripts\python.exe -m trader.loop --paper --minutes 20160 --dir data/trader/exits_paper
```

- `features.json` (or `--enable exits` on the command line) turns the flag on. The clearance lasts the length of the `--days` you sign, so re-sign before it lapses.
- Use the same flags as `paper14` (none) plus `exits`, so the two runs differ only in exits.
- Watch it by copying `data\trader\exits_on\summary.py` into the new folder (it opens the `trader.db` next to itself, read-only), and let the daily `python -m research.exits.study` pick up `exits_paper` automatically.
- Do **not** combine `exits` with `live_risk` yet: in REDUCING that pair refuses taker exits (fail closed). That needs a decision first.

## What remains

1. **Fix the two minor defects that matter before R2 or the second run** (one line each): `merge()` should withdraw the complement bid only when an exit SELL is actually sent (WX-A), and the study should read its parameters from `trader.engines.exits.PARAMS` (WX-C).
2. **Start the second paper run** (above) and keep running the study daily until n ≥ 100 closed positions, or futility after 50.
3. **Decide `exits` + `live_risk`** before both flags are on together.
4. **Persist cost basis** before enabling R2 or R3: `LadderEngine.cost` is in memory only, so after a restart carried positions have no cost and R2/R3 cannot fire on them. R1 does not need cost.
5. **R2–R4 parameters** (`tp_min_tau_h` 2, `sl_tolerance` 0.02, `release_room_usd` 5) are placeholders until the study sets them. R4's free-capital condition is assumed true in the study (an upper bound).
6. **btc-speed positions cannot be exited** under the current pull window, and log no fair value. Exits for speed trades would need their own rule; out of scope here.
7. **Promotion:** if `exit-manager-v1` passes, switch `exits` on in the main system through the promotion gate and only with your approval (rule 7).

---

## WX-A: Exit rules and wiring

**Final verdict:** PASS (from `audit:WX-A`). Agent sequence: build → audit.

| AC | Status | Evidence | Command |
|---|---|---|---|
| X1 flag off: every existing test passes, ladder intents on a recorded tick set identical | pass | 768 passed. The D1 frozen-loop parity test runs and passes (not skipped). `test_x1` reproduces the WW-C baseline digest with `LadderEngine()` and `LadderEngine(flags=('exits',))`. Every WX-A change in `ladder.py`, `loop.py` and `features.py` is gated on the flag; `exits` is in `FLAGS` but not `PAPER_SAFE`. paper14 has no `features.json`, so it runs flags-off | `pytest` full suite; `pytest tests/wiring/test_ww_d.py -k d1 -rs`; diff of `ladder.py` against the WW-C baseline; grep of `exit` in ladder/loop/features |
| X2 R1 fires exactly when bid − fee > f + margin; R2–R4 only when their parameter is set | pass | R1 fires iff `sell > f + max(fv_margin, k_unc·unc) + 1e-9`. R2, R3 and R4 each require their parameter to be non-None, and PARAMS has `tp_pct`/`sl_drop`/`release_bid` = None. The 3,000-point R1 property test and one on/off/threshold test each for R2–R4 pass | code read `trader/engines/exits.py:88-95`; `test_x2_*` |
| X3 never sells more than held net of pending SELLs/complement bids; never rounds up; refuses below min size | pass | Taker size = `floor_to(min(n, top_bid_size))`, maker size = `floor_to(n)`, with n = position minus in-flight SELL takers (an unknown order counts in full). Below min size: a `below_min` row and no intent. Three independent backstops block an oversell: `kernel.reduces`, the router's position check and `sim_guard`. Probe: a bid showing 6 of 10 held gives a taker for 6; a NaN bid size falls back to a post-only maker. Smoke: max(size − held) = 0 | code read `exits.py`, `kernel.py:280-288`, `router.py:202-205`; `build/exits/audit-tmp/WX-A/probe.py`; `test_x3_property_random_holdings` |
| X4 exit intents are `reduces_exposure=True` SELLs the real kernel approves in REDUCING | pass | The real `RiskKernel` in global REDUCING approves taker and maker exits and rejects a BUY. The loop test sells 10 shares under a REDUCING trip with 0 violations. Caveat: with `live_risk` also on, the reducing rule fails closed for taker exits | `test_x4_kernel_approves_exit_sells_in_reducing`; `test_loop_exit_sells_held_position_through_kernel[True]`; code read `kernel.check` 210-228 |
| X5 no exit on stale books, in the pre-close pull window or the oracle gap | pass | Every pull reason (stale_book, close, oracle_gap, sharp_move, book fault) gives a skip row and no intent. Through the real `LadderEngine(flags=('exits',))`: the control fires R1; a 61 s stale book, end − 9 min and the oracle gap each give no intent with the matching reason. The smoke logged live skips for stale_book (9) and sharp_move (2) | code read `exits.py:83-87`, `ladder.py:492-494`; `test_x5_*` |
| X6 20-min paper smoke in `data/trader/exits_on/` with `--enable exits`: no crash, 0 violations, `exit_decisions` rows | pass | Run `1791387918129-10992`: 43 `exit_decisions` rows (hold 31, skip stale_book 9, skip sharp_move 2, sell_taker R1 1), 0 violations, 0 trips; fills BUY 5@0.34, BUY 5@0.51, SELL 5@0.54 plus 2 speed fills. Every count matches `reports/exits_smoke.md`. The run used the disclosed `seed_smoke.py` (stock `loop.main` with `--paper --enable exits` plus two 5-share paper taker seeds through the real kernel and router). Unseeded run 1 was also clean but logged 0 rows (no positions) | independent read-only (`mode=ro`) query of `data/trader/exits_on/trader.db`; `smoke.log`, `smoke_run1.log`, `seed_smoke.py` |

**Open defects at final audit** (none are blockers or majors):

- **minor**: `merge()` withdraws the ladder's complement BUY for every token whose row has a rule set, including rows where no exit SELL is sent (`below_min`, or "maker would cross"). Probe: 3 shares held with min size 5 and R1 firing gives no exit and no complement bid, so the residual can neither be sold nor completed into a pair while R1 keeps firing. Flag-on path only. Fix: build `fired` from the emitted exit intents (`{i.token_id for i in exits}`). File: `trader/engines/exits.py`.

**Not defects, noted for later:** `exit_decisions` repeats are rate-limited to one per (token, action, rule, reason) per minute, following the existing `LOG_REPEAT_MS` convention (the study should know rows are deduplicated; taken exits are also in `fills`). The maker price adds a `bid + tick` floor beyond the dispatch formula, a safe guard against crossing. The builder's design decision is accepted: a fired exit takes precedence over the complement bid, which matches `kernel.reduces`; the literal reading would leave typical 5–10 share positions unexitable.

**Rules check:** Files modified after the dispatch are `trader/engines/exits.py`, `ladder.py`, `loop.py`, `features.py`, `tests/exits/test_exits.py`, `reports/exits_smoke.md` and `data/trader/exits_on/*`, all owned. `data/markets/2026-10-07T152218Z.jsonl` is the stock loop's startup crawl snapshot, normal for any paper run. No WX-A file references paper14. The only running python processes are the two paper14 loops (started before this build); no smoke process was left running and nothing was signalled. Grep of the owned files finds no requests/urllib/http/LLM/py_clob/API key usage; the signing key was a throwaway env value. No pip installs. The report ends with "How to reproduce".

---

## WX-C: Counterfactual exit study

**Final verdict:** PASS (from `audit:WX-C`). Agent sequence: build → audit.

| AC | Status | Evidence | Command |
|---|---|---|---|
| C1 unit tests on a synthetic path: each rule exits at the right minute; improvement maths exact | pass | 27 passed. The R1–R4 and pull-window tests each assert the exact exit minute, including the strict R1 threshold at ±1e-9, the unc term overriding the margin, a stale fair after 6 min, and no exit before the fill or inside end − 10 min. `improvement = shares × (bid − fee(bid) − payout)` is checked to 1e-12. FIFO lots net of sells and merges are checked. The rule formulas match dispatch R1–R4 | `pytest tests/exits/test_study.py -q`; code read of `research/exits/study.py` `first_exit`/`improvement` |
| C2 no look-ahead: a decision at minute t uses only data up to t | pass | `first_exit` iterates minutes in order and returns at the first firing minute. `fair_at` uses `bisect_right`, so only fairs with ts ≤ t are used, and only if at most 5 min old. The test truncates the path at every t over 20 seeds and every variant and gets the same exit; scrambling all data after the exit leaves it unchanged | `test_decision_at_t_uses_only_data_up_to_t[0..19]`; code read |
| C3 opens every ledger read-only (`mode=ro`); writes nothing under `data/trader/` | pass | The only DB access is the pre-existing `nightly.scorer.tables` (`?mode=ro`). The test wraps `sqlite3.connect`: every URI ends `?mode=ro`, INSERT raises, and the ledger is byte-identical afterwards. Real before/after stat: no `trader.db` changed, no file created; paper14's db and -shm untouched (its -wal changed only from the live writer). Finished ledgers' -shm files got new mtimes from SQLite's read-lock protocol, as with the nightly scorer | grep `mode=ro`; stat of `data/trader/*/trader.db*` before and after two `--offline` runs; `test_end_to_end_read_only` |
| C4 report exists, covers every variant, gives n and SE, states INCONCLUSIVE where n < 100 | pass | All 11 variants, each with n, not evaluable, exited, clusters, mean, CR0 cluster SE and verdict, plus an h = 0.005/0.01/0.02 sensitivity table. States in bold that the sample is too small (n = 2 of 100). Has a Sources table and ends with "How to reproduce" | `cat reports/exits_counterfactual.md`; `test_end_to_end_read_only` |
| C5 one documented command reproduces it | pass | Two runs give identical output (md5 566af55a…). They differ from the committed report only by the new `exits_on` ledger row (WX-A's smoke started after the builder's run, 0 fills) | `.venv\Scripts\python.exe -m research.exits.study --offline --out build/exits/audit-tmp/WX-C/out --report build/exits/audit-tmp/WX-C/r1.md` (and r2.md); md5sum |
| Flag off = unchanged behaviour / full suite | pass | 768 passed. WX-C touches no trader code; it only imports scorer, fees and `ladder.PARAMS` read-only | full-suite command |
| No real orders / authenticated / LLM calls; tests offline; owned paths only | pass | The only network call is `scorer.fetch_outcome` (public GET, User-Agent only), skipped with `--offline`; tests pass `fetch=None`. Files: `research/exits/{__init__,study}.py`, `tests/exits/test_study.py`, `reports/exits_counterfactual.md`; `tests/exits/__init__.py` is the shared package marker | code read of `study.py` imports and `outcomes()`; stat of owned files |

**Open defects at final audit** (none are blockers or majors):

- **minor**: The study's rule parameters diverge from WX-A's published `PARAMS`: the study uses `tp_min_tau_h` = 1.0 where `trader/engines/exits.py` has 2.0, and it hard-codes `fv_margin`, `k_unc` and `sl_tolerance`. So R2 in the study can fire where live R2 would not. No effect on current results (nothing can fire on n = 2). Fix: build the study's parameters from `trader.engines.exits.PARAMS`. File: `research/exits/study.py`.
- **minor**: Combination variants R1+R2 and R1+R3 drop every lot without a fresh fair from n, even though their R2 leg could still fire. Documented ("not evaluable for R1/R3"), but it understates R1+R2's sample. Acceptable as is; optionally let only the R2 leg evaluate on such lots. File: `research/exits/study.py`.

**Rules check:** paper14 is opened only through `scorer.tables` with `mode=ro`; its db and -shm were unchanged. Nothing was written, moved or deleted under `data/trader/`. No processes signalled. The `exits` flag is not touched by WX-C. No real orders, authenticated calls, LLM calls or pip installs. Tests are offline. Edits stay in owned paths; auditor scratch is under `build/exits/audit-tmp/WX-C/`. Code is 290 lines and reuses `scorer.tables`, `cluster_se`, `fetch_outcome`, `fees.fee` and `ladder.PARAMS`.

## How to reproduce

From `C:\Users\DELL\Downloads\saugan_pr\market_updated\roster`:

```
set PYTHONDONTWRITEBYTECODE=1
rem full suite (768 passed)
.venv\Scripts\python.exe -m pytest -p no:cacheprovider trader/tests tests/invariants tests/phase2 tests/phase3 tests/phase4 tests/phase5 tests/wiring tests/exits -q
rem D1 frozen-loop parity, must run (not skip)
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/wiring/test_ww_d.py -k d1 -rs
rem WX-A auditor probe and smoke summary (read-only)
.venv\Scripts\python.exe build\exits\audit-tmp\WX-A\probe.py
.venv\Scripts\python.exe data\trader\exits_on\summary.py
rem WX-C study into scratch (offline, read-only ledgers)
.venv\Scripts\python.exe -m research.exits.study --offline --out build/exits/audit-tmp/WX-C/out --report build/exits/audit-tmp/WX-C/r1.md
```
