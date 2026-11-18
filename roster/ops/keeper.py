"""Keeper (15 Oct, from the fix arena): keeps the active paper runs alive without a scheduled task. Once a minute it
restarts the feed hub if it is gone, starts at most one dead run (the 40 s CLOB stagger, 11 Oct 429s), with backoff
10 min doubling to hourly and no give-up, and every 10 min runs `paper_tasks.ps1 resume` (feed-gap-only pauses: a 60 s
blip had paused every run 34 min on 14 Oct). It acts only through the existing ps1 actions, so the key never passes
through here, and it is single-instance by a file lock. A run whose ledger ends with a clean runs_end is not restarted.

  .venv\\Scripts\\python.exe -u ops\\keeper.py        # normally: ops\\paper_tasks.ps1 keep (WMI-detached, at logon)
"""
import datetime as dt
import json
import msvcrt
import pathlib
import sqlite3
import subprocess
import time
import traceback
from pathlib import PureWindowsPath

import psutil

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOG = ROOT / "data" / "trader" / "paper_tasks.log"
NET_LOG = ROOT / "data" / "trader" / "net_usage.jsonl"   # the whole PC's network counters, one line a minute (ops/data_usage.py)
# paper14 left out 20 Oct: its own ~380-token PM socket cannot run in the hub's low-data poll mode (~2-3 GB/hour)
ACTIVE = {"paper_v4b": ("startv4b", "start_paper_v4b.bat"), "paper_v7b": ("startv7b", "start_paper_v7b.bat"),
          "paper_v4add": ("startv4add", "start_paper_v4add.bat"),   # 15 Nov: v4b + one same-side add (user approved)
          "paper_v4sz50": ("startv4sz50", "start_paper_v4sz50.bat"),   # 17 Nov: v4b at 8 shares, $50
          "paper_v4sz100": ("startv4sz100", "start_paper_v4sz100.bat"),  # 17 Nov: v4b at 8 shares, $100
          "paper_v9fix": ("startv9fix", "start_paper_v9fix.bat")}  # 18 Nov: review fixes + live-like paper fills, $50
# retired 15 Nov (user): paper_v8b (its ask <= 0.50 rule failed forward, -4.99 live estimate vs v4b +73.92 on 31 Oct-14 Nov)
# and the weather NO run paper_wx (testing stopped); their data stays on disk
# paused 12 Nov for the live v4 test (user, to save RAM/data/Gamma calls): put back to resume them
PAUSED = {"paper_ethb": ("startethb", "start_paper_ethb.bat"), "paper_v6b": ("startv6b", "start_paper_v6b.bat"),
          "paper_mk": ("startmk", "start_paper_mk.bat"), "paper_ethmk": ("startethmk", "start_paper_ethmk.bat")}
# retired runs (paper_v3, paper_ethc, paper_v4, paper_v5, paper_eth; paper_v5b and paper_eth6b on 23 Oct: subsets of
# v4b / ethb, eth6b's skips cost ETH winners; paper_eth7c on 31 Oct: its pre-registered futility rule fired, live
# -0.281 +/- 0.156 per trade at n=125, reports/research/eth7c_retired_2026-10-31.md) are absent on purpose: never restarted
# non-trader runs: restarted the same way, but kept out of ACTIVE because the dashboard reads ACTIVE runs' trader.db
EXTRA = {}   # non-trader runs (none since the weather run was retired, 15 Nov)
CYCLE_S, BACKOFF_S, BACKOFF_MAX_S, HEALTHY_S = 60, 600, 3600, 3600
RESUME_S = 600   # > feed_resume.TOKEN_MS + a trader minute: one live reset token per pause
PS = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "ops" / "paper_tasks.ps1")]
# shortcut: a run alive but hung (event loop stuck) is not detected or killed; none seen so far, add a latency-row
# age check and a process-tree kill if one appears
# shortcut: backoff state is in memory, so a keeper restart gives each dead run one immediate retry
# shortcut: nothing restarts the keeper itself before the next logon (a 30-min `keep` task would; the lock makes it safe)


def matches(cmd: list[str], run: str, bat: str) -> bool:
    """A process belongs to run: its cmd wrapper (alive through the drills crawl) or its trader.loop --dir. Whole
    tokens, so paper_v4 never matches paper_v4b."""
    if any(f"ops\\{bat}" in c for c in cmd):
        return True
    return "trader.loop" in cmd and "--dir" in cmd[:-1] and PureWindowsPath(cmd[cmd.index("--dir") + 1]).name == run


