# paper_ethb day 3: 2026-10-13 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-10-13 00:00:00 to 2026-10-14 00:00:00 UTC (data from 2026-10-13 04:16:13 to 2026-10-13 16:21:10). Paper only: no order ever left this PC.

## Summary

- Runs started: 1; clean shutdowns: 0; still running or ended by a crash or kill: 1 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 48, approved 48, orders 48, paper fills 48, btc-speed events 54 and trades 48.
- Paper P&L to the end of the window: btc-speed +74.69 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 90 | 179.39 | 0.00 | 5.4269 | 0.00 | 258.50 | 10 | 1.00 | +74.6881 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 48 intents, 48 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | taker | 48 | 48 | 240 | 0.4507 | 2.9670 |

Merges of YES+NO pairs: 0; paper redemptions: 46.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| btc-speed | 5 s | 47 | +3.79c | +0.90c | 1 |
| btc-speed | 60 s | 42 | +9.61c | +2.89c | 6 |
| btc-speed | 300 s | 20 | +16.91c | +5.33c | 27 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-v4-eth-bybit**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 88 in 88 markets (needs 200), unresolved 2, mean 0.8637 USD, cluster SE 0.2103, total +76.0080 USD. Verdict: **running (88 of 200)**.
- **Paper-fill realism** (btc-speed at real tape prices): 74 of 88 resolved trades repriced at what real takers paid in our order's second. Paper +72.95 USD -> best case +54.73 (cheapest real price), typical +26.93 (median real price); real takers paid a median +9.0c over our fill. Paper assumes we win every race for the cheapest ask.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-11 19:34:32), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-11 19:34:32), `btc-speed-v4-eth-bybit` (sha256 04680de003a175aa, written 2026-10-11 19:34:32).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

