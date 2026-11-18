# paper_ethb day 23: 2026-11-02 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-11-02 00:00:00 to 2026-11-03 00:00:00 UTC (data from 2026-11-02 00:00:07 to 2026-11-02 16:21:36). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 51, approved 51, orders 51, paper fills 49, btc-speed events 65 and trades 52.
- Paper P&L to the end of the window: btc-speed +182.59 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 544 | 1277.70 | 0.00 | 35.5038 | 0.00 | 1493.50 | 15 | 2.30 (+1 unmarked) | +182.5945 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 51 intents, 51 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | taker | 51 | 49 | 245 | 0.5121 | 3.3495 |

Merges of YES+NO pairs: 0; paper redemptions: 46.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| btc-speed | 5 s | 48 | +7.54c | +1.61c | 1 |
| btc-speed | 60 s | 42 | +6.74c | +3.71c | 6 |
| btc-speed | 300 s | 15 | +5.28c | +6.70c | 31 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-v4-eth-bybit**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 536 in 536 markets (needs 200), unresolved 3, mean 0.3485 USD, cluster SE 0.0925, total +186.7985 USD. Verdict: **PASS**.
- **Paper-fill realism** (btc-speed at real tape prices): 457 of 536 resolved trades repriced at what real takers paid in our order's second. Paper +196.85 USD -> best case +106.03 (cheapest real price), typical +25.74 (median real price), **live estimate +30.38** (our order behind the real takers that beat us, partial fills; 67% of our shares filled); real takers paid a median +5.0c over our fill. Paper assumes we win every race for the cheapest ask. Not comparable with reports before 15 Oct.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-11 19:34:32), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-11 19:34:32), `btc-speed-v4-eth-bybit` (sha256 04680de003a175aa, written 2026-10-11 19:34:32).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

