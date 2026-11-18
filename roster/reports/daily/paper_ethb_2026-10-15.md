# paper_ethb day 5: 2026-10-15 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-10-15 00:00:00 to 2026-10-16 00:00:00 UTC (data from 2026-10-15 06:08:08 to 2026-10-15 16:21:32). Paper only: no order ever left this PC.

## Summary

- Runs started: 3; clean shutdowns: 0; still running or ended by a crash or kill: 3 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 67, approved 67, orders 67, paper fills 67, btc-speed events 115 and trades 67.
- Paper P&L to the end of the window: btc-speed +136.18 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 234 | 487.52 | 0.00 | 14.8042 | 0.00 | 638.50 | 0 | 0.00 | +136.1788 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 67 intents, 67 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | taker | 67 | 67 | 330 | 0.4437 | 4.6695 |

Merges of YES+NO pairs: 0; paper redemptions: 66.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| btc-speed | 5 s | 65 | +6.05c | +1.04c | 2 |
| btc-speed | 60 s | 63 | +8.52c | +1.95c | 4 |
| btc-speed | 300 s | 19 | +8.53c | +5.10c | 48 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-v4-eth-bybit**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 232 in 232 markets (needs 200), unresolved 0, mean 0.5870 USD, cluster SE 0.1380, total +136.1788 USD. Verdict: **PASS**.
- **Paper-fill realism** (btc-speed at real tape prices): 193 of 232 resolved trades repriced at what real takers paid in our order's second. Paper +120.49 USD -> best case +66.40 (cheapest real price), typical +26.26 (median real price), **live estimate +30.80** (our order behind the real takers that beat us, partial fills; 63% of our shares filled); real takers paid a median +7.5c over our fill. Paper assumes we win every race for the cheapest ask. Not comparable with reports before 15 Oct.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-11 19:34:32), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-11 19:34:32), `btc-speed-v4-eth-bybit` (sha256 04680de003a175aa, written 2026-10-11 19:34:32).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

