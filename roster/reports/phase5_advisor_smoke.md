# Phase 5 advisor roles smoke (WP5-D)

All four roles run against a scripted fake gateway (no vendor call, no network, no key). Market text comes from `data/markets/2026-10-07T042023Z.jsonl` (608 markets); headlines are synthetic samples. `now` = the snapshot time. Prompt hashes: board `ba47ac6c0b5d9999`, shock `1d4b7f436fefc509`, shadow `928c22495856c99e`.

## Role 24, crypto shock reader (LLM part)

Enabled underlyings ('BTC', 'ETH'). 6 synthetic headlines, 4 gateway calls (unmatched and late items make none). Prompt sha256 `1d4b7f436fefc5090eb18194505ddfd981c31c5e45bbd351e638e49b4d6453a6`.

| item | title | keyword match | recorded after now | signals |
|---|---|---|---|---|
| n1 | Exchange hot-wallet exploit: ETH withdrawals paused | True | False | pull ETH x0.0 240 min fresh-obs=True |
| n2 | Largest dollar stablecoin depegs as issuer reports insolvency | True | False | pull BTC x0.0 60 min fresh-obs=True, pull ETH x0.0 60 min fresh-obs=True |
| n3 | Spot bitcoin ETF inflows rise for a third day | False | False | - |
| n4 | Exchange schedules a two-hour maintenance outage for Sunday | True | False | - |
| n5 | DeFi lending protocol hack drains a liquidity pool | True | False | pull BTC x0.0 240 min fresh-obs=True, pull ETH x0.0 240 min fresh-obs=True |
| n6 | Second exchange reports a hack | True | True | - |

Signal fields: ['action', 'expires_ms', 'reason', 'resume_requires_fresh_observation', 'role', 'scope', 'shrink_factor']. No direction field exists; the vendor's extra "direction" was dropped.

## Role 30, correlation adversary

New group `bitcoin-above-on-october-7-2026` (11 markets); held: `ethereum-above-on-october-7-2026`, `epl-ars-lee-2026-10-10`. The cap is a cache key only and never reaches a prompt. `calls` is the cumulative gateway call count.

| review | calls | verdict | votes | reasons |
|---|---|---|---|---|
| first entry, cap 100 | 1 | clear | fake1:clear, fake2:clear |  |
| 100 repeats at cap 100, then cap 50 | 1 | clear | fake1:clear, fake2:clear |  |
| cap raise to 250 | 2 | veto | fake1:clear, fake2:veto | fake2: link ethereum-above-on-october-7-2026: BTC and ETH strikes settle on the same noon ET Binance print; one crypto move hits both |

## Role 31, change gate

Rule 7 first, then the evidence check (flagged learned changes only, judged from the numbers), then a 2-vendor review that sees directions and relative moves, never values or evidence.

| change | rule-7 flags | calls | verdict | votes | reasons |
|---|---|---|---|---|---|
| lower quote_size (not flagged) | - | 1 | clear | fake1:clear, fake2:clear | pass still needs a human token |
| raise quote_size, no pre-registration | quote_size raised | 0 | veto | - | quote_size raised; no pre-registration (n, pass_z) |
| raise c_shrink, evidence below n | c_shrink raised | 0 | veto | - | c_shrink raised; evidence below its pre-registered n |
| kappa change, failed test | kappa change: 24 | 0 | veto | - | kappa change: 24; pre-registered test not passed |
| raise c_shrink, passing evidence | c_shrink raised | 1 | clear | fake1:clear, fake2:clear | c_shrink raised; pass still needs a human token |
| code change to trader/kernel.py | code touches T0 or a sizer: trader/kernel.py | 1 | veto | fake1:clear, fake2:veto | fake2: no retry on unknown order state: resubmit after UnknownState; code touches T0 or a sizer: trader/kernel.py |

## Role 26, shadow forecaster

4 markets from the snapshot, 6 fake vendors each (4 gateway calls). Platt is the identity (no resolved rows yet); the mid is a synthetic 0.5 placeholder. Prompt sha256 `928c22495856c99eefabdb7f39a5ad8fe5eb89adbe011caebee39169ac7c99ec`.

| market | mode | status | usable | method | combined | calibrated | blended |
|---|---|---|---|---|---|---|---|
| epl-ars-lee-2026-10-10 | sports-pregame | ok | 6 | median | 0.528 | 0.528 | 0.509 |
| epl-ars-lee-2026-10-10 | sports-pregame | ok | 6 | trimmed | 0.354 | 0.354 | 0.455 |
| bitcoin-above-on-october-7-2026 | crypto-term | ok | 6 | median | 0.268 | 0.268 | 0.425 |
| bitcoin-above-on-october-7-2026 | crypto-term | insufficient | 3 | trimmed | None | None | None |

run_batch with 6 vendors x 2 requests of quota: 2 forecasts, then it stopped (quota left {'fake1': 0, 'fake2': 0, 'fake3': 0, 'fake4': 0, 'fake5': 0, 'fake6': 0}, fewer than 4 vendors with quota).
Log: `shadow_smoke.jsonl`, 6 lines.

## Fail-closed cases

Every vendor answers the same failure. Role 24 pulls every enabled underlying, roles 30 and 31 veto, and role 26 excludes the answers (status `insufficient` below 4 usable). A prompt holding the value of an env var named like a secret is never sent (0 calls).

| case | role 24 | role 30 | role 31 | role 26 |
|---|---|---|---|---|
| ok=False | 2 pulls (BTC, ETH), calls 1 | veto, calls 1 | veto, calls 1 | insufficient, 6 excluded, calls 1 |
| malformed | 2 pulls (BTC, ETH), calls 1 | veto, calls 1 | veto, calls 1 | insufficient, 6 excluded, calls 1 |
| missing field | 2 pulls (BTC, ETH), calls 1 | veto, calls 1 | veto, calls 1 | insufficient, 6 excluded, calls 1 |
| quota exhausted | 2 pulls (BTC, ETH), calls 1 | veto, calls 1 | veto, calls 1 | insufficient, 6 excluded, calls 1 |
| secret in prompt | 2 pulls (BTC, ETH), calls 0 | veto, calls 0 | veto, calls 0 | insufficient, 0 excluded, calls 0 |

## How to reproduce

From the code root (`roster/`):

```
.venv\Scripts\python.exe -m advisor.roles_p5.smoke
.venv\Scripts\python.exe -m pytest tests/phase5/test_advisor_roles.py -q
```

The smoke reads the latest `data/markets/*Z.jsonl` snapshot, makes no network call and needs no key. It rewrites this report and `advisor/roles_p5/out/shadow_smoke.jsonl`.
