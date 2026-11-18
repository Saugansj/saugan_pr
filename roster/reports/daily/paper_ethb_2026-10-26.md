# paper_ethb day 16: 2026-10-26 (UTC)

Ledger `data/trader/paper_ethb`, window 2026-10-26 00:00:00 to 2026-10-27 00:00:00 UTC (data from 2026-10-26 01:00:17 to 2026-10-26 16:20:28). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 89, approved 2, orders 2, paper fills 2, btc-speed events 76 and trades 89.
- Paper P&L to the end of the window: btc-speed +136.70 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| btc-speed | 349 | 784.42 | 0.00 | 22.3777 | 0.00 | 943.50 | 0 | 0.00 | +136.7030 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 89 intents, 2 approved, 87 rejected: REDUCING 87.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

Latest distinct rejections:

| Time UTC | Strategy | Reason | Binding cap |
|---|---|---|---|
| 2026-10-26 16:16:06 | btc-speed | REDUCING: only exposure-reducing orders | - |

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | taker | 2 | 2 | 10 | 0.7950 | 0.1141 |

Merges of YES+NO pairs: 0; paper redemptions: 3.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| btc-speed | 5 s | 2 | +3.00c | +2.50c | 0 |
| btc-speed | 60 s | 2 | -15.25c | +10.25c | 0 |
| btc-speed | 300 s | 2 | -17.50c | +5.00c | 0 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v2**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 0 (needs 60), mean - USD, SE -, fills still without a 5 m markout 0. Verdict: **running (0 of 60)**.
- **btc-speed-v4-eth-bybit**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 345 in 345 markets (needs 200), unresolved 0, mean 0.3962 USD, cluster SE 0.1166, total +136.7030 USD. Verdict: **PASS**.
- **Paper-fill realism** (btc-speed at real tape prices): 290 of 345 resolved trades repriced at what real takers paid in our order's second. Paper +130.54 USD -> best case +65.36 (cheapest real price), typical +15.70 (median real price), **live estimate +10.06** (our order behind the real takers that beat us, partial fills; 67% of our shares filled); real takers paid a median +6.0c over our fill. Paper assumes we win every race for the cheapest ask. Not comparable with reports before 15 Oct.
- Pre-registrations in the ledger (immutable): `ladder-maker-v2` (sha256 d96c11b3b0eed3b0, written 2026-10-11 19:34:32), `btc-speed-v2` (sha256 9c070380c5632f7b, written 2026-10-11 19:34:32), `btc-speed-v4-eth-bybit` (sha256 04680de003a175aa, written 2026-10-11 19:34:32).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