54 causal ETH moves (>= 6.0 bp in 2 s) and 48 trades sent to the kernel. Per mapped market: trade 48, already holding this market 28, ask above max price 14, ends too soon 11, no ask 5, stale book 2.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-13 11:50:11 | -7.6 | 0x714a5ca3: trade; 0x8b9e20da: ask above max price |
| 2026-10-13 11:53:15 | -6.0 | 0x714a5ca3: already holding this market; 0x8b9e20da: ask above max price |
| 2026-10-13 12:01:31 | +6.2 | 0x38d3819a: trade; 0xe2bb440c: trade |
| 2026-10-13 12:03:41 | -6.0 | 0x38d3819a: already holding this market; 0xe2bb440c: already holding this market |
| 2026-10-13 12:16:23 | +6.1 | 0x75378160: trade; 0xdfeb913c: trade |
| 2026-10-13 12:25:08 | +6.4 | 0x1c91f0ee: trade; 0x75378160: already holding this market |
| 2026-10-13 12:37:43 | -6.2 | 0x93e3561c: trade; 0xdf3b745e: trade |
| 2026-10-13 12:49:56 | +6.1 | 0xaae8cdd5: trade; 0xfe716ffa: ends too soon |
| 2026-10-13 13:32:06 | -6.2 | 0x3e5259f5: trade; 0x4598fbd9: trade |
| 2026-10-13 13:33:48 | -6.7 | 0x3e5259f5: already holding this market; 0x4598fbd9: already holding this market |
| 2026-10-13 13:36:29 | +6.2 | 0x3e5259f5: already holding this market; 0xc2941e0e: trade |
| 2026-10-13 13:37:33 | +6.0 | 0x3e5259f5: already holding this market; 0xc2941e0e: already holding this market |
| 2026-10-13 13:38:56 | +6.6 | 0x3e5259f5: already holding this market; 0xc2941e0e: already holding this market |
| 2026-10-13 13:44:00 | +6.0 | 0x3e5259f5: already holding this market; 0x67063d5a: ends too soon |
| 2026-10-13 13:45:34 | +6.1 | 0xdb454c52: trade; 0xe11879ee: trade |
| 2026-10-13 13:49:38 | -7.1 | 0xdb454c52: already holding this market; 0xe11879ee: already holding this market |
| 2026-10-13 14:05:52 | +6.0 | 0x16e53f02: trade; 0x612b6061: ask above max price |
| 2026-10-13 14:11:57 | +7.0 | 0x3c517a26: ask above max price; 0x612b6061: ask above max price |
| 2026-10-13 14:13:05 | -6.1 | 0x3c517a26: stale book; 0x612b6061: stale book |
| 2026-10-13 14:23:40 | +6.1 | 0xf10d3b63: trade; 0xfcdfe056: trade |
| 2026-10-13 14:33:58 | -6.3 | 0x0c352d1c: trade; 0x7e23bf1c: trade |
| 2026-10-13 14:51:26 | -6.5 | 0x49a47e48: ask above max price; 0x54c27b33: trade |
| 2026-10-13 15:19:52 | -7.2 | 0x01085523: ends too soon; 0x307bd1d9: ask above max price |
| 2026-10-13 15:32:44 | -6.2 | 0x26ed38b3: trade; 0xd870013e: trade |
| 2026-10-13 15:38:00 | -6.4 | 0x3f9ef948: no ask; 0xd870013e: already holding this market |
| 2026-10-13 15:49:25 | +6.2 | 0x141e5a3d: ends too soon; 0x44878605: trade |
| 2026-10-13 15:51:45 | -6.0 | 0x0b0ecc16: trade; 0x44878605: already holding this market |
| 2026-10-13 15:56:26 | +6.1 | 0x2375e67a: trade; 0x44878605: already holding this market |
| 2026-10-13 16:05:02 | -7.4 | 0xaa06fb87: trade; 0xacb90a02: trade |
| 2026-10-13 16:19:43 | -6.5 | 0x6ad1d46a: ends too soon; 0xcd7982ed: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-13 08:00:57 | 0x8782acb4 | 15m | 0.69 | approved | open | 5 | 0.690 | 0.0749 | -3.5249 |
| 2026-10-13 08:00:57 | 0x480810c0 | 5m | 0.8 | approved | open | 5 | 0.800 | 0.0560 | 0.9440 |
| 2026-10-13 08:57:11 | 0x9806fcda | 5m | 0.63 | approved | open | 5 | 0.630 | 0.0816 | 1.7684 |
| 2026-10-13 09:05:43 | 0x9581a438 | 5m | 0.78 | approved | open | 5 | 0.780 | 0.0601 | -3.9601 |
| 2026-10-13 10:32:42 | 0xac64b02e | 15m | 0.77 | approved | open | 5 | 0.850 | 0.0446 | 0.7054 |
| 2026-10-13 10:42:40 | 0x1a8c21c3 | 5m | 0.79 | approved | open | 5 | 0.790 | 0.0581 | 0.9919 |
| 2026-10-13 10:46:55 | 0x39d0336c | 15m | 0.23 | approved | open | 5 | 0.230 | 0.0620 | -1.2120 |
| 2026-10-13 10:46:55 | 0xdc175fad | 5m | 0.08 | approved | open | 5 | 0.080 | 0.0258 | -0.4258 |
| 2026-10-13 11:21:44 | 0x9fc43f29 | 15m | 0.84 | approved | open | 5 | 0.840 | 0.0470 | 0.7530 |
| 2026-10-13 11:23:46 | 0xceeb60da | 5m | 0.001 | approved | open | 5 | 0.001 | 0.0003 | -0.0053 |
| 2026-10-13 11:30:15 | 0xac7cd34f | 15m | 0.51 | approved | open | 5 | 0.510 | 0.0875 | 2.3625 |
| 2026-10-13 11:30:15 | 0xdbcb1969 | 5m | 0.53 | approved | open | 5 | 0.540 | 0.0869 | 2.2131 |
| 2026-10-13 11:50:11 | 0x714a5ca3 | 5m | 0.77 | approved | open | 5 | 0.800 | 0.0560 | 0.9440 |
| 2026-10-13 12:01:31 | 0x38d3819a | 15m | 0.27 | approved | open | 5 | 0.320 | 0.0762 | -1.6762 |
| 2026-10-13 12:01:31 | 0xe2bb440c | 5m | 0.12 | approved | open | 5 | 0.130 | 0.0396 | -0.6896 |
| 2026-10-13 12:16:23 | 0xdfeb913c | 5m | 0.13 | approved | open | 5 | 0.130 | 0.0396 | -0.6896 |
| 2026-10-13 12:16:23 | 0x75378160 | 15m | 0.28 | approved | open | 5 | 0.280 | 0.0706 | 3.5294 |
| 2026-10-13 12:25:08 | 0x1c91f0ee | 5m | 0.77 | approved | open | 5 | 0.770 | 0.0620 | 1.0880 |
| 2026-10-13 12:37:43 | 0x93e3561c | 15m | 0.22 | approved | open | 5 | 0.240 | 0.0638 | 3.7362 |
| 2026-10-13 12:37:43 | 0xdf3b745e | 5m | 0.019 | approved | open | 5 | 0.038 | 0.0128 | -0.2028 |
| 2026-10-13 12:49:56 | 0xaae8cdd5 | 15m | 0.77 | approved | open | 5 | 0.780 | 0.0601 | 1.0399 |
| 2026-10-13 13:32:06 | 0x4598fbd9 | 5m | 0.18 | approved | open | 5 | 0.210 | 0.0581 | 3.8919 |
| 2026-10-13 13:32:06 | 0x3e5259f5 | 15m | 0.34 | approved | open | 5 | 0.330 | 0.0774 | 3.2726 |
| 2026-10-13 13:36:29 | 0xc2941e0e | 5m | 0.27 | approved | open | 5 | 0.270 | 0.0690 | 3.5810 |
| 2026-10-13 13:45:34 | 0xdb454c52 | 5m | 0.4 | approved | open | 5 | 0.390 | 0.0833 | 2.9667 |
| 2026-10-13 13:45:34 | 0xe11879ee | 15m | 0.41 | approved | open | 5 | 0.410 | 0.0847 | -2.1347 |
| 2026-10-13 14:05:52 | 0x16e53f02 | 5m | 0.68 | approved | open | 5 | 0.720 | 0.0706 | 1.3294 |
| 2026-10-13 14:23:40 | 0xf10d3b63 | 15m | 0.35 | approved | open | 5 | 0.350 | 0.0796 | 3.1704 |
| 2026-10-13 14:23:40 | 0xfcdfe056 | 5m | 0.3 | approved | open | 5 | 0.280 | 0.0706 | 3.5294 |
| 2026-10-13 14:33:58 | 0x7e23bf1c | 5m | 0.69 | approved | open | 5 | 0.680 | 0.0762 | 1.5238 |
| 2026-10-13 14:33:58 | 0x0c352d1c | 15m | 0.55 | approved | open | 5 | 0.550 | 0.0866 | -2.8366 |
| 2026-10-13 14:51:26 | 0x54c27b33 | 15m | 0.6 | approved | open | 5 | 0.600 | 0.0840 | 1.9160 |
| 2026-10-13 15:32:44 | 0x26ed38b3 | 5m | 0.5 | approved | open | 5 | 0.500 | 0.0875 | -2.5875 |
| 2026-10-13 15:32:44 | 0xd870013e | 15m | 0.51 | approved | open | 5 | 0.510 | 0.0875 | 2.3625 |
| 2026-10-13 15:49:25 | 0x44878605 | 15m | 0.22 | approved | open | 5 | 0.220 | 0.0601 | 3.8399 |
| 2026-10-13 15:51:45 | 0x0b0ecc16 | 5m | 0.08 | approved | open | 5 | 0.080 | 0.0258 | -0.4258 |
| 2026-10-13 15:56:26 | 0x2375e67a | 5m | 0.43 | approved | open | 5 | 0.430 | 0.0858 | 2.7642 |
| 2026-10-13 16:05:02 | 0xaa06fb87 | 15m | 0.19 | approved | open | 5 | 0.200 | 0.0560 | unresolved |
| 2026-10-13 16:05:02 | 0xacb90a02 | 5m | 0.56 | approved | open | 5 | 0.560 | 0.0862 | 2.1138 |
| 2026-10-13 16:19:43 | 0xcd7982ed | 15m | 0.24 | approved | open | 5 | 0.240 | 0.0638 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 722, median 235, p90 317, min 204, max 634.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 229568, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 1.8, max 63.0.
- Binance event time to local receive (network + clock offset): n 229568, median of minute medians -804.0, worst minute p90 5305.0, worst minute p99 7375.0, max 8510.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 402187, median of minute medians 7.5, worst minute p90 194.1, worst minute p99 231.2, max 581.5.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 54, median -588, p90 66, min -1029, max 316.
- Local receive to decision: n 54, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 54, median 390, p90 430, min 359, max 662.

