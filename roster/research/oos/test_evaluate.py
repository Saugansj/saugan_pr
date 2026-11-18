from research.oos.evaluate import verdict


def test_verdict_follows_the_preregistered_rule():
    assert verdict(0.5, 0.2, 250) == "PASS"
    assert verdict(0.5, 0.3, 250) == "INCONCLUSIVE"   # under 2 SE
    assert verdict(0.9, 0.1, 150) == "INCONCLUSIVE"   # under 200 trades
    assert verdict(-0.01, 0.1, 400) == "FAIL"
    assert verdict(float("nan"), float("nan"), 0).startswith("INCONCLUSIVE")


def test_an_empty_archive_hour_makes_the_day_incomplete(tmp_path, monkeypatch):
    import datetime as dt
    import pandas as pd
    from research.oos import evaluate as E
    monkeypatch.setattr(E, "DATA", tmp_path)
    tob = tmp_path / "history" / "pm_fast" / "tob"
    tob.mkdir(parents=True)
    rows = pd.DataFrame({"ts_ms": [1], "asset_id": ["a"], "best_bid": [0.4], "best_ask": [0.5]})
    for h in range(24):
        (rows if h != 5 else rows.iloc[:0]).to_parquet(tob / f"2026-06-21T{h:02d}.parquet")
    assert not E.has_books(dt.date(2026, 6, 21))
    rows.to_parquet(tob / "2026-06-21T05.parquet")
    assert E.has_books(dt.date(2026, 6, 21))
