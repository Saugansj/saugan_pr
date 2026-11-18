# Phase 2 Audit: Live-micro (safety gate, live adapters)

Contract: [dispatch.md](dispatch.md). Process: [../README.md](../README.md). An independent auditor agent, which did not write the code, checked every acceptance criterion below. The compiler then re-ran every test suite (2026-10-07).

Nothing in this phase places, signs, posts or cancels a real order, or calls an authenticated endpoint. All authenticated code sits behind the three-flag live guard (config `trader/live/live.json` ships `{"live": false}`, env `ROSTER_LIVE=1`, CLI `--live`). It reads credentials only from environment variables and was tested only against fakes.

## Summary

| Work package | Code audit | Fix rounds | Tests (compiler re-run) | Result |
|---|---|---|---|---|
| **WP2-A** Heartbeat warden, outside-the-VM safety, clock gate (2.1, 2.2, 2.4 clock) | PASS (ops pending) | 0 | 45 passed | Freeze drill: zero open orders after 9.0 s (14.0 s with a 15 s venue). Network cut: zero after 9.0 s, with 18 failed sends and none raising. Clock skew: 250 ms gives REDUCING, 1,500 ms gives HALTED. A failed audit write stops the heartbeat. Kill script matches the HMAC vector on a fake venue. **This PC's clock is about 250-350 ms off, so the clock gate reads REDUCING here** |
| **WP2-B** Live execution and preflight (2.3, 2.7 self-tests) | PASS (ops pending) | 0 | 61 passed | Every authenticated call is blocked when any flag is off (9 methods x 3 flags, 0 transport calls). Dropped-ack drill: HALTED at 30.0 s plus one cancel-all. kill -9 mid-batch (k=1,3,5): 0 reposts, and replay equals memory. Doctor: dry run makes 0 calls. Signer id equals the SDK's EIP-712 hash |
| **WP2-C** Kernel and breaker additions (2.4 except clock, 2.5) | PASS | 0 | 36 passed | Worst-case positions, a cross-instant stress cap (matches an independent scipy brute force exactly), a resolution-risk cap (10% per market, 20% total), a 7-day drawdown breaker, and pull/REDUCING rules. 5 of 5 mutants killed. No [ops] items |
| **WP2-D** Settlement keeper and canary evaluation (2.6, 2.8) | PASS (ops pending) | 0 | 37 passed | Outcome derivation agrees 8,669/8,669 (strike) and 1,116/1,116 (Up/Down) offline. Mismatch drill: 1 page, 1 REDUCING lock, no repage. Canary: PASS on synthetic rows; the shifted control FAILs. **The specified canary rule false-FAILs 57-68% of the time**, which needs your decision |

All 179 Phase 2 tests pass (`tests/phase2`). Together with the Phase 1 trader tests (`tests/phase2 trader/tests`), 288 pass. Nothing failed.

## Phase 2 exit gate: **NOT MET** (the code is ready; live evidence is not)

The build plan's gate is: **canary fills inside replay's 90% interval over ≥ 30 fill clusters, and zero unknown-state incidents, and the pre-registered cluster count reached with the fee-net primary statistic passing.** All three need live-micro trading with real money. The dispatch puts going live out of scope for this build.

| Gate item | Status |
|---|---|
| Canary inside replay's 90% interval over ≥ 30 live fill clusters (2.8) | **[ops] pending** (D12). The evaluator is built and tested on synthetic rows. **Open decision:** as specified (8 checks, each at 90%), a perfect simulator FAILs 57-68% of the time. The builder recommends Bonferroni-adjusted intervals (0.625th-99.375th percentile): 16% false FAILs measured, with full power at a 0.60 to 0.85 fill-rate shift. The rule was not changed |
| Zero unknown-state incidents | **[ops] pending.** The unknown-order handling (5 s cancel and query, HALTED at 30 s, never blind-retry) passes its drills on fakes (B6-B8) |
| Pre-registered cluster count reached, fee-net statistic passing (2.9) | **[ops] pending.** Not built in this phase, by the dispatch: it uses the Phase 1 scorer and registry |
| Post-close capture, live (2.10) | **Not built**, by the dispatch: its Phase 0 measurement failed (0.9% of prints against a 33% gate) |

### What remains [ops] before going live and before the gate can be met

The **entry gate** (2.1-2.6 built, every 2.7 drill passed on paper) is met at code level: every drill passes on fakes. Before the first live order, the dispatch also requires the Phase 1 exit gate (14 days, compiled separately), every 2.7 drill passing on the real venue, keys on the VM and your token.

