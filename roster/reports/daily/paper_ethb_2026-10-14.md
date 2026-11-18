# paper_ethb day 4: 2026-10-14 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-10-14 00:00:00 to 2026-10-15 00:00:00 UTC (data from 2026-10-14 02:04:01 to 2026-10-14 16:21:46). Paper only: no order ever left this PC.

## Summary

- Runs started: 1; clean shutdowns: 0; still running or ended by a crash or kill: 1 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 63, approved 62, orders 62, paper fills 63, btc-speed events 79 and trades 63.
- Paper P&L to the end of the window: btc-speed +127.80 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 163 | 335.68 | 0.00 | 10.0179 | 0.00 | 473.50 | 0 | 0.00 | +127.8021 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 63 intents, 62 approved, 1 rejected: over strategy 1.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

Latest distinct rejections:

| Time UTC | Strategy | Reason | Binding cap |
|---|---|---|---|
| 2026-10-14 12:46:37 | btc-speed | over strategy:btc-speed: needs 2.80, room 2.25 | strategy:btc-speed |

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | taker | 62 | 63 | 310 | 0.4500 | 4.1000 |

Merges of YES+NO pairs: 0; paper redemptions: 62.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| btc-speed | 5 s | 62 | +6.69c | +1.50c | 1 |
| btc-speed | 60 s | 60 | +10.55c | +2.79c | 3 |
| btc-speed | 300 s | 21 | +6.39c | +3.66c | 42 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-v4-eth-bybit**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 162 in 162 markets (needs 200), unresolved 0, mean 0.7889 USD, cluster SE 0.1574, total +127.8021 USD. Verdict: **running (162 of 200)**.
- **Paper-fill realism** (btc-speed at real tape prices): 144 of 162 resolved trades repriced at what real takers paid in our order's second. Paper +126.00 USD -> best case +87.57 (cheapest real price), typical +39.63 (median real price), **live estimate +26.50** (median real price within our limit, else missed); real takers paid a median +9.0c over our fill. Paper assumes we win every race for the cheapest ask.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-11 19:34:32), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-11 19:34:32), `btc-speed-v4-eth-bybit` (sha256 04680de003a175aa, written 2026-10-11 19:34:32).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

