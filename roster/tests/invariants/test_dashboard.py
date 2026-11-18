"""ops/dashboard.py: the day x run live-estimate table and per-run summary."""
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).parents[2]
spec = importlib.util.spec_from_file_location("dashboard", ROOT / "ops" / "dashboard.py")
D = importlib.util.module_from_spec(spec)
spec.loader.exec_module(D)


def test_returns_table():
    row = lambda run, day, m, live, paper: {"run": run, "day_ist": day, "market": m, "live_est_pnl": str(live), "paper_pnl": str(paper)}
    days, runs, cell, per = D.returns([row("paper_v4b", "2026-10-20", "a", 1.0, 2.0), row("paper_v4b", "2026-10-20", "b", -0.5, 1.0),
                                       row("paper_v4b", "2026-10-21", "c", 2.0, 2.0), row("paper_v3", "2026-10-08", "d", -1.0, 0.0)])
    assert days == ["2026-10-08", "2026-10-20", "2026-10-21"]
    assert runs[0] == "paper_v4b" and runs[-1] == "paper_v3" and set(D.ACTIVE) <= set(runs)   # active runs first (even without trades), the retired one last
    assert cell[("2026-10-20", "paper_v4b")] == pytest.approx(0.5) and ("2026-10-08", "paper_v4b") not in cell
    assert per["paper_v4b"]["n"] == 3 and per["paper_v4b"]["total"] == pytest.approx(2.5) and per["paper_v4b"]["paper"] == 5.0
    assert per["paper_v3"]["start"] == 50.0 and per["paper_v3"]["se"] is None   # one market: no clustered SE


def test_active_run_without_trades_still_listed():
    days, runs, cell, per = D.returns([])
    assert set(D.ACTIVE) <= set(runs) and days == []
    assert per["paper_v7b"]["n"] == 0 and per["paper_v7b"]["mean"] is None and per["paper_v7b"]["se"] is None


def test_live_money_won_lost_open(tmp_path):
    import json
    import sqlite3
    con = sqlite3.connect(tmp_path / "trader.db")
    con.execute("CREATE TABLE rows (id INTEGER PRIMARY KEY, tbl TEXT, event_ms INTEGER, recorded_ms INTEGER, body TEXT)")
    put = lambda t, ms, b: con.execute("INSERT INTO rows (tbl, event_ms, recorded_ms, body) VALUES (?, ?, ?, ?)", (t, ms, ms, json.dumps(b)))
    put("runs", 1, {"cash0": 19.65})
    for cid, tok, px in (("a", "ta", 0.40), ("b", "tb", 0.60), ("c", "tc", 0.30)):
        put("fills", 2, {"cid": cid, "token_id": tok, "side": "BUY", "price": px, "size": 5.0, "fee": 0.1})
    put("settlements", 3, {"cid": "a", "winner": "ta"})
    put("settlements", 3, {"cid": "b", "winner": "other"})
    con.commit(); con.close()
    m = D.live_money(tmp_path)
    assert m["cash0"] == 19.65
    won, lost, still = m["fills"]
    assert won["won"] is True and won["pnl"] == pytest.approx(5 - 2.1)
    assert lost["won"] is False and lost["pnl"] == pytest.approx(-3.1)
    assert still["won"] is None and still["pnl"] is None
    assert D.live_money(tmp_path / "missing") == {"cash0": None, "fills": []}


def test_live_money_uses_the_venue_sizing(tmp_path):
    """12 Nov: a 5-share BUY at limit 0.60 that matched at 0.53 spent 3.00 and held 5.66 shares on chain."""
    import json
    import sqlite3
    con = sqlite3.connect(tmp_path / "trader.db")
    con.execute("CREATE TABLE rows (id INTEGER PRIMARY KEY, tbl TEXT, event_ms INTEGER, recorded_ms INTEGER, body TEXT)")
    put = lambda t, b: con.execute("INSERT INTO rows (tbl, event_ms, recorded_ms, body) VALUES (?, 1, 1, ?)", (t, json.dumps(b)))
    put("runs", {"cash0": 19.65})
    put("orders", {"order_id": "o1", "side": "BUY", "price": 0.60})
    put("fills", {"order_id": "o1", "strategy": "btc-speed", "cid": "a", "token_id": "ta", "side": "BUY", "price": 0.53,
                  "size": 5.0, "fee": 0.0872})
    put("settlements", {"cid": "a", "winner": "ta"})
    con.commit(); con.close()
    [f] = D.live_money(tmp_path)["fills"]
    assert f["size"] == pytest.approx(5 * 0.60 / 0.53) and f["cost"] == pytest.approx(3.0872)
    assert f["pnl"] == pytest.approx(5 * 0.60 / 0.53 - 3.0872)


def test_live_state_with_no_session(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "T", tmp_path)
    s = D.live_state(1_794_680_000_000)
    assert s["state"] == "stopped" and s["open"] == [] and s["done"] == [] and s["feed"] == [] and s["series"] == []
    assert s["daily_stop"] == 0.20 and s["limit"] is None
