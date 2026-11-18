# Phase 1 daily paper report 2026-10-07

Ledger `data/trader/smoke_v2`, window 2026-10-07 00:00:00 to 2026-10-08 00:00:00 UTC (data from 2026-10-07 06:13:53 to 2026-10-07 07:13:53). Paper only: no order ever left this PC.

## Summary

- Runs started: 1; clean shutdowns: 1; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 39699, approved 372, orders 372, paper fills 1, btc-speed events 0 and trades 0.
- Paper P&L to the end of the window: ladder-maker -0.19 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| ladder-maker | 1 | 2.80 | 0.00 | 0.0000 | 0.00 | 0.00 | 10 | 2.61 | -0.1900 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 39699 intents, 372 approved, 39327 rejected: over group 39327.
  Also: cancel:ladder-maker 362.
- **btc-speed**: 0 intents, 0 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

Latest distinct rejections:

| Time UTC | Strategy | Reason | Binding cap |
|---|---|---|---|
| 2026-10-07 07:13:42 | ladder-maker | over group:BTC@2026-10-07T16:00Z: needs 9.85, room 0.14 | group:BTC@2026-10-07T16:00Z |

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| ladder-maker | maker | 372 | 1 | 10 | 0.2800 | 0.0000 |

Merges of YES+NO pairs: 0; paper redemptions: 0.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| ladder-maker | 5 s | 1 | +0.15c | - | 0 |
| ladder-maker | 60 s | 1 | +1.00c | - | 0 |
| ladder-maker | 300 s | 1 | -2.15c | - | 0 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v1**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 1 (needs 60), mean -0.1868 USD, SE -, fills still without a 5 m markout 0. Verdict: **running (1 of 60)**.
- **btc-speed-v1**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 0 in 0 markets (needs 200), unresolved 0, mean - USD, cluster SE -, total +0.0000 USD. Verdict: **running (0 of 200)**.
- Pre-registrations in the ledger (immutable): `ladder-maker-v1` (sha256 faacb13c96a3180f, written 2026-10-07 06:13:53), `btc-speed-v1` (sha256 88942b658a24774b, written 2026-10-07 06:13:53).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

0 causal BTC moves (>= 10.0 bp in 5 s) and 0 trades sent to the kernel. Per mapped market: none.

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 60, median 236, p90 289, min 214, max 389.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 385036, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 25.2, max 326.0.
- Binance event time to local receive (network + clock offset): n 385036, median of minute medians -33.5, worst minute p90 76.0, worst minute p99 493.0, max 774.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 34540, median of minute medians 2.3, worst minute p90 167.6, worst minute p99 167.6, max 276.7.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 0.
- Local receive to decision: n 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 0.

## Risk, reconciliation, invariants and audit

- Trips: 0.
- Human resets: 0; halts confirmed by zero open orders: 0.
- Reconciles: 14 (startup 1, periodic 12, shutdown 1); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 1812 records, head 9c017955bdd8d97e; last head anchored in the ledger: 1812 records, 9c017955bdd8d97e (shutdown, 2026-10-07 07:13:53).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v1 | 1 | 60 / 30 | 23.33 | 59 |
| btc-speed-v1 | 0 | 200 / 100 | 0.00 | no evidence yet |

Elapsed since the first run: 0.04 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## Notes

- Built on the 60-minute smoke run's ledger (the only paper run on 2026-10-07 in data/trader/smoke_v2); the nightly job for the 14-day run is the same command with --dir data/trader.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m trader.loop --paper --minutes 60 --dir data/trader/smoke_v2
.venv\Scripts\python.exe -m nightly.report --dir data/trader/smoke_v2 --date 2026-10-07
```
