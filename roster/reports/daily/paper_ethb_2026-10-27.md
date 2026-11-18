# paper_ethb day 17: 2026-10-27 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-10-27 00:00:00 to 2026-10-28 00:00:00 UTC (data from 2026-10-27 00:00:51 to 2026-10-27 16:20:43). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 36, approved 19, orders 19, paper fills 18, btc-speed events 42 and trades 36.
- Paper P&L to the end of the window: btc-speed +131.02 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 367 | 823.97 | 0.00 | 23.5097 | 0.00 | 978.50 | 0 | 0.00 | +131.0210 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 36 intents, 19 approved, 17 rejected: REDUCING 17.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

Latest distinct rejections:

| Time UTC | Strategy | Reason | Binding cap |
|---|---|---|---|
| 2026-10-27 16:06:44 | btc-speed | REDUCING: only exposure-reducing orders | - |

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | taker | 19 | 18 | 90 | 0.4394 | 1.1319 |

Merges of YES+NO pairs: 0; paper redemptions: 18.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| btc-speed | 5 s | 18 | +5.61c | +2.32c | 0 |
| btc-speed | 60 s | 18 | +6.08c | +3.82c | 0 |
| btc-speed | 300 s | 8 | +1.86c | +8.71c | 10 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-v4-eth-bybit**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 363 in 363 markets (needs 200), unresolved 0, mean 0.3609 USD, cluster SE 0.1126, total +131.0210 USD. Verdict: **PASS**.
- **Paper-fill realism** (btc-speed at real tape prices): 303 of 363 resolved trades repriced at what real takers paid in our order's second. Paper +133.07 USD -> best case +65.28 (cheapest real price), typical +14.50 (median real price), **live estimate +8.61** (our order behind the real takers that beat us, partial fills; 67% of our shares filled); real takers paid a median +6.0c over our fill. Paper assumes we win every race for the cheapest ask. Not comparable with reports before 15 Oct.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-11 19:34:32), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-11 19:34:32), `btc-speed-v4-eth-bybit` (sha256 04680de003a175aa, written 2026-10-11 19:34:32).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