| Item | WP / AC | Needs |
|---|---|---|
| Venue setup: `trader`-only key file, Deposit Wallet session key, hot wallet funded up to the cap, SDK installed on the VM | B17 | VM, keys, funds (pip was not run on this machine) |
| Doctor on the real venue: wallet check, deep post-only order then cancel, tiny round trip | B18 | Keys and all three flags |
| Real-venue drills: dropped ack, kill -9 mid-batch | B19 | Live venue |
| Freeze drill on the real venue (zero open orders within 15 s) | A13 | Keys, live venue, resting deep post-only orders |
| Network-cut drill on the real venue (venue cancels after about 10 s) | A14 | Keys, live venue |
| Kill script live from the home PC | A15 | L2 credentials on the home PC |
| External dead-man (healthchecks.io) with an observed alert | A16 | A healthchecks check and `ROSTER_DEADMAN_URL` on the VM |
| Clock sync on the VM (chrony) | WP2-A finding | Without it, the clock gate holds REDUCING (this PC: about +250-350 ms; CLOB /time about +715-912 ms) |
| Real canary report over ≥ 30 live fill clusters | D12 | About 30 days of live-micro, plus your decision on the canary rule |
| Chainlink TWAP reader (crypto-fast outcome derivation) | D13 | CLOB credentials. Until then, Chainlink markets derive None, then page and lock after the 10-minute grace |
| Relayer redeem/merge execution, and a real ntfy page drill | D14 | Relayer (role 05), `ROSTER_NTFY_TOPIC` |
| Promotion evidence (2.9) | not a WP | Live clusters, Phase 1 scorer and pre-registration |

## Decisions for you

1. **Canary statistic (2.8).** Keep the specified per-bucket 90% rule (it blocks the gate most of the time even with a perfect simulator), or switch to the Bonferroni-adjusted interval. Changing it changes the build plan's statistic.
2. **Clock sync on the VM** must be in place before going live, or the kernel will sit in REDUCING.

## Wiring later

Phase 2 modules are standalone. Nothing imports `trader.loop` or another Phase 2 work package. The wiring package should do the following.

**WP2-A (heartbeat, clock, kill script)**
- At the end of each loop tick: `f = health_failures(now, tick_ms, ws_connected, reconcile_clean, router.orders, books, feed_age_ms, journal_ok, audit_ok, clock_offset_ms, kernel.state)`, then `sent = warden.end_of_tick(now, f)`. While `kernel.state` is HALTED, call `warden.on_halted(now)`. Then `deadman.maybe_ping(now, sent)`.
- Build `failures` from `health_failures(..., kernel.state)` exactly. The warden ends a halt episode when the list has no `halted` entry; if the loop builds the list differently, `on_halted` cancels on every tick and never latches (auditor caution).
- The warden's three callables come from WP2-B: `send = client.heartbeat`, `cancel_all = router.cancel_all`, `confirm_zero_open = router.confirm_zero_open`.
- A worker thread runs every 60 s: `off = clock.measure()` (optionally also `clob_offset_ms()`), then `ClockGate(kernel).apply(*clock_gate(off, measured_at_ms, now, clob_off))`. Its latest offset feeds `health_failures`.
- `warden.rearm()` belongs in the human reset path. `DeadMan()` reads `ROSTER_DEADMAN_URL`.
- `tools/live_tools/kill_all.py` is copied alone to the home PC with the four L2 variables, and run as `python kill_all.py --live --config live.json` with `ROSTER_LIVE=1`.
- Contract gap: KernelContext has no clock or health fields, so `health_failures` and `clock_gate` take them as arguments.

**WP2-B (live router, CLOB client, doctor)**
- When all three flags are set, build `LiveRouter(markets, L2Client(cli_live=args.live), SdkSigner(), trip=kernel.trip, journal=data/trader/live_journal.jsonl)` instead of PaperRouter, and keep `router.starts` in sync with `kernel.starts`.
- On every pass: call `router.poll(now)` and send its fills to the reconciler and ledger. Run `UserWS(router.on_user_event, markets=cids, cli_live=True).run()` as an asyncio task; its `connected` flag is `ws_connected`. Call `router.reconcile_venue(client.open_orders())` on start and every minute (empty list = clean).
- `ctx.open_orders` comes from `router.open_orders()`, which includes unknown orders.
- The doctor runs once, by hand, before the first live order, and writes into the same live journal. Paper and live never run in one process (PaperRouter refuses to start when `ROSTER_LIVE` is set).
- `SdkSigner` fills the SDK's private tick-size cache (`_ClobClient__tick_sizes`). If an SDK upgrade renames it, call `get_clob_market_info(cid)` once per market at startup instead.
- `poll` sends a cancel and a query on every call for each pending order. Space these out if the venue rate-limits.

