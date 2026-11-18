"""Named live accounts so two Polymarket wallets can run v4 in parallel on this PC.

  live    = the existing Windows-user POLY_* account (data/trader/live)
  live_b  = second Magic account; credentials only in %USERPROFILE%\\.roster_live_b.json (never HKCU, never the repo)

Setup live_b once:  .venv\\Scripts\\python.exe ops\\setup_live_b.py
Start either:       powershell -File ops\\start_live_v4.ps1 -Account live_b -DailyStop 0.35
"""
import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

# id -> paths and label. env_file None = use the process / Windows-user POLY_* already set for account A.
ACCOUNTS = {
    "live": {
        "label": "Account A",
        "dir": ROOT / "data" / "trader" / "live",
        "archive": ROOT / "data" / "trader" / "live_archive",
        "switch": ROOT / "trader" / "live" / "live.json",
        "claims": ROOT / "data" / "trader" / "claims.jsonl",
        "env_file": None,
    },
    "live_b": {
        "label": "winsorwills",
        "dir": ROOT / "data" / "trader" / "live_b",
        "archive": ROOT / "data" / "trader" / "live_b_archive",
        "switch": ROOT / "trader" / "live" / "live_b.json",
        "claims": ROOT / "data" / "trader" / "claims_b.jsonl",
        "env_file": pathlib.Path.home() / ".roster_live_b.json",
    },
}

POLY_KEYS = ("POLY_PRIVATE_KEY", "POLY_SIGNATURE_TYPE", "POLY_FUNDER", "POLY_ADDRESS",
             "POLY_API_KEY", "POLY_API_SECRET", "POLY_API_PASSPHRASE")
# optional; without them auto-claim stays off for that account
RELAYER_KEYS = ("RELAYER_API_KEY", "RELAYER_API_KEY_ADDRESS")


def get(account: str) -> dict:
    if account not in ACCOUNTS:
        raise SystemExit(f"unknown live account {account!r}; choose one of: {', '.join(ACCOUNTS)}")
    return ACCOUNTS[account]


def load_env_file(path: pathlib.Path) -> dict:
    """JSON object of POLY_* (and optional RELAYER_*) names -> values. Never prints values."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"missing credentials file {path}: run ops\\setup_live_b.py first") from None
    except ValueError as e:
        raise SystemExit(f"credentials file {path} is not JSON: {e}") from None
    if not isinstance(raw, dict):
        raise SystemExit(f"credentials file {path} must be a JSON object")
    return {k: str(v) for k, v in raw.items() if isinstance(v, (str, int, float)) and not str(k).startswith("_")}


def apply_account_env(account: str, env: dict | None = None) -> dict:
    """Return an env mapping with this account's POLY_* loaded (process-local; does not write HKCU).
    Also sets ROSTER_LIVE_JSON to this account's switch file so the three-flag guard is per-account.
    A file-backed account (live_b) does not inherit another wallet's RELAYER_* from Windows user env."""
    a = get(account)
    out = dict(os.environ if env is None else env)
    if a["env_file"] is not None:
        for k in RELAYER_KEYS:  # Account A's relayer must not claim Account B's wins
            out.pop(k, None)
        out.update(load_env_file(a["env_file"]))
    out["ROSTER_LIVE_JSON"] = str(a["switch"])
    out["ROSTER_LIVE_ACCOUNT"] = account
    missing = [k for k in POLY_KEYS if not out.get(k)]
    if missing:
        raise SystemExit(f"account {account}: missing {', '.join(missing)}")
    return out


def switch_on(account: str) -> bool:
    try:
        return json.loads(get(account)["switch"].read_text(encoding="utf-8")).get("live") is True
    except (OSError, ValueError):
        return False