42 causal ETH moves (>= 6.0 bp in 2 s) and 36 trades sent to the kernel. Per mapped market: trade 36, ask above max price 19, already holding this market 14, ends too soon 10, no ask 3, stale signal 2.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-27 10:14:39 | -7.0 | 0x7fe43f63: ends too soon; 0x9df544c5: already holding this market |
| 2026-10-27 10:37:01 | +6.0 | 0x917a090a: trade; 0xb82e4d25: trade |
| 2026-10-27 10:39:43 | +6.2 | 0x917a090a: already holding this market; 0xb82e4d25: already holding this market |
| 2026-10-27 10:45:29 | -6.6 | 0x58120499: trade; 0xb133efe7: trade |
| 2026-10-27 10:46:39 | -6.4 | 0x58120499: already holding this market; 0xb133efe7: already holding this market |
| 2026-10-27 10:59:08 | -6.3 | 0x2ede651e: ends too soon; 0x58120499: already holding this market |
| 2026-10-27 12:15:33 | -8.5 | 0x3ed3deac: trade; 0xc6bf4ad0: trade |
| 2026-10-27 12:26:03 | +6.1 | 0xbe21c336: trade; 0xc6bf4ad0: already holding this market |
| 2026-10-27 12:39:21 | +6.9 | 0xdcd1862c: ends too soon; 0xff924010: ask above max price |
| 2026-10-27 12:48:43 | +6.2 | 0xd12c3475: trade; 0xd48843c8: no ask |
| 2026-10-27 12:55:20 | +6.0 | 0xb695382c: trade; 0xd12c3475: already holding this market |
| 2026-10-27 13:31:23 | -6.2 | 0xbf65ee67: trade; 0xcc4ade4b: trade |
| 2026-10-27 13:32:57 | -6.6 | 0xbf65ee67: already holding this market; 0xcc4ade4b: already holding this market |
| 2026-10-27 13:36:05 | -6.3 | 0x7620b02e: trade; 0xcc4ade4b: already holding this market |
| 2026-10-27 13:52:39 | -6.4 | 0xacd943eb: ask above max price; 0xfaadd853: ask above max price |
| 2026-10-27 14:13:07 | +6.2 | 0xc314f06c: ask above max price; 0xf083fdae: ask above max price |
| 2026-10-27 14:31:12 | -6.3 | 0x47b88832: trade; 0x851a0db4: trade |
| 2026-10-27 15:00:19 | +6.0 | 0x2e02f82b: trade; 0xd873071f: trade |
| 2026-10-27 15:12:06 | +7.2 | 0x017128da: trade; 0xd873071f: trade |
| 2026-10-27 15:20:40 | +6.6 | 0xba1905e2: trade; 0xd0aa0f45: ask above max price |
| 2026-10-27 15:21:45 | +7.3 | 0xba1905e2: ask above max price; 0xd0aa0f45: no ask |
| 2026-10-27 15:23:26 | +6.8 | 0xba1905e2: ask above max price; 0xd0aa0f45: ask above max price |
| 2026-10-27 15:24:39 | -6.1 | 0xba1905e2: ends too soon; 0xd0aa0f45: trade |
| 2026-10-27 15:26:12 | +6.4 | 0x70abae99: trade; 0xd0aa0f45: ask above max price |
| 2026-10-27 15:30:26 | -6.4 | 0x785055ae: trade; 0xc446bcc6: trade |
| 2026-10-27 15:35:02 | -6.8 | 0x017465ad: trade; 0x785055ae: ask above max price |
| 2026-10-27 15:46:18 | +6.2 | 0xb57b97a7: trade; 0xfaf6c57f: trade |
| 2026-10-27 15:49:05 | +6.2 | 0xb57b97a7: trade; 0xfaf6c57f: ends too soon |
| 2026-10-27 15:51:40 | +6.3 | 0xb57b97a7: stale signal; 0xee89a645: stale signal |
| 2026-10-27 16:06:44 | -6.1 | 0xc0626068: trade; 0xc11a3290: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-27 00:03:47 | 0x7a729502 | 15m | 0.42 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-27 00:03:47 | 0x4c9248f3 | 5m | 0.14 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-27 05:30:12 | 0x43799fa1 | 5m | 0.75 | approved | open | 5 | 0.770 | 0.0620 | 1.0880 |
| 2026-10-27 05:30:12 | 0xc2f54038 | 15m | 0.69 | approved | open | 5 | 0.690 | 0.0749 | -3.5249 |
| 2026-10-27 07:47:38 | 0x68990b39 | 5m | 0.62 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-27 07:47:38 | 0x9b724a95 | 15m | 0.55 | approved | open | 5 | 0.630 | 0.0816 | 1.7684 |
| 2026-10-27 10:10:15 | 0x9df544c5 | 5m | 0.81 | approved | open | 5 | 0.830 | 0.0494 | 0.8006 |
| 2026-10-27 10:37:01 | 0x917a090a | 5m | 0.5 | approved | open | 5 | 0.500 | 0.0875 | 2.4125 |
| 2026-10-27 10:37:01 | 0xb82e4d25 | 15m | 0.58 | approved | open | 5 | 0.580 | 0.0853 | 2.0147 |
| 2026-10-27 10:45:29 | 0xb133efe7 | 5m | 0.09 | approved | open | 5 | 0.110 | 0.0343 | -0.5843 |
| 2026-10-27 10:45:29 | 0x58120499 | 15m | 0.21 | approved | open | 5 | 0.240 | 0.0638 | -1.2638 |
| 2026-10-27 12:15:33 | 0x3ed3deac | 5m | 0.11 | approved | open | 5 | 0.110 | 0.0343 | -0.5843 |
| 2026-10-27 12:15:33 | 0xc6bf4ad0 | 15m | 0.25 | approved | open | 5 | 0.250 | 0.0656 | -1.3156 |
| 2026-10-27 12:26:03 | 0xbe21c336 | 5m | 0.73 | approved | open | 5 | 0.780 | 0.0601 | 1.0399 |
| 2026-10-27 12:48:43 | 0xd12c3475 | 15m | 0.81 | approved | open | 5 | 0.830 | 0.0494 | 0.8006 |
| 2026-10-27 12:55:20 | 0xb695382c | 5m | 0.48 | approved | open | 5 | 0.480 | 0.0874 | -2.4874 |
| 2026-10-27 13:31:23 | 0xcc4ade4b | 15m | 0.28 | approved | open | 5 | 0.290 | 0.0721 | -1.5221 |
| 2026-10-27 13:31:23 | 0xbf65ee67 | 5m | 0.17 | approved | open | 5 | 0.170 | 0.0494 | -0.8994 |
| 2026-10-27 13:36:05 | 0x7620b02e | 5m | 0.16 | approved | open | 5 | 0.200 | 0.0560 | -1.0560 |
| 2026-10-27 14:31:12 | 0x47b88832 | 5m | 0.11 | approved | open | 5 | 0.160 | 0.0470 | -0.8470 |
| 2026-10-27 14:31:12 | 0x851a0db4 | 15m | 0.26 | approved | open | 5 | 0.290 | 0.0721 | -1.5221 |
| 2026-10-27 15:00:19 | 0xd873071f | 15m | 0.52 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-27 15:00:19 | 0x2e02f82b | 5m | 0.52 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-27 15:12:06 | 0xd873071f | 15m | 0.14 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-27 15:12:06 | 0x017128da | 5m | 0.73 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-27 15:20:40 | 0xba1905e2 | 5m | 0.83 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-27 15:24:39 | 0xd0aa0f45 | 15m | 0.004 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-27 15:26:12 | 0x70abae99 | 5m | 0.16 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-27 15:30:26 | 0x785055ae | 15m | 0.59 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-27 15:30:26 | 0xc446bcc6 | 5m | 0.64 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-27 15:35:02 | 0x017465ad | 5m | 0.5 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-27 15:46:18 | 0xfaf6c57f | 5m | 0.84 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-27 15:46:18 | 0xb57b97a7 | 15m | 0.68 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-27 15:49:05 | 0xb57b97a7 | 15m | 0.54 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-27 16:06:44 | 0xc11a3290 | 15m | 0.68 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-27 16:06:44 | 0xc0626068 | 5m | 0.43 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 981, median 221, p90 259, min 182, max 596.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 279054, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 28.1, max 98.0.
- Binance event time to local receive (network + clock offset): n 279054, median of minute medians 10.0, worst minute p90 2544.1, worst minute p99 2589.0, max 2819.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 535618, median of minute medians 9.7, worst minute p90 19.2, worst minute p99 128.9, max 529.4.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 42, median 36, p90 187, min -75, max 1366.
- Local receive to decision: n 42, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 42, median 380, p90 417, min 355, max 501.

## Risk, reconciliation, invariants and audit

- Trips: 2: btc-speed ACTIVE (reset, human:DELL-auto); btc-speed REDUCING (strategy daily loss 5.03 USD > 5.00 (start of day 136.70), breaker:strategy).
- Human resets: 1; halts confirmed by zero open orders: 0.
- Reconciles: 196 (periodic 196); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 2044 records, head 92eded75482492f4; last head anchored in the ledger: 1709 records, 2c03399bc4bb6647 (startup, 2026-10-24 17:16:01).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 363 | 200 / 100 | 22.88 | 0 |

Elapsed since the first run: 15.87 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-10-27 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-10-27.md --title "paper_ethb day 17: 2026-10-27 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **MET.**

- Days without a violation: **17 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **10 of 10** (need 5+, all clean)
- Running time: 195.9 hours (8.16 days of 24 h)

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
| 2026-10-27 | 16.4 |