**WP2-C (live risk caps, drawdown breaker)**
- After `kernel.check(intent, ctx)` approves: `check_live(intent, ctx, worst_case_positions(router.positions, router.open_orders()), md.ref, opens, printed)`. Here `opens` is {cid: Up/Down open price} from `ref[asset]['final']` at `ladder.prev_noon_ms(m.end_ms)`, and `printed` is WP2-D's `keeper.oracle_gap()`.
- Next to `Breakers.on_equity`: `dd7.on_equity(trader.kernel.bankroll(cash, positions, books), now)`. Persist `dd7.samples()` as JSON under `data/trader/` (for example `dd7_samples.json`) and restore with `SevenDayDrawdown(kernel, samples=...)`.
- When any scope enters REDUCING, cancel `pull_ids(router.open_orders(), router.positions, markets, cids_in_scope)` through `router.cancel` (global scope = every cid). Each kernel-approved reducing intent in REDUCING also goes through `reducing_rule(intent, m.fee_rate, group_over_cap, human_token_ok)`; a non-None result means refuse.
- **Keep held markets in `ctx.markets` until they are redeemed.** Phase 1 marketdata drops markets 6 h after `end_ms` (`trader/marketdata.py:406-407`). Without this, the stress and resolution caps skip a held, disputed market, and the 20% total undercounts.

**WP2-D (settlement keeper, canary)**
- Build `SettlementKeeper(markets, common.get_json, settlement.page, kernel.trip)` and call `keeper.step(now_ms, router.positions)` once a minute in a worker thread (public GETs only).
- Send `fund_intents(router.positions, router.open_orders(), markets, keeper.statuses)` through `gate(fi, kernel.scopes, keeper.statuses.get(fi.cid))`, then to role 05's relayer once it exists (D14). In paper, `PaperRouter.merge` covers merges.
- Feed `keeper.oracle_gap()` to the ladder engine's pull rule and to WP2-C's `check_live(..., printed=...)`.
- `settlement.page` reads `ROSTER_NTFY_TOPIC` at call time; when unset, it only logs.
- Canary, nightly: build rows with `rows_from_journal(data/trader/live_journal.jsonl, markets, mid_at)` and the same over the replay journal, where `mid_at(token, ts)` is the mid excluding own orders from the recorder's books. Then run `python -m trader.live.canary --live live.jsonl --replay replay.jsonl --out reports/phase2_canary.md`.
- Contract gaps, worked around without edits: Intent has no merge or redeem kind (FundIntent and `gate()` are used instead), the Kernel protocol's `trip` has no level argument, and MarketInfo has no hourly flag or Up/Down open.

## Orchestration notes

- All four work packages passed their first independent audit, with 0 fix rounds.
- The WP2-A builder resumed an earlier partial build. It removed a `secret="x"` literal from the tests, which made A10 fail, and wrote the report.
- WP2-B and WP2-D results were passed inline. WP2-A and WP2-C results were read from `claims/WP2-A.*.json` and `claims/WP2-C.*.json`.
- `trader/loop.py` changed during the build because WP1-F was editing it in parallel. No Phase 2 package wrote to it or imports it.
- The Phase 1 audit has not been compiled yet (`build/phase-1/audit.md` does not exist), so the Phase 1 exit gate status is not restated here.
- **Compiler re-run:** 45 + 61 + 36 + 37 = 179 passed; `tests/phase2` together = 179 passed; `tests/phase2 trader/tests` = 288 passed.

---

## WP2-A: Heartbeat warden, outside-the-VM safety, clock gate (2.1, 2.2, 2.4 clock)

**Final verdict:** PASS_WITH_OPERATIONAL_PENDING. Agent sequence: build (resumed partial work) → audit. Files: `trader/live/heartbeat.py`, `trader/live/clock.py`, `tools/live_tools/kill_all.py`, `tests/phase2/test_heartbeat.py`, `reports/phase2_safety.md`.

