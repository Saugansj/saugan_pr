"""v7 test helpers (23 Oct): reference ticks per day and the fair-value inputs at a decision, offline.

Ticks: Bybit spot trades (the paper runs' ref feed; research.feeds.bybit_replay caches them), else Binance 1 s klines
(close of each second at its last ms) for a day Bybit has not published yet. rv30 and K follow the engine exactly:
speed.RealisedVol's definition (prices in force strictly before t - 30 min .. t, bp/min) and speed.StartPrice's
(time-weighted average of the ticks over the 60 s before the window start).
"""
import datetime as dt
import math

import numpy as np
import pandas as pd

import common
from common import DATA
from history import save_parquet
from research.feeds.bybit_replay import ticks as bybit_ticks
from trader.growth.fast_updown import twa

BIN1S = DATA / "history" / "binance1s"


def binance_1s(day: dt.date, symbol: str, until_ms: int | None = None) -> pd.DataFrame:
    """One UTC day of Binance 1 s klines as ts_ms (the second's last ms), price (close); cached (a day still running
    is cached as <day>.partial.parquet and reused: delete it to extend it)."""
    p, part = BIN1S / symbol / f"{day}.parquet", BIN1S / symbol / f"{day}.partial.parquet"
    for f in (p, part):
        if f.exists():
            return pd.read_parquet(f)
    d0 = int(dt.datetime.combine(day, dt.time(), dt.timezone.utc).timestamp() * 1000)
    end = min(d0 + 86_400_000, until_ms or common.now_ms())
    rows, t = [], d0
    while t < end:
        k = common.get_json("https://api.binance.com/api/v3/klines",
                            {"symbol": symbol, "interval": "1s", "startTime": t, "limit": 1000})
        if not k:
            break
        rows += [(int(b[0]) + 999, float(b[4])) for b in k if int(b[0]) < end]
        t = int(k[-1][0]) + 1000
    df = pd.DataFrame(rows, columns=["ts_ms", "price"])
    save_parquet(df, p if end == d0 + 86_400_000 else part)
    return df


def load_ticks(asset: str, days, binance_days=()) -> tuple[np.ndarray, np.ndarray]:
    """(ts_ms, price) arrays over the days, Bybit spot unless the day is in binance_days."""
    sym = f"{asset.upper()}USDT"
    parts = [binance_1s(d, sym) if d in binance_days else bybit_ticks(d, "spot", sym) for d in sorted(set(days))]
    t = pd.concat(parts).sort_values("ts_ms", kind="stable")
    return t.ts_ms.to_numpy(), t.price.to_numpy()


def rv30(ts: np.ndarray, px: np.ndarray, t: int) -> float | None:
    """speed.RealisedVol.rv30 from the full tick record (exact prices in force strictly before each minute mark)."""
    if not len(ts) or ts[0] >= t - 30 * 60_000:
        return None
    idx = np.searchsorted(ts, [t - s * 60_000 for s in range(30, -1, -1)], "left") - 1
    r = np.diff(np.log(px[idx]))
    return float(np.std(r) * 1e4)


def start_k(ts: np.ndarray, px: np.ndarray, b: int, w: int = 60_000) -> float | None:
    """speed.StartPrice's K for the window starting at b."""
    i0, i1 = np.searchsorted(ts, b - w, "right") - 1, np.searchsorted(ts, b, "left")
    if i0 < 0 or i1 <= i0:
        return None
    return twa(list(zip(ts[i0:i1].tolist(), px[i0:i1].tolist())), b - w, b)


def price_at(ts: np.ndarray, px: np.ndarray, t: int) -> float | None:
    i = np.searchsorted(ts, t, "right") - 1
    return float(px[i]) if i >= 0 else None


def fit_c(lr: np.ndarray, sd1: np.ndarray, won: np.ndarray, grid=None) -> tuple[float, float]:
    """The c minimising the log-loss of Phi(lr / (c sd1)) for the favoured side; lr = signed ln(S/K), sd1 = sigma
    sqrt(tau) at c = 1. Returns (c, log-loss)."""
    from scipy.stats import norm
    best = None
    for c in grid if grid is not None else np.round(np.arange(0.3, 4.01, 0.05), 2):
        p = np.clip(norm.cdf(lr / (c * sd1)), 1e-4, 1 - 1e-4)
        ll = float(-np.mean(won * np.log(p) + (1 - won) * np.log(1 - p)))
        if best is None or ll < best[1]:
            best = (float(c), ll)
    return best


def logloss(p, won) -> float:
    p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    return float(-np.mean(won * np.log(p) + (1 - won) * np.log(1 - p)))


def reliability(p, won, label: str, bins=10) -> list[str]:
    """Markdown rows: decile of p -> mean p, win rate, n."""
    d = pd.DataFrame({"p": p, "won": np.asarray(won, float)}).dropna()
    d["q"] = pd.qcut(d.p.rank(method="first"), bins, labels=False)
    L = [f"| {label} decile | mean {label} | win rate | n |", "|---|---|---|---|"]
    for q, g in d.groupby("q"):
        L.append(f"| {q + 1} | {g.p.mean():.3f} | {g.won.mean():.3f} | {len(g)} |")
    return L


def sd1(rv: float | None, tau_s: float, fallback: float) -> float:
    return (rv if rv is not None else fallback) / math.sqrt(60) * 1e-4 * math.sqrt(max(tau_s, 0.0))