65 causal ETH moves (>= 6.0 bp in 2 s) and 52 trades sent to the kernel. Per mapped market: already holding this market 54, trade 52, ask above max price 13, ends too soon 7, no ask 3, too little size at ask 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-11-02 14:32:46 | +6.5 | 0xdd1b9849: already holding this market; 0xde7b7fad: already holding this market |
| 2026-11-02 14:34:54 | +6.3 | 0xdd1b9849: already holding this market; 0xde7b7fad: already holding this market |
| 2026-11-02 14:37:02 | -6.9 | 0xdd1b9849: already holding this market; 0xf4cb5289: trade |
| 2026-11-02 14:38:42 | -7.4 | 0xdd1b9849: already holding this market; 0xf4cb5289: already holding this market |
| 2026-11-02 14:41:33 | -6.5 | 0xdd1b9849: already holding this market; 0xe5377631: trade |
| 2026-11-02 14:44:39 | +6.1 | 0xdd1b9849: already holding this market; 0xe5377631: already holding this market |
| 2026-11-02 14:48:45 | -9.0 | 0x5a26f595: trade; 0x5c62c60c: trade |
| 2026-11-02 14:50:38 | -6.5 | 0x5c62c60c: already holding this market; 0xc2f31bed: trade |
| 2026-11-02 14:54:46 | -6.0 | 0x5c62c60c: already holding this market; 0xc2f31bed: already holding this market |
| 2026-11-02 14:56:15 | -6.2 | 0x5c62c60c: already holding this market; 0xc1b34799: trade |
| 2026-11-02 14:59:59 | +6.3 | 0x5c62c60c: already holding this market; 0xc1b34799: already holding this market |
| 2026-11-02 15:02:17 | +6.2 | 0x483d4685: too little size at ask; 0xac606ffc: trade |
| 2026-11-02 15:03:39 | -6.4 | 0x483d4685: trade; 0xac606ffc: already holding this market |
| 2026-11-02 15:05:27 | +6.6 | 0x4c56c341: trade; 0xac606ffc: already holding this market |
| 2026-11-02 15:07:05 | +6.0 | 0x4c56c341: already holding this market; 0xac606ffc: already holding this market |
| 2026-11-02 15:09:56 | +6.3 | 0x4c56c341: already holding this market; 0xac606ffc: already holding this market |
| 2026-11-02 15:15:24 | -6.5 | 0x31664cff: trade; 0x92707243: trade |
| 2026-11-02 15:26:08 | +6.0 | 0x6ed8e67d: trade; 0x92707243: already holding this market |
| 2026-11-02 15:38:57 | -6.3 | 0x83cecd90: ask above max price; 0xe3f32cdc: ask above max price |
| 2026-11-02 15:41:54 | -7.0 | 0xe3f32cdc: ask above max price; 0xff5db958: trade |
| 2026-11-02 15:58:09 | -8.9 | 0x02f3bdb0: no ask; 0x37d68fc1: no ask |
| 2026-11-02 16:00:13 | -6.4 | 0x0382603f: trade; 0xfe358e97: trade |
| 2026-11-02 16:02:33 | -6.5 | 0x0382603f: already holding this market; 0xfe358e97: already holding this market |
| 2026-11-02 16:03:49 | +6.7 | 0x0382603f: already holding this market; 0xfe358e97: already holding this market |
| 2026-11-02 16:08:42 | -6.3 | 0x0382603f: already holding this market; 0xa53a3b23: trade |
| 2026-11-02 16:10:09 | -6.2 | 0x0382603f: already holding this market; 0xb45135c3: trade |
| 2026-11-02 16:11:11 | -6.8 | 0x0382603f: already holding this market; 0xb45135c3: already holding this market |
| 2026-11-02 16:13:08 | -6.2 | 0x0382603f: already holding this market; 0xb45135c3: already holding this market |
| 2026-11-02 16:17:10 | -6.2 | 0x34e1633a: trade; 0x4146351a: trade |
| 2026-11-02 16:21:28 | -6.1 | 0x34e1633a: already holding this market; 0x5988a355: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-02 07:58:17 | 0xe8356793 | 5m | 0.01 | approved | open | 5 | 0.010 | 0.0035 | -0.0535 |
| 2026-11-02 08:40:44 | 0x431c019d | 5m | 0.8 | approved | open | 5 | 0.800 | 0.0560 | 0.9440 |
| 2026-11-02 08:49:35 | 0x0523b707 | 15m | 0.71 | approved | open | 5 | 0.710 | 0.0721 | -3.6221 |
| 2026-11-02 09:09:41 | 0xf776cf08 | 15m | 0.26 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 09:50:43 | 0x22ec0fbc | 5m | 0.41 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 10:22:55 | 0xaa50f268 | 15m | 0.36 | approved | open | 5 | 0.390 | 0.0833 | 2.9667 |
| 2026-11-02 10:22:55 | 0x124e7ab3 | 5m | 0.07 | approved | open | 5 | 0.070 | 0.0228 | 4.6272 |
| 2026-11-02 11:39:55 | 0x0d146bee | 15m | 0.66 | approved | open | 5 | 0.660 | 0.0785 | 1.6215 |
| 2026-11-02 12:15:48 | 0xa8510127 | 5m | 0.67 | approved | open | 5 | 0.670 | 0.0774 | 1.5726 |
| 2026-11-02 12:15:48 | 0x32c824e0 | 15m | 0.55 | approved | open | 5 | 0.550 | 0.0866 | -2.8366 |
| 2026-11-02 12:40:03 | 0x0b024c98 | 5m | 0.54 | approved | open | 5 | 0.540 | 0.0869 | -2.7869 |
| 2026-11-02 13:36:50 | 0xdbf7e062 | 15m | 0.76 | approved | open | 5 | 0.780 | 0.0601 | 1.0399 |
| 2026-11-02 13:40:07 | 0x4e2445ea | 5m | 0.45 | approved | open | 5 | 0.500 | 0.0875 | -2.5875 |
| 2026-11-02 13:45:37 | 0x8250d8d5 | 5m | 0.6 | approved | open | 5 | 0.620 | 0.0825 | 1.8175 |
| 2026-11-02 13:45:37 | 0x1414a00e | 15m | 0.55 | approved | open | 5 | 0.570 | 0.0858 | 2.0642 |
| 2026-11-02 13:55:19 | 0x7c7697ec | 5m | 0.46 | approved | open | 5 | 0.480 | 0.0874 | 2.5126 |
| 2026-11-02 14:00:55 | 0xb8cff587 | 15m | 0.63 | approved | open | 5 | 0.670 | 0.0774 | -3.4274 |
| 2026-11-02 14:00:55 | 0xea858e9b | 5m | 0.75 | approved | open | 5 | 0.790 | 0.0581 | 0.9919 |
| 2026-11-02 14:30:08 | 0xde7b7fad | 5m | 0.3 | approved | open | 5 | 0.300 | 0.0735 | 3.4265 |
| 2026-11-02 14:30:08 | 0xdd1b9849 | 15m | 0.36 | approved | open | 5 | 0.360 | 0.0806 | 3.1194 |
| 2026-11-02 14:37:02 | 0xf4cb5289 | 5m | 0.31 | approved | open | 5 | 0.310 | 0.0749 | 3.3751 |
| 2026-11-02 14:41:33 | 0xe5377631 | 5m | 0.53 | approved | open | 5 | 0.530 | 0.0872 | 2.2628 |
| 2026-11-02 14:48:45 | 0x5c62c60c | 15m | 0.33 | approved | open | 5 | 0.330 | 0.0774 | 3.2726 |
| 2026-11-02 14:48:45 | 0x5a26f595 | 5m | 0.04 | approved | open | 5 | 0.040 | 0.0134 | -0.2134 |
| 2026-11-02 14:50:38 | 0xc2f31bed | 5m | 0.74 | approved | open | 5 | 0.740 | 0.0673 | 1.2327 |
| 2026-11-02 14:56:15 | 0xc1b34799 | 5m | 0.75 | approved | open | 5 | 0.820 | 0.0517 | 0.8483 |
| 2026-11-02 15:02:17 | 0xac606ffc | 15m | 0.35 | approved | open | 5 | 0.370 | 0.0816 | 3.0684 |
| 2026-11-02 15:03:39 | 0x483d4685 | 5m | 0.66 | approved | open | 5 | 0.660 | 0.0785 | 1.6215 |
| 2026-11-02 15:05:27 | 0x4c56c341 | 5m | 0.6 | approved | open | 5 | 0.690 | 0.0749 | 1.4751 |
| 2026-11-02 15:15:24 | 0x31664cff | 5m | 0.64 | approved | open | 5 | 0.640 | 0.0806 | 1.7194 |
| 2026-11-02 15:15:24 | 0x92707243 | 15m | 0.58 | approved | open | 5 | 0.580 | 0.0853 | 2.0147 |
| 2026-11-02 15:26:08 | 0x6ed8e67d | 5m | 0.59 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 15:41:54 | 0xff5db958 | 5m | 0.25 | approved | open | 5 | 0.250 | 0.0656 | -1.3156 |
| 2026-11-02 16:00:13 | 0xfe358e97 | 5m | 0.57 | approved | open | 5 | 0.580 | 0.0853 | -2.9853 |
| 2026-11-02 16:00:13 | 0x0382603f | 15m | 0.55 | approved | open | 5 | 0.550 | 0.0866 | 2.1634 |
| 2026-11-02 16:08:42 | 0xa53a3b23 | 5m | 0.75 | approved | open | 5 | 0.780 | 0.0601 | 1.0399 |
| 2026-11-02 16:10:09 | 0xb45135c3 | 5m | 0.8 | approved | open | 5 | 0.850 | 0.0446 | 0.7054 |
| 2026-11-02 16:17:10 | 0x4146351a | 5m | 0.34 | approved | open | 5 | 0.410 | 0.0847 | unresolved |
| 2026-11-02 16:17:10 | 0x34e1633a | 15m | 0.42 | approved | open | 5 | 0.460 | 0.0869 | unresolved |
| 2026-11-02 16:21:28 | 0x5988a355 | 5m | 0.38 | approved | open | 5 | 0.380 | 0.0825 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 750, median 220, p90 243, min 191, max 572.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 268005, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 13.0, max 98.0.
- Binance event time to local receive (network + clock offset): n 268005, median of minute medians -90.0, worst minute p90 4361.0, worst minute p99 8012.7, max 9687.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 409146, median of minute medians 9.6, worst minute p90 13.2, worst minute p99 1119013.6, max 13985347.5.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 65, median -34, p90 125, min -303, max 2253.
- Local receive to decision: n 65, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 65, median 368, p90 391, min 341, max 609.

## Risk, reconciliation, invariants and audit

- Trips: 4: global REDUCING (stale feed polymarket:crypto-fast: 13979461 ms, breaker:stale_feed); global REDUCING (stale feed binance:ETH: 13981470 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 13979461 ms, breaker:stale_feed); global ACTIVE (reset, human:DELL-feed).
- Human resets: 43; halts confirmed by zero open orders: 0.
- Reconciles: 150 (periodic 150); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 2957 records, head bfa9e8d0feb5b579; last head anchored in the ledger: 2046 records, 22b64a79d0480995 (startup, 2026-10-28 18:33:10).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 536 | 200 / 100 | 24.51 | 0 |

Elapsed since the first run: 21.87 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-11-02 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-11-02.md --title "paper_ethb day 23: 2026-11-02 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **MET.**

- Days without a violation: **23 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **11 of 11** (need 5+, all clean)
- Running time: 295.0 hours (12.29 days of 24 h)

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
| 2026-11-02 | 12.5 |