| AC | Status | Evidence | Command |
|---|---|---|---|
| A1 health_failures: [] when healthy; each single failing input names its check | pass | All 14 parametrized cases give exactly one entry, prefixed with its check name. The boundaries pass (2,000 ms tick, -1,000 ms offset, 30,000 ms book, 10,000 ms unknown feed). STALE_MS and LIVE are imported from trader.kernel. Probe: NaN or None inputs fail, and three failures give three entries | `pytest test_a1_*; read heartbeat.py:28-56; audit-tmp/WP2-A/probe.py` |
| A2 Sends only when healthy, chains heartbeat_id, returns False without raising | pass | send got ids ['', 'hb1', 'hb2']. ConnectionError gives False, errors == 1, last_error 'send: ConnectionError'. A failures list holding only 'halted' blocks the send | `test_a2_*; probe.py` |
| A3 Halt cadence every 2 s until confirmed; latched stop at 10 s until rearm() | pass | cancels == [0, 2000, 4000], then stops. Unconfirmed: cancels every 2 s and latches stopped at exactly 10,000 ms. No heartbeat until rearm(). A cancel_all or confirm exception counts as not confirmed | `test_a3_* (4 tests); probe.py` |
| A4 Freeze, negative control and network cut on a fake venue | pass | Freeze: passed=True, zero_after_ms 9000 (14000 with a 15 s venue). Negative control: passed=False. Network cut: zero after 9000 ms, 18 send errors, 0 heartbeats after the cut. Matches the report | `test_a4_* (6 tests); python -m tests.phase2.test_heartbeat` |
| A5 Dead-man | pass | Pings at 0, 61 and 121 s only. No URL (or an empty one) means no call. Errors are swallowed. The URL never appears in logs, repr or returns, even when the exception message contains it | `test_a5_deadman; probe.py` |
| A6 SNTP with a fake socket | pass | Offset 146 and delay 8 within 1 ms. Kiss-o'-Death, bad mode, zero transmit time, a non-echoed transmit time, leap indicator 3 and a 47-byte packet are rejected. measure() is the median of the servers that answered, and None when all fail | `test_a6_*; probe.py; read clock.py:35-76` |
| A7 Clock gate with a real RiskKernel | pass | 50/100/150/1000/1500 ms give A/A/R/R/H, symmetric. None, NaN or older than 600,000 ms gives REDUCING. CLOB +2,500 gives HALTED. One trip per rise, from a privileged source. REDUCING rejects BUY; HALTED rejects both. After recovery the kernel stays HALTED until a human reset | `test_a7_* (4 tests); drill printer` |
| A8 Failed audit write stops the heartbeat | pass | A real AuditLog whose path is a directory raises AuditWriteError. failures == ['audit: last audit write failed'] and send is never called | `test_a8_failed_audit_write_stops_heartbeat` |
| A9 kill_all.py | pass | Missing flag: exit 2 with 0 transport calls (6 cases). POLY_PRIVATE_KEY set: exit 3. Fake server: signature equals vector qFXxB7_..., zero open confirmed, exit 0. A venue that never empties: 8 DELETEs and exit 1 at 14 s simulated. Imports are stdlib only. Request shape matches the SDK | `test_a9_* (5 tests); CLI runs with fake env; probe.py` |
| A10 No network in tests; no secrets in the owned paths | pass | 45 passed under a stricter DNS and connect block (52 socket calls, 0 off loopback). The 0x+64-hex grep and the assigned-secret grep are empty | `audit-tmp/WP2-A/strict_nonet.py; greps over the 5 owned paths` |
| A11 Report covers the A4/A7/A8/A9 drills and ends with How to reproduce | pass | Every number matches the re-run. The smoke finding holds (auditor: about +250 ms, REDUCING; CLOB +715 ms) | `read reports/phase2_safety.md; optional SNTP/CLOB /time smoke` |
| A12 Tests pass | pass | Compiler re-run: 45 passed in 1.75 s | `.venv\Scripts\python.exe -m pytest tests/phase2/test_heartbeat.py -q` |
| A13 [ops] Freeze drill on the real venue | operational_pending | Needs keys, the live venue and resting post-only orders; `freeze_drill` is injectable | n/a |
| A14 [ops] Network-cut drill on the real venue | operational_pending | Needs keys and the live venue | n/a |
| A15 [ops] Kill script live from the home PC | operational_pending | Needs L2 credentials on the home PC | n/a |
| A16 [ops] External dead-man with an observed alert | operational_pending | Needs a healthchecks.io check and ROSTER_DEADMAN_URL on the VM | n/a |

**Open defects at final audit** (none are blockers or majors):

- **minor** (`tools/live_tools/kill_all.py:124`): the retry loop catches only (OSError, ValueError). An `http.client.HTTPException` (for example IncompleteRead) escapes main() after the first request instead of retrying every 2 s for 15 s. The exit code is still 1, so there is no false confirmation. Fix: also catch `http.client.HTTPException`.
- **minor** (`trader/live/clock.py:95`): clock_gate does not check that `measured_ms` is finite, so a NaN timestamp counts as fresh and can return ACTIVE instead of REDUCING. Fix: test `_finite(measured_ms) is None`.

**Rules check:** Files only in owned paths. Contracts unchanged (sha256 1c0e3f29...68bf). Only stable Phase 1 imports. heartbeat.py and clock.py reach the network only through the env-gated dead-man GET, public SNTP and public CLOB /time. kill_all's authenticated calls run only after the three-flag check, with env-only credentials and nothing printed. No LLM, no secrets, and the report ends with How to reproduce.

