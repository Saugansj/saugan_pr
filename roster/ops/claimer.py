"""Auto-claim (15 Nov): redeem winning positions of resolved markets into pUSD, in the same wallet, gasless via
Polymarket's relayer (official SDK `polymarket-client`, installed in its own venv because it pins older websockets and
eth-account than the trader uses).

    .venv-claim\\Scripts\\python.exe ops\\claimer.py               # dry run: list what would be claimed, nothing sent
    .venv-claim\\Scripts\\python.exe ops\\claimer.py --live --once # claim what is claimable now, then exit
    .venv-claim\\Scripts\\python.exe ops\\claimer.py --live        # every 2 min (ops\\start_live_v4.ps1 starts this)

Claims only: it never trades, transfers or approves anything. Each winner is redeemed one at a time and confirmed before
the next (the relayer allows 25 submits a minute). A failed claim is retried after RETRY_S. Every attempt is logged to
data/trader/claims.jsonl (the live page reads it). Credentials come from the environment, never from arguments or logs:
POLY_PRIVATE_KEY, POLY_FUNDER (the deposit wallet), POLY_API_KEY/SECRET/PASSPHRASE (existing CLOB credentials, so
nothing new is derived), RELAYER_API_KEY and RELAYER_API_KEY_ADDRESS (tools/live_tools/setup_relayer_key.py).
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import time
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import common  # noqa: E402 - stdlib only, safe in the claim venv

LOG = common.DATA / "trader" / "claims.jsonl"
POSITIONS = "https://data-api.polymarket.com/v2/positions"
INTERVAL_S, RETRY_S, MIN_VALUE = 120, 600, 0.01   # losers (value 0) are not worth a relayer call
NEEDED = ("POLY_PRIVATE_KEY", "POLY_FUNDER", "POLY_API_KEY", "POLY_API_SECRET", "POLY_API_PASSPHRASE",
          "RELAYER_API_KEY", "RELAYER_API_KEY_ADDRESS")


def fetch_redeemable(wallet: str, get=common.get_json, pages: int = 20) -> list[dict]:
    """Every REDEEMABLE position row of the wallet (data API v2, cursor pages)."""
    rows, cursor = [], None
    for _ in range(pages):
        q = {"user": wallet, "status": "REDEEMABLE", "limit": 500, **({"cursor": cursor} if cursor else {})}
        page = get(f"{POSITIONS}?{urllib.parse.urlencode(q)}")
        data = page.get("data", []) if isinstance(page, dict) else page
        rows += data or []
        cursor = (page.get("pagination") or {}).get("next_cursor") if isinstance(page, dict) else None
        if not cursor or not data:
            break
    return rows


def claimable(rows: list[dict]) -> dict[str, dict]:
    """{condition_id: {value, shares, title, outcome}} for winners worth claiming (value >= MIN_VALUE)."""
    out: dict[str, dict] = {}
    for r in rows:
        value = float(r.get("current_value") or 0)
        if value < MIN_VALUE or not r.get("condition_id"):
            continue
        c = out.setdefault(r["condition_id"], {"value": 0.0, "shares": 0.0, "title": r.get("title") or "",
                                               "outcome": r.get("outcome") or ""})
        c["value"] += value
        c["shares"] += float(r.get("current_size") or 0)
    return out


def log(e: dict, path: pathlib.Path = LOG) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": common.now_ms(), **e}, separators=(",", ":")) + "\n")


def make_client(env=None):
    """The SDK's SecureClient for the deposit wallet, with the existing CLOB credentials and the relayer key."""
    from polymarket import ApiKeyCreds, RelayerApiKey, SecureClient
    env = os.environ if env is None else env
    missing = [k for k in NEEDED if not env.get(k)]
    if missing:
        raise SystemExit(f"claimer: missing environment variable(s): {', '.join(missing)} "
                         "(run tools\\live_tools\\setup_relayer_key.py for the relayer key, then open a new window)")
    creds = ApiKeyCreds.model_validate({"apiKey": env["POLY_API_KEY"], "secret": env["POLY_API_SECRET"],
                                        "passphrase": env["POLY_API_PASSPHRASE"]})
    return SecureClient.create(private_key=env["POLY_PRIVATE_KEY"], wallet=env["POLY_FUNDER"], credentials=creds,
                               api_key=RelayerApiKey(key=env["RELAYER_API_KEY"], address=env["RELAYER_API_KEY_ADDRESS"]))


