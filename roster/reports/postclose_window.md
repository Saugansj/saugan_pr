# Post-close window (WP0-E, build-plan task 0.11)

Generated 2026-10-01 05:45 UTC. Public read-only data; no orders, no keys.

## Answer

- **2075 prints analysed** (8305 daily markets in 1403 daily prints from WP0-B, 672 hourly markets from the last 14 days). A print is one resolution (one asset, one template, one settlement time); a daily strike ladder is one print with many markets.
- **How often:** a winning-side ask at <= 0.98 with >= 5 shares (a taker BUY fill there) appeared after **0.9%** of prints. The plan's suggested gate is one third (33.3%): **NOT MET**, so post-close capture does not go to Phase 1 paper on this evidence.
- **How cheaply and what size:** 102 winning-side fills at <= 0.98 and 1005 at <= 0.99 in the 10 s - 120 min windows (table below). Most post-print winning-side volume trades at 0.99-0.999. Excluded as possibly pre-print: 312 winning-side fills at <= 0.98 (249,124 shares) stamped in the first 10 s.
- **Expected $/day at the plan's sizing ($50, quarter Kelly, c = 0.3, q = 0.995, caps 20% / 10%): $0.279/day** (daily prints $0.027 + hourly $0.252). 134 fills pass the sizer; the rest are refused because the shrunk edge is <= 0 or the Kelly stake is under 5 shares. This is an upper bound: it assumes we get every such fill before other takers/makers.
- **Wrong or disputed resolutions:** 1 disputed of 8977 markets with a UMA record (0.01%), 0 where the final price differs from the first proposal; 0 of 8919 markets whose recorded winner disagrees with the winner recomputed from Binance (0.000%; plan assumes 0.5%, 95% upper bound 0.034% by the rule of three).

## Frequency, size and timing per print

`ask` = a winning-side taker BUY fill of >= 5 shares at the price or better (an ask was there to take); `bid fill` = a taker SELL fill of >= 5 shares (a resting bid there was filled: our maker bid could have been). Shares are all winning-side fills at the price or better; minutes are after the print. `mid<=0.98 minute` = the winner's 1m price-history point sat at <= 0.98 at least once in the window.

|                                |     all |   daily-strike |   daily-updown |   hourly-updown |
|:-------------------------------|--------:|---------------:|---------------:|----------------:|
| prints                         |  2075   |          688   |          715   |           672   |
| markets                        |  8977   |         7590   |          715   |           672   |
| ask<=0.98 (>=5sh) %            |     0.9 |            1.5 |            0.6 |             0.6 |
| bid fill<=0.98 %               |     0.4 |            0.7 |            0.3 |             0.1 |
| either<=0.98 %                 |     1   |            1.6 |            0.8 |             0.6 |
| ask<=0.99 (>=5sh) %            |     1.1 |            1.9 |            0.8 |             0.6 |
| either<=0.99 %                 |     7.3 |            7.7 |            5.3 |             9.1 |
| median shares<=0.98 | any      |   118.5 |         3577.4 |            7.8 |           242.9 |
| mean shares<=0.98 | any        |  3073   |         5931.4 |          778.3 |           375.4 |
| p90 shares<=0.98 | any         | 12086.8 |        13027.5 |         2498.7 |           804.6 |
| shares<=0.99 per print         |   154   |          364.9 |           75.1 |            22   |
| median first min | any         |    25   |           24.7 |           25.3 |            28.3 |
| median span min | any          |     0   |            0.1 |            0   |             0   |
| prints with mid<=0.98 minute % |     3.1 |            4.5 |            1.4 |             3.6 |

## Expected income at the plan's sizing

Each winning-side fill at <= 0.99, in time order, goes through the plan's sizer: q = 1 - 0.005, m = the winner's last 1m mid (fill price if none), q_used = m + 0.3 (q - m), cost = price + 0.07 p (1 - p) (taker BUY only; as a maker bid we pay no fee) + lockup price x 20%/yr x 2h, f = (q_used - cost) / (1 - cost), stake = 0.25 f x bankroll, capped by the fill's size, 10% of bankroll per market and 20% per print time (BTC and ETH, strike and Up/Down, all resolve together at 12:00 ET); floor to whole shares, refuse < 5. Expected P&L = shares x (0.995 - cost). The $250 row is the next capital-ladder step, for scale.

|   bankroll $ | prints   |   days |   captures | taker / maker   |   shares |   avg price |   expected $ total |   $/day |
|-------------:|:---------|-------:|-----------:|:----------------|---------:|------------:|-------------------:|--------:|
|           50 | daily    |    359 |         82 | 9 / 73          |      412 |      0.9727 |               9.74 |   0.027 |
|           50 | hourly   |     14 |         52 | 1 / 51          |      261 |      0.9825 |               3.53 |   0.252 |
|          250 | daily    |    359 |        108 | 12 / 96         |     2014 |      0.9759 |              33.39 |   0.093 |
|          250 | hourly   |     14 |         73 | 3 / 70          |     1143 |      0.9748 |              19.73 |   1.409 |

## Wrong and disputed resolutions

- Source 1, Data API `/v2/resolutions?condition=<id>` (built from UMA events: `was_disputed`, `proposed_price`, `price`, `status`): 8977 of 8977 markets have a record; statuses {'resolved': 8977}; disputed 1; proposal differs from final 0.
- Source 2, recompute from WP0-B's Binance 1m klines (rules text: strike = 12:00 ET 1m close > K; daily Up/Down = that close vs the previous day's 12:00 ET close, equal = 50-50; hourly = 1H close >= 1H open, from the hour's first 1m open and last 1m close). Markets after 2026-09-29 have no Binance file yet.

| kind          |   markets |   wrong |
|:--------------|----------:|--------:|
| daily-strike  |      7568 |       0 |
| daily-updown  |       713 |       0 |
| hourly-updown |       638 |       0 |

No disagreements.

## Limits

- Timestamps: a Data API fill's timestamp is 1.38-3.0 s (p10-p90, median 2.42 s) after the match time of the same trade in WP0-A's recorded WebSocket `last_trade_price` messages (156 trades matched by transaction hash), i.e. it is the on-chain time. Fills stamped in the first 10 s after the print are therefore excluded; most cheap winning-side fills sit there and were probably matched before the outcome was known.
- The Data API gives taker fills, not the book: an ask or bid that rested without being hit is invisible, so frequencies are lower bounds for availability, while the $/day assumes we win every observed fill (an upper bound for our capture). The book-based measure (best ask, size, how long it lasted) needs the recorder's post-print books on the VM.
- Losing-side fills are not counted (8092 in the windows): through the CLOB's MINT/MERGE matching a loser fill at x can be the other leg of a winner order at 1 - x, but the API does not say which.
- 1m price-history points are the only book proxy after the print; `mid<=0.98` minutes use them.
- Hourly markets close (automatic resolution) about 12 minutes after the print, so their window is short; daily markets stay open about 2 hours (UMA challenge window).
- Fee rate 0.07 is today's crypto schedule (WP0-A crawl), applied to all history.

## How to reproduce

From `roster/` (needs WP0-B's `data/history/polymarket` and `data/history/binance`):

```
.venv\Scripts\python.exe -m research.measure.postclose                 # rewrites this file; first run fetches hourly markets and /v2/resolutions (~20 min at 8 req/s), cached in research/measure/data/
.venv\Scripts\python.exe -m research.measure.postclose --refresh       # refetch the hourly sample
.venv\Scripts\python.exe -m pytest research/measure -q                   # fee and sizer unit tests
```
