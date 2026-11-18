# paper_ethb day 1: 2026-10-11 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-10-11 00:00:00 to 2026-10-12 00:00:00 UTC (data from 2026-10-11 19:34:32 to 2026-10-11 19:40:32). Paper only: no order ever left this PC.

## Summary

- Runs started: 1; clean shutdowns: 0; still running or ended by a crash or kill: 1 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 0, approved 0, orders 0, paper fills 0, btc-speed events 0 and trades 0.
- Paper P&L to the end of the window: no fills yet.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 0 intents, 0 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|

Merges of YES+NO pairs: 0; paper redemptions: 0.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| - | - | 0 | - | - | - |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-v4-eth-bybit**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 0 in 0 markets (needs 200), unresolved 0, mean - USD, cluster SE -, total +0.0000 USD. Verdict: **running (0 of 200)**.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-11 19:34:32), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-11 19:34:32), `btc-speed-v4-eth-bybit` (sha256 04680de003a175aa, written 2026-10-11 19:34:32).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

0 causal ETH moves (>= 6.0 bp in 2 s) and 0 trades sent to the kernel. Per mapped market: none.

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 7, median 251, p90 320, min 210, max 313.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 385, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 1.0, max 1.0.
- Binance event time to local receive (network + clock offset): n 385, median of minute medians -9.8, worst minute p90 499.4, worst minute p99 1431.8, max 1399.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 3375, median of minute medians 7.0, worst minute p90 196.9, worst minute p99 196.9, max 237.2.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 0.
- Local receive to decision: n 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 0.

## Risk, reconciliation, invariants and audit

- Trips: 0.
- Human resets: 0; halts confirmed by zero open orders: 0.
- Reconciles: 3 (startup 1, periodic 2); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 1 records, head 89929b71006538c3; last head anchored in the ledger: 0 records, None (startup, 2026-10-11 19:34:32).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 0 | 200 / 100 | 0.00 | no evidence yet |

Elapsed since the first run: 0.04 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-10-11 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-10-11.md --title "paper_ethb day 1: 2026-10-11 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **1 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **0 of 0** (need 5+, all clean)
- Running time: 0.1 hours (0.00 days of 24 h)

| UTC day | Hours running |
|---|---|
| 2026-10-11 | 0.1 |
