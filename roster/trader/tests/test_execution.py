"""WP1-C tests: market data parsing, paper router (rounding, fills, journal) and reconciler. No network."""
import datetime as dt
import json

import pytest

from trader import marketdata as md
from trader.contracts import Book, Fill, Intent, MarketInfo
from trader.reconciler import Reconciler
from trader.router import MAX_BATCH, LiveTradingForbidden, PaperRouter, round_price, round_size


def fee(C, p, rate):  # fake of trader.fees.fee (WP1-A builds the real one in parallel)
    return C * rate * p * (1 - p)


MKT = MarketInfo(cid="c1", token_yes="Y", token_no="N", mode="crypto-fast", question="q", rules_sha256="h",
                 tick_size=0.01, min_size=5, fee_rate=0.07, neg_risk=False, end_ms=10_000_000,
                 event_group="BTC-5m@x", asset="BTC", kind="updown")


def intent(**kw):
    return Intent(**{"strategy": "t", "cid": "c1", "token_id": "Y", "side": "BUY", "price": 0.45, "size": 10,
                     "kind": "maker", "expiry_ms": 5_000_000, "fair": 0.5, "reason": "test", **kw})


def router(tmp_path, rtt=100):
    return PaperRouter({"c1": MKT}, rtt_ms=rtt if callable(rtt) else (lambda: rtt), journal=tmp_path / "j.jsonl", fee=fee)


def with_books(r, t=0):
    for tok in ("Y", "N"):
        r.on_book(Book(tok, [(0.45, 200), (0.40, 100)], [(0.55, 100)], t), t)
    return r


# ---------- C1: market data ----------

ROW_TERM = {"mode": "crypto-term", "event_slug": "bitcoin-above-on-october-1-2026", "condition_id": "0xterm",
            "question": "Will the price of Bitcoin be above $74,000 on October 1?", "yes_token_id": "1", "no_token_id": "2",
            "rules_text": 'This market will resolve to "Yes" if the Binance 1 minute candle for BTC/USDT 12:00 in the ET '
                          'timezone (noon) on the date specified in the title has a final "Close" price higher than ...',
            "rules_sha256": "h1", "fee_schedule": {"exponent": 1, "rate": 0.07, "takerOnly": True, "rebateRate": 0.2},
            "fees_enabled": True, "tick_size": 0.001, "min_order_size": 5, "neg_risk": False,
            "end_time": "2026-10-01T16:00:00Z"}
ROW_FAST = {**ROW_TERM, "mode": "crypto-fast", "event_slug": "btc-updown-5m-1790837400", "condition_id": "0xfast",
            "question": "Bitcoin Up or Down - October 1, 2:50AM-2:55AM ET", "yes_token_id": "3", "no_token_id": "4",
            "rules_text": "... The resolution source for this market is information from Chainlink, specifically the "
                          "BTC/USD TWAP data stream available at https://data.chain.link/streams/btc-usd-twap-60s-streams.",
            "tick_size": 0.01, "end_time": "2026-10-01T06:55:00Z"}
ROW_UPDOWN = {**ROW_TERM, "event_slug": "ethereum-up-or-down-on-october-1-2026", "condition_id": "0xud",
              "question": "Ethereum Up or Down on October 1?", "yes_token_id": "5", "no_token_id": "6",
              "rules_text": 'This market will resolve to "Up" if the "Close" price for the Binance 1 minute candle for '
                            "ETH/USDT Sep 30 '26 12:00 in the ET timezone (noon) is lower than ..."}


