# paper_ethb day 25: 2026-11-04 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-11-04 00:00:00 to 2026-11-05 00:00:00 UTC (data from 2026-11-04 00:00:31 to 2026-11-04 16:21:24). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 184, approved 20, orders 20, paper fills 16, btc-speed events 154 and trades 184.
- Paper P&L to the end of the window: btc-speed +190.50 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 620 | 1462.25 | 0.00 | 40.7457 | 0.00 | 1693.50 | 0 | 0.00 | +190.5026 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 184 intents, 20 approved, 164 rejected: REDUCING 164.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

Latest distinct rejections:

| Time UTC | Strategy | Reason | Binding cap |
|---|---|---|---|
| 2026-11-04 16:16:47 | btc-speed | REDUCING: only exposure-reducing orders | - |

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | taker | 20 | 16 | 80 | 0.5000 | 1.0102 |

Merges of YES+NO pairs: 0; paper redemptions: 16.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| btc-speed | 5 s | 15 | +7.50c | +2.35c | 1 |
| btc-speed | 60 s | 15 | +4.87c | +3.05c | 1 |
| btc-speed | 300 s | 5 | -15.39c | +11.12c | 11 |

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

154 causal ETH moves (>= 6.0 bp in 2 s) and 184 trades sent to the kernel. Per mapped market: trade 184, ask above max price 52, ends too soon 36, already holding this market 18, no ask 14, move started before the window 3, too little size at ask 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-11-04 15:21:26 | +6.3 | 0x3dcf7415: trade; 0xeb89c131: trade |
| 2026-11-04 15:22:31 | +6.3 | 0x3dcf7415: trade; 0xeb89c131: trade |
| 2026-11-04 15:23:36 | -6.9 | 0x3dcf7415: trade; 0xeb89c131: trade |
| 2026-11-04 15:25:16 | +6.2 | 0xa51c418f: trade; 0xeb89c131: trade |
| 2026-11-04 15:27:09 | -6.9 | 0xa51c418f: trade; 0xeb89c131: trade |
| 2026-11-04 15:29:07 | +6.4 | 0xa51c418f: ends too soon; 0xeb89c131: ends too soon |
| 2026-11-04 15:30:48 | +6.8 | 0x8b08383d: trade; 0xb141338f: trade |
| 2026-11-04 15:32:36 | -6.9 | 0x8b08383d: trade; 0xb141338f: trade |
| 2026-11-04 15:33:38 | +6.0 | 0x8b08383d: trade; 0xb141338f: trade |
| 2026-11-04 15:34:43 | -6.1 | 0x8b08383d: ends too soon; 0xb141338f: trade |
| 2026-11-04 15:40:16 | +6.6 | 0x05dcb763: trade; 0xb141338f: trade |
| 2026-11-04 15:44:02 | +6.3 | 0x05dcb763: ends too soon; 0xb141338f: ends too soon |
| 2026-11-04 15:45:03 | -6.8 | 0x96207c3a: trade; 0xad4834c7: trade |
| 2026-11-04 15:47:40 | +7.9 | 0x96207c3a: trade; 0xad4834c7: trade |
| 2026-11-04 15:49:38 | +6.6 | 0x96207c3a: ends too soon; 0xad4834c7: trade |
| 2026-11-04 15:51:07 | -7.1 | 0xad4834c7: trade; 0xf84a9ec3: trade |
| 2026-11-04 15:52:35 | +6.0 | 0xad4834c7: trade; 0xf84a9ec3: trade |
| 2026-11-04 15:54:48 | -6.0 | 0xad4834c7: trade; 0xf84a9ec3: ends too soon |
| 2026-11-04 15:57:00 | +6.3 | 0x3c61c935: trade; 0xad4834c7: trade |
| 2026-11-04 16:00:02 | +6.5 | 0x3da262c4: trade; 0xcb6fdb82: trade |
| 2026-11-04 16:01:02 | -6.1 | 0x3da262c4: trade; 0xcb6fdb82: trade |
| 2026-11-04 16:02:15 | -6.9 | 0x3da262c4: trade; 0xcb6fdb82: trade |
| 2026-11-04 16:03:24 | +8.4 | 0x3da262c4: no ask; 0xcb6fdb82: trade |
| 2026-11-04 16:04:38 | +6.8 | 0x3da262c4: ends too soon; 0xcb6fdb82: trade |
| 2026-11-04 16:06:31 | +6.5 | 0x80fe3e78: trade; 0xcb6fdb82: trade |
| 2026-11-04 16:08:08 | +6.0 | 0x80fe3e78: ask above max price; 0xcb6fdb82: ask above max price |
| 2026-11-04 16:10:32 | -8.0 | 0x651acdaa: trade; 0xcb6fdb82: trade |
| 2026-11-04 16:12:22 | -6.6 | 0x651acdaa: trade; 0xcb6fdb82: trade |
| 2026-11-04 16:13:57 | -6.6 | 0x651acdaa: trade; 0xcb6fdb82: trade |
| 2026-11-04 16:16:47 | +6.6 | 0x25619559: trade; 0xeaac569f: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-04 15:27:09 | 0xa51c418f | 5m | 0.81 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:30:48 | 0x8b08383d | 5m | 0.72 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:30:48 | 0xb141338f | 15m | 0.62 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:32:36 | 0x8b08383d | 5m | 0.54 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:32:36 | 0xb141338f | 15m | 0.54 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:33:38 | 0x8b08383d | 5m | 0.74 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:33:38 | 0xb141338f | 15m | 0.54 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:34:43 | 0xb141338f | 15m | 0.44 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:40:16 | 0xb141338f | 15m | 0.57 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:40:16 | 0x05dcb763 | 5m | 0.59 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:45:03 | 0xad4834c7 | 15m | 0.52 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:45:03 | 0x96207c3a | 5m | 0.52 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:47:40 | 0xad4834c7 | 15m | 0.32 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:47:40 | 0x96207c3a | 5m | 0.12 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:49:38 | 0xad4834c7 | 15m | 0.58 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:51:07 | 0xad4834c7 | 15m | 0.6 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:51:07 | 0xf84a9ec3 | 5m | 0.79 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:52:35 | 0xad4834c7 | 15m | 0.33 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:52:35 | 0xf84a9ec3 | 5m | 0.11 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:54:48 | 0xad4834c7 | 15m | 0.78 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:57:00 | 0xad4834c7 | 15m | 0.14 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:57:00 | 0x3c61c935 | 5m | 0.41 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:00:02 | 0xcb6fdb82 | 15m | 0.65 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:00:02 | 0x3da262c4 | 5m | 0.7 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:01:02 | 0xcb6fdb82 | 15m | 0.19 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:01:02 | 0x3da262c4 | 5m | 0.07 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:02:15 | 0xcb6fdb82 | 15m | 0.23 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:02:15 | 0x3da262c4 | 5m | 0.05 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:03:24 | 0xcb6fdb82 | 15m | 0.82 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:04:38 | 0xcb6fdb82 | 15m | 0.81 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:06:31 | 0xcb6fdb82 | 15m | 0.84 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:06:31 | 0x80fe3e78 | 5m | 0.37 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:10:32 | 0xcb6fdb82 | 15m | 0.009 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:10:32 | 0x651acdaa | 5m | 0.25 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:12:22 | 0xcb6fdb82 | 15m | 0.003 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:12:22 | 0x651acdaa | 5m | 0.24 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:13:57 | 0xcb6fdb82 | 15m | 0.001 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:13:57 | 0x651acdaa | 5m | 0.05 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:16:47 | 0x25619559 | 5m | 0.59 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:16:47 | 0xeaac569f | 15m | 0.52 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 982, median 204, p90 221, min 182, max 482.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 546203, median of minute medians 0.0, worst minute p90 2.0, worst minute p99 3.6, max 77.0.
- Binance event time to local receive (network + clock offset): n 546203, median of minute medians -30.0, worst minute p90 1268.5, worst minute p99 4059.7, max 5800.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 535223, median of minute medians 11.2, worst minute p90 15.8, worst minute p99 101.7, max 273.0.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 154, median -25, p90 90, min -117, max 372.
- Local receive to decision: n 154, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 154, median 358, p90 372, min 332, max 632.

## Risk, reconciliation, invariants and audit

- Trips: 3: btc-speed REDUCING (strategy daily loss 5.02 USD > 5.00 (start of day 201.51), breaker:strategy); btc-speed ACTIVE (reset, human:DELL-auto); btc-speed REDUCING (strategy daily loss 5.04 USD > 5.00 (start of day 196.50), breaker:strategy).
- Human resets: 1; halts confirmed by zero open orders: 0.
- Reconciles: 196 (periodic 196); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 3464 records, head 7fe04ac68160c80e; last head anchored in the ledger: 3104 records, 4d498a17305ea3e9 (startup, 2026-11-03 11:52:50).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 615 | 200 / 100 | 25.77 | 0 |

Elapsed since the first run: 23.87 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-11-04 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-11-04.md --title "paper_ethb day 25: 2026-11-04 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **MET.**

- Days without a violation: **25 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **12 of 12** (need 5+, all clean)
- Running time: 333.5 hours (13.90 days of 24 h)

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
| 2026-11-04 | 16.4 |
