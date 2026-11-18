# Quote-engine full objective: smoke (Phase 5, WP5-C)

Built ahead of its gate: nothing in the trader calls this module, no order is placed, and fits are registry candidates only. Exploratory illustration of the objective on real market parameters and recorded books, with stated prior fill and markout parameters (no fills have been measured yet).

## Inputs

- Markets: latest crawler snapshot `data/markets/2026-10-01T121820Z.jsonl` (462 rows): real tick, minimum size, fee rate, rebate rate and reward parameters.
- Books: replayed through `trader.marketdata.Books` from recordings/parquet/stream=crypto-fast/date=2026-09-30/14.parquet (40763 messages), recordings/parquet/stream=crypto-hourly/date=2026-09-30/14.parquet (14768 messages), recordings/parquet/stream=crypto-term/date=2026-09-30/14.parquet (46643 messages), recordings/parquet/stream=sports-pregame/date=2026-09-30/14.parquet (1059 messages); quoting time = last recorded message, 2026-09-30 14:30:59 UTC. Only markets whose YES and NO books were both recorded and whose book is at most 0.10 wide are sampled, mid nearest 0.5 first.
- Fill rate (stated prior, not fitted): A = 0.01/s, k = 100.0 per probability unit (1/k = 0.010). Adverse move: m0 = 0.0, m1 = 0.0 (Phase 1's markout_prior = 0.0).
- sigma = 0.0005/sqrt(s) (stated), gamma = 1.0, tau = min(60 s requote, time to the pull 10 min before close), grid d_max = 40 ticks, size step 1.0, inventory limit 50.0.
- q = mid (no reference feed in the window, so role 23's shrink has nothing to move; edge then equals the distance d). I = 0 unless stated.
- Phase 1 `ladder.quotes()` on the same inputs: q = mid, half = half_min + k_vol x sigma x sqrt(vol_horizon_s) = 0.0069, ladder.PARAMS defaults; its bids are scored with the same objective.
- Phase 1's pull rules run before either quoter (the caller's job when wired; markets inside the pre-close pull window are not sampled).

## crypto-term

### Bitcoin Up or Down on October 1?

`0xeeda1f1344…` tick 0.01, min size 5.0, fee rate 0.07, rebate rate 0.2, reward pool $0.0/day (min 50, max spread 4.5c), YES book 0.49 x 323.62 / 0.52 x 10, NO best ask 0.51, mid 0.5050, tau 60 s, Q_others 179.7.

| quote | token | price | size | d | P(fill) | edge | rebate | a(d) | fill term |
|---|---|---|---|---|---|---|---|---|---|
| objective | YES | 0.5 | 50 | 0.005 | 0.3051 | 0.005 | 0.0035 | 0 | 0.1296 |
| objective | NO | 0.49 | 50 | 0.005 | 0.3051 | 0.005 | 0.003499 | 0 | 0.1296 |
| objective | total |  |  |  |  |  | reward 0 | inventory -0 | J 0.2593 (J0 -0) |
| Phase 1 quotes() | YES | 0.49 | 10 | 0.015 | 0.1253 | 0.015 | 0.003499 | 0 | 0.02318 |
| Phase 1 quotes() | NO | 0.48 | 10 | 0.015 | 0.1253 | 0.015 | 0.003494 | 0 | 0.02317 |
| Phase 1 quotes() | total |  |  |  |  |  | reward 0 | inventory -0 | J 0.04635 (J0 -0) |

### Ethereum Up or Down on October 1?

`0xbd1d2de1db…` tick 0.01, min size 5.0, fee rate 0.07, rebate rate 0.2, reward pool $0.0/day (min 50, max spread 4.5c), YES book 0.51 x 13.89 / 0.52 x 40, NO best ask 0.49, mid 0.5150, tau 60 s, Q_others 98.7.

| quote | token | price | size | d | P(fill) | edge | rebate | a(d) | fill term |
|---|---|---|---|---|---|---|---|---|---|
| objective | YES | 0.51 | 50 | 0.005 | 0.3051 | 0.005 | 0.003499 | 0 | 0.1296 |
| objective | NO | 0.48 | 50 | 0.005 | 0.3051 | 0.005 | 0.003494 | 0 | 0.1296 |
| objective | total |  |  |  |  |  | reward 0 | inventory -0 | J 0.2592 (J0 -0) |
| Phase 1 quotes() | YES | 0.5 | 10 | 0.015 | 0.1253 | 0.015 | 0.0035 | 0 | 0.02318 |
| Phase 1 quotes() | NO | 0.47 | 10 | 0.015 | 0.1253 | 0.015 | 0.003487 | 0 | 0.02317 |
| Phase 1 quotes() | total |  |  |  |  |  | reward 0 | inventory -0 | J 0.04635 (J0 -0) |

### Will the price of Bitcoin be above $84,000 on October 5?

`0xa36c093c5f…` tick 0.01, min size 5.0, fee rate 0.07, rebate rate 0.2, reward pool $0.0/day (min 50, max spread 4.5c), YES book 0.45 x 7675 / 0.48 x 1005, NO best ask 0.55, mid 0.4650, tau 60 s, Q_others 5851.1.

| quote | token | price | size | d | P(fill) | edge | rebate | a(d) | fill term |
|---|---|---|---|---|---|---|---|---|---|
| objective | YES | 0.46 | 50 | 0.005 | 0.3051 | 0.005 | 0.003478 | 0 | 0.1293 |
| objective | NO | 0.53 | 50 | 0.005 | 0.3051 | 0.005 | 0.003487 | 0 | 0.1295 |
| objective | total |  |  |  |  |  | reward 0 | inventory -6.48e-32 | J 0.2588 (J0 -0) |
| Phase 1 quotes() | YES | 0.45 | 10 | 0.015 | 0.1253 | 0.015 | 0.003465 | 0 | 0.02314 |
| Phase 1 quotes() | NO | 0.52 | 10 | 0.015 | 0.1253 | 0.015 | 0.003494 | 0 | 0.02317 |
| Phase 1 quotes() | total |  |  |  |  |  | reward 0 | inventory -6.656e-34 | J 0.04631 (J0 -0) |

## crypto-hourly

### Ethereum Up or Down - October 1, 12PM ET

`0x04a8bd1b88…` tick 0.01, min size 5.0, fee rate 0.07, rebate rate 0.2, reward pool $0.0/day (min 50, max spread 4.5c), YES book 0.49 x 10 / 0.51 x 10, NO best ask 0.51, mid 0.5000, tau 60 s, Q_others 60.2.

| quote | token | price | size | d | P(fill) | edge | rebate | a(d) | fill term |
|---|---|---|---|---|---|---|---|---|---|
| objective | YES | 0.49 | 50 | 0.01 | 0.1981 | 0.01 | 0.003499 | 0 | 0.1337 |
| objective | NO | 0.49 | 50 | 0.01 | 0.1981 | 0.01 | 0.003499 | 0 | 0.1337 |
| objective | total |  |  |  |  |  | reward 0 | inventory -0 | J 0.2674 (J0 -0) |
| Phase 1 quotes() | YES | 0.49 | 10 | 0.01 | 0.1981 | 0.01 | 0.003499 | 0 | 0.02674 |
| Phase 1 quotes() | NO | 0.49 | 10 | 0.01 | 0.1981 | 0.01 | 0.003499 | 0 | 0.02674 |
| Phase 1 quotes() | total |  |  |  |  |  | reward 0 | inventory -0 | J 0.05347 (J0 -0) |

### Bitcoin Up or Down - October 2, 12AM ET

`0x08203af95c…` tick 0.01, min size 5.0, fee rate 0.07, rebate rate 0.2, reward pool $0.0/day (min 50, max spread 4.5c), YES book 0.49 x 1165 / 0.51 x 1165, NO best ask 0.51, mid 0.5000, tau 60 s, Q_others 2355.4.

| quote | token | price | size | d | P(fill) | edge | rebate | a(d) | fill term |
|---|---|---|---|---|---|---|---|---|---|
| objective | YES | 0.49 | 50 | 0.01 | 0.1981 | 0.01 | 0.003499 | 0 | 0.1337 |
| objective | NO | 0.49 | 50 | 0.01 | 0.1981 | 0.01 | 0.003499 | 0 | 0.1337 |
| objective | total |  |  |  |  |  | reward 0 | inventory -0 | J 0.2674 (J0 -0) |
| Phase 1 quotes() | YES | 0.49 | 10 | 0.01 | 0.1981 | 0.01 | 0.003499 | 0 | 0.02674 |
| Phase 1 quotes() | NO | 0.49 | 10 | 0.01 | 0.1981 | 0.01 | 0.003499 | 0 | 0.02674 |
| Phase 1 quotes() | total |  |  |  |  |  | reward 0 | inventory -0 | J 0.05347 (J0 -0) |

## sports-pregame

### Will Bologna FC 1909 win on 2026-10-11?

`0x911d3b772d…` tick 0.01, min size 5.0, fee rate 0.05, rebate rate 0.15, reward pool $0.0/day (min 50, max spread 4.5c), YES book 0.48 x 605 / 0.5 x 128, NO best ask 0.52, mid 0.4900, tau 60 s, Q_others 894.4.

| quote | token | price | size | d | P(fill) | edge | rebate | a(d) | fill term |
|---|---|---|---|---|---|---|---|---|---|
| objective | YES | 0.48 | 50 | 0.01 | 0.1981 | 0.01 | 0.001872 | 0 | 0.1176 |
| objective | NO | 0.5 | 50 | 0.01 | 0.1981 | 0.01 | 0.001875 | 0 | 0.1176 |
| objective | total |  |  |  |  |  | reward 0 | inventory -0 | J 0.2352 (J0 -0) |
| Phase 1 quotes() | YES | 0.48 | 10 | 0.01 | 0.1981 | 0.01 | 0.001872 | 0 | 0.02351 |
| Phase 1 quotes() | NO | 0.5 | 10 | 0.01 | 0.1981 | 0.01 | 0.001875 | 0 | 0.02352 |
| Phase 1 quotes() | total |  |  |  |  |  | reward 0 | inventory -0 | J 0.04703 (J0 -0) |

### Will Stade Brestois 29 win on 2026-10-10?

`0xce57663667…` tick 0.01, min size 5.0, fee rate 0.05, rebate rate 0.15, reward pool $0.0/day (min 50, max spread 4.5c), YES book 0.5 x 178 / 0.52 x 698, NO best ask 0.5, mid 0.5100, tau 60 s, Q_others 971.6.

| quote | token | price | size | d | P(fill) | edge | rebate | a(d) | fill term |
|---|---|---|---|---|---|---|---|---|---|
| objective | YES | 0.5 | 50 | 0.01 | 0.1981 | 0.01 | 0.001875 | 0 | 0.1176 |
| objective | NO | 0.48 | 50 | 0.01 | 0.1981 | 0.01 | 0.001872 | 0 | 0.1176 |
| objective | total |  |  |  |  |  | reward 0 | inventory -0 | J 0.2352 (J0 -0) |
| Phase 1 quotes() | YES | 0.5 | 10 | 0.01 | 0.1981 | 0.01 | 0.001875 | 0 | 0.02352 |
| Phase 1 quotes() | NO | 0.48 | 10 | 0.01 | 0.1981 | 0.01 | 0.001872 | 0 | 0.02351 |
| Phase 1 quotes() | total |  |  |  |  |  | reward 0 | inventory -0 | J 0.04703 (J0 -0) |

## Scenarios on the first sampled market

Bitcoin Up or Down on October 1?

### Inventory: I = +20 YES bought at 0.505 (the mid), so the NO bid is a complement bid strictly below 1 - 0.505 - 0.01 and at most 20 shares

| quote | token | price | size | d | P(fill) | edge | rebate | a(d) | fill term |
|---|---|---|---|---|---|---|---|---|---|
| objective | YES | 0.5 | 30 | 0.005 | 0.3051 | 0.005 | 0.0035 | 0 | 0.07779 |
| objective | NO | 0.48 | 20 | 0.015 | 0.1253 | 0.015 | 0.003494 | 0 | 0.04635 |
| objective | total |  |  |  |  |  | reward 0 | inventory -0.01065 | J 0.1135 (J0 -0.006) |
| objective, gamma 50 | YES | 0.47 | 30 | 0.035 | 0.01796 | 0.035 | 0.003487 | 0 | 0.02073 |
| objective, gamma 50 | NO | 0.48 | 20 | 0.015 | 0.1253 | 0.015 | 0.003494 | 0 | 0.04635 |
| objective, gamma 50 | total |  |  |  |  |  | reward 0 | inventory -0.2439 | J -0.1768 (J0 -0.3) |
| Phase 1 quotes() | YES | 0.49 | 10 | 0.015 | 0.1253 | 0.015 | 0.003499 | 0 | 0.02318 |
| Phase 1 quotes() | NO | 0.48 | 10 | 0.015 | 0.1253 | 0.015 | 0.003494 | 0 | 0.02317 |
| Phase 1 quotes() | total |  |  |  |  |  | reward 0 | inventory -0.006 | J 0.04035 (J0 -0.006) |

### Hypothetical reward pool $100/day (today's real pool is $0.0): exercises the reward term on the real book

| quote | token | price | size | d | P(fill) | edge | rebate | a(d) | fill term |
|---|---|---|---|---|---|---|---|---|---|
| objective | YES | 0.5 | 50 | 0.005 | 0.3051 | 0.005 | 0.0035 | 0 | 0.1296 |
| objective | NO | 0.49 | 50 | 0.005 | 0.3051 | 0.005 | 0.003499 | 0 | 0.1296 |
| objective | total |  |  |  |  |  | reward 0.01251 | inventory -0 | J 0.2718 (J0 -0) |

## Fits on seeded synthetic rows (candidates only)

crypto-term: 4,000 orders in 60 clusters over 2 markets, true A = 0.02, k = 60, m0 = -0.002, m1 = -0.3. sports-pregame: 600 orders in 12 clusters (under min_clusters = 30, so its mode and market use the prior). Standard errors are CR1 cluster-robust.

| candidate | A | k | se_k | m0 | se_m0 | m1 | se_m1 | fill source | adverse source | order clusters |
|---|---|---|---|---|---|---|---|---|---|---|
| quote-objective:crypto-term | 0.01996 | 63.05 | 2.431 | -0.004831 | 0.001518 | -0.2602 | 0.03565 | mode | mode | 60 |
| quote-objective:0xaaa | 0.02092 | 64.89 | 3.487 | -0.005922 | 0.001604 | -0.2193 | 0.04932 | market | market | 60 |
| quote-objective:0xbbb | 0.01898 | 61.07 | 3.818 | -0.003665 | 0.001631 | -0.3025 | 0.05771 | market | market | 60 |
| quote-objective:sports-pregame | 0.01 | 100 | - | 0 | - | 0 | - | prior | prior | 12 |
| quote-objective:0xccc | 0.01 | 100 | - | 0 | - | 0 | - | prior | prior | 12 |

The two crypto-term markets share the same 60 clusters, so their fit errors are correlated; the tests check CR1 coverage over 20 seeds (each coefficient inside 2 SE in at least 16 of 20).

No candidate is registered or promoted by this module; wiring passes them to the ledger's registry (state `candidate`), and live use needs Loop B and a human token.

## Reading the results

- With prior fills (1/k = 1 cent) and a = 0, the objective quotes at the touch or one tick inside a wider book, where Phase 1 sits half_min + vol below q. On one-tick-wide books both quote the touch.
- J is linear in size apart from the inventory term, so the objective sizes up to the inventory limit (50) while Phase 1 quotes 10. At the stated sigma and gamma = 1 the inventory term is tiny (gamma sigma^2 tau = 1.5e-5 per share^2); gamma = 50 visibly widens the YES bid when long YES. gamma has to be calibrated (a registry parameter) before this objective could replace quotes().
- The rebate is material at mid 0.5: 0.0035 per share against a 1-cent edge.
- The reward term is 0 on every sampled market (no target market pays rewards today, as Phase 0 found); a hypothetical $100/day pool adds about $0.01 per 60 s quote here.
- Comparative statics as built: a larger sigma or tau never tightens a flat, symmetric quote, and never tightens the bid that adds to expected inventory. The bid that sheds expected inventory can tighten under a larger sigma or tau: that is the inventory term doing its job (as in Avellaneda-Stoikov), not a bug, and it follows from J as specified.
- Reward formula re-read on docs.polymarket.com/market-makers/liquidity-rewards (2026-10-01): S, Q_one, Q_two, Q_min with c = 3 and the 0.10-0.90 band match; tests pin S(4.5, 1.5) = 0.4444 and agree with Phase 0's research.measure.reward_income scorer.

## How to reproduce

From `roster/`:

```
.venv\Scripts\python.exe -m learning.quote_objective --smoke
.venv\Scripts\python.exe -m pytest tests/phase5/test_quote_objective.py -q
```

Uses the latest `data/markets/` snapshot and the recorded Parquet books on this PC (read-only); no network.
