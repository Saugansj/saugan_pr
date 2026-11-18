"""WP0-B tests: checksum, parsing, date/strike logic, paging, and that a second run skips completed work (B5)."""
import datetime as dt
import hashlib
import io
import zipfile

import pandas as pd
import pytest

from history import binance, deribit, footballdata, polymarket


# ---------- Binance ----------

def _zip(lines: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x.csv", "\n".join(lines) + "\n")
    return buf.getvalue()


ROW_MS = "1717200000000,1,2,0.5,1.5,10,1717200059999,15,7,4,6,0"
ROW_US = "1790640000000000,1,2,0.5,1.5,10,1790640059999999,15,7,4,6,0"


def test_periods_monthly_then_daily():
    p = binance.periods(dt.date(2024, 11, 1), dt.date(2025, 1, 3))
    assert p == [("monthly", "2024-11"), ("monthly", "2024-12"), ("daily", "2025-01-01"), ("daily", "2025-01-02")]


def test_verify_and_parse_normalises_microseconds():
    z = _zip(["open_time,open,high,low,close,volume,close_time,qv,n,tb,tq,ignore", ROW_MS, ROW_US])
    good = hashlib.sha256(z).hexdigest() + "  x.zip\n"
    assert binance.verify(z, good) and not binance.verify(z + b"x", good)
    df = binance.parse(z)
    assert len(df) == 2 and "ignore" not in df
    assert df.open_time.tolist() == [1717200000000, 1790640000000]  # header dropped, us -> ms
    assert df.close_time.iloc[1] == 1790640059999 and df.close.dtype == "float64"


def test_binance_second_run_skips_and_bad_checksum_not_written(tmp_path, monkeypatch):
    z = _zip([ROW_MS])
    calls = []

    def fake(url):
        calls.append(url)
        if "2024-12" in url:  # corrupt one file
            return b"0" * 64 + b"  f.zip" if url.endswith(".CHECKSUM") else z
        return (hashlib.sha256(z).hexdigest() + "  f.zip").encode() if url.endswith(".CHECKSUM") else z

    monkeypatch.setattr(binance, "get_bytes", fake)
    monkeypatch.setattr(binance, "PAUSE", 0)
    stale_daily = tmp_path / "BTCUSDT" / "BTCUSDT-1m-2024-11-05.parquet"
    stale_daily.parent.mkdir(parents=True)
    stale_daily.write_bytes(b"old")
    s1 = binance.download(["BTCUSDT"], dt.date(2024, 11, 1), dt.date(2025, 1, 2), out=tmp_path)
    assert s1["downloaded"] == 2 and s1["checksum_failed"] == ["BTCUSDT 2024-12"]
    assert not (tmp_path / "BTCUSDT" / "BTCUSDT-1m-2024-12.parquet").exists()
    assert not stale_daily.exists()  # the monthly file replaced the month's daily files
    n = len(calls)
    s2 = binance.download(["BTCUSDT"], dt.date(2024, 11, 1), dt.date(2025, 1, 2), out=tmp_path)
    assert s2["skipped"] == 2 and len(calls) - n == 2  # only the failed month is retried


# ---------- Deribit ----------

def test_dvol_pages_backwards_then_resumes_from_tail(tmp_path, monkeypatch):
    H = 3_600_000
    series = {i * H: [i * H, 1, 2, 0.5, float(i)] for i in range(10)}
    asked = []

    def fake(url, params, **kw):
        s, e = params["start_timestamp"], params["end_timestamp"]
        asked.append((s, e))
        rows = sorted((v for t, v in series.items() if s <= t <= e), key=lambda r: r[0])[-4:]  # 4 per page, newest
        return {"result": {"data": rows, "continuation": rows[0][0] - H if rows else None}}

    monkeypatch.setattr(deribit, "get_json", fake)
    monkeypatch.setattr(deribit, "PAUSE", 0)
    assert deribit.update("BTC", "1h", 0, 9 * H, out=tmp_path) == (10, 10)
    series[9 * H][4] = 99.0  # last candle was still open; it changes
    series[10 * H] = [10 * H, 1, 2, 0.5, 10.0]
    asked.clear()
    assert deribit.update("BTC", "1h", 0, 10 * H, out=tmp_path) == (1, 11)
    assert asked[0][0] == 9 * H  # resumed from the stored tail, not from the start
    df = pd.read_parquet(tmp_path / "dvol_BTC_1h.parquet")
    assert df.ts.is_unique and df.ts.is_monotonic_increasing and df.close.iloc[-2] == 99.0


# ---------- Polymarket ----------

def test_strike_and_settlement_parsing():
    assert polymarket.parse_strike("Bitcoin above $104K on September 1?") == 104000
    assert polymarket.parse_strike("Will the price of $ETH be above $1300 on Sept 30?") == 1300
    assert polymarket.parse_strike("Will the price of Bitcoin be above $102,000 on September 29?") == 102000
    # endDate a month off -> the question's date wins; year picked closest to endDate
    assert polymarket.settle_date("Bitcoin above $104K on September 1?", "2025-08-01T16:00:00Z") == dt.date(2025, 9, 1)
    assert polymarket.settle_date("ETH above $1,850 on April 1?", "2023-03-31T00:00:00Z") == dt.date(2023, 4, 1)
    assert polymarket.settle_date("Bitcoin Up or Down on December 31?", "2026-01-01T17:00:00Z") == dt.date(2025, 12, 31)
    assert polymarket.settle_date("Weird title", "2025-05-02T16:00:00Z") == dt.date(2025, 5, 2)
    # noon ET is 16:00 UTC in summer (EDT) and 17:00 UTC in winter (EST)
    assert polymarket.noon_et_ms(dt.date(2025, 9, 29)) == int(dt.datetime(2025, 9, 29, 16, tzinfo=dt.timezone.utc).timestamp() * 1000)
    assert polymarket.noon_et_ms(dt.date(2025, 12, 1)) == int(dt.datetime(2025, 12, 1, 17, tzinfo=dt.timezone.utc).timestamp() * 1000)
    assert polymarket.winner(["Yes", "No"], ["0", "1"]) == "No"
    assert polymarket.winner(["Up", "Down"], ["0.9999987", "0.0000013"]) == "Up"
    assert polymarket.winner(["Up", "Down"], ["0.5", "0.5"]) == "50-50"
    assert polymarket.winner(["Yes", "No"], ["0.4", "0.6"]) is None
    rules = "Binance 1 minute candle ... 12:00 in the ET timezone"
    base = {"closed": True, "clobTokenIds": "[1,2]", "description": rules}
    assert polymarket.is_target("strike", {**base, "question": "Will the price of Ethereum be above $2000 on May 9?"})
    assert not polymarket.is_target("strike", {**base, "question": "Will the price of Ethereum be between $1900 and $2000 on May 9?"})
    assert not polymarket.is_target("updown", {**base, "description": "Coingecko", "question": "x"})


def test_price_windows_respect_15_day_cap():
    w = polymarket.windows(0, 40 * 86400)
    assert w[0][0] == 0 and w[-1][1] == 40 * 86400 and len(w) == 3
    assert all(e - s <= polymarket.MAX_WINDOW for s, e in w) and all(a[1] == b[0] for a, b in zip(w, w[1:]))
    # missing closedTime (NaN in DataFrame records) -> settlement + 1 day; missing start -> 14 days before
    s, e = polymarket.price_window({"closed_time": float("nan"), "start_date": float("nan"), "settle_ts_ms": 86_400_000})
    assert e == 2 * 86400 + 3600 and s == e - 3600 - 14 * 86400 - 3600


def test_trades_paging_and_offset_cap(monkeypatch):
    monkeypatch.setattr(polymarket, "TRADES_PAGE", 3)
    monkeypatch.setattr(polymarket, "TRADES_MAX_OFFSET", 6)
    data = list(range(7))
    monkeypatch.setattr(polymarket, "polite_get", lambda url, p: data[p["offset"]:p["offset"] + p["limit"]])
    assert polymarket.fetch_trades("c") == (data, False)
    data[:] = list(range(20))
    rows, truncated = polymarket.fetch_trades("c")
    assert truncated and rows == list(range(9))


def test_event_second_run_skips(tmp_path, monkeypatch):
    calls = []

    def fake_get(url, params):
        calls.append(url)
        if "prices-history" in url:
            return {"history": [{"t": params["startTs"], "p": 0.4}]}
        return [{"conditionId": "c1", "asset": "y", "outcome": "Yes", "outcomeIndex": 0, "side": "BUY",
                 "price": 0.4, "size": 5, "timestamp": 1, "transactionHash": "0x", "proxyWallet": "0xw"}]

    monkeypatch.setattr(polymarket, "polite_get", fake_get)
    m = {"condition_id": "c1", "yes_token": "y", "no_token": "n", "yes_outcome": "Yes", "no_outcome": "No",
         "start_date": "2025-09-22T16:00:00Z", "closed_time": "2025-09-29 18:00:00+00", "settle_ts_ms": 0}
    assert polymarket.fetch_event("ev", [m], out=tmp_path) == "downloaded"
    n = len(calls)
    assert n == 3  # two tokens (one window each) + one trades page
    assert polymarket.fetch_event("ev", [m], out=tmp_path) == "skipped" and len(calls) == n
    p = pd.read_parquet(tmp_path / "prices" / "ev.parquet")
    assert set(p.token_id) == {"y", "n"} and p.t.dtype == "int64"


# ---------- football-data ----------

def test_season_codes():
    c =footballdata.season_codes(2012, dt.date(2026, 9, 30))
    assert c[0] == "1213" and c[-1] == "2627" and len(c) == 15
    assert footballdata.season_codes(2024, dt.date(2026, 6, 1)) == ["2425", "2526"]


def test_football_skips_past_refreshes_current_and_parses(tmp_path, monkeypatch):
    csv_old = "﻿Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,PSH,PSD,PSA,PSCH,PSCD,PSCA\nE0,18/08/12,A,B,1,0,H,2.0,3.4,4.0,1.9,3.5,4.2\n,,,,,,,,,,,,\n"
    csv_cur = "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,PPH,PPD,PPA\nE0,21/08/2026,C,D,2,2,D,2.1,3.3,3.9\n"
    calls = []

    def fake(url):
        calls.append(url)
        return (csv_cur if "/2627/" in url else csv_old).encode("utf-8")

    monkeypatch.setattr(footballdata, "get_bytes", fake)
    monkeypatch.setattr(footballdata, "PAUSE", 0)
    codes = ["2526", "2627"]
    assert footballdata.download(["E0"], codes, out=tmp_path)["downloaded"] == 2
    s2 = footballdata.download(["E0"], codes, out=tmp_path)
    assert s2 == {"downloaded": 1, "skipped": 1, "missing": []} and calls[-1].endswith("/2627/E0.csv")
    df = footballdata.build(out=tmp_path)
    assert len(df) == 2  # blank trailing row dropped
    old = df[df.season == "2025/26"].iloc[0]
    assert old.PSCH == pytest.approx(1.9) and old.Date == pd.Timestamp("2012-08-18") and old.FTHG == 1
    assert df[df.season == "2026/27"].PSCH.isna().all()  # current season has no Pinnacle columns
