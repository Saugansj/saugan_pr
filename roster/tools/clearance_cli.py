"""Clearance CLI (WP1-B, task 1.17). You, the human, sign clearance records and reset tokens into data/trader/advice.db.
The trader only reads that file (trader.kernel.load_advice opens it read-only).

Signing key: env ROSTER_HUMAN_KEY (the same key trader/ledger.py uses for promotions), or --key.

  # keys the kernel saw without a clearance (RiskKernel.dump_uncleared writes data/trader/uncleared.jsonl)
  python -m tools.clearance_cli sign --keys data/trader/uncleared.jsonl --signer NAME --days 7
  # reset a breaker trip ("global", a cid, an event group or a strategy)
  python -m tools.clearance_cli token --scope global --signer NAME
  python -m tools.clearance_cli list

A clearance key is (template, rules_sha256, fee_rate, tick_size, min_size, neg_risk, source_id); the kernel accepts a
record only while every field equals the market's latest MarketInfo, so a tick, fee or rules change needs a new signature.
"""
import argparse
import datetime
import json
import os
import pathlib
import secrets
import sqlite3
import sys

from common import now_ms
from trader.kernel import ADVICE_DB, KEY_FIELDS, load_advice, sign, verify


def write(db: pathlib.Path, rec: dict, key: str) -> dict:
    rec = {**rec, "nonce": secrets.token_hex(16), "signed_ms": now_ms()}
    rec["sig"] = sign(rec, key)
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    try:
        con.execute("CREATE TABLE IF NOT EXISTS advice (nonce TEXT PRIMARY KEY, type TEXT NOT NULL, rec TEXT NOT NULL)")
        con.execute("INSERT INTO advice VALUES (?, ?, ?)", (rec["nonce"], rec["type"], json.dumps(rec, sort_keys=True)))
        con.commit()
    finally:
        con.close()
    return rec


def _iso(ms: int) -> str:
    return datetime.datetime.fromtimestamp(ms / 1000, datetime.UTC).strftime("%Y-%m-%dT%H:%MZ")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=pathlib.Path, default=ADVICE_DB)
    ap.add_argument("--key", default=None, help="signing key (default: env ROSTER_HUMAN_KEY)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sign", help="sign clearance records")
    s.add_argument("--keys", type=pathlib.Path, required=True, help="JSONL: a key dict per line, or {'key': {...}, ...}")
    s.add_argument("--signer", required=True)
    s.add_argument("--days", type=float, default=7.0)
    t = sub.add_parser("token", help="sign a one-use token, e.g. a breaker reset")
    t.add_argument("--scope", required=True)
    t.add_argument("--signer", required=True)
    t.add_argument("--action", default="reset")
    t.add_argument("--minutes", type=float, default=30.0)
    sub.add_parser("list", help="show signed records")
    a = ap.parse_args(argv)
    key = a.key if a.key is not None else os.environ.get("ROSTER_HUMAN_KEY", "")

    if a.cmd == "list":
        clear, other = load_advice(a.db)
        now = now_ms()
        for r in clear.values():
            ok = "ok" if verify(r, key) and r["expiry_ms"] > now else "INVALID" if not verify(r, key) else "expired"
            print(f"{ok:8} {r['key']['template']:28} rules {r['key']['rules_sha256'][:10]} tick {r['key']['tick_size']}"
                  f" source {r['key']['source_id']} by {r['signer']} until {_iso(r['expiry_ms'])}")
        for r in other:
            print(f"token    {r.get('type')} scope {r.get('scope')} by {r.get('signer')} until {_iso(r.get('expiry_ms', 0))}")
        return 0

    if not key:
        print("set ROSTER_HUMAN_KEY (or pass --key) to sign", file=sys.stderr)
        return 2
    if a.cmd == "token":
        rec = write(a.db, {"type": a.action, "scope": a.scope, "signer": a.signer,
                           "expiry_ms": now_ms() + int(a.minutes * 60_000)}, key)
        print(json.dumps(rec))
        return 0

    n = 0
    for line in a.keys.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        k = row.get("key", row)
        if sorted(k) != sorted(KEY_FIELDS):
            print(f"skipped (fields must be exactly {KEY_FIELDS}): {line[:120]}", file=sys.stderr)
            continue
        rec = write(a.db, {"type": "clearance", "key": k, "signer": a.signer,
                           "expiry_ms": now_ms() + int(a.days * 86_400_000)}, key)
        n += 1
        print(f"signed {k['template']} rules {k['rules_sha256'][:10]} tick {k['tick_size']} fee {k['fee_rate']} "
              f"source {k['source_id']} until {_iso(rec['expiry_ms'])}  e.g. {row.get('question', '')[:60]}")
    print(f"{n} clearance(s) written to {a.db}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
