# paper_ethmk day 14: 2026-11-02 (UTC)

Ledger `data/trader/paper_ethmk`, window 2026-11-02 00:00:00 to 2026-11-03 00:00:00 UTC (data from 2026-11-02 00:00:08 to 2026-11-02 16:23:13). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 33, approved 33, orders 33, paper fills 0, btc-speed events 66 and trades 34.
- Paper P&L to the end of the window: no fills yet.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 33 intents, 33 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | maker | 33 | 0 | 0 | - | 0.0000 |

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

66 causal ETH moves (>= 6.0 bp in 2 s) and 34 trades sent to the kernel. Per mapped market: trade 34, ends too soon 22, ask above max price 8, no ask 1, stale signal 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-11-02 14:34:54 | +6.3 | 0xdd1b9849: trade |
| 2026-11-02 14:37:02 | -6.9 | 0xdd1b9849: trade |
| 2026-11-02 14:38:42 | -7.4 | 0xdd1b9849: trade |
| 2026-11-02 14:41:33 | -6.5 | 0xdd1b9849: ends too soon |
| 2026-11-02 14:44:39 | +6.1 | 0xdd1b9849: ends too soon |
| 2026-11-02 14:48:45 | -9.0 | 0x5c62c60c: trade |
| 2026-11-02 14:50:38 | -6.5 | 0x5c62c60c: trade |
| 2026-11-02 14:54:46 | -6.0 | 0x5c62c60c: trade |
| 2026-11-02 14:56:15 | -6.2 | 0x5c62c60c: ends too soon |
| 2026-11-02 14:59:59 | +6.3 | 0x5c62c60c: ends too soon |
| 2026-11-02 15:02:17 | +6.2 | 0xac606ffc: trade |
| 2026-11-02 15:03:39 | -6.4 | 0xac606ffc: trade |
| 2026-11-02 15:05:27 | +6.6 | 0xac606ffc: trade |
| 2026-11-02 15:07:05 | +6.0 | 0xac606ffc: trade |
| 2026-11-02 15:09:56 | +6.3 | 0xac606ffc: ask above max price |
| 2026-11-02 15:15:24 | -6.5 | 0x92707243: trade |
| 2026-11-02 15:26:08 | +6.0 | 0x92707243: ends too soon |
| 2026-11-02 15:38:57 | -6.3 | 0xe3f32cdc: ask above max price |
| 2026-11-02 15:41:54 | -7.0 | 0xe3f32cdc: ends too soon |
| 2026-11-02 15:58:09 | -8.9 | 0x37d68fc1: ends too soon |
| 2026-11-02 16:00:13 | -6.4 | 0x0382603f: trade |
| 2026-11-02 16:02:33 | -6.5 | 0x0382603f: stale signal |
| 2026-11-02 16:03:49 | +6.7 | 0x0382603f: trade |
| 2026-11-02 16:08:42 | -6.3 | 0x0382603f: trade |
| 2026-11-02 16:10:09 | -6.2 | 0x0382603f: ends too soon |
| 2026-11-02 16:11:11 | -6.8 | 0x0382603f: ends too soon |
| 2026-11-02 16:13:08 | -6.2 | 0x0382603f: ends too soon |
| 2026-11-02 16:17:10 | -6.2 | 0x34e1633a: trade |
| 2026-11-02 16:21:28 | -6.1 | 0x34e1633a: trade |
| 2026-11-02 16:23:13 | +6.8 | 0x34e1633a: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-02 00:00:34 | 0xdb63fbd1 | 15m | 0.69 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 05:21:58 | 0x8a9c8053 | 15m | 0.36 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 06:20:21 | 0x73a0b3fe | 15m | 0.19 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 07:35:16 | 0xbe0084c9 | 15m | 0.83 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 08:49:35 | 0x0523b707 | 15m | 0.71 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 09:09:41 | 0xf776cf08 | 15m | 0.26 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 10:22:55 | 0xaa50f268 | 15m | 0.36 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 11:39:55 | 0x0d146bee | 15m | 0.66 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 12:15:48 | 0x32c824e0 | 15m | 0.55 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 13:36:50 | 0xdbf7e062 | 15m | 0.76 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 13:45:37 | 0x1414a00e | 15m | 0.55 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 13:46:51 | 0x1414a00e | 15m | 0.55 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 13:49:08 | 0x1414a00e | 15m | 0.83 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 14:00:55 | 0xb8cff587 | 15m | 0.63 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 14:30:08 | 0xdd1b9849 | 15m | 0.36 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 14:31:35 | 0xdd1b9849 | 15m | 0.46 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 14:32:46 | 0xdd1b9849 | 15m | 0.79 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 14:34:54 | 0xdd1b9849 | 15m | 0.84 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 14:37:02 | 0xdd1b9849 | 15m | 0.09 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 14:38:42 | 0xdd1b9849 | 15m | 0.25 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 14:48:45 | 0x5c62c60c | 15m | 0.33 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 14:50:38 | 0x5c62c60c | 15m | 0.54 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 14:54:46 | 0x5c62c60c | 15m | 0.46 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 15:02:17 | 0xac606ffc | 15m | 0.35 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 15:03:39 | 0xac606ffc | 15m | 0.56 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 15:05:27 | 0xac606ffc | 15m | 0.46 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 15:07:05 | 0xac606ffc | 15m | 0.53 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 15:15:24 | 0x92707243 | 15m | 0.58 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 16:00:13 | 0x0382603f | 15m | 0.55 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 16:03:49 | 0x0382603f | 15m | 0.7 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 16:08:42 | 0x0382603f | 15m | 0.2 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 16:17:10 | 0x34e1633a | 15m | 0.42 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 16:21:28 | 0x34e1633a | 15m | 0.31 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-02 16:23:13 | 0x34e1633a | 15m | 0.56 | approved | open | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 751, median 220, p90 243, min 193, max 498.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 269599, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 9.9, max 86.0.
- Binance event time to local receive (network + clock offset): n 269599, median of minute medians -90.0, worst minute p90 4360.0, worst minute p99 8003.6, max 9686.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 410699, median of minute medians 9.6, worst minute p90 16.8, worst minute p99 2937072.5, max 13985359.5.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 66, median -34, p90 124, min -303, max 2252.
- Local receive to decision: n 66, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 66, median 368, p90 397, min 343, max 520.

