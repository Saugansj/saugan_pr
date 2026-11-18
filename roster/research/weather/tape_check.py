"""Could the backtest's "first" entries have been bought? (23 Oct) For a random sample of entries, every data-api
trade of the bucket in [entry, entry + WINDOW_H]: a trade's NO-equivalent price is its price on the NO token, or
1 - price on the YES token. Filled if trades at or below our fill price (p + 1c) carry >= SHARES / (1 - RACE)
shares (we get the share left after the takers ahead of us, as nightly.scorer's RACE_AHEAD); filled at the VWAP of
those trades. Unfilled entries count 0.

  .venv\\Scripts\\python.exe -m research.weather.tape_check --n 300
"""
import argparse
import concurrent.futures as cf
import json

import numpy as np
import pandas as pd

import common
from common import DATA
from research.weather.backtest import FEE, cluster_se, fill

W = DATA / "research" / "weather"
WINDOW_H, SHARES, RACE = 3, 5, 0.31


def trades(cid: str) -> list[dict]:
    f = W / "trades" / f"{cid}.json"
    if f.exists():
        return json.loads(f.read_text())
    out, off = [], 0
    while True:
        page = common.get_json("https://data-api.polymarket.com/trades",
                               {"market": cid, "limit": 500, "offset": off, "takerOnly": "false"})
        out += page
        if len(page) < 500 or off >= 2500:   # shortcut: offset cap 3,000 (oldest trades of busy buckets missed)
            break
        off += 500
    f.write_text(json.dumps([{k: t[k] for k in ("asset", "side", "price", "size", "timestamp")} for t in out]))
    return out


def reprice(r, tr: list[dict]) -> tuple[bool, float | None, float]:
    t0 = (r.end_ms + r.h * 3.6e6) / 1000
    lim = float(fill(np.array([r.p]))[0])
    px, sz = [], []
    for t in tr:
        if t0 <= t["timestamp"] <= t0 + WINDOW_H * 3600:
            p = t["price"] if t["asset"] == r.no_token else 1 - t["price"]
            if p <= lim + 1e-9:
                px.append(p)
                sz.append(t["size"])
    avail = float(sum(sz))
    ok = avail >= SHARES / (1 - RACE)
    return ok, (float(np.average(px, weights=sz)) if ok else None), avail


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    a = ap.parse_args()
    (W / "trades").mkdir(exist_ok=True)
    e = pd.read_parquet(W / "entries.parquet")
    e = e[(e.rule == "first") & (e.band == "0.85-0.97")]
    s = pd.concat([e[e["tail"]].sample(min(a.n, int(e["tail"].sum())), random_state=7),
                   e[~e["tail"]].sample(a.n, random_state=7)])
    with cf.ThreadPoolExecutor(6) as pool:
        tr = dict(zip(s.cid, pool.map(trades, s.cid)))
    rows = []
    for r in s.itertuples():
        ok, vwap, avail = reprice(r, tr[r.cid])
        f = vwap if ok else None
        live = (float(r.won_no) - f - FEE * f * (1 - f)) if ok else 0.0
        ff = float(fill(np.array([r.p]))[0])
        rows.append({"tail": r.tail, "event": r.event, "filled": ok, "avail": avail, "paper": float(r.won_no) - ff - FEE * ff * (1 - ff),
                     "live": live, "won": r.won_no, "p": r.p, "vwap": vwap})
    d = pd.DataFrame(rows)
    d.to_csv(W / "tape_check.csv", index=False)
    for kind, x in (("tail", d[d["tail"]]), ("middle", d[~d["tail"]])):
        fx = x[x.filled]
        print(f"{kind:6} n {len(x)} | filled {100 * x.filled.mean():.0f}% | paper {x.paper.mean():+.4f}/sh | live {x.live.mean():+.4f}/sh "
              f"(SE {cluster_se(x.live.to_numpy(), x.event.to_numpy()):.4f}) | on filled: win {100 * fx.won.mean():.1f}% "
              f"at vwap {fx.vwap.mean():.3f} -> {fx.live.mean():+.4f}/sh | median shares at/below our price {x.avail.median():.0f}")


if __name__ == "__main__":
    main()
