"""18 Nov review fixes (paper_v9fix): venue amount precision, the min-price skip, live-like paper fills, the live
ledger's share count on price improvement, and the daily stop across restarts. No network."""
import datetime as dt
import json

import pytest

from trader import realism
from trader.breakers import Breakers
from trader.contracts import Book, Intent, MarketInfo
from trader.engines import speed
from trader.router import PaperRouter, buy_amounts_ok, marketable_buy, replay

MKT = MarketInfo(cid="c1", token_yes="Y", token_no="N", mode="crypto-fast", question="q", rules_sha256="h",
                 tick_size=0.01, min_size=5, fee_rate=0.07, neg_risk=False, end_ms=10_000_000,
                 event_group="BTC-5m@x", asset="BTC", kind="updown")


def fee(C, p, rate):
    return C * rate * p * (1 - p)


def taker(**kw):
    return Intent(**{"strategy": "btc-speed", "cid": "c1", "token_id": "Y", "side": "BUY", "price": 0.84,
                     "size": 5.0, "kind": "taker", "expiry_ms": 3_000, "fair": 0.74, "reason": "test", **kw})


# ---- fix 1: venue amount precision ------------------------------------------------------------------------------
@pytest.mark.parametrize("size,price,ok", [
    (9.81, 0.102, False),   # 1.00062: refused live 18 Nov 00:09
    (9.1, 0.11, False),     # 1.001: refused live (handoff 6.1)
    (5.56, 0.18, False),    # 1.0008
    (5.0, 0.84, True), (5.0, 0.85, True), (5.0, 0.857, False), (5.0, 0.856, True),
    (10.0, 0.102, True), (6.8, 0.15, True), (6.67, 0.15, False),
])
def test_buy_amounts_follow_the_venue_rule(size, price, ok):
    assert buy_amounts_ok(size, price) is ok


def test_buy_amounts_minimum_notional():
    assert buy_amounts_ok(5.0, 0.15, 1.0) is False         # $0.75
    assert buy_amounts_ok(6.8, 0.15, 1.0) is True          # $1.02


def test_marketable_buy_keeps_valid_orders_unchanged():
    for lim in (0.35, 0.5, 0.61, 0.84, 0.85):
        assert marketable_buy(5.0, lim, 0.01, 1.0, max_size=8) == (lim, 5.0)


def test_marketable_buy_smallest_valid_size_at_or_above_the_floor():
    assert marketable_buy(5.0, 0.15, 0.01, 1.0, max_size=8) == (0.15, 6.8)   # was 6.67 (refused): 6.8 x 0.15 = 1.02
    p, s = marketable_buy(5.0, 0.15, 0.01, 1.0, max_size=8)
    assert buy_amounts_ok(s, p, 1.0)


def test_marketable_buy_shades_a_three_decimal_limit_before_growing_the_size():
    assert marketable_buy(5.0, 0.857, 0.001, 1.0, max_size=8, floor_price=0.757) == (0.856, 5.0)


def test_marketable_buy_refuses_when_only_a_size_over_the_cap_would_do():
    # 0.102: whole cents need a multiple of 5 shares and $1 needs > 9.8 -> 10 shares, over the 8-share cap
    assert marketable_buy(5.0, 0.102, 0.001, 1.0, max_size=8, floor_price=0.102) is None
    assert marketable_buy(5.0, 0.102, 0.001, 1.0, max_size=10, floor_price=0.102) == (0.102, 10.0)


def test_marketable_buy_never_below_the_floor_price():
    assert marketable_buy(5.0, 0.857, 0.001, 0.0, max_size=5, floor_price=0.857) is None


# ---- fix 1 + 3: the speed engine's sizing and the min-price skip ---------------------------------------------------
T = 1_790_843_000_000
SPD = MarketInfo("S5", "S5U", "S5D", "crypto-fast", "Bitcoin Up or Down - October 1, 4:22AM-4:27AM ET", "r2",
                 0.01, 5.0, 0.07, False, T + 4 * 60_000, "BTC-5m@2026-10-01T08:22Z", "BTC", None, "updown",
                 "chainlink:BTC/USD")