def test_market_info_builds_group_asset_strike_kind_and_source():
    term, fast, ud = map(md.market_info, (ROW_TERM, ROW_FAST, ROW_UPDOWN))
    assert (term.event_group, term.asset, term.strike, term.kind, term.source_id, term.fee_rate, term.tick_size) == \
           ("BTC@2026-10-01T16:00Z", "BTC", 74000.0, "strike", "binance:BTC/USDT", 0.07, 0.001)
    assert (fast.event_group, fast.kind, fast.strike, fast.source_id) == ("BTC-5m@2026-10-01T06:50Z", "updown", None,
                                                                         "chainlink:BTC/USD")
    assert (ud.event_group, ud.asset, ud.kind, ud.source_id) == ("ETH@2026-10-01T16:00Z", "ETH", "updown", "binance:ETH/USDT")
    assert md.source_id("... the BTC/USDT 1 hour candle ...") == "binance:BTC/USDT" and md.source_id("CoinGecko") == ""
    assert md.market_info({**ROW_TERM, "min_order_size": None}) is None  # never guess a trading field
    assert md.market_info({**ROW_TERM, "fee_schedule": None}) is None    # fees on, rate unknown: not tradable
    assert md.market_info({**ROW_TERM, "fee_schedule": None, "fees_enabled": False}).fee_rate == 0.0


def test_load_markets_crawls_only_when_the_snapshot_is_stale_or_lacks_a_mode(tmp_path):
    calls = []

    def crawl(modes):
        calls.append(modes)
        return [ROW_TERM, ROW_FAST], None, []

    snap = tmp_path / "2026-10-01T060000Z.jsonl"
    snap.write_text(json.dumps(ROW_TERM) + "\n" + json.dumps(ROW_FAST) + "\n", encoding="utf-8")
    t = dt.datetime(2026, 10, 1, 6, 30, tzinfo=dt.timezone.utc).timestamp()
    markets, rows = md.load_markets(markets_dir=tmp_path, crawl=crawl, now_s=t)
    assert calls == [] and set(markets) == {"0xterm", "0xfast"} and rows["0xterm"]["fee_schedule"]["rate"] == 0.07
    md.load_markets(markets_dir=tmp_path, crawl=crawl, now_s=t + 3600)  # 1.5 h old
    assert calls == [md.crawler.MODES]  # every mode: the snapshot dir is shared with the recorder
    snap.write_text(json.dumps(ROW_TERM) + "\n", encoding="utf-8")       # e.g. the recorder's crawl without crypto-fast
    md.load_markets(markets_dir=tmp_path, crawl=crawl, now_s=t)
    assert len(calls) == 2


def test_ws_books_sorted_best_first_with_staleness_clock_and_mid_ex_own():
    b = md.Books()
    snap = [{"event_type": "book", "asset_id": "Y", "market": "c1", "timestamp": "1", "tick_size": "0.01",
             "bids": [{"price": "0.40", "size": "100"}, {"price": "0.45", "size": "10"}],  # worst first, as sent
             "asks": [{"price": "0.60", "size": "50"}, {"price": "0.55", "size": "20"}]}]
    ev = b.apply(json.dumps(snap), 1000)
    bk = b.books["Y"]
    assert ("book", "Y") in ev and ("tick", "Y", 0.01) in ev
    assert (bk.bids, bk.asks, bk.ts_ms) == ([(0.45, 10), (0.40, 100)], [(0.55, 20), (0.60, 50)], 1000)
    assert bk.mid_ex_own() == pytest.approx(0.50)
    bk.own = {0.45: 10.0}  # the whole best bid is ours: the mid skips it
    assert bk.mid_ex_own() == pytest.approx((0.40 + 0.55) / 2)
    pc = {"event_type": "price_change", "market": "c1", "timestamp": "2", "price_changes": [
        {"asset_id": "Y", "price": "0.45", "size": "0", "side": "BUY"},
        {"asset_id": "Y", "price": "0.54", "size": "7", "side": "SELL"},
        {"asset_id": "Z", "price": "0.1", "size": "1", "side": "BUY"}]}  # Z has no snapshot: ignored
    assert b.apply(json.dumps(pc), 2000) == [("book", "Y")]
    assert (bk.bids, bk.asks[0], bk.ts_ms) == ([(0.40, 100)], (0.54, 7), 2000)
    tr = {"event_type": "last_trade_price", "asset_id": "Y", "price": "0.54", "size": "3", "side": "BUY",
          "timestamp": "1790837442624"}
    assert b.apply(json.dumps(tr), 3000) == [("trade", "Y", 0.54, 3.0, "BUY", 1790837442624)]
    assert b.apply("PONG", 4000) == []
    assert b.apply(json.dumps({"event_type": "tick_size_change", "asset_id": "Y", "new_tick_size": "0.001"}), 5000) \
        == [("tick", "Y", 0.001)]


