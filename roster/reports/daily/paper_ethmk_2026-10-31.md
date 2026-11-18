# paper_ethmk day 12: 2026-10-31 (UTC)

Ledger `data/trader/paper_ethmk`, window 2026-10-31 00:00:00 to 2026-11-01 00:00:00 UTC (data from 2026-10-31 00:00:00 to 2026-10-31 16:21:24). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 3, approved 3, orders 3, paper fills 0, btc-speed events 7 and trades 3.
- Paper P&L to the end of the window: no fills yet.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 3 intents, 3 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | maker | 3 | 0 | 0 | - | 0.0000 |

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

7 causal ETH moves (>= 6.0 bp in 2 s) and 3 trades sent to the kernel. Per mapped market: trade 3, ask above max price 3, ends too soon 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-31 00:12:16 | +7.2 | 0x14fb9822: ends too soon |
| 2026-10-31 01:46:14 | +8.4 | 0xa432776f: trade |
| 2026-10-31 06:47:16 | +6.4 | 0xab75a79e: trade |
| 2026-10-31 07:31:38 | +6.2 | 0x9a81cf57: trade |
| 2026-10-31 08:33:31 | -6.4 | 0x25dafd9f: ask above max price |
| 2026-10-31 11:37:36 | +6.4 | 0x15d1464f: ask above max price |
| 2026-10-31 12:36:24 | +6.0 | 0xbf8941d8: ask above max price |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-31 01:46:14 | 0xa432776f | 15m | 0.54 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-31 06:47:16 | 0xab75a79e | 15m | 0.65 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-31 07:31:38 | 0x9a81cf57 | 15m | 0.49 | approved | open | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 912, median 215, p90 235, min 187, max 509.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 131884, median of minute medians 0.0, worst minute p90 1.4, worst minute p99 10.3, max 54.0.
- Binance event time to local receive (network + clock offset): n 131884, median of minute medians -85.0, worst minute p90 497.7, worst minute p99 2244.9, max 2792.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 497246, median of minute medians 9.8, worst minute p90 19.4, worst minute p99 5955358.0, max 4179023.8.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 7, median -69, p90 -15, min -265, max -20.
- Local receive to decision: n 7, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 7, median 362, p90 400, min 347, max 396.

## Risk, reconciliation, invariants and audit

- Trips: 4: global REDUCING (stale feed polymarket:crypto-fast: 4232131 ms, breaker:stale_feed); global REDUCING (stale feed binance:ETH: 4231997 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 4232131 ms, breaker:stale_feed); global ACTIVE (reset, human:DELL-feed).
- Human resets: 43; halts confirmed by zero open orders: 0.
- Reconciles: 183 (periodic 183); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 1256 records, head 2135cfd2b2521b09; last head anchored in the ledger: 774 records, 98146af57cfcca98 (startup, 2026-10-28 18:21:55).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-mk-eth-bybit | 0 | 200 / 100 | 0.00 | no evidence yet |

Elapsed since the first run: 11.13 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethmk --date 2026-10-31 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethmk_2026-10-31.md --title "paper_ethmk day 12: 2026-10-31 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **12 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **3 of 3** (need 5+, all clean)
- Running time: 170.8 hours (7.12 days of 24 h)

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
| 2026-10-31 | 15.2 |
