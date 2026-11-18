# Paper-run health check for the restart-paper-runs skill (read-only: it never starts, stops or resets anything).
# For each active run: is its process up, how long since its event loop last wrote a latency row, and which
# pauses (breaker trips) are still in force. Also the feed hub and the keeper.
#
#   roster\.venv\Scripts\python.exe .claude\skills\restart-paper-runs\scripts\check_runs.py
import datetime as dt
import importlib.util
import pathlib
import sqlite3
import sys

import psutil

# The roster folder sits next to .claude; its venv runs this script.
ROSTER = pathlib.Path(__file__).resolve().parents[4] / "roster"
sys.path.insert(0, str(ROSTER))
from nightly import scorer  # noqa: E402

# Reuse the keeper's own list of active runs and its process matcher, so this check never drifts from it.
spec = importlib.util.spec_from_file_location("keeper", ROSTER / "ops" / "keeper.py")
keeper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(keeper)

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
now_ms = dt.datetime.now().timestamp() * 1000
procs = [p.info["cmdline"] or [] for p in psutil.process_iter(["cmdline"])]

# The hub and the keeper are matched on exact command tokens, as the keeper itself does.
print(f"time {dt.datetime.now(IST):%d %b %H:%M} IST")
print(f"feed hub: {'up' if any('trader.feedhub' in c for c in procs) else 'DOWN'}")
print(f"keeper:   {'up' if any(any(x.endswith('keeper.py') for x in c) for c in procs) else 'DOWN'}")

for run, (action, bat) in keeper.ACTIVE.items():
    up = any(keeper.matches(c, run, bat) for c in procs)
    db = ROSTER / "data" / "trader" / run / "trader.db"
    age = None
    if db.exists():
        con = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True, timeout=5)
        try:
            # The event loop writes a latency row every minute while it runs: the best "is it alive" signal.
            last = con.execute("SELECT MAX(recorded_ms) FROM rows WHERE tbl = 'latency'").fetchone()[0]
        finally:
            con.close()
        age = None if last is None else max(0, int((now_ms - last) / 1000))   # a row written just after now_ms reads as -1
    # Latest trip per scope; anything not ACTIVE is a pause still in force.
    state = {}
    for t in scorer.tables(ROSTER / "data" / "trader" / run).get("trips", []):
        state[t["scope"]] = (t.get("state") or t.get("level"), t.get("reason", "")[:60],
                             dt.datetime.fromtimestamp(t["event_ms"] / 1000, IST).strftime("%d %H:%M"))
    paused = {k: v for k, v in state.items() if v[0] != "ACTIVE"}
    alive = "-" if age is None else f"{age} s ago"
    print(f"{run:12s} process {'up' if up else 'DOWN':4s} | loop alive {alive:10s} | "
          + ("all ACTIVE" if not paused else "; ".join(f"{k} {v[0]} since {v[2]}: {v[1]}" for k, v in paused.items())))
