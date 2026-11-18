"""Create (or re-derive) your Polymarket trading API keys from your wallet key, and save every variable the live trader
reads as a Windows user environment variable (HKCU\\Environment). Prints variable names only, never a value.

    .venv\\Scripts\\python.exe -m tools.live_tools.setup_keys

Asks (hidden input) for the wallet private key unless POLY_PRIVATE_KEY is already set, and for the signature type and
the Polymarket wallet address unless POLY_SIGNATURE_TYPE / POLY_FUNDER are set. One network call: the SDK's
create_or_derive_api_key (L1-signed; it places no order). Running it again re-derives the same keys.

Never sets ROSTER_LIVE: set system-wide it would make every paper run refuse to start (trader/router.py LIVE_ENV).
Open a new terminal afterwards; terminals already open keep their old environment.
"""
import getpass
import os
import re
import sys

from trader.live.clob import CHAIN, HOST, SDK_MISSING

TYPES = {"1": "you log in to Polymarket with email or Google",
         "2": "you log in with a browser wallet such as MetaMask",
         "0": "the key's own address holds the pUSD (no Polymarket wallet)"}
ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}")


def save_user_env(values: dict) -> None:
    import ctypes
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as k:
        for name, v in values.items():
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, v)
    # WM_SETTINGCHANGE "Environment" so terminals opened from now on see the new values
    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x1A, 0, "Environment", 0x2, 5000, ctypes.byref(ctypes.c_ulong()))


def main(env=None, ask=input, ask_secret=getpass.getpass, client_cls=None, save=save_user_env, out=print) -> int:
    env = os.environ if env is None else env
    if client_cls is None:
        try:
            from py_clob_client_v2.client import ClobClient as client_cls
        except ImportError:
            out(SDK_MISSING)
            return 2
    from eth_account import Account
    new = {}
    key = env.get("POLY_PRIVATE_KEY") or ask_secret("Wallet private key (input hidden): ").strip()
    try:
        address = Account.from_key(key).address
    except Exception:  # noqa: BLE001 - its message could echo the key
        out("That is not a valid private key (64 hex characters, with or without 0x). Nothing was saved.")
        return 1
    if not env.get("POLY_PRIVATE_KEY"):
        new["POLY_PRIVATE_KEY"] = key
    st = env.get("POLY_SIGNATURE_TYPE")
    if not st:
        for k, v in TYPES.items():
            out(f"  {k} = {v}")
        st = ask("Signature type [1]: ").strip() or "1"
        if st not in TYPES:
            out(f"Signature type must be one of {', '.join(TYPES)}. Nothing was saved.")
            return 1
        new["POLY_SIGNATURE_TYPE"] = st
    funder = env.get("POLY_FUNDER")
    if not funder and st != "0":
        funder = ask("Polymarket wallet address (0x..., on polymarket.com under your profile / Deposit): ").strip()
        if not ADDRESS.fullmatch(funder):
            out("That is not a 0x address of 40 hex characters. Nothing was saved.")
            return 1
        new["POLY_FUNDER"] = funder
    try:
        creds = client_cls(HOST, CHAIN, key=key, signature_type=int(st), funder=funder or None) \
            .create_or_derive_api_key()
    except Exception as e:  # noqa: BLE001
        out(f"Polymarket refused the key request ({type(e).__name__}: {str(e).replace(key, '***')[:200]}). "
            "Nothing was saved.")
        return 1
    new.update(POLY_ADDRESS=address, POLY_API_KEY=creds.api_key, POLY_API_SECRET=creds.api_secret,
               POLY_API_PASSPHRASE=creds.api_passphrase)
    save(new)
    out("Saved as user environment variables: " + ", ".join(sorted(new)))
    out("Open a NEW terminal, then run: .venv\\Scripts\\python.exe -m tools.live_tools.doctor --step wallet ...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
