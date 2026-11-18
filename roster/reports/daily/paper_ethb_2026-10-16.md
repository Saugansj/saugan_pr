# paper_ethb day 6: 2026-10-16 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-10-16 00:00:00 to 2026-10-17 00:00:00 UTC (data from 2026-10-16 04:56:35 to 2026-10-16 16:21:11). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 47, approved 7, orders 7, paper fills 7, btc-speed events 45 and trades 47.
- Paper P&L to the end of the window: btc-speed +133.65 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 247 | 524.22 | 0.00 | 15.6375 | 0.00 | 673.50 | 0 | 0.00 | +133.6455 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 47 intents, 7 approved, 40 rejected: REDUCING 40.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

Latest distinct rejections:

| Time UTC | Strategy | Reason | Binding cap |
|---|---|---|---|
| 2026-10-16 15:55:58 | btc-speed | REDUCING: only exposure-reducing orders | - |

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | taker | 7 | 7 | 35 | 0.5900 | 0.4592 |

Merges of YES+NO pairs: 0; paper redemptions: 7.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| btc-speed | 5 s | 7 | +1.30c | +2.57c | 0 |
| btc-speed | 60 s | 7 | -2.24c | +7.59c | 0 |
| btc-speed | 300 s | 3 | -0.17c | +15.76c | 4 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-v4-eth-bybit**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 245 in 245 markets (needs 200), unresolved 0, mean 0.5455 USD, cluster SE 0.1360, total +133.6455 USD. Verdict: **PASS**.
- **Paper-fill realism** (btc-speed at real tape prices): 206 of 245 resolved trades repriced at what real takers paid in our order's second. Paper +117.95 USD -> best case +61.49 (cheapest real price), typical +21.06 (median real price), **live estimate +23.72** (our order behind the real takers that beat us, partial fills; 64% of our shares filled); real takers paid a median +7.0c over our fill. Paper assumes we win every race for the cheapest ask. Not comparable with reports before 15 Oct.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-11 19:34:32), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-11 19:34:32), `btc-speed-v4-eth-bybit` (sha256 04680de003a175aa, written 2026-10-11 19:34:32).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

