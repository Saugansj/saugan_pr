# paper_ethmk day 2: 2026-10-21 (UTC)

Ledger `data/trader/paper_ethmk`, window 2026-10-21 00:00:00 to 2026-10-22 00:00:00 UTC (data from 2026-10-21 01:05:48 to 2026-10-21 16:21:05). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 28, approved 28, orders 28, paper fills 0, btc-speed events 61 and trades 28.
- Paper P&L to the end of the window: no fills yet.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 28 intents, 28 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | maker | 28 | 0 | 0 | - | 0.0000 |

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

61 causal ETH moves (>= 6.0 bp in 2 s) and 28 trades sent to the kernel. Per mapped market: trade 28, ends too soon 18, ask above max price 14, no ask 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-21 14:30:48 | +7.0 | 0x8e6b93b2: trade |
| 2026-10-21 14:32:53 | +6.3 | 0x8e6b93b2: trade |
| 2026-10-21 14:39:30 | -6.4 | 0x8e6b93b2: trade |
| 2026-10-21 14:43:07 | +6.1 | 0x8e6b93b2: ends too soon |
| 2026-10-21 14:48:08 | +6.0 | 0x3ccacd51: trade |
| 2026-10-21 14:49:35 | +6.2 | 0x3ccacd51: trade |
| 2026-10-21 14:51:55 | +7.2 | 0x3ccacd51: ask above max price |
| 2026-10-21 14:53:02 | +6.8 | 0x3ccacd51: ask above max price |
| 2026-10-21 14:55:02 | +6.0 | 0x3ccacd51: ends too soon |
| 2026-10-21 14:58:29 | +6.3 | 0x3ccacd51: ends too soon |
| 2026-10-21 15:00:59 | +6.2 | 0x19c73826: trade |
| 2026-10-21 15:04:30 | +6.1 | 0x19c73826: trade |
| 2026-10-21 15:05:57 | +7.9 | 0x19c73826: trade |
| 2026-10-21 15:07:13 | +6.1 | 0x19c73826: ask above max price |
| 2026-10-21 15:08:15 | +6.2 | 0x19c73826: ask above max price |
| 2026-10-21 15:09:20 | -6.7 | 0x19c73826: trade |
| 2026-10-21 15:11:20 | -7.4 | 0x19c73826: ends too soon |
| 2026-10-21 15:12:21 | -6.1 | 0x19c73826: ends too soon |
| 2026-10-21 15:14:40 | -6.1 | 0x19c73826: ends too soon |
| 2026-10-21 15:17:00 | -7.0 | 0xb9be801d: trade |
| 2026-10-21 15:18:43 | -6.0 | 0xb9be801d: ask above max price |
| 2026-10-21 15:25:12 | +6.9 | 0xb9be801d: ends too soon |
| 2026-10-21 15:33:38 | +7.0 | 0x4dea41dc: ask above max price |
| 2026-10-21 15:39:39 | +6.2 | 0x4dea41dc: ask above max price |
| 2026-10-21 15:44:38 | -8.1 | 0x4dea41dc: ends too soon |
| 2026-10-21 15:56:25 | -6.6 | 0x09b5995b: ends too soon |
| 2026-10-21 15:58:02 | +7.5 | 0x09b5995b: ends too soon |
| 2026-10-21 16:04:46 | -8.4 | 0x3ea8792f: trade |
| 2026-10-21 16:06:52 | +6.1 | 0x3ea8792f: trade |
| 2026-10-21 16:09:51 | +6.4 | 0x3ea8792f: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-21 08:49:42 | 0x7237292a | 15m | 0.8 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 08:51:32 | 0x7237292a | 15m | 0.47 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 09:38:42 | 0x5715fa26 | 15m | 0.74 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 11:30:48 | 0x299d877d | 15m | 0.72 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 13:01:02 | 0xbc16d509 | 15m | 0.83 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 13:30:09 | 0x0c562854 | 15m | 0.69 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 13:31:20 | 0x0c562854 | 15m | 0.74 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 13:32:30 | 0x0c562854 | 15m | 0.18 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 13:37:23 | 0x0c562854 | 15m | 0.01 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 13:45:27 | 0x588d0f8f | 15m | 0.51 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 13:47:28 | 0x588d0f8f | 15m | 0.63 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 13:48:49 | 0x588d0f8f | 15m | 0.73 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:02:42 | 0xc5673657 | 15m | 0.67 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:04:18 | 0xc5673657 | 15m | 0.73 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:08:01 | 0xc5673657 | 15m | 0.06 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:30:48 | 0x8e6b93b2 | 15m | 0.62 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:32:53 | 0x8e6b93b2 | 15m | 0.54 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:39:30 | 0x8e6b93b2 | 15m | 0.28 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:48:08 | 0x3ccacd51 | 15m | 0.71 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 14:49:35 | 0x3ccacd51 | 15m | 0.79 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 15:00:59 | 0x19c73826 | 15m | 0.58 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 15:04:30 | 0x19c73826 | 15m | 0.78 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 15:05:57 | 0x19c73826 | 15m | 0.84 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 15:09:20 | 0x19c73826 | 15m | 0.04 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 15:17:00 | 0xb9be801d | 15m | 0.75 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 16:04:46 | 0x3ea8792f | 15m | 0.64 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 16:06:52 | 0x3ea8792f | 15m | 0.13 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-21 16:09:51 | 0x3ea8792f | 15m | 0.79 | approved | open | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 601, median 239, p90 270, min 200, max 561.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 218840, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 21.7, max 48.0.
- Binance event time to local receive (network + clock offset): n 218840, median of minute medians -99.0, worst minute p90 831.1, worst minute p99 2075.6, max 2716.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 329953, median of minute medians 9.6, worst minute p90 38.9, worst minute p99 24015574.0, max 18762216.0.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 61, median -231, p90 -50, min -301, max 247.
- Local receive to decision: n 61, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 61, median 378, p90 406, min 358, max 504.

## Risk, reconciliation, invariants and audit

- Trips: 8: global REDUCING (stale feed polymarket:crypto-fast: 14369186 ms, breaker:stale_feed); global REDUCING (stale feed binance:ETH: 14381054 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 14369186 ms, breaker:stale_feed); global ACTIVE (reset, human:DELL-feed); global REDUCING (stale feed binance:ETH: 60612 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 60563 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 60563 ms, breaker:stale_feed); global ACTIVE (reset, human:DELL-feed).
- Human resets: 2; halts confirmed by zero open orders: 0.
- Reconciles: 122 (periodic 122); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 242 records, head ec1117b2f3cd596a; last head anchored in the ledger: 0 records, None (startup, 2026-10-20 13:10:40).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-mk-eth-bybit | 0 | 200 / 100 | 0.00 | no evidence yet |

Elapsed since the first run: 1.13 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethmk --date 2026-10-21 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethmk_2026-10-21.md --title "paper_ethmk day 2: 2026-10-21 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **2 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **0 of 0** (need 5+, all clean)
- Running time: 17.5 hours (0.73 days of 24 h)

| UTC day | Hours running |
|---|---|
| 2026-10-20 | 7.5 |
| 2026-10-21 | 10.0 |
