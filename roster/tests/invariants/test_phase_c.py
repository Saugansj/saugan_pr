"""ops/phase_c.py: days to the 2 SE bar, the Phase D gate and trading-ready uptime."""
import importlib.util
import pathlib

from trader.ledger import Ledger

ROOT = pathlib.Path(__file__).parents[2]
spec = importlib.util.spec_from_file_location("phase_c", ROOT / "ops" / "phase_c.py")
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)


def test_days_to_bar():
    assert P.days_to_bar(100, 0.10, 0.10, 20) == (400 - 100) / 20        # needs 4x the trades: 2 SE at n 400
    assert P.days_to_bar(300, 0.50, 0.10, 20) == 0.0                      # already past both bars
    assert P.days_to_bar(50, 0.50, 0.01, 10) == 15.0                      # the 200-trade floor still applies
    assert P.days_to_bar(100, -0.1, 0.1, 20) is None and P.days_to_bar(0, None, None, 0) is None


def test_gate_needs_all_three():
    run = lambda name, n, m, se, up: {"run": name, "n": n, "mean": m, "se": se, "uptime": up}
    g = P.gate([run("paper_ethb", 250, 0.3, 0.1, 0.95), run("paper_v4b", 90, 0.1, 0.2, 0.8)], oos_pass=True)
    assert [met for _, met, _ in g] == [True, True, True]
    g = P.gate([run("paper_ethb", 250, 0.3, 0.1, 0.70), run("paper_v4b", 90, -0.1, 0.2, 0.9)], oos_pass=True)
    assert [met for _, met, _ in g] == [True, False, False]             # BTC forward < 0; uptime under 90%


def test_ready_share_counts_minutes_with_a_loop_and_no_pause(tmp_path):
    t = [0]
    led = Ledger(tmp_path / "trader.db", clock=lambda: t[0])
    for m in range(10):                                                  # the loop ran minutes 0-9 of 20
        led.record("latency", {}, m * 60_000 + 1)
    led.record("trips", {"scope": "global", "state": "REDUCING"}, 2 * 60_000)
    led.record("trips", {"scope": "btc-speed", "state": "REDUCING"}, 3 * 60_000)   # a strategy pause is not a global one
    led.record("trips", {"scope": "global", "state": "ACTIVE"}, 4 * 60_000)
    assert P.ready_share(tmp_path / "trader.db", 0, 20 * 60_000) == 8 / 20          # minutes 2-3 paused
    assert P.ready_share(tmp_path / "nope.db", 0, 60_000) == 0.0
    assert P.ready_share(tmp_path / "trader.db", 0, 20 * 60_000, awake=set(range(10))) == 8 / 10   # PC on minutes 0-9 only
    log = tmp_path / "clock.jsonl"
    log.write_text("\n".join(['{"ts_ms": 60000}', '{"ts_ms": 61000}', '{"ts_ms": 999999999}']) + "\n")
    assert P.awake_minutes(0, 600_000, log) == {1}
