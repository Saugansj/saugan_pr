# Phase 3 Dispatch — Grow carefully (build now, wire later)

Source: [build-plan-v4.md](../../../build-plan-v4.md) Phase 3 (tasks 3.1–3.5), [36-agent-roles-polymarket-v4.md](../../../36-agent-roles-polymarket-v4.md) (roles 01, 06, 16, 17, 18, 20, 23; Loop B; strategy table rows 1, 4, 5), the Phase 0 results in [../phase-0/audit.md](../phase-0/audit.md), and the Phase 1 dispatch [../phase-1/dispatch.md](../phase-1/dispatch.md). Process: [../README.md](../README.md).

**Scope and gate (the user's decision):** Phase 3's entry gate, Phase 2's exit, is not met. Phase 2 is still being built and Phase 1 integration is still running. The user chose to **build every buildable Phase 3 piece now as standalone modules and wire them into the loop later**. Nothing in this phase is wired into `trader/loop.py`, the kernel or the crawler. Every parameter set ships as a registry `candidate`, and every strategy, market addition and capital step still has to pass its own pre-registered test and get your token before it is used. These Phase 0 results shape the scope:
- **Touch markets (3.1):** the pricer is built. κ failed its Phase 0 test (1.8 SE), so the touch κ is a `candidate`, and for τ > 24 h it is not fitted at all.
- **negRisk (3.3):** the plan says "only if earned". The executor is built behind a scanner-evidence gate that cannot open on today's data: no confirmed-eligible opportunities exist yet.
- **Fast Up/Down (3.5):** the latency test passed only on free data, and only for BTC, which is fragile. The decision logic is built, and it emits nothing until the 4-week test on our own data (Phase 0 E6) is recorded as a PASS.

- Code root: `C:\Users\DELL\Downloads\saugan_pr\market_updated\roster`
- Python: `roster\.venv\Scripts\python.exe`. Run tests from the code root: `.venv\Scripts\python.exe -m pytest tests/phase3 -q`
- **Shared contracts:** `roster/trader/contracts.py` and `roster/advisor/contracts.py` are read-only, and so is `roster/common.py`. Implement against `MarketInfo`, `Book`, `Intent`, `Fill`, `Ledger` and `Engine`. If a contract is insufficient, work around it inside your package and list the gap in your report. Don't edit the contract. Known gaps: `MarketInfo` has no window start, no negRisk-augmented flag and no event id.
- **Read-only imports are allowed and preferred over copying:** Phase 1 code (`trader/*.py`, `trader/engines/*`, owned by the running Phase 1 integration) and Phase 0 code (`recorder/`, `research/`). Reuse these helpers rather than rewriting them:
  - `trader.engines.ladder`: `digital`, `kappa_for`, `sigma_q`, `shrink`, `invariant_ok`, `floor_to`, `pull_reason`, `book_fault`
  - `trader.fees.fee`
  - `trader.kernel`: `sign`, `verify`
  - `trader.marketdata`: `source_id`, `market_info`
  - `trader.ledger`: `Ledger`, `human_token`
  - `recorder.crawler`: `mode_of`, `gamma_events`
- `trader/growth/__init__.py` and `tests/phase3/__init__.py` already exist and are shared. Leave them alone.

**Convention shared by WP3-A and WP3-C** (so neither depends on the other): a touch market is a `MarketInfo` with `kind = "touch-up"` ("will X reach $H") or `"touch-down"` ("will X dip to $H"), `strike` = the barrier H in USDT, `end_ms` = the end of the touch window, `mode = "crypto-term"`, and `event_group = "<ASSET>-touch@<end UTC>"`. The window start is not in `MarketInfo`. The caller passes the running 1m high and low since the window start in `ref[asset]["high"]` and `ref[asset]["low"]`.

## Work packages and order

| WP | Build-plan tasks | Owns | Starts after |
|---|---|---|---|
| **WP3-A** Touch-market pricer and coherence bound | 3.1 | `trader/growth/touch.py`, `tests/phase3/test_touch.py`, `reports/phase3_touch.md` | — |
| **WP3-B** negRisk executor behind a scanner-evidence gate | 3.3 | `trader/growth/negrisk.py`, `tests/phase3/test_negrisk.py`, `reports/phase3_negrisk.md` | — |
| **WP3-C** Universe extension: SOL/XRP ladders, extra strikes, touch templates | 3.4 | `trader/growth/universe.py`, `tests/phase3/test_universe.py`, `reports/phase3_universe.md` | — |
| **WP3-D** Capital ladder and fast Up/Down maker-first | 3.2, 3.5 | `trader/growth/capital.py`, `trader/growth/fast_updown.py`, `tests/phase3/test_gates.py`, `reports/phase3_gates.md` | — |

All four build in parallel. Each WP uses fakes and temporary ledgers (`Ledger(path=tmp_path / "t.db")`) in its own tests. **[ops]** items need keys, real money, a live venue or calendar time, and auditors mark them `operational_pending`.

## Rules every Phase 3 WP follows (each WP's "Rules check" AC means all of these hold)

- **R1** Files are created only inside the WP's owned paths. No existing file is edited: not Phase 1's `trader/*.py`, `trader/engines/*`, `nightly/`, `tests/invariants/` or `data/trader/`, not Phase 0 code, not the shared contracts, and not the two `__init__.py` files.
- **R2** Unit tests need no network. The module does network I/O only in an optional `--smoke` path under `if __name__ == "__main__":`. That path makes only public, read-only GETs, and the tests never call it. Auditor's check: grep the test file and the module body for `urllib`, `http.client`, `httpx`, `websockets`, `socket` and `get_json` outside the smoke function.
- **R3** No order is placed, signed, posted or cancelled, and no authenticated endpoint is called. No venue credential or LLM vendor is used, no paid service is touched, and nothing is pip-installed. Modules return `Intent`s and dicts only. `os.environ` is read only for `ROSTER_HUMAN_KEY`, through the existing `trader.ledger` and `trader.kernel` helpers. Auditor's check: grep for `py_clob_client`, `eth_account`, `POST`, `api_key`, `secret` (other than the HMAC secret argument) and `os.environ`.
- **R4** Minimal code with no speculative abstractions: the listed helpers are imported, not copied, and there is one test file per WP. The report ends with "How to reproduce".

---

## WP3-A — Touch-market pricer and coherence bound (3.1; roles 17, 18)

**Requirements** (pure functions, no I/O; same units as `trader.engines.ladder.digital`: σ annualised on a 365-day year, τ in hours)
- `one_touch(S, H, sigma, tau_h, up, basis=1.0, touched=False) -> float`: the exact GBM one-touch probability under continuous monitoring, with log drift −σ²/2, so that S is a martingale. Binance 1m highs and lows are treated as effectively continuous. With s = σ√τ, H' = H × basis and b = |ln(H'/S)|:
  - up (H' > S): P = N((−b − s²/2)/s) + (S/H')·N((−b + s²/2)/s)
  - down (H' < S): P = N((−b + s²/2)/s) + (S/H')·N((−b − s²/2)/s)
  - P = 1 if `touched` is set or S is already at or beyond the barrier. P = 0 if τ ≤ 0 and the barrier was not touched.
  - Basis hook: H is in USDT. `basis` is USD per USDT and is not 1.0 only when S is a USD index. It is 1.0 when S is the Binance USDT price, which is the resolution source.
