import asyncio

import websockets
from websockets.asyncio.server import broadcast, serve

from trader import feedhub


def test_hub_relays_each_feed_to_its_clients_only_and_closes_unknown_paths():
    async def main():
        async with serve(feedhub.handler, "127.0.0.1", 0) as srv:
            port = srv.sockets[0].getsockname()[1]
            by = await websockets.connect(f"ws://127.0.0.1:{port}/bybit")
            bn = await websockets.connect(f"ws://127.0.0.1:{port}/binance?streams=x")  # a run's own query is ignored
            await by.send('{"op": "subscribe"}')                                           # ignored, not echoed
            for _ in range(50):
                if feedhub.clients["bybit"] and feedhub.clients["binance"]:
                    break
                await asyncio.sleep(0.02)
            broadcast(feedhub.clients["bybit"], '{"topic": "publicTrade.BTCUSDT"}')
            assert await asyncio.wait_for(by.recv(), 2) == '{"topic": "publicTrade.BTCUSDT"}'
            try:
                await asyncio.wait_for(bn.recv(), 0.3)
                raise AssertionError("binance client got a bybit message")
            except asyncio.TimeoutError:
                pass
            bad = await websockets.connect(f"ws://127.0.0.1:{port}/nope")
            await asyncio.wait_for(bad.wait_closed(), 2)
            assert bad.close_code == 1008
            for c in (by, bn):
                await c.close()

    asyncio.run(main())


def test_hub_serves_without_compression():
    import inspect
    assert "compression=None" in inspect.getsource(feedhub.main)   # deflate per run cost 4.7x the CPU (15 Oct)


def test_pm_upstream_queues_bursts_instead_of_pausing_the_socket():
    import inspect
    assert "max_queue=PM_MAX_QUEUE" in inspect.getsource(feedhub.pm_upstream)   # default 16 drew PM 1013s (20 Oct)
    assert feedhub.PM_MAX_QUEUE >= 1000


def test_clock_offset_is_server_minus_local_midpoint(monkeypatch):
    t = iter([1000.0, 1000.1, 2000.0, 2000.2])  # time.time(): binance request start/end, then bybit's (seconds)
    monkeypatch.setattr(feedhub.time, "time", lambda: next(t))
    replies = iter([{"serverTime": 1_000_100}, {"result": {"timeNano": str(2_000_000 * 1_000_000)}}])
    monkeypatch.setattr(feedhub, "get_json", lambda url: next(replies))
    monkeypatch.setattr(feedhub.common, "now_ms", lambda: 0)
    out = feedhub.clock_offsets()
    assert out["binance"] == {"offset_ms": 50, "rtt_ms": 100}     # server 1_000_100 vs midpoint 1_000_050: PC behind
    assert out["bybit"] == {"offset_ms": -100, "rtt_ms": 200}     # server 2_000_000 vs midpoint 2_000_100: PC ahead


# ---- Polymarket through the hub (15 Oct) ----------------------------------------------------------------------------
import json

import pytest

from trader.marketdata import Books


@pytest.fixture(autouse=True)
def fresh_pm():
    feedhub.pm.update(books=Books(), tick={}, ids=frozenset(), live_ms=0, grow_ms=None)
    feedhub.pm_subs.clear()
    feedhub.pm_out.clear()
    feedhub.clients["polymarket"].clear()
    for d in (feedhub.pm_win, feedhub.pm_cid, feedhub.pm_last_ts):
        d.clear()
    feedhub.pm_trade_conns.clear()
    feedhub.armed["until"] = 0
    feedhub.meter.update(mb=0.0, said=False)
    yield


def book(t, ask):
    return {"event_type": "book", "asset_id": t, "bids": [{"price": "0.40", "size": "10"}],
            "asks": [{"price": str(ask), "size": "20"}], "tick_size": "0.01"}


async def recv_or_none(ws, s=0.3):
    try:
        return await asyncio.wait_for(ws.recv(), s)
    except asyncio.TimeoutError:
        return None


