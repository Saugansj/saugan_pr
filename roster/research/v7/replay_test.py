"""v7 test B (23 Oct): the archive replay (Bybit-fed, research.loop.nightly's wide rows and live entry rule) for v4, v6,
the 0.70 cap, v7 (fair-value skip + limit) and v7 with a volatility-scaled trigger.

  fit   in-sample archive (data/research/loop/wide_bybit, 27 Jul - 9 Aug): c by log-loss, m by total P&L at 500 ms,
        k (vol trigger) so its v4-rule trade count matches 6 bp's. Prints the values; nothing out of sample is read.
  oos   the 14 frozen days (data/research/oos/bybit), with the values fixed in reports/research/oos/
        prereg_addendum3_v7.md (FIXED below), at 500 ms (pre-registered) and 1000 ms.

S = the Bybit tick that fired, K = speed.StartPrice's 60 s TWAP before the window start, rv30 = the wide row's (the
same definition as speed.RealisedVol), tau = time left at the decision (left_ms - lag). Replay P&L is an upper bound:
top of book, 5 shares at the ask, no queue behind other bots.

    python -m research.v7.replay_test fit
    python -m research.v7.replay_test oos
"""
import datetime as dt
import math
import sys

import numpy as np
import pandas as pd

from common import DATA
from research.feeds.bybit_replay import ticks as bybit_ticks
from research.loop import nightly as N
from research.replay.replay import load_day
from research.v7 import fv_data as F
from trader.engines import speed

IS_DIR, OOS_DIR = DATA / "research" / "loop" / "wide_bybit", DATA / "research" / "oos" / "bybit"
IS_DAYS = (dt.date(2026, 7, 27), dt.date(2026, 8, 9))
CACHE = DATA / "research" / "v7"
M_GRID = np.round(np.arange(-0.10, 0.1001, 0.01), 2)
K_GRID = (3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 7.0, 8.0, 9.0, 10.0, 12.0)   # 7-12 added after 6.0 still gave 417 trades vs 261
FLOOR_BP = 4.0
LAGS = (500, 1000)
# The values written into prereg_addendum3_v7.md before the oos step ran (from `fit`; None until then).
FIXED = {"c": 1.3, "m": 0.07, "k": 8.0, "rv30_fallback": 5.65}


def days_in(d, first=None, last=None) -> list[dt.date]:
    out = sorted(dt.date.fromisoformat(p.stem) for p in d.glob("*.parquet"))
    return [x for x in out if (first is None or x >= first) and (last is None or x <= last)]


def day_ticks(day: dt.date) -> tuple[np.ndarray, np.ndarray]:
    t = pd.concat([bybit_ticks(day - dt.timedelta(days=1)), bybit_ticks(day)]).sort_values("ts_ms", kind="stable")
    return t.ts_ms.to_numpy(), t.price.to_numpy()


def add_sk(w: pd.DataFrame, ts, px) -> pd.DataFrame:
    """S at the signal tick and K of each row's window."""
    w = w.copy()
    s = {t: F.price_at(ts, px, int(t)) for t in w.t.unique()}
    starts = (w.t - w.since_ms).astype("int64")
    k = {b: F.start_k(ts, px, int(b)) for b in starts.unique()}
    w["S"], w["K"] = w.t.map(s), starts.map(k)
    w["lr"] = w.dir * np.log(w.S / w.K)
    return w


def load_wide(d, days) -> pd.DataFrame:
    """2 s / 6 bp rows at LAGS with S and K, cached per day."""
    out = []
    for day in days:
        c = CACHE / f"wide_{d.parent.name}_{d.name}" / f"{day}.parquet"
        if not c.exists():
            w = pd.read_parquet(d / f"{day}.parquet")
            w = w[(w.cfg == "2s/6bp") & w.lag.isin(LAGS)]
            c.parent.mkdir(parents=True, exist_ok=True)
            add_sk(w, *day_ticks(day)).to_parquet(c, index=False)
        out.append(pd.read_parquet(c))
    return pd.concat(out, ignore_index=True)


