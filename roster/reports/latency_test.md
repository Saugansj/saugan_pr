# Latency test (WP0-E, build-plan task 0.12)

Generated 2026-10-01 04:30 UTC. Public data only; no orders, no keys.

## Verdict

**PASS** on the free dataset: mean fee-net edge **2.02c per share ± 0.34c** (market-clustered SE, t = 5.9) over **2165 events**, buying the favoured side at the ask on tick s + 2 (the move's last second is s) and valuing at the mid 30 s later. Rule (plan): PASS needs mean > 2 SE over >= 200 events. Held to resolution instead (no exit cost), the edge is 2.86c ± 0.74c over 2317 events.

- **The edge is a one-to-two-second effect and decays fast** (sensitivity table): entry on tick s + 1 would earn about three times as much; the rule fails from tick s + 3 on. A slower VM, a slower Binance feed, or makers pulling faster than in March-May 2026 removes it.
- **It is not the same for every coin:** BTC +6.67c ± 0.59c over 882 events; ETH -1.18c ± 0.39c over 1283 events. A pooled PASS can hide a losing coin; a live test should use only the coins that pass on their own.
- Polymarket's lag: over 1727 events where the favoured mid moved >= 2c by s + 60, it had covered half of that move a median **0 s** after the Binance second closed (p25 -1 s, p75 2 s; <= 0 = within the same second, before we could act). 73% had covered half the move before our order meets the book.
- Scale: about 46 events a day across BTC and ETH; at 5 shares each that is about **$3.62/day** before any competition for the same asks.
- Events detected: 2918; with a book and >= 5 shares at the entry ask: 2421 (497 dropped: no tick, empty side or too little size).
- This gates only fast Up/Down in Phase 3. **[ops] E6**: the 4-week test on our own recordings (recorder `--fast` plus Binance, measured from the VM) is still to run and decides it.

## Results (plan entry)

| entry                    | valued at           |   events |   mean edge (c/share) |   SE (c) |    t | verdict   |
|:-------------------------|:--------------------|---------:|----------------------:|---------:|-----:|:----------|
| tick s + 2 (150ms + RTT) | mid +10s            |     2265 |                 1.75  |    0.245 | 7.14 |           |
| tick s + 2 (150ms + RTT) | mid +30s            |     2165 |                 2.019 |    0.344 | 5.88 | PASS      |
| tick s + 2 (150ms + RTT) | mid +60s            |     1993 |                 1.995 |    0.452 | 4.41 |           |
| tick s + 2 (150ms + RTT) | final outcome (1/0) |     2317 |                 2.856 |    0.741 | 3.86 |           |

| coin   |   events |   events/day |   markets |   mean edge (c) |   SE (c) |   median ask |   median fee (c) |   median ask size |
|:-------|---------:|-------------:|----------:|----------------:|---------:|-------------:|-----------------:|------------------:|
| btc    |      882 |         16.2 |       842 |           6.67  |    0.589 |         0.75 |            1.12  |               129 |
| eth    |     1283 |         30.1 |      1149 |          -1.179 |    0.391 |         0.81 |            0.893 |                60 |

## Sensitivity to the entry tick

Same events, entering on tick s + k. k = 1 is the book one second after the move's last second, before our order could arrive (an upper bound); each extra second stands for extra latency or a clock error.

| entry      | valued at     |   events |   mean edge (c/share) |   SE (c) |     t | verdict   |
|:-----------|:--------------|---------:|----------------------:|---------:|------:|:----------|
| tick s + 1 | mid +30s      |     2168 |                 6.506 |    0.385 | 16.92 | PASS      |
| tick s + 1 | final outcome |     2352 |                 7.212 |    0.747 |  9.65 | PASS      |
| tick s + 2 | mid +30s      |     2165 |                 2.019 |    0.344 |  5.88 | PASS      |
| tick s + 2 | final outcome |     2317 |                 2.856 |    0.741 |  3.86 | PASS      |
| tick s + 3 | mid +30s      |     2156 |                 0.499 |    0.329 |  1.51 | FAIL      |
| tick s + 3 | final outcome |     2313 |                 1.624 |    0.736 |  2.2  | PASS      |
| tick s + 4 | mid +30s      |     2175 |                -0.657 |    0.305 | -2.15 | FAIL      |
| tick s + 4 | final outcome |     2319 |                 0.554 |    0.727 |  0.76 | FAIL      |
| tick s + 5 | mid +30s      |     2165 |                -0.943 |    0.304 | -3.1  | FAIL      |
| tick s + 5 | final outcome |     2295 |                 0.232 |    0.732 |  0.32 | FAIL      |

## Clock check of the dataset

Share of Data API taker BUY fills (120 random BTC markets) whose price equals the kacho best ask of the bought token at the fill's timestamp + shift. Best at **-3 s** (52.9%). Data API timestamps are on-chain times, 2.42 s (median; p10-p90 1.38-3.0 s) after the match (measured on 156 trades against WP0-A's recorded WebSocket match times), so the kacho tick that best matches a fill sits about -0.6 s from the match: the dataset's clock is within about a second of real time, not late (a late clock would inflate the edge).