---

## WP2-B: Live execution and preflight (2.3, 2.7 self-tests)

**Final verdict:** PASS_WITH_OPERATIONAL_PENDING. Agent sequence: build → audit. Files: `trader/live/clob.py`, `trader/live/router.py`, `trader/live/live.json`, `tools/live_tools/doctor.py`, `tests/phase2/test_live_exec.py`, `reports/phase2_execution.md`.

| AC | Status | Evidence | Command |
|---|---|---|---|
| B1 Three-flag guard | pass | live.json is `{"live": false}`. live_enabled needs cfg live is True, ROSTER_LIVE == '1' and cli_live True. All 8 combinations and the near misses are off and name the missing flags. Doctor with no flags prints all 3 missing | `pytest test_b1_*; cat trader/live/live.json` |
| B2 Every authenticated call blocked with any flag off | pass | `self.transport(` appears once, in L2Client._req, after require_live() and Creds.from_env. UserWS checks the guard before every connect. The LiveRouter constructor checks it too. 0 transport calls for 9 methods x 3 flags, and a flag turned off after construction blocks the next call | `pytest test_b2_*; grep transport(/urlopen/connect( clob.py` |
| B3 HMAC vectors, header names, Creds repr | pass | Both orchestrator vectors reproduce. The header tuple has exactly five names. Creds repr is masked. Errors name variables, not values, and VenueError redacts credentials | `pytest test_b3_*` |
| B4 GTD table and refusal | pass | min(requested, end-2 min, start-5 min while ahead), floored to seconds. Anything under now+2 min+30 s is refused. 10 table cases. GTD for makers; FAK with expiration 0 for takers | `pytest test_b4_*` |
| B5 Write-ahead | pass | All `new` lines are fsynced before the single post_orders call. The fake venue checks the journal on post (wal_checked == 1). An fsync ENOSPC propagates with 0 posts | `pytest test_b5_*` |
| B6 Acks, rejections, timeouts, poll | pass | Ack gives open. success:false or 4xx (except 408) gives cancelled. 5xx, 408, timeout, missing orderID or a non-list body gives unknown. Poll at 5.000 s sends DELETE then GET. Each posted id is posted at most once over 40 s | `pytest test_b6_*; audit-tmp/WP2-B/probe.py` |
| B7 Dropped-ack drill | pass | Real RiskKernel: halted at 30.0 s, trips [global, HALTED, router], 1 cancel-all. A retry is rejected, posts of that id = 1, and the order is cancelled after reconcile | `python -m tests.phase2.test_live_exec; pytest test_b7_*` |
| B8 kill -9 mid-batch drill | pass | k=3: [unknown, unknown] after restart, 0 reposts, a new same-side order rejected, replay equals memory. k=1,3,5 pass. A torn line is ignored and terminated | `pytest test_b8_*` |
| B9 User events and reconciliation | pass | Fills journaled once per trade id, and the dedup survives a restart. FAILED trips HALTED. Venue-only and journal-only orders are flagged. confirm_zero_open is True only when both sides are empty | `pytest test_b9_*` |
| B10 Paper rules carry over | pass | Uses Phase 1 round_price and round_size. Covers min size, tick range, the batch-of-16 limit, an unknown order blocking its token and side, and SELL capped at the position not already offered. No size is rounded up | `pytest test_b10_*` |
| B11 Doctor | pass | Dry run: exit 2, 0 venue calls, 0 signer calls. All pass: exit 0. Deep fill: FAIL plus 1 cancel-all. Residual 5.0: FAIL. Cost 0.225 > 0.10: refused with 0 calls. Every order goes through LiveRouter's journal | `python -m tools.live_tools.doctor --step all --cid 0xabc; pytest test_b11_*` |
| B12 Signer | pass | The main venv raises LiveUnavailable with the [ops] message. Spike venv: our id == SDK EIP-712 hash for BUY and neg-risk SELL, the signature recovers to the key, posted false, 0 network calls | `pytest test_b12_*; research/spike/.venv/Scripts/python.exe -m trader.live.clob --signer-check` |
| B13 User channel against a local websocket server | pass | Subscribe message carries credentials from the env dict. connected goes True, False, True across a server drop. With ROSTER_LIVE=0: LiveGuardError and 0 connections | `pytest test_b13_user_ws` |
| B14 No network, no secrets, no loop import, Phase 1 unmodified | pass | Greps empty. Loopback-only fixture present. Contracts and Phase 1 files predate the build (except trader/loop.py, owned by WP1-F). No live journal was created | `greps; ls --time-style=full-iso` |
| B15 Report | pass | Covers B6-B11, venue rejection and the signer check. Ends with '## How to reproduce'. Numbers match the re-run | `grep '^#' reports/phase2_execution.md` |
| B16 Tests pass | pass | Compiler re-run: 61 passed in 2.93 s | `.venv\Scripts\python.exe -m pytest tests/phase2/test_live_exec.py -q` |
| B17 [ops] Venue setup | operational_pending | Needs the VM, keys and funds; pip was not run here | n/a |
| B18 [ops] Doctor on the real venue | operational_pending | Needs keys and all three flags | n/a |
| B19 [ops] Real-venue drills | operational_pending | Needs the live venue; passes on fakes (B7, B8) | n/a |