def fire(eng, ask, tick=0.01):
    """A +15 bp / 2 s Bybit move with the 5m Up token's ask at `ask`. Returns the intents and the event."""
    m = SPD if tick == 0.01 else MarketInfo(**{**SPD.__dict__, "tick_size": tick})
    markets = {m.cid: m}
    books = {"S5U": Book("S5U", [(round(ask - 0.01, 3), 50)], [(ask, 50)], T + 7000)}
    for s in range(7):
        eng.on_tick(T + s * 1000, markets, books, {"BTC": {"price": 84000.0, "ts_ms": T + s * 1000}}, {})
    out = eng.on_tick(T + 7000, markets, books, {"BTC": {"price": 84000.0 * 1.0015, "ts_ms": T + 7000}}, {})
    return out, eng.events[-1]


def test_v9_skips_asks_below_the_min_price_and_v4b_does_not():
    out, ev = fire(speed.SpeedEngine(version=speed.VERSION_V9), 0.30)
    assert out == [] and ev["markets"]["S5"] == "ask below min price"
    out, _ = fire(speed.SpeedEngine(version=speed.VERSION_V4_BYBIT), 0.30)
    assert len(out) == 1                                            # paper_v4b and live are unchanged
    out, _ = fire(speed.SpeedEngine(version=speed.VERSION_V9), 0.35)
    assert len(out) == 1 and out[0].price == pytest.approx(0.45)   # 0.35 itself is allowed


def test_v9_min_price_is_a_parameter():
    eng = speed.SpeedEngine(version=speed.VERSION_V9, params={"min_price": 0.50})
    assert fire(eng, 0.45)[0] == []
    assert speed.version_v9(0.5) == "9-fix-mp0.5" and speed.version_v9(0.35) == speed.VERSION_V9
    assert speed.prereg_v9(0.5)["params"]["min_price"] == 0.5


def test_venue_amounts_sizing_on_the_live_path():
    eng = speed.SpeedEngine(version=speed.VERSION_V4_BYBIT)
    eng.min_notional, eng.venue_amounts = 1.0, True
    out, _ = fire(eng, 0.05)                                        # limit 0.15: $1 floor -> 6.8 shares (was 6.67)
    assert [(i.price, i.size) for i in out] == [(0.15, 6.8)] and buy_amounts_ok(6.8, 0.15, 1.0)
    out, _ = fire(speed.SpeedEngine(version=speed.VERSION_V4_BYBIT), 0.05)
    assert [(i.price, i.size) for i in out] == [(0.15, 5.0)]        # paper runs keep the pre-registered sizing
    eng = speed.SpeedEngine(version=speed.VERSION_V4_BYBIT)
    eng.min_notional, eng.venue_amounts = 1.0, True
    out, ev = fire(eng, 0.002, tick=0.001)                          # limit 0.102: only 10 shares would do
    assert out == [] and ev["markets"]["S5"] == "no venue-valid amount under the share cap"


# ---- fix 4: paper fills like the live venue -------------------------------------------------------------------------
def rz_router(tmp_path, **cfg):
    c = {**realism.load(), **cfg}
    return PaperRouter({"c1": MKT}, rtt_ms=lambda: 100, journal=tmp_path / "j.jsonl", fee=fee, liquidity_once=True,
                       realism=c)


def book(r, asks, t):
    return r.on_book(Book("Y", [(0.70, 100)], asks, t), t)


