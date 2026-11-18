Features: ['speed_only']; global cap 1000.0; Binance receive lag 60 ms; RTT 250.0 ms; book depth 100.0 shares per side (assumed); start cash 50.0. Sim clock, 24 h a day, 08:15 IST breaker reset.

# System backtest v2_nocap: 2026-07-27 to 2026-08-09

Ledger `data/research/backtest/v2_nocap`, window 2026-07-27 00:00:00 to 2026-08-10 00:00:00 UTC (data from 2026-07-27 00:00:00 to 2026-08-09 23:59:46). Paper only: no order ever left this PC.

## Summary

- Runs started: 1; clean shutdowns: 0; still running or ended by a crash or kill: 1 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 161, approved 115, orders 115, paper fills 73, btc-speed events 149 and trades 161.
- Paper P&L to the end of the window: btc-speed +37.38 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 73 | 197.93 | 0.00 | 4.6840 | 0.00 | 240.00 | 0 | 0.00 | +37.3810 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 161 intents, 115 approved, 46 rejected: REDUCING 46.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

Latest distinct rejections:

| Time UTC | Strategy | Reason | Binding cap |
|---|---|---|---|
| 2026-08-06 02:20:19 | btc-speed | REDUCING: only exposure-reducing orders | - |

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | taker | 115 | 73 | 365 | 0.5423 | 4.6840 |

Merges of YES+NO pairs: 0; paper redemptions: 73.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| btc-speed | 5 s | 72 | +10.83c | +1.85c | 1 |
| btc-speed | 60 s | 70 | +12.77c | +2.93c | 3 |
| btc-speed | 300 s | 29 | +8.86c | +5.36c | 44 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-v2**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 73 in 73 markets (needs 200), unresolved 0, mean 0.5121 USD, cluster SE 0.2361, total +37.3810 USD. Verdict: **running (73 of 200)**.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-09 14:24:15), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-09 14:24:15).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

