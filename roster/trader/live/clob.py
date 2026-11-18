"""Polymarket CLOB venue client for live execution (task 2.3, roles 05 and 14). Built now, wired later; no keys here.

Three-flag live guard: live is on only if trader/live/live.json holds "live": true (the JSON boolean), the environment
has ROSTER_LIVE=1 and the command line has --live. Every authenticated call checks it at call time (L2Client._req is
the only place that calls the transport, and it checks first; UserWS checks before every connect).

Credentials come from the environment at the moment of use and are never logged, printed, stored, or put in a repr or
an exception: L2 = POLY_ADDRESS, POLY_API_KEY, POLY_API_SECRET, POLY_API_PASSPHRASE; signing (trader process only) =
POLY_PRIVATE_KEY, optional POLY_FUNDER and POLY_SIGNATURE_TYPE.

L2 auth is the SDK's HMAC: urlsafe-b64(HMAC-SHA256(urlsafe_b64decode(secret), ts + METHOD + path + body)); the query
string is not signed (as py_clob_client_v2). The client never retries: retry decisions belong to the router.

Signing: SdkSigner imports py_clob_client_v2 lazily ([ops]: 1.2.0 in the trader user's venv). The order id is the
order's EIP-712 hash, computed locally before anything is sent; it is the id the CLOB uses, so an order whose ack was
lost can still be cancelled by id.

    research/spike/.venv/Scripts/python.exe -m trader.live.clob --signer-check   # one-off: our id == SDK EIP-712 hash, nothing posted
"""
import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

log = logging.getLogger(__name__)
HOST = "https://clob.polymarket.com"
USER_WS = "wss://ws-subscriptions-clob.polymarket.com/ws/user"
LIVE_JSON = pathlib.Path(__file__).resolve().parent / "live.json"
CHAIN = 137  # Polygon
L2 = ("POLY_ADDRESS", "POLY_API_KEY", "POLY_API_SECRET", "POLY_API_PASSPHRASE")
HEADERS = ("POLY_ADDRESS", "POLY_SIGNATURE", "POLY_TIMESTAMP", "POLY_API_KEY", "POLY_PASSPHRASE")
FIRST_CURSOR, END_CURSOR, MAX_PAGES = "MA==", "LTE=", 100
SDK_MISSING = "py-clob-client-v2 not installed: [ops] install 1.2.0 into the trader user's venv"


class LiveGuardError(RuntimeError):
    """A live flag is missing: nothing was sent."""


class CredentialsMissing(RuntimeError):
    """A credential variable is unset: nothing was sent. The message names the variable, never a value."""


class LiveUnavailable(RuntimeError):
    pass


class VenueError(RuntimeError):
    def __init__(self, status: int, body):
        super().__init__(f"venue HTTP {status}: {str(body)[:200]}")
        self.status, self.body = status, body


def live_switch_path(env=None) -> pathlib.Path:
    """Default live.json, or ROSTER_LIVE_JSON when a second account runs in parallel."""
    env = os.environ if env is None else env
    return pathlib.Path(env["ROSTER_LIVE_JSON"]) if env.get("ROSTER_LIVE_JSON") else LIVE_JSON


# ---- the three-flag guard -------------------------------------------------------------------------------------------
def live_enabled(config_path=None, env=None, cli_live=False) -> tuple[bool, list[str]]:
    """(on, missing flag names). Exactly: config "live" is the JSON true, env ROSTER_LIVE == "1", cli_live is True."""
    env = os.environ if env is None else env
    path = pathlib.Path(config_path) if config_path is not None else live_switch_path(env)
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cfg = None
    ok = {f'"live": true in {path.name}': isinstance(cfg, dict) and cfg.get("live") is True,
          "ROSTER_LIVE=1": env.get("ROSTER_LIVE") == "1",
          "--live": cli_live is True}
    missing = [k for k, v in ok.items() if not v]
    return not missing, missing


def require_live(config_path=None, env=None, cli_live=False) -> None:
    on, missing = live_enabled(config_path, env, cli_live)
    if not on:
        raise LiveGuardError("live trading is off; missing: " + ", ".join(missing))


