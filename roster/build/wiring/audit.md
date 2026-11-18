# Wiring Audit: Phases 2-5 connected to the Phase 1 trader

Contract: [dispatch.md](dispatch.md). Process: [../README.md](../README.md). An independent auditor agent, which did not write the code, checked every acceptance criterion below. The compiler then re-ran every test suite. The 14-day paper run in `data/trader/paper14/` kept running throughout. No package wrote to it or signalled its processes (see each package's rules check).

## Summary

| Work package | Final verdict | Fix rounds | Tests (compiler re-run) | Key result |
|---|---|---|---|---|
| **WW-A** Kernel and breakers | PASS | 0 | 149 passed (`test_ww_a` + `trader/tests` + `tests/invariants`) | Flags-off `check()` digest equals the Phase 1 kernel (`ca338f30...cfba`, 3,000 cases). The auditor's 3-seed x 4,000-case differential found 0 differences. Every flag rejects its synthetic trigger. dd7 survives restart. The cap follows `current_cap`. No AI or T5 source can reach HALTED |
| **WW-B** Market data and execution | PASS | 0 | 147 passed (`test_ww_b` + `trader/tests` + `tests/invariants`); `recorder/test_recorder.py` 11 passed | Flags-off market set is identical (golden digests reproduced from pre-edit code; real snapshot 222/318 markets identical). Live flagged crawl: 1,031 rows, 267 touch windows all priced via `touch_ref`. The router `liquidity_once` fuzz found 0 mismatches over 19,737 fills (1,021 with it off) |
| **WW-C** Engines | PASS | 0 | 146 passed (`test_ww_c` + `trader/tests` + `tests/invariants`) | Flags-off ladder is byte-identical (150 seeds x 60 ticks, 25,054 intents). Every new-engine intent passes the sizer invariant. Sports fails closed without keyed odds. The fast maker stays silent while its gate is closed |
| **WW-E** Nightly and advisor processes | PASS | 0 | 29 passed (`test_ww_e` + `tests/invariants`) | `nightly.run` writes all six sections offline on smoke data and never touches the run dir. The three Phase 5 invariants were copied verbatim. `advisor.run` with no vendor key exits 0 and writes nothing |
| **WW-D** Loop integration | PASS | 0 | 14 passed (`test_ww_d`); full suite 725 | Flags off is identical to the frozen Phase 1 loop. Live 20 min flags off: 748/748 intents approved, 0 violations. Live 20 min with 10 paper-safe flags: 781 intents, 593 approved, 188 stress rejections, 0 violations/mismatches/trips. Crash drills with flags on: PASS. Found the touch pricing defect (open) |

**Full suite (compiler re-run, 2026-10-07):** `trader/tests tests/invariants tests/phase2 tests/phase3 tests/phase4 tests/phase5 tests/wiring` gives **725 passed in 56.43s, exit 0** (`audit-tmp/compile/suite.txt`). `tests/wiring` alone: 62 passed. This is more than the 700 to 711 the earlier packages reported because WW-D's 14 tests and other parallel additions landed later.

Caveat on the count: two `tests/phase3/test_universe.py` tests read the newest shared `data/markets` snapshot. They fail while that file is an extended (touch/universe_ext) crawl. The newest snapshot at re-run time was `2026-10-07T101806Z.jsonl`, a flags-off crawl, so 725 passed (see WW-D defect 1).

## Verdict: wiring stage **PASS**, with flags OFF by default

- **With no flags set, the trader is the audited Phase 1 build.** Five independent checks show this: the kernel digest and differential (WW-A), the market-set golden digests and the router fuzz (WW-B), the 150-seed ladder differential (WW-C), the frozen-loop parity test plus an auditor sensitivity test (WW-D), and WW-E adding no trader file. paper14 has no `features.json`, so a restart of it on the new code runs flags-off.
- **There are 0 blocker or major defects. Open minor defects: 15** (WW-A 2, WW-B 2, WW-C 3 including the touch defect WW-D found, WW-E 3, WW-D 5). WW-D's integration later resolved 2 minors from the package audits: WW-A's clock-thread race and WW-B's `liquidity_once` wiring. The one that affects a flag's usefulness is **touch markets are never priced** (`trader/engines/ladder.py:481` passes `ref[asset]` instead of `marketdata.touch_ref(ref, m)`). It fails closed, so `touch` is inert until a one-line WW-C fix.
- No package ran a fix round.

## Feature flags

Enable with `<run dir>/features.json` (a JSON list of names, or `{name: true}`) or `python -m trader.loop --paper ... --enable <flag>` (repeatable). An unknown name raises `ValueError` (file) or `SystemExit` (CLI `choices`). With any flag on, the router's `liquidity_once` is also on. Every enabled module's registry entries and pre-registrations are written at start.

| Flag | What it does | How to enable | Paper-safe? | Evidence it works |
|---|---|---|---|---|
| `live_risk` | Phase 2 stress cap, resolution-risk cap and worst-case positions after `check()`. Reducing rule in REDUCING; taker exits fail closed. The loop feeds `ref`, Up/Down opens each minute and `printed` = oracle gap, pulls risk-increasing orders on REDUCING each second, and keeps held markets until redeemed (`md.held`) | `--enable live_risk` | yes | `test_a2` live_risk tests (stress, resolution, reducing rule, `pull_ids`); B2 held-market test. `wiring_on`: 188 of 781 ladder intents and both btc-speed takers rejected by `stress`, and 26 resting quotes pulled on re-check. Pull-on-REDUCING had nothing to pull (no REDUCING scope) |
| `dd7` | 7-day drawdown breaker; samples persisted to `<run dir>/dd7_samples.json` | `--enable dd7` | yes | `test_a2` (11% loss trips `breaker:drawdown7d`, R) and `test_a3_dd7_survives_restart`. `wiring_on/dd7_samples.json` written; no trip (flat equity) |
| `clock_gate` | SNTP worker every 60 s; the loop thread applies `kernel.clock(offset)`. REDUCING above threshold, HALTED at 1,500 ms, REDUCING on NaN/garbage | `--enable clock_gate` | yes, but holds global REDUCING on this PC (175-380 ms offset) | `test_a2` clock_gate plus auditor probes (NaN, string, inf all give REDUCING; a good clock never lowers HALTED); WW-D unit test. Not part of the D2 smoke |
| `heartbeat` | `health_failures` + `HeartbeatWarden` at the end of every tick; paper send is a counted no-op. DeadMan ping only if `ROSTER_DEADMAN_URL` is set. Also starts the SNTP worker | `--enable heartbeat` | yes | `wiring_on`: 10,763 counted sends in about 11,500 ticks. Withheld on 533 ticks (quiet resting books, `book` rule), 195 (stale feed) and 2 (no clock yet) |
| `settlement` | `SettlementKeeper.step` every 60 s in a worker (public GETs; ntfy only if `ROSTER_NTFY_TOPIC` is set). Merges go to `PaperRouter.merge`; redeems are logged; the oracle-gap set goes to the ladder pull rule and the stress cap | `--enable settlement` | yes | `wiring_on`: keeper stepped each minute, and 16 ended markets in the oracle gap were pulled. No held positions, so the fund-intent → merge path was not exercised live (covered by unit tests and `fund_intents` flooring) |
| `capital_ladder` | Kernel global cap = `growth.capital.current_cap(ledger)`, re-read each minute; the 1.1x refusal follows it | `--enable capital_ladder` | yes ($50 on a fresh ledger) | `test_a4_capital_ladder`: 55 passes, 56 refused at $50; 270 passes, 276 refused at $250. A NaN cap fails closed. `wiring_on`: cap $50, no refusals |
| `touch` | Crawler discovers touch templates (100-day horizon). Marketdata backfills each window's high/low (Binance 1m/1h REST) into `ref[asset]["touch"][cid]`. The ladder routes touch kinds to `touch_value` with Phase 3 guards | `--enable touch` | yes, as a candidate | B3 tests and live crawl (267 windows, `touch_fair` priced all 267 via `touch_ref`); C2 fuzz and touch guards. **But in the loop no touch market is ever priced or quoted** (WW-C/WW-D defect, fails closed). Inert until fixed |
| `universe_ext` | SOL/XRP Gamma tags, strike and Up/Down slugs; Binance SOL/XRP stream with 1440 1m backfill and `sigma_q` (NaN guard); kernel sources for SOL/XRP | `--enable universe_ext` | yes, as candidates | B3 (live `sigma_q` about 0.47); `test_a2` universe_ext (SOL rejected off, approved on, stale feed rejected). `wiring_on`: 614 markets loaded, SOL/XRP subscribed and cleared. Not quoted, by design: entries stay `candidate` until promoted |
| `quote_objective` | Ladder quotes via `wider(optimise(...), quotes(...))`; Phase 1 `quotes()` is the anchor, so price and size can only go down | `--enable quote_objective` | yes, as a candidate | C2 fuzz: 271 intents, all at or below anchor price and size, on grid, invariant OK; about 6 ms per market. `wiring_on`: intent and order rates close to flags-off; no reward pool (rate 0) |
| `negrisk_scan` | `NegRiskScanner` scans crawler negRisk events each minute and writes log rows only; ineligible without a secret and signed confirmation; never an intent | `--enable negrisk_scan` | yes (log-only) | WW-C tests. `wiring_on`: 96 events, 1,824 scans, **0 rows**, because no leg book is subscribed (open issue). Inert today |
| `fast_maker` | `FastMakerEngine` around `growth.fast_updown`, gated by `e6_edges(ledger)` re-read every 60 s; kernel strategy `fast-updown-maker` | `--enable fast_maker` | gated (no intents until a passing E6 row exists) | C4 tests (no ledger, raising ledger, no prereg, failing 1.5 SE row all give []; a passing row opens and re-closes the gate); `test_a2` budget/stale/mode rejections |
| `sports` | `sports-pregame` mode; `md.set_sports` via `odds.map_markets`; ESPN game states and Kalshi every 5 min; `SportsMakerEngine`; game-state cancel signals; kernel strategy `sports-maker` (needs start time; sports GTD fail-closed) | `--enable sports` | partly (keyed SGO odds are not fetched, so it always pulls: fail closed) | C3 (10 pull cases, NaN odds, missing keyed odds all give []); `test_a2` sports rejections; B3 sports mapping test. Not part of the D2 smoke |
| `markout_cusum` | Phase 5 CUSUM markout lock on `series:<mode>:<asset>:<kind>` instead of the count blacklist (always R); state in `<run dir>/markout_cusum.json` | `--enable markout_cusum` | yes | `test_a2` (series lock blocks a sibling cid; count blacklist no longer trips) and `test_a3_markout_cusum_survives_restart`. `wiring_on`: active, no fills to update |
| `liquidity_once` (router kwarg, not a dispatch flag) | Two own orders cannot both fill the same displayed size, so paper matches strict replay | automatic with any flag on | yes | B4 fuzz: 0 mismatches over 19,737 fills with competing own orders; 1,021 with it off |

WW-E adds no flag: `python -m nightly.run` and `python -m advisor.run` are separate processes started by hand. Nothing in `trader/` or `ops/` imports them. The existing `nightly.report` daily line is unchanged.

## What remains operational

Code is wired and audited. These items need running time, data, keys or a follow-up fix before the flags produce evidence:

| Item | What is needed | Blocks |
|---|---|---|
| Phase 1 exit gate: 14-day paper run | Keep `ops\start_paper_14d.bat` running in `data/trader/paper14/` (started 2026-10-07 13:28:55). It runs flags-off | Phase 1 gate |
| Touch pricing fix | One line in `trader/engines/ladder.py:481`: `r = marketdata.touch_ref(ref, m)` for touch kinds, plus an assertion in `test_touch_routed_only_with_flag_and_guarded` | `touch` producing any evidence |
| negRisk leg books | Marketdata must subscribe negRisk leg tokens (WW-B follow-up) | `negrisk_scan` recording rows |
| Sizing to the stress room | Engines sizing to the $2.50 stress cap at $50, or a larger bankroll. Today `live_risk` rejects about 24% of ladder bids and every btc-speed taker | Meaningful `live_risk`-on evidence |
| Clock accuracy | A clock within the gate threshold (e.g. w32time/chrony tuning). At 175-380 ms `clock_gate` holds REDUCING | `clock_gate` in a trading run |
| Keyed sports odds | An SGO sharp snapshot (keyed, paid) or another sharp source | `sports` quoting |
| E6 latency evidence | A passing E6 pre-registered row (4 weeks of recorder `--fast` data) | `fast_maker` quoting |
| CUSUM `h` calibration | `calibrate_h` on real markout/CLV series; `h=4.0` is a labelled placeholder | Trusting CUSUM locks and nightly scans |
| Advisor | A vendor key (GEMINI/GROQ/OPENROUTER) in the advisor's own shell, and `ROSTER_ADVISOR_KEY` distinct from `ROSTER_HUMAN_KEY`. The kernel does not yet accept LLM clearances | Advisor output reaching the trader |
| Heartbeat `book` rule review | Quiet books withheld the heartbeat on 4.6% of ticks; a live venue would cancel everything | `heartbeat` going live |
| Separate markets dir for flagged runs | Flagged runs re-crawl into the shared `data/markets` whenever the latest snapshot lacks their templates (about 254 s, blocking) | Long flagged runs alongside paper14; the Phase 3 snapshot tests |

---

## WW-A: Kernel and breakers

**Final verdict:** PASS (from `audit:WW-A`). Agent sequence: build → audit. Owned files: `trader/kernel.py`, `trader/breakers.py`, `tests/wiring/test_ww_a.py`.

| AC | Status | Evidence | Command |
|---|---|---|---|
| A1 flags off: every existing kernel test passes unchanged and decisions on a recorded intent set are identical | pass | 149 passed; `test_kernel.py` not modified. PHASE1_DIGEST `ca338f30...cfba` reproduced from the pre-WW-A kernel copy (saved 55 s before the first edit, contains every Phase 1 audit fix). Independent differential, 3 new seeds x 4,000 cases on 9 markets: 0 differences in decisions, state, scopes, trips, uncleared, `reduces()`, `exposure()`, `clearance()`, `provenance_checks()`, for flags-off and for the non-check flags. The only difference is direct `gtd()` on sports modes, which `check()` never reaches with default STRATEGIES. Breakers flags-off differential: 20 seeds x 3,000 events, identical | `pytest tests/wiring/test_ww_a.py trader/tests tests/invariants`; `audit-tmp/WW-A/diff_kernel.py`; `probe2.py` |
| A2 each flag's rule rejects its synthetic trigger | pass | One test per flag: live_risk (stress, resolution, reducing rule, taker exit, `pull_ids`), dd7 (11% trips), clock_gate (300 ms REDUCING, NaN REDUCING, 1,500 ms HALTED), negrisk/fast/sports (unknown when off; budget, stale feed, start, source, mode rejections when on), universe_ext (SOL off/on, stale feed, STRATEGIES not mutated), markout_cusum (series lock). Probes: NaN/string/None/inf clock inputs give REDUCING; a good clock does not lower HALTED | `test_a2_*`; `probe2.py` |
| A3 the dd7 state survives a restart | pass | Atomic save (tmp + `os.replace`) each minute and on trip. 100 → 97, restart, 89 trips; the control without the file does not; no re-trip after a second restart. Global REDUCING is restored by the loop's startup trip replay (`loop.py:197-202`). markout_cusum also round-trips | `test_a3_dd7_survives_restart`, `test_a3_markout_cusum_survives_restart` |
| A4 the capital cap follows `current_cap`, and the 1.1x refusal follows it | pass | Fresh $50: 55 pass, 56 refused. After a live $250 row and one minute: 270 pass, 276 refused. Flag off keeps $50; no ledger raises; a missing live row gives $50; a forged NaN cap rejects | `test_a4_capital_ladder`; `probe2.py` |
| A5 no AI or T5 source can reach HALTED | pass | `trip()` unchanged. New trip sites: dd7 R, markout_cusum hard-coded R, clock gate source `kernel` (T0). Probe with every flag on: 02-cusum, 34-drift, advisor, T5:x, llm, learning tripping HALTED on any scope end at REDUCING. No kernel input is AI-influenced; size and price are never changed | `test_a5_no_ai_halt_with_every_flag`; `tests/invariants`; `probe2.py` |

**Open defects at final audit** (none are blockers or majors):

- **minor**: The sports GTD fail-closed change in `gtd()` (`kernel.py:356-359`) is not behind a flag. It is unreachable with default STRATEGIES (0 decision differences), but a custom strategy table trading sports modes now rejects makers that Phase 1 approved. It is stricter only, and it closes a Phase 1 wiring-later item. *Fix hint:* accept it as an intentional tightening, or gate it on `sports`.
- **minor**: Phase 3 wiring items are only partly done; all fail closed and are disclosed. XRP is not in the stress cap (`risk.py` is read-only), so XRP positions count as a full loss. negRisk `worst_case_leg_loss_usd` is not counted, and completion intents are refused in REDUCING. `reducing_rule` always gets `human_token_ok=False`. No action needed while `negrisk_scan` is log-only.
- *Resolved by WW-D:* the clock-thread race on `trip()` (WW-D calls `kernel.clock()` in the loop thread via `_worker`'s `apply`, `loop.py:820-822`). The pre-clear from module STRATEGIES is also fixed: the loop uses `kernel.strategies` (`loop.py:642`).
- Notes: a corrupt `dd7_samples.json` or `markout_cusum.json` makes Breakers raise at startup (loud, no data loss). `trader/breakers.py` changed to CRLF line endings (cosmetic).

**Rules check:** Flags default OFF; `trader/loop.py` in the flags-off path still builds the kernel and Breakers with no flags. `trader.live.risk`, `trader.live.clock`, `growth.capital` and `learning.cusum` are imported lazily, only when a flag is on. The all-flags import closure has no send path, `kernel.clock` makes no network call, and `test_no_order_send_path` passes. Nothing under paper14 was touched (listings show only the running process's own appends) and no process was signalled. Only the 3 owned files were changed. No secrets.

---

## WW-B: Market data and execution

**Final verdict:** PASS (from `audit:WW-B`). Agent sequence: build → audit. Owned files: `trader/marketdata.py`, `trader/router.py`, `recorder/crawler.py`, `tests/wiring/test_ww_b.py`.

| AC | Status | Evidence | Command |
|---|---|---|---|
| B1 flags off: market set and books identical (fixture snapshot) | pass | The test's own state builder, run with the pre-WW-B modules swapped in, gives `d4d3794a...212ea` = GOLD_B1, so the golden value came from unedited code; the new code matches. Real snapshot 074751Z (read-only, crawling refused): 222 markets (TARGET_MODES) and 318 (all modes), identical | `audit-tmp/WW-B/gold_check.py O orig\|new`; `real_snap.py O` |
| B2 a held market past end+6h stays until its position is zero | pass | `held=None` drops at end+6h; held keeps it, also after it leaves the snapshot, and drops it at position 0. `Trader.positions` fits the callable contract; a raising `held()` skips that reload (fails safe) | `test_b2_held_market_past_end_stays_until_position_is_zero` |
| B3 touch and SOL/XRP rows map correctly with their flags on | pass | Asset, kind, strike, event_group, source_id and window_start checked; each template appears only with its flag. Live smoke: 1,031 rows, all 4 assets, 0 without source_id, 267 touch windows all priced; SOL/XRP `sigma_q` about 0.47 | `test_b3_*`; `data/trader/wiring_B/smoke.json` |
| B4 router: two own takers cannot both fill the same displayed size; existing execution tests pass | pass | Phase-5-style parity fuzz: 3,000 scenarios / 15,489 fills and 3,000 / 19,737 fills (competing own orders) with 0 mismatches when on; 1,021 mismatches when off (the fuzz is sensitive). Flag-off router vs original: 2,000 op sequences, 0 differences. `trader/tests` and `tests/phase5` pass | `fuzz_on_a.py`, `fuzz_on_b.py`, `fuzz_off_b.py`, `router_fuzz.py O` |
| B5 crawler changes additive: flags off gives the same rows | pass | B5 digest `83798ff7...706a7` identical from old and new crawler (= GOLD_B5). `classify()` returns the old mode and horizon with no flags. `recorder/test_recorder.py` passes | `gold_check.py`; `pytest recorder/test_recorder.py` |
| Hard rules (flags off, paper only, paper14, rounding, owned files) | pass | All defaults off; no new hosts (public Binance klines only); sports helpers are pure; the `LIVE_ENV` refusal is unchanged. paper14 was stat-only; output went to `data/trader/wiring_B/`. `round_size` floors. Only the 4 owned files changed | code read; `find -newermt` |

**Open defects at final audit** (none are blockers or majors):

- **minor**: With `touch` or `universe_ext` on, `load_markets` re-crawls into the shared `data/markets/` whenever the latest snapshot lacks a flagged template. The recorder's and paper14's hourly flags-off crawls cause this. It takes about 254 s live, blocks MarketData start-up and may repeat on every 5-minute reload. A flags-off reader's market set is unaffected. *Fix hint:* give flagged runs their own `markets_dir`, and add a "crawled with" marker.
- **minor**: `recorder/crawler.py` changed from LF to CRLF line endings, so every line diffs. Behaviour unchanged (B5 verified).
- *Resolved by WW-D:* `liquidity_once` is now on whenever any flag is on (`loop.py:187-189`).
- Notes: `loop.MD._subscribe` may drop untraded touch/SOL/XRP/sports markets. Touch windows are never pruned for dropped markets (small memory cost).

**Rules check:** Flags-off equivalence verified on the original code (B1/B5 digests, real snapshot, router fuzz). No new hosts or keyed calls; no LLM. paper14 untouched (it started 13:28:54, before the edits); shared `data/markets` latest was unchanged at audit time. No process signalled. Sizes floor. Only the 4 owned files changed.

---

## WW-C: Engines

**Final verdict:** PASS (from `audit:WW-C`). Agent sequence: build → audit. Owned files: `trader/engines/ladder.py`, `trader/engines/sports_maker.py` (new), `trader/engines/fast_maker.py` (new), `tests/wiring/test_ww_c.py`.

| AC | Status | Evidence | Command |
|---|---|---|---|
| C1 flags off: ladder intents on a recorded tick set identical | pass | Baseline: builder's copy after the Phase 1 follow-up fixes (sha256 `a204f35c`, contains `fit_to_caps`). Independent differential: 150 seeds x 60 ticks with strikes, Up/Down, touch, sports and SOL markets, faults, fills and rewards. "intents+records identical; total intents 25054", for `LadderEngine()` and with non-ladder flags. `loop.py` flags-off path still builds `LadderEngine()` | `diff`; `audit-tmp/WW-C/c1_diff.py`; `test_c1_flags_off_ladder_identical_to_audited_build` |
| C2 each new engine meets the Engine protocol and its invariants (sizer sign/magnitude, never rounds up) | pass | All three engines match `contracts.Engine`. Every quote goes through `quotes()` (floors) or `wider()` (min price and min size against the Phase 1 anchor; `reduces` is AND-ed). Fuzz of 400 markets: 271 intents, all `invariant_ok`, on grid, size within [min_size, 10], at or below anchor. Sports 300 random cases; fast maker within MAX_SHARES | `test_c2_*`; `audit-tmp/WW-C/probe.py` |
| C3 sports engine returns no quotes when any pull reason holds or keyed odds are missing | pass | `_quote` runs only with no reasons; no SGO snapshot gives no fair value, so it pulls. All 10 pull cases, pre-start and unmapped cid give []. NaN odds give [] ("quote gate: no fair value"). Non-pull cautions leave output unchanged; AI can only remove quotes | `test_c3_sports_quotes_only_when_no_pull_and_keyed_odds_present`; inline probe |
| C4 the fast maker returns nothing while its gate is closed | pass | `gate()` sets edges from `e6_edges`, or {} on no ledger or an error. No ledger, raising ledger, no prereg, no result, failing 1.5 SE row all give []; a passing row opens and re-closes after `refresh_ms` | `test_c4_*` |

**Open defects at final audit** (none are blockers or majors):

- **minor** (found by WW-D, confirmed by its auditor): **touch markets are never priced in the loop.** `LadderEngine.on_tick` (`ladder.py:481`) passes `ref[asset]` to `touch_value`, which reads `r["high"]`/`r["low"]`. WW-B stores them in `ref[asset]["touch"][cid]`, so `touch_value` returns err. It fails closed; the `touch` flag is inert. *Fix hint:* `r = marketdata.touch_ref(ref, m)` for touch kinds. Still unfixed at compile time (`ladder.py` last modified 13:43).
- **minor**: a touch market whose barrier is already crossed (`touched=True`) still gets an ordinary bid on the dead outcome (probe: `tN BUY 0.27 x 10`, fair 0). The sizer invariant holds, but any fill is a certain loss. *Fix hint:* skip quoting when `fv.get("touched")`, or drop the zero-fair bid unless it reduces exposure.
- **minor**: `SportsMakerEngine` ignores CautionSignal `shrink` (only `pull` acts). Conservative. *Fix hint:* scale size by the smallest `shrink_factor` (≤1), floored, or document it as unwired.
- Notes: the `soccer-maker` vs `sports-maker` prereg naming needs aligning. Quote-objective sigma is a model-implied proxy. Touch quotes only at tau ≤ 24 h. The fast maker's first window after the gate opens has no recorded open and will not quote.

**Rules check:** Flags default off; byte-identical flags-off output. The engines and every module they import make no network or LLM call (the `common.py` urllib import is unused on these paths; tests block `socket.connect`). NegRiskScanner returns log records only. Cautions only add pull reasons. Nothing touches kernel or breaker state. Sizes floor. Only the owned files changed; no paper14 access; no process signalled. No secrets (`s3cret` is a fixture).

---

## WW-E: Nightly and advisor processes

**Final verdict:** PASS (from `audit:WW-E`). Agent sequence: build → audit. Owned files: `nightly/run.py` (new), `advisor/run.py` (new), `tests/invariants/test_learning_invariants.py` (addition), `tests/wiring/test_ww_e.py`.

| AC | Status | Evidence | Command |
|---|---|---|---|
| E1 the nightly run produces each new section (canary, analyst, outcome-blind postmortems, CUSUM scans, Loop A candidates-only, replay with trials logged) on smoke data without network calls | pass | 29 passed. `test_e1_nightly_sections_offline` (sockets blocked) checks all six headings, no failed section, the run dir byte-identical (sidecars excluded). Real `smoke_v2` run: exit 0, all sections under the out-dir only, smoke_v2 sha256 unchanged. Offline replay: 38,760 ticks, 5.5M look-ahead checks, trial `t000001` logged. Failed replays are logged before re-raising | `pytest tests/wiring/test_ww_e.py tests/invariants`; `python -m nightly.run --dir data/trader/smoke_v2 --out-dir ...`; `audit-tmp/WW-E/offline_replay.py` |
| E2 nothing in nightly can promote a registry version or reach HALTED; three Phase 5 invariants copied | pass | `test_a4_no_promote_anywhere`, `test_a5_outcome_blind`, `test_a10_no_halt` textually identical to Phase 5. Source scan for promote/register/trip/HALTED/Ledger/TradingState. Registry rows and ledger row count unchanged after `nightly.build`. The only RiskKernel is an in-memory replay kernel. Nothing in `trader/` or `ops/` imports `nightly.run` or `advisor.run` | code read; `test_e2_*` |
| E3 `advisor/run.py` with no keys exits cleanly, makes no network call, writes no clearance | pass | Prints "no vendor key set ... nothing started, nothing written (fail closed)", exit 0; `data/advisor` listing identical. Test with sockets blocked: `LLMGateway` never constructed, no output dir. The board signs only with `ROSTER_ADVISOR_KEY` ≠ `ROSTER_HUMAN_KEY` into `llm_clearances.db`; sentinel signals are pull with shrink 0 | `python -m advisor.run --once`; `test_e3_*` |
| Hard rules | pass | No trader file edited; no flag added. Offline nightly (`fetch=None`, `load_ref`). No sizes produced. No secrets | `find -newer`; secret scan |

**Open defects at final audit** (none are blockers or majors):

- **minor**: Process lapse, disclosed by the builder: a glob over `data/trader/*/trader.db` opened `paper14/trader.db` read-only for one `SELECT COUNT(*)`. No write is evident (`trader.db-shm` mtime still 13:28:56). It breaks the letter of the "never touch paper14" rule. *Fix hint:* exclude paper14 explicitly in survey globs.
- **minor**: canary clustering maps cid → event group from fills only, so unfilled maker orders get cluster = cid (smoke_v2: 11 "clusters", 10 bare cids). This inflates the independent-cluster count and narrows the canary PI once a live journal exists. *Fix hint:* map from `universe_checkpoint.cluster` first.
- **minor**: `build_rows` uses the first fill's price as entry for SELL-only positions instead of the sell VWAP. Latent (ladder fills are BUYs). *Fix hint:* track proceeds/sold.
- Notes: CUSUM `h` is a 4.0 placeholder. The kernel does not accept LLM clearances. Replay passes no clearances, so on real data every intent is "not cleared". The advisor's news offset is in memory, so CautionSignals can repeat after a restart.

**Rules check:** Standalone processes; flags-off trader unchanged. No order, authenticated or vendor call reachable without a key. Owned files only (mtime scan). The auditor opened nothing under paper14 and signalled no process. CUSUM output is report-only. No secrets.

---

## WW-D: Loop integration

**Final verdict:** PASS (from `audit:WW-D`). Agent sequence: build (resumed from partial files) → audit. Owned files: `trader/loop.py`, `trader/features.py` (new), `tests/wiring/test_ww_d.py`, `reports/wiring_smoke.md`, `data/trader/wiring_{D,off,on,drills}/`.

| AC | Status | Evidence | Command |
|---|---|---|---|
| D1 flags off: 20-min paper smoke in `wiring_off` matches Phase 1 (counts in range, zero violations) | pass | The diff vs the frozen Phase 1 loop (contains all four Phase 1 follow-up fixes) is purely additive and gated on F. The parity test (ledger rows, journal, counts identical) passes; the auditor's sensitivity test shows flags-off = old and live_risk ≠ old. Live run `1791363562252-19488`: 20.0 min, 748 intents, 748 approved, 748 orders, 0 violations, 0 trips, 0 of 6 reconciles with mismatches; 37.4 intents/min, inside the Phase 1 final-code drills' 29.3-57.3/min | `diff data/trader/wiring_D/loop_phase1_before.py trader/loop.py`; `test_d1_*`; `audit-tmp/WW-D/test_d1_sensitivity.py`; read-only sqlite (`ledgers.txt`) |
| D2 all 10 paper-safe flags on: 20-min smoke in `wiring_on`, no crash, zero violations, report per flag | pass | Run `1791366707170-11888` with [capital_ladder, dd7, heartbeat, live_risk, markout_cusum, negrisk_scan, quote_objective, settlement, touch, universe_ext]: clean end, 0 violations, 0 mismatches, 0 open orders, 0 trips, 0 of 18 reconciles with mismatches. Ladder 781 / 593 approved / 188 stress; btc-speed 2 stress; heartbeat sent 10,763; negrisk no_books 1,824. `reports/wiring_smoke.md` has a section per flag. Two earlier keyless runs in the folder are disclosed and excluded | read-only sqlite of `wiring_on/trader.db`; `reports/wiring_smoke.md` |
| D3 crash drills pass with all paper-safe flags on, own folder | pass | `wiring_drills/drills.md`: PASS. 2x kill -9 random, 2x kill -9 mid-batch, 1 clean stop, each next startup 0 mismatches. 6 runs, each with the 10 features, 0 violations, 0 trips, 0 of 14 reconciles with mismatches. Runs started after the final `loop.py` save | `data/trader/wiring_drills/drills.md`; read-only sqlite |
| D4 full suite passes | pass | 725 passed (auditor), and 725 passed in the compiler re-run. It depends on the newest shared snapshot being flags-off (defect 1) | `pytest trader/tests tests/invariants tests/phase2 tests/phase3 tests/phase4 tests/phase5 tests/wiring -q` |
| D5 nothing under paper14 touched; no other process signalled | pass | paper14 PIDs 17464 and 3720 (started 13:28:55) alive in `d5_before` (08:36Z), `d5_after` (10:15Z) and at audit; `advice.db` and `keys.jsonl` mtimes unchanged. The only new paper14 file, `outcomes.json` (14:07:22), came from the user's ops daily-report automation. No WW-D file references paper14. paper14's flags-off market set is unaffected by extended snapshots (222 markets either way) | `Get-CimInstance Win32_Process`; `d5_{before,after}.txt`; `audit-tmp/WW-D/snapshot_effect.txt` |
| Cross-cutting: flags default OFF; unknown flag raises | pass | `load()` returns an empty frozenset without `features.json`; dict values count only when exactly True; unknown names raise; the CLI uses `choices=FLAGS` | `test_features_default_off_file_and_cli` |
| Cross-cutting: no path to a real order, authenticated endpoint or LLM vendor | pass | With all 13 flags' modules imported: no clob, live.router, advisor, anthropic, openai or web3 module. Heartbeat send is a no-op; DeadMan/ntfy are network-free without env vars; merges go to `PaperRouter.merge`; `LiveTradingForbidden` on live env vars | `audit-tmp/WW-D/imports.txt` |
| Cross-cutting: AI/T5 cannot raise edge/size or reach HALTED; sizes never round up | pass | The loop has no advisor/T5 input. Keeper trips are capped at REDUCING by `kernel.trip`; the oracle gap only pulls. `fund_intents` floors via `round_size`. `check_intent` covers sports-maker | code read |

**Open defects at final audit** (none are blockers or majors):

- **minor**: Work outside owned paths. The builder ran one flags-off crawl into shared `data/markets/2026-10-07T101806Z.jsonl` (and `changes.jsonl`) to turn two `tests/phase3/test_universe.py` tests green. Those tests fail whenever the newest shared snapshot is an extended crawl, so D4 depends on snapshot state. *Fix hint:* phase3 tests filter to flags-off slugs or skip; flagged runs crawl into a run-local `markets_dir`.
- **minor**: The D1 parity test loads its frozen baseline from `data/trader/wiring_D/loop_phase1_before.py` and **skips** if it is missing, so cleaning `data/` silently drops the main flags-off guarantee. *Fix hint:* move the baseline to `tests/wiring/fixtures/`, or fail instead of skip.
- **minor**: With `heartbeat` on and `ROSTER_DEADMAN_URL` set, `DeadMan.maybe_ping` does a blocking 5 s urllib GET inside `tick()` once a minute. Unreachable by default. *Fix hint:* `asyncio.to_thread`.
- **minor**: `check_intent`'s runtime sizer invariant does not cover `fast-updown-maker` intents. They cannot occur while the gate is closed. *Fix hint:* add it before the gate can open.
- **minor**: `reports/wiring_smoke.md` D5 says paper14 changed "only through its own appends", but `outcomes.json` came from the ops daily-report task. Wording only.
- The touch pricing defect WW-D found is listed under WW-C (its file).
- Builder's open issues (not code defects of WW-D): negRisk legs have no books; the stress cap rejects most risk at $50; slow exit (2 min 37 s) with touch/universe_ext while a crawl thread is in flight; the heartbeat `book` rule on quiet books (4.6% of ticks).

**Rules check:** All 13 flags are OFF by default; flags-off is byte-identical to the audited Phase 1 loop (parity test, sensitivity test, code diff). No authenticated, live-router or LLM module is reachable. paper14 untouched; both PIDs alive with their original start times. No foreign process signalled. Phase 2-5 modules and other packages' files were not edited (mtimes predate WW-D). One exception to owned paths: a shared `data/markets` snapshot (minor above). No secrets. The report ends with "How to reproduce".

---

## Compiler notes

- **Rules check (compiler):** I modified no code. I wrote only this file and scratch under `build/wiring/audit-tmp/compile/` (`suite.txt`, `per_wp.txt`). I read nothing under `data/trader/paper14/` and signalled no process. pytest ran with `PYTHONDONTWRITEBYTECODE=1 -p no:cacheprovider`.
- **Spot checks of the integration claims:** `loop.py:187-189` passes `liquidity_once=bool(F)`; `loop.py:642` uses `kernel.strategies`; `loop.py:820-822` applies `kernel.clock()` in the loop thread. These close WW-A's clock-race defect and pre-clear note, and WW-B's `liquidity_once` defect. `ladder.py:481` still passes `r` (= `ref[asset]`) to `touch_value`, so the touch defect is open.
- **Per-package scopes re-run by the compiler:** A 149, B 147, C 146, E 29, D 14, `tests/wiring` 62, `recorder/test_recorder.py` 11, all passed.

## How to reproduce

From `C:\Users\DELL\Downloads\saugan_pr\market_updated\roster`:

```
set PYTHONDONTWRITEBYTECODE=1
.venv\Scripts\python.exe -m pytest -p no:cacheprovider trader/tests tests/invariants tests/phase2 tests/phase3 tests/phase4 tests/phase5 tests/wiring -q
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/wiring/test_ww_a.py trader/tests tests/invariants -q
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/wiring/test_ww_b.py trader/tests tests/invariants -q
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/wiring/test_ww_c.py trader/tests tests/invariants -q
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/wiring/test_ww_e.py tests/invariants -q
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/wiring/test_ww_d.py -q
.venv\Scripts\python.exe -m pytest -p no:cacheprovider recorder/test_recorder.py -q
```

The auditors' independent checks are in `build\wiring\audit-tmp\WW-{A,B,C,D,E}\`. Each package section above names its scripts. The WW-A and WW-B differentials take the pre-edit module copies in the session scratchpad as their argument. The live smokes and drills are reproduced with the commands at the end of `reports/wiring_smoke.md`, each in its own `data/trader/wiring_*` folder, never `paper14`.

---

## Orchestrator follow-up (2026-10-07)

**Touch pricing fixed.** `trader/engines/ladder.py` now merges the per-market window (`ref[asset]["touch"][cid]`, the shape `marketdata` produces) before calling `touch_value`; before, every touch market returned `err` and the `touch` flag did nothing. Regression test `test_touch_uses_the_per_market_window_shape_marketdata_produces` (the old test used a flat shape, which is why it slipped through). Full suite: 726 passed.
