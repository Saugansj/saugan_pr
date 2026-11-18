"""One-shot: derive CLOB API keys for the second Magic account and save them outside the repo.

  .venv\\Scripts\\python.exe ops\\setup_live_b.py
  .venv\\Scripts\\python.exe ops\\setup_live_b.py --key 0x...     # non-interactive (input still hidden if omitted)

Writes %USERPROFILE%\\.roster_live_b.json only (never HKCU Environment — that stays Account A's).
Looks up the Polymarket proxy wallet from the Magic signer via gamma public-profile.
Does not start a live run. Relayer keys are optional later (auto-claim off until set).
"""
import argparse
import getpass
import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from trader.live.clob import CHAIN, HOST, SDK_MISSING  # noqa: E402

OUT = pathlib.Path.home() / ".roster_live_b.json"
GAMMA = "https://gamma-api.polymarket.com/public-profile?address="


def proxy_for(address: str) -> tuple[str, str]:
    """(proxyWallet, display name) for a Magic/email signer."""
    with urllib.request.urlopen(GAMMA + address, timeout=15) as r:
        p = json.loads(r.read())
    proxy = p.get("proxyWallet")
    if not proxy:
        raise SystemExit(f"gamma has no proxyWallet for {address}: is this a Magic/email Polymarket login?")
    return proxy, p.get("name") or p.get("pseudonym") or "live_b"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Save live_b Magic credentials to ~/.roster_live_b.json")
    ap.add_argument("--key", default=None, help="Magic wallet private key (omit to type hidden)")
    ap.add_argument("--funder", default=None, help="Polymarket proxy wallet (0x...); looked up from gamma if omitted")
    ap.add_argument("--label", default=None, help="dashboard label (default: gamma name or live_b)")
    # 18 Nov: Magic + this PC's Account A both need 3 for CLOB balance/orders (type 1 auths but returns $0)
    ap.add_argument("--sig", default="3", choices=("0", "1", "2", "3"), help="POLY_SIGNATURE_TYPE (default 3)")
    ap.add_argument("--out", type=pathlib.Path, default=OUT)
    a = ap.parse_args(argv)
    try:
        from py_clob_client_v2.client import ClobClient
        from eth_account import Account
    except ImportError:
        print(SDK_MISSING)
        return 2
    key = (a.key or getpass.getpass("Magic private key (hidden): ")).strip()
    try:
        address = Account.from_key(key).address
    except Exception:  # noqa: BLE001 - message must not echo the key
        print("That is not a valid private key. Nothing saved.")
        return 1
    if a.funder:
        funder, label = a.funder, a.label or "live_b"
    else:
        try:
            funder, label = proxy_for(address)
            if a.label:
                label = a.label
        except Exception as e:  # noqa: BLE001
            print(f"Could not look up proxy wallet ({type(e).__name__}: {e}). Pass --funder 0x... Nothing saved.")
            return 1
    sig = int(a.sig)
    try:
        creds = ClobClient(HOST, CHAIN, key=key, signature_type=sig, funder=funder).create_or_derive_api_key()
    except Exception as e:  # noqa: BLE001
        print(f"Polymarket refused API key derive ({type(e).__name__}). Nothing saved.")
        return 1
    payload = {
        "label": label,
        "POLY_PRIVATE_KEY": key,
        "POLY_SIGNATURE_TYPE": str(sig),
        "POLY_FUNDER": funder,
        "POLY_ADDRESS": address,
        "POLY_API_KEY": creds.api_key,
        "POLY_API_SECRET": creds.api_secret,
        "POLY_API_PASSPHRASE": creds.api_passphrase,
    }
    a.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    try:
        a.out.chmod(0o600)
    except OSError:
        pass
    print(f"Saved {a.out}")
    print(f"  label   {label}")
    print(f"  signer  {address}")
    print(f"  funder  {funder}")
    print(f"  api_key {creds.api_key[:8]}…")
    print("Account A's Windows POLY_* env is untouched. Start with:")
    print("  powershell -ExecutionPolicy Bypass -File ops\\start_live_v4.ps1 -Account live_b -DailyStop 0.35")
    return 0


if __name__ == "__main__":
    sys.exit(main())
