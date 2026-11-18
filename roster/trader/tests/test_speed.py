"""WP1-E tests: btc-speed detector, market mapping, buy rule, latency stamps, pre-registration (E1-E5)."""
import pathlib

import numpy as np
import pandas as pd
import pytest

from research.measure.latency import detect_events
from trader.contracts import Book, MarketInfo
from trader.engines.speed import MAX_SHARES, PREREG, MoveDetector, SpeedEngine, duration_min

T0 = 1_790_786_700_000  # 2026-09-30 16:45:00Z, a 15m and a 5m window start
MIN = 60_000


def mkt(cid, asset="BTC", start=T0, dur=5):
    name = {"BTC": "Bitcoin", "ETH": "Ethereum"}[asset]
    q = f"{name} Up or Down - September 30, 12:45PM-{'12:50PM' if dur == 5 else '1:00PM'} ET"
    return MarketInfo(cid=cid, token_yes=cid + "-up", token_no=cid + "-down", mode="crypto-fast", question=q,
                      rules_sha256="r", tick_size=0.01, min_size=5, fee_rate=0.07, neg_risk=False,
                      end_ms=start + dur * MIN, event_group=f"{asset}-{dur}m@{start}", asset=asset, kind="updown")


def books_for(markets, now, ask=0.6, size=50.0, age_ms=100):
    return {t: Book(t, [(ask - 0.02, 50.0)], [(ask, size)], now - age_ms)
            for m in markets.values() for t in (m.token_yes, m.token_no)}


def run(engine, ticks, markets, books=None, asset="BTC", recv_lag=40):
    """Feed (ts_ms, price) ticks; returns all intents. now_ms = receive time = tick + recv_lag."""
    out = []
    for ts, px in ticks:
        now = ts + recv_lag
        out += engine.on_tick(now, markets, books if books is not None else books_for(markets, now),
                              {asset: {"price": px, "ts_ms": ts, "recv_ms": now}}, {})
    return out


def jump_ticks(start_ms, bp, n_before=10):
    """Flat for n_before seconds, then one tick moved by `bp`."""
    flat = [(start_ms + i * 1000, 100_000.0) for i in range(n_before)]
    return flat + [(start_ms + n_before * 1000, 100_000.0 * np.exp(bp / 1e4))]


# ---------- E1 detector ----------

def test_no_event_before_threshold_then_fires_on_crossing_tick():
    d = MoveDetector(5, 10, 60)
    px = [100.0] * 6 + [100.0 * np.exp(k / 1e4) for k in (3, 6, 9, 9.99, 10.01)]
    hits = [d.update(i * 1000, p) for i, p in enumerate(px)]
    assert hits[:-1] == [None] * (len(px) - 1)
    assert hits[-1][0] == 1 and hits[-1][1] == pytest.approx(10.01)


def test_fires_within_the_second_on_the_first_crossing_tick():
    d = MoveDetector(5, 10, 60)
    for s in range(6):
        assert d.update(s * 1000 + 500, 100.0) is None
    assert d.update(6000 + 100, 100.05) is None          # 5 bp
    assert d.update(6000 + 300, 99.9)[0] == -1           # -10 bp vs the close of second 1, mid-second
    assert d.update(6000 + 900, 99.8) is None            # same move continues: cooldown


def test_one_event_per_cooldown():
    d = MoveDetector(5, 10, 60)
    px, events = 100.0, []
    for s in range(400):                                  # a steady 3 bp/s rise: always above threshold
        px *= np.exp(3e-4)
        if d.update(s * 1000, px):
            events.append(s)
    assert events == [5, 66, 127, 188, 249, 310, 371]     # first at 5 s of history, then every cooldown + 1 s
    assert all(b - a > 60 for a, b in zip(events, events[1:]))


def _engine_events(ts_s, close):
    d = MoveDetector(5, 10, 60)
    return [(s, h[0]) for s, c in zip(ts_s, close) if (h := d.update(int(s) * 1000, float(c)))]


def test_matches_phase0_detector_on_random_walk():
    rng = np.random.default_rng(1)
    close = 50_000 * np.exp(np.cumsum(rng.normal(0, 4e-4, 30_000)))
    ts = np.arange(1_700_000_000, 1_700_030_000)
    ours = _engine_events(ts, close)
    assert len(ours) > 50
    assert ours == [(int(s), d) for s, d in detect_events(ts, close, 5, 10, 60)]