- `touch_fair(m, r, now_ms, params) -> dict` for a `MarketInfo` with kind `touch-up` or `touch-down` (see the convention above), where r = `ref[asset]` carries `price`, either `dvol` or a precomputed `sigma_q` (for assets without DVOL), `high` and `low` (running extremes since the window start) and an optional `basis`.
  - σ_P = κ(τ) × σ_Q, where κ comes from this module's registered `touch` parameter set through `ladder.kappa_for`. For τ beyond 24 h it uses the 24 h bucket, and the returned dict flags that value as unfitted.
  - It returns `f`, `unc` (half the change in f for σ_P ± `sigma_rel_unc`, as `ladder.fair_value` does), `S`, `H`, `sigma_q`, `kappa`, `sigma_p`, `tau_h`, `basis` and `touched`.
  - It returns `{"err": ...}` on a missing price, vol or barrier, or on a wrong kind. It never guesses.
- **Coherence (role 18), applying the bound digital ≤ touch ≤ 2 × digital + ε:**
  - `bounds(S, H, sigma, tau_h, up, eps_tol)` → (lower, upper). Here "digital" is the same-side terminal probability: `ladder.digital` for up, and 1 − `ladder.digital` for down (the NO token of the "above $H" market).
  - Under this model, touch_up = 2·digital_up + C(H)/H and touch_down = 2·digital_down − P(H)/H, where C and P are the undiscounted call and put at strike H with the same σ and τ. An up-touch therefore always sits above 2 × digital, so ε = C(H)/H + `eps_tol` for up barriers and ε = `eps_tol` for down barriers. With ε = 0, the check would flag correctly priced up-touch markets.
  - `coherence_flags(touch_book, digital_book, S, H, sigma, tau_h, up, eps_tol) -> list[str]` is log-only on market prices. It returns `"touch<terminal"` when touch_ask < digital_bid and `"touch>2x_digital+eps"` when touch_bid > 2 × digital_ask + ε. For a down-touch, digital_book is the NO token's book.
