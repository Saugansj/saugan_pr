# paper_ethmk day 18: 2026-11-06 (UTC)

Ledger `data/trader/paper_ethmk`, window 2026-11-06 00:00:00 to 2026-11-07 00:00:00 UTC (data from 2026-11-06 06:58:31 to 2026-11-06 16:25:14). Paper only: no order ever left this PC.

## Summary

- Runs started: 1; clean shutdowns: 0; still running or ended by a crash or kill: 1 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 54, approved 54, orders 54, paper fills 0, btc-speed events 85 and trades 54.
- Paper P&L to the end of the window: no fills yet.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 54 intents, 54 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | maker | 54 | 0 | 0 | - | 0.0000 |

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

85 causal ETH moves (>= 6.0 bp in 2 s) and 54 trades sent to the kernel. Per mapped market: trade 54, ends too soon 25, ask above max price 5.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-11-06 15:12:02 | +6.4 | 0x1a8d737a: ends too soon |
| 2026-11-06 15:13:08 | +7.1 | 0x1a8d737a: ends too soon |
| 2026-11-06 15:14:15 | +6.2 | 0x1a8d737a: ends too soon |
| 2026-11-06 15:17:02 | +6.3 | 0x2a6f106f: trade |
| 2026-11-06 15:18:03 | -7.9 | 0x2a6f106f: trade |
| 2026-11-06 15:19:47 | -6.3 | 0x2a6f106f: trade |
| 2026-11-06 15:20:49 | +6.0 | 0x2a6f106f: trade |
| 2026-11-06 15:22:06 | +6.7 | 0x2a6f106f: trade |
| 2026-11-06 15:23:55 | -6.2 | 0x2a6f106f: ask above max price |
| 2026-11-06 15:25:33 | +6.3 | 0x2a6f106f: ends too soon |
| 2026-11-06 15:27:43 | -6.1 | 0x2a6f106f: ends too soon |
| 2026-11-06 15:30:06 | -6.2 | 0xfc97bfc0: trade |
| 2026-11-06 15:31:17 | +6.5 | 0xfc97bfc0: trade |
| 2026-11-06 15:33:15 | -6.3 | 0xfc97bfc0: trade |
| 2026-11-06 15:34:28 | -7.3 | 0xfc97bfc0: trade |
| 2026-11-06 15:35:34 | -7.3 | 0xfc97bfc0: trade |
| 2026-11-06 15:38:21 | +6.5 | 0xfc97bfc0: trade |
| 2026-11-06 15:39:36 | +6.2 | 0xfc97bfc0: trade |
| 2026-11-06 15:42:10 | -6.2 | 0xfc97bfc0: ends too soon |
| 2026-11-06 15:43:17 | +6.2 | 0xfc97bfc0: ends too soon |
| 2026-11-06 15:46:53 | -6.2 | 0xb46e1612: trade |
| 2026-11-06 15:52:33 | -6.5 | 0xb46e1612: trade |
| 2026-11-06 16:00:02 | +6.3 | 0x8dc13e68: trade |
| 2026-11-06 16:02:00 | -6.8 | 0x8dc13e68: trade |
| 2026-11-06 16:05:01 | -6.5 | 0x8dc13e68: trade |
| 2026-11-06 16:08:17 | +6.2 | 0x8dc13e68: trade |
| 2026-11-06 16:10:35 | -6.0 | 0x8dc13e68: ends too soon |
| 2026-11-06 16:12:58 | -6.0 | 0x8dc13e68: ends too soon |
| 2026-11-06 16:14:14 | +6.2 | 0x8dc13e68: ends too soon |
| 2026-11-06 16:17:12 | -6.7 | 0x86050294: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-06 14:31:09 | 0x4bc582e2 | 15m | 0.46 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 14:32:33 | 0x4bc582e2 | 15m | 0.71 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 14:33:34 | 0x4bc582e2 | 15m | 0.25 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 14:34:35 | 0x4bc582e2 | 15m | 0.85 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 14:35:37 | 0x4bc582e2 | 15m | 0.16 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 14:37:12 | 0x4bc582e2 | 15m | 0.68 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 14:38:14 | 0x4bc582e2 | 15m | 0.8 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 14:39:18 | 0x4bc582e2 | 15m | 0.73 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 14:46:18 | 0xffc90d36 | 15m | 0.33 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 14:47:32 | 0xffc90d36 | 15m | 0.32 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 14:48:42 | 0xffc90d36 | 15m | 0.31 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 14:50:06 | 0xffc90d36 | 15m | 0.47 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 14:51:16 | 0xffc90d36 | 15m | 0.82 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 14:52:29 | 0xffc90d36 | 15m | 0.31 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:01:02 | 0x1a8d737a | 15m | 0.52 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:02:26 | 0x1a8d737a | 15m | 0.57 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:03:29 | 0x1a8d737a | 15m | 0.23 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:04:48 | 0x1a8d737a | 15m | 0.77 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:05:52 | 0x1a8d737a | 15m | 0.85 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:07:00 | 0x1a8d737a | 15m | 0.24 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:09:05 | 0x1a8d737a | 15m | 0.14 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:17:02 | 0x2a6f106f | 15m | 0.4 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:18:03 | 0x2a6f106f | 15m | 0.69 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:19:47 | 0x2a6f106f | 15m | 0.66 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:20:49 | 0x2a6f106f | 15m | 0.26 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:22:06 | 0x2a6f106f | 15m | 0.19 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:30:06 | 0xfc97bfc0 | 15m | 0.54 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:31:17 | 0xfc97bfc0 | 15m | 0.24 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:33:15 | 0xfc97bfc0 | 15m | 0.56 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:34:28 | 0xfc97bfc0 | 15m | 0.55 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:35:34 | 0xfc97bfc0 | 15m | 0.73 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:38:21 | 0xfc97bfc0 | 15m | 0.33 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:39:36 | 0xfc97bfc0 | 15m | 0.31 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:46:53 | 0xb46e1612 | 15m | 0.35 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:52:33 | 0xb46e1612 | 15m | 0.16 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 16:00:02 | 0x8dc13e68 | 15m | 0.48 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 16:02:00 | 0x8dc13e68 | 15m | 0.55 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 16:05:01 | 0x8dc13e68 | 15m | 0.49 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 16:08:17 | 0x8dc13e68 | 15m | 0.33 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-06 16:17:12 | 0x86050294 | 15m | 0.41 | approved | open | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 428, median 211, p90 431, min 184, max 675.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 243868, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 1.9, max 59.0.
- Binance event time to local receive (network + clock offset): n 243868, median of minute medians -806.5, worst minute p90 6439.7, worst minute p99 9316.6, max 9317.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 234243, median of minute medians 9.4, worst minute p90 50.5, worst minute p99 182644564.0, max 113443841.8.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 85, median -853, p90 -330, min -951, max 146.
- Local receive to decision: n 85, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 85, median 360, p90 387, min 336, max 611.

## Risk, reconciliation, invariants and audit

- Trips: 1: global ACTIVE (reset, human:DELL-feed).
- Human resets: 13; halts confirmed by zero open orders: 0.
- Reconciles: 88 (periodic 87, startup 1); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 2027 records, head 2d39bc9874179364; last head anchored in the ledger: 1864 records, 26135ad16d280914 (startup, 2026-11-06 09:29:51).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-mk-eth-bybit | 0 | 200 / 100 | 0.00 | no evidence yet |

Elapsed since the first run: 17.14 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethmk --date 2026-11-06 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethmk_2026-11-06.md --title "paper_ethmk day 18: 2026-11-06 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **MET.**

- Days without a violation: **18 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **5 of 5** (need 5+, all clean)
- Running time: 263.4 hours (10.98 days of 24 h)

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
| 2026-11-06 | 7.1 |
