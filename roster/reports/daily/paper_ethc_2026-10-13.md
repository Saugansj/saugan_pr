# paper_ethc day 1: 2026-10-13 (UTC)

Ledger `data/trader/paper_ethc`, window 2026-10-13 00:00:00 to 2026-10-14 00:00:00 UTC (data from 2026-10-13 06:31:25 to 2026-10-13 16:21:57). Paper only: no order ever left this PC.

## Summary

- Runs started: 1; clean shutdowns: 0; still running or ended by a crash or kill: 1 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 60, approved 8, orders 8, paper fills 7, btc-speed events 48 and trades 60.
- Paper P&L to the end of the window: btc-speed -7.79 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 7 | 30.29 | 0.00 | 0.4959 | 0.00 | 23.00 | 0 | 0.00 | -7.7879 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 60 intents, 8 approved, 52 rejected: REDUCING 52.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

Latest distinct rejections:

| Time UTC | Strategy | Reason | Binding cap |
|---|---|---|---|
| 2026-10-13 16:19:43 | btc-speed | REDUCING: only exposure-reducing orders | - |

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | taker | 8 | 7 | 54 | 0.5610 | 0.4959 |

Merges of YES+NO pairs: 0; paper redemptions: 7.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| btc-speed | 5 s | 7 | +4.05c | +1.25c | 0 |
| btc-speed | 60 s | 7 | +0.55c | +3.88c | 0 |
| btc-speed | 300 s | 1 | -14.00c | - | 6 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-v4-eth-bybit-c**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 7 in 7 markets (needs 200), unresolved 0, mean -1.1126 USD, cluster SE 1.1165, total -7.7879 USD. Verdict: **running (7 of 200)**.
- **Paper-fill realism** (btc-speed at real tape prices): 4 of 7 resolved trades repriced at what real takers paid in our order's second. Paper -3.47 USD -> best case -4.16 (cheapest real price), typical -5.16 (median real price); real takers paid a median +7.5c over our fill. Paper assumes we win every race for the cheapest ask.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-13 06:31:25), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-13 06:31:25), `btc-speed-v4-eth-bybit-c` (sha256 cbb49bb7298f5753, written 2026-10-13 06:31:25).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

