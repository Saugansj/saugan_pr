"""v7 test A (23 Oct): the active taker runs' real trades re-priced under the v7 fair-value rule, the 0.70 cap and v6's
skips, on the real taker tape (nightly.scorer.tape_reprice with new limits, cache only: no tape download).

Per trade: S = the ref price logged with its signal (Bybit), K = speed.StartPrice's 60 s TWAP before the window start
and rv30 = speed.RealisedVol's, both from Bybit spot ticks (Binance 1 s klines on a day Bybit has not published),
tau = end - decision. A skipped trade counts 0. Fit (c, m) on the earlier half of the de-duplicated trades (one per
market per asset, the earliest), judge on the later half. Writes data/research/v7/live_trades.parquet and prints
markdown.

    python -m research.v7.live_test
"""
import datetime as dt
import math
import sys

import numpy as np
import pandas as pd

import common
from common import DATA
from nightly import scorer
from research.v7 import fv_data as F
from trader.engines import speed

TAKERS = {"BTC": ("paper_v4b", "paper_v5b", "paper_v6b"), "ETH": ("paper_ethb", "paper_eth6b")}
OUT = DATA / "research" / "v7"
M_GRID = np.round(np.arange(-0.10, 0.1001, 0.01), 2)   # first run had -0.03..0.10 and picked the edge, -0.03
ARCHIVE = {"c": 1.3, "m": 0.07}   # test B's in-sample fit (27 Jul - 9 Aug): out of sample on every live trade
TICK = 0.01


def load(run: str, asset: str) -> tuple[list, dict, pd.DataFrame]:
    d = DATA / "trader" / run
    t = scorer.tables(d)
    oc = scorer.outcomes(d, t, common.now_ms(), None)
    st = scorer.speed_stat(t.get("fills", []), oc)
    arr = {s["order_id"]: s["arrival_ms"] for s in t.get("speed_trades", []) if s.get("order_id")}
    lim = {o["order_id"]: o["price"] for o in t.get("orders", [])}
    srow = {s["order_id"]: s for s in t.get("speed_trades", []) if s.get("order_id")}
    ref = {e["decision_ms"]: e["ref_price"] for e in t.get("speed_events", []) if e.get("asset") == asset}
    trades = [x for x in st["trades"] if not x["maker"] and x["order_id"] in srow]
    rows = []
    for x in trades:
        s = srow[x["order_id"]]
        rows.append({"run": run, "asset": asset, "order_id": x["order_id"], "cid": x["cid"], "token": x["token_id"],
                     "decision_ms": s["decision_ms"], "end_ms": s["end_ms"], "dur": s["duration_min"], "dir": s["dir"],
                     "ask": s["ask"], "limit0": lim.get(x["order_id"], 1.0), "S": ref.get(s["decision_ms"]),
                     "won": float((oc.get(x["cid"]) or {}).get("winner") == x["token_id"])})
    return trades, arr, pd.DataFrame(rows)


def features(df: pd.DataFrame) -> pd.DataFrame:
    out = []
    for asset, g in df.groupby("asset"):
        days = {dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).date() + dt.timedelta(days=k)
                for t in g.decision_ms for k in (-1, 0)}
        bybit_ok = {d for d in days if (DATA / "history" / "bybit" / f"{asset}USDT" / f"{d}.parquet").exists()}
        late = {d for d in days if d >= dt.date(2026, 10, 22)}   # not published by Bybit yet: Binance 1 s klines
        ts, px = F.load_ticks(asset, bybit_ok | late, late)
        g = g.copy()
        g["start_ms"] = g.end_ms - g.dur * 60_000
        g["K"] = [F.start_k(ts, px, int(b)) for b in g.start_ms]
        g["rv30"] = [F.rv30(ts, px, int(t)) for t in g.decision_ms]
        g["src"] = ["binance1s" if dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).date() in late else "bybit"
                    for t in g.decision_ms]
        out.append(g)
    df = pd.concat(out, ignore_index=True)
    df["tau"] = (df.end_ms - df.decision_ms) / 1000
    df["lr"] = df.dir * np.log(df.S / df.K)
    return df


def v7_limits(df: pd.DataFrame, c: float, m: float, fallback: dict) -> tuple[pd.Series, pd.Series]:
    """(limit or 0 for a skip, FV of the favoured side) per trade."""
    p = {"fv_margin": m, "max_price": 0.85, "max_slip": 0.10}
    lim, fvs = [], []
    for r in df.itertuples():
        rv = r.rv30 if r.rv30 == r.rv30 and r.rv30 is not None else fallback[r.asset]
        fv_up = speed.fair_up(r.S, r.K, rv, r.tau, c)
        fv = fv_up if r.dir > 0 else 1 - fv_up
        fvs.append(fv)
        lim.append(speed.fv_limit(fv, r.ask, p, TICK) or 0.0)
    return pd.Series(lim, index=df.index), pd.Series(fvs, index=df.index)


