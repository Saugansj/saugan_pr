# paper_ethb day 32: 2026-11-11 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-11-11 00:00:00 to 2026-11-12 00:00:00 UTC (data from 2026-11-11 14:41:31 to 2026-11-11 16:21:02). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 19, approved 19, orders 19, paper fills 19, btc-speed events 31 and trades 19.
- Paper P&L to the end of the window: btc-speed +204.34 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 639 | 1502.35 | 0.00 | 42.0368 | 0.00 | 1738.50 | 15 | 10.22 | +204.3415 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 19 intents, 19 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | taker | 19 | 19 | 95 | 0.4221 | 1.2912 |

Merges of YES+NO pairs: 0; paper redemptions: 16.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| btc-speed | 5 s | 19 | +5.56c | +1.83c | 0 |
| btc-speed | 60 s | 16 | +5.42c | +5.66c | 3 |
| btc-speed | 300 s | 6 | +5.82c | +9.95c | 12 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-v4-eth-bybit**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 631 in 631 markets (needs 200), unresolved 3, mean 0.3197 USD, cluster SE 0.0854, total +201.7233 USD. Verdict: **PASS**.
- **Paper-fill realism** (btc-speed at real tape prices): 532 of 631 resolved trades repriced at what real takers paid in our order's second. Paper +202.88 USD -> best case +102.05 (cheapest real price), typical +9.25 (median real price), **live estimate +32.57** (our order behind the real takers that beat us, partial fills; 67% of our shares filled); real takers paid a median +5.0c over our fill. Paper assumes we win every race for the cheapest ask. Not comparable with reports before 15 Oct.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-11 19:34:32), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-11 19:34:32), `btc-speed-v4-eth-bybit` (sha256 04680de003a175aa, written 2026-10-11 19:34:32).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

