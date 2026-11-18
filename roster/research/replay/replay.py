"""btc-speed signal replay over history (research-layer plan R2 + R3). Read-only on data/history; no network.

For each UTC day: Binance BTCUSDT aggTrades -> the live detector (trader.engines.speed.MoveDetector: 10 bp in 5 s,
60 s cooldown) -> every open BTC 5m/15m Up/Down market (history/pm_fast catalog) -> a paper taker BUY of 5 shares of
the favoured side at the ask in force at arrival, then each exit rule. Rules are the grid of
  cap  (max entry price)              0.75, 0.90
  lag  (extra ms before arrival)      0, 1000, 2000, 5000   - what acting late costs (the live stale guard is 1 s)
  exit (hold, or sell at the bid N s after the fill)  hold, 5, 8, 15, 30, 60
Entry: the signal is seen `lag` ms late (the ask seen is the one at signal + lag); arrival = seen + 150 ms + RTT (200);
filled at the ask at arrival when the ask seen is within the cap and the ask at arrival is at most 2c above it (v2's
limit, rounded as live). Same-market rule: no new buy while a position in that market is open.
Exit: the SELL is sent N s after the fill and arrives 150 ms + RTT later; it fills at the bid then (both taker fees).
An exit due within 15 s of the end holds instead (as live v3).
Hold: 5 x (1 if the side won else 0) - cost - fee.
Regime features at the signal (data before it only): BTC log return over 5, 15 and 60 min signed by the signal's
direction, 30-min realised volatility of 1-min returns, and signals in the previous 30 min.

Limits: top of book only (no depth: 5 shares assumed available at the ask), the archive's receive clock, no queueing
behind other takers, no stale-book rule (a quote is the last change, however old). Days without all 24 archive hours
are skipped. The detector runs on aggTrades trade time T; live uses the stream's event time E (a few ms later).
Results are an upper bound on what a live fill gets. SE is clustered by market (cid), as the scorer.

    python -m research.replay.replay 2026-07-27 2026-08-09 [--rtt 200]
"""
import argparse
import bisect
import datetime as dt
import itertools
import math
import pathlib
import statistics

import numpy as np
import pandas as pd

from common import DATA, REPORTS
from nightly.scorer import cluster_se
from trader import fees
from trader.engines.speed import MoveDetector

H = DATA / "history"
OUT = DATA / "research" / "replay"
CAPS, LAGS, EXITS = (0.75, 0.90), (0, 1000, 2000, 5000), ("hold", 5, 8, 15, 30, 60)
SHARES, FEE_RATE, TAKER_DELAY_MS, SLIP, MIN_LEFT_MS, EXIT_MIN_LEFT_MS = 5.0, 0.07, 150, 0.02, 60_000, 15_000


def detect(ts: np.ndarray, px: np.ndarray) -> list[tuple[int, int, float]]:
    """[(ts_ms, direction, move_bp)] from the live detector, tick by tick."""
    det, out = MoveDetector(5, 10.0, 60), []
    for t, p in zip(ts.tolist(), px.tolist()):
        hit = det.update(t, p)
        if hit:
            out.append((t, hit[0], hit[1]))
    return out


class Tob:
    """Top of book per token: the last (bid, ask) at or before a time."""

    def __init__(self, df: pd.DataFrame):
        self.by = {k: (g.ts_ms.to_numpy(), g.best_bid.to_numpy(), g.best_ask.to_numpy())
                   for k, g in df.sort_values("ts_ms", kind="stable").groupby("asset_id")}

    def at(self, token: str, t: int) -> tuple[float | None, float | None]:
        g = self.by.get(token)
        if g is None:
            return None, None
        i = bisect.bisect_right(g[0], t) - 1
        if i < 0:
            return None, None
        b, a = g[1][i], g[2][i]
        return (None if np.isnan(b) else float(b)), (None if np.isnan(a) else float(a))


