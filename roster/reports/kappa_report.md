# Go/no-go test A: crypto kappa (WP0-C, build-plan task 0.6)

Generated 2026-09-30 17:15 UTC by `research/kappa/kappa.py` from WP0-B's downloads
(nothing re-downloaded). Public data only; no keys, no orders.

## Verdict: **FAIL**

Plan criterion (build-plan-v4 Phase 0, test A): the kappa-adjusted model beats kappa = 1 by more than 2 day-clustered
standard errors **and** beats the Polymarket mid on log loss.

- Beats kappa = 1 by > 2 SE (log score of the realised settlement, 1671 scored settlement days):
  **no**, gain 0.0072 nats per observation, SE 0.0040 (1.8 SE).
- Beats the Polymarket mid on binary log loss (24754 market-checkpoints, 8279 markets,
  358 days): **no**, model 0.1168 vs mid
  0.1129 (difference 0.0039, day-clustered SE
  0.0011).

At least one condition fails, so test A does not pass on free history.

## Data used

- Binance BTCUSDT and ETHUSDT 1m klines (`data/history/binance/`), the resolution source. Settlement price = close of
  the 1m candle that opens at 12:00 America/New_York; spot at a checkpoint = close of the candle ending h hours before
  that candle closes (tau = exactly 24h, 6h, 1h).
- Deribit DVOL 1h (`data/history/deribit/dvol_*_1h.parquet`): sigma_Q = close of the latest hourly candle that had
  closed by the checkpoint (it closes 1 minute before it).
- Polymarket closed daily strike and Up/Down markets (`data/history/polymarket/markets.parquet`) and 1m price history
  (`data/history/polymarket/prices/`).
- Settlement rows built: 10,386 (asset x day x checkpoint); complete (spot, settlement and DVOL present):
  10,386 over 1,731 days. Scored after a 60-day training-only burn-in:
  **10,026 rows over 1,671 settlement days** (2022-03-04 to 2026-09-29).
- Settlement check: the Binance-derived outcome (S_T > K; Up/Down: S_T > previous noon close) disagrees with
  Polymarket's resolved outcome on 0 market-checkpoint rows (0 markets).
  Polymarket's outcome is used as the label.

## Method