31 causal ETH moves (>= 6.0 bp in 2 s) and 19 trades sent to the kernel. Per mapped market: already holding this market 28, trade 19, ask above max price 6, ends too soon 3.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-11-11 14:46:42 | +6.0 | - |
| 2026-11-11 14:48:02 | +6.6 | - |
| 2026-11-11 14:51:28 | -6.1 | 0xa226594e: trade; 0xcc42b292: trade |
| 2026-11-11 14:54:43 | +6.2 | 0xa226594e: already holding this market; 0xcc42b292: already holding this market |
| 2026-11-11 14:56:04 | +6.0 | 0x023fc8ae: trade; 0xa226594e: already holding this market |
| 2026-11-11 14:59:35 | +6.4 | 0x023fc8ae: already holding this market; 0xa226594e: already holding this market |
| 2026-11-11 15:00:46 | +6.3 | 0x455379c5: trade; 0xb111b5f7: trade |
| 2026-11-11 15:09:14 | -6.2 | 0x319f1dad: ends too soon; 0xb111b5f7: already holding this market |
| 2026-11-11 15:12:03 | +6.0 | 0xb111b5f7: already holding this market; 0xc1010376: ask above max price |
| 2026-11-11 15:14:19 | +6.3 | 0xb111b5f7: already holding this market; 0xc1010376: ends too soon |
| 2026-11-11 15:21:38 | -6.3 | 0x2a342bf9: ask above max price; 0x93922000: ask above max price |
| 2026-11-11 15:25:02 | +6.2 | 0x2f88abff: trade; 0x93922000: trade |
| 2026-11-11 15:32:26 | +6.9 | 0x104a1436: trade; 0xb67e65cf: trade |
| 2026-11-11 15:33:46 | +7.5 | 0x104a1436: already holding this market; 0xb67e65cf: already holding this market |
| 2026-11-11 15:34:48 | +6.1 | 0x104a1436: already holding this market; 0xb67e65cf: already holding this market |
| 2026-11-11 15:35:49 | +8.9 | 0x104a1436: already holding this market; 0xfc5ab9fc: ask above max price |
| 2026-11-11 15:37:01 | -6.2 | 0x104a1436: already holding this market; 0xfc5ab9fc: trade |
| 2026-11-11 15:38:14 | -6.2 | 0x104a1436: already holding this market; 0xfc5ab9fc: already holding this market |
| 2026-11-11 15:44:58 | -6.0 | 0x0c83458f: ends too soon; 0x104a1436: already holding this market |
| 2026-11-11 15:48:33 | +6.8 | 0x464a2e7a: trade; 0x5b0aab0c: trade |
| 2026-11-11 15:51:31 | -7.4 | 0x464a2e7a: already holding this market; 0xfb9d941f: trade |
| 2026-11-11 15:52:39 | -6.1 | 0x464a2e7a: already holding this market; 0xfb9d941f: already holding this market |
| 2026-11-11 15:57:10 | -6.7 | 0x464a2e7a: already holding this market; 0xe29915ad: ask above max price |
| 2026-11-11 16:02:15 | +6.8 | 0xb365fb6b: trade; 0xd7b166b8: trade |
| 2026-11-11 16:07:28 | +6.5 | 0x55eda706: trade; 0xd7b166b8: already holding this market |
| 2026-11-11 16:09:22 | +6.1 | 0x55eda706: already holding this market; 0xd7b166b8: already holding this market |
| 2026-11-11 16:12:16 | +6.0 | 0xd7b166b8: already holding this market; 0xe6bc9e7f: ask above max price |
| 2026-11-11 16:16:02 | -6.9 | 0xb58f5778: trade; 0xe29d38a8: trade |
| 2026-11-11 16:18:16 | -7.3 | 0xb58f5778: already holding this market; 0xe29d38a8: already holding this market |
| 2026-11-11 16:20:21 | -7.0 | 0xd4a204a5: trade; 0xe29d38a8: already holding this market |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-11 14:51:28 | 0xa226594e | 15m | 0.21 | approved | open | 5 | 0.210 | 0.0581 | -1.1081 |
| 2026-11-11 14:51:28 | 0xcc42b292 | 5m | 0.54 | approved | open | 5 | 0.540 | 0.0869 | 2.2131 |
| 2026-11-11 14:56:04 | 0x023fc8ae | 5m | 0.75 | approved | open | 5 | 0.760 | 0.0638 | 1.1362 |
| 2026-11-11 15:00:46 | 0x455379c5 | 5m | 0.34 | approved | open | 5 | 0.370 | 0.0816 | 3.0684 |
| 2026-11-11 15:00:46 | 0xb111b5f7 | 15m | 0.41 | approved | open | 5 | 0.430 | 0.0858 | 2.7642 |
| 2026-11-11 15:25:02 | 0x93922000 | 15m | 0.01 | approved | open | 5 | 0.009 | 0.0031 | -0.0481 |
| 2026-11-11 15:25:02 | 0x2f88abff | 5m | 0.52 | approved | open | 5 | 0.520 | 0.0874 | 2.3126 |
| 2026-11-11 15:32:26 | 0xb67e65cf | 5m | 0.72 | approved | open | 5 | 0.720 | 0.0706 | 1.3294 |
| 2026-11-11 15:32:26 | 0x104a1436 | 15m | 0.58 | approved | open | 5 | 0.590 | 0.0847 | 1.9653 |
| 2026-11-11 15:37:01 | 0xfc5ab9fc | 5m | 0.03 | approved | open | 5 | 0.040 | 0.0134 | -0.2134 |
| 2026-11-11 15:48:33 | 0x5b0aab0c | 5m | 0.12 | approved | open | 5 | 0.120 | 0.0370 | -0.6370 |
| 2026-11-11 15:48:33 | 0x464a2e7a | 15m | 0.37 | approved | open | 5 | 0.370 | 0.0816 | -1.9316 |
| 2026-11-11 15:51:31 | 0xfb9d941f | 5m | 0.68 | approved | open | 5 | 0.680 | 0.0762 | -3.4762 |
| 2026-11-11 16:02:15 | 0xb365fb6b | 5m | 0.58 | approved | open | 5 | 0.580 | 0.0853 | -2.9853 |
| 2026-11-11 16:02:15 | 0xd7b166b8 | 15m | 0.51 | approved | open | 5 | 0.510 | 0.0875 | 2.3625 |
| 2026-11-11 16:07:28 | 0x55eda706 | 5m | 0.07 | approved | open | 5 | 0.100 | 0.0315 | 4.4685 |
| 2026-11-11 16:16:02 | 0xe29d38a8 | 15m | 0.48 | approved | open | 5 | 0.520 | 0.0874 | unresolved |
| 2026-11-11 16:16:02 | 0xb58f5778 | 5m | 0.46 | approved | open | 5 | 0.560 | 0.0862 | unresolved |
| 2026-11-11 16:20:21 | 0xd4a204a5 | 5m | 0.39 | approved | open | 5 | 0.390 | 0.0833 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 100, median 215, p90 236, min 196, max 390.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 47677, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 3.9, max 104.0.
- Binance event time to local receive (network + clock offset): n 47677, median of minute medians 30.0, worst minute p90 2773.0, worst minute p99 7055.5, max 7231.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 53963, median of minute medians 9.7, worst minute p90 71.6, worst minute p99 82682121.7, max 62168392.1.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 31, median 34, p90 73, min -2095, max 177.
- Local receive to decision: n 31, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 31, median 360, p90 381, min 346, max 403.

## Risk, reconciliation, invariants and audit

- Trips: 2: btc-speed ACTIVE (reset, human:DELL-auto); global ACTIVE (reset, human:DELL-auto).
- Human resets: 154; halts confirmed by zero open orders: 0.
- Reconciles: 20 (periodic 20); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 3766 records, head 5ad634113413f798; last head anchored in the ledger: 3652 records, b3aa58660ee55267 (startup, 2026-11-10 07:26:35).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 631 | 200 / 100 | 20.44 | 0 |

Elapsed since the first run: 30.87 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-11-11 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-11-11.md --title "paper_ethb day 32: 2026-11-11 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **MET.**

- Days without a violation: **32 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **15 of 15** (need 5+, all clean)
- Running time: 358.6 hours (14.94 days of 24 h)

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
| 2026-11-11 | 1.7 |