76 causal ETH moves (>= 6.0 bp in 2 s) and 89 trades sent to the kernel. Per mapped market: trade 89, ask above max price 38, ends too soon 15, no ask 5, move started before the window 2, too little size at ask 2, already holding this market 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-26 14:00:22 | +6.2 | 0x862f64fa: trade; 0x928eb5da: trade |
| 2026-10-26 14:01:25 | -6.5 | 0x862f64fa: trade; 0x928eb5da: trade |
| 2026-10-26 14:03:18 | -6.9 | 0x862f64fa: trade; 0x928eb5da: trade |
| 2026-10-26 14:06:46 | -7.0 | 0x862f64fa: trade; 0xebba497d: trade |
| 2026-10-26 14:09:51 | +6.5 | 0x862f64fa: ask above max price; 0xebba497d: ends too soon |
| 2026-10-26 14:11:16 | +7.7 | 0x862f64fa: no ask; 0xec15b4dd: ask above max price |
| 2026-10-26 14:15:47 | +6.0 | 0xe3834b19: trade; 0xf0e1c0d5: trade |
| 2026-10-26 14:19:28 | +6.1 | 0xe3834b19: ask above max price; 0xf0e1c0d5: ends too soon |
| 2026-10-26 14:22:00 | -6.9 | 0x4f7cbe7e: trade; 0xe3834b19: trade |
| 2026-10-26 14:26:50 | -6.1 | 0xe3834b19: trade; 0xf8644d8a: ask above max price |
| 2026-10-26 14:30:26 | +6.7 | 0x5139324e: trade; 0xca796055: trade |
| 2026-10-26 14:32:24 | -6.9 | 0x5139324e: trade; 0xca796055: ask above max price |
| 2026-10-26 14:35:53 | +6.9 | 0x5139324e: trade; 0x6113cb08: trade |
| 2026-10-26 14:37:01 | -6.4 | 0x5139324e: trade; 0x6113cb08: trade |
| 2026-10-26 14:47:12 | -6.3 | 0x186a7ea8: trade; 0xb4e358e0: ask above max price |
| 2026-10-26 14:48:38 | -6.2 | 0x186a7ea8: trade; 0xb4e358e0: trade |
| 2026-10-26 14:50:31 | -6.2 | 0x186a7ea8: trade; 0x778a68dd: trade |
| 2026-10-26 15:04:03 | +7.2 | 0x202e940c: ends too soon; 0xd5ce8f98: too little size at ask |
| 2026-10-26 15:05:34 | +6.7 | 0xd5ce8f98: trade; 0xe49be4b2: trade |
| 2026-10-26 15:07:45 | +6.0 | 0xd5ce8f98: trade; 0xe49be4b2: trade |
| 2026-10-26 15:11:17 | -6.2 | 0x6be60d82: trade; 0xd5ce8f98: trade |
| 2026-10-26 15:18:11 | +6.1 | 0x527f5f51: trade; 0xba995d54: ask above max price |
| 2026-10-26 15:21:02 | +6.2 | 0x3fd73e6d: trade; 0x527f5f51: ask above max price |
| 2026-10-26 15:22:08 | +6.7 | 0x3fd73e6d: trade; 0x527f5f51: ask above max price |
| 2026-10-26 15:23:10 | +6.5 | 0x3fd73e6d: too little size at ask; 0x527f5f51: ask above max price |
| 2026-10-26 15:24:23 | +7.2 | 0x3fd73e6d: ends too soon; 0x527f5f51: ask above max price |
| 2026-10-26 15:37:59 | +6.9 | 0x2e54f204: ask above max price; 0xc0cb399d: ask above max price |
| 2026-10-26 15:46:45 | +6.5 | 0x444a9506: trade; 0x53068678: trade |
| 2026-10-26 16:08:07 | -6.7 | 0x5b50db7b: trade; 0xfc93858c: trade |
| 2026-10-26 16:16:06 | -6.1 | 0xa4e331c7: trade; 0xea5eed2a: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-26 14:00:22 | 0x928eb5da | 5m | 0.83 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:00:22 | 0x862f64fa | 15m | 0.7 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:01:25 | 0x928eb5da | 5m | 0.35 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:01:25 | 0x862f64fa | 15m | 0.42 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:03:18 | 0x928eb5da | 5m | 0.78 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:03:18 | 0x862f64fa | 15m | 0.58 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:06:46 | 0x862f64fa | 15m | 0.22 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:06:46 | 0xebba497d | 5m | 0.17 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:15:47 | 0xe3834b19 | 15m | 0.54 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:15:47 | 0xf0e1c0d5 | 5m | 0.56 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:22:00 | 0xe3834b19 | 15m | 0.03 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:22:00 | 0x4f7cbe7e | 5m | 0.15 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:26:50 | 0xe3834b19 | 15m | 0.61 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:30:26 | 0x5139324e | 15m | 0.49 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:30:26 | 0xca796055 | 5m | 0.51 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:32:24 | 0x5139324e | 15m | 0.64 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:35:53 | 0x5139324e | 15m | 0.53 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:35:53 | 0x6113cb08 | 5m | 0.82 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:37:01 | 0x5139324e | 15m | 0.37 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:37:01 | 0x6113cb08 | 5m | 0.08 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:47:12 | 0x186a7ea8 | 15m | 0.71 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:48:38 | 0xb4e358e0 | 5m | 0.02 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:48:38 | 0x186a7ea8 | 15m | 0.27 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:50:31 | 0x186a7ea8 | 15m | 0.31 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 14:50:31 | 0x778a68dd | 5m | 0.55 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 15:05:34 | 0xd5ce8f98 | 15m | 0.46 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 15:05:34 | 0xe49be4b2 | 5m | 0.41 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 15:07:45 | 0xd5ce8f98 | 15m | 0.68 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 15:07:45 | 0xe49be4b2 | 5m | 0.78 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 15:11:17 | 0xd5ce8f98 | 15m | 0.04 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 15:11:17 | 0x6be60d82 | 5m | 0.16 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 15:18:11 | 0x527f5f51 | 15m | 0.72 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 15:21:02 | 0x3fd73e6d | 5m | 0.77 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 15:22:08 | 0x3fd73e6d | 5m | 0.73 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 15:46:45 | 0x444a9506 | 5m | 0.46 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 15:46:45 | 0x53068678 | 15m | 0.46 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 16:08:07 | 0x5b50db7b | 15m | 0.8 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 16:08:07 | 0xfc93858c | 5m | 0.7 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 16:16:06 | 0xa4e331c7 | 5m | 0.73 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |
| 2026-10-26 16:16:06 | 0xea5eed2a | 15m | 0.64 | REDUCING: only exposure-reducing orders | - | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 626, median 226, p90 255, min 195, max 709.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 232269, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 9.1, max 59.0.
- Binance event time to local receive (network + clock offset): n 232269, median of minute medians -136.8, worst minute p90 1446.0, worst minute p99 4588.8, max 4881.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 340520, median of minute medians 9.6, worst minute p90 50.1, worst minute p99 29190053.5, max 17798823.1.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 76, median -239, p90 15, min -326, max 262.
- Local receive to decision: n 76, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 76, median 380, p90 401, min 355, max 459.

## Risk, reconciliation, invariants and audit

- Trips: 2: global ACTIVE (reset, human:DELL-feed); btc-speed REDUCING (strategy daily loss 5.02 USD > 5.00 (start of day 144.77), breaker:strategy).
- Human resets: 24; halts confirmed by zero open orders: 0.
- Reconciles: 126 (periodic 126); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 1928 records, head 6e0318c97ef02f0d; last head anchored in the ledger: 1709 records, 2c03399bc4bb6647 (startup, 2026-10-24 17:16:01).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-v4-eth-bybit | 345 | 200 / 100 | 23.21 | 0 |

Elapsed since the first run: 14.87 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethb --date 2026-10-26 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethb_2026-10-26.md --title "paper_ethb day 16: 2026-10-26 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **MET.**

- Days without a violation: **16 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **10 of 10** (need 5+, all clean)
- Running time: 171.9 hours (7.16 days of 24 h)

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
| 2026-10-26 | 10.4 |