def ended(run: str) -> bool | None:
    """True when the run's ledger ends with a clean runs_end; None when the db cannot be read (skip this cycle)."""
    db = ROOT / "data" / "trader" / run / "trader.db"
    if not db.exists():
        return False
    try:
        con = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True, timeout=5)
        try:
            m = dict(con.execute("SELECT tbl, MAX(recorded_ms) FROM rows WHERE tbl IN ('runs', 'runs_end') GROUP BY tbl"))
        finally:
            con.close()
    except sqlite3.Error:
        return None
    return (m.get("runs_end") or 0) > (m.get("runs") or 0)


def decide(now: float, running: bool, done: bool, s: dict) -> str:
    if running:
        return "ok"
    return "done" if done else "wait" if now < s["next"] else "start"


def ps(action: str) -> int:
    try:
        return subprocess.run(PS + [action], cwd=ROOT, timeout=180, creationflags=subprocess.CREATE_NO_WINDOW).returncode
    except subprocess.TimeoutExpired:
        return -1


def note(msg: str) -> None:
    """Same file and format as the ps1's Note; never raises (a ps1 Out-File pipeline can hold the log open)."""
    line = f"{dt.datetime.now():%Y-%m-%dT%H:%M:%S} [keep] {msg}"
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        print(line, flush=True)


def cycle(st: dict, now: float, procs=None, run_ps=ps) -> None:
    procs = procs if procs is not None else [p.info["cmdline"] or [] for p in psutil.process_iter(["cmdline"])]
    if not any("trader.feedhub" in cmd for cmd in procs):   # the exact -m token: a command that merely mentions it is no hub
        note(f"feed hub down; hub (exit {run_ps('hub')})")   # runs wait a cycle for the relay
        return
    if now - st["_resume"] >= RESUME_S:
        st["_resume"] = now
        run_ps("resume")
    started = False
    for r, (action, bat) in (ACTIVE | EXTRA).items():
        done = ended(r)
        if done is None:
            continue
        s = st.setdefault(r, {"fails": 0, "next": 0.0, "said": None})
        running = any(matches(cmd, r, bat) for cmd in procs)
        v = decide(now, running, done, s)
        if v == "start" and not started:
            started, s["fails"] = True, s["fails"] + 1
            wait = min(BACKOFF_MAX_S, BACKOFF_S * 2 ** (s["fails"] - 1))
            s["next"] = now + wait
            capped = wait == BACKOFF_MAX_S and s["said"] != "cap"
            note(f"{r} not running; {action} (try {s['fails']}, exit {run_ps(action)})"
                 + (f"; retrying hourly now, look at data\\trader\\{r}_console.log" if capped else ""))
            s["said"] = "cap" if wait == BACKOFF_MAX_S else s["said"]
        elif v == "done" and s["said"] != "done":
            s["said"] = "done"
            note(f"{r} finished cleanly (runs_end); not restarting")
        elif v == "ok":
            s.setdefault("up", now)
            if now - s["up"] > HEALTHY_S:   # an hour up: the next failure starts the backoff afresh
                s["fails"], s["said"] = 0, None
        if v != "ok":
            s.pop("up", None)


def sample_net() -> None:
    """Append this PC's cumulative received/sent bytes (all processes, all adapters); never raises."""
    try:
        n = psutil.net_io_counters()
        with open(NET_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": int(time.time()), "recv": n.bytes_recv, "sent": n.bytes_sent}) + "\n")
    except OSError:
        pass


def main() -> int:
    lock = open(ROOT / "data" / "trader" / "keeper.lock", "a+")
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        print("keeper already running", flush=True)
        return 0
    st = {r: {"fails": 0, "next": 0.0, "said": None} for r in ACTIVE | EXTRA} | {"_resume": 0.0}
    note("keeper up")
    while True:
        sample_net()
        try:
            cycle(st, time.time())
        except Exception as e:  # noqa: BLE001 - one bad minute never stops the keeper
            note(f"cycle error {e!r}")
            traceback.print_exc()
        t = time.time()
        time.sleep(CYCLE_S)
        if time.time() - t > CYCLE_S + 60:
            note(f"woke after {int(time.time() - t) // 60} min")


if __name__ == "__main__":
    raise SystemExit(main())
