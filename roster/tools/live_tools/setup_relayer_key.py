"""Save the Polymarket Relayer API key for ops/claimer.py as Windows user environment variables (HKCU\\Environment):
RELAYER_API_KEY and RELAYER_API_KEY_ADDRESS. Create the key yourself on polymarket.com -> Settings -> API Keys ->
Relayer API Keys; the page shows the key and the address it belongs to. Run this in its own PowerShell window (the
key prompt is hidden). Prints variable names only, never a value.

    .venv\\Scripts\\python.exe -m tools.live_tools.setup_relayer_key
"""
import getpass
import re
import sys

from tools.live_tools.setup_keys import save_user_env

ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")


def main(ask=input, ask_secret=getpass.getpass, save=save_user_env, out=print) -> int:
    key = ask_secret("Relayer API key (hidden): ").strip()
    if len(key) < 8:
        out("That key looks too short; nothing saved.")
        return 2
    address = ask("Address shown next to the key on polymarket.com (0x...): ").strip()
    if not ADDRESS.match(address):
        out("That is not a 0x address with 40 hex characters; nothing saved.")
        return 2
    save({"RELAYER_API_KEY": key, "RELAYER_API_KEY_ADDRESS": address})
    out("Saved RELAYER_API_KEY and RELAYER_API_KEY_ADDRESS. Open a new PowerShell window before starting the live run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
