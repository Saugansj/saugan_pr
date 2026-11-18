# paper_ethb day 19: 2026-10-29 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-10-29 00:00:00 to 2026-10-30 00:00:00 UTC (data from 2026-10-29 00:00:29 to 2026-10-29 16:20:21). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 67, approved 67, orders 67, paper fills 58, btc-speed events 85 and trades 67.
- Paper P&L to the end of the window: btc-speed +146.62 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 441 | 1012.93 | 0.00 | 28.4493 | 0.00 | 1178.50 | 10 | 9.50 | +146.6240 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 67 intents, 67 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | taker | 67 | 58 | 290 | 0.5174 | 3.8436 |

Merges of YES+NO pairs: 0; paper redemptions: 56.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| btc-speed | 5 s | 57 | +5.75c | +1.48c | 1 |
| btc-speed | 60 s | 53 | +5.73c | +3.12c | 5 |
| btc-speed | 300 s | 22 | +5.20c | +5.12c | 34 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-v4-eth-bybit**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 434 in 434 markets (needs 200), unresolved 2, mean 0.3340 USD, cluster SE 0.1029, total +144.9446 USD. Verdict: **PASS**.
- **Paper-fill realism** (btc-speed at real tape prices): 362 of 434 resolved trades repriced at what real takers paid in our order's second. Paper +152.63 USD -> best case +74.94 (cheapest real price), typical +16.48 (median real price), **live estimate +13.61** (our order behind the real takers that beat us, partial fills; 68% of our shares filled); real takers paid a median +5.5c over our fill. Paper assumes we win every race for the cheapest ask. Not comparable with reports before 15 Oct.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-11 19:34:32), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-11 19:34:32), `btc-speed-v4-eth-bybit` (sha256 04680de003a175aa, written 2026-10-11 19:34:32).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

