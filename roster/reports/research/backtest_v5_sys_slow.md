Features: ['speed_only', 'speed_v5']; global cap 1000.0; Binance receive lag 400 ms; RTT 250.0 ms; book depth 100.0 shares per side (assumed); start cash 50.0. Sim clock, 24 h a day, 08:15 IST breaker reset.

# System backtest v5_sys_slow: 2026-07-27 to 2026-08-09

Ledger `data/research/backtest/v5_sys_slow`, window 2026-07-27 00:00:00 to 2026-08-10 00:00:00 UTC (data from 2026-07-27 00:00:00 to 2026-08-09 23:59:17). Paper only: no order ever left this PC.

## Summary

- Runs started: 1; clean shutdowns: 0; still running or ended by a crash or kill: 1 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 193, approved 144, orders 144, paper fills 84, btc-speed events 366 and trades 193.
- Paper P&L to the end of the window: btc-speed +66.48 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 84 | 242.99 | 0.00 | 5.5266 | 0.00 | 315.00 | 0 | 0.00 | +66.4834 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 193 intents, 144 approved, 49 rejected: REDUCING 49.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

Latest distinct rejections:

| Time UTC | Strategy | Reason | Binding cap |
|---|---|---|---|
| 2026-08-06 02:20:19 | btc-speed | REDUCING: only exposure-reducing orders | - |

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | taker | 144 | 84 | 420 | 0.5785 | 5.5266 |

Merges of YES+NO pairs: 0; paper redemptions: 84.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| btc-speed | 5 s | 83 | +9.76c | +1.52c | 1 |
| btc-speed | 60 s | 81 | +10.61c | +2.37c | 3 |
| btc-speed | 300 s | 32 | +1.81c | +5.09c | 52 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-v5**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 84 in 84 markets (needs 200), unresolved 0, mean 0.7915 USD, cluster SE 0.2296, total +66.4834 USD. Verdict: **running (84 of 200)**.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-10 18:54:33), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-10 18:54:33), `btc-speed-v5` (sha256 1cb89f1faedfdf12, written 2026-10-10 18:54:33).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

