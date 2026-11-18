# paper_ethmk day 8: 2026-10-27 (UTC)

Ledger `data/trader/paper_ethmk`, window 2026-10-27 00:00:00 to 2026-10-28 00:00:00 UTC (data from 2026-10-27 00:00:51 to 2026-10-27 16:20:43). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 18, approved 18, orders 18, paper fills 0, btc-speed events 42 and trades 18.
- Paper P&L to the end of the window: no fills yet.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 18 intents, 18 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | maker | 18 | 0 | 0 | - | 0.0000 |

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

42 causal ETH moves (>= 6.0 bp in 2 s) and 18 trades sent to the kernel. Per mapped market: trade 18, ends too soon 12, ask above max price 9, no ask 2, stale signal 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-27 10:14:39 | -7.0 | 0x7fe43f63: ends too soon |
| 2026-10-27 10:37:01 | +6.0 | 0xb82e4d25: trade |
| 2026-10-27 10:39:43 | +6.2 | 0xb82e4d25: no ask |
| 2026-10-27 10:45:29 | -6.6 | 0x58120499: trade |
| 2026-10-27 10:46:39 | -6.4 | 0x58120499: trade |
| 2026-10-27 10:59:08 | -6.3 | 0x58120499: ends too soon |
| 2026-10-27 12:15:33 | -8.5 | 0xc6bf4ad0: trade |
| 2026-10-27 12:26:03 | +6.1 | 0xc6bf4ad0: ends too soon |
| 2026-10-27 12:39:21 | +6.9 | 0xff924010: ask above max price |
| 2026-10-27 12:48:43 | +6.2 | 0xd12c3475: trade |
| 2026-10-27 12:55:20 | +6.0 | 0xd12c3475: ends too soon |
| 2026-10-27 13:31:23 | -6.2 | 0xcc4ade4b: trade |
| 2026-10-27 13:32:57 | -6.6 | 0xcc4ade4b: trade |
| 2026-10-27 13:36:05 | -6.3 | 0xcc4ade4b: trade |
| 2026-10-27 13:52:39 | -6.4 | 0xacd943eb: ask above max price |
| 2026-10-27 14:13:07 | +6.2 | 0xf083fdae: ends too soon |
| 2026-10-27 14:31:12 | -6.3 | 0x851a0db4: trade |
| 2026-10-27 15:00:19 | +6.0 | 0xd873071f: trade |
| 2026-10-27 15:12:06 | +7.2 | 0xd873071f: ends too soon |
| 2026-10-27 15:20:40 | +6.6 | 0xd0aa0f45: ask above max price |
| 2026-10-27 15:21:45 | +7.3 | 0xd0aa0f45: no ask |
| 2026-10-27 15:23:26 | +6.8 | 0xd0aa0f45: ask above max price |
| 2026-10-27 15:24:39 | -6.1 | 0xd0aa0f45: trade |
| 2026-10-27 15:26:12 | +6.4 | 0xd0aa0f45: ends too soon |
| 2026-10-27 15:30:26 | -6.4 | 0x785055ae: trade |
| 2026-10-27 15:35:02 | -6.8 | 0x785055ae: ask above max price |
| 2026-10-27 15:46:18 | +6.2 | 0xb57b97a7: trade |
| 2026-10-27 15:49:05 | +6.2 | 0xb57b97a7: trade |
| 2026-10-27 15:51:40 | +6.3 | 0xb57b97a7: stale signal |
| 2026-10-27 16:06:44 | -6.1 | 0xc11a3290: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-27 00:03:47 | 0x7a729502 | 15m | 0.42 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-27 05:30:12 | 0xc2f54038 | 15m | 0.69 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-27 07:47:38 | 0x9b724a95 | 15m | 0.55 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-27 10:37:01 | 0xb82e4d25 | 15m | 0.58 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-27 10:45:29 | 0x58120499 | 15m | 0.21 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-27 10:46:39 | 0x58120499 | 15m | 0.11 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-27 12:15:33 | 0xc6bf4ad0 | 15m | 0.25 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-27 12:48:43 | 0xd12c3475 | 15m | 0.81 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-27 13:31:23 | 0xcc4ade4b | 15m | 0.28 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-27 13:32:57 | 0xcc4ade4b | 15m | 0.69 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-27 13:36:05 | 0xcc4ade4b | 15m | 0.22 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-27 14:31:12 | 0x851a0db4 | 15m | 0.26 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-27 15:00:19 | 0xd873071f | 15m | 0.52 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-27 15:24:39 | 0xd0aa0f45 | 15m | 0.004 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-27 15:30:26 | 0x785055ae | 15m | 0.59 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-27 15:46:18 | 0xb57b97a7 | 15m | 0.68 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-27 15:49:05 | 0xb57b97a7 | 15m | 0.54 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-27 16:06:44 | 0xc11a3290 | 15m | 0.68 | approved | open | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 982, median 222, p90 250, min 184, max 708.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 279054, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 9.1, max 59.0.
- Binance event time to local receive (network + clock offset): n 279054, median of minute medians 9.0, worst minute p90 2544.3, worst minute p99 2588.0, max 2818.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 536056, median of minute medians 9.7, worst minute p90 19.7, worst minute p99 173.8, max 458.3.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 42, median 36, p90 186, min -75, max 1366.
- Local receive to decision: n 42, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 42, median 374, p90 424, min 355, max 488.

## Risk, reconciliation, invariants and audit

- Trips: 0.
- Human resets: 0; halts confirmed by zero open orders: 0.
- Reconciles: 196 (periodic 196); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 771 records, head e0c52021b27c8642; last head anchored in the ledger: 472 records, 5bc1e03d3b2abafd (startup, 2026-10-24 17:18:49).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-mk-eth-bybit | 0 | 200 / 100 | 0.00 | no evidence yet |

Elapsed since the first run: 7.13 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethmk --date 2026-10-27 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethmk_2026-10-27.md --title "paper_ethmk day 8: 2026-10-27 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **8 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **2 of 2** (need 5+, all clean)
- Running time: 115.6 hours (4.82 days of 24 h)

| UTC day | Hours running |
|---|---|
| 2026-10-20 | 7.5 |
| 2026-10-21 | 17.6 |
| 2026-10-22 | 15.9 |
| 2026-10-23 | 16.3 |
| 2026-10-24 | 6.7 |
| 2026-10-25 | 17.2 |
| 2026-10-26 | 18.1 |
| 2026-10-27 | 16.4 |