def _agg(p, t):
    return json.dumps({"stream": "btcusdt@aggTrade", "data": {"e": "aggTrade", "E": t + 5, "s": "BTCUSDT",
                                                               "p": str(p), "q": "0.1", "T": t, "m": True}})


def test_ref_ticks_and_finals_publish_on_the_first_trade_after_the_print_minute():
    r = md.Ref(("BTC",))
    noon = int(dt.datetime(2026, 10, 1, 12, 0, tzinfo=md.ET).timestamp() * 1000)
    assert r.apply(_agg(100.0, noon + 1_000), noon + 1_010) == ["BTC"]
    r.apply(_agg(101.0, noon + 59_999), 0)
    assert r.ref["BTC"]["final"] == {}  # not final until a later trade proves the minute is over
    r.apply(_agg(102.0, noon + 60_000), noon + 60_020)
    assert r.ref["BTC"]["final"] == {noon: 101.0}  # the 12:00 ET candle's close, keyed by the daily market's end_ms
    assert (r.ref["BTC"]["price"], r.ref["BTC"]["ts_ms"], r.ref["BTC"]["recv_ms"]) == (102.0, noon + 60_005, noon + 60_020)
    kline = {"stream": "btcusdt@kline_1m", "data": {"e": "kline", "s": "BTCUSDT",
                                                     "k": {"t": noon, "T": noon + 59_999, "c": "101.5", "x": True}}}
    assert r.apply(json.dumps(kline), 0) == [] and r.ref["BTC"]["final"][noon] == 101.5  # the source's candle wins
    hour = noon + 3_600_000
    r.apply(_agg(103.0, hour - 1), 0)
    r.apply(_agg(104.0, hour + 5), 0)
    assert r.ref["BTC"]["final_1h"] == {hour: 103.0} and list(r.ref["BTC"]["final"]) == [noon]


def test_backfill_recovers_prints_missed_while_disconnected():
    r = md.Ref(("BTC",))
    now = int(dt.datetime(2026, 10, 1, 13, 30, tzinfo=md.ET).timestamp() * 1000)

    def get(url, params):
        if params["interval"] == "1m":
            return [[params["startTime"], "0", "0", "0", str(params["startTime"] % 1000 + 200.0)]]
        return [[0, 0, 0, 0, "300", 0, now - 1_800_001], [0, 0, 0, 0, "301", 0, now + 1_799_999]]  # 2nd still open

    r.backfill(now, get)
    noons = [int(dt.datetime(2026, 9, d, 12, tzinfo=md.ET).timestamp() * 1000) for d in (29, 30)] + \
            [int(dt.datetime(2026, 10, 1, 12, tzinfo=md.ET).timestamp() * 1000)]
    assert sorted(r.ref["BTC"]["final"]) == noons and r.ref["BTC"]["final_1h"] == {now - 1_800_000: 300.0}


def test_feed_ages_use_the_kernel_feed_names_and_basis_parses():
    m = md.MarketData.__new__(md.MarketData)  # no network: only the fields feed_age_ms reads
    m.modes, m.subs = ("crypto-term", "crypto-fast"), {"crypto-term": {"1"}, "crypto-fast": {"3"}}
    m.seen = {"polymarket:crypto-term": 900, "binance:BTC": 990, "dvol:BTC": 500, "basis:USDT": 400}
    assert "polymarket" not in m.feed_age_ms(1000)  # one connection never heard from: the kernel sees it stale
    m.seen["polymarket:crypto-fast"] = 950
    assert m.feed_age_ms(1000) == {"polymarket:crypto-term": 100, "polymarket:crypto-fast": 50, "polymarket": 100,
                                   "binance:BTC": 10, "dvol:BTC": 500, "basis:USDT": 600}
    kraken = {"error": [], "result": {"USDTZUSD": {"a": ["0.99946", "1", "1"], "b": ["0.99944", "1", "1"]}}}
    assert md.fetch_usdt_usd(lambda url, params: kraken) == pytest.approx(0.99945)


