# paper_ethb day 39: 2026-11-18 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-11-18 00:00:00 to 2026-11-19 00:00:00 UTC (data from - to -). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 0, approved 0, orders 0, paper fills 0, btc-speed events 0 and trades 0.
- Paper P&L to the end of the window: btc-speed +225.63 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 656 | 1538.54 | 0.00 | 43.1017 | 0.00 | 1803.50 | 10 | 3.77 | +225.6285 |

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
- **btc-speed-v4-eth-bybit**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 650 in 650 markets (needs 200), unresolved 0, mean 0.3490 USD, cluster SE 0.0843, total +226.8560 USD. Verdict: **PASS**.
- **Paper-fill realism** (btc-speed at real tape prices): 548 of 650 resolved trades repriced at what real takers paid in our order's second. Paper +222.04 USD -> best case +118.37 (cheapest real price), typical +23.98 (median real price), **live estimate +48.09** (our order behind the real takers that beat us, partial fills; 68% of our shares filled); real takers paid a median +5.0c over our fill. Paper assumes we win every race for the cheapest ask. Not comparable with reports before 15 Oct.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-11 19:34:32), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-11 19:34:32), `btc-speed-v4-eth-bybit` (sha256 04680de003a175aa, written 2026-10-11 19:34:32).

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
- Audit chain verifies: 3857 records, head c29f15605f57beeb; last head anchored in the ledger: 3819 records, cfd2f02bb73df9d2 (startup, 2026-11-12 07:29:03).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 650 | 200 / 100 | 17.17 | 0 |

Elapsed since the first run: 37.87 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-11-18 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-11-18.md --title "paper_ethb day 39: 2026-11-18 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **MET.**

- Days without a violation: **39 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **16 of 16** (need 5+, all clean)
- Running time: 364.6 hours (15.19 days of 24 h)

| UTC day | Hours running |
|---|---|
| 2026-10-11 | 1.1 |
| 2026-10-12 | 15.4 |
| 2026-10-13 | 16.7 |
| 2026-10-14 | 16.0 |
| 2026-10-15 | 12.8 |
| 2026-10-16 | 13.3 |
| 2026-10-20 | 12.4 |
| 2026-10-21 | 17.6 |
| 2026-10-22 | 16.0 |
| 2026-10-23 | 16.3 |
| 2026-10-24 | 6.7 |
| 2026-10-25 | 17.2 |
| 2026-10-26 | 18.1 |
| 2026-10-27 | 18.4 |
| 2026-10-28 | 5.4 |
| 2026-10-29 | 19.6 |
| 2026-10-30 | 12.8 |
| 2026-10-31 | 22.8 |
| 2026-11-01 | 24.0 |
| 2026-11-02 | 20.1 |
| 2026-11-03 | 14.5 |
| 2026-11-04 | 19.4 |
| 2026-11-06 | 11.0 |
| 2026-11-07 | 3.2 |
| 2026-11-10 | 6.2 |
| 2026-11-11 | 4.4 |
| 2026-11-12 | 3.3 |
