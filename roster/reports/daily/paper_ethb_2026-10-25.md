# paper_ethb day 15: 2026-10-25 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-10-25 00:00:00 to 2026-10-26 00:00:00 UTC (data from 2026-10-25 00:00:25 to 2026-10-25 16:20:53). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 14, approved 14, orders 14, paper fills 14, btc-speed events 16 and trades 14.
- Paper P&L to the end of the window: btc-speed +145.23 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 344 | 766.22 | 0.00 | 22.0474 | 0.00 | 933.50 | 0 | 0.00 | +145.2333 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 14 intents, 14 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | taker | 14 | 14 | 70 | 0.5857 | 0.8481 |

Merges of YES+NO pairs: 0; paper redemptions: 14.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| btc-speed | 5 s | 14 | +15.64c | +5.05c | 0 |
| btc-speed | 60 s | 9 | +8.22c | +7.34c | 5 |
| btc-speed | 300 s | 6 | -6.83c | +12.16c | 8 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-v4-eth-bybit**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 340 in 340 markets (needs 200), unresolved 0, mean 0.4272 USD, cluster SE 0.1162, total +145.2333 USD. Verdict: **PASS**.
- **Paper-fill realism** (btc-speed at real tape prices): 286 of 340 resolved trades repriced at what real takers paid in our order's second. Paper +135.06 USD -> best case +70.32 (cheapest real price), typical +21.26 (median real price), **live estimate +18.11** (our order behind the real takers that beat us, partial fills; 67% of our shares filled); real takers paid a median +6.0c over our fill. Paper assumes we win every race for the cheapest ask. Not comparable with reports before 15 Oct.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-11 19:34:32), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-11 19:34:32), `btc-speed-v4-eth-bybit` (sha256 04680de003a175aa, written 2026-10-11 19:34:32).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

