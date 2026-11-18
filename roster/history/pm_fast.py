"""BTC 5m/15m Up/Down history for research/replay: market catalog (Gamma) + top-of-book and trades (pmxt archive).

1. Catalog per UTC day: every btc-updown-5m-<start> / btc-updown-15m-<start> event (start = unix seconds, slot-aligned)
   -> data/history/pm_fast/catalog/<day>.parquet: cid, slug, dur_min, start_ms, end_ms, token_up, token_down, winner
   ("up" / "down" / None if not resolved). One Gamma GET per slug, threads share a rate cap.
2. Book per UTC hour from the pmxt v2 archive (hourly Parquet of the Polymarket CLOB market WebSocket, one row per
   event, files sorted by market so a market filter fetches only its row groups):
   -> data/history/pm_fast/tob/<day>T<HH>.parquet: ts_ms (archive receive time), asset_id, best_bid, best_ask, kept
      only when the pair changes (price_change rows carry both).
   -> data/history/pm_fast/trades/<day>T<HH>.parquet: ts_ms, asset_id, price, size, side (last_trade_price rows).
   Events in one millisecond keep the archive's file order; only the last state per (asset, ms) is kept.
   Limits: no depth (the size at the best ask is not kept); the archive covers 2026-04-13 to about 2026-08-10;
   ts_ms is the archive's receive clock. Read asset_id as str.
   An hour whose two files exist is skipped, so reruns resume; a missing archive hour is logged and skipped.

    python -m history.pm_fast 2026-07-27 2026-08-09 [--workers 8] [--rps 8] [--asset eth]
ETH (10 Oct, --asset eth): the same for eth-updown-* events, under data/history/pm_fast/eth/ (BTC paths unchanged).
"""
import argparse
import datetime as dt
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import duckdb
import pandas as pd

from common import DATA, append_jsonl, get_json, now_ms
from history import save_parquet

GAMMA = "https://gamma-api.polymarket.com/events"
ARCHIVE = "https://r2v2.pmxt.dev/polymarket_orderbook_{}.parquet"   # {} = YYYY-MM-DDTHH (UTC)
OUT = DATA / "history" / "pm_fast"
DURS = (5, 15)
base = lambda asset: OUT if asset == "btc" else OUT / asset   # BTC keeps the original paths


class Rate:
    def __init__(self, rps: float):
        self.gap, self.next, self.lock = 1.0 / rps, 0.0, threading.Lock()

    def wait(self) -> None:
        with self.lock:
            t = max(time.monotonic(), self.next)
            self.next = t + self.gap
        time.sleep(max(0.0, t - time.monotonic()))


def market_row(slug: str, dur: int, start_s: int, rate: Rate) -> dict | None:
    rate.wait()
    try:
        ev = get_json(GAMMA, {"slug": slug})
    except Exception:  # noqa: BLE001 - one failed GET must not abort the day; the catalog is saved only when complete
        return None
    if not ev or not ev[0].get("markets"):
        return None
    m = ev[0]["markets"][0]
    toks, names = json.loads(m["clobTokenIds"]), [o.lower() for o in json.loads(m["outcomes"])]
    prices = json.loads(m.get("outcomePrices") or "[]")
    up = names.index("up")
    winner = None
    if m.get("closed") and prices and sorted(prices) == ["0", "1"]:
        winner = "up" if prices[up] == "1" else "down"
    return {"cid": m["conditionId"], "slug": slug, "dur_min": dur, "start_ms": start_s * 1000,
            "end_ms": (start_s + dur * 60) * 1000, "token_up": toks[up], "token_down": toks[1 - up], "winner": winner}


def catalog(day: dt.date, workers: int, rate: Rate, asset: str = "btc") -> pd.DataFrame:
    path = base(asset) / "catalog" / f"{day}.parquet"
    if path.exists():
        return pd.read_parquet(path)
    t0 = int(dt.datetime.combine(day, dt.time(), dt.timezone.utc).timestamp())
    jobs = [(f"{asset}-updown-{d}m-{s}", d, s) for d in DURS for s in range(t0, t0 + 86_400, d * 60)]
    with ThreadPoolExecutor(workers) as ex:
        rows = [r for r in ex.map(lambda j: market_row(*j, rate), jobs) if r]
    df = pd.DataFrame(rows)
    if len(df) == len(jobs) and df.winner.notna().all():  # cache only a complete, resolved day; else retry next run
        save_parquet(df, path)
    return df


