# paper_ethb day 21: 2026-10-31 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-10-31 00:00:00 to 2026-11-01 00:00:00 UTC (data from 2026-10-31 00:00:01 to 2026-10-31 16:20:24). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 8, approved 6, orders 6, paper fills 4, btc-speed events 7 and trades 8.
- Paper P&L to the end of the window: btc-speed +140.12 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 477 | 1112.33 | 0.00 | 31.0528 | 0.00 | 1283.50 | 0 | 0.00 | +140.1205 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 8 intents, 6 approved, 2 rejected: REDUCING 2.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

Latest distinct rejections:

| Time UTC | Strategy | Reason | Binding cap |
|---|---|---|---|
| 2026-10-31 01:46:14 | btc-speed | REDUCING: only exposure-reducing orders | - |

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | taker | 6 | 4 | 20 | 0.6325 | 0.2987 |

Merges of YES+NO pairs: 0; paper redemptions: 4.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| btc-speed | 5 s | 4 | +16.37c | +3.06c | 0 |
| btc-speed | 60 s | 3 | -2.50c | +8.39c | 1 |
| btc-speed | 300 s | 2 | -9.00c | +32.50c | 2 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-v4-eth-bybit**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 472 in 472 markets (needs 200), unresolved 0, mean 0.2969 USD, cluster SE 0.0987, total +140.1205 USD. Verdict: **PASS**.
- **Paper-fill realism** (btc-speed at real tape prices): 396 of 472 resolved trades repriced at what real takers paid in our order's second. Paper +145.77 USD -> best case +64.28 (cheapest real price), typical +3.64 (median real price), **live estimate +9.18** (our order behind the real takers that beat us, partial fills; 69% of our shares filled); real takers paid a median +5.0c over our fill. Paper assumes we win every race for the cheapest ask. Not comparable with reports before 15 Oct.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-11 19:34:32), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-11 19:34:32), `btc-speed-v4-eth-bybit` (sha256 04680de003a175aa, written 2026-10-11 19:34:32).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

7 causal ETH moves (>= 6.0 bp in 2 s) and 8 trades sent to the kernel. Per mapped market: trade 8, ask above max price 5, no ask 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-31 00:12:16 | +7.2 | 0x116d79d4: ask above max price; 0x14fb9822: ask above max price |
| 2026-10-31 01:46:14 | +8.4 | 0xa432776f: trade; 0xfbdb7e60: trade |
| 2026-10-31 06:47:16 | +6.4 | 0x2645bf9a: trade; 0xab75a79e: trade |
| 2026-10-31 07:31:38 | +6.2 | 0x3f2aefa0: trade; 0x9a81cf57: trade |
| 2026-10-31 08:33:31 | -6.4 | 0x25dafd9f: ask above max price; 0x2846053a: no ask |
| 2026-10-31 11:37:36 | +6.4 | 0x15d1464f: ask above max price; 0xc7237791: trade |
| 2026-10-31 12:36:24 | +6.0 | 0xbf8941d8: ask above max price; 0xcb1f1898: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-31 01:46:14 | 0xfbdb7e60 | 5m | 0.58 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-31 01:46:14 | 0xa432776f | 15m | 0.54 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-31 06:47:16 | 0x2645bf9a | 5m | 0.85 | approved | open | 5 | 0.850 | 0.0446 | 0.7054 |
| 2026-10-31 06:47:16 | 0xab75a79e | 15m | 0.65 | approved | open | 5 | 0.650 | 0.0796 | 1.6704 |
| 2026-10-31 07:31:38 | 0x3f2aefa0 | 5m | 0.54 | approved | open | 5 | 0.540 | 0.0869 | -2.7869 |
| 2026-10-31 07:31:38 | 0x9a81cf57 | 15m | 0.49 | approved | open | 5 | 0.490 | 0.0875 | -2.5375 |
| 2026-10-31 11:37:36 | 0xc7237791 | 5m | 0.71 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-31 12:36:24 | 0xcb1f1898 | 5m | 0.74 | approved | open | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 911, median 215, p90 232, min 188, max 503.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 131767, median of minute medians 0.0, worst minute p90 3.0, worst minute p99 57.5, max 64.0.
- Binance event time to local receive (network + clock offset): n 131767, median of minute medians -85.0, worst minute p90 497.2, worst minute p99 2239.1, max 2792.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 496349, median of minute medians 9.8, worst minute p90 19.8, worst minute p99 5500956.0, max 4179042.4.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 7, median -70, p90 -15, min -266, max -20.
- Local receive to decision: n 7, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 7, median 368, p90 534, min 349, max 508.

## Risk, reconciliation, invariants and audit

- Trips: 5: btc-speed ACTIVE (reset, human:DELL-auto); global REDUCING (stale feed polymarket:crypto-fast: 4232134 ms, breaker:stale_feed); global REDUCING (stale feed binance:ETH: 4232000 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 4232134 ms, breaker:stale_feed); global ACTIVE (reset, human:DELL-feed).
- Human resets: 44; halts confirmed by zero open orders: 0.
- Reconciles: 183 (periodic 183); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 2665 records, head 205122e4329c31bb; last head anchored in the ledger: 2046 records, 22b64a79d0480995 (startup, 2026-10-28 18:33:10).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 472 | 200 / 100 | 23.76 | 0 |

Elapsed since the first run: 19.87 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-10-31 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-10-31.md --title "paper_ethb day 21: 2026-10-31 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **MET.**

- Days without a violation: **21 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **11 of 11** (need 5+, all clean)
- Running time: 250.9 hours (10.45 days of 24 h)

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
| 2026-10-31 | 15.2 |