48 causal ETH moves (>= 6.0 bp in 2 s) and 60 trades sent to the kernel. Per mapped market: trade 60, ask above max price 18, ends too soon 13, stale book 2, no ask 2, already holding this market 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-13 11:50:11 | -7.6 | 0x714a5ca3: trade; 0x8b9e20da: ask above max price |
| 2026-10-13 11:53:15 | -6.0 | 0x714a5ca3: trade; 0x8b9e20da: ask above max price |
| 2026-10-13 12:01:31 | +6.2 | 0x38d3819a: trade; 0xe2bb440c: trade |
| 2026-10-13 12:03:41 | -6.0 | 0x38d3819a: trade; 0xe2bb440c: trade |
| 2026-10-13 12:16:23 | +6.1 | 0x75378160: trade; 0xdfeb913c: trade |
| 2026-10-13 12:25:08 | +6.4 | 0x1c91f0ee: trade; 0x75378160: trade |
| 2026-10-13 12:37:43 | -6.2 | 0x93e3561c: trade; 0xdf3b745e: trade |
| 2026-10-13 12:49:56 | +6.1 | 0xaae8cdd5: trade; 0xfe716ffa: ends too soon |
| 2026-10-13 13:32:06 | -6.2 | 0x3e5259f5: trade; 0x4598fbd9: trade |
| 2026-10-13 13:33:48 | -6.7 | 0x3e5259f5: trade; 0x4598fbd9: trade |
| 2026-10-13 13:36:29 | +6.2 | 0x3e5259f5: trade; 0xc2941e0e: trade |
| 2026-10-13 13:37:33 | +6.0 | 0x3e5259f5: trade; 0xc2941e0e: ask above max price |
| 2026-10-13 13:38:56 | +6.6 | 0x3e5259f5: ask above max price; 0xc2941e0e: no ask |
| 2026-10-13 13:44:00 | +6.0 | 0x3e5259f5: ends too soon; 0x67063d5a: ends too soon |
| 2026-10-13 13:45:34 | +6.1 | 0xdb454c52: trade; 0xe11879ee: trade |
| 2026-10-13 13:49:39 | -7.1 | 0xdb454c52: ends too soon; 0xe11879ee: trade |
| 2026-10-13 14:05:52 | +6.0 | 0x16e53f02: trade; 0x612b6061: ask above max price |
| 2026-10-13 14:11:57 | +7.0 | 0x3c517a26: ask above max price; 0x612b6061: ask above max price |
| 2026-10-13 14:13:05 | -6.1 | 0x3c517a26: trade; 0x612b6061: trade |
| 2026-10-13 14:23:40 | +6.1 | 0xf10d3b63: trade; 0xfcdfe056: trade |
| 2026-10-13 14:33:58 | -6.3 | 0x0c352d1c: trade; 0x7e23bf1c: trade |
| 2026-10-13 14:51:26 | -6.5 | 0x49a47e48: trade; 0x54c27b33: trade |
| 2026-10-13 15:19:52 | -7.2 | 0x01085523: ends too soon; 0x307bd1d9: ask above max price |
| 2026-10-13 15:32:44 | -6.2 | 0x26ed38b3: trade; 0xd870013e: trade |
| 2026-10-13 15:38:00 | -6.4 | 0x3f9ef948: ask above max price; 0xd870013e: trade |
| 2026-10-13 15:49:25 | +6.2 | 0x141e5a3d: ends too soon; 0x44878605: trade |
| 2026-10-13 15:51:45 | -6.0 | 0x0b0ecc16: trade; 0x44878605: trade |
| 2026-10-13 15:56:26 | +6.1 | 0x2375e67a: trade; 0x44878605: trade |
| 2026-10-13 16:05:02 | -7.4 | 0xaa06fb87: trade; 0xacb90a02: trade |
| 2026-10-13 16:19:43 | -6.5 | 0x6ad1d46a: ends too soon; 0xcd7982ed: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-13 12:01:31 | 0xe2bb440c | 5m | 0.19 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 12:03:41 | 0x38d3819a | 15m | 0.53 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 12:03:41 | 0xe2bb440c | 5m | 0.59 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 12:16:23 | 0xdfeb913c | 5m | 0.1 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 12:16:23 | 0x75378160 | 15m | 0.24 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 12:25:08 | 0x75378160 | 15m | 0.7 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 12:25:08 | 0x1c91f0ee | 5m | 0.82 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 12:37:43 | 0x93e3561c | 15m | 0.24 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 12:37:43 | 0xdf3b745e | 5m | 0.03 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 12:49:56 | 0xaae8cdd5 | 15m | 0.75 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 13:32:06 | 0x4598fbd9 | 5m | 0.21 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 13:32:06 | 0x3e5259f5 | 15m | 0.33 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 13:33:48 | 0x4598fbd9 | 5m | 0.62 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 13:33:48 | 0x3e5259f5 | 15m | 0.53 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 13:36:29 | 0xc2941e0e | 5m | 0.35 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 13:36:29 | 0x3e5259f5 | 15m | 0.23 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 13:37:33 | 0x3e5259f5 | 15m | 0.75 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 13:45:34 | 0xdb454c52 | 5m | 0.49 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 13:45:34 | 0xe11879ee | 15m | 0.48 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 13:49:39 | 0xe11879ee | 15m | 0.48 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 14:05:52 | 0x16e53f02 | 5m | 0.68 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 14:13:05 | 0x612b6061 | 15m | 0.006 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 14:13:05 | 0x3c517a26 | 5m | 0.01 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 14:23:40 | 0xf10d3b63 | 15m | 0.34 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 14:23:40 | 0xfcdfe056 | 5m | 0.3 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 14:33:58 | 0x7e23bf1c | 5m | 0.61 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 14:33:58 | 0x0c352d1c | 15m | 0.53 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 14:51:26 | 0x54c27b33 | 15m | 0.59 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 14:51:26 | 0x49a47e48 | 5m | 0.85 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 15:32:44 | 0x26ed38b3 | 5m | 0.51 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 15:32:44 | 0xd870013e | 15m | 0.52 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 15:38:00 | 0xd870013e | 15m | 0.8 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 15:49:25 | 0x44878605 | 15m | 0.23 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 15:51:45 | 0x44878605 | 15m | 0.36 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 15:51:45 | 0x0b0ecc16 | 5m | 0.11 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 15:56:26 | 0x44878605 | 15m | 0.82 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 15:56:26 | 0x2375e67a | 5m | 0.39 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 16:05:02 | 0xaa06fb87 | 15m | 0.22 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 16:05:02 | 0xacb90a02 | 5m | 0.64 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-13 16:19:43 | 0xcd7982ed | 15m | 0.34 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 592, median 238, p90 304, min 199, max 972.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 200296, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 2.5, max 112.0.
- Binance event time to local receive (network + clock offset): n 200296, median of minute medians -848.0, worst minute p90 6167.0, worst minute p99 7378.9, max 8510.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 330538, median of minute medians 6.6, worst minute p90 63.0, worst minute p99 172.6, max 343.5.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 48, median -445, p90 80, min -1029, max 317.
- Local receive to decision: n 48, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 48, median 387, p90 502, min 355, max 698.

## Risk, reconciliation, invariants and audit

- Trips: 4: global REDUCING (stale feed dvol:BTC: 600771 ms, breaker:stale_feed); global REDUCING (stale feed dvol:ETH: 600771 ms, breaker:stale_feed); btc-speed REDUCING (strategy daily loss 7.46 USD > 7.31 (start of day -0.33), breaker:strategy); global ACTIVE (reset, human:DELL-feed).
- Human resets: 1; halts confirmed by zero open orders: 0.
- Reconciles: 120 (startup 1, periodic 119); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 87 records, head 6d3f224fbd862b17; last head anchored in the ledger: 0 records, None (startup, 2026-10-13 06:31:25).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit-c | 7 | 200 / 100 | 17.05 | 11 |

Elapsed since the first run: 0.41 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethc --date 2026-10-13 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethc_2026-10-13.md --title "paper_ethc day 1: 2026-10-13 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **1 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **0 of 0** (need 5+, all clean)
- Running time: 9.9 hours (0.41 days of 24 h)

| UTC day | Hours running |
|---|---|
| 2026-10-13 | 9.9 |
