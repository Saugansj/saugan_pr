# paper_ethmk day 7: 2026-10-26 (UTC)

Ledger `data/trader/paper_ethmk`, window 2026-10-26 00:00:00 to 2026-10-27 00:00:00 UTC (data from 2026-10-26 01:00:17 to 2026-10-26 16:21:28). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 47, approved 47, orders 47, paper fills 0, btc-speed events 76 and trades 47.
- Paper P&L to the end of the window: no fills yet.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 47 intents, 47 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | maker | 47 | 0 | 0 | - | 0.0000 |

Merges of YES+NO pairs: 0; paper redemptions: 0.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| - | - | 0 | - | - | - |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-mk-eth-bybit**: P&L per trade in USD held to resolution: size * (outcome - fill price), maker (no fee). Resolved trades 0 in 0 markets (needs 200), unresolved 0, mean - USD, cluster SE -, total +0.0000 USD. Verdict: **running (0 of 200)**.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-20 13:10:40), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-20 13:10:40), `btc-speed-mk-eth-bybit` (sha256 3ee8f1e109811bdc, written 2026-10-20 13:10:40).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

76 causal ETH moves (>= 6.0 bp in 2 s) and 47 trades sent to the kernel. Per mapped market: trade 47, ask above max price 15, ends too soon 13, move started before the window 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-26 14:00:22 | +6.2 | 0x862f64fa: trade |
| 2026-10-26 14:01:25 | -6.5 | 0x862f64fa: trade |
| 2026-10-26 14:03:18 | -6.9 | 0x862f64fa: trade |
| 2026-10-26 14:06:46 | -7.0 | 0x862f64fa: trade |
| 2026-10-26 14:09:51 | +6.5 | 0x862f64fa: ask above max price |
| 2026-10-26 14:11:16 | +7.7 | 0x862f64fa: ends too soon |
| 2026-10-26 14:15:47 | +6.0 | 0xe3834b19: trade |
| 2026-10-26 14:19:28 | +6.1 | 0xe3834b19: ask above max price |
| 2026-10-26 14:22:00 | -6.9 | 0xe3834b19: trade |
| 2026-10-26 14:26:50 | -6.1 | 0xe3834b19: ends too soon |
| 2026-10-26 14:30:26 | +6.7 | 0x5139324e: trade |
| 2026-10-26 14:32:24 | -6.9 | 0x5139324e: trade |
| 2026-10-26 14:35:53 | +6.9 | 0x5139324e: trade |
| 2026-10-26 14:37:01 | -6.4 | 0x5139324e: trade |
| 2026-10-26 14:47:12 | -6.3 | 0x186a7ea8: trade |
| 2026-10-26 14:48:38 | -6.2 | 0x186a7ea8: trade |
| 2026-10-26 14:50:31 | -6.2 | 0x186a7ea8: trade |
| 2026-10-26 15:04:03 | +7.2 | 0xd5ce8f98: trade |
| 2026-10-26 15:05:34 | +6.7 | 0xd5ce8f98: trade |
| 2026-10-26 15:07:45 | +6.0 | 0xd5ce8f98: trade |
| 2026-10-26 15:11:17 | -6.2 | 0xd5ce8f98: ends too soon |
| 2026-10-26 15:18:11 | +6.1 | 0x527f5f51: trade |
| 2026-10-26 15:21:02 | +6.2 | 0x527f5f51: ask above max price |
| 2026-10-26 15:22:08 | +6.7 | 0x527f5f51: ask above max price |
| 2026-10-26 15:23:10 | +6.5 | 0x527f5f51: ask above max price |
| 2026-10-26 15:24:23 | +7.2 | 0x527f5f51: ask above max price |
| 2026-10-26 15:37:59 | +6.9 | 0xc0cb399d: ask above max price |
| 2026-10-26 15:46:45 | +6.5 | 0x53068678: trade |
| 2026-10-26 16:08:07 | -6.7 | 0x5b50db7b: trade |
| 2026-10-26 16:16:06 | -6.1 | 0xea5eed2a: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-26 08:32:37 | 0x3db32744 | 15m | 0.64 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 09:17:42 | 0xe3ce751f | 15m | 0.71 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 11:53:19 | 0xfd6ecfe8 | 15m | 0.85 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 12:34:49 | 0x246918cf | 15m | 0.38 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 12:45:23 | 0x12849111 | 15m | 0.58 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 12:47:42 | 0x12849111 | 15m | 0.42 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 13:02:01 | 0x449449bd | 15m | 0.83 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 13:31:13 | 0xa151c9c9 | 15m | 0.4 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 13:32:23 | 0xa151c9c9 | 15m | 0.31 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 13:33:35 | 0xa151c9c9 | 15m | 0.28 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 13:36:06 | 0xa151c9c9 | 15m | 0.06 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 13:37:10 | 0xa151c9c9 | 15m | 0.25 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 13:38:30 | 0xa151c9c9 | 15m | 0.67 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 13:45:39 | 0x385be21b | 15m | 0.65 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 13:47:42 | 0x385be21b | 15m | 0.58 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 13:49:01 | 0x385be21b | 15m | 0.52 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 13:50:07 | 0x385be21b | 15m | 0.42 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 13:52:15 | 0x385be21b | 15m | 0.63 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 13:53:21 | 0x385be21b | 15m | 0.78 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 13:54:53 | 0x385be21b | 15m | 0.1 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:00:22 | 0x862f64fa | 15m | 0.7 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:01:25 | 0x862f64fa | 15m | 0.42 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:03:18 | 0x862f64fa | 15m | 0.58 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:06:46 | 0x862f64fa | 15m | 0.22 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:15:47 | 0xe3834b19 | 15m | 0.54 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:22:00 | 0xe3834b19 | 15m | 0.03 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:30:26 | 0x5139324e | 15m | 0.49 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:32:24 | 0x5139324e | 15m | 0.64 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:35:53 | 0x5139324e | 15m | 0.53 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:37:01 | 0x5139324e | 15m | 0.37 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:47:12 | 0x186a7ea8 | 15m | 0.71 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:48:38 | 0x186a7ea8 | 15m | 0.27 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:50:31 | 0x186a7ea8 | 15m | 0.31 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 15:04:03 | 0xd5ce8f98 | 15m | 0.5 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 15:05:34 | 0xd5ce8f98 | 15m | 0.46 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 15:07:45 | 0xd5ce8f98 | 15m | 0.68 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 15:18:11 | 0x527f5f51 | 15m | 0.72 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 15:46:45 | 0x53068678 | 15m | 0.46 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 16:08:07 | 0x5b50db7b | 15m | 0.8 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-26 16:16:06 | 0xea5eed2a | 15m | 0.64 | approved | open | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 626, median 226, p90 253, min 200, max 573.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 232779, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 14.0, max 58.0.
- Binance event time to local receive (network + clock offset): n 232779, median of minute medians -137.0, worst minute p90 1446.0, worst minute p99 4551.3, max 4880.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 341383, median of minute medians 9.7, worst minute p90 64.0, worst minute p99 28465867.0, max 17793227.8.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 76, median -238, p90 14, min -326, max 262.
- Local receive to decision: n 76, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 76, median 379, p90 414, min 356, max 471.

## Risk, reconciliation, invariants and audit

- Trips: 1: global ACTIVE (reset, human:DELL-feed).
- Human resets: 20; halts confirmed by zero open orders: 0.
- Reconciles: 126 (periodic 126); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 681 records, head fa7a636aa68e2b13; last head anchored in the ledger: 472 records, 5bc1e03d3b2abafd (startup, 2026-10-24 17:18:49).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-mk-eth-bybit | 0 | 200 / 100 | 0.00 | no evidence yet |

Elapsed since the first run: 6.13 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethmk --date 2026-10-26 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethmk_2026-10-26.md --title "paper_ethmk day 7: 2026-10-26 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **7 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **2 of 2** (need 5+, all clean)
- Running time: 91.6 hours (3.82 days of 24 h)

| UTC day | Hours running |
|---|---|
| 2026-10-20 | 7.5 |
| 2026-10-21 | 17.6 |
| 2026-10-22 | 15.9 |
| 2026-10-23 | 16.3 |
| 2026-10-24 | 6.7 |
| 2026-10-25 | 17.2 |
| 2026-10-26 | 10.4 |
