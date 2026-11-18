# paper_ethb day 13: 2026-10-23 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-10-23 00:00:00 to 2026-10-24 00:00:00 UTC (data from 2026-10-23 00:00:55 to 2026-10-23 20:17:43). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 43, approved 37, orders 37, paper fills 31, btc-speed events 56 and trades 43.
- Paper P&L to the end of the window: btc-speed +132.33 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 325 | 715.22 | 0.00 | 20.9533 | 0.00 | 868.50 | 0 | 0.00 | +132.3274 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 43 intents, 37 approved, 6 rejected: REDUCING 6.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

Latest distinct rejections:

| Time UTC | Strategy | Reason | Binding cap |
|---|---|---|---|
| 2026-10-23 02:32:17 | btc-speed | REDUCING: only exposure-reducing orders | - |

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | taker | 37 | 31 | 150 | 0.5213 | 2.1683 |

Merges of YES+NO pairs: 0; paper redemptions: 30.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| btc-speed | 5 s | 30 | +5.73c | +1.27c | 1 |
| btc-speed | 60 s | 28 | +7.71c | +3.49c | 3 |
| btc-speed | 300 s | 15 | +2.90c | +7.15c | 16 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-v4-eth-bybit**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 321 in 321 markets (needs 200), unresolved 0, mean 0.4122 USD, cluster SE 0.1214, total +132.3274 USD. Verdict: **PASS**.
- **Paper-fill realism** (btc-speed at real tape prices): 267 of 321 resolved trades repriced at what real takers paid in our order's second. Paper +122.16 USD -> best case +59.31 (cheapest real price), typical +15.93 (median real price), **live estimate +13.92** (our order behind the real takers that beat us, partial fills; 68% of our shares filled); real takers paid a median +6.0c over our fill. Paper assumes we win every race for the cheapest ask. Not comparable with reports before 15 Oct.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-11 19:34:32), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-11 19:34:32), `btc-speed-v4-eth-bybit` (sha256 04680de003a175aa, written 2026-10-11 19:34:32).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