- Pricer: log S_T ~ N(log S_t - s^2/2, s^2), s = sigma_P sqrt(tau), sigma_P = kappa(bucket) x sigma_Q, zero drift.
  Strike: P(S_T > K) = N(d2). Up/Down: P(S_T >= S_open) with S_open = the previous day's 12:00 ET close (at T-24h
  the checkpoint is that close, so p = N(-s/2)). No skew term: free historical option IVs by strike do not exist
  (Deribit's public API has only DVOL history), so the plan's `- F phi(d1) sqrt(tau) dsigma/dK` is left out.
- kappa: 3 parameters (one per checkpoint), pooled over BTC and ETH, maximising the summed log score of the realised
  settlement (log density of ln(S_T/S_t)). Walk-forward: kappa for day d uses only days strictly before d (expanding
  window, refitted every day); the first 60 days are training only.
- Gain over kappa = 1: mean per-observation log-score difference; SE clustered by settlement day (BTC, ETH and the three
  checkpoints of one day share a cluster).
- PIT = model CDF at the realised settlement: one value per settlement instant, so it covers every strike at once.
  Uniformity: Kolmogorov-Smirnov per asset and checkpoint (one observation per settlement day), plus the share inside the
  central 90% band (5-95%), which should be 90%.
- Binary log loss: probabilities clipped to [0.001, 0.999] (Polymarket's finest tick) for the model and the mid
  alike. Polymarket mid = the YES token's last `/prices-history` point at or before the checkpoint; points older than
  10 minutes are dropped. Market-checkpoints without a fresh mid:
  4,512 in events WP0-B has not downloaded yet (pending in reports/history_manifest.md; these settle
  2022-09-23 to 2025-10-14), 45 listed after the checkpoint, and
  44 stale. The mid comparison therefore covers 2025-10-07 to 2026-09-29 only (partial history).

## kappa per bucket

sigma_P = kappa x DVOL. kappa < 1 means DVOL overstates the vol that followed.

| bucket | kappa (all days, for registration) | walk-forward first | min | median | max | last |
|---|---|---|---|---|---|---|
| T-1h | 1.150 | 1.050 | 0.910 | 1.026 | 1.152 | 1.149 |
| T-6h | 1.034 | 1.022 | 0.841 | 0.928 | 1.035 | 1.034 |
| T-24h | 0.905 | 1.113 | 0.873 | 0.894 | 1.114 | 0.905 |

## Log score of the realised settlement: kappa vs kappa = 1

Walk-forward kappa, scored days only. Gain > 0 favours the kappa model.

| bucket | obs | days | mean log score kappa | mean log score kappa=1 | gain / obs | day-clustered SE | gain / SE |
|---|---|---|---|---|---|---|---|
| T-1h | 3342 | 1671 | 3.5104 | 3.4944 | 0.0160 | 0.0090 | 1.8 |
| T-6h | 3342 | 1671 | 2.7311 | 2.7326 | -0.0015 | 0.0050 | -0.3 |
| T-24h | 3342 | 1671 | 2.1744 | 2.1675 | 0.0069 | 0.0052 | 1.3 |
| all | 10026 | 1671 | 2.8053 | 2.7981 | 0.0072 | 0.0040 | 1.8 |

## PIT uniformity

| asset, checkpoint | days | KS D (kappa) | KS p (kappa) | KS D (kappa=1) | KS p (kappa=1) | in 5-95% band (kappa) | in 5-95% band (kappa=1) |
|---|---|---|---|---|---|---|---|
| BTC T-1h | 1671 | 0.075 | 1.41e-08 | 0.070 | 1.78e-07 | 90.1% | 89.4% |
| BTC T-6h | 1671 | 0.069 | 2.75e-07 | 0.078 | 2.34e-09 | 88.7% | 90.0% |
| BTC T-24h | 1671 | 0.081 | 5.71e-10 | 0.098 | 2.28e-14 | 90.9% | 92.9% |
| ETH T-1h | 1671 | 0.082 | 4.11e-10 | 0.074 | 1.87e-08 | 90.7% | 89.3% |
| ETH T-6h | 1671 | 0.071 | 7.81e-08 | 0.077 | 3.76e-09 | 88.5% | 89.5% |
| ETH T-24h | 1671 | 0.061 | 6.46e-06 | 0.081 | 5.85e-10 | 90.5% | 92.6% |

## Binary log loss on Polymarket's daily markets: kappa vs kappa = 1

Every closed strike and Up/Down market on a scored day (whether or not it was listed yet at the checkpoint). Negative
diff favours the kappa model; SE clustered by settlement day.

| slice | obs | markets | days | log loss kappa | log loss kappa=1 | diff | SE |
|---|---|---|---|---|---|---|---|
| all | 29355 | 9785 | 636 | 0.1327 | 0.1328 | -0.0002 | 0.0003 |
| strike T-1h | 8669 | 8669 | 499 | 0.0410 | 0.0416 | -0.0006 | 0.0003 |
| strike T-6h | 8669 | 8669 | 499 | 0.0959 | 0.0957 | 0.0002 | 0.0002 |
| strike T-24h | 8669 | 8669 | 499 | 0.1397 | 0.1397 | -0.0000 | 0.0008 |
| updown T-1h | 1116 | 1116 | 562 | 0.2009 | 0.2019 | -0.0010 | 0.0024 |
| updown T-6h | 1116 | 1116 | 562 | 0.4471 | 0.4471 | 0.0000 | 0.0006 |
| updown T-24h | 1116 | 1116 | 562 | 0.6936 | 0.6937 | -0.0001 | 0.0000 |

## Model vs Polymarket mid (overlapping markets)

Market-checkpoints with a fresh mid. Negative `kappa - mid` means the model had the lower log loss.

| slice | obs | markets | days | log loss kappa | log loss mid | kappa - mid | SE | log loss kappa=1 |
|---|---|---|---|---|---|---|---|---|
| all | 24754 | 8279 | 358 | 0.1168 | 0.1129 | 0.0039 | 0.0011 | 0.1171 |
| strike T-1h | 7568 | 7568 | 344 | 0.0376 | 0.0358 | 0.0018 | 0.0010 | 0.0382 |
| strike T-6h | 7550 | 7550 | 344 | 0.0896 | 0.0840 | 0.0057 | 0.0018 | 0.0894 |
| strike T-24h | 7512 | 7512 | 342 | 0.1260 | 0.1245 | 0.0015 | 0.0015 | 0.1263 |
| updown T-1h | 711 | 711 | 356 | 0.2180 | 0.1973 | 0.0206 | 0.0080 | 0.2214 |
| updown T-6h | 709 | 709 | 355 | 0.4795 | 0.4551 | 0.0244 | 0.0080 | 0.4780 |
| updown T-24h | 704 | 704 | 353 | 0.6933 | 0.6972 | -0.0040 | 0.0032 | 0.6933 |

## Limitations

- DVOL is a 30-day constant-maturity index, not the 1h-24h implied vol at the strike. kappa absorbs the term-structure
  gap and intraday seasonality (noon ET is a busy hour), so it is a DVOL-to-realised scale, not a pure risk premium.
  Once the recorder has Deribit option summaries, sigma_Q can be the interpolated short-dated IV with skew.
- No skew or fat tails: far strikes are priced by a lognormal. The clip at 0.001 caps the loss on a very confident miss.
- Binance USDT pairs are used directly; the USDT/USD basis and the Deribit forward are ignored (zero drift from spot).
- The Polymarket comparison covers only WP0-B's downloaded price history (2025-10-07 to 2026-09-29) and
  only markets listed at the checkpoint. `/prices-history` gives one point about every minute; WP0-B describes it as the mid, and Polymarket's docs
  do not say whether wide-spread books show the last trade instead. A mid is not a tradable price: beating it on log
  loss is necessary, not sufficient, for a trading edge after spread and fees.
- One expanding window: kappa adapts slowly to regime changes. A rolling window or vol-regime cells are Loop B candidates.
- Up/Down ties (50-50) are not modelled; none occurred in the data.

## How to reproduce

From `roster/` (needs WP0-B's `data/history/` downloads; about 2-3 minutes, no network):

```
.venv\Scripts\python.exe -m research.kappa.kappa          # writes this report and research/kappa/out/*.parquet, summary.json
.venv\Scripts\python.exe -m pytest research/kappa -q       # unit tests
```
