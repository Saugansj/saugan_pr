# paper_ethmk day 4: 2026-10-23 (UTC)

Ledger `data/trader/paper_ethmk`, window 2026-10-23 00:00:00 to 2026-10-24 00:00:00 UTC (data from 2026-10-23 00:00:50 to 2026-10-23 20:17:43). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 34, approved 34, orders 34, paper fills 0, btc-speed events 56 and trades 34.
- Paper P&L to the end of the window: no fills yet.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 34 intents, 34 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | maker | 34 | 0 | 0 | - | 0.0000 |

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

56 causal ETH moves (>= 6.0 bp in 2 s) and 34 trades sent to the kernel. Per mapped market: trade 34, ends too soon 18, ask above max price 4.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-23 13:35:25 | +7.0 | 0x832d1240: trade |
| 2026-10-23 13:36:32 | +6.1 | 0x832d1240: trade |
| 2026-10-23 13:41:33 | +6.5 | 0x832d1240: ends too soon |
| 2026-10-23 13:42:50 | +6.1 | 0x832d1240: ends too soon |
| 2026-10-23 13:44:07 | +6.2 | 0x832d1240: ends too soon |
| 2026-10-23 13:45:30 | +7.2 | 0x06346734: trade |
| 2026-10-23 14:11:21 | -7.4 | 0x9ea87eef: ends too soon |
| 2026-10-23 14:13:03 | -6.1 | 0x9ea87eef: ends too soon |
| 2026-10-23 14:16:20 | -6.3 | 0x451d7b8e: trade |
| 2026-10-23 14:17:22 | +6.4 | 0x451d7b8e: trade |
| 2026-10-23 14:18:26 | -6.2 | 0x451d7b8e: ask above max price |
| 2026-10-23 14:19:39 | +6.1 | 0x451d7b8e: trade |
| 2026-10-23 14:20:53 | +6.1 | 0x451d7b8e: trade |
| 2026-10-23 14:22:01 | +6.1 | 0x451d7b8e: trade |
| 2026-10-23 14:23:02 | -6.0 | 0x451d7b8e: trade |
| 2026-10-23 14:25:53 | +6.3 | 0x451d7b8e: ends too soon |
| 2026-10-23 14:27:41 | +6.1 | 0x451d7b8e: ends too soon |
| 2026-10-23 14:30:08 | -6.0 | 0x274099db: trade |
| 2026-10-23 14:31:18 | -6.3 | 0x274099db: trade |
| 2026-10-23 14:35:04 | +6.0 | 0x274099db: trade |
| 2026-10-23 14:36:13 | +6.2 | 0x274099db: ask above max price |
| 2026-10-23 14:41:29 | -6.1 | 0x274099db: ends too soon |
| 2026-10-23 14:46:06 | +6.8 | 0x2a82879b: trade |
| 2026-10-23 14:53:15 | +7.1 | 0x2a82879b: trade |
| 2026-10-23 15:13:49 | +6.1 | 0x30eaf932: ends too soon |
| 2026-10-23 15:15:23 | +6.4 | 0xa36aec1e: trade |
| 2026-10-23 15:16:28 | -6.4 | 0xa36aec1e: trade |
| 2026-10-23 15:22:05 | +6.2 | 0xa36aec1e: trade |
| 2026-10-23 15:24:37 | +6.2 | 0xa36aec1e: trade |
| 2026-10-23 15:27:01 | +6.1 | 0xa36aec1e: ends too soon |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-23 02:21:31 | 0x4cb218d2 | 15m | 0.78 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 02:32:17 | 0x49d05e8b | 15m | 0.09 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 03:02:38 | 0x7ab1c10b | 15m | 0.5 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 04:34:09 | 0xdeac92ca | 15m | 0.54 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 05:34:53 | 0x5597d026 | 15m | 0.14 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 06:50:27 | 0x42933c90 | 15m | 0.79 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 09:30:07 | 0xfc391e04 | 15m | 0.64 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 09:31:30 | 0xfc391e04 | 15m | 0.64 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 09:46:09 | 0xbea4f82a | 15m | 0.66 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 11:01:53 | 0xfc4b96fc | 15m | 0.81 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 12:47:28 | 0x46383bca | 15m | 0.48 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 13:17:37 | 0x5404fb53 | 15m | 0.24 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 13:30:07 | 0x832d1240 | 15m | 0.53 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 13:31:32 | 0x832d1240 | 15m | 0.34 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 13:32:44 | 0x832d1240 | 15m | 0.54 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 13:33:48 | 0x832d1240 | 15m | 0.54 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 13:35:25 | 0x832d1240 | 15m | 0.61 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 13:36:32 | 0x832d1240 | 15m | 0.48 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 13:45:30 | 0x06346734 | 15m | 0.45 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 14:16:20 | 0x451d7b8e | 15m | 0.64 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 14:17:22 | 0x451d7b8e | 15m | 0.11 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 14:19:39 | 0x451d7b8e | 15m | 0.06 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 14:20:53 | 0x451d7b8e | 15m | 0.08 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 14:22:01 | 0x451d7b8e | 15m | 0.17 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 14:23:02 | 0x451d7b8e | 15m | 0.82 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 14:30:08 | 0x274099db | 15m | 0.49 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 14:31:18 | 0x274099db | 15m | 0.48 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 14:35:04 | 0x274099db | 15m | 0.85 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 14:46:06 | 0x2a82879b | 15m | 0.4 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 14:53:15 | 0x2a82879b | 15m | 0.81 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 15:15:23 | 0xa36aec1e | 15m | 0.55 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 15:16:28 | 0xa36aec1e | 15m | 0.35 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 15:22:05 | 0xa36aec1e | 15m | 0.78 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-23 15:24:37 | 0xa36aec1e | 15m | 0.72 | approved | open | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 976, median 208, p90 223, min 186, max 513.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 288023, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 3.4, max 77.0.
- Binance event time to local receive (network + clock offset): n 288023, median of minute medians -100.5, worst minute p90 591.0, worst minute p99 1220.0, max 65534.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 533853, median of minute medians 9.7, worst minute p90 20.4, worst minute p99 22450831.4, max 14391593.2.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 56, median -100, p90 -38, min -241, max 41.
- Local receive to decision: n 56, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 56, median 359, p90 388, min 343, max 492.

## Risk, reconciliation, invariants and audit

- Trips: 3: global REDUCING (stale feed polymarket:crypto-fast: 66179 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 66179 ms, breaker:stale_feed); global REDUCING (stale feed binance:ETH: 14396649 ms, breaker:stale_feed).
- Human resets: 6; halts confirmed by zero open orders: 0.
- Reconciles: 196 (periodic 196); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 472 records, head 5bc1e03d3b2abafd; last head anchored in the ledger: 278 records, 32be13c0879007b5 (startup, 2026-10-22 13:09:13).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-mk-eth-bybit | 0 | 200 / 100 | 0.00 | no evidence yet |

Elapsed since the first run: 3.45 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethmk --date 2026-10-23 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethmk_2026-10-23.md --title "paper_ethmk day 4: 2026-10-23 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **4 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **1 of 1** (need 5+, all clean)
- Running time: 57.3 hours (2.39 days of 24 h)

| UTC day | Hours running |
|---|---|
| 2026-10-20 | 7.5 |
| 2026-10-21 | 17.6 |
| 2026-10-22 | 15.9 |
| 2026-10-23 | 16.3 |