def test_pm_hub_routes_tokens_and_snapshots_late_subscribers():
    async def main():
        async with serve(feedhub.handler, "127.0.0.1", 0) as srv:
            port = srv.sockets[0].getsockname()[1]
            a = await websockets.connect(f"ws://127.0.0.1:{port}/polymarket")
            b = await websockets.connect(f"ws://127.0.0.1:{port}/polymarket")
            await a.send(json.dumps({"assets_ids": ["a1", "a2"], "type": "market"}))
            await b.send(json.dumps({"assets_ids": ["b1"], "type": "market"}))
            for _ in range(50):
                if len(feedhub.pm_subs) == 2:
                    break
                await asyncio.sleep(0.02)
            assert feedhub.pm["grow_ms"] is not None                         # new tokens: the upstream must resubscribe
            feedhub.pm_relay(json.dumps([book("a1", 0.55), book("b1", 0.66)]))
            feedhub.pm_relay(json.dumps({"event_type": "price_change", "price_changes": [
                {"asset_id": "a1", "side": "SELL", "price": "0.56", "size": "3"}]}))
            assert await recv_or_none(a) is None                              # batched: nothing until the flush
            feedhub.pm_flush()
            got_a, got_b = json.loads(await recv_or_none(a, 2)), json.loads(await recv_or_none(b, 2))
            assert [m.get("asset_id") for m in got_a] == ["a1", None] and [m["asset_id"] for m in got_b] == ["b1"]
            assert got_a[1]["price_changes"][0]["price"] == "0.56"            # one send, both frames, in order
            feedhub.pm_relay("PONG")
            assert await recv_or_none(a, 2) == "PONG" and await recv_or_none(b, 2) == "PONG"
            c = await websockets.connect(f"ws://127.0.0.1:{port}/polymarket")   # a run that (re)subscribes late
            await c.send(json.dumps({"assets_ids": ["a1", "zz"], "type": "market"}))
            snap = json.loads(await recv_or_none(c, 2))
            bk = Books()
            bk.apply_msg(snap, 1)
            assert bk.books["a1"].asks == [(0.55, 20.0), (0.56, 3.0)] and "zz" not in bk.books   # the others' book
            feedhub.pm["live_ms"] -= 60_000                                         # upstream dead: no stale snapshot
            d = await websockets.connect(f"ws://127.0.0.1:{port}/polymarket")
            await d.send(json.dumps({"assets_ids": ["a1"]}))
            assert await recv_or_none(d) is None
            for bad in ("not json", '{"assets_ids": "abc"}', '{"assets_ids": [1]}'):
                x = await websockets.connect(f"ws://127.0.0.1:{port}/polymarket")
                await x.send(bad)
                await asyncio.wait_for(x.wait_closed(), 2)
                assert x.close_code == 1008
            for w in (a, b, c, d):
                await w.close()

    asyncio.run(main())


def test_pm_upstream_subscribes_the_union_and_resyncs_on_a_bad_frame(monkeypatch):
    subs, frames = [], [json.dumps([book("T1", 0.5)]), json.dumps({"event_type": "price_change", "price_changes": [{"asset_id": "T1"}]}),
                        json.dumps([book("T1", 0.6)])]

    async def fake_pm(conn):
        subs.append(json.loads(await conn.recv())["assets_ids"])
        await conn.send(frames.pop(0))
        if frames:
            await conn.send(frames.pop(0))    # the malformed price_change (no side/price): hub must resync
        await conn.wait_closed()

    async def main():
        async with serve(fake_pm, "127.0.0.1", 0) as pm_srv, serve(feedhub.handler, "127.0.0.1", 0) as hub:
            monkeypatch.setattr(feedhub, "PM_WS", f"ws://127.0.0.1:{pm_srv.sockets[0].getsockname()[1]}")
            run = await websockets.connect(f"ws://127.0.0.1:{hub.sockets[0].getsockname()[1]}/polymarket")
            await run.send(json.dumps({"assets_ids": ["T1"]}))
            tasks = [asyncio.create_task(feedhub.pm_upstream()), asyncio.create_task(feedhub.pm_flusher())]
            asks = []
            while len(asks) < 2:                                           # batched: both books may share one message
                asks += [m["asks"][0]["price"] for m in json.loads(await asyncio.wait_for(run.recv(), 5))]
            for task in tasks:
                task.cancel()
            assert subs == [["T1"], ["T1"]]                                 # one upstream, resubscribed after the bad frame
            assert asks == ["0.5", "0.6"]                                   # in order; the bad frame never forwarded
            await run.close()

    asyncio.run(main())