85 causal ETH moves (>= 6.0 bp in 2 s) and 67 trades sent to the kernel. Per mapped market: trade 67, already holding this market 61, ask above max price 16, no ask 12, ends too soon 9, move started before the window 3, too little size at ask 2.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-29 13:51:18 | +6.1 | 0x0de913f4: already holding this market; 0xccd2ecc6: ask above max price |
| 2026-10-29 14:06:30 | -6.2 | 0x15169815: trade; 0xe63d8ae6: trade |
| 2026-10-29 14:13:11 | +6.1 | 0x134e250f: ask above max price; 0xe63d8ae6: already holding this market |
| 2026-10-29 14:32:20 | +6.1 | 0x18a0d71b: ask above max price; 0xe66f443f: no ask |
| 2026-10-29 14:33:47 | +6.3 | 0x18a0d71b: ask above max price; 0xe66f443f: no ask |
| 2026-10-29 14:35:26 | -6.2 | 0x18a0d71b: trade; 0x8d370c9e: trade |
| 2026-10-29 14:36:27 | +7.5 | 0x18a0d71b: already holding this market; 0x8d370c9e: already holding this market |
| 2026-10-29 14:37:29 | +6.2 | 0x18a0d71b: already holding this market; 0x8d370c9e: already holding this market |
| 2026-10-29 14:38:46 | +6.2 | 0x18a0d71b: already holding this market; 0x8d370c9e: already holding this market |
| 2026-10-29 14:45:26 | -8.1 | 0x0c6452fc: trade; 0x2667ab96: trade |
| 2026-10-29 14:49:27 | -7.7 | 0x0c6452fc: already holding this market; 0x2667ab96: already holding this market |
| 2026-10-29 14:50:34 | +6.3 | 0x0c6452fc: already holding this market; 0xaf66abef: trade |
| 2026-10-29 15:00:12 | -6.1 | 0x7aeba3a6: trade; 0xaa6760c2: too little size at ask |
| 2026-10-29 15:08:32 | +7.4 | 0xaa6760c2: ask above max price; 0xec89df9d: no ask |
| 2026-10-29 15:09:33 | +6.0 | 0xaa6760c2: ask above max price; 0xec89df9d: ends too soon |
| 2026-10-29 15:10:43 | -6.0 | 0xa068bd03: trade; 0xaa6760c2: trade |
| 2026-10-29 15:12:26 | +6.8 | 0xa068bd03: already holding this market; 0xaa6760c2: already holding this market |
| 2026-10-29 15:14:47 | +6.5 | 0xa068bd03: already holding this market; 0xaa6760c2: already holding this market |
| 2026-10-29 15:31:36 | +6.5 | 0x425fb6e4: trade; 0xda496208: trade |
| 2026-10-29 15:32:45 | +6.0 | 0x425fb6e4: already holding this market; 0xda496208: already holding this market |
| 2026-10-29 15:34:02 | +6.4 | 0x425fb6e4: already holding this market; 0xda496208: already holding this market |
| 2026-10-29 15:35:15 | +6.6 | 0xc2fa96ce: trade; 0xda496208: already holding this market |
| 2026-10-29 15:46:04 | +6.2 | 0x47a00561: trade; 0x8b13af5c: trade |
| 2026-10-29 16:02:50 | -6.0 | 0x02709ec9: trade; 0xd109f094: ask above max price |
| 2026-10-29 16:07:58 | +6.1 | 0x02709ec9: already holding this market; 0x41f29ecd: no ask |
| 2026-10-29 16:09:19 | +6.1 | 0x02709ec9: already holding this market; 0x41f29ecd: ends too soon |
| 2026-10-29 16:10:54 | +6.6 | 0x02709ec9: already holding this market; 0x14b4111e: trade |
| 2026-10-29 16:13:19 | -6.0 | 0x02709ec9: already holding this market; 0x14b4111e: already holding this market |
| 2026-10-29 16:16:14 | -6.3 | 0x01d41825: trade; 0x24cbbe99: trade |
| 2026-10-29 16:19:04 | -6.6 | 0x01d41825: already holding this market; 0x24cbbe99: already holding this market |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-29 07:46:56 | 0xc0feef13 | 15m | 0.67 | approved | open | 5 | 0.670 | 0.0774 | -3.4274 |
| 2026-10-29 08:03:58 | 0xd6bac83b | 15m | 0.76 | approved | open | 5 | 0.760 | 0.0638 | 1.1362 |
| 2026-10-29 08:55:08 | 0x5acc4f07 | 15m | 0.17 | approved | open | 5 | 0.170 | 0.0494 | 4.1006 |
| 2026-10-29 08:55:08 | 0xc8fc7cbb | 5m | 0.81 | approved | open | 5 | 0.810 | 0.0539 | 0.8961 |
| 2026-10-29 09:10:43 | 0x74005806 | 5m | 0.52 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 09:21:31 | 0x2697d024 | 15m | 0.66 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 09:21:31 | 0xe41a00f3 | 5m | 0.76 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 10:56:20 | 0x1e5727ad | 15m | 0.01 | approved | open | 5 | 0.010 | 0.0035 | -0.0535 |
| 2026-10-29 10:56:20 | 0x037452fe | 5m | 0.66 | approved | open | 5 | 0.660 | 0.0785 | 1.6215 |
| 2026-10-29 11:12:20 | 0x3bbf1c7f | 5m | 0.7 | approved | open | 5 | 0.700 | 0.0735 | 1.4265 |
| 2026-10-29 11:15:26 | 0x2bebb9c0 | 15m | 0.43 | approved | open | 5 | 0.430 | 0.0858 | -2.2358 |
| 2026-10-29 11:15:26 | 0x6f3805cc | 5m | 0.41 | approved | open | 5 | 0.410 | 0.0847 | -2.1347 |
| 2026-10-29 12:37:12 | 0xe22b0a20 | 15m | 0.2 | approved | open | 5 | 0.200 | 0.0560 | -1.0560 |
| 2026-10-29 12:37:12 | 0xc38465de | 5m | 0.62 | approved | open | 5 | 0.620 | 0.0825 | 1.8175 |
| 2026-10-29 13:18:05 | 0x4a1d9d68 | 5m | 0.84 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 13:18:05 | 0xe127c8dc | 15m | 0.64 | approved | open | 5 | 0.670 | 0.0774 | 1.5726 |
| 2026-10-29 13:30:47 | 0x1cc03456 | 5m | 0.32 | approved | open | 5 | 0.400 | 0.0840 | 2.9160 |
| 2026-10-29 13:30:47 | 0x6928fecd | 15m | 0.4 | approved | open | 5 | 0.490 | 0.0875 | 2.4625 |
| 2026-10-29 13:42:12 | 0xacffdc73 | 5m | 0.07 | approved | open | 5 | 0.070 | 0.0228 | -0.3728 |
| 2026-10-29 13:45:16 | 0x8bdbadb0 | 5m | 0.45 | approved | open | 5 | 0.450 | 0.0866 | -2.3366 |
| 2026-10-29 13:45:16 | 0x0de913f4 | 15m | 0.47 | approved | open | 5 | 0.470 | 0.0872 | -2.4372 |
| 2026-10-29 14:06:30 | 0xe63d8ae6 | 15m | 0.81 | approved | open | 5 | 0.840 | 0.0470 | -4.2470 |
| 2026-10-29 14:06:30 | 0x15169815 | 5m | 0.77 | approved | open | 5 | 0.780 | 0.0601 | 1.0399 |
| 2026-10-29 14:35:26 | 0x18a0d71b | 15m | 0.03 | approved | open | 5 | 0.030 | 0.0102 | -0.1602 |
| 2026-10-29 14:35:26 | 0x8d370c9e | 5m | 0.45 | approved | open | 5 | 0.540 | 0.0869 | -2.7869 |
| 2026-10-29 14:45:26 | 0x2667ab96 | 5m | 0.51 | approved | open | 5 | 0.510 | 0.0875 | 2.3625 |
| 2026-10-29 14:45:26 | 0x0c6452fc | 15m | 0.51 | approved | open | 5 | 0.510 | 0.0875 | 2.3625 |
| 2026-10-29 14:50:34 | 0xaf66abef | 5m | 0.7 | approved | open | 5 | 0.710 | 0.0721 | 1.3779 |
| 2026-10-29 15:00:12 | 0x7aeba3a6 | 5m | 0.37 | approved | open | 5 | 0.410 | 0.0847 | -2.1347 |
| 2026-10-29 15:10:43 | 0xaa6760c2 | 15m | 0.009 | approved | open | 5 | 0.009 | 0.0031 | -0.0481 |
| 2026-10-29 15:10:43 | 0xa068bd03 | 5m | 0.26 | approved | open | 5 | 0.260 | 0.0673 | -1.3673 |
| 2026-10-29 15:31:36 | 0xda496208 | 15m | 0.59 | approved | open | 5 | 0.590 | 0.0847 | 1.9653 |
| 2026-10-29 15:31:36 | 0x425fb6e4 | 5m | 0.74 | approved | open | 5 | 0.740 | 0.0673 | 1.2327 |
| 2026-10-29 15:35:15 | 0xc2fa96ce | 5m | 0.55 | approved | open | 5 | 0.550 | 0.0866 | -2.8366 |
| 2026-10-29 15:46:04 | 0x8b13af5c | 15m | 0.64 | approved | open | 5 | 0.640 | 0.0806 | 1.7194 |
| 2026-10-29 15:46:04 | 0x47a00561 | 5m | 0.78 | approved | open | 5 | 0.780 | 0.0601 | -3.9601 |
| 2026-10-29 16:02:50 | 0x02709ec9 | 15m | 0.76 | approved | open | 5 | 0.760 | 0.0638 | 1.1362 |
| 2026-10-29 16:10:54 | 0x14b4111e | 5m | 0.35 | approved | open | 5 | 0.350 | 0.0796 | -1.8296 |
| 2026-10-29 16:16:14 | 0x01d41825 | 5m | 0.84 | approved | open | 5 | 0.840 | 0.0470 | unresolved |
| 2026-10-29 16:16:14 | 0x24cbbe99 | 15m | 0.7 | approved | open | 5 | 0.700 | 0.0735 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 981, median 215, p90 243, min 186, max 594.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 294980, median of minute medians 0.0, worst minute p90 2.0, worst minute p99 12.4, max 76.0.
- Binance event time to local receive (network + clock offset): n 294980, median of minute medians -79.0, worst minute p90 8316.0, worst minute p99 9560.4, max 9561.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 535369, median of minute medians 9.6, worst minute p90 12.0, worst minute p99 130.9, max 294.6.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 85, median -70, p90 50, min -288, max 229.
- Local receive to decision: n 85, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 85, median 365, p90 391, min 338, max 594.