def test_reload_from_an_older_snapshot_keeps_the_websocket_tick():
    m = md.MarketData.__new__(md.MarketData)
    term = md.dataclasses.replace(md.market_info(ROW_TERM), end_ms=2**62)  # snapshot tick 0.001; never ends
    m.modes, m.subs, m.rows, m.markets, m.ws_tick, m.counts = ("crypto-term",), {}, {}, {"0xterm": term}, {}, md.collections.Counter()
    m.on_book = m.on_trade = None
    m._subscribe(0)
    m.pm = md.Books()
    m.books = m.pm.books
    m._on_pm(json.dumps([{"event_type": "book", "asset_id": "1", "tick_size": "0.01", "bids": [], "asks": []}]), 1)
    assert m.markets["0xterm"].tick_size == 0.01                  # the venue changed it: MarketInfo follows
    m._set_markets(({"0xterm": term}, {}))                          # 5-min reload of the hour-old snapshot
    assert m.markets["0xterm"].tick_size == 0.01                  # not reverted (that would void the clearance)


# ---------- C2: order rules ----------

def test_rounding_min_size_never_rounds_up_batch_limit_and_live_flag(tmp_path, monkeypatch):
    assert (round_price(0.4567, 0.01, "BUY"), round_price(0.4567, 0.01, "SELL")) == (0.45, 0.46)  # passive
    assert (round_price(0.45, 0.01, "BUY"), round_price(0.456, 0.001, "SELL"), round_price(0.29, 0.01, "SELL")) == \
           (0.45, 0.456, 0.29)  # prices already on the tick are kept despite float noise
    assert (round_size(5.999), round_size(7), round_size(4.999)) == (5.99, 7, 4.99)
    r = with_books(router(tmp_path))
    o = r.submit(intent(price=0.4567, size=5.999), 0)
    assert (o.status, o.intent.price, o.intent.size) == ("open", 0.45, 5.99)
    small = r.submit(intent(size=4.999), 0)  # would need rounding up to reach the minimum: refused
    assert small.status == "rejected" and "minimum" in r.reasons[small.order_id]
    cross = r.submit(intent(price=0.55), 0)
    assert cross.status == "rejected" and "cross" in r.reasons[cross.order_id]
    capped = r.submit(intent(price=0.40, expiry_ms=99_000_000), 0)
    assert capped.intent.expiry_ms == MKT.end_ms - 120_000  # GTD capped at close - 2 min
    late = r.submit(intent(price=0.40, expiry_ms=99_000_000), MKT.end_ms - 150_000)
    assert late.status == "rejected" and "GTD" in r.reasons[late.order_id]
    with pytest.raises(ValueError):
        r.submit_batch([intent(price=0.30)] * (MAX_BATCH + 1), 0)
    assert all(o.status == "open" for o in r.submit_batch([intent(price=0.30)] * MAX_BATCH, 0))
    with pytest.raises(LiveTradingForbidden):
        PaperRouter({}, 100, journal=tmp_path / "x.jsonl", fee=fee, live=True)
    with pytest.raises(LiveTradingForbidden):
        r.live = True
    monkeypatch.setenv("ROSTER_LIVE", "1")
    with pytest.raises(LiveTradingForbidden):
        router(tmp_path)


# ---------- C3: strict fill model ----------

def test_maker_fills_on_a_trade_through_its_price(tmp_path):
    r = with_books(router(tmp_path, rtt=100))
    o = r.submit(intent(price=0.45, size=10), 1000)
    assert o.queue_ahead == 200
    assert r.on_trade("Y", 0.44, 1.0, "SELL", 1050) == []  # before created + round trip: not resting yet
    f = r.on_trade("Y", 0.44, 1.0, "SELL", 1200)
    assert [(x.price, x.size, x.maker, x.fee) for x in f] == [(0.45, 10, True, 0.0)] and o.status == "filled"
    assert r.positions["Y"] == 10 and r.state.cash == pytest.approx(-4.5)
    s = r.submit(intent(side="SELL", price=0.56, size=10), 2000)  # sell what we hold
    assert r.on_trade("Y", 0.56, 50, "SELL", 3000) == []         # a seller at our price takes no ask queue
    assert [x.size for x in r.on_trade("Y", 0.57, 1, "BUY", 3000)] == [10] and s.status == "filled"
    assert r.positions["Y"] == 0 and r.state.cash == pytest.approx(-4.5 + 5.6)
    assert r.submit(intent(side="SELL", price=0.56, size=5), 4000).status == "rejected"  # nothing left to sell


