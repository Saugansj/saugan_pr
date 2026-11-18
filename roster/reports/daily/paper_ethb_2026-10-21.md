# paper_ethb day 11: 2026-10-21 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-10-21 00:00:00 to 2026-10-22 00:00:00 UTC (data from 2026-10-21 01:05:48 to 2026-10-21 16:20:05). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 69, approved 2, orders 2, paper fills 2, btc-speed events 61 and trades 69.
- Paper P&L to the end of the window: btc-speed +130.38 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 288 | 619.77 | 0.00 | 18.3496 | 0.00 | 768.50 | 0 | 0.00 | +130.3784 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 69 intents, 2 approved, 67 rejected: REDUCING 67.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

Latest distinct rejections:

| Time UTC | Strategy | Reason | Binding cap |
|---|---|---|---|
| 2026-10-21 16:09:51 | btc-speed | REDUCING: only exposure-reducing orders | - |

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | taker | 2 | 2 | 10 | 0.6550 | 0.1472 |

Merges of YES+NO pairs: 0; paper redemptions: 2.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| btc-speed | 5 s | 2 | +25.50c | +11.00c | 0 |
| btc-speed | 60 s | 2 | +5.00c | +2.50c | 0 |
| btc-speed | 300 s | 0 | - | - | 2 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-v4-eth-bybit**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 285 in 285 markets (needs 200), unresolved 0, mean 0.4575 USD, cluster SE 0.1270, total +130.3784 USD. Verdict: **PASS**.
- **Paper-fill realism** (btc-speed at real tape prices): 239 of 285 resolved trades repriced at what real takers paid in our order's second. Paper +118.50 USD -> best case +60.33 (cheapest real price), typical +20.00 (median real price), **live estimate +27.00** (our order behind the real takers that beat us, partial fills; 68% of our shares filled); real takers paid a median +6.0c over our fill. Paper assumes we win every race for the cheapest ask. Not comparable with reports before 15 Oct.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-11 19:34:32), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-11 19:34:32), `btc-speed-v4-eth-bybit` (sha256 04680de003a175aa, written 2026-10-11 19:34:32).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

