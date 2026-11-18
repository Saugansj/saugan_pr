# paper_ethb day 12: 2026-10-22 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-10-22 00:00:00 to 2026-10-23 00:00:00 UTC (data from 2026-10-22 00:00:22 to 2026-10-22 16:20:30). Paper only: no order ever left this PC.

## Summary

- Runs started: 1; clean shutdowns: 0; still running or ended by a crash or kill: 1 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 32, approved 6, orders 6, paper fills 6, btc-speed events 35 and trades 32.
- Paper P&L to the end of the window: btc-speed +127.69 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 294 | 637.02 | 0.00 | 18.7850 | 0.00 | 783.50 | 0 | 0.00 | +127.6930 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 32 intents, 6 approved, 26 rejected: REDUCING 26.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

Latest distinct rejections:

| Time UTC | Strategy | Reason | Binding cap |
|---|---|---|---|
| 2026-10-22 16:16:47 | btc-speed | REDUCING: only exposure-reducing orders | - |

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | taker | 6 | 6 | 30 | 0.5750 | 0.4354 |

Merges of YES+NO pairs: 0; paper redemptions: 6.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| btc-speed | 5 s | 6 | +2.83c | +2.67c | 0 |
| btc-speed | 60 s | 6 | +0.50c | +8.12c | 0 |
| btc-speed | 300 s | 2 | -28.48c | +20.02c | 4 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-v4-eth-bybit**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 291 in 291 markets (needs 200), unresolved 0, mean 0.4388 USD, cluster SE 0.1274, total +127.6930 USD. Verdict: **PASS**.
- **Paper-fill realism** (btc-speed at real tape prices): 242 of 291 resolved trades repriced at what real takers paid in our order's second. Paper +120.11 USD -> best case +61.26 (cheapest real price), typical +20.79 (median real price), **live estimate +26.65** (our order behind the real takers that beat us, partial fills; 68% of our shares filled); real takers paid a median +6.0c over our fill. Paper assumes we win every race for the cheapest ask. Not comparable with reports before 15 Oct.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-11 19:34:32), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-11 19:34:32), `btc-speed-v4-eth-bybit` (sha256 04680de003a175aa, written 2026-10-11 19:34:32).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

