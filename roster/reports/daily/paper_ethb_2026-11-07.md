# paper_ethb day 28: 2026-11-07 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-11-07 00:00:00 to 2026-11-08 00:00:00 UTC (data from 2026-11-07 14:24:26 to 2026-11-07 16:21:33). Paper only: no order ever left this PC.

## Summary

- Runs started: 1; clean shutdowns: 0; still running or ended by a crash or kill: 1 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 2, approved 0, orders 0, paper fills 0, btc-speed events 2 and trades 2.
- Paper P&L to the end of the window: btc-speed +190.50 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 620 | 1462.25 | 0.00 | 40.7457 | 0.00 | 1693.50 | 0 | 0.00 | +190.5026 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 2 intents, 0 approved, 2 rejected: REDUCING 2.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

Latest distinct rejections:

| Time UTC | Strategy | Reason | Binding cap |
|---|---|---|---|
| 2026-11-07 15:45:29 | btc-speed | REDUCING: only exposure-reducing orders | - |

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
- **btc-speed-v4-eth-bybit**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 615 in 615 markets (needs 200), unresolved 0, mean 0.3098 USD, cluster SE 0.0864, total +190.5026 USD. Verdict: **PASS**.
- **Paper-fill realism** (btc-speed at real tape prices): 521 of 615 resolved trades repriced at what real takers paid in our order's second. Paper +192.75 USD -> best case +92.47 (cheapest real price), typical +0.38 (median real price), **live estimate +22.51** (our order behind the real takers that beat us, partial fills; 67% of our shares filled); real takers paid a median +5.0c over our fill. Paper assumes we win every race for the cheapest ask. Not comparable with reports before 15 Oct.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-11 19:34:32), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-11 19:34:32), `btc-speed-v4-eth-bybit` (sha256 04680de003a175aa, written 2026-10-11 19:34:32).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

2 causal ETH moves (>= 6.0 bp in 2 s) and 2 trades sent to the kernel. Per mapped market: trade 2, ask above max price 2.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-11-07 15:45:29 | -6.7 | 0xbb253f0d: trade; 0xc6de4447: trade |
| 2026-11-07 15:46:30 | -6.9 | 0xbb253f0d: ask above max price; 0xc6de4447: ask above max price |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-07 15:45:29 | 0xbb253f0d | 5m | 0.82 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-07 15:45:29 | 0xc6de4447 | 15m | 0.73 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 118, median 216, p90 450, min 191, max 500.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 15146, median of minute medians 0.0, worst minute p90 2.0, worst minute p99 10.9, max 35.0.
- Binance event time to local receive (network + clock offset): n 15146, median of minute medians -84.0, worst minute p90 1342.3, worst minute p99 2466.5, max 2468.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 63861, median of minute medians 9.5, worst minute p90 87.5, worst minute p99 87.5, max 487.4.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 2, median -102, p90 -92, min -107, max -98.
- Local receive to decision: n 2, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 2, median 360, p90 373, min 354, max 365.

## Risk, reconciliation, invariants and audit

- Trips: 3: global REDUCING (restart: stale feed polymarket: 524164 ms, loop:restart); btc-speed REDUCING (restart: restart: strategy daily loss 5.04 USD > 5.00 (start of day 19, loop:restart); global ACTIVE (reset, human:DELL-feed).
- Human resets: 324; halts confirmed by zero open orders: 0.
- Reconciles: 25 (startup 1, periodic 24); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 3652 records, head b3aa58660ee55267; last head anchored in the ledger: 3646 records, eac18174d55db0dc (startup, 2026-11-07 14:24:26).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 615 | 200 / 100 | 22.89 | 0 |

Elapsed since the first run: 26.87 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-11-07 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-11-07.md --title "paper_ethb day 28: 2026-11-07 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **MET.**

- Days without a violation: **28 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **14 of 14** (need 5+, all clean)
- Running time: 349.5 hours (14.56 days of 24 h)

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
| 2026-11-07 | 2.0 |