- `REGISTRY` (the `touch` parameter set, state `candidate`: κ buckets, `sigma_rel_unc`, `eps_tol`) and `PREREG` (the touch Loop B test: name, hypothesis, statistic, cluster, se, alpha, pass_z, n, futility_z, futility_n), as dicts. Nothing is written anywhere.
- `reports/phase3_touch.md`:
  - the formulas and the ε finding, with a table of C(H)/H at representative inputs
  - worked examples
  - optionally, a smoke comparison of model and mid on currently listed touch markets (public GETs only), or "not run" with the reason
  - "How to reproduce"

**Acceptance criteria**
- **A1** `one_touch` matches values computed by hand (shown in the test) at 3 or more input sets. The identities touch_up = 2·digital_up + C/H and touch_down = 2·digital_down − P/H hold to 1e-12 on a grid of S, H, σ and τ (test).
- **A2** A seeded Monte Carlo (numpy GBM with log drift −σ²/2, at least 10,000 steps per path) agrees with `one_touch` within 3 MC standard errors plus 0.01 at 2 or more settings, one up and one down (test).
- **A3** These properties hold (test):
  - `touched` → 1.0; τ ≤ 0 without a touch → 0.0
  - the value tends to 1 as H → S
  - the up-touch decreases in H and increases in σ and τ; the down-touch increases in H
  - the value is always in [same-side digital, 1]
  - `one_touch(S, H, basis=b)` equals `one_touch(S, H·b)`
- **A4** `touch_fair` gives κ = 1.150, 1.034, 0.905 and 0.905 at τ = 1 h, 6 h, 24 h and 10 days (the last flagged as unfitted), with σ_P = κ·σ_Q. A running high ≥ H on an up-touch, or a running low ≤ H on a down-touch, gives f = 1. Missing inputs or a wrong kind give `err` (test).
- **A5** Bound checks (test):
  - On 10,000 random inputs, the model touch lies within `bounds(..., eps_tol=0)`, and the up-touch exceeds 2 × digital, so the C/H term is needed.
  - `coherence_flags` fires on a synthetic touch_ask < digital_bid and on touch_bid > 2·digital_ask + ε, and returns nothing on a coherent pair.
- **A6** `REGISTRY["touch"]` has state `candidate`, and `PREREG` has every listed field (test or code read).
- **A7** `reports/phase3_touch.md` exists with the sections listed above and ends with "How to reproduce".
- **A8** Rules check: R1–R4 hold for this WP's files.
- **A9** The tests in `tests/phase3/test_touch.py` pass.
- **A10 [ops]** The touch markets go through Loop B (replay → shadow → canary → your token). You sign clearances for the touch templates with `tools/clearance_cli.py` (template key `crypto-term:<ASSET>:touch-up` or `:touch-down`). κ for τ > 24 h is refit through Loop B.

**Wiring later:**
- `ladder.fair_value` dispatches kinds `touch-*` to `touch_fair`, and the ladder's arb scan calls `coherence_flags` for each (touch, same-level digital) pair.
- `marketdata` keeps the running 1m high and low since each touch window's start (the Binance `kline_1m` stream already carries h and l), and the loader supplies the window start (WP3-C's `window_start_ms`).
- The fair-value record carries `basis` for the kernel's provenance check.

---

## WP3-B — negRisk executor behind a scanner-evidence gate (3.3; role 18; role 06 conversions deferred)

