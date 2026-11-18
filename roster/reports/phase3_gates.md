# Phase 3 gates: capital ladder and fast Up/Down maker-first (WP3-D)

Modules: `trader/growth/capital.py` (build-plan 3.2; roles 01, 23) and `trader/growth/fast_updown.py` (3.5; roles 17, 20, 23).
Tests: `tests/phase3/test_gates.py` (19 tests, all passing). Neither module is wired into the loop or the kernel. Every
parameter set ships as a registry `candidate`, and every promotion stays **[ops]**.

## 1. The capital ladder

The global cap moves **$50 → $250 → $500 → $1,000**, one step at a time (`capital.STEPS`, registry name `global-cap`).

| Step | Needs |
|---|---|
| $50 (start) | nothing: `current_cap` returns `STEPS[0]` when `global-cap` has no live version |
| $50 → $250 | one pre-registered test that passed **at cap $50** + your token for `promote:global-cap:250:live` |
| $250 → $500 | one pre-registered test that passed **at cap $250** + your token for `promote:global-cap:500:live` |
| $500 → $1,000 | one pre-registered test that passed **at cap $500** + your token for `promote:global-cap:1000:live` |
| any → $50 | retiring the live version (automatic demotion), with no token |

**What "passed" means.** `test_passed(ledger, name, now_ms, cap_usd=None)` is the shared check. It recomputes the result from the numbers and never trusts a verdict string. It passes only when all of these hold:

1. the pre-registration `name` exists (`Ledger.preregistration`)
2. there is **exactly one** `test_results` row with `test == name` visible at `as_of(now_ms)` (two rows break rule 4, test once)
3. that row was recorded after the pre-registration (strictly later `recorded_ms`)
4. `n ≥` the pre-registered `n`, and `se > 0`
5. `mean > pass_z × se`, with all values finite
6. when `cap_usd` is given, the row's `cap_usd` equals it

**`promote_step(ledger, to_usd, test_name, nonce, sig, now_ms)`**:
- **Refusals.** It refuses anything but the next step above `current_cap`: skips, steps down and steps past $1,000 all raise `ValueError`. It also refuses a test that fails `test_passed(..., cap_usd=current_cap)`.
- **Registration.** It registers version `str(to_usd)` with params `{cap_usd, from_usd, test, result, evidence}`, so every step sits in the registry with its evidence. It then walks the version candidate → shadow → canary → live through `Ledger.promote`, and the live step checks your HMAC token and burns the nonce.
- **Bad token.** A bad token or a reused nonce raises `PermissionError` and leaves the cap unchanged. The version stays at canary, so a retry with a fresh valid token resumes from there and completes the step (tested).
- **Re-climbing after a demotion.** The retired step's test is refused, so a re-climb needs a new pre-registered test. The re-climb gets version `250-2` (token purpose `promote:global-cap:250-2:live`), because a registered version is immutable and a retired one cannot be promoted again.
- **Scope.** It returns a cap only. Sizing, including the within-group Kelly cap, is untouched.

**`current_cap` on a fresh ledger: $50.0** (real run, see "How to reproduce"). `data/trader/trader.db` does not exist on
this machine yet, so the real ledger has no `global-cap` version and no `test_results` rows.

**Contract gap.** The Ledger has no read of a pre-registration's `recorded_ms`. `capital.prereg_recorded_ms` reads it with a read-only `SELECT recorded_ms FROM prereg WHERE name = ?` on `Ledger.db`.

## 2. Fast Up/Down gate status: **CLOSED**

`latency_gate(ledger, now_ms)` returns the assets whose **own** `by_asset[asset] = {n, mean, se}` in the single
`latency-e6-v1` result row pass `LATENCY_PREREG`. It uses the same checks as `test_passed`: one row, recorded after the pre-registration, n ≥ 200, se > 0 and mean > 2 SE. A pooled pass with no `by_asset` counts for nothing (tested). The Phase 0 free-data PASS in `reports/latency_test.md` does not count, and the module never reads it: the test walks the module's AST for file calls and runs the gate and the engine with `open` and `Path.read_text` patched to raise.

