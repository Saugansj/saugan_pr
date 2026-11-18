# paper_ethb day 31: 2026-11-10 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-11-10 00:00:00 to 2026-11-11 00:00:00 UTC (data from 2026-11-10 07:26:35 to 2026-11-10 17:21:34). Paper only: no order ever left this PC.

## Summary

- Runs started: 1; clean shutdowns: 0; still running or ended by a crash or kill: 1 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 30, approved 0, orders 0, paper fills 0, btc-speed events 31 and trades 30.
- Paper P&L to the end of the window: btc-speed +190.50 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 620 | 1462.25 | 0.00 | 40.7457 | 0.00 | 1693.50 | 0 | 0.00 | +190.5026 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 30 intents, 0 approved, 30 rejected: REDUCING 30.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

Latest distinct rejections:

| Time UTC | Strategy | Reason | Binding cap |
|---|---|---|---|
| 2026-11-10 13:32:56 | btc-speed | REDUCING: only exposure-reducing orders | - |

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

31 causal ETH moves (>= 6.0 bp in 2 s) and 30 trades sent to the kernel. Per mapped market: trade 30, ask above max price 10, ends too soon 6, stale signal 4, stale book 2.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-11-10 08:00:21 | -6.3 | 0x2bdf593c: trade; 0x6516b5c2: trade |
| 2026-11-10 08:03:46 | -6.3 | 0x2bdf593c: ask above max price; 0x6516b5c2: trade |
| 2026-11-10 08:31:29 | -6.2 | 0x25e810e4: trade |
| 2026-11-10 09:00:02 | -6.2 | 0x42f50bf7: trade; 0xa7a11112: trade |
| 2026-11-10 09:01:33 | +7.1 | 0x42f50bf7: trade; 0xa7a11112: trade |
| 2026-11-10 09:09:51 | -6.0 | 0xa7a11112: ask above max price; 0xcc8225ba: ends too soon |
| 2026-11-10 09:11:03 | +6.7 | 0x0f1a7d2a: stale signal; 0xa7a11112: stale signal |
| 2026-11-10 09:17:47 | +6.1 | 0x27a2df9b: trade; 0x95c512c4: ask above max price |
| 2026-11-10 09:36:00 | -6.5 | 0x0d4d34c0: ask above max price; 0xa9c231c7: ask above max price |
| 2026-11-10 09:37:01 | +6.5 | 0x0d4d34c0: trade; 0xa9c231c7: trade |
| 2026-11-10 09:44:46 | +6.4 | 0x0d4d34c0: ends too soon; 0x5f7574ff: ends too soon |
| 2026-11-10 10:02:55 | -6.2 | 0x027948e7: stale book; 0x8cb726cd: stale book |
| 2026-11-10 10:27:42 | -8.5 | 0x035a56ef: ask above max price; 0x4a35c6ad: ask above max price |
| 2026-11-10 10:32:42 | -6.0 | 0xbc71743a: trade; 0xd0b25bed: trade |
| 2026-11-10 10:41:12 | -6.0 | 0x698d8900: ask above max price; 0xbc71743a: ask above max price |
| 2026-11-10 10:45:50 | -6.8 | 0xe7397f4b: ask above max price |
| 2026-11-10 11:00:16 | -6.4 | - |
| 2026-11-10 11:15:45 | +6.2 | - |
| 2026-11-10 11:17:15 | -6.0 | - |
| 2026-11-10 11:40:25 | +7.1 | 0x55fdd8e5: trade; 0x5e7c8034: trade |
| 2026-11-10 12:33:15 | +6.3 | 0x163ec053: trade; 0x6d6070fa: trade |
| 2026-11-10 12:36:35 | +6.2 | 0x6d6070fa: trade; 0xc365d1c9: trade |
| 2026-11-10 13:19:02 | +6.2 | 0x34ce9e9a: ends too soon; 0x548c2eeb: trade |
| 2026-11-10 13:20:29 | +6.0 | 0x548c2eeb: trade; 0x58f4d9a3: trade |
| 2026-11-10 13:25:02 | -6.9 | 0x0e59c486: trade; 0x548c2eeb: trade |
| 2026-11-10 13:29:52 | +7.6 | 0x0e59c486: ends too soon; 0x548c2eeb: ends too soon |
| 2026-11-10 13:30:55 | -6.6 | 0x3edfe631: stale signal; 0x886d9e26: stale signal |
| 2026-11-10 13:31:54 | +7.0 | 0x3edfe631: trade; 0x886d9e26: trade |
| 2026-11-10 13:32:56 | +6.2 | 0x3edfe631: trade; 0x886d9e26: trade |
| 2026-11-10 16:19:24 | -6.8 | - |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-10 07:37:30 | 0x8a8e7fc7 | 15m | 0.08 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 07:37:30 | 0x77870d1a | 5m | 0.13 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 08:00:21 | 0x6516b5c2 | 15m | 0.72 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 08:00:21 | 0x2bdf593c | 5m | 0.82 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 08:03:46 | 0x6516b5c2 | 15m | 0.65 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 08:31:29 | 0x25e810e4 | 5m | 0.72 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 09:00:02 | 0x42f50bf7 | 5m | 0.79 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 09:00:02 | 0xa7a11112 | 15m | 0.68 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 09:01:33 | 0x42f50bf7 | 5m | 0.01 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 09:01:33 | 0xa7a11112 | 15m | 0.03 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 09:17:47 | 0x27a2df9b | 15m | 0.81 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 09:37:01 | 0x0d4d34c0 | 15m | 0.07 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 09:37:01 | 0xa9c231c7 | 5m | 0.08 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 10:32:42 | 0xbc71743a | 15m | 0.67 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 10:32:42 | 0xd0b25bed | 5m | 0.85 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 11:40:25 | 0x5e7c8034 | 15m | 0.03 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 11:40:25 | 0x55fdd8e5 | 5m | 0.18 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 12:33:15 | 0x163ec053 | 5m | 0.03 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 12:33:15 | 0x6d6070fa | 15m | 0.26 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 12:36:35 | 0x6d6070fa | 15m | 0.13 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 12:36:35 | 0xc365d1c9 | 5m | 0.19 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 13:19:02 | 0x548c2eeb | 15m | 0.12 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 13:20:29 | 0x58f4d9a3 | 5m | 0.79 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 13:20:29 | 0x548c2eeb | 15m | 0.24 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 13:25:02 | 0x548c2eeb | 15m | 0.67 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 13:25:02 | 0x0e59c486 | 5m | 0.62 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 13:31:54 | 0x3edfe631 | 5m | 0.02 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 13:31:54 | 0x886d9e26 | 15m | 0.1 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 13:32:56 | 0x3edfe631 | 5m | 0.01 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-10 13:32:56 | 0x886d9e26 | 15m | 0.07 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 372, median 207, p90 437, min 184, max 799.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 156454, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 3.0, max 38.0.
- Binance event time to local receive (network + clock offset): n 156454, median of minute medians -1306.0, worst minute p90 20297.0, worst minute p99 28622.8, max 28997.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 202481, median of minute medians 9.6, worst minute p90 4976966.3, worst minute p99 6896647.2, max 9901816.7.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 31, median -1242, p90 -727, min -1517, max 2954.
- Local receive to decision: n 31, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 31, median 355, p90 568, min 342, max 590.

## Risk, reconciliation, invariants and audit

- Trips: 7: btc-speed REDUCING (restart: restart: restart: strategy daily loss 5.04 USD > 5.00 (start , loop:restart); global REDUCING (stale feed polymarket:crypto-fast: 9902084 ms, breaker:stale_feed); global REDUCING (stale feed binance:ETH: 9901882 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 9902084 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 60629 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 60629 ms, breaker:stale_feed); global REDUCING (stale feed binance:ETH: 3556336 ms, breaker:stale_feed).
- Human resets: 114; halts confirmed by zero open orders: 0.
- Reconciles: 77 (startup 1, periodic 76); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 3691 records, head 42f7578bce96e53e; last head anchored in the ledger: 3652 records, b3aa58660ee55267 (startup, 2026-11-10 07:26:35).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 615 | 200 / 100 | 20.56 | 0 |

Elapsed since the first run: 29.91 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-11-10 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-11-10.md --title "paper_ethb day 31: 2026-11-10 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **MET.**

- Days without a violation: **31 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **15 of 15** (need 5+, all clean)
- Running time: 357.0 hours (14.87 days of 24 h)

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