# ---- credentials and L2 headers -------------------------------------------------------------------------------------
class Creds:
    __slots__ = ("address", "api_key", "secret", "passphrase")

    def __init__(self, address, api_key, secret, passphrase):
        self.address, self.api_key, self.secret, self.passphrase = address, api_key, secret, passphrase

    def __repr__(self):
        return "Creds(address=***, api_key=***, secret=***, passphrase=***)"

    @classmethod
    def from_env(cls, env=None) -> "Creds":
        env = os.environ if env is None else env
        missing = [k for k in L2 if not env.get(k)]
        if missing:
            raise CredentialsMissing("missing environment variable(s): " + ", ".join(missing))
        return cls(*(env[k] for k in L2))


def l2_headers(creds: Creds, method: str, path: str, body: str = "", ts: int | None = None) -> dict:
    ts = int(time.time()) if ts is None else int(ts)
    msg = f"{ts}{method}{path}" + (body or "").replace("'", '"')  # the SDK's quote normalisation, kept for parity
    sig = hmac.new(base64.urlsafe_b64decode(creds.secret), msg.encode(), hashlib.sha256).digest()
    return dict(zip(HEADERS, (creds.address, base64.urlsafe_b64encode(sig).decode(), str(ts), creds.api_key,
                              creds.passphrase)))


