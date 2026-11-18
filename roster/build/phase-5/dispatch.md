# Phase 5 Dispatch — Full learning stack (build now, wire later)

Source: [build-plan-v4.md](../../../build-plan-v4.md) Phase 5 (tasks 5.1–5.7), [36-agent-roles-polymarket-v4.md](../../../36-agent-roles-polymarket-v4.md) (roles 02, 20, 24, 26, 30–35, the Self-learning loop and rules 1–7), the Phase 0 results in [../phase-0/audit.md](../phase-0/audit.md) and the Phase 1 contracts in [../phase-1/dispatch.md](../phase-1/dispatch.md). Process: [../README.md](../README.md).

**Built ahead of its gate (the user's decision):** in the plan, Phase 5 comes after Phase 4 and needs months of ledger data. The user chose to build every piece that can be built now as **standalone modules, and wire them in later**. In this phase:
- Nothing is called by the trading loop, places an order, or changes a live parameter.
- Every module implements against the shared contracts. It runs on fixtures, on seeded synthetic data, and on the recordings and history already on this PC.
- Anything that needs resolved clusters, live fills, vendor keys, real money or calendar time is marked **[ops]**. Auditors mark those items `operational_pending`.

Phase 5 has no exit gate. From here on, every change goes through the gate (Loop B, role 31's veto, then your token).

- Code root: `C:\Users\DELL\Downloads\saugan_pr\market_updated\roster`
- Python: `roster\.venv\Scripts\python.exe`. Run tests from the code root as `.venv\Scripts\python.exe -m pytest <path>`. Installed: numpy 2.x, scipy 1.18, pandas 3.0, duckdb, pyarrow, httpx, websockets, penaltyblog, eth-account. **Don't pip install anything.** If something truly needs a new package, put it behind an interface, mark the AC [ops] and report it.
- **Shared contracts, read-only:** `trader/contracts.py` (`MarketInfo`, `Book`, `Intent`, `Decision`, `Order`, `Fill`, `Ledger`, `Kernel`, `KernelContext`, `Router`, `Engine`) and `advisor/contracts.py` (`Gateway`, `LLMResult`, `RoleVerdict`, `CautionSignal`). Helpers in `common.py` are also read-only. If a contract is genuinely insufficient, work around it inside your package and report it. Don't edit it.
- **Read-only imports allowed:**
  - `research.kappa.kappa.clustered_mean`: the audited CR1 cluster-robust mean and SE. Use it for every clustered SE; don't write another.
  - `trader.fees.fee`: the one fee function.
  - `trader.marketdata.Books` and `trader.marketdata.market_info`: the live parsers.
  - `trader.router.PaperRouter`, for the WP5-B parity test only.
  - `trader.engines.ladder` and `trader.engines.speed`.
  - Phase 0 `history/`, `recorder/` and `research/`.
- **Running in parallel:** the Phase 1 integration owns `trader/*.py`, `trader/engines/*`, `nightly/`, `tests/invariants/` and `data/trader/`. Other phases' agents work in other folders. `learning/loop_a.py` belongs to Phase 4: don't create it.
- **This phase owns only** `learning/` (except `loop_a.py`), `advisor/roles_p5/`, `tests/phase5/` and `reports/phase5_*.md`:
  - Each work package edits only its own paths in the table below.
  - Don't edit the existing `learning/__init__.py`, `advisor/roles_p5/__init__.py` or `tests/phase5/__init__.py`.
  - Don't add a `tests/phase5/conftest.py`, because that folder is shared. Each test file keeps its own fakes and fixtures.
- **Data:** read `data/recordings/`, `data/markets/` and `data/history/` read-only. Every file a module writes takes a path argument:
  - tests use pytest's `tmp_path`
  - smoke defaults stay inside the package's own `out/` folder (listed in the table) until wiring moves them under `data/`

## Hard rules (every work package)

1. **No orders, no authenticated calls.** Never place, sign, post or cancel a real order, and never call an authenticated endpoint. Nothing in this phase needs one: replay and quoting are simulated, and the LLM roles talk only to a `Gateway` object.
2. **No paid or LLM vendor calls.** Never call an LLM vendor API or any paid service. Every LLM role is tested with a fake `Gateway` defined in its test file.
3. **Unit tests run offline.** An optional smoke run may make public read-only GETs (for example Binance klines or Deribit DVOL); unit tests may not.
4. **No secrets** in files, prompts or reports. Every report ends with "How to reproduce".
5. **Learning never promotes (rule 5).** A module may compute, trip an alarm, lock (`REDUCING` scoped to one market) or propose a **registry candidate**: a dict `{"name", "version", "params", "evidence"}`, optionally passed to `Ledger.register`, which only creates state `candidate`. No module calls `promote`, writes a live version or moves an anchor.
6. **T3/T5 trips are capped at `REDUCING`.** Their actions are `alarm`, `lock`, `pull` or `shrink`; never `halt`.
7. **Never pool across modes.** Every statistic, fit and breakdown is computed within one mode.
8. **Count clusters, not rows.** One cluster is one `event_group`. Use `clustered_mean` for SEs. A sample-size threshold counts clusters.
9. **Seeded randomness.** Every random procedure takes a `seed`, and the tests are deterministic.
10. **Minimal code.** No speculative abstractions, the fewest files, and one test file per work package covering the non-trivial logic.

## Shared input rows (what the modules consume)

Modules take plain `list[dict]` rows, the shape `Ledger.as_of()` returns (pandas inside is fine). Role 22's scorer (`nightly/scorer.py`, being built by Phase 1) will produce these rows. Its table names are not fixed yet, so mapping them is part of wiring.

- **Forecast rows** (universe checkpoints, traded or not):
  - fields: `cid, cluster_id, mode, strategy (None if untraded), traded, underlying, league, horizon_h, p, mid_ex_own, outcome (0/1 once resolved), event_ms, recorded_ms`
- **Maker order rows** (one per posted maker order, filled or not):
  - fields: `cid, cluster_id, mode, token_id, side, price, size, distance (|price − mid_ex_own| at posting), rest_ms (until fill or cancel), filled`
- **Fill rows:**
  - fields: `cid, cluster_id, mode, strategy, underlying, league, token_id, side, price, size, maker, fee, rebate, reward, ts_ms, mid_ex_own, markout_5s, markout_1m, markout_5m`
  - `markout_x` = side-signed `(mid_ex_own x later − fill price)` per share, so it **includes** the spread captured; positive is good for us
- **Closed-position rows:**
  - fields: `pos_id, cid, cluster_id, mode, strategy, underlying, league, horizon_h, side, size, entry_price, clv, markout_5m, fee_per_share, flags, outcome, pnl, primary`
  - `clv` is in probability points per share, positive = good
  - `flags` is a list of strings with prefixes `resolution:`, `wording:` or `data:`
  - `primary` is role 22's fee-net primary statistic for the position
  - `outcome`, `pnl` and `primary` depend on the outcome

## Work packages and order

| WP | Build-plan tasks | Owns | Starts after |
|---|---|---|---|
| **WP5-A** Calibration analyst, postmortems, drift and CUSUM triggers | 5.1, 5.2, 5.3 (roles 32, 33, 34, 02) | `learning/analyst.py`, `learning/postmortem.py`, `learning/cusum.py`, `tests/phase5/test_analysis.py`, `reports/phase5_analysis_smoke.md` | — |
| **WP5-B** Replay lab | 5.4 (role 35) | `learning/replay/` (package, including `learning/replay/out/`), `tests/phase5/test_replay.py`, `reports/phase5_replay_smoke.md` | — |
| **WP5-C** Quote-engine full objective | 5.5 (role 20) | `learning/quote_objective.py`, `tests/phase5/test_quote_objective.py`, `reports/phase5_quote_objective.md` | — |
| **WP5-D** Advisor roles 24, 26, 30, 31 | 5.6, 5.7 | `advisor/roles_p5/shock.py`, `advisor/roles_p5/board.py`, `advisor/roles_p5/shadow.py`, `advisor/roles_p5/smoke.py`, `advisor/roles_p5/out/`, `tests/phase5/test_advisor_roles.py`, `reports/phase5_advisor_smoke.md` | — |

All four work packages are independent and build in parallel. No work package imports another's module. **[ops]** items need keys, real money, a live venue or calendar time.

---

## WP5-A — Calibration analyst, postmortems, drift and CUSUM triggers (5.1–5.3)

**Requirements**

`learning/analyst.py` (role 32), pure functions on rows:
- **`breakdown(positions, fills)`:** per mode, and within each mode per league, underlying, horizon bucket (≤ 1h, ≤ 6h, ≤ 24h, > 24h) and strategy. Each cell reports, each with its cluster-robust SE:
  - rows and clusters
  - mean CLV
  - mean markout at 5 s, 1 m and 5 m
  - the fee-net primary statistic per cluster
  - reward and rebate income
- **`reliability(forecasts, bins=10)`:** per mode and per breakdown key, separately for the universe and for the traded subset, plus the gap between them (the selection effect). It reports:
  - per bin: mean forecast, observed frequency, rows and clusters
  - Brier and log loss of `p` and of the market baseline `mid_ex_own` on identical rows (a row missing either is dropped from both)
  - the difference between the two, with its cluster SE
- **`budget_candidate(stats, budgets, min_clusters=20, step=0.5)`**, per mode:
  - a strategy whose fee-net mean per cluster is below 0 by more than 2 SE loses `step` of its budget
  - the freed amount goes to strategies above 0 by more than 2 SE, pro rata, or is left unallocated if none qualify
  - strategies under `min_clusters` are unchanged
  - returns a registry candidate (`name = "budgets:<mode>"`) or None, and never applies it

`learning/postmortem.py` (role 33), which never reaches the sizing or gating path:
- **`BLIND_FIELDS`** = `clv, markout_5m, fee_per_share, flags, mode, strategy`. `classify(pos, sd)` reads only these fields. It never reads `outcome`, `pnl` or `primary`.
- **Classes, first match wins:**
  1. `resolution_wording`: a `resolution:` or `wording:` flag
  2. `data_provenance`: a `data:` flag
  3. `indeterminate`: |clv| ≤ sd_clv
  4. `model`: clv < −sd_clv
  5. `execution`: clv > sd_clv, and either markout_5m < −sd_markout or clv − fee_per_share < 0 (the fee was not covered)
  6. `indeterminate`: |markout_5m| ≤ sd_markout
  7. `variance`: everything else (positive CLV, clean markout, clean audit, fee covered). Not a mistake.
- **`sd`:** the sample SD (ddof = 1) of clv and of markout_5m per (mode, strategy) over the batch, or passed in. `classify_all(positions)` computes it.
- **`lessons(positions, classes, now_ms, min_clusters=20, z=1.645, by=None)`:**
  - groups by (mode, strategy, class, optional `by` key) and skips `variance` and `indeterminate`
  - the group statistic is `primary`, read only here, after classification, and fed to `clustered_mean`
  - a lesson is written only if clusters ≥ 20 **and** mean + z·SE < 0
  - lesson = registry candidate `name = "lesson:<mode>:<strategy>:<class>[:<key>=<value>]"`, with params class, clusters, mean, SE, importance = −mean/SE, created_ms and half_life_days (default 30)
  - `importance(lesson, now_ms)` = importance × 0.5^(age_days / half_life_days)

`learning/cusum.py` (roles 34 and 02):
- **`per_cluster(rows, value, key)`:** one value per cluster (the mean of its rows), in cluster close-time order, per key.
- **`standardise(x, ref_mean, ref_sd)`**, where the reference is the first `burn_in` clusters (default 20) or a registered baseline.
- **`Cusum(k=0.5, h, direction="low"|"high")`:**
  - update: S_t = max(0, S_{t−1} ∓ z_t − k); trips when S_t > h
  - once tripped it stays tripped and ignores new data until `reset()`
  - `reset()` is called only by the breaker board after it verifies a human token (Phase 1's path); this module never resets itself
- **`calibrate_h(null_z, families, k, budget=1.0, block=5, B=2000, seed)`:**
  - `families` = [(n_series, clusters_per_2_weeks), …] for the whole system
  - cluster block bootstrap: resample the standardised null series in moving blocks of `block` clusters, re-centred to mean 0 and SD 1
  - simulate every monitor in the system over 2 weeks, B times
  - return the smallest h on a 0.1 grid whose expected system-wide false trips per 2 weeks are ≤ `budget`, together with that estimated rate
- **`Monitor`:** one class for both roles, holding a `Cusum` per key. `update(key, z, now_ms)` returns None or an action `{"source": "02-cusum"|"34-drift", "scope", "action": "lock"|"alarm", "reason", "ts_ms"}`. Monitors:
  - **Role 02 locks (`lock`):** markout per market (`direction="low"`); CLV per (mode, strategy). Role 34's per-market markout drift is the same monitor, not a second one.
  - **Role 34 bias drift (`alarm`):** two one-sided CUSUMs on the standardised per-cluster bias (p − outcome), per model version, per source id and per entity (underlying, league, team).
  - **Role 34 error-correlation drift (`alarm`):** the Fisher z of the correlation between two estimators' errors over consecutive windows of W clusters, standardised against the reference window (SE 1/√(W − 3)), with high and low CUSUMs.
  - **Venue regime changes (`alarm`, immediate, no CUSUM):** `venue_changes(prev_markets, curr_markets, prev_venue, curr_venue)` compares, per mode, the modal `fee_rate`, `tick_size`, `min_size` and `source_id` across the mode's markets, plus venue fields (taker delay ms, settlement method per mode). A single market's tick change is not an alarm: role 01 already voids its clearance.
  - No action is ever `halt`.
- **Smoke:** `python -m learning.analyst --smoke` writes `reports/phase5_analysis_smoke.md` from a seeded synthetic set: 3 modes, 2 strategies, ≥ 60 clusters, a planted negative-CLV group, a planted variance group and one market whose markouts drift from cluster 50. It includes:
  - breakdown and reliability tables
  - class counts and lessons
  - the calibrated h for a stated system size, with the ARL check
  - when the planted drift tripped

**Wiring later**
- Rows come from `Ledger.as_of` and `nightly/scorer.py` once their tables are fixed.
- Monitor actions go to `kernel.trip(scope, reason, source)` and `trader/breakers.py`, through Loop B:
  - the kernel already caps AI and T5 trips at `REDUCING`
  - the CUSUM markout lock replaces the count-based blacklist (30 fills, 2 SE)
- Candidates go to `Ledger.register`.
- Report sections feed role 36's daily report.
- Copy the no-promote and outcome-blind tests into `tests/invariants/`.

**Acceptance criteria**
- **A1** Clustered SEs come from `research.kappa.kappa.clustered_mean`. Test: duplicating every row inside its own cluster leaves the SE unchanged, while counting the duplicates as new clusters shrinks it.
- **A2** Breakdowns never pool modes. Test: every output row carries exactly one mode, and a two-mode fixture's numbers per mode equal those computed on each mode alone.
- **A3** Reliability (test):
  - on synthetic calibrated forecasts (y ~ Bernoulli(p), seeded), every bin's frequency is within 3 SE of its mean forecast
  - forecast and baseline scores use identical rows
  - universe, traded subset and gap are all reported
- **A4** Budget candidate (test + grep):
  - the total never rises, and no budget goes below 0
  - a strategy under `min_clusters` is unchanged
  - the result is a candidate dict
  - `grep -n "promote(" learning/analyst.py learning/postmortem.py learning/cusum.py` finds nothing
- **A5** Outcome-blind:
  - test: over 1,000 random positions, flipping `outcome` and negating `pnl` and `primary` changes no class
  - code read: `classify` touches only `BLIND_FIELDS`
- **A6** Truth table (test): one fixture per rule 1–7 gets its class, including precedence (a `resolution:` flag beats negative CLV; positive CLV with the fee not covered → `execution`).
- **A7** Lessons (tests):
  - 20 clusters with a significantly negative mean → one lesson
  - 19 such clusters → none
  - 20 clusters, negative but not significant → none
  - 60 rows in 5 clusters → none
  - `variance` and `indeterminate` groups never produce a lesson
  - importance halves at the half-life
- **A8** CUSUM ARL (test, seeded): the simulated one-sided in-control ARL for k = 0.5, h = 4 on iid N(0,1) is within 10% of Siegmund's approximation (e^{2kb} − 2kb − 1)/(2k²) with b = h + 1.166, which is ≈ 338.
- **A9** Threshold (tests): for an iid null with families [(50, 14)], the calibrated h gives ≤ 1.2 system-wide false trips per 2 weeks on a fresh simulation with another seed (≤ 1 plus Monte Carlo error). h rises with n_series. h for an AR(1) null with φ = 0.5 is above the iid h.
- **A10** Trips (test + grep):
  - a tripped monitor stays tripped through 100 later good observations until `reset()`
  - a planted −1 SD shift from cluster 50 trips the markout lock after cluster 50 and within 30 clusters of it, at the calibrated h
  - no code path emits `halt`
- **A11** Drift-watch (tests):
  - bias drift fires for a planted biased entity and for no other entity
  - the error-correlation monitor fires when the correlation moves from 0 to 0.8
  - `venue_changes` alarms on a mode-wide fee change and on a taker-delay change, but not on one market's tick change
- **A12** `python -m learning.analyst --smoke` writes `reports/phase5_analysis_smoke.md` with every section listed above, and the planted effects are found: a lesson for the planted group, none for the variance group, and the drift's trip cluster. It ends with "How to reproduce".
- **A13** `python -m pytest tests/phase5/test_analysis.py -q` passes offline.
- **A14 [ops]**
  - run on real ledger rows once groups reach ≥ 20 resolved clusters (about 1 crypto cluster a day)
  - calibrate h on real per-cluster series
  - confirm ≤ 1 false reset per 2 weeks in operation

## WP5-B — Replay lab (5.4)

**Requirements** (package `learning/replay/`, with `events.py`, `fills.py`, `run.py` and `validate.py`; merge files if that is shorter; CLI `python -m learning.replay`)

Event store (`events.py`):
- **Recorder input:** reads the recorder's files (`data/recordings/<stream>/<date>/<HH>.jsonl` and `data/recordings/parquet/stream=*/date=*/*.parquet`, rows `{t, raw}`) and parses them with **`trader.marketdata.Books.apply(raw, t)`**, the parser the live loop uses. `recorded_ms` = `t` (local receive time) and `event_ms` = the message `timestamp`.
- **Markets:** `MarketInfo` comes from the crawler snapshot in force at each time (`data/markets/<ts>Z.jsonl`, through `trader.marketdata.market_info`).
- **Reference feed:**
  - Binance 1m closes from `data/history/binance/` (or a `{ts_ms, price}` list); a candle's `recorded_ms` is its close time
  - DVOL from `data/history/deribit/`
  - the smoke may fetch the missing window by a public GET
- **`as_of(t)`:** books, trades, reference values and markets as known at t. It only uses events with `recorded_ms ≤ t`.

**Look-ahead tripwire:** before every engine call at decision time t, every input must have been recorded by t:
- each `Book.ts_ms`
- each reference `ts_ms`
- the `MarketInfo` snapshot time
- the recorded time of every `ref[asset]["final"]` value

Any input recorded after t raises `LookAheadError`. The run fails and writes no report.

Fill model (`fills.py`): standalone, with the role 05 paper rules from `trader/router.py`'s docstring.
- **Maker:**
  - live from created + rtt; post-only, so refused if it would cross at posting
  - queue ahead = the displayed size at its price at posting, excluding our own orders
  - **`mode="strict"`** (default, the same as paper mode): fills its whole remaining size on a trade strictly through its price, or once volume traded at its price by the other side reaches queue ahead + own size
  - **`mode="queue"`**: displayed size at its price that disappears without a trade moves the order up the queue by `cancel_ahead` × the drop, and volume beyond the queue fills it partially
- **Taker:** arrives at decision + 150 ms + rtt and fills against the book in force at arrival, level by level up to its limit and size. The rest is killed. The fee is `trader.fees.fee` per level.
- **The three Phase 1 execution issues, fixed here** (`trader/router.py` belongs to Phase 1):
  1. a maker never fills on a trade at or after its GTD expiry
  2. liquidity is used once: a taker's fills deplete the levels it took for later takers until that token's next book update, and one trade's volume is allocated once across our makers at that price, oldest first
  3. a taker arriving with no book in force, or past its give-up time, is killed with zero fill

Runner (`run.py`), `replay(engine, store, start_ms, end_ms, rtt_ms, kernel=None, outcomes=None)`:
- **Ticks:** calls the **unmodified** engine's `on_tick(now_ms, markets, books, ref, positions)` on every reference update and every book update for a market the engine trades, as the live loop does.
- **Orders:**
  - maker targets are diffed against resting orders by (token, side, price, size): cancel what is no longer targeted, submit what is new
  - taker intents are submitted at once
  - every intent goes through `kernel.check(intent, ctx)` when a kernel is given
  - the engine's `on_fill` is called if it exists
- **Output:** intents, decisions, orders, fills (`Fill`), positions, and fee-net P&L per cluster. P&L uses `outcomes` {cid: 0|1} where known; otherwise the position is marked at the last `mid_ex_own` and flagged unresolved.
- **Labelling:** every result is labelled *exploratory*. Statistics use `clustered_mean`.

Validation (`validate.py`, numpy, scipy and pandas only):
- **`walk_forward(clusters, n_folds, embargo_ms)`:**
  - clusters = (cluster_id, first_decision_ms, resolve_ms), ordered by first decision
  - test folds are consecutive blocks of clusters, and a cluster is never split
  - a fold trains only on clusters with resolve_ms < test_start − embargo_ms; any cluster still unresolved then is purged
- **`nested_select(...)`:** model selection runs an inner walk-forward inside each outer training set. The outer test fold scores only the selected trial.
- **`cpcv(clusters, n_groups, k_test, embargo_ms)`:**
  - C(n_groups, k_test) splits
  - training drops clusters whose [first_decision, resolve] interval overlaps a test group's span
  - training also drops clusters starting within the embargo after a test group
- **`deflated_sharpe(returns, sr_trials)`** (Bailey & López de Prado 2014):
  - DSR = Φ((SR̂ − SR₀)·√(T−1) / √(1 − γ₃·SR̂ + (γ₄ − 1)/4·SR̂²))
  - SR₀ = √V·((1 − γ)·Φ⁻¹(1 − 1/N) + γ·Φ⁻¹(1 − 1/(N·e)))
  - SR̂ is the per-period Sharpe over T clusters; γ₃ is skewness; γ₄ is kurtosis (normal = 3); γ = 0.5772156649
  - V is the variance of the N trials' Sharpes; N = 1 → SR₀ = 0
- **`pbo(perf, S=16)`** (CSCV, Bailey et al. 2014):
  - split the T × N performance matrix into S contiguous blocks
  - for each of the C(S, S/2) in-sample halves, take the in-sample best trial and its out-of-sample relative rank ω = rank/(N + 1), and compute λ = ln(ω/(1 − ω))
  - PBO = the share of splits with λ ≤ 0
- **`random_entry(store, result, R, seed)`:**
  - R baseline runs that keep each cluster's number of entries and their sizes
  - entry times uniform in the market's tradable window; side 50/50
  - filled as takers through the same fill model and fees, and held as the strategy holds
  - returns the baseline distribution and the strategy's percentile
- **`TrialLog(path)`:**
  - append-only JSONL, one row per trial, failed and discarded trials included
  - each row: trial id, family, params hash, dataset hash, statistic, Sharpe, clusters, ts
  - `count(family)` and `sharpes(family)` give the DSR its N and V

**Smoke data on this PC:** about 2 minutes of recorded books (2026-09-30 14:29 UTC, Parquet). Binance 1m history ends 2026-09-29, so the smoke may fetch that window's klines by a public GET, in memory, writing nothing outside `learning/replay/out/`. If it can't, the report says so.

**Wiring later**
- The nightly job runs the lab (the plan's `nightly/replay/`, importing `learning.replay`).
- Its fill model, or its three fixes, replaces `trader/router.py`'s simulator through role 31 and your token, so paper and replay stay identical.
- The maker diff is shared with `trader/loop.py`.
- Loop B candidates are replayed (exploratory evidence) before shadow.
- Task 2.8's canary interval is computed from `mode="queue"` replays.

**Acceptance criteria**
- **B1** The store parses the recorded hour `data/recordings/parquet/stream=crypto-term/date=2026-09-30/14.parquet` through `trader.marketdata.Books`. Test: a book the store rebuilds at time t equals the result of applying the same raw messages to `Books` directly up to t (fixture, plus the smoke on the real file).
- **B2** Test: `as_of(t)` never returns an event with `recorded_ms > t`, including a message whose `event_ms ≤ t` but which was recorded late.
- **B3** Tripwire (test): a leaky feeder (a book with `ts_ms > now`, or a `final` value whose candle closed after now) raises `LookAheadError`, and no report is written. A clean run records 0 violations.
- **B4** Strict-mode parity (test): the fill model's fills equal `trader.router.PaperRouter`'s (imported read-only, journal in `tmp_path`) on fixtures covering:
  - a maker filled by a trade through its price
  - a maker at the touch filled only after queue ahead + own size traded
  - a taker filled at the arrival-time book, partially when size is short
  - taker fees
- **B5** The three fixes (tests):
  - no maker fill on a trade at or after its expiry
  - two takers arriving before the next book update cannot both take the same level's size
  - one trade's volume fills our makers at that price only once, oldest first
  - a taker arriving with no book is killed with zero fill
- **B6** Queue mode (test):
  - a displayed drop ahead without trades advances the queue by `cancel_ahead` × the drop
  - volume beyond the queue fills partially
  - with `cancel_ahead = 0`, the total filled equals strict mode's once queue ahead + own size has traded
- **B7** Runner (test): a scripted fake `Engine` (maker targets that change once, plus one taker intent) produces the expected cancels, submissions and fills. `on_tick` receives exactly the `Engine` protocol's arguments. A fake `Kernel` that rejects one intent stops that intent.
- **B8** Walk-forward (test, plus a property test over 200 random cluster sets): no training cluster has resolve_ms ≥ test start − embargo; no cluster is in both train and test; test folds run in time order.
- **B9** Nested selection (test): the selector never receives outer-test clusters (assert on the indices it saw), and a trial that is best only on the outer test data is not selected.
- **B10** CPCV (test): N = 6, k = 2 gives 15 splits; each group is a test group in exactly 5 splits; no training cluster overlaps a test span or falls in its embargo.
- **B11** DSR (test):
  - SR̂ = 0.10, T = 250, γ₃ = 0, γ₄ = 3, N = 10, SD of the trial Sharpes 0.05 → SR₀ = 0.07873 and DSR = 0.6311 (± 1e-3)
  - N = 1 gives PSR(0) = 0.9423
  - DSR falls as N or V rises
- **B12** PBO (test, seeded): pure-noise trials (N = 50, T = 1,000, S = 16) give PBO in [0.3, 0.7]. One trial with a consistent edge of ≥ 0.2 SD per period among noise trials gives PBO ≤ 0.1.
- **B13** Test: random-entry baselines keep each cluster's entry count and sizes, use the same fill model and fees (fees > 0), and are reproducible by seed.
- **B14** Trial log (test + code read): every run, failed ones included, appends one row. The DSR's N equals the family's row count. Earlier lines are byte-identical after more runs. No code path rewrites or deletes the log.
- **B15** Smoke: `python -m learning.replay --engine ladder` and `--engine speed` on the recorded window use the real `trader.engines` classes unmodified, finish with 0 tripwire violations, and write `reports/phase5_replay_smoke.md` with:
  - events read per type
  - intents, kernel decisions, and fills (maker and taker)
  - fees
  - the per-cluster statistic (exploratory)
  - the random-entry percentile and the trial count
  - DSR and PBO on a seeded synthetic trial set
  - "How to reproduce"

  Zero intents is acceptable only if the report says why (for example, no reference ticks in the window).
- **B16** No order path (grep): `grep -rnE "^\s*(import|from)\s+(httpx|urllib|requests|websockets|socket|py_clob_client|eth_account|trader\.live|tools)" learning/replay` finds nothing. The smoke's optional public GET goes through `common.get_json`.
- **B17** `python -m pytest tests/phase5/test_replay.py -q` passes offline.
- **B18 [ops]**
  - replay over ≥ 7 recorded days, once the recorder runs on the VM
  - the canary check of task 2.8 (live fill rate and 5m markout per queue bucket inside replay's 90% interval over ≥ 30 fill clusters) needs live fills, which need keys and money

## WP5-C — Quote-engine full objective (5.5)

**Requirements** (`learning/quote_objective.py`: pure functions, no I/O outside the smoke)
- **Reward score:** the Polymarket liquidity-rewards formula. Re-verify it against the venue's rewards docs; a test pins it.
  - S(v, s) = ((v − s)/v)² for s < v, else 0, where s = an order's distance from the mid and v = `reward_max_spread`, both in cents. An order below `reward_min_size` scores 0.
  - Q_one = Σ S·size over YES bids and NO asks. Q_two = Σ S·size over YES asks and NO bids. A NO bid at x is a YES ask at 1 − x.
  - Q_min = max(min(Q_one, Q_two), max(Q_one/c, Q_two/c)) when 0.10 ≤ mid ≤ 0.90, else min(Q_one, Q_two); c = 3 (a registry parameter).
  - Reward = `reward_daily_rate` × τ/86,400 × Q_ours / (Q_ours + Q_others).
  - Q_others = Σ S·size over the displayed non-own size within v on both sides. The book doesn't say who owns what, so this overstates competition and keeps the term conservative.
- **Fill rate:** λ(d) = A·e^(−k·d) per second at distance d from `mid_ex_own`; fill probability over horizon τ is P = 1 − e^(−λτ). `fit_fill_rate(orders)` is a Poisson maximum-likelihood fit on maker order rows (scipy): log L = Σ [filled·ln λᵢ − λᵢ·restᵢ].
- **Adverse move:** a(d) = m₀ + m₁·d per share, fitted by OLS on maker fills, where a = markout_5m − (side-signed distance captured at the fill). A fill row's markout already includes the spread, so this term is the mid move only and nothing is counted twice.
- **Fits per market:**
  - a market with fewer than `min_clusters` (default 30) clusters uses its mode's fit; a mode without enough uses registered priors (Phase 1's `markout_prior`)
  - never pooled across modes
  - every fit is returned as a registry candidate (`name = "quote-objective:<cid|mode>"`) and is not applied by this module
- **Objective** for one market, in Phase 1's convention (bids only: BUY YES at price x_Y and BUY NO at price x_N; I = YES − NO shares held):
  - J = reward + Σ_{s∈{Y,N}} Pₛ·sizeₛ·(edgeₛ + rebateₛ + a(dₛ)) − γ·σ²·τ·(I + size_Y·P_Y − size_N·P_N)²
  - edge_Y = q − x_Y and edge_N = (1 − q) − x_N, where q is role 23's shrunk fair value
  - rebate = `rebateRate` × `trader.fees.fee(1, x, fee_rate)`
  - σ = mid volatility per √s, in probability units
  - τ = seconds to the next requote or the pull time before close, whichever is first
- **Optimiser:**
  - grid search over prices on the tick grid within d_max ticks of the mid, and sizes in {0} ∪ [min_size … inventory limit]
  - BUY prices rounded down, and never at or above the token's best ask (post-only)
  - sizes floored to 0.01; sub-minimum sizes dropped
  - Phase 1's complement cap (holding one outcome bought at p, bid the other strictly below 1 − p − margin) and the inventory limit (|I| after a fill) both bind
  - returns `[(token, price, size, reduces_exposure)]` (the shape of `trader.engines.ladder.quotes()`) plus the breakdown of each term; if J ≤ 0 everywhere, it returns no quote
  - Phase 1's pull rules still run first
- **Anchor rule (Loop A, rule 7):** `wider(a, b)` keeps, per token, the lower price and the smaller size, and drops a token quoted by only one of the two. Quotes from current parameters pass through `wider(current, anchor)`.
- **Smoke:** `python -m learning.quote_objective --smoke` writes `reports/phase5_quote_objective.md` using:
  - markets from the latest `data/markets/` snapshot (real tick, fee, rebate and reward parameters)
  - recorded books where available
  - stated synthetic or prior fill and markout parameters

  For each sample market it shows the chosen quote and each term, next to Phase 1's `quotes()` on the same inputs.

**Wiring later**
- `LadderEngine` calls the objective in place of `quotes()` once the objective passes Loop B (replay → shadow → canary → your token).
- Fits come from `nightly/scorer.py`'s order and fill rows.
- `wider()` runs with Phase 4's `learning/loop_a.py` anchors.

**Acceptance criteria**
- **C1** S(v, s) (test): v = 4.5 and s = 1.5 → (3/4.5)² = 0.4444; s ≥ v → 0; size below `reward_min_size` → 0.
- **C2** Q_min (test): with the mid in [0.10, 0.90], one-sided Q → Q/3 and two-sided → max(min, max/3); with the mid outside that band, one-sided → 0.
- **C3** Reward term (test): a zero `reward_daily_rate` gives 0 (every target market today, per Phase 0); the share Q_ours/(Q_ours + Q_others) matches a hand-computed fixture.
- **C4** Fits (test, seeded): `fit_fill_rate` recovers A and k within 10% on ≥ 2,000 censored synthetic orders from λ = A·e^(−kd); the adverse-move fit recovers m₀ and m₁ within 2 SE.
- **C5** Test: a market under `min_clusters` uses its mode's fit, and a two-mode fixture shows no pooling.
- **C6** Test: with q = mid, no reward, no rebate, a = 0 and γ = 0 (small λτ), the chosen distance is within one tick of 1/k.
- **C7** Comparative statics (tests):
  - a more negative adverse move gives the same or a lower price, or a smaller size
  - with I > 0 the NO bid is no further from its mid than the YES bid, and a large γ takes the YES size to 0
  - a larger σ or τ never tightens a quote
  - with a = 0 the fill term equals Σ P·size·(edge + rebate) exactly (no double count)
- **C8** Output (test): prices on the tick grid; BUY rounded down; never at or above the best ask; sizes floored and ≥ `min_size`; |I| after a fill within the limit; the complement cap binds.
- **C9** Anchor (test): `wider(a, b)` never returns a price or size above either input and drops one-sided tokens. A chain of 10 ever-tighter refits passed through `wider(·, anchor)` never quotes tighter than the anchor.
- **C10** Grep: fits are candidate dicts, and `grep -n "promote(\|\.register(\|\.record(" learning/quote_objective.py` finds nothing.
- **C11** `python -m learning.quote_objective --smoke` writes `reports/phase5_quote_objective.md` with the sections above, ending with "How to reproduce".
- **C12** `python -m pytest tests/phase5/test_quote_objective.py -q` passes offline.
- **C13 [ops]**
  - per-market fits from role 22's paper and live maker fills (weeks of data)
  - non-zero reward terms need reward-paying markets (none among today's targets)
  - live use only through Loop B and your token

## WP5-D — Advisor roles 24, 26, 30, 31 (5.6, 5.7)

**Requirements**

Common rules (from `advisor/contracts.py`):
- **Gateway only:** each role talks only to a `Gateway` (`complete`, `quota_left`), never to a vendor SDK or HTTP.
- **Validate answers:** each role checks the returned `data` against its own schema.
- **Public text only:** prompts carry public market or news text only. Never sides, sizes, prices paid, balances, positions, P&L, evidence statistics or caps.
- **Secret guard:** a prompt containing the value of any set environment variable whose name contains KEY, SECRET, PASS or TOKEN is not sent, and the role returns its fail-closed result.
- **Fail closed:** `ok=False`, a missing or wrongly typed field, an exhausted quota, or too few usable answers mean:
  - roles 30 and 31: **veto**
  - role 24: **pull**
  - role 26: the answer is **excluded**
- **Prompts** are module constants, and each module exposes `PROMPT_SHA256` so the audit log (role 04) can stamp the prompt version.

`advisor/roles_p5/shock.py`, role 24's LLM part (unscheduled shocks). `ShockReader.read(items, now_ms, gw) -> list[CautionSignal]`:
- **Input:** news items `{id, source, ts_ms, recorded_ms, title, body}`. Items recorded after `now_ms` are ignored.
- **Prefilter:** a keyword prefilter on title and body (hack, exploit, drained, depeg, insolvent, bankrupt, withdrawals halted, paused or suspended, delist, ban, charges, emergency, outage). An item that matches nothing makes no gateway call.
- **LLM call** on a matched item: `gw.complete("24-crypto-shock", prompt, schema, vendors=1)` with schema `{is_shock: bool, underlyings: [BTC|ETH|SOL|XRP|ALL], severity: low|medium|high, reason: str}`.
- **Signals:**
  - a confirmed shock → a `pull` per affected enabled underlying ("ALL" → each one), with `shrink_factor` 0.0, `resume_requires_fresh_observation` True and an expiry by severity
  - not a shock → no signal
  - a failure after a keyword match → `pull` on every enabled underlying
- **No direction:** the output carries no direction, and any extra field from the vendor is dropped.

`advisor/roles_p5/board.py`, roles 30 and 31 (veto only, returning `RoleVerdict`):
- **Role 30, `CorrelationAdversary.review(group, group_markets, exposed_groups, cap, gw)`:**
  - runs once per new event-group exposure: the first entry into a group, or a raise of its cap
  - verdicts are cached by (group, cap); a repeat with the same or a lower cap makes no gateway call
  - the prompt carries only the new group's question and rules text and the questions of the currently exposed groups; `cap` is a cache key only
  - 2 distinct vendors, schema `{verdict, hidden_links: [{other_group, mechanism}]}`
  - clear only if both vendors return a valid clear answer with no links; anything else is a veto, with each (vendor, clear|veto|error) in `vendor_votes` and the links in `reasons`
- **Role 31, `ChangeGate.review(change, gw)`:**
  - `change` = `{kind: code|learned, name, paths, diff, old, new, prereg, evidence}`
  - **Deterministic first.** `rule7(change)` lists everything that can raise |edge|, size, a budget or quote aggressiveness, or weaken a cautious component:
    - a direction table for the known Phase 1 and Phase 5 parameters (for example `quote_size`, `max_inv`, `kelly_cap`, `c_shrink`, `max_markets`, `max_price`, `reward_share`, budgets: up is flagged; `half_min`, `k_unc`, `k_vol`, `complement_margin`, `pull_before_close_ms`, `gamma`: down is flagged; `move_k`, `book_stale_ms`, `ref_stale_ms`: up is flagged)
    - any κ change and any unknown parameter are flagged
    - a code change touching T0 (`trader/kernel.py`, `breakers.py`, `router.py`, `audit.py`, `ledger.py`, `reconciler.py`, a live router or the settlement keeper) or the sizer is always flagged
  - **Evidence check:** a flagged learned change needs a pre-registration, evidence collected at its pre-registered n, and a recorded pass. Otherwise it is vetoed with no LLM call.
  - **LLM review:** 2 vendors review the diff or the parameter change against the invariant list (AI can't raise size; never round up; halt = confirmed cancel-all; no retry on unknown state; journal before send; one fee function; live only behind three flags; LLM output only shrinks, pulls or vetoes) and rule 7. Schema `{verdict, violations: [str]}`. Any veto or error → veto.
  - **The prompt** never contains evidence numbers.
  - **A clear verdict** lists "pass still needs a human token" in its reasons. The module has no path to promote or to write the registry.

`advisor/roles_p5/shadow.py`, role 26, a permanent shadow forecaster:
- **`forecast(market, now_ms, gw, n_vendors=6)`:**
  - asks 4–10 distinct vendors for `{p: 0..1, rationale}`
  - the prompt carries the question, rules text and end date only, never the market price
  - invalid answers are dropped; fewer than `min_models` (4) usable answers → a row with status `insufficient` and no forecast
- **Combining:**
  - median (default) or 10% trimmed mean
  - Platt map p_cal = σ(a + b·logit p), with (a, b) from `fit_platt(resolved_rows)` (logistic regression, scipy) once ≥ 100 resolved rows exist, identity before that
  - extremes capped to [0.03, 0.97]
  - market-blended prior: logit q = logit m + w·(logit p_cal − logit m), with w = 0.3
- **Research log:** one append-only JSON line per forecast, written to a path argument (default `advisor/roles_p5/out/shadow_research.jsonl`). Each line has event_ms, recorded_ms, cid, cluster_id, each model's (vendor, model, p or error), the combined, calibrated and blended values, the method and the prompt hash.
- **`score(rows, outcomes, cutoffs)`:** Brier and log loss per model and for the ensemble, against the market mid at forecast time, with `clustered_mean` SEs. A model is scored only on markets that resolved after its own training cutoff; a model with no cutoff is not scored.
- **`error_correlation(rows, outcomes)`:** the matrix of correlations between the models' errors, and N_eff = N / (1 + (N − 1)·ρ̄), where ρ̄ is the mean off-diagonal correlation, floored at 0.
- **`run_batch(markets, now_ms, gw, max_markets)`:** a small daily batch that stops when fewer than `min_models` vendors have quota left.
- **Nothing live reads it:** roles 20, 21 and 23 never read its output, and no module outside `advisor/roles_p5/` imports it.

`advisor/roles_p5/smoke.py`: `python -m advisor.roles_p5.smoke` runs all four roles against a scripted fake gateway. It uses public question and rules text from the latest `data/markets/` snapshot and sample headlines, and writes `reports/phase5_advisor_smoke.md`.

**Wiring later**
- The roles run in the advisor process, behind Phase 4's real gateway, which implements `Gateway`.
- Role 24's signals go to `advice.db`, and the trader pulls on them.
- Role 30 runs at the kernel's first entry into a group or a cap raise, and a veto means "not cleared".
- Role 31 becomes a required step before any `promote`, still followed by your token.
- Role 26's log moves to a ledger table that nothing in the trader reads.

**Acceptance criteria**
- **D1** Grep: `grep -rnE "^\s*(import|from)\s+(httpx|urllib|requests|aiohttp|websockets|socket|openai|anthropic|google|groq)" advisor/roles_p5` finds nothing.
- **D2** Prompt hygiene (test):
  - inputs carry sentinel values for size, price paid, balance, P&L, evidence and cap
  - a fake env var `POLY_API_SECRET` holds a sentinel
  - the fake gateway records every prompt: no sentinel appears in any of them, and a prompt that would contain the env value is never sent (the role returns its fail-closed result)
- **D3** Fail closed, per role (test): `ok=False`, malformed data, a missing field and an exhausted quota each give:
  - roles 30 and 31: a veto
  - role 24: a pull on every enabled underlying
  - role 26: an excluded model, and `insufficient` below `min_models`
- **D4** Role 24 (tests):
  - an unmatched item makes 0 gateway calls
  - a confirmed ETH shock → one `pull` scoped "ETH", with `shrink_factor` ≤ 1 and resume-on-fresh-observation True
  - "ALL" → one signal per enabled underlying
  - not a shock → no signal
  - no signal carries a direction even when the fake vendor sends one
  - an item recorded after `now_ms` is ignored
- **D5** Role 30 (tests): 100 reviews of the same group and cap make 1 gateway call; a cap raise makes a new one; clear needs 2 distinct vendors, both clear, with no links; one veto or one error → veto; the cap never appears in a prompt.
- **D6** Role 31, rule 7 (tests): these are flagged:
  - raising `quote_size`, a budget or `c_shrink`
  - lowering `half_min` or `complement_margin`
  - raising `move_k`
  - any κ change
  - an unknown parameter
  - a code change touching `trader/kernel.py`

  Lowering `quote_size` is not flagged.
- **D7** Role 31, evidence (tests): a flagged learned change without a pre-registration, below its n, or with a failed test is vetoed with 0 gateway calls. With complete passing evidence, the 2-vendor review runs, and a clear verdict's reasons contain "human token". Evidence numbers never reach a prompt.
- **D8** Grep: `grep -n "promote(\|\.register(\|\.record(" advisor/roles_p5/board.py` finds nothing.
- **D9** Role 26, ensemble (tests): median and trimmed mean match hand values; fewer than 4 valid answers → `insufficient` and no forecast; caps clip to [0.03, 0.97]; the market mid never appears in a prompt.
- **D10** Platt (test, seeded): `fit_platt` recovers known (a, b) within 0.1 on 2,000 synthetic rows, and is the identity below 100 resolved rows.
- **D11** Scoring and correlation (tests): a model is scored only on markets resolved after its cutoff (a fixture with one market before the cutoff and one after); N_eff = 1 for identical models, and within 10% of N for independent synthetic models.
- **D12** Permanent shadow (test + grep): the research log's earlier lines are byte-identical after more forecasts, and `grep -rn "roles_p5.shadow\|shadow_research" trader learning nightly --include=*.py` finds nothing.
- **D13** `python -m advisor.roles_p5.smoke` writes `reports/phase5_advisor_smoke.md` with each role's gateway calls, verdicts or signals, and fail-closed cases. It ends with "How to reproduce".
- **D14** `python -m pytest tests/phase5/test_advisor_roles.py -q` passes offline.
- **D15 [ops]**
  - real vendor calls need Phase 4's gateway and free-tier API keys (none on this machine)
  - shadow scores need markets that resolve after each model's cutoff (calendar time)
  - role 30 and role 31 verdicts should be compared against yours on a backlog before they are relied on

## Phase 5 checks (orchestrator)

- `python -m pytest tests/phase5 -q` passes.
- No file outside the owned roots is created or changed. Each builder lists every file it wrote, and the auditor checks the list against the table.
- `grep -rn "promote(" learning advisor/roles_p5 --exclude=loop_a.py` finds nothing (hard rule 5).
- Every [ops] item is listed in `phase-5/audit.md` as `operational_pending`, with what it waits for.
