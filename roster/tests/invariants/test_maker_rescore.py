"""ops/maker_rescore.py: which real prints fill a resting maker bid."""
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).parents[2]
spec = importlib.util.spec_from_file_location("maker_rescore", ROOT / "ops" / "maker_rescore.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


def test_fill_counts_sells_through_our_bid_and_complement_buys_behind_the_queue():
    prints = [["A", "SELL", 0.60, 10, 30.0],   # our token sold at our bid: fills
              ["A", "SELL", 0.62, 10, 99.0],   # sold above our bid: someone else's better bid
              ["B", "BUY", 0.40, 11, 20.0],    # complement bought at 1 - bid: mints against our bid
              ["B", "BUY", 0.38, 11, 99.0],    # complement under 1 - bid: does not reach us
              ["A", "SELL", 0.55, 30, 99.0]]   # outside the rest window
    assert M.fill(0.60, 5.0, 40.0, "A", "B", prints, 9, 12) == (5.0, 5.0)     # 50 through, 40 ahead: 10 left, we want 5
    assert M.fill(0.60, 25.0, 40.0, "A", "B", prints, 9, 12) == (10.0, 25.0)
    assert M.fill(0.60, 5.0, 60.0, "A", "B", prints, 9, 12) == (0.0, 5.0)     # the queue ate it all
