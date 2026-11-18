# paper_ethmk day 11: 2026-10-30 (UTC)

Ledger `data/trader/paper_ethmk`, window 2026-10-30 00:00:00 to 2026-10-31 00:00:00 UTC (data from 2026-10-30 11:09:19 to 2026-10-30 16:21:35). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 55, approved 55, orders 55, paper fills 0, btc-speed events 82 and trades 55.
- Paper P&L to the end of the window: no fills yet.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 55 intents, 55 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | maker | 55 | 0 | 0 | - | 0.0000 |

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

82 causal ETH moves (>= 6.0 bp in 2 s) and 55 trades sent to the kernel. Per mapped market: trade 55, ends too soon 23, ask above max price 4.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-30 14:53:50 | +6.0 | 0xdbea8884: trade |
| 2026-10-30 14:55:41 | +6.1 | 0xdbea8884: ends too soon |
| 2026-10-30 15:01:02 | +7.0 | 0xbf8d8a3c: trade |
| 2026-10-30 15:02:34 | -6.1 | 0xbf8d8a3c: trade |
| 2026-10-30 15:06:59 | +8.4 | 0xbf8d8a3c: ask above max price |
| 2026-10-30 15:09:18 | +6.8 | 0xbf8d8a3c: ask above max price |
| 2026-10-30 15:11:34 | -6.1 | 0xbf8d8a3c: ends too soon |
| 2026-10-30 15:13:49 | -6.2 | 0xbf8d8a3c: ends too soon |
| 2026-10-30 15:16:41 | +6.0 | 0xbd210a85: trade |
| 2026-10-30 15:18:41 | +6.2 | 0xbd210a85: trade |
| 2026-10-30 15:19:48 | +7.2 | 0xbd210a85: trade |
| 2026-10-30 15:21:05 | -6.4 | 0xbd210a85: trade |
| 2026-10-30 15:22:12 | -6.0 | 0xbd210a85: trade |
| 2026-10-30 15:23:35 | +6.2 | 0xbd210a85: trade |
| 2026-10-30 15:24:43 | +6.7 | 0xbd210a85: trade |
| 2026-10-30 15:26:16 | -6.1 | 0xbd210a85: ends too soon |
| 2026-10-30 15:27:47 | -6.4 | 0xbd210a85: ends too soon |
| 2026-10-30 15:31:36 | -6.1 | 0xf3a2dd03: trade |
| 2026-10-30 15:38:20 | +6.4 | 0xf3a2dd03: trade |
| 2026-10-30 15:42:01 | -6.5 | 0xf3a2dd03: ends too soon |
| 2026-10-30 15:44:25 | -6.2 | 0xf3a2dd03: ends too soon |
| 2026-10-30 15:47:26 | -7.0 | 0xb5c4b1c4: trade |
| 2026-10-30 15:50:17 | -6.7 | 0xb5c4b1c4: trade |
| 2026-10-30 15:55:10 | +6.6 | 0xb5c4b1c4: ends too soon |
| 2026-10-30 15:57:21 | +6.3 | 0xb5c4b1c4: ends too soon |
| 2026-10-30 15:59:48 | -6.2 | 0xb5c4b1c4: ends too soon |
| 2026-10-30 16:00:59 | -6.7 | 0xb75ef2a7: trade |
| 2026-10-30 16:02:06 | +6.1 | 0xb75ef2a7: trade |
| 2026-10-30 16:04:01 | -6.2 | 0xb75ef2a7: trade |
| 2026-10-30 16:20:48 | -7.9 | 0xbdbf5860: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-30 13:45:32 | 0x5d135964 | 15m | 0.51 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 13:46:37 | 0x5d135964 | 15m | 0.54 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 13:47:52 | 0x5d135964 | 15m | 0.63 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 13:49:10 | 0x5d135964 | 15m | 0.26 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 13:50:17 | 0x5d135964 | 15m | 0.8 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 13:52:51 | 0x5d135964 | 15m | 0.1 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 13:53:57 | 0x5d135964 | 15m | 0.25 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 14:00:06 | 0x8fb42e03 | 15m | 0.48 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 14:01:44 | 0x8fb42e03 | 15m | 0.46 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 14:02:46 | 0x8fb42e03 | 15m | 0.69 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 14:06:55 | 0x8fb42e03 | 15m | 0.38 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 14:08:31 | 0x8fb42e03 | 15m | 0.79 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 14:18:26 | 0x1d376ae9 | 15m | 0.4 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 14:20:36 | 0x1d376ae9 | 15m | 0.17 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 14:23:55 | 0x1d376ae9 | 15m | 0.11 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 14:31:46 | 0xd33b6f88 | 15m | 0.4 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 14:36:15 | 0xd33b6f88 | 15m | 0.74 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 14:37:54 | 0xd33b6f88 | 15m | 0.21 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 14:39:36 | 0xd33b6f88 | 15m | 0.83 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 14:45:19 | 0xdbea8884 | 15m | 0.5 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 14:49:16 | 0xdbea8884 | 15m | 0.67 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 14:50:34 | 0xdbea8884 | 15m | 0.81 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 14:53:50 | 0xdbea8884 | 15m | 0.67 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:01:02 | 0xbf8d8a3c | 15m | 0.65 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:02:34 | 0xbf8d8a3c | 15m | 0.22 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:16:41 | 0xbd210a85 | 15m | 0.62 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:18:41 | 0xbd210a85 | 15m | 0.85 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:19:48 | 0xbd210a85 | 15m | 0.82 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:21:05 | 0xbd210a85 | 15m | 0.48 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:22:12 | 0xbd210a85 | 15m | 0.61 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:23:35 | 0xbd210a85 | 15m | 0.34 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:24:43 | 0xbd210a85 | 15m | 0.34 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:31:36 | 0xf3a2dd03 | 15m | 0.84 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:38:20 | 0xf3a2dd03 | 15m | 0.05 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:47:26 | 0xb5c4b1c4 | 15m | 0.72 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:50:17 | 0xb5c4b1c4 | 15m | 0.59 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 16:00:59 | 0xb75ef2a7 | 15m | 0.76 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 16:02:06 | 0xb75ef2a7 | 15m | 0.31 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 16:04:01 | 0xb75ef2a7 | 15m | 0.77 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-30 16:20:48 | 0xbdbf5860 | 15m | 0.22 | approved | open | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 313, median 220, p90 240, min 196, max 1086.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 197523, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 3.9, max 58.0.
- Binance event time to local receive (network + clock offset): n 197523, median of minute medians -78.0, worst minute p90 326.9, worst minute p99 1320.8, max 1893.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 170809, median of minute medians 9.7, worst minute p90 39.0, worst minute p99 65083989.2, max 41454787.4.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 82, median -90, p90 26, min -182, max 249.
- Local receive to decision: n 82, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 82, median 375, p90 400, min 353, max 513.

## Risk, reconciliation, invariants and audit

- Trips: 2: global REDUCING (stale feed binance:ETH: 41449317 ms, breaker:stale_feed); global ACTIVE (reset, human:DELL-auto).
- Human resets: 49; halts confirmed by zero open orders: 0.
- Reconciles: 63 (periodic 63); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 1165 records, head d77f101d5cd1100f; last head anchored in the ledger: 774 records, 98146af57cfcca98 (startup, 2026-10-28 18:21:55).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-mk-eth-bybit | 0 | 200 / 100 | 0.00 | no evidence yet |

Elapsed since the first run: 10.13 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethmk --date 2026-10-30 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethmk_2026-10-30.md --title "paper_ethmk day 11: 2026-10-30 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **11 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **3 of 3** (need 5+, all clean)
- Running time: 147.9 hours (6.16 days of 24 h)

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
| 2026-10-30 | 5.2 |
