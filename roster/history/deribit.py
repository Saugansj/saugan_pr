"""Deribit DVOL (volatility index) history for BTC and ETH at 1h and 1D -> Parquet.

public/get_volatility_index_data returns at most 1000 candles per call, newest first, plus a
`continuation` timestamp to page backwards. One file per currency and resolution under
data/history/deribit/; a rerun only fetches candles newer than the last stored one.

    python -m history.deribit [--start 2022-01-01]
"""
import argparse
import datetime as dt
import time

import pandas as pd

from common import DATA, get_json, now_ms
from history import save_parquet

URL = "https://www.deribit.com/api/v2/public/get_volatility_index_data"
OUT = DATA / "history" / "deribit"
RESOLUTIONS = {"1h": "3600", "1D": "1D"}
COLS = ["ts", "open", "high", "low", "close"]
PAUSE = 0.2  # Deribit public limit is ~20 req/s; stay far below


def fetch(currency: str, resolution: str, start_ms: int, end_ms: int) -> list[list]:
    rows, end = [], end_ms
    while end > start_ms:
        r = get_json(URL, {"currency": currency, "start_timestamp": start_ms,
                           "end_timestamp": end, "resolution": resolution})["result"]
        rows += r["data"]
        cont = r.get("continuation")
        if not r["data"] or not cont or cont >= end:
            break
        end = cont
        time.sleep(PAUSE)
    return rows


def update(currency: str, res_name: str, start_ms: int, end_ms: int, out=OUT) -> tuple[int, int]:
    """Fetch from the stored tail on (re-fetching the last, possibly still open, candle); returns (new rows, total rows)."""
    path = out / f"dvol_{currency}_{res_name}.parquet"
    old = pd.read_parquet(path) if path.exists() else pd.DataFrame(columns=COLS)
    since = int(old.ts.max()) if len(old) else start_ms
    new = pd.DataFrame(fetch(currency, RESOLUTIONS[res_name], since, end_ms), columns=COLS)
    new = new[new.ts >= since]
    added = len(set(new.ts) - set(old.ts))
    if len(new):
        df = pd.concat([old, new]).astype({"ts": "int64"}).drop_duplicates("ts", keep="last").sort_values("ts")
        save_parquet(df.astype({c: "float64" for c in COLS[1:]}), path)
    return added, len(old) + added


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--start", default="2022-01-01")
    a = ap.parse_args()
    start = int(dt.datetime.fromisoformat(a.start).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
    for cur in ("BTC", "ETH"):
        for res in RESOLUTIONS:
            n, total = update(cur, res, start, now_ms())
            print(f"dvol {cur} {res}: {n} new rows, {total} total")
