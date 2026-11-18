"""Paper only: the 08:15 task's breaker reset (policy B, 8 Oct). For each run folder, a scope whose latest trip left it
REDUCING gets a one-use reset token signed with ROSTER_HUMAN_KEY; the trader applies it within a minute. A HALTED scope
(an invariant violation or a failed halt) is never reset here: that one waits for a person to look.

  set ROSTER_HUMAN_KEY=...  &&  .venv\\Scripts\\python.exe ops\\morning_reset.py paper14 paper_v3
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


def paused_scopes(run_dir: pathlib.Path) -> list[str]:
    """Scopes whose latest trip row is REDUCING (read-only on the ledger)."""
    db = run_dir / "trader.db"
    if not db.exists():
        return []
    con = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)
    try:
        last = {}
        for (b,) in con.execute("SELECT body FROM rows WHERE tbl = 'trips' ORDER BY id"):
            t = json.loads(b)
            last[t["scope"]] = t.get("state") or t.get("level")
    finally:
        con.close()
    return sorted(s for s, st in last.items() if st == "REDUCING")


def main(argv) -> int:
    key = os.environ.get("ROSTER_HUMAN_KEY", "")
    if not key:
        print("ROSTER_HUMAN_KEY not set")
        return 2
    for name in argv or ["paper14"]:
        d = ROOT / "data" / "trader" / name
        for scope in paused_scopes(d):
            write(d / "advice.db", {"type": "reset", "scope": scope, "signer": f"{os.environ.get('USERNAME', 'user')}-auto",
                                    "expiry_ms": now_ms() + 30 * 60_000}, key)
            print(f"{name}: reset token for {scope}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
