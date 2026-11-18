"""Replay checks: no look-ahead in features, entry/exit/hold maths, same-market rule, the live detector."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

from research.replay import replay as R
from trader import fees

DAY = dt.date(2026, 8, 1)
D0 = int(dt.datetime(2026, 8, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
T = D0 + 3_600_000 + 30_000           # the signal: 01:00:30, inside the 01:00-01:05 window


def ticks(jump_at=T, bp=12.0):
    ts = np.arange(D0, D0 + 7_200_000, 1000)
    px = np.where(ts >= jump_at, 100_000 * np.exp(bp / 1e4), 100_000.0)
    return pd.DataFrame({"ts_ms": ts, "price": px})


def cat(winner="up"):
    return pd.DataFrame([{"cid": "c5", "slug": "s", "dur_min": 5, "start_ms": D0 + 3_600_000, "end_ms": D0 + 3_900_000,
                          "token_up": "U", "token_down": "D", "winner": winner}])


def tob(rows):
    return R.Tob(pd.DataFrame(rows, columns=["ts_ms", "asset_id", "best_bid", "best_ask"]))


BOOK = [(D0, "U", 0.48, 0.50), (T + 5_000, "U", 0.60, 0.62)]   # the ask at arrival is 0.50; bid 0.60 from +5 s


def test_features_use_only_ticks_before_the_signal():
    a, b = ticks(), ticks()
    b.loc[b.ts_ms >= T, "price"] *= 1.5                          # rewrite the future
    fa = R.features(a.ts_ms.to_numpy(), a.price.to_numpy(), T, 1, [])
    fb = R.features(b.ts_ms.to_numpy(), b.price.to_numpy(), T, 1, [])
    assert fa == fb


def test_hold_and_exit_maths():
    df = R.replay(ticks(), cat("up"), tob(BOOK), DAY, rtt=200)
    f = df[df.filled & (df.cap == 0.75) & (df.lag == 0)].set_index("exit")
    cost = 5 * 0.50 + fees.fee(5, 0.50, 0.07)
    assert f.loc["hold", "pnl"] == pytest.approx(5 - cost)
    assert f.loc["8", "pnl"] == pytest.approx(5 * 0.60 - fees.fee(5, 0.60, 0.07) - cost)
    assert f.loc["8", "exit_px"] == 0.60
    lost = R.replay(ticks(), cat("down"), tob(BOOK), DAY, rtt=200)
    assert lost[lost.filled & (lost.exit == "hold") & (lost.cap == 0.75) & (lost.lag == 0)].pnl.iloc[0] == pytest.approx(-cost)


def test_cap_and_slippage_limit():
    high = [(D0, "U", 0.78, 0.80)]
    df = R.replay(ticks(), cat(), tob(high), DAY, rtt=200)
    assert not df[df.cap == 0.75].filled.any() and df[df.cap == 0.90].filled.any()
    jumped = [(D0, "U", 0.48, 0.50), (T + 100, "U", 0.55, 0.56)]     # ask moved 6c before arrival: over the 2c limit
    df = R.replay(ticks(), cat(), tob(jumped), DAY, rtt=200)
    assert not df[df.lag == 0].filled.any()


def test_detector_is_the_live_one():
    t = ticks()
    ev = R.detect(t.ts_ms.to_numpy(), t.price.to_numpy())
    assert [(e[0], e[1]) for e in ev] == [(T, 1)]


def test_no_second_buy_while_the_market_is_held():
    t = ticks()
    t.loc[t.ts_ms >= T + 70_000, "price"] *= np.exp(12 / 1e4)          # a second signal 70 s later, same window
    df = R.replay(t, cat(), tob(BOOK), DAY, rtt=200)
    g = df[(df.cap == 0.90) & (df.lag == 0)]
    assert g[g.exit == "hold"].filled.tolist() == [True, False]      # held: the market is still open
    assert g[g.exit == "8"].filled.tolist() == [True, True]          # sold after 8 s: free to buy again


def test_slip_limit_rounded_as_live_and_lag_sees_the_later_ask():
    moved = [(D0, "U", 0.10, 0.12), (T + 100, "U", 0.12, 0.14)]      # +2c exactly: live accepts after rounding
    df = R.replay(ticks(), cat(), tob(moved), DAY, rtt=200)
    assert df[(df.lag == 0) & (df.cap == 0.75)].filled.all()
    late = [(D0, "U", 0.48, 0.50), (T + 500, "U", 0.58, 0.60)]       # seen 1 s late: the ask seen is already 0.60
    df = R.replay(ticks(), cat(), tob(late), DAY, rtt=200)
    g = df[(df.lag == 1000) & (df.cap == 0.75) & (df.exit == "hold")]
    assert g.filled.all() and g.ask0.iloc[0] == 0.60 and g.ask.iloc[0] == 0.60
