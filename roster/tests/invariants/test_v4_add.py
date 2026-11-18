"""btc-speed v4-add (15 Nov): v4b plus one more same-side bet in an already-held market."""
import pytest

from trader.engines import speed
from tests.wiring.test_ww_d import boot, env  # noqa: F401 - env is a fixture


def test_v4_add_is_v4b_with_add_once_only():
    assert speed.PARAMS_V4_BYBIT_ADD == {**speed.PARAMS_V4_BYBIT, "add_once": True}
    assert speed.BY_VERSION[speed.VERSION_V4_BYBIT_ADD] is speed.PARAMS_V4_BYBIT_ADD
    assert speed.PREREG_V4_BYBIT_ADD["test_id"] == "btc-speed-v4-bybit-add"


def test_add_flag_boots_the_btc_side_run_and_refuses_otherwise(env):  # noqa: F811
    _, tr = boot(env, {"speed_v4", "ref_bybit", "speed_only", "speed_add"})
    assert tr.speed.versions == (("btc-speed", speed.VERSION_V4_BYBIT_ADD),)
    assert tr.ledger.preregistration("btc-speed-v4-bybit-add") is not None
    for flags in ({"speed_v4", "speed_only", "speed_add"}, {"speed_v4", "ref_bybit", "speed_only", "speed_add", "speed_v8"}):
        with pytest.raises(ValueError):
            boot(env, flags)
