# paper_ethb day 24: 2026-11-03 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-11-03 00:00:00 to 2026-11-04 00:00:00 UTC (data from 2026-11-03 00:00:33 to 2026-11-03 16:24:06). Paper only: no order ever left this PC.

## Summary

- Runs started: 1; clean shutdowns: 0; still running or ended by a crash or kill: 1 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 26, approved 26, orders 26, paper fills 23, btc-speed events 39 and trades 26.
- Paper P&L to the end of the window: btc-speed +202.94 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 599 | 1410.95 | 0.00 | 39.3370 | 0.00 | 1648.50 | 5 | 4.72 | +202.9363 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 26 intents, 26 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | taker | 26 | 23 | 115 | 0.4048 | 1.5251 |

Merges of YES+NO pairs: 0; paper redemptions: 22.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| btc-speed | 5 s | 23 | +7.28c | +2.99c | 0 |
| btc-speed | 60 s | 20 | +9.78c | +3.74c | 3 |
| btc-speed | 300 s | 8 | +3.81c | +9.03c | 14 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-v4-eth-bybit**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 593 in 593 markets (needs 200), unresolved 1, mean 0.3402 USD, cluster SE 0.0879, total +201.7362 USD. Verdict: **PASS**.
- **Paper-fill realism** (btc-speed at real tape prices): 483 of 593 resolved trades repriced at what real takers paid in our order's second. Paper +196.69 USD -> best case +102.54 (cheapest real price), typical +19.25 (median real price), **live estimate +25.40** (our order behind the real takers that beat us, partial fills; 68% of our shares filled); real takers paid a median +5.0c over our fill. Paper assumes we win every race for the cheapest ask. Not comparable with reports before 15 Oct.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-11 19:34:32), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-11 19:34:32), `btc-speed-v4-eth-bybit` (sha256 04680de003a175aa, written 2026-10-11 19:34:32).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

