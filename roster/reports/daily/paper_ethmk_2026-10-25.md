# paper_ethmk day 6: 2026-10-25 (UTC)

Ledger `data/trader/paper_ethmk`, window 2026-10-25 00:00:00 to 2026-10-26 00:00:00 UTC (data from 2026-10-25 00:00:09 to 2026-10-25 16:20:52). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 7, approved 7, orders 7, paper fills 0, btc-speed events 16 and trades 7.
- Paper P&L to the end of the window: no fills yet.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 7 intents, 7 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | maker | 7 | 0 | 0 | - | 0.0000 |

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

16 causal ETH moves (>= 6.0 bp in 2 s) and 7 trades sent to the kernel. Per mapped market: trade 7, ends too soon 5, ask above max price 4.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-25 01:47:33 | +6.0 | 0x221b369c: trade |
| 2026-10-25 02:13:39 | +7.1 | 0x1f9d953a: ends too soon |
| 2026-10-25 06:50:59 | -6.0 | 0x73a2fae2: trade |
| 2026-10-25 06:52:30 | -6.0 | 0x73a2fae2: ask above max price |
| 2026-10-25 08:28:38 | -6.2 | 0x4f1af8a7: ends too soon |
| 2026-10-25 09:12:43 | -6.1 | 0x926dca70: ends too soon |
| 2026-10-25 09:17:28 | -8.3 | 0x030d780b: trade |
| 2026-10-25 09:18:43 | -6.3 | 0x030d780b: ask above max price |
| 2026-10-25 09:21:10 | -6.1 | 0x030d780b: trade |
| 2026-10-25 11:00:35 | +6.3 | 0x4d8dd282: ask above max price |
| 2026-10-25 11:44:52 | +6.4 | 0x1d21ca8f: ends too soon |
| 2026-10-25 11:46:02 | +6.3 | 0xf7cf2a45: trade |
| 2026-10-25 13:33:28 | -6.2 | 0x68f88a41: trade |
| 2026-10-25 13:40:40 | +6.1 | 0x68f88a41: ends too soon |
| 2026-10-25 15:00:37 | +6.2 | 0x24305063: trade |
| 2026-10-25 15:35:42 | +7.0 | 0x5177f34d: ask above max price |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-25 01:47:33 | 0x221b369c | 15m | 0.84 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-25 06:50:59 | 0x73a2fae2 | 15m | 0.8 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-25 09:17:28 | 0x030d780b | 15m | 0.57 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-25 09:21:10 | 0x030d780b | 15m | 0.75 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-25 11:46:02 | 0xf7cf2a45 | 15m | 0.74 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-25 13:33:28 | 0x68f88a41 | 15m | 0.66 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-25 15:00:37 | 0x24305063 | 15m | 0.63 | approved | open | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 871, median 219, p90 237, min 189, max 553.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 121042, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 5.5, max 138.0.
- Binance event time to local receive (network + clock offset): n 121042, median of minute medians -142.0, worst minute p90 6625006.0, worst minute p99 6692719.2, max 6700885.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 474748, median of minute medians 9.7, worst minute p90 12.8, worst minute p99 4892149.9, max 6701564.7.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 16, median -161, p90 72, min -280, max 76.
- Local receive to decision: n 16, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 16, median 370, p90 378, min 355, max 379.

## Risk, reconciliation, invariants and audit

- Trips: 4: global REDUCING (stale feed polymarket:crypto-fast: 6701880 ms, breaker:stale_feed); global REDUCING (stale feed binance:ETH: 6702676 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 6701880 ms, breaker:stale_feed); global ACTIVE (reset, human:DELL-feed).
- Human resets: 49; halts confirmed by zero open orders: 0.
- Reconciles: 174 (periodic 174); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 533 records, head 363bba1158669008; last head anchored in the ledger: 472 records, 5bc1e03d3b2abafd (startup, 2026-10-24 17:18:49).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-mk-eth-bybit | 0 | 200 / 100 | 0.00 | no evidence yet |

Elapsed since the first run: 5.13 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethmk --date 2026-10-25 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethmk_2026-10-25.md --title "paper_ethmk day 6: 2026-10-25 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **6 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **2 of 2** (need 5+, all clean)
- Running time: 78.5 hours (3.27 days of 24 h)

| UTC day | Hours running |
|---|---|
| 2026-10-20 | 7.5 |
| 2026-10-21 | 17.6 |
| 2026-10-22 | 15.9 |
| 2026-10-23 | 16.3 |
| 2026-10-24 | 6.7 |
| 2026-10-25 | 14.5 |