def features(ts: np.ndarray, px: np.ndarray, t: int, d: int, sig_times: list[int]) -> dict:
    """Regime features from ticks strictly before t."""
    i = bisect.bisect_left(ts, t) - 1
    if i < 0:
        return {}
    p = px[i]
    out = {}
    for m in (5, 15, 60):
        j = bisect.bisect_right(ts, t - m * 60_000) - 1
        out[f"ret{m}"] = d * math.log(p / px[j]) * 1e4 if j >= 0 else None   # bp, signed with the signal
    closes = [px[k] for k in (bisect.bisect_left(ts, t - s * 60_000) - 1 for s in range(30, -1, -1)) if k >= 0]  # < t
    r = np.diff(np.log(closes)) if len(closes) > 2 else []
    out["rv30"] = float(np.std(r) * 1e4) if len(r) > 1 else None             # bp per minute
    out["nsig30"] = sum(1 for s in sig_times if t - 30 * 60_000 <= s < t)
    return out


def load_day(day: dt.date, asset: str = "btc"):
    sym = f"{asset.upper()}USDT"
    agg = H / "binance" / sym / "aggTrades"
    parts = [pd.read_parquet(p) for p in (agg / f"{sym}-aggTrades-{day - dt.timedelta(days=1)}.parquet",
                                          agg / f"{sym}-aggTrades-{day}.parquet") if p.exists()]
    pm = H / "pm_fast" if asset == "btc" else H / "pm_fast" / asset   # as history.pm_fast.base
    cat_p = pm / "catalog" / f"{day}.parquet"
    tob_ps = sorted((pm / "tob").glob(f"{day}T*.parquet"))
    if not parts or not cat_p.exists() or len(tob_ps) < 24:  # a missing hour would leave old quotes in force
        return None
    ticks = pd.concat(parts).sort_values("ts_ms", kind="stable")
    return ticks, pd.read_parquet(cat_p), Tob(pd.concat(pd.read_parquet(p) for p in tob_ps)), len(tob_ps)


def replay_day(day: dt.date, rtt: int) -> pd.DataFrame:
    got = load_day(day)
    if got is None:
        return pd.DataFrame()
    ticks, cat, tob, _ = got
    return replay(ticks, cat, tob, day, rtt)


def replay(ticks: pd.DataFrame, cat: pd.DataFrame, tob: Tob, day: dt.date, rtt: int) -> pd.DataFrame:
    ts, px = ticks.ts_ms.to_numpy(), ticks.price.to_numpy()
    d0 = int(dt.datetime.combine(day, dt.time(), dt.timezone.utc).timestamp() * 1000)
    every = detect(ts, px)                         # includes the previous day's tail (features look back 30 min)
    sig_times = [e[0] for e in every]
    events = [e for e in every if d0 <= e[0] < d0 + 86_400_000]
    cat = cat[cat.winner.notna()]
    rows, open_until = [], {}
    for t, d, bp in events:
        f = features(ts, px, t, d, sig_times)
        live = cat[(cat.start_ms <= t - 5000) & (cat.end_ms - t > MIN_LEFT_MS)]   # open, move inside the window
        for m in live.itertuples():
            token = m.token_up if d > 0 else m.token_down
            won = (m.winner == "up") == (d > 0)
            for cap, lag in itertools.product(CAPS, LAGS):
                _, ask0 = tob.at(token, t + lag)
                arr = t + lag + TAKER_DELAY_MS + rtt
                _, ask = tob.at(token, arr)
                base = {"day": str(day), "t": t, "dir": d, "move_bp": round(bp, 2), "cid": m.cid, "dur": m.dur_min,
                        "cap": cap, "lag": lag, "won": won, "ask0": ask0, "ask": ask, **f}
                ok = ask is not None and ask0 is not None and ask0 <= cap and ask <= round(min(cap, ask0 + SLIP), 6) and ask < 1.0
                for ex in EXITS:
                    key = (m.cid, cap, lag, ex)
                    if not ok or open_until.get(key, -1) > t:
                        rows.append({**base, "exit": str(ex), "filled": False, "pnl": None, "exit_px": None})
                        continue
                    cost = SHARES * ask + fees.fee(SHARES, ask, FEE_RATE)
                    if ex == "hold" or m.end_ms - (arr + ex * 1000) <= EXIT_MIN_LEFT_MS:
                        pnl, xp, until = SHARES * (1.0 if won else 0.0) - cost, None, m.end_ms
                    else:
                        bid, _ = tob.at(token, arr + ex * 1000 + TAKER_DELAY_MS + rtt)
                        if bid is None or bid <= 0:
                            pnl, xp, until = SHARES * (1.0 if won else 0.0) - cost, None, m.end_ms  # no bid: hold
                        else:
                            pnl = SHARES * bid - fees.fee(SHARES, bid, FEE_RATE) - cost
                            xp, until = bid, arr + ex * 1000
                    open_until[key] = until
                    rows.append({**base, "exit": str(ex), "filled": True, "pnl": pnl, "exit_px": xp})
    return pd.DataFrame(rows)