39 causal ETH moves (>= 6.0 bp in 2 s) and 26 trades sent to the kernel. Per mapped market: already holding this market 33, trade 26, ask above max price 8, ends too soon 5, no ask 4, move started before the window 2.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-11-03 13:28:52 | +6.1 | 0x173c6082: no ask; 0xd1e9799d: already holding this market |
| 2026-11-03 13:29:58 | -6.1 | 0x173c6082: ends too soon; 0xd1e9799d: already holding this market |
| 2026-11-03 13:31:03 | -6.2 | 0x068b0b6e: trade; 0x70980e62: trade |
| 2026-11-03 13:32:07 | +6.0 | 0x068b0b6e: already holding this market; 0x70980e62: already holding this market |
| 2026-11-03 13:33:07 | +6.4 | 0x068b0b6e: already holding this market; 0x70980e62: already holding this market |
| 2026-11-03 13:34:14 | +7.6 | 0x068b0b6e: already holding this market; 0x70980e62: already holding this market |
| 2026-11-03 13:36:48 | +7.6 | 0x70980e62: already holding this market; 0xeb2bf301: trade |
| 2026-11-03 13:38:41 | -6.3 | 0x70980e62: already holding this market; 0xeb2bf301: already holding this market |
| 2026-11-03 13:46:39 | -6.0 | 0x26e08ea3: trade; 0x5c7f1d52: trade |
| 2026-11-03 13:53:53 | -6.6 | 0x5c7f1d52: already holding this market; 0xa8e714e9: no ask |
| 2026-11-03 13:59:17 | +6.8 | 0x5a921ee3: ends too soon; 0x5c7f1d52: already holding this market |
| 2026-11-03 14:01:44 | -6.2 | 0x0f02a27b: trade; 0x1bd99964: trade |
| 2026-11-03 14:02:52 | -6.1 | 0x0f02a27b: already holding this market; 0x1bd99964: no ask |
| 2026-11-03 14:07:27 | +6.7 | 0x0f02a27b: already holding this market; 0x915e3f1d: trade |
| 2026-11-03 14:24:39 | -6.1 | 0x468222d4: trade; 0x57f146e5: ends too soon |
| 2026-11-03 14:26:35 | +8.0 | 0x00879449: trade; 0x468222d4: already holding this market |
| 2026-11-03 14:30:07 | +6.2 | 0x099f48eb: trade; 0x09fa29ff: trade |
| 2026-11-03 14:31:29 | -6.0 | 0x099f48eb: already holding this market; 0x09fa29ff: already holding this market |
| 2026-11-03 14:32:59 | +6.4 | 0x099f48eb: already holding this market; 0x09fa29ff: already holding this market |
| 2026-11-03 14:51:43 | +6.1 | 0x4e411179: trade; 0xee49d5c7: trade |
| 2026-11-03 14:53:01 | +6.5 | 0x4e411179: already holding this market; 0xee49d5c7: already holding this market |
| 2026-11-03 14:55:28 | +6.1 | 0x4e411179: already holding this market; 0x7d1bd9f5: trade |
| 2026-11-03 15:00:01 | -6.4 | 0x422ba13e: move started before the window; 0x70f043d4: move started before the window |
| 2026-11-03 15:09:22 | +7.8 | 0x422ba13e: trade; 0x4b235b17: ends too soon |
| 2026-11-03 15:12:10 | +6.2 | 0x3a6132d2: trade; 0x422ba13e: already holding this market |
| 2026-11-03 15:13:35 | -6.0 | 0x3a6132d2: already holding this market; 0x422ba13e: already holding this market |
| 2026-11-03 15:41:21 | +7.1 | 0x502d16b3: ask above max price; 0xa2b9a6f7: no ask |
| 2026-11-03 15:46:59 | +6.0 | 0x4f2da75a: trade; 0x7c662c10: ask above max price |
| 2026-11-03 15:53:32 | +6.5 | 0x4f2da75a: already holding this market; 0xeddddba8: trade |
| 2026-11-03 16:21:25 | -6.1 | 0x0bbb6a49: ask above max price; 0xad575f8d: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-03 12:16:10 | 0x81dfa261 | 5m | 0.12 | approved | open | 5 | 0.160 | 0.0470 | -0.8470 |
| 2026-11-03 12:16:10 | 0x4219f034 | 15m | 0.23 | approved | open | 5 | 0.270 | 0.0690 | -1.4190 |
| 2026-11-03 12:25:40 | 0xee8642f4 | 5m | 0.68 | approved | open | 5 | 0.680 | 0.0762 | 1.5238 |
| 2026-11-03 12:47:42 | 0x781efed8 | 15m | 0.57 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-03 12:47:42 | 0x07fd21eb | 5m | 0.73 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-03 13:17:19 | 0xd1e9799d | 15m | 0.68 | approved | open | 5 | 0.680 | 0.0762 | 1.5238 |
| 2026-11-03 13:31:03 | 0x068b0b6e | 5m | 0.18 | approved | open | 5 | 0.210 | 0.0581 | -1.1081 |
| 2026-11-03 13:31:03 | 0x70980e62 | 15m | 0.29 | approved | open | 5 | 0.310 | 0.0749 | -1.6249 |
| 2026-11-03 13:36:48 | 0xeb2bf301 | 5m | 0.02 | approved | open | 5 | 0.020 | 0.0069 | -0.1069 |
| 2026-11-03 13:46:39 | 0x26e08ea3 | 5m | 0.4 | approved | open | 5 | 0.400 | 0.0840 | 2.9160 |
| 2026-11-03 13:46:39 | 0x5c7f1d52 | 15m | 0.46 | approved | open | 5 | 0.470 | 0.0872 | 2.5628 |
| 2026-11-03 14:01:44 | 0x0f02a27b | 15m | 0.63 | approved | open | 5 | 0.700 | 0.0735 | 1.4265 |
| 2026-11-03 14:01:44 | 0x1bd99964 | 5m | 0.75 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-03 14:07:27 | 0x915e3f1d | 5m | 0.19 | approved | open | 5 | 0.230 | 0.0620 | -1.2120 |
| 2026-11-03 14:24:39 | 0x468222d4 | 15m | 0.04 | approved | open | 5 | 0.050 | 0.0166 | -0.2666 |
| 2026-11-03 14:26:35 | 0x00879449 | 5m | 0.13 | approved | open | 5 | 0.140 | 0.0421 | -0.7421 |
| 2026-11-03 14:30:07 | 0x09fa29ff | 5m | 0.61 | approved | open | 5 | 0.670 | 0.0774 | 1.5726 |
| 2026-11-03 14:30:07 | 0x099f48eb | 15m | 0.58 | approved | open | 5 | 0.600 | 0.0840 | 1.9160 |
| 2026-11-03 14:51:43 | 0x4e411179 | 15m | 0.54 | approved | open | 5 | 0.530 | 0.0872 | -2.7372 |
| 2026-11-03 14:51:43 | 0xee49d5c7 | 5m | 0.33 | approved | open | 5 | 0.350 | 0.0796 | -1.8296 |
| 2026-11-03 14:55:28 | 0x7d1bd9f5 | 5m | 0.39 | approved | open | 5 | 0.390 | 0.0833 | -2.0333 |
| 2026-11-03 15:09:22 | 0x422ba13e | 15m | 0.5 | approved | open | 5 | 0.500 | 0.0875 | 2.4125 |
| 2026-11-03 15:12:10 | 0x3a6132d2 | 5m | 0.49 | approved | open | 5 | 0.480 | 0.0874 | 2.5126 |
| 2026-11-03 15:46:59 | 0x4f2da75a | 15m | 0.71 | approved | open | 5 | 0.720 | 0.0706 | 1.3294 |
| 2026-11-03 15:53:32 | 0xeddddba8 | 5m | 0.01 | approved | open | 5 | 0.060 | 0.0197 | -0.3197 |
| 2026-11-03 16:21:25 | 0xad575f8d | 5m | 0.69 | approved | open | 5 | 0.690 | 0.0749 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 438, median 218, p90 410, min 188, max 2236.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 166639, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 2.7, max 54.0.
- Binance event time to local receive (network + clock offset): n 166639, median of minute medians -12.0, worst minute p90 402.0, worst minute p99 2213.1, max 2281.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 225853, median of minute medians 12.9, worst minute p90 16.4, worst minute p99 111.3, max 258.9.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 39, median 28, p90 238, min -106, max 323.
- Local receive to decision: n 39, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 39, median 366, p90 385, min 344, max 447.

## Risk, reconciliation, invariants and audit

- Trips: 0.
- Human resets: 0; halts confirmed by zero open orders: 0.
- Reconciles: 85 (periodic 84, startup 1); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 3203 records, head 3fbebd90e45ec741; last head anchored in the ledger: 3104 records, 4d498a17305ea3e9 (startup, 2026-11-03 11:52:50).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 593 | 200 / 100 | 25.93 | 0 |

Elapsed since the first run: 22.87 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-11-03 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-11-03.md --title "paper_ethb day 24: 2026-11-03 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **MET.**

- Days without a violation: **24 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **12 of 12** (need 5+, all clean)
- Running time: 309.9 hours (12.91 days of 24 h)

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
| 2026-10-29 | 19.6 |
| 2026-10-30 | 12.8 |
| 2026-10-31 | 22.8 |
| 2026-11-01 | 24.0 |
| 2026-11-02 | 20.1 |
| 2026-11-03 | 7.3 |