**Open defects at final audit** (none are blockers or majors):

- **minor** (`trader/live/router.py`): if GET /data/order omits associate_trades, poll journals the fill with no trade ids. The same trade arriving on the user channel is then journaled again (capped by remaining size), and a cancelled order reopens as partial. Probe: order 10, poll 4 → filled 4; user trade 4 → filled 8. Low risk, because Polymarket normally returns associate_trades. Fix: skip user-channel legs for poll-resolved fills without trade ids, or cap them by the journaled size_matched.
- **minor** (`tools/live_tools/doctor.py`): `--config PATH` lets the config flag point at any file with live:true. The env and `--live` flags are still required. Fix: drop it, or document it as matching kill_all's `--config`.
- **minor** (`trader/live/router.py`): reconcile_venue marks an order absent after a cancel-all as cancelled even when get_order failed, so a matched taker's fill could be missed on a flaky venue. This matches the spec. Fix: mark it cancelled only after a successful get_order or a definite not-found.

**Rules check:** No path reaches the network without the guard. live.json ships false and the CLI defaults off. Creds are env-only, masked and redacted. No keys or secrets in owned files. Loopback-only tests. Sizes floored. Files confined to the owned paths, with no trader.loop import. The auditor wrote only scratch under `audit-tmp/WP2-B/`.

---

## WP2-C: Kernel and breaker additions (2.4 except clock gate, 2.5)

**Final verdict:** PASS. Agent sequence: build → audit. Files: `trader/live/risk.py` (238 lines), `tests/phase2/test_live_risk.py`. No [ops] items, and the dispatch names no report.

| AC | Status | Evidence | Command |
|---|---|---|---|
| C1 worst_case_positions: non-terminal BUYs add, partial adds the remainder, unknown adds full size, SELLs never subtract; works on a replayed journal | pass | Table covers all 8 statuses plus SELLs. Replay of a fixture with a torn last line gives 53 for both dict and list input. The input is not mutated. Mutant unknown→size-filled: 4 failures | `pytest test_c1_*; audit-tmp/WP2-C/mutate.py unknown_partial` |
| C2 Stress: 4 shocks x sigma*1.5 on BTC/ETH/SOL together; hand computation within 1e-9; worst scenario by side | pass | SHOCKS=(-0.10,-0.05,0.05,0.10), VOL_UP=1.5. Independent scipy brute force on a random 12-market portfolio: 19.417768650607456, diff 0.0. Mutant VOL_UP=1.0: 2 failures | `pytest test_c2_*; audit-tmp/WP2-C/probe.py` |
| C3 stress_check | pass | Approves at 0.99x and exactly 5% (room 0.00), rejects at 1.01x, binding_cap 'stress'. An unknown BUY flips approval. Unpriceable positions count as a total loss. NaN rejects. Printed and non-crypto excluded | `pytest test_c3_*; probe.py case 6` |
| C4 resolution_check: 10% per market, 20% total | pass | 11 x 0.95 > 10 gives resolution:p1; 20.90 > 20 gives resolution:total. Held printed positions and unknown orders count. No bid counts as 1.0. Unprinted is unaffected. NaN rejects. Mutant resolution_off: 5 failures | `pytest test_c4_*; mutate.py resolution_off` |
| C5 SevenDayDrawdown | pass | 11% trips global REDUCING with source breaker:drawdown7d (privileged). Exactly 10% and an expired high do not trip. A real signed reset re-arms; a reused nonce is refused. Rebuilding from JSON samples gives identical trips. Mutant no_rearm: 2 failures | `pytest test_c5_*; mutate.py no_rearm` |
| C6 pull_ids and reducing_rule | pass | The fixture returns exactly ['uncovered', 'unk']. Refuses a taker exit without a token unless the group is over its cap, a maker SELL below fair - fee and a complement BUY above fair + fee. NaN refuses | `pytest test_c6_*; probe.py cases 7, 10` |
| C7 Entry-gate regression through RiskKernel | pass | REDUCING rejects risk-increasing intents and accepts reducing ones, through signed clearance, provenance and GTD. A market lock is scoped. An AI trip is capped at REDUCING. A human HALTED rejects all | `pytest test_c7_*` |
| C8 check_live order, binding cap, reducing pass-through | pass | Stress runs first. When only resolution fails, the result is resolution:p1. Approvals name the tightest cap. Reducing intents pass (uses RiskKernel.reduces). Mutant no_reduce_pass: 2 failures | `pytest test_c8_*; mutate.py no_reduce_pass` |
| C9 risk.py does no I/O | pass | The grep finds nothing. Imports are only on the dispatch's stable list. No environment reads | `grep -nE "open\(\|socket\|urllib\|httpx\|sqlite3\|requests" trader/live/risk.py` |
| C10 Tests pass | pass | Compiler re-run: 36 passed in 0.48 s | `.venv\Scripts\python.exe -m pytest tests/phase2/test_live_risk.py -q` |