|   shift s |   fills |   price = ask % |
|----------:|--------:|----------------:|
|        -8 |   92469 |            17.6 |
|        -7 |   92469 |            20.8 |
|        -6 |   92469 |            25.1 |
|        -5 |   92469 |            31.1 |
|        -4 |   92469 |            44.6 |
|        -3 |   92469 |            52.9 |
|        -2 |   92469 |            42.5 |
|        -1 |   92469 |            30.8 |
|         0 |   92469 |            24.3 |
|         1 |   92469 |            20.3 |
|         2 |   92469 |            17   |
|         3 |   92469 |            14.8 |
|         4 |   92469 |            13.5 |

## Method

- Event: Binance 1s close moved >= 10 bp over 5 s (first crossing; then 60 s with no new event), inside a 5-minute market with the whole measurement window in that one market.
- Entry: the move is known when its last 1s candle closes (s + 1). Our order meets the book after the 150 ms taker delay plus a 200 ms round trip (median HTTPS round trip from the build PC to clob.polymarket.com was 197 ms), i.e. at s + 1 + 0.35 s; with 1 Hz ticks we use the first tick at or after that, s + 2, which already includes other takers' and makers' reactions up to then (conservative, if the clock check holds).
- Price: the favoured token's best ask, needing >= 5 shares there (our minimum order). Fee 0.07 x p x (1 - p) per share (today's crypto schedule; makers pay none). No exit fee is charged in the markout rows; the final-outcome rows need no exit.
- Edge per share: the favoured token's mid at entry + H minus ask minus fee (a markout: what Polymarket itself concluded after catching up), or the final outcome (the dataset's inferred outcome, null for some markets) minus ask minus fee.
- SE: cluster-robust by market (events in the same 5-minute market share a cluster).
- Lag: first tick after s - 5 at which the favoured mid had covered half its move from s - 5 to s + 60, in seconds after s + 1; only events where that move is >= 2c.

## Data

| coin   | from             | to               |   markets |   ticks kept |
|:-------|:-----------------|:-----------------|----------:|-------------:|
| btc    | 2026-03-24 22:10 | 2026-05-18 10:35 |     15682 |      4704518 |
| eth    | 2026-04-05 19:25 | 2026-05-18 10:35 |     12258 |      3677321 |

- kacho ticks: one sample per second per market of best bid/ask and sizes for Up and Down (no trades, no depth beyond the touch). Binance 1s klines (data.binance.vision, checksum-verified): close per second, gaps forward-filled. Both are at 1 s resolution, so a sub-second lag cannot be seen.
- Not available: a fill model beyond the touch, queue position, and the markets' resolution source (Chainlink 60s TWAP), which differs slightly from Binance spot; Binance is used for the move only.
- The dataset ends 2026-05-18; fees, taker delay and the bots competing in these markets have changed since.

## How to reproduce

From `roster/` (downloads ~290 MB from Hugging Face and ~100 daily 1s-kline zips into research/measure/data/ on the first run, about 45 min; later runs reuse them and take a few minutes):

```
.venv\Scripts\python.exe -m research.measure.latency --bp 10 --window 5 --rtt-ms 200   # rewrites this file
.venv\Scripts\python.exe -m pytest research/measure -q                              # fee, offset, SE, verdict, edge tests
```
