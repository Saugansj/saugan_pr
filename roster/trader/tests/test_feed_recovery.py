"""Feed recovery after a wake from sleep (10 Oct: an 8 h sleep left crypto-fast subscribed to ended windows, silent
until a restart): a failed poll retries in RETRY_S, a wake event reruns it at once, a silent PM socket asks for one."""
import asyncio

import trader.marketdata as md_mod
from trader.marketdata import MarketData


def bare():
    m = object.__new__(MarketData)  # no __init__: it loads markets over the network
    m.reload, m.seen, m.subs = asyncio.Event(), {}, {}
    return m


def test_failed_poll_retries_soon_and_wake_reruns_at_once(monkeypatch):
    monkeypatch.setattr(md_mod, "RETRY_S", 0.05)
    calls, got = [], []

    def fn():
        calls.append(1)
        if len(calls) == 1:
            raise OSError("getaddrinfo failed")  # DNS not up yet just after the wake
        return len(calls)

    async def main():
        m = bare()
        task = asyncio.create_task(m._poll(3600, "markets", fn, got.append, m.reload))
        await asyncio.sleep(0.3)
        assert got == [2]           # retried in RETRY_S, not an hour later
        m.reload.set()
        await asyncio.sleep(0.1)
        assert got == [2, 3]        # the wake event reran it at once
        task.cancel()

    asyncio.run(main())


def test_silent_pm_socket_requests_a_reload_and_reconnects(monkeypatch):
    monkeypatch.setattr(md_mod, "SILENT_S", 0.2)
    opened = []

    class WS:
        async def send(self, msg):
            pass

        async def recv(self):
            await asyncio.sleep(3600)  # subscribed to ended windows: no frame ever

        async def __aenter__(self):
            opened.append(1)
            return self

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(md_mod.websockets, "connect", lambda *a, **k: WS())

    async def main():
        m = bare()
        m.subs["crypto-fast"] = frozenset({"T1", "T2"})
        task = asyncio.create_task(m._pm_ws("crypto-fast"))
        await asyncio.wait_for(m.reload.wait(), 3)
        await asyncio.sleep(0.1)
        assert len(opened) >= 2     # left the silent socket and connected again
        task.cancel()

    asyncio.run(main())


def test_bybit_trade_message_sets_the_btc_reference_and_fires_on_ref():
    import collections, json
    m = bare()
    m.ref, m.counts, got = {"BTC": {"price": None, "ts_ms": None, "recv_ms": None}}, collections.Counter(), []
    m.on_ref = lambda a, now: got.append((a, now))
    m._on_bybit(json.dumps({"success": True, "op": "subscribe"}), 1)          # ack: ignored
    m._on_bybit(json.dumps({"topic": "publicTrade.BTCUSDT", "ts": 1700000000123,
                            "data": [{"p": "82000.5", "T": 1700000000120}, {"p": "82001.0", "T": 1700000000122}]}), 5)
    assert m.ref["BTC"] == {"price": 82001.0, "ts_ms": 1700000000123, "recv_ms": 5}
    assert m.seen["binance:BTC"] == 5 and got == [("BTC", 5)] and m.counts["tick_BTC"] == 1


def test_bybit_eth_message_sets_the_eth_reference_only():
    import collections, json
    m = bare()
    m.ref, m.counts, got = {"BTC": {"price": None}, "ETH": {"price": None, "ts_ms": None, "recv_ms": None}}, collections.Counter(), []
    m.on_ref = lambda a, now: got.append(a)
    m._on_bybit(json.dumps({"topic": "publicTrade.ETHUSDT", "ts": 7, "data": [{"p": "2500.1"}]}), 9)
    assert m.ref["ETH"]["price"] == 2500.1 and m.ref["BTC"]["price"] is None and got == ["ETH"] and m.seen == {"binance:ETH": 9}


def test_bybit_closes_parse_newest_first_reply_and_seed_vol_uses_the_runs_source(monkeypatch):
    import trader.marketdata as md
    from trader import loop
    from trader.engines.speed import SpeedEngine
    reply = {"result": {"list": [["1700000060000", "1", "1", "1", "101.5", "0", "0"],
                                 ["1700000000000", "1", "1", "1", "101.0", "0", "0"]]}}
    assert md.fetch_bybit_closes("BTC", 1700000130000, get=lambda url, q: reply) == {1700000000000: 101.0,
                                                                                     1700000060000: 101.5}
    seeded = []
    e = SpeedEngine(version=5)
    e.vol = {"BTC": type("V", (), {"seed": lambda self, c: seeded.append(c)})()}
    monkeypatch.setattr(md, "fetch_bybit_closes", lambda a, now: {1: 2.0})
    monkeypatch.setattr(md, "fetch_closes", lambda a, now, n: {9: 9.0})
    loop.seed_vol(e, True, now_ms=1)
    loop.seed_vol(e, False, now_ms=1)
    assert seeded == [{1: 2.0}, {9: 9.0}]   # Bybit run seeds from Bybit, Binance run from Binance


def test_speed_only_runs_pause_only_on_their_own_feeds():
    from trader.loop import breaker_feeds
    ages = {"polymarket": 61_000, "polymarket:crypto-fast": 61_000, "binance:BTC": 1, "binance:ETH": 70_000,
            "dvol:BTC": 900_000, "basis:USDT": 900_000}
    assert breaker_feeds(ages, {"speed_only", "speed_v4"}, ("BTC",)) == \
        {"polymarket": 61_000, "polymarket:crypto-fast": 61_000, "binance:BTC": 1}   # no dvol, basis or ETH
    assert breaker_feeds(ages, set(), ("BTC",)) == ages                                # paper14 (ladder) watches all


def test_feed_hub_routes_the_pm_socket_to_the_hub(monkeypatch):
    urls = []

    def connect(url, **k):
        urls.append(url)
        raise OSError("stop here")

    monkeypatch.setattr(md_mod.websockets, "connect", connect)
    monkeypatch.setattr(md_mod.asyncio, "sleep", lambda s: (_ for _ in ()).throw(asyncio.CancelledError()))
    for feats, want in (({"feed_hub", "speed_only"}, f"{md_mod.FEED_HUB}/polymarket"), ({"feed_hub"}, md_mod.PM_WS),
                        (set(), md_mod.PM_WS)):   # paper14 (feed_hub, ladder) keeps its own PM socket
        m = bare()
        m.features = frozenset(feats)
        m.subs["crypto-fast"] = frozenset({"T1"})
        try:
            asyncio.run(m._pm_ws("crypto-fast"))
        except asyncio.CancelledError:
            pass
        assert urls[-1] == want
