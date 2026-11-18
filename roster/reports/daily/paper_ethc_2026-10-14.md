# paper_ethc day 2: 2026-10-14 (UTC)

Ledger `data/trader/paper_ethc`, window 2026-10-14 00:00:00 to 2026-10-15 00:00:00 UTC (data from - to -). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 0, approved 0, orders 0, paper fills 0, btc-speed events 0 and trades 0.
- Paper P&L to the end of the window: btc-speed -7.79 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 7 | 30.29 | 0.00 | 0.4959 | 0.00 | 23.00 | 0 | 0.00 | -7.7879 |

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
- **btc-speed-v4-eth-bybit-c**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 7 in 7 markets (needs 200), unresolved 0, mean -1.1126 USD, cluster SE 1.1165, total -7.7879 USD. Verdict: **running (7 of 200)**.
- **Paper-fill realism** (btc-speed at real tape prices): 4 of 7 resolved trades repriced at what real takers paid in our order's second. Paper -3.47 USD -> best case -4.16 (cheapest real price), typical -5.16 (median real price), **live estimate -6.78** (median real price within our limit, else missed); real takers paid a median +7.5c over our fill. Paper assumes we win every race for the cheapest ask.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-13 06:31:25), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-13 06:31:25), `btc-speed-v4-eth-bybit-c` (sha256 cbb49bb7298f5753, written 2026-10-13 06:31:25).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

0 causal ETH moves (>= 6.0 bp in 2 s) and 0 trades sent to the kernel. Per mapped market: none.

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 0.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: no samples.
- Binance event time to local receive (network + clock offset): no samples.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): no samples.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 0.
- Local receive to decision: n 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 0.

## Risk, reconciliation, invariants and audit

- Trips: 0.
- Human resets: 0; halts confirmed by zero open orders: 0.
- Reconciles: 0 (); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 96 records, head b97fb88ae0be278e; last head anchored in the ledger: 0 records, None (startup, 2026-10-13 06:31:25).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit-c | 7 | 200 / 100 | 4.96 | 39 |

Elapsed since the first run: 1.41 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethc --date 2026-10-14 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethc_2026-10-14.md --title "paper_ethc day 2: 2026-10-14 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **2 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **0 of 0** (need 5+, all clean)
- Running time: 13.4 hours (0.56 days of 24 h)

| UTC day | Hours running |
|---|---|
| 2026-10-13 | 13.4 |
