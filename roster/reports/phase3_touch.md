# Phase 3 WP3-A: touch-market pricer and coherence bound

Module: `trader/growth/touch.py` (pure functions, no I/O, nothing wired). Tests: `tests/phase3/test_touch.py` (15 pass).
Build-plan task 3.1, roles 17 (pricer) and 18 (coherence). Every parameter is a registry `candidate`.

## Formulas

The units match `trader.engines.ladder.digital`: σ is annualised on a 365-day year and τ is in hours, so s = σ·√(τ/8760). The model is GBM with log drift −σ²/2, so S is a martingale. Binance 1m highs and lows are treated as continuous monitoring.

With H' = H × basis, b = |ln(H'/S)|, a = (−b − s²/2)/s and c = (−b + s²/2)/s:

| | one-touch probability |
|---|---|
| up (H' > S), "will X reach $H" | P = N(a) + (S/H')·N(c) |
| down (H' < S), "will X dip to $H" | P = N(c) + (S/H')·N(a) |

- P = 1 if `touched` is set or S is at or beyond the barrier. P = 0 if τ ≤ 0 (or σ ≤ 0) and the barrier was not touched.
- `basis` is USD per USDT. It is 1.0 here, because S is the Binance USDT price and Binance is the resolution source. `one_touch(S, H, basis=b)` equals `one_touch(S, H·b)` exactly.
- `touch_fair` computes σ_P = κ(τ)·σ_Q, with κ taken from `REGISTRY["touch"]["params"]["kappa"]` through `ladder.kappa_for`. The values are ladder κ v1: 1.150 at 1h, 1.034 at 6h and 0.905 at 24h. Above 24h it uses the 24h bucket and returns `kappa_unfitted: True`. `unc` is half the change in f for σ_P ± 10%. The market counts as touched when the running Binance 1m `high` ≥ H (up) or `low` ≤ H (down). Both are in USDT, like H.
- `touch_fair` returns `err` when the price, the vol (`dvol` or `sigma_q`), the barrier, or the relevant running high or low is missing, or when the kind is wrong. A missing running extreme is an error rather than "untouched", because the barrier may already have been hit.

## The ε finding (coherence bound, role 18)

Under this model, with C and P the undiscounted zero-drift call and put at strike H:

- touch_up = 2·digital_up + C(H)/H
- touch_down = 2·digital_down − P(H)/H, where digital_down is the NO token of "above $H"

Both identities hold to 1e-12 on a 216-point grid of S, H, σ and τ (test). An up-touch therefore **always** sits above 2 × digital. The bound touch ≤ 2·digital + ε needs ε = C(H)/H + `eps_tol` for up barriers, and ε = `eps_tol` (0.01) for down barriers. On 10,000 random inputs the model lies inside `bounds(..., eps_tol=0)`. More than 90% of the up-touches with H > S sit more than 1e-6 above plain 2 × digital, so with ε = 0 the check would flag correctly priced up-touch markets.

C(H)/H at representative inputs (S = 100, σ = 0.5):

| H/S | τ (h) | digital_up | 2 × digital | C(H)/H | touch_up |
|---|---|---|---|---|---|
| 1.01 | 24 | 0.3471 | 0.6941 | 0.0062 | 0.7003 |
| 1.01 | 168 | 0.4292 | 0.8585 | 0.0228 | 0.8813 |
| 1.01 | 720 | 0.4439 | 0.8878 | **0.0520** | 0.9398 |
| 1.05 | 24 | 0.0302 | 0.0605 | 0.0003 | 0.0608 |
| 1.05 | 168 | 0.2299 | 0.4598 | 0.0096 | 0.4693 |
| 1.05 | 720 | 0.3402 | 0.6803 | 0.0352 | 0.7155 |
| 1.10 | 168 | 0.0791 | 0.1582 | 0.0025 | 0.1608 |
| 1.10 | 720 | 0.2307 | 0.4614 | 0.0207 | 0.4821 |
| 1.20 | 720 | 0.0895 | 0.1791 | 0.0063 | 0.1854 |

On month-long windows with near barriers, the C/H term (up to about 5 points) is larger than a 1-tick `eps_tol`. A fixed ε would either miss real incoherence or flag fair prices.

`coherence_flags(touch_book, digital_book, ...)` is log-only and works on market prices:

- `"touch<terminal"` when touch_ask < digital_bid
- `"touch>2x_digital+eps"` when touch_bid > 2·digital_ask + ε

There is a wiring caveat. The lower check is model-free, but it needs the digital to settle inside the touch window. The upper check needs the digital to settle at the window end, and the σ and τ passed in must be those of that common horizon. Today's monthly touch windows end at 00:00 ET on the 1st, while the daily digitals settle at 12:00 ET. So for monthly windows only the lower check applies until a digital is found that settles at the window end.

