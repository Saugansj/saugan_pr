"""btc-speed v7 (23 Oct): the fair-value function, K tracking per window and the skip/limit decision; older versions
untouched."""
import math
from statistics import NormalDist

import pytest

from trader.engines import speed
from trader.engines.speed import SpeedEngine, StartPrice, fair_up, fv_limit
from tests.wiring.test_ww_d import boot, env  # noqa: F401 - env is a fixture
from trader.tests.test_speed import T0, books_for, mkt

P = {"fv_margin": 0.02, "max_price": 0.85, "max_slip": 0.10}


def test_fair_up_is_the_normal_cdf_of_the_scaled_log_move():
    assert fair_up(100.0, 100.0, 5.0, 300, 1.0) == 0.5
    s, k, rv, tau, c = 100.05, 100.0, 6.0, 200, 1.3
    want = NormalDist().cdf(math.log(s / k) / (c * rv / math.sqrt(60) * 1e-4 * math.sqrt(tau)))
    assert fair_up(s, k, rv, tau, c) == pytest.approx(want)
    assert fair_up(100.1, 100, 5, 300, 1) > fair_up(100.05, 100, 5, 300, 1) > 0.5 > fair_up(99.95, 100, 5, 300, 1)
    assert fair_up(100.05, 100, 5, 300, 2.0) < fair_up(100.05, 100, 5, 300, 1.0)   # larger c: less sure
    assert fair_up(100.0, 100.0, 5, 0, 1) == 1.0 and fair_up(99.9, 100.0, 5, 0, 1) == 0.0   # at the end: ties Up


def test_fv_limit_skips_above_fair_value_and_caps_the_limit():
    # fv 0.80, ask 0.70: top = 0.80 - 0.07 x 0.21 - 0.02 = 0.7653 -> floor 0.76 (under ask + 0.10 and 0.85)
    assert fv_limit(0.80, 0.70, P, 0.01) == 0.76
    assert fv_limit(0.99, 0.70, P, 0.01) == 0.80          # ask + 10c binds
    assert fv_limit(0.99, 0.84, P, 0.01) == 0.85          # max price binds
    assert fv_limit(0.70, 0.70, P, 0.01) is None          # fee + margin put the ask above the top
    assert fv_limit(0.72, 0.70, {**P, "fv_margin": -0.02}, 0.01) == 0.72   # a negative margin buys a little over FV


def test_start_price_is_the_60s_twap_before_each_5_minute_boundary():
    b = T0                                                 # a 5-minute boundary
    sp = StartPrice()
    for s in range(-70, 0):                                # one tick a second: 100, then 102 from -30 s, 104 from -3 s
        sp.add(b + s * 1000, 100.0 if s < -30 else 102.0 if s < -3 else 104.0)
    assert b not in sp.k                                   # not recorded before a tick at or after the boundary
    sp.add(b + 400, 999.0)                                 # the crossing tick itself is not in the average
    assert sp.k[b] == pytest.approx((100 * 30 + 102 * 27 + 104 * 3) / 60)
    sp.add(b + 500, 1.0)
    assert sp.k[b] == pytest.approx((100 * 30 + 102 * 27 + 104 * 3) / 60)   # set once
    sp.add(b - 1000, 5.0)                                  # an older tick is ignored
    assert list(sp.h)[-1] == (b + 500, 1.0)


def test_start_price_after_a_feed_gap_is_unknown_not_stale():
    b, sp = T0, StartPrice()
    sp.add(b - 70_000, 100.0)
    sp.add(b - 50_000, 100.0)
    sp.add(b + 1000, 101.0)                                # 51 s silent across the boundary: history restarts
    assert b not in sp.k
    sp3 = StartPrice()                                     # quiet spells under K_GAP_S (12 s here) are forward-filled
    for s, px in ((-70, 100.0), (-58, 100.0), (-46, 102.0), (-34, 102.0), (-22, 102.0), (-10, 104.0)):
        sp3.add(b + s * 1000, px)
    sp3.add(b + 2000, 999.0)
    assert sp3.k[b] == pytest.approx((100 * 14 + 102 * 36 + 104 * 10) / 60)
    sp2 = StartPrice()
    sp2.add(b - 20_000, 100.0)                             # started 20 s before the boundary: not 60 s of history
    sp2.add(b + 10, 100.0)
    assert b not in sp2.k


def _v7(**kw):
    return SpeedEngine(version=speed.VERSION_V7_BYBIT, params={"fv_c": 1.0, "fv_margin": 0.0, "fv_rv30_fallback": 5.0, **kw})


def _feed(e, markets, books, ticks):
    out = []
    for ts, px in ticks:
        out += e.on_tick(ts + 40, markets, books, {"BTC": {"price": px, "ts_ms": ts, "recv_ms": ts + 40}}, {})
    return out


def _ticks(jump_bp: float):
    """1 tick/s from 90 s before T0 to 20 s after at 100k, then a jump: K = 100k, S = 100k x e^(jump)."""
    flat = [(T0 + i * 1000, 100_000.0) for i in range(-90, 21)]
    return flat + [(T0 + 21_000, 100_000.0 * math.exp(jump_bp / 1e4))]


