# Phase 1 Audit — Paper trading

Contract: [dispatch.md](dispatch.md). Process: [../README.md](../README.md). Every acceptance criterion below was checked by an independent auditor agent that did not write the code. The compiler then re-ran every work package's tests (2026-10-07).

**Gate override (the user's decision):** Phase 0's exit gate was not met (both go/no-go tests failed). The user chose to run Phase 1 anyway, **paper only**, with two strategies side by side: `ladder-maker` (registered as a `candidate` because its κ test failed) and `btc-speed` (the only Phase 0 test that passed). No keys exist on this machine, and no order can reach the venue.

## Summary

| Work package | Code audit | Fix rounds | Tests (compiler re-run) | Result |
|---|---|---|---|---|
| **WP1-A** Core: fees, ledger, audit log (1.1–1.3) | PASS | 0 | 37 passed | `fee()` matches the venue docs (100 sh @ 0.50 = $1.75); `as_of()` never leaks a later row (property test with clock jumps); hash-chained audit log detects tampering. Minor: a raw `INSERT OR REPLACE` bypasses the append-only triggers |
| **WP1-B** Kernel, breakers, clearances (1.14, 1.15, 1.17) | PASS | 1 | 20 passed | All kernel checks have failing-input tests; 46 of 50 mutations caught (the 4 survivors are harmless). The round-0 major (REDUCING did not net live orders) is fixed |
| **WP1-C** Market data, paper execution, reconciliation (1.4, 1.5, 1.7, 1.16) | PASS | 1 | 14 passed | Live smoke: 222 markets, WS books match the venue's own best bid/ask 99.7% of the time, finals equal Binance REST exactly, round trip about 208 ms. Journal replay after a torn mid-batch crash is exact. 4 minor fill-simulator gaps |
| **WP1-D** Ladder-maker strategy (1.6, 1.8–1.13) | PASS | 0 | 19 passed | Pricer equals the closed form; sizer invariant holds on 10,000 random intents (0 bad); every pull rule fires on its trigger; worst-case `on_tick` 46.8 ms |
| **WP1-E** BTC-speed strategy (from 0.12) | PASS | 0 | 19 passed | Detector finds the same 1,512 events as Phase 0 over 56 days, event by event; provably causal; hard 5-share cap, BTC only, max price 0.90 |
| **WP1-F** Integration, scoring, ops, drills (1.18–1.20, invariants) | PASS (ops pending) | 0 | 125 passed (`trader/tests` + `tests/invariants`, includes the 109 above) | 60-min live paper run: 0 violations, 0 trips, 14 clean reconciles, audit chain verifies. 5 forced restarts (2 × `kill -9` mid-batch) all reconcile clean. 1 fill in the hour; 0 btc-speed events (largest 5 s BTC move 5.94 bp vs 10 bp threshold) |

**All tests pass:** 37 + 20 + 14 + 19 + 19 = 109 in `trader/tests`, plus 16 in `tests/invariants` = **125 passed, 0 failed** (`trader/tests tests/invariants`, 13.1 s). The WP1-F auditor also ran the 125 with sockets blocked: all pass, so no test needs the network.

No work package has a blocker or major defect open. All 19 open defects are minor.

Fix-round counts for WP1-A to WP1-E are not stored in the claims files; WP1-B's and WP1-C's single rounds are taken from the audits' own text ("the major defect from round 0 is fixed"; "WP1-C's parallel fix round").

## Phase 1 exit gate: **NOT MET yet ([ops] pending)**

The build plan's gate is **14 consecutive days with zero invariant violations and a clean reconcile across all 5+ forced restarts**.

| Gate item | Status |
|---|---|
| Clean reconcile across 5+ forced restarts, including `kill -9` mid-batch | **MET** in `data/trader/drills_v2` (14 reconciles, all clean). Caveat: the drills ran on the version of `trader/loop.py` one save before the final one (WP1-F defect 1); re-running them on the final code (about 15 min) makes this strictly true |
| 14 consecutive days of paper running, zero invariant violations | **[ops] pending**: needs 14 days of wall-clock time on this PC (WP1-F F7) |
| Invariant suite green | **MET**: 16 passed |

### What remains [ops] before the gate can be met

1. **Set up the human key and clearances** (you, not an agent): set `ROSTER_HUMAN_KEY` in the trader's shell, then sign clearances for every traded market key (`python -m nightly.drills keys > keys.jsonl`, then `python -m tools.clearance_cli --db data/trader/advice.db sign --keys keys.jsonl --signer <you> --days N`). Re-sign before they expire; unsigned keys go to `data/trader/uncleared.jsonl`. Keep the key out of files.
2. **Start the 14-day run:** `python -m trader.loop --paper --minutes 20160 --dir data/trader`, with the PC kept awake.
3. **Schedule the nightly report** in Task Scheduler: `python -m nightly.report --dir data/trader` (add `--ntfy` with `NTFY_TOPIC` set for phone alerts).
4. **Watch for at least one live btc-speed event** going through mapping, kernel and a simulated fill. In the smoke hour BTC never moved 10 bp in 5 s, so the live speed path is so far covered only by the fake-feed end-to-end test.

### Recommended before starting the 14-day run (minor fixes, not gate items)

- **WP1-D:** the ladder engine ignores the kernel's remaining room, so 99% of its 39,699 smoke intents were rejected "over group". Harmless (fail-closed) but it wastes kernel work and clutters the decision log.
- **WP1-C:** two one-line fill-simulator fixes (an expired GTD maker can fill; a taker with no book at arrival is not killed). The loop already guards both (`Trader.sim_guard`, expire-before-trade), so paper results are protected; the fixes belong in the router before any live router copies its logic.
- **WP1-A:** set `PRAGMA recursive_triggers=ON` in `Ledger.__init__` (or add a BEFORE INSERT trigger) so a raw `INSERT OR REPLACE` cannot rewrite a pre-registration or a ledger row. Today it is detected at the next start, not prevented.
- **WP1-B:** ignore a NaN equity in `Breakers.on_equity`, which otherwise disables the drawdown breaker for the rest of the UTC day.
- **WP1-F:** re-run the drills on the final `loop.py`; tidy the superseded folders in `data/trader/`.

### Decisions only you can make

- **Time to evidence:** `ladder-maker-v1`'s pre-registration needs 60 daily clusters, so at least about 59 more days of paper running, well past the 14-day gate. Decide whether Phase 2 waits for it or starts on the 14-day gate alone.
- **btc-speed sample size** is set by how often BTC moves 10 bp in 5 s (0 times in the smoke hour). Its kernel budget ($25) allows about 5 open trades at once, since each is held to resolution at up to $4.50.

## What Phase 1 found

| Question | Answer | Evidence |
|---|---|---|
| Does the full paper stack run on live data without crashing? | **Yes** | 60-minute run on 191 markets, clean shutdown, 0 invariant violations, 0 reconcile mismatches, 0 trips, 1,812 audit records with the head anchored in the ledger |
| Does it survive crashes? | **Yes** | 5 forced restarts, 2 of them `kill -9` mid-batch; each startup marks the journaled-but-unacked order `unknown`, does not retry it, resolves it, and reconciles clean |
| Does ladder-maker get filled? | **Rarely so far** | 372 maker orders, 1 fill (BUY 10 @ 0.28) in the hour; markouts +0.15¢ / +1.00¢ / −2.15¢ (5 s / 1 m / 5 m); paper P&L −$0.19 at mid. One fill says nothing about edge |
| What is the real latency from this PC? | **About 236 ms round trip** | Median 236 ms (p90 289) to `clob.polymarket.com`; tick-to-decision p99 25 ms; event-loop lag median 2.3 ms but worst-minute p90 168 ms. Phase 0's edge on free data lived within about 2 s, so 236 ms leaves room, but only live events will tell |
| Is the market feed reliable? | **Mostly** | Books match the venue 99.7% of the time (mismatches transient). The crypto-fast socket was closed by the venue 22 times in the hour (down from 53 after the ETH-fast filter); WP1-C's slow-consumer drops remain an open issue |
| How long until evidence? | **Weeks to months** | ladder-maker: about 59 more days (one cluster per daily settle). btc-speed: limited by 10 bp BTC moves |

## Wiring later

Collected from each work package's audit (WP1-A to WP1-E) and WP1-F's builder notes. For paper trading, everything is already wired by `trader/loop.py`; the items below are what a later phase, or the live router, must respect.

**WP1-F (integration, already wired for paper)**
- `trader/loop.py` is the Phase 1 integration point; nothing else needs wiring for paper. It connects market data (books, trades, Binance ticks, DVOL, basis, round trip) to btc-speed on every BTC tick and to ladder-maker at most once a second, then the kernel, the paper router (batches ≤ 15, maker targets diffed against live orders), fills, the ledger, audit log, breakers, reconciler, markouts and paper settlement.
- 14-day run procedure: see "What remains [ops]" above. To reset a trip: `python -m tools.clearance_cli --db data/trader/advice.db token ...`; the loop re-reads `advice.db` every minute.
- **Live mode stays impossible in this closure.** A live router must be a separate module behind the three-flag guard (config, env, CLI; default off), swapped in where `Trader` builds `PaperRouter`. `test_no_order_send_path` keeps live code out of the paper import closure.
- Before going live, move the simulator guards (`Trader.sim_guard`, expire-before-trade, local clock) into the router.

**WP1-A (core)**
- The promotion token is an HMAC with a shared key, so any process holding `ROSTER_HUMAN_KEY` can mint tokens. Set the key only in the shell the human promotes or signs from; keep it out of the trader's environment once a live router exists (the Phase 1 kernel needs it to verify clearances and resets).
- `taker_rate` checks only `fee_schedule`; `fee_type`, `fees_enabled` and the base fees are ignored. Every row seen today has fees enabled, so it is conservative; a live taker path should refuse an unknown `fee_type`.
- `sqlite3` uses `check_same_thread=True`: call the Ledger from one thread.
- `AuditLog` checks only the last line on open; run `verify()` at startup or nightly (WP1-F anchors the head in the ledger).
- Contract gaps (worked around inside the packages): `MarketInfo` has no fee schedule, `Fill` has no `cluster_id`, there is no pre-registration schema or audit interface in `contracts.py`.

**WP1-B (kernel, breakers, clearances)**
- Refresh `ctx.open_orders` between `check()` calls within one tick, and fill `kernel.starts`.
- The GTD start bound fails open after the start or when `kernel.starts` is empty. Sports modes must close this before going live (ponytail note in `gtd()`).
- Any caller can use the `human` or `loop` source prefixes to set HALTED, which errs on the safe side.
- An invalid clearance row with a later expiry can hide a valid one (the market then reads as not cleared, which fails closed).

**WP1-C (market data, paper execution, reconciliation)**
- Call `router.poll(now_ms)` every tick; call `reconciler.merge_pairs` and `reconcile` at a chosen cadence; wire `rtt_ms=lambda: md.rtt_ms`; hand `md.markets` (the same dict) to router and kernel.
- DVOL is in percent. The marketdata docstring's trade rates are stale (about 9 trades/s each for BTC and ETH, not 3 and 12).
- Replay skips any unparseable journal line, not just a torn last one; the ledger-fills cross-check in `reconcile()` covers that.

**WP1-D (ladder-maker)**
- Drain `engine.records`, call `on_fill` (and replay it on restart), trip role 02 on `data_fault` records, and have the human confirm PREREG before it is written.
- The selector ranks purely on income per dollar, so a market holding inventory could in principle fall outside `max_markets` (not reproduced; a complement bid raises that market's income).
- With a non-default `pull_before_close_ms` below about 5 min, the expiry can land under now + 2 min; the kernel rejects it (fails closed).
- Worst-case `on_tick` is 46.8 ms (O(n²) arb scan on a 154-strike ladder): do not call it on every Binance trade (the loop calls it at most once a second).
- The stale-feed check uses Binance event time, so local clock skew over 5 s would pull every quote, or none.
- The engine ignores the kernel's remaining room (99% "over group" rejections in the smoke run).

**WP1-E (btc-speed)**
- Put `recv_ms` in `ref`, update `engine.rtt_ms` from the router's measured round trip, drain `engine.trades` and `engine.events`, and pre-register the actual params if the engine starts with overrides.
- Kernel budget $25 allows about 5 open trades at once (0.90 × 5 = $4.50 each, held to resolution).
- No guard against acting on a late Binance tick if the loop falls behind (optional: skip when `decision_ms − recv_ms` exceeds a registered bound).

## Orchestration notes

- **Interruption:** the multi-agent run was stopped on 2026-10-01 with WP1-F's build unfinished. It resumed from the partial files on disk (see [../RESUME.md](../RESUME.md)); WP1-A to WP1-E were not re-run, and their final audits come from `claims/*.audit.json`.
- **WP1-F's runs** are in `data/trader/smoke_v2` (60-min smoke) and `data/trader/drills_v2` (drills). The other folders in `data/trader/` are superseded trial runs from older code; some contain trips and should be ignored.
- **Compiler re-run** (2026-10-07): every work package's tests, run independently, 125 passed in total. No code was modified while compiling this file.

---

## WP1-A: Core: fees, ledger, audit log (1.1–1.3)

**Final verdict:** PASS. Fix rounds: 0. Final audit: `claims/WP1-A.audit.json`. Tests: `trader/tests/test_core.py`.

| AC | Status | Evidence | Command |
|---|---|---|---|
| A1 fee() matches hand-computed values at p=0.1/0.5/0.9 for rates 0.07 and 0.05; an unmodel… | pass | With C=100, my own run gave 0.63/1.75/0.63 at rate 0.07 and 0.45/1.25/0.45 at rate 0.05, all within 1e-12 of hand values. C=7, p=0.37 equals 7*0.07*0.37*0.63 exactly. The docs (read 2026-10-01) say fee = C x feeRate x p x (1-p), crypto 0.07, sports 0.05, makers never charged, and the worked example is 100 shares at 0.50 = $1.75. Refused with UnmodelledFee: an extra field (feeCap), exponent 1.5, exponent None, takerOn… | `.venv\Scripts\python.exe build/phase-1/audit-tmp/WP1-A/a1_probe.py ; WebFetch https://docs.polymarket.com/trading/fees` |
| A2 as_of(t) never returns a row recorded after t (test) | pass | My own property test: 400 writes across 3 tables with a random clock that jumps backwards and once forwards to 10^6, the db reopened every 37 writes, and a random query after each write. 0 rows came back with recorded_ms > t. Stored recorded_ms never decreases in insertion order. For 500 random t, as_of counts equal a raw SQL count of recorded_ms <= t. Forecasts and fills rows with no cluster_id, an empty one or None… | `.venv\Scripts\python.exe build/phase-1/audit-tmp/WP1-A/ledger_probe.py (A2 section)` |
| A3 Registry: states; live promotion without a valid unused nonce refused; reused nonce ref… | pass | From candidate, moves to live, canary, candidate or a bogus state are refused. Live promotion is refused (PermissionError) for: a signature made for nonce n1 but sent with n2, a token signed for the 'shadow' purpose, and a wrong key. Refusals use up no nonces (0 in the table). A valid token promotes, sets the anchor and retires the old live version. A second live->live is refused. After closing and reopening, a nonce… | `.venv\Scripts\python.exe build/phase-1/audit-tmp/WP1-A/ledger_probe.py (A3 section)` |
| A4 Pre-registrations cannot be changed or deleted once written (test) | pass | Through the Ledger API, a changed dict raises ValueError. The same dict with keys in another order does nothing. n=200.0 instead of 200 counts as a change, which is the safe direction. The record survives a reopen. Raw UPDATE and DELETE are refused by the triggers. However, a raw 'INSERT OR REPLACE' or 'REPLACE INTO prereg' does change the record, because SQLite does not run delete triggers on REPLACE unless recursiv… | `.venv\Scripts\python.exe build/phase-1/audit-tmp/WP1-A/ledger_probe.py (A4 section)` |
| A5 Audit log: tampering with any record is detected by verifying the chain; a failed write… | pass | Editing any one of 6 records, first through last, is detected. Editing a record and recomputing its own hash is detected for records 1-5 but not for the last one. Also detected: dropping the first record, duplicating the last, reversing the order, a blank line, and a changed seq. Cutting off the tail is not detected. Both gaps are what an unkeyed chain cannot catch, and the builder disclosed them (minor defect 2). Fa… | `.venv\Scripts\python.exe build/phase-1/audit-tmp/WP1-A/audit_probe.py` |
| A6 Tests in trader/tests/test_core.py pass | pass | 37 passed in 1.98s (37 tests collected) | `.venv\Scripts\python.exe -m pytest trader/tests/test_core.py -q (from code root)` |

**Open defects at final audit** (all minor; none are blockers or majors):

- **minor** (`trader/ledger.py`): The triggers that make tables append-only can be bypassed with INSERT OR REPLACE / REPLACE. SQLite does not run BEFORE DELETE triggers on a REPLACE unless PRAGMA recursive_triggers is on. Confirmed: 'INSERT OR REPLACE INTO prereg ...' replaced the btc-speed pre-registration, and 'INSERT OR REPLACE INTO rows (id, ...)' rewrote ledger row 1 with recorded_ms=0, which defeats the no-look-ahead property at the database level. The registry table also allows DELETE and REPLACE, so a version can be deleted and re-registere… *Fix:* Add self.db.execute('PRAGMA recursive_triggers=ON') in Ledger.__init__. I checked it on a copy: prereg REPLACE is then refused with 'pre-registrations are immutable'. Also add a BEFORE DELETE trigger on registry, and one test that runs a raw INSERT OR REPLACE…
- **minor** (`trader/audit.py`): The audit chain has no key. Editing the newest record and recomputing its hash, or cutting records off the end, still passes verify(). The dispatch only asks for a hash chain, but build-plan task 1.3 says 'signed'. The builder disclosed this. *Fix:* WP1-F should store verify()'s (count, head) in the ledger and the daily report at least daily, or the record hash could be keyed with an HMAC key kept outside the log.
- **minor** (`trader/audit.py`): If os.write writes the full line but then os.fsync fails, append() raises AuditWriteError and blocks further writes. On restart, though, _load_head treats that complete line as a valid record, and no recovery note is written. So a record the caller was told had failed shows up in the chain. This contradicts the docstring's 'a record counts only after write + fsync'. *Fix:* Before writing, note the file size. In the except path, try os.ftruncate(fd, old_size) before blocking the log, or append a 'recovery' record on restart whenever the file ends in a record the previous run reported as failed.
- **minor** (`trader/audit.py`): append() raises TypeError, not AuditWriteError, when data cannot be turned into JSON, and does not block further writes. A caller in WP1-F that catches only AuditWriteError in order to trip HALTED would miss it. *Fix:* Wrap the _hash/_canon step and re-raise as AuditWriteError, or WP1-F catches Exception around audit.append.

**Rules check:** Paper only: WP1-A imports only hashlib, hmac, json, os, pathlib, sqlite3 and common (it uses only common.DATA and common.now_ms). A grep for requests/urllib/http/socket/websocket/get_json/post(/sign_order/create_order/private_key/web3/clob/api_key/0x-addresses found nothing in fees.py, ledger.py or audit.py. The only os.environ read is ROSTER_HUMAN_KEY, used to check promotion tokens. Secrets: the only key string is the test placeholder 'human-secret' in test_core.py. Owned paths: the builder's 4 files (trader/fees.py, ledger.py, audit.py, tests/test_core.py) are all inside WP1-A's paths. Other files newer than contracts.py (kernel.py, breakers.py, engines/speed.py, tools/clearance_cli.py, _…

---

## WP1-B: Kernel, breakers, clearances (1.14, 1.15, 1.17)

**Final verdict:** PASS. Fix rounds: 1. Final audit: `claims/WP1-B.audit.json`. Tests: `trader/tests/test_kernel.py`.

| AC | Status | Evidence | Command |
|---|---|---|---|
| B1 State rules: REDUCING rejects a risk-increasing intent and accepts a reducing one; HALT… | pass | All B1 tests pass. The major defect from round 0 is fixed. With REDUCING and 10 YES held, probe P1 (live SELL 10 YES, then BUY 10 NO) and P1b (live BUY 10 NO, then SELL 10 YES) are both rejected with 'REDUCING: only exposure-reducing orders'. Live orders on both routes add up: Q2, with a live SELL 4 YES and a live BUY 4 NO, approves BUY 2 NO and rejects BUY 3 NO. A journaled order counts (Q1: SELL 4 approved, SELL 5… | `pytest trader/tests/test_kernel.py (test_b1_states, test_b1_ai_trips_capped_at_reducing, test_b1_reducing_nets_live_orders_on_both_routes, t…` |
| B2 An intent over an event-group cap or a strategy budget is rejected, and the Decision na… | pass | An over-cap intent is rejected with binding_cap 'group:BTC@2026-10-02T16:00Z' or 'strategy:btc-speed', and an approved intent also names its tightest cap. P4: an empty bid side now marks 100.0 for 100 shares, the same as a missing book. P5: btc-speed trading a crypto-hourly market is rejected with "btc-speed does not trade mode 'crypto-hourly'". The comparisons now reject NaN (code line 182: 'if not need <= room[cap]… | `pytest test_b2_group_cap_binds, test_b2_strategy_budget_binds_and_unknown_orders_count_full, test_nan_inputs_fail_closed, test_exposure_mark…` |
| B3 Clearance: valid key -> approved; changed rules hash, tick or fee -> rejected; missing… | pass | A changed rules_sha256, tick_size or fee_rate each gives a '<field> changed' rejection. A missing record gives 'no clearance' and an expired one 'clearance expired'. P2 (a record filed under the wrong key_id) now gives 'clearance record is for a different key'. Q10 (key edited after signing) gives 'signature invalid'. P10: min_size 5 and 5.0 give the same id. Real run: rejected before signing, approved after the CLI… | `pytest test_b3_clearance; probe.py P2/P9/P10; probe2.py Q10; real_cli.py (real snapshot 2026-10-01T064938Z, scratch DB under audit-tmp/WP1-B…` |
| B4 Each provenance check has a failing-input test | pass | There is a failing-input test for each check: wrong source, blank source, stale binance:BTC (6000 ms against a 5000 ms bound), missing polymarket feed, and missing basis:USDT for ladder-maker on a binance USDT market. btc-speed is approved without the basis feed. Mutations caught: no source check, no basis check, stale feed ok, missing feed ok. | `pytest test_b4_provenance; mutate2.py` |
| B5 GTD rule: a resting expiry past the allowed bound is rejected | pass | Expiry exactly at end - 2 min is approved; 1 ms later is rejected. Expiry at now + 2 min (below the 2 min + margin floor) is rejected. With a start ahead, now+26m is rejected and now+25m approved. Takers are exempt. Mutations caught: gtd no lower bound, gtd no end bound, start bound ignored. P3 shows the start bound fails open once the start has passed. That is documented in a ponytail note in gtd(). The design docs… | `pytest test_b5_gtd; probe.py P3; mutate2.py; grep of the design docs for the GTD cap` |
| B6 The 1.1x cap refusal works | pass | A bankroll of 55.00 is approved; 55.01 is rejected with binding_cap 'global'. A reducing SELL is still approved at a bankroll of 99. bankroll() marks at best bid, with no bid or no book = 0 (checked: 14.0). P11: bankroll NaN gives 'bankroll nan > 1.1 x global cap 50.00' with binding_cap 'global'. Mutations caught: 1.1x -> 1.2x, NaN bankroll approves, bankroll marks no-bid at 1. | `pytest test_b6_bankroll_over_1_1x_global_cap, test_nan_inputs_fail_closed; probe.py P11; mutate2.py` |
| B7 Breakers: each automatic rule trips on a synthetic input; a reset without a valid unuse… | pass | The stale-feed rule trips once at 61 s. Drawdown trips at 10.2%; after a reset the same equity stays ACTIVE, and a further 10.9% drop trips again. P7 (12% then 50% the same day after a reset) now ends REDUCING. The markout rule locks the market for BUY fills and for adverse SELL fills (c-sold), but not for noisy or favourable ones (Q9: None). A reset is refused for a bad signature, wrong scope, expired token, wrong t… | `pytest test_b7_stale_feed_trips_once, test_b7_daily_drawdown, test_b7_markout_blacklist, test_b7_manual_halt_and_reset_needs_valid_unused_no…` |
| B8 The clearance CLI writes a signed record that the kernel accepts, and a tampered record… | pass | Test: CLI sign exits 0, the kernel approves the record, and stretching the expiry without re-signing gives 'signature invalid'. A token resets once and its reuse is refused. With an empty key the CLI exits 2. Real run: sign rc 0; approved; list shows 'ok crypto-term:BTC:strike rules 43c4bf4589 tick 0.001 source binance:BTC/USDT'; token reset approved and reuse refused; with no ROSTER_HUMAN_KEY it exits 2. load_advice… | `pytest test_b8_cli_record_accepted_and_tamper_rejected; real_cli.py` |
| B9 Tests in trader/tests/test_kernel.py pass | pass | 20 passed in 0.65s. The full trader/tests suite gave 107 passed in 5.47s. | `C:\Users\DELL\Downloads\saugan_pr\market_updated\roster\.venv\Scripts\python.exe -m pytest trader/tests/test_kernel.py -q -p no:cacheprovide…` |

**Open defects at final audit** (all minor; none are blockers or majors):

- **minor** (`trader/breakers.py`): Breakers.on_equity can switch the drawdown breaker off for the rest of a UTC day. If the first equity reading of the day is NaN (bankroll() returns NaN when a book has a NaN bid), self.hwm is set to NaN. After that, max(nan, x) stays NaN and dd = NaN > 0.10 is always False. Probe Q7: equity NaN, then 50, then 10 on the same day leaves the state ACTIVE with hwm nan. This fails open, unlike the NaN-safe kernel checks added in this round. While the NaN lasts, the kernel's 1.1x check still rejects new risk, because ctx… *Fix:* At the top of on_equity, ignore a non-finite equity: 'if not math.isfinite(equity_usd): return'. Alternatively, trip REDUCING on it. Either way, hwm is never set to NaN. Add one assert to test_b7_daily_drawdown.
- **minor** (`trader/tests/test_kernel.py`): Test gap: exposure() limits open orders to the strategy being checked ('strategy is None or o.intent.strategy == strategy'), but no test covers that filter, and the mutation that drops it survives. It does not matter in Phase 1, because the two strategies trade different modes and check() now enforces that. *Fix:* Optional: in test_b2_strategy_budget_binds..., add a live order from the other strategy in the same mode and assert that it does not count toward this strategy's budget. Or leave it until two strategies share a mode.

**Rules check:** Paper only: kernel.py, breakers.py, clearance_cli.py and test_kernel.py import only the standard library (hashlib, hmac, json, os, pathlib, sqlite3, argparse, secrets, collections, datetime, statistics) plus common and trader.contracts. A grep for requests, urllib, http, websocket, aiohttp, socket, clob, web3, eth_account, private_key and order-placing calls found nothing. The 'sign' function is an HMAC over human clearance and reset records, not an order signature. No path can send, sign or post an order. Owned paths: WP1-B's files changed after the dispatch (12:12:40) are trader/kernel.py (12:38), trader/breakers.py (12:38), trader/tests/test_kernel.py (12:39) and tools/clearance_cli.py (1…

---

## WP1-C: Market data, paper execution, reconciliation (1.4, 1.5, 1.7, 1.16)

**Final verdict:** PASS. Fix rounds: 1. Final audit: `claims/WP1-C.audit.json`. Tests: `trader/tests/test_execution.py`.

| AC | Status | Evidence | Command |
|---|---|---|---|
| C1 A live smoke run (>= 60 s) receives Polymarket books for target markets and Binance tic… | pass | Exit 0, SMOKE OK. 222 markets (77+77 strike, 2+2 daily updown, 32+32 fast). crypto-term: 316/316 tokens had a book; crypto-fast: 120/128. 63,168 book events and 198 trades. BTC 670 ticks, ETH 698. DVOL BTC 35.49 / ETH 49.65; usdt_usd 0.999455; RTT 207.7 ms. Every kernel feed name was present (polymarket, polymarket:<mode>, binance:BTC/ETH, dvol:BTC/ETH, basis:USDT). Book accuracy: 116,294 of 116,646 price_change mess… | `python build/phase-1/audit-tmp/WP1-C/smoke.py (runs trader.marketdata.main --seconds 75, with the RTT log and any crawl sent to scratch); bo…` |
| C2 Rounding, minimum size, never rounding up and batch limits are tested; setting a live f… | pass | Test passes. P4: 200,000 random prices at ticks 0.01 and 0.001 gave 0 roundings that were more aggressive or off-tick (BUY rounds down, SELL rounds up). round_size floors (4.9999999999 -> 4.99; 5.004 -> 5.0). The only 'up' case is 5e-12 shares of float tolerance, which is not a real round-up. 4.999 is refused below the minimum of 5. A batch of 16 raises ValueError; 15 is accepted. LiveTradingForbidden is raised for l… | `pytest test_rounding_min_size_never_rounds_up_batch_limit_and_live_flag; probe.py P3/P4/P5/P8` |
| C3 Fill-model tests: maker fills on a trade through its price; maker at the touch fills on… | pass | Tests pass. Code: _takers runs before the new book is stored, so a taker fills against the last book received before its arrival. Same-side trades do not move the queue. Trades before created + RTT are ignored (P10: _cum stays empty). P6 with the real trader.fees.fee: taker limit 0.55 fills 2 at 0.50 and kills the rest at 0.60; fee 0.035 = 2*0.07*0.5*0.5. Caveats are listed as minor defects: P1 GTD order, P2 no book… | `pytest test_maker_fills_on_a_trade_through_its_price, test_maker_at_the_touch_fills_only_after_queue_ahead_plus_own_size_trades, test_taker_…` |
| C4 Journal: a simulated crash mid-batch, then replay, reproduces every order's state; an u… | pass | _log writes, flushes and fsyncs before state.apply. A 'new' entry is on disk before the 'ack' entries, which are sent after the whole batch. In the test, KeyboardInterrupt fires halfway through the 2nd 'new' line of a batch. After restart, the torn line is ignored, the journaled-but-unacked order and the in-flight taker are 'unknown', and positions and cash are equal. A retry on that token/side is rejected and adds n… | `pytest test_crash_mid_batch_then_replay_reproduces_every_order_and_unknown_is_not_retried; code read of router.py _log/replay/__init__` |
| C5 Reconciler: positions match the fills; an injected mismatch trips a breaker; YES+NO pai… | pass | Test passes. With the real kernel: a clean reconcile leaves it ACTIVE. Injecting +3 shares of drift gives 'position (journal) Y: 13 vs 10'; kernel state becomes HALTED and the trip record has source 'reconciler' ('reconciler' is in PRIVILEGED). merge_pairs merged 10 pairs, cost 9.5, edge 0.5, leaving positions at 0 and cash at +0.5. | `pytest test_reconciler_matches_fills_trips_on_mismatch_and_merges_pairs; probe2.py with the real trader.kernel.RiskKernel` |
| C6 The measured round trip is logged and used by the taker fill timing | pass | _set_rtt appends each measurement to rtt.jsonl. The builder's runs left 8 lines (202-225 ms; these include the claimed 222.3 and 224.9). My run logged 197.8 and 207.7 ms to scratch. Taker 'new' entries carry arrival_ms = now + 150 + round(rtt) and rtt_ms. In the test, a 400 ms RTT meets a later book than a 100 ms one. | `pytest test_measured_round_trip_sets_taker_arrival_and_is_journaled; cat data/trader/rtt.jsonl; scratch rtt.jsonl from my smoke run` |
| C7 Tests in trader/tests/test_execution.py pass | pass | 14 passed in 0.57s. The whole trader suite: 109 passed in 8.45s. | `.venv\Scripts\python.exe -m pytest trader/tests/test_execution.py -q (from the code root)` |

**Open defects at final audit** (all minor; none are blockers or majors):

- **minor** (`trader/router.py`): A GTD-expired maker can still fill. on_trade does not check expiry before filling and calls _expire(ts_ms) only afterwards. Probe P1: a maker with expiry_ms=100000 filled 10 shares on a trade through its price at ts 200000. In live use the window is small, because on_book expires orders on every book event, but a venue-vs-local clock gap widens it. *Fix:* Call self._expire(ts_ms) at the start of on_trade, or skip makers with o.intent.expiry_ms <= ts_ms in the loop.
- **minor** (`trader/router.py`): A taker that reaches arrival with no book in the router is not killed. It waits, then fills against a book received after its arrival, with the fill stamped at arrival time (look-ahead). Probe P2: arrival at 1250, no book; a book arrived at 3000; the fill came at 0.30 with ts 1250. The kernel does not require a book, so whether this happens depends on the engines. *Fix:* In _takers, when bk is None and arr <= now_ms, log 'done' (FAK with no liquidity) instead of continuing.
- **minor** (`trader/router.py`): Our own orders reuse the same displayed liquidity. Two takers on one token both fill the full level (probe3: 5 shown, 10 filled at 0.50). A second maker at the same price does not count our first maker in its queue_ahead. Both make paper results slightly optimistic. *Fix:* Subtract size already filled at a level from the stored book for the same book snapshot, and add our own resting size at that price to queue_ahead.
- **minor** (`trader/marketdata.py`): on_trade mixes two clocks. It compares the venue's server timestamp (last_trade_price.timestamp) against the local created_ms + RTT. If the local clock is behind the venue (Binance receive lag measured -68 to -86 ms), trades from shortly before the order could rest count towards queue progress. The builder already reported this. *Fix:* Pass the local receive ms (now) as ts_ms to on_trade in MarketData._on_pm, which is conservative, or correct it by the measured server offset.

**Rules check:** Paper only: no code path sends, signs or posts an order. The router imports only stdlib, common, trader.contracts and trader.fees. The only outbound calls in marketdata are HTTPS GET /time to clob.polymarket.com, GETs through common.get_json (Binance klines, Deribit DVOL, Kraken ticker), and on the WebSocket only the market subscribe message and 'PING'. There are no private keys or secrets in the owned files. Owned paths: the only changed code files are trader/marketdata.py, router.py, reconciler.py and tests/test_execution.py. Outside them, only required runtime output exists: data/trader/rtt.jsonl (the C6 RTT log) and the crawler snapshot data/markets/2026-10-01T074836Z.jsonl from the forc…

---

## WP1-D: Ladder-maker strategy (1.6, 1.8–1.13)

**Final verdict:** PASS. Fix rounds: 0. Final audit: `claims/WP1-D.audit.json`. Tests: `trader/tests/test_ladder.py`.

| AC | Status | Evidence | Command |
|---|---|---|---|
| D1 Pricer: matches closed form; P(>K)+P(<=K)=1; decreasing in K; kappa applied per bucket | pass | Probe: digital() against an independent erf-based N(d2) on 5000 random (S,K,sigma,tau) inputs, max error 0.0. P(>K) plus an independent P(<=K)=N(-d2) equals 1 to 1e-12 on all 5000. The price never increases in K over 60k..100k in steps of 25. Through fair_value at tau 23.9/13/11.9/6/2.5/2.4/1/0.3h, kappa is 0.905/0.905/1.034/1.034/1.034/1.150/1.150/1.150 and sigma_P = kappa x DVOL/100 exactly. Future keys in ref['fin… | `pytest trader/tests/test_ladder.py -v -rs (D1 tests: 5 pass, none skipped, so the Phase 0 replay on research/kappa/out/binary.parquet really…` |
| D2 Universe checkpoint rows for every tradable ladder market at each checkpoint (fixtures) | pass | Each of the 13 ladder markets got exactly one row at buckets [24,6,1] (dict equality, no extras or duplicates). There were no rows for the 3 non-ladder markets. Every row's tau_h lies in (bucket-10min, bucket]. Rows carry fair and mid_ex_own (0.5 where a book exists, None where it doesn't). The strike=None market still gets rows with err set. Builder test test_checkpoint_rows_for_every_ladder_market also passes. | `probe.py D2 section: a simulated 50h at 30s ticks with 13 ladder markets (8 BTC strikes, Up/Down, 2 ETH, one with strike=None, one next-day…` |
| D3 Selector: reward term 0 below min size; ties go to the shorter-dated market | pass | With reward min_size 50 and quote size 10, income stays exactly 0.04874719939117203 with or without the reward. With quote_size 50 it rises from 0.0487 to 0.2571. In the exact tie (equal incomes 0.027545306122449) the near-dated market is chosen in both insertion orders, and only its intents are emitted. The selector_ranking record carries income, bids, size, reward, markout, tau_h and fee_rate. | `probe.py D3 section: engine runs with engine.rewards set, plus an exact-tie test with fair_value stubbed identically, in both insertion orde…` |
| D4 Quote engine: spread widens with uncertainty; skew follows inventory; complement p+q<1-… | pass | As unc goes 0 to 0.08, the spread goes [0.02,0.02,0.04,0.06,0.10]. As vol goes 0, 0.02, 0.05, it goes 0.02, 0.04, 0.06. At engine level, a larger sigma_rel_unc gives a wider spread. Skew: long YES lowers the YES bid and long NO lowers the NO bid at net 10/30/45. Complement: 3000 random holdings >= min_size with random costs and mids gave 3000 complement bids, all with cost + bid < 0.99 and size <= held. Pulls fire on… | `probe.py D4 section (market_intents plus full LadderEngine.on_tick)` |
| D5 Sizer invariant on 10,000 random intents; never rounds up; refuses sub-minimum | pass | n=10000 intents, 0 bad. On each one: invariant_ok(q,f,m) from the reason; q == Intent.fair; q = m + 0.3(f-m) to 1e-12; m equals the YES mid_ex_own (or 1 minus it); min_size <= size <= inventory or quote cap; size on the 0.01 grid; price on the tick grid and >= tick; post-only (price < best ask); maker BUY; GTD in (now+2min, end-2min]; complement cost+price < 0.99. floor_to was never above x on 200k on-grid and nextaf… | `probe.py D5 section: 10,000 intents through full LadderEngine.on_tick with random strike/updown markets, tick 0.01/0.001, min_size 1/5/15, r…` |
| D6 Book-integrity check flags a crossed complement book | pass | book_fault gives 'asks sum 0.9400 < 1' for YES ask 0.42 / NO ask 0.52 and 'bids sum 1.0500 > 1' for bids 0.60/0.45. It gives None for coherent books, including the exact-sum-1 boundary. In the engine, a crossed book gives no intents for that market plus a rate-limited data_fault record of kind book_integrity. ladder_arbs is log-only; the engine emits only maker BUY intents. | `probe.py D6 section plus the engine case` |
| D7 Tests in trader/tests/test_ladder.py pass | pass | 19 passed in 5.01s (re-run with -v -rs: 19 passed, 0 skipped). Whole repo: 158 passed in 16.45s. | `C:\Users\DELL\Downloads\saugan_pr\market_updated\roster\.venv\Scripts\python.exe -m pytest trader/tests/test_ladder.py -q -p no:cacheprovide…` |

**Open defects at final audit** (all minor; none are blockers or majors):

- **minor** (`trader/engines/ladder.py`): Complement-bid price cap is skipped for holdings below min_size. quotes() applies the p+q<1-margin cap only when held_other >= m.min_size. With a smaller holding (for example a partial maker fill of 3-4.99 shares), the bid on the other outcome is a plain quote with no cap. Reproduced: holding 4 YES at 0.60 with the mid now 0.40, the engine posts a NO bid at 0.59 x 10, so a fill pairs 4 shares at p+q = 1.19 against 1-margin = 0.99. That locks a loss on merge and contradicts the requirement 'holding one outcome bough… *Fix:* In quotes(), when 0 < held_other < min_size and the cost is known, still cap px at 1 - cost[other] - margin (strictly below), keeping the plain size. If the cost is unknown, skip the bid, as the complement path does. Add one test case with a 4-share holding.
- **minor** (`trader/engines/ladder.py`): Role 23's invariant is checked only on the YES-side (f, m, q). NO-side intents carry 1-f, 1-mid, 1-q, which under float rounding can break sign/magnitude when /f-mid/ <= 4.4e-16. A probe with f within 2 ulps of mid emitted 2717 intents whose parsed reason fails invariant_ok. With real data this can't practically happen (f comes from a CDF, mid is on the tick grid), but the downstream invariant suite would count it as a violation. *Fix:* In market_intents, run invariant_ok on the exact (ff, mm, qq) written into each intent's reason before emitting it, or compute the NO q as shrink(1-f, 1-mid).

**Rules check:** Paper only: ladder.py imports only datetime, math, re, zoneinfo, collections.deque, statistics.NormalDist and trader.contracts. There is no network, socket, file, subprocess, signing or order code (grep of imports, open(, http, socket, urllib, requests, websocket, sign, private, submit, send, sqlite came back clean). The engine only returns Intent objects (maker BUY, kind 'maker'); arbs are log-only records. No secrets (grep for api key, secret, private key, passphrase, mnemonic and 0x addresses: no matches). Owned paths: WP1-D changed only trader/engines/ladder.py and trader/tests/test_ladder.py. trader/engines/__init__.py dates from the orchestrator setup (12:12:51, same as trader/tests/__…

---

## WP1-E: BTC-speed strategy (from 0.12)

**Final verdict:** PASS. Fix rounds: 0. Final audit: `claims/WP1-E.audit.json`. Tests: `trader/tests/test_speed.py`.

| AC | Status | Evidence | Command |
|---|---|---|---|
| E1 Detector: no event before the threshold is crossed; one event per cooldown; a test prov… | pass | All 6 detector tests pass, and the real-Binance-day test ran rather than being skipped. I re-ran the equivalence myself over all 56 BTC 1s files (2026-03-24 to 2026-05-18, 4,838,400 s): Phase 0 detect_events found 1,512 events, MoveDetector found 1,512, identical event by event, at 3.48 us per tick. This matches the builder's claim. I also wrote my own brute-force causal reference, which only looks at ticks already s… | `pytest trader/tests/test_speed.py -q -v (6 detector tests); PYTHONPATH=. python build/phase-1/audit-tmp/WP1-E/equiv56.py; PYTHONPATH=. pytho…` |
| E2 Mapping: the right 5m/15m market and favoured token; markets about to end are skipped | pass | Tests pass. On the real snapshots, every crypto-fast question parses to 5 or 15 (50+18 and 48+16 markets), and every other mode parses to None, so hourly, term and sports markets are excluded. end_time minus the parsed length equals event_start_time on every fast row (0 mismatches), and outcomes are ['Up','Down'] on all of them, which supports token_yes=Up. Fuzz over 540 events and 302 intents with rolling 5m/15m mar… | `pytest (test_maps_to_open_5m_and_15m_and_favoured_token, test_skips_market_about_to_end_and_stale_book, test_skips_move_that_started_before_…` |
| E3 Rule: buys only with >= 5 shares at or below the max price; never sizes above 5 shares;… | pass | Tests pass: 4.99 shares gives no trade, an ask of 0.90 trades and 0.91 does not. Fuzz: all 302 intents were size 5.0, limit price 0.90, BUY taker, with ask <= 0.90 and ask_size >= 5. In random books with sizes 1, 4.99, 5 and 20, 340 markets were skipped for too little size and 56 for an ask above the max. shares values of nan, 0, -1 and 5.0000001 all raise ValueError (MAX_SHARES=5 hard cap). min_size > 5 is skipped,… | `pytest (test_buy_rule_size_and_max_price x4, test_never_sizes_above_five, test_eth_is_ignored); causal_fuzz.py; python -c probe of SpeedEngi…` |
| E4 Each trade record carries all four latency timestamps | pass | Every record in engine.trades carries binance_ms (ref ts_ms), recv_ms (ref recv_ms, else now), decision_ms (now) and arrival_ms (now + 150 + round(rtt_ms)). In the fuzz, all 302 records had all four stamps, with arrival = decision + 150 + 300 at rtt 300. | `pytest test_trade_records_carry_four_latency_stamps; causal_fuzz.py stamp/arrival invariant; code read speed.py:133-134,164-166` |
| E5 The pre-registration dict is complete (statistic, alpha, n, futility rule) | pass | PREREG has statistic 'fee-net P&L per trade in USD held to resolution', cluster = market, cluster-robust SE, alpha 0.0228 (one-sided z=2, 1-Phi(2)=0.02275), pass_rule 'mean > 2 SE with n >= 200' (pass_z 2.0, n 200), futility 'mean < -1 SE once n >= 100' (futility_z -1, futility_n 100), and params. This matches the dispatch text. | `pytest test_preregistration_complete; code read speed.py:42-57` |
| E6 Tests in trader/tests/test_speed.py pass | pass | 19 passed in 2.19s; with -rs -v, 19 passed and none skipped | `C:\Users\DELL\Downloads\saugan_pr\market_updated\roster\.venv\Scripts\python.exe -m pytest trader/tests/test_speed.py -q (from roster/)` |

**Open defects at final audit** (all minor; none are blockers or majors):

- **minor** (`trader/engines/speed.py`): A reference price of zero or below makes MoveDetector.update raise ValueError ('math domain error' from math.log). Fed through SpeedEngine.on_tick, that would crash the loop iteration, not skip the tick. Probe: 6 ticks at 100.0, then price 0.0 raises ValueError. *Fix:* In on_tick, skip a ref whose price is not > 0 (one guard next to the existing None check at line 120).
- **minor** (`trader/engines/speed.py`): Parameter overrides validate only 'shares'. max_price is not checked against (0, 1) or the tick grid: SpeedEngine({'max_price': 1.5}) is accepted. Kernel.check rejects price >= 1, so there is no safety impact, but an invalid registered parameter set could be pre-registered. *Fix:* Raise ValueError in __init__ unless 0 < max_price < 1, alongside the shares check.
- **minor** (`trader/engines/speed.py`): There is no guard against acting on a late Binance tick: if the loop falls behind, the engine still trades a move whose edge Phase 0 found gone by s+3. The builder disclosed this as an open issue. The dispatch only requires a book-staleness skip, so it is not an AC failure. *Fix:* Optional: skip when decision_ms - recv_ms exceeds a registered bound, using the local clock only, so Binance clock offset does not matter.

**Rules check:** Paper only: speed.py imports only math, re, collections.deque and trader.contracts. It does no I/O and has no network, signing, key or order-sending code (grep for urllib/requests/socket/websocket/http/sign/post/key/send/subprocess/os./eval/exec found only the dedupe 'key' variable). The engine returns Intent objects only. The builder's live smoke script is in the session scratchpad, outside the code base, and calls only public read endpoints (Binance wss trades, Gamma /events, CLOB POST /books, GET /time). Owned paths: the deliverables are only trader/engines/speed.py (12:25) and trader/tests/test_speed.py (12:19), and no WP1-E files exist elsewhere in roster. contracts.py has mtime 2026-10…

---

## WP1-F: Integration, scoring, ops, drills (1.18–1.20, invariant suite)

**Final verdict:** PASS (ops pending). Fix rounds: 0. Final audit: `audit-tmp/compile/WP1-F.json`. Tests: `trader/tests tests/invariants`.

| AC | Status | Evidence | Command |
|---|---|---|---|
| F1 60-minute integration paper run with both strategies on live data completes without cra… | pass | run_id 1791353633764 = 2026-10-07 06:13:53 UTC, SHUTDOWN clean at 07:13:53 (60 min), 191 markets. Ledger: 1 run, 1 clean runs_end (mismatches [], violations 0, open_orders 0), 14 reconciles all clean, 0 invariant violations, 0 trips, 372 orders, 1 fill (ladder-maker BUY 10 @ 0.28, maker, fee 0), 3 markouts, 61 latency rows. The regenerated report matches reports/phase1_smoke.md except the wall-clock time-to-evidence… | `Read data/trader/smoke_v2/smoke_run.log; audit-tmp/WP1-F/q.py (read-only sqlite query of smoke_v2/trader.db); bn.py (public Binance 1s kline…` |
| F2 scorer and daily report run on the smoke data and produce the report with every listed… | pass | The rebuild matches the committed daily report except the wall-clock-dependent time-to-evidence rate. Sections: paper P&L per strategy, intents and kernel decisions (rejections by reason), orders and fills, markouts against mid_ex_own (5 s / 1 m / 5 m), pre-registered statistics (ladder per-cluster fee-net statistic; speed held-to-resolution P&L with CR0 cluster SE), universe vs traded, btc-speed events and trades, l… | `.venv\Scripts\python.exe -m nightly.report --dir data/trader/smoke_v2 --date 2026-10-07 --offline --out build/phase-1/audit-tmp/WP1-F/daily_…` |
| F3 invariant suite passes | pass | 125 passed (also 125 passed with the network blocked). The 16 invariant tests cover: AI cannot raise state or size, never rounding up (10k samples), halt means cancel-all confirmed by the reconciler, unknown orders never retried plus journal replay after a torn mid-batch crash, fee values, simulator guards, ledger REPLACE, no send path, prefer_ipv4 and the untraded filter. | `.venv\Scripts\python.exe -m pytest trader/tests tests/invariants -q -p no:cacheprovider (also re-run with a scratch plugin that blocks socke…` |
| F4 drills: 5 forced restarts including kill -9 mid-batch, all with clean reconciles; phase… | pass | 6 runs, 2 clean runs_end (steps 3 and 6), 14 reconciles all with mismatches [], unknown_resolved = 1 after each mid-batch kill, 0 invariant violations, 0 trips. Logs show 'DRILL kill -9 mid-batch: order ... journaled' twice (exit 15) and random kills at 69.1 s and 45.6 s (exit 1); every next startup reconciles clean and the final shutdown is clean with 0 open orders. Caveat (defect 1): all 6 drill runs started before… | `Read reports/phase1_drills.md, data/trader/drills_v2/drill_*.log, drills.json, drills_run.log; q.py on drills_v2/trader.db; compared run_id…` |
| F5 both pre-registrations in the ledger and unchangeable | pass | smoke_v2 and drills_v2 both hold btc-speed-v1 and ladder-maker-v1. UPDATE and DELETE are refused by triggers; INSERT OR REPLACE is refused with recursive_triggers=ON (the loop sets it). On a plain connection it silently replaced btc-speed-v1 (WP1-A root cause, defect 2), and Trader.start on the tampered copy then refused: "pre-registration 'btc-speed-v1' already exists and cannot be changed". Tampering is caught at t… | `q.py (prereg names, triggers); on a scratch copy of smoke_v2/trader.db: UPDATE / DELETE / INSERT OR REPLACE with and without recursive_trigg…` |
| F6 no order can reach the network; grep confirms | pass | No order-sending code anywhere. Hits are only the HMAC verification of human tokens in kernel.py (key from env ROSTER_HUMAN_KEY), common.get_json (public GET), and the ntfy.sh POST in report.py (free, unauthenticated, summary only). PaperRouter raises LiveTradingForbidden on live=True, on the live setter, or on any LIVE_ENV variable. test_no_order_send_path checks the whole import closure in a clean interpreter. No L… | `Grep py_clob_client/post_order/create_order/place_order/sign_order/private_key/eth_account/web3/requests.post/POST//order/urlopen/httpx.(pos…` |
| F7 [ops] 14 consecutive days of paper running on this PC with zero invariant violations | operational_pending | Not runnable in an audit. Procedure documented: python -m trader.loop --paper --minutes 20160 --dir data/trader, a nightly nightly.report, signed clearances, and no sleep. | `n/a (needs 14 days of wall-clock time)` |

**Open defects at final audit** (all minor; none are blockers or majors):

- **minor** (`reports/phase1_drills.md`): Wrong provenance claim about the drills: phase1_drills.md says steps 4-6 used ES_DISPLAY_REQUIRED, but all six drill runs started before trader/loop.py was last saved (steps 4/5/6 at 06:11:34, 06:12:18, 06:12:22 UTC; loop.py mtime 06:12:36 UTC). The delta is most likely only the SetThreadExecutionState flag in main(), so the reconcile evidence stands, but the note is inaccurate. *Fix:* Re-run python -m nightly.drills --dir data/trader/drills_v3 on the final loop.py (about 15 min), or correct the note.
- **minor** (`trader/ledger.py`): Pre-registrations can be replaced by a plain 'INSERT OR REPLACE INTO prereg' on any connection without PRAGMA recursive_triggers=ON; the loop sets the pragma only on its own connection. Caught at the next Trader.start (detected, not prevented). Root cause in trader/ledger.py (WP1-A), outside WP1-F's paths. *Fix:* WP1-A: add a BEFORE INSERT trigger on prereg (and rows) that aborts when the key exists, or set recursive_triggers in Ledger.__init__, plus a test with a fresh connection.
- **minor** (`nightly/report.py`): Time to evidence counts elapsed days to min(t1, now) instead of the last data point, so the rate per day of a finished run depends on when the report is generated (23.34 in the committed report vs 20.64 re-generated). *Fix:* Use min(t1, now_ms, last event_ms in the ledger), or the summed run uptime, as the denominator.
- **minor** (`data/trader`): Superseded run folders are still in data/trader (trial, smoke, smoke60, smoke1h, drill5, drills, drills_final, smoke_final, smoke_prefilter); some contain trips from older code and could confuse a reader. *Fix:* Delete them or move them under data/trader/old/ (user's choice).

**Rules check:** Paper only: no code path in trader/, nightly/ or tests/invariants signs, posts or cancels a real order or calls an authenticated endpoint; PaperRouter raises on any live flag. Only public GETs, public websockets and the optional ntfy POST. No LLM or paid API. Tests pass with sockets blocked. No look-ahead: markouts taken at due time, causal speed detector, scorer windows respect t1. The loop does no sizing; it flags order_exceeds_intent and checks role 23's invariant and the btc-speed 5-share BTC-only rule on every intent. sim_guard runs before kernel.check; a kept resting quote is re-checked; a halt does cancel_all with a confirmation violation after 10 s. Reports regenerated offline match…

---

## How to reproduce

From `roster/`:

```
.venv\Scripts\python.exe -m pytest trader/tests/test_core.py -q        # WP1-A: 37 passed
.venv\Scripts\python.exe -m pytest trader/tests/test_kernel.py -q      # WP1-B: 20 passed
.venv\Scripts\python.exe -m pytest trader/tests/test_execution.py -q   # WP1-C: 14 passed
.venv\Scripts\python.exe -m pytest trader/tests/test_ladder.py -q      # WP1-D: 19 passed
.venv\Scripts\python.exe -m pytest trader/tests/test_speed.py -q       # WP1-E: 19 passed
.venv\Scripts\python.exe -m pytest trader/tests tests/invariants -q    # WP1-F: 125 passed
.venv\Scripts\python.exe -m nightly.report --dir data/trader/smoke_v2 --date 2026-10-07 --offline --out <scratch>.md   # rebuild the daily report from the smoke ledger
python build\phase-1\audit-tmp\compile\compile.py                        # regenerate this file from claims/ and the WP1-F result
```
Reports: [phase1_smoke.md](../../reports/phase1_smoke.md), [phase1_drills.md](../../reports/phase1_drills.md), [phase1_daily_2026-10-07.md](../../reports/phase1_daily_2026-10-07.md). Run data: `data/trader/smoke_v2`, `data/trader/drills_v2`. Auditors' scratch probes: `build/phase-1/audit-tmp/<WP>/`.

---

## Orchestrator follow-up (2026-10-07)

The four minor defects recommended for fixing before the 14-day run are fixed, each with a regression test:

| Defect | Fix | Test |
|---|---|---|
| WP1-D: 99% of ladder intents rejected "over group" | `fit_to_caps()` in `trader/engines/ladder.py` packs ranked targets into the per-group ($10) and strategy ($25) room after holdings; reducing bids always pass | `test_fit_to_caps_packs_targets_into_group_and_budget_room` |
| WP1-C: an expired GTD maker could fill; a bookless taker was not killed | `on_trade` expires first; a taker with no book at arrival is expired | `test_expired_maker_does_not_fill_and_bookless_taker_is_killed` |
| WP1-B: a NaN equity disabled the drawdown breaker for the day | `on_equity` ignores non-finite readings | `test_b7_nan_equity_does_not_disable_the_drawdown_breaker` |
| WP1-A: raw `INSERT OR REPLACE` could rewrite a pre-registration | `PRAGMA recursive_triggers=ON` | `test_raw_replace_cannot_rewrite_a_preregistration_or_ledger_row` (fails without the fix) |

`trader/tests` + `tests/invariants`: **129 passed**.

**Restart gate caveat resolved:** the drills were re-run on the final code in `data/trader/drills_v3/` (log `build/phase-1/drills_v3.log`). Verdict **PASS**: five forced restarts, including two `kill -9` mid-batch, all reconciled with zero mismatches. `reports/phase1_drills.md` now reflects this run.

**Remaining [ops] for the Phase 1 exit gate:** 14 days of paper running. Launcher: `ops/start_paper_14d.bat`.

## Day-1 report review (2026-10-07 evening)

Anomalies found in `reports/daily/paper14_2026-10-07.md` and fixed (771 + 1 tests pass):

| Anomaly | Fix |
|---|---|
| btc-speed bought both sides of market 0xfdbb6b6a (DOWN 0.86, UP 0.90): a $1 pair for $1.76, locked loss about -$3.87 | v2: skip any market already held (`already holding this market`) |
| btc-speed limit was the 0.90 cap; one fill paid 0.58 for a 0.48 ask | v2: limit = ask seen + 0.02 (`max_slip`) |
| btc-speed acted on ticks up to about 1.2 s old (edge gone by about 2 s); worst Binance minutes lagged 15 s | v2: skip when the tick arrived more than 1000 ms late (`stale signal`) |
| ladder-maker sent 139,119 quotes the kernel rejected while REDUCING | loop drops risk-increasing ladder targets while the kernel is not ACTIVE |
| a new strategy version would inherit the old version's trades in its statistic | scorer counts only fills recorded after the current version's pre-registration |

btc-speed is now **v2** with a new immutable pre-registration (`btc-speed-v2`, written at the next start); `btc-speed-v1` keeps its 6 trades. All changes make the system more cautious (rule 7). They load at the next trader start.