def book_hour(hour: dt.datetime, cat: pd.DataFrame, con, asset: str = "btc") -> str:
    tag = hour.strftime("%Y-%m-%dT%H")
    tob_p, tr_p = base(asset) / "tob" / f"{tag}.parquet", base(asset) / "trades" / f"{tag}.parquet"
    if tob_p.exists() and tr_p.exists():
        return "skipped"
    h0 = int(hour.timestamp() * 1000)
    live = cat[(cat.end_ms > h0) & (cat.start_ms < h0 + 3_600_000 + 15 * 60_000)]  # open in, or listed just before
    if live.empty:
        return "no markets"
    cids = ", ".join(f"'{c}'::BLOB" for c in live.cid)
    url = ARCHIVE.format(tag)
    try:
        con.execute(f"""CREATE OR REPLACE TEMP TABLE ev AS
            SELECT epoch_ms(timestamp_received) AS ts_ms, asset_id, event_type, CAST(best_bid AS DOUBLE) AS best_bid,
                   CAST(best_ask AS DOUBLE) AS best_ask, CAST(price AS DOUBLE) AS price, CAST(size AS DOUBLE) AS size, side,
                   file_row_number AS rn
            FROM read_parquet('{url}', file_row_number = true)
            WHERE market IN ({cids}) AND event_type IN ('price_change', 'last_trade_price')""")
    except duckdb.Error as e:
        return f"archive error: {str(e)[:120]}"
    # many events share a millisecond: file order (file_row_number) is the arrival order; keep the last state per ms
    tob = con.execute("""WITH last_per_ms AS (
            SELECT * FROM ev WHERE event_type = 'price_change'
            QUALIFY row_number() OVER (PARTITION BY asset_id, ts_ms ORDER BY rn DESC) = 1)
        SELECT ts_ms, asset_id, best_bid, best_ask FROM (
            SELECT *, lag(best_bid) OVER w AS pb, lag(best_ask) OVER w AS pa FROM last_per_ms
            WINDOW w AS (PARTITION BY asset_id ORDER BY ts_ms))
        WHERE pb IS DISTINCT FROM best_bid OR pa IS DISTINCT FROM best_ask ORDER BY ts_ms, asset_id""").df()
    trades = con.execute("""SELECT ts_ms, asset_id, price, size, side FROM ev
        WHERE event_type = 'last_trade_price' ORDER BY ts_ms, rn""").df()
    save_parquet(trades, tr_p)
    save_parquet(tob, tob_p)
    return f"{len(tob)} tob, {len(trades)} trades"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("first")
    ap.add_argument("last")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--rps", type=float, default=8.0)
    ap.add_argument("--asset", choices=("btc", "eth"), default="btc")
    a = ap.parse_args(argv)
    rate, con = Rate(a.rps), duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; SET threads = 4; SET memory_limit = '1GB'; "
                f"SET temp_directory = '.tmp/pm_fast_{os.getpid()}';")  # 8 GB PC shared with the paper runs; own spill dir per process
    day, last = dt.date.fromisoformat(a.first), dt.date.fromisoformat(a.last)
    while day <= last:
        cat = catalog(day, a.workers, rate, a.asset)
        print(f"{day}: {len(cat)} markets, {int(cat.winner.notna().sum()) if len(cat) else 0} resolved", flush=True)
        for h in range(24):
            hour = dt.datetime.combine(day, dt.time(h), dt.timezone.utc)
            t = time.monotonic()
            res = book_hour(hour, cat, con, a.asset)
            append_jsonl(base(a.asset) / "log.jsonl", {"hour": hour.isoformat(), "result": res,
                                             "s": round(time.monotonic() - t, 1), "at_ms": now_ms()})
            print(f"  {hour:%H}: {res} ({time.monotonic() - t:.0f} s)", flush=True)
        day += dt.timedelta(days=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