56 causal ETH moves (>= 6.0 bp in 2 s) and 43 trades sent to the kernel. Per mapped market: trade 43, already holding this market 39, ask above max price 17, no ask 7, ends too soon 5, too little size at ask 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-23 13:35:25 | +7.0 | 0x832d1240: already holding this market; 0x9e901aa6: trade |
| 2026-10-23 13:36:32 | +6.1 | 0x832d1240: already holding this market; 0x9e901aa6: trade |
| 2026-10-23 13:41:33 | +6.5 | 0x832d1240: already holding this market; 0xc395d9f7: ask above max price |
| 2026-10-23 13:42:50 | +6.1 | 0x832d1240: already holding this market; 0xc395d9f7: ask above max price |
| 2026-10-23 13:44:07 | +6.2 | 0x832d1240: already holding this market; 0xc395d9f7: ends too soon |
| 2026-10-23 13:45:30 | +7.2 | 0x06346734: trade; 0xa043722c: trade |
| 2026-10-23 14:11:21 | -7.4 | 0x5ef415f6: ask above max price; 0x9ea87eef: no ask |
| 2026-10-23 14:13:03 | -6.1 | 0x5ef415f6: no ask; 0x9ea87eef: no ask |
| 2026-10-23 14:16:20 | -6.3 | 0x451d7b8e: trade; 0x931e7b37: trade |
| 2026-10-23 14:17:22 | +6.4 | 0x451d7b8e: already holding this market; 0x931e7b37: already holding this market |
| 2026-10-23 14:18:26 | -6.2 | 0x451d7b8e: already holding this market; 0x931e7b37: already holding this market |
| 2026-10-23 14:19:39 | +6.1 | 0x451d7b8e: already holding this market; 0x931e7b37: already holding this market |
| 2026-10-23 14:20:53 | +6.1 | 0x451d7b8e: already holding this market; 0x54614dd7: trade |
| 2026-10-23 14:22:01 | +6.1 | 0x451d7b8e: already holding this market; 0x54614dd7: already holding this market |
| 2026-10-23 14:23:02 | -6.0 | 0x451d7b8e: already holding this market; 0x54614dd7: already holding this market |
| 2026-10-23 14:25:53 | +6.3 | 0x451d7b8e: already holding this market; 0x759a20af: trade |
| 2026-10-23 14:27:41 | +6.1 | 0x451d7b8e: already holding this market; 0x759a20af: already holding this market |
| 2026-10-23 14:30:08 | -6.0 | 0x274099db: trade; 0x8eb5d244: trade |
| 2026-10-23 14:31:18 | -6.3 | 0x274099db: already holding this market; 0x8eb5d244: already holding this market |
| 2026-10-23 14:35:04 | +6.0 | 0x274099db: already holding this market; 0x8de257a7: trade |
| 2026-10-23 14:36:13 | +6.2 | 0x274099db: already holding this market; 0x8de257a7: already holding this market |
| 2026-10-23 14:41:29 | -6.1 | 0x274099db: already holding this market; 0x6f56a43a: trade |
| 2026-10-23 14:46:06 | +6.8 | 0x0141432d: trade; 0x2a82879b: trade |
| 2026-10-23 14:53:15 | +7.1 | 0x2a82879b: already holding this market; 0x8a4228f4: ask above max price |
| 2026-10-23 15:13:49 | +6.1 | 0x30eaf932: trade; 0xaf33d708: trade |
| 2026-10-23 15:15:23 | +6.4 | 0xa36aec1e: trade; 0xd0a9c5cf: trade |
| 2026-10-23 15:16:28 | -6.4 | 0xa36aec1e: already holding this market; 0xd0a9c5cf: already holding this market |
| 2026-10-23 15:22:05 | +6.2 | 0x4a3880fb: trade; 0xa36aec1e: already holding this market |
| 2026-10-23 15:24:37 | +6.2 | 0x4a3880fb: already holding this market; 0xa36aec1e: already holding this market |
| 2026-10-23 15:27:01 | +6.1 | 0xa36aec1e: already holding this market; 0xf6acb47e: ask above max price |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-23 02:21:31 | 0x815b5b1c | 5m | 0.84 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-23 02:32:17 | 0x49d05e8b | 15m | 0.09 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-23 02:32:17 | 0x1767811f | 5m | 0.01 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-23 03:02:38 | 0xcfcc26d2 | 5m | 0.43 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 03:02:38 | 0x7ab1c10b | 15m | 0.5 | approved | open | 5 | 0.570 | 0.0858 | 2.0642 |
| 2026-10-23 04:34:09 | 0xdeac92ca | 15m | 0.54 | approved | open | 5 | 0.540 | 0.0869 | 2.2131 |
| 2026-10-23 04:57:00 | 0x48a44466 | 5m | 0.84 | approved | open | 5 | 0.840 | 0.0470 | 0.7530 |
| 2026-10-23 05:34:53 | 0x5597d026 | 15m | 0.14 | approved | open | 5 | 0.140 | 0.0421 | -0.7421 |
| 2026-10-23 06:50:27 | 0x42933c90 | 15m | 0.79 | approved | open | 5 | 0.790 | 0.0581 | 0.9919 |
| 2026-10-23 06:50:27 | 0xf20b1d5d | 5m | 0.48 | approved | open | 5 | 0.480 | 0.0874 | 2.5126 |
| 2026-10-23 09:30:07 | 0xfc391e04 | 15m | 0.64 | approved | open | 5 | 0.640 | 0.0806 | 1.7194 |
| 2026-10-23 09:31:30 | 0x62518f2f | 5m | 0.72 | approved | open | 5 | 0.720 | 0.0706 | -3.6706 |
| 2026-10-23 09:46:09 | 0xbea4f82a | 15m | 0.66 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 09:46:09 | 0xd23d6b9b | 5m | 0.77 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 11:01:53 | 0xfc4b96fc | 15m | 0.81 | approved | open | 5 | 0.810 | 0.0539 | 0.8961 |
| 2026-10-23 12:47:28 | 0x71276178 | 5m | 0.43 | approved | open | 5 | 0.430 | 0.0858 | 2.7642 |
| 2026-10-23 12:47:28 | 0x46383bca | 15m | 0.48 | approved | open | 5 | 0.480 | 0.0874 | -2.4874 |
| 2026-10-23 13:17:37 | 0xa58d0940 | 5m | 0.03 | approved | open | 5 | 0.030 | 0.0102 | -0.1602 |
| 2026-10-23 13:17:37 | 0x5404fb53 | 15m | 0.24 | approved | open | 5 | 0.240 | 0.0638 | 3.7362 |
| 2026-10-23 13:30:07 | 0x832d1240 | 15m | 0.53 | approved | open | 5 | 0.520 | 0.0874 | 2.3126 |
| 2026-10-23 13:30:07 | 0x0897aa94 | 5m | 0.49 | approved | open | 5 | 0.490 | 0.0875 | 2.4625 |
| 2026-10-23 13:35:25 | 0x9e901aa6 | 5m | 0.42 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 13:36:32 | 0x9e901aa6 | 5m | 0.27 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 13:45:30 | 0x06346734 | 15m | 0.45 | approved | open | 5 | 0.450 | 0.0866 | -2.3366 |
| 2026-10-23 13:45:30 | 0xa043722c | 5m | 0.49 | approved | open | 5 | 0.500 | 0.0875 | -2.5875 |
| 2026-10-23 14:16:20 | 0x451d7b8e | 15m | 0.64 | approved | open | 5 | 0.680 | 0.0762 | 1.5238 |
| 2026-10-23 14:16:20 | 0x931e7b37 | 5m | 0.77 | approved | open | 5 | 0.800 | 0.0560 | 0.9440 |
| 2026-10-23 14:20:53 | 0x54614dd7 | 5m | 0.71 | approved | open | 5 | 0.720 | 0.0706 | 1.3294 |
| 2026-10-23 14:25:53 | 0x759a20af | 5m | 0.5 | approved | open | 5 | 0.530 | 0.0872 | -2.7372 |
| 2026-10-23 14:30:08 | 0x8eb5d244 | 5m | 0.5 | approved | open | 5 | 0.550 | 0.0866 | -2.8366 |
| 2026-10-23 14:30:08 | 0x274099db | 15m | 0.49 | approved | open | 5 | 0.490 | 0.0875 | -2.5398 |
| 2026-10-23 14:35:04 | 0x8de257a7 | 5m | 0.66 | approved | open | 5 | 0.660 | 0.0785 | 1.6215 |
| 2026-10-23 14:41:29 | 0x6f56a43a | 5m | 0.55 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 14:46:06 | 0x0141432d | 5m | 0.34 | approved | open | 5 | 0.340 | 0.0785 | -1.7785 |
| 2026-10-23 14:46:06 | 0x2a82879b | 15m | 0.4 | approved | open | 5 | 0.400 | 0.0840 | -2.0840 |
| 2026-10-23 15:13:49 | 0x30eaf932 | 15m | 0.001 | approved | open | 5 | 0.009 | 0.0031 | -0.0481 |
| 2026-10-23 15:13:49 | 0xaf33d708 | 5m | 0.01 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 15:15:23 | 0xa36aec1e | 15m | 0.55 | approved | open | 5 | 0.550 | 0.0866 | 2.1634 |
| 2026-10-23 15:15:23 | 0xd0a9c5cf | 5m | 0.62 | approved | open | 5 | 0.620 | 0.0825 | 1.8175 |
| 2026-10-23 15:22:05 | 0x4a3880fb | 5m | 0.62 | approved | open | 5 | 0.620 | 0.0825 | -3.1825 |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 977, median 208, p90 224, min 184, max 497.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 288022, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 5.3, max 99.0.
- Binance event time to local receive (network + clock offset): n 288022, median of minute medians -101.2, worst minute p90 590.5, worst minute p99 1204.7, max 65532.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 533413, median of minute medians 9.6, worst minute p90 14.8, worst minute p99 22306868.7, max 14391540.7.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 56, median -99, p90 -39, min -241, max 41.
- Local receive to decision: n 56, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 56, median 360, p90 379, min 337, max 566.

## Risk, reconciliation, invariants and audit

- Trips: 4: btc-speed ACTIVE (reset, human:DELL-auto); global REDUCING (stale feed polymarket:crypto-fast: 66178 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 66178 ms, breaker:stale_feed); global REDUCING (stale feed binance:ETH: 14396662 ms, breaker:stale_feed).
- Human resets: 9; halts confirmed by zero open orders: 0.
- Reconciles: 196 (periodic 196); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 1709 records, head 2c03399bc4bb6647; last head anchored in the ledger: 1485 records, 37ffb6c17c971b9c (startup, 2026-10-22 13:08:18).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 321 | 200 / 100 | 26.35 | 0 |

Elapsed since the first run: 12.18 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-10-23 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-10-23.md --title "paper_ethb day 13: 2026-10-23 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **13 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **9 of 9** (need 5+, all clean)
- Running time: 137.6 hours (5.73 days of 24 h)

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
