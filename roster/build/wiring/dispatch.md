# Wiring Dispatch — connect Phases 2–5 to the Phase 1 trader

Source: the **Wiring later** sections of [phase-2](../phase-2/audit.md), [phase-3](../phase-3/audit.md), [phase-4](../phase-4/audit.md) and [phase-5](../phase-5/audit.md) audits, plus [phase-1/audit.md](../phase-1/audit.md). Process: [../README.md](../README.md).

## Ground rules for this dispatch

1. **Every new connection is behind a feature flag, OFF by default.** Flags live in one file, `trader/features.py` (owned by WW-D), read from `data/trader/<run dir>/features.json` and `--enable <flag>` on the CLI. With no flags set, the trader must behave exactly as the audited Phase 1 build: same intents, same kernel decisions, same tests passing.
2. **A 14-day paper run may be in progress** in `data/trader/paper14/` from `trader/loop.py`. Never read-modify, delete or write anything under `data/trader/paper14/`, and never kill or signal another Python process. Smoke runs and drills use your own folder under `data/trader/wiring_<WP>/`.
3. Paper only. Live-router code stays unreachable in a paper process (PaperRouter already refuses when `ROSTER_LIVE` is set). No authenticated calls, no LLM calls, no paid feeds. Key-dependent features are wired so they **fail closed** when keys are missing.
4. Each work package owns only the files listed. The Phase 2–5 modules are read-only. Fix the minor defects that their audits assigned "at wiring time" by guarding inputs in your own files, or report them.
5. The full suite must stay green: `python -m pytest trader/tests tests/invariants tests/phase2 tests/phase3 tests/phase4 tests/phase5 -q`.

## Feature flags (names are the contract between packages)

| Flag | Turns on | Paper-safe today? |
|---|---|---|
| `live_risk` | Phase 2 stress cap, resolution-risk cap, worst-case positions, pull-on-REDUCING, reducing rule | yes |
| `dd7` | 7-day drawdown breaker (persisted) | yes |
| `clock_gate` | SNTP clock-offset gate (this PC reads about 300 ms off, so it would sit in REDUCING) | yes, but expect REDUCING |
| `heartbeat` | Health-gated heartbeat warden (paper: the send is a no-op that is recorded) | yes |
| `settlement` | Settlement keeper (UMA proposal vs Binance, paging via ntfy if set), fund intents → `PaperRouter.merge` | yes |
| `capital_ladder` | Kernel global cap from `growth.capital.current_cap(ledger)` | yes ($50 on a fresh ledger) |
| `touch` | Touch markets in the ladder engine (crawler discovery + high/low in ref) | yes, as a candidate |
| `universe_ext` | SOL/XRP ladders and extra strikes (Loop B candidates) | yes, as candidates |
| `quote_objective` | Phase 5 full quote objective instead of Phase 1 `quotes()`, passed through `wider()` | yes, as a candidate |
| `negrisk_scan` | negRisk scanner logging (executor stays behind its closed evidence gate) | yes |
| `fast_maker` | Fast Up/Down maker (stays off until the latency gate opens) | gated |
| `sports` | Soccer maker engine from `sports/` (Kalshi + football-data free; keyed odds fail closed) | partly |
| `markout_cusum` | Phase 5 CUSUM markout lock replacing the count-based blacklist | yes |

## Work packages

| WP | Owns | Starts after |
|---|---|---|
| **WW-A** Kernel and breakers | `trader/kernel.py`, `trader/breakers.py`, `tests/wiring/test_ww_a.py` | — |
| **WW-B** Market data and execution | `trader/marketdata.py`, `trader/router.py`, `recorder/crawler.py` (additive only, behind `touch`/`universe_ext`), `tests/wiring/test_ww_b.py` | — |
| **WW-C** Engines | `trader/engines/ladder.py`, `trader/engines/sports_maker.py` (new), `trader/engines/fast_maker.py` (new adapter), `tests/wiring/test_ww_c.py` | — |
| **WW-E** Nightly and advisor processes | `nightly/` (new files and additive edits), `advisor/run.py` (new), `tests/invariants/` (additions only), `tests/wiring/test_ww_e.py` | — |
| **WW-D** Loop integration | `trader/loop.py`, `trader/features.py` (new), `tests/wiring/test_ww_d.py`, `reports/wiring_smoke.md`, `data/trader/wiring_*/` | WW-A, WW-B, WW-C |

