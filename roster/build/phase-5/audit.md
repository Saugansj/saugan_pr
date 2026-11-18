# Phase 5 Audit — Full learning stack (build now, wire later)

Contract: [dispatch.md](dispatch.md). Process: [../README.md](../README.md). An independent auditor agent, not the builder, checked every acceptance criterion below. The orchestrator then re-ran every test suite on 2026-10-07.

The user chose to build Phase 5 ahead of its gate. Every module is standalone: the trading loop calls none of them, none places an order, and none changes a live parameter.

## Summary

| Work package | Code audit | Fix rounds | Tests (orchestrator re-run) | Result |
|---|---|---|---|---|
| **WP5-A** Calibration analyst, postmortems, drift and CUSUM triggers (5.1–5.3; roles 32, 33, 34, 02) | PASS (ops pending) | 0 | 29 passed | The smoke finds the planted lesson (crypto-hourly speed-taker, 72 clusters) and gives no lesson for the variance group. The planted −1 SD markout drift trips the role 02 lock at cluster 65 with no false trips. Calibrated h = 6.7 for 124 monitors. Simulated ARL is within 1% of Siegmund (338) |
| **WP5-B** Replay lab (5.4; role 35) | PASS (ops pending) | 0 | 28 passed | The real 2-min recording replays with the tripwire armed and 0 look-ahead violations (42,527 ladder and 38,992 speed engine calls). Strict mode matches PaperRouter with 0 mismatches over 15,489 fuzzed fills. Seeded synthetic set: PBO 0.061 with an edge trial and 0.363 on noise only. The best noise trial has DSR 0.489 against an undeflated PSR of 0.987 |
| **WP5-C** Quote-engine full objective (5.5; role 20) | PASS (ops pending) | 0 | 15 passed | The fill-rate MLE is unbiased and its SEs are calibrated (40 seeds). Outputs pass the 435-quote constraint fuzz with 0 violations. The reward term is $0 on every real market (no target market pays rewards). At γ = 1 the objective sizes to the 50-share limit, so γ needs calibrating |
| **WP5-D** Advisor roles 24, 30, 31, 26 against `Gateway` (5.6, 5.7) | PASS (ops pending) | 1 | 83 passed | Every role fails closed: a failure gives a pull, a veto or an exclusion. A prompt holding a secret is never sent. The round-1 fixes closed the NaN/inf bypass of rule 7 (a major defect) and three smaller defects. LLM output can only pull, veto or be excluded |

**Tests:** all four suites pass: 29 + 28 + 15 + 83 = 155. The whole `tests/phase5` folder also passes as one run (155 passed in 32.74 s). Nothing failed.

**Orchestrator checks (dispatch, "Phase 5 checks"):**
- `grep -rn "promote(" learning advisor/roles_p5 --exclude=loop_a.py --include=*.py` finds nothing (exit 1).
- The shared contracts are unchanged since the earlier audits:
  - `trader/contracts.py` sha256 `1c0e3f29…`
  - `advisor/contracts.py` `cd19a7dc…`
  - `common.py` `e1fea022…`
- Every auditor confirmed that its builder wrote only inside its owned paths.
- Every [ops] item is listed below as `operational_pending`.

## Phase 5 exit gate: **none (by design)**

The build plan says: *"Exit gate: none. From here on, every change goes through the gate."* That means Loop B, then role 31's veto, then the user's token. The code side of Phase 5 is finished and audited. Nothing is wired in yet. These [ops] items stand between this code and live use:

| Item | Waits for |
|---|---|
| **A14** Analyst, postmortems and CUSUM on real data | Real ledger rows with at least 20 resolved clusters per group, h calibrated on the real standardised per-cluster series, and at least 2 weeks of operation confirming no more than 1 false human reset per 2 weeks system-wide |
| **B18** Replay on real history and the task 2.8 canary | 7 or more recorded days from the VM recorder, and live fills, which need keys and money |
| **C13** Fitted quote objective | Weeks of role 22 maker fills for per-market fits, reward-paying markets (today every target market has `reward_daily_rate` 0), then Loop B and a human token |
| **D15** Advisor roles on real vendors | Phase 4 gateway keys (none on this machine), calendar time for markets to resolve after each model's cutoff, and a comparison of role 30 and role 31 verdicts against the user's on a backlog |

