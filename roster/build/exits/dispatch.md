# Exit Manager — plan and dispatch

## The gap

The trader manages entries carefully (pricing, sizing, caps, audits) but has no rule for an open position. It holds every share to settlement, apart from merging completed YES+NO pairs. On 7 Oct the paper account rose to $58.49 on open marks and fell back to about $39 before settlement, with nothing able to lock in or cut anything. Account-level breakers protect capital; nothing manages a single position.

## The plan

1. **Build** an exit manager (role 20/23 extension) as a flagged module, `exits`, OFF by default, so the 14-day gate run is unchanged.
2. **Prove** each exit rule on real paper positions: replay the per-minute price path of every position the paper runs held, with and without each rule, against the actual settlement. Decision rules are fixed before looking (pre-registered).
3. **Adopt** only rules that win, through the normal promotion gate and your token (rule 7). Until then, `exits` stays off in `paper14`.

Process: [../README.md](../README.md). Contracts: `trader/contracts.py` (read-only).

## Work packages

| WP | Owns | Starts after |
|---|---|---|
| **WX-A** Exit rules + wiring | `trader/engines/exits.py` (new), additive flag-gated edits in `trader/engines/ladder.py`, `trader/loop.py` and `trader/features.py` (add flag `exits` only), `tests/exits/test_exits.py` | — |
| **WX-C** Counterfactual exit study | `research/exits/` (new), `tests/exits/test_study.py`, `reports/exits_counterfactual.md` | — |

Ground rules: paper only; never touch anything under `data/trader/paper14/` except **read-only** opens (SQLite `mode=ro`) by WX-C; never kill or signal a process you didn't start; with `exits` off, behaviour and every existing test are unchanged; no pip installs; minimal code; tests need no network.

### WX-A — Exit rules and wiring

A pure function `exit_intents(now_ms, held, cost, books, fair, markets, params) -> list[Intent]` and its wiring.

Per held token: shares (net of live SELLs and of shares already committed to complement bids), average cost, best bid/ask, the engine's fair probability **for that token** (YES f, NO 1 − f) with its uncertainty, time to settlement, fee rate.

- **Hold value** per share = fair f. **Sell value** per share at the bid = bid − fee(bid).
- **R1 fair-value exit (core):** sell when `bid − fee(bid) > f + max(fv_margin, k_unc × unc)`. The market pays more than the model thinks the share is worth.
- **R2 take-profit (candidate, off unless `tp_pct` is set):** sell when `(bid − cost)/cost ≥ tp_pct` and `tau_h ≥ tp_min_tau_h`.
- **R3 model stop (candidate, off unless `sl_drop` is set):** sell when `f < cost − sl_drop` and `bid − fee(bid) ≥ f − sl_tolerance` (cut only when the market still pays about fair).
- **R4 capital release (candidate, off unless `release_bid` is set):** sell when `bid ≥ release_bid`, `tau_h ≥ 1` and the strategy's free capital room is under `release_room_usd`.
- Execution: a SELL `Intent` with `reduces_exposure=True`; taker at the best bid (limit = bid) when the bid's size covers at least the market minimum, otherwise a post-only maker sell at `max(ask − tick, f + fv_margin)` with GTD. Never sell more than held; never round up; refuse below min size. Skip on stale books, inside the final pull window before close, or when the market is in the oracle gap.
- Exits stay allowed in `REDUCING` (they reduce risk). They never raise size anywhere.
- Every exit decision, taken or skipped-by-threshold, is logged to ledger table `exit_decisions` with hold value, sell value and rule, for the study.
- Registry: parameter set `exit-manager` v1 as `candidate`. Defaults: R1 on (`fv_margin` 0.02, `k_unc` 1.0); R2/R3/R4 parameters `None`. Pre-registration `exit-manager-v1`: statistic = per closed position, realised exit value − hold-to-settlement value, net of fees, clustered by event group; PASS if mean > 0 by 2 SE over ≥ 100 positions; futility if below 0 by 1 SE after 50.
- **Wiring:** flag `exits` in `trader/features.py`; when on, the ladder engine (or the loop, whichever owns cost basis and fair values) appends `exit_intents(...)` to its intents each tick, through the kernel like every intent.

**AC**
- **X1** flag off: every existing test passes, and ladder intents on a recorded tick set are identical (test).
- **X2** R1 fires exactly when `bid − fee > f + margin` and not otherwise; R2–R4 fire only when their parameter is set (tests per rule).
- **X3** never sells more than held net of pending SELLs/complement bids; never rounds up; refuses below min size (property test over random holdings).
- **X4** exit intents are `reduces_exposure=True` SELLs that the kernel approves in `REDUCING` (test with the real kernel).
- **X5** no exit on stale books, in the pre-close pull window or the oracle gap (tests).
- **X6** a 20-minute paper smoke in `data/trader/exits_on/` with `--enable exits` runs without crashing, with zero invariant violations, and logs `exit_decisions` rows (report the counts in `reports/exits_smoke.md`).

### WX-C — Counterfactual exit study

`research/exits/study.py` replays real positions from paper ledgers (read-only) and compares exit rules with holding to settlement.

- Positions: from `fills` (BUY lots, net of sells and merges), with cost and fill time; per-minute price path from `marks` (token → mid each minute); outcome from `settlements` (or the CLOB resolution if missing, public GET, cached under `data/exits/`).
- Exit price = mid − half-spread, with half-spread as a sensitivity (0.005, 0.01, 0.02) plus the taker fee; fair value from `universe_checkpoint`/engine records where available, otherwise R1 is reported as not evaluable.
- Variants: hold (baseline), R1, R2 at tp 10/15/25%, R3 at drop 0.10/0.15, R4 at bid 0.95/0.97, and combinations R1+R2, R1+R3.
- Output `reports/exits_counterfactual.md`: per variant the mean improvement per position vs hold, cluster-robust SE (by event group), n, and the pre-registered verdict (PASS / FAIL / INCONCLUSIVE if n < 100). It must say plainly when the sample is too small. Runs over every paper ledger it finds (`paper14`, `wiring_*`, `drills_*`, `smoke*`) and labels each source.
- Runnable daily: `python -m research.exits.study` (idempotent).

**AC**
- **C1** unit tests on a synthetic position path: each rule exits at the right minute and the improvement maths is exact (tests).
- **C2** no look-ahead: a rule's decision at minute t uses only data up to t (test).
- **C3** opens every ledger read-only (`mode=ro`) and writes nothing under `data/trader/` (code read + test).
- **C4** the report exists, covers every variant, gives n and SE per variant, and states INCONCLUSIVE where n < 100.
- **C5** one documented command reproduces it.