def test_uses_no_future_ticks():
    """Events up to tick k are identical whatever comes after k (prefix invariance)."""
    rng = np.random.default_rng(2)
    a = 50_000 * np.exp(np.cumsum(rng.normal(0, 4e-4, 5000)))
    b = a.copy()
    k = 2500
    b[k:] = b[k - 1] * np.exp(np.cumsum(rng.normal(0, 8e-4, 5000 - k)))  # different future
    ts = np.arange(5000)
    ea, eb = _engine_events(ts, a), _engine_events(ts, b)
    assert [e for e in ea if e[0] < k] == [e for e in eb if e[0] < k]
    assert ea != eb
    assert _engine_events(ts[:k], a[:k]) == [e for e in ea if e[0] < k]


BN = pathlib.Path(__file__).resolve().parents[2] / "research/measure/data/binance1s/BTCUSDT-1s-2026-04-01.parquet"


@pytest.mark.skipif(not BN.exists(), reason="Phase 0 Binance 1s klines not downloaded")
def test_matches_phase0_detector_on_a_real_binance_day():
    bn = pd.read_parquet(BN)
    s = bn.assign(t=bn.open_time // 1000).drop_duplicates("t").set_index("t").close
    s = s.reindex(np.arange(s.index.min(), s.index.max() + 1)).ffill()
    ours = _engine_events(s.index.to_numpy(), s.to_numpy())
    assert ours == [(int(t), d) for t, d in detect_events(s.index.to_numpy(), s.to_numpy(), 5, 10, 60)]


# ---------- E2 mapping ----------

def test_duration_from_real_questions():
    assert duration_min("Bitcoin Up or Down - September 30, 12:45PM-1:00PM ET") == 15
    assert duration_min("Bitcoin Up or Down - September 30, 1:05PM-1:10PM ET") == 5
    assert duration_min("Bitcoin Up or Down - September 30, 11:55PM-12:00AM ET") == 5
    assert duration_min("Bitcoin Up or Down - September 30, 1PM ET") is None


def test_maps_to_open_5m_and_15m_and_favoured_token():
    markets = {m.cid: m for m in (
        mkt("b5", dur=5), mkt("b15", dur=15),
        mkt("b5-next", start=T0 + 5 * MIN), mkt("b5-prev", start=T0 - 5 * MIN),
        mkt("e5", asset="ETH"),
        MarketInfo("h1", "h1-up", "h1-down", "crypto-hourly", "Bitcoin Up or Down - September 30, 12PM ET", "r",
                   0.01, 5, 0.07, False, T0 + 15 * MIN, "BTC@h", "BTC", None, "updown"))}
    up = run(SpeedEngine(), jump_ticks(T0 + 20_000, 12), markets)
    assert sorted((i.cid, i.token_id) for i in up) == [("b15", "b15-up"), ("b5", "b5-up")]
    down = run(SpeedEngine(), jump_ticks(T0 + 20_000, -12), markets)
    assert sorted(i.token_id for i in down) == ["b15-down", "b5-down"]


def test_skips_market_about_to_end_and_stale_book():
    markets = {m.cid: m for m in (mkt("b5", dur=5), mkt("b15", dur=15))}
    e = SpeedEngine()
    ticks = jump_ticks(T0 + 5 * MIN - 50_000 - 10_000, 12)   # event 50 s before the 5m market ends
    assert [i.cid for i in run(e, ticks, markets)] == ["b15"]
    assert e.events[-1]["markets"] == {"b5": "ends too soon", "b15": "trade"}

    e = SpeedEngine()
    now = T0 + 30_000 + 40
    stale = books_for(markets, now, age_ms=6000)
    assert run(e, jump_ticks(T0 + 20_000, 12), markets, stale) == []
    assert set(e.events[-1]["markets"].values()) == {"stale book"}


def test_skips_move_that_started_before_the_window():
    markets = {"b5": mkt("b5", start=T0 + 7_000)}      # opened 3 s before the event; the move began earlier
    e = SpeedEngine()
    assert run(e, jump_ticks(T0, 12), markets) == []
    assert e.events[-1]["markets"] == {"b5": "move started before the window"}


def test_live_warmup_skips_signals_until_it_ends():
    markets = {m.cid: m for m in (mkt("b5", dur=5), mkt("b15", dur=15))}
    e = SpeedEngine()
    e.warm_until = T0 + 60_000                           # the signal at T0 + 30 s falls inside the warm-up
    assert run(e, jump_ticks(T0 + 20_000, 12), markets) == []
    assert set(e.events[-1]["markets"].values()) == {"warming up after start"}
    e = SpeedEngine()
    e.warm_until = T0 + 10_000                           # over before the signal: trades as usual
    assert sorted(i.cid for i in run(e, jump_ticks(T0 + 20_000, 12), markets)) == ["b15", "b5"]


def test_v4_add_buys_one_more_on_the_held_side_only():
    from trader.engines import speed as S
    markets = {m.cid: m for m in (mkt("b5", dur=5), mkt("b15", dur=15))}

    def fire(version, positions):
        e = SpeedEngine(version=version)
        out = []
        for ts, px in jump_ticks(T0 + 20_000, 12):
            now = ts + 40
            out += e.on_tick(now, markets, books_for(markets, now), {"BTC": {"price": px, "ts_ms": ts, "recv_ms": now}}, positions)
        return sorted(i.token_id for i in out), e.events[-1]["markets"]

    add = S.VERSION_V4_BYBIT_ADD
    assert fire(add, {"b5-up": 5.0})[0] == ["b15-up", "b5-up"]                       # one add on the side we hold
    assert fire(add, {"b5-up": 10.0}) == (["b15-up"], {"b5": "already added once", "b15": "trade"})
    assert fire(add, {"b5-down": 5.0}) == (["b15-up"], {"b5": "holding the other side", "b15": "trade"})
    assert fire(S.VERSION_V4_BYBIT, {"b5-up": 5.0})[1]["b5"] == "already holding this market"   # v4b unchanged


def test_repeated_ref_on_book_updates_does_not_refire():
    markets = {"b5": mkt("b5")}
    e = SpeedEngine()
    ticks = jump_ticks(T0 + 20_000, 12)
    assert len(run(e, ticks, markets)) == 1
    assert run(e, [ticks[-1]] * 3, markets) == []     # same ref seen again on later book updates


# ---------- E3 rule ----------

@pytest.mark.parametrize("ask,size,trades", [(0.6, 5, True), (0.6, 4.99, False), (0.90, 50, True),
                                             (0.91, 50, False)])
def test_buy_rule_size_and_max_price(ask, size, trades):
    markets = {"b5": mkt("b5")}
    now = T0 + 30_000 + 40
    out = run(SpeedEngine(), jump_ticks(T0 + 20_000, 12), markets, books_for(markets, now, ask=ask, size=size))
    assert bool(out) is trades
    for i in out:
        assert (i.side, i.kind, i.size, i.strategy) == ("BUY", "taker", 5.0, "btc-speed")
        assert i.price == round(min(0.90, ask + 0.02), 6) and i.fair == ask and i.expiry_ms == now + 2000  # v2 slip cap


def test_never_sizes_above_max_shares():
    with pytest.raises(ValueError):
        SpeedEngine({"shares": MAX_SHARES + 0.0000001})


def test_eth_is_ignored():
    markets = {"e5": mkt("e5", asset="ETH"), "b5": mkt("b5")}
    e = SpeedEngine()
    assert run(e, jump_ticks(T0 + 20_000, 50), markets, asset="ETH") == []
    assert e.events == [] and "ETH" not in e.det


def test_v4_eth_trades_eth_markets_only():
    markets = {"e5": mkt("e5", asset="ETH"), "b5": mkt("b5")}
    now = T0 + 30_000 + 40
    e = SpeedEngine(version="4-eth")
    [i] = run(e, jump_ticks(T0 + 20_000, 7), markets, books_for(markets, now), asset="ETH")
    assert i.cid == "e5" and (i.price, i.size) == (0.7, 5.0) and set(e.det) == {"ETH"}  # v4 rule, ETH move
    assert run(SpeedEngine(version="4-eth"), jump_ticks(T0 + 20_000, 7), markets, books_for(markets, now)) == []


def test_v5_rv30_matches_the_replay_feature():
    """Live rv30 (one tick per second) equals research.replay.replay.features' rv30 on the same ticks."""
    from research.replay.replay import features
    from trader.engines.speed import RealisedVol
    rng = np.random.default_rng(7)
    ts = np.arange(T0, T0 + 40 * MIN, 1000)
    px = 100_000 * np.exp(np.cumsum(rng.normal(0, 3e-5, len(ts))))
    v = RealisedVol()
    for a, b in zip(ts[:-1].tolist(), px[:-1].tolist()):
        v.add(a, b)
    t = int(ts[-1])
    assert abs(v.rv30(t) - features(ts, px, t, 1, [])["rv30"]) < 1e-9
    assert RealisedVol().rv30(t) is None


def _calm_then_jump(start, step_bp):
    """29 min of one tick per second alternating +-step_bp each minute, flat until the window opens, then a 7 bp jump."""
    ticks = [(start + i * 1000, 100_000.0 * np.exp((step_bp if i % 120 < 60 else -step_bp) / 1e4) if i < 29 * 60
              else 100_000.0) for i in range(31 * 60)]
    return ticks + jump_ticks(ticks[-1][0] + 1000, 7)


def test_v5_trades_a_calm_signal_and_skips_a_volatile_one():
    start = T0 - 31 * MIN
    for step, trades, why in ((0.5, 1, "trade"), (40.0, 0, "volatile market")):
        markets = {"b5": mkt("b5")}
        e = SpeedEngine(version=5)
        ticks = _calm_then_jump(start, step)
        now = ticks[-1][0] + 40
        out = run(e, ticks, markets, books_for(markets, now))
        assert len(out) == trades and e.events[-1]["markets"]["b5"] == why
        assert (e.events[-1]["rv30"] < 5.5) == (trades == 1)


def test_v5_skips_until_30_minutes_of_history():
    markets = {"b5": mkt("b5")}
    e = SpeedEngine(version=5)
    assert run(e, jump_ticks(T0 + 20_000, 7), markets, books_for(markets, T0 + 30_040)) == []
    assert e.events[-1]["markets"]["b5"] == "no volatility history"


# ---------- E4 latency ----------

def test_trade_records_carry_four_latency_stamps():
    markets = {"b5": mkt("b5"), "b15": mkt("b15", dur=15)}
    e = SpeedEngine(rtt_ms=180)
    out = run(e, jump_ticks(T0 + 20_000, 12), markets, recv_lag=40)
    assert len(e.trades) == len(out) == 2
    for t in e.trades:
        assert t["binance_ms"] == T0 + 30_000
        assert t["recv_ms"] == t["decision_ms"] == T0 + 30_040
        assert t["arrival_ms"] == t["decision_ms"] + 150 + 180
        assert t["intent"] in out and t["ask"] == 0.6 and t["ask_size"] == 50.0


# ---------- E5 pre-registration ----------

def test_preregistration_complete():
    for k in ("test_id", "strategy", "statistic", "cluster", "alpha", "pass_rule", "pass_z", "n", "futility_rule",
              "futility_z", "futility_n", "params"):
        assert PREREG[k] not in (None, "")
    assert (PREREG["pass_z"], PREREG["n"], PREREG["futility_z"], PREREG["futility_n"]) == (2.0, 200, -1.0, 100)
    assert "resolution" in PREREG["statistic"] and "fee" in PREREG["statistic"]
    assert PREREG["params"]["assets"] == ("BTC",) and PREREG["strategy"] == SpeedEngine.name


# ---------- v2 guards (day-1 anomalies, 8 Oct) ----------

def test_v2_never_trades_a_market_already_held():
    """Day 1 bought DOWN at 0.86 then UP at 0.90 on one 15m market: a pair worth $1 for $1.76, a locked loss."""
    markets = {"b5": mkt("b5"), "b15": mkt("b15", dur=15)}
    e, out = SpeedEngine(), []
    for ts, px in jump_ticks(T0 + 20_000, 12):
        now = ts + 40
        out += e.on_tick(now, markets, books_for(markets, now), {"BTC": {"price": px, "ts_ms": ts, "recv_ms": now}},
                         {"b15-down": 5.0})                                # already hold the other side of b15
    assert [i.cid for i in out] == ["b5"]
    assert e.events[-1]["markets"]["b15"] == "already holding this market"


def test_v2_skips_a_stale_signal():
    markets = {"b5": mkt("b5")}
    e = SpeedEngine()
    assert run(e, jump_ticks(T0 + 20_000, 12), markets, recv_lag=1500) == []   # tick reached us 1.5 s late
    assert e.events[-1]["markets"] == {"b5": "stale signal"}


def test_v2_limit_is_ask_plus_slip_not_the_cap():
    markets = {"b5": mkt("b5")}
    now = T0 + 30_000 + 40
    out = run(SpeedEngine(), jump_ticks(T0 + 20_000, 12), markets, books_for(markets, now, ask=0.48))
    assert [i.price for i in out] == [0.5]                                  # v1 sent 0.90 and filled at 0.58


def test_v2_statistic_excludes_trades_before_its_preregistration():
    from nightly.scorer import speed_stat
    f = lambda oid, rec: {"strategy": "btc-speed", "order_id": oid, "cid": "c", "token_id": "up", "size": 5.0,
                          "price": 0.6, "fee": 0.0, "ts_ms": rec, "recorded_ms": rec}
    out = speed_stat([f("v1-trade", 100), f("v2-trade", 300)], {"c": {"winner": "up"}}, since_ms=200)
    assert [t["order_id"] for t in out["trades"]] == ["v2-trade"]


# ---------- v3: quick exit + 0.75 cap (8 Oct) ----------

def test_v3_caps_the_buy_price_at_075():
    markets = {"b5": mkt("b5")}
    now = T0 + 30_000 + 40
    assert run(SpeedEngine(version=3), jump_ticks(T0 + 20_000, 12), markets, books_for(markets, now, ask=0.76)) == []
    assert len(run(SpeedEngine(version=3), jump_ticks(T0 + 20_000, 12), markets, books_for(markets, now, ask=0.70))) == 1


def test_v3_sells_the_position_8s_after_the_fill_and_retries():
    from trader.contracts import Fill
    markets, e = {"b5": mkt("b5")}, SpeedEngine(version=3)
    t = T0 + 30_000
    e.on_fill(Fill("o1", "btc-speed", "b5", "b5-up", "BUY", 0.6, 5.0, t, False, 0.08))
    books = lambda now: {"b5-up": Book("b5-up", [(0.65, 50.0)], [(0.67, 50.0)], now - 100)}
    pos = {"b5-up": 5.0}
    assert e.exit_intents(t + 7_900, markets, books(t + 7_900), pos) == []          # not due yet
    [i] = e.exit_intents(t + 8_000, markets, books(t + 8_000), pos)
    assert (i.side, i.size, i.price, i.kind, i.reduces_exposure) == ("SELL", 5.0, 0.63, "taker", True)
    assert e.exit_intents(t + 8_500, markets, books(t + 8_500), pos) == []          # wait 1 s before a retry
    assert len(e.exit_intents(t + 9_000, markets, books(t + 9_000), pos)) == 1      # not filled: retry
    assert e.exit_intents(t + 10_000, markets, books(t + 10_000), {}) == [] and e.exit_due == {}  # sold: done


def test_v3_holds_to_resolution_near_the_end_and_v2_never_exits():
    from trader.contracts import Fill
    markets, e = {"b5": mkt("b5")}, SpeedEngine(version=3)
    end = markets["b5"].end_ms
    e.on_fill(Fill("o1", "btc-speed", "b5", "b5-up", "BUY", 0.6, 5.0, end - 20_000, False, 0.08))
    bk = {"b5-up": Book("b5-up", [(0.65, 50.0)], [(0.67, 50.0)], end - 12_100)}
    assert e.exit_intents(end - 12_000, markets, bk, {"b5-up": 5.0}) == [] and e.exit_due == {}
    v2 = SpeedEngine()
    v2.on_fill(Fill("o1", "btc-speed", "b5", "b5-up", "BUY", 0.6, 5.0, T0, False, 0.08))
    assert v2.exit_due == {}


def test_tape_reprice_uses_real_takers_in_our_matched_second(tmp_path, monkeypatch):
    import json
    from nightly import scorer
    from nightly.scorer import speed_stat, tape_reprice
    fee = lambda p, n=5: n * 0.07 * p * (1 - p)
    f = {"strategy": "btc-speed", "order_id": "o", "cid": "c", "token_id": "up", "side": "BUY", "size": 5.0,
         "price": 0.6, "fee": fee(0.6), "ts_ms": 100_500}
    tr = speed_stat([f], {"c": {"winner": "up"}})["trades"]
    monkeypatch.setattr(scorer, "RACE_AHEAD", 0.5)                        # the arithmetic below, whatever the fit
    tape = [["up", "BUY", 0.70, 102, 3], ["dn", "SELL", 0.20, 103, 4],   # in the window: 3 up @0.70, then 4 @ 1-0.20
            ["up", "SELL", 0.50, 102, 9], ["up", "BUY", 0.55, 99, 9]]    # a sale (bid) and a print before the window
    calls = []
    out = tape_reprice(tmp_path, tr, {"o": 100_500}, lambda cid, lo, hi: calls.append((lo, hi)) or tape)
    val = lambda p: 5 * (1 - p) - fee(p)                                  # the trade bought at p instead of 0.60
    assert out["n"] == 1 and out["paper"] == pytest.approx(2.0 - fee(0.6)) and calls == [(90, 110)]
    assert out["best"] == pytest.approx(val(0.7)) and out["typical"] == pytest.approx(val(0.75))
    assert out["gap_median"] == pytest.approx(0.15) and out["trades"][0]["tape_median"] == pytest.approx(0.75)
    # RACE_AHEAD 0.5 of 7 shares: the first 3 @0.70 and 0.5 @0.80 beat us, we get the other 3.5 @0.80
    assert out["live_shares"] == pytest.approx(3.5) and out["trades"][0]["live_px"] == pytest.approx(0.8)
    assert out["live"] == pytest.approx(3.5 * val(0.8) / 5)
    assert tape_reprice(tmp_path, tr, {"o": 100_500}, None) == out          # cache only, no GET
    assert tape_reprice(tmp_path, tr, {"o": 100_500}, None, {"o": 0.75})["live_shares"] == 0   # what is left is above
    monkeypatch.setattr(scorer, "RACE_AHEAD", 0.0)
    first = tape_reprice(tmp_path, tr, {"o": 100_500}, None)
    assert first["live_shares"] == pytest.approx(5) and first["trades"][0]["live_px"] == pytest.approx((3 * .7 + 2 * .8) / 5)
    assert first["live"] == pytest.approx((3 * val(0.7) + 2 * val(0.8)) / 5)   # each slice at its own price and fee
    sell = {**f, "order_id": "o", "side": "SELL", "price": 0.65, "fee": fee(0.65), "ts_ms": 100_508}   # v3 exit
    [v3] = tape_reprice(tmp_path, speed_stat([f, sell], {})["trades"], {"o": 100_500}, None)["trades"]
    assert v3["best"] == pytest.approx(5 * 0.65 - fee(0.65) - 5 * 0.7 - fee(0.7))   # the sale keeps its paper price
    (tmp_path / "tape.json").write_text(json.dumps({"c": [["up", "BUY", 0.7, 102]], "o": []}))   # pre-15 Oct cache
    assert tape_reprice(tmp_path, tr, {"o": 100_500}, None)["n"] == 0
    tape_reprice(tmp_path, tr, {"o": 100_500}, lambda cid, lo, hi: tape)
    assert list(json.loads((tmp_path / "tape.json").read_text())) == ["o"]   # refetched per order; the old key is gone


def test_walk_skips_the_racers_in_time_then_sweeps_cheapest_under_the_limit():
    from nightly.scorer import walk
    assert walk([(1, .9, 2), (2, .6, 4), (3, .7, 9)], 2, .75, 5) == [(.6, 4), (.7, 1)]
    assert walk([(1, .7, 3), (2, .8, 4), (3, .9, 9)], 3.5, .85, 5) == [(.8, 3.5)]
    assert walk([(1, .7, 3), (2, .8, 4), (3, .9, 9)], 0, .65, 5) == []


def test_fetch_tape_keeps_the_window_and_refuses_a_cut_one():
    from nightly import scorer
    row = lambda ts: {"token_id": "up", "side": "BUY", "price": "0.5", "timestamp": ts, "size": "2"}
    asked = []

    def page(rows, more=False, cursor=None):
        return {"data": rows, "pagination": {"has_more": more, "next_cursor": cursor}}

    def get(url, params):   # v2: cursor pages, newest first, no start/end filter on the API side
        asked.append((url, params))
        return page([row(111), row(105), row(99)])

    assert scorer.fetch_tape("c", 100, 110, get) == [["up", "BUY", 0.5, 105, 2.0]]
    assert asked[0][1]["condition"] == "c" and asked[0][1]["taker_only"] == "true" and "cursor" not in asked[0][1]

    pages = iter([page([row(120), row(110)], True, "p2"), page([row(110), row(105)], True, "p3"),
                  page([row(99)])])
    assert scorer.fetch_tape("c", 100, 110, lambda url, params: next(pages)) == [["up", "BUY", 0.5, 110, 2.0],
                                                                                 ["up", "BUY", 0.5, 105, 2.0]]
    with pytest.raises(RuntimeError):   # every page full and still newer than the window: the page cap cut it
        scorer.fetch_tape("c", 100, 110, lambda url, params: page([row(105)] * 500, True, "next"))


def test_v3_statistic_counts_the_exit_sale():
    from nightly.scorer import speed_stat
    buy = {"strategy": "btc-speed", "order_id": "b", "cid": "c", "token_id": "up", "side": "BUY", "size": 5.0,
           "price": 0.6, "fee": 0.08, "ts_ms": 100}
    sell = {**buy, "order_id": "s", "side": "SELL", "price": 0.65, "fee": 0.08, "ts_ms": 108}
    out = speed_stat([buy, sell], {}, since_ms=0)                       # sold out: scored without an outcome
    assert out["n"] == 1 and out["pending"] == 0
    assert out["trades"][0]["pnl"] == pytest.approx(5 * 0.65 - 5 * 0.6 - 0.16)


# ---------- v4: 2 s / 6 bp detector, 0.85 cap, 10c slippage, hold (9 Oct) ----------

def test_v4_fires_on_6bp_where_v2_does_not_and_holds():
    markets = {"b5": mkt("b5")}
    now = T0 + 30_000 + 40
    ticks = jump_ticks(T0 + 20_000, 7)
    assert run(SpeedEngine(), ticks, markets, books_for(markets, now)) == []
    v4 = SpeedEngine(version=4)
    [i] = run(v4, ticks, markets, books_for(markets, now))
    assert (i.price, i.size) == (0.7, 5.0)                     # ask 0.60 + 10c
    assert "exit_after_ms" not in v4.p                          # held to resolution, as v2


def test_v4_limit_never_above_085():
    markets = {"b5": mkt("b5")}
    now = T0 + 30_000 + 40
    [i] = run(SpeedEngine(version=4), jump_ticks(T0 + 20_000, 7), markets, books_for(markets, now, ask=0.80))
    assert i.price == 0.85
    assert run(SpeedEngine(version=4), jump_ticks(T0 + 20_000, 7), markets, books_for(markets, now, ask=0.86)) == []


def test_detector_ignores_a_jump_across_a_feed_gap():
    """12 Oct: after an 8 h sleep the first tick vs the pre-sleep price read as +51 bp."""
    d = MoveDetector(2, 6.0, 60)
    for i in range(10):
        assert d.update(T0 + i * 1000, 100_000.0) is None
    assert d.update(T0 + 3_600_000, 100_600.0) is None          # +60 bp, but an hour after the last tick
    assert d.update(T0 + 3_601_000, 100_600.0) is None
    assert d.update(T0 + 3_603_000, 100_600.0 * np.exp(7 / 1e4)) is not None   # a real move after it still fires


def test_v5_seeded_from_minute_closes_trades_right_after_a_restart():
    from trader.engines.speed import RealisedVol
    v = RealisedVol()
    start = T0 - 31 * MIN
    v.seed({start + i * MIN: 100_000.0 * (1 + 1e-5 * (i % 2)) for i in range(31)})  # calm: ~1 bp swings
    rv = v.rv30(T0 + 10_000)
    assert rv is not None and rv < 5.5
    markets = {"b5": mkt("b5")}
    e = SpeedEngine(version=5)
    e.vol["BTC"] = v
    now = T0 + 30_040
    out = run(e, jump_ticks(T0 + 20_000, 7), markets, books_for(markets, now))
    assert len(out) == 1 and e.events[-1]["markets"]["b5"] == "trade"


def test_compound_size_scales_with_the_account_within_its_bounds():
    e = SpeedEngine(version="4-eth-bybit-c")
    assert e.size_for(100) == 5.0                     # no account value yet: the base size
    for equity, ask_size, want in ((80.86, 100, 8), (30, 100, 5), (500, 100, 14), (120, 9.5, 9), (120, 6, 6)):
        e.equity = equity
        assert e.size_for(ask_size) == want, (equity, ask_size)
    assert SpeedEngine(version="4-eth-bybit").size_for(100) == 5.0   # the control run never compounds


# ---------- v6: v4 on Bybit + the 14 Oct skips ----------

def test_v6_skips_the_coin_flip_band_and_early_15m_windows():
    from trader.engines.speed import VERSION_V6_BYBIT, VERSION_V6_ETH_BYBIT
    now, ticks = T0 + 30_000 + 40, jump_ticks(T0 + 20_000, 7)
    markets = {"b5": mkt("b5"), "b15": mkt("b15", dur=15)}       # 30 s in: the 15m window has 14.5 min left
    v6 = SpeedEngine(version=VERSION_V6_BYBIT)
    assert run(v6, ticks, markets, books_for(markets, now, ask=0.45)) == []
    assert v6.events[-1]["markets"] == {"b5": "ask in the skip band", "b15": "too much time left"}
    [i] = run(SpeedEngine(version=VERSION_V6_BYBIT), ticks, markets, books_for(markets, now, ask=0.30))  # 0.30 is outside
    assert i.cid == "b5" and i.price == 0.4
    eth = {"e15": mkt("e15", asset="ETH", dur=15)}
    assert len(run(SpeedEngine(version=VERSION_V6_ETH_BYBIT), ticks, eth, books_for(eth, now, ask=0.6), asset="ETH")) == 1
    e6 = SpeedEngine(version=VERSION_V6_ETH_BYBIT)                 # ETH keeps its >600 s trades, skips the band
    assert run(e6, ticks, eth, books_for(eth, now, ask=0.5), asset="ETH") == []
    assert e6.events[-1]["markets"] == {"e15": "ask in the skip band"}


def test_maker_rests_one_tick_under_the_ask_on_15m_markets_only():
    from trader.engines.speed import VERSION_MAKER_BYBIT, VERSION_MAKER_ETH_BYBIT
    now, ticks = T0 + 30_000 + 40, jump_ticks(T0 + 20_000, 7)
    markets = {"b5": mkt("b5"), "b15": mkt("b15", dur=15)}
    mk = SpeedEngine(version=VERSION_MAKER_BYBIT)
    [i] = run(mk, ticks, markets, books_for(markets, now, ask=0.62, size=2.0))   # thin ask: fine for a maker
    assert (i.cid, i.token_id, i.side, i.kind, i.price, i.size) == ("b15", "b15-up", "BUY", "maker", 0.61, 5.0)
    assert i.expiry_ms == now + 155_000            # >= the kernel's GTD floor (now + 2 min + 30 s margin)
    assert "b5" not in mk.events[-1]["markets"]    # 5m windows are not mapped (their GTD could not fit)
    late = T0 + 11 * MIN                           # 4 min left: under min_left_s, the GTD would pass end - 2 min
    assert run(SpeedEngine(version=VERSION_MAKER_BYBIT), jump_ticks(late - 10_000, 7), markets,
               books_for(markets, late + 40, ask=0.62)) == []
    eth = {"e15": mkt("e15", asset="ETH", dur=15)}
    [e] = run(SpeedEngine(version=VERSION_MAKER_ETH_BYBIT), ticks, eth, books_for(eth, now, ask=0.5), asset="ETH")
    assert e.kind == "maker" and e.price == 0.49


def test_tape_reprice_keeps_a_maker_fill_at_its_paper_price_without_a_get(tmp_path):
    from nightly.scorer import speed_stat, tape_reprice
    f = {"strategy": "btc-speed", "order_id": "m", "cid": "c", "token_id": "up", "side": "BUY", "size": 5.0,
         "price": 0.61, "fee": 0.0, "ts_ms": 100_500, "maker": True}
    tr = speed_stat([f], {"c": {"winner": "up"}})["trades"]
    out = tape_reprice(tmp_path, tr, {}, lambda *a: pytest.fail("no tape for a maker fill"))
    assert out["n"] == 1 and out["live"] == out["paper"] == pytest.approx(5 * 0.39) and out["live_shares"] == 5


def test_live_min_notional_sizes_cheap_bets_to_one_dollar_only():
    markets = {"b5": mkt("b5", dur=5)}
    def fire(ask, floor):
        e = SpeedEngine(version=__import__("trader.engines.speed", fromlist=["x"]).VERSION_V4_BYBIT)
        e.min_notional = floor
        out = []
        for ts, px in jump_ticks(T0 + 20_000, 12):
            now = ts + 40
            out += e.on_tick(now, markets, books_for(markets, now, ask=ask), {"BTC": {"price": px, "ts_ms": ts, "recv_ms": now}}, {})
        return [(i.price, i.size) for i in out]
    assert fire(0.05, 1.0) == [(0.15, 6.67)]                  # 6.67 x 0.15 = 1.0005: just over the venue's $1
    assert fire(0.004, 1.0) == [(0.104, 9.62)]
    assert fire(0.40, 1.0) == [(0.50, 5.0)]                    # already over $1: unchanged
    assert fire(0.05, 0.0) == [(0.15, 5.0)]                    # paper (no floor): unchanged
