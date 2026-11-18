"""btc-speed v4-sz (17 Nov): v4b at 8 shares."""
import pytest

from trader.engines import speed
from tests.wiring.test_ww_d import boot, env  # noqa: F401 - env is a fixture


def test_v4_sz_is_v4b_at_eight_shares():
    assert speed.PARAMS_V4_BYBIT_SZ == {**speed.PARAMS_V4_BYBIT, "shares": 8.0}
    assert speed.BY_VERSION[speed.VERSION_V4_BYBIT_SZ] is speed.PARAMS_V4_BYBIT_SZ
    assert speed.PREREG_V4_BYBIT_SZ["test_id"] == "btc-speed-v4-bybit-sz"
    assert speed.SpeedEngine(version=speed.VERSION_V4_BYBIT_SZ).p["shares"] == 8.0


def test_sz_flag_boots_the_btc_side_run_and_refuses_otherwise(env):  # noqa: F811
    _, tr = boot(env, {"speed_v4", "ref_bybit", "speed_only", "speed_sz"})
    assert tr.speed.versions == (("btc-speed", speed.VERSION_V4_BYBIT_SZ),)
    assert tr.ledger.preregistration("btc-speed-v4-bybit-sz") is not None
    for flags in ({"speed_v4", "speed_only", "speed_sz"},
                  {"speed_v4", "ref_bybit", "speed_only", "speed_sz", "speed_add"},
                  {"speed_v4", "ref_bybit", "speed_only", "speed_sz", "speed_v8"}):
        with pytest.raises(ValueError):
            boot(env, flags)
