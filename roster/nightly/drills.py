"""Restart drills (build-plan 1.20): 5 forced restarts of a live paper run, each followed by a clean reconcile.

  ROSTER_HUMAN_KEY=... python -m nightly.drills [--dir data/trader/drills]     # writes reports/phase1_drills.md
  python -m nightly.drills keys > keys.jsonl          # clearance keys to sign for a paper drill or smoke folder
  python -m nightly.drills --dir <dir> report         # rewrite the report from <dir>/drills.json

Plan: kill -9 at a random moment, kill -9 mid-batch, a clean stop, kill -9 at a random moment, kill -9 mid-batch, then
a final run whose startup reconciles the last one. kill -9 is Popen.kill(), i.e. TerminateProcess on Windows: no
cleanup, no flush, no atexit. Mid-batch: the child (this module's `child` command) arms a hook that terminates its own
process the same way right after the first order of a multi-order batch is fsync'd to the journal, before any ack.
The production loop carries no drill code. After every stop the drill replays the journal itself; the next run's
startup (unknown orders cancelled by id, lost ledger fills backfilled, journal vs memory vs ledger fills) must report
zero mismatches. Trading needs signed clearances in <dir>/advice.db (python -m tools.clearance_cli --db ... sign).
"""
import argparse
import json
import os
import pathlib
import random
import signal
import subprocess
import sys
import time

import common
from trader.router import replay

PLAN = (("kill -9 at a random moment", "random"), ("kill -9 mid-batch", "midbatch"), ("clean stop", "clean"),
        ("kill -9 at a random moment", "random"), ("kill -9 mid-batch", "midbatch"))
MINUTES = {"random": 8, "midbatch": 8, "clean": 1.5, "final": 1.5}


def child(d: pathlib.Path, minutes: float, midbatch: bool) -> int:
    if midbatch:
        from trader import router
        batch, log = router.PaperRouter.submit_batch, router.PaperRouter._log
        armed = [False]

        def submit_batch(self, intents, now_ms):
            armed[0] = len(intents) >= 2
            try:
                return batch(self, intents, now_ms)
            finally:
                armed[0] = False

        def _log(self, e):
            log(self, e)
            if armed[0] and e["op"] == "new":
                print(f"DRILL kill -9 mid-batch: order {e['id'][:12]} journaled, batch not acknowledged", flush=True)
                os.kill(os.getpid(), getattr(signal, "SIGKILL", signal.SIGTERM))  # Windows: TerminateProcess

        router.PaperRouter.submit_batch, router.PaperRouter._log = submit_batch, _log
    from trader import loop
    return loop.main(["--paper", "--minutes", str(minutes), "--dir", str(d)])


def keys() -> str:
    """Clearance keys (JSONL) for every market the strategies trade, at both tick sizes so a tick change mid-run stays
    cleared: input for `tools.clearance_cli sign --keys`. Paper drills and smoke runs only; you sign real ones."""
    from trader.kernel import STRATEGIES, clearance_key
    from trader.marketdata import load_markets
    out = {}
    for m in load_markets()[0].values():
        if any(m.mode in s["modes"] and m.asset in s["sources"] for s in STRATEGIES.values()):
            for tick in (0.01, 0.001):
                k = {**clearance_key(m), "tick_size": tick}
                out[json.dumps(k, sort_keys=True)] = json.dumps({"key": k, "question": m.question})
    return "\n".join(out.values())


def _wait_for(log: pathlib.Path, text: str, p, timeout: float) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout and p.poll() is None:
        if text in log.read_text(encoding="utf-8", errors="replace"):
            return True
        time.sleep(1)
    return False


def _line(log: pathlib.Path, prefix: str) -> dict | None:
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(prefix):
            return json.loads(line[len(prefix):])
    return None


