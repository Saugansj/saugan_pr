# How the build works

Each phase of [build-plan-v4.md](../../build-plan-v4.md) is built by a team of agents, with two files that bracket the work:

```
dispatch.md ──► builder agent (per work package) ──► independent auditor ──► pass? ──► audit.md ──► phase gate
                        ▲                                   │
                        └──── fixer agent (max 2 rounds) ◄──┘ fail
```

1. **Dispatch** (`phase-N/dispatch.md`): one work package per group of build-plan tasks. Each has its requirements, the folders it owns, and numbered acceptance criteria (AC) that an auditor can check with a command.
2. **Build:** one builder agent per work package writes code only inside its owned folders, runs its own tests and real smoke runs, and reports which AC it believes it met.
3. **Audit:** a separate auditor agent, which never edits code, re-runs the tests and checks every AC with evidence (the command it ran and what it saw). Verdicts:
   - `PASS`: every AC met
   - `PASS_WITH_OPERATIONAL_PENDING`: all code-level AC met; what remains needs real running time (for example, 7 days of recording)
   - `FAIL`: at least one code-level AC failed, or a blocker defect was found
4. **Fix:** on `FAIL`, a fixer agent gets the auditor's defects and repairs them, then the work goes back for a fresh audit. At most 2 fix rounds; anything still failing is reported, not hidden.
5. **Audit file** (`phase-N/audit.md`): every AC with its verdict and evidence, the defects found and fixed, and what is still pending.
6. **Phase gate:** the next phase starts only when the phase's exit gate in the build plan is met. Code-complete is not the same as gate-met: operational items (running days, live results) are listed separately in the audit file.

## Rules every agent follows

- Edit only inside the work package's owned paths. `common.py` is shared and read-only.
- Use `roster/.venv/Scripts/python.exe`. Prefer the standard library and the preinstalled packages; report anything newly installed.
- Minimal code: no speculative abstractions, fewest files, one test file per work package covering the non-trivial logic (`python -m pytest`).
- Public, read-only endpoints only. No private keys on disk, and never place an order.
- Large data lives under `roster/data/`. Human-readable results go in `roster/reports/`, each ending with "How to reproduce".