366 causal BTC moves (>= 6.0 bp in 2 s) and 193 trades sent to the kernel. Per mapped market: volatile market 322, trade 193, ask above max price 92, ends too soon 79, no ask 20, move started before the window 18, already holding this market 8.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-08-07 02:41:23 | +6.1 | 0x33808dbc: trade; 0x81aa7ab7: trade |
| 2026-08-07 03:00:52 | -6.0 | 0x29861850: trade; 0x7a8af94c: trade |
| 2026-08-07 04:49:39 | -6.0 | 0x34eeecee: ends too soon; 0xaa4278ea: trade |
| 2026-08-07 07:21:51 | +6.0 | 0x62d5530f: trade; 0xdfd59011: trade |
| 2026-08-07 07:24:21 | +6.0 | 0x62d5530f: ends too soon; 0xdfd59011: trade |
| 2026-08-07 08:42:10 | +6.0 | 0x43a8b6db: ask above max price; 0xf4d42ae8: no ask |
| 2026-08-07 09:25:10 | +6.0 | 0x174430d8: ask above max price; 0xb283f7c7: trade |
| 2026-08-07 11:22:08 | +6.0 | 0xbbff4c6e: no ask; 0xbc3366fe: ask above max price |
| 2026-08-07 12:11:27 | +6.0 | 0x1930c017: ask above max price; 0x7264de01: ask above max price |
| 2026-08-07 12:29:46 | -6.0 | 0x7c7981fb: ends too soon; 0xc787cd0b: ends too soon |
| 2026-08-07 12:34:54 | -6.0 | 0x83ac57cd: volatile market; 0xb95b4255: volatile market |
| 2026-08-07 12:36:08 | -6.0 | 0x83ac57cd: volatile market; 0xf949fad1: volatile market |
| 2026-08-07 13:49:38 | +6.1 | 0x79b8c9d8: volatile market; 0xee9c6ae6: volatile market |
| 2026-08-07 13:51:30 | -6.1 | 0x3ba8a4c2: volatile market; 0x79b8c9d8: volatile market |
| 2026-08-07 14:34:19 | +6.0 | 0xdf3cc693: volatile market; 0xe0b2a84a: volatile market |
| 2026-08-07 16:20:18 | +6.0 | 0xec467047: trade; 0xf8e6f38f: trade |
| 2026-08-07 19:01:29 | +6.0 | 0x3de7a5b1: ask above max price; 0x62aa4a80: ask above max price |
| 2026-08-07 19:36:24 | +6.0 | 0x84737012: ask above max price; 0xd283be40: ask above max price |
| 2026-08-07 20:01:39 | +6.0 | 0x721ffe34: trade; 0xa447128b: trade |
| 2026-08-07 21:41:04 | +6.0 | 0x0697c3d2: ask above max price; 0xa609fc76: ask above max price |
| 2026-08-08 00:19:21 | -6.0 | 0xc6fc0c40: ends too soon; 0xcd7bad8e: ask above max price |
| 2026-08-08 01:11:17 | +6.0 | 0x6f730401: trade; 0x7507bc10: trade |
| 2026-08-08 04:32:50 | +6.0 | 0x4b2768f3: trade; 0xd0aff90c: trade |
| 2026-08-08 14:28:38 | +6.0 | 0x540aede2: ask above max price; 0xde7cfad3: trade |
| 2026-08-08 20:49:37 | +6.0 | 0x22a5b479: trade; 0xa0cfe98f: ends too soon |
| 2026-08-09 01:50:41 | -6.0 | 0x4e23015c: trade; 0x9e6ca5e7: trade |
| 2026-08-09 08:04:42 | +6.0 | 0x79ade561: ends too soon; 0xc609b6b0: ask above max price |
| 2026-08-09 20:14:08 | -6.0 | 0x311e98a8: ends too soon; 0x73b341b0: ends too soon |
| 2026-08-09 22:14:20 | +6.0 | 0x022f109d: ends too soon; 0xd3f9c53e: ends too soon |
| 2026-08-09 22:39:32 | -6.0 | 0x18f6f89a: volatile market; 0x80757bf3: volatile market |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-08-04 18:15:26 | 0xeea07746 | 15m | 0.64 | approved | open | 5 | 0.740 | 0.0673 | 1.2327 |
| 2026-08-04 19:38:38 | 0xc6d79b03 | 15m | 0.37 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-04 19:38:38 | 0x0183ea50 | 5m | 0.22 | approved | open | 5 | 0.270 | 0.0690 | 3.5810 |
| 2026-08-04 20:01:26 | 0xf2088c94 | 5m | 0.64 | approved | open | 5 | 0.640 | 0.0806 | 1.7194 |
| 2026-08-04 20:01:26 | 0x34cc368e | 15m | 0.58 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-04 20:40:09 | 0xcd154059 | 5m | 0.66 | approved | open | 5 | 0.700 | 0.0735 | 1.4265 |
| 2026-08-04 23:18:17 | 0x0fd271dd | 15m | 0.75 | approved | open | 5 | 0.770 | 0.0620 | -3.9120 |
| 2026-08-06 02:20:19 | 0xb369bd7a | 15m | 0.71 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-08-06 02:20:19 | 0x407fbe05 | 5m | 0.43 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-08-06 02:49:40 | 0xc8779212 | 15m | 0.26 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-06 09:22:37 | 0xb4e3fe11 | 15m | 0.05 | approved | open | 5 | 0.050 | 0.0166 | 4.7334 |
| 2026-08-06 09:22:37 | 0x36801c32 | 5m | 0.14 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-06 09:28:40 | 0x28a98e6b | 5m | 0.52 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-06 13:23:30 | 0x902ca6e2 | 15m | 0.59 | approved | open | 5 | 0.590 | 0.0847 | 1.9653 |
| 2026-08-06 13:23:30 | 0x5e058df3 | 5m | 0.66 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-06 14:18:11 | 0x784e7f29 | 5m | 0.43 | approved | open | 5 | 0.500 | 0.0875 | 2.4125 |
| 2026-08-06 14:18:11 | 0x1e33cb07 | 15m | 0.47 | approved | open | 5 | 0.560 | 0.0862 | 2.1138 |
| 2026-08-07 02:15:29 | 0x5546f185 | 5m | 0.69 | approved | open | 5 | 0.690 | 0.0749 | 1.4751 |
| 2026-08-07 02:15:29 | 0x667b3040 | 15m | 0.63 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-07 02:41:23 | 0x33808dbc | 15m | 0.62 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-07 02:41:23 | 0x81aa7ab7 | 5m | 0.68 | approved | open | 5 | 0.700 | 0.0735 | 1.4265 |
| 2026-08-07 03:00:52 | 0x7a8af94c | 5m | 0.81 | approved | open | 5 | 0.840 | 0.0470 | 0.7530 |
| 2026-08-07 03:00:52 | 0x29861850 | 15m | 0.71 | approved | open | 5 | 0.810 | 0.0539 | 0.8961 |
| 2026-08-07 04:49:39 | 0xaa4278ea | 15m | 0.74 | approved | open | 5 | 0.750 | 0.0656 | 1.1844 |
| 2026-08-07 07:21:51 | 0xdfd59011 | 15m | 0.43 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-07 07:21:51 | 0x62d5530f | 5m | 0.23 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-07 07:24:21 | 0xdfd59011 | 15m | 0.84 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-07 09:25:10 | 0xb283f7c7 | 5m | 0.47 | approved | open | 5 | 0.510 | 0.0875 | 2.3625 |
| 2026-08-07 16:20:18 | 0xf8e6f38f | 15m | 0.2 | approved | open | 5 | 0.200 | 0.0560 | -1.0560 |
| 2026-08-07 16:20:18 | 0xec467047 | 5m | 0.58 | approved | open | 5 | 0.580 | 0.0853 | -2.9853 |
| 2026-08-07 20:01:39 | 0xa447128b | 5m | 0.79 | approved | open | 5 | 0.820 | 0.0517 | 0.8483 |
| 2026-08-07 20:01:39 | 0x721ffe34 | 15m | 0.67 | approved | open | 5 | 0.740 | 0.0673 | 1.2327 |
| 2026-08-08 01:11:17 | 0x6f730401 | 15m | 0.52 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-08 01:11:17 | 0x7507bc10 | 5m | 0.49 | approved | open | 5 | 0.490 | 0.0875 | 2.4625 |
| 2026-08-08 04:32:50 | 0x4b2768f3 | 5m | 0.84 | approved | open | 5 | 0.850 | 0.0446 | 0.7054 |
| 2026-08-08 04:32:50 | 0xd0aff90c | 15m | 0.65 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-08 14:28:38 | 0xde7cfad3 | 5m | 0.04 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-08 20:49:37 | 0x22a5b479 | 15m | 0.46 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-09 01:50:41 | 0x9e6ca5e7 | 15m | 0.59 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-08-09 01:50:41 | 0x4e23015c | 5m | 0.39 | approved | open | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 0.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 7912738, median of minute medians 0.0, worst minute p90 0.0, worst minute p99 0.0, max 0.0.
- Binance event time to local receive (network + clock offset): n 7912738, median of minute medians 400.0, worst minute p90 400.0, worst minute p99 400.0, max 400.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): no samples.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 366, median 400, p90 400, min 400, max 400.
- Local receive to decision: n 366, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 366, median 400, p90 400, min 400, max 400.

