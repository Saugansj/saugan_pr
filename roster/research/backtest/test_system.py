"""System backtest checks: question format parses as live; a synthetic day runs the real trader end to end."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

from research.backtest import system as S
from trader.engines.speed import duration_min

DAY = dt.date(2026, 8, 3)
D0 = int(dt.datetime(2026, 8, 3, tzinfo=dt.timezone.utc).timestamp() * 1000)
START = D0 + 12 * 3_600_000          # a 5m window 12:00-12:05 UTC
T = START + 60_000                   # the BTC jump, 1 min into the window


@pytest.mark.parametrize("hour,dur", [(0, 5), (3, 15), (16, 5), (4, 15)])   # ET midnight, noon, 23:55 crossings
def test_question_parses_to_the_window_length(hour, dur):
    s = D0 + hour * 3_600_000 - dur * 60_000
    row = pd.Series({"cid": "c", "token_up": "u", "token_down": "d", "dur_min": dur, "start_ms": s, "end_ms": s + dur * 60_000})
    assert duration_min(S.market(row).question) == dur


def synthetic(tmp_path, monkeypatch, winner="up"):
    h = tmp_path / "history"
    agg = h / "binance" / "BTCUSDT" / "aggTrades"
    agg.mkdir(parents=True)
    ts = np.arange(D0, D0 + 86_400_000, 1000)
    px = np.where(ts >= T, 100_000 * np.exp(12 / 1e4), 100_000.0)
    pd.DataFrame({"ts_ms": ts, "price": px, "qty": 1.0, "buyer_maker": False}).to_parquet(agg / f"BTCUSDT-aggTrades-{DAY}.parquet")
    (h / "pm_fast" / "catalog").mkdir(parents=True)
    pd.DataFrame([{"cid": "c5", "slug": "s", "dur_min": 5, "start_ms": START, "end_ms": START + 300_000,
                   "token_up": "U", "token_down": "D", "winner": winner}]).to_parquet(h / "pm_fast" / "catalog" / f"{DAY}.parquet")
    for sub in ("tob", "trades"):
        (h / "pm_fast" / sub).mkdir(parents=True)
    for hr in range(24):
        h0 = D0 + hr * 3_600_000
        rows = [(t, tok, *((0.60, 0.62) if tok == "U" and t >= T + 5_000 else (0.48, 0.50)))   # Up reprices at +5 s
                for t in range(h0, h0 + 3_600_000, 2_000) for tok in ("U", "D")]
        pd.DataFrame(sorted(rows), columns=["ts_ms", "asset_id", "best_bid", "best_ask"]).to_parquet(
            h / "pm_fast" / "tob" / f"{DAY}T{hr:02d}.parquet")
        pd.DataFrame({"ts_ms": [h0 + 1], "asset_id": ["U"], "price": [0.5], "size": [1.0], "side": ["BUY"]}).to_parquet(
            h / "pm_fast" / "trades" / f"{DAY}T{hr:02d}.parquet")
    monkeypatch.setattr(S, "H", h)
    monkeypatch.setattr(S, "DATA", tmp_path / "data")
    monkeypatch.setattr(S, "REPORTS", tmp_path / "reports")


def test_v3_buys_on_the_jump_and_sells_about_8s_later(tmp_path, monkeypatch):
    synthetic(tmp_path, monkeypatch)
    d = S.run(DAY, DAY, "t3", {"speed_only", "speed_v3"}, lag_ms=60, rtt=250.0, depth=100.0, cash=50.0)
    from nightly import scorer
    f = scorer.tables(d)["fills"]
    buy, sell = [x for x in f if x["side"] == "BUY"], [x for x in f if x["side"] == "SELL"]
    assert len(buy) == 1 and buy[0]["token_id"] == "U" and buy[0]["price"] == 0.50
    assert len(sell) == 1 and sell[0]["price"] == 0.60 and 8_000 <= sell[0]["ts_ms"] - buy[0]["ts_ms"] < 10_000
    assert (tmp_path / "reports" / "research" / "backtest_t3.md").exists()


def test_v2_holds_and_settles_from_the_catalog(tmp_path, monkeypatch):
    synthetic(tmp_path, monkeypatch, winner="down")
    d = S.run(DAY, DAY, "t2", {"speed_only"}, lag_ms=60, rtt=250.0, depth=100.0, cash=50.0)
    from nightly import scorer
    t = scorer.tables(d)
    assert [x["side"] for x in t["fills"]] == ["BUY"]
    assert [(s["token_id"], s["payout"]) for s in t["settlements"]] == [("U", 0.0)]