def http(method: str, url: str, headers: dict, body: str | None = None, timeout: float = 5.0):
    """(status, parsed JSON or None). Network errors and timeouts raise."""
    data = body.encode() if body else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        **headers, "User-Agent": "roster/0.1", **({"Content-Type": "application/json"} if data else {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    try:
        return status, json.loads(raw or b"null")
    except ValueError:
        return status, None


class KeepAlive:
    """http() over one kept-open HTTPS connection per host: an order skips the ~170-230 ms TCP + TLS setup that a new
    connection costs from the home PC (12 Oct measurement). The 5 s live heartbeat keeps it warm. Same contract as
    http(): (status, JSON or None), network errors raise, never a retry (a failed POST may have reached the venue; the
    router journals it unknown and reconciles). The connection is dropped on any error and before reuse after
    IDLE_S, so a socket the server may have closed is never written to."""
    IDLE_S = 30.0

    def __init__(self, connect=None, clock=time.monotonic):
        import http.client
        import threading
        self.connect = connect or (lambda host, timeout: http.client.HTTPSConnection(host, timeout=timeout))
        self.clock, self.conns, self.lock = clock, {}, threading.Lock()

    def __call__(self, method: str, url: str, headers: dict, body: str | None = None, timeout: float = 5.0):
        import socket
        u = urllib.parse.urlsplit(url)
        with self.lock:
            conn, used = self.conns.pop(u.netloc, (None, 0.0))
            if conn is not None and self.clock() - used > self.IDLE_S:
                conn.close()
                conn = None
            if conn is None:
                conn = self.connect(u.netloc, timeout)
                conn.connect()
                conn.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # small orders leave at once
            try:
                conn.sock.settimeout(timeout)
                data = body.encode() if body else None
                conn.request(method, u.path + (f"?{u.query}" if u.query else ""), body=data, headers={
                    **headers, "User-Agent": "roster/0.1", **({"Content-Type": "application/json"} if data else {})})
                r = conn.getresponse()
                status, raw = r.status, r.read()
            except BaseException:
                conn.close()
                raise
            if r.will_close:
                conn.close()
            else:
                self.conns[u.netloc] = (conn, self.clock())
        try:
            return status, json.loads(raw or b"null")
        except ValueError:
            return status, None


# ---- the client -----------------------------------------------------------------------------------------------------
class L2Client:
    def __init__(self, transport=None, host=HOST, config_path=None, env=None, cli_live=False, timeout=5.0,
                 wall=time.time):
        self.transport, self.host, self.timeout, self.wall = transport or KeepAlive(), host.rstrip("/"), timeout, wall
        self.env, self.cli_live = env, cli_live
        self.config_path = pathlib.Path(config_path) if config_path is not None else live_switch_path(self._env())

    def _env(self):
        return os.environ if self.env is None else self.env

    def require_live(self) -> None:
        require_live(self.config_path, self._env(), self.cli_live)

    def _req(self, method: str, path: str, body=None, query: dict | None = None):
        """The one transport call site: guard, then credentials, then send. Non-2xx raises VenueError. No retry."""
        self.require_live()
        creds = Creds.from_env(self._env())
        if callable(body):
            body = body(creds)
        raw = "" if body is None else json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        url = self.host + path + ("?" + urllib.parse.urlencode(query) if query else "")
        status, data = self.transport(method, url, l2_headers(creds, method, path, raw, int(self.wall())), raw or None,
                                      self.timeout)
        if not 200 <= status < 300:
            text = str(data)[:300]
            for v in (creds.api_key, creds.secret, creds.passphrase):  # in case the venue echoes the request
                text = text.replace(v, "***")
            raise VenueError(status, text)
        return data

    @staticmethod
    def _wrap(payload: dict, order_type: str, post_only: bool, owner: str) -> dict:
        return {"order": payload, "owner": owner, "orderType": order_type, "deferExec": False,
                "postOnly": bool(post_only and order_type not in ("FAK", "FOK"))}

    def heartbeat(self, hb_id: str = ""):
        return self._req("POST", "/v1/heartbeats", {"heartbeat_id": hb_id})

    def post_order(self, payload: dict, order_type: str, post_only: bool):
        return self._req("POST", "/order", lambda c: self._wrap(payload, order_type, post_only, c.api_key))

    def post_orders(self, items: list[tuple[dict, str]], post_only: bool):
        """items = [(signed payload, order type)]. post_only applies to GTD/GTC items only (the CLOB refuses it on FAK)."""
        return self._req("POST", "/orders", lambda c: [self._wrap(p, t, post_only, c.api_key) for p, t in items])

    def cancel(self, order_id: str):
        return self._req("DELETE", "/order", {"orderID": order_id})

    def cancel_all(self):
        return self._req("DELETE", "/cancel-all")

    def get_order(self, order_id: str):
        return self._req("GET", f"/data/order/{order_id}")

    def open_orders(self) -> list[dict]:
        out, cursor = [], FIRST_CURSOR
        for _ in range(MAX_PAGES):
            page = self._req("GET", "/data/orders", query={"next_cursor": cursor})
            out += page.get("data") or []
            cursor = page.get("next_cursor") or END_CURSOR
            if cursor == END_CURSOR:
                return out
        raise VenueError(200, f"open orders: more than {MAX_PAGES} pages")

    def balance_allowance(self, asset_type: str = "COLLATERAL", token_id: str | None = None):
        q = {"asset_type": asset_type, "signature_type": int(self._env().get("POLY_SIGNATURE_TYPE") or 0)}
        if token_id:
            q["token_id"] = token_id
        return self._req("GET", "/balance-allowance", query=q)

    def server_time(self) -> int:
        return int(self._req("GET", "/time"))


# ---- signing --------------------------------------------------------------------------------------------------------
class SdkSigner:
    """sign(intent, market, expiration_s, order_type) -> (order_id, payload); the key is read from the env at each call."""

    def __init__(self, env=None, host=HOST):
        self.env, self.host = env, host

    def _key(self) -> str:
        key = (os.environ if self.env is None else self.env).get("POLY_PRIVATE_KEY")
        if not key:
            raise CredentialsMissing("missing environment variable(s): POLY_PRIVATE_KEY")
        return key

    def address(self) -> str:
        from eth_account import Account
        return Account.from_key(self._key()).address

    def warm(self) -> float:
        """Sign one throwaway order locally (no network, nothing sent) so the first real order does not pay the SDK's
        import and crypto set-up (about 1.5 s measured 15 Nov). Returns the ms it took; never raises."""
        import time
        import types
        from trader.contracts import Intent
        t0 = time.perf_counter()
        try:
            self.sign(Intent("warm-up", "0x" + "0" * 64, "1", "BUY", 0.5, 5.0, "taker", 0, 0.5, "warm-up"),
                      types.SimpleNamespace(tick_size=0.01, neg_risk=False), 0, "FAK")
        except Exception as e:  # noqa: BLE001 - a failed warm-up only means the first order pays the set-up
            log.warning("signer warm-up failed: %s", type(e).__name__)
        return (time.perf_counter() - t0) * 1000

    def sign(self, intent, market, expiration_s: int, order_type: str) -> tuple[str, dict]:
        try:
            from py_clob_client_v2.client import ClobClient
            from py_clob_client_v2.clob_types import OrderArgsV2, PartialCreateOrderOptions
            from py_clob_client_v2.config import get_contract_config
            from py_clob_client_v2.order_utils.exchange_order_builder_v2 import ExchangeOrderBuilderV2
            from py_clob_client_v2.order_utils.model.order_data_v2 import order_to_json_v2
        except ImportError:
            raise LiveUnavailable(SDK_MISSING) from None
        env = os.environ if self.env is None else self.env
        st = env.get("POLY_SIGNATURE_TYPE")
        client = ClobClient(self.host, CHAIN, key=self._key(), signature_type=int(st) if st else None,
                            funder=env.get("POLY_FUNDER") or None)
        tick = format(market.tick_size, "g")  # the SDK's TickSize strings: "0.01", "0.001", ...
        # ponytail: seeds the SDK's private tick cache so create_order makes no GET /tick-size on the hot path; a stale
        # tick makes the venue reject the order explicitly. Use get_clob_market_info at startup if the SDK renames it.
        client._ClobClient__tick_sizes[intent.token_id] = tick
        order = client.create_order(
            OrderArgsV2(token_id=intent.token_id, price=intent.price, size=intent.size, side=intent.side,
                        expiration=int(expiration_s)),
            PartialCreateOrderOptions(tick_size=tick, neg_risk=market.neg_risk, version=2))
        cfg = get_contract_config(CHAIN)
        b = ExchangeOrderBuilderV2(cfg.neg_risk_exchange_v2 if market.neg_risk else cfg.exchange_v2, CHAIN,
                                   client.signer, domain_version="2")
        return b.build_order_hash(b.build_order_typed_data(order)), order_to_json_v2(order, "", order_type)["order"]


def session(env=None) -> tuple[L2Client, SdkSigner]:
    """For trader.loop --live: (L2Client, SdkSigner) once all three switches are on, the SDK is installed and every
    credential variable is set; otherwise SystemExit naming what is missing (never a value), before any connection."""
    import importlib.util
    env = os.environ if env is None else env
    cfg = live_switch_path(env)
    try:
        require_live(config_path=cfg, env=env, cli_live=True)
        Creds.from_env(env)
        signer = SdkSigner(env=env)
        signer._key()
    except (LiveGuardError, CredentialsMissing) as e:
        raise SystemExit(f"live: {e}") from None
    if importlib.util.find_spec("py_clob_client_v2") is None:
        raise SystemExit(f"live: {SDK_MISSING}")
    return L2Client(env=env, cli_live=True, config_path=cfg), signer


# ---- user channel (role 14) -----------------------------------------------------------------------------------------
class UserWS:
    """Own order and trade events: `await UserWS(on_event, ...).run(stop)`. Guarded and authenticated from the env at
    every connect; `connected` mirrors the socket; reconnects with backoff. Sends "PING" every 10 s (as the market
    channel). A failing on_event (e.g. a journal write) raises out of run(): it is never mistaken for a socket error."""

    def __init__(self, on_event, markets=(), url=USER_WS, config_path=None, env=None, cli_live=False,
                 backoff_s=(1, 2, 5, 10, 30), connect=None):
        self.on_event, self.markets, self.url, self.backoff_s, self.connect = on_event, markets, url, backoff_s, connect
        self.env, self.cli_live = env, cli_live
        self.config_path = pathlib.Path(config_path) if config_path is not None else live_switch_path(
            os.environ if env is None else env)
        self.connected = False

    async def run(self, stop: asyncio.Event | None = None) -> None:
        import websockets
        connect, fails = self.connect or websockets.connect, 0
        env = os.environ if self.env is None else self.env
        while not (stop and stop.is_set()):
            require_live(self.config_path, env, self.cli_live)
            c = Creds.from_env(env)
            try:
                async with connect(self.url, open_timeout=10) as ws:
                    await ws.send(json.dumps({"auth": {"apiKey": c.api_key, "secret": c.secret, "passphrase": c.passphrase},
                                              "markets": list(self.markets), "type": "user"}))
                    self.connected, fails, last_ping = True, 0, time.monotonic()
                    while not (stop and stop.is_set()):
                        if time.monotonic() - last_ping >= 10:
                            await ws.send("PING")
                            last_ping = time.monotonic()
                        try:
                            raw = await asyncio.wait_for(ws.recv(), 1)
                        except asyncio.TimeoutError:
                            continue
                        try:
                            data = json.loads(raw)
                        except ValueError:  # "PONG"
                            continue
                        for m in data if isinstance(data, list) else [data]:
                            try:
                                self.on_event(m)
                            except Exception as e:
                                raise RuntimeError("user-channel on_event failed") from e
            except (OSError, asyncio.TimeoutError, websockets.WebSocketException) as e:
                log.warning("user channel: %s; reconnecting", type(e).__name__)
            finally:
                self.connected = False
            await asyncio.sleep(self.backoff_s[min(fails, len(self.backoff_s) - 1)])
            fails += 1


# ---- one-off signer check (research/spike/.venv only) ---------------------------------------------------------------
def _signer_check() -> dict:
    """Sign with a throwaway in-memory key under the spike's guard() (every post/cancel/heartbeat refused) with GETs
    and sockets refused too, then recompute the EIP-712 hash of the payload we would send with the SDK's builder and
    recover the signer with eth_account. Nothing is posted; the key never leaves this function."""
    import socket
    import sys
    import types
    from eth_account import Account
    from eth_account.messages import encode_typed_data
    from py_clob_client_v2.client import ClobClient
    from py_clob_client_v2.config import get_contract_config
    from py_clob_client_v2.order_utils.exchange_order_builder_v2 import ExchangeOrderBuilderV2
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "research" / "spike"))
    import spike
    from trader.contracts import Intent, MarketInfo

    spike.guard(ClobClient)
    calls = []

    def refuse(*a, **k):
        calls.append(a[1:2])
        raise RuntimeError("signer check: network refused")
    ClobClient._get = refuse
    socket.socket.connect = refuse
    acct = Account.create()
    out = {"posted": False, "cases": []}
    for neg_risk, side in ((False, "BUY"), (True, "SELL")):
        m = MarketInfo("check", "1234567890123", "1234567890124", "crypto-term", "signer check", "", 0.001, 5.0, 0.07,
                       neg_risk, 0, "check")
        i = Intent("doctor", m.cid, m.token_yes, side, 0.001 if side == "BUY" else 0.999, 5.0, "maker", 0, 0.0, "check")
        oid, payload = SdkSigner(env={"POLY_PRIVATE_KEY": acct.key.hex()}).sign(i, m, 1_900_000_000, "GTD")
        cfg = get_contract_config(CHAIN)
        b = ExchangeOrderBuilderV2.__new__(ExchangeOrderBuilderV2)
        b.chain_id, b.domain_version = CHAIN, "2"
        b.contract_address = cfg.neg_risk_exchange_v2 if neg_risk else cfg.exchange_v2
        side_n = 0 if payload["side"] == "BUY" else 1
        typed = b.build_order_typed_data(types.SimpleNamespace(**{**payload, "side": side_n}))
        sdk_hash = b.build_order_hash(typed)
        signer = Account.recover_message(encode_typed_data(full_message=typed), signature=payload["signature"])
        out["cases"].append({"neg_risk": neg_risk, "side": side, "our_id": oid, "sdk_eip712_hash": sdk_hash,
                             "equal": oid == sdk_hash, "signature_recovers_to_key": signer == acct.address,
                             "expiration": payload["expiration"], "maker_amount": payload["makerAmount"],
                             "taker_amount": payload["takerAmount"]})
    out["network_calls"] = len(calls)
    blob = json.dumps(out)
    assert acct.key.hex().removeprefix("0x").lower() not in blob.lower()  # the key never reaches the output
    return out


if __name__ == "__main__":
    import sys
    if "--signer-check" not in sys.argv:
        sys.exit("usage: python -m trader.live.clob --signer-check   (in research/spike/.venv)")
    res = _signer_check()
    print(json.dumps(res, indent=1))
    sys.exit(0 if all(c["equal"] and c["signature_recovers_to_key"] for c in res["cases"]) and not res["network_calls"]
             else 1)
