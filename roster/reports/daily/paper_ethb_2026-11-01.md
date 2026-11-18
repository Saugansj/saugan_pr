# paper_ethb day 22: 2026-11-01 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-11-01 00:00:00 to 2026-11-02 00:00:00 UTC (data from 2026-11-01 00:00:50 to 2026-11-01 16:20:42). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 16, approved 16, orders 16, paper fills 12, btc-speed events 15 and trades 16.
- Paper P&L to the end of the window: btc-speed +148.50 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 491 | 1143.08 | 0.00 | 31.9207 | 0.00 | 1323.50 | 0 | 0.00 | +148.5026 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 16 intents, 16 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | taker | 16 | 12 | 60 | 0.4992 | 0.8175 |

Merges of YES+NO pairs: 0; paper redemptions: 12.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| btc-speed | 5 s | 12 | +26.17c | +4.67c | 0 |
| btc-speed | 60 s | 10 | +20.80c | +4.54c | 2 |
| btc-speed | 300 s | 4 | +11.62c | +11.23c | 8 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-v4-eth-bybit**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 486 in 486 markets (needs 200), unresolved 0, mean 0.3056 USD, cluster SE 0.0973, total +148.5026 USD. Verdict: **PASS**.
- **Paper-fill realism** (btc-speed at real tape prices): 410 of 486 resolved trades repriced at what real takers paid in our order's second. Paper +154.15 USD -> best case +69.14 (cheapest real price), typical -0.79 (median real price), **live estimate +11.28** (our order behind the real takers that beat us, partial fills; 68% of our shares filled); real takers paid a median +5.3c over our fill. Paper assumes we win every race for the cheapest ask. Not comparable with reports before 15 Oct.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-11 19:34:32), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-11 19:34:32), `btc-speed-v4-eth-bybit` (sha256 04680de003a175aa, written 2026-10-11 19:34:32).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

15 causal ETH moves (>= 6.0 bp in 2 s) and 16 trades sent to the kernel. Per mapped market: trade 16, ask above max price 6, already holding this market 4, ends too soon 2, no ask 2.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-11-01 01:23:51 | +6.0 | 0xa3a7d88a: ask above max price; 0xf9f9dcdb: ask above max price |
| 2026-11-01 01:35:24 | +6.3 | 0x506cab3f: trade; 0xc2cb0ea3: ask above max price |
| 2026-11-01 02:02:35 | +6.4 | 0x5b2a2551: trade; 0xaa1b85c9: trade |
| 2026-11-01 02:03:53 | +6.5 | 0x5b2a2551: already holding this market; 0xaa1b85c9: already holding this market |
| 2026-11-01 02:50:15 | -6.7 | 0x06027427: trade; 0x63cdf1df: trade |
| 2026-11-01 03:53:12 | +6.2 | 0x31eab959: trade; 0xf815f1f1: trade |
| 2026-11-01 08:35:02 | +6.1 | 0x51251d4a: trade; 0x91703414: ask above max price |
| 2026-11-01 08:49:29 | +6.4 | 0x30e6497f: ends too soon; 0xb3b991f5: trade |
| 2026-11-01 08:58:37 | +6.4 | 0x66d2db27: ask above max price; 0xb3b991f5: no ask |
| 2026-11-01 12:09:30 | -6.8 | 0x081062be: ask above max price; 0x11e890f3: ends too soon |
| 2026-11-01 12:15:19 | -6.3 | 0x7fc208d2: trade; 0xbbf97640: trade |
| 2026-11-01 12:17:41 | +6.2 | 0x7fc208d2: already holding this market; 0xbbf97640: already holding this market |
| 2026-11-01 13:36:58 | -6.5 | 0x297c9626: trade; 0x8ec48364: trade |
| 2026-11-01 14:07:44 | +6.1 | 0x101e3028: no ask; 0xb0c3a88a: trade |
| 2026-11-01 14:18:22 | +6.5 | 0x8d2d6386: trade; 0xabe6859a: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-01 01:35:24 | 0x506cab3f | 5m | 0.8 | approved | open | 5 | 0.850 | 0.0446 | 0.7054 |
| 2026-11-01 02:02:35 | 0x5b2a2551 | 15m | 0.64 | approved | open | 5 | 0.640 | 0.0806 | -3.2806 |
| 2026-11-01 02:02:35 | 0xaa1b85c9 | 5m | 0.84 | approved | open | 5 | 0.840 | 0.0470 | 0.7530 |
| 2026-11-01 02:50:15 | 0x63cdf1df | 15m | 0.13 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-01 02:50:15 | 0x06027427 | 5m | 0.44 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-01 03:53:12 | 0xf815f1f1 | 15m | 0.04 | approved | open | 5 | 0.040 | 0.0134 | -0.2134 |
| 2026-11-01 03:53:12 | 0x31eab959 | 5m | 0.38 | approved | open | 5 | 0.380 | 0.0825 | 3.0175 |
| 2026-11-01 08:35:02 | 0x51251d4a | 5m | 0.43 | approved | open | 5 | 0.430 | 0.0858 | -2.2358 |
| 2026-11-01 08:49:29 | 0xb3b991f5 | 15m | 0.8 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-01 12:15:19 | 0xbbf97640 | 15m | 0.58 | approved | open | 5 | 0.580 | 0.0853 | 2.0147 |
| 2026-11-01 12:15:19 | 0x7fc208d2 | 5m | 0.68 | approved | open | 5 | 0.680 | 0.0762 | 1.5238 |
| 2026-11-01 13:36:58 | 0x297c9626 | 15m | 0.18 | approved | open | 5 | 0.180 | 0.0517 | -0.9517 |
| 2026-11-01 13:36:58 | 0x8ec48364 | 5m | 0.58 | approved | open | 5 | 0.580 | 0.0853 | 2.0147 |
| 2026-11-01 14:07:44 | 0xb0c3a88a | 15m | 0.57 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-01 14:18:22 | 0x8d2d6386 | 5m | 0.34 | approved | open | 5 | 0.340 | 0.0785 | 3.2215 |
| 2026-11-01 14:18:22 | 0xabe6859a | 15m | 0.45 | approved | open | 5 | 0.450 | 0.0866 | -2.3366 |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 981, median 210, p90 229, min 186, max 522.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 109450, median of minute medians 0.0, worst minute p90 2.0, worst minute p99 76.5, max 115.0.
- Binance event time to local receive (network + clock offset): n 109450, median of minute medians -20.0, worst minute p90 1193.0, worst minute p99 1200.5, max 1914.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 534614, median of minute medians 9.7, worst minute p90 12.0, worst minute p99 123.0, max 271.1.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 15, median 55, p90 240, min -109, max 353.
- Local receive to decision: n 15, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 15, median 360, p90 412, min 342, max 456.

## Risk, reconciliation, invariants and audit

- Trips: 3: global REDUCING (stale feed polymarket:crypto-fast: 60344 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 60344 ms, breaker:stale_feed); global ACTIVE (reset, human:DELL-feed).
- Human resets: 67; halts confirmed by zero open orders: 0.
- Reconciles: 196 (periodic 196); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 2736 records, head f1aa6339a1328c51; last head anchored in the ledger: 2046 records, 22b64a79d0480995 (startup, 2026-10-28 18:33:10).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 486 | 200 / 100 | 23.29 | 0 |

Elapsed since the first run: 20.87 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-11-01 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-11-01.md --title "paper_ethb day 22: 2026-11-01 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **MET.**

- Days without a violation: **22 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **11 of 11** (need 5+, all clean)
- Running time: 274.9 hours (11.45 days of 24 h)

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
| 2026-11-01 | 16.4 |