def test_v7_buys_under_fair_value_at_the_fv_limit_and_logs_it():
    markets = {"b5": mkt("b5")}                            # 5m window from T0; the move comes 21 s in
    now = T0 + 21_040
    e = _v7()
    [i] = _feed(e, markets, books_for(markets, now, ask=0.60), _ticks(7))
    tau = (T0 + 5 * 60_000 - now) / 1000
    fv = fair_up(100_000 * math.exp(7e-4), 100_000.0, 5.0, tau, 1.0)
    assert i.token_id == "b5-up" and i.price == fv_limit(fv, 0.60, {**e.p}, 0.01) and i.price <= 0.70
    t = e.trades[-1]
    assert t["fv"] == round(fv, 4) and t["k"] == pytest.approx(100_000.0) and t["limit"] == i.price
    assert t["sigma"] == pytest.approx(5.0 / math.sqrt(60) * 1e-4) and t["rv30"] is None   # fallback: no 30 min yet
    assert t["edge"] == round(fv - 0.07 * 0.6 * 0.4 - 0.6, 4)
    assert e.events[-1]["fv"]["b5"]["fv"] == round(fv, 4) and e.events[-1]["markets"]["b5"] == "trade"


def test_v7_skips_an_ask_above_fair_value_and_a_window_without_k():
    markets = {"b5": mkt("b5")}
    now = T0 + 21_040
    e = _v7(fv_margin=0.05)
    assert _feed(e, markets, books_for(markets, now, ask=0.84), _ticks(7)) == []
    assert e.events[-1]["markets"]["b5"] == "ask above fair value" and e.trades == []
    late = _v7()                                           # started inside the window: no K for it
    assert _feed(late, markets, books_for(markets, now, ask=0.60), _ticks(7)[100:]) == []
    assert late.events[-1]["markets"]["b5"] == "no start price"


def test_v7_params_are_v4_bybit_plus_the_fair_value_keys_only():
    for v7, v4 in ((speed.PARAMS_V7_BYBIT, speed.PARAMS_V4_BYBIT), (speed.PARAMS_V7_ETH_BYBIT, speed.PARAMS_V4_ETH_BYBIT)):
        extra = {k: v for k, v in v7.items() if k not in v4}
        assert {k: v7[k] for k in v4} == v4 and set(extra) == {"fv_c", "fv_margin", "fv_rv30_fallback"}
    assert speed.BY_VERSION[speed.VERSION_V7_BYBIT] is speed.PARAMS_V7_BYBIT
    assert speed.PREREG_V7_BYBIT["params"]["version"] == "7-bybit" and speed.PREREG_V7_ETH_BYBIT["test_id"].endswith("v7-eth-bybit")


def test_older_versions_track_no_start_price_and_keep_their_volatility_state():
    for v in speed.BY_VERSION:
        if str(v).startswith("7"):
            continue
        e = SpeedEngine(version=v)
        assert e.k0 == {} and bool(e.vol) == ("max_rv30" in speed.BY_VERSION[v])


@pytest.mark.parametrize("eth", [False, True])
def test_v7_flag_boots_its_own_bybit_side_run(env, eth):  # noqa: F811
    flags = {"speed_v7", "ref_bybit", "speed_only"} | ({"speed_eth"} if eth else set())
    _, tr = boot(env, flags)
    v = speed.VERSION_V7_ETH_BYBIT if eth else speed.VERSION_V7_BYBIT
    assert tr.speed.versions == (("btc-speed", v),) and tr.speed.k0 and tr.speed.vol
    assert tr.ledger.preregistration(f"btc-speed-v{v}") is not None


def test_v7_flag_refuses_to_run_without_bybit_or_beside_another_version(env):  # noqa: F811
    for flags in ({"speed_v7", "speed_only"}, {"speed_v7", "speed_v6", "ref_bybit", "speed_only"}):
        with pytest.raises(ValueError):
            boot(env, flags)


def test_v7c_is_ethb_with_a_070_cap_only():
    assert speed.PARAMS_V7C_ETH_BYBIT == {**speed.PARAMS_V4_ETH_BYBIT, "max_price": 0.70}
    assert speed.BY_VERSION[speed.VERSION_V7C_ETH_BYBIT] is speed.PARAMS_V7C_ETH_BYBIT
    assert speed.PREREG_V7C_ETH_BYBIT["params"]["max_price"] == 0.70


def test_v7c_skips_asks_above_070_and_caps_the_limit():
    e = SpeedEngine(version=speed.VERSION_V7C_ETH_BYBIT)
    assert e.p["assets"] == ("ETH",) and e.p["max_price"] == 0.70
    for ask, want in ((0.72, None), (0.65, 0.70), (0.55, 0.65)):
        e = SpeedEngine(version=speed.VERSION_V7C_ETH_BYBIT)
        markets = {"e5": mkt("e5", asset="ETH")}
        now = T0 + 21_040
        books = books_for(markets, now, ask=ask)
        out = []
        for ts, px in [(T0 + i * 1000, 3000.0) for i in range(0, 21)] + [(T0 + 21_000, 3000.0 * math.exp(7e-4))]:
            out += e.on_tick(ts + 40, markets, books, {"ETH": {"price": px, "ts_ms": ts, "recv_ms": ts + 40}}, {})
        assert [i.price for i in out] == ([] if want is None else [want])


def test_cap70_flag_boots_the_eth_side_run_and_refuses_otherwise(env):  # noqa: F811
    _, tr = boot(env, {"speed_v4", "speed_eth", "ref_bybit", "speed_only", "speed_cap70"})
    assert tr.speed.versions == (("btc-speed", speed.VERSION_V7C_ETH_BYBIT),)
    assert tr.ledger.preregistration("btc-speed-v7c-eth-bybit") is not None
    for flags in ({"speed_v4", "ref_bybit", "speed_only", "speed_cap70"},
                  {"speed_v4", "speed_eth", "ref_bybit", "speed_only", "speed_cap70", "compound"}):
        with pytest.raises(ValueError):
            boot(env, flags)
