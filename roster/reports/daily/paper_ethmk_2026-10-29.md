# paper_ethmk day 10: 2026-10-29 (UTC)

Ledger `data/trader/paper_ethmk`, window 2026-10-29 00:00:00 to 2026-10-30 00:00:00 UTC (data from 2026-10-29 00:00:13 to 2026-10-29 16:21:12). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 43, approved 43, orders 43, paper fills 0, btc-speed events 86 and trades 43.
- Paper P&L to the end of the window: no fills yet.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 43 intents, 43 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | maker | 43 | 0 | 0 | - | 0.0000 |

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

86 causal ETH moves (>= 6.0 bp in 2 s) and 43 trades sent to the kernel. Per mapped market: trade 43, ends too soon 22, ask above max price 19, move started before the window 1, no ask 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-29 14:06:30 | -6.2 | 0xe63d8ae6: trade |
| 2026-10-29 14:13:11 | +6.1 | 0xe63d8ae6: ends too soon |
| 2026-10-29 14:32:20 | +6.1 | 0x18a0d71b: ask above max price |
| 2026-10-29 14:33:47 | +6.3 | 0x18a0d71b: ask above max price |
| 2026-10-29 14:35:26 | -6.2 | 0x18a0d71b: trade |
| 2026-10-29 14:36:27 | +7.5 | 0x18a0d71b: ask above max price |
| 2026-10-29 14:37:29 | +6.2 | 0x18a0d71b: no ask |
| 2026-10-29 14:38:46 | +6.2 | 0x18a0d71b: ask above max price |
| 2026-10-29 14:45:26 | -8.1 | 0x0c6452fc: trade |
| 2026-10-29 14:49:27 | -7.7 | 0x0c6452fc: ask above max price |
| 2026-10-29 14:50:34 | +6.3 | 0x0c6452fc: trade |
| 2026-10-29 15:00:12 | -6.1 | 0xaa6760c2: trade |
| 2026-10-29 15:08:32 | +7.4 | 0xaa6760c2: ask above max price |
| 2026-10-29 15:09:33 | +6.0 | 0xaa6760c2: ask above max price |
| 2026-10-29 15:10:43 | -6.0 | 0xaa6760c2: ends too soon |
| 2026-10-29 15:12:26 | +6.8 | 0xaa6760c2: ends too soon |
| 2026-10-29 15:14:47 | +6.5 | 0xaa6760c2: ends too soon |
| 2026-10-29 15:31:36 | +6.5 | 0xda496208: trade |
| 2026-10-29 15:32:45 | +6.0 | 0xda496208: trade |
| 2026-10-29 15:34:02 | +6.4 | 0xda496208: ask above max price |
| 2026-10-29 15:35:15 | +6.6 | 0xda496208: ask above max price |
| 2026-10-29 15:46:04 | +6.2 | 0x8b13af5c: trade |
| 2026-10-29 16:02:50 | -6.0 | 0x02709ec9: trade |
| 2026-10-29 16:07:58 | +6.1 | 0x02709ec9: trade |
| 2026-10-29 16:09:19 | +6.1 | 0x02709ec9: ask above max price |
| 2026-10-29 16:10:54 | +6.6 | 0x02709ec9: ends too soon |
| 2026-10-29 16:13:19 | -6.0 | 0x02709ec9: ends too soon |
| 2026-10-29 16:16:14 | -6.3 | 0x24cbbe99: trade |
| 2026-10-29 16:19:04 | -6.6 | 0x24cbbe99: ask above max price |
| 2026-10-29 16:21:12 | -6.2 | 0x24cbbe99: ask above max price |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-29 01:53:36 | 0x2a190bb5 | 15m | 0.03 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 02:01:03 | 0x7e034c1a | 15m | 0.54 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 02:05:30 | 0x7e034c1a | 15m | 0.67 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 02:06:34 | 0x7e034c1a | 15m | 0.83 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 02:08:24 | 0x7e034c1a | 15m | 0.24 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 02:16:20 | 0x134606a1 | 15m | 0.41 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 02:17:34 | 0x134606a1 | 15m | 0.62 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 02:18:38 | 0x134606a1 | 15m | 0.67 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 02:30:40 | 0x1515ae6a | 15m | 0.59 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 02:31:42 | 0x1515ae6a | 15m | 0.38 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 02:32:53 | 0x1515ae6a | 15m | 0.55 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 02:34:44 | 0x1515ae6a | 15m | 0.71 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 02:35:47 | 0x1515ae6a | 15m | 0.83 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 02:37:29 | 0x1515ae6a | 15m | 0.83 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 02:39:06 | 0x1515ae6a | 15m | 0.1 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 03:00:05 | 0xe05546ae | 15m | 0.61 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 03:04:23 | 0xe05546ae | 15m | 0.29 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 03:36:39 | 0xd28dc593 | 15m | 0.49 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 05:03:41 | 0x90d2f99a | 15m | 0.17 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 06:09:39 | 0xd68b546e | 15m | 0.85 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 07:46:56 | 0xc0feef13 | 15m | 0.67 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 08:03:58 | 0xd6bac83b | 15m | 0.76 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 09:21:31 | 0x2697d024 | 15m | 0.66 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 11:15:26 | 0x2bebb9c0 | 15m | 0.43 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 12:37:12 | 0xe22b0a20 | 15m | 0.2 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 13:18:05 | 0xe127c8dc | 15m | 0.64 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 13:30:47 | 0x6928fecd | 15m | 0.4 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 13:45:16 | 0x0de913f4 | 15m | 0.47 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 13:46:29 | 0x0de913f4 | 15m | 0.73 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 14:06:30 | 0xe63d8ae6 | 15m | 0.81 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 14:35:26 | 0x18a0d71b | 15m | 0.03 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 14:45:26 | 0x0c6452fc | 15m | 0.51 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 14:50:34 | 0x0c6452fc | 15m | 0.14 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 15:00:12 | 0xaa6760c2 | 15m | 0.43 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 15:31:36 | 0xda496208 | 15m | 0.59 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 15:32:45 | 0xda496208 | 15m | 0.81 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 15:46:04 | 0x8b13af5c | 15m | 0.64 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 16:02:50 | 0x02709ec9 | 15m | 0.76 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 16:07:58 | 0x02709ec9 | 15m | 0.84 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-29 16:16:14 | 0x24cbbe99 | 15m | 0.7 | approved | open | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 981, median 218, p90 273, min 185, max 613.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 295344, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 14.0, max 60.0.
- Binance event time to local receive (network + clock offset): n 295344, median of minute medians -77.5, worst minute p90 8314.0, worst minute p99 9559.4, max 9562.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 536367, median of minute medians 9.7, worst minute p90 12.1, worst minute p99 146.4, max 347.4.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 86, median -67, p90 50, min -288, max 230.
- Local receive to decision: n 86, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 86, median 368, p90 383, min 341, max 557.

## Risk, reconciliation, invariants and audit

- Trips: 3: global REDUCING (stale feed polymarket:crypto-fast: 61005 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 61005 ms, breaker:stale_feed); global ACTIVE (reset, human:DELL-feed).
- Human resets: 43; halts confirmed by zero open orders: 0.
- Reconciles: 196 (periodic 196); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 978 records, head af183f1a06758467; last head anchored in the ledger: 774 records, 98146af57cfcca98 (startup, 2026-10-28 18:21:55).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-mk-eth-bybit | 0 | 200 / 100 | 0.00 | no evidence yet |

Elapsed since the first run: 9.13 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethmk --date 2026-10-29 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethmk_2026-10-29.md --title "paper_ethmk day 10: 2026-10-29 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **10 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **3 of 3** (need 5+, all clean)
- Running time: 139.5 hours (5.81 days of 24 h)

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
| 2026-10-29 | 16.4 |