**Requirements** (pure functions, no I/O; `strategy = "negrisk-arb"`)
- `NegRiskEvent` (a dataclass) with these fields:
  - `event_id`
  - `legs: list[MarketInfo]`: the YES token of each listed outcome
  - `augmented: bool | None`: from the crawler's `neg_risk_augmented`
  - `has_other: bool | None`: True if any leg is the crawler's `neg_risk_other` placeholder
- `eligible(event, confirmation, now_ms, secret) -> (bool, reason)`: eligible only if every one of these holds, and fail closed on None:
  - `augmented is False` and `has_other is False`
  - every leg has `neg_risk` True
  - an **exactly-one-YES confirmation** is valid. This is a record signed with `trader.kernel.sign` (verified with `verify`), signed by you now and by role 27 from Phase 4. Its key is {event_id, sorted leg cids, sorted leg `rules_sha256`, leg count}, and it has an `expiry_ms`. A leg added, a rules hash changed, an expired or missing record, or a bad signature makes the event ineligible.
- `hurdle(asks, rates, legging_budget) -> float` = Σ ask_i + Σ rate_i × ask_i × (1 − ask_i) + legging_budget, computed with `trader.fees.fee(1, ask_i, rate_i)` on every leg. The basket is executable only when the hurdle is below 1.
- `scan(event, books, now_ms, round_trip_ms, is_eligible, params) -> dict`: one log-only scanner row with `event_id`, `ts_ms`, per-leg asks and best-ask sizes, `hurdle`, `edge = 1 − hurdle`, `size_at_touch` (the smallest best-ask size), `eligible`, `reason` and `round_trip_ms` (our RTT plus the market's taker delay, computed by the caller). If any leg has no ask, `edge` is None.
- `evidence(rows, n_min=30) -> dict` returns {pass, n_eligible, episodes}.
  - Rows are grouped by event in time order. An episode is a maximal run of consecutive rows that are eligible, have `edge > 0` and have `size_at_touch` ≥ the largest leg `min_size`.
  - Duration = the last such row's `ts_ms` − the first row's `ts_ms`. A single-row sighting therefore has duration 0.
  - An episode counts only if its duration exceeds its `round_trip_ms`. The gate is PASS when n_eligible ≥ `n_min`.
- `basket(event, books, now_ms, params, rows, replay_ref, confirmation, secret) -> (intents, info)` emits nothing and returns the reason unless all of these hold:
  - `evidence(rows)` passes (recomputed here; a flag passed in is never trusted)
  - `replay_ref` is non-empty
  - the event is eligible
  - the hurdle is below 1

  When it emits:
  - **Size:** the smallest best-ask size, capped at `max_shares` and at `budget_usd / Σ cost_i`, floored with `ladder.floor_to` (never rounded up). If the result is below the largest leg `min_size`, the basket is refused.
  - **Intents:** one BUY YES taker `Intent` per leg at its best ask, all the same size, with `expiry_ms = now + legging_ms` and a basket id in `reason`.
  - **info:** `locked_edge_usd` = size × (1 − Σ cost_i) and `worst_case_leg_loss_usd` = size × (Σ cost_i − min_i cost_i), where cost_i = ask_i + fee_i. That is the loss if every leg fills except the winner. The basket is refused if this exceeds `max_leg_loss_usd`.
- `completion(info, filled, books, now_ms, params) -> (intents, reason)`: taker intents for the unfilled legs only. It completes them only while (cost already paid) + (remaining legs at their current asks plus fees) ≤ (planned Σ cost + legging_budget) per share. Otherwise it returns no intents and reason `"legging budget exceeded"`.
- `REGISTRY` (`negrisk-arb` parameter set, state `candidate`: `legging_budget`, `legging_ms`, `max_shares`, `budget_usd`, `max_leg_loss_usd`, `n_min`) and `PREREG` (role 22's arb statistic: realised ≥ predicted − legging budget over ≥ 30 eligible opportunities; with name, statistic, cluster = event, se, alpha, pass_z, n, futility).
- Role 06's negRisk conversions are **not** built. They are built only if this strategy passes.
- `reports/phase3_negrisk.md`:
  - the eligibility rule, the hurdle and the gate
  - the gate's status on the evidence available today. CLOSED is expected, because no confirmed-eligible opportunities exist. Optionally, it reports unconfirmed scanner counts on any recorded negRisk books under `data/recordings/`.
  - "How to reproduce"

**Acceptance criteria**
- **B1** `hurdle` matches values computed by hand for a 3-leg and a 5-leg basket with rates 0.07, 0.05 and 0, with the fee on every leg. Below 1 is executable; 1 or more is not (test).
- **B2** Eligibility (test). Each of these makes an event ineligible:
  - `augmented` True or None
  - `has_other` True or None
  - a leg that is not negRisk
  - a confirmation that is missing, expired, unsigned or tampered with
  - a leg added, or a rules hash changed, after signing

  The valid case is eligible.
- **B3** Evidence gate (test):
  - 29 qualifying episodes → closed; 30 → open
  - an episode no longer than its round trip doesn't count
  - ineligible rows, rows below the minimum size and single-row sightings don't count
- **B4** `basket` returns no intents, with the reason, when the gate is closed, `replay_ref` is empty, the event is ineligible or the hurdle is 1 or more (test).
- **B5** Basket (test):
  - one BUY taker intent per leg at the best ask, all the same size
  - size ≤ the smallest best-ask size, ≤ `max_shares` and floored; below the largest leg minimum, it is refused
  - `worst_case_leg_loss_usd` = size × (Σ cost − min cost) on a hand-computed example
  - a basket over `max_leg_loss_usd` is refused
- **B6** `completion` completes the missing legs while the total stays within the planned cost plus the legging budget, and emits nothing beyond it (test).
- **B7** `reports/phase3_negrisk.md` exists with the sections listed above and ends with "How to reproduce".
- **B8** Rules check: R1–R4 hold for this WP's files.
- **B9** The tests in `tests/phase3/test_negrisk.py` pass.
- **B10 [ops]** These need real data and calendar time:
  - 30 or more eligible opportunities from real scanner logs, lasting longer than our round trip
  - replay confirming fee-net executable edge × size at the touch, which gives `replay_ref`
  - exactly-one-YES confirmations signed per event
  - then role 06's conversions, and the pre-registered test

**Wiring later:**
- The loop calls `scan` for every negRisk event in the crawler snapshot and logs the rows to a ledger table `negrisk_scan`. `evidence` reads them back through `Ledger.as_of`.
- Kernel changes:
  - `STRATEGIES` gains `negrisk-arb` with its budget
  - the event is one exposure group
  - `worst_case_leg_loss_usd` counts against the caps
  - `REDUCING` allows `completion` intents for an in-flight basket within its legging budget
- `NegRiskEvent` is built from the crawler's `neg_risk_augmented` and `neg_risk_other` fields, which `MarketInfo` lacks.

---

## WP3-C — Universe extension: SOL/XRP ladders, extra strikes, touch templates (3.4; roles 16, 17)

**Requirements** (configuration plus pure helpers; network only in the optional smoke)
- `ASSETS`: BTC and ETH (the Phase 1 baseline), plus SOL and XRP. Each entry has:
  - the Binance symbol
  - the Gamma slug prefixes
  - `source_id` in the `trader.marketdata.source_id` format (for example `binance:SOL/USDT`)
  - the vol source: `"dvol"` where Deribit publishes a DVOL index, otherwise `"realized"`. The optional smoke may confirm availability with a public GET; the unit tests don't depend on it.
  - `state`
  - `loop_b`
- `ENTRIES`: versioned universe entries {id, asset, kinds, max_tau_h, band_z, state, loop_b, prereg}.
  - **Baseline:** BTC/ETH, kinds `strike` and `updown`, `max_tau_h = 24`, `band_z = None`. This reproduces exactly what Phase 1 trades.
  - **Additions,** each its own entry:
    - SOL ladder (strike and updown)
    - XRP ladder (strike and updown)
    - BTC/ETH extra strikes: a wider `max_tau_h` (listed ladders dated beyond tomorrow) and/or a `band_z` moneyness band
    - BTC/ETH touch templates (`touch-up`, `touch-down`)
  - Every addition has state `candidate`, `loop_b = True` and its own complete `PREREG` dict with a unique name, so each addition passes its own test.
- `SLUG_MODE_EXT` and `mode_of_ext(slug) -> (mode, asset, kind) | None`:
  - It gives the same mode as `recorder.crawler.mode_of` for every BTC/ETH slug.
  - It also classifies SOL/XRP daily strike and Up/Down slugs, and touch slugs ("what price will X hit in <month>").
  - Use the slug shapes Gamma actually returns. Confirm them in the optional smoke and record them in the report. If reality differs from your fixtures, follow reality.
- `market_info_ext(row) -> MarketInfo | None` for crawler-shaped rows of the new templates:
  - the asset from the slug
  - `kind` and `strike` (or the barrier) parsed from the question, in USDT
  - `event_group`: `<ASSET>@<end UTC>` for strike and Up/Down, or `<ASSET>-touch@<end UTC>`
  - `source_id` through `trader.marketdata.source_id`. If touch rules text isn't recognised there, add a parser here for the touch rules phrasing.
  - It returns None if any needed field is missing; it never guesses.
- `window_start_ms(row) -> int | None` for touch markets.
- `sigma_q_for(asset, r, closes_1m=None) -> float | None`:
  - DVOL assets: `ladder.sigma_q(r["dvol"])`
  - realized assets: the annualised standard deviation of 1m log returns over the last `vol_bars` closes (365-day year), or None when fewer than `min_bars` exist
  - this parameter set is registered as a `candidate`
- `accepts(entry, m, S, sigma, now_ms) -> bool`: true when the asset and kind match, 0 < τ ≤ `max_tau_h`, and, when `band_z` is set, |ln(K/S)| ≤ band_z·σ√τ.
- `cluster_id(m, corr) -> str`: the evidence cluster is the settlement instant. Assets settling at the same instant share one cluster unless their measured residual correlation is below 0.3. This is union-find over asset pairs, and an unmeasured pair counts as merged. The exposure `event_group` (per asset, as in role 01) is unchanged.
- `reports/phase3_universe.md`:
  - the asset and entry tables
  - what each entry needs before it goes live
  - smoke results: currently open SOL/XRP/touch events found by a public Gamma read and how they classify (or "not run" with the reason)
  - "How to reproduce"

**Acceptance criteria**
- **C1** `mode_of_ext` gives the same mode as `recorder.crawler.mode_of` for every `event_slug` in the latest `data/markets/*.jsonl` snapshot (for example `2026-10-01T084927Z.jsonl`; the test skips if none exists). It classifies the SOL, XRP and touch fixture slugs correctly and returns None for unrelated slugs (test).
- **C2** `market_info_ext` produces the right `kind`, `strike`/barrier, `asset`, `event_group` and `source_id` for SOL/XRP strike and Up/Down fixtures and for touch-up and touch-down fixtures. It returns None when a needed field is missing. A BTC/ETH strike row gives the same `MarketInfo` as `trader.marketdata.market_info` (test).
- **C3** On a seeded synthetic GBM with σ = 0.6/yr and at least one day of 1m bars, the realised σ_Q is within 10%. Too few bars gives None. A DVOL asset returns `ladder.sigma_q(dvol)` (test).
- **C4** The baseline entry accepts BTC/ETH strike and Up/Down at τ ≤ 24 h, and rejects SOL, XRP, touch and τ > 24 h. A `band_z` entry rejects a strike outside band_z·σ√τ (test).
- **C5** Every non-baseline entry has state `candidate`, `loop_b` True, and a complete, uniquely named pre-registration (test).
- **C6** `cluster_id` (test):
  - BTC, ETH and SOL at one instant → one cluster
  - SOL with measured correlation below 0.3 to both BTC and ETH → its own cluster
  - correlation below 0.3 to one but 0.3 or more to the other → merged
  - different instants → different clusters
- **C7** `reports/phase3_universe.md` exists with the sections listed above and ends with "How to reproduce".
- **C8** Rules check: R1–R4 hold for this WP's files.
- **C9** The tests in `tests/phase3/test_universe.py` pass.
- **C10 [ops]** Each addition goes through Loop B (replay → shadow → canary → your token) with its own pre-registered test. κ and vol for SOL/XRP are fitted on recorded data. You sign clearances for the new templates.

**Wiring later:**
- `recorder.crawler.SLUG_MODE` adopts `SLUG_MODE_EXT`, and `marketdata.load_markets` falls back to `market_info_ext` for the new templates.
- `marketdata` subscribes to the Binance symbols in `ASSETS`.
- Kernel changes:
  - `STRATEGIES[...]["sources"]` gains the SOL and XRP `source_id`s
  - the cross-instant stress cap adds XRP to BTC/ETH/SOL
- Role 16's selector filters candidates with `accepts` for entries whose live registry version is promoted. The scorer uses `cluster_id`.

---

## WP3-D — Capital ladder and fast Up/Down maker-first (3.2, 3.5; roles 01, 23, 17, 20)

**Requirements**
- `trader/growth/capital.py`:
  - `STEPS = (50, 250, 500, 1000)` (USD) and registry name `global-cap`.
  - `test_passed(ledger, name, now_ms, cap_usd=None) -> (bool, reason)`, the shared "pre-registered pass" check. It passes only if all of these hold:
    - a pre-registration `name` exists (`Ledger.preregistration`)
    - there is **exactly one** row in ledger table `test_results` (read with `as_of(now_ms)`) whose `test` field equals `name`. Two or more rows means refused: rule 4, test once.
    - that row was recorded after the pre-registration. Reading `prereg.recorded_ms` with a read-only SELECT on the ledger's connection is acceptable; report it as a contract gap.
    - the row's `n` ≥ the pre-registration's `n`, and `se` > 0
    - `mean > pass_z × se`, recomputed here; a verdict string is never trusted
    - when `cap_usd` is given, the row's `cap_usd` equals it

    A result row looks like {test, n, mean, se, cap_usd, evidence, by_asset?}.
  - `current_cap(ledger) -> float`: the `cap_usd` of the live `global-cap` version, or `STEPS[0]` ($50) when there is none. Retiring the live version (automatic demotion) therefore drops to $50.
  - `promote_step(ledger, to_usd, test_name, nonce, sig, now_ms)`:
    - It refuses unless `to_usd` is the next step above `current_cap`: no skipping, no stepping past the last step, and no stepping down.
    - It refuses unless `test_passed(..., cap_usd=current_cap)` holds.
    - It then registers version `str(to_usd)` with params {cap_usd, from_usd, test, result row, evidence} and walks candidate → shadow → canary → live with `Ledger.promote`. The live step needs your token: the purpose is `promote:global-cap:<usd>:live`, with an unused nonce.
    - A refused token leaves `current_cap` unchanged, and a retry with a valid fresh token resumes from the version's current state and completes the step.
  - It returns a cap only. Sizing, including the within-group Kelly cap, is untouched.
- `trader/growth/fast_updown.py` (an `Engine` named `fast-updown-maker`; pure decisions, no I/O):
  - `LATENCY_PREREG`: the Phase 0 E6 test on our own data.
    - name `latency-e6-v1`
    - statistic: fee-net edge per event when entering at decision + 150 ms + measured RTT, using the Phase 0 method
    - cluster = market
    - judged per asset, with n ≥ 200 events, pass_z 2 and a futility rule
  - `FAST_PREREG`: this engine's own Loop B test. `REGISTRY` holds the parameter set as a `candidate`.
  - `latency_gate(ledger, now_ms) -> set[str]`: the assets whose own `by_asset` stats in the single `latency-e6-v1` result row pass the pre-registered rule (through `capital.test_passed` logic). With no row it returns the empty set. The Phase 0 free-data PASS (`reports/latency_test.md`) does not count.
  - `twap_up(open_px, x, realised_avg, tau_s, sigma_abs, w=60) -> float`: role 17's Chainlink 60 s TWAP Up probability, P(TWAP ≥ open), where a tie resolves to Up.
    - For τ ≥ w: mean = x and variance = σ²(τ − 2w/3).
    - For τ < w: mean = ((w − τ)·realised_avg + τ·x)/w and variance = σ²·τ³/(3w²).
    - At τ = 0 it returns 1 if mean ≥ open, else 0.
  - `FastUpDownMaker(passing_assets, params)`: its `on_tick` returns targets only for `crypto-fast` Up/Down markets of passing assets, and `[]` when the set is empty. For each market after its window start (end − duration, the duration parsed from `event_group`):
    - **Open:** the open is the reference price at the window start. It is recorded from ticks, as the Binance proxy for the Chainlink snapshot open. The USD/USDT basis cancels because the open and x come from the same feed.
    - **Fair value:** f = `twap_up` with σ_abs = κ_fast·σ_Q·x/√(seconds per year); κ_fast is a registered `candidate`, default 1.0.
    - **Shrink:** q = `ladder.shrink(f, mid_ex_own, 0.3)`, checked with `ladder.invariant_ok`.
    - **Maker first:** post-only bids on Up at ≤ q − half and on Down at ≤ (1 − q) − half, floored to the tick, with size = the market's `min_size` and never above `max_shares` (5).
    - **Pulls:** the same pull rules, through `ladder.pull_reason`: close, stale book, stale feed, sharp move and book integrity.
    - **GTD:** the expiry must lie in [now + 2 min + margin, end − 2 min], the kernel's resting-order rule. When that window is empty, no maker quote is emitted.
    - **Taker:** only when the asset's E6 measured edge is above 0 **and** q − ask − `fee(1, ask, rate)` − slippage > `min_edge`. The size is `min_size`, the give-up deadline is now + `give_up_ms`, and there is no taker while the market is pulled.
- `reports/phase3_gates.md`:
  - the ladder steps and what each needs
  - `current_cap` on a fresh ledger ($50)
  - the fast Up/Down gate status: CLOSED until an E6 result is recorded
  - "How to reproduce"

**Acceptance criteria**
- **D1** `test_passed` (test, temporary ledger). Each of these is refused:
  - a missing pre-registration
  - zero result rows, or two
  - n below the pre-registered n
  - mean ≤ pass_z·se, even when the row says "PASS"
  - a result recorded before the pre-registration
  - a cap mismatch

  The valid case passes.
- **D2** Capital (test, temporary ledger, fake `ROSTER_HUMAN_KEY` through monkeypatch):
  - A fresh ledger gives $50.
  - 50 → 250 with a test passed at cap 50 and a valid token gives $250.
  - Each of these is refused and leaves the cap unchanged: a skip (50 → 500), a test passed at another cap, a bad token, and a reused nonce.
  - A retry after a refused token completes the step.
  - Retiring the live version gives $50.
  - Every step is in the registry with its evidence.
- **D3** TWAP (test):
  - the variance is continuous at τ = w and positive at every τ > 0 on a grid
  - P(Up) = 0.5 at x = open with τ ≥ w
  - P(Up) increases in x
  - at τ = 0, a tie resolves Up
- **D4** Gate (test):
  - with no E6 row, the engine returns no intents on any input
  - with BTC passing and ETH failing, only BTC markets get quotes
  - the engine doesn't read `reports/latency_test.md`
- **D5** Maker (test):
  - bids on both outcomes, floored to the tick, with size = `min_size` ≤ `max_shares`
  - role 23's invariant holds on 10,000 random (f, m) pairs
  - each pull rule removes the quotes on its synthetic trigger
  - an empty GTD window gives no maker quote
  - every maker expiry emitted satisfies the kernel's GTD rule
- **D6** Taker: it trades only when the asset's measured edge is positive and the per-trade fee-net edge at the ask exceeds `min_edge`, never while pulled, and never above `max_shares` (test).
- **D7** `reports/phase3_gates.md` exists with the sections listed above and ends with "How to reproduce".
- **D8** Rules check: R1–R4 hold for this WP's files.
- **D9** The tests in `tests/phase3/test_gates.py` pass.
- **D10 [ops]** These need real money, live results or calendar time:
  - each capital step needs a real pre-registered pass at the current size and your token, and the hot wallet is funded only up to the cap
  - the 4-week E6 latency recording from our own machine
  - the fast maker's own pre-registered test (replay → shadow → canary → your token)

**Wiring later:**
- The kernel is built with `RiskKernel(global_cap_usd=capital.current_cap(ledger))`, and its 1.1× refusal follows the cap.
- Role 22 or 35 writes `test_results` rows. The loop writes `LATENCY_PREREG` and `FAST_PREREG` to the ledger once, before the E6 data is analysed.
- The loop builds `FastUpDownMaker(latency_gate(ledger, now))`, and `STRATEGIES` gains `fast-updown-maker` with a canary-sized budget.
- `kernel.starts` must not be set for crypto-fast markets. Otherwise the start − 5 min GTD bound refuses every maker order.

---

## Phase 3 exit gate (from the build plan)

Each addition passes its own pre-registered test, and each capital step is your decision. This build delivers code-complete, audited, unwired modules, and every promotion stays **[ops]**. Code-complete is not gate-met.

## How to reproduce

From `roster/`: `.venv\Scripts\python.exe -m pytest tests/phase3 -q` runs all four WPs' tests. Each report in `reports/phase3_*.md` ends with its own reproduce commands.