def test_maker_at_the_touch_fills_only_after_queue_ahead_plus_own_size_trades(tmp_path):
    r = with_books(router(tmp_path, rtt=0))
    o = r.submit(intent(price=0.45, size=10), 0)
    assert r.on_trade("Y", 0.45, 150, "SELL", 500) == []
    assert r.on_trade("Y", 0.45, 500, "BUY", 600) == []   # a buyer at our price does not consume the bid queue
    assert r.on_trade("Y", 0.46, 500, "SELL", 700) == []  # above our bid: not through
    assert r.on_trade("Y", 0.45, 59, "SELL", 800) == []   # 209 traded < 200 ahead + 10 own
    f = r.on_trade("Y", 0.45, 1, "SELL", 900)             # 210 = queue ahead + own size
    assert [(x.price, x.size) for x in f] == [(0.45, 10)] and o.status == "filled"


def test_taker_fills_at_the_arrival_time_book_partially_with_fees(tmp_path):
    r = router(tmp_path, rtt=200)
    r.on_book(Book("Y", [(0.40, 50)], [(0.50, 3), (0.52, 1.5)], 1000), 1000)  # book at decision time
    o = r.submit(intent(kind="taker", price=0.55, size=10, expiry_ms=5000), 1000)
    arrival = 1000 + 150 + 200
    assert r.on_book(Book("Y", [(0.40, 50)], [(0.51, 2), (0.53, 2), (0.56, 100)], 1300), 1300) == []  # before arrival
    f = r.on_book(Book("Y", [(0.40, 50)], [(0.30, 100)], 1400), 1400)  # the book in force at arrival is the 1300 one
    assert [(x.price, x.size, x.ts_ms, x.maker) for x in f] == [(0.51, 2, arrival, False), (0.53, 2, arrival, False)]
    assert [x.fee for x in f] == pytest.approx([fee(2, 0.51, 0.07), fee(2, 0.53, 0.07)])
    assert (o.status, o.filled) == ("cancelled", 4)  # FAK: 0.56 is above the limit, the rest is killed
    assert r.positions["Y"] == 4 and r.state.cash == pytest.approx(-(1.02 + 1.06) - sum(x.fee for x in f))
    late = r.submit(intent(kind="taker", price=0.55, size=5, expiry_ms=1500), 1400)  # gives up before it can arrive
    assert r.on_book(Book("Y", [], [(0.30, 100)], 1800), 1800) == [] and late.status == "expired"
    quiet = r.submit(intent(kind="taker", price=0.55, size=5, expiry_ms=9000), 2000)
    assert [x.price for x in r.poll(2400)] == [0.30] and quiet.status == "filled"  # no update since: last book holds


# ---------- C6: measured round trip in taker timing ----------

def test_measured_round_trip_sets_taker_arrival_and_is_journaled(tmp_path):
    rtt = {"ms": 100.0}
    r = router(tmp_path, rtt=lambda: rtt["ms"])
    got = {}
    for ms in (100.0, 400.0):
        rtt["ms"] = ms
        t0 = 10_000 * int(ms)
        r.on_book(Book("Y", [], [(0.50, 10)], t0), t0)
        o = r.submit(intent(kind="taker", price=0.6, size=5, expiry_ms=t0 + 2000), t0)
        fills = r.on_book(Book("Y", [], [(0.51, 10)], t0 + 300), t0 + 300) + r.on_book(Book("Y", [], [(0.52, 10)], t0 + 600), t0 + 600)
        got[ms] = (fills[0].price, fills[0].ts_ms - t0)
        assert r.state.arrival[o.order_id] == t0 + 150 + ms
    assert got == {100.0: (0.50, 250), 400.0: (0.51, 550)}  # a slower round trip meets a later book
    news = [json.loads(x) for x in (tmp_path / "j.jsonl").read_text().splitlines() if '"op":"new"' in x]
    assert [e["rtt_ms"] for e in news] == [100.0, 400.0]


