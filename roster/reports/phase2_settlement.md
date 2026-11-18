# Phase 2 — Settlement keeper and canary evaluation (WP2-D: build-plan 2.6, 2.8)

Built as standalone modules and not wired into `trader/loop.py`. The keeper only watches: it makes public GETs and never signs. Nothing here places, signs, posts or cancels an order, or calls an authenticated endpoint. No page was sent to ntfy; every page in this report went to a fake `send` or was recorded locally.

| File | What it does |
|---|---|
| `trader/live/settlement.py` | `derive_outcome`, `proposal`, `SettlementKeeper` (`step`, `oracle_gap`), `FundIntent`, `fund_intents`, `gate`, `page` |
| `trader/live/canary.py` | `rows_from_journal`, `evaluate`, `BUCKETS`, the CLI `python -m trader.live.canary` |
| `tests/phase2/test_settlement_canary.py` | 37 tests (D1–D9), run behind the autouse no-network guard. Its `__main__` prints the numbers in this report. |
| `reports/phase2_canary_synthetic.md`, `reports/phase2_canary_synthetic_shifted.md` | The canary CLI run on **synthetic** rows: a PASS case and a negative control |

## Results at a glance

| AC | Result |
|---|---|
| D1 outcome derivation | Unit fixtures pass, including a DST-day fixture and the old 12:00Z endDate convention. Offline on Phase 0 data: **8,669 of 8,669** strike and **1,116 of 1,116** Up/Down outcomes agree with the recorded winners (the 24 markets without local klines are all dated 2026-09-30). |
| D2 `proposal()` | Real records copied from the Phase 0 cache parse correctly; `"69"`, missing and garbage values give `None`. **8,281 of 8,281** cached proposals agree with the derived outcome. |
| D3 mismatch drill | One page and one REDUCING lock on the cid. The page carries the cid, question, both outcomes and deadline = proposal + 2 h. A second `step` sends nothing. |
| D4 unreadable / dispute | Unreadable 10 min after the print gives a page and a lock (not at 9 min). A dispute on a held market gives one trip (`breaker:dispute`) and one page; an unheld disputed market gives neither. |
| D5 `oracle_gap()` | A market enters the gap at its print and leaves it at resolution. A resolved market is not polled again. |
| D6 fund intents and gate | Merges net of open SELL offers, floored. Redeems winning shares (both tokens on 50-50). Never redeems a mismatched, disputed or locked market. The gate refuses everything under HALTED and allows merges under REDUCING. |
| D7 `page()` | With no topic: no call and `False`. The body has only the cid, question, outcomes and deadline. No hard-coded topic, and the topic never appears in logs. |
| D8 canary | Same process gives PASS; a shifted fill rate gives FAIL naming `[0, 1) fill_rate`; 29 clusters give INSUFFICIENT; a bucket with no replay clusters gives FAIL; the same seed gives identical output. **Caveat:** about 57–59% of same-process samples FAIL by chance under the specified rule (see below). |
| D9 `rows_from_journal` | `queue_ahead` comes from the `new` entries, the markout from the injected `mid_at` at fill + 5 min. Open orders, unknown orders and takers are excluded. |
| Live read-only smoke | The real keeper on public Binance and Data API GETs, over 168 daily markets from the last 7 days: **168 derived, 168 with a proposal, 168 agree**, 0 mismatches, 0 disputes. |
| D12–D14 | **[ops]**, pending (see the end of this report) |

## Drills on fixtures (fake `get`, real `trader.kernel.RiskKernel`)

Output of `python -m tests.phase2.test_settlement_canary`:

**D3 — a fake mismatched proposal pages you.** Held strike market "Bitcoin above $100,000 on October 1?". The Binance 12:00 ET close is 100,500, so the derived outcome is YES. The Data API proposal is `"0"` (NO), proposed at print + 5 min.
```
D3 mismatch: pages after step 1 / trips: (1, 1) | after step 2: (1, 1)
trip: {'scope': '0xs1', 'level': 'REDUCING', 'reason': 'settlement mismatch: proposed NO, derived YES', 'source': 'breaker:settlement'}
ROSTER settlement MISMATCH
cid: 0xs1
question: Bitcoin above $100,000 on October 1?
proposed: NO
derived: YES
challenge deadline: 2026-10-01T18:06Z        <- proposal 16:06Z + 2 h
```
The kernel's `scopes['0xs1']` is REDUCING and the global state stays ACTIVE: the lock is on the market, not a halt.

