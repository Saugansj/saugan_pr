"""Feed race (11 Oct): which free BTC trade feed moves first as received on this PC, and which one moves before
Polymarket reprices the BTC 5m/15m Up/Down markets? A 10-min calm-Sunday run saw Bybit/OKX ~0.5 s ahead of Binance.

record: every trade from 5 exchanges' public WebSockets (no keys) and the top of book of every open BTC crypto-fast Up
token (trader.marketdata's loader and parser), stamped with local receive time ->
data/research/feeds/<UTC start>/{binance,coinbase,kraken,bybit,okx}.csv (local_ms,price), pm.csv
(local_ms,token,bid,ask), markets.csv (token,start_ms,end_ms). Markets reload every 5 min.
analyze: per feed, (1) the lag that best aligns its 100 ms returns with Binance's, (2) the lag that best aligns them
with Polymarket Up-mid changes inside open windows (positive = the feed leads Polymarket), and (3) after each feed's
3 bp / 2 s move, the median time until the Up mid moved 1c the same way.

    python -m research.feeds.race record --hours 12
    python -m research.feeds.race analyze data/research/feeds/<dir>
"""
import argparse
import asyncio
import csv
import datetime as dt
import json
import pathlib
import re
import time

import numpy as np
import pandas as pd
import websockets

from common import DATA
from trader.marketdata import PM_WS, Books, load_markets

OUT = DATA / "research" / "feeds"
FEEDS = {  # name: (url, subscribe message or None, message -> prices)
    "binance": ("wss://stream.binance.com:9443/ws/btcusdt@trade", None,
                lambda m: [float(m["p"])] if m.get("e") == "trade" else []),
    "coinbase": ("wss://ws-feed.exchange.coinbase.com",
                 {"type": "subscribe", "product_ids": ["BTC-USD"], "channels": ["matches"]},
                 lambda m: [float(m["price"])] if m.get("type") in ("match", "last_match") else []),
    "kraken": ("wss://ws.kraken.com/v2", {"method": "subscribe", "params": {"channel": "trade", "symbol": ["BTC/USD"]}},
               lambda m: [float(t["price"]) for t in m.get("data", [])] if m.get("channel") == "trade" else []),
    "bybit": ("wss://stream.bybit.com/v5/public/spot", {"op": "subscribe", "args": ["publicTrade.BTCUSDT"]},
              lambda m: [float(t["p"]) for t in m.get("data", [])] if str(m.get("topic", "")).startswith("publicTrade") else []),
    "okx": ("wss://ws.okx.com:8443/ws/v5/public", {"op": "subscribe", "args": [{"channel": "trades", "instId": "BTC-USDT"}]},
            lambda m: [float(t["px"]) for t in m.get("data", [])] if m.get("arg", {}).get("channel") == "trades" else []),
}
now_ms = lambda: int(time.time() * 1000)


class Writer:
    def __init__(self, path, header):
        self.f = open(path, "a", newline="", encoding="utf-8")
        self.w = csv.writer(self.f)
        if self.f.tell() == 0:
            self.w.writerow(header)

    def row(self, *r):
        self.w.writerow(r)


async def feed(name, url, sub, parse, out, end):
    while time.time() < end:
        try:
            async with websockets.connect(url, open_timeout=15, max_size=None, ping_interval=20) as ws:
                if sub:
                    await ws.send(json.dumps(sub))
                while time.time() < end:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), 5)
                    except asyncio.TimeoutError:
                        continue
                    t = now_ms()
                    try:
                        for p in parse(json.loads(raw)):
                            out.row(t, p)
                    except (ValueError, KeyError, TypeError):
                        pass
        except Exception as e:  # noqa: BLE001 - a dropped feed reconnects; the gap shows in its file
            print(f"{name}: {e!r}", flush=True)
            await asyncio.sleep(2)


def btc_up_tokens() -> dict[str, tuple[int, int]]:
    markets, _ = load_markets(("crypto-fast",))
    out = {}
    for m in markets.values():
        d = re.search(r"-(\d+)m@", m.event_group or "")
        if m.asset == "BTC" and d and m.end_ms > now_ms() - 60_000 and m.end_ms - int(d[1]) * 60_000 < now_ms() + 15 * 60_000:
            out[m.token_yes] = (m.end_ms - int(d[1]) * 60_000, m.end_ms)
    return out


async def polymarket(out, mk, end):
    while time.time() < end:
        toks = await asyncio.to_thread(btc_up_tokens)
        for t, (s, e) in toks.items():
            mk.row(t, s, e)
        books, until, last = Books(), time.time() + 300, {}
        try:
            async with websockets.connect(PM_WS, max_size=None, open_timeout=20) as ws:
                await ws.send(json.dumps({"assets_ids": sorted(toks), "type": "market"}))
                last_ping = 0.0
                while time.time() < min(until, end):
                    if time.time() - last_ping >= 10:
                        await ws.send("PING")
                        last_ping = time.time()
                    try:
                        raw = await asyncio.wait_for(ws.recv(), 1)
                    except asyncio.TimeoutError:
                        continue
                    t = now_ms()
                    for ev in books.apply(raw if isinstance(raw, str) else raw.decode(), t):
                        if ev[0] == "book" and ev[1] in toks:
                            b = books.books[ev[1]]
                            top = (b.best_bid(), b.best_ask())
                            if last.get(ev[1]) != top:  # top of book only: deeper levels made 884 MB in 5 h
                                last[ev[1]] = top
                                out.row(t, ev[1], *top)
        except Exception as e:  # noqa: BLE001
            print(f"polymarket: {e!r}", flush=True)
            await asyncio.sleep(2)


