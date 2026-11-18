# paper_ethb day 27: 2026-11-06 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-11-06 00:00:00 to 2026-11-07 00:00:00 UTC (data from 2026-11-06 06:58:31 to 2026-11-06 16:20:22). Paper only: no order ever left this PC.

## Summary

- Runs started: 1; clean shutdowns: 0; still running or ended by a crash or kill: 1 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 117, approved 0, orders 0, paper fills 0, btc-speed events 85 and trades 117.
- Paper P&L to the end of the window: btc-speed +190.50 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 620 | 1462.25 | 0.00 | 40.7457 | 0.00 | 1693.50 | 0 | 0.00 | +190.5026 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 117 intents, 0 approved, 117 rejected: REDUCING 117.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

Latest distinct rejections:

| Time UTC | Strategy | Reason | Binding cap |
|---|---|---|---|
| 2026-11-06 16:17:12 | btc-speed | REDUCING: only exposure-reducing orders | - |

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

85 causal ETH moves (>= 6.0 bp in 2 s) and 117 trades sent to the kernel. Per mapped market: trade 117, ask above max price 20, ends too soon 20, no ask 8, too little size at ask 2, move started before the window 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-11-06 15:12:02 | +6.4 | 0x1a8d737a: trade; 0x28fce834: trade |
| 2026-11-06 15:13:08 | +7.1 | 0x1a8d737a: trade; 0x28fce834: ask above max price |
| 2026-11-06 15:14:15 | +6.2 | 0x1a8d737a: ends too soon; 0x28fce834: ends too soon |
| 2026-11-06 15:17:02 | +6.3 | 0x2a6f106f: trade; 0x2b119193: trade |
| 2026-11-06 15:18:03 | -7.9 | 0x2a6f106f: trade; 0x2b119193: ask above max price |
| 2026-11-06 15:19:47 | -6.3 | 0x2a6f106f: trade; 0x2b119193: ends too soon |
| 2026-11-06 15:20:49 | +6.0 | 0x2a6f106f: trade; 0xd2565134: trade |
| 2026-11-06 15:22:06 | +6.7 | 0x2a6f106f: trade; 0xd2565134: trade |
| 2026-11-06 15:23:55 | -6.2 | 0x2a6f106f: ask above max price; 0xd2565134: no ask |
| 2026-11-06 15:25:33 | +6.3 | 0x2a6f106f: trade; 0x67574b47: trade |
| 2026-11-06 15:27:43 | -6.1 | 0x2a6f106f: ask above max price; 0x67574b47: trade |
| 2026-11-06 15:30:06 | -6.2 | 0x0570fa59: trade; 0xfc97bfc0: trade |
| 2026-11-06 15:31:17 | +6.5 | 0x0570fa59: trade; 0xfc97bfc0: trade |
| 2026-11-06 15:33:15 | -6.3 | 0x0570fa59: trade; 0xfc97bfc0: trade |
| 2026-11-06 15:34:28 | -7.3 | 0x0570fa59: ends too soon; 0xfc97bfc0: trade |
| 2026-11-06 15:35:34 | -7.3 | 0xbeb9af1c: trade; 0xfc97bfc0: trade |
| 2026-11-06 15:38:21 | +6.5 | 0xbeb9af1c: trade; 0xfc97bfc0: trade |
| 2026-11-06 15:39:36 | +6.2 | 0xbeb9af1c: ends too soon; 0xfc97bfc0: trade |
| 2026-11-06 15:42:10 | -6.2 | 0xc5a0f52f: trade; 0xfc97bfc0: trade |
| 2026-11-06 15:43:17 | +6.2 | 0xc5a0f52f: no ask; 0xfc97bfc0: ask above max price |
| 2026-11-06 15:46:53 | -6.2 | 0x0a19f183: trade; 0xb46e1612: trade |
| 2026-11-06 15:52:33 | -6.5 | 0xb46e1612: trade; 0xda88683c: trade |
| 2026-11-06 16:00:02 | +6.3 | 0x8dc13e68: trade; 0xe3229f3b: trade |
| 2026-11-06 16:02:00 | -6.8 | 0x8dc13e68: trade; 0xe3229f3b: trade |
| 2026-11-06 16:05:01 | -6.5 | 0x38ca5eff: move started before the window; 0x8dc13e68: trade |
| 2026-11-06 16:08:17 | +6.2 | 0x38ca5eff: trade; 0x8dc13e68: trade |
| 2026-11-06 16:10:35 | -6.0 | 0x8dc13e68: ask above max price; 0xde79d67d: trade |
| 2026-11-06 16:12:58 | -6.0 | 0x8dc13e68: no ask; 0xde79d67d: no ask |
| 2026-11-06 16:14:14 | +6.2 | 0x8dc13e68: ends too soon; 0xde79d67d: ends too soon |
| 2026-11-06 16:17:12 | -6.7 | 0x86050294: trade; 0xb5a8059d: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-06 15:13:08 | 0x1a8d737a | 15m | 0.37 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:17:02 | 0x2b119193 | 5m | 0.29 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:17:02 | 0x2a6f106f | 15m | 0.4 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:18:03 | 0x2a6f106f | 15m | 0.69 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:19:47 | 0x2a6f106f | 15m | 0.66 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:20:49 | 0x2a6f106f | 15m | 0.26 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:20:49 | 0xd2565134 | 5m | 0.35 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:22:06 | 0x2a6f106f | 15m | 0.19 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:22:06 | 0xd2565134 | 5m | 0.17 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:25:33 | 0x2a6f106f | 15m | 0.15 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:25:33 | 0x67574b47 | 5m | 0.7 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:27:43 | 0x67574b47 | 5m | 0.36 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:30:06 | 0xfc97bfc0 | 15m | 0.54 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:30:06 | 0x0570fa59 | 5m | 0.56 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:31:17 | 0xfc97bfc0 | 15m | 0.24 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:31:17 | 0x0570fa59 | 5m | 0.09 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:33:15 | 0xfc97bfc0 | 15m | 0.56 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:33:15 | 0x0570fa59 | 5m | 0.7 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:34:28 | 0xfc97bfc0 | 15m | 0.55 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:35:34 | 0xfc97bfc0 | 15m | 0.73 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:35:34 | 0xbeb9af1c | 5m | 0.72 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:38:21 | 0xfc97bfc0 | 15m | 0.33 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:38:21 | 0xbeb9af1c | 5m | 0.43 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:39:36 | 0xfc97bfc0 | 15m | 0.31 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:42:10 | 0xfc97bfc0 | 15m | 0.74 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:42:10 | 0xc5a0f52f | 5m | 0.32 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:46:53 | 0xb46e1612 | 15m | 0.35 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:46:53 | 0x0a19f183 | 5m | 0.2 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:52:33 | 0xb46e1612 | 15m | 0.16 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 15:52:33 | 0xda88683c | 5m | 0.19 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 16:00:02 | 0xe3229f3b | 5m | 0.44 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 16:00:02 | 0x8dc13e68 | 15m | 0.48 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 16:02:00 | 0xe3229f3b | 5m | 0.6 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 16:02:00 | 0x8dc13e68 | 15m | 0.55 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 16:05:01 | 0x8dc13e68 | 15m | 0.49 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 16:08:17 | 0x38ca5eff | 5m | 0.15 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 16:08:17 | 0x8dc13e68 | 15m | 0.33 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 16:10:35 | 0xde79d67d | 5m | 0.75 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 16:17:12 | 0xb5a8059d | 5m | 0.33 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-06 16:17:12 | 0x86050294 | 15m | 0.41 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 437, median 211, p90 256, min 188, max 1872.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 244323, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 3.5, max 124.0.
- Binance event time to local receive (network + clock offset): n 244323, median of minute medians -802.5, worst minute p90 6440.8, worst minute p99 9315.6, max 9317.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 237217, median of minute medians 9.4, worst minute p90 133.3, worst minute p99 184913477.5, max 113443890.3.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 85, median -855, p90 -330, min -951, max 147.
- Local receive to decision: n 85, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 85, median 361, p90 479, min 338, max 2022.

## Risk, reconciliation, invariants and audit

- Trips: 2: global ACTIVE (reset, human:DELL-feed); btc-speed REDUCING (restart: strategy daily loss 5.04 USD > 5.00 (start of day 196.50), loop:restart).
- Human resets: 13; halts confirmed by zero open orders: 0.
- Reconciles: 89 (periodic 88, startup 1); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 3611 records, head 5e06b975cad48f9f; last head anchored in the ledger: 3492 records, a48e2582da8b0e4b (startup, 2026-11-06 09:18:59).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 615 | 200 / 100 | 23.78 | 0 |

Elapsed since the first run: 25.87 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-11-06 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-11-06.md --title "paper_ethb day 27: 2026-11-06 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **MET.**

- Days without a violation: **27 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **13 of 13** (need 5+, all clean)
- Running time: 343.8 hours (14.32 days of 24 h)

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
| 2026-11-06 | 7.3 |
