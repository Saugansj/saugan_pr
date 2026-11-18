"""Advisor process entry point (WW-E): LLM gateway + clearance board (roles 27, 28) + role 25 sports sentinel.

  python -m advisor.run [--once] [--interval 60] [--backlog data/trader/uncleared.jsonl] [--news data/advisor/news.jsonl]
                        [--maps data/advisor/maps.json]

Fail closed: with no vendor key in env (GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY) it builds nothing, makes no
network call, writes nothing (no clearance, no gateway db) and exits 0 saying so.
With a key, every pass: when the backlog file changed, `board.agree` runs over it (the board signs clearances under
ROSTER_ADVISOR_KEY into data/advisor/llm_clearances.db, never advice.db); each new news line goes through
`Sentinel.on_news` and its CautionSignals are appended to --cautions; a vendor at 0 quota prints an AI-quota alarm.
Run one advisor process only: the gateway's quota has no inter-process lock.
"""
import argparse
import dataclasses
import json
import os
import pathlib
import time

from advisor import board
from advisor.gateway import DB as GATEWAY_DB
from advisor.gateway import VENDORS, LLMGateway
from advisor.sentinel import Sentinel
from common import DATA, append_jsonl
from trader.kernel import ADVICE_DB


def has_keys() -> bool:
    return any(os.environ.get(c["env"]) for c in VENDORS.values())


def main(argv=None, gateway=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass, then exit")
    ap.add_argument("--interval", type=float, default=60.0)
    ap.add_argument("--backlog", type=pathlib.Path, default=DATA / "trader" / "uncleared.jsonl")
    ap.add_argument("--snapshot", type=pathlib.Path, help="crawler JSONL (default: latest data/markets/*Z.jsonl)")
    ap.add_argument("--human-db", type=pathlib.Path, default=ADVICE_DB)
    ap.add_argument("--out", type=pathlib.Path, default=DATA / "advisor" / "agreement.md")
    ap.add_argument("--db", type=pathlib.Path, default=board.LLM_DB)
    ap.add_argument("--keys-out", type=pathlib.Path, default=board.KEYS_OUT)
    ap.add_argument("--gateway-db", type=pathlib.Path, default=GATEWAY_DB)
    ap.add_argument("--news", type=pathlib.Path, default=DATA / "advisor" / "news.jsonl")
    ap.add_argument("--maps", type=pathlib.Path, default=DATA / "advisor" / "maps.json")
    ap.add_argument("--cautions", type=pathlib.Path, default=DATA / "advisor" / "cautions.jsonl")
    a = ap.parse_args(argv)
    if gateway is None and not has_keys():
        print("advisor: no vendor key set (" + ", ".join(c["env"] for c in VENDORS.values())
              + "): nothing started, nothing written (fail closed)")
        return 0
    gw = gateway or LLMGateway(a.gateway_db)
    sentinel = Sentinel(gw, json.loads(a.maps.read_text(encoding="utf-8")) if a.maps.exists() else [])
    seen_backlog, news_done = None, 0  # ponytail: news offset in memory; a restart re-reads the file from the top
    while True:
        if any(v == 0 for v in gw.quota_left().values()):
            print(f"advisor: AI-quota alarm (role 36): {gw.quota_left()}", flush=True)
        if a.backlog.exists() and a.backlog.stat().st_size and a.backlog.stat().st_mtime_ns != seen_backlog:
            seen_backlog = a.backlog.stat().st_mtime_ns
            snaps = sorted((DATA / "markets").glob("*Z.jsonl"))
            snap = a.snapshot or (snaps[-1] if snaps else None)
            if snap:
                print("advisor: board", board.agree(a.backlog, snap, a.human_db, a.out, gw, db=a.db,
                                                    keys_out=a.keys_out), flush=True)
        if a.news.exists():
            lines = a.news.read_text(encoding="utf-8").splitlines()
            for i in range(news_done, len(lines)):
                try:
                    item = json.loads(lines[i])
                except ValueError:
                    if i == len(lines) - 1:
                        break  # torn last line: read it again next pass
                    item = None  # a bad line in the middle is skipped
                for sig, _refresh in (sentinel.on_news(item) if item else ()):
                    append_jsonl(a.cautions, dataclasses.asdict(sig))
                news_done = i + 1
        if a.once:
            return 0
        time.sleep(a.interval)


if __name__ == "__main__":
    raise SystemExit(main())
