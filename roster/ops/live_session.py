"""Live-session bookkeeping for ops/start_live_v4.ps1 (12 Nov; multi-account 18 Nov).

The live loop's cash = --cash + every fill and payout in its journal since the journal began, so --cash must be the
wallet balance at the journal's start. The launcher therefore starts each session on a fresh journal: the previous
session's folder is archived once all its bets have settled, and --cash is the wallet balance read here.

  python ops/live_session.py check [--account live|live_b]
  python ops/live_session.py archive [--account live|live_b]
  python ops/live_session.py balance [--account live|live_b]
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import sqlite3
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ops.live_accounts import apply_account_env, get  # noqa: E402


def unsettled(d: pathlib.Path, get_json=None) -> dict[str, float]:
    """Tokens the journal still holds whose market is not settled: {token: shares}."""
    from trader.router import replay
    st = replay(d / "journal.jsonl")
    held = {t: n for t, n in st.positions.items() if abs(n) > 1e-9}
    db = d / "trader.db"
    if held and db.exists():
        con = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True, timeout=5)
        try:
            for (b,) in con.execute("SELECT body FROM rows WHERE tbl = 'settlements'"):
                held.pop(json.loads(b).get("token_id"), None)
        finally:
            con.close()
    if held:
        import common
        get_json = get_json or common.get_json
        cids = {o.intent.cid for o in st.orders.values() if o.intent.token_id in held}
        for cid in cids:
            try:
                m = get_json(f"https://clob.polymarket.com/markets/{cid}")
            except Exception:  # noqa: BLE001
                continue
            if any(t.get("winner") for t in m.get("tokens") or []):
                for t in m.get("tokens") or []:
                    held.pop(t.get("token_id"), None)
    return held


def archive(d: pathlib.Path, archive_root: pathlib.Path, now: dt.datetime | None = None) -> pathlib.Path | None:
    """Move a finished session's folder aside (None if there is nothing to archive). Refuses with open bets."""
    if not (d / "journal.jsonl").exists() or (d / "journal.jsonl").stat().st_size == 0:
        return None
    if left := unsettled(d):
        raise SystemExit(f"{len(left)} bet(s) not settled yet: wait for them (5/15-min markets), then start again")
    dest = archive_root / f"{(now or dt.datetime.now()):%Y%m%d-%H%M%S}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    d.rename(dest)
    return dest


def carry_daily(src: pathlib.Path, dst: pathlib.Path, flow: float = 0.0, now: dt.datetime | None = None) -> dict | None:
    """18 Nov: keep the daily stop across relaunches. trader.breakers saves the day's start equity in the run folder
    (daily_start.json, UTC day) and re-reads it after a restart, but the launcher archives that folder at every start,
    so each relaunch began a fresh day at the new wallet balance (17 Nov: four fresh starts). This copies the archived
    session's mark into the new folder when it is for the current UTC day, moved by `flow` (USD deposited (+) or
    withdrawn (-) since that mark: a withdrawal must not read as a loss). The breaker then measures today's drawdown
    from the day's first start. Returns the carried mark, or None (nothing for today; the new session starts a day).
    The per-strategy marks (strategy_start.json) are carried only when flow is 0 (they are not cash-adjustable)."""
    day = str((now or dt.datetime.now(dt.UTC)).astimezone(dt.UTC).date())
    f = src / "daily_start.json"
    if not f.exists():
        return None
    saved = json.loads(f.read_text(encoding="utf-8"))
    if saved.get("day") != day or not isinstance(saved.get("mark"), (int, float)):
        return None
    out = {"day": day, "mark": round(float(saved["mark"]) + flow, 6), "carried_from": str(src), "flow": flow}
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "daily_start.json").write_text(json.dumps(out), encoding="utf-8")
    sf = src / "strategy_start.json"
    if flow == 0 and sf.exists() and json.loads(sf.read_text(encoding="utf-8")).get("day") == day:
        (dst / "strategy_start.json").write_text(sf.read_text(encoding="utf-8"), encoding="utf-8")
    return out


def balance(account: str = "live") -> float:
    """The wallet's pUSD via GET /balance-allowance. Uses a temp live switch so paper runs and the other account
    are untouched. Credentials are passed into L2Client only — os.environ is not rewritten (two accounts in one
    process must not bleed into each other)."""
    from trader.live.clob import L2Client
    env = apply_account_env(account)
    with tempfile.TemporaryDirectory() as tmp:
        cfg = pathlib.Path(tmp) / "live.json"
        cfg.write_text('{"live": true}', encoding="utf-8")
        client_env = {**env, "ROSTER_LIVE": "1", "ROSTER_LIVE_JSON": str(cfg)}
        c = L2Client(config_path=cfg, env=client_env, cli_live=True)
        q = {"asset_type": "COLLATERAL", "signature_type": int(client_env.get("POLY_SIGNATURE_TYPE") or 0)}
        try:
            c._req("GET", "/balance-allowance/update", query=q)
        except Exception:  # noqa: BLE001
            pass
        return int(c.balance_allowance().get("balance", 0)) / 1e6


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=("check", "archive", "balance"))
    ap.add_argument("--account", default="live", choices=("live", "live_b"))
    ap.add_argument("--carry-daily", action="store_true",
                    help="archive: keep today's (UTC) daily-stop start mark in the new session folder")
    ap.add_argument("--flow", type=float, default=0.0,
                    help="with --carry-daily: USD deposited (+) or withdrawn (-) since the day's first start")
    a = ap.parse_args(argv)
    acct = get(a.account)
    d, arch = acct["dir"], acct["archive"]
    if a.cmd == "check":
        if not (d / "journal.jsonl").exists():
            print("ok: no unsettled bets")
            return 0
        left = unsettled(d)
        print(f"{len(left)} unsettled bet(s)" if left else "ok: no unsettled bets")
        return 3 if left else 0
    if a.cmd == "archive":
        try:
            dest = archive(d, arch)
        except SystemExit as e:
            print(e)
            return 3
        print(f"archived previous session to {dest}" if dest else "no previous session to archive")
        if a.carry_daily and dest:
            c = carry_daily(dest, d, a.flow)
            print(f"daily stop carried: start of day {c['mark']:.2f} (UTC day {c['day']}, flow {a.flow:+.2f})" if c
                  else "daily stop: no mark for today in the archived session; today starts at this session's cash")
        return 0
    if a.cmd == "balance":
        print(f"{balance(a.account):.6f}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
