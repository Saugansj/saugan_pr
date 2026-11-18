# paper_ethb day 2: 2026-10-12 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-10-12 00:00:00 to 2026-10-13 00:00:00 UTC (data from 2026-10-12 02:37:33 to 2026-10-12 19:53:03). Paper only: no order ever left this PC.

## Summary

- Runs started: 2; clean shutdowns: 0; still running or ended by a crash or kill: 2 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 46, approved 46, orders 46, paper fills 38, btc-speed events 59 and trades 46.
- Paper P&L to the end of the window: btc-speed +27.11 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 40 | 64.07 | 0.00 | 2.3250 | 0.00 | 93.50 | 0 | 0.00 | +27.1050 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 46 intents, 46 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | taker | 46 | 38 | 188.5 | 0.3253 | 2.2001 |

Merges of YES+NO pairs: 0; paper redemptions: 38.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| btc-speed | 5 s | 38 | +11.52c | +1.99c | 0 |
| btc-speed | 60 s | 36 | +11.09c | +3.21c | 2 |
| btc-speed | 300 s | 16 | +11.12c | +5.87c | 22 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-v4-eth-bybit**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 40 in 40 markets (needs 200), unresolved 0, mean 0.6776 USD, cluster SE 0.3045, total +27.1050 USD. Verdict: **running (40 of 200)**.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-11 19:34:32), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-11 19:34:32), `btc-speed-v4-eth-bybit` (sha256 04680de003a175aa, written 2026-10-11 19:34:32).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