45 causal ETH moves (>= 6.0 bp in 2 s) and 47 trades sent to the kernel. Per mapped market: trade 47, ask above max price 20, ends too soon 8, no ask 5, already holding this market 2, stale book 2, too little size at ask 1, move started before the window 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-16 12:01:55 | -7.1 | 0x4a93fac9: trade; 0x8a8d8e47: trade |
| 2026-10-16 12:15:12 | -6.3 | 0xb65c22bc: trade; 0xf588c7d9: trade |
| 2026-10-16 12:17:27 | -6.4 | 0xb65c22bc: trade; 0xf588c7d9: trade |
| 2026-10-16 12:19:00 | +6.6 | 0xb65c22bc: too little size at ask; 0xf588c7d9: ends too soon |
| 2026-10-16 12:20:48 | +8.1 | 0xb65c22bc: trade; 0xce918c97: trade |
| 2026-10-16 13:10:13 | -6.3 | 0x5102224d: trade; 0xc2843d76: trade |
| 2026-10-16 13:23:54 | -6.2 | 0x6b663679: trade; 0x9e97fd7d: trade |
| 2026-10-16 13:30:09 | -6.4 | 0x7353d6c4: trade; 0xdbec76df: trade |
| 2026-10-16 13:31:23 | -6.1 | 0x7353d6c4: trade; 0xdbec76df: trade |
| 2026-10-16 13:32:29 | -6.3 | 0x7353d6c4: ask above max price; 0xdbec76df: trade |
| 2026-10-16 13:34:33 | +6.7 | 0x7353d6c4: ends too soon; 0xdbec76df: trade |
| 2026-10-16 13:45:58 | -6.4 | 0x553fdd45: trade; 0x674acc80: trade |
| 2026-10-16 13:50:28 | -6.2 | 0x674acc80: ask above max price; 0xd62cff92: trade |
| 2026-10-16 14:03:22 | +6.1 | 0x8438ef1d: trade; 0xdf1299c8: trade |
| 2026-10-16 14:14:04 | +9.0 | 0xc8ac27e3: ends too soon; 0xdf1299c8: ends too soon |
| 2026-10-16 14:16:47 | +6.5 | 0x589cbd04: ask above max price; 0xa930a992: trade |
| 2026-10-16 14:20:00 | +7.0 | 0x077df4e2: move started before the window; 0xa930a992: ask above max price |
| 2026-10-16 14:28:51 | +7.1 | 0x12295244: trade; 0xa930a992: ask above max price |
| 2026-10-16 14:47:46 | +6.4 | 0x6c0b32e9: trade; 0x70ccf871: trade |
| 2026-10-16 14:53:53 | -6.0 | 0x6c0b32e9: ask above max price; 0xfc1a690b: no ask |
| 2026-10-16 15:05:22 | -6.1 | 0x2947a220: ask above max price; 0xf69c2d98: trade |
| 2026-10-16 15:06:23 | -6.0 | 0x2947a220: stale book; 0xf69c2d98: stale book |
| 2026-10-16 15:07:35 | +6.2 | 0x2947a220: trade; 0xf69c2d98: trade |
| 2026-10-16 15:11:14 | +6.8 | 0x2947a220: trade; 0xc920cae0: ask above max price |
| 2026-10-16 15:12:44 | +6.8 | 0x2947a220: trade; 0xc920cae0: ask above max price |
| 2026-10-16 15:15:26 | -7.8 | 0xdd35e7a7: trade; 0xf2799f3c: trade |
| 2026-10-16 15:25:07 | -6.4 | 0xae3f9bb3: trade; 0xf2799f3c: ask above max price |
| 2026-10-16 15:45:44 | -6.3 | 0x460fc409: trade; 0xf0e47dae: trade |
| 2026-10-16 15:50:51 | -7.0 | 0x018b8b03: ask above max price; 0x460fc409: ask above max price |
| 2026-10-16 15:55:58 | -6.8 | 0x460fc409: ask above max price; 0xc3dfe227: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-16 11:35:51 | 0x54d49693 | 15m | 0.08 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 11:35:51 | 0x0ddd51c2 | 5m | 0.41 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 12:01:55 | 0x4a93fac9 | 15m | 0.61 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 12:01:55 | 0x8a8d8e47 | 5m | 0.74 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 12:15:12 | 0xb65c22bc | 15m | 0.61 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 12:15:12 | 0xf588c7d9 | 5m | 0.71 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 12:17:27 | 0xb65c22bc | 15m | 0.44 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 12:17:27 | 0xf588c7d9 | 5m | 0.33 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 12:20:48 | 0xb65c22bc | 15m | 0.8 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 12:20:48 | 0xce918c97 | 5m | 0.61 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 13:10:13 | 0x5102224d | 15m | 0.65 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 13:10:13 | 0xc2843d76 | 5m | 0.28 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 13:23:54 | 0x9e97fd7d | 15m | 0.71 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 13:23:54 | 0x6b663679 | 5m | 0.11 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 13:30:09 | 0x7353d6c4 | 5m | 0.26 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 13:30:09 | 0xdbec76df | 15m | 0.34 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 13:31:23 | 0x7353d6c4 | 5m | 0.77 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 13:31:23 | 0xdbec76df | 15m | 0.66 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 13:32:29 | 0xdbec76df | 15m | 0.7 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 13:34:33 | 0xdbec76df | 15m | 0.27 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 13:45:58 | 0x674acc80 | 15m | 0.56 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 13:45:58 | 0x553fdd45 | 5m | 0.63 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 13:50:28 | 0xd62cff92 | 5m | 0.59 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 14:03:22 | 0xdf1299c8 | 15m | 0.6 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 14:03:22 | 0x8438ef1d | 5m | 0.75 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 14:16:47 | 0xa930a992 | 15m | 0.74 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 14:28:51 | 0x12295244 | 5m | 0.05 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 14:47:46 | 0x70ccf871 | 5m | 0.57 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 14:47:46 | 0x6c0b32e9 | 15m | 0.52 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 15:05:22 | 0xf69c2d98 | 5m | 0.7 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 15:07:35 | 0x2947a220 | 15m | 0.03 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 15:07:35 | 0xf69c2d98 | 5m | 0.01 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 15:11:14 | 0x2947a220 | 15m | 0.039 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 15:12:44 | 0x2947a220 | 15m | 0.006 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 15:15:26 | 0xdd35e7a7 | 5m | 0.43 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 15:15:26 | 0xf2799f3c | 15m | 0.48 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 15:25:07 | 0xae3f9bb3 | 5m | 0.31 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 15:45:44 | 0xf0e47dae | 5m | 0.55 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 15:45:44 | 0x460fc409 | 15m | 0.52 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-16 15:55:58 | 0xc3dfe227 | 5m | 0.57 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 685, median 251, p90 297, min 222, max 788.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 248283, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 9.0, max 525.0.
- Binance event time to local receive (network + clock offset): n 248283, median of minute medians -71.0, worst minute p90 1696.4, worst minute p99 2961.0, max 3058.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 378912, median of minute medians 9.1, worst minute p90 17.5, worst minute p99 23309325.8, max 21190692.7.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 45, median -77, p90 104, min -177, max 259.
- Local receive to decision: n 45, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 45, median 407, p90 446, min 382, max 681.

## Risk, reconciliation, invariants and audit

- Trips: 5: global ACTIVE (reset, human:DELL-feed); global REDUCING (stale feed polymarket:crypto-fast: 60364 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 240421 ms, breaker:stale_feed); global ACTIVE (reset, human:DELL-feed); btc-speed REDUCING (strategy daily loss 5.01 USD > 5.00 (start of day 139.75), breaker:strategy).
- Human resets: 20; halts confirmed by zero open orders: 0.
- Reconciles: 137 (periodic 137); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 1111 records, head bfee32c08bee84ca; last head anchored in the ledger: 763 records, 062ce1de6c686c06 (startup, 2026-10-15 11:10:14).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 245 | 200 / 100 | 50.35 | 0 |

Elapsed since the first run: 4.87 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-10-16 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-10-16.md --title "paper_ethb day 6: 2026-10-16 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **6 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **7 of 7** (need 5+, all clean)
- Running time: 73.3 hours (3.06 days of 24 h)

| UTC day | Hours running |
|---|---|
| 2026-10-11 | 1.1 |
| 2026-10-12 | 15.4 |
| 2026-10-13 | 16.7 |
| 2026-10-14 | 16.0 |
| 2026-10-15 | 12.8 |
| 2026-10-16 | 11.4 |