def test_realism_latency_is_drawn_from_the_live_distribution_and_journaled(tmp_path):
    r = rz_router(tmp_path, kill_mode="off")
    book(r, [(0.80, 100)], 0)
    lat = []
    for k in range(200):
        o = r.submit(taker(expiry_ms=2_000 + k, token_id="Y"), 1_000 + k)
        lat.append(r.state.arrival[o.order_id] - (1_000 + k))
        r.cancel(o.order_id, 0)
        r.state.orders[o.order_id].status = "cancelled"   # test only: free the token for the next draw
    knots = realism.DEFAULTS["latency_knots"]
    assert min(lat) >= knots[0][1] and max(lat) <= knots[-1][1]
    lat.sort()
    assert 700 <= lat[100] <= 1600                                  # median near the live 1115 ms
    assert realism.latency_ms(r.realism, "abc") == realism.latency_ms(r.realism, "abc")   # reproducible


def test_realism_fills_at_the_book_in_force_at_arrival_and_ignores_the_give_up(tmp_path):
    r = rz_router(tmp_path, kill_mode="off", latency_knots=[[0.0, 2500], [1.0, 2500]])
    book(r, [(0.74, 100)], 0)
    o = r.submit(taker(expiry_ms=1_000 + 2_000), 1_000)              # give-up at decision + 2 s
    assert r.state.arrival[o.order_id] == 3_500
    assert book(r, [(0.78, 100)], 2_000) == []                       # moved before we arrive
    fills = book(r, [(0.90, 100)], 4_000)                            # the 0.78 book was in force at 3.5 s
    assert [(f.price, f.size) for f in fills] == [(0.78, pytest.approx(4.2 / 0.78, abs=1e-6))]
    assert sum(f.size * f.price for f in fills) == pytest.approx(4.2, abs=1e-5)   # spends size x limit, as live


def test_default_paper_router_still_kills_late_takers(tmp_path):
    r = PaperRouter({"c1": MKT}, rtt_ms=lambda: 3000, journal=tmp_path / "j.jsonl", fee=fee)
    r.on_book(Book("Y", [(0.70, 100)], [(0.74, 100)], 0), 0)
    o = r.submit(taker(expiry_ms=3_000), 1_000)                      # arrives at 4.15 s, after its 3 s give-up
    assert r.on_book(Book("Y", [(0.70, 100)], [(0.74, 100)], 5_000), 5_000) == []
    assert r.state.orders[o.order_id].status == "expired"


def test_realism_refuses_what_the_venue_refuses(tmp_path):
    r = rz_router(tmp_path, kill_mode="off")
    book(r, [(0.10, 100)], 0)
    bad = r.submit(taker(price=0.11, size=9.1, fair=0.10), 1_000)
    assert bad.status == "rejected" and "max accuracy of 2 decimals" in r.reasons[bad.order_id]
    small = r.submit(taker(price=0.11, size=5.0, fair=0.10), 1_000)
    assert small.status == "rejected" and "min size: 1" in r.reasons[small.order_id]
    plain = PaperRouter({"c1": MKT}, rtt_ms=lambda: 100, journal=tmp_path / "p.jsonl", fee=fee)
    plain.on_book(Book("Y", [(0.09, 100)], [(0.10, 100)], 0), 0)
    assert plain.submit(taker(price=0.11, size=9.1, fair=0.10), 1_000).status == "open"   # existing runs unchanged


def test_realism_kill_rate_tracks_the_live_fill_rate_and_survives_a_restart(tmp_path):
    r = rz_router(tmp_path, latency_knots=[[0.0, 100], [1.0, 100]])
    t, n, filled = 0, 400, 0
    for k in range(n):
        book(r, [(0.80, 100)], t)
        o = r.submit(taker(expiry_ms=t + 3_000), t + 1)
        filled += bool(book(r, [(0.80, 100)], t + 200))
        assert r.state.orders[o.order_id].status in ("filled", "cancelled")
        t += 1_000
    assert abs(filled / n - realism.DEFAULTS["target_fill_rate"]) < 0.08
    assert r.kill.n == n and r.kill.filled == n                      # every order would have filled on the book
    r2 = rz_router(tmp_path)                                         # restart: the counts come back from the journal
    assert (r2.kill.n, r2.kill.filled) == (n, n)
    st = replay(tmp_path / "j.jsonl")
    assert sum(1 for o in st.orders.values() if o.status == "filled") == filled


