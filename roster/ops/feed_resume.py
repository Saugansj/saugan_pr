"""Paper only: lift a pause caused by nothing but a feed gap, instead of waiting for the 08:15 reset (9 Oct; a 41-min
archive gap cost the rest of the day in the backtest). Every 10 min, for each run folder: a scope that is REDUCING, and
whose every trip since its last reset was a stale feed at least QUIET_MS ago, gets a short-lived reset token signed with
ROSTER_HUMAN_KEY, the same path as ops/morning_reset.py. Any other trip (loss, drawdown, clock, reconcile) waits for
08:15 or a person. Safe while a feed is still dead: the kernel refuses each order on a stale feed (kernel.STALE_MS).

  set ROSTER_HUMAN_KEY=...  &&  .venv\\Scripts\\python.exe ops\\feed_resume.py paper14 paper_v3 paper_v4
"""
import json
import os
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common import now_ms  # noqa: E402
from tools.clearance_cli import write  # noqa: E402

QUIET_MS = 5 * 60_000
TOKEN_MS = 3 * 60_000   # the trader reads advice each minute; a short life leaves no token for a later, different trip


def resumable(trips: list[tuple[int, dict]], now: int, quiet_ms: int = QUIET_MS) -> list[str]:
    """Scopes paused by stale feeds only, the newest of them at least quiet_ms old. trips: (event_ms, body) in order."""
    since: dict[str, list[tuple[int, str, str]]] = {}  # scope -> (ts, state, reason) since its last reset
    for ts, t in trips:
        state = t.get("state") or t.get("level")
        if state == "ACTIVE":
            since.pop(t["scope"], None)
        else:
            since.setdefault(t["scope"], []).append((ts, state, t.get("reason", "").replace("restart: ", "")))
    return sorted(s for s, rows in since.items()
                  if rows[-1][1] == "REDUCING" and all(st == "REDUCING" and r.startswith("stale feed") for _, st, r in rows)
                  and now - rows[-1][0] >= quiet_ms)


def main(argv) -> int:
    key = os.environ.get("ROSTER_HUMAN_KEY", "")
    if not key:
        print("ROSTER_HUMAN_KEY not set")
        return 2
    for name in argv:
        d = ROOT / "data" / "trader" / name
        if not (d / "trader.db").exists():
            continue
        con = sqlite3.connect(f"{(d / 'trader.db').resolve().as_uri()}?mode=ro", uri=True)
        try:
            trips = [(ts, json.loads(b)) for ts, b in
                     con.execute("SELECT event_ms, body FROM rows WHERE tbl = 'trips' ORDER BY id")]
        finally:
            con.close()
        now = now_ms()
        for scope in resumable(trips, now):
            write(d / "advice.db", {"type": "reset", "scope": scope, "signer": f"{os.environ.get('USERNAME', 'user')}-feed",
                                    "expiry_ms": now + TOKEN_MS}, key)
            print(f"{name}: feed-gap reset token for {scope}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
