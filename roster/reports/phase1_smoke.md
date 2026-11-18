# Phase 1 smoke run: 60 minutes, both strategies, live public data, paper only

Ledger `data/trader/smoke_v2`, window start to now UTC (data from 2026-10-07 06:13:53 to 2026-10-07 07:13:53). Paper only: no order ever left this PC.

## Summary

- Runs started: 1; clean shutdowns: 1; still running or ended by a crash or kill: 0 (a killed run's journal is replayed and reconciled at the next start).
- **Invariant violations: 0.**
- Intents 39699, approved 372, orders 372, paper fills 1, btc-speed events 0 and trades 0.
- Paper P&L to the end of the window: ladder-maker -0.19 USD.

## Paper P&L per strategy (cumulative to the end of the window)

| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |
|---|---|---|---|---|---|---|---|---|---|
| ladder-maker | 1 | 2.80 | 0.00 | 0.0000 | 0.00 | 0.00 | 10 | 2.61 | -0.1900 |

Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.

## Intents and kernel decisions

- **ladder-maker**: 39699 intents, 372 approved, 39327 rejected: over group 39327.
  Also: cancel:ladder-maker 362.
- **btc-speed**: 0 intents, 0 approved, 0 rejected.

Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the `decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = refused by the router's order rules. Reasons without a kernel prefix ("own order already live ...", "no book for a taker", "book snapshot already taken ...") are the loop's guards against a flattering fill simulator.

Latest distinct rejections:

| Time UTC | Strategy | Reason | Binding cap |
|---|---|---|---|
| 2026-10-07 07:13:42 | ladder-maker | over group:BTC@2026-10-07T16:00Z: needs 9.85, room 0.14 | group:BTC@2026-10-07T16:00Z |

## Orders and fills

| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |
|---|---|---|---|---|---|---|
| ladder-maker | maker | 372 | 1 | 10 | 0.2800 | 0.0000 |

Merges of YES+NO pairs: 0; paper redemptions: 0.

## Markouts against mid_ex_own

Per share, signed by side (positive = the mid moved our way).

| Strategy | Horizon | n | Mean | SE | No mid |
|---|---|---|---|---|---|
| ladder-maker | 5 s | 1 | +0.15c | - | 0 |
| ladder-maker | 60 s | 1 | +1.00c | - | 0 |
| ladder-maker | 300 s | 1 | -2.15c | - | 0 |

## Pre-registered statistics (all data to the end of the window)

- **ladder-maker-v1**: per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, summed per cluster. Clusters 1 (needs 60), mean -0.1868 USD, SE -, fills still without a 5 m markout 0. Verdict: **running (1 of 60)**.
- **btc-speed-v1**: fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee. Resolved trades 0 in 0 markets (needs 200), unresolved 0, mean - USD, cluster SE -, total +0.0000 USD. Verdict: **running (0 of 200)**.
- Pre-registrations in the ledger (immutable): `ladder-maker-v1` (sha256 faacb13c96a3180f, written 2026-10-07 06:13:53), `btc-speed-v1` (sha256 88942b658a24774b, written 2026-10-07 06:13:53).

## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)

| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |
|---|---|---|---|---|---|---|---|---|
| universe | 0 | 0 | 0 | - | - | 0 | - | - |
| traded | 0 | 0 | 0 | - | - | 0 | - | - |

## btc-speed events and trades

0 causal BTC moves (>= 10.0 bp in 5 s) and 0 trades sent to the kernel. Per mapped market: none.

## Latency (ms)

- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): n 60, median 236, p90 289, min 214, max 389.

Every Binance tick and every 100 ms timer, summarised per minute by the loop:

- Decision lag: local receive of a Binance tick to both engines decided and orders sent: n 385036, median of minute medians 0.0, worst minute p90 1.0, worst minute p99 25.2, max 326.0.
- Binance event time to local receive (network + clock offset): n 385036, median of minute medians -33.5, worst minute p90 76.0, worst minute p99 493.0, max 774.0.
- Event-loop lag: a 100 ms timer firing late (time a message can wait unread): n 34540, median of minute medians 2.3, worst minute p90 167.6, worst minute p99 167.6, max 276.7.

btc-speed events (one sample per event, traded or not):

- Binance event to local receive: n 0.
- Local receive to decision: n 0.
- Decision to simulated arrival (150 ms taker delay + measured round trip): n 0.

## Risk, reconciliation, invariants and audit

- Trips: 0.
- Human resets: 0; halts confirmed by zero open orders: 0.
- Reconciles: 14 (startup 1, periodic 12, shutdown 1); with mismatches: 0; unknown orders cancelled at startup: 0; journaled fills backfilled into the ledger: 0.
- **Invariant violations: 0**.
- Data faults flagged by ladder-maker (quotes pulled): 0; log-only arb opportunities: 0.
- Audit chain verifies: 1812 records, head 9c017955bdd8d97e; last head anchored in the ledger: 1812 records, 9c017955bdd8d97e (shutdown, 2026-10-07 07:13:53).

## Time to evidence

| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |
|---|---|---|---|---|
| ladder-maker-v1 | 1 | 60 / 30 | 23.34 | 59 |
| btc-speed-v1 | 0 | 200 / 100 | 0.00 | no evidence yet |

Elapsed since the first run: 0.04 days. ladder-maker's clusters are settlement instants (one per daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate.

## Notes

- Run 2026-10-07 06:13:53 to 07:13:53 UTC on this PC, exit code 0, clean shutdown, 0 invariant violations, 0 reconcile mismatches, 0 trips. Console log: data/trader/smoke_v2/smoke_run.log.
- Zero btc-speed events is the correct answer for this hour, not a wiring gap: BTC's largest trailing 5 s move in the window was 5.94 bp (Binance BTCUSDT 1 s klines, 3,600 seconds; p99.9 4.59 bp), under the 10 bp threshold. Phase 0 saw 1,512 events in 56 days (about 1.1 per hour). The speed path (event, 5m Up taker at the arrival-time ask, fee, markouts, latency stamps, settlement) runs on the real modules in tests/invariants/test_invariants.py::test_end_to_end_paper_loop.
- Zero universe checkpoint rows is also expected: ladder checkpoints fall at tau 24 h / 6 h / 1 h before the 16:00Z settle (16:00Z the day before, 10:00Z, 15:00Z); none is inside 06:13-07:13 UTC.
- 99% of ladder-maker intents were rejected 'over group': the engine re-proposes about 11 quotes a second across every strike of a ladder, and the kernel's per-event-group cap leaves room for a few resting bids. This is the kernel working, but it slows ladder evidence; see open issues (the engine does not size to the kernel's remaining room).
- The one paper fill: ladder-maker BUY 10 @ 0.28 (maker, fee 0) at 06:29:09 UTC; 5 s / 1 m / 5 m markouts +0.15c / +1.00c / -2.15c per share.
- Time to evidence: ladder-maker-v1 clusters on the settlement instant, so at most one new cluster appears per day; its 60-cluster pass n needs at least about 60 trading days, far beyond the 14-day paper gate. btc-speed-v1 clusters per 5m/15m market and is limited by BTC moves (about 27 a day in Phase 0).
- Feed quality: the Polymarket crypto-fast WebSocket was closed by the venue 22 times ('slow consumer: send buffer full'), each a 1 s reconnect plus a fresh snapshot. A first run before leaving out the ETH 5m/15m markets no strategy trades had 53 (data/trader/smoke_prefilter). The rest is in trader/marketdata.py (WP1-C), recorded as an open issue.
- Fill-simulator guards in trader/loop.py (WP1-C audit findings): GTD expiry is applied before every trade, trades use the local receive clock, a taker with no book is refused, one own order per token and side (no reuse of displayed liquidity or a queue that omits our own size), and no taker on a book snapshot our last taker already took. None had to refuse anything in this run.
- Network: this PC's IPv6 route was dead on 2026-10-07 (each connect waited out a timeout per v6 address; ~16 s per GET). trader.loop, nightly.drills and nightly.report now resolve IPv4 first (trader/loop.py prefer_ipv4).

## How to reproduce

```
cd roster
rem throwaway signing key, this shell only (the trader verifies clearances with the same env key)
set ROSTER_HUMAN_KEY=<any random string>
.venv\Scripts\python.exe -m nightly.drills keys > keys.jsonl
.venv\Scripts\python.exe -m tools.clearance_cli --db data/trader/smoke_v2/advice.db sign --keys keys.jsonl --signer <you> --days 3
.venv\Scripts\python.exe -m trader.loop --paper --minutes 60 --dir data/trader/smoke_v2
.venv\Scripts\python.exe -m nightly.report --dir data/trader/smoke_v2 --all --out reports/phase1_smoke.md --title "Phase 1 smoke run: 60 minutes, both strategies, live public data, paper only"
```