## Risk, reconciliation, invariants and audit

- Trips: 8: global REDUCING (stale feed basis:USDT: 22183723 ms, breaker:stale_feed); global REDUCING (stale feed dvol:BTC: 22183399 ms, breaker:stale_feed); global REDUCING (stale feed dvol:ETH: 22183399 ms, breaker:stale_feed); global REDUCING (restart: stale feed dvol:ETH: 22183399 ms, loop:restart); global ACTIVE (reset, human:DELL-auto); global REDUCING (stale feed dvol:BTC: 600728 ms, breaker:stale_feed); global REDUCING (stale feed dvol:ETH: 600728 ms, breaker:stale_feed); global ACTIVE (reset, human:DELL-feed).
- Human resets: 2; halts confirmed by zero open orders: 0.
- Reconciles: 146 (periodic 145, startup 1); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 406 records, head 7317ec8b15805296; last head anchored in the ledger: 210 records, 1a84568afefe3782 (startup, 2026-10-13 04:24:31).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 88 | 200 / 100 | 47.16 | 2 |

Elapsed since the first run: 1.87 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-10-13 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-10-13.md --title "paper_ethb day 3: 2026-10-13 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **3 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **3 of 3** (need 5+, all clean)
- Running time: 28.5 hours (1.19 days of 24 h)

| UTC day | Hours running |
|---|---|
| 2026-10-11 | 1.1 |
| 2026-10-12 | 15.4 |
| 2026-10-13 | 12.0 |