# ---------- C4: write-ahead journal ----------

def test_crash_mid_batch_then_replay_reproduces_every_order_and_unknown_is_not_retried(tmp_path, monkeypatch):
    r = with_books(router(tmp_path, rtt=0))
    r.submit(intent(price=0.41), 0)                                  # stays open
    r.cancel(r.submit(intent(price=0.42), 0).order_id, 1)            # cancelled
    r.submit(intent(price=0.43), 0)
    r.on_trade("Y", 0.425, 1, "SELL", 10)                            # fills the 0.43 bid only
    taker = r.submit(intent(kind="taker", price=0.6, size=5, expiry_ms=99_999), 20)  # in flight at the crash
    real, news = r._log, []

    def dying(e):  # kill -9 while journaling the second order of a batch: half a line reaches the disk
        if e["op"] == "new":
            news.append(e["id"])
            if len(news) == 2:
                r._f.write(json.dumps(e)[:25])
                r._f.flush()
                raise KeyboardInterrupt
        real(e)

    monkeypatch.setattr(r, "_log", dying)
    with pytest.raises(KeyboardInterrupt):
        r.submit_batch([intent(token_id="N", price=0.31), intent(token_id="N", price=0.32), intent(token_id="N", price=0.33)], 30)
    before = {k: (o.status, o.filled) for k, o in r.state.orders.items()}
    r._f.close()

    r2 = router(tmp_path, rtt=0)  # restart
    after = {k: (o.status, o.filled) for k, o in r2.state.orders.items()}
    assert before[news[0]] == ("journaled", 0.0) and before[taker.order_id] == ("open", 0.0)
    assert after == {**before, news[0]: ("unknown", 0.0), taker.order_id: ("unknown", 0.0)}  # torn 2nd never existed
    assert r2.positions == r.positions and r2.state.cash == pytest.approx(r.state.cash) and r2.positions["Y"] == 10
    lines = len((tmp_path / "j.jsonl").read_text().splitlines())
    with_books(r2, 40)
    retry = r2.submit(intent(token_id="N", price=0.31), 40)
    assert retry.status == "rejected" and "unknown" in r2.reasons[retry.order_id]
    assert len((tmp_path / "j.jsonl").read_text().splitlines()) == lines  # nothing journaled: never sent
    trips = []
    rec = Reconciler(r2, lambda *a: trips.append(a))
    assert rec.reconcile(r2.state.fills) == [] and trips == []        # clean reconcile after the crash
    assert sorted(rec.resolve_unknown(50)) == sorted([news[0], taker.order_id])  # cancel by id
    assert r2.submit(intent(token_id="N", price=0.31), 60).status == "open"


# ---------- C5: reconciler ----------

def test_reconciler_matches_fills_trips_on_mismatch_and_merges_pairs(tmp_path):
    r = with_books(router(tmp_path, rtt=0))
    trips = []
    rec = Reconciler(r, lambda *a: trips.append(a))
    r.submit(intent(token_id="Y", price=0.45, size=10), 0)
    r.submit(intent(token_id="N", price=0.50, size=6), 0)
    assert not rec.confirm_zero_open()
    fills = r.on_trade("Y", 0.40, 1, "SELL", 10) + r.on_trade("N", 0.30, 1, "SELL", 10)
    assert rec.reconcile(fills) == [] and trips == []
    merges = rec.merge_pairs(20)
    assert [(m["cid"], m["size"]) for m in merges] == [("c1", 6)]
    assert merges[0]["edge"] == pytest.approx(6 * (1 - 0.45 - 0.50))  # locked edge 1 - p - q per pair
    assert r.positions == {"Y": 4, "N": 0} and r.state.cash == pytest.approx(-4.5 - 3.0 + 6)
    assert rec.merge_pairs(30) == [] and rec.reconcile(fills) == []    # fills minus merges still match
    r2 = router(tmp_path, rtt=0)
    assert r2.positions == r.positions and r2.state.merges == r.state.merges  # merges survive a restart
    assert rec.reconcile(fills[:1])                                     # the ledger lost a fill: mismatch
    assert trips[-1][0] == "global" and trips[-1][2] == "reconciler"
    trips.clear()
    r.state.positions["Y"] += 1                                         # memory diverges from the journal
    assert any("journal" in b for b in rec.reconcile(fills)) and trips
    r.state.positions["Y"] -= 1
    o = r.submit(intent(price=0.30, size=5), 40)
    assert o.status == "open", r.reasons.get(o.order_id)
    r.cancel_all(50)
    assert rec.confirm_zero_open() and rec.reconcile(fills) == []