**Open defects at final audit** (none are blockers or majors):

- **minor** (`trader/live/risk.py`): tokens missing from `markets` are skipped by stress_loss and the resolution exposure. Phase 1 marketdata drops markets 6 h after end, so a held, disputed market can fall out of the 20% total. Standalone resolution_check also approves an intent whose printed cid is missing (check_live rejects it first as 'unknown market'). Fix: count missing tokens as shares x 1.0, or have the wiring keep held markets until redeemed.
- **minor** (`trader/live/risk.py`): a negative DVOL or an infinite spot is not treated as unpriceable. A negative sigma inverts the digital (probe: a gain of -0.90 instead of a loss of +4.97). Deribit never publishes a negative DVOL. Fix: in `_yes`, require finite positive S and sigma.
- **minor** (`trader/live/risk.py`): the SevenDayDrawdown constructor does not filter non-finite restored samples. A NaN in a corrupted file blocks tripping for up to 7 days. Fix: apply on_equity's finite check in `__init__`.
- **minor** (`tests/phase2/test_live_risk.py`): the tests import `clearance_key` and `key_id` from trader.kernel, which are not on the stable-import list. Tests only; no production effect.

**Rules check:** Two owned files only. Contracts unchanged (by sha256 and mtime). No I/O, network, environment reads, LLM or secrets. NaN-safe comparisons. Reuses RiskKernel.reduces and kernel.LIVE instead of copying them.

---

## WP2-D: Settlement keeper and canary evaluation (2.6, 2.8)

**Final verdict:** PASS_WITH_OPERATIONAL_PENDING. Agent sequence: build → audit. Files: `trader/live/settlement.py` (264 lines), `trader/live/canary.py` (174 lines), `tests/phase2/test_settlement_canary.py`, `reports/phase2_settlement.md`, `reports/phase2_canary_synthetic.md`, `reports/phase2_canary_synthetic_shifted.md`.