16 causal ETH moves (>= 6.0 bp in 2 s) and 14 trades sent to the kernel. Per mapped market: trade 14, ask above max price 9, already holding this market 5, no ask 2, ends too soon 2.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-25 01:47:33 | +6.0 | 0x221b369c: trade; 0x86985822: ask above max price |
| 2026-10-25 02:13:39 | +7.1 | 0x1f9d953a: trade; 0x29e9c19f: trade |
| 2026-10-25 06:50:59 | -6.0 | 0x73a2fae2: trade; 0x990715d3: ask above max price |
| 2026-10-25 06:52:30 | -6.0 | 0x73a2fae2: already holding this market; 0x990715d3: no ask |
| 2026-10-25 08:28:38 | -6.2 | 0x4f1af8a7: ask above max price; 0x668f874c: no ask |
| 2026-10-25 09:12:43 | -6.1 | 0x7cf92f9c: trade; 0x926dca70: ask above max price |
| 2026-10-25 09:17:28 | -8.3 | 0x030d780b: trade; 0xadd69723: trade |
| 2026-10-25 09:18:43 | -6.3 | 0x030d780b: already holding this market; 0xadd69723: already holding this market |
| 2026-10-25 09:21:10 | -6.1 | 0x030d780b: already holding this market; 0x53a44056: trade |
| 2026-10-25 11:00:35 | +6.3 | 0x4d8dd282: ask above max price; 0xe8cd6e3f: ask above max price |
| 2026-10-25 11:44:52 | +6.4 | 0x02a4dde8: ends too soon; 0x1d21ca8f: ends too soon |
| 2026-10-25 11:46:02 | +6.3 | 0xc007a69d: ask above max price; 0xf7cf2a45: trade |
| 2026-10-25 13:33:28 | -6.2 | 0x68f88a41: trade; 0x85a0498b: ask above max price |
| 2026-10-25 13:40:40 | +6.1 | 0x68f88a41: already holding this market; 0x8b5ec156: trade |
| 2026-10-25 15:00:37 | +6.2 | 0x24305063: trade; 0xd3858ebd: trade |
| 2026-10-25 15:35:42 | +7.0 | 0x5177f34d: ask above max price; 0x54c03f24: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-25 01:47:33 | 0x221b369c | 15m | 0.84 | approved | open | 5 | 0.840 | 0.0470 | 0.7530 |
| 2026-10-25 02:13:39 | 0x1f9d953a | 15m | 0.22 | approved | open | 5 | 0.220 | 0.0601 | -1.1601 |
| 2026-10-25 02:13:39 | 0x29e9c19f | 5m | 0.16 | approved | open | 5 | 0.160 | 0.0470 | -0.8470 |
| 2026-10-25 06:50:59 | 0x73a2fae2 | 15m | 0.8 | approved | open | 5 | 0.850 | 0.0446 | 0.7054 |
| 2026-10-25 09:12:43 | 0x7cf92f9c | 5m | 0.85 | approved | open | 5 | 0.850 | 0.0446 | 0.7054 |
| 2026-10-25 09:17:28 | 0xadd69723 | 5m | 0.68 | approved | open | 5 | 0.770 | 0.0620 | 1.0880 |
| 2026-10-25 09:17:28 | 0x030d780b | 15m | 0.57 | approved | open | 5 | 0.620 | 0.0825 | 1.8175 |
| 2026-10-25 09:21:10 | 0x53a44056 | 5m | 0.04 | approved | open | 5 | 0.040 | 0.0134 | -0.2134 |
| 2026-10-25 11:46:02 | 0xf7cf2a45 | 15m | 0.74 | approved | open | 5 | 0.760 | 0.0638 | 1.1362 |
| 2026-10-25 13:33:28 | 0x68f88a41 | 15m | 0.66 | approved | open | 5 | 0.660 | 0.0785 | -3.3785 |
| 2026-10-25 13:40:40 | 0x8b5ec156 | 5m | 0.35 | approved | open | 5 | 0.370 | 0.0816 | 3.0684 |
| 2026-10-25 15:00:37 | 0xd3858ebd | 5m | 0.67 | approved | open | 5 | 0.670 | 0.0774 | 1.5726 |
| 2026-10-25 15:00:37 | 0x24305063 | 15m | 0.63 | approved | open | 5 | 0.630 | 0.0816 | 1.7684 |
| 2026-10-25 15:35:42 | 0x54c03f24 | 5m | 0.76 | approved | open | 5 | 0.760 | 0.0638 | 1.1362 |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 871, median 218, p90 238, min 195, max 520.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 121036, median of minute medians 0.0, worst minute p90 1.2, worst minute p99 11.5, max 290.0.
- Binance event time to local receive (network + clock offset): n 121036, median of minute medians -142.0, worst minute p90 6626033.0, worst minute p99 6693709.8, max 6701364.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 474324, median of minute medians 9.7, worst minute p90 12.3, worst minute p99 177.7, max 6701561.1.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 16, median -161, p90 73, min -281, max 76.
- Local receive to decision: n 16, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 16, median 374, p90 395, min 351, max 425.

## Risk, reconciliation, invariants and audit

- Trips: 4: global REDUCING (stale feed polymarket:crypto-fast: 6701876 ms, breaker:stale_feed); global REDUCING (stale feed binance:ETH: 6702673 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 6701876 ms, breaker:stale_feed); global ACTIVE (reset, human:DELL-feed).
- Human resets: 61; halts confirmed by zero open orders: 0.
- Reconciles: 175 (periodic 175); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 1816 records, head 1a0e3a7ca63993bd; last head anchored in the ledger: 1709 records, 2c03399bc4bb6647 (startup, 2026-10-24 17:16:01).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 340 | 200 / 100 | 24.52 | 0 |

Elapsed since the first run: 13.87 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-10-25 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-10-25.md --title "paper_ethb day 15: 2026-10-25 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **MET.**

- Days without a violation: **15 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **10 of 10** (need 5+, all clean)
- Running time: 158.8 hours (6.62 days of 24 h)

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
| 2026-10-25 | 14.5 |
