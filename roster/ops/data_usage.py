"""Today's data consumption and every running roster item (the /data-usage command of the data-usage mod).

- This PC's network use today (all processes): data/trader/net_usage.jsonl, the keeper's per-minute samples of the
  adapter counters. Counters restart at a reboot; a sample lower than the one before is read as counting from zero.
- The feed hub's own internet download today (all market feeds of the speed runs): its meter, the latest
  `hub data:` line in feedhub_console.log; earlier days from data_meter.jsonl.
- Running items: hub, keeper, each paper run (loop alive = its newest ledger latency row), research loop,
  archive downloaders, with uptime, CPU and memory; active runs that are not running are listed as missing.

  .venv\\Scripts\\python.exe ops\\data_usage.py
"""
import datetime as dt
import importlib.util
import json
import pathlib
import re
import sqlite3
import sys
import time

import psutil

ROOT = pathlib.Path(__file__).resolve().parents[1]
T = ROOT / "data" / "trader"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def day_usage(samples: list[dict], start_s: int, end_s: int) -> dict:
    """Bytes received/sent between consecutive samples whose later one falls in [start_s, end_s), by IST hour."""
    out = {"recv": 0, "sent": 0, "samples": 0, "hours": {}, "from": None}   # from: the baseline the day's count starts at
    prev = None
    for s in sorted(samples, key=lambda x: x["t"]):
        if prev is not None and start_s <= s["t"] < end_s:
            d = {k: max(0, s[k] - prev[k]) for k in ("recv", "sent")}   # lower: counter reset (reboot or a Wi-Fi reset on wake, 22 Oct +31 GB phantom); count 0
            h = dt.datetime.fromtimestamp(s["t"], IST).hour
            out["recv"] += d["recv"]
            out["sent"] += d["sent"]
            out["hours"][h] = out["hours"].get(h, 0) + d["recv"] + d["sent"]
            out["samples"] += 1
            out["from"] = out["from"] or prev["t"]
        prev = s
    return out


def hub_today(log: pathlib.Path) -> tuple[float | None, str]:
    """(MB the hub downloaded today, its last data line) from the newest `hub data:` line."""
    try:
        with open(log, "rb") as f:
            f.seek(max(0, f.seek(0, 2) - 400_000))
            lines = [l for l in f.read().decode("utf-8", "replace").splitlines() if l.startswith("hub data:")]
    except OSError:
        return None, ""
    if not lines:
        return None, ""
    m = re.search(r"today (\d+(?:\.\d+)?) MB", lines[-1])
    return (float(m.group(1)) if m else None), lines[-1]


def label(cmd: list[str]) -> str | None:
    j = " ".join(cmd)
    if "trader.loop" in cmd and "--dir" in cmd[:-1]:
        return pathlib.PureWindowsPath(cmd[cmd.index("--dir") + 1]).name
    for key, name in (("trader.feedhub", "feed hub"), ("keeper.py", "keeper"), ("research.loop", "research loop"),
                      ("history.pm_fast", "archive download"), ("research.feeds.race", "feed race recorder")):
        if key in cmd or key in j:
            return name + (f" {cmd[-2]}..{cmd[-1]}" if key == "history.pm_fast" else "")
    return None


def running() -> dict:
    """label -> the process that does the work (the venv launcher's child: the bigger of the pair)."""
    procs = {}
    for p in psutil.process_iter(["cmdline", "name", "create_time", "memory_info"]):
        if "python" not in (p.info["name"] or "").lower() or not (lab := label(p.info["cmdline"] or [])):
            continue
        if lab not in procs or p.info["memory_info"].rss > procs[lab].info["memory_info"].rss:
            procs[lab] = p
    for p in procs.values():
        try:
            p.cpu_percent(None)
        except psutil.Error:
            pass
    time.sleep(1)
    return procs


def loop_age_s(run: str) -> int | None:
    db = T / run / "trader.db"
    try:
        con = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True, timeout=5)
        try:
            ms = con.execute("SELECT MAX(recorded_ms) FROM rows WHERE tbl = 'latency'").fetchone()[0]
        finally:
            con.close()
    except sqlite3.Error:
        return None
    return int(time.time() - ms / 1000) if ms else None


def active_runs() -> list[str]:
    spec = importlib.util.spec_from_file_location("keeper", ROOT / "ops" / "keeper.py")
    k = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(k)
    return list(k.ACTIVE)


def main() -> int:
    now = dt.datetime.now(IST)
    d0 = int(dt.datetime.combine(now.date(), dt.time(), IST).timestamp())
    try:
        samples = [json.loads(l) for l in (T / "net_usage.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    except OSError:
        samples = []
    u = day_usage(samples, d0, d0 + 86_400)
    gb = lambda b: f"{b / 1e9:.2f} GB" if b >= 1e9 else f"{b / 1e6:.0f} MB"
    out = [f"## Data consumption, {now:%d %b %Y} (IST, as of {now:%H:%M})", ""]
    if u["samples"]:
        out += [f"**This PC, all processes:** {gb(u['recv'] + u['sent'])} (download {gb(u['recv'])}, upload {gb(u['sent'])})"
                + ("" if u["from"] <= d0 else f", measured since {dt.datetime.fromtimestamp(u['from'], IST):%H:%M} (the keeper's "
                   "sampling began then)") + ". A PC sleep is still counted: the next sample covers it.", ""]
        top = sorted(u["hours"].items())
        out += ["| Hour | MB |", "|---|---|"] + [f"| {h:02d}:00 | {b / 1e6:.0f} |" for h, b in top] + [""]
    else:
        out += ["**This PC, all processes:** no samples yet today (the keeper writes one a minute to data/trader/net_usage.jsonl).", ""]
    mb, line = hub_today(T / "feedhub_console.log")
    mode = (T / "feedhub_mode.txt").read_text(encoding="utf-8").strip() if (T / "feedhub_mode.txt").exists() else "stream"
    out += [f"**Feed hub (all speed runs' market data), mode {mode}:** " + (f"{mb:.0f} MB downloaded today" if mb is not None
            else "no data meter line yet (the meter prints in poll mode)") + (f"; last: `{line}`" if line else ""), ""]
    try:
        hist = [json.loads(l) for l in (T / "data_meter.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()][-5:]
        if hist:
            out += ["Hub, earlier days: " + ", ".join(f"{h['day']} {h['mb']:.0f} MB" for h in hist), ""]
    except OSError:
        pass

    procs, act = running(), active_runs()
    out += ["## Running items", "", "| Item | Up since | CPU % | Memory MB | Loop alive |", "|---|---|---|---|---|"]
    for lab in sorted(procs, key=lambda x: (not x.startswith("paper"), x)):
        p = procs[lab]
        try:
            cpu, rss = p.cpu_percent(None), p.memory_info().rss / 2**20
        except psutil.Error:
            continue
        age = loop_age_s(lab) if lab.startswith("paper") else None
        up = dt.datetime.fromtimestamp(p.info["create_time"], IST).strftime("%d %b %H:%M")
        out.append(f"| {lab} | {up} | {cpu:.0f} | {rss:.0f} | {'' if age is None else f'{age} s ago'} |")
    missing = [r for r in act if r not in procs]
    out += ["", "**Missing (active but not running):** " + (", ".join(missing) if missing else "none")]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
