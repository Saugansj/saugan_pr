# Phase 3 WP3-B: negRisk executor behind a scanner-evidence gate (build-plan 3.3, role 18)

Module: `trader/growth/negrisk.py`. Tests: `tests/phase3/test_negrisk.py` (18 tests, no network). Strategy name `negrisk-arb`. Nothing is wired into the loop, the kernel or the crawler. The parameter set ships as a registry `candidate`. Role 06's negRisk conversions are **not built**; they are built only if this strategy passes its pre-registered test.

## Eligibility rule

A negRisk event lists N mutually exclusive outcomes. Buying one YES share of every leg pays exactly $1 only if exactly one listed outcome resolves YES. `eligible(event, confirmation, now_ms, secret)` returns `(True, "eligible")` only if every one of these holds. Anything else fails closed, None included:

| Check | Ineligible when |
|---|---|
| `augmented` | True or None (from the crawler's `neg_risk_augmented`, the event-level flag) |
| `has_other` | True or None (True if any leg is the crawler's `neg_risk_other` placeholder) |
| legs | fewer than 2, or duplicate cids |
| every leg `neg_risk` | any leg not exactly True |
| exactly-one-YES confirmation | missing; wrong `type`; bad, missing or foreign signature (`trader.kernel.verify`, HMAC); no key; key mismatch; `expiry_ms` reached |

The confirmation is `{"type": "negrisk-exactly-one-yes", "key", "signer", "expiry_ms", "sig"}`, signed with `trader.kernel.sign`. `confirm()` builds one. Its key is `{event_id, sorted leg cids, sorted leg rules_sha256, n_legs}`, so a leg added or a rules text changed after signing makes the event ineligible (`"confirmation stale: legs or rules changed"`). It is signed by you now and by role 27 from Phase 4.

`event_from_rows(event_id, crawler_rows)` builds the event from crawler rows, because `MarketInfo` lacks the augmented and other flags. It returns None if any leg cannot be built (missing field, unmodelled fee schedule). A missing leg would make the basket look cheaper than it is.

## Hurdle

`hurdle(asks, rates, legging_budget) = Σ ask_i + Σ rate_i · ask_i · (1 − ask_i) + legging_budget`. The fee is `trader.fees.fee(1, ask_i, rate_i)` on every leg. The basket is executable only when the hurdle is **< 1**; exactly 1 is refused.

Hand-checked values (test B1):

| Basket | Asks | Rates | Legging | Hurdle |
|---|---|---|---|---|
| 3-leg | 0.30, 0.40, 0.25 | 0.07, 0.05, 0 | 0.01 | 0.9867 (executable) |
| 5-leg | 0.20, 0.25, 0.15, 0.10, 0.22 | 0.07, 0.05, 0, 0.07, 0.05 | 0.005 | 0.960455 (executable) |
| 5-leg | 0.21, 0.26, 0.16, 0.11, 0.23 | same | 0.005 | 1.011941 (not executable) |

## Scanner and evidence gate

- `scan()` writes one log-only row per event per tick, with these fields: `event_id`, `ts_ms`, `cids`, per-leg `asks` and `ask_sizes`, `hurdle`, `edge = 1 − hurdle` (None if any leg has no ask), `size_at_touch` (the smallest best-ask size), `min_size` (the largest leg minimum), `eligible`, `reason`, `round_trip_ms` (our RTT plus the market's taker delay, from the caller).
- `evidence(rows, n_min=30)` groups rows by event in time order. An episode is a maximal run of consecutive rows that are eligible, have `edge > 0` and have `size_at_touch ≥ min_size`. Duration is the last row's `ts_ms` minus the first row's `ts_ms`, so a single-row sighting lasts 0. An episode counts only if its duration is longer than its round trip (the largest in the run; a missing round trip means it does not count). The gate opens at `n_eligible ≥ n_min`.
- `basket()` recomputes `evidence(rows)` itself and never trusts a flag passed in. It then requires a non-empty `replay_ref`, eligibility and a hurdle below 1. When it emits:
  - one BUY YES taker `Intent` per leg at its best ask, all the same size, `expiry_ms = now + legging_ms`, with `basket=<event>@<now>` in `reason`
  - size = min(smallest best-ask size, `max_shares`, `budget_usd / Σ cost_i`), floored to 0.01 with `ladder.floor_to`
  - refused if the size is below the largest leg minimum, or if `worst_case_leg_loss_usd = size × (Σ cost − min cost)` exceeds `max_leg_loss_usd`
  - `info` carries `locked_edge_usd = size × (1 − Σ cost)`
- `completion(info, fills, books, ...)` sends takers for the unfilled part of each leg only while (USD already paid, fees included) + (remaining shares at current asks plus fees) ≤ size × (planned Σ cost + legging budget). Otherwise it returns `[]` and `"legging budget exceeded"`.

Candidate parameters (`REGISTRY["negrisk-arb"]`, state `candidate`):

| Parameter | Value |
|---|---|
| `legging_budget` | 0.01 USD/share |
| `legging_ms` | 3000 |
| `max_shares` | 10 |
| `budget_usd` | 10 |
| `max_leg_loss_usd` | 8 |
| `n_min` | 30 |

`PREREG` (role 22) uses the per-basket statistic d = realised − (locked_edge_usd − size × legging_budget), clustered by event. It passes if mean d > 2 SE over ≥ 30 eligible opportunities (one-sided α = 0.0228), and stops for futility if mean d < −1 SE once n ≥ 15.

## Gate status today: **CLOSED**

No event carries an exactly-one-YES confirmation, so every scanner row is ineligible and the gate cannot open. This is expected.

Unconfirmed scanner counts on the recorded negRisk books (`python -m trader.growth.negrisk --replay`, local files only, run 2026-10-01):

| Item | Value |
|---|---|
| Recording | `data/recordings/parquet/stream=sports-pregame/date=2026-09-30/14.parquet`: 1,059 WS messages over **1.9 min** (the only negRisk recording on disk) |
| Events | 48 negRisk soccer moneyline events (EPL etc.), every one with 3 legs (home / draw / away), all `neg_risk_augmented = False`, `neg_risk_other = False` |
| Scanner rows | 1,086, all with an ask on every leg |
| Round trip used | 210 ms (median of `data/trader/rtt.jsonl`) + 1,000 ms market taker delay (`seconds_delay = 1`) |
| Confirmed-eligible episodes | **0 / 30**; every row's reason is `no exactly-one-YES confirmation` |
| As if every event were confirmed (**not evidence**) | 0 rows with edge > 0, 0 episodes |
| `edge = 1 − hurdle` | max −0.0367, median −0.0597, min −0.1440 |
| Lowest raw Σ asks (before fees and legging) | 1.0100 |

The basket is never cheaper than $1 even before fees in this sample. The sample is only 1.9 minutes, so it says nothing about how often an edge appears, only that there was none here.

## What is still needed (B10, operational)

1. At least 30 eligible opportunities in real scanner logs, each lasting longer than our round trip. This needs the loop to log `scan()` rows to ledger table `negrisk_scan`, signed confirmations, and calendar time.
2. A replay confirming fee-net executable edge × size at the touch. That replay's id becomes `replay_ref`.
3. Exactly-one-YES confirmations signed per event (by you now, by role 27 from Phase 4).
4. Then role 06's conversions, and the pre-registered test.

## Contract gaps (worked around here, contracts not edited)

- `MarketInfo` has no event id, no negRisk-augmented flag and no "other" flag. `NegRiskEvent` carries them, built from crawler rows by `event_from_rows`. Legs get `event_group = event_id` and `kind = "negrisk"`.
- `trader.marketdata.market_info` returns None for sports rows (no crypto asset), so `event_from_rows` builds the leg `MarketInfo` itself.
- Completion remainders below the venue minimum size are sent as they are. The router rejects them, and the basket stays legged until the legging timeout; this is marked `ponytail:` in the code.

## How to reproduce

From the code root `C:\Users\DELL\Downloads\saugan_pr\market_updated\roster`:

```
.venv\Scripts\python.exe -m pytest tests/phase3/test_negrisk.py -q        # 18 passed, no network
.venv\Scripts\python.exe -m trader.growth.negrisk --replay                # local files only: prints the counts above
```

The replay reads every crawler snapshot under `data/markets/` (the union of rows with `neg_risk` True), the recorded books under `data/recordings/parquet/stream=sports-pregame/`, and `data/trader/rtt.jsonl`. It makes no network call and writes nothing.
