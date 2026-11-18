# paper_ethmk day 15: 2026-11-03 (UTC)

Ledger `data/trader/paper_ethmk`, window 2026-11-03 00:00:00 to 2026-11-04 00:00:00 UTC (data from 2026-11-03 00:00:34 to 2026-11-03 16:49:19). Paper only: no order ever left this PC.

## Summary

- Runs started: 1; clean shutdowns: 0; still running or ended by a crash or kill: 1 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 18, approved 18, orders 18, paper fills 0, btc-speed events 39 and trades 18.
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

39 causal ETH moves (>= 6.0 bp in 2 s) and 18 trades sent to the kernel. Per mapped market: trade 18, ends too soon 12, ask above max price 8, move started before the window 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-11-03 13:28:52 | +6.1 | 0xd1e9799d: ends too soon |
| 2026-11-03 13:29:58 | -6.1 | 0xd1e9799d: ends too soon |
| 2026-11-03 13:31:03 | -6.2 | 0x70980e62: trade |
| 2026-11-03 13:32:07 | +6.0 | 0x70980e62: ask above max price |
| 2026-11-03 13:33:07 | +6.4 | 0x70980e62: ask above max price |
| 2026-11-03 13:34:14 | +7.6 | 0x70980e62: ask above max price |
| 2026-11-03 13:36:48 | +7.6 | 0x70980e62: trade |
| 2026-11-03 13:38:41 | -6.3 | 0x70980e62: trade |
| 2026-11-03 13:46:39 | -6.0 | 0x5c7f1d52: trade |
| 2026-11-03 13:53:53 | -6.6 | 0x5c7f1d52: ask above max price |
| 2026-11-03 13:59:17 | +6.8 | 0x5c7f1d52: ends too soon |
| 2026-11-03 14:01:44 | -6.2 | 0x0f02a27b: trade |
| 2026-11-03 14:02:52 | -6.1 | 0x0f02a27b: ask above max price |
| 2026-11-03 14:07:27 | +6.7 | 0x0f02a27b: trade |
| 2026-11-03 14:24:39 | -6.1 | 0x468222d4: trade |
| 2026-11-03 14:26:35 | +8.0 | 0x468222d4: ends too soon |
| 2026-11-03 14:30:07 | +6.2 | 0x099f48eb: trade |
| 2026-11-03 14:31:29 | -6.0 | 0x099f48eb: trade |
| 2026-11-03 14:32:59 | +6.4 | 0x099f48eb: trade |
| 2026-11-03 14:51:43 | +6.1 | 0x4e411179: trade |
| 2026-11-03 14:53:01 | +6.5 | 0x4e411179: trade |
| 2026-11-03 14:55:28 | +6.1 | 0x4e411179: ends too soon |
| 2026-11-03 15:00:01 | -6.4 | 0x422ba13e: move started before the window |
| 2026-11-03 15:09:22 | +7.8 | 0x422ba13e: trade |
| 2026-11-03 15:12:10 | +6.2 | 0x422ba13e: ends too soon |
| 2026-11-03 15:13:35 | -6.0 | 0x422ba13e: ends too soon |
| 2026-11-03 15:41:21 | +7.1 | 0xa2b9a6f7: ends too soon |
| 2026-11-03 15:46:59 | +6.0 | 0x4f2da75a: trade |
| 2026-11-03 15:53:32 | +6.5 | 0x4f2da75a: trade |
| 2026-11-03 16:21:25 | -6.1 | 0x0bbb6a49: ask above max price |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-03 12:16:10 | 0x4219f034 | 15m | 0.23 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-03 12:47:42 | 0x781efed8 | 15m | 0.57 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-03 13:17:19 | 0xd1e9799d | 15m | 0.68 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-03 13:31:03 | 0x70980e62 | 15m | 0.29 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-03 13:36:48 | 0x70980e62 | 15m | 0.75 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-03 13:38:41 | 0x70980e62 | 15m | 0.18 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-03 13:46:39 | 0x5c7f1d52 | 15m | 0.46 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-03 14:01:44 | 0x0f02a27b | 15m | 0.63 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-03 14:07:27 | 0x0f02a27b | 15m | 0.04 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-03 14:24:39 | 0x468222d4 | 15m | 0.04 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-03 14:30:07 | 0x099f48eb | 15m | 0.58 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-03 14:31:29 | 0x099f48eb | 15m | 0.38 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-03 14:32:59 | 0x099f48eb | 15m | 0.67 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-03 14:51:43 | 0x4e411179 | 15m | 0.54 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-03 14:53:01 | 0x4e411179 | 15m | 0.64 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-03 15:09:22 | 0x422ba13e | 15m | 0.5 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-03 15:46:59 | 0x4f2da75a | 15m | 0.71 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-03 15:53:32 | 0x4f2da75a | 15m | 0.69 | approved | open | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 440, median 217, p90 409, min 189, max 516.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 175234, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 5.5, max 54.0.
- Binance event time to local receive (network + clock offset): n 175234, median of minute medians -23.0, worst minute p90 482.9, worst minute p99 2213.6, max 2282.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 238127, median of minute medians 13.0, worst minute p90 20.9, worst minute p99 81.4, max 324.1.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 39, median 29, p90 239, min -106, max 324.
- Local receive to decision: n 39, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 39, median 361, p90 382, min 347, max 385.

## Risk, reconciliation, invariants and audit

- Trips: 0.
- Human resets: 0; halts confirmed by zero open orders: 0.
- Reconciles: 89 (periodic 88, startup 1); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 1553 records, head 3bdd9b10dd7782b1; last head anchored in the ledger: 1498 records, bcae86ac12c7e3da (startup, 2026-11-03 11:56:02).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-mk-eth-bybit | 0 | 200 / 100 | 0.00 | no evidence yet |

Elapsed since the first run: 14.15 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethmk --date 2026-11-03 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethmk_2026-11-03.md --title "paper_ethmk day 15: 2026-11-03 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **15 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **4 of 4** (need 5+, all clean)
- Running time: 229.8 hours (9.57 days of 24 h)

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
| 2026-11-03 | 7.3 |