def run_once(wallet: str, client_factory, get=common.get_json, tried: dict | None = None, path: pathlib.Path = LOG,
             now_s=time.time, out=print) -> dict:
    """One pass: claim every claimable winner not tried in the last RETRY_S. Returns {claimed, failed, waiting}."""
    tried = {} if tried is None else tried
    todo = {cid: c for cid, c in claimable(fetch_redeemable(wallet, get)).items()
            if now_s() - tried.get(cid, -1e18) >= RETRY_S}
    res, client = {"claimed": 0, "failed": 0, "waiting": len(todo)}, None
    for cid, c in todo.items():
        tried[cid] = now_s()
        label = f"{c['title'][-45:]} | {c['outcome']} | {c['shares']:.2f} shares ~ ${c['value']:.2f}"
        try:
            client = client or client_factory()
            outcome = client.redeem_positions(condition_id=cid, metadata="roster auto-claim").wait()
            log({"cid": cid, "ok": True, "value": round(c["value"], 4), "shares": round(c["shares"], 4),
                 "title": c["title"], "outcome": c["outcome"], "tx": str(getattr(outcome, "transaction_hash", ""))}, path)
            out(f"claimed {label} tx {getattr(outcome, 'transaction_hash', '')}")
            res["claimed"] += 1
        except SystemExit:
            raise
        except Exception as e:  # noqa: BLE001 - log, retry after RETRY_S; never stop the loop on one market
            log({"cid": cid, "ok": False, "value": round(c["value"], 4), "title": c["title"],
                 "error": f"{type(e).__name__}: {str(e)[:200]}"}, path)
            out(f"claim failed {label}: {type(e).__name__}: {str(e)[:120]}")
            res["failed"] += 1
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Claim winning positions into pUSD (gasless, same wallet).")
    ap.add_argument("--live", action="store_true", help="really claim (without it: list what would be claimed)")
    ap.add_argument("--once", action="store_true", help="one pass, then exit")
    ap.add_argument("--interval", type=int, default=INTERVAL_S)
    ap.add_argument("--log", type=pathlib.Path, default=LOG,
                    help="claims jsonl path (per-account when two live wallets run in parallel)")
    a = ap.parse_args(argv)
    wallet = os.environ.get("POLY_FUNDER")
    if not wallet:
        raise SystemExit("claimer: POLY_FUNDER (the deposit wallet) is not set in this window")
    path = a.log
    if not a.live:
        c = claimable(fetch_redeemable(wallet))
        print(f"dry run: {len(c)} claimable market(s), ${sum(x['value'] for x in c.values()):.2f} in total")
        for cid, x in c.items():
            print(f"  {x['title'][-50:]} | {x['outcome']} | {x['shares']:.2f} shares ~ ${x['value']:.2f}")
        return 0
    tried: dict = {}
    print(f"claimer started {dt.datetime.now():%H:%M:%S}: every {a.interval} s, winners only, log {path}", flush=True)
    while True:
        try:
            r = run_once(wallet, make_client, tried=tried, path=path)
            if r["claimed"] or r["failed"]:
                print(f"{dt.datetime.now():%H:%M:%S} claimed {r['claimed']}, failed {r['failed']}", flush=True)
        except SystemExit:
            raise
        except Exception as e:  # noqa: BLE001 - data API down etc.: try again next round
            print(f"{dt.datetime.now():%H:%M:%S} claim round skipped: {type(e).__name__}", flush=True)
        if a.once:
            return 0
        time.sleep(a.interval)


if __name__ == "__main__":
    sys.exit(main())