def test_hub_records_trades_with_both_clocks_and_rolls_files(tmp_path, monkeypatch):
    """16 Oct: our own ms tape (venue stamp + receive time) replaces the data-api's lagging second stamps."""
    monkeypatch.setattr(feedhub, "tape", feedhub.Rolling(tmp_path / "tape", feedhub._utc("%Y-%m-%dT%H"),
                                                         "recv_ms,venue_ms,asset_id,price,size,side"))
    monkeypatch.setattr(feedhub.common, "now_ms", lambda: 1_792_170_000_123)
    feedhub.pm_relay(json.dumps({"event_type": "last_trade_price", "asset_id": "a1", "price": "0.55", "size": "7",
                                 "side": "BUY", "timestamp": "1792169999900"}))
    feedhub.tape.f.close()
    [f] = list((tmp_path / "tape").glob("*.csv"))
    assert f.read_text().splitlines() == ["recv_ms,venue_ms,asset_id,price,size,side",
                                          "1792170000123,1792169999900,a1,0.55,7.0,BUY"]
    assert feedhub.pm_stats["lag"][-1] == 223                              # receive minus venue, ms


# ---- poll mode (20 Oct, low data) ------------------------------------------------------------------------------------
def test_poll_mode_routes_each_book_to_its_runs_and_drops_a_reply_that_arrives_late():
    a, b = object(), object()
    feedhub.pm_subs.update({a: frozenset({"u1", "d1"}), b: frozenset({"u2"})})
    reply = lambda t, ts, ask: {"asset_id": t, "market": "c" + t, "timestamp": str(ts), "tick_size": "0.01",
                                "bids": [{"price": "0.40", "size": "5"}], "asks": [{"price": ask, "size": "7"}]}
    feedhub.pm_poll_apply([reply("u1", 2000, "0.55"), reply("u2", 2000, "0.66")], 2100)
    assert [json.loads(x)["asset_id"] for x in feedhub.pm_out[a]] == ["u1"] and len(feedhub.pm_out[b]) == 1
    assert feedhub.pm["books"].books["u1"].asks == [(0.55, 7.0)] and feedhub.pm_cid["u1"] == "cu1"
    feedhub.pm_poll_apply([reply("u1", 1900, "0.99")], 2200)                 # an older reply arriving after a newer one
    assert feedhub.pm["books"].books["u1"].asks == [(0.55, 7.0)] and len(feedhub.pm_out[a]) == 1
    bk = Books()
    bk.apply_msg([json.loads(x) for x in feedhub.pm_out[a]], 1)             # the runs read it as a normal book event
    assert bk.books["u1"].asks == [(0.55, 7.0)]


def test_poll_mode_polls_only_open_markets_and_reads_windows_and_trades_from_the_subscribe():
    conn = object()
    msg = {"assets_ids": ["now", "later", "old"], "trades": True,
           "windows": {"now": [1000, 301_000], "later": [301_000, 601_000], "old": [0, 900], "x": [1, 2], "bad": "?"}}
    assert feedhub.pm_subscribe(conn, json.dumps(msg))
    assert feedhub.pm_win == {"now": (1000, 301_000), "later": (301_000, 601_000), "old": (0, 900)}   # only its ids
    assert conn in feedhub.pm_trade_conns
    assert feedhub.active(5000) == ["now"] and feedhub.active(298_000) == ["later", "now"]   # from 5 s before the start
    assert feedhub.pm_subscribe(conn, json.dumps({"assets_ids": ["now"]})) and conn not in feedhub.pm_trade_conns