## Risk, reconciliation, invariants and audit

- Trips: 4: global REDUCING (stale feed polymarket:crypto-fast: 13979457 ms, breaker:stale_feed); global REDUCING (stale feed binance:ETH: 13981466 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 13979457 ms, breaker:stale_feed); global ACTIVE (reset, human:DELL-feed).
- Human resets: 43; halts confirmed by zero open orders: 0.
- Reconciles: 150 (periodic 150); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 1408 records, head 3e53cd6a78bac1d1; last head anchored in the ledger: 774 records, 98146af57cfcca98 (startup, 2026-10-28 18:21:55).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-mk-eth-bybit | 0 | 200 / 100 | 0.00 | no evidence yet |

Elapsed since the first run: 13.13 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethmk --date 2026-11-02 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethmk_2026-11-02.md --title "paper_ethmk day 14: 2026-11-02 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **14 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **3 of 3** (need 5+, all clean)
- Running time: 214.9 hours (8.95 days of 24 h)

| UTC day | Hours running |
|---|---|
| 2026-10-20 | 7.5 |
| 2026-10-21 | 17.6 |
| 2026-10-22 | 15.9 |
| 2026-10-23 | 16.3 |
| 2026-10-24 | 6.7 |
| 2026-10-25 | 17.2 |
| 2026-10-26 | 18.1 |
| 2026-10-27 | 18.3 |
| 2026-10-28 | 5.6 |
| 2026-10-29 | 19.6 |
| 2026-10-30 | 12.8 |
| 2026-10-31 | 22.8 |
| 2026-11-01 | 24.0 |
| 2026-11-02 | 12.5 |