35 causal ETH moves (>= 6.0 bp in 2 s) and 32 trades sent to the kernel. Per mapped market: trade 32, ask above max price 14, already holding this market 10, ends too soon 7, no ask 4, move started before the window 2, too little size at ask 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-22 01:42:22 | -6.4 | 0x910df502: no ask; 0x9e86ae70: ask above max price |
| 2026-10-22 02:00:52 | -6.1 | 0x0fe17db3: trade; 0xf14fead9: trade |
| 2026-10-22 02:21:28 | -6.0 | 0xb456928a: ask above max price; 0xec70ffa4: trade |
| 2026-10-22 02:25:11 | -6.4 | 0x12e3774a: trade; 0xb456928a: ask above max price |
| 2026-10-22 02:27:57 | -6.6 | 0x12e3774a: ask above max price; 0xb456928a: no ask |
| 2026-10-22 03:39:54 | +7.0 | 0x48c4921a: ends too soon; 0x8a5de847: trade |
| 2026-10-22 13:13:09 | -7.2 | 0x524827b2: ask above max price; 0xc74dd621: trade |
| 2026-10-22 13:31:19 | -6.3 | 0x9736edc4: ask above max price; 0xfcc5da41: trade |
| 2026-10-22 13:34:49 | +6.3 | 0x9736edc4: ends too soon; 0xfcc5da41: already holding this market |
| 2026-10-22 13:36:46 | +6.0 | 0x023d4628: trade; 0xfcc5da41: already holding this market |
| 2026-10-22 13:39:01 | -6.7 | 0x023d4628: already holding this market; 0xfcc5da41: already holding this market |
| 2026-10-22 13:40:41 | +6.2 | 0xac6935b4: trade; 0xfcc5da41: already holding this market |
| 2026-10-22 13:41:43 | +6.6 | 0xac6935b4: already holding this market; 0xfcc5da41: already holding this market |
| 2026-10-22 13:45:01 | -6.2 | 0x63eabfe9: move started before the window; 0x84cacf08: move started before the window |
| 2026-10-22 13:49:38 | +6.3 | 0x63eabfe9: trade; 0x84cacf08: ends too soon |
| 2026-10-22 13:50:55 | -6.0 | 0x63eabfe9: already holding this market; 0xddc8a60c: trade |
| 2026-10-22 13:53:52 | +6.4 | 0x63eabfe9: already holding this market; 0xddc8a60c: already holding this market |
| 2026-10-22 14:21:38 | +6.1 | 0x434ab4e1: trade; 0xbcf7c600: ask above max price |
| 2026-10-22 14:41:14 | +6.6 | 0x50321a3c: ask above max price; 0x9f9077da: trade |
| 2026-10-22 14:44:38 | +6.0 | 0x50321a3c: ends too soon; 0x9f9077da: ends too soon |
| 2026-10-22 14:48:10 | -6.3 | 0x17e44177: no ask; 0xe7d8705d: trade |
| 2026-10-22 15:11:01 | -6.0 | 0x6f995cb1: ask above max price; 0xe92de85a: too little size at ask |
| 2026-10-22 15:12:23 | -6.8 | 0x6f995cb1: no ask; 0xe92de85a: ask above max price |
| 2026-10-22 15:16:51 | +6.1 | 0x81b40643: trade; 0xdc75ae6f: trade |
| 2026-10-22 15:19:19 | +6.0 | 0x81b40643: ends too soon; 0xdc75ae6f: trade |
| 2026-10-22 15:22:32 | -6.4 | 0x59d3f545: trade; 0xdc75ae6f: trade |
| 2026-10-22 15:31:43 | -6.3 | 0x6df053aa: trade; 0xe241cd97: trade |
| 2026-10-22 15:40:36 | -6.4 | 0x80c7f3ea: trade; 0xe241cd97: trade |
| 2026-10-22 15:42:02 | +7.0 | 0x80c7f3ea: trade; 0xe241cd97: trade |
| 2026-10-22 16:16:47 | -6.1 | 0x5cd038f1: trade; 0xb7869cd3: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-22 00:00:22 | 0x22d31d9c | 5m | 0.2 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 00:00:22 | 0x858a07b8 | 15m | 0.31 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 01:01:03 | 0x3663edd7 | 15m | 0.75 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 01:39:04 | 0x910df502 | 15m | 0.01 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 01:40:14 | 0x9e86ae70 | 5m | 0.49 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 02:00:52 | 0x0fe17db3 | 15m | 0.53 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 02:00:52 | 0xf14fead9 | 5m | 0.57 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 02:21:28 | 0xec70ffa4 | 5m | 0.59 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 02:25:11 | 0x12e3774a | 5m | 0.48 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 03:39:54 | 0x8a5de847 | 15m | 0.63 | approved | open | 5 | 0.630 | 0.0816 | 1.7684 |
| 2026-10-22 13:13:09 | 0xc74dd621 | 5m | 0.7 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 13:31:19 | 0xfcc5da41 | 15m | 0.72 | approved | open | 5 | 0.720 | 0.0706 | -3.6706 |
| 2026-10-22 13:36:46 | 0x023d4628 | 5m | 0.43 | approved | open | 5 | 0.530 | 0.0872 | -2.7372 |
| 2026-10-22 13:40:41 | 0xac6935b4 | 5m | 0.54 | approved | open | 5 | 0.560 | 0.0862 | 2.1138 |
| 2026-10-22 13:49:38 | 0x63eabfe9 | 15m | 0.17 | approved | open | 5 | 0.200 | 0.0560 | 3.9440 |
| 2026-10-22 13:50:55 | 0xddc8a60c | 5m | 0.81 | approved | open | 5 | 0.810 | 0.0539 | -4.1039 |
| 2026-10-22 14:21:38 | 0x434ab4e1 | 15m | 0.78 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 14:41:14 | 0x9f9077da | 5m | 0.66 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 14:48:10 | 0xe7d8705d | 15m | 0.84 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 15:16:51 | 0x81b40643 | 5m | 0.36 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 15:16:51 | 0xdc75ae6f | 15m | 0.41 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 15:19:19 | 0xdc75ae6f | 15m | 0.77 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 15:22:32 | 0xdc75ae6f | 15m | 0.22 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 15:22:32 | 0x59d3f545 | 5m | 0.71 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 15:31:43 | 0xe241cd97 | 15m | 0.63 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 15:31:43 | 0x6df053aa | 5m | 0.76 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 15:40:36 | 0xe241cd97 | 15m | 0.62 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 15:40:36 | 0x80c7f3ea | 5m | 0.67 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 15:42:02 | 0xe241cd97 | 15m | 0.18 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 15:42:02 | 0x80c7f3ea | 5m | 0.16 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 16:16:47 | 0xb7869cd3 | 5m | 0.22 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-22 16:16:47 | 0x5cd038f1 | 15m | 0.37 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 510, median 218, p90 255, min 184, max 449.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 186259, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 2.3, max 51.0.
- Binance event time to local receive (network + clock offset): n 186259, median of minute medians -32.0, worst minute p90 3918.0, worst minute p99 7482.2, max 8956.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 278265, median of minute medians 9.6, worst minute p90 147.2, worst minute p99 151.7, max 358.2.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 35, median 3, p90 58, min -266, max 325.
- Local receive to decision: n 35, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 35, median 376, p90 435, min 345, max 459.

## Risk, reconciliation, invariants and audit

- Trips: 6: btc-speed ACTIVE (reset, human:DELL-auto); global REDUCING (stale feed polymarket:crypto-fast: 60045 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 60045 ms, breaker:stale_feed); global REDUCING (restart: stale feed polymarket: 60045 ms, loop:restart); global ACTIVE (reset, human:DELL-feed); btc-speed REDUCING (strategy daily loss 5.19 USD > 5.00 (start of day 130.38), breaker:strategy).
- Human resets: 81; halts confirmed by zero open orders: 0.
- Reconciles: 103 (periodic 102, startup 1); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 1526 records, head 592389050a4ed9d5; last head anchored in the ledger: 1485 records, 37ffb6c17c971b9c (startup, 2026-10-22 13:08:18).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 291 | 200 / 100 | 26.78 | 0 |

Elapsed since the first run: 10.87 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-10-22 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-10-22.md --title "paper_ethb day 12: 2026-10-22 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **12 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **9 of 9** (need 5+, all clean)
- Running time: 113.8 hours (4.74 days of 24 h)

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
| 2026-10-22 | 8.5 |