def record(hours: float) -> pathlib.Path:
    d = OUT / dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    d.mkdir(parents=True, exist_ok=True)
    end = time.time() + hours * 3600
    ws = {n: Writer(d / f"{n}.csv", ["local_ms", "price"]) for n in FEEDS}
    pm, mk = Writer(d / "pm.csv", ["local_ms", "token", "bid", "ask"]), Writer(d / "markets.csv", ["token", "start_ms", "end_ms"])

    async def flush():
        while time.time() < end:
            await asyncio.sleep(1)
            for w in (*ws.values(), pm, mk):
                w.f.flush()

    async def main():
        await asyncio.gather(flush(), polymarket(pm, mk, end), *(feed(n, *FEEDS[n], ws[n], end) for n in FEEDS))

    print(f"recording to {d} for {hours} h", flush=True)
    asyncio.run(main())
    return d


# ---------- analyze ----------

def on_grid(df: pd.DataFrame, col: str, grid: np.ndarray) -> np.ndarray:
    """Last value at or before each grid time (NaN before the first)."""
    i = np.searchsorted(df.local_ms.to_numpy(), grid, side="right") - 1
    v = df[col].to_numpy(dtype=float)
    return np.where(i >= 0, v[np.clip(i, 0, None)], np.nan)


def best_lag(x: np.ndarray, y: np.ndarray, max_steps: int) -> tuple[int, float]:
    """Steps L maximising corr(x[t], y[t + L]): positive L = x moves L steps before y."""
    best = (0, -1.0)
    for L in range(-max_steps, max_steps + 1):
        a, b = (x[:len(x) - L], y[L:]) if L >= 0 else (x[-L:], y[:len(y) + L])
        ok = np.isfinite(a) & np.isfinite(b)
        if ok.sum() > 100 and np.std(a[ok]) > 0 and np.std(b[ok]) > 0:
            c = np.corrcoef(a[ok], b[ok])[0, 1]
            if c > best[1]:
                best = (L, c)
    return best


def analyze(d: pathlib.Path, step: int = 100) -> str:
    fx = {n: pd.read_csv(d / f"{n}.csv") for n in FEEDS if (d / f"{n}.csv").exists()}
    fx = {n: v for n, v in fx.items() if len(v) > 100}
    pm = pd.read_csv(d / "pm.csv", dtype={"token": str}).dropna()
    mk = pd.read_csv(d / "markets.csv", dtype={"token": str}).drop_duplicates("token")
    t0 = max(v.local_ms.iloc[0] for v in fx.values()) + 5000
    t1 = min(v.local_ms.iloc[-1] for v in fx.values())
    grid = np.arange(t0, t1, step, dtype=float)
    lp = {n: np.log(on_grid(v, "price", grid)) for n, v in fx.items()}
    ret = {n: np.diff(v) for n, v in lp.items()}
    L = [f"Feed race {d.name}: {(t1 - t0) / 3.6e6:.1f} h, trades " + ", ".join(f"{n} {len(v)}" for n, v in fx.items()), "",
         "| feed | leads Binance by (ms) | corr | leads Polymarket by (ms) | corr | 3 bp move -> PM 1c (median ms, n) |",
         "|---|---|---|---|---|---|"]
    pm["mid"] = (pm.bid + pm.ask) / 2
    up = {t: g.sort_values("local_ms") for t, g in pm.groupby("token")}
    for n in fx:
        lb, cb = best_lag(ret["binance"], ret[n], 30) if n != "binance" else (0, 1.0)
        xs, ys, waits = [], [], []
        for r in mk.itertuples():
            g = up.get(r.token)
            if g is None or len(g) < 50:
                continue
            m = (grid >= r.start_ms) & (grid < r.end_ms - 60_000)
            if m.sum() < 100:
                continue
            mid = on_grid(g, "mid", grid[m])
            xs.append(np.diff(lp[n][m]))
            ys.append(np.diff(mid))
            s, gm = lp[n][m], grid[m]
            last = -1e18
            for i in range(20, len(s)):
                mv = (s[i] - s[i - 20]) * 1e4
                if abs(mv) >= 3 and gm[i] - last > 60_000 and np.isfinite(mid[i]):
                    last = gm[i]
                    j = next((k for k in range(i, min(len(mid), i + 100)) if np.isfinite(mid[k])
                              and np.sign(mv) * (mid[k] - mid[i]) >= 0.01), None)
                    if j is not None:
                        waits.append((j - i) * step)
        if xs:
            lp_, cp = best_lag(np.concatenate(xs), np.concatenate(ys), 30)
            w = f"{np.median(waits):.0f} ({len(waits)})" if waits else "-"
            L.append(f"| {n} | {-lb * step:+d} | {cb:.2f} | {lp_ * step:+d} | {cp:.2f} | {w} |")
    L += ["", "Read: a feed that leads Polymarket by more, with a higher corr, is the better signal. All times are this "
              "PC's receive clock, so network distance is included."]
    text = "\n".join(L) + "\n"
    (d / "analysis.md").write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("record").add_argument("--hours", type=float, default=12)
    sp.add_parser("analyze").add_argument("dir", type=pathlib.Path)
    a = ap.parse_args()
    print(analyze(record(a.hours)) if a.cmd == "record" else analyze(a.dir))