def test_expired_maker_does_not_fill_and_bookless_taker_is_killed(tmp_path):
    r = with_books(router(tmp_path, rtt=0))
    o = r.submit(intent(price=0.45, size=10), 0)
    assert r.on_trade("Y", 0.44, 1.0, "SELL", o.intent.expiry_ms + 1) == []  # trade through, but after GTD expiry
    assert o.status == "expired"
    r2 = router(tmp_path / "b", rtt=0)                                     # no books at all
    t = r2.submit(intent(kind="taker", price=0.50, size=5), 0)
    if t.status != "rejected":                                             # router may refuse up front (also safe)
        r2.poll(10_000)
        assert t.status == "expired" and r2.positions.get("Y", 0) == 0


# ---------- live router: a fill the venue reconcile finds must reach the caller ----------

class FakeVenue:
    """Just the L2Client calls the router makes, with one acked order that the venue reports as matched."""

    def __init__(self):
        self.filled = "5"

    def require_live(self):
        pass

    def post_orders(self, orders, post_only=True):
        return [{"success": True, "orderID": "0xabc", "status": "matched"} for _ in orders]

    def open_orders(self):
        return []  # filled, so no longer open at the venue

    def get_order(self, oid):
        return {"status": "MATCHED", "size_matched": self.filled, "associate_trades": ["t1"]}

    def cancel(self, oid):
        return {"canceled": []}

    def cancel_all(self):
        return {"canceled": []}


class FakeSigner:
    def sign(self, i, m, exp_s, otype):
        return "0xabc", {"order": i.token_id}


def live_router(tmp_path, now=1_000):
    from trader.live.router import LiveRouter
    return LiveRouter({"c1": MKT}, FakeVenue(), FakeSigner(), lambda *a: None, tmp_path / "live.jsonl",
                      now_ms=lambda: now)


def test_venue_reconcile_hands_its_fills_to_the_caller_so_the_ledger_cannot_miss_them(tmp_path):
    """16 Nov: a taker filled between submit and the periodic venue check. reconcile_venue journaled the fill, the
    loop never recorded it, and the next reconcile saw a position the ledger lacked: HALTED, 40 min of no trading."""
    r = live_router(tmp_path)
    o = r.submit(intent(kind="taker", price=0.85, size=5, expiry_ms=9_000), 1_000)
    assert o.status == "open", r.reasons.get(o.order_id)
    assert r.positions == {} and r.recon_fills == []

    lines = r.reconcile_venue(r.client.open_orders(), 2_000)
    assert lines and "absent at the venue" in lines[0]
    assert r.positions == {"Y": 5.0}                    # the journal and memory now hold the fill
    assert [(f.order_id, f.size, f.token_id) for f in r.recon_fills] == [("0xabc", 5.0, "Y")]

    # what the loop does with it: record it, then the comparison that halted the run is clean
    rec = Reconciler(r, lambda *a: None)
    fills = [Fill(**{k: getattr(f, k) for k in ("order_id", "strategy", "cid", "token_id", "side", "price", "size",
                                                "ts_ms", "maker", "fee")}) for f in r.recon_fills]
    assert rec.reconcile(fills) == []                   # recorded: memory and the ledger agree

