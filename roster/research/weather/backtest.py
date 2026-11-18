"""Weather "buy NO at 85-97c, hold to resolution" (Reddit post, 23 Oct) on 40 days of settled Polymarket highest-
temperature markets (research.weather.pull). Rules fixed before looking:

- price: CLOB prices-history at 60 min (mid / last trade); we pay p + SLIP (1c over), capped at 0.99
- fee: 0.05 f (1 - f) per share (the markets' taker feeSchedule: rate 0.05, exponent 1)
- "first": the first hourly point with NO in [lo, hi] before the market's end; "at H": the last point at or before
  end + H hours, if in band
- tail = the open-ended buckets ("X or below" / "Y or higher"), the post's "extreme temperatures"
- SE clustered by city-day (buckets of one day settle together); halves split by date (first 20 days / last 20)

  .venv\\Scripts\\python.exe -m research.weather.backtest
"""
import datetime as dt
import json

import numpy as np
import pandas as pd

from common import DATA

W = DATA / "research" / "weather"
SLIP, FEE = 0.01, 0.05
BANDS = ((0.85, 0.97), (0.85, 0.90), (0.90, 0.95), (0.95, 0.97))
AT_H = (-48, -36, -24, -12, -6, 0, 6)


def fill(p: np.ndarray) -> np.ndarray:
    return np.minimum(p + SLIP, 0.99)


def pnl(won: np.ndarray, f: np.ndarray) -> np.ndarray:
    return won - f - FEE * f * (1 - f)


def cluster_se(x: np.ndarray, g: np.ndarray) -> float:
    s = pd.Series(x - x.mean()).groupby(g).sum()
    return float(np.sqrt((s ** 2).sum()) / len(x)) if len(x) > 1 else float("nan")


def entries(m: pd.DataFrame) -> pd.DataFrame:
    """One row per (bucket, rule, band) where the rule's entry price is in the band."""
    out = []
    for r in m.itertuples():
        h = json.loads((W / "prices" / f"{r.no_token}.json").read_text())
        if not h:
            continue
        t = np.array([x["t"] * 1000 for x in h]) - r.end_ms
        p = np.array([float(x["p"]) for x in h])
        for lo, hi in BANDS:
            band = f"{lo:.2f}-{hi:.2f}"
            ok = (t < 0) & (p >= lo) & (p <= hi)
            if ok.any():
                i = int(np.argmax(ok))
                out.append((r.Index, "first", band, p[i], t[i] / 3.6e6))
            for H in AT_H:
                j = np.searchsorted(t, H * 3.6e6, side="right") - 1
                if j >= 0 and lo <= p[j] <= hi and t[j] > H * 3.6e6 - 3 * 3.6e6:   # a point within 3 h of the time
                    out.append((r.Index, f"at {H:+d}h", band, p[j], t[j] / 3.6e6))
    e = pd.DataFrame(out, columns=["i", "rule", "band", "p", "h"]).set_index("i")
    return e.join(m)


def score(x: pd.DataFrame) -> dict:
    f = fill(x.p.to_numpy())
    v = pnl(x.won_no.to_numpy(float), f)
    return {"n": len(x), "win%": 100 * x.won_no.mean(), "need%": 100 * (f + FEE * f * (1 - f)).mean(),
            "pnl/sh": v.mean(), "se": cluster_se(v, x.event.to_numpy()), "roi%": 100 * v.sum() / f.sum(),
            "usd_5sh": 5 * v.sum()}


def main() -> None:
    m = pd.read_parquet(W / "markets.parquet").reset_index(drop=True)
    m["date"] = [dt.datetime.strptime(d, "%B-%d-%Y").date() for d in m.day]
    days = sorted(m.date.unique())
    half = days[len(days) // 2]
    e = entries(m)
    e.to_parquet(W / "entries.parquet")
    rows = []
    for (rule, band), g in e.groupby(["rule", "band"]):
        for kind, x in (("tail", g[g["tail"]]), ("middle", g[~g["tail"]]), ("all", g)):
            for part, y in (("all", x), ("1st half", x[x.date < half]), ("2nd half", x[x.date >= half])):
                if len(y) >= 30:
                    rows.append({"rule": rule, "band": band, "buckets": kind, "part": part, **score(y)})
    df = pd.DataFrame(rows)
    df.to_csv(W / "backtest.csv", index=False)
    pd.set_option("display.width", 220, "display.max_rows", 500)
    print(f"{len(m)} buckets, {m.event.nunique()} city-days, {days[0]} .. {days[-1]}, split at {half}")
    print(df[df.part == "all"].round(4).to_string(index=False))


if __name__ == "__main__":
    assert abs(pnl(np.array([1.0]), np.array([0.9]))[0] - (0.1 - 0.05 * 0.09)) < 1e-12
    main()