### WW-A — Kernel and breakers
- `live_risk`: after `check()` approves, apply Phase 2 `check_live(...)` with `worst_case_positions(...)`; expose `pull_ids` and the reducing rule for the loop. `dd7`: `SevenDayDrawdown` next to `on_equity`, with samples persisted to the run dir. `clock_gate`: a method the loop calls with the measured offset. `capital_ladder`: the global cap comes from `capital.current_cap(ledger)`. `STRATEGIES` gains `negrisk-arb`, `fast-updown-maker` and `sports-maker` entries with small budgets, plus SOL/XRP sources, all inactive unless their flag is on. `markout_cusum`: the CUSUM monitor replaces the count blacklist when on.
- **AC:** A1 flags off: every existing kernel test passes unchanged and decisions on a recorded intent set are identical (test). A2 each flag's rule rejects its synthetic trigger (test per flag). A3 the dd7 state survives a restart (test). A4 the capital cap follows `current_cap`, and the 1.1× refusal follows it (test). A5 no AI or T5 source can reach HALTED (existing invariant still holds).

### WW-B — Market data and execution
- Keep held markets in `markets` until redeemed (the Phase 2 audit's must-fix). `touch`: crawler discovery of touch templates (`SLUG_MODE_EXT`, horizons past 8 days) and running 1m high/low per window in `ref[asset]`. `universe_ext`: SOL/XRP Binance subscriptions and `sigma_q`. `sports`: build sports `MarketInfo` from `odds.map_markets(...)` and merge `gamestate.feed_age_ms`. Router: port the replay fill model's remaining fix (two own orders must not fill against the same displayed liquidity), so paper and replay agree.
- **AC:** B1 flags off: the market set and books are identical to before (test against a fixture snapshot). B2 a held market past end+6h stays in `markets` until its position is zero (test). B3 touch and SOL/XRP rows map correctly with their flags on (fixture test). B4 router: two own takers cannot both fill the same displayed size (test); every existing execution test passes. B5 crawler changes are additive: with flags off, the same snapshot rows come out (test).

### WW-C — Engines
- Ladder: route `touch-up`/`touch-down` kinds to `growth.touch.touch_fair` (flag `touch`), guarding the NaN/τ≤0 inputs listed in the Phase 3 audit; use `quote_objective.optimise(...)` passed through `wider()` when `quote_objective` is on; accept an `oracle_gap` set from the settlement keeper for the pull rule. New `SportsMakerEngine` (Engine protocol) built from `sports.fair` and `sports.pulls` with Phase 1's quote/sizer functions. New `FastMakerEngine` adapter around `growth.fast_updown` that returns no intents while the latency gate is closed. A negRisk scan adapter that only produces log records.
- **AC:** C1 flags off: ladder intents on a recorded tick set are identical to before (test). C2 each new engine meets the Engine protocol and its invariants (sizer sign/magnitude, never rounds up) (tests). C3 the sports engine returns no quotes when any pull reason holds or keyed odds are missing (test). C4 the fast maker returns nothing while its gate is closed (test).

### WW-E — Nightly and advisor processes
- Nightly: canary evaluation (`trader.live.canary`), analyst, outcome-blind postmortems and CUSUM scans (`learning/`), Loop A anchored refits (candidates only), and the replay job (`learning.replay`, outputs under `data/`, trials logged). Each is a section or subcommand of the nightly run, and none promotes anything. Copy the Phase 5 invariant tests named in its audit (`test_a4_no_promote_anywhere`, `test_a5_outcome_blind`, `test_a10_no_halt`) into `tests/invariants/`. `advisor/run.py`: the advisor process entry point (gateway + board + sentinel). With no vendor keys it does nothing and says so (fail closed).
- **AC:** E1 the nightly run produces each new section on the existing smoke data without network calls (test with fixtures). E2 nothing in nightly can promote a registry version or reach HALTED (invariant tests). E3 `advisor/run.py` with no keys exits cleanly, makes no network call, and writes no clearance (test).

### WW-D — Loop integration (after A, B, C)
- `trader/features.py` and the CLI `--enable`. Wire everything above into `trader/loop.py` behind its flag: the heartbeat warden at the end of each tick (paper send = recorded no-op); the settlement keeper worker; fund intents → `PaperRouter.merge`; the clock-gate worker; pull-on-REDUCING; registry and pre-registration writes for every enabled module; the sports engine and game-state cancel signals; the oracle-gap set to the ladder.
- **AC:** D1 flags off: a 20-minute paper smoke in `data/trader/wiring_off/` matches the Phase 1 behaviour (intent and decision counts in the same range, zero invariant violations). D2 all paper-safe flags on (`live_risk dd7 heartbeat settlement capital_ladder touch universe_ext quote_objective negrisk_scan markout_cusum`): a 20-minute paper smoke in `data/trader/wiring_on/` runs without crashing, with zero invariant violations, and `reports/wiring_smoke.md` reports what each flag did. D3 the crash drills (`nightly.drills`) pass with all paper-safe flags on, in your own folder. D4 the full suite passes. D5 no file under `data/trader/paper14/` was touched, and no other process was signalled (show how you checked).
