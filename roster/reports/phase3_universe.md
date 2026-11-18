# Phase 3 / WP3-C: universe extension (SOL/XRP ladders, wider BTC/ETH strikes, touch templates)

Build-plan task 3.4, roles 16 and 17. Module: `trader/growth/universe.py`. Tests: `tests/phase3/test_universe.py` (41 pass).

**Status: code complete, not wired, not live.** Every addition is a registry `candidate` with its own pre-registered test. None of them trades until it has gone through Loop B (replay, then shadow, then canary) and you have signed its token. The baseline entry is exactly what the Phase 1 ladder trades today: crypto-term BTC/ETH strike and Up/Down markets at τ ≤ 24 h, the same filter as `ladder.py`. The module does no I/O, and only the optional `--smoke` path makes public read-only GETs.

## Assets

| asset | Binance symbol | Gamma slug prefixes | `source_id` | vol source | state | Loop B |
|---|---|---|---|---|---|---|
| BTC | BTCUSDT | `bitcoin`, `btc` | `binance:BTC/USDT` | `dvol` | baseline | no |
| ETH | ETHUSDT | `ethereum`, `eth` | `binance:ETH/USDT` | `dvol` | baseline | no |
| SOL | SOLUSDT | `solana` | `binance:SOL/USDT` | `realized` | candidate | yes |
| XRP | XRPUSDT | `xrp` | `binance:XRP/USDT` | `realized` | candidate | yes |

How the vol sources were chosen: the 2026-10-01 smoke asked Deribit's public `get_volatility_index_data` for each asset. It returned BTC 35.97 and ETH 49.85, and nothing for SOL or XRP. For a realized-vol asset, σ_Q is the sample SD of 1m log returns over the last `vol_bars` = 1440 closes, annualised on a 365-day year. It is None when fewer than `min_bars` = 720 closes exist. This parameter set is registered as `universe-vol` v1, state `candidate`.

## Entries

All entries are `mode = crypto-term` and version 1. `accepts(entry, m, S, σ, now)` requires the mode, asset and kind to match and 0 < τ ≤ `max_tau_h`. When `band_z` is set, it also requires |ln(K/S)| ≤ band_z·σ·√τ, and it fails closed if K, S or σ is missing.

| id | assets | kinds | max τ (h) | band_z | state | Loop B | pre-registration |
|---|---|---|---|---|---|---|---|
| `baseline` | BTC, ETH | strike, updown | 24 | none | baseline | no | Phase 1's own |
| `sol-ladder` | SOL | strike, updown | 24 | none | candidate | yes | `universe-sol-ladder-v1` |
| `xrp-ladder` | XRP | strike, updown | 24 | none | candidate | yes | `universe-xrp-ladder-v1` |
| `btc-eth-wide-strikes` | BTC, ETH | strike | 168 | 2.0 | candidate | yes | `universe-btc-eth-wide-strikes-v1` |
| `btc-eth-touch` | BTC, ETH | touch-up, touch-down | 24 | none | candidate | yes | `universe-btc-eth-touch-v1` |

Every pre-registration is a complete dict:
- **Statistic:** the fee-net 5-minute markout per fill (size × (mid_ex_own 5 min later − fill price) + maker rebate + allocated reward), summed per cluster.
- **Cluster:** `cluster_id`. **SE:** cluster-robust.
- **Pass:** alpha 0.0228; PASS if mean > 2 SE with n ≥ 60 clusters (pass_z 2.0).
- **Futility:** stop if mean < −1 SE once n ≥ 30 clusters.
- **Also recorded:** the data used and the params `{entry, version, vol}`.

Each addition has a unique name, so each one passes or fails on its own. `REGISTRY` holds `universe-<id>` (the entry minus its prereg) plus `universe-vol`, all as `candidate`. The test writes all of them into a temporary `Ledger` to show they register and preregister as they are.

**Evidence clusters (`cluster_id`).** A cluster is the settlement instant plus the set of assets merged at that instant. The merge is union-find over asset pairs. A pair stays apart only if its measured residual correlation is below 0.3. An unmeasured or NaN pair counts as merged. The exposure `event_group` (`<ASSET>@<end>` or `<ASSET>-touch@<end>`, per asset as in role 01) is unchanged.

## What each entry needs before it goes live