def rule_limits(df: pd.DataFrame, rule: str) -> pd.Series:
    v4 = np.minimum(0.85, (df.ask + 0.10).round(6))
    if rule == "actual":
        return df.limit0
    if rule == "v4":
        return v4
    if rule == "v6":
        skip = ((df.ask > 0.30) & (df.ask <= 0.50)) | ((df.asset == "BTC") & (df.tau > 600))
        return v4.where(~skip, 0.0)
    if rule == "cap70":
        return np.minimum(0.70, (df.ask + 0.10).round(6)).where(df.ask <= 0.70, 0.0)
    raise ValueError(rule)


class Pricer:
    """live estimate per order id for a limits column, through scorer.tape_reprice per run (cache only)."""

    def __init__(self, runs: dict):
        self.runs = runs   # run -> (trades, arrival map)

    def live(self, df: pd.DataFrame, limits: pd.Series) -> pd.Series:
        out = {}
        for run, g in df.groupby("run"):
            trades, arr = self.runs[run]
            want = set(g.order_id)
            lim = dict(zip(g.order_id, limits.loc[g.index]))
            res = scorer.tape_reprice(DATA / "trader" / run, [t for t in trades if t["order_id"] in want], arr, None, lim)
            out.update({r["order_id"]: r["live"] for r in res["trades"]})
        return df.order_id.map(out)


def stat(x: pd.Series, cid: pd.Series, taken: pd.Series) -> str:
    """n taken, total, per taken trade +/- cluster SE (market)."""
    xs, gs = x[taken].tolist(), cid[taken].tolist()
    if not xs:
        return "0 | +0.00 | -"
    se = scorer.cluster_se(xs, gs)
    return f"{len(xs)} | {sum(xs):+.2f} | {np.mean(xs):+.3f} ± {'-' if se is None else f'{se:.3f}'}"


def diff(a: pd.Series, b: pd.Series, cid: pd.Series) -> str:
    """Total of a - b over the same trades, with the cluster SE of that total."""
    dd = (a - b).tolist()
    se = scorer.cluster_se(dd, cid.tolist())
    return f"{sum(dd):+.2f} ± {'-' if se is None else f'{se * len(dd):.2f}'}"


