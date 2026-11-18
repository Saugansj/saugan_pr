"""ops/data_usage.py: daily totals from the keeper's network samples, and the hub meter line."""
import datetime as dt
import importlib.util
import pathlib

spec = importlib.util.spec_from_file_location("data_usage", pathlib.Path(__file__).parents[2] / "ops" / "data_usage.py")
U = importlib.util.module_from_spec(spec)
spec.loader.exec_module(U)


def test_day_usage_sums_deltas_in_the_day_and_survives_a_counter_reset():
    d0 = int(dt.datetime(2026, 10, 20, tzinfo=U.IST).timestamp())
    s = [{"t": d0 - 60, "recv": 1000, "sent": 100},       # yesterday's last sample: the baseline only
         {"t": d0 + 60, "recv": 3000, "sent": 300},       # +2000 / +200 at 00:01
         {"t": d0 + 3660, "recv": 500, "sent": 50},       # counter reset at 01:01 (reboot or Wi-Fi reset): counts 0, never the reading
         {"t": d0 + 86_460, "recv": 9000, "sent": 900}]   # tomorrow: not counted
    u = U.day_usage(s, d0, d0 + 86_400)
    assert (u["recv"], u["sent"], u["samples"]) == (2000, 200, 2)
    assert u["hours"] == {0: 2200, 1: 0}
    assert u["from"] == d0 - 60                            # counted from yesterday's last sample: the whole day


def test_hub_today_reads_the_newest_meter_line(tmp_path):
    log = tmp_path / "feedhub_console.log"
    log.write_text("hub data: 1.0 MB/min, 9 requests, today 12 MB, calm\nother\nhub data: 1.1 MB/min, 9 requests, today 470 MB, calm\n")
    assert U.hub_today(log)[0] == 470.0
    assert U.hub_today(tmp_path / "missing.log") == (None, "")