**D4 — source unreadable.** A held chainlink crypto-fast market, which prints at its end, and a held Binance strike market whose klines GET keeps timing out.
```
D4 unreadable: after 9 min: (1, 1) | after 10-11 min: (2, 2)
  [('0xf1', 'breaker:settlement', 'REDUCING'), ('0xs2', 'breaker:settlement', 'REDUCING')]
```
The chainlink market pages 10 min after its print. The Binance market does not page at print + 9 min, pages at + 10 min, and does not page again at + 11 min. Both pages say "derived: source cannot be read". The spec counts "unreadable after grace" as a mismatch, so both statuses become `mismatch` and are locked. A test also checks that garbage responses (a non-numeric kline close, a non-dict record) don't raise: the market stays `printed`.

**D4 — dispute.** The record has `status: "disputed"`, `was_disputed: true`.
```
D4 dispute: (1, 1) {'scope': '0xs1', 'level': 'REDUCING', 'reason': 'settlement dispute: proposed YES, derived YES', 'source': 'breaker:dispute'}
```
The same disputed record on a market we don't hold gives no trip and no page.

**D5 — oracle gap.** Past the end but before the print candle closes, the status is `waiting` and the market is not in the gap. At print + 30 s it is in the gap, but no kline has been read yet, because the close must be final. At print + 60 s it is `printed`, derived YES. With a proposal it is `matched` and still in the gap. Once `resolved` (outcome YES) it leaves the gap and is not polled again.

**D6 — fund intents and gate.**
```
merge  0xa (0xa-Y, 0xa-N) 8.0    <- min(12.345 YES, 10 NO - 2 offered by an open SELL); a cancelled SELL is not counted
merge  0xb (0xb-Y, 0xb-N) 7.12   <- floor(7.129), never rounded up
redeem 0xy (0xy-Y) 10.0          <- resolved YES; the 4 NO shares are worthless and not redeemed
redeem 0xn (0xn-N) 6.5           <- resolved NO
redeem 0xh (0xh-Y) 2.0 / (0xh-N) 5.0   <- 50-50: both tokens
(no intent for the resolved mismatched, disputed and locked markets; resolved markets are never merged)
```
`gate`:
- Under global HALTED or market HALTED, both merge and redeem are refused.
- Under global REDUCING, both are allowed.
- Under market REDUCING (a lock), merge is allowed and redeem is refused.
- A status with mismatch, disputed or locked refuses redeem.
- An unknown kind is refused.

**D7 — page.**
- No `ROSTER_NTFY_TOPIC`: `False`, and neither the fake nor the default sender is called.
- With a topic, the URL is `https://ntfy.sh/<topic>` and the body lines are exactly `cid`, `question`, `proposed`, `derived` and `challenge deadline`. No balance, position, shares, bankroll or credential words appear.
- A failing sender is swallowed, and the topic never appears in the captured logs.
- `grep -nE "ntfy\.sh/\w" trader/live/settlement.py` finds nothing.

## Outcome derivation against real data (D1, D2)

**Candle timing** is Phase 0's `binance_check`:
- daily: the 1m candle opening at 12:00 ET on the settlement date, read on the ET calendar date of `end_ms`. That way both the crawler's `end_time` (12:00 ET) and old Gamma `endDate`s (12:00Z) map to the right candle.
- daily Up/Down open: `prev_noon_ms`
- hourly: open of the first 1m candle and close of the last (the 1H candle)

The DST fixture is a settlement on Sunday 2026-11-01, the day DST ends. The previous close is 2026-10-31 16:00Z, which is 25 h before the 17:00Z print candle. A decoy candle exactly 24 h earlier would flip the result. The test asserts the candle times equal `history.polymarket.noon_et_ms`, the function `binance_check` itself uses.

**Offline over Phase 0's history** (`--history`). It reads `data/history/polymarket/markets.parquet`, the local Binance 1m parquet and `research/measure/data/resolutions.jsonl`, with no network:

| mode | markets | derived | agree with recorded winner | with cached proposal | agree with proposal |
|---|---|---|---|---|---|
| strike | 8,691 | 8,669 | **8,669** | 7,568 | **7,568** |
| updown | 1,118 | 1,116 | **1,116** | 713 | **713** |