def journal_state(d: pathlib.Path) -> dict:
    j = d / "journal.jsonl"
    st = replay(j)
    raw = j.read_bytes() if j.exists() else b""
    return {"lines": raw.count(b"\n"), "torn_tail": bool(raw) and not raw.endswith(b"\n"),
            "orders": len(st.orders), "fills": len(st.fills),
            "unacked": sorted(o.order_id[:12] for o in st.orders.values() if o.status == "journaled"),
            "takers_in_flight": sum(o.intent.kind == "taker" and o.status in ("open", "partial") for o in st.orders.values()),
            "open_makers": sum(o.intent.kind == "maker" and o.status in ("open", "partial") for o in st.orders.values()),
            "positions": {t[:10]: s for t, s in st.positions.items() if abs(s) > 1e-9}}


def run_step(d: pathlib.Path, n: int, mode: str, rng: random.Random) -> dict:
    log = d / f"drill_{n}_{mode}.log"
    cmd = [sys.executable, "-m", "nightly.drills", "child", "--dir", str(d), "--minutes", str(MINUTES[mode])]
    if mode == "midbatch":
        cmd.append("--midbatch")
    with open(log, "w", encoding="utf-8") as f:
        p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=common.ROOT)
    t0 = time.time()
    started = _wait_for(log, "RUNNING", p, 300)
    killed_at = None
    if mode == "random" and started:
        until = time.time() + rng.uniform(20, 90)
        while time.time() < until and p.poll() is None:
            time.sleep(0.5)
        if p.poll() is None:
            killed_at = round(time.time() - t0, 1)
            p.kill()
    rc = p.wait(timeout=MINUTES[mode] * 60 + 600)
    text = log.read_text(encoding="utf-8", errors="replace")
    return {"step": n, "mode": mode, "exit": rc, "alive_s": round(time.time() - t0, 1), "killed_at_s": killed_at,
            "midbatch_fired": "DRILL kill -9 mid-batch" in text, "clean_shutdown": "SHUTDOWN " in text,
            "startup": _line(log, "RECONCILE "), "shutdown": _line(log, "SHUTDOWN "), "journal_after": journal_state(d),
            "log": log.name, "violations_logged": text.count("INVARIANT VIOLATION")}


