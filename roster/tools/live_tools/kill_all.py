"""Home-PC kill switch (task 2.2): cancel every order under the L2 API credentials, then confirm zero open orders.

Self-contained and stdlib-only, so a copy runs on the home PC with no roster checkout. The home PC holds L2 credentials
only: POLY_ADDRESS, POLY_API_KEY, POLY_API_SECRET, POLY_API_PASSPHRASE from the environment. It refuses to run if
POLY_PRIVATE_KEY is set.

  python kill_all.py                          dry run: prints what it would send, no network call (exit 2)
  python kill_all.py --live --config live.json  with ROSTER_LIVE=1 and {"live": true} in the config: the real thing

Exit: 0 zero open orders confirmed, 1 not confirmed within 15 s, 2 dry run (a guard flag missing), 3 refused (credential problem,
or a --host that is neither https nor loopback).
Prints counts and statuses only: never a credential value, a header value or a response body.
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

L2 = ("POLY_ADDRESS", "POLY_API_KEY", "POLY_API_SECRET", "POLY_API_PASSPHRASE")
HOST = "https://clob.polymarket.com"
CANCEL_ALL, ORDERS = "/cancel-all", "/data/orders"
END_CURSOR = "LTE="
DEFAULT_CONFIG = pathlib.Path(__file__).resolve().parent.parent.parent / "trader" / "live" / "live.json"
HEADERS = ("POLY_ADDRESS", "POLY_SIGNATURE", "POLY_TIMESTAMP", "POLY_API_KEY", "POLY_PASSPHRASE")
RETRY_S, BUDGET_S, MAX_PAGES = 2, 15, 100


def signature(secret_b64: str, ts: int, method: str, path: str, body: str = "") -> str:
    """Polymarket L2 HMAC: urlsafe-b64(HMAC-SHA256(urlsafe_b64decode(secret), ts + METHOD + path + body))."""
    mac = hmac.new(base64.urlsafe_b64decode(secret_b64), f"{ts}{method}{path}{body}".encode(), hashlib.sha256)
    return base64.urlsafe_b64encode(mac.digest()).decode()


def l2_headers(env, method: str, path: str, ts: int) -> dict:
    return dict(zip(HEADERS, (env["POLY_ADDRESS"], signature(env["POLY_API_SECRET"], ts, method, path), str(ts),
                              env["POLY_API_KEY"], env["POLY_API_PASSPHRASE"])))


def http(method: str, url: str, headers: dict, timeout: float = 5):
    """(status, parsed JSON or None). Network errors raise."""
    req = urllib.request.Request(url, method=method, headers={**headers, "User-Agent": "roster-kill/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    try:
        return status, json.loads(raw or b"null")
    except ValueError:
        return status, None


def config_live(path) -> bool:
    try:
        cfg = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(cfg, dict) and cfg.get("live") is True


def open_count(host, env, transport, wall) -> int | None:
    """Open orders over every page of GET /data/orders, or None if any page failed."""
    n, cursor = 0, "MA=="
    for _ in range(MAX_PAGES):
        status, body = transport("GET", f"{host}{ORDERS}?{urllib.parse.urlencode({'next_cursor': cursor})}",
                                 l2_headers(env, "GET", ORDERS, int(wall())))
        if status != 200 or not isinstance(body, dict) or not isinstance(body.get("data"), list):
            print(f"open orders: status {status}, unreadable")
            return None
        n += len(body["data"])
        cursor = body.get("next_cursor") or END_CURSOR
        if cursor == END_CURSOR:
            return n
    return None


def main(argv=None, env=None, transport=http, wall=time.time, mono=time.monotonic, sleep=time.sleep) -> int:
    ap = argparse.ArgumentParser(description="Cancel every Polymarket order under the L2 credentials in the env.")
    ap.add_argument("--live", action="store_true", help="one of the three live flags")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG), help='JSON file that must contain "live": true')
    ap.add_argument("--host", default=HOST, help="CLOB host (tests point this at a local fake)")
    a = ap.parse_args(argv)
    env = os.environ if env is None else env
    if "POLY_PRIVATE_KEY" in env:
        print("refusing: POLY_PRIVATE_KEY is set; the home PC holds L2 credentials only", file=sys.stderr)
        return 3
    missing = [k for k in L2 if not env.get(k)]
    if missing:
        print(f"refusing: missing environment variable(s) {', '.join(missing)}", file=sys.stderr)
        return 3
    u = urllib.parse.urlsplit(a.host)
    if u.scheme != "https" and not (u.scheme == "http" and u.hostname in ("127.0.0.1", "localhost", "::1")):
        print("refusing: --host must be https (plain http only to loopback, for a local fake)", file=sys.stderr)
        return 3
    try:
        base64.urlsafe_b64decode(env["POLY_API_SECRET"])
    except ValueError:
        print("refusing: POLY_API_SECRET is not valid base64", file=sys.stderr)
        return 3
    flags = {"--live": a.live, "ROSTER_LIVE=1": env.get("ROSTER_LIVE") == "1",
             f'"live": true in {a.config}': config_live(a.config)}
    off = [k for k, ok in flags.items() if not ok]
    if off:
        names = ", ".join(HEADERS)
        print(f"DRY RUN (missing: {'; '.join(off)}); no network call.\n"
              f"would send: DELETE {CANCEL_ALL} to {urllib.parse.urlsplit(a.host).hostname} with headers {names}\n"
              f"then: GET {ORDERS} (same headers) every {RETRY_S} s until zero open orders, for up to {BUDGET_S} s")
        return 2
    host, start = a.host.rstrip("/"), mono()
    while True:
        try:
            status, body = transport("DELETE", host + CANCEL_ALL, l2_headers(env, "DELETE", CANCEL_ALL, int(wall())))
            done = len(body.get("canceled") or []) if isinstance(body, dict) else "?"
            print(f"cancel-all: status {status}, canceled {done}")
            n = open_count(host, env, transport, wall)
        except (OSError, ValueError) as e:
            print(f"network error: {type(e).__name__}")
            n = None
        print(f"open orders: {'unknown' if n is None else n} at {mono() - start:.1f} s")
        if n == 0:
            print("CONFIRMED: zero open orders")
            return 0
        if mono() - start + RETRY_S > BUDGET_S:
            print(f"NOT CONFIRMED within {BUDGET_S} s: check the venue by hand", file=sys.stderr)
            return 1
        sleep(RETRY_S)


if __name__ == "__main__":
    sys.exit(main())