def test_bybit_moves_arm_the_fast_poll_and_noise_does_not():
    feedhub.arm_det.update(BTCUSDT=feedhub.MoveDetector(2, feedhub.ARM_BP, 1), ETHUSDT=feedhub.MoveDetector(2, feedhub.ARM_BP, 1))
    frame = lambda ts, p: json.dumps({"topic": "publicTrade.BTCUSDT", "data": [{"T": ts, "p": str(p)}]})
    for k in range(40):
        feedhub.arm_from(frame(1_000_000 + 100 * k, 100_000 + (k % 2)), 5)    # 0.1 bp wiggles for 4 s
    assert feedhub.armed["until"] == 0
    feedhub.arm_from(frame(1_004_100, 100_040), 5)                            # +4 bp inside 2 s
    assert feedhub.armed["until"] == 5 + feedhub.ARM_HOLD_MS
    feedhub.arm_from("pong", 5)                                               # junk never raises


def test_trade_rows_become_last_trade_price_events_once():
    import collections
    seen = collections.OrderedDict()
    row = {"token_id": "u1", "side": "BUY", "price": 0.61, "size": 5.0, "timestamp": 1_792_500_899, "proxy_wallet": "w"}
    [e] = feedhub.pm_trade_events([row], seen)
    assert e == {"event_type": "last_trade_price", "asset_id": "u1", "price": "0.61", "size": "5.0", "side": "BUY",
                 "timestamp": "1792500899000"}
    assert feedhub.pm_trade_events([row], seen) == []                         # the next poll returns it again
    assert Books().apply_msg(e, 1) == [("trade", "u1", 0.61, 5.0, "BUY", 1_792_500_899_000)]


def test_over_the_daily_budget_the_calm_poll_slows():
    feedhub.meter.update(day="", mb=0.0, said=False)
    feedhub.meter_add(1)                                                      # a new IST day starts the count
    assert feedhub.calm_s() == feedhub.CALM_S
    feedhub.meter["mb"] = feedhub.DAY_BUDGET_MB + 1
    assert feedhub.calm_s() == feedhub.OVER_BUDGET_CALM_S


def test_poll_mode_poller_fetches_only_open_tokens_and_relays_with_liveness(monkeypatch):
    calls, sent = [], []
    def fake(self, method, url, body=None):
        calls.append((method, url, [b["token_id"] for b in body]))
        return [{"asset_id": "now", "market": "c", "timestamp": str(len(calls)), "bids": [], "asks": [{"price": "0.5", "size": "9"}]}]
    monkeypatch.setattr(feedhub.Http, "__call__", fake)
    monkeypatch.setattr(feedhub, "CALM_S", 0.05)
    monkeypatch.setattr(feedhub, "broadcast", lambda conns, msg: sent.append((list(conns), msg)))
    conn, now = object(), feedhub.common.now_ms()
    feedhub.pm_subs[conn] = frozenset({"now", "later"})
    feedhub.pm_win.update(now=(now - 1000, now + 60_000), later=(now + 60_000, now + 120_000))

    async def main():
        task = asyncio.create_task(feedhub.pm_poller())
        await asyncio.sleep(0.4)
        task.cancel()
    asyncio.run(main())
    assert len(calls) >= 3 and all(c == ("POST", f"{feedhub.CLOB}/books", ["now"]) for c in calls)   # not "later"
    assert any(c == [conn] and '"asset_id": "now"' in m for c, m in sent)   # the book reached the run
    assert any(m == "PONG" for _, m in sent)                                 # and the liveness ping
