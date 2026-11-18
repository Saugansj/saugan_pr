"""btc-speed v8 (30 Oct): v4b with no buy at a seen ask above 0.50, limit unchanged."""
import math

import pytest

from trader.engines import speed
from trader.engines.speed import SpeedEngine
from tests.wiring.test_ww_d import boot, env  # noqa: F401 - env is a fixture
from trader.tests.test_speed import T0, books_for, mkt


def test_v8_is_v4b_with_the_ask_skip_only():
    assert speed.PARAMS_V8_BYBIT == {**speed.PARAMS_V4_BYBIT, "skip_ask": (0.50, 1.0)}
    assert speed.BY_VERSION[speed.VERSION_V8_BYBIT] is speed.PARAMS_V8_BYBIT
    assert speed.PREREG_V8_BYBIT["test_id"] == "btc-speed-v8-bybit"


def test_v8_skips_asks_above_050_and_keeps_the_ask_plus_10c_limit():
    for ask, want in ((0.51, None), (0.70, None), (0.50, 0.60), (0.30, 0.40)):
        e = SpeedEngine(version=speed.VERSION_V8_BYBIT)
        markets = {"b5": mkt("b5")}
        books = books_for(markets, T0 + 21_040, ask=ask)
        out = []
        for ts, px in [(T0 + i * 1000, 100_000.0) for i in range(0, 21)] + [(T0 + 21_000, 100_000.0 * math.exp(7e-4))]:
            out += e.on_tick(ts + 40, markets, books, {"BTC": {"price": px, "ts_ms": ts, "recv_ms": ts + 40}}, {})
        assert [i.price for i in out] == ([] if want is None else [want])


def test_v8_flag_boots_the_btc_side_run_and_refuses_otherwise(env):  # noqa: F811
    _, tr = boot(env, {"speed_v4", "ref_bybit", "speed_only", "speed_v8"})
    assert tr.speed.versions == (("btc-speed", speed.VERSION_V8_BYBIT),)
    assert tr.ledger.preregistration("btc-speed-v8-bybit") is not None
    for flags in ({"speed_v4", "speed_only", "speed_v8"}, {"speed_v4", "speed_eth", "ref_bybit", "speed_only", "speed_v8"}):
        with pytest.raises(ValueError):
            boot(env, flags)
