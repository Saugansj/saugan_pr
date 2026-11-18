# Exit manager (WX-A): build and 20-minute paper smoke

Contract: [build/exits/dispatch.md](../build/exits/dispatch.md), work package WX-A. The flag is `exits`, OFF by default. `paper14` is untouched and stays flags-off.

## What was built

- `trader/engines/exits.py` (new, pure functions):
  - `exit_intents(now_ms, held, cost, books, fair, markets, params, room_usd)` returns the SELL intents and one `exit_decisions` row per held token. It applies rules R1 (fair-value exit, on), R2 (take-profit), R3 (model stop) and R4 (capital release). R2 to R4 are off while their parameter is `None`.
  - Execution: a taker sell at the best bid (limit = bid, size ≤ the shares the bid shows) when the bid covers the market minimum. Otherwise a post-only GTD maker sell at `max(ask − tick, f + fv_margin, bid + tick)`.
  - Sizes are floored, and nothing is sent below the minimum size. A market is skipped whenever the ladder's pull rule holds: the pre-close window, the oracle gap, a stale book or feed, a sharp move or a book fault.
  - Also in the module: `available()` (positions net of in-flight SELL takers) and `merge()`.
  - Registry `exit-manager` v1 is registered as `candidate`. Pre-registration `exit-manager-v1`: PASS if mean > 2 SE with n ≥ 100; futility if mean < −1 SE after 50.
- `trader/engines/ladder.py`: with `exits` on, `engine.fair[cid]` keeps this tick's fair value and pull reason. Quotes are unchanged.
- `trader/loop.py`, with `exits` on:
  - `exit_round()` runs each ladder round. It appends the exit SELLs to the ladder targets, which go through the requote diff and the kernel like every intent.
  - Rows go to ledger `exit_decisions`. A repeated (token, action, rule, reason) is written at most once a minute.
  - Registry and pre-registration are written at start.
  - New runtime invariant `exit_rule`: an exit SELL must be `reduces_exposure` and no larger than the shares held. Otherwise it is a violation and a global HALT.
- `trader/features.py`: `exits` was added to `FLAGS`. It was not added to `PAPER_SAFE`, so the WW-D D2 set is unchanged.

**Design decision to review: an exit takes precedence over the complement bid.** The dispatch says to sell only shares not already committed to complement bids. The ladder always bids the complement for what it holds, up to 10 shares. Read literally, a typical 5 to 10 share position would therefore never be exitable.

So when a rule fires on a token, `merge()` withdraws the ladder's BUY on the other outcome for that round. The exit then sells the whole holding net of in-flight SELLs. As a result no share is ever both offered for sale and committed to a complement pair, which is the X3 property. The kernel's own `reduces()` check (SELLs of the token plus BUYs of its complement) agrees in the property test. If a rule stops firing, the resting exit is cancelled and the complement bid comes back.

## Acceptance criteria

| AC | Status | Evidence |
|---|---|---|
| X1: flag off, existing tests pass, ladder intents identical | met | Full suite **768 passed**. `test_x1_ladder_targets_identical_with_and_without_flag`: `LadderEngine()` and `LadderEngine(flags=("exits",))` both reproduce WW-C's audited `BASELINE` digest on the recorded tick set. WW-D's D1 frozen-loop parity test passes. `test_loop_flags_off_has_no_exit_wiring`; `registrations(frozenset()) == ({}, [])` |
| X2: R1 fires exactly when `bid − fee > f + margin`; R2 to R4 only when set | met | `test_x2_r1_*`: 3,000 random (f, unc, bid) points; the rule equals R1 if and only if `sell > f + max(fv_margin, k_unc·unc)`. One test each for R2, R3 and R4 checks: off with its parameter at None, fires when set, and does not fire past each threshold (tau, room, bid). Execution test: taker at the bid, maker at `max(ask − tick, f + margin, bid + tick)`, NO token priced at 1 − f |
| X3: never more than held net of pending SELLs/complement bids; never rounds up; refuses below min size | met | `test_x3_property_random_holdings`: 2,000 random holdings, in-flight takers (some `unknown`), top-of-book sizes and minimum sizes; more than 300 sells and more than 100 below-minimum refusals. Every sell is ≤ held − in-flight, is on the 0.01 grid, is ≥ min size, has its complement BUY withdrawn, and passes `RiskKernel.reduces` |
| X4: exit intents are `reduces_exposure=True` SELLs the real kernel approves in REDUCING | met | `test_x4_kernel_approves_exit_sells_in_reducing`: a real `RiskKernel` with a signed clearance and global REDUCING approves both a taker and a maker exit ("reduces exposure") and rejects a new BUY. Loop test `test_loop_exit_sells_held_position_through_kernel[True]`: under a REDUCING trip, the real kernel and paper router sell a 10-share position at the bid, with 0 violations and a clean reconcile |
| X5: no exit on stale books, in the pre-close window or the oracle gap | met | `test_x5_*` through the real `LadderEngine(flags=("exits",))`. The control fires R1. A book 61 s old, `now = end − 9 min` and `oracle_gap = {cid}` each give no intent and a `skip` row with reason `stale_book` / `close` / `oracle_gap`. A market without a fair value gives nothing |
| X6: 20-min paper smoke in `data/trader/exits_on/` with `--enable exits`: no crash, 0 violations, `exit_decisions` rows | met (with a seed, disclosed) | Two 20-minute runs, both a clean shutdown with 0 violations, 0 mismatches and 0 trips. Run 2 logged **43 `exit_decisions` rows**, including one live R1 exit (see below) |

Mutation check: breaking each of these makes at least one test fail. The in-flight netting, the pull guard, the uncertainty term, the taker size bound, and the complement withdrawal.