**Contract gaps for wiring (reported, not edited):**
- `trader/contracts.py`'s `Ledger` Protocol has no `register()`. Candidate dicts from WP5-A and WP5-C stay unregistered until Phase 1 adds `Ledger.register`, which may only create state `candidate`.
- Closed-position rows have no close-time field, which the CLV lock's per-cluster ordering needs.
- `MarketInfo` has no rebate or reward fields.
- Markout sign: Phase 1 `ladder.income_per_dollar` treats markouts as a cost, while role 22 treats positive as good. The two must agree before non-zero markouts feed either module.

**One spec conflict for the user to decide (WP5-C, C7):** "a larger σ or τ never tightens a quote" cannot hold for the bid that sheds expected inventory under the dispatch's own J. Audit counterexample: at I = +20 and γ = 5, the NO bid goes from d = 0.006 to d = 0.0 as σ rises from 0.0005 to 0.002. The code implements J faithfully. There are two ways to resolve it:
- narrow C7 to flat quotes and the bid that adds to inventory, which holds and is tested, or
- change the inventory term in the spec.

## Wiring later

### WP5-A (learning/analyst.py, postmortem.py, cusum.py)
1. **Rows:** feed `breakdown`, `reliability`, `classify_all`, `lessons` and `scan` from `Ledger.as_of` tables or `nightly/scorer.py` once their table names are fixed. The rows are plain dicts in the dispatch's shapes.
   - Closed-position rows have no time field, so `per_cluster` takes `time=` (fills use `ts_ms`, forecasts `event_ms`).
   - Positions need a close time, or a time mapped by `cluster_id`, before the CLV lock runs.
2. **Monitor actions** are `{source, scope, action, reason, ts_ms}`.
   - Send them to `kernel.trip(scope, reason, source)` and `trader/breakers.py` through Loop B. The kernel caps AI and T5 sources at REDUCING.
   - The role 02 markout lock (`Monitor('02-cusum','lock','markout',h)`) replaces the count-based blacklist (30 fills, 2 SE).
   - Key the lock by a recurring market series (template, underlying or team), not by cid. Each cid sits in one event group, so a per-cid series has only one point.
3. **Resets:** only the breaker board calls `Monitor.reset(key)`, after it verifies the human token. Persist the Monitor state (S and tripped per key and direction) across restarts.
4. **Calibrating h:** calibrate it once on the real standardised per-cluster series with the real system families, via `calibrate_h(null_z, families)`. Store h, the null's provenance and the seed as a registry entry. Because of the audit's minor defect, report a bootstrap interval for h, or take an upper quantile across null resamples.
5. **Candidates** (`budgets:<mode>`, `lesson:...`) are plain `{name, version, params, evidence}` dicts. They need `Ledger.register` (see the contract gaps above).
6. **Reporting:** the report sections feed role 36's daily report.
7. **Invariant tests:** copy `test_a4_no_promote_anywhere`, `test_a5_outcome_blind` and `test_a10_no_halt` into `tests/invariants/`.
8. **venue_changes** takes MarketInfo lists from consecutive crawler snapshots plus venue dicts (for example `{taker_delay_ms, settlement:{mode: method}}`) and `now_ms`.

### WP5-B (learning/replay/)
- **Nightly job:** `nightly/replay/` calls `learning.replay.run.replay(engine, Store.load(start, end, streams), start, end, rtt_ms, kernel=<real kernel>, outcomes=<scorer outcomes>)`.
  - Log every run through `validate.TrialLog` under `data/`, and take the DSR's N and V from `TrialLog.count` and `TrialLog.sharpes`.
  - Move the `--out` and `--report` defaults from `learning/replay/out/` to `data/`.
- **Router:** through role 31 and the user's token, either swap `trader/router.py`'s simulator for `learning.replay.fills.FillModel`, or port its three fixes:
  - the expiry check before trades
  - the used/traded liquidity maps
  - the no-book and give-up kill

  Either way, paper and replay stay identical, and the B4 parity test is the guard.