| entry | needs (all of these are [ops]) |
|---|---|
| `sol-ladder`, `xrp-ladder` | <ul><li>Record SOL/XRP books and Binance 1m klines.</li><li>Fit κ per τ bucket on recorded data, the same way Phase 0 fitted BTC/ETH.</li><li>Check the realized σ_Q window (1440 bars, at least 720) against recorded outcomes.</li><li>Loop B: replay, then shadow, then canary, then your token, against `universe-<asset>-ladder-v1`.</li><li>Sign clearances for `crypto-term:SOL:*` / `crypto-term:XRP:*`.</li><li>Kernel: add the `source_id`s to `STRATEGIES[...]["sources"]` and XRP to the cross-instant stress cap.</li></ul> |
| `btc-eth-wide-strikes` | <ul><li>Refit κ for τ > 24 h. Today `kappa_for` reuses the 24 h bucket, and `ladder.py` caps τ at 24 h.</li><li>Raise the ladder's `max_tau_h` only for markets this entry accepts.</li><li>Loop B against `universe-btc-eth-wide-strikes-v1`. Its data is fills at τ > 24 h only, because the baseline covers τ ≤ 24 h.</li></ul> |
| `btc-eth-touch` | <ul><li>The WP3-A touch pricer goes through its own Loop B. The touch κ is a `candidate` that failed its Phase 0 test at 1.8 SE.</li><li>`marketdata` keeps the running 1m high/low from `window_start_ms(row)`.</li><li>Loop B against `universe-btc-eth-touch-v1`.</li><li>Sign clearances for `crypto-term:<ASSET>:touch-up` / `:touch-down`.</li><li>Weekly, monthly and year-end touch markets are classified, but this entry doesn't accept them (τ > 24 h) until κ for τ > 24 h is refit (WP3-A, A10).</li></ul> |

SOL/XRP touch markets are classified and parsed, but no entry covers them. A `sol-xrp-touch` entry would need both the SOL/XRP vol fit and the touch pricer to have passed first.

## Slug shapes and classification

`mode_of_ext(slug) -> (mode, asset, kind)`. For every BTC/ETH slug it gives the same mode as `recorder.crawler.mode_of`. I checked these shapes against what Gamma returned live on 2026-10-01:

| template | slug | question |
|---|---|---|
| daily strike | `solana-above-on-october-2-2026` | "Will the price of Solana be above $95 on October 2?" |
| daily Up/Down | `xrp-up-or-down-on-october-1-2026` | "XRP Up or Down on October 1?" |
| touch, day | `what-price-will-bitcoin-hit-on-october-1-2026` | "Will Bitcoin reach $91,000 on October 1?" |
| touch, week | `what-price-will-solana-hit-september-28-october-4-2026`, `...-hit-september-21-27-2026` | "Will Solana reach $190 September 28-October 4?" |
| touch, month | `what-price-will-xrp-hit-in-october-2026` | "Will XRP dip to $1.40 in October?" |
| touch, year | `what-price-will-bitcoin-hit-before-2027` | "Will Bitcoin dip to $60,000 by December 31, 2026?" |

Deliberately left unclassified (None), because no entry covers them:
- SOL/XRP `-updown-5m/15m/4h-` slugs and the hourly `solana-up-or-down-october-1-2026-3am-et`
- the `-price-on-` range buckets
- `what-price-will-ethbtc-hit-...`, `will-solana-hit-X-or-Y-first` and the all-time-high markets
- older closed touch slugs without a year (`what-price-will-bitcoin-hit-january-5-11`)

`market_info_ext(row)` builds the `MarketInfo` for these templates:
- **BTC/ETH strike and Up/Down:** it calls `marketdata.market_info` and returns the same `MarketInfo` (tested on fixtures and on every classified row of the latest snapshot).
- **Other templates:** it reuses `market_info`'s field checks, then sets the asset from the slug and the kind and strike from the question. For a touch market, "reach $H" gives `touch-up` and "dip to $H" gives `touch-down`, with the barrier in USDT.
- **event_group:** `<ASSET>@<end UTC>`, or `<ASSET>-touch@<end UTC>` for touch markets.
- **source_id:** through `marketdata.source_id`. For touch markets, a local parser handles the touch rules phrasing ("Binance 1-minute candle for Solana (SOL/USDT)"). It returns `binance:<X>/USDT` only if the rules name the candle field the kind needs (High for an up-touch, Low for a down-touch). Otherwise it returns "", like `market_info` does, so the kernel's provenance check refuses the market.
- **Missing fields:** if a token, end, tick, minimum size, fee or the strike/barrier is missing, it returns None.

`window_start_ms(row)` gives the start of the touch window. It is None whenever the start is unknown:
1. If the rules say "creation of this market" (markets added mid-window, most year-end markets), the start is the market's `open_time`. Price action before creation doesn't count.
2. If the rules name an explicit ET start ("between November 24, 2025, 14:00 and December 31, 2026, 23:59 in the ET timezone"), that is the start. 67 of today's open year-end markets use this phrasing.
3. Otherwise, the start is 00:00 ET on the first day in the slug.