61 causal ETH moves (>= 6.0 bp in 2 s) and 69 trades sent to the kernel. Per mapped market: trade 69, ask above max price 26, ends too soon 17, no ask 9, too little size at ask 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-21 14:30:48 | +7.0 | 0x4f16f69f: trade; 0x8e6b93b2: trade |
| 2026-10-21 14:32:53 | +6.3 | 0x4f16f69f: trade; 0x8e6b93b2: trade |
| 2026-10-21 14:39:30 | -6.4 | 0x4c51cab5: ends too soon; 0x8e6b93b2: trade |
| 2026-10-21 14:43:07 | +6.1 | 0x462fcc59: no ask; 0x8e6b93b2: no ask |
| 2026-10-21 14:48:08 | +6.0 | 0x3ccacd51: trade; 0x78ed8d70: ask above max price |
| 2026-10-21 14:49:35 | +6.2 | 0x3ccacd51: trade; 0x78ed8d70: ends too soon |
| 2026-10-21 14:51:55 | +7.2 | 0x3ccacd51: ask above max price; 0xe1af78e8: ask above max price |
| 2026-10-21 14:53:02 | +6.8 | 0x3ccacd51: ask above max price; 0xe1af78e8: trade |
| 2026-10-21 14:55:02 | +6.0 | 0x3ccacd51: ask above max price; 0x8e0f6cc0: trade |
| 2026-10-21 14:58:29 | +6.3 | 0x3ccacd51: no ask; 0x8e0f6cc0: trade |
| 2026-10-21 15:00:59 | +6.2 | 0x19c73826: trade; 0x5fc1d36c: trade |
| 2026-10-21 15:04:30 | +6.1 | 0x19c73826: trade; 0x5fc1d36c: ends too soon |
| 2026-10-21 15:05:57 | +7.9 | 0x19c73826: trade; 0x7f03209d: trade |
| 2026-10-21 15:07:13 | +6.1 | 0x19c73826: ask above max price; 0x7f03209d: trade |
| 2026-10-21 15:08:15 | +6.2 | 0x19c73826: ask above max price; 0x7f03209d: ask above max price |
| 2026-10-21 15:09:20 | -6.7 | 0x19c73826: trade; 0x7f03209d: ends too soon |
| 2026-10-21 15:11:20 | -7.4 | 0x19c73826: trade; 0xb77b25de: trade |
| 2026-10-21 15:12:21 | -6.1 | 0x19c73826: trade; 0xb77b25de: trade |
| 2026-10-21 15:14:40 | -6.1 | 0x19c73826: ends too soon; 0xb77b25de: ends too soon |
| 2026-10-21 15:17:00 | -7.0 | 0x17073882: ask above max price; 0xb9be801d: trade |
| 2026-10-21 15:18:43 | -6.0 | 0x17073882: no ask; 0xb9be801d: ask above max price |
| 2026-10-21 15:25:12 | +6.9 | 0xb9be801d: trade; 0xf60b2857: trade |
| 2026-10-21 15:33:38 | +7.0 | 0x4dea41dc: ask above max price; 0x7599fb33: no ask |
| 2026-10-21 15:39:39 | +6.2 | 0x1b0b2226: ends too soon; 0x4dea41dc: ask above max price |
| 2026-10-21 15:44:38 | -8.1 | 0x4dea41dc: ends too soon; 0xeb9a7c0a: ends too soon |
| 2026-10-21 15:56:25 | -6.6 | 0x09b5995b: trade; 0xc91fdcde: trade |
| 2026-10-21 15:58:02 | +7.5 | 0x09b5995b: ask above max price; 0xc91fdcde: trade |
| 2026-10-21 16:04:46 | -8.4 | 0x3ea8792f: trade; 0x83ed2fb9: ends too soon |
| 2026-10-21 16:06:52 | +6.1 | 0x3ea8792f: trade; 0xdb4c5095: trade |
| 2026-10-21 16:09:51 | +6.4 | 0x3ea8792f: trade; 0xdb4c5095: ends too soon |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-21 14:02:42 | 0xc5673657 | 15m | 0.67 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:04:18 | 0xc5673657 | 15m | 0.73 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:08:01 | 0xc5673657 | 15m | 0.06 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:08:01 | 0x407a31bc | 5m | 0.11 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:11:12 | 0xc5673657 | 15m | 0.07 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:11:12 | 0xa9699c10 | 5m | 0.4 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:13:39 | 0xc5673657 | 15m | 0.01 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:13:39 | 0xa9699c10 | 5m | 0.56 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:27:51 | 0xb87eb32f | 5m | 0.63 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:30:48 | 0x8e6b93b2 | 15m | 0.62 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:30:48 | 0x4f16f69f | 5m | 0.74 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:32:53 | 0x8e6b93b2 | 15m | 0.54 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:32:53 | 0x4f16f69f | 5m | 0.62 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:39:30 | 0x8e6b93b2 | 15m | 0.28 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:48:08 | 0x3ccacd51 | 15m | 0.71 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:49:35 | 0x3ccacd51 | 15m | 0.79 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:53:02 | 0xe1af78e8 | 5m | 0.68 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:55:02 | 0x8e0f6cc0 | 5m | 0.67 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:58:29 | 0x8e0f6cc0 | 5m | 0.61 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 15:00:59 | 0x19c73826 | 15m | 0.58 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 15:00:59 | 0x5fc1d36c | 5m | 0.65 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 15:04:30 | 0x19c73826 | 15m | 0.78 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 15:05:57 | 0x19c73826 | 15m | 0.84 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 15:05:57 | 0x7f03209d | 5m | 0.58 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 15:07:13 | 0x7f03209d | 5m | 0.84 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 15:09:20 | 0x19c73826 | 15m | 0.04 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 15:11:20 | 0x19c73826 | 15m | 0.009 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 15:11:20 | 0xb77b25de | 5m | 0.39 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 15:12:21 | 0x19c73826 | 15m | 0.008 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 15:12:21 | 0xb77b25de | 5m | 0.36 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 15:17:00 | 0xb9be801d | 15m | 0.75 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 15:25:12 | 0xb9be801d | 15m | 0.07 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 15:25:12 | 0xf60b2857 | 5m | 0.52 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 15:56:25 | 0x09b5995b | 15m | 0.15 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 15:56:25 | 0xc91fdcde | 5m | 0.54 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 15:58:02 | 0xc91fdcde | 5m | 0.47 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 16:04:46 | 0x3ea8792f | 15m | 0.64 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 16:06:52 | 0x3ea8792f | 15m | 0.13 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 16:06:52 | 0xdb4c5095 | 5m | 0.14 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-21 16:09:51 | 0x3ea8792f | 15m | 0.79 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 601, median 240, p90 271, min 205, max 546.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 218457, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 6.3, max 58.0.
- Binance event time to local receive (network + clock offset): n 218457, median of minute medians -98.0, worst minute p90 840.3, worst minute p99 2076.7, max 2718.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 329167, median of minute medians 9.6, worst minute p90 25.4, worst minute p99 24953644.7, max 18762215.9.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 61, median -230, p90 -49, min -300, max 249.
- Local receive to decision: n 61, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 61, median 379, p90 402, min 358, max 449.

## Risk, reconciliation, invariants and audit

- Trips: 9: global REDUCING (stale feed binance:ETH: 14381051 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 14369184 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 14369184 ms, breaker:stale_feed); global ACTIVE (reset, human:DELL-feed); btc-speed REDUCING (strategy daily loss 5.40 USD > 5.00 (start of day 137.08), breaker:strategy); global REDUCING (stale feed binance:ETH: 60879 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 60721 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 60721 ms, breaker:stale_feed); global ACTIVE (reset, human:DELL-feed).
- Human resets: 14; halts confirmed by zero open orders: 0.
- Reconciles: 122 (periodic 122); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 1448 records, head 32a5d81841d563d8; last head anchored in the ledger: 1192 records, 59040b69e25ee342 (startup, 2026-10-20 13:06:37).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 285 | 200 / 100 | 28.89 | 0 |

Elapsed since the first run: 9.87 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-10-21 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-10-21.md --title "paper_ethb day 11: 2026-10-21 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **11 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **8 of 8** (need 5+, all clean)
- Running time: 97.7 hours (4.07 days of 24 h)

| UTC day | Hours running |
|---|---|
| 2026-10-11 | 1.1 |
| 2026-10-12 | 15.4 |
| 2026-10-13 | 16.7 |
| 2026-10-14 | 16.0 |
| 2026-10-15 | 12.8 |
| 2026-10-16 | 13.3 |
| 2026-10-20 | 12.4 |
| 2026-10-21 | 10.0 |