def test_realism_config_rejects_unknown_settings(tmp_path):
    p = tmp_path / "rz.json"
    p.write_text(json.dumps({"target_fill_rate": 0.5, "typo": 1}))
    with pytest.raises(ValueError):
        realism.load(p)
    p.write_text(json.dumps({"target_fill_rate": 0.5, "comment": "from calibrate_paper_fills"}))
    assert realism.load(p)["target_fill_rate"] == 0.5


# ---- fix 5: live ledger books the shares the venue delivered ---------------------------------------------------------
def test_live_buy_books_the_extra_shares_of_a_price_improved_fill(tmp_path):
    from trader.tests.test_execution import live_router
    r = live_router(tmp_path)
    o = r.submit(taker(price=0.84, size=5, expiry_ms=9_000, fair=0.80), 1_000)
    assert o.status == "open", r.reasons.get(o.order_id)
    fills = r.on_user_event({"event_type": "trade", "id": "t1", "status": "MATCHED", "taker_order_id": "0xabc",
                             "size": "5.25", "price": "0.80", "maker_orders": [], "match_time": "2"}, 2_000)
    assert [(f.size, f.price) for f in fills] == [(5.25, 0.80)]
    assert r.positions == {"Y": 5.25}
    assert r.state.cash == pytest.approx(-(5.25 * 0.80 + fills[0].fee))   # spent 4.20 + fee, not 4.00
    # a later venue query cannot add the order's size again
    assert r._resolve(r.state.orders["0xabc"], {"status": "MATCHED", "size_matched": "5"}, 3_000) == []
    assert r.positions == {"Y": 5.25}


def test_live_buy_share_count_is_capped_by_the_usdc_the_order_may_spend(tmp_path):
    from trader.tests.test_execution import live_router
    r = live_router(tmp_path)
    r.submit(taker(price=0.84, size=5, expiry_ms=9_000), 1_000)
    fills = r.on_user_event({"event_type": "trade", "id": "t1", "status": "MATCHED", "taker_order_id": "0xabc",
                             "size": "9", "price": "0.80", "maker_orders": []}, 2_000)
    assert fills[0].size == pytest.approx(5.25) and fills[0].size * 0.80 <= 4.2 + 1e-9


def test_live_router_refuses_a_buy_whose_usdc_leg_is_not_whole_cents(tmp_path):
    from trader.tests.test_execution import live_router
    r = live_router(tmp_path)
    o = r.submit(taker(price=0.22, size=5.56, expiry_ms=9_000), 1_000)   # 1.2232: the venue refuses it
    assert o.status == "rejected" and "whole cents" in r.reasons[o.order_id]


# ---- fix 2: the daily stop survives restarts (same run folder, same UTC day) ----------------------------------------
class K:
    features = frozenset()

    def __init__(self):
        self.trips = []

    def trip(self, *a):
        self.trips.append(a)


def ms(y, m, d, h=0):
    return int(dt.datetime(y, m, d, h, tzinfo=dt.UTC).timestamp() * 1000)


def test_daily_start_mark_is_kept_across_restarts_on_the_same_utc_day(tmp_path):
    b = Breakers(K(), daily_dd=0.35, run_dir=tmp_path)
    b.on_equity(50.0, ms(2026, 11, 18, 1))
    k2 = K()
    b2 = Breakers(k2, daily_dd=0.35, run_dir=tmp_path)               # a restart, lower equity
    b2.on_equity(35.0, ms(2026, 11, 18, 9))
    assert b2.hwm == 50.0 and json.loads((tmp_path / "daily_start.json").read_text())["mark"] == 50.0
    b2.on_equity(32.0, ms(2026, 11, 18, 10))                         # 36% below the day's start
    assert k2.trips and "daily drawdown" in k2.trips[0][1]
    b3 = Breakers(K(), daily_dd=0.35, run_dir=tmp_path)
    b3.on_equity(40.0, ms(2026, 11, 19, 0))                          # a new UTC day starts a new mark
    assert b3.hwm == 40.0