## The smoke runs (`data/trader/exits_on/`)

Earlier fresh 20-minute smokes recorded 0 ladder fills (`wiring_off`, `wiring_on`). Run 1 below shows the same. With no fills the exit manager has nothing to manage.

Run 2 therefore uses `data/trader/exits_on/seed_smoke.py`. This is the stock `trader.loop.main(["--paper", "--minutes", "20", "--dir", ..., "--enable", "exits"])`, plus one addition. In its first 10 minutes it buys up to two 5-share paper positions, taker at the ask, through the real kernel and router (reason `smoke-seed`):
- the token whose bid was richest against the model;
- then the token nearest to fair.

Run 1 found no seed candidate. Its markets were either under 1 h or over 30 h from close, because it ran 15:25 to 15:45 UTC, just before the 16:00 UTC print. The tau window was then widened from 1-20 h to 1-30 h.

| Run | Window (UTC) | Clean | Violations | Mismatches | Trips | Fills | exit_decisions |
|---|---|---|---|---|---|---|---|
| `1791386701013-15104` (`smoke_run1.log`) | 15:25 to 15:45 | yes | 0 | [] | 0 | 0 | 0 (no positions) |
| `1791387918129-10992` (`smoke.log`) | 15:45 to 16:05 | yes | 0 | [] | 0 | ladder BUY taker 2 (seeds), **ladder SELL taker 1 (exit)**, btc-speed 2 | **43**: hold 31, skip `stale_book` 9, skip `sharp_move` 2, **sell_taker R1 1** |

Run 2 counts: 314 ladder intents, of which 119 were approved and 195 were rejected `over group` (the seeded positions plus resting bids fill the $10 group cap). 116 maker orders, 108 cancels, 3 ladder takers and 3 fills. 0 `exit_rule` violations.

**The live R1 exit:**
- Seed 2 bought 5 shares of token `5111209921…` at 0.51.
- About 16 minutes later the bid rose to 0.54 while the model's fair stayed at 0.4955 (unc 0.0004). Sell value 0.54 − 0.0174 fee = 0.5226, above f + 0.02 = 0.5155.
- R1 fired, and the taker sold 5 @ 0.54 (fee 0.0869) 0.45 s later.
- Realised result: +0.15 on price, −0.174 in fees in and out, so about −$0.02. The rule's premise is that holding was worth only about 0.4955 × 5. Whether that wins on average is WX-C's study, not this smoke.
- Seed 1 (`9984029257…`, 5 @ 0.34) stayed a `hold` all run (sell value at or below f + margin) and is still held in the folder's paper journal.

Network: the public Polymarket WebSocket dropped and reconnected 13 times in run 2 and 9 times in run 1 ("slow consumer", as in earlier runs, with paper14 running alongside). There was no crash.

## Open points

- The seed in `seed_smoke.py` is a test harness, not part of the trader. Without it, a 20-minute smoke has nothing to exit.
- With `live_risk` also on, the kernel's REDUCING rule refuses taker exits (`reducing_rule`, fail closed, no token path yet). A taker exit is then refused in REDUCING. A maker exit (used when the bid is thin) is not affected. This was not exercised; `exits` + `live_risk` together needs a decision.
- R2, R3 and R4 default parameters (`tp_min_tau_h` 2, `sl_tolerance` 0.02, `release_room_usd` 5) are placeholders. Their rules stay off until WX-C's study sets them.
- Exit SELLs carry strategy `ladder-maker`, the only kernel strategy that trades these markets. A ladder SELL can only exist with the flag on. With `exits` on, ladder SELLs are checked by `exit_rule` and ladder BUYs still by the role 23 sizer invariant.

## Rules check

- Only owned files were edited: `trader/engines/exits.py` (new); additive flag-gated edits in `trader/engines/ladder.py`, `trader/loop.py` and `trader/features.py` (one flag name); `tests/exits/test_exits.py`; this report; and `data/trader/exits_on/`.
- `trader/loop.py` keeps its CRLF line endings, and the diff is additive only.
- Nothing under `data/trader/paper14/` was read, opened or written, and no process I did not start was signalled.
- Paper only. No authenticated or LLM call, and no pip install.
- The signing key was a throwaway random value in the shell environment, kept in the session scratchpad and not in the repo.

## How to reproduce

From `C:\Users\DELL\Downloads\saugan_pr\market_updated\roster`:

```
set PYTHONDONTWRITEBYTECODE=1
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/exits/test_exits.py trader/tests tests/invariants tests/wiring -q
.venv\Scripts\python.exe -m pytest -p no:cacheprovider trader/tests tests/invariants tests/phase2 tests/phase3 tests/phase4 tests/phase5 tests/wiring tests/exits -q

rem smoke (paper; throwaway key for this shell only)
set ROSTER_HUMAN_KEY=<any random string>
.venv\Scripts\python.exe -m nightly.drills keys > data\trader\exits_on\keys.jsonl
.venv\Scripts\python.exe -m tools.clearance_cli --db data/trader/exits_on/advice.db sign --keys data/trader/exits_on/keys.jsonl --signer <you> --days 2
.venv\Scripts\python.exe data\trader\exits_on\seed_smoke.py 20
rem unseeded (exactly the AC command; usually 0 positions, so 0 exit rows):
rem .venv\Scripts\python.exe -m trader.loop --paper --minutes 20 --dir data/trader/exits_on --enable exits
.venv\Scripts\python.exe data\trader\exits_on\summary.py
```

`summary.py` opens `trader.db` read-only (`mode=ro`) and prints per run: the clean flag, violations, trips, fills, and `exit_decisions` counts by action, rule and reason.
