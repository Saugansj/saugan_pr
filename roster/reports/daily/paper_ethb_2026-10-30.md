# paper_ethb day 20: 2026-10-30 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-10-30 00:00:00 to 2026-10-31 00:00:00 UTC (data from 2026-10-30 11:09:19 to 2026-10-30 16:20:48). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 81, approved 22, orders 22, paper fills 22, btc-speed events 82 and trades 83.
- Paper P&L to the end of the window: btc-speed +143.07 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 473 | 1099.68 | 0.00 | 30.7542 | 0.00 | 1273.50 | 0 | 0.00 | +143.0691 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 81 intents, 22 approved, 59 rejected: REDUCING 59.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

Latest distinct rejections:

| Time UTC | Strategy | Reason | Binding cap |
|---|---|---|---|
| 2026-10-30 16:20:48 | btc-speed | REDUCING: only exposure-reducing orders | - |

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | taker | 22 | 22 | 110 | 0.5377 | 1.7034 |

Merges of YES+NO pairs: 0; paper redemptions: 22.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| btc-speed | 5 s | 22 | +2.23c | +2.24c | 0 |
| btc-speed | 60 s | 21 | -2.38c | +3.56c | 1 |
| btc-speed | 300 s | 8 | -6.06c | +6.17c | 14 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-v4-eth-bybit**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 468 in 468 markets (needs 200), unresolved 0, mean 0.3057 USD, cluster SE 0.0991, total +143.0691 USD. Verdict: **PASS**.
- **Paper-fill realism** (btc-speed at real tape prices): 392 of 468 resolved trades repriced at what real takers paid in our order's second. Paper +148.72 USD -> best case +68.38 (cheapest real price), typical +9.17 (median real price), **live estimate +7.60** (our order behind the real takers that beat us, partial fills; 69% of our shares filled); real takers paid a median +5.0c over our fill. Paper assumes we win every race for the cheapest ask. Not comparable with reports before 15 Oct.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-11 19:34:32), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-11 19:34:32), `btc-speed-v4-eth-bybit` (sha256 04680de003a175aa, written 2026-10-11 19:34:32).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

