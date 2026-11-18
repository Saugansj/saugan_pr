"""Would a Bybit BTC signal beat our Binance one? (11 Oct; a 10-min feed race from this PC saw Bybit/OKX ~0.5 s ahead.)

Downloads Bybit BTCUSDT daily trades (public.bybit.com, free): spot, or `--market linear` for the perpetual future.
Runs the research loop's wide replay (research.loop.nightly.wide) on them against the same Polymarket books and catalog
(history/pm_fast), and prints v4's and v5's live rules per delay next to the Binance-driven replay already in
data/research/loop/wide. `--first` (12 Oct) adds a "first to report" source: Binance, Bybit spot and Bybit perp signals
merged, keeping per market and direction the earliest signal (then the 60 s detector cooldown), as if the trader acted
on whichever feed crossed first. Timestamps are each exchange's own trade time, so this measures which exchange's
price leads, not network distance from this PC (research/feeds/race.py measures that).

    python -m research.feeds.bybit_replay 2026-07-27 2026-08-09 [--market linear] [--first]
"""
import argparse
import datetime as dt
import gzip
import io
import urllib.request

import pandas as pd

from common import DATA
from history import save_parquet
from research.loop import nightly as N
from research.replay.replay import load_day

SRC = {  # market: (URL, cache dir, timestamp column, its unit in ms); {s} = symbol, {d} = day
    "spot": ("https://public.bybit.com/spot/{s}/{s}_{d}.csv.gz", "{s}", "timestamp", 1),
    "linear": ("https://public.bybit.com/trading/{s}/{s}{d}.csv.gz", "{s}-linear", "timestamp", 1000),
}
RULES = {"v4": (0.85, 0.10, "none", "hold"), "v5": (0.85, 0.10, "calm55", "hold")}


def ticks(day: dt.date, market: str = "spot", symbol: str = "BTCUSDT") -> pd.DataFrame:
    """One day's Bybit trades as ts_ms, price (the Binance aggTrades columns the replay reads); cached as Parquet."""
    url, sub, col, unit = SRC[market]
    p = DATA / "history" / "bybit" / sub.format(s=symbol) / f"{day}.parquet"
    if not p.exists():
        with urllib.request.urlopen(url.format(s=symbol, d=day), timeout=180) as r:
            df = pd.read_csv(io.BytesIO(gzip.decompress(r.read())), usecols=[col, "price"])
        df = pd.DataFrame({"ts_ms": (df[col] * unit).round().astype("int64"), "price": df.price.astype("float64")})
        save_parquet(df.sort_values("ts_ms", kind="stable"), p)
    return pd.read_parquet(p)


def first_to_report(wides: list[pd.DataFrame]) -> pd.DataFrame:
    """Merge signal rows from several feeds: per (day, lag, cfg, cid, dir), keep a signal only if no kept signal for the
    same key was within the last 60 s (the detector cooldown), taking the earliest feed first."""
    w = pd.concat(wides, ignore_index=True).sort_values("t", kind="stable")
    keep, last = [], {}
    for r in w[["day", "lag", "cfg", "cid", "dir", "t"]].itertuples():
        k = (r.day, r.lag, r.cfg, r.cid, r.dir)
        if r.t - last.get(k, -10**15) > 60_000:
            last[k] = r.t
            keep.append(r.Index)
    return w.loc[keep]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("first")
    ap.add_argument("last")
    ap.add_argument("--market", choices=tuple(SRC), default="spot")
    ap.add_argument("--first", dest="merge", action="store_true", help="also Binance + Bybit spot + perp, first to report")
    a = ap.parse_args(argv)
    d, last = dt.date.fromisoformat(a.first), dt.date.fromisoformat(a.last)
    feeds = {a.market: []} if not a.merge else {"spot": [], "linear": []}
    while d <= last:
        got = load_day(d)  # Binance ticks (unused here), the catalog and the archive books
        if got:
            for m in feeds:
                t = pd.concat([ticks(d - dt.timedelta(days=1), m), ticks(d, m)]).sort_values("ts_ms", kind="stable")
                feeds[m].append(N.wide(t, got[1], got[2], d, source=f"bybit-{m}"))
            print(d, "replayed", flush=True)
        d += dt.timedelta(days=1)
    by = {m: pd.concat(v, ignore_index=True) for m, v in feeds.items()}
    days = set(next(iter(by.values())).day)
    bn = pd.concat([pd.read_parquet(p) for p in sorted((N.OUT / "wide").glob("*.parquet"))], ignore_index=True)
    srcs = {"Binance": bn[bn.day.isin(days)], **{f"Bybit {m}": w for m, w in by.items()}}
    if a.merge:
        srcs["First of all"] = first_to_report(list(srcs.values()))
    print(f"\n{len(days)} days; 2 s / 6 bp detector; per trade ± SE (n) total")
    for lag in N.LAGS:
        for name, rule in RULES.items():
            line = f"delay {lag:4d} ms {name}:"
            for src, w in srcs.items():
                g = N.pnl(w[(w.lag == lag) & (w.cfg == "2s/6bp")])
                tr = N.trades(g, *rule)
                m, se, n = N.stat(tr)
                line += f" | {src} {m:+.3f} ± {se:.3f} ({n}) {tr.pnl.sum():+6.1f}"
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
