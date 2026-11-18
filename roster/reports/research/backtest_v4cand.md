Features: ['speed_only']; global cap 50.0; Binance receive lag 60 ms; RTT 250.0 ms; book depth 100.0 shares per side (assumed); start cash 50.0. Sim clock, 24 h a day, 08:15 IST breaker reset.

# System backtest v4cand: 2026-07-27 to 2026-08-09

Ledger `data/research/backtest/v4cand`, window 2026-07-27 00:00:00 to 2026-08-10 00:00:00 UTC (data from 2026-07-27 00:00:00 to 2026-08-09 23:59:46). Paper only: no order ever left this PC.

## Summary

- Runs started: 1; clean shutdowns: 0; still running or ended by a crash or kill: 1 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 405, approved 16, orders 16, paper fills 13, btc-speed events 366 and trades 405.
- Paper P&L to the end of the window: btc-speed +5.35 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 13 | 33.75 | 0.00 | 0.8972 | 0.00 | 40.00 | 0 | 0.00 | +5.3528 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 405 intents, 16 approved, 389 rejected: bankroll 301; REDUCING 88.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

Latest distinct rejections:

| Time UTC | Strategy | Reason | Binding cap |
|---|---|---|---|
| 2026-08-06 02:20:19 | btc-speed | REDUCING: only exposure-reducing orders | - |
| 2026-08-09 01:50:40 | btc-speed | bankroll 55.35 > 1.1 x global cap 50.00 | global |

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | taker | 16 | 13 | 65 | 0.5192 | 0.8972 |

Merges of YES+NO pairs: 0; paper redemptions: 13.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| btc-speed | 5 s | 13 | +4.31c | +1.85c | 0 |
| btc-speed | 60 s | 13 | +12.23c | +5.74c | 0 |
| btc-speed | 300 s | 4 | -6.75c | +30.63c | 9 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-v2**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 13 in 13 markets (needs 200), unresolved 0, mean 0.4118 USD, cluster SE 0.6542, total +5.3528 USD. Verdict: **running (13 of 200)**.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-09 14:57:24), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-09 14:57:24).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