| Check | Today |
|---|---|
| `LATENCY_PREREG` written to the ledger | no (the loop writes it once, before the E6 data is analysed) |
| `latency-e6-v1` result row | none (the 4-week own-machine E6 recording has not been done) |
| `latency_gate(fresh ledger)` | `set()` |
| engine output | `[]` on every input (tested on 300 random inputs) |

The gate opens per asset only when role 22 or 35 records the E6 row and that asset's own stats pass.

**LATENCY_PREREG** (`latency-e6-v1`):
- **Statistic:** the fee-net edge per event when entering at decision + 150 ms + measured RTT, by the Phase 0 method (`research.measure.latency`).
- **Clustering:** one cluster per market.
- **Judging:** per asset. PASS needs mean > 2 SE with n ≥ 200 events. Futility stops an asset at mean < −1 SE once n ≥ 100.
- **Data:** 28 days of our own recordings.

**FAST_PREREG** (`fast-updown-maker-v1`): the engine's own Loop B test. The statistic is fee-net P&L per market held to resolution, clustered per market, with PASS at mean > 2 SE and n ≥ 200 markets.

## 3. The engine (`FastUpDownMaker`)

**Pricer (role 17).** `twap_up` gives P(Chainlink 60 s TWAP ≥ open), with ties resolving Up. It models the price as arithmetic Brownian motion with σ_abs = κ_fast·σ_Q·x/√(s per year), and κ_fast = 1.0 is a candidate.
- **τ ≥ w:** mean x and variance σ²(τ − 2w/3).
- **τ < w:** mean ((w − τ)·realised_avg + τ·x)/w and variance σ²τ³/(3w²).
- **Checks (tested):** both branches give σ²w/3 at τ = w. A seeded Monte Carlo agrees at τ = 70 s (model 0.6425) and at τ = 40 s with 20 s already realised (model 0.8311). Replacing either variance with a wrong formula fails the tests.

**Open price.** The open is the first reference tick at or after the window start (end − duration, with the duration parsed from `event_group`). It must arrive within 2 s of the start, or the engine does not quote. The USD/USDT basis cancels because the open and x come from the same feed.

**Worked example** (BTC 15m, open 60,000, DVOL 50, 13 min left, Up book 0.50/0.54, Down book 0.46/0.50, min_size 5, tick 0.01):

| x | f(Up) | q = m + 0.3(f − m) | Intents |
|---|---|---|---|
| 60,060 | 0.660 | 0.562 | maker BUY Up 5 @ 0.53 (capped at ask − tick); maker BUY Down 5 @ 0.41 (≤ 0.438 − 0.02) |
| 60,400 | 0.997 | 0.663 | with E6 edge > 0: taker BUY Up 5 @ 0.54 (fee-net edge 0.10 > 0.02); maker BUY Down 5 @ 0.31; no Up bid (max_shares room used by the taker) |

**Pulls.** These use the same rules as the ladder, through `ladder.pull_reason`: close (the last 60 s), a stale book (> 5 s), a stale feed (> 2 s), a sharp move (> 4σ over 10 s, with a 30 s cooldown) and book integrity. A pulled market gets no maker and no taker (each rule is tested).

**GTD and quoting windows.** A maker expiry must lie in [now + 2 min + 45 s, end − 2 min], which sits inside the kernel's [now + 2 min + 30 s, end − 2 min]. When that window is empty, the engine emits no maker quote. Every emitted expiry passed `RiskKernel.gtd` on 1,500 random scenarios. The rule leaves these maker windows:

| Market | Maker quotes possible |
|---|---|
| 5m | the first 16 s of 300 s |
| 15m | the first 616 s of 900 s |
| 4h | the first 14,116 s of 14,400 s |