79 causal ETH moves (>= 6.0 bp in 2 s) and 63 trades sent to the kernel. Per mapped market: already holding this market 74, trade 63, ends too soon 9, ask above max price 7, move started before the window 2, no ask 2, too little size at ask 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-14 13:58:47 | -7.2 | 0x31cba18e: already holding this market; 0x43c82637: already holding this market |
| 2026-10-14 13:59:55 | -8.3 | 0x31cba18e: already holding this market; 0x43c82637: already holding this market |
| 2026-10-14 14:01:00 | -6.1 | 0x36c2312a: trade; 0x962449e1: trade |
| 2026-10-14 14:02:13 | -7.1 | 0x36c2312a: already holding this market; 0x962449e1: already holding this market |
| 2026-10-14 14:03:39 | +6.1 | 0x36c2312a: already holding this market; 0x962449e1: already holding this market |
| 2026-10-14 14:04:40 | -6.0 | 0x36c2312a: already holding this market; 0x962449e1: already holding this market |
| 2026-10-14 14:05:43 | +6.3 | 0x0efb6c8e: trade; 0x962449e1: already holding this market |
| 2026-10-14 14:07:19 | +6.9 | 0x0efb6c8e: already holding this market; 0x962449e1: already holding this market |
| 2026-10-14 14:08:39 | -6.0 | 0x0efb6c8e: already holding this market; 0x962449e1: already holding this market |
| 2026-10-14 14:11:04 | -6.1 | 0x962449e1: already holding this market; 0xb4561098: too little size at ask |
| 2026-10-14 14:14:16 | +6.0 | 0x962449e1: already holding this market; 0xb4561098: ends too soon |
| 2026-10-14 14:19:58 | -6.1 | 0x19c29b5a: trade; 0xdae37074: ends too soon |
| 2026-10-14 14:21:48 | +6.0 | 0x19c29b5a: already holding this market; 0xad9688b1: trade |
| 2026-10-14 14:27:01 | +6.2 | 0x19c29b5a: already holding this market; 0xfcced14f: trade |
| 2026-10-14 14:31:15 | -6.1 | 0x50d89d58: trade; 0x883c9e59: trade |
| 2026-10-14 14:37:11 | +6.6 | 0x44822644: trade; 0x883c9e59: already holding this market |
| 2026-10-14 14:40:54 | +6.6 | 0x41c9d3f1: trade; 0x883c9e59: already holding this market |
| 2026-10-14 14:42:58 | -6.5 | 0x41c9d3f1: already holding this market; 0x883c9e59: already holding this market |
| 2026-10-14 14:59:25 | +7.9 | 0x9792a9b4: ends too soon; 0xa1884996: ends too soon |
| 2026-10-14 15:03:03 | -7.2 | 0x7199c6af: trade; 0xd4bc056b: trade |
| 2026-10-14 15:05:48 | -8.0 | 0x484182ab: trade; 0xd4bc056b: already holding this market |
| 2026-10-14 15:08:04 | -6.4 | 0x484182ab: already holding this market; 0xd4bc056b: already holding this market |
| 2026-10-14 15:13:48 | +6.7 | 0x16579274: no ask; 0xd4bc056b: already holding this market |
| 2026-10-14 15:16:20 | +6.0 | 0x5d460b87: trade; 0x8b679268: ask above max price |
| 2026-10-14 15:17:30 | +6.2 | 0x5d460b87: already holding this market; 0x8b679268: no ask |
| 2026-10-14 15:19:27 | -6.6 | 0x5d460b87: already holding this market; 0x8b679268: ends too soon |
| 2026-10-14 15:23:36 | -6.0 | 0x5d460b87: already holding this market; 0x7b15381b: ask above max price |
| 2026-10-14 15:38:45 | -8.3 | 0xa69462a9: ask above max price; 0xdca714b4: trade |
| 2026-10-14 15:40:32 | -6.4 | 0xcc22b60e: trade; 0xdca714b4: already holding this market |
| 2026-10-14 15:59:11 | -6.7 | 0xb7271ce7: ends too soon; 0xe1d8fce7: ends too soon |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-14 09:57:10 | 0xb73cc1dc | 5m | 0.21 | approved | open | 5 | 0.200 | 0.0560 | 3.9440 |
| 2026-10-14 10:03:15 | 0x2aabc1b1 | 15m | 0.81 | approved | open | 5 | 0.790 | 0.0581 | 0.9919 |
| 2026-10-14 10:05:31 | 0xfe754fcd | 5m | 0.39 | approved | open | 5 | 0.360 | 0.0806 | 3.1194 |
| 2026-10-14 11:45:41 | 0x1fe4cc13 | 15m | 0.29 | approved | open | 5 | 0.290 | 0.0721 | -1.5221 |
| 2026-10-14 11:45:41 | 0x2d883d50 | 5m | 0.17 | approved | open | 5 | 0.170 | 0.0494 | -0.8994 |
| 2026-10-14 12:28:55 | 0x8ecc0cf7 | 15m | 0.44 | approved | open | 5 | 0.533 | 0.0871 | 2.2479 |
| 2026-10-14 12:28:55 | 0xe40d937f | 5m | 0.01 | approved | open | 5 | 0.010 | 0.0035 | -0.0535 |
| 2026-10-14 12:31:02 | 0x02bf99db | 5m | 0.06 | approved | open | 5 | 0.070 | 0.0228 | -0.3728 |
| 2026-10-14 12:31:02 | 0xab91db52 | 15m | 0.11 | approved | open | 5 | 0.110 | 0.0343 | -0.5843 |
| 2026-10-14 12:35:32 | 0x72e66df1 | 5m | 0.54 | approved | open | 5 | 0.540 | 0.0869 | -2.7869 |
| 2026-10-14 12:40:26 | 0xe6b0e04e | 5m | 0.65 | approved | open | 5 | 0.650 | 0.0796 | 1.6704 |
| 2026-10-14 12:46:37 | 0x864949e0 | 15m | 0.45 | approved | open | 5 | 0.450 | 0.0866 | 2.6634 |
| 2026-10-14 12:46:37 | 0x61064737 | 5m | 0.46 | over strategy:btc-speed: needs 2.80, room 2.25 | - | 0 | - | 0.0000 | unresolved |
| 2026-10-14 12:52:36 | 0x8bdec90a | 5m | 0.15 | approved | open | 5 | 0.140 | 0.0421 | 4.2579 |
| 2026-10-14 12:56:30 | 0x8a9fb609 | 5m | 0.44 | approved | open | 5 | 0.430 | 0.0858 | 2.7642 |
| 2026-10-14 13:01:35 | 0x42a94fba | 5m | 0.61 | approved | open | 5 | 0.610 | 0.0833 | 1.8667 |
| 2026-10-14 13:01:35 | 0x5dce929d | 15m | 0.6 | approved | open | 5 | 0.610 | 0.0833 | -3.1333 |
| 2026-10-14 13:20:30 | 0x2b1e40d7 | 15m | 0.73 | approved | open | 5 | 0.730 | 0.0690 | -3.7190 |
| 2026-10-14 13:20:30 | 0xeaefd2b9 | 5m | 0.66 | approved | open | 5 | 0.660 | 0.0785 | 1.6215 |
| 2026-10-14 13:30:27 | 0xa642372a | 5m | 0.82 | approved | open | 5 | 0.840 | 0.0470 | 0.7530 |
| 2026-10-14 13:30:27 | 0x3ab56529 | 15m | 0.7 | approved | open | 5 | 0.710 | 0.0721 | 1.3779 |
| 2026-10-14 13:45:19 | 0x9c1462c6 | 5m | 0.45 | approved | open | 5 | 0.450 | 0.0866 | 2.6634 |
| 2026-10-14 13:45:19 | 0x43c82637 | 15m | 0.47 | approved | open | 5 | 0.470 | 0.0872 | 2.5628 |
| 2026-10-14 13:55:13 | 0x31cba18e | 5m | 0.57 | approved | open | 5 | 0.610 | 0.0833 | 1.8667 |
| 2026-10-14 14:01:00 | 0x962449e1 | 15m | 0.62 | approved | open | 5 | 0.630 | 0.0816 | 1.7684 |
| 2026-10-14 14:01:00 | 0x36c2312a | 5m | 0.66 | approved | open | 5 | 0.700 | 0.0735 | 1.4265 |
| 2026-10-14 14:05:43 | 0x0efb6c8e | 5m | 0.36 | approved | open | 5 | 0.420 | 0.0853 | -2.1853 |
| 2026-10-14 14:19:58 | 0x19c29b5a | 15m | 0.51 | approved | open | 5 | 0.500 | 0.0875 | 2.4125 |
| 2026-10-14 14:21:48 | 0xad9688b1 | 5m | 0.39 | approved | open | 5 | 0.390 | 0.0833 | -2.0333 |
| 2026-10-14 14:27:01 | 0xfcced14f | 5m | 0.17 | approved | open | 5 | 0.150 | 0.0446 | -0.7946 |
| 2026-10-14 14:31:15 | 0x50d89d58 | 5m | 0.43 | approved | open | 5 | 0.430 | 0.0858 | 2.7642 |
| 2026-10-14 14:31:15 | 0x883c9e59 | 15m | 0.45 | approved | open | 5 | 0.450 | 0.0866 | 2.6634 |
| 2026-10-14 14:37:11 | 0x44822644 | 5m | 0.32 | approved | open | 5 | 0.340 | 0.0785 | -1.7785 |
| 2026-10-14 14:40:54 | 0x41c9d3f1 | 5m | 0.6 | approved | open | 5 | 0.620 | 0.0825 | 1.8175 |
| 2026-10-14 15:03:03 | 0x7199c6af | 5m | 0.48 | approved | open | 5 | 0.500 | 0.0875 | -2.5875 |
| 2026-10-14 15:03:03 | 0xd4bc056b | 15m | 0.51 | approved | open | 5 | 0.510 | 0.0875 | 2.3625 |
| 2026-10-14 15:05:48 | 0x484182ab | 5m | 0.42 | approved | open | 5 | 0.420 | 0.0853 | 2.8147 |
| 2026-10-14 15:16:20 | 0x5d460b87 | 15m | 0.74 | approved | open | 5 | 0.780 | 0.0601 | 1.0399 |
| 2026-10-14 15:38:45 | 0xdca714b4 | 15m | 0.82 | approved | open | 5 | 0.820 | 0.0517 | 0.8483 |
| 2026-10-14 15:40:32 | 0xcc22b60e | 5m | 0.52 | approved | open | 5 | 0.510 | 0.0875 | 2.3625 |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 846, median 262, p90 419, min 205, max 1220.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 291166, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 10.2, max 93.0.
- Binance event time to local receive (network + clock offset): n 291166, median of minute medians -47.0, worst minute p90 1846418.0, worst minute p99 1846418.0, max 1846418.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 473407, median of minute medians 5.9, worst minute p90 159.9, worst minute p99 25563511.8, max 16386890.4.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 79, median -22, p90 133, min -356, max 523.
- Local receive to decision: n 79, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 79, median 393, p90 544, min 361, max 703.

