"""weather/paper.py: bucket titles, METAR temperatures, the market's rounding, dead/far classification, book walk."""
from datetime import datetime, timezone

from weather import paper as W


def test_bucket_titles():
    assert W.parse_bucket("74-75°F") == (74, 75, "F")
    assert W.parse_bucket("8°C or below") == (None, 8, "C")
    assert W.parse_bucket("18°C or higher") == (18, None, "C")
    assert W.parse_bucket("-2°C") == (-2, -2, "C")
    assert W.parse_bucket("−3°C or below") == (None, -3, "C")


def test_metar_temperature_and_rule_rounding():
    assert W.metar_temp("METAR KLGA 020951Z 00000KT 10SM FEW250 11/04 A3041 RMK AO2 SLP298 T01060044") == 10.6
    assert W.metar_temp("METAR ZBAA 021000Z 20004MPS CAVOK 15/M00 Q1019 NOSIG") == 15
    assert W.metar_temp("METAR EGLC 021020Z AUTO M01/M03 Q1036") == -1
    assert W.metar_temp("SPECI KLGA 021012Z 00000KT 11/04 RMK T01110044") is None
    assert W.metar_temp("KLGA 020951Z 00000KT 10SM RMK T10171022") == -1.7
    # the rule text's own examples
    assert [W.to_unit(c, "C") for c in (13.9, 17.4, 16.5, -1.7, -8.5)] == [14, 17, 17, -2, -8]
    assert [W.to_unit(c, "F") for c in (18.3, 17.8, 19, -22.5)] == [65, 64, 66, -8]


def test_observed_uses_the_local_day_only():
    now = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
    t0 = datetime(2026, 11, 2, 4, 0, tzinfo=timezone.utc).timestamp()   # local midnight 04:00 UTC
    lines = ["METAR KLGA 020351Z 11/04 RMK T01500044",                    # previous local day: ignored
             "METAR KLGA 020451Z 11/04 RMK T01060044", "METAR KLGA 021151Z 13/04 RMK T01280044",
             "SPECI KLGA 021131Z 15/04 RMK T01560044"]                     # SPECI never counts
    assert W.observed(lines, t0, now, "highest", "F") == 55               # 12.8 C = 55.04 F
    assert W.observed(lines, t0, now, "lowest", "C") == 11


def test_classify_dead_needs_a_unit_of_margin_and_far_waits_for_the_hour():
    assert W.classify("highest", 74, 75, "F", 77, 9) == "dead"            # top 75 <= 77 - 2
    assert W.classify("highest", 76, 77, "F", 77, 9) is None              # contains the max
    assert W.classify("highest", 74, 75, "F", 76, 9) is None              # only 1 F past: a correction could undo it
    assert W.classify("highest", 82, 83, "F", 77, 15) == "far"
    assert W.classify("highest", 82, 83, "F", 77, 11) is None             # too early in the day
    assert W.classify("highest", 80, None, "C", 77, 15) == "far"
    assert W.classify("lowest", 9, 9, "C", 7, 3) == "dead"                # bottom 9 >= 7 + 2
    assert W.classify("lowest", None, 4, "C", 7, 12) == "far"
    assert W.classify("lowest", 9, None, "C", 7, 3) == "dead"
    assert W.classify("highest", 74, 75, "F", None, 15) is None


def test_walk_fills_up_to_the_limit_only():
    assert W.walk([(0.96, 2), (0.95, 2), (0.99, 10)], 0.96, 5) == (4, 0.95 * 2 + 0.96 * 2)
    got, cost = W.walk([(0.95, 10)], 0.96, 5)
    assert got == 5 and abs(cost - 4.75) < 1e-9