115 causal ETH moves (>= 6.0 bp in 2 s) and 67 trades sent to the kernel. Per mapped market: already holding this market 143, trade 67, ask above max price 10, ends too soon 5, no ask 2, too little size at ask 2, move started before the window 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-15 14:56:42 | +6.5 | 0x3132c4c2: trade; 0x792ce22d: already holding this market |
| 2026-10-15 14:59:21 | -6.0 | 0x3132c4c2: already holding this market; 0x792ce22d: already holding this market |
| 2026-10-15 15:01:02 | +6.2 | 0x1ae09979: trade; 0x544f1d09: trade |
| 2026-10-15 15:03:22 | +6.5 | 0x1ae09979: already holding this market; 0x544f1d09: already holding this market |
| 2026-10-15 15:04:20 | +6.0 | 0x1ae09979: already holding this market; 0x544f1d09: already holding this market |
| 2026-10-15 15:05:23 | -6.0 | 0x1ae09979: already holding this market; 0x4583a898: trade |
| 2026-10-15 15:06:29 | +8.3 | 0x1ae09979: already holding this market; 0x4583a898: already holding this market |
| 2026-10-15 15:07:36 | -6.1 | 0x1ae09979: already holding this market; 0x4583a898: already holding this market |
| 2026-10-15 15:09:06 | +6.2 | 0x1ae09979: already holding this market; 0x4583a898: already holding this market |
| 2026-10-15 15:12:33 | -7.3 | 0x1ae09979: already holding this market; 0x575d4873: trade |
| 2026-10-15 15:15:42 | -6.7 | 0x4034666a: trade; 0x874ebecd: trade |
| 2026-10-15 15:17:44 | +6.6 | 0x4034666a: already holding this market; 0x874ebecd: already holding this market |
| 2026-10-15 15:20:16 | +6.3 | 0x01abe250: too little size at ask; 0x874ebecd: already holding this market |
| 2026-10-15 15:23:06 | +7.1 | 0x01abe250: trade; 0x874ebecd: already holding this market |
| 2026-10-15 15:27:51 | +6.4 | 0x36a99d0d: trade; 0x874ebecd: already holding this market |
| 2026-10-15 15:31:09 | -6.9 | 0x2be8292d: trade; 0xec3c927a: trade |
| 2026-10-15 15:32:16 | +6.0 | 0x2be8292d: already holding this market; 0xec3c927a: already holding this market |
| 2026-10-15 15:34:20 | +9.9 | 0x2be8292d: already holding this market; 0xec3c927a: already holding this market |
| 2026-10-15 15:35:43 | +6.5 | 0x21cb08f9: trade; 0x2be8292d: already holding this market |
| 2026-10-15 15:37:35 | +6.4 | 0x21cb08f9: already holding this market; 0x2be8292d: already holding this market |
| 2026-10-15 15:38:52 | +6.0 | 0x21cb08f9: already holding this market; 0x2be8292d: already holding this market |
| 2026-10-15 15:39:55 | +6.6 | 0x21cb08f9: already holding this market; 0x2be8292d: already holding this market |
| 2026-10-15 15:41:02 | +7.2 | 0x2be8292d: already holding this market; 0x5a08c291: trade |
| 2026-10-15 15:42:03 | +6.9 | 0x2be8292d: already holding this market; 0x5a08c291: already holding this market |
| 2026-10-15 15:43:18 | +6.4 | 0x2be8292d: already holding this market; 0x5a08c291: already holding this market |
| 2026-10-15 15:45:46 | +7.5 | 0x2368e1b8: trade; 0xf07c320a: trade |
| 2026-10-15 15:47:09 | -6.2 | 0x2368e1b8: already holding this market; 0xf07c320a: already holding this market |
| 2026-10-15 16:04:33 | +7.3 | 0xaced6f24: trade; 0xc21b29b5: ends too soon |
| 2026-10-15 16:08:24 | +6.2 | 0x297cd6d5: no ask; 0xaced6f24: already holding this market |
| 2026-10-15 16:10:46 | +7.4 | 0xaced6f24: already holding this market; 0xc8d66162: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-15 13:30:35 | 0x6afc099c | 5m | 0.59 | approved | open | 5 | 0.600 | 0.0840 | -3.0840 |
| 2026-10-15 13:30:35 | 0x1eeea9d2 | 15m | 0.55 | approved | open | 5 | 0.550 | 0.0866 | -2.8366 |
| 2026-10-15 13:35:23 | 0x8606ab69 | 5m | 0.63 | approved | open | 5 | 0.640 | 0.0806 | -3.2806 |
| 2026-10-15 13:41:14 | 0xe23c380b | 5m | 0.64 | approved | open | 5 | 0.660 | 0.0785 | 1.6215 |
| 2026-10-15 13:46:28 | 0xbdf4db58 | 15m | 0.59 | approved | open | 5 | 0.580 | 0.0853 | 2.0147 |
| 2026-10-15 13:46:28 | 0x4cea5cb0 | 5m | 0.68 | approved | open | 5 | 0.670 | 0.0774 | 1.5726 |
| 2026-10-15 13:52:55 | 0xced7165e | 5m | 0.001 | approved | open | 5 | 0.001 | 0.0003 | -0.0053 |
| 2026-10-15 13:55:21 | 0xd937b62e | 5m | 0.34 | approved | open | 5 | 0.430 | 0.0858 | 2.7642 |
| 2026-10-15 14:00:33 | 0x18a2e2a0 | 5m | 0.5 | approved | open | 5 | 0.500 | 0.0875 | 2.4125 |
| 2026-10-15 14:00:33 | 0x68a6573b | 15m | 0.51 | approved | open | 5 | 0.540 | 0.0869 | 2.2131 |
| 2026-10-15 14:06:10 | 0xe397197c | 5m | 0.14 | approved | open | 5 | 0.170 | 0.0494 | -0.8994 |
| 2026-10-15 14:10:25 | 0x8ca4ed22 | 5m | 0.08 | approved | open | 5 | 0.080 | 0.0258 | -0.4258 |
| 2026-10-15 14:15:14 | 0x25403b41 | 5m | 0.3 | approved | open | 5 | 0.330 | 0.0774 | 3.2726 |
| 2026-10-15 14:15:14 | 0xbecbb6a1 | 15m | 0.37 | approved | open | 5 | 0.390 | 0.0833 | -2.0333 |
| 2026-10-15 14:20:18 | 0x3a938833 | 5m | 0.5 | approved | open | 5 | 0.510 | 0.0875 | 2.3625 |
| 2026-10-15 14:26:29 | 0x58b2ad91 | 5m | 0.41 | approved | open | 5 | 0.410 | 0.0847 | 2.8653 |
| 2026-10-15 14:31:42 | 0x77a206a2 | 15m | 0.7 | approved | open | 5 | 0.700 | 0.0735 | -3.5735 |
| 2026-10-15 14:32:54 | 0x3ae920d1 | 5m | 0.09 | approved | open | 5 | 0.090 | 0.0287 | 4.5213 |
| 2026-10-15 14:38:50 | 0xf511a6a6 | 5m | 0.08 | approved | open | 5 | 0.080 | 0.0258 | -0.4258 |
| 2026-10-15 14:40:03 | 0x35105b11 | 5m | 0.63 | approved | open | 5 | 0.630 | 0.0816 | 1.7684 |
| 2026-10-15 14:46:07 | 0x3ac02e29 | 5m | 0.6 | approved | open | 5 | 0.620 | 0.0825 | -3.1825 |
| 2026-10-15 14:46:07 | 0x792ce22d | 15m | 0.56 | approved | open | 5 | 0.560 | 0.0862 | -2.8862 |
| 2026-10-15 14:51:41 | 0xadfb4c12 | 5m | 0.11 | approved | open | 5 | 0.100 | 0.0315 | 4.4685 |
| 2026-10-15 14:56:42 | 0x3132c4c2 | 5m | 0.83 | approved | open | 5 | 0.850 | 0.0446 | 0.7054 |
| 2026-10-15 15:01:02 | 0x1ae09979 | 15m | 0.5 | approved | open | 5 | 0.520 | 0.0874 | 2.3126 |
| 2026-10-15 15:01:02 | 0x544f1d09 | 5m | 0.54 | approved | open | 5 | 0.530 | 0.0872 | 2.2628 |
| 2026-10-15 15:05:23 | 0x4583a898 | 5m | 0.27 | approved | open | 5 | 0.290 | 0.0721 | -1.5221 |
| 2026-10-15 15:12:33 | 0x575d4873 | 5m | 0.25 | approved | open | 5 | 0.250 | 0.0656 | -1.3156 |
| 2026-10-15 15:15:42 | 0x4034666a | 5m | 0.35 | approved | open | 5 | 0.390 | 0.0833 | -2.0333 |
| 2026-10-15 15:15:42 | 0x874ebecd | 15m | 0.43 | approved | open | 5 | 0.470 | 0.0872 | -2.4372 |
| 2026-10-15 15:23:06 | 0x01abe250 | 5m | 0.33 | approved | open | 5 | 0.370 | 0.0816 | 3.0684 |
| 2026-10-15 15:27:51 | 0x36a99d0d | 5m | 0.53 | approved | open | 5 | 0.540 | 0.0869 | 2.2131 |
| 2026-10-15 15:31:09 | 0x2be8292d | 15m | 0.5 | approved | open | 5 | 0.500 | 0.0875 | -2.5875 |
| 2026-10-15 15:31:09 | 0xec3c927a | 5m | 0.44 | approved | open | 5 | 0.450 | 0.0866 | -2.3366 |
| 2026-10-15 15:35:43 | 0x21cb08f9 | 5m | 0.63 | approved | open | 5 | 0.630 | 0.0816 | 1.7684 |
| 2026-10-15 15:41:02 | 0x5a08c291 | 5m | 0.51 | approved | open | 5 | 0.520 | 0.0874 | -2.6874 |
| 2026-10-15 15:45:46 | 0x2368e1b8 | 5m | 0.23 | approved | open | 5 | 0.250 | 0.0656 | -1.3156 |
| 2026-10-15 15:45:46 | 0xf07c320a | 15m | 0.34 | approved | open | 5 | 0.340 | 0.0785 | 3.2215 |
| 2026-10-15 16:04:33 | 0xaced6f24 | 15m | 0.29 | approved | open | 5 | 0.290 | 0.0721 | -1.5221 |
| 2026-10-15 16:10:46 | 0xc8d66162 | 5m | 0.47 | approved | open | 5 | 0.480 | 0.0874 | -2.4874 |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 612, median 260, p90 324, min 219, max 1170.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 293947, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 41.0, max 107.0.
- Binance event time to local receive (network + clock offset): n 293947, median of minute medians -720.0, worst minute p90 11133.6, worst minute p99 17886.6, max 18630.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 338753, median of minute medians 8.6, worst minute p90 136.0, worst minute p99 167.9, max 627.5.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 115, median -857, p90 52, min -973, max 1672.
- Local receive to decision: n 115, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 115, median 408, p90 452, min 378, max 566.

## Risk, reconciliation, invariants and audit

- Trips: 4: global REDUCING (stale feed polymarket:crypto-fast: 60630 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 60630 ms, breaker:stale_feed); global REDUCING (stale feed binance:ETH: 60551 ms, breaker:stale_feed); global ACTIVE (reset, human:DELL-feed).
- Human resets: 1; halts confirmed by zero open orders: 0.
- Reconciles: 127 (startup 3, periodic 124); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 1007 records, head 003fab80f1d15292; last head anchored in the ledger: 763 records, 062ce1de6c686c06 (startup, 2026-10-15 11:10:14).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 232 | 200 / 100 | 60.00 | 0 |

Elapsed since the first run: 3.87 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-10-15 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-10-15.md --title "paper_ethb day 5: 2026-10-15 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **5 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **7 of 7** (need 5+, all clean)
- Running time: 59.3 hours (2.47 days of 24 h)

| UTC day | Hours running |
|---|---|
| 2026-10-11 | 1.1 |
| 2026-10-12 | 15.4 |
| 2026-10-13 | 16.7 |
| 2026-10-14 | 16.0 |
| 2026-10-15 | 10.2 |
