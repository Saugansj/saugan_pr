"""ops/live_session.py: a new live session starts on a fresh journal, never while a bet is unsettled (12 Nov)."""
import dataclasses
import datetime as dt
import json
import sqlite3

import pytest

from ops import live_session as S
from trader.contracts import Fill, Intent


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """No test here may reach Polymarket: the resolved-market lookup sees the network as down unless a test injects it."""
    import common

    def down(*a, **k):
        raise OSError("offline in tests")
    monkeypatch.setattr(common, "get_json", down)


def session(d, settled=False):
    d.mkdir(parents=True)
    i = Intent("btc-speed", "C1", "T1", "BUY", 0.6, 5.0, "taker", 2_000, 0.5, "BTC down")
    f = Fill(order_id="o1", strategy="btc-speed", cid="C1", token_id="T1", side="BUY", price=0.53, size=5.0,
             ts_ms=1_500, maker=False, fee=0.08)
    lines = [{"op": "new", "id": "o1", "ts": 1_000, "intent": dataclasses.asdict(i)}, {"op": "ack", "id": "o1", "ts": 1_100},
             {"op": "fill", "id": "o1", "fill": dataclasses.asdict(f)}, {"op": "done", "id": "o1", "ts": 1_600}]
    (d / "journal.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    con = sqlite3.connect(d / "trader.db")
    con.execute("CREATE TABLE rows (id INTEGER PRIMARY KEY, tbl TEXT, event_ms INTEGER, recorded_ms INTEGER, body TEXT)")
    if settled:
        con.execute("INSERT INTO rows (tbl, event_ms, recorded_ms, body) VALUES ('settlements', 9, 9, ?)",
                    (json.dumps({"cid": "C1", "token_id": "T1", "winner": "T1", "payout": 1.0, "shares": 5.0}),))
    con.commit()
    con.close()


def test_open_bet_blocks_the_archive(tmp_path, monkeypatch):
    d = tmp_path / "live"
    session(d)
    assert S.unsettled(d) == {"T1": 5.0}
    with pytest.raises(SystemExit):
        S.archive(d)
    assert d.exists()


def test_settled_session_is_archived_and_empty_one_is_left(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "ARCHIVE", tmp_path / "archive")
    d = tmp_path / "live"
    session(d, settled=True)
    assert S.unsettled(d) == {}
    dest = S.archive(d, now=dt.datetime(2026, 11, 12, 21, 0))
    assert dest == tmp_path / "archive" / "20261112-210000" and (dest / "journal.jsonl").exists() and not d.exists()
    assert S.archive(tmp_path / "nothing") is None


def test_daily_dd_flag_is_bounded():
    from trader import loop
    for bad in ("0.9", "0.01"):
        with pytest.raises(SystemExit):
            loop.main(["--paper", "--minutes", "1", "--daily-dd", bad])


def test_a_market_resolved_on_polymarket_counts_as_settled(tmp_path):
    d = tmp_path / "live"
    session(d)                                       # the bot stopped before it booked the result
    resolved = lambda url: {"tokens": [{"token_id": "T1", "winner": True}, {"token_id": "T0", "winner": False}]}
    pending = lambda url: {"tokens": [{"token_id": "T1", "winner": False}, {"token_id": "T0", "winner": False}]}
    def down(url):
        raise OSError("offline")
    assert S.unsettled(d, get=resolved) == {}
    assert S.unsettled(d, get=pending) == {"T1": 5.0}
    assert S.unsettled(d, get=down) == {"T1": 5.0}  # cannot check: stays unsettled
