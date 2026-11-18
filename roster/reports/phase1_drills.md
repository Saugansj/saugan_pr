# Phase 1 restart drills (task 1.20)

Run 2026-10-07 07:49 UTC on this PC with live public feeds, paper only, data in `data/trader/drills_v3/`. Five forced restarts, each followed by a startup reconcile in the next run.

**Verdict: PASS.** Every restart was forced as planned and every next startup reconciled with zero mismatches.

| # | Restart | What happened | Journal after the stop | Next startup reconcile | Result |
|---|---|---|---|---|---|
| 1 | kill -9 at a random moment | killed 37.6 s after start (exit 1) | 57 lines, 22 orders, 0 unacknowledged, 0 takers in flight, 9 makers resting, torn tail no | 0 unknown cancelled, 0 fills backfilled, 0 mismatches | PASS |
| 2 | kill -9 mid-batch | killed itself after journaling the first order of a batch (exit 15) | 67 lines, 23 orders, 1 unacknowledged, 0 takers in flight, 0 makers resting, torn tail no | 1 unknown cancelled, 0 fills backfilled, 0 mismatches | PASS |
| 3 | clean stop | stopped at its time limit (exit 0) | 201 lines, 67 orders, 0 unacknowledged, 0 takers in flight, 0 makers resting, torn tail no | 0 unknown cancelled, 0 fills backfilled, 0 mismatches | PASS |
| 4 | kill -9 at a random moment | killed 62.1 s after start (exit 1) | 288 lines, 99 orders, 0 unacknowledged, 0 takers in flight, 9 makers resting, torn tail no | 0 unknown cancelled, 0 fills backfilled, 0 mismatches | PASS |
| 5 | kill -9 mid-batch | killed itself after journaling the first order of a batch (exit 15) | 298 lines, 100 orders, 1 unacknowledged, 0 takers in flight, 0 makers resting, torn tail no | 1 unknown cancelled, 0 fills backfilled, 0 mismatches | PASS |

Final run: startup {"run_id": "1791359585008-8740", "unknown_resolved": 1, "fills_backfilled": 0, "mismatches": [], "open_orders": 0}; shutdown {"clean": true, "mismatches": [], "violations": 0, "open_orders": 0, "audit_records": 480}.

What each restart checks:
- **kill -9** is `Popen.kill()`, which on Windows is TerminateProcess: no cleanup, no buffered writes, no atexit.
- **mid-batch:** the child process terminates itself the same way right after the first order of a multi-order batch is fsync'd to the journal and before any acknowledgement. On restart that order replays as `unknown`, blocks new orders on its token and side, and is cancelled by id (never re-sent).
- **startup reconcile** (trader/loop.py `start`): journal replay rebuilds every order, unknown orders are cancelled by id, fills on disk but missing from the ledger are written, then router memory, a fresh journal replay and the ledger's fills must agree on every order state and position. A mismatch would trip HALTED and count as an invariant violation.

Not exercised live in this drill (no such state existed at any stop): a journaled fill missing from the ledger or a taker in flight. Both restart paths are covered on the real modules by tests/invariants (test_unknown_never_retried_and_journal_replay_after_crash).

Per-step logs: `drill_1_random.log`, `drill_2_midbatch.log`, `drill_3_clean.log`, `drill_4_random.log`, `drill_5_midbatch.log`, `drill_6_final.log` in `data/trader/drills_v3/`; every step as JSON in `data/trader/drills_v3/drills.json`.

## How to reproduce

```
cd roster
rem paper clearances for the drill folder, signed with a throwaway key that lives only in this shell
set ROSTER_HUMAN_KEY=<any random string; your own key for real runs>
.venv\Scripts\python.exe -m nightly.drills keys > keys.jsonl
.venv\Scripts\python.exe -m tools.clearance_cli --db data/trader/drills_v3/advice.db sign --keys keys.jsonl --signer <you> --days 2
.venv\Scripts\python.exe -m nightly.drills --dir data/trader/drills_v3
```