149 causal BTC moves (>= 10.0 bp in 5 s) and 161 trades sent to the kernel. Per mapped market: trade 161, ask above max price 44, ends too soon 35, already holding this market 24, move started before the window 17, no ask 17.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-08-04 13:30:04 | -10.0 | 0x7c860872: move started before the window; 0x908762cf: move started before the window |
| 2026-08-04 13:39:05 | +10.0 | 0x7c860872: trade; 0x9e211716: ends too soon |
| 2026-08-04 13:50:08 | +10.0 | 0x38188b0f: trade; 0x571cfb4b: trade |
| 2026-08-04 14:38:19 | +10.1 | 0x5e8c1758: trade; 0xd1fc7926: trade |
| 2026-08-04 14:40:14 | +10.0 | 0x09ee80ff: trade; 0xd1fc7926: ask above max price |
| 2026-08-04 15:38:33 | +10.0 | 0x0bc015ce: trade; 0x6e966c4d: trade |
| 2026-08-04 15:44:43 | +10.0 | 0x0bc015ce: ends too soon; 0xe5a4d617: ends too soon |
| 2026-08-04 15:49:20 | -10.0 | 0x1ecf2a8f: trade; 0x48656cf2: ends too soon |
| 2026-08-04 19:38:38 | +10.0 | 0x0183ea50: trade; 0xc6d79b03: trade |
| 2026-08-04 19:59:52 | -10.0 | 0x16728961: ends too soon; 0xd1965fae: ends too soon |
| 2026-08-04 20:01:26 | -10.0 | 0x34cc368e: trade; 0xf2088c94: trade |
| 2026-08-04 20:17:04 | -10.0 | 0x077268ff: trade; 0x9fd1c829: ask above max price |
| 2026-08-04 20:40:12 | +10.0 | 0x357121f4: no ask; 0xcd154059: trade |
| 2026-08-04 23:08:54 | +10.0 | 0x470f451f: ask above max price; 0x4a7a214d: no ask |
| 2026-08-06 00:00:00 | +86.8 | 0x220e0d2f: move started before the window; 0xe47b3a34: move started before the window |
| 2026-08-06 02:20:19 | -10.0 | 0x407fbe05: trade; 0xb369bd7a: trade |
| 2026-08-06 12:56:30 | -10.0 | 0x64fd28d6: trade; 0x81bbded0: no ask |
| 2026-08-06 14:42:48 | +10.0 | 0x218ab399: ask above max price; 0x65b20bd2: ask above max price |
| 2026-08-07 02:15:29 | +10.0 | 0x5546f185: trade; 0x667b3040: trade |
| 2026-08-07 02:41:23 | +10.0 | 0x33808dbc: trade; 0x81aa7ab7: trade |
| 2026-08-07 06:47:50 | -10.0 | 0x34f57349: trade; 0xd2aa257a: trade |
| 2026-08-07 07:21:51 | +10.0 | 0x62d5530f: trade; 0xdfd59011: trade |
| 2026-08-07 08:42:12 | +10.0 | 0x43a8b6db: no ask; 0xf4d42ae8: no ask |
| 2026-08-07 09:25:10 | +10.1 | 0x174430d8: ask above max price; 0xb283f7c7: trade |
| 2026-08-07 12:29:48 | -10.0 | 0x7c7981fb: ends too soon; 0xc787cd0b: ends too soon |
| 2026-08-07 13:49:40 | +10.0 | 0x79b8c9d8: trade; 0xee9c6ae6: ends too soon |
| 2026-08-07 20:01:42 | +10.0 | 0x721ffe34: trade; 0xa447128b: ask above max price |
| 2026-08-07 21:41:09 | -10.1 | 0x0697c3d2: trade; 0xa609fc76: trade |
| 2026-08-09 08:04:42 | +10.0 | 0x79ade561: ends too soon; 0xc609b6b0: ask above max price |
| 2026-08-09 22:14:21 | +10.0 | 0x022f109d: ends too soon; 0xd3f9c53e: ends too soon |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-08-04 02:34:09 | 0xe46982ff | 15m | 0.9 | approved | open | 5 | 0.900 | 0.0315 | 0.4685 |
| 2026-08-04 04:46:40 | 0x1e175149 | 5m | 0.7 | approved | open | 5 | 0.700 | 0.0735 | 1.4265 |
| 2026-08-04 04:46:40 | 0x97498144 | 15m | 0.58 | approved | open | 5 | 0.600 | 0.0840 | -3.0840 |
| 2026-08-04 10:45:24 | 0x2b02305f | 5m | 0.85 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-04 10:45:24 | 0x5f2320f8 | 15m | 0.84 | approved | open | 5 | 0.850 | 0.0446 | 0.7054 |
| 2026-08-04 11:43:32 | 0xe4e1bc52 | 15m | 0.72 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-04 11:43:32 | 0xf952a338 | 5m | 0.9 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-04 13:20:50 | 0x1af16b10 | 15m | 0.41 | approved | open | 5 | 0.410 | 0.0847 | -2.1347 |
| 2026-08-04 13:20:50 | 0x5191096e | 5m | 0.88 | approved | open | 5 | 0.880 | 0.0370 | 0.5630 |
| 2026-08-04 13:39:05 | 0x7c860872 | 15m | 0.81 | approved | open | 5 | 0.820 | 0.0517 | 0.8483 |
| 2026-08-04 13:50:08 | 0x571cfb4b | 15m | 0.24 | approved | open | 5 | 0.250 | 0.0656 | -1.3156 |
| 2026-08-04 13:50:08 | 0x38188b0f | 5m | 0.62 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-04 14:38:19 | 0xd1fc7926 | 15m | 0.75 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-04 14:38:19 | 0x5e8c1758 | 5m | 0.56 | approved | open | 5 | 0.580 | 0.0853 | 2.0147 |
| 2026-08-04 14:40:14 | 0x09ee80ff | 5m | 0.7 | approved | open | 5 | 0.710 | 0.0721 | 1.3779 |
| 2026-08-04 15:38:33 | 0x0bc015ce | 15m | 0.19 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-04 15:38:33 | 0x6e966c4d | 5m | 0.75 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-04 15:49:20 | 0x1ecf2a8f | 15m | 0.3 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-04 19:38:38 | 0xc6d79b03 | 15m | 0.37 | approved | open | 5 | 0.370 | 0.0816 | 3.0684 |
| 2026-08-04 19:38:38 | 0x0183ea50 | 5m | 0.22 | approved | open | 5 | 0.220 | 0.0601 | 3.8399 |
| 2026-08-04 20:01:26 | 0xf2088c94 | 5m | 0.64 | approved | open | 5 | 0.640 | 0.0806 | 1.7194 |
| 2026-08-04 20:01:26 | 0x34cc368e | 15m | 0.58 | approved | open | 5 | 0.580 | 0.0853 | 2.0147 |
| 2026-08-04 20:17:04 | 0x077268ff | 15m | 0.86 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-04 20:40:12 | 0xcd154059 | 5m | 0.87 | approved | open | 5 | 0.890 | 0.0343 | 0.5157 |
| 2026-08-06 02:20:19 | 0xb369bd7a | 15m | 0.71 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-08-06 02:20:19 | 0x407fbe05 | 5m | 0.44 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-08-06 12:56:30 | 0x64fd28d6 | 5m | 0.89 | approved | open | 5 | 0.890 | 0.0343 | 0.5157 |
| 2026-08-07 02:15:29 | 0x5546f185 | 5m | 0.69 | approved | open | 5 | 0.690 | 0.0749 | 1.4751 |
| 2026-08-07 02:15:29 | 0x667b3040 | 15m | 0.63 | approved | open | 5 | 0.630 | 0.0816 | -3.2316 |
| 2026-08-07 02:41:23 | 0x33808dbc | 15m | 0.55 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-07 02:41:23 | 0x81aa7ab7 | 5m | 0.65 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-07 06:47:50 | 0x34f57349 | 5m | 0.79 | approved | open | 5 | 0.800 | 0.0560 | 0.9440 |
| 2026-08-07 06:47:50 | 0xd2aa257a | 15m | 0.72 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-07 07:21:51 | 0xdfd59011 | 15m | 0.43 | approved | open | 5 | 0.430 | 0.0858 | 2.7642 |
| 2026-08-07 07:21:51 | 0x62d5530f | 5m | 0.24 | approved | open | 5 | 0.230 | 0.0620 | 3.7880 |
| 2026-08-07 09:25:10 | 0xb283f7c7 | 5m | 0.47 | approved | open | 5 | 0.470 | 0.0872 | 2.5628 |
| 2026-08-07 13:49:40 | 0x79b8c9d8 | 15m | 0.22 | approved | open | 5 | 0.240 | 0.0638 | -1.2638 |
| 2026-08-07 20:01:42 | 0x721ffe34 | 15m | 0.77 | approved | open | 5 | 0.780 | 0.0601 | 1.0399 |
| 2026-08-07 21:41:09 | 0x0697c3d2 | 15m | 0.13 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-07 21:41:09 | 0xa609fc76 | 5m | 0.22 | approved | open | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 0.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 7912774, median of minute medians 0.0, worst minute p90 0.0, worst minute p99 0.0, max 0.0.
- Binance event time to local receive (network + clock offset): n 7912774, median of minute medians 60.0, worst minute p90 60.0, worst minute p99 60.0, max 60.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): no samples.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 149, median 60, p90 60, min 60, max 60.
- Local receive to decision: n 149, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 149, median 400, p90 400, min 400, max 400.

