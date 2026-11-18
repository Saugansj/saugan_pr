"""Prints a JSON snapshot of this repo's Claude Code sessions, read from their transcript tails.

Usage: python dashboard/sessions_snapshot.py [project_dir]   (default: current directory)
"""
import json
import os
import re
import sys
import time
from pathlib import Path

TAIL_BYTES = 600_000
MAX_AGE_S = 3 * 86400
MAX_SESSIONS = 6
RUNNING_MAX_AGE_S = 20 * 60  # a tool with no result older than this is a dead session, not a running one
TEST_CMD = re.compile(r"pytest|unittest|\btests?\b", re.I)
PASSED = re.compile(r"(\d+) passed")
FAILED = re.compile(r"(\d+) (failed|error)")


def transcript_dir(project):
    return Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(project))


def tail_records(path):
    with open(path, "rb") as f:
        size = f.seek(0, os.SEEK_END)
        f.seek(max(0, size - TAIL_BYTES))
        data = f.read().decode("utf8", errors="replace")
    lines = data.splitlines()
    if size > TAIL_BYTES:
        lines = lines[1:]  # first line is cut mid-record
    for line in lines:
        try:
            yield json.loads(line)
        except ValueError:
            continue


def describe(name, inp):
    if name == "Bash":
        return (inp.get("command") or "")[:90]
    if name in ("Read", "Edit", "Write"):
        return os.path.basename(inp.get("file_path") or "")
    return (inp.get("description") or inp.get("prompt") or inp.get("pattern") or "")[:90]


def result_text(content):
    if isinstance(content, list):
        content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    return str(content or "")


def summarise(path, now):
    title, last_prompt, calls, results = "", "", {}, {}
    for r in tail_records(path):
        kind = r.get("type")
        if kind == "custom-title":
            title = r.get("customTitle") or title
        elif kind == "last-prompt":
            last_prompt = r.get("lastPrompt") or last_prompt
        msg = r.get("message")
        content = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                inp = b.get("input") or {}
                calls[b["id"]] = {"tool": b["name"], "desc": describe(b["name"], inp),
                                  "cmd": inp.get("command") or "", "ts": r.get("timestamp", "")}
            elif b.get("type") == "tool_result":
                results[b.get("tool_use_id")] = (bool(b.get("is_error")), result_text(b.get("content")))
    age = now - path.stat().st_mtime
    events, tests = [], None
    for cid, c in calls.items():
        done = cid in results
        is_error, text = results.get(cid, (False, ""))
        events.append({"tool": c["tool"], "desc": c["desc"], "state": ("error" if is_error else "ok") if done else "running"})
        if done and c["tool"] == "Bash" and TEST_CMD.search(c["cmd"]):
            p, f = PASSED.search(text), FAILED.search(text)
            if p or f:
                tests = {"passed": int(p.group(1)) if p else 0, "failed": int(f.group(1)) if f else 0}
    running = [e for e in events if e["state"] == "running"] if age < RUNNING_MAX_AGE_S else []
    return {
        "id": path.stem[:8],
        "title": title or last_prompt[:60] or "(untitled)",
        "age_s": int(age),
        "state": "running" if running else "active" if age < 120 else "idle",
        "running": running,
        "recent": events[-6:],
        "calls": len(events),
        "errors": sum(e["state"] == "error" for e in events),
        "tests": tests,
    }


def snapshot(project):
    now = time.time()
    files = [p for p in transcript_dir(project).glob("*.jsonl") if now - p.stat().st_mtime < MAX_AGE_S]
    files.sort(key=lambda p: -p.stat().st_mtime)
    return {"sessions": [summarise(p, now) for p in files[:MAX_SESSIONS]]}


if __name__ == "__main__":
    print(json.dumps(snapshot(sys.argv[1] if len(sys.argv) > 1 else os.getcwd())))