366 causal BTC moves (>= 6.0 bp in 2 s) and 405 trades sent to the kernel. Per mapped market: trade 405, ask above max price 152, ends too soon 118, no ask 36, move started before the window 17, already holding this market 2, stale book 2.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-08-07 02:41:23 | +6.1 | 0x33808dbc: trade; 0x81aa7ab7: trade |
| 2026-08-07 03:00:52 | -6.0 | 0x29861850: trade; 0x7a8af94c: trade |
| 2026-08-07 04:49:39 | -6.0 | 0x34eeecee: ends too soon; 0xaa4278ea: trade |
| 2026-08-07 07:21:51 | +6.0 | 0x62d5530f: trade; 0xdfd59011: trade |
| 2026-08-07 07:24:20 | +6.0 | 0x62d5530f: ends too soon; 0xdfd59011: trade |
| 2026-08-07 08:42:09 | +6.0 | 0x43a8b6db: ask above max price; 0xf4d42ae8: ask above max price |
| 2026-08-07 09:25:10 | +6.0 | 0x174430d8: ask above max price; 0xb283f7c7: trade |
| 2026-08-07 11:22:08 | +6.0 | 0xbbff4c6e: no ask; 0xbc3366fe: ask above max price |
| 2026-08-07 12:11:27 | +6.0 | 0x1930c017: ask above max price; 0x7264de01: ask above max price |
| 2026-08-07 12:29:46 | -6.0 | 0x7c7981fb: ends too soon; 0xc787cd0b: ends too soon |
| 2026-08-07 12:34:54 | -6.0 | 0x83ac57cd: trade; 0xb95b4255: ends too soon |
| 2026-08-07 12:36:08 | -6.0 | 0x83ac57cd: trade; 0xf949fad1: trade |
| 2026-08-07 13:49:38 | +6.1 | 0x79b8c9d8: trade; 0xee9c6ae6: ends too soon |
| 2026-08-07 13:51:30 | -6.1 | 0x3ba8a4c2: trade; 0x79b8c9d8: trade |
| 2026-08-07 14:34:19 | +6.0 | 0xdf3cc693: ends too soon; 0xe0b2a84a: trade |
| 2026-08-07 16:20:18 | +6.0 | 0xec467047: trade; 0xf8e6f38f: trade |
| 2026-08-07 19:01:28 | +6.0 | 0x3de7a5b1: ask above max price; 0x62aa4a80: ask above max price |
| 2026-08-07 19:36:24 | +6.0 | 0x84737012: ask above max price; 0xd283be40: ask above max price |
| 2026-08-07 20:01:38 | +6.0 | 0x721ffe34: trade; 0xa447128b: trade |
| 2026-08-07 21:41:03 | +6.0 | 0x0697c3d2: ask above max price; 0xa609fc76: ask above max price |
| 2026-08-08 00:19:21 | -6.0 | 0xc6fc0c40: ends too soon; 0xcd7bad8e: ask above max price |
| 2026-08-08 01:11:16 | +6.0 | 0x6f730401: trade; 0x7507bc10: trade |
| 2026-08-08 04:32:49 | +6.0 | 0x4b2768f3: trade; 0xd0aff90c: trade |
| 2026-08-08 14:28:37 | +6.0 | 0x540aede2: ask above max price; 0xde7cfad3: trade |
| 2026-08-08 20:49:37 | +6.0 | 0x22a5b479: trade; 0xa0cfe98f: ends too soon |
| 2026-08-09 01:50:40 | -6.0 | 0x4e23015c: trade; 0x9e6ca5e7: trade |
| 2026-08-09 08:04:42 | +6.0 | 0x79ade561: ends too soon; 0xc609b6b0: ask above max price |
| 2026-08-09 20:14:07 | -6.0 | 0x311e98a8: ends too soon; 0x73b341b0: ends too soon |
| 2026-08-09 22:14:19 | +6.0 | 0x022f109d: ends too soon; 0xd3f9c53e: ends too soon |
| 2026-08-09 22:39:31 | -6.0 | 0x18f6f89a: ends too soon; 0x80757bf3: ask above max price |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-08-06 09:22:37 | 0xb4e3fe11 | 15m | 0.05 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-06 09:22:37 | 0x36801c32 | 5m | 0.14 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-06 09:28:40 | 0xb4e3fe11 | 15m | 0.05 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-06 09:28:40 | 0x28a98e6b | 5m | 0.51 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-06 13:23:29 | 0x902ca6e2 | 15m | 0.59 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-06 13:23:29 | 0x5e058df3 | 5m | 0.66 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-06 14:18:11 | 0x784e7f29 | 5m | 0.43 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-06 14:18:11 | 0x1e33cb07 | 15m | 0.47 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-06 15:02:40 | 0xe7c3a781 | 5m | 0.46 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-06 15:02:40 | 0xcafffb6f | 15m | 0.49 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-07 02:15:29 | 0x5546f185 | 5m | 0.69 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-07 02:15:29 | 0x667b3040 | 15m | 0.63 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-07 02:41:23 | 0x33808dbc | 15m | 0.55 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-07 02:41:23 | 0x81aa7ab7 | 5m | 0.65 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-07 03:00:52 | 0x7a8af94c | 5m | 0.8 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-07 03:00:52 | 0x29861850 | 15m | 0.71 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-07 04:49:39 | 0xaa4278ea | 15m | 0.48 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-07 07:21:51 | 0xdfd59011 | 15m | 0.43 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-07 07:21:51 | 0x62d5530f | 5m | 0.24 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-07 07:24:20 | 0xdfd59011 | 15m | 0.77 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-07 09:25:10 | 0xb283f7c7 | 5m | 0.47 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-07 12:34:54 | 0x83ac57cd | 15m | 0.74 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-07 12:36:08 | 0x83ac57cd | 15m | 0.63 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-07 12:36:08 | 0xf949fad1 | 5m | 0.38 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-07 13:49:38 | 0x79b8c9d8 | 15m | 0.18 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-07 13:51:30 | 0x79b8c9d8 | 15m | 0.83 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-07 13:51:30 | 0x3ba8a4c2 | 5m | 0.58 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-07 14:34:19 | 0xe0b2a84a | 15m | 0.48 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-07 16:20:18 | 0xf8e6f38f | 15m | 0.17 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-07 16:20:18 | 0xec467047 | 5m | 0.57 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-07 20:01:38 | 0xa447128b | 5m | 0.77 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-07 20:01:38 | 0x721ffe34 | 15m | 0.65 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-08 01:11:16 | 0x6f730401 | 15m | 0.52 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-08 01:11:16 | 0x7507bc10 | 5m | 0.49 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-08 04:32:49 | 0x4b2768f3 | 5m | 0.84 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-08 04:32:49 | 0xd0aff90c | 15m | 0.56 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-08 14:28:37 | 0xde7cfad3 | 5m | 0.04 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-08 20:49:37 | 0x22a5b479 | 15m | 0.45 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-09 01:50:40 | 0x9e6ca5e7 | 15m | 0.59 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |
| 2026-08-09 01:50:40 | 0x4e23015c | 5m | 0.39 | bankroll 55.35 > 1.1 x global cap 50.00 | - | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 0.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 7912774, median of minute medians 0.0, worst minute p90 0.0, worst minute p99 0.0, max 0.0.
- Binance event time to local receive (network + clock offset): n 7912774, median of minute medians 60.0, worst minute p90 60.0, worst minute p99 60.0, max 60.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): no samples.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 366, median 60, p90 60, min 60, max 60.
- Local receive to decision: n 366, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 366, median 400, p90 400, min 400, max 400.

## Risk, reconciliation, invariants and audit

- Trips: 25: btc-speed REDUCING (strategy daily loss 5.74 USD > 5.00 (start of day 0.34), breaker:strategy); btc-speed ACTIVE (reset, human:backtest-auto); global REDUCING (stale feed polymarket: 60133 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 60133 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 60900 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 60900 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 61530 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 61530 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 61288 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 61288 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 60520 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 60520 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 61257 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 61257 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 61239 ms, breaker:stale_feed).
- Human resets: 3; halts confirmed by zero open orders: 0.
- Reconciles: 3744 (startup 1, periodic 3743); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 473 records, head 8da0e00bbb9ed1ff; last head anchored in the ledger: 0 records, None (startup, 2026-07-27 00:00:00).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v2 | 13 | 200 / 100 | 0.93 | 201 |

Elapsed since the first run: 14.00 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## Per day (cash flows of fills bought that day plus their settlement payouts)

| UTC day | fills | buys | sells | P&L USD |
|---|---|---|---|---|
| 2026-07-27 | 2 | 2 | 0 | -1.40 |
| 2026-07-28 | 2 | 2 | 0 | +4.20 |
| 2026-07-29 | 9 | 9 | 0 | +2.55 |
