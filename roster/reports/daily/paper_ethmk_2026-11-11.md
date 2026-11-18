# paper_ethmk day 23: 2026-11-11 (UTC)

Ledger `data/trader/paper_ethmk`, window 2026-11-11 00:00:00 to 2026-11-12 00:00:00 UTC (data from 2026-11-11 14:41:31 to 2026-11-11 16:21:43). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 16, approved 16, orders 16, paper fills 0, btc-speed events 32 and trades 17.
- Paper P&L to the end of the window: no fills yet.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 16 intents, 16 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | maker | 16 | 0 | 0 | - | 0.0000 |

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

32 causal ETH moves (>= 6.0 bp in 2 s) and 17 trades sent to the kernel. Per mapped market: trade 17, ends too soon 8, ask above max price 4.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-11-11 14:48:02 | +6.6 | - |
| 2026-11-11 14:51:28 | -6.1 | 0xa226594e: trade |
| 2026-11-11 14:54:43 | +6.2 | 0xa226594e: trade |
| 2026-11-11 14:56:04 | +6.0 | 0xa226594e: ends too soon |
| 2026-11-11 14:59:35 | +6.4 | 0xa226594e: ends too soon |
| 2026-11-11 15:00:46 | +6.3 | 0xb111b5f7: trade |
| 2026-11-11 15:09:14 | -6.2 | 0xb111b5f7: trade |
| 2026-11-11 15:12:03 | +6.0 | 0xb111b5f7: ends too soon |
| 2026-11-11 15:14:19 | +6.3 | 0xb111b5f7: ends too soon |
| 2026-11-11 15:21:38 | -6.3 | 0x93922000: ask above max price |
| 2026-11-11 15:25:02 | +6.2 | 0x93922000: ends too soon |
| 2026-11-11 15:32:26 | +6.9 | 0x104a1436: trade |
| 2026-11-11 15:33:46 | +7.5 | 0x104a1436: ask above max price |
| 2026-11-11 15:34:48 | +6.1 | 0x104a1436: ask above max price |
| 2026-11-11 15:35:49 | +8.9 | 0x104a1436: ask above max price |
| 2026-11-11 15:37:01 | -6.2 | 0x104a1436: trade |
| 2026-11-11 15:38:14 | -6.2 | 0x104a1436: trade |
| 2026-11-11 15:44:58 | -6.0 | 0x104a1436: ends too soon |
| 2026-11-11 15:48:33 | +6.8 | 0x464a2e7a: trade |
| 2026-11-11 15:51:31 | -7.4 | 0x464a2e7a: trade |
| 2026-11-11 15:52:39 | -6.1 | 0x464a2e7a: trade |
| 2026-11-11 15:57:10 | -6.7 | 0x464a2e7a: ends too soon |
| 2026-11-11 16:02:15 | +6.8 | 0xd7b166b8: trade |
| 2026-11-11 16:07:28 | +6.5 | 0xd7b166b8: trade |
| 2026-11-11 16:09:22 | +6.1 | 0xd7b166b8: trade |
| 2026-11-11 16:12:16 | +6.0 | 0xd7b166b8: ends too soon |
| 2026-11-11 16:16:02 | -6.9 | 0xe29d38a8: trade |
| 2026-11-11 16:18:16 | -7.3 | 0xe29d38a8: trade |
| 2026-11-11 16:20:21 | -7.0 | 0xe29d38a8: trade |
| 2026-11-11 16:21:43 | -6.0 | 0xe29d38a8: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-11 14:51:28 | 0xa226594e | 15m | 0.21 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-11 14:54:43 | 0xa226594e | 15m | 0.37 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-11 15:00:46 | 0xb111b5f7 | 15m | 0.41 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-11 15:09:14 | 0xb111b5f7 | 15m | 0.72 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-11 15:32:26 | 0x104a1436 | 15m | 0.58 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-11 15:37:01 | 0x104a1436 | 15m | 0.031 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-11 15:38:14 | 0x104a1436 | 15m | 0.01 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-11 15:48:33 | 0x464a2e7a | 15m | 0.37 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-11 15:51:31 | 0x464a2e7a | 15m | 0.71 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-11 15:52:39 | 0x464a2e7a | 15m | 0.53 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-11 16:02:15 | 0xd7b166b8 | 15m | 0.51 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-11 16:07:28 | 0xd7b166b8 | 15m | 0.15 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-11 16:09:22 | 0xd7b166b8 | 15m | 0.53 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-11 16:16:02 | 0xe29d38a8 | 15m | 0.48 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-11 16:18:16 | 0xe29d38a8 | 15m | 0.59 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-11 16:20:21 | 0xe29d38a8 | 15m | 0.49 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-11 16:21:43 | 0xe29d38a8 | 15m | 0.63 | approved | open | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 101, median 217, p90 240, min 195, max 303.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 48130, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 1.8, max 48.0.
- Binance event time to local receive (network + clock offset): n 48130, median of minute medians 29.5, worst minute p90 2773.0, worst minute p99 7029.1, max 7232.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 54609, median of minute medians 9.8, worst minute p90 66.1, worst minute p99 81438867.9, max 62168401.3.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 32, median 34, p90 71, min -2095, max 177.
- Local receive to decision: n 32, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 32, median 366, p90 376, min 345, max 400.

## Risk, reconciliation, invariants and audit

- Trips: 1: global ACTIVE (reset, human:DELL-auto).
- Human resets: 89; halts confirmed by zero open orders: 0.
- Reconciles: 21 (periodic 21); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 2186 records, head 9b46fd1abc9cdb85; last head anchored in the ledger: 2084 records, 1cc73551a21c94ca (startup, 2026-11-10 07:09:10).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-mk-eth-bybit | 0 | 200 / 100 | 0.00 | no evidence yet |

Elapsed since the first run: 22.13 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethmk --date 2026-11-11 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethmk_2026-11-11.md --title "paper_ethmk day 23: 2026-11-11 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **MET.**

- Days without a violation: **23 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **7 of 7** (need 5+, all clean)
- Running time: 279.8 hours (11.66 days of 24 h)

| UTC day | Hours running |
|---|---|
| 2026-10-20 | 7.5 |
| 2026-10-21 | 17.6 |
| 2026-10-22 | 15.9 |
| 2026-10-23 | 16.3 |
| 2026-10-24 | 6.7 |
| 2026-10-25 | 17.2 |
| 2026-10-26 | 18.1 |
| 2026-10-27 | 18.3 |
| 2026-10-28 | 5.6 |
| 2026-10-29 | 19.6 |
| 2026-10-30 | 12.8 |
| 2026-10-31 | 22.8 |
| 2026-11-01 | 24.0 |
| 2026-11-02 | 20.1 |
| 2026-11-03 | 14.4 |
| 2026-11-04 | 19.4 |
| 2026-11-06 | 10.8 |
| 2026-11-07 | 4.5 |
| 2026-11-10 | 6.5 |
| 2026-11-11 | 1.7 |