## Monte Carlo check (A2)

The check uses seeded numpy GBM with log drift −σ²/2, 10,000 paths and 10,000 steps per path:

| setting | MC | MC SE | one_touch | allowed (3 SE + 0.01) |
|---|---|---|---|---|
| up S=100, H=110, σ=0.6, τ=720h | 0.5409 | 0.0050 | 0.5518 | 0.025 |
| down S=100, H=92, σ=0.5, τ=240h | 0.3272 | 0.0047 | 0.3269 | 0.024 |

Discrete monitoring makes MC slightly low for the up case, by about 0.58·σ√dt in log barrier distance, as expected. The mean of S_T/S_0 is within 1% of 1 in both runs, which confirms the martingale drift.

## Worked examples

1. Up, S = 100, H = 110, σ = 0.5, τ = 720h: s = 0.14335, b = 0.09531, a = −0.73657, c = −0.59323, N(a) = 0.23069, N(c) = 0.27652, so P = 0.23069 + (100/110)·0.27652 = **0.48207**. Bounds with `eps_tol` 0.01 are (0.23069, 0.49207), where ε = C/H 0.02069 + 0.01.
2. Down, S = 100, H = 90, σ = 0.8, τ = 168h: P = N(c) + (100/90)·N(a) = 0.18523 + 1.1111·0.15711 = **0.35980**. Bounds with `eps_tol` 0.01 are (0.18523, 0.38046).
3. `touch_fair`, BTC reach $87,500 with 30h left, S = 83,667.3, DVOL 36.3: τ = 30h is above 24h, so κ = 0.905 is flagged unfitted. σ_P = 0.3285, f = 0.0194, unc = 0.0120.
4. `touch_fair`, BTC dip to $82,500 with 6h left: κ = 1.034, σ_P = 0.3753, f = 0.1537, unc = 0.0410. With a running low of 82,400 ≤ H, f = 1.0, unc = 0 and touched = True.

## Smoke: model vs mid on the listed monthly touch markets (public GETs, 2026-10-01 09:13Z)

The smoke ran `python -m trader.growth.touch --smoke` against these public sources:

- Gamma events `what-price-will-{bitcoin,ethereum}-hit-in-october-2026` for best bid and ask
- Binance `/api/v3/ticker/price` for S, and 1h klines since 00:00 ET Oct 1 for the running high and low (an hourly high is the maximum of its 1m highs)
- Deribit DVOL, last hourly close

All markets have τ = 738.8h, so κ = 0.905 is unfitted for all of them. Closed markets are skipped (ETH dip to $2,700 had already touched).

| asset | market | S | high/low | σ_Q | f (model) | unc | bid | ask | mid | f − mid |
|---|---|---|---|---|---|---|---|---|---|---|
| BTC | dip to 60,000 | 83667.3 | 83186 | 0.3630 | 0.001 | 0.001 | 0.028 | 0.033 | 0.030 | −0.030 |
| BTC | dip to 65,000 | 83667.3 | 83186 | 0.3630 | 0.009 | 0.007 | 0.032 | 0.069 | 0.051 | −0.041 |
| BTC | dip to 70,000 | 83667.3 | 83186 | 0.3630 | 0.067 | 0.028 | 0.11 | 0.12 | 0.115 | −0.048 |
| BTC | dip to 75,000 | 83667.3 | 83186 | 0.3630 | 0.266 | 0.050 | 0.27 | 0.29 | 0.280 | −0.014 |
| BTC | dip to 77,500 | 83667.3 | 83186 | 0.3630 | 0.438 | 0.048 | 0.40 | 0.41 | 0.405 | +0.033 |
| BTC | dip to 80,000 | 83667.3 | 83186 | 0.3630 | 0.653 | 0.035 | 0.63 | 0.64 | 0.635 | +0.018 |
| BTC | dip to 82,500 | 83667.3 | 83186 | 0.3630 | 0.889 | 0.012 | 0.85 | 0.87 | 0.860 | +0.029 |
| BTC | reach 85,000 | 83667.3 | 84419.7 | 0.3630 | 0.861 | 0.013 | 0.845 | 0.887 | 0.866 | −0.005 |
| BTC | reach 87,500 | 83667.3 | 84419.7 | 0.3630 | 0.624 | 0.033 | 0.64 | 0.65 | 0.645 | −0.021 |
| BTC | reach 90,000 | 83667.3 | 84419.7 | 0.3630 | 0.428 | 0.044 | 0.44 | 0.45 | 0.445 | −0.017 |
| BTC | reach 95,000 | 83667.3 | 84419.7 | 0.3630 | 0.172 | 0.041 | 0.19 | 0.20 | 0.195 | −0.023 |
| BTC | reach 100,000 | 83667.3 | 84419.7 | 0.3630 | 0.056 | 0.024 | 0.08 | 0.10 | 0.090 | −0.034 |
| BTC | reach 150,000 | 83667.3 | 84419.7 | 0.3630 | 0.000 | 0.000 | 0.002 | 0.003 | 0.003 | −0.002 |
| ETH | dip to 2,000 | 2689.86 | 2673.13 | 0.4959 | 0.027 | 0.016 | 0.037 | 0.08 | 0.058 | −0.032 |
| ETH | dip to 2,300 | 2689.86 | 2673.13 | 0.4959 | 0.248 | 0.050 | 0.26 | 0.27 | 0.265 | −0.017 |
| ETH | dip to 2,500 | 2689.86 | 2673.13 | 0.4959 | 0.595 | 0.040 | 0.55 | 0.57 | 0.560 | +0.035 |
| ETH | dip to 2,600 | 2689.86 | 2673.13 | 0.4959 | 0.808 | 0.021 | 0.81 | 0.82 | 0.815 | −0.007 |
| ETH | reach 2,800 | 2689.86 | 2722 | 0.4959 | 0.743 | 0.023 | 0.77 | 0.79 | 0.780 | −0.037 |
| ETH | reach 3,000 | 2689.86 | 2722 | 0.4959 | 0.381 | 0.045 | 0.40 | 0.41 | 0.405 | −0.024 |
| ETH | reach 3,200 | 2689.86 | 2722 | 0.4959 | 0.167 | 0.040 | 0.22 | 0.23 | 0.225 | −0.058 |
| ETH | reach 3,500 | 2689.86 | 2722 | 0.4959 | 0.038 | 0.018 | 0.057 | 0.059 | 0.058 | −0.020 |