def test_live_launcher_can_carry_the_days_mark_into_the_new_session(tmp_path):
    from ops.live_session import carry_daily
    old, new = tmp_path / "archive" / "s1", tmp_path / "live"
    old.mkdir(parents=True)
    now = dt.datetime(2026, 11, 18, 9, tzinfo=dt.UTC)
    (old / "daily_start.json").write_text(json.dumps({"day": "2026-11-18", "mark": 37.34}))
    (old / "strategy_start.json").write_text(json.dumps({"day": "2026-11-18", "marks": {"btc-speed": 37.34}}))
    c = carry_daily(old, new, flow=-20.10, now=now)                  # a 20.10 withdrawal is not a loss
    assert c["mark"] == pytest.approx(17.24)
    assert json.loads((new / "daily_start.json").read_text())["mark"] == pytest.approx(17.24)
    assert not (new / "strategy_start.json").exists()                # not cash-adjustable: only carried at flow 0
    b = Breakers(K(), daily_dd=0.35, run_dir=new)
    b.on_equity(17.0, int(now.timestamp() * 1000))
    assert b.hwm == pytest.approx(17.24)
    assert carry_daily(old, tmp_path / "x", now=dt.datetime(2026, 11, 19, 1, tzinfo=dt.UTC)) is None   # yesterday's


# ---- wiring: the paper_v9fix flags -------------------------------------------------------------------------------
V9 = {"speed_v4", "ref_bybit", "speed_only", "speed_v9", "paper_realism"}


def test_trader_wires_the_v9fix_run(tmp_path, monkeypatch):
    from tests.invariants.test_invariants import FakeMD
    from trader.loop import Trader, registrations
    monkeypatch.setenv("ROSTER_HUMAN_KEY", "k")
    tr = Trader(FakeMD(), tmp_path, cash=50.0, fetch=lambda cid: None, features=V9)
    assert tr.speed.versions == ((speed.NAME, speed.VERSION_V9),) and tr.speed.p["min_price"] == 0.35
    assert tr.router.realism is not None and tr.speed.venue_amounts and tr.speed.min_notional == 1.0
    assert tr.cash0 == 50.0
    _, pre = registrations(frozenset(V9), 0.5)
    assert [p["test_id"] for p in pre] == ["btc-speed-v9-fix-mp0.5"]
    tr2 = Trader(FakeMD(), tmp_path / "b", fetch=lambda cid: None, features=V9, min_price=0.5)
    assert tr2.speed.versions == ((speed.NAME, "9-fix-mp0.5"),) and tr2.speed.p["min_price"] == 0.5


def test_v9_flags_are_refused_in_bad_combinations(tmp_path, monkeypatch):
    from tests.invariants.test_invariants import FakeMD
    from trader.loop import Trader
    monkeypatch.setenv("ROSTER_HUMAN_KEY", "k")
    with pytest.raises(ValueError):
        Trader(FakeMD(), tmp_path / "a", fetch=lambda cid: None, features={"speed_v9", "speed_only"})
    with pytest.raises(ValueError):
        Trader(FakeMD(), tmp_path / "b", fetch=lambda cid: None, features=V9 | {"speed_sz"})
    with pytest.raises(ValueError):
        Trader(FakeMD(), tmp_path / "c", fetch=lambda cid: None, features={"speed_v4", "speed_only"}, min_price=0.5)
    tr = Trader(FakeMD(), tmp_path / "d", fetch=lambda cid: None, features={"speed_v4", "ref_bybit", "speed_only"})
    assert tr.router.realism is None and not tr.speed.venue_amounts   # paper_v4b's wiring is unchanged
