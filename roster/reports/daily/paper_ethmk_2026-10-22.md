# paper_ethmk day 3: 2026-10-22 (UTC)

Ledger `data/trader/paper_ethmk`, window 2026-10-22 00:00:00 to 2026-10-23 00:00:00 UTC (data from 2026-10-22 00:00:22 to 2026-10-22 16:20:24). Paper only: no order ever left this PC.

## Summary

- Runs started: 1; clean shutdowns: 0; still running or ended by a crash or kill: 1 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 18, approved 18, orders 18, paper fills 0, btc-speed events 35 and trades 18.
- Paper P&L to the end of the window: no fills yet.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 18 intents, 18 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | maker | 18 | 0 | 0 | - | 0.0000 |

Merges of YES+NO pairs: 0; paper redemptions: 0.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| - | - | 0 | - | - | - |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-mk-eth-bybit**: P&L per trade in USD held to resolution: size * (outcome - fill price), maker (no fee). Resolved trades 0 in 0 markets (needs 200), unresolved 0, mean - USD, cluster SE -, total +0.0000 USD. Verdict: **running (0 of 200)**.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-20 13:10:40), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-20 13:10:40), `btc-speed-mk-eth-bybit` (sha256 3ee8f1e109811bdc, written 2026-10-20 13:10:40).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

35 causal ETH moves (>= 6.0 bp in 2 s) and 18 trades sent to the kernel. Per mapped market: trade 18, ends too soon 13, ask above max price 3, move started before the window 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-22 01:42:22 | -6.4 | 0x910df502: ends too soon |
| 2026-10-22 02:00:52 | -6.1 | 0x0fe17db3: trade |
| 2026-10-22 02:21:28 | -6.0 | 0xb456928a: ask above max price |
| 2026-10-22 02:25:11 | -6.4 | 0xb456928a: ends too soon |
| 2026-10-22 02:27:57 | -6.6 | 0xb456928a: ends too soon |
| 2026-10-22 03:39:54 | +7.0 | 0x8a5de847: trade |
| 2026-10-22 13:13:09 | -7.2 | 0x524827b2: ends too soon |
| 2026-10-22 13:31:19 | -6.3 | 0xfcc5da41: trade |
| 2026-10-22 13:34:49 | +6.3 | 0xfcc5da41: trade |
| 2026-10-22 13:36:46 | +6.0 | 0xfcc5da41: trade |
| 2026-10-22 13:39:01 | -6.7 | 0xfcc5da41: trade |
| 2026-10-22 13:40:41 | +6.2 | 0xfcc5da41: ends too soon |
| 2026-10-22 13:41:43 | +6.6 | 0xfcc5da41: ends too soon |
| 2026-10-22 13:45:01 | -6.2 | 0x63eabfe9: move started before the window |
| 2026-10-22 13:49:38 | +6.3 | 0x63eabfe9: trade |
| 2026-10-22 13:50:55 | -6.0 | 0x63eabfe9: ask above max price |
| 2026-10-22 13:53:52 | +6.4 | 0x63eabfe9: trade |
| 2026-10-22 14:21:38 | +6.1 | 0x434ab4e1: trade |
| 2026-10-22 14:41:14 | +6.6 | 0x50321a3c: ends too soon |
| 2026-10-22 14:44:38 | +6.0 | 0x50321a3c: ends too soon |
| 2026-10-22 14:48:10 | -6.3 | 0xe7d8705d: trade |
| 2026-10-22 15:11:01 | -6.0 | 0x6f995cb1: ends too soon |
| 2026-10-22 15:12:23 | -6.8 | 0x6f995cb1: ends too soon |
| 2026-10-22 15:16:51 | +6.1 | 0xdc75ae6f: trade |
| 2026-10-22 15:19:19 | +6.0 | 0xdc75ae6f: trade |
| 2026-10-22 15:22:32 | -6.4 | 0xdc75ae6f: trade |
| 2026-10-22 15:31:43 | -6.3 | 0xe241cd97: trade |
| 2026-10-22 15:40:36 | -6.4 | 0xe241cd97: ends too soon |
| 2026-10-22 15:42:02 | +7.0 | 0xe241cd97: ends too soon |
| 2026-10-22 16:16:47 | -6.1 | 0x5cd038f1: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-22 00:00:22 | 0x858a07b8 | 15m | 0.31 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-22 01:01:03 | 0x3663edd7 | 15m | 0.75 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-22 01:39:04 | 0x910df502 | 15m | 0.01 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-22 02:00:52 | 0x0fe17db3 | 15m | 0.53 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-22 03:39:54 | 0x8a5de847 | 15m | 0.63 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-22 13:31:19 | 0xfcc5da41 | 15m | 0.72 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-22 13:34:49 | 0xfcc5da41 | 15m | 0.79 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-22 13:36:46 | 0xfcc5da41 | 15m | 0.77 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-22 13:39:01 | 0xfcc5da41 | 15m | 0.6 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-22 13:49:38 | 0x63eabfe9 | 15m | 0.17 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-22 13:53:52 | 0x63eabfe9 | 15m | 0.1 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-22 14:21:38 | 0x434ab4e1 | 15m | 0.78 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-22 14:48:10 | 0xe7d8705d | 15m | 0.84 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-22 15:16:51 | 0xdc75ae6f | 15m | 0.41 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-22 15:19:19 | 0xdc75ae6f | 15m | 0.77 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-22 15:22:32 | 0xdc75ae6f | 15m | 0.22 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-22 15:31:43 | 0xe241cd97 | 15m | 0.63 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-22 16:16:47 | 0x5cd038f1 | 15m | 0.37 | approved | open | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 510, median 220, p90 257, min 182, max 494.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 185976, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 3.1, max 47.0.
- Binance event time to local receive (network + clock offset): n 185976, median of minute medians -32.0, worst minute p90 3646.7, worst minute p99 7388.9, max 8956.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 277942, median of minute medians 9.7, worst minute p90 218.7, worst minute p99 218.7, max 362.7.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 35, median 3, p90 58, min -266, max 326.
- Local receive to decision: n 35, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 35, median 376, p90 423, min 345, max 644.

## Risk, reconciliation, invariants and audit

- Trips: 4: global REDUCING (stale feed polymarket:crypto-fast: 60700 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 60700 ms, breaker:stale_feed); global REDUCING (restart: stale feed polymarket: 60700 ms, loop:restart); global ACTIVE (reset, human:DELL-feed).
- Human resets: 52; halts confirmed by zero open orders: 0.
- Reconciles: 103 (periodic 102, startup 1); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 320 records, head d3a27d6215ad84b2; last head anchored in the ledger: 278 records, 32be13c0879007b5 (startup, 2026-10-22 13:09:13).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-mk-eth-bybit | 0 | 200 / 100 | 0.00 | no evidence yet |

Elapsed since the first run: 2.13 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethmk --date 2026-10-22 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethmk_2026-10-22.md --title "paper_ethmk day 3: 2026-10-22 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **3 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **1 of 1** (need 5+, all clean)
- Running time: 33.6 hours (1.40 days of 24 h)

| UTC day | Hours running |
|---|---|
| 2026-10-20 | 7.5 |
| 2026-10-21 | 17.6 |
| 2026-10-22 | 8.5 |
