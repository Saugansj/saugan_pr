# paper_ethmk day 16: 2026-11-04 (UTC)

Ledger `data/trader/paper_ethmk`, window 2026-11-04 00:00:00 to 2026-11-05 00:00:00 UTC (data from 2026-11-04 00:00:43 to 2026-11-04 16:22:59). Paper only: no order ever left this PC.

## Summary

- Runs started: 0; clean shutdowns: 0; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 82, approved 82, orders 82, paper fills 0, btc-speed events 155 and trades 83.
- Paper P&L to the end of the window: no fills yet.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 0 intents, 0 approved, 0 rejected.
- **btc-speed**: 82 intents, 82 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| btc-speed | maker | 82 | 0 | 0 | - | 0.0000 |

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

155 causal ETH moves (>= 6.0 bp in 2 s) and 83 trades sent to the kernel. Per mapped market: trade 83, ends too soon 44, ask above max price 24, no ask 3, move started before the window 1.

| Event UTC | Move bp | Markets |
|---|---|---|
| 2026-11-04 15:22:31 | +6.3 | 0xeb89c131: trade |
| 2026-11-04 15:23:36 | -6.9 | 0xeb89c131: trade |
| 2026-11-04 15:25:16 | +6.2 | 0xeb89c131: ends too soon |
| 2026-11-04 15:27:09 | -6.9 | 0xeb89c131: ends too soon |
| 2026-11-04 15:29:07 | +6.4 | 0xeb89c131: ends too soon |
| 2026-11-04 15:30:48 | +6.8 | 0xb141338f: trade |
| 2026-11-04 15:32:36 | -6.9 | 0xb141338f: trade |
| 2026-11-04 15:33:38 | +6.0 | 0xb141338f: trade |
| 2026-11-04 15:34:43 | -6.1 | 0xb141338f: trade |
| 2026-11-04 15:40:16 | +6.6 | 0xb141338f: ends too soon |
| 2026-11-04 15:44:02 | +6.3 | 0xb141338f: ends too soon |
| 2026-11-04 15:45:03 | -6.8 | 0xad4834c7: trade |
| 2026-11-04 15:47:40 | +7.9 | 0xad4834c7: trade |
| 2026-11-04 15:49:38 | +6.6 | 0xad4834c7: trade |
| 2026-11-04 15:51:07 | -7.1 | 0xad4834c7: trade |
| 2026-11-04 15:52:35 | +6.0 | 0xad4834c7: trade |
| 2026-11-04 15:54:48 | -6.0 | 0xad4834c7: trade |
| 2026-11-04 15:57:00 | +6.3 | 0xad4834c7: ends too soon |
| 2026-11-04 16:00:02 | +6.5 | 0xcb6fdb82: trade |
| 2026-11-04 16:01:02 | -6.1 | 0xcb6fdb82: trade |
| 2026-11-04 16:02:15 | -6.9 | 0xcb6fdb82: trade |
| 2026-11-04 16:03:24 | +8.4 | 0xcb6fdb82: trade |
| 2026-11-04 16:04:38 | +6.8 | 0xcb6fdb82: trade |
| 2026-11-04 16:06:31 | +6.5 | 0xcb6fdb82: trade |
| 2026-11-04 16:08:08 | +6.0 | 0xcb6fdb82: ask above max price |
| 2026-11-04 16:10:32 | -8.0 | 0xcb6fdb82: ends too soon |
| 2026-11-04 16:12:22 | -6.6 | 0xcb6fdb82: ends too soon |
| 2026-11-04 16:13:57 | -6.6 | 0xcb6fdb82: ends too soon |
| 2026-11-04 16:16:47 | +6.6 | 0xeaac569f: trade |
| 2026-11-04 16:22:59 | -6.1 | 0xeaac569f: trade |

| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-04 14:35:58 | 0xae6a8691 | 15m | 0.2 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 14:37:31 | 0xae6a8691 | 15m | 0.17 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 14:45:41 | 0x6590d213 | 15m | 0.51 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 14:46:45 | 0x6590d213 | 15m | 0.56 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 14:47:45 | 0x6590d213 | 15m | 0.67 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 14:48:51 | 0x6590d213 | 15m | 0.84 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 14:49:52 | 0x6590d213 | 15m | 0.04 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 14:51:56 | 0x6590d213 | 15m | 0.03 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 14:53:07 | 0x6590d213 | 15m | 0.02 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 14:54:20 | 0x6590d213 | 15m | 0.019 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:00:05 | 0x758471de | 15m | 0.6 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:01:06 | 0x758471de | 15m | 0.76 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:06:11 | 0x758471de | 15m | 0.016 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:07:16 | 0x758471de | 15m | 0.011 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:15:44 | 0xeb89c131 | 15m | 0.49 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:16:47 | 0xeb89c131 | 15m | 0.54 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:17:51 | 0xeb89c131 | 15m | 0.37 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:19:24 | 0xeb89c131 | 15m | 0.57 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:20:25 | 0xeb89c131 | 15m | 0.51 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:21:26 | 0xeb89c131 | 15m | 0.64 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:22:31 | 0xeb89c131 | 15m | 0.49 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:23:36 | 0xeb89c131 | 15m | 0.28 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:30:48 | 0xb141338f | 15m | 0.62 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:32:36 | 0xb141338f | 15m | 0.54 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:33:38 | 0xb141338f | 15m | 0.54 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:34:43 | 0xb141338f | 15m | 0.44 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:45:03 | 0xad4834c7 | 15m | 0.52 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:47:40 | 0xad4834c7 | 15m | 0.32 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:49:38 | 0xad4834c7 | 15m | 0.58 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:51:07 | 0xad4834c7 | 15m | 0.6 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:52:35 | 0xad4834c7 | 15m | 0.33 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 15:54:48 | 0xad4834c7 | 15m | 0.78 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:00:02 | 0xcb6fdb82 | 15m | 0.65 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:01:02 | 0xcb6fdb82 | 15m | 0.19 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:02:15 | 0xcb6fdb82 | 15m | 0.23 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:03:24 | 0xcb6fdb82 | 15m | 0.82 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:04:38 | 0xcb6fdb82 | 15m | 0.81 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:06:31 | 0xcb6fdb82 | 15m | 0.84 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:16:47 | 0xeaac569f | 15m | 0.52 | approved | open | 0 | - | 0.0000 | unresolved |
| 2026-11-04 16:22:59 | 0xeaac569f | 15m | 0.73 | approved | open | 0 | - | 0.0000 | unresolved |

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 983, median 202, p90 218, min 182, max 504.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 546986, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 2.0, max 80.0.
- Binance event time to local receive (network + clock offset): n 546986, median of minute medians -29.0, worst minute p90 2104.0, worst minute p99 4061.1, max 5801.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 537362, median of minute medians 11.9, worst minute p90 15.8, worst minute p99 89.2, max 209.3.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 155, median -24, p90 90, min -117, max 373.
- Local receive to decision: n 155, median 0, p90 0, min 0, max 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 155, median 356, p90 372, min 335, max 654.

## Risk, reconciliation, invariants and audit

- Trips: 0.
- Human resets: 0; halts confirmed by zero open orders: 0.
- Reconciles: 197 (periodic 197); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 1818 records, head 50c93a24e980a557; last head anchored in the ledger: 1498 records, bcae86ac12c7e3da (startup, 2026-11-03 11:56:02).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v2 | 0 | 60 / 30 | 0.00 | no evidence yet |
| btc-speed-mk-eth-bybit | 0 | 200 / 100 | 0.00 | no evidence yet |

Elapsed since the first run: 15.13 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## How to reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/trader/paper_ethmk --date 2026-11-04 --out C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/reports/daily/paper_ethmk_2026-11-04.md --title "paper_ethmk day 16: 2026-11-04 (UTC)"
```

## Phase 1 gate progress

Gate (build plan v4): 14 consecutive days with zero invariant violations and 5+ restarts with a clean reconcile. **not met yet.**

- Days without a violation: **16 of 14** (days with violations: 0)
- Restarts with a clean startup reconcile: **4 of 4** (need 5+, all clean)
- Running time: 253.3 hours (10.55 days of 24 h)

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
| 2026-11-04 | 16.4 |