# ---------- vol-scaled trigger ----------

def rv30_per_second(ts: np.ndarray, px: np.ndarray, secs: np.ndarray) -> np.ndarray:
    """speed.RealisedVol.rv30 at each second's start (NaN without 30 min of history)."""
    marks = secs[:, None] * 1000 - np.arange(30, -1, -1)[None, :] * 60_000
    idx = np.searchsorted(ts, marks, "left") - 1
    r = np.diff(np.log(px[np.clip(idx, 0, None)]), axis=1)
    out = np.std(r, axis=1) * 1e4
    out[idx[:, 0] < 0] = np.nan
    return out


def vol_events(ts, px, d0: int, k: float) -> list[tuple]:
    """Signals of the 2 s detector with threshold max(FLOOR_BP, k sigma_2s), sigma_2s = rv30 sqrt(2/60); 6 bp while
    rv30 is unknown. Fed from 2 min before the day (history and cooldown)."""
    i0 = np.searchsorted(ts, d0 - 120_000)
    t, p = ts[i0:], px[i0:]
    secs = np.unique(t // 1000)
    rv = dict(zip(secs.tolist(), rv30_per_second(ts, px, secs).tolist()))
    det, out = speed.MoveDetector(2, 6.0, 60), []
    for a, b in zip(t.tolist(), p.tolist()):
        v = rv[a // 1000]
        h = det.update(a, b, 6.0 if v != v else max(FLOOR_BP, k * v * math.sqrt(2 / 60)))
        if h and d0 <= a < d0 + 86_400_000:
            out.append((a, h[0], h[1]))
    return out


def vol_wide(day: dt.date, k: float, ts=None, px=None, got=None) -> pd.DataFrame:
    """research.loop.nightly.wide's rows (LAGS only, no exit bids) for the vol-scaled detector, with S, K and rv30."""
    c = CACHE / "wide_vol" / f"k{k}" / f"{day}.parquet"
    if c.exists():
        return pd.read_parquet(c)
    if ts is None:
        ts, px = day_ticks(day)
    if got is None:
        got = load_day(day)
    _, cat, tob, _ = got
    d0 = int(dt.datetime.combine(day, dt.time(), dt.timezone.utc).timestamp() * 1000)
    cat, rows = cat[cat.winner.notna()], []
    for t, d, mbp in vol_events(ts, px, d0, k):
        rv = F.rv30(ts, px, t)
        for m in cat[(cat.start_ms <= t) & (cat.end_ms > t)].itertuples():
            tok = m.token_up if d > 0 else m.token_down
            base = dict(day=str(day), source="bybit-vol", cfg="2s/vol", t=t, dir=d, move_bp=round(mbp, 2), cid=m.cid,
                        dur=m.dur_min, left_ms=m.end_ms - t, since_ms=t - m.start_ms,
                        won=(m.winner == "up") == (d > 0), rv30=rv, bid8=np.nan, bid30=np.nan)
            for lag in LAGS:
                rows.append(dict(base, lag=lag, ask0=tob.at(tok, t + lag)[1], ask=tob.at(tok, t + lag + N.SEND)[1]))
    w = add_sk(pd.DataFrame(rows), ts, px) if rows else pd.DataFrame()
    c.parent.mkdir(parents=True, exist_ok=True)
    w.to_parquet(c, index=False)
    return w


# ---------- rules ----------

def with_fv(w: pd.DataFrame, c: float, fallback: float) -> pd.DataFrame:
    w = w.copy()
    tau = (w.left_ms - w.lag) / 1000
    rv = w.rv30.fillna(fallback)
    from scipy.stats import norm
    up = norm.cdf(np.log(w.S / w.K) / (c * rv / math.sqrt(60) * 1e-4 * np.sqrt(tau.clip(lower=0))))
    w["fv"] = np.where(w.dir > 0, up, 1 - up)
    return w


def rule_trades(w: pd.DataFrame, rule: str, lag: int, m: float = 0.0) -> pd.DataFrame:
    g = N.pnl(w[w.lag == lag])
    if rule == "v4":
        return N.trades(g, 0.85, 0.10, "none", "hold")
    if rule == "v6":
        return N.trades(g, 0.85, 0.10, "v6", "hold")
    if rule == "cap70":
        return N.trades(g, 0.70, 0.10, "none", "hold")
    if rule == "v7":
        p = {"fv_margin": m, "max_price": 0.85, "max_slip": 0.10}
        ok = g.ask0.notna() & g.ask.notna() & g.fv.notna()   # no K: no fair value, no trade
        lim = pd.Series([speed.fv_limit(f, a, p, 0.01) if o else None for f, a, o in zip(g.fv, g.ask0, ok)], index=g.index)
        g = g[lim.notna() & (g.ask <= lim.fillna(-1) + 1e-9)]
        return N.trades(g, 0.85, 0.10, "none", "hold")
    raise ValueError(rule)


def line(name: str, tr: pd.DataFrame) -> str:
    m, se, n = N.stat(tr)
    return f"| {name} | {m:+.3f} ± {se:.3f} | {n} | {tr.pnl.sum():+.1f} |"


def paired(a: pd.DataFrame, b: pd.DataFrame) -> str:
    """Total P&L of a minus b, per market, with SE = sd of the per-market differences x sqrt(markets)."""
    d = a.groupby("cid").pnl.sum().sub(b.groupby("cid").pnl.sum(), fill_value=0.0)
    return f"{d.sum():+.1f} ± {d.std(ddof=1) * math.sqrt(len(d)):.1f}"


def decision_rows(w: pd.DataFrame, lag: int = 500) -> pd.DataFrame:
    """One row per (signal, market) at the decision: the calibration sample (live in-window and time-left skips)."""
    g = w[(w.lag == lag) & (w.since_ms >= 2000) & (w.left_ms > 60_000) & w.ask0.notna() & w.K.notna()]
    return g.drop_duplicates(["t", "cid"])


def fit() -> int:
    w = load_wide(IS_DIR, days_in(IS_DIR, *IS_DAYS))
    fallback = float(w.drop_duplicates("t").rv30.median())
    cal = decision_rows(w)
    sd = np.array([F.sd1(r if r == r else None, (lm - 500) / 1000, fallback) for r, lm in zip(cal.rv30, cal.left_ms)])
    c, ll = F.fit_c(cal.lr.to_numpy(), sd, cal.won.astype(float).to_numpy())
    w = with_fv(w, c, fallback)
    L = [f"In-sample: {w.day.nunique()} days, {cal.shape[0]} decision rows. rv30 fallback {fallback:.2f} bp/min.",
         f"c = {c} (log-loss {ll:.4f}; seen ask {F.logloss(cal.ask0, cal.won.astype(float)):.4f})", "",
         "| m | v7 per trade ± SE | n | total |", "|---|---|---|---|"]
    tot = {}
    for m in M_GRID:
        tr = rule_trades(w, "v7", 500, float(m))
        tot[float(m)] = tr.pnl.sum()
        L.append(line(f"{m:+.2f}", tr))
    m_best = max(tot, key=tot.get)
    L += ["", f"m = {m_best:+.2f}", "", "| rule (500 ms) | per trade ± SE | n | total |", "|---|---|---|---|"]
    for r in ("v4", "v6", "cap70"):
        L.append(line(r, rule_trades(w, r, 500)))
    n6 = len(rule_trades(w, "v4", 500))
    L += ["", f"Vol trigger (floor {FLOOR_BP} bp): v4-rule trades at 500 ms vs 6 bp's {n6}", "",
          "| k | v4-rule n | v4 per trade ± SE | total | v7 per trade ± SE | v7 n | v7 total |", "|---|---|---|---|---|---|---|"]
    cnt = {}
    for day in days_in(IS_DIR, *IS_DAYS):
        ts, px = day_ticks(day)
        got = None
        for k in K_GRID:
            if not (CACHE / "wide_vol" / f"k{k}" / f"{day}.parquet").exists() and got is None:
                got = load_day(day)
            vol_wide(day, k, ts, px, got)
        print(day, "vol replay done", flush=True, file=sys.stderr)
    for k in K_GRID:
        v = with_fv(pd.concat([vol_wide(d, k) for d in days_in(IS_DIR, *IS_DAYS)], ignore_index=True), c, fallback)
        t4, t7 = rule_trades(v, "v4", 500), rule_trades(v, "v7", 500, m_best)
        cnt[k] = len(t4)
        a, b = N.stat(t4)[:2], N.stat(t7)
        L.append(f"| {k} | {len(t4)} | {a[0]:+.3f} ± {a[1]:.3f} | {t4.pnl.sum():+.1f} | {b[0]:+.3f} ± {b[1]:.3f} | {b[2]} | "
                 f"{t7.pnl.sum():+.1f} |")
    k_best = min(cnt, key=lambda k: abs(cnt[k] - n6))
    L += ["", f"k = {k_best} (trade count nearest 6 bp's)"]
    print("\n".join(L))
    return 0


def oos() -> int:
    if None in FIXED.values():
        raise SystemExit("write prereg_addendum3_v7.md and FIXED first")
    c, m, k, fb = FIXED["c"], FIXED["m"], FIXED["k"], FIXED["rv30_fallback"]
    days = days_in(OOS_DIR)
    w = with_fv(load_wide(OOS_DIR, days), c, fb)
    vol = with_fv(pd.concat([vol_wide(d, k) for d in days], ignore_index=True), c, fb)
    L = [f"OOS: {len(days)} days ({days[0]} .. {days[-1]}), Bybit-fed replay. c {c}, m {m:+.2f}, k {k}, rv30 fallback {fb}.", ""]
    for lag in LAGS:
        tr = {r: rule_trades(w, r, lag, m) for r in ("v4", "v6", "cap70", "v7")}
        tr["v7+vol"] = rule_trades(vol, "v7", lag, m)
        tr["v4+vol"] = rule_trades(vol, "v4", lag)
        L += [f"### Delay {lag} ms", "", "| rule | per trade ± SE | n | total |", "|---|---|---|---|"]
        L += [line(r, t) for r, t in tr.items()]
        L += ["", "Paired totals by market (a - b ± SE): " + "; ".join(
            f"{a} - {b} {paired(tr[a], tr[b])}" for a, b in (("v7", "v4"), ("v7", "v6"), ("cap70", "v4"),
                                                               ("v7+vol", "v7"), ("v7+vol", "v4"))), ""]
    cal = decision_rows(w)
    won = cal.won.astype(float)
    L += ["### Calibration (OOS decision rows at 500 ms)", "",
          f"Log-loss: FV {F.logloss(cal.fv, won):.4f}, seen ask {F.logloss(cal.ask0, won):.4f}, n {len(cal)}.", ""]
    L += F.reliability(cal.fv, won, "FV") + [""] + F.reliability(cal.ask0, won, "ask") + [""]
    L += ["| ask band | FV > ask: win rate (n) | mean ask | FV <= ask: win rate (n) | mean ask |", "|---|---|---|---|---|"]
    for lo, hi in ((0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.85), (0.85, 1.0)):
        g = cal[(cal.ask0 > lo) & (cal.ask0 <= hi)]
        a, b = g[g.fv > g.ask0], g[g.fv <= g.ask0]
        cell = lambda x: f"{x.won.mean():.2f} ({len(x)}) | {x.ask0.mean():.2f}" if len(x) else "- (0) | -"
        L.append(f"| ({lo}, {hi}] | {cell(a)} | {cell(b)} |")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit({"fit": fit, "oos": oos}[sys.argv[1]]())