def main() -> int:
    frames, runs = [], {}
    for asset, names in TAKERS.items():
        for run in names:
            trades, arr, df = load(run, asset)
            runs[run] = (trades, arr)
            frames.append(df)
    df = features(pd.concat(frames, ignore_index=True))
    pr = Pricer(runs)
    df["live_actual"] = pr.live(df, rule_limits(df, "actual"))
    df = df[df.live_actual.notna() & df.S.notna() & df.K.notna()].reset_index(drop=True)   # repriced trades only
    first = df.sort_values(["decision_ms", "run"]).drop_duplicates(["asset", "cid"])
    df["dedup"] = df.order_id.isin(first.order_id)
    cut = int(df[df.dedup].decision_ms.median())
    df["half"] = np.where(df.decision_ms < cut, "fit", "test")
    fit = df[df.dedup & (df.half == "fit")]
    fallback = {a: float(g.rv30.median()) for a, g in fit.groupby("asset")}
    sd = np.array([F.sd1(r if r == r else None, t, fallback[a]) for r, t, a in zip(fit.rv30, fit.tau, fit.asset)])
    c, ll = F.fit_c(fit.lr.to_numpy(), sd, fit.won.to_numpy())
    per_asset_c = {a: F.fit_c(g.lr.to_numpy(), np.array([F.sd1(r if r == r else None, t, fallback[a])
                                                          for r, t in zip(g.rv30, g.tau)]), g.won.to_numpy())
                   for a, g in fit.groupby("asset")}
    for rule in ("v4", "v6", "cap70"):
        df[f"lim_{rule}"] = rule_limits(df, rule)
        df[f"live_{rule}"] = pr.live(df, df[f"lim_{rule}"])
    tot = {}
    for m in M_GRID:
        lim, _ = v7_limits(fit, c, m, fallback)
        tot[float(m)] = float(pr.live(fit, lim).sum())
    m_best = max(tot, key=tot.get)
    df["lim_v7"], df["fv"] = v7_limits(df, c, m_best, fallback)
    df["live_v7"] = pr.live(df, df.lim_v7)
    df["lim_v7a"], df["fv_a"] = v7_limits(df, ARCHIVE["c"], ARCHIVE["m"], fallback)
    df["live_v7a"] = pr.live(df, df.lim_v7a)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT / "live_trades.parquet", index=False)

    ist = lambda t: dt.datetime.fromtimestamp(t / 1000, dt.timezone(dt.timedelta(hours=5, minutes=30))).strftime("%d %b %H:%M")
    L = [f"Split at {ist(cut)} IST (median decision time of the de-duplicated trades). Trades repriced: {len(df)} "
         f"({df.dedup.sum()} de-duplicated). rv30 fallback (fit-half median, bp/min): " +
         ", ".join(f"{a} {v:.2f}" for a, v in fallback.items()) + f"; rv30 missing on {df.rv30.isna().sum()} trades.",
         f"Ticks: {(df.src == 'bybit').sum()} trades on Bybit ticks, {(df.src == 'binance1s').sum()} on Binance 1 s klines (22 Oct).",
         "", f"Fitted on the fit half (both coins pooled, de-duplicated, n {len(fit)}): **c = {c}** (log-loss {ll:.4f}; "
         f"per coin: " + ", ".join(f"{a} c {v[0]} ({v[1]:.4f})" for a, v in per_asset_c.items()) +
         f"), **m = {m_best:+.2f}** (fit-half live estimate by m: " + ", ".join(f"{k:+.2f}: {v:+.1f}" for k, v in tot.items()) + ").",
         "", "### Per run (each run's own trades; n = trades taken, per trade ± cluster SE by market)", "",
         "| run | half | actual | v6 skips | cap 0.70 | v7 | v7 archive params | v7 - actual (total ± SE) |", "|---|---|---|---|---|---|---|---|"]
    for run in sum(TAKERS.values(), ()):
        for half in ("fit", "test"):
            g = df[(df.run == run) & (df.half == half)]
            cells = [stat(g.live_actual, g.cid, g.live_actual.notna())]
            for rule in ("v6", "cap70", "v7", "v7a"):
                cells.append(stat(g[f"live_{rule}"], g.cid, g[f"lim_{rule}"] > 0))
            L.append(f"| {run} | {half} | " + " | ".join(cells) + f" | {diff(g.live_v7, g.live_actual, g.cid)} |")
    L += ["", "Cells: n | total | per trade ± SE.", "",
          "### De-duplicated (one trade per market per coin, the earliest of the runs)", "",
          "| coin | half | v4 rule | v6 rule | cap 0.70 | v7 | v7 archive params | v7 - v4 | v7 - v6 | v7a - v4 | v7a - v6 | cap70 - v4 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for asset in ("BTC", "ETH", "both"):
        for half in ("fit", "test"):
            g = df[df.dedup & (df.half == half) & ((df.asset == asset) if asset != "both" else True)]
            cells = [stat(g[f"live_{r}"], g.cid, g[f"lim_{r}"] > 0) for r in ("v4", "v6", "cap70", "v7", "v7a")]
            L.append(f"| {asset} | {half} | " + " | ".join(cells) + f" | {diff(g.live_v7, g.live_v4, g.cid)} | "
                     f"{diff(g.live_v7, g.live_v6, g.cid)} | {diff(g.live_v7a, g.live_v4, g.cid)} | "
                     f"{diff(g.live_v7a, g.live_v6, g.cid)} | {diff(g.live_cap70, g.live_v4, g.cid)} |")
    test = df[df.dedup & (df.half == "test")]
    L += ["", "### Calibration on the test half (de-duplicated trades)", "",
          f"Log-loss: FV {F.logloss(test.fv, test.won):.4f} (archive c {F.logloss(test.fv_a, test.won):.4f}), seen ask {F.logloss(test.ask, test.won):.4f}, "
          f"0.5 {F.logloss(np.full(len(test), 0.5), test.won):.4f} (n {len(test)}).", ""]
    L += F.reliability(test.fv, test.won, "FV") + [""] + F.reliability(test.ask, test.won, "ask") + [""]
    L += ["Within ask bands: win rate when FV is above the ask vs below it (does FV add information over the price?)", "",
          "| ask band | FV > ask: win rate (n) | mean ask | FV <= ask: win rate (n) | mean ask |", "|---|---|---|---|---|"]
    for lo, hi in ((0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.85)):
        g = test[(test.ask > lo) & (test.ask <= hi)]
        a, b = g[g.fv > g.ask], g[g.fv <= g.ask]
        cell = lambda x: f"{x.won.mean():.2f} ({len(x)}) | {x.ask.mean():.2f}" if len(x) else "- (0) | -"
        L.append(f"| ({lo}, {hi}] | {cell(a)} | {cell(b)} |")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
