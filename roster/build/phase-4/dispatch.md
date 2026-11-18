# Phase 4 Dispatch — Sports and AI audits (build now, wire later)

Source: [build-plan-v4.md](../../../build-plan-v4.md) Phase 4 (tasks 4.1–4.10), [36-agent-roles-polymarket-v4.md](../../../36-agent-roles-polymarket-v4.md) (roles 11, 12, 19, 20, 21, 23, 25, 27, 28, the LLM gateway in "Zero-cost operating plan", Loop A in "Self-learning loop", and "Data sources"), and the Phase 0 results in [../phase-0/audit.md](../phase-0/audit.md). Process: [../README.md](../README.md). Style follows [../phase-1/dispatch.md](../phase-1/dispatch.md).

**Scope (the user's decision): build now, wire later.** Phase 4's entry gate (Phase 3 gates met) is not met. The user chose to build every buildable Phase 4 piece now as **standalone modules**, each implementing against the shared contracts, so they can be wired into the trader loop and the advisor process later. Nothing in this phase changes the running Phase 1 paper loop.

What Phase 0 found that shapes this phase:
- football-data.co.uk **stopped publishing Pinnacle odds in January 2026** (0% PSC* fill on 250 current-season matches; 2026/27 CSVs carry only PP*, BFE*, BFEC*, AvgC*). Closing lines for CLV fall back to Betfair Exchange closing (BFEC*), then market average closing (AvgC*). The sharp snapshot source for quoting is SportsGameOdds (Pinnacle), which needs an API key that does not exist here.
- Phase 0's per-league devig choice (on closing odds): D1 multiplicative, E0 odds_ratio, F1 power, I1 power, SP1 odds_ratio. SP1 held-out calibration slope was 1.19.
- penaltyblog 1.12.3 is installed and exposes all 7 methods (`ImpliedMethod`): multiplicative, additive, power, shin, differential_margin_weighting, odds_ratio, logarithmic.

Environment:
- Code root: `C:\Users\DELL\Downloads\saugan_pr\market_updated\roster`
- Python: `roster\.venv\Scripts\python.exe` for everything. Run tests from the code root: `.venv\Scripts\python.exe -m pytest <paths> -q`.
- **Shared contracts (read-only):** `roster/trader/contracts.py` (`MarketInfo`, `Book`, `Intent`, `Order`, `Router`, `Ledger`, …) and `roster/advisor/contracts.py` (`LLMResult`, `Gateway`, `RoleVerdict`, `CautionSignal`). `common.py` is shared and read-only. If a contract is genuinely insufficient, work around it inside your package and report it; don't edit it.
- **Read-only imports allowed:** Phase 0 code (`recorder/`, `history/`, `research/`, e.g. `research/devig/devig.py`'s `devig()`, `choose_method`, `log_loss`), and Phase 1's `trader.kernel` helpers (`sign`, `verify`, `clearance_key`, `key_id`, `KEY_FIELDS`, `load_advice`) and `tools/clearance_cli.py`. Import them; never edit them. Phase 1 files (`trader/*.py`, `trader/engines/*`, `nightly/`, `tests/invariants/`, `data/trader/`) are owned by the running Phase 1 integration.
- Read-only data: `data/history/footballdata/matches.parquet` (25,491 matches, E0/SP1/D1/I1/F1, 2012/13–2026/27) and crawler snapshots `data/markets/*Z.jsonl` (144 `sports-pregame` moneyline rows in the latest).
- Runtime output folders (new, created at run time only; **tests write to `tmp_path` only**): `data/sports/` (WP4-A) and `data/advisor/` (WP4-C).

**Hard rules for every work package**
- Never place, sign, post or cancel a real order; never call an authenticated venue endpoint. Game-state cancels go through the `Router` protocol and are tested on fakes only.
- **Never call an LLM vendor API or any paid service.** LLM code is tested with fake vendors only. No vendor key exists on this machine.
- API keys (SportsGameOdds, odds-api.io, LLM vendors, `ROSTER_ADVISOR_KEY`) are read from environment variables at call time, never written to any file, log or report. No key → that source is unavailable, with zero network calls.
- Unit tests never touch the network: each test file has an autouse fixture that makes `socket.socket.connect` raise, so any network attempt fails the test. Public read-only GETs are allowed only in optional smoke runs.
- No `pip install`. Use stdlib, numpy, scipy, pandas, duckdb, pyarrow, websockets, httpx, penaltyblog. Anything that truly needs a new package goes behind an interface, its AC is marked [ops], and it is reported.
- Minimal code: fewest files, no speculative abstractions, one test file per work package covering the non-trivial logic. Reports end with "How to reproduce".

## Work packages and order

| WP | Build-plan tasks | Owns | Starts after |
|---|---|---|---|
| **WP4-A** Sports data: odds collectors, game state | 4.1, 4.2 (roles 11, 12) | `sports/odds.py`, `sports/gamestate.py`, `tests/phase4/test_sports_data.py`, `tests/phase4/fixtures/sports_data/`, `reports/phase4_quota.md`, `reports/phase4_sports_smoke.md`; runtime `data/sports/` | — |
| **WP4-B** Sports fair value and sports pulls | 4.3, 4.4, 4.10 pre-registration (roles 19, 20) | `sports/fair.py`, `sports/pulls.py`, `tests/phase4/test_sports_fair.py`, `reports/phase4_devig.md` | — |
| **WP4-C** LLM gateway and clearance board | 4.6, 4.8 (gateway, roles 27, 28) | `advisor/gateway.py`, `advisor/board.py`, `tests/phase4/test_advisor_board.py`, `reports/phase4_agreement.md`; runtime `data/advisor/` | — |
| **WP4-D** News sentinel, calibration blend, Loop A | 4.5, 4.7, 4.9 (roles 25, 21, 23) | `advisor/sentinel.py`, `learning/loop_a.py`, `tests/phase4/test_sentinel_loop_a.py` | — |

All four build in parallel. None imports another's module: they meet only through the shared contracts and the dispatch-level record shapes below, and each test file builds those records by hand. `advisor/contracts.py`, `advisor/roles_p5/` (Phase 5), `sports/__init__.py`, `learning/__init__.py` and `tests/phase4/__init__.py` are not owned by any WP. **[ops]** items need keys, real money, a live venue or calendar time; auditors mark them `operational_pending`.

### Dispatch-level record shapes (plain dicts; every WP implements against these)

League codes are football-data.co.uk's (`E0`, `SP1`, `D1`, `I1`, `F1`). Probabilities and odds are for the full 1X2: keys `"H"`, `"D"`, `"A"`.

| Shape | Keys |
|---|---|
| **OddsSnapshot** | `source` (`"sgo"` \| `"odds-api"` \| `"kalshi"` \| `"betfair"` \| `"football-data"`), `book` (e.g. `"pinnacle"`, a bookmaker name, or the venue), `league`, `event_key`, `home`, `away`, `start_ms`, `obs_ms` (source timestamp), `recv_ms` (local receive), and either `odds` (decimal H/D/A) or `probs` (H/D/A probabilities, for venues such as Kalshi) |
| **MarketMap** | `cid`, `token_yes`, `token_no`, `event_key`, `league`, `home`, `away`, `outcome` (`"H"` \| `"D"` \| `"A"`, the outcome this Polymarket market's YES pays on), `start_ms`, `rule_flags` (list of strings) |
| **GameState** | `source`, `league`, `event_key`, `home`, `away`, `scheduled_start_ms`, `status` (`scheduled` \| `in_progress` \| `final` \| `postponed` \| `delayed` \| `suspended` \| `cancelled`), `obs_ms`, `recv_ms` |

`event_key` = `"<league>:<home>:<away>:<kickoff UTC date YYYY-MM-DD>"` with WP4-A's normalized team names. It is the event group and cluster id for one match (one cluster = one match).

---

## WP4-A — Sports data: odds collectors and game state (4.1, 4.2; roles 11, 12)

**Requirements**
- `sports/odds.py` (role 11). All HTTP goes through one injectable fetch function (default `common.get_json` or httpx), so tests pass fakes.
  - **Kalshi public client (no key):** list soccer game markets for configured series and read their order books from `https://api.elections.kalshi.com/trade-api/v2` (public GETs only). Convert each game to an OddsSnapshot with `probs`: per outcome market, YES mid = (best YES bid + (1 − best NO bid)) / 2 from the book's cents; an outcome with an empty side gives no snapshot.
  - **football-data closing reader:** from `matches.parquet` (read-only), closing H/D/A odds per match in priority PSC* → BFEC* → AvgC*, with the column family recorded as `book`. A close equal to its opening column (PSC vs PS, BFEC vs BFE, AvgC vs Avg) on all three outcomes counts as missing. Used for CLV only, never for quoting.
  - **SportsGameOdds client (Pinnacle 1X2) and odds-api.io client (per-book 1X2, recreational books):** keys from env `SPORTSGAMEODDS_API_KEY` and `ODDS_API_IO_KEY`, read at call time. No key → an error result and zero network calls. Parsers produce OddsSnapshot records and are tested on recorded or mock responses in `tests/phase4/fixtures/sports_data/` (shapes taken from the vendors' public docs; label mock fixtures as mock). Every raw response is appended with its receive time to `data/sports/raw/<source>/<YYYY-MM-DD>.jsonl` (path param), with the key stripped from any URL or header before writing.
  - **Snapshot schedule:** `due(start_ms, lineup_ms, done_labels, now_ms)` returns the labels now due among `T-24h`, `T-3h`, `lineup+10m`, each at most once. `lineup_ms` comes from the caller (game state or news); when unknown it is assumed at start − 60 min (param), and the label is flagged `lineup_assumed`.
  - **Market mapping:** crawler `sports-pregame` moneyline rows (the `data/markets/*Z.jsonl` shape: `event_slug`, `question`, `event_start_time`, tokens, `rules_text`) → MarketMap. A match needs the same league, kickoff within 15 min and both team names equal after normalization plus a small alias table; no match or more than one candidate → unmapped (never guessed). `rule_flags` record where Polymarket's rules differ from sportsbook settlement, parsed from the rules text: postponed "remains open until completed", cancelled → "No", 90 minutes plus stoppage time. Spread and total markets are skipped (the crawler records moneyline only); add when the crawler records them.
  - **Quota:** a quota book per source (SportsGameOdds 2,500 events/month, odds-api.io 500 requests/day; both params) persisted to a JSON file (path param, default `data/sports/quota.json`). A routine request is refused once the period's usage reaches 80% of quota; a request with priority `"news"` may use the last 20% (role 25's reserve); at 100% everything is refused (fail closed).
  - **Per-league quota projection:** per league, the peak calendar month of fixtures over the recent seasons in `matches.parquet` × snapshots per event (3, param) = projected units. Leagues are enabled in a priority order (param) while the cumulative projected peak month of enabled leagues stays ≤ 80% of the monthly quota. A CLI (`python -m sports.odds quota`) writes `reports/phase4_quota.md`: per league the peak month, fixtures, projected units, cumulative share of quota, enabled yes/no, and the assumptions.
- `sports/gamestate.py` (role 12):
  - **Polymarket sports WebSocket client** (public, no auth, `websockets`) and an **ESPN soccer scoreboard poller** (`https://site.api.espn.com/apis/site/v2/sports/soccer/<league>/scoreboard`, public JSON), both producing GameState records; parsers tested on fixtures captured from (or shaped like) the live feeds. The module exposes each feed's age, under the feed name `sports`.
  - **Cancel rule:** `cancel_signal(game_state, maps, now_ms, stale_ms=120_000)` returns `{"event_key", "cids", "reason", "ts_ms"}` or None. It fires when the scheduled start differs from the markets' `start_ms` by more than 60 s, when the status is `in_progress` while now is before the scheduled start, when the status is postponed, delayed, suspended or cancelled, or when the game's state is older than `stale_ms`. `cids` lists every mapped market of that game.
  - **`cancel_game(signal, router, now_ms)`:** cancels every open order (via the `trader.contracts.Router` protocol) whose `intent.cid` is in the signal's cids, and nothing else.

**Acceptance criteria**
- **A1** Kalshi: the parser turns a fixture market list plus order books into OddsSnapshot `probs` equal to hand-computed mids; an outcome with an empty side gives no snapshot (test).
- **A2** football-data reader: PSC* is chosen where present; a synthetic row with close == open is missing; on the real `matches.parquet`, 2026/27 rows never come back with `book` = PSC (test).
- **A3** SportsGameOdds and odds-api.io: fixtures parse to OddsSnapshot records; with the env key unset the client returns an error and makes no fetch call; with a fake key set and a fake fetch, the key string appears in no stored raw line (test).
- **A4** Schedule: each of `T-24h`, `T-3h`, `lineup+10m` fires once at its time and not before; an unknown lineup uses start − 60 min and is flagged (test).
- **A5** Mapping: a real crawler row fixture maps to the right `outcome` and `event_key`; a kickoff 2 h off, a team mismatch, or two candidate events → unmapped; `rule_flags` carry the postponed and cancelled clauses (test).
- **A6** Quota: routine requests are refused at 80%, news requests allowed until 100%, all refused at 100%; usage persists across two instances on the same file (test). `python -m sports.odds quota` writes `reports/phase4_quota.md` with every listed column, ending with "How to reproduce".
- **A7** Game state: WS and ESPN fixtures parse to GameState; the cancel rule fires on a changed start, an early `in_progress`, a postponement and a stale feed, and does not fire for an on-time scheduled game (tests).
- **A8** Early-start drill: `cancel_game` on a fake Router cancels every open order of the early-starting game and none of another game's (test).
- **A9** Smoke (public GETs only): one run records Kalshi soccer markets and books, an ESPN scoreboard and ≥ 60 s of the Polymarket sports WebSocket, and maps today's crawler rows; `reports/phase4_sports_smoke.md` gives counts per source, mapped vs unmapped, and states any source that was unreachable (an unreachable source is reported, not hidden).
- **A10** `python -m pytest tests/phase4/test_sports_data.py -q` passes, with the autouse socket guard in the file.
- **A11 [ops]** Live SportsGameOdds and odds-api.io snapshots with real keys, and verifying the live response shapes against the fixtures. The quota projection in Phase 1's daily report (wiring).

**Wiring later:** the recorder process runs the collectors and game-state feeds on the snapshot schedule and appends OddsSnapshot and GameState records; Phase 1's `trader/marketdata.py` builds sports `MarketInfo` from MarketMap; the loop calls `cancel_signal` on every GameState update and `cancel_game` with the paper router, and reports feed age `sports` in `KernelContext.feed_age_ms`; `nightly/report.py` adds the quota projection section.

## WP4-B — Sports fair value and sports pulls (4.3, 4.4, 4.10 pre-registration; roles 19, 20)

**Requirements**
- `sports/fair.py` (role 19). Pure functions apart from the report CLI.
  - **Devig** with penaltyblog, all 7 methods (reusing `research/devig/devig.py` read-only is fine).
  - **Per-league method choice** by mean log loss against **match outcomes** on the full 1X2 (never against the closing line), on training seasons strictly earlier than the held-out seasons. Early-quote fits use opening odds (PSH/PSD/PSA, the seasons that have them); closing odds are for CLV only. The choice is returned as a registry-ready parameter set `{"name": "sports-devig", "version": ..., "params": {league: method}, "state": "candidate"}`.
  - **Devig report CLI** (`python -m sports.fair devig-report`): re-runs the choice on recent data from `matches.parquet` and writes `reports/phase4_devig.md`: per league, the chosen method, training and held-out log loss, n matches, Phase 0's closing-odds choice next to it, and a note that PS* stops in January 2026.
  - **Fair value:** `fair(market_map, sharp_snapshot, methods)` devigs the latest sharp OddsSnapshot (SportsGameOdds Pinnacle) with the league's method and returns the probability of the market's `outcome`, with the method and snapshot age.
  - **Uncertainty:** `sigma_fair(age_ms, params)` = sqrt(s0² + k · age_hours), non-decreasing in age; `params` (s0, k, max_age) is a registry-ready candidate. No sharp snapshot, or one older than `max_age` → no fair value, reason `"no sharp reference"` (role 19 then has no sharp reference and sports stays out).
  - **Continuous sources:** odds-api.io per-book records are devigged per book with the league's method and combined by the median (consensus); Kalshi `probs` are used as given; a `betfair` record is accepted if one is supplied (no Betfair client: it needs an account; [ops]).
  - **Quote gate:** `quote_allowed(fair, sigma, continuous_snapshots, now_ms, max_age_ms)` → `(bool, reason)`: needs at least one fresh continuous source, and every fresh continuous source within 1·σ of fair. Stale sources are ignored. Anything else refuses.
  - **Universe checkpoints:** `checkpoint_rows(maps, sharp, continuous, books, label, ts_ms)` → one row per mapped market at each snapshot label, traded or not: `cid`, `token_id`, `label`, `ts_ms`, `fair`, `sigma`, `mid_ex_own` (from `Book.mid_ex_own()`), `method`, `source`, `cluster_id` (= `event_key`), `mode` = `"sports-pregame"`. Rows fit `Ledger.record("forecasts", row, event_ms)` (the forecasts table needs `cluster_id`).
  - **Soccer pre-registration (4.10):** a dict for role 15's registry: name `soccer-maker`, statistic = fee-net maker 5m markout + rebate + allocated reward per cluster against `mid_ex_own`, cluster = one match, α, n ≥ 100 clusters in shadow, PASS if mean > 2 cluster-robust SE, futility if mean < 0 by more than 1 SE after 50 clusters, Brier and log-loss non-inferiority margin 0.005.
- `sports/pulls.py` (role 20, sports pull rules; pure):
  - `pull_reasons(now_ms, market_map, game_state, lineup_ms, last_sharp_obs_ms, cautions, feed_age_ms, gate, params)` → list of reasons (empty = may quote). Pull:
    - from scheduled start − margin (default 5 min, matching the kernel's start − 5 min resting rule); never relies on the venue's auto-cancel
    - from lineup release until a sharp snapshot with `obs_ms` > `lineup_ms` arrives (an older snapshot does not clear it)
    - on the game-state cancel conditions (changed start, early `in_progress`, postponed, delayed, suspended, cancelled)
    - on any `CautionSignal` with `action == "pull"` whose scope is this market's cid or `event_key`. When `resume_requires_fresh_observation` is True, its `expires_ms` is ignored (a timeout never resumes); it ends only when the sentinel replaces it with an `action == "none"` signal
    - on a stale book, sharp or game-state feed (bounds in params)
    - when the quote gate refuses
  - `maker_expiry(start_ms, end_ms)` = min(start − 5 min, end − 2 min).

**Acceptance criteria**
- **B1** All 7 penaltyblog methods run on a fixture 1X2 and each returns a probability vector summing to 1 (test).
- **B2** Method choice uses training seasons only (corrupting held-out rows leaves the choice unchanged) and scores against match outcomes; the parameter set has `state` `"candidate"` (test).
- **B3** `python -m sports.fair devig-report` writes `reports/phase4_devig.md` with every listed column for E0, SP1, D1, I1, F1, ending with "How to reproduce".
- **B4** `sigma_fair` is non-decreasing in age over random ages (test); `fair` refuses with no sharp snapshot or one past `max_age` (test).
- **B5** Quote gate: no fresh continuous source → refuse; one fresh source outside 1σ → refuse; all fresh sources within 1σ → allow; a stale outlier is ignored (tests).
- **B6** Consensus is the median of per-book devigged probabilities; the three fair values of one match (H, D, A) sum to 1 (test).
- **B7** Universe checkpoints: one row per mapped market per label, untraded markets included, each with `cluster_id` and `mid_ex_own` (test).
- **B8** Pull drills: each pull rule fires on its synthetic trigger and clears when the trigger clears; the lineup pull holds until a sharp snapshot newer than the lineup time; a pull `CautionSignal` with `resume_requires_fresh_observation=True` still pulls after its `expires_ms` (tests).
- **B9** The soccer pre-registration dict has statistic, α, n clusters, PASS rule, futility rule and guardrail (test).
- **B10** `python -m pytest tests/phase4/test_sports_fair.py -q` passes, with the autouse socket guard in the file.
- **B11 [ops]** Soccer through Loop B: replay → shadow (≥ 100 clusters) → canary at its own small cap → your token (task 4.10). Weighting continuous sources by how well they predicted the Pinnacle close needs ledger history; add it when that history exists.

**Wiring later:** a soccer maker `Engine` (Phase 1 contract) calls `fair`, `sigma_fair` and `quote_allowed`, feeds fair and σ to Phase 1's quote engine (role 20) and sizer (role 23), and drops all quotes whenever `pull_reasons` is non-empty; the loop writes `checkpoint_rows` to the ledger at each snapshot label; WP1-F's registry registers `sports-devig`, the σ params and the `soccer-maker` pre-registration.

## WP4-C — LLM gateway and clearance board (4.6, 4.8; gateway, roles 27, 28)

**Requirements**
- `advisor/gateway.py`: `LLMGateway` implementing `advisor.contracts.Gateway`. It never raises.
  - **Vendors:** Gemini, Groq and OpenRouter (`:free` models). Model names and daily caps live in one module-level config dict (defaults from the roles doc: Gemini 1,000, Groq 1,000, OpenRouter 50 requests/day; the caps change often). Keys come from env `GEMINI_API_KEY`, `GROQ_API_KEY` and `OPENROUTER_API_KEY`, read at call time; a vendor without a key is unavailable. There is no local-model vendor.
  - **Transport:** all HTTP goes through one injected callable (default: httpx POST with a timeout). Tests use fake vendors only.
  - **Quota:** counted per vendor per UTC day, persisted in SQLite (path param, default `data/advisor/gateway.db`). A request counts when sent. An exhausted vendor is unavailable. `quota_left()` reports what remains.
  - **Rotation:** `complete(task, prompt, schema, vendors=n)` asks n distinct available vendors, most quota left first. If fewer than n are available, each missing one comes back as `ok=False`, `error="no vendor available"`, so `len(result) == n` always.
  - **Cache by input hash:** key = sha256 of (task, vendor, model, prompt, schema). Only `ok` results are cached; a hit returns `cached=True`, spends no quota and makes no call.
  - **Fail closed:** a timeout, HTTP error, non-JSON answer or schema mismatch (missing required field, wrong type, value outside an enum) → `ok=False`. A small validator covers the JSON-schema subset the prompts use (object, required, string, boolean, number, array, enum).
  - **Public text only:** before any call, refuse a prompt containing the value (≥ 8 chars) of any env var whose name ends in `_KEY`, `_SECRET`, `_TOKEN` or `_PASSWORD`, a 64-hex-character string (private-key shape), or the words bankroll, balance, pnl, P&L or "position size" (case-insensitive) → `ok=False`, `error="non-public content"`, nothing sent.
  - **Never on the trading path:** `gateway.py` imports nothing from `trader`; nothing under `trader/` imports `advisor`.
- `advisor/board.py` (roles 27, 28 and the qualified clearance board):
  - **Role 27 (resolution auditor):** a prompt plus JSON schema requiring an answer on every material point: named resolution source, print or cutoff time (including 12:00 ET), "≥" vs ">", TWAP vs snapshot, tie and 50-50 rules, cancellation rule, postponed games that "remain open until completed", negRisk exactly-one-YES, augmented "Other" outcomes, and a dispute-risk score. A missing or empty answer on any material point, or dispute risk `"high"`, is a veto.
  - **Role 28 (wording adversary):** a prompt plus schema; it vetoes only with a specific, concrete reading under which the position loses although the forecast is right. A veto without a concrete reading is malformed, which is still a veto.
  - Prompts carry only public market text: the question, the rules text and the template key fields.
  - **Board:** `clear_template(gateway, key, question, rules_text, now_ms)` → `(cleared, [RoleVerdict("27-resolution"), RoleVerdict("28-wording")])`. Each role is asked with `vendors=2`. Cleared only if both roles got parsed `"clear"` answers from two **different** vendors whose (vendor, model) pairs are both in a `QUALIFIED` allowlist. A parse failure, timeout, missing item, error, a same-vendor pair or an unqualified model is a veto. `vendor_votes` records clear, veto or error per vendor.
  - **Clearance records** in exactly `tools/clearance_cli.py`'s shape: `{"type": "clearance", "key": <trader.kernel.KEY_FIELDS dict>, "signer": "llm-board:<v1>/<m1>+<v2>/<m2>", "expiry_ms", "nonce", "signed_ms", "sig"}`, signed with `trader.kernel.sign` under env `ROSTER_ADVISOR_KEY` (never the human key). They go into an `advice` table with clearance_cli's schema, in a db path param (default `data/advisor/llm_clearances.db`; never `data/trader/advice.db`). No key, or a veto → nothing written. The board also writes the cleared keys as `{"key": ..., "question": ...}` JSONL that `python -m tools.clearance_cli sign --keys` accepts, so you can co-sign during the run-alongside period.
  - **Backlog and agreement report:** `python -m advisor.board agree --backlog <file> --snapshot <crawler jsonl> --human-db <advice.db> --out <report>`. The backlog is the `{"key", "cid", "question"}` JSONL that Phase 1's kernel dumps (`data/trader/uncleared.jsonl`) or a list of key dicts. It joins rules text from the crawler snapshot by cid, runs the board, reads human clearances with `trader.kernel.load_advice` (read-only) and writes the report (default `reports/phase4_agreement.md`): counts of agree-cleared, agree-not-cleared, board-only and human-only, per-template reasons, vendor calls used, and "How to reproduce".

**Acceptance criteria**
- **C1** With fake vendors, `vendors=2` returns two distinct vendors, rotation prefers the vendor with the most quota left, and `len(result) == vendors` even when fewer are available (test).
- **C2** Quota counts persist across two gateway instances on one db and reset on the next UTC day; an exhausted vendor's transport is never called (test).
- **C3** Cache: an identical input returns `cached=True` with no transport call and unchanged quota; failed results are not cached (test).
- **C4** Fail closed: timeout, HTTP 429 and 500, non-JSON, missing field and out-of-enum value each give `ok=False` without raising (one test per case).
- **C5** A prompt carrying an env secret value, a 64-hex string or "bankroll" is refused before any transport call (test).
- **C6** With no keys in env, every vendor is unavailable and the transport is never called (test). `grep -rn "advisor" trader/` finds no import, and `gateway.py` has no `trader` import (code read).
- **C7** Parsers: a complete clear answer parses as clear; a role-27 answer missing any material point, or with dispute risk high, is a veto; a role-28 veto without a concrete reading is a veto; non-JSON is a veto (tests).
- **C8** Board matrix: both roles × two qualified vendors clear → cleared; any single veto, error, timeout, same-vendor pair or unqualified model → not cleared (tests).
- **C9** Exhausted quota blocks new clearances: with every vendor at zero quota, nothing is cleared and nothing is written (test; the 4.6 done-when).
- **C10** Compatibility: a cleared record in a tmp db is read back by `trader.kernel.load_advice`, its key equals `trader.kernel.clearance_key(m)` for a fixture `MarketInfo`, and `trader.kernel.verify(rec, test_key)` is True and False under another key; the emitted keys JSONL is accepted by `tools.clearance_cli.main(["--db", tmp, "--key", test_key, "sign", "--keys", jsonl, "--signer", "t"])` (test).
- **C11** The agreement CLI runs end to end with a fake gateway on a fixture backlog in tmp paths and writes a report with every listed section (test). The real report is C13.
- **C12** `python -m pytest tests/phase4/test_advisor_board.py -q` passes, with the autouse socket guard in the file.
- **C13 [ops]** A separate advisor OS user with no key or journal access; real free-tier vendor keys; the agreement report on the real template backlog against your clearances (task 4.8); switching to board clearances only once they agree with you.

**Wiring later:** the advisor process runs `LLMGateway` and the board over new or changed (template, rules hash) keys and re-runs on every clarification (a new rules hash is a new key); the kernel learns to accept board-signed records under `ROSTER_ADVISOR_KEY` for slow-lane templates (or reads `llm_clearances.db` alongside `advice.db`), a Phase 1 kernel change that needs your token; role 36's report adds an AI-quota alarm from `quota_left()`.

## WP4-D — News sentinel, calibration blend, Loop A (4.5, 4.7, 4.9; roles 25, 21, 23)

**Requirements**
- `advisor/sentinel.py` (role 25), using any `advisor.contracts.Gateway` (tests pass a fake):
  - **Keyword prefilter:** a news item (`text`, `source_family`, `published_ms`, `recv_ms`, `url`) passes only if it names a tracked team or player (names from MarketMap records, case- and accent-insensitive) **and** contains a keyword: out, injury, injured, doubtful, questionable, suspended, ruled out, scratched, lineup, starting XI, postponed, delayed, weather, abandoned. No match → no LLM call.
  - **LLM only on matches:** `gateway.complete("25-sports-news", prompt, schema, vendors=1)`, with the prompt built from the item text and candidate team names only; schema `{material: bool, team: str, kind: enum}`.
  - **Output** `CautionSignal(role="25-sports-news", scope=<event_key>, action="pull", shrink_factor ≤ 1, expires_ms=<scheduled start>, resume_requires_fresh_observation=True, reason=<kind, source family>)` for material news. An LLM failure on a matched item also pulls (the cautious default). Non-material news changes nothing.
  - **Source families:** when families disagree on the same game (one material, one not), the pull stays and the reason says `sources disagree`.
  - **Resume only on a fresh observation:** `on_sharp_observation(scope, obs_ms)` returns an `action="none"` signal only if `obs_ms` is later than the latest news time (max of published and received) for that scope. Time passing alone never resumes, and newer news re-arms the requirement.
  - **News refresh request:** each pull also returns `{"event_key": ..., "priority": "news"}` so role 11 can spend its 20% news reserve on a fresh sharp snapshot.
  - It never emits a size or a price, and `shrink_factor` is always in [0, 1].
- `learning/loop_a.py` (Loop A, roles 21 and 23). Pure functions on lists or arrays; it registers or promotes nothing itself.
  - **Logit blend fit (role 21):** logit q = a + b·logit(m) + c·(logit f − logit m), fitted by penalized maximum likelihood on resolved universe-checkpoint rows (`y`, `m` = mid ex own, `f` = calibrated fair, `cluster_id`), with Gaussian priors centred at a = 0, b = 1 and c constrained to [0, 1]. Fewer than 100 distinct clusters → None.
  - **Cluster bootstrap of c:** resample clusters; the declared lower quantile (default 20th percentile).
  - **Switch rule for role 23's c:** `c_in_force(live_params)` returns the registry's live c, else 0.3. `c_candidate(rows)` returns None below 100 resolved clusters; otherwise a registry candidate `{"name": "kelly-c", "params": {"c": <lower quantile>, "quantile": 0.2, "n_clusters": n}, "state": "candidate"}`. The switch takes effect only through a registry promotion with your human token (task 4.5).
  - **Anchor rule:** `anchored_p(p_anchor, p_current, mid)` returns whichever is nearer the mid, or the mid if they straddle it; `anchored_spread(s_anchor, s_current)` returns the wider.
  - **Refit gate:** `accept_refit(ll_current, ll_candidate, cluster_ids, min_clusters=100)` → `(accepted, gain, se, n)`: per-cluster summed log-loss gain, accepted only if n ≥ 100 clusters and the mean gain > 2 × its cluster-robust SE.
  - **Walk-forward split:** `walk_forward(rows, t_split)` puts in training only rows resolved before `t_split` and in testing only rows resolved after it, with no cluster on both sides.
  - **Refit step:** `refit_step(anchor, current, candidate, eval_rows)` returns the candidate if `accept_refit` passes out of sample, else the current. It applies to role 21's maps, role 19's devig choice and role 20's toxicity params alike. The anchor never moves in Loop A; only a Loop B promotion moves it.

**Acceptance criteria**
- **D1** Prefilter: an item without a tracked name, or without a keyword, makes no gateway call; a matching item makes exactly one (fake gateway counts calls) (test).
- **D2** Material news → a pull for the right `event_key` with `resume_requires_fresh_observation=True` and `shrink_factor` ≤ 1; an LLM failure or parse failure on a matched item → pull (test).
- **D3** Resume drill (4.7): no resume at +1 h or +23 h without an observation; an observation not later than the news time does not resume; a later one does; newer news re-arms (test).
- **D4** Disagreeing source families keep the pull and are flagged (test).
- **D5** Blend fit recovers a, b and c within tolerance on 300 synthetic clusters generated with known values; c stays in [0, 1] when the data imply c > 1 or c < 0; below 100 clusters it returns None (test).
- **D6** Switch: 0.3 below 100 clusters; above, the candidate's c equals the bootstrap lower quantile, is ≤ the point estimate and lies in [0, 1]; the output is a candidate dict, and `loop_a.py` contains no registry write or `promote` call (test plus grep).
- **D7** Refit gate: accepted only with ≥ 100 clusters and gain > 2 cluster-robust SE; a gain that is significant counted per row but not per cluster (correlated rows within clusters) is rejected (test).
- **D8** Anchor rule (4.9 done-when): over 10,000 random chains of accepted refits, |p_used − mid| ≤ |p_anchor − mid| and p_used never lies past the anchor on the far side of the mid; straddling gives the mid; the spread is the wider of the two (property test).
- **D9** Walk-forward split: no test row resolves before any training row, and no cluster appears on both sides (test).
- **D10** `python -m pytest tests/phase4/test_sentinel_loop_a.py -q` passes, with the autouse socket guard in the file.
- **D11 [ops]** The c switch after 100 resolved clusters (calendar time), as a registry promotion with your token. Sentinel news sources (RSS, league injury reports) feeding it live through role 13.

**Wiring later:** the advisor process runs the sentinel on role 13's news items through WP4-C's gateway and writes its CautionSignals for the trader to read (pulls via WP4-B's `pull_reasons`; shrinks via role 23); a fresh sharp observation from WP4-A calls `on_sharp_observation`; the nightly job runs `refit_step` and `c_candidate` on ledger rows, and WP1-F's registry registers the candidates; role 23 reads `c_in_force`; the trader applies `anchored_p` and `anchored_spread` at use time.

---

## Phase 4 exit gate (from the build plan)

Soccer passes its own pre-registered test. That needs soccer through Loop B (replay → shadow ≥ 100 clusters → canary at its own cap → your token), real odds keys, and calendar time, so it is **[ops]**. This build delivers the standalone modules, their tests, the quota and devig reports, the public smoke run, and the drills in code (early start cancels orders; news pulls and resumes only after a fresh observation; exhausted quota blocks clearances; a chain of refits cannot pass the anchor).

**Not built in this phase:** spread and total market mapping (the crawler records moneyline only), a Betfair client (needs an account), an OddsPapi client, source weighting by past accuracy (needs ledger history), role 20's full objective, CUSUM triggers and postmortems (Phase 5), and role 13's news collector.

## How to reproduce

From the code root, run each work package's tests and CLIs:

```
.venv\Scripts\python.exe -m pytest tests/phase4 -q
.venv\Scripts\python.exe -m sports.odds quota
.venv\Scripts\python.exe -m sports.fair devig-report
```
