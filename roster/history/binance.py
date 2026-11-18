"""Binance spot 1m klines from data.binance.vision -> Parquet, each zip verified against its .CHECKSUM.

Monthly zips up to the last full month, daily zips for the current month (up to yesterday).
One Parquet per zip under data/history/binance/<SYMBOL>/; an existing file is skipped, so reruns resume.
When a month completes, its monthly file replaces that month's daily files.

    python -m history.binance [--start 2022-01] [--symbols BTCUSDT ETHUSDT]
    python -m history.binance --aggtrades 2026-07-27 2026-08-09 [--symbols BTCUSDT]   # tick data for research/replay
"""
import argparse
import datetime as dt
import hashlib
import io
import time
import zipfile

import pandas as pd

from common import DATA, append_jsonl, now_ms
from history import get_bytes, save_parquet

BASE = "https://data.binance.vision/data/spot"
OUT = DATA / "history" / "binance"
COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
        "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"]
PAUSE = 0.2  # seconds between files; data.binance.vision is a static bucket


def periods(start: dt.date, today: dt.date) -> list[tuple[str, str]]:
    """[("monthly", "YYYY-MM"), ..., ("daily", "YYYY-MM-DD"), ...] from start to yesterday."""
    out, (y, m) = [], (start.year, start.month)
    while (y, m) < (today.year, today.month):
        out.append(("monthly", f"{y:04d}-{m:02d}"))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    d = max(today.replace(day=1), start)
    while d < today:
        out.append(("daily", d.isoformat()))
        d += dt.timedelta(days=1)
    return out


def verify(zip_bytes: bytes, checksum_text: str) -> bool:
    """.CHECKSUM files read '<sha256>  <filename>'."""
    return hashlib.sha256(zip_bytes).hexdigest() == checksum_text.split()[0].strip().lower()


def parse(zip_bytes: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        raw = z.read(z.namelist()[0])
    df = pd.read_csv(io.BytesIO(raw), header=None, names=COLS, dtype=str)
    df = df[df.open_time.str.isdigit()].drop(columns="ignore")  # drop a header row if present
    for c in ("open_time", "close_time", "trades"):
        df[c] = df[c].astype("int64")
    for c in ("open_time", "close_time"):  # files from 2025 on use microseconds; store ms
        df.loc[df[c] > 10**14, c] //= 1000
    for c in ("open", "high", "low", "close", "volume", "quote_volume", "taker_buy_base", "taker_buy_quote"):
        df[c] = df[c].astype("float64")
    return df.reset_index(drop=True)


AGG_COLS = ["agg_id", "price", "qty", "first_id", "last_id", "ts_ms", "buyer_maker", "best_match"]


def parse_agg(zip_bytes: bytes) -> pd.DataFrame:
    """aggTrades CSV -> ts_ms (trade time, ms), price, qty, buyer_maker. Files from 2025 on use microseconds."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        raw = z.read(z.namelist()[0])
    df = pd.read_csv(io.BytesIO(raw), header=None, names=AGG_COLS, dtype=str)
    df = df[df.agg_id.str.isdigit()]
    ts = df.ts_ms.astype("int64")
    out = pd.DataFrame({"ts_ms": ts.where(ts < 10**14, ts // 1000), "price": df.price.astype("float64"),
                        "qty": df.qty.astype("float64"), "buyer_maker": df.buyer_maker.str.lower() == "true"})
    return out.reset_index(drop=True)


def download_agg(symbols, first: dt.date, last: dt.date, out=OUT) -> dict:
    """Daily aggTrades zips (checksum-verified) -> <out>/<SYMBOL>/aggTrades/<SYMBOL>-aggTrades-<day>.parquet."""
    stats = {"downloaded": 0, "skipped": 0, "not_published": [], "checksum_failed": []}
    for sym in symbols:
        d = first
        while d <= last:
            path = out / sym / "aggTrades" / f"{sym}-aggTrades-{d}.parquet"
            if path.exists():
                stats["skipped"] += 1
            else:
                url = f"{BASE}/daily/aggTrades/{sym}/{sym}-aggTrades-{d}.zip"
                z, c = get_bytes(url), get_bytes(url + ".CHECKSUM")
                if z is None or c is None:
                    stats["not_published"].append(f"{sym} {d}")
                elif not verify(z, c.decode()):
                    stats["checksum_failed"].append(f"{sym} {d}")
                else:
                    df = parse_agg(z)
                    save_parquet(df, path)
                    append_jsonl(out / "checksums.jsonl", {"file": path.name, "sha256": c.decode().split()[0],
                                                           "verified": True, "rows": len(df), "at_ms": now_ms()})
                    stats["downloaded"] += 1
                    time.sleep(PAUSE)
            d += dt.timedelta(days=1)
    return stats


def download(symbols, start: dt.date, today: dt.date, out=OUT) -> dict:
    stats = {"downloaded": 0, "skipped": 0, "not_published": [], "checksum_failed": []}
    for sym in symbols:
        for kind, tag in periods(start, today):
            path = out / sym / f"{sym}-1m-{tag}.parquet"
            if path.exists():
                stats["skipped"] += 1
                continue
            url = f"{BASE}/{kind}/klines/{sym}/1m/{sym}-1m-{tag}.zip"
            z, c = get_bytes(url), get_bytes(url + ".CHECKSUM")
            if z is None or c is None:
                stats["not_published"].append(f"{sym} {tag}")
                continue
            if not verify(z, c.decode()):
                stats["checksum_failed"].append(f"{sym} {tag}")
                continue
            df = parse(z)
            save_parquet(df, path)
            append_jsonl(out / "checksums.jsonl", {"file": path.name, "sha256": c.decode().split()[0],
                                                   "verified": True, "rows": len(df), "at_ms": now_ms()})
            if kind == "monthly":
                for daily in (out / sym).glob(f"{sym}-1m-{tag}-*.parquet"):
                    daily.unlink()
            stats["downloaded"] += 1
            time.sleep(PAUSE)
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--start", default="2022-01", help="first month YYYY-MM (default 2022-01)")
    ap.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT"])
    ap.add_argument("--aggtrades", nargs=2, metavar=("FIRST_DAY", "LAST_DAY"), help="daily aggTrades instead of klines")
    a = ap.parse_args()
    if a.aggtrades:
        s = download_agg(a.symbols, *(dt.date.fromisoformat(x) for x in a.aggtrades))
        print(s)
        raise SystemExit(1 if s["checksum_failed"] else 0)
    s = download(a.symbols, dt.date.fromisoformat(a.start + "-01"), dt.datetime.now(dt.timezone.utc).date())
    print(s)
    raise SystemExit(1 if s["checksum_failed"] else 0)