The 24 markets that weren't derived (22 strike, 2 Up/Down) all settle on 2026-09-30, after the last local kline file (2026-09-29). The strike count equals Phase 0's 8,669 of 8,669.

**`proposal()`.** The parsed fields are `status`, `was_disputed`, `proposed_price`, `reproposed_price`, `price` and `last_update_timestamp`. The cache has 4,663 `0/69`, 4,289 `1e18/69`, 13 `1e18/1e18`, 11 `0/0` and one disputed record. A reproposal, which follows a dispute, supersedes the first proposal. The cache has no 50-50 record, so the 5e17 case is a cached record with that one field changed.

**Live read-only smoke** (`--smoke-days 7`). This is the real `SettlementKeeper` with `common.get_json` against public `api.binance.com/api/v3/klines` and `data-api.polymarket.com/v2/resolutions`. It ran over Phase 0's daily BTC/ETH markets settled 2026-09-24…30, all treated as held. Pages and trips were only recorded, never sent.
```
smoke since 2026-09-24: 168 markets ({'strike': 154, 'updown': 14}), derived 168, with a proposal 168, agree 168,
mismatch 0, disputed 0, states {'resolved': 168}, pages 0 (not sent), trips 0 (recorded only), GETs 16 kline candles cached
```
This confirms the live response shapes: `{"data": [record]}`, and kline rows indexed by open time. The whole run took about 100 s, with roughly 185 GETs. Hourly markets are not in Phase 0's catalog, so the hourly path is covered by unit fixtures only.

## Canary CLI on synthetic rows (D8) — SYNTHETIC, not live evidence

The rows come from `synth()` in the test file:
- per-bucket fill probability (0.6, 0.4, 0.2, 0.05), with a cluster-level shift
- markout N(μ_b, 0.02)
- 8 orders per cluster
- replay: 400 clusters, seed 1; live: 60 clusters, seed 2

| Run | Verdict | Report |
|---|---|---|
| live from the same process | **PASS**: 56 live clusters with a fill. Every bucket is inside on fill rate and markout. The `[0, 1)` fill rate is 0.5219 against [0.5186, 0.6811]. | `reports/phase2_canary_synthetic.md` |
| live `[0, 1)` fill probability 0.6 → 0.98 (negative control) | **FAIL**: "outside replay's 90% interval: [0, 1) fill_rate. recalibrate the fill simulator and re-run replay before continuing" | `reports/phase2_canary_synthetic_shifted.md` |

Two CLI runs with the same seed gave byte-identical files (SHA-256 `82BC275B…E8ED8`).

**Finding: the specified rule has a high false-alarm rate.** It uses a 90% interval for each of 4 buckets × 2 metrics, so a live sample from exactly the replay process FAILs in about 1 − 0.9⁸ ≈ 57% of cases. Measured: 59 of 100 seeds (and 59.0% over 200). The D8 PASS test therefore relies on its fixed seed. I implemented the rule as specified and have not changed it. If the canary is meant to gate the Phase 2 exit, I recommend a Bonferroni-adjusted interval per check: the 0.625th–99.375th percentiles for 8 checks. In a scratch run this cut the same-process FAIL rate to 16.0% (200 seeds) and still FAILed 100% of samples with a `[0, 1)` fill shift of 0.60 → 0.85. This is your call. It's a change to the build plan's statistic, so I did not make it myself.

## Decisions and deviations (all fail-closed)

- **The oracle gap includes printed markets we don't hold.** WP2-C's resolution cap must apply to a first buy after the print. These markets are not polled (no GET is spent on them), so they stay in the gap until they leave the `markets` dict. A `ponytail:` comment marks this.
- **The dispute lock is REDUCING**, the same as the mismatch lock. Role 01: "A market with open exposure enters a UMA dispute → lock that market."
- **Unreadable after grace counts as a mismatch**, so redeem is refused until a human resets it. Every crypto-fast (chainlink) position will page and lock at resolution until D13 exists.
- **Deadline = the record's `last_update_timestamp` + 2 h**, taken when a new proposal is first seen. The records have no separate proposal-time field. A reproposal resets the deadline.
- **The print candle is read only 60 s after it closes** (`SETTLE_MS`, a tuning knob). The derived outcome is cached, so a close that wasn't final yet must never be cached.
- **One page per (cid, kind)**, with no retry if ntfy delivery fails. The dead-man (WP2-A) is the backstop for a dead loop, not for a lost page.
- **Canary details:**
  - fill rate = filled shares / offered shares
  - markout = filled-share-weighted mean per share: mid − price for BUY, price − mid for SELL
  - only terminal maker orders become rows
  - the fill rate is judged in every bucket with live orders and replay clusters. This is slightly stricter than "buckets with live fills": it also catches a bucket where live never fills but replay predicts fills.
  - a bucket with live fills but no 5m mid → FAIL (`markout_5m missing`)