82 causal ETH moves (>= 6.0 bp in 2 s) and 83 trades sent to the kernel. Per mapped market: trade 83, already holding this market 49, ask above max price 15, ends too soon 12, no ask 4, too little size at ask 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-30 14:53:50 | +6.0 | 0xdbea8884: trade; 0xfcf57652: trade |
| 2026-10-30 14:55:41 | +6.1 | 0xb639544d: trade; 0xdbea8884: ask above max price |
| 2026-10-30 15:01:02 | +7.0 | 0xbf8d8a3c: trade; 0xf016bd07: trade |
| 2026-10-30 15:02:34 | -6.1 | 0xbf8d8a3c: trade; 0xf016bd07: trade |
| 2026-10-30 15:06:59 | +8.4 | 0xa47c1d73: trade; 0xbf8d8a3c: ask above max price |
| 2026-10-30 15:09:18 | +6.8 | 0xa47c1d73: ends too soon; 0xbf8d8a3c: ask above max price |
| 2026-10-30 15:11:34 | -6.1 | 0xbf8d8a3c: trade; 0xeaa83978: trade |
| 2026-10-30 15:13:49 | -6.2 | 0xbf8d8a3c: trade; 0xeaa83978: trade |
| 2026-10-30 15:16:41 | +6.0 | 0xa5065508: trade; 0xbd210a85: trade |
| 2026-10-30 15:18:41 | +6.2 | 0xa5065508: no ask; 0xbd210a85: trade |
| 2026-10-30 15:19:48 | +7.2 | 0xa5065508: ends too soon; 0xbd210a85: trade |
| 2026-10-30 15:21:05 | -6.4 | 0x0a5d7433: ask above max price; 0xbd210a85: trade |
| 2026-10-30 15:22:12 | -6.0 | 0x0a5d7433: ask above max price; 0xbd210a85: trade |
| 2026-10-30 15:23:35 | +6.2 | 0x0a5d7433: trade; 0xbd210a85: trade |
| 2026-10-30 15:24:43 | +6.7 | 0x0a5d7433: ends too soon; 0xbd210a85: trade |
| 2026-10-30 15:26:16 | -6.1 | 0x2f4edce2: ask above max price; 0xbd210a85: ask above max price |
| 2026-10-30 15:27:47 | -6.4 | 0x2f4edce2: no ask; 0xbd210a85: no ask |
| 2026-10-30 15:31:36 | -6.1 | 0x2e3ffc27: ask above max price; 0xf3a2dd03: trade |
| 2026-10-30 15:38:20 | +6.4 | 0x361e6b90: trade; 0xf3a2dd03: trade |
| 2026-10-30 15:42:01 | -6.5 | 0xc1c6c54d: trade; 0xf3a2dd03: no ask |
| 2026-10-30 15:44:25 | -6.2 | 0xc1c6c54d: ends too soon; 0xf3a2dd03: ends too soon |
| 2026-10-30 15:47:26 | -7.0 | 0xa9a7f1ca: ask above max price; 0xb5c4b1c4: trade |
| 2026-10-30 15:50:17 | -6.7 | 0x4836ed9e: trade; 0xb5c4b1c4: trade |
| 2026-10-30 15:55:10 | +6.6 | 0x5af79d50: trade; 0xb5c4b1c4: trade |
| 2026-10-30 15:57:21 | +6.3 | 0x5af79d50: trade; 0xb5c4b1c4: trade |
| 2026-10-30 15:59:48 | -6.2 | 0x5af79d50: ends too soon; 0xb5c4b1c4: ends too soon |
| 2026-10-30 16:00:59 | -6.7 | 0xb75ef2a7: trade; 0xc2ed8e83: ask above max price |
| 2026-10-30 16:02:06 | +6.1 | 0xb75ef2a7: trade; 0xc2ed8e83: trade |
| 2026-10-30 16:04:01 | -6.2 | 0xb75ef2a7: trade; 0xc2ed8e83: ends too soon |
| 2026-10-30 16:20:48 | -7.9 | 0x8e3522cd: trade; 0xbdbf5860: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-30 14:50:34 | 0xdbea8884 | 15m | 0.81 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 14:50:34 | 0xfcf57652 | 5m | 0.59 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 14:53:50 | 0xdbea8884 | 15m | 0.67 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 14:53:50 | 0xfcf57652 | 5m | 0.04 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 14:55:41 | 0xb639544d | 5m | 0.75 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:01:02 | 0xf016bd07 | 5m | 0.8 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:01:02 | 0xbf8d8a3c | 15m | 0.65 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:02:34 | 0xf016bd07 | 5m | 0.02 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:02:34 | 0xbf8d8a3c | 15m | 0.22 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:06:59 | 0xa47c1d73 | 5m | 0.65 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:11:34 | 0xbf8d8a3c | 15m | 0.009 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:11:34 | 0xeaa83978 | 5m | 0.68 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:13:49 | 0xbf8d8a3c | 15m | 0.001 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:13:49 | 0xeaa83978 | 5m | 0.65 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:16:41 | 0xa5065508 | 5m | 0.75 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:16:41 | 0xbd210a85 | 15m | 0.62 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:18:41 | 0xbd210a85 | 15m | 0.85 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:19:48 | 0xbd210a85 | 15m | 0.82 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:21:05 | 0xbd210a85 | 15m | 0.48 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:22:12 | 0xbd210a85 | 15m | 0.61 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:23:35 | 0xbd210a85 | 15m | 0.34 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:23:35 | 0x0a5d7433 | 5m | 0.001 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:24:43 | 0xbd210a85 | 15m | 0.34 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:31:36 | 0xf3a2dd03 | 15m | 0.84 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:38:20 | 0xf3a2dd03 | 15m | 0.05 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:38:20 | 0x361e6b90 | 5m | 0.61 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:42:01 | 0xc1c6c54d | 5m | 0.57 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:47:26 | 0xb5c4b1c4 | 15m | 0.72 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:50:17 | 0xb5c4b1c4 | 15m | 0.59 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:50:17 | 0x4836ed9e | 5m | 0.36 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:55:10 | 0xb5c4b1c4 | 15m | 0.29 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:55:10 | 0x5af79d50 | 5m | 0.66 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:57:21 | 0xb5c4b1c4 | 15m | 0.22 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 15:57:21 | 0x5af79d50 | 5m | 0.7 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 16:00:59 | 0xb75ef2a7 | 15m | 0.76 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 16:02:06 | 0xc2ed8e83 | 5m | 0.16 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 16:02:06 | 0xb75ef2a7 | 15m | 0.31 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 16:04:01 | 0xb75ef2a7 | 15m | 0.77 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 16:20:48 | 0xbdbf5860 | 15m | 0.22 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-30 16:20:48 | 0x8e3522cd | 5m | 0.44 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 313, median 218, p90 242, min 195, max 1668.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 196987, median of minute medians 0.0, worst minute p90 2.0, worst minute p99 8.0, max 84.0.
- Binance event time to local receive (network + clock offset): n 196987, median of minute medians -78.0, worst minute p90 327.0, worst minute p99 1228.3, max 1892.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 170032, median of minute medians 9.7, worst minute p90 24.0, worst minute p99 67144061.2, max 41449147.5.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 82, median -90, p90 26, min -182, max 249.
- Local receive to decision: n 82, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 82, median 368, p90 400, min 347, max 454.

## Risk, reconciliation, invariants and audit

- Trips: 4: global REDUCING (stale feed binance:ETH: 41449438 ms, breaker:stale_feed); btc-speed ACTIVE (reset, human:DELL-auto); global ACTIVE (reset, human:DELL-auto); btc-speed REDUCING (strategy daily loss 5.10 USD > 5.00 (start of day 148.92), breaker:strategy).
- Human resets: 50; halts confirmed by zero open orders: 0.
- Reconciles: 63 (periodic 63); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 2586 records, head 412fa5435f445cec; last head anchored in the ledger: 2046 records, 22b64a79d0480995 (startup, 2026-10-28 18:33:10).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 468 | 200 / 100 | 24.81 | 0 |

Elapsed since the first run: 18.87 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-10-30 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-10-30.md --title "paper_ethb day 20: 2026-10-30 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **MET.**

- Days without a violation: **20 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **11 of 11** (need 5+, all clean)
- Running time: 228.1 hours (9.50 days of 24 h)

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
| 2026-10-30 | 5.2 |
