# Phase 1 Dispatch — Paper trading (no keys, no real money)

Source: [build-plan-v4.md](../../../build-plan-v4.md) Phase 1 (tasks 1.1–1.20), [36-agent-roles-polymarket-v4.md](../../../36-agent-roles-polymarket-v4.md), and the Phase 0 results in [../phase-0/audit.md](../phase-0/audit.md). Process: [../README.md](../README.md).

**Gate override (the user's decision):** Phase 0's exit gate was not met. The user chose to start Phase 1 anyway, in paper only, with **two strategies side by side**:
- **ladder-maker:** strategy 1, maker quotes on BTC/ETH daily strike ladders and daily Up/Down. Its Phase 0 κ test failed, so it is registered as a `candidate`; paper trading measures whether it also loses after adverse selection.
- **btc-speed:** BTC-only taker on 5m/15m Up/Down after causal Binance moves. It is the only Phase 0 test that passed (+2.02¢ ± 0.34¢ on free data, BTC only). Paper trading measures the real latency from this PC.

Post-close capture is **not** built (its Phase 0 measurement failed: 0.9% of prints). Everything runs on the user's Windows PC; no VM.

- Code root: `C:\Users\DELL\Downloads\saugan_pr\market_updated\roster`
- Python: `roster\.venv\Scripts\python.exe` (same packages as Phase 0)
- **Shared contracts:** `roster/trader/contracts.py`, read-only. Every work package implements against these types and protocols (`MarketInfo`, `Book`, `Intent`, `Decision`, `Order`, `Fill`, `KernelContext`, `Ledger`, `Kernel`, `Router`, `Engine`). If a contract is genuinely insufficient, work around it inside your package and report it; don't edit it.
- Phase 0 code (`recorder/`, `history/`, `research/`) may be imported read-only. Don't edit it.

## Work packages and order

| WP | Build-plan tasks | Owns | Starts after |
|---|---|---|---|
| **WP1-A** Core: fees, ledger, audit log | 1.1, 1.2, 1.3 | `trader/fees.py`, `trader/ledger.py`, `trader/audit.py`, `trader/tests/test_core.py` | — |
| **WP1-B** Kernel, breakers, clearances | 1.14, 1.15, 1.17 | `trader/kernel.py`, `trader/breakers.py`, `tools/clearance_cli.py`, `trader/tests/test_kernel.py` | — |
| **WP1-C** Market data, paper execution, reconciliation | 1.4, 1.5, 1.7, 1.16 | `trader/marketdata.py`, `trader/router.py`, `trader/reconciler.py`, `trader/tests/test_execution.py` | — |
| **WP1-D** Ladder-maker strategy | 1.6, 1.8–1.13 | `trader/engines/ladder.py` (and helpers in `trader/engines/`), `trader/tests/test_ladder.py` | — |
| **WP1-E** BTC-speed strategy | new (from Phase 0 test 0.12) | `trader/engines/speed.py`, `trader/tests/test_speed.py` | — |
| **WP1-F** Integration, scoring, ops, drills | 1.18, 1.19, 1.20, invariant suite | `trader/loop.py`, `nightly/`, `tests/invariants/`, `reports/phase1_*.md`, `data/trader/` | WP1-A … WP1-E |

WP1-A to E build in parallel against the contracts, using fakes for the other packages in their own tests. WP1-F wires the real pieces together. **[ops]** items need real running time; auditors mark them `operational_pending`.

---

## WP1-A — Core: fees, ledger, audit log (1.1–1.3)

**Requirements**
- `trader/fees.py`: `fee(C, p, rate)` = C × rate × p(1−p). Refuses taker orders on schedules with unmodelled fields.
- `trader/ledger.py`: SQLite `data/trader/trader.db` implementing the `Ledger` protocol: bitemporal rows (event_ms, recorded_ms), `as_of()`, a cluster id on forecasts and fills, a registry of versioned parameter sets with states `candidate → shadow → canary → live → retired` and a gated anchor per name, and immutable pre-registrations. Promotion to `live` needs a human token with an unused nonce.
- `trader/audit.py`: append-only audit log with a hash chain (each record carries the previous record's hash). Any failed write raises, so the caller can halt.

**Acceptance criteria**
- **A1** `fee()` matches hand-computed values at p = 0.1, 0.5 and 0.9 for rates 0.07 and 0.05; an unmodelled schedule field is refused.
- **A2** `as_of(t)` never returns a row recorded after t (test).
- **A3** Registry: versions move through the states; promotion to `live` without a valid unused nonce is refused, and a reused nonce is refused; the anchor is kept.
- **A4** Pre-registrations cannot be changed or deleted once written (test).
- **A5** Audit log: tampering with any record is detected by verifying the chain; a failed write raises (test).
- **A6** Tests in `trader/tests/test_core.py` pass.

## WP1-B — Kernel, breakers, clearances (1.14, 1.15, 1.17)

**Requirements**
- `trader/kernel.py` implementing `Kernel`:
  - states `ACTIVE` / `REDUCING` (only exposure-reducing orders) / `HALTED` (no new orders); trips from AI sources are capped at `REDUCING`
  - caps on worst-case exposure per event group and per-strategy budgets, recording the binding cap in each `Decision`
  - the clearance check: a clearance is valid only if its key (template, rules hash, fee params, tick, min size, negRisk flag, source id) equals the latest `MarketInfo`; a tick change voids it; missing or expired means not cleared
  - `provenance_checks()`: source id matches the market's rules source; every feed is within its staleness bound; a basis adjustment is present when USD-index inputs price a USDT-settled market
  - the resting-order rule: maker expiry ≤ min(market end − 2 min, start − 5 min if a start exists) and ≥ now + 2 min + margin
  - refuse new risk when bankroll exceeds 1.1× the global cap; bankroll = redeemable pUSD + positions at best bid
- `trader/breakers.py`: manual halt, stale-feed trip, daily drawdown marked at best bid → `REDUCING`, and the markout blacklist (a market whose mean 5m markout over its last 30 fills is below zero by more than 2 SE is locked for quoting). Resets need a human token with an unused nonce.
- `tools/clearance_cli.py`: you sign clearance records with a nonce into `data/trader/advice.db`. The trader only reads this file.

**Acceptance criteria**
- **B1** State rules: `REDUCING` rejects a risk-increasing intent and accepts a reducing one; `HALTED` rejects all new intents; an AI-source trip never reaches `HALTED`.
- **B2** An intent over an event-group cap or a strategy budget is rejected, and the `Decision` names the binding cap.
- **B3** Clearance: valid key → approved; changed rules hash, tick or fee → rejected; missing or expired → rejected.
- **B4** Each provenance check has a failing-input test.
- **B5** GTD rule: a resting expiry past the allowed bound is rejected.
- **B6** The 1.1× cap refusal works.
- **B7** Breakers: each automatic rule trips on a synthetic input; a reset without a valid unused nonce is refused.
- **B8** The clearance CLI writes a signed record that the kernel accepts, and a tampered record is rejected.
- **B9** Tests in `trader/tests/test_kernel.py` pass.

## WP1-C — Market data, paper execution, reconciliation (1.4, 1.5, 1.7, 1.16)

**Requirements**
- `trader/marketdata.py`:
  - load `MarketInfo` for target markets from WP0-A's latest crawler snapshot (`data/markets/`), building `event_group`, `asset`, `strike` and `kind`; run the crawler again when the snapshot is older than an hour
  - Polymarket market WebSocket → `Book` per token with a staleness clock, and a trades callback
  - Binance BTC/ETH real-time trades or 1s klines → `ref` prices with a tick callback, plus the final value at each print time (12:00 ET daily, hourly closes)
  - Deribit DVOL (BTC, ETH), polled every 60 s
  - a measured round trip to `clob.polymarket.com` (GET `/time`), refreshed periodically
- `trader/router.py` implementing `Router` in **paper mode only**:
  - tick rounding, minimum size, never rounding up, batches ≤ 15, GTD expiry
  - live mode impossible: there is no code path that sends orders, and setting any live flag raises
  - **strict fill simulator:** a maker order fills only on a trade strictly through its price, or when cumulative traded volume at its price reaches the queue ahead at posting plus its own size; a taker order fills at the book seen at arrival time (decision time + 150 ms taker delay + measured round trip) up to the size available; taker fees charged
  - **write-ahead journal:** each order's hash is appended and fsync'd to `data/trader/journal.jsonl` before the order counts as sent; on restart the journal is replayed to rebuild order states; an unknown state is never retried
- `trader/reconciler.py`: positions and open orders rebuilt from fills and the journal; a mismatch trips a breaker; completed YES+NO pairs are merged at once (simulated).

**Acceptance criteria**
- **C1** A live smoke run (≥ 60 s) receives Polymarket books for target markets and Binance ticks for BTC and ETH; `mid_ex_own` excludes our size (test).
- **C2** Rounding, minimum size, never rounding up and batch limits are tested; setting a live flag raises.
- **C3** Fill-model tests: a maker fills on a trade through its price; a maker at the touch fills only after queue-ahead plus own size has traded; a taker fills at the arrival-time book, partially when size is short; fees are correct.
- **C4** Journal: a simulated crash mid-batch, then replay, reproduces every order's state; an unknown order is not retried (test).
- **C5** Reconciler: positions match the fills; an injected mismatch trips a breaker; YES+NO pairs merge (test).
- **C6** The measured round trip is logged and used by the taker fill timing.
- **C7** Tests in `trader/tests/test_execution.py` pass.

## WP1-D — Ladder-maker strategy (1.6, 1.8–1.13)

**Requirements** (an `Engine` named `ladder-maker`; pure functions, no I/O)
- **Pricer (17):** daily strike digital P(S_T > K) and daily Up/Down P(S_T ≥ S_open); lognormal, zero drift; σ_P = κ(τ bucket) × σ_Q, with σ_Q from live DVOL and κ from Phase 0's fitted values (T−1h 1.150, T−6h 1.034, T−24h 0.905), registered as `candidate`. Strict ">" strikes, and a hook for USD/USDT basis. Reusing `research/kappa` read-only is fine.
- **Universe checkpoints:** a forecast plus `mid_ex_own` for every tradable ladder market at τ ∈ {24h, 6h, 1h}, traded or not, for the ledger.
- **Selector (16):** rank markets by income per dollar (spread + reward share + rebate − markout − lockup); the reward term is 0 below the minimum reward size (the target markets have no pools today); short-dated wins ties; the ranking is logged.
- **Quote engine (20), Phase 1 version:** a pure function `(book, inventory, fair, uncertainty, params, clock) → target quotes`:
  - the spread widens with vol and uncertainty, with inventory skew
  - complement bids: holding one outcome bought at p, bid the other at q with p + q < 1 − margin
  - pulls: before close and through the oracle gap, on a stale book or feed, on a sharp reference move (> k·σ in a short window)
  - requotes driven by reference ticks
- **Sizer (23):** q_used = m + 0.3 × (f − m); the invariant sign(q_used − m) = sign(f − m) and |q_used − m| ≤ |f − m| on every intent; full taker cost (fee + slippage + lockup at a human-set r_lock of 20%/yr); the within-group cap; never rounds up; refuses sub-minimum sizes. Maker sizes are capped by the inventory limits.
- **Arb scanner (18):** log-only, plus the book-integrity check (YES_ask + NO_ask < 1 or YES_bid + NO_bid > 1 → pull and flag a data fault).

**Acceptance criteria**
- **D1** Pricer tests: matches the closed form; P(> K) + P(≤ K) = 1; decreasing in K; κ applied per bucket.
- **D2** Universe checkpoint rows are produced for every tradable ladder market at each checkpoint (test with fixtures).
- **D3** Selector: the reward term is 0 below the minimum size; ties go to the shorter-dated market (test).
- **D4** Quote engine: spread widens with uncertainty; skew follows inventory; a complement bid keeps p + q < 1 − margin; each pull rule fires on its synthetic trigger (tests).
- **D5** Sizer invariant holds on 10,000 random intents; it never rounds up; it refuses sub-minimum sizes.
- **D6** The book-integrity check flags a crossed complement book.
- **D7** Tests in `trader/tests/test_ladder.py` pass.

## WP1-E — BTC-speed strategy (from Phase 0 test 0.12)

**Requirements** (an `Engine` named `btc-speed`; pure decisions, no I/O)
- A causal move detector on BTC reference ticks, with the Phase 0 parameters (5 s window, 10 bp, 60 s cooldown). An event fires at the first second the trailing move crosses the threshold, using no future data.
- Map each event to the currently open BTC 5m and 15m Up/Down markets; the favoured side is the move's direction. Skip a market that ends within a set number of seconds, or whose book is stale.
- Rule, matching what Phase 0 tested: buy 5 shares of the favoured side at the ask (taker), when at least 5 shares are on offer, at or below a registered maximum price. Hold to resolution.
- BTC only (ETH lost money in Phase 0); ETH stays off by config.
- Latency accounting per trade: Binance event time, local receive time, decision time, and simulated arrival time (decision + 150 ms + measured round trip), so the router fills at the arrival-time ask.
- A pre-registration record (handed to the ledger by WP1-F): statistic = fee-net P&L per trade held to resolution, clustered by market; PASS if mean > 2 SE over ≥ 200 trades; futility if the mean is below zero by more than 1 SE after 100 trades.

**Acceptance criteria**
- **E1** Detector test: no event before the threshold is crossed; one event per cooldown; a test proves it uses no future ticks.
- **E2** Mapping test: the right 5m/15m market and favoured token; markets about to end are skipped.
- **E3** Rule test: buys only with ≥ 5 shares at or below the max price; never sizes above 5 shares; ETH is ignored.
- **E4** Each trade record carries all four latency timestamps.
- **E5** The pre-registration dict is complete (statistic, α, n, futility rule).
- **E6** Tests in `trader/tests/test_speed.py` pass.

## WP1-F — Integration, scoring, ops, drills (1.18–1.20, invariant suite)

**Requirements**
- `trader/loop.py`: one asyncio loop wiring marketdata → both engines → kernel → router → fills → reconciler, ledger and audit log. It diffs maker targets against live orders. Paper only. CLI: `python -m trader.loop --paper --minutes N`. On start it writes both strategies' pre-registrations to the ledger (if not already there) and the parameter sets to the registry.
- `nightly/scorer.py` (22): per strategy, fills and markouts at 5 s / 1 m / 5 m against `mid_ex_own`, the fee-net primary statistic per cluster, universe vs traded subset, and speed-trade P&L once its markets resolve.
- `nightly/report.py` (36): daily `reports/phase1_daily_<date>.md` with paper P&L per strategy, fills, markouts, kernel rejections by reason, invariant violations, latency statistics and time to evidence. Optional ntfy alert with no secrets.
- `tests/invariants/`: the invariant suite from the build plan (AI can't raise size, never round up, halt means cancel-all confirmed by the reconciler, no retry on unknown state, journal replay, fee values).
- A drill script: 5 forced restarts during a paper run, including `kill -9` mid-batch, each followed by a clean reconcile.

**Acceptance criteria**
- **F1** A 60-minute integration paper run with both strategies on live data completes without crashing. `reports/phase1_smoke.md` reports intents, kernel decisions with rejection reasons, paper fills, markouts, speed events and trades, latency (round trip and decision lag), and zero invariant violations.
- **F2** The scorer and daily report run on the smoke data and produce the report with every listed section.
- **F3** The invariant suite passes (`python -m pytest tests/invariants -q`).
- **F4** Drills: 5 forced restarts including `kill -9` mid-batch, all with clean reconciles; `reports/phase1_drills.md` records each.
- **F5** Both pre-registrations are in the ledger and cannot be changed.
- **F6** No order can reach the network: there is no sending code path, and a grep confirms it.
- **F7 [ops]** 14 consecutive days of paper running on this PC with zero invariant violations (the Phase 1 exit gate).

## Phase 1 exit gate (from the build plan)

14 days with zero invariant violations, and a clean reconcile across 5 or more forced restarts including `kill -9` mid-batch. The build delivers the code, the drills and a 60-minute smoke run. The 14 days run on this PC afterwards (it must stay on and not sleep).
