"""trader.loop --live wiring: LiveRouter in the loop against the fake CLOB (test_live_exec.Venue), and the API-key setup
script. No network: the venue is an in-process transport and the WW-D guard refuses every socket."""
import pytest

from tests.phase2.test_live_exec import FakeSigner, Venue, live
from tests.wiring.test_ww_d import LAD, T, FakeMD, books, env, no_network  # noqa: F401 - fixtures
from tools.live_tools import setup_keys
from trader.contracts import TradingState
from trader.live.clob import L2Client, session as live_session
from trader.live.router import LiveRouter
from trader.loop import HB_EVERY_MS, Trader


def boot_live(d, tmp_path):
    cfg, env_ = live(tmp_path)
    venue = Venue(journal=d / "journal.jsonl")
    md = FakeMD()
    tr = Trader(md, d, fetch=lambda cid: None, features={"heartbeat"},
                live=(L2Client(transport=venue, config_path=cfg, env=env_, cli_live=True), FakeSigner()))
    tr.now = lambda: T
    tr.start(T)
    books(md, T)
    return md, tr, venue


def test_live_session_exits_with_missing_switch_names(monkeypatch):
    monkeypatch.delenv("ROSTER_LIVE", raising=False)
    with pytest.raises(SystemExit) as e:
        live_session(env={})
    assert "ROSTER_LIVE=1" in str(e.value) and "live.json" in str(e.value)  # live.json ships {"live": false}


def test_live_loop_posts_fills_heartbeats_and_halts(env, tmp_path):
    md, tr, venue = boot_live(env, tmp_path)
    assert isinstance(tr.router, LiveRouter) and tr.router.starts is tr.kernel.starts
    assert venue.n("GET", "/data/orders") == 1  # startup reconcile asked the venue

    tr.ladder_round(T)
    posted = venue.posted_ids()
    assert posted and venue.wal_checked  # maker quotes went out, each journaled before the post
    o = tr.router.state.orders[posted[0]]
    assert o.status == "open" and o.intent.cid == LAD.cid

    # a maker fill on the user channel -> ledger fill; no merge attempt (LiveRouter has none)
    tr.user_event({"event_type": "trade", "id": "t-1", "status": "MATCHED", "taker_order_id": "someone",
                   "size": "5", "price": "0.4", "matchtime": str(T // 1000),
                   "maker_orders": [{"order_id": o.order_id, "matched_amount": "5", "price": str(o.intent.price)}]})
    assert tr.router.state.orders[o.order_id].filled == 5.0
    assert tr.counts["fill:ladder-maker:maker"] == 1

    # heartbeat: sent only while the user channel is up, then at most every HB_EVERY_MS
    tr.tick(T)
    assert venue.n("POST", "/v1/heartbeats") == 0
    tr.user_ws.connected, tr.clock_off = True, 20.0  # the clock worker's first measurement
    for k in range(5):
        tr.now = lambda k=k: T + 1000 + k * 100
        tr.tick(T + 1000 + k * 100)
    assert venue.n("POST", "/v1/heartbeats") == 1
    tr.now = lambda: T + 1000 + HB_EVERY_MS
    tr.tick(T + 1000 + HB_EVERY_MS)
    assert venue.n("POST", "/v1/heartbeats") == 2

    # a halt is confirmed by the venue: cancel-all, then zero open orders on GET /data/orders
    tr.kernel.trip("global", "test halt", "loop")
    tr.now = lambda: T + 20_000
    tr.tick(T + 20_000)
    assert tr.kernel.state == TradingState.HALTED and venue.n("DELETE", "/cancel-all") >= 1
    assert not tr.router.open_orders() and tr.halt_flagged and tr.violations == 0


def test_setup_keys_saves_names_and_never_prints_values():
    from eth_account import Account
    acct, saved, printed = Account.create(), {}, []
    key = acct.key.hex()

    class Creds:
        api_key, api_secret, api_passphrase = "k-id", "s3cret", "p4ss"

    class Client:
        def __init__(self, host, chain, key, signature_type, funder):
            Client.args = (chain, signature_type, funder)

        def create_or_derive_api_key(self):
            return Creds()

    funder = "0x" + "ab" * 20
    answers = iter(["", funder])  # default signature type 1, then the wallet address
    rc = setup_keys.main(env={}, ask=lambda _: next(answers), ask_secret=lambda _: key, client_cls=Client,
                         save=saved.update, out=printed.append)
    assert rc == 0 and Client.args == (137, 1, funder)
    assert saved == {"POLY_PRIVATE_KEY": key, "POLY_SIGNATURE_TYPE": "1", "POLY_FUNDER": funder,
                     "POLY_ADDRESS": acct.address, "POLY_API_KEY": "k-id", "POLY_API_SECRET": "s3cret",
                     "POLY_API_PASSPHRASE": "p4ss"}
    text = "\n".join(printed)
    assert not any(v in text for v in (key, key.removeprefix("0x"), "s3cret", "p4ss", "k-id"))
    assert "ROSTER_LIVE" not in saved


def test_setup_keys_bad_key_saves_nothing():
    saved, printed = {}, []
    rc = setup_keys.main(env={}, ask_secret=lambda _: "not-a-key", client_cls=object, save=saved.update,
                         out=printed.append)
    assert rc == 1 and not saved and "not-a-key" not in "\n".join(printed)
