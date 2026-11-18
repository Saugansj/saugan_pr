"""Crypto version of the weather "NO at 85-97c" idea (23 Oct): in the last L seconds of a BTC 5m/15m Up/Down market,
buy the leading side when its ask is in [lo, hi] and hold to settlement. Offline on the archive already on disk
(data/history/pm_fast: catalog = winner per market, tob = best bid/ask changes); no download.

  .venv\\Scripts\\python.exe -m research.weather.crypto_endgame

The book at a checkpoint is the last top-of-book row at or before it (within 120 s). Taker at that ask (no race
modelled: an upper bound), fee 0.07 p(1-p) per share. SE clustered by UTC hour (markets of one hour move together).
"""
import glob
import pathlib

import numpy as np
import pandas as pd

from common import DATA

H = DATA / "history" / "pm_fast"
LEFT_S = (240, 120, 60, 30, 15)
BANDS = ((0.85, 0.90), (0.90, 0.95), (0.95, 0.97), (0.85, 0.97))


def day_rows(day: str) -> pd.DataFrame:
    cat = pd.read_parquet(H / "catalog" / f"{day}.parquet")
    files = sorted(glob.glob(str(H / "tob" / f"{day}T*.parquet")))
    if not files or cat.empty:
        return pd.DataFrame()
    tob = pd.concat([pd.read_parquet(f) for f in files]).sort_values("ts_ms")
    cat = cat[cat.winner.isin(["up", "down"])]
    q = pd.concat([cat.assign(side=s, token=cat[f"token_{s}"], t=cat.end_ms - L * 1000, left_s=L)
                   for s in ("up", "down") for L in LEFT_S]).sort_values("t")
    q["token"], tob["asset_id"] = q.token.astype(str), tob.asset_id.astype(str)
    q["t"], tob["ts_ms"] = q.t.astype("int64"), tob.ts_ms.astype("int64")
    m = pd.merge_asof(q, tob.rename(columns={"asset_id": "token", "ts_ms": "t"}), on="t", by="token",
                      direction="backward", tolerance=120_000)
    m = m.dropna(subset=["best_ask"])
    m["won"] = (m.side == m.winner).astype(float)
    m["day"] = day
    return m[["cid", "dur_min", "end_ms", "left_s", "side", "best_ask", "won", "day"]]


def cluster_se(x: np.ndarray, g: np.ndarray) -> float:
    s = pd.Series(x - x.mean()).groupby(g).sum()
    return float(np.sqrt((s ** 2).sum()) / len(x)) if len(x) > 1 else float("nan")


def score(t: pd.DataFrame) -> dict:
    a = t.best_ask.to_numpy()
    pnl = t.won.to_numpy() - a - 0.07 * a * (1 - a)
    hour = (t.end_ms // 3_600_000).to_numpy()
    return {"n": len(t), "win%": 100 * t.won.mean(), "need%": 100 * (a + 0.07 * a * (1 - a)).mean(),
            "pnl/share": pnl.mean(), "se": cluster_se(pnl, hour), "pnl_5sh": 5 * pnl.sum()}


def main() -> None:
    days = sorted(pathlib.Path(f).stem for f in glob.glob(str(H / "catalog" / "*.parquet")))
    rows = pd.concat([day_rows(d) for d in days], ignore_index=True)
    days_used = sorted(rows.day.unique())
    half = days_used[len(days_used) // 2]
    print(f"{len(days_used)} days with books ({days_used[0]} .. {days_used[-1]}), split at {half}")
    out = []
    for dur in (5, 15):
        for L in LEFT_S:
            for lo, hi in BANDS:
                t = rows[(rows.dur_min == dur) & (rows.left_s == L) & rows.best_ask.between(lo, hi)]
                for part, x in (("all", t), ("first half", t[t.day < half]), ("second half", t[t.day >= half])):
                    if len(x) >= 20:
                        out.append({"dur": dur, "left_s": L, "band": f"{lo:.2f}-{hi:.2f}", "part": part, **score(x)})
    df = pd.DataFrame(out)
    pd.set_option("display.width", 200)
    print(df.round(4).to_string(index=False))
    df.to_csv(DATA / "research" / "crypto_endgame.csv", index=False)


if __name__ == "__main__":
    t = pd.DataFrame({"best_ask": [0.9, 0.9], "won": [1.0, 0.0], "end_ms": [0, 3_600_000]})
    s = score(t)
    assert abs(s["pnl/share"] - (0.1 - 0.9 - 2 * 0.07 * 0.09) / 2) < 1e-9 and s["n"] == 2
    main()