- **`rows_from_journal` cannot tell a venue rejection from a normal cancel.** WP2-B journals both as `cancel`, and `trader.router.State` keeps no reason. Rejected orders would count as unfilled rows. That is conservative for the fill rate.

## Contract gaps (worked around, contracts untouched)

- `Intent` has no merge or redeem kind, so this package has its own `FundIntent` and `gate()`.
- `MarketInfo` has no Up/Down open price and no hourly flag. The open is read from Binance (`prev_noon_ms`), and hourly is `mode == "crypto-hourly"`.
- The `Kernel` protocol's `trip` has no level argument. The keeper calls `trip(cid, reason, source, REDUCING)`, which is `RiskKernel.trip`'s real signature.

## [ops] items (operational_pending)

- **D12:** the real `reports/phase2_canary.md` over ≥ 30 live fill clusters. This needs about 30 days or more of live-micro.
- **D13:** a Chainlink TWAP reader for crypto-fast outcomes. It needs CLOB credentials. Until it exists, every btc-speed position pages "source cannot be read" and is locked at resolution.
- **D14:** redeem and merge executed through Polymarket's relayer (role 05, authenticated, behind the three flags), and the D3 drill re-run with a real `ROSTER_NTFY_TOPIC`.

## Wiring later

- **Keeper:** the loop builds `SettlementKeeper(markets, common.get_json, page, kernel.trip)` and calls `keeper.step(now, router.positions)` once a minute in a worker thread. It uses public GETs only, and each failure is logged and retried on the next step.
  - Keep held markets in `markets` until they resolve. The keeper also remembers every market it has started tracking.
  - Drop closed markets you don't hold from `markets`, so they leave the gap.
- **Fund intents:** `fund_intents(router.positions, router.open_orders(), markets, keeper.statuses)` → `gate(fi, kernel.scopes, keeper.statuses.get(fi.cid))` → role 05's relayer, once it exists (D14). Until then, Phase 1's `PaperRouter.merge` covers merges in paper.
- **Oracle gap:** `keeper.oracle_gap()` feeds the ladder engine's pull rule and WP2-C's `check_live(..., printed=...)`.
- **Canary:** runs nightly:
  ```
  rows_from_journal(live_journal, markets, mid_at) and rows_from_journal(paper_journal, markets, mid_at)
  python -m trader.live.canary --live ... --replay ... --out reports/phase2_canary.md
  ```
  `mid_at(token, ts)` comes from the recorder's books, as mid excluding own orders.

## How to reproduce

From `roster/` (Windows paths; use `/` on Linux):

```
.venv\Scripts\python.exe -m pytest tests/phase2/test_settlement_canary.py -q        # 37 passed, no network
.venv\Scripts\python.exe -m tests.phase2.test_settlement_canary                    # D3, D4, D6 drill output and the D8 false-FAIL rate
.venv\Scripts\python.exe -m tests.phase2.test_settlement_canary --history          # offline: derived vs recorded winners and cached proposals
.venv\Scripts\python.exe -m tests.phase2.test_settlement_canary --smoke-days 7     # optional: public read-only GETs (Binance, Data API)
.venv\Scripts\python.exe -m tests.phase2.test_settlement_canary --synthetic <dir>  # writes synthetic_live / _replay / _live_shifted .jsonl
.venv\Scripts\python.exe -m trader.live.canary --live <dir>\synthetic_live.jsonl --replay <dir>\synthetic_replay.jsonl --out reports/phase2_canary_synthetic.md --label "SYNTHETIC rows (generated by tests/phase2/test_settlement_canary.py --synthetic); not live evidence, not the D12 report"
.venv\Scripts\python.exe -m trader.live.canary --live <dir>\synthetic_live_shifted.jsonl --replay <dir>\synthetic_replay.jsonl --out reports/phase2_canary_synthetic_shifted.md --label "SYNTHETIC rows with the [0, 1) live fill probability shifted 0.6 -> 0.98 (negative control); not live evidence"
```