These are 21 of the 39 rows. The full output has every listed barrier. Over all 39 markets, mean f − mid = −0.023, mean |f − mid| = 0.030, and 5 of 39 are positive.

How to read this: the model tracks the shape of the barrier ladder well, but sits about 2–3 points below the mid in the wings. That fits the market pricing fatter tails than GBM and/or a longshot premium. It also fits the unfitted 24h κ = 0.905 shrinking the month-long vol. It is not evidence for or against an edge. It is one snapshot of one window, it is not fee- or spread-adjusted, and κ above 24h is exactly what Loop B has to refit. The pre-registered test (`PREREG`, log loss vs mid, clustered per window end) decides.

## Registry and pre-registration (not written anywhere)

- `REGISTRY["touch"]` has version 1 and state `candidate`. Its params are: κ = {24: 0.905, 6: 1.034, 1: 1.150} (a copy of ladder κ v1, never fitted on touch outcomes), `sigma_rel_unc` 0.10 and `eps_tol` 0.01.
- `PREREG` is `touch-v1` and tests the model's log loss against the mid excluding our orders, per (market, daily checkpoint). The cluster is the touch window end instant. The statistic uses a cluster-robust SE, alpha 0.0228 one-sided, PASS at z ≥ 2 with n ≥ 30 clusters, and futility at z < −1 once n ≥ 15. There are few clusters, about 1 per month per window type, so replay on past windows carries most of the n.

## Gaps and wiring notes

- `MarketInfo` has no window start. The caller supplies the running `high` and `low` since the window start (WP3-C's `window_start_ms`). The current crawler (`recorder/crawler.py`) does not list touch events yet. Slugs look like `what-price-will-bitcoin-hit-in-<month>-<year>`, the window runs from 00:00 ET on the 1st to the end of the month, and resolution is "any Binance 1m candle High ≥ H" (reach) or "Low ≤ H" (dip).
- κ keys are ints. A κ dict read back from the JSON ledger has string keys and must be converted before `kappa_for`, which is the same as for ladder κ.
- Phase 1 files to change when wiring: `ladder.fair_value` dispatches `touch-*` to `touch_fair`; the arb scan calls `coherence_flags` (only the lower check for monthly windows, see above); `marketdata` keeps per-window running 1m high and low.
- A10 [ops] is open. The touch markets still have to go through Loop B (replay → shadow → canary → your token). Clearances are signed with `tools/clearance_cli.py` for the templates `crypto-term:<ASSET>:touch-up` and `crypto-term:<ASSET>:touch-down`. κ for τ > 24h is refit through Loop B.

## How to reproduce

From `C:\Users\DELL\Downloads\saugan_pr\market_updated\roster`:

```
.venv\Scripts\python.exe -m pytest tests/phase3/test_touch.py -q          # 15 passed (~15 s, offline)
.venv\Scripts\python.exe -m trader.growth.touch --smoke                    # optional, public GETs only; prints the smoke table
```

The C(H)/H table and the worked examples come from `one_touch`, `digital`, `call_over_h`, `bounds` and `touch_fair` with the inputs shown above. The MC numbers come from `tests.phase3.test_touch.mc_touch` (seed 7).