def report(d: pathlib.Path, steps: list[dict]) -> str:
    rows, ok = [], True
    for kind_mode, s, nxt in zip(PLAN, steps, steps[1:]):
        kind, mode = kind_mode
        rec = nxt["startup"] or {}
        forced = (mode == "random" and s["killed_at_s"] is not None) or (mode == "midbatch" and s["midbatch_fired"]) \
            or (mode == "clean" and s["clean_shutdown"])
        clean = bool(nxt["startup"]) and rec.get("mismatches") == [] and nxt["violations_logged"] == 0
        ok &= forced and clean
        j = s["journal_after"]
        what = (f"killed {s['killed_at_s']} s after start" if mode == "random" else
                "killed itself after journaling the first order of a batch" if s["midbatch_fired"] else
                "stopped at its time limit" if s["clean_shutdown"] else "did not trigger")
        rows.append(f"| {s['step']} | {kind} | {what} (exit {s['exit']}) | {j['lines']} lines, {j['orders']} orders, "
                    f"{len(j['unacked'])} unacknowledged, {j['takers_in_flight']} takers in flight, {j['open_makers']} "
                    f"makers resting, torn tail {'yes' if j['torn_tail'] else 'no'} | {rec.get('unknown_resolved')} "
                    f"unknown cancelled, {rec.get('fills_backfilled')} fills backfilled, "
                    f"{len(rec.get('mismatches') or [])} mismatches | {'PASS' if forced and clean else 'FAIL'} |")
    fin = steps[-1]
    rel = d.relative_to(common.ROOT).as_posix()
    t0 = int((steps[0]["startup"] or {}).get("run_id", "0-0").split("-")[0]) / 1000 or time.time()
    untested = [what for what, key in (("a journaled fill missing from the ledger", "fills"),
                                       ("a taker in flight", "takers_in_flight"))
                if not any(s["journal_after"][key] for s in steps[:-1])]
    out = [
        "# Phase 1 restart drills (task 1.20)", "",
        f"Run {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(t0))} on this PC with live public feeds, paper only, data in "
        f"`{rel}/`. Five forced restarts, each followed by a startup reconcile in the next run.", "",
        f"**Verdict: {'PASS' if ok else 'FAIL'}.** "
        + ("Every restart was forced as planned and every next startup reconciled with zero mismatches."
           if ok else "At least one restart did not trigger as planned or did not reconcile cleanly; see the table."), "",
        "| # | Restart | What happened | Journal after the stop | Next startup reconcile | Result |",
        "|---|---|---|---|---|---|", *rows, "",
        f"Final run: startup {json.dumps(fin['startup'])}; shutdown "
        f"{json.dumps({k: (fin['shutdown'] or {}).get(k) for k in ('clean', 'mismatches', 'violations', 'open_orders', 'audit_records')})}.", "",
        "What each restart checks:",
        "- **kill -9** is `Popen.kill()`, which on Windows is TerminateProcess: no cleanup, no buffered writes, no atexit.",
        "- **mid-batch:** the child process terminates itself the same way right after the first order of a multi-order "
        "batch is fsync'd to the journal and before any acknowledgement. On restart that order replays as `unknown`, "
        "blocks new orders on its token and side, and is cancelled by id (never re-sent).",
        "- **startup reconcile** (trader/loop.py `start`): journal replay rebuilds every order, unknown orders are "
        "cancelled by id, fills on disk but missing from the ledger are written, then router memory, a fresh journal "
        "replay and the ledger's fills must agree on every order state and position. A mismatch would trip HALTED and "
        "count as an invariant violation.", ""]
    if untested:
        out += [f"Not exercised live in this drill (no such state existed at any stop): {' or '.join(untested)}. Both "
                "restart paths are covered on the real modules by tests/invariants "
                "(test_unknown_never_retried_and_journal_replay_after_crash).", ""]
    out += [
        "Per-step logs: " + ", ".join(f"`{s['log']}`" for s in steps) + f" in `{rel}/`; every step as JSON in "
        f"`{rel}/drills.json`.", "",
        "## How to reproduce", "",
        "```",
        "cd roster",
        "rem paper clearances for the drill folder, signed with a throwaway key that lives only in this shell",
        "set ROSTER_HUMAN_KEY=<any random string; your own key for real runs>",
        ".venv\\Scripts\\python.exe -m nightly.drills keys > keys.jsonl",
        f".venv\\Scripts\\python.exe -m tools.clearance_cli --db {rel}/advice.db sign --keys keys.jsonl --signer <you> --days 2",
        f".venv\\Scripts\\python.exe -m nightly.drills --dir {rel}",
        "```", ""]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("child")
    c.add_argument("--dir", type=pathlib.Path, required=True)
    c.add_argument("--minutes", type=float, required=True)
    c.add_argument("--midbatch", action="store_true")
    sub.add_parser("keys", help="print clearance keys to sign for a paper drill or smoke run")
    sub.add_parser("report", help="rewrite the report from <dir>/drills.json")
    ap.add_argument("--dir", type=pathlib.Path, default=common.DATA / "trader" / "drills")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--out", type=pathlib.Path, default=common.REPORTS / "phase1_drills.md")
    a = ap.parse_args(argv)
    from trader.loop import prefer_ipv4
    prefer_ipv4()
    if a.cmd == "child":
        return child(a.dir, a.minutes, a.midbatch)
    if a.cmd == "keys":
        print(keys())
        return 0
    d = a.dir.resolve()
    if a.cmd == "report":
        a.out.write_text(report(d, json.loads((d / "drills.json").read_text(encoding="utf-8"))), encoding="utf-8")
        print(f"wrote {a.out}")
        return 0
    d.mkdir(parents=True, exist_ok=True)
    rng = random.Random(a.seed)
    steps = []
    for n, (kind, mode) in enumerate(PLAN + (("final run", "final"),), 1):
        print(f"step {n}: {kind}", flush=True)
        steps.append(run_step(d, n, mode, rng))
        print(json.dumps(steps[-1]), flush=True)
    (d / "drills.json").write_text(json.dumps(steps, indent=1), encoding="utf-8")
    a.out.write_text(report(d, steps), encoding="utf-8")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
