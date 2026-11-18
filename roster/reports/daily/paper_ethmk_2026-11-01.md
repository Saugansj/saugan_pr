# paper_ethmk day 13: 2026-11-01 (UTC)

Ledger `data/trader/paper_ethmk`, window 2026-11-01 00:00:00 to 2026-11-02 00:00:00 UTC (data from 2026-11-01 00:00:50 to 2026-11-01 16:21:43). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 10, approved 10, orders 10, paper fills 0, btc-speed events 15 and trades 10.
- Paper P&L to the end of the window: no fills yet.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 10 intents, 10 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | maker | 10 | 0 | 0 | - | 0.0000 |

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

15 causal ETH moves (>= 6.0 bp in 2 s) and 10 trades sent to the kernel. Per mapped market: trade 10, ask above max price 4, ends too soon 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-11-01 01:23:51 | +6.0 | 0xf9f9dcdb: ask above max price |
| 2026-11-01 01:35:24 | +6.3 | 0xc2cb0ea3: ask above max price |
| 2026-11-01 02:02:35 | +6.4 | 0x5b2a2551: trade |
| 2026-11-01 02:03:53 | +6.5 | 0x5b2a2551: trade |
| 2026-11-01 02:50:15 | -6.7 | 0x63cdf1df: trade |
| 2026-11-01 03:53:12 | +6.2 | 0xf815f1f1: trade |
| 2026-11-01 08:35:02 | +6.1 | 0x91703414: ask above max price |
| 2026-11-01 08:49:29 | +6.4 | 0xb3b991f5: trade |
| 2026-11-01 08:58:37 | +6.4 | 0xb3b991f5: ends too soon |
| 2026-11-01 12:09:30 | -6.8 | 0x081062be: ask above max price |
| 2026-11-01 12:15:19 | -6.3 | 0xbbf97640: trade |
| 2026-11-01 12:17:41 | +6.2 | 0xbbf97640: trade |
| 2026-11-01 13:36:58 | -6.5 | 0x297c9626: trade |
| 2026-11-01 14:07:44 | +6.1 | 0xb0c3a88a: trade |
| 2026-11-01 14:18:22 | +6.5 | 0xabe6859a: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-01 02:02:35 | 0x5b2a2551 | 15m | 0.64 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-01 02:03:53 | 0x5b2a2551 | 15m | 0.85 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-01 02:50:15 | 0x63cdf1df | 15m | 0.13 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-01 03:53:12 | 0xf815f1f1 | 15m | 0.04 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-01 08:49:29 | 0xb3b991f5 | 15m | 0.8 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-01 12:15:19 | 0xbbf97640 | 15m | 0.58 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-01 12:17:41 | 0xbbf97640 | 15m | 0.07 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-01 13:36:58 | 0x297c9626 | 15m | 0.18 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-01 14:07:44 | 0xb0c3a88a | 15m | 0.57 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-01 14:18:22 | 0xabe6859a | 15m | 0.45 | approved | open | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 982, median 210, p90 231, min 190, max 700.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 109512, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 46.6, max 67.0.
- Binance event time to local receive (network + clock offset): n 109512, median of minute medians -19.0, worst minute p90 1193.6, worst minute p99 1201.5, max 1915.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 535489, median of minute medians 9.8, worst minute p90 12.0, worst minute p99 138.5, max 340.0.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 15, median 56, p90 241, min -109, max 354.
- Local receive to decision: n 15, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 15, median 356, p90 566, min 347, max 850.

## Risk, reconciliation, invariants and audit

- Trips: 3: global REDUCING (stale feed polymarket:crypto-fast: 60064 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 60064 ms, breaker:stale_feed); global ACTIVE (reset, human:DELL-feed).
- Human resets: 67; halts confirmed by zero open orders: 0.
- Reconciles: 196 (periodic 196); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 1295 records, head f35a355d27d64848; last head anchored in the ledger: 774 records, 98146af57cfcca98 (startup, 2026-10-28 18:21:55).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-mk-eth-bybit | 0 | 200 / 100 | 0.00 | no evidence yet |

Elapsed since the first run: 12.13 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethmk --date 2026-11-01 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethmk_2026-11-01.md --title "paper_ethmk day 13: 2026-11-01 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **13 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **3 of 3** (need 5+, all clean)
- Running time: 194.8 hours (8.12 days of 24 h)

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
| 2026-11-01 | 16.4 |
