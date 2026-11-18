# paper_ethmk day 24: 2026-11-12 (UTC)

Ledger `data/trader/paper_ethmk`, window 2026-11-12 00:00:00 to 2026-11-13 00:00:00 UTC (data from 2026-11-12 07:32:06 to 2026-11-12 14:27:55). Paper only: no order ever left this PC.

## Summary

- Runs started: 1; clean shutdowns: 0; still running or ended by a crash or kill: 1 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 2, approved 2, orders 2, paper fills 0, btc-speed events 16 and trades 2.
- Paper P&L to the end of the window: no fills yet.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 2 intents, 2 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | maker | 2 | 0 | 0 | - | 0.0000 |

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

16 causal ETH moves (>= 6.0 bp in 2 s) and 2 trades sent to the kernel. Per mapped market: ask above max price 3, trade 2, ends too soon 2.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-11-12 11:30:41 | -6.1 | 0xf0d89d1f: trade |
| 2026-11-12 14:00:46 | +6.3 | - |
| 2026-11-12 14:09:58 | -6.1 | - |
| 2026-11-12 14:11:37 | -6.9 | - |
| 2026-11-12 14:13:05 | +7.3 | - |
| 2026-11-12 14:14:33 | +6.4 | - |
| 2026-11-12 14:16:20 | -7.0 | - |
| 2026-11-12 14:17:48 | -6.9 | - |
| 2026-11-12 14:18:55 | -6.8 | - |
| 2026-11-12 14:20:05 | +6.1 | - |
| 2026-11-12 14:21:45 | -6.1 | 0x14da5729: ask above max price |
| 2026-11-12 14:22:46 | -7.0 | 0x14da5729: ask above max price |
| 2026-11-12 14:23:52 | -6.5 | 0x14da5729: ask above max price |
| 2026-11-12 14:24:59 | +7.0 | 0x14da5729: trade |
| 2026-11-12 14:26:52 | -6.9 | 0x14da5729: ends too soon |
| 2026-11-12 14:27:53 | -6.6 | 0x14da5729: ends too soon |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-12 11:30:41 | 0xf0d89d1f | 15m | 0.7 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-12 14:24:59 | 0x14da5729 | 15m | 0.009 | approved | open | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 196, median 204, p90 235, min 184, max 579.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 40385, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 29.5, max 47.0.
- Binance event time to local receive (network + clock offset): n 40385, median of minute medians -153.8, worst minute p90 7931530.0, worst minute p99 7932481.3, max 7932462.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 105073, median of minute medians 9.5, worst minute p90 304.3, worst minute p99 1912954.6, max 7931641.4.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 16, median -344, p90 -38, min -365, max 87.
- Local receive to decision: n 16, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 16, median 360, p90 533, min 350, max 729.

## Risk, reconciliation, invariants and audit

- Trips: 20: global REDUCING (stale feed polymarket:crypto-fast: 885342 ms, breaker:stale_feed); global REDUCING (stale feed binance:ETH: 888800 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 885342 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 2517872 ms, breaker:stale_feed); global REDUCING (stale feed binance:ETH: 2518479 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 2517872 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 1113895 ms, breaker:stale_feed); global REDUCING (stale feed binance:ETH: 1116196 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 1113895 ms, breaker:stale_feed); global REDUCING (stale feed polymarket:crypto-fast: 184749 ms, breaker:stale_feed); global REDUCING (stale feed binance:ETH: 187031 ms, breaker:stale_feed); global REDUCING (stale feed polymarket: 184749 ms, breaker:stale_feed); global ACTIVE (reset, human:DELL-feed); global REDUCING (stale feed polymarket:crypto-fast: 7931742 ms, breaker:stale_feed); global REDUCING (stale feed binance:ETH: 7931713 ms, breaker:stale_feed).
- Human resets: 321; halts confirmed by zero open orders: 0.
- Reconciles: 43 (startup 1, periodic 42); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 2243 records, head 643aa5f36a2bca69; last head anchored in the ledger: 2216 records, 19bacae27bfcf667 (startup, 2026-11-12 07:32:06).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-mk-eth-bybit | 0 | 200 / 100 | 0.00 | no evidence yet |

Elapsed since the first run: 23.13 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethmk --date 2026-11-12 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethmk_2026-11-12.md --title "paper_ethmk day 24: 2026-11-12 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **MET.**

- Days without a violation: **24 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **8 of 8** (need 5+, all clean)
- Running time: 285.7 hours (11.91 days of 24 h)

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
| 2026-11-02 | 20.1 |
| 2026-11-03 | 14.4 |
| 2026-11-04 | 19.4 |
| 2026-11-06 | 10.8 |
| 2026-11-07 | 4.5 |
| 2026-11-10 | 6.5 |
| 2026-11-11 | 4.4 |
| 2026-11-12 | 3.3 |