| AC | Status | Evidence | Command |
|---|---|---|---|
| D1 derive_outcome: strike, daily and hourly Up/Down, chainlink/sports → None, DST timing | pass | Timing matches binance_check. The winter strike candle is 17:00Z. 3 of 3 mutants killed. Offline history: strike 8,669/8,669 agree with winners and 7,568/7,568 with proposals; Up/Down 1,116/1,116 and 713/713 | `pytest test_d1_*; python -m tests.phase2.test_settlement_canary --history` |
| D2 proposal(): 1e18 YES, 0 NO, 5e17 50-50; '69'/missing/garbage → None | pass | Exact-string PRICE lookup. 8 parametrized None cases. Fixtures are real resolutions.jsonl records | `pytest test_d2_*` |
| D3 Mismatch drill: exactly one page and one REDUCING lock, deadline = proposal + 2 h, no repage | pass | (1, 1) after step 1 and after step 2. Trip scope 0xs1, source breaker:settlement, REDUCING, with the real RiskKernel's global still ACTIVE. Dedupe mutant: 3 failures | `pytest test_d3_*; python -m tests.phase2.test_settlement_canary` |
| D4 Unreadable after print+grace → page and lock; dispute → one trip and one page | pass | 9 min: (1, 1); 10-11 min: (2, 2). Dispute: (1, 1) breaker:dispute. Grace mutant killed. Garbage input does not raise | `pytest test_d4_*; drill output` |
| D5 oracle_gap holds a printed, unresolved market and drops it on resolution | pass | waiting → printed (in gap) → matched → resolved (out). 0 klines GETs before print + 60 s, so there is no look-ahead | `pytest test_d5_oracle_gap; probe` |
| D6 fund_intents and gate | pass | 5.999999 pairs merge as 5.99 (floored). An unknown SELL counts as offered. Never redeems mismatched, disputed or locked markets. Gate matrix: merge [F,F,T,T,T], redeem [F,F,T,F,T]. 2 mutants killed | `pytest test_d6_*; audit-tmp/WP2-D/r2/probe.py` |
| D7 page(): no topic → no call; body has no balance, position or credential | pass | Topic read from env at call time. Body has only cid, question, proposed, derived and deadline. No hard-coded topic | `pytest test_d7_*; grep -nE 'ntfy\.sh/\w'` |
| D8 Canary: same-process PASS, shifted FAIL naming bucket and metric, 29 → INSUFFICIENT, no replay clusters → FAIL, deterministic | pass | Regenerated tables are identical to the committed synthetic reports. The no-replay mutant is killed. The PASS relies on a fixed seed: the measured same-process FAIL rate is 136/200 = 68% (a property of the specified rule; flagged for you) | `pytest test_d8_*; --synthetic regenerate; audit-tmp/WP2-D/r2/rate.py` |
| D9 rows_from_journal | pass | queue_ahead comes from `new` entries, markout from injected mid_at at +300 s. Open, unknown and taker orders excluded. A torn last line is tolerated. Mutant killed | `pytest test_d9_rows_from_journal` |
| D10 No-network fixture; report sections and How to reproduce | pass | 37 passed under a strict DNS/connect-blocking plugin. All three reports end with '## How to reproduce' | `pytest -p strictnet; grep '^## ' reports/*.md` |
| D11 Tests pass | pass | Compiler re-run: 37 passed in 3.84 s | `.venv\Scripts\python.exe -m pytest tests/phase2/test_settlement_canary.py -q` |
| D12 [ops] Real canary report over ≥ 30 live fill clusters | operational_pending | Only SYNTHETIC reports exist. Needs about 30 days of live-micro | n/a |
| D13 [ops] Chainlink TWAP reader | operational_pending | Not built; needs CLOB credentials. Chainlink markets derive None, then page and lock after the grace | n/a |
| D14 [ops] Relayer redeem/merge and a real ntfy drill | operational_pending | No execution code; FundIntent and gate only. No real page sent | n/a |

**Open defects at final audit** (none are blockers or majors):

- **minor** (`reports/phase2_settlement.md`): the report quotes a 57-59% canary false-FAIL rate (seeds 100-199). The auditor measures 68% on seeds 1000-1199. Fix: quote a range of about 59-68%.
- **minor** (`trader/live/settlement.py`): a held Chainlink market that resolves before the 10-minute grace never pages or locks, and redeem is emitted without a derived check. This is harmless, because redeem only reduces exposure. Fix: accept and document it, or fire the 'unreadable' alarm when a held market resolves with derived None.
- **minor** (`tests/phase2/test_settlement_canary.py`): no test pins the canary's 5th/95th percentile interval; mutants widening it survive. Fix: one test with a shift outside 90% but inside 98%.
- **minor** (`trader/live/canary.py`): bucket_of raises StopIteration on a negative or NaN queue_ahead. Fix: validate rows and raise a ValueError naming the row.
- **minor** (`reports/phase2_canary_synthetic.md`): How to reproduce points at an ephemeral scratchpad path. Fix: use `<dir>` placeholders.

**Rules check:** Owned files only. Contracts unchanged (sha256 1c0e3f29...68bf). Imports are only trader.contracts, trader.engines.ladder.prev_noon_ms and trader.router. No order, signing or authenticated endpoint. The only direct network call is the spec-mandated ntfy POST, and only when ROSTER_NTFY_TOPIC is set. No look-ahead. Sizes floored. No secrets.

---

## How to reproduce

From the code root `C:\Users\DELL\Downloads\saugan_pr\market_updated\roster`:

```
.venv\Scripts\python.exe -m pytest tests/phase2/test_heartbeat.py -q          # 45 passed
.venv\Scripts\python.exe -m pytest tests/phase2/test_live_exec.py -q          # 61 passed
.venv\Scripts\python.exe -m pytest tests/phase2/test_live_risk.py -q          # 36 passed
.venv\Scripts\python.exe -m pytest tests/phase2/test_settlement_canary.py -q  # 37 passed
.venv\Scripts\python.exe -m pytest tests/phase2 -q                            # 179 passed
.venv\Scripts\python.exe -m pytest tests/phase2 trader/tests -q               # 288 passed
```

Drill printers: `python -m tests.phase2.test_heartbeat`, `python -m tests.phase2.test_live_exec`, `python -m tests.phase2.test_settlement_canary` (add `--history` for the offline outcome check). Auditor scratch scripts (probes, mutants, strict no-network runners) are under `build/phase-2/audit-tmp/WP2-A..D/`. Per-WP build and audit records: `build/phase-2/claims/`.
