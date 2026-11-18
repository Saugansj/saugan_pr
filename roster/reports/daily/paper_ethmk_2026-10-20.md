# paper_ethmk day 1: 2026-10-20 (UTC)

Ledger `data/trader/paper_ethmk`, window 2026-10-20 00:00:00 to 2026-10-21 00:00:00 UTC (data from 2026-10-20 13:10:40 to 2026-10-20 16:21:51). Paper only: no order ever left this PC.

## Summary

- Runs started: 1; clean shutdowns: 0; still running or ended by a crash or kill: 1 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 44, approved 44, orders 44, paper fills 0, btc-speed events 69 and trades 44.
- Paper P&L to the end of the window: no fills yet.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 44 intents, 44 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | maker | 44 | 0 | 0 | - | 0.0000 |

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

69 causal ETH moves (>= 6.0 bp in 2 s) and 44 trades sent to the kernel. Per mapped market: trade 44, ends too soon 22, ask above max price 2, no ask 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-10-20 14:42:09 | -6.4 | 0x7285396d: ends too soon |
| 2026-10-20 14:43:21 | -6.0 | 0x7285396d: ends too soon |
| 2026-10-20 14:44:40 | -6.1 | 0x7285396d: ends too soon |
| 2026-10-20 14:47:05 | -6.0 | 0x48cdab44: trade |
| 2026-10-20 14:54:45 | +6.8 | 0x48cdab44: trade |
| 2026-10-20 14:57:06 | +6.1 | 0x48cdab44: ends too soon |
| 2026-10-20 14:58:08 | -6.3 | 0x48cdab44: ends too soon |
| 2026-10-20 15:00:05 | -6.8 | 0x0dc6b4e0: trade |
| 2026-10-20 15:03:14 | +6.7 | 0x0dc6b4e0: trade |
| 2026-10-20 15:05:29 | +6.9 | 0x0dc6b4e0: trade |
| 2026-10-20 15:12:19 | -9.6 | 0x0dc6b4e0: ends too soon |
| 2026-10-20 15:13:24 | +6.1 | 0x0dc6b4e0: ends too soon |
| 2026-10-20 15:14:27 | -6.0 | 0x0dc6b4e0: ends too soon |
| 2026-10-20 15:15:31 | +6.2 | 0x58823b59: trade |
| 2026-10-20 15:16:32 | +6.1 | 0x58823b59: trade |
| 2026-10-20 15:17:58 | -6.9 | 0x58823b59: trade |
| 2026-10-20 15:20:19 | -6.1 | 0x58823b59: trade |
| 2026-10-20 15:21:32 | -6.2 | 0x58823b59: trade |
| 2026-10-20 15:22:46 | +6.1 | 0x58823b59: trade |
| 2026-10-20 15:24:03 | -6.1 | 0x58823b59: trade |
| 2026-10-20 15:30:12 | +6.0 | 0xa4755395: trade |
| 2026-10-20 15:31:16 | +6.4 | 0xa4755395: trade |
| 2026-10-20 15:33:02 | +6.2 | 0xa4755395: trade |
| 2026-10-20 15:37:54 | +6.2 | 0xa4755395: trade |
| 2026-10-20 15:42:03 | +6.3 | 0xa4755395: ends too soon |
| 2026-10-20 15:43:34 | -6.2 | 0xa4755395: ends too soon |
| 2026-10-20 15:45:34 | -6.8 | 0x90002e58: trade |
| 2026-10-20 15:47:04 | +6.1 | 0x90002e58: trade |
| 2026-10-20 16:07:19 | -9.3 | 0x4e8f02ca: trade |
| 2026-10-20 16:20:25 | +7.4 | 0x98488e37: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-20 13:37:16 | 0xe256153e | 15m | 0.24 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 13:46:17 | 0x82d0ddbf | 15m | 0.27 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 13:47:34 | 0x82d0ddbf | 15m | 0.22 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 13:50:02 | 0x82d0ddbf | 15m | 0.13 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 14:01:04 | 0x7c2f97b0 | 15m | 0.61 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 14:02:07 | 0x7c2f97b0 | 15m | 0.2 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 14:03:21 | 0x7c2f97b0 | 15m | 0.22 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 14:07:52 | 0x7c2f97b0 | 15m | 0.02 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 14:15:35 | 0x760acb62 | 15m | 0.36 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 14:16:37 | 0x760acb62 | 15m | 0.53 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 14:17:47 | 0x760acb62 | 15m | 0.67 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 14:18:51 | 0x760acb62 | 15m | 0.41 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 14:20:06 | 0x760acb62 | 15m | 0.53 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 14:21:31 | 0x760acb62 | 15m | 0.67 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 14:23:50 | 0x760acb62 | 15m | 0.59 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 14:30:42 | 0x7285396d | 15m | 0.6 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 14:31:44 | 0x7285396d | 15m | 0.43 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 14:33:52 | 0x7285396d | 15m | 0.65 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 14:35:42 | 0x7285396d | 15m | 0.56 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 14:38:41 | 0x7285396d | 15m | 0.36 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 14:47:05 | 0x48cdab44 | 15m | 0.67 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 14:54:45 | 0x48cdab44 | 15m | 0.25 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 15:00:05 | 0x0dc6b4e0 | 15m | 0.57 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 15:03:14 | 0x0dc6b4e0 | 15m | 0.08 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 15:05:29 | 0x0dc6b4e0 | 15m | 0.03 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 15:15:31 | 0x58823b59 | 15m | 0.43 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 15:16:32 | 0x58823b59 | 15m | 0.69 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 15:17:58 | 0x58823b59 | 15m | 0.21 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 15:20:19 | 0x58823b59 | 15m | 0.3 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 15:21:32 | 0x58823b59 | 15m | 0.5 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 15:22:46 | 0x58823b59 | 15m | 0.44 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 15:24:03 | 0x58823b59 | 15m | 0.78 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 15:30:12 | 0xa4755395 | 15m | 0.61 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 15:31:16 | 0xa4755395 | 15m | 0.51 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 15:33:02 | 0xa4755395 | 15m | 0.43 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 15:37:54 | 0xa4755395 | 15m | 0.64 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 15:45:34 | 0x90002e58 | 15m | 0.78 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 15:47:04 | 0x90002e58 | 15m | 0.29 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 16:07:19 | 0x4e8f02ca | 15m | 0.44 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-10-20 16:20:25 | 0x98488e37 | 15m | 0.16 | approved | open | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 192, median 227, p90 243, min 201, max 396.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 137492, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 1.7, max 53.0.
- Binance event time to local receive (network + clock offset): n 137492, median of minute medians -228.0, worst minute p90 13.4, worst minute p99 1291.9, max 1298.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 104881, median of minute medians 9.6, worst minute p90 38.2, worst minute p99 126.6, max 212.3.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 69, median -241, p90 -104, min -294, max 95.
- Local receive to decision: n 69, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 69, median 376, p90 390, min 353, max 546.

## Risk, reconciliation, invariants and audit

- Trips: 0.
- Human resets: 0; halts confirmed by zero open orders: 0.
- Reconciles: 40 (startup 1, periodic 39); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 133 records, head dc2abf66df024d16; last head anchored in the ledger: 0 records, None (startup, 2026-10-20 13:10:40).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-mk-eth-bybit | 0 | 200 / 100 | 0.00 | no evidence yet |

Elapsed since the first run: 0.13 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethmk --date 2026-10-20 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethmk_2026-10-20.md --title "paper_ethmk day 1: 2026-10-20 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **1 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **0 of 0** (need 5+, all clean)
- Running time: 3.2 hours (0.13 days of 24 h)

| UTC day | Hours running |
|---|---|
| 2026-10-20 | 3.2 |