- **Maker diff:** the (token, side, price, size) diff in `run.replay` can be shared with `trader/loop.py`.
- **Loop B:** candidates go through replay, `random_entry` and the DSR/PBO checks as exploratory evidence before shadow.
- **Task 2.8 canary:** its interval comes from replays with `fill_mode="queue"` and a calibrated `cancel_ahead`.
- **Before trusting results:** add a configurable reference-feed latency (the audit's minor defect: the replay currently has zero ref latency).

### WP5-C (learning/quote_objective.py)
1. **Replace `quotes()` in the ladder engine.** In `trader.engines.ladder.market_intents`, call `optimise(m, q, mid, (yes.best_ask(), no.best_ask()), net, cost, fit, sigma, tau, reward, q_others(yes, mid, v), p)`. The output has the same shape, `[(token, price, size, reduces)]`, and `pull_reason()` still runs first.
2. **Inputs to compute:**
   - τ = min(requote interval, (end_ms − pull_before_close_ms − now)/1000)
   - σ = realised mid volatility per √s, in probability units
   - `reward` comes from the crawler row's `reward_min_size`, `reward_max_spread` and `reward_daily_rate`
   - `rebate_rate` comes from `fee_schedule.rebateRate`, passed in `p`
3. **Anchor:** pass the result through `wider(current, anchor)`, with anchors from Phase 4's `learning/loop_a.py`.
4. **Fits:** feed `fit_candidates(orders, fills)` with maker order and fill rows from `nightly/scorer.py`. Each result is a candidate dict for the registry (state `candidate` only).
5. **Gate:** all of this happens only after the objective passes Loop B (replay, then shadow, then canary) and the user's token.
6. **Registry parameters:** make γ, d_max, size_step and c registry parameters, and calibrate γ before use.
7. **Documentation:** document that the no-quote baseline is J0 = −γσ²τI², not J ≤ 0.

### WP5-D (advisor/roles_p5/)
- **Gateway:** construct the roles in the advisor process and pass Phase 4's `advisor.gateway.LLMGateway` as `gw`. The roles call only `gw.complete` and `gw.quota_left`.
- **Role 24:** `ShockReader(enabled=<live underlyings>).read(news_items, now_ms, gw)`.
  - Write each CautionSignal to advice.db.
  - The trader pulls until `expires_ms` and resumes only on a fresh observation.
  - Keep `recorded_ms` an int: float values are skipped.
- **Role 30:** call `CorrelationAdversary.review(event_group, group_markets, {held_group: [markets]}, cap, gw)` from the kernel's first-entry or cap-raise path.
  - Keep one instance per process so the cache holds. A veto means "not cleared".
  - Error vetoes are cached until a cap raise or a restart. Add a TTL if this bites.
- **Role 31:** make `ChangeGate().review(change, gw)` a required step before any `Ledger.promote`, still followed by the human token.
  - The change dict is `{kind: code|learned, name, paths, diff, old, new, prereg: {n, pass_z}, evidence: {n, mean, se}}`.
  - Any change to `trader/fees.py` counts as a T0 change.
- **Role 26:** run `shadow.run_batch(markets, now_ms, gw, max_markets, platt=shadow.fit_platt(resolved_rows_one_mode), log_path=<ledger-side path>)` daily.
  - `error_correlation` counts only rows that have a non-None `mid` and that appear in `outcomes`.
  - Move the research log to a ledger table that nothing in the trader reads.
- **Audit stamps:** each module exposes `PROMPT_SHA256` for role 04's audit log.
- **Invariant tests:** copy the D2/D3 fail-closed and prompt-hygiene tests into `tests/invariants/`.

---

## WP5-A: Calibration analyst, postmortems, drift and CUSUM triggers (5.1–5.3; roles 32, 33, 34, 02)

**Final verdict:** PASS_WITH_OPERATIONAL_PENDING. Agent sequence: build → audit. Tests: 29 passed (orchestrator re-run 17.30 s).

**Key results (builder, confirmed by the byte-identical smoke re-run):**
- **Lessons:** the smoke finds one lesson, `lesson:crypto-hourly:speed-taker:model`, over 72 clusters (mean −0.0585 ± 0.0139).
- **Variance group:** its mean is −0.0369 ± 0.0121, which is significantly negative, and it still produces no lesson, as designed.
- **Budget candidates:** these are proposals only. crypto-hourly speed-taker goes 1.0 → 0.5, and sports-pregame ladder-maker goes 1.0 → 0.5.
- **Calibrated h:** 6.7 for 124 monitors, at 0.939 false trips per 2 weeks (0.812 on a fresh simulation).
- **Drift:** the planted drift trips at cluster 65.

| AC | Status | Evidence | Command |
|---|---|---|---|
| A1 Clustered SEs from `research.kappa.kappa.clustered_mean`; duplicates inside a cluster leave the SE unchanged, duplicates as new clusters shrink it | pass | Both modules import `clustered_mean`. Independent check: SE 0.15299 base, 0.15299 with duplicates inside clusters, 0.10678 with duplicates as new clusters. NaN SE below 2 clusters | read imports; pytest test_a1; audit-tmp/WP5-A/check.py |
| A2 Breakdowns never pool modes | pass | `_groups` filters by mode before keying. The per-mode slices of a two-mode run equal single-mode runs (NaN-aware) | pytest test_a2 |
| A3 Reliability: calibrated bins within 3 SE, identical rows, universe/traded/gap | pass | Incomplete rows are dropped before scoring. With 20,000 seeded rows, all 10 bins are within 3 SE. Brier and log loss match a hand computation. Gap = traded − universe (no SE; disclosed) | pytest test_a3 |
| A4 Budget candidate: total never rises, none < 0, unchanged under min_clusters, returns a candidate dict, no `promote(` | pass | The grep finds nothing. 300 random cases pass. Edge case A=1, B=0, step 1 → {A:0, B:1}. Mixed modes raise ValueError | grep; pytest test_a4*; check.py |
| A5 Outcome-blind classify | pass | An access tracker recorded reads of only clv, fee_per_share, flags, markout_5m, mode and strategy. Flipping the outcomes of 1,000 positions changes no class | pytest test_a5; check.py |
| A6 Truth table and precedence | pass | The rule order matches dispatch rules 1–7. 10 parametrized cases pass | pytest test_a6 |
| A7 Lesson thresholds and importance half-life | pass | 20 significant clusters → 1 lesson; 19 → none; non-significant → none; variance/indeterminate → none. Importance halves at 30 days | pytest test_a7 |
| A8 CUSUM ARL within 10% of Siegmund (~338) | pass | `siegmund_arl(0.5,4)` = 338.1. Independent seeds give ratios of 0.997, 0.993 and 1.004 | pytest test_a8; check.py |
| A9 Calibrated h ≤ 1.2 false trips per 2 weeks on a fresh simulation; h rises with n_series; AR(1) h above iid h | pass | Seed 202: h 4.4, fresh 1.03, h500 6.2, hAR 6.7. Seed 101 gave a fresh rate of 1.315. Across 10 null samples, the true rate at the calibrated h is 0.82–1.31 (minor defect below) | pytest test_a9; check.py, check2.py, check3.py |
| A10 Sticky trips; a planted −1 SD shift trips within 30 clusters after cluster 50; no halt | pass | Only `reset()` clears a trip, and nothing in the modules calls it. ACTIONS = ('lock','alarm'). Seeds 1–20 at h = 4.3: 18/20 tripped in [50, 80], and the other 2 were early false trips | pytest test_a10*; grep halt; check.py |
| A11 Bias drift trips only on the planted entity; error correlation fires on 0 → 0.8; venue_changes alarms correctly | pass | Only entity C trips. Exactly one high error-corr alarm. Venue changes give mode, venue and per-mode alarms; a single-market tick change gives none | pytest test_a11_* |
| A12 Smoke report has every section, finds the planted effects, ends with How to reproduce | pass | The regenerated report is byte-identical to `reports/phase5_analysis_smoke.md` | `python -m learning.analyst --smoke --out build/phase-5/audit-tmp/WP5-A/smoke.md` |
| A13 Tests pass offline | pass | 29 passed. No network imports | `python -m pytest tests/phase5/test_analysis.py -q` |
| A14 [ops] Real ledger rows, h calibrated on real clusters, false-reset rate in operation | operational_pending | Needs at least 20 resolved clusters per group, calibration on real series and at least 2 weeks of operation | n/a |

**Open defects at final audit** (all minor):
- **minor** (`learning/cusum.py`): with two directions, `Monitor.update` returns when one direction trips, so the other direction misses that observation. This affects only the bias and error-corr monitors. Fix: update every direction first, then return.
- **minor** (`learning/cusum.py`): `calibrate_h`'s false-trip rate depends on the null sample. The true iid rate at the calibrated h was 0.82–1.31 (3 of 10 samples above 1.2). test_a9 depends on its seed. Fix at wiring: take an upper quantile or a safety margin, and assert against a direct iid simulation.
- **minor** (`learning/cusum.py`): `error_corr_z`'s reference defaults to the first 4·W clusters rather than one window. The deviation is disclosed; reference noise inflates the variance of z to about 1.25. Prefer a registered `ref_fz`, or scale by √(1 + 1/ref_windows).

**Rules check:** WP5-A wrote only its 5 owned files. The contracts are unmodified (hashes match). There are no order or network paths, no credential reads and no LLM calls. Nothing outside the tests imports these modules, `promote(` is absent, and no action is "halt". Standardisation uses only earlier clusters, so there is no look-ahead. The code is 3 modules (685 lines) and 1 test file.

---

## WP5-B: Replay lab (5.4; role 35)

**Final verdict:** PASS_WITH_OPERATIONAL_PENDING. Agent sequence: build → audit. Tests: 28 passed (orchestrator re-run 8.29 s).

**Key results (builder, reproduced by the auditor's ladder re-run):** the recording covers 2026-09-30 14:29–14:31 UTC, replayed with rtt 210 ms and Binance 1s klines fetched publicly into memory.
- **Ladder:** 46,643 pm messages and 42,527 engine calls, with 14.3M tripwire input checks and 0 violations.
  - 826 maker intents, 826 cancels and 0 fills, so there is no per-cluster statistic.
  - The cancels follow the engine's own flapping targets.
- **Speed:** 38,992 calls and 0 intents. The largest 5 s BTC move was 7.37 bp, below the 10 bp trigger.
- **Synthetic set (20 trials × 500 periods):**
  - PBO is 0.061 with an edge trial and 0.363 with noise only.
  - The edge trial's DSR is 0.920.
  - The best noise trial's DSR is 0.489, against a PSR of 0.987.

| AC | Status | Evidence | Command |
|---|---|---|---|
| B1 Store parses the recorded hour through `trader.marketdata.Books` | pass | Books are equal at every step in the fixture. On the real file, books are equal for 316 tokens (ladder) and 124 (speed) | pytest test_b1_* |
| B2 `as_of(t)` never returns events recorded after t | pass | A trade recorded late (event +35 ms, recorded +500 ms) is absent at +100 and present at +500. A 50-sample random check also passes | pytest test_b2_* |
| B3 Tripwire: a leaky feeder raises LookAheadError, no report is written, a clean run has 0 violations | pass | Auditor probes catch a future snapshot and a final that is not yet closed. In the CLI test, a leak writes no report and logs one failed trial row | pytest test_b3_*; auditor probe |
| B4 Strict mode matches PaperRouter | pass | 4 cases match. Independent fuzz: 3,000 scenarios, 15,489 fills, 0 mismatches (excluding the intended fix-2 cases) | pytest test_b4; audit-tmp/WP5-B/fuzz_parity.py |
| B5 Three execution fixes | pass | An expired maker gets no fill. A second taker gets only what remains of the level. A trade's volume goes oldest first. A taker with no book, or past its give-up time, is killed | pytest test_b5_* |
| B6 Queue mode | pass | A drop of 40 with cancel_ahead 0.5 moves the queue 100 → 80. A trade of 85 gives a partial fill of 5. Drops explained by trades are not double-counted | pytest test_b6_* |
| B7 Runner diff/submit/fill, protocol args, kernel rejection | pass | 3 submits, 1 cancel and fills, with on_fill called. On real data, 25,494 non-empty ticks give only 826 submits | pytest test_b7_*; ladder_probe.py |
| B8 Walk-forward, with a property test over 200 sets | pass | The embargo holds, there is no overlap, folds run in time order, unresolved clusters are purged, and more folds than clusters works | pytest test_b8_* |
| B9 Nested selection | pass | Inner calls see only outer-train ids. The "cheat" trial is never selected | pytest test_b9_* |
| B10 CPCV N=6, k=2 | pass | 15 splits, each group is a test group 5 times, and the embargo is respected | pytest test_b10_cpcv |
| B11 DSR | pass | An independent scipy computation (sr0 0.07873, DSR 0.6311, PSR 0.9423) matches. DSR is monotone in N and V | pytest test_b11; stats_check.py |
| B12 PBO | pass | The seeded test passes. On extra seeds, the edge trial gives PBO ≤ 0.003. Noise-only PBO varies (0.126–0.61), which is ordinary sampling variance | pytest test_b12; stats_check.py |
| B13 Random-entry baselines | pass | Each cluster's entry count and sizes are kept, fills go through FillModel with fees > 0, and output is deterministic per seed | pytest test_b13 |
| B14 Trial log is append-only, includes failed runs, N = row count | pass | The log is written only through `common.append_jsonl` (mode 'a'). Earlier bytes are unchanged | pytest test_b14 |
| B15 Smoke with real engines, 0 violations, report contents | pass | The engine source hashes match. The auditor's re-run reproduced 42,527/826/826/0 and the 7.37 bp move. The report ends with How to reproduce | ladder_probe.py; read report |
| B16 No order path; the optional GET goes through `common.get_json` | pass | The import grep finds nothing (exit 1) | grep (see per-AC command in audit) |
| B17 Tests pass offline | pass | 28 passed, also with sockets blocked | `python -m pytest tests/phase5/test_replay.py -q` |
| B18 [ops] 7+ recorded days; task 2.8 canary with live fills | operational_pending | Needs 7+ days from the VM recorder and live fills (keys and money) | n/a |

**Open defects at final audit** (all minor):
- **minor** (`learning/replay/fills.py`): two of our makers at the same token and price each count the queue ahead of them separately. The bias is conservative (too few fills), and it is rare because the diff keeps one order per key.
- **minor** (`learning/replay/events.py`): the reference feed has zero latency (recorded_ms == ts_ms). The tripwire does not check that a DVOL value was recorded after its 1h close; only a hand-fed feeder could leak it.
- **minor** (`learning/replay/run.py`): `res['violations']` is always 0, because a violation raises instead. It is truthful, but the field can never be non-zero.
- **minor** (`learning/replay/__main__.py`): `render()` uses every `smoke_*.json` in out/, so a ladder-only run republishes a stale speed section.

**Rules check:** there is no order, signing or authenticated path. The only network code is the public GET in `fetch_ref`. Tests pass with sockets blocked. The tripwire is armed before every engine call. Sizes are floored. Builder files: `learning/replay/*`, `tests/phase5/test_replay.py` and `reports/phase5_replay_smoke.md`, all owned. The code is 5 modules (about 1,050 lines).

---

## WP5-C: Quote-engine full objective (5.5; role 20)

**Final verdict:** PASS_WITH_OPERATIONAL_PENDING. Agent sequence: build → audit. Tests: 15 passed (orchestrator re-run 11.83 s).

**Key results (builder):**
- **Placement:** with the prior fill parameters (A = 0.01/s, 1/k = 1 cent, a = 0), the objective quotes at the touch, or one tick inside a wider book. Phase 1 quotes half_min + vol below q.
- **Sizing:** it sizes to the 50-share inventory limit, where Phase 1 quotes 10.
- **Rebate:** at mid 0.5 it is 0.0035 per share, against a 1-cent edge.
- **Reward term:** it is $0 on every sampled market. A hypothetical $100/day pool adds about $0.0125 per 60 s quote.
- **Speed:** about 0.14 s per `optimise()` call.

| AC | Status | Evidence | Command |
|---|---|---|---|
| C1 S(v,s): v=4.5, s=1.5 → 0.4444; s ≥ v → 0; size below reward_min_size → 0 | pass | Matches Phase 0's `research.measure.reward_income.order_score` | pytest test_c1_score |
| C2 Q_min: one-sided and two-sided inside 0.10–0.90; one-sided 0 outside | pass | Tested at mids 0.5, 0.10 and 0.9 inside the band and 0.05 and 0.95 outside it | pytest test_c2_q_min |
| C3 Reward term: a zero rate gives 0; the share matches a hand-computed fixture | pass | `q_others` subtracts our own size and skips the 10c level. The reward matches the hand-computed Q1 and Q2 | pytest test_c3_reward_term |
| C4 The fill-rate fit recovers A and k within 10% (≥ 2,000 censored orders); the adverse fit is within 2 SE | pass | 40 seeds: at n = 20,000, mean k is 60.02 vs a true 60 and mean A 0.02004 vs 0.02. The SEs are calibrated (z SD about 1.0). The adverse fit was within 2 SE in 10/10 seeds | pytest test_c4; audit-tmp/WP5-C/check.py, bias.py |
| C5 A market under min_clusters uses its mode's fit; no pooling across modes | pass | The mode fit is identical with and without sports rows. A mode under min_clusters uses `priors[mode]` | pytest test_c5 |
| C6 Degenerate case: distance within one tick of 1/k | pass | Extra cases at k = 200, 30 and 77 (tick 0.001) and k = 30 and 50 (tick 0.01) all hold | pytest test_c6; check.py |
| C7 Comparative statics | pass (spec conflict noted) | The adverse move, inventory skew and no-double-count properties hold. Flat sweeps show 0 tightening. The universal "σ/τ never tightens" clause conflicts with the specified J for the bid that sheds inventory; see the defect below | pytest test_c7_*; check.py |
| C8 Output constraints (tick grid, below best ask, sizes floored, inventory limit, complement cap) | pass | 435 random quotes, 0 violations (150 of them complement quotes) | pytest test_c8; check.py |
| C9 `wider()` is never above either input; anchored refits never get tighter | pass | Refits reached 0.50 × 50, while the `wider()` outputs stayed at or below the anchor's 0.48 × 20 | pytest test_c9_wider; check.py |
| C10 Fits are candidate dicts; no promote/register/record | pass | The grep finds nothing (exit 1) | grep |
| C11 Smoke report with the required sections, ending with How to reproduce | pass | The re-run is byte-identical to `reports/phase5_quote_objective.md` | `qo.smoke(report=audit-tmp/WP5-C/smoke_rerun.md)` |
| C12 Tests pass offline | pass | 15 passed, also with sockets blocked | `python -m pytest tests/phase5/test_quote_objective.py -q` |
| C13 [ops] Per-market fits from real maker fills; non-zero reward terms; live use via Loop B and a token | operational_pending | Needs weeks of role 22 maker fills, reward-paying markets, Loop B and a human token | n/a |

**Open defects at final audit** (all minor):
- **minor, spec conflict for the user** (`learning/quote_objective.py`): the C7 clause "a larger σ or τ never tightens a quote" cannot hold for the bid that sheds inventory under the specified J. Counterexample: at I = +20 and γ = 5, the NO bid's distance goes 0.006 → 0.0 as σ goes 0.0005 → 0.002. The code matches the spec formula. The user should either narrow C7 or change the inventory term.
- **minor** (`learning/quote_objective.py`): the no-quote rule compares J against J0 = −γσ²τI² (not quoting), not "J ≤ 0". A quote that sheds inventory can buy above fair value to cut risk. This is undocumented in the report.
- **minor** (`learning/quote_objective.py`): at γ = 1 the objective sizes to the inventory limit and has no capital lock-up cost. Calibrate γ, and make it a registry parameter, before Loop B.

**Rules check:** WP5-C wrote only its 3 owned files. There is no order, authenticated, network or LLM code. Sizes are floored and prices stay strictly below the best ask and the complement cap. Results are not hard-coded (the smoke is byte-identical). The code is one module of pure functions and one test file.

---

## WP5-D: Advisor roles 24 (shock LLM part), 30 (correlation adversary), 31 (change gate), 26 (shadow forecaster) (5.6, 5.7)

**Final verdict:** PASS_WITH_OPERATIONAL_PENDING. Agent sequence: build → audit → fix1 → reaudit1. Tests: 83 passed (orchestrator re-run 5.01 s).

**Key results (builder smoke on `data/markets/2026-10-01T121820Z.jsonl`, 462 markets):**
- **Role 24:** 6 headlines led to 4 calls. The ETH exploit gave a 240-min pull on ETH, and the depeg gave pulls on BTC and ETH.
- **Role 30:** 100 repeats made 1 call. A cap raise made a second call, which was vetoed on the BTC/ETH same-noon-print link.
- **Role 31:** changes without a pre-registration, with low n or with a failed test were each vetoed with 0 calls. A kernel retry change was flagged as touching T0 and vetoed. Clears carry "pass still needs a human token".
- **Role 26:** 3 of 4 markets got a forecast, and the quota stop worked.

**Round 1 fixed:**
1. NaN and inf can no longer bypass rule 7 or the evidence check (major).
2. A bad `recorded_ms` is skipped instead of aborting the batch.
3. T0 path matching ignores case and covers `trader/fees.py`.
4. `error_correlation` uses p − mid, so N_eff is right with binary outcomes.

| AC | Status | Evidence | Command |
|---|---|---|---|
| D1 No network or vendor imports in `advisor/roles_p5` | pass | The import grep finds nothing. Every call goes through `board.ask` → `gw.complete` | grep (see audit) |
| D2 Prompt hygiene and secret guard | pass | No sentinel appears in any recorded prompt. With a secret in the env and in the prompt, every role makes 0 calls and returns its fail-closed result (env values under 8 characters are ignored, documented) | pytest test_d2_* |
| D3 Each role fails closed | pass | For ok=False, malformed, missing-field and quota-exhausted results: role 24 pulls BTC and ETH, roles 30 and 31 veto, and role 26 returns insufficient | pytest test_d3_*; smoke_r2.md |
| D4 Role 24 | pass | An unmatched item makes 0 calls. The ETH shock gives an ETH pull with shrink 0.0. There is no direction field. Bad or future `recorded_ms` values are skipped | pytest test_d4_*; probe3.py |
| D5 Role 30 | pass | 100 repeats make 1 call and a cap raise makes a new one. A clear needs 2 or more vendors. The cap never appears in a prompt | pytest test_d5_*; probe.py |
| D6 Role 31, rule 7 (including the fix round: NaN/inf, path case, fees.py) | pass | `_num` requires finite values. NaN, inf, None and added keys are flagged. 'TRADER/Kernel.py' and 'trader\FEES.py' are flagged | pytest test_d6_*; probe.py, probe3.py |
| D7 Role 31, evidence | pass | Each NaN, inf or degenerate evidence case is vetoed with 0 calls. With good evidence, the evidence numbers never reach the prompt | pytest test_d7_*; probe3.py |
| D8 No promote/register/record in board.py | pass | Both greps find nothing | grep |
| D9 Ensemble | pass | The median and trimmed mean match hand values. Fewer than 4 usable answers gives insufficient. Calibration clips to [0.03, 0.97]. NaN answers are excluded | pytest test_d9_* |
| D10 Platt | pass | Recovers (a, b) within 0.1 on 2,000 rows, and returns the identity below 100 rows | pytest test_d10_* |
| D11 Scoring and error correlation (including the fix round's binary outcomes) | pass | A model is scored only on markets resolved after its cutoff. With Bernoulli outcomes, N_eff is 1.0 for identical models and 6.0 for 6 independent ones | pytest test_d11_*; probe3.py |
| D12 Permanent shadow | pass | The log is append-only. Nothing outside `roles_p5` imports it | pytest test_d12_*; grep |
| D13 Smoke report | pass | The regenerated report matches `reports/phase5_advisor_smoke.md` apart from the log file name. It ends with How to reproduce | `python -m advisor.roles_p5.smoke --report …` |
| D14 Tests pass offline | pass | 83 passed. An autouse fixture blocks `socket.connect` | `python -m pytest tests/phase5/test_advisor_roles.py -q` |
| D15 [ops] Real vendors, post-cutoff scores, comparison against the user's verdicts on a backlog | operational_pending | Needs Phase 4 gateway keys, calendar time and a human verdict backlog | n/a |

**Open defects at final audit:** none.

**Observations (not defects):**
- The secret guard ignores env values under 8 characters (documented).
- A float `recorded_ms` is skipped, so the wiring should keep it an int.
- Rule 7 trusts a code change's declared `paths`. The LLM review still sees the diff, and a clear still needs the user's token.
- Role 30 caches error vetoes until a cap raise or a restart.

**Rules check:** WP5-D's files are all within its owned paths. No orders and no vendor calls; every LLM call goes through the injected Gateway. The smoke's fake secret lives only in `os.environ` inside try/finally. LLM output can only pull, veto or be excluded: `shrink_factor` is always 0.0, and nothing live reads role 26's output. There is no look-ahead. The code is 4 modules and 1 test file.

---

## How to reproduce

From `roster/`:

```
.venv\Scripts\python.exe -m pytest tests/phase5/test_analysis.py -q -p no:cacheprovider
.venv\Scripts\python.exe -m pytest tests/phase5/test_replay.py -q -p no:cacheprovider
.venv\Scripts\python.exe -m pytest tests/phase5/test_quote_objective.py -q -p no:cacheprovider
.venv\Scripts\python.exe -m pytest tests/phase5/test_advisor_roles.py -q -p no:cacheprovider
.venv\Scripts\python.exe -m pytest tests/phase5 -q -p no:cacheprovider
grep -rn "promote(" learning advisor/roles_p5 --exclude=loop_a.py --include=*.py
```

Smoke reports (compare with `reports/phase5_*.md`):

```
.venv\Scripts\python.exe -m learning.analyst --smoke --out build/phase-5/audit-tmp/WP5-A/smoke.md
.venv\Scripts\python.exe -m advisor.roles_p5.smoke --report build/phase-5/audit-tmp/WP5-D/smoke_r2.md --log build/phase-5/audit-tmp/WP5-D/smoke_r2.jsonl
```

Auditor scratch checks live in `build/phase-5/audit-tmp/WP5-*/`. Run them with `PYTHONPATH=.`: `check.py`, `check2.py`, `check3.py`, `fuzz_parity.py`, `stats_check.py`, `bias.py`, `probe3.py`. `ladder_probe.py` makes a public Binance GET and takes about 3 min.
