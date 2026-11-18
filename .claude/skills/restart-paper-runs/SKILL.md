---
name: restart-paper-runs
description: Restart or check the Polymarket paper runs (roster) after a PC sleep, crash or reboot, and lift feed-gap pauses. Use when the user says "restart the paper runs", "start the paper runs", "the PC was asleep", "are the runs running", or asks for the run status.
---

# Restart the paper runs

Paper only. Never touch `trader/live/live.json`, never pass `--live`, never start a retired run
(paper_v3, paper_ethc, paper_v4, paper_v5, paper_eth). All commands run from `roster/`.

# 1. Look first (read-only)

```bash
cd roster && .venv/Scripts/python.exe ../.claude/skills/restart-paper-runs/scripts/check_runs.py
```

It prints the hub, the keeper, and per active run: process up/DOWN, seconds since its loop last wrote a
latency row, and any pause still in force. A healthy run: process up, loop alive under ~90 s, all ACTIVE.

# 2. Start what is missing: through the keeper, nothing else

The keeper (`ops/keeper.py`) is the only automatic starter. It brings up the hub first, then one dead
run per minute (40 s CLOB stagger), with backoff, and runs the feed-gap resume every 10 min.

```bash
cd roster && powershell -NoProfile -ExecutionPolicy Bypass -File ops/paper_tasks.ps1 keep
```

- Safe to run any time: a second keeper exits on its file lock.
- Runs need 1-5 min after start (the `nightly.drills keys` market crawl) before they write latency rows.
- Do not start runs one by one with the `start*` actions unless the keeper is broken; never kill and restart
  healthy runs (a restart costs minutes of trading).
- If processes are up but `loop alive` is stale after a long sleep, wait 2-3 min first: the loop resumes
  on wake. Only a run still stale after ~20 min needs its processes killed (the keeper then restarts it).

# 3. Lift pauses

- Feed-gap pauses ("stale feed ..."): the keeper's resume lifts them within ~10 min once the feed has
  been back 5 min. To do it now: `powershell -NoProfile -ExecutionPolicy Bypass -File ops/paper_tasks.ps1 resume`.
- Loss pauses ("strategy daily loss ...") are by design: they reset at the 08:15 `sign` task. Do not
  lift them by hand unless the user asks.
- `paper_tasks.log` can be held open by a running research loop or report; if `resume` fails with an
  Out-File error, wait for that to finish and retry.

# 4. Report

Re-run the check (wait with an until-loop, not chained sleeps) and tell the user: which runs were down
and were started, which pauses remain and why, and the time the PC was asleep if the keeper logged
`woke after N min` in `data/trader/paper_tasks.log`.