## Risk, reconciliation, invariants and audit

- Trips: 29: btc-speed REDUCING (strategy daily loss 5.04 USD > 5.00 (start of day 0.34), breaker:strategy); btc-speed ACTIVE (reset, human:backtest-auto); global REDUCING (stale feed polymarket: 60133 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 60133 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 60900 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 60900 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 61530 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 61530 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 61288 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 61288 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 60520 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 60520 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 61257 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 61257 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 61239 ms, breaker:stale_feed).
- Human resets: 5; halts confirmed by zero open orders: 0.
- Reconciles: 3744 (startup 1, periodic 3743); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 452 records, head fa661312927eb57d; last head anchored in the ledger: 0 records, None (startup, 2026-07-27 00:00:00).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v2 | 73 | 200 / 100 | 5.21 | 24 |

Elapsed since the first run: 14.00 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## Per day (cash flows of fills bought that day plus their settlement payouts)

| UTC day | fills | buys | sells | P&L USD |
|---|---|---|---|---|
| 2026-07-27 | 3 | 3 | 0 | -5.35 |
| 2026-07-29 | 15 | 15 | 0 | -0.58 |
| 2026-07-30 | 4 | 4 | 0 | +8.71 |
| 2026-07-31 | 15 | 15 | 0 | +2.84 |
| 2026-08-01 | 3 | 3 | 0 | +1.09 |
| 2026-08-03 | 9 | 9 | 0 | +10.05 |
| 2026-08-04 | 15 | 15 | 0 | +12.03 |
| 2026-08-06 | 1 | 1 | 0 | +0.52 |
| 2026-08-07 | 8 | 8 | 0 | +8.08 |
