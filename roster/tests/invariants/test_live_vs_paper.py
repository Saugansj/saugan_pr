"""ops/live_vs_paper.py: venue sizing, miss detection, paused orders left out (12 Nov)."""
import dataclasses
import json
import sqlite3

import pytest

from ops import live_vs_paper as V
from trader.contracts import Fill, Intent


def db(path, rows):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE rows (id INTEGER PRIMARY KEY, tbl TEXT, event_ms INTEGER, recorded_ms INTEGER, body TEXT)")
    for t, ms, b in rows:
        con.execute("INSERT INTO rows (tbl, event_ms, recorded_ms, body) VALUES (?, ?, ?, ?)", (t, ms, ms, json.dumps(b)))
    con.commit()
    con.close()


def test_live_orders_venue_sizing_and_misses(tmp_path):
    d = tmp_path / "live"
    d.mkdir()
    i = lambda cid, lim: dataclasses.asdict(Intent("btc-speed", cid, cid + "-up", "BUY", lim, 5.0, "taker", 3_000, 0.5, "BTC up"))
    f = Fill(order_id="o1", strategy="btc-speed", cid="A", token_id="A-up", side="BUY", price=0.53, size=5.0, ts_ms=1_200,
             maker=False, fee=0.09)
    lines = [{"op": "new", "id": "o1", "ts": 1_000, "intent": i("A", 0.60)}, {"op": "ack", "id": "o1", "ts": 1_000},
             {"op": "fill", "id": "o1", "fill": dataclasses.asdict(f)},
             {"op": "new", "id": "o2", "ts": 1_000, "intent": i("B", 0.34)}, {"op": "cancel", "id": "o2", "ts": 1_100}]
    (d / "journal.jsonl").write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    db(d / "trader.db", [("settlements", 5_000, {"cid": "A", "winner": "A-up"})])
    a, b = sorted(V.live_orders(d), key=lambda r: r["cid"])
    assert a["spend"] == pytest.approx(3.09) and a["shares"] == pytest.approx(3.0 / 0.53)
    assert a["won"] is True and a["pnl"] == pytest.approx(3.0 / 0.53 - 3.09)
    assert b["filled"] is False and b["pnl"] is None


def test_paused_spans():
    rows = [("trips", 10, {"scope": "global", "state": "REDUCING"}), ("trips", 20, {"scope": "global", "state": "ACTIVE"}),
            ("trips", 30, {"scope": "btc-speed", "state": "REDUCING"}), ("trips", 40, {"scope": "global", "state": "REDUCING"})]
    assert V.paused_spans(rows) == [(10, 20), (40, 10**15)]


def test_timing_medians(tmp_path):
    rows = [{"kind": "post", "decision_ms": 1_000, "post_start_ms": 1_040, "post_end_ms": 1_400,
             "orders": [{"id": "a"}, {"id": "b"}], "response": [{"status": "matched"}, {"errorMsg": "no orders found"}]},
            {"kind": "trade_event", "msg": {"taker_order_id": "a", "match_time": "1700"}},           # seconds: 1 700 000 ms
            {"kind": "trade_event", "msg": {"taker_order_id": "a", "match_time": "1250"}}]
    rows[1]["msg"]["match_time"] = str(1_900)                                                     # ms value below 1e11 reads as s
    (tmp_path / "order_timing.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    t = V.timing(tmp_path)
    assert t["n"] == 1 and t["pc_ms"] == 40 and t["post_ms"] == 360
    assert t["status"] == {"matched": 1, "no orders found": 1} and t["n_match"] == 1
    assert V.timing(tmp_path / "none") is None


SUB_DOLLAR = ("venue HTTP 400: {'error': 'invalid amount for a marketable BUY order ($0.7), min size: 1'}")
RACE_LOST = "no orders found to match with FAK order. FAK orders are partially filled or killed if no match is found."


def journal(d, lines):
    d.mkdir(parents=True, exist_ok=True)
    (d / "journal.jsonl").write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")


def test_refusal_is_not_a_lost_race(tmp_path):
    """16 Nov: an order Polymarket refused never reached the book; only "no orders found" is a lost race."""
    d = tmp_path / "live"
    i = lambda cid, lim: dataclasses.asdict(Intent("btc-speed", cid, cid + "-up", "BUY", lim, 5.0, "taker", 3_000, 0.5, "sig"))
    journal(d, [{"op": "new", "id": "o1", "ts": 1_000, "intent": i("A", 0.19)},     # 5 x 0.19 = $0.95: under the minimum
                {"op": "cancel", "id": "o1", "ts": 1_100, "reason": SUB_DOLLAR},
                {"op": "new", "id": "o2", "ts": 1_000, "intent": i("B", 0.60)},
                {"op": "cancel", "id": "o2", "ts": 1_100, "reason": RACE_LOST},
                {"op": "new", "id": "o3", "ts": 1_000, "intent": i("C", 0.70)},   # 5 x 0.70 = $3.50: its batch died
                {"op": "cancel", "id": "o3", "ts": 1_100, "reason": SUB_DOLLAR}])
    a, b, c = sorted(V.live_orders(d), key=lambda r: r["cid"])
    assert a["refused"] is True and a["filled"] is False and a["pnl"] is None
    assert b["refused"] is False and b["filled"] is False
    assert c["refused"] is True
    assert V.refusal_label(a["why"]) == "refused: under $1"
    assert V.refusal_label("venue HTTP 400: " + "x" * 40) == "refused: venue HTTP 400: " + "x" * 24


def test_compare_counts_refusals_apart_from_lost_races(tmp_path, monkeypatch):
    t = tmp_path / "trader"
    d = t / "live"
    i = lambda cid, lim: dataclasses.asdict(Intent("btc-speed", cid, cid + "-up", "BUY", lim, 5.0, "taker", 3_000, 0.5, "sig"))
    journal(d, [{"op": "new", "id": "o1", "ts": 1_000, "intent": i("A", 0.19)},
                {"op": "cancel", "id": "o1", "ts": 1_100, "reason": SUB_DOLLAR},
                {"op": "new", "id": "o2", "ts": 1_000, "intent": i("B", 0.60)},
                {"op": "cancel", "id": "o2", "ts": 1_100, "reason": RACE_LOST},
                {"op": "new", "id": "o3", "ts": 1_000, "intent": i("C", 0.70)},
                {"op": "cancel", "id": "o3", "ts": 1_100, "reason": SUB_DOLLAR}])
    paper = {"A": [{"ts": 1_000, "token": "A-up", "price": 0.13, "cost": 0.75, "won": True, "pnl": 4.25}],
             "B": [{"ts": 1_000, "token": "B-up", "price": 0.50, "cost": 2.59, "won": True, "pnl": 2.41}]}
    monkeypatch.setattr(V, "T", t)
    monkeypatch.setattr(V, "paper_fills", lambda run="paper_v4b": paper)
    monkeypatch.setattr(V, "estimates", lambda: {})
    rows, s = V.compare()
    assert s["orders"] == 3 and s["filled"] == 0 and s["paper_had"] == 2
    assert s["refused"] == 2 and s["refused_paper_filled"] == 1
    assert s["missed_paper_filled"] == 1            # the race loss only, not every unfilled order
    assert s["paper_pnl"] == pytest.approx(4.25 + 2.41)
    rep = V.report()
    assert "Lost the race where paper filled" in rep and "Refused by Polymarket (not a race)" in rep
    assert "refused: under $1" in rep and "refused: other leg under $1" in rep
