# Phase 4 Audit: Sports and AI audits

Contract: [dispatch.md](dispatch.md). Process: [../README.md](../README.md). An independent auditor agent that did not write the code checked every acceptance criterion below. The audit compiler then re-ran every test suite.

**Scope (the user's decision): build now, wire later.** Phase 4's entry gate requires the Phase 3 gates to be met, and it is not met. Every buildable Phase 4 piece was built as a standalone module against the shared contracts. Nothing here changes the running Phase 1 paper loop.

## Summary

| Work package | Code audit | Fix rounds | Tests (compiler re-run) | Result |
|---|---|---|---|---|
| **WP4-A** Sports data: odds collectors and game state (4.1, 4.2; roles 11, 12) | PASS (ops pending) | 0 | 23 passed | Kalshi, ESPN and Polymarket sports WS smoke run: 144 of 144 crawler moneyline rows mapped to 48 events, 0 unmapped. Quota projection peaks at 30.5% of the SportsGameOdds quota, so all 5 leagues are enabled. Early-start drill cancels only that game's orders. The `sports` feed age now fails closed |
| **WP4-B** Sports fair value and sports pulls (4.3, 4.4, 4.10 pre-registration; roles 19, 20) | PASS (ops pending) | 0 | 12 passed | The devig method chosen on Pinnacle opening odds matches Phase 0's closing-odds choice in all 5 leagues (D1 multiplicative, E0 odds_ratio, F1 power, I1 power, SP1 odds_ratio). Paramset `sports-devig` ee7d3af0e9a5 is a candidate. Pull drills pass and the soccer pre-registration is ready |
| **WP4-C** LLM gateway and clearance board (4.6, 4.8; gateway, roles 27, 28) | PASS (ops pending) | 0 | 47 passed | The gateway fails closed in every tested case and refuses non-public prompts before sending. With quota exhausted, nothing is cleared. The real no-key run on 16 snapshot keys sent 0 requests and cleared nothing. Board records load in the kernel and clearance_cli |
| **WP4-D** News sentinel, calibration blend, Loop A (4.5, 4.7, 4.9; roles 25, 21, 23) | PASS (ops pending) | 0 | 20 passed | News leads to a pull, and the pull resumes only on a sharp price newer than the news. The blend fit is unbiased on synthetic data. Candidate c (bootstrap 20th percentile) is 0.4748 against a point estimate of 0.5071. The cluster-robust refit gate rejects gains that are significant only per row. The anchor rule held over 10,000 refit chains |

All 102 Phase 4 tests pass (`tests/phase4`: 23 + 12 + 47 + 20). No test failed. The `common.py` self-check passes. The shared contracts are unchanged: sha256 prefixes are trader/contracts.py 1c0e3f299907, advisor/contracts.py cd19a7dc8960 and common.py e1fea02292a2, the same values the WP audits recorded. No auditor found a blocker or major defect. There are 11 minor defects, listed under each work package.

## Phase 4 exit gate: **NOT MET**

The build plan's gate is **soccer passes its own pre-registered test** (task 4.10). That test cannot run yet. The code is complete, and what remains is operational:

| Gate item / task check | Status |
|---|---|
| 4.1 Quota projection per league in the daily report | **Code done**: `odds.project_quota()` and `reports/phase4_quota.md`. Putting it in Phase 1's `nightly/report.py` is wiring |
| 4.2 Drill: simulated early start cancels orders | **PASS** (A8, fake router) |
| 4.3 Universe checkpoints written at snapshot times | **PASS** on synthetic data (B7, real `Ledger` accepted the rows). Real snapshots need SGO keys |
| 4.4 Pull drills pass | **PASS** (B8) |
| 4.5 c switch as a registry promotion with your token | **[ops]**: code ready (`c_candidate`, `c_in_force`). Needs 100 resolved clusters and your token |
| 4.6 Exhausted quota blocks new clearances (test) | **PASS** (C9) |
| 4.7 Drill: news, then pull, then resume only after a fresh observation | **PASS** (D3) |
| 4.8 Agreement report on the backlog | **[ops]**: CLI tested (C11). The real report so far is a no-key run that failed closed. It needs vendor keys, your clearances and the real backlog |
| 4.9 Anchor-rule test: a chain of refits cannot raise edge past the anchor | **PASS** (D8) |
| 4.10 Soccer through Loop B, pre-registered test passed | **[ops] pending**: needs replay, shadow (at least 100 match clusters), canary and your token |

### What remains [ops] before the gate can be met

1. **Upstream gates.** Phase 0 (both go/no-go tests failed, no 7-day recording yet), Phase 1, Phase 2 and Phase 3 gates come first. Phase 4 entry needs the Phase 3 gates for anything in use.
2. **Sharp odds keys (A11, B11).** `SPORTSGAMEODDS_API_KEY` and `ODDS_API_IO_KEY`, set in env only. Then check the live response shapes against the MOCK fixtures, which were built from the vendor docs. Capture Polymarket WS frames on a soccer match day; the league codes epl/lal/bun/sea/fl1 have not been seen live.
3. **Advisor process (C13).** A separate advisor OS user with no access to the trading key or journal. Free-tier keys `GEMINI_API_KEY`, `GROQ_API_KEY` and `OPENROUTER_API_KEY`, and `ROSTER_ADVISOR_KEY` (never the human key). Before that, confirm `gateway.VENDORS` models and caps against current vendor docs and update `board.QUALIFIED` to match. Then run the agreement report on the kernel's real `uncleared.jsonl` against your clearances, and switch only once they agree.
4. **News sources (D11).** Role 13's news collector (RSS, league injury reports) is not built in Phase 4. The sentinel has no live input until it is.
5. **Calendar time and your token (D11, B11, 4.10).** 100 resolved clusters for the c switch, made as a registry promotion with your token. Then soccer goes through Loop B: replay, then shadow with at least 100 match clusters, then canary at its own small cap, then your token. Source weighting by past accuracy needs ledger history.
6. **Before Loop B replay, fix two minor defects.** WP4-B treats future-dated snapshots as fresh, which is look-ahead in replay. WP4-C's role-27 silence check misses the "not stated in rules" sentinel. Both are listed below.

## Wiring later

Collected from each WP's wiring notes and its auditor's cautions. All of it is later integration work. The parts that change Phase 1 files (kernel, marketdata, nightly report) need your token.

**WP4-A (odds and game state)**
- The recorder process runs `sports.odds.kalshi_snapshots()`, `sgo_snapshots()` and `oddsapi_snapshots()`. All three share one `sports.odds.Quota(data/sports/quota.json)`, and news refreshes pass `priority="news"`. Pass the Quota explicitly: the keyed collectors default to `quota=None`, which means no quota check (minor defect).
- For each mapped event the loop calls `odds.due(start_ms, lineup_ms, done_labels, now)` and records the returned labels. Call `sgo_snapshots` once per due label at most, because each call charges `limit` units.
- The loop runs `gamestate.poll_espn(league)` every 30 to 60 s near kickoff, and runs `gamestate.listen_ws(seconds, on_state)` in a reconnect loop (it raises on disconnect). OddsSnapshot and GameState dicts are appended under `data/sports/`.
- `trader/marketdata.py` builds sports MarketInfo from `odds.map_markets(crawler_rows, espn_states + kalshi_snapshots)`. `MarketMap.event_key` is the event group / cluster id.
- On every GameState update the loop calls `sig = gamestate.cancel_signal(gs, maps, now)` and, if a signal comes back, `gamestate.cancel_game(sig, router, now)`. Auditor caution: the stale trigger fires only if the loop also re-checks the last stored state per mapped event on a timer.
- `marketdata.feed_age_ms` merges `gamestate.feed_age_ms(now)`. If the WS is not run, pass `feeds=("espn",)`; otherwise `sports` never appears and the kernel treats the feed as stale.
- `nightly/report.py` calls `odds.project_quota()` and `odds.Quota().used(source)` for the quota section.
- football-data `closing_odds()` is for CLV only, never for quoting.
- Auditor caution: `http_get` follows redirects, so a cross-origin redirect would forward the SGO `X-Api-Key` header. Use `follow_redirects=False` for keyed calls.
- One collector process owns `quota.json`, because there is no inter-process lock.

**WP4-B (fair value and pulls)**, per tick and per mapped market in the soccer maker Engine:
1. `f = fair.fair(mm, sgo_snapshots, devig_params, now_ms, sigma_params)`
2. `cs = fair.continuous_sources(mm, odds_api_kalshi_betfair_snapshots, devig_params, now_ms, sigma_params['continuous_max_age_ms'])`
3. `gate = fair.quote_allowed(f['fair'], f['sigma'], cs, now_ms, sigma_params['continuous_max_age_ms'])`
4. `reasons = pulls.pull_reasons(now_ms, mm, game_state, lineup_ms, f['obs_ms'], cautions, feed_age_ms, gate)`
5. If `reasons` is non-empty, return no quotes. Otherwise pass `f['fair']` and `f['sigma']` to Phase 1's quote engine (role 20) and sizer (role 23).
6. Set `Intent.expiry_ms` to at most `pulls.maker_expiry(mm['start_ms'], market.end_ms)`.

- `feed_age_ms` keys: `polymarket` (Phase 1 book feed) and `sports` (WP4-A). `cautions` come from WP4-D's sentinel in arrival order. `lineup_ms` comes from WP4-A game state or from news.
- At each label from `odds.due()`, the loop calls `fair.checkpoint_rows(maps, sgo, continuous, books_by_token, label, ts_ms, devig_params)` and writes each row with `Ledger.record('forecasts', row, row['ts_ms'])`.
- Registry (WP1-F): register `sports-devig` (the JSON is in `reports/phase4_devig.md`, or rebuild it with `fair.choose_methods`) and `fair.SIGMA`, and preregister `fair.SOCCER_PREREG`.
- The σ defaults (s0 0.015, k 2e-5 per hour, max_age 22 h, continuous sources fresh for 10 min) and the pull bounds are starting values. Loop B should refit them from checkpoint rows.

**WP4-C (gateway and board)**
- The advisor process runs as its own OS user, builds `LLMGateway()` (db `data/advisor/gateway.db`) and runs `python -m advisor.board agree --backlog data/trader/uncleared.jsonl` each time the kernel dumps that file, and on every rules or clarification change (a new rules hash is a new key). Per key, `board.clear_template(gw, key, question, rules_text, now_ms)` also works.
- Kernel acceptance is a Phase 1 change that needs your token. Either RiskKernel also loads `data/advisor/llm_clearances.db` via `load_advice` and verifies under `ROSTER_ADVISOR_KEY` (slow-lane templates only), or you co-sign `data/advisor/cleared_keys.jsonl` with `python -m tools.clearance_cli sign --keys ... --signer NAME`.
- Role 36 raises an AI-quota alarm when any vendor shows 0 in `quota_left()`.
- WP4-D's sentinel takes this `LLMGateway` as its `Gateway`. Its prompts must avoid 64-hex strings and account words, or they are refused (fail closed). Rules texts that mention "balance" can never be board-cleared and need your clearance.
- One advisor process only, because quota has no inter-process lock.

**WP4-D (sentinel and Loop A)**
- Sentinel: `Sentinel(gateway, market_maps)` with WP4-C's gateway and WP4-A's MarketMaps (an optional `players` list per map). For each role 13 news item call `on_news(item)`, which returns (CautionSignal, refresh request) pairs. Write each CautionSignal where the trader reads T3 signals, so it feeds WP4-B's `pull_reasons`. Send `{event_key, priority: news}` to WP4-A for a fresh snapshot from the news reserve. On each sharp snapshot call `on_sharp_observation(event_key, obs_ms)` and publish any non-None resume signal.
- Pull state is in memory only. On an advisor restart, re-read the last CautionSignals. Rebuild the Sentinel when the market map changes. Team aliases (for example "Man Utd") need an alias list.
- Loop A, nightly: read resolved checkpoint rows (y, m, f, cluster_id, resolved_ms). Split them with `walk_forward(rows, t_split)`, then call `refit_step(anchor_fn, current_fn, candidate_fn, test)`. An accepted candidate is registered through WP1-F. `c_candidate(rows)` goes to `Ledger.register('kelly-c', ...)`, and making it live needs `Ledger.promote` with your token.
- Role 23 takes c from `c_in_force(ledger.registry_live('kelly-c'))`; pass None on a KeyError to get 0.3. At use time the trader applies `anchored_p(p_anchor, p_current, mid_ex_own)` and role 20 applies `anchored_spread`. Guard against non-finite inputs, because `anchored_p` fails open on NaN (minor defect).

---

## WP4-A: Sports data: odds collectors and game state (4.1, 4.2; roles 11, 12)

**Final verdict:** PASS_WITH_OPERATIONAL_PENDING (from `audit:WP4-A`). Agent sequence: build (resumed) → audit.

| AC | Status | Evidence | Command |
|---|---|---|---|
| A1 Kalshi probs = hand-computed mids; empty side gives no snapshot | pass | Fixture best bids give H=(0.72+1-0.27)/2=0.725, the value the test checks. The 3 fixture books are byte-equal to the raw capture (149 lines). Re-parsing the raw data offline gives 48 snapshots, with prob sums from 0.96 to 1.015. An empty NO side gives None. Legacy cents books are covered | `pytest tests/phase4/test_sports_data.py (test_kalshi_*); audit-tmp/WP4-A/probe_kalshi.py` |
| A2 football-data closing PSC→BFEC→AvgC; close==open counts as missing; 2026/27 never PSC | pass | Synthetic rows give [PSC, BFEC, PSC, AvgC], and BST converts correctly. Real 2026/27: 250 rows, PSCH non-null 0, books {BFEC 247, AvgC 3}. 2024/25 E0 returns PSC more than 300 times | `pytest (test_closing_*); audit-tmp/WP4-A/probe_edges.py` |
| A3 SGO/odds-api fixtures parse; no key gives an error and zero fetches; fake key never in raw lines | pass | Fixtures are labelled MOCK. `_keyed` reads env at call time and errors before any fetch. Headers are never stored, apiKey is dropped and the key is scrubbed from lines and errors, even when the body echoes it | `pytest (test_sgo_and_oddsapi_fixtures_parse, test_no_key_*, test_fake_key_*)` |
| A4 Schedule T-24h, T-3h, lineup+10m once each, not before; unknown lineup = start-60m, flagged | pass | Nothing at t-1, the label at t, not repeated once done, nothing at or after start. Lineup None gives a start-50m label with `lineup_assumed` | `pytest (test_schedule_*)` |
| A5 Mapping: real crawler rows give the right outcome and event_key; 2h off, team mismatch or two candidates are unmapped; rule_flags | pass | All 6 fixture rows are real rows from 2026-10-01T084927Z. The refusals are parametrized (2h off, team mismatch, home/away swap, 2 candidates). Flags are parsed from real rules text | `pytest (test_mapping_*); audit-tmp/WP4-A/probe_smoke.py` |
| A6 Quota: 80% routine / news to 100% / all refused at 100%; persists across instances; CLI report | pass | With limit 10: 8 routine allowed and the 9th refused, news allowed up to 10, and a second instance sees 10. The regenerated report is byte-identical, and an independent recompute matches (peak 30.5%) | `pytest (test_quota_*); python -m sports.odds quota --out audit-tmp/WP4-A/phase4_quota.regen.md; diff` |
| A7 WS and ESPN fixtures parse to GameState; cancel rule fires on a changed start, early in_progress, postponement or stale state; not on an on-time game | pass | The fixtures match raw captures. All 4 triggers fire, and the on-time, within-60s, normal in-play and 119s cases hold. `sports` feed age is the oldest feed and is absent until all have reported (fail closed) | `pytest (test_espn_and_ws_*, test_cancel_rule_*, test_feed_age_under_sports)` |
| A8 Early-start drill cancels only that game's orders | pass | a0, a1, a2 and a9 (partial) are cancelled. b0-b2 and x1 stay open, and FakeRouter.submit raises | `pytest test_early_start_drill_cancels_only_that_game` |
| A9 Smoke: Kalshi, ESPN, at least 60 s of WS, map today's crawler rows; report | pass | Re-derived offline: Kalshi 48, ESPN 48 games, 144/144 mapped (48 events, 0 unmapped), 53 WS frames in 75 s (none in our leagues). SGO and odds-api are stated as not run (no keys) | `audit-tmp/WP4-A/probe_smoke.py; reports/phase4_sports_smoke.md` |
| A10 pytest passes with the autouse socket guard | pass | 23 passed. The probe confirmed the guard blocks httpx, websockets and the Kalshi client. Data and report hashes are unchanged after the run | `.venv\Scripts\python.exe -m pytest tests/phase4/test_sports_data.py -q` |
| A11 [ops] Live SGO and odds-api.io with real keys; quota projection in the Phase 1 daily report | operational_pending | No keys on this machine (env grep count 0). Daily-report wiring belongs to the Phase 1 integration | `n/a (needs keys)` |

**Open defects at final audit** (none are blockers or majors):

- **minor**: `cancel_signal` matches maps only by exact `event_key`, which embeds the kickoff UTC date. A kickoff moved to another UTC date gets a new key and no signal fires, even on an early in_progress. The WS receive-date key has the same gap. Fix: match by (league, home, away) with the start within a few days (`sports/gamestate.py`).
- **minor**: `parse_espn` falls back to the coarse ESPN state for unknown status names ('pre' becomes scheduled, 'post' becomes final), so a new halt-type status would not cancel. The comment claims unknown statuses fail closed (`sports/gamestate.py`).
- **minor**: `sgo_snapshots` and `oddsapi_snapshots` default to `quota=None`, so a wiring that forgets the Quota bypasses the 80%/100% book (`sports/odds.py`).

**Builder's open issues:** the Kalshi kickoff is taken as occurrence_datetime minus 3h, which held for 48 of 48 events. The soccer WS status strings have not been seen live. `Quota.take` has no file lock.

**Rules check:** GETs only, to public Kalshi, ESPN and Polymarket sports WS, plus SGO and odds-api only with an env key, and none exists. `cancel_game` only calls `router.cancel` and was tested on a fake. Credentials come from env only and are never written. Tests make no network calls and write to tmp_path only. Files stayed inside the owned paths. Both reports end with "How to reproduce".

---

## WP4-B: Sports fair value and sports pulls (4.3, 4.4, 4.10 pre-registration; roles 19, 20)

**Final verdict:** PASS_WITH_OPERATIONAL_PENDING (from `audit:WP4-B`). Agent sequence: build → audit.

| AC | Status | Evidence | Command |
|---|---|---|---|
| B1 All 7 penaltyblog methods give probability vectors summing to 1 | pass | The test passes. The auditor's 3 extra fixtures sum to 1 ± 1e-12 for every method. Odds ≤ 1 or NaN give None | `pytest test_all_seven_methods_*; audit-tmp/WP4-B/probe.py` |
| B2 Method choice uses training seasons only, scores against outcomes, state 'candidate' | pass | On the real matches.parquet with every held-out row's odds replaced by noise and FTR set to 'D', the paramset is unchanged (version ee7d3af0e9a5) and train_ll is unchanged. Only opening columns are read | `audit-tmp/WP4-B/b2_real.py; read fair.choose_methods` |
| B3 devig-report writes reports/phase4_devig.md with every column for 5 leagues, ending How to reproduce | pass | The regenerated report differs only in the "Generated" line. Training log losses match Phase 0's opening-odds table exactly. The note says PS* stops in January 2026 | `audit-tmp/WP4-B/regen.py; diff reports/phase4_devig.md audit-tmp/WP4-B/phase4_devig.regen.md` |
| B4 sigma_fair non-decreasing in age; fair refuses with no sharp snapshot or one past max_age | pass | sigma = sqrt(s0² + k·age), checked over 2000 random ages. None, [], max_age+1, football-data PSC, another event and Kalshi-only input all refuse. Exactly max_age is accepted | `pytest test_sigma_fair_*, test_fair_refuses_*` |
| B5 Quote gate: none fresh, refuse; one fresh outside 1σ, refuse; all within, allow; stale outlier ignored | pass | Every case is tested. NaN fair or sigma refuses | `pytest test_quote_gate; probe.py` |
| B6 Consensus = median of per-book devig; H+D+A = 1 | pass | p is the median of 3 books' odds_ratio devig. Superseded and stale records are excluded. The sum is 1 within 1e-9 | `pytest test_consensus_*` |
| B7 One checkpoint row per mapped market per label, untraded included, with cluster_id and mid_ex_own | pass | 5 maps give 5 rows. The real `trader.ledger.Ledger` (temp dir) accepted the rows and rejected `cluster_id=None` | `pytest test_checkpoint_rows_*; probe.py` |
| B8 Pull drills fire and clear; lineup pull holds; sticky caution persists past expires_ms | pass | Every rule fires and clears. The lineup pull holds until obs > lineup. A sticky pull holds past expiry and ends on a later 'none'. Unknown and final statuses pull | `pytest test_pull_drills_*, test_lineup_pull_*, test_caution_pulls_*` |
| B9 Soccer pre-registration dict complete | pass | Fee-net 5m markout + rebate + reward against mid_ex_own, one match per cluster, alpha 0.0228, n 100, PASS at > 2 SE, futility (-1 SE, 50), Brier/log-loss guardrail 0.005. The real `Ledger.preregister` stored it, and re-registering was a no-op | `pytest test_soccer_preregistration; probe.py` |
| B10 pytest passes with the autouse socket guard | pass | 12 passed, using synthetic data only | `.venv\Scripts\python.exe -m pytest tests/phase4/test_sports_fair.py -q` |
| B11 [ops] Soccer through Loop B; source weighting by past accuracy | operational_pending | Needs keys, the running loop, ledger history and calendar time | `n/a` |

**Open defects at final audit** (none are blockers or majors):

- **minor**: Future-dated snapshots are treated as fresh. `fair()` clamps age at 0 and `continuous_sources()` accepts negative ages, so a snapshot at now+1h is chosen as perfectly fresh, and a lone future Kalshi record makes `quote_allowed` return True. Live this needs clock skew, but in Loop B replay it is look-ahead. Fix: ignore `obs_ms > now_ms` (`sports/fair.py`). **Fix before replay wiring.**
- **minor**: A sticky caution pull also ends on a later 'shrink', or on a non-sticky 'pull' that then expires, for the same (role, scope). The dispatch says only 'none' clears it. WP4-D never emits those, so it cannot happen today (`sports/pulls.py`).

**Builder's open issues:** s0 and the 10-minute continuous freshness are not checked against data. The devig choice was fitted only on data before January 2026 (football-data has no PS* after that). The SP1 slope of 1.19 is left to role 21.

**Rules check:** Pure modules with no network, env, credential, router or order code. Imports are stdlib, numpy, pandas, penaltyblog, common and the read-only `research.devig`. Tests write nothing. AI cautions can only add pull reasons. Files stayed inside the owned paths. The report ends with "How to reproduce".

---

## WP4-C: LLM gateway and clearance board (4.6, 4.8; gateway, roles 27, 28)

**Final verdict:** PASS_WITH_OPERATIONAL_PENDING (from `audit:WP4-C`). Agent sequence: build → audit.

| AC | Status | Evidence | Command |
|---|---|---|---|
| C1 vendors=2 gives two distinct vendors, most quota first, len == vendors | pass | Tie broken by name, then by quota order. One key with vendors=3 gives [gemini, none, none]. Cached vendors go first (benign, documented). The mut_quota mutation fails the test | `pytest test_c1_*; mut_quota` |
| C2 Quota persists across instances, resets next UTC day, exhausted transport never called | pass | SQLite (day, vendor), counted before sending. A second instance sees 997, and 1000 after +1 day. With cap 2 the transport is called only twice | `pytest test_c2_*` |
| C3 Identical input cached, no call, quota unchanged; failures not cached | pass | sha256 cache key. Insert only after validation passes | `pytest test_c3_*` |
| C4 Timeout, 429, 500, non-JSON, missing field, out-of-enum give ok=False without raising | pass | 7 parametrized cases, httpx.ReadTimeout and an unopenable db are all covered. The mut_valid mutation fails the tests | `pytest test_c4_*; mut_valid` |
| C5 Env secret value, 64-hex or 'bankroll' refused before any transport call | pass | `is_public()` runs on prompt + schema before quota. The mut_public mutation fails all 7 C5 tests | `pytest test_c5_*; mut_public` |
| C6 No keys: every vendor unavailable; no trader↔advisor imports | pass | No transport calls. The AST import scan passes, and a grep of trader/ finds only a string literal in a test | `pytest test_c6_*; grep -rn advisor trader/` |
| C7 Parsers: clear, missing point, dispute high, role-28 veto without reading, non-JSON | pass | All 12 cases pass. See the minor defect on the "not stated in rules" sentinel | `pytest test_c7_*; probe.py` |
| C8 Board matrix: both roles x two qualified vendors clear gives cleared; anything else not | pass | 7-case matrix. The auditor's probes (3 results, 1 result, same vendor with another model, ok=True failing R27) are all not cleared. The rules hash never appears in a prompt | `pytest test_c8_*; probe.py` |
| C9 Zero quota everywhere: nothing cleared, nothing written | pass | Real LLMGateway with caps 0: 0 calls, no db and no JSONL. The no-key reproduction gives 16/16 not cleared and 0 calls | `pytest test_c9_*; audit-tmp/WP4-C/repro.py` |
| C10 Record read by load_advice, key == clearance_key, verify True/False, keys JSONL accepted by clearance_cli sign | pass | Written via `tools.clearance_cli.write`. Nothing is signed without `ROSTER_ADVISOR_KEY`, when it equals the human key, or when the db resolves to advice.db | `pytest test_c10_*; probe.py` |
| C11 Agreement CLI end to end with a fake gateway; every section present | pass | The 2x2 table, Skipped, Per template, Vendor calls used and How to reproduce are all present. The human db is untouched. The real report reproduces | `pytest test_c11_*; repro.py` |
| C12 pytest passes with the autouse socket guard | pass | 47 passed, using fake transports only | `.venv\Scripts\python.exe -m pytest tests/phase4/test_advisor_board.py -q` |
| C13 [ops] Advisor OS user, real keys, agreement against your clearances | operational_pending | No vendor keys, no advice.db and no real uncleared.jsonl yet. The current report is a no-key run that failed closed and says it is not a qualification run | `n/a` |

**Open defects at final audit** (none are blockers or majors):

- **minor**: Role-27 "silence = veto" never fires for a model that follows the prompt. The prompt says to write "not stated in rules", but `parse_27` vetoes only empty strings, so an answer with resolution_source "not stated in rules" and verdict clear parses as clear (`advisor/board.py`). **Fix before the C13 qualification run.**
- **minor**: `LLMGateway.complete()` raises a TypeError on `vendors=None`, because `int()` runs outside the try (`advisor/gateway.py`).
- **minor**: The signer can name three vendor/model pairs when roles 27 and 28 use different pairs. The record still loads and verifies (`advisor/board.py`).

**Builder's open issues:** models and caps in `VENDORS` have not been checked against live docs. "Vendor calls used" is wrong for a run that crosses UTC midnight. The agreement report counts human records without verifying their signatures. Quota has no inter-process lock.

**Rules check:** No order, router or venue code. The only signature is the HMAC clearance under env `ROSTER_ADVISOR_KEY`. All vendor HTTP goes through an injected transport, and the no-key real run sent 0 requests. Keys go in headers (Gemini uses `x-goog-api-key`). No secrets found. Files stayed inside the owned paths. The report ends with "How to reproduce".

---

## WP4-D: News sentinel, calibration blend, Loop A (4.5, 4.7, 4.9; roles 25, 21, 23)

**Final verdict:** PASS_WITH_OPERATIONAL_PENDING (from `audit:WP4-D`). Agent sequence: build → audit.

| AC | Status | Evidence | Command |
|---|---|---|---|
| D1 Prefilter: no tracked name or keyword, no call; a match, exactly one call | pass | All 14 keywords give 1 call each. Partial words ('Outlook', 'without', 'Arsenalfan') give 0. One item naming two games gives 1 call and 2 pulls. The prompt holds no url, source family or timestamp | `pytest test_prefilter_*; audit-tmp/WP4-D/probe_sentinel.py` |
| D2 Material news pulls the right event_key, sticky, shrink ≤ 1; LLM or parse failure pulls | pass | Pull with scope=event_key, shrink 0.0, expiry at start, and a refresh request. Six failure shapes all pull with 'llm-failure'. A 3000-trial fuzz only ever emits pulls with shrink in [0,1] | `pytest test_material_*, test_llm_or_parse_failure_pulls; probe_sentinel.py` |
| D3 Resume only on an observation strictly after the news; newer news re-arms | pass | The only resume path is `on_sharp_observation` with obs > news_ms, and nothing resumes on time. The fuzz model matches in 3000 trials. Mutating `<=` to `<` is caught | `pytest test_resume_*, test_news_time_*; probe_sentinel.py` |
| D4 Disagreeing source families keep the pull and are flagged | pass | Both orders give 'injury, bbc; sources disagree'. Non-material verdicts from 3 families never lift a pull | `pytest test_disagreeing_*; probe_sentinel.py` |
| D5 Blend fit recovers a, b, c on 300 clusters; c bounded to [0,1]; below 100 clusters, None | pass | Mean over 10 seeds (0.197, 0.904, 0.613) against true (0.2, 0.9, 0.6). True c of 1.8, 3.0, -0.8 and -3.0 all fit inside [0,1]. The builder's figures reproduce exactly | `audit-tmp/WP4-D/probe_loop_a.py` |
| D6 Switch: 0.3 below 100 clusters; candidate c = bootstrap lower quantile ≤ point; no registry write in loop_a.py | pass | Candidate {kelly-c, c 0.4748, quantile 0.2, n 300, candidate}. c_in_force gives 0.3 for None, {}, NaN, -0.1 and 1.7. The grep finds nothing | `pytest test_c_switch; grep -niE "promot\|regist\|\.record\(\|sqlite\|open\(" learning/loop_a.py` |
| D7 Refit gate: ≥ 100 clusters and gain > 2 cluster-robust SE; per-row-only significance rejected | pass | Row t is about 7.7, yet the gate rejects (0.01 < 2 x 0.0091). 99 clusters are rejected. NaN fails closed. Both mutations are caught | `pytest test_refit_gate, test_refit_step_*; probe_loop_a.py` |
| D8 Anchor rule over 10,000 random refit chains; straddle gives the mid; spread is the wider | pass | The exhaustive 61³ grid (226,981 triples) holds. Six real accepted refits leave anchored_p at the anchor | `pytest test_anchor_rule_*, test_chain_of_real_refits_*; probe_loop_a.py` |
| D9 Walk-forward: no test row before any train row; no cluster on both sides | pass | Straddling clusters are excluded from test. Removing that exclusion is caught | `pytest test_walk_forward_split; probe_loop_a.py` |
| D10 pytest passes with the autouse socket guard | pass | 20 passed. `test_guard_blocks_network` proves the guard works | `.venv\Scripts\python.exe -m pytest tests/phase4/test_sentinel_loop_a.py -q` |
| D11 [ops] c switch after 100 clusters with your token; live news through role 13 | operational_pending | The code side is ready. Needs calendar time, your token and role 13 (not built) | `n/a` |

**Open defects at final audit** (none are blockers or majors):

- **minor**: `anchored_p` fails open on non-finite input. A NaN anchor returns the unbounded current, and a NaN current returns NaN (`learning/loop_a.py`). Fix: return the mid if any input is not finite.
- **minor**: Family verdicts are never cleared, so a 40-hour-old non-material verdict from another source makes an unrelated pull read "sources disagree", and `self.verdicts` grows without bound. The pull itself is correct (`advisor/sentinel.py`).
- **minor**: Test gap: out-of-order news arrival (an older timestamp received later) is untested, and replacing the `max(...)` survives the test file. The code is correct today (`tests/phase4/test_sentinel_loop_a.py`).

**Builder's open issues:** `refit_step` takes but never scores the anchor, by design (the bound is applied at use time). `players` on MarketMap is an optional extension. Pull state is in memory only. Team aliases are not handled.

**Rules check:** Imports are only re, unicodedata, advisor.contracts, numpy and scipy, with no network, env or subprocess. The LLM is reached only through an injected Gateway, and tests use a fake. The sentinel never emits a size or price, and a non-material LLM verdict cannot lift a pull. No report path was assigned and none was written. Files stayed inside the owned paths.

---

## How to reproduce

From `C:\Users\DELL\Downloads\saugan_pr\market_updated\roster`:

```
.venv\Scripts\python.exe -m pytest tests/phase4/test_sports_data.py -q       # 23 passed
.venv\Scripts\python.exe -m pytest tests/phase4/test_sports_fair.py -q       # 12 passed
.venv\Scripts\python.exe -m pytest tests/phase4/test_advisor_board.py -q     # 47 passed
.venv\Scripts\python.exe -m pytest tests/phase4/test_sentinel_loop_a.py -q   # 20 passed
.venv\Scripts\python.exe -m pytest tests/phase4 -q                           # 102 passed
.venv\Scripts\python.exe common.py                                           # self-check, exit 0
```

The per-WP claims (build and final audit) are in `build/phase-4/claims/WP4-{A,B,C,D}.{build,audit}.json`. The auditors' probes are in `build/phase-4/audit-tmp/WP4-*/`, and each audit's notes give the exact probe commands. Reports: `reports/phase4_quota.md` (`python -m sports.odds quota`), `reports/phase4_sports_smoke.md`, `reports/phase4_devig.md` (`python -m sports.fair devig-report`) and `reports/phase4_agreement.md` (`python -m advisor.board agree ...`).