59 causal ETH moves (>= 6.0 bp in 2 s) and 46 trades sent to the kernel. Per mapped market: trade 46, already holding this market 25, ask above max price 20, ends too soon 16, no ask 5, stale signal 2, too little size at ask 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-12 12:36:55 | -7.8 | 0x07de3efb: already holding this market; 0xe1adf6db: no ask |
| 2026-10-12 12:38:09 | -7.0 | 0x07de3efb: already holding this market; 0xe1adf6db: no ask |
| 2026-10-12 12:39:21 | -6.1 | 0x07de3efb: already holding this market; 0xe1adf6db: ends too soon |
| 2026-10-12 12:40:36 | -7.8 | 0x07de3efb: already holding this market; 0x27b25c73: trade |
| 2026-10-12 13:01:31 | +7.1 | 0x45406225: trade; 0xa3509096: trade |
| 2026-10-12 13:07:48 | -6.1 | 0x0f6267d8: trade; 0xa3509096: already holding this market |
| 2026-10-12 13:16:42 | -6.3 | 0x3a0694c6: trade; 0x6a46f42c: trade |
| 2026-10-12 13:22:56 | -6.0 | 0x6a46f42c: already holding this market; 0xae55b3e7: trade |
| 2026-10-12 13:29:42 | -6.6 | 0x4a6eed58: ends too soon; 0x6a46f42c: already holding this market |
| 2026-10-12 13:31:03 | +6.1 | 0x4e84a230: trade; 0xe57b033d: trade |
| 2026-10-12 13:33:32 | +6.6 | 0x4e84a230: already holding this market; 0xe57b033d: already holding this market |
| 2026-10-12 13:34:35 | -6.8 | 0x4e84a230: already holding this market; 0xe57b033d: already holding this market |
| 2026-10-12 13:39:03 | +6.5 | 0xb9af1b28: ends too soon; 0xe57b033d: already holding this market |
| 2026-10-12 13:46:55 | +6.0 | 0x44ad4196: trade; 0x93de7a0a: trade |
| 2026-10-12 13:54:47 | +7.8 | 0x8629a329: ends too soon; 0x93de7a0a: already holding this market |
| 2026-10-12 13:56:09 | +6.3 | 0x93de7a0a: already holding this market; 0xe5e53f23: ask above max price |
| 2026-10-12 14:38:26 | -6.4 | 0x5a685005: ask above max price; 0x799b3c84: no ask |
| 2026-10-12 14:39:34 | -6.5 | 0x5a685005: ask above max price; 0x799b3c84: ends too soon |
| 2026-10-12 14:46:43 | +6.1 | 0x2b05dab8: trade; 0x6a6e2152: trade |
| 2026-10-12 14:49:29 | -6.1 | 0x2b05dab8: already holding this market; 0x6a6e2152: already holding this market |
| 2026-10-12 15:33:36 | -6.2 | 0x8a52998e: trade; 0xe65087b2: trade |
| 2026-10-12 15:45:16 | +6.3 | 0x021e01aa: trade; 0xbe81a5a8: trade |
| 2026-10-12 16:10:54 | -6.4 | 0xcb48100a: trade; 0xcdbe97de: trade |
| 2026-10-12 16:54:18 | -6.2 | 0xee9f6a00: ends too soon; 0xf8fb5163: ask above max price |
| 2026-10-12 16:57:44 | -6.3 | 0x1736d128: ask above max price; 0xf8fb5163: ask above max price |
| 2026-10-12 16:59:26 | -7.5 | 0x1736d128: ends too soon; 0xf8fb5163: ends too soon |
| 2026-10-12 17:19:15 | -6.2 | 0x6b69e2d2: too little size at ask; 0xaec96db9: ends too soon |
| 2026-10-12 17:28:11 | -6.1 | 0x6b69e2d2: no ask; 0xc948a677: ask above max price |
| 2026-10-12 17:37:48 | -6.4 | 0x1554271e: ask above max price; 0x83a0ec6c: trade |
| 2026-10-12 19:11:01 | +7.4 | 0xacdd0d36: trade; 0xca575364: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-12 06:27:44 | 0x8b1e6ff2 | 5m | 0.12 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-12 06:38:30 | 0xe59780f5 | 15m | 0.02 | approved | open | 5 | 0.020 | 0.0069 | -0.1069 |
| 2026-10-12 06:49:39 | 0x862c8da5 | 15m | 0.5 | approved | open | 5 | 0.530 | 0.0872 | -2.7372 |
| 2026-10-12 07:40:20 | 0x6d9def4f | 15m | 0.004 | approved | open | 5 | 0.004 | 0.0014 | -0.0214 |
| 2026-10-12 07:40:20 | 0x5408e4e3 | 5m | 0.37 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-12 07:51:41 | 0x13e1dff7 | 15m | 0.37 | approved | open | 5 | 0.380 | 0.0825 | 3.0175 |
| 2026-10-12 07:51:41 | 0x04025717 | 5m | 0.15 | approved | open | 5 | 0.140 | 0.0421 | 4.2579 |
| 2026-10-12 09:26:04 | 0x5d5c4a66 | 15m | 0.02 | approved | open | 5 | 0.020 | 0.0069 | -0.1069 |
| 2026-10-12 09:26:04 | 0x37710bde | 5m | 0.07 | approved | open | 5 | 0.080 | 0.0258 | -0.4258 |
| 2026-10-12 10:05:47 | 0x84092409 | 15m | 0.63 | approved | open | 3.5 | 0.700 | 0.0515 | 0.9986 |
| 2026-10-12 10:05:47 | 0x91b5cab8 | 5m | 0.43 | approved | open | 5 | 0.470 | 0.0872 | 2.5628 |
| 2026-10-12 10:48:58 | 0x45fb1eaa | 5m | 0.01 | approved | open | 5 | 0.010 | 0.0035 | -0.0535 |
| 2026-10-12 10:48:58 | 0xf535010f | 15m | 0.24 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-12 11:34:36 | 0x9205edfc | 15m | 0.5 | approved | open | 5 | 0.590 | 0.0847 | 1.9653 |
| 2026-10-12 11:41:16 | 0x2cb27074 | 5m | 0.19 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-12 12:25:38 | 0x54783333 | 5m | 0.33 | approved | open | 5 | 0.340 | 0.0785 | 3.2215 |
| 2026-10-12 12:31:29 | 0x07de3efb | 15m | 0.49 | approved | open | 5 | 0.490 | 0.0875 | -2.5375 |
| 2026-10-12 12:31:29 | 0xe36fde9e | 5m | 0.43 | approved | open | 5 | 0.450 | 0.0866 | -2.3366 |
| 2026-10-12 12:40:36 | 0x27b25c73 | 5m | 0.33 | approved | open | 5 | 0.310 | 0.0749 | -1.6249 |
| 2026-10-12 13:01:31 | 0xa3509096 | 15m | 0.32 | approved | open | 5 | 0.320 | 0.0762 | -1.6762 |
| 2026-10-12 13:01:31 | 0x45406225 | 5m | 0.15 | approved | open | 5 | 0.160 | 0.0470 | -0.8470 |
| 2026-10-12 13:07:48 | 0x0f6267d8 | 5m | 0.08 | approved | open | 5 | 0.080 | 0.0258 | -0.4258 |
| 2026-10-12 13:16:42 | 0x6a46f42c | 15m | 0.48 | approved | open | 5 | 0.480 | 0.0874 | 2.5126 |
| 2026-10-12 13:16:42 | 0x3a0694c6 | 5m | 0.49 | approved | open | 5 | 0.470 | 0.0872 | 2.5628 |
| 2026-10-12 13:22:56 | 0xae55b3e7 | 5m | 0.16 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-12 13:31:03 | 0xe57b033d | 15m | 0.32 | approved | open | 5 | 0.320 | 0.0762 | 3.3238 |
| 2026-10-12 13:31:03 | 0x4e84a230 | 5m | 0.21 | approved | open | 5 | 0.210 | 0.0581 | 3.8919 |
| 2026-10-12 13:46:55 | 0x44ad4196 | 5m | 0.3 | approved | open | 5 | 0.310 | 0.0749 | 3.3751 |
| 2026-10-12 13:46:55 | 0x93de7a0a | 15m | 0.41 | approved | open | 5 | 0.410 | 0.0847 | 2.8653 |
| 2026-10-12 14:46:43 | 0x2b05dab8 | 5m | 0.09 | approved | open | 5 | 0.140 | 0.0421 | -0.7421 |
| 2026-10-12 14:46:43 | 0x6a6e2152 | 15m | 0.23 | approved | open | 5 | 0.230 | 0.0620 | -1.2120 |
| 2026-10-12 15:33:36 | 0xe65087b2 | 5m | 0.02 | approved | open | 5 | 0.030 | 0.0102 | -0.1602 |
| 2026-10-12 15:33:36 | 0x8a52998e | 15m | 0.29 | approved | open | 5 | 0.320 | 0.0762 | -1.6762 |
| 2026-10-12 15:45:16 | 0xbe81a5a8 | 5m | 0.36 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-12 15:45:16 | 0x021e01aa | 15m | 0.44 | approved | open | 5 | 0.460 | 0.0869 | 2.6131 |
| 2026-10-12 16:10:54 | 0xcdbe97de | 15m | 0.04 | approved | open | 5 | 0.070 | 0.0228 | -0.3728 |
| 2026-10-12 16:10:54 | 0xcb48100a | 5m | 0.36 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-12 17:37:48 | 0x83a0ec6c | 15m | 0.79 | approved | open | 5 | 0.790 | 0.0581 | 0.9919 |
| 2026-10-12 19:11:01 | 0xca575364 | 15m | 0.19 | approved | open | 5 | 0.190 | 0.0539 | -1.0039 |
| 2026-10-12 19:11:01 | 0xacdd0d36 | 5m | 0.13 | approved | open | 5 | 0.130 | 0.0396 | -0.6896 |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 910, median 244, p90 315, min 200, max 868.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 241853, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 28.0, max 62.0.
- Binance event time to local receive (network + clock offset): n 241853, median of minute medians -62.0, worst minute p90 3668498.0, worst minute p99 3668498.0, max 3668498.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 511415, median of minute medians 6.6, worst minute p90 95.8, worst minute p99 28477670.0, max 17910497.4.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 59, median -83, p90 89, min -284, max 1323.
- Local receive to decision: n 59, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 59, median 393, p90 489, min 350, max 594.

## Risk, reconciliation, invariants and audit

- Trips: 6: global REDUCING (stale feed binance:ETH: 17914934 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 60741 ms, breaker:stale_feed); global ACTIVE (reset, human:DELL-auto); global REDUCING (stale feed polymarket: 213834 ms, breaker:stale_feed); global REDUCING (restart: stale feed polymarket: 213834 ms, loop:restart); global ACTIVE (reset, human:DELL-feed).
- Human resets: 2; halts confirmed by zero open orders: 0.
- Reconciles: 186 (periodic 184, startup 2); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 192 records, head c1244343aceac8f6; last head anchored in the ledger: 26 records, d2ae9c90d412568a (startup, 2026-10-12 05:22:16).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 40 | 200 / 100 | 39.48 | 4 |

Elapsed since the first run: 1.01 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-10-12 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-10-12.md --title "paper_ethb day 2: 2026-10-12 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **2 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **2 of 2** (need 5+, all clean)
- Running time: 16.2 hours (0.68 days of 24 h)

| UTC day | Hours running |
|---|---|
| 2026-10-11 | 1.1 |
| 2026-10-12 | 15.2 |