## Risk, reconciliation, invariants and audit

- Trips: 3: global REDUCING (stale feed polymarket:crypto-fast: 60014 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 60014 ms, breaker:stale_feed); global ACTIVE (reset, human:DELL-feed).
- Human resets: 43; halts confirmed by zero open orders: 0.
- Reconciles: 196 (periodic 196); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 2383 records, head 6a5de228ab7efe41; last head anchored in the ledger: 2046 records, 22b64a79d0480995 (startup, 2026-10-28 18:33:10).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 434 | 200 / 100 | 24.29 | 0 |

Elapsed since the first run: 17.87 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-10-29 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-10-29.md --title "paper_ethb day 19: 2026-10-29 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **MET.**

- Days without a violation: **19 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **11 of 11** (need 5+, all clean)
- Running time: 219.6 hours (9.15 days of 24 h)

| UTC day | Hours running |
|---|---|
| 2026-10-11 | 1.1 |
| 2026-10-12 | 15.4 |
| 2026-10-13 | 16.7 |
| 2026-10-14 | 16.0 |
| 2026-10-15 | 12.8 |
| 2026-10-16 | 13.3 |
| 2026-10-20 | 12.4 |
| 2026-10-21 | 17.6 |
| 2026-10-22 | 16.0 |
| 2026-10-23 | 16.3 |
| 2026-10-24 | 6.7 |
| 2026-10-25 | 17.2 |
| 2026-10-26 | 18.1 |
| 2026-10-27 | 18.4 |
| 2026-10-28 | 5.4 |
| 2026-10-29 | 16.4 |