## Risk, reconciliation, invariants and audit

- Trips: 9: global REDUCING (stale feed binance:BTC: 16391385 ms, breaker:stale_feed); global REDUCING (stale feed basis:USDT: 18261775 ms, breaker:stale_feed); global REDUCING (restart: stale feed basis:USDT: 18261775 ms, loop:restart); global ACTIVE (reset, human:DELL-feed); global REDUCING (stale feed binance:BTC: 60466 ms, breaker:stale_feed); global REDUCING (stale feed binance:ETH: 60911 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 60741 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 60741 ms, breaker:stale_feed); global ACTIVE (reset, human:DELL-feed).
- Human resets: 2; halts confirmed by zero open orders: 0.
- Reconciles: 172 (periodic 171, startup 1); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 717 records, head f8c6e2bc9962cba8; last head anchored in the ledger: 459 records, d5703267b32012f6 (startup, 2026-10-14 02:21:37).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 162 | 200 / 100 | 56.52 | 1 |

Elapsed since the first run: 2.87 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-10-14 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-10-14.md --title "paper_ethb day 4: 2026-10-14 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **4 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **4 of 4** (need 5+, all clean)
- Running time: 47.2 hours (1.97 days of 24 h)

| UTC day | Hours running |
|---|---|
| 2026-10-11 | 1.1 |
| 2026-10-12 | 15.4 |
| 2026-10-13 | 16.7 |
| 2026-10-14 | 14.1 |