5m makers are therefore nearly inert under the kernel's resting-order rule. That is a design consequence for the operator to weigh, and it is not a defect.

**Taker.** The engine takes only when the asset's E6 measured edge is above 0 **and** q − ask − fee(1, ask, rate) − slippage > `min_edge`. The size is `min_size`, the give-up deadline is now + 2 s, and only one taker runs per market at a time.

**Exposure cap.** For each token, held + in-flight taker + this tick's taker + bid ≤ `max_shares` (5, a hard ceiling). The taker uses the room first.

### Defects fixed while finishing this WP (found by the new tests)

1. **Over-cap exposure.** One tick could emit both a maker bid and a taker on the same token, each of `min_size`. That gave 10 shares against `max_shares = 5` at min_size 5, and an in-flight taker wasn't counted either. The fix is a per-token room budget that the taker draws first.
2. **Stale pending taker.** An expired pending taker was pruned only at the end of `on_tick`, so it blocked the market for one extra tick after its give-up deadline. The prune now runs at the start of `on_tick`.

### Known gaps (reported, not worked around)

- **No 4h groups.** `recorder.crawler` and `trader.marketdata` produce only `BTC/ETH-5m|15m@<start>` groups for crypto-fast. The engine parses `-4h@`, but no 4h market reaches it until the crawler's `SLUG_MODE` and the marketdata regex learn the 4h slug.
- **Takers need the E6 edges passed in.** The `edges` keyword gives the takers their E6 edges and defaults to empty, so no takers run. Build the engine with `FastUpDownMaker(latency_gate(L, now), edges=e6_edges(L, now))` to enable them.
- **The open is a proxy.** The open is the Binance price, standing in for the Chainlink snapshot (marked `ponytail:` in the code). Once a feed exists, read Polymarket's own open or TWAP feed.

## Wiring later

- **Kernel cap.** Build the kernel with `RiskKernel(global_cap_usd=capital.current_cap(ledger))`; its 1.1× bankroll refusal then follows the cap.
- **Result rows.** Role 22 or 35 writes one `test_results` row per test: `{test, n, mean, se, cap_usd, evidence, by_asset?}`.
- **Pre-registrations.** The loop writes `LATENCY_PREREG` and `FAST_PREREG` once (`Ledger.preregister`) before the data is analysed.
- **Capital steps.** You sign `human_token(key, "promote:global-cap:<version>:live", nonce)`, and the loop calls `promote_step`.
- **The engine.** The loop builds `FastUpDownMaker(latency_gate(ledger, now), edges=e6_edges(ledger, now))`, and `STRATEGIES` gains `fast-updown-maker` with a canary-sized budget. `ref[asset]` needs `price`, `ts_ms` and `dvol` (or `sigma_q`).
- **Kernel settings.** `kernel.starts` must stay unset for crypto-fast markets, or the start − 5 min GTD bound refuses every maker order. The kernel's `gtd_margin_ms` must stay ≤ the engine's (30 s against 45 s).

## Operational items [ops]

- **Capital steps:** each step needs a real pre-registered pass at the current size and your token, and the hot wallet is funded only up to the cap.
- **E6 recording:** the 4-week latency recording from our own machine, after which the E6 row is written.
- **Fast maker test:** the engine's own pre-registered test (replay → shadow → canary → your token).

## How to reproduce

From `roster/`:

```
.venv\Scripts\python.exe -m pytest tests/phase3/test_gates.py -q      # 19 passed
.venv\Scripts\python.exe -m trader.growth.fast_updown                 # module self-check
.venv\Scripts\python.exe -c "import tempfile, pathlib; from trader.ledger import Ledger; from trader.growth import capital, fast_updown as fu; d = tempfile.mkdtemp(); L = Ledger(path=pathlib.Path(d) / 't.db'); print(capital.current_cap(L), fu.latency_gate(L, 10**13))"
```

The last command prints `50.0 set()`: a fresh ledger sits at $50 with the fast Up/Down gate CLOSED.