def summarise(df: pd.DataFrame) -> str:
    f = df[df.filled]
    L = []
    days = sorted(df.day.unique())
    L += [f"# btc-speed replay: {days[0]} to {days[-1]} ({len(days)} days)", "",
          f"Signals {df.t.nunique()}; market-signals {df[['t', 'cid']].drop_duplicates().shape[0]}. "
          "Per trade: 5 shares, taker fees on every leg, P&L in USD. SE is cluster-robust by market.", "",
          "## Every rule", "", "| cap | lag ms | exit | trades | mean | SE | total | win % (held side) |",
          "|---|---|---|---|---|---|---|---|"]
    for (cap, lag, ex), g in f.groupby(["cap", "lag", "exit"], sort=True):
        xs = g.pnl.tolist()
        se = cluster_se(xs, g.cid.tolist())
        L.append(f"| {cap} | {lag} | {ex} | {len(xs)} | {statistics.fmean(xs):+.3f} | "
                 f"{'-' if se is None else f'{se:.3f}'} | {sum(xs):+.2f} | {100 * g.won.mean():.0f} |")
    base = f[(f.cap == 0.75) & (f.lag == 0)]
    L += ["", "## Hold vs exit by regime (cap 0.75, lag 0): mean P&L per trade", ""]
    for feat in ("ret15", "ret60", "rv30", "nsig30"):
        g = base.dropna(subset=[feat])
        if g.empty:
            continue
        q = g[feat].quantile([1 / 3, 2 / 3]).tolist()
        g = g.assign(bucket=np.where(g[feat] <= q[0], "low", np.where(g[feat] <= q[1], "mid", "high")))
        L += [f"**{feat}** (tercile cuts {q[0]:.1f}, {q[1]:.1f})", "", "| bucket | " + " | ".join(map(str, EXITS)) + " |",
              "|---|" + "---|" * len(EXITS)]
        for b in ("low", "mid", "high"):
            gb = g[g.bucket == b]
            cells = [f"{gb[gb.exit == str(e)].pnl.mean():+.3f} (n {len(gb[gb.exit == str(e)])})" for e in EXITS]
            L.append(f"| {b} | " + " | ".join(cells) + " |")
        L.append("")
    L += ["## By day (cap 0.75, lag 0)", "", "| day | trades | hold | exit 8 s |", "|---|---|---|---|"]
    for day, g in base.groupby("day"):
        h, e = g[g.exit == "hold"].pnl, g[g.exit == "8"].pnl
        L.append(f"| {day} | {len(h)} | {h.sum():+.2f} | {e.sum():+.2f} |")
    L += ["", "Limits: top of book only (5 shares assumed at the ask), archive receive clock, no queueing behind other "
          "takers: an upper bound on live fills."]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("first")
    ap.add_argument("last")
    ap.add_argument("--rtt", type=int, default=200)
    a = ap.parse_args(argv)
    day, last, parts = dt.date.fromisoformat(a.first), dt.date.fromisoformat(a.last), []
    while day <= last:
        df = replay_day(day, a.rtt)
        print(f"{day}: {df.t.nunique() if len(df) else 0} signals, {int(df.filled.sum()) if len(df) else 0} fills "
              f"over all rules", flush=True)
        if len(df):
            parts.append(df)
        day += dt.timedelta(days=1)
    if not parts:
        print("no data")
        return 1
    df = pd.concat(parts, ignore_index=True)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT / f"trades_{a.first}_{a.last}.parquet", index=False)
    rep = REPORTS / "research" / f"replay_{a.first}_{a.last}.md"
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text(summarise(df), encoding="utf-8")
    print("wrote", rep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
