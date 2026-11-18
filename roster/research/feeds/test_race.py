import numpy as np

from research.feeds.race import best_lag


def test_best_lag_sign_positive_when_x_moves_first():
    x = np.random.default_rng(1).normal(size=2000)
    y = np.roll(x, 3)            # y repeats x three steps later
    assert best_lag(x, y, 10)[0] == 3
    assert best_lag(y, x, 10)[0] == -3


def test_first_to_report_keeps_the_earliest_feed_and_the_cooldown():
    import pandas as pd
    from research.feeds.bybit_replay import first_to_report
    row = lambda t, src: dict(day="d", lag=0, cfg="2s/6bp", cid="m", dir=1, t=t, source=src)
    a = pd.DataFrame([row(1_000, "binance"), row(100_000, "binance")])
    b = pd.DataFrame([row(900, "bybit"), row(30_000, "bybit")])
    out = first_to_report([a, b])
    assert out.t.tolist() == [900, 100_000] and out.source.tolist() == ["bybit", "binance"]