A slug-based start must also fit the market's end: 0 < end − start ≤ the window length (1, 7 or 31 days) + 1 day. This catches a year convention we haven't seen.

## Smoke results (2026-10-01, 12:23 UTC; public Gamma and Deribit GETs only)

`python -m trader.growth.universe --smoke`:
- 1882 open events, tags solana/xrp/bitcoin/ethereum, ending within 100 days
- BTC/ETH slugs where `mode_of_ext` and `crawler.mode_of` disagree: **0**

New-template events and open markets:

| asset | strike events (markets) | Up/Down events (markets) | touch events | touch-up markets | touch-down markets |
|---|---|---|---|---|---|
| SOL | 7 (77) | 2 (2) | 4 | 33 | 30 |
| XRP | 7 (77) | 2 (2) | 4 | 34 | 24 |
| BTC | baseline | baseline | 4 | 40 | 39 |
| ETH | baseline | baseline | 4 | 35 | 33 |

- **All 426 open new-template markets** gave a `MarketInfo`. None had a missing field. None had an empty `source_id`, and none of the touch markets lacked a window start.
- **First smoke pass:** it found 67 year-end touch markets with no window start. Their rules give an explicit ET start date instead of the creation clause. I then added parsing for that phrasing, and the gap went to 0.
- **Examples:**
  - `solana-above-on-october-1-2026` gives strike 90.0, `binance:SOL/USDT`, `SOL@2026-10-01T16:00Z`.
  - `what-price-will-xrp-hit-before-2027` "Will XRP dip to $1.00 by December 31, 2026?" gives a touch-down with barrier 1.0. Its window runs from 2026-08-25T04:21Z (creation) to 2027-01-01T05:00Z, with group `XRP-touch@2027-01-01T05:00Z`.
  - `what-price-will-bitcoin-hit-september-28-october-4-2026` gives a window from 2026-09-28T04:00Z to 2026-10-05T04:00Z.
- **DVOL:** BTC 35.97, ETH 49.85; SOL and XRP return none, which matches the configured vol sources.

## Findings and contract gaps

- **Window start.** `MarketInfo` has no field for it, which is a known gap. `window_start_ms` reads it from the crawler row. The year-end windows can start as early as 2025-11-24, so their running high/low needs a kline backfill longer than the 1m live stream. Daily 1d candles plus 1m bars for the partial days would cover it.
- **Weekly windows that cross a year.** I assume the slug's year is the week's end year. No live example exists, and the closed 2025/26 week (`what-price-will-bitcoin-hit-december-29-january-4`) had no year. If Gamma uses the start year instead, the end-fit check returns None (fail closed), not a wrong start.
- **XRP year-end rules** name both High and Low in one text ("above for ↑ High, below for ↓ Low"), so the field check passes for both kinds there. The kind comes from the question.
- **The crawler's crypto-term horizon (8 days)** doesn't reach the monthly or year-end touch windows. That matters only for recording them, because the touch entry accepts τ ≤ 24 h.

## Wiring later (nothing here is wired)

- `recorder.crawler.SLUG_MODE` adopts `SLUG_MODE_EXT` (call `mode_of_ext(slug)[0]`), and the crawler also queries the `solana` and `xrp` tags. `marketdata.load_markets` maps rows with `market_info_ext`, which is identical to `market_info` for BTC/ETH.
- `marketdata` subscribes to `ASSETS[a]["symbol"]` and keeps each touch window's running 1m high/low from `window_start_ms(row)` in `ref[asset]["high"/"low"]`. For SOL/XRP it supplies `ref[asset]["sigma_q"] = sigma_q_for(asset, ref, closes_1m)`.
- Kernel: `STRATEGIES[...]["sources"]` gains `binance:SOL/USDT` and `binance:XRP/USDT`, and the cross-instant stress cap adds XRP to BTC/ETH/SOL.
- Role 16's selector keeps a market only if `accepts(entry, m, S, σ, now)` holds for an entry whose `universe-<id>` registry version is live in the ledger. The baseline is always on. The scorer groups evidence with `cluster_id(m, measured_corr, assets_settling_at_that_instant)`.
- `REGISTRY` and each entry's `PREREG` are written to the ledger once, before any of that entry's data is analysed.

## How to reproduce

From `roster/`:

```
.venv\Scripts\python.exe -m pytest tests/phase3/test_universe.py -q
.venv\Scripts\python.exe -m trader.growth.universe --smoke
```

- The first command runs the unit tests (41, no network). The C1/C2 snapshot checks use the latest `data/markets/*.jsonl` and skip if none exists.
- The second command is optional and makes public read-only GETs to Gamma and Deribit. On Windows consoles, set `PYTHONIOENCODING=utf-8` first.