## Risk, reconciliation, invariants and audit

- Trips: 27: global REDUCING (stale feed polymarket: 60473 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 60473 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 61240 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 61240 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 60252 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 60252 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 60095 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 60095 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 60860 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 60860 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 60205 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 60205 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 61579 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 61579 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 60684 ms, breaker:stale_feed).
- Human resets: 4; halts confirmed by zero open orders: 0.
- Reconciles: 3744 (startup 1, periodic 3743); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 533 records, head 151c88f0dcad28cc; last head anchored in the ledger: 0 records, None (startup, 2026-07-27 00:00:00).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v5 | 84 | 200 / 100 | 6.00 | 19 |

Elapsed since the first run: 14.00 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## Per day (cash flows of fills bought that day plus their settlement payouts)

| UTC day | fills | buys | sells | P&L USD |
|---|---|---|---|---|
| 2026-07-27 | 8 | 8 | 0 | +10.81 |
| 2026-07-28 | 6 | 6 | 0 | +10.89 |
| 2026-07-29 | 8 | 8 | 0 | +6.94 |
| 2026-07-30 | 9 | 9 | 0 | +1.21 |
| 2026-07-31 | 5 | 5 | 0 | -2.21 |
| 2026-08-01 | 5 | 5 | 0 | -0.91 |
| 2026-08-02 | 2 | 2 | 0 | +3.17 |
| 2026-08-03 | 11 | 11 | 0 | +2.81 |
| 2026-08-04 | 14 | 14 | 0 | +13.25 |
| 2026-08-06 | 4 | 4 | 0 | +11.22 |
| 2026-08-07 | 10 | 10 | 0 | +6.14 |
| 2026-08-08 | 2 | 2 | 0 | +3.17 |
