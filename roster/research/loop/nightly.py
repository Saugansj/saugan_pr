"""Nightly research loop (9 Oct): each day the paper runs trade, it becomes replay data, and every candidate rule is
re-tested on days it was not chosen on. It writes a report and, when a challenger clearly beats a live rule, a draft
proposal. It never changes a trader, a flag or a run: a person reads the proposal and pre-registers a new paper run.

For a UTC day D (default: yesterday):
  1. ingest   Binance BTCUSDT aggTrades for D-1 and D (history.binance), the BTC 5m/15m catalog with winners
              (history.pm_fast), and D's top of book from paper_v3's own recorder (record_tob) -> data/research/loop/tob.
  2. wide     every signal of every detector in DETS x every open market x LAGS, no skip rule applied: raw asks and
              bids only -> data/research/loop/wide/<D>.parquet. Hours without the recording (and the hour after a
              gap) are left out. The 27 Jul-9 Aug archive days were written by `--backfill` from history/pm_fast.
  3. grid     RULES (detector x cap x slippage x filter x exit) under the live entry rule (ask <= min(cap, ask seen +
              slip), one position per market), leave-one-day-out over every wide day: out-of-sample P&L per rule.
  4. live     each paper run's btc-speed events on D: what the skipped ones would have made held (missed money by
              reason), and the replay vs live gap for its filled trades (price and P&L).
  5. report   reports/research/loop/<D>.md; reports/research/loop/proposals/<D>.md when a challenger beats a live
              rule by more than 2 SE out of sample over at least MIN_N trades.

13 Oct additions: (#5) each day is also replayed on Bybit spot trades (data/research/loop[/eth]/wide_bybit), and
runs fed by Bybit (BYBIT_RUNS) are compared with that replay; (#4) the price gap between live fills and the replay is
kept for every delay in LAGS (gaps.parquet) and, unless --lag is given, the report uses the delay whose mean gap is
nearest zero once MIN_GAP_N fills exist; (#7) a weekly table splits v4/v5 into signal (replay at 0 ms), our delay
(replay at the matched delay) and live paper results, so a fading edge shows whether the market or our speed moved.

Limits: a replay is an upper bound (top of book only, 5 shares assumed at the ask, no queue behind other bots). Live
days are on this PC's clock, which drifts from Binance's by up to about 0.7 s; step 4's gap is how much to trust it.

    python -m research.loop.nightly [--day YYYY-MM-DD] [--lag 500] [--asset eth]
    python -m research.loop.nightly --backfill 2026-07-27 2026-08-09   # archive days, once

ETH (10 Oct, --asset eth): the same loop for v4's rule on ETH (paper_eth, which records its own top of book) under
data/research/loop/eth and reports/research/loop/eth. It starts with live days only; archive days need
`python -m history.pm_fast FIRST LAST --asset eth` plus ETHUSDT aggTrades, then `--backfill ... --asset eth`.
"""
import argparse
import bisect
import datetime as dt
import gzip
import io
import itertools
import json
import sqlite3

import numpy as np
import pandas as pd

from common import DATA, REPORTS
from nightly.scorer import cluster_se
from research.replay.replay import Tob, features, load_day
from trader.engines import speed

OUT = DATA / "research" / "loop"
REP = REPORTS / "research" / "loop"
RUNS = ("paper14", "paper_v3", "paper_v4", "paper_v4b", "paper_v5", "paper_v5b", "paper_v6b", "paper_v7b")
DETS = ((5, 10), (5, 8), (3, 8), (3, 10), (2, 6), (5, 12))      # (window s, bp)
LAGS = (0, 200, 500, 1000)
SEND, SH, FEE = 350, 5.0, 0.07                                  # 150 ms taker delay + 200 ms RTT, as the replay
CAPS, SLIPS = (0.65, 0.75, 0.85), (0.02, 0.05, 0.10)
FILTS, EXITS = ("none", "quiet30", "5m"), ("x8", "x30", "hold")
MIN_N = 100
MIN_GAP_N = 30                                                  # live fills needed before the matched delay is used
BYBIT_RUNS = {"paper_v4b", "paper_v5b", "paper_v6b", "paper_ethb", "paper_ethc", "paper_eth6b", "paper_v7b", "paper_eth7b"}            # runs with the ref_bybit flag
LIVE = {"v2": ("5s/10bp", 0.90, 0.02, "none", "hold"), "v3": ("5s/10bp", 0.75, 0.02, "none", "x8"),
        "v4": ("2s/6bp", 0.85, 0.10, "none", "hold"),
        "v5": ("2s/6bp", 0.85, 0.10, "calm55", "hold"),
        "v6": ("2s/6bp", 0.85, 0.10, "v6", "hold")}           # the pre-registered live rules, in grid terms
RUN_CFG = {"paper14": "5s/10bp", "paper_v3": "5s/10bp", "paper_v4": "2s/6bp", "paper_v5": "2s/6bp", "paper_v5b": "2s/6bp", "paper_v4b": "2s/6bp",
           "paper_ethb": "2s/6bp", "paper_ethc": "2s/6bp", "paper_v6b": "2s/6bp", "paper_eth6b": "2s/6bp",
           "paper_v7b": "2s/6bp", "paper_eth7b": "2s/6bp",
           "paper_eth": "2s/6bp"}
# per coin: Binance symbol, live rules, paper runs, the run whose record_tob is the replay's book, output subfolder
ASSETS = {"btc": ("BTCUSDT", LIVE, RUNS, ("paper_v3", "paper_v6b"), ""),   # v3 recorded BTC until 14 Oct, then v6b
          "eth": ("ETHUSDT", {"v4-eth": LIVE["v4"], "v6-eth": ("2s/6bp", 0.85, 0.10, "v6eth", "hold")},
                  ("paper_eth", "paper_ethb", "paper_ethc", "paper_eth6b"), "paper_ethb", "eth")}  # ethb records
fee = lambda p: SH * FEE * p * (1 - p)


# ---------- 1. ingest ----------

def live_tob(day: dt.date, run: str | tuple = "paper_v3") -> pd.DataFrame:
    """D's recorded top-of-book changes (every pid file of each hour, and D-1's last hour for the quotes in force at
    midnight), in the archive's columns. run: one recorder, or several read together (BTC: paper_v3 until 14 Oct, then
    paper_v6b; on the handover day both views interleave)."""
    parts = []
    for p in [p for r in ((run,) if isinstance(run, str) else run) for p in
              sorted((DATA / "trader" / r / "tob").glob(f"{day - dt.timedelta(days=1)}T23*")) +
              sorted((DATA / "trader" / r / "tob").glob(f"{day}T*"))]:
        raw = gzip.decompress(p.read_bytes()) if p.suffix == ".gz" else p.read_bytes()
        if raw.strip():
            parts.append(pd.read_csv(io.BytesIO(raw), header=None, names=["ts_ms", "asset_id", "best_bid", "best_ask"],
                                     dtype={"asset_id": str}))
    return pd.concat(parts, ignore_index=True).sort_values("ts_ms", kind="stable") if parts else pd.DataFrame()


def ingest(day: dt.date, asset: str = "btc"):
    from history import binance, pm_fast
    sym, _, _, tob_run, _ = ASSETS[asset]
    got = binance.download_agg([sym], day - dt.timedelta(days=1), day)
    if got["not_published"] or got["checksum_failed"]:
        raise RuntimeError(f"Binance aggTrades not ready: {got}")
    cat = pm_fast.catalog(day, 8, pm_fast.Rate(8), asset)
    tob = live_tob(day, tob_run)
    agg = DATA / "history" / "binance" / sym / "aggTrades"
    ticks = pd.concat(pd.read_parquet(agg / f"{sym}-aggTrades-{d}.parquet")
                      for d in (day - dt.timedelta(days=1), day)).sort_values("ts_ms", kind="stable")
    d0 = int(dt.datetime.combine(day, dt.time(), dt.timezone.utc).timestamp() * 1000)
    hours = set(((tob.ts_ms - d0) // 3_600_000).tolist()) if len(tob) else set()
    ok = {h for h in range(24) if h in hours and h - 1 in hours}   # quotes in force at h need the hour before
    return ticks, cat, Tob(tob) if len(tob) else None, ok


def bybit_wide(day: dt.date, symbol: str, cat, tob, hours=None) -> pd.DataFrame:
    """#5: the same wide replay driven by Bybit spot trades (the feed of BYBIT_RUNS)."""
    from research.feeds.bybit_replay import ticks as bybit_ticks
    t = pd.concat([bybit_ticks(day - dt.timedelta(days=1), "spot", symbol), bybit_ticks(day, "spot", symbol)])
    return wide(t.sort_values("ts_ms", kind="stable"), cat, tob, day, hours, source="bybit")


# ---------- 2. wide replay ----------

def wide(ticks: pd.DataFrame, cat: pd.DataFrame, tob: Tob, day: dt.date, hours=None, source="live") -> pd.DataFrame:
    ts, px = ticks.ts_ms.to_numpy(), ticks.price.to_numpy()
    d0 = int(dt.datetime.combine(day, dt.time(), dt.timezone.utc).timestamp() * 1000)
    cat, rows = cat[cat.winner.notna()], []
    for w, bp in DETS:
        det, ev = speed.MoveDetector(w, float(bp), 60), []
        for t, p in zip(ts.tolist(), px.tolist()):
            h = det.update(t, p)
            if h:
                ev.append((t, h[0], h[1]))
        st = [e[0] for e in ev]
        for t, d, mbp in ev:
            if not d0 <= t < d0 + 86_400_000 or hours is not None and (t - d0) // 3_600_000 not in hours:
                continue
            f = features(ts, px, t, d, st)
            for m in cat[(cat.start_ms <= t) & (cat.end_ms > t)].itertuples():
                tok = m.token_up if d > 0 else m.token_down
                base = dict(day=str(day), source=source, cfg=f"{w}s/{bp}bp", t=t, dir=d, move_bp=round(mbp, 2),
                            cid=m.cid, dur=m.dur_min, left_ms=m.end_ms - t, since_ms=t - m.start_ms,
                            won=(m.winner == "up") == (d > 0), **f)
                for lag in LAGS:
                    arr = t + lag + SEND
                    rows.append(dict(base, lag=lag, ask0=tob.at(tok, t + lag)[1], ask=tob.at(tok, arr)[1],
                                     bid8=tob.at(tok, arr + 8000 + SEND)[0], bid30=tob.at(tok, arr + 30_000 + SEND)[0]))
    return pd.DataFrame(rows)


# ---------- 3. grid ----------

def pnl(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["hold"] = SH * df.won - SH * df.ask - fee(df.ask)
    for x in (8, 30):
        b = df[f"bid{x}"]
        df[f"x{x}"] = np.where(b.notna() & (b > 0), SH * b - fee(b.fillna(0)) - SH * df.ask - fee(df.ask), df.hold)
    return df


def trades(g: pd.DataFrame, cap, slip, filt, ex) -> pd.DataFrame:
    """The live entry rule (speed.SpeedEngine._act): ask seen <= cap, fill at the arrival ask <= min(cap, seen + slip);
    the live in-window and 60 s-left skips; one open position per market."""
    g = g.reset_index(drop=True)   # days concatenated keep their own row numbers; .loc below needs unique ones
    win = g.cfg.str.split("s/").str[0].astype(int) * 1000
    g = g[(g.since_ms >= win) & (g.left_ms > 60_000) & g.ask0.notna() & g.ask.notna() & (g.ask0 <= cap)
          & (g.ask <= np.minimum(cap, (g.ask0 + slip).round(6))) & (g.ask < 1)]
    if filt == "quiet30":
        g = g[g.nsig30 == 0]
    elif filt == "5m":
        g = g[g.dur == 5]
    elif filt == "calm55":   # v5's live filter (speed.PARAMS_V5); a live rule only, not in the FILTS search
        g = g[g.rv30 < 5.5]
    elif filt in ("v6", "v6eth"):   # v6's skips on the ask seen (speed.PARAMS_V6_*); live rules only
        g = g[~((g.ask0 > 0.30) & (g.ask0 <= 0.50))]
        if filt == "v6":
            g = g[g.left_ms <= 600_000]
    keep, busy = [], {}
    for r in g.sort_values("t").itertuples():
        if busy.get(r.cid, -1) > r.t:
            continue
        busy[r.cid] = r.t + r.left_ms if ex == "hold" else r.t + r.lag + 2 * SEND + int(ex[1:]) * 1000
        keep.append(r.Index)
    return g.loc[keep, ["day", "t", "cid", ex]].rename(columns={ex: "pnl"})


def grid(w: pd.DataFrame, lag: int, live_rules: dict = LIVE):
    """{rule: trades} for every rule, and the leave-one-day-out out-of-sample trades of the selection itself."""
    w = pnl(w[w.lag == lag])
    rules = list(itertools.product(sorted(w.cfg.unique()), CAPS, SLIPS, FILTS, EXITS)) + list(live_rules.values())
    res = {r: trades(w[w.cfg == r[0]], *r[1:]) for r in dict.fromkeys(rules)}
    days, oos, picks = sorted(w.day.unique()), [], []
    for d in days:
        best = max(res, key=lambda r: res[r][res[r].day != d].pnl.sum())
        picks.append(best)
        oos.append(res[best][res[best].day == d])
    return res, pd.concat(oos), picks


def stat(v: pd.DataFrame) -> tuple[float, float, int]:
    if len(v) < 3:
        return float("nan"), float("nan"), len(v)
    return v.pnl.mean(), cluster_se(v.pnl.tolist(), v.cid.tolist()), len(v)


# ---------- 4. live: missed money and the replay gap ----------

def live_day(run: str, day: dt.date, w: pd.DataFrame, lag: int, wb: pd.DataFrame | None = None) -> dict | None:
    """w: the Binance replay; wb: the Bybit replay, used for runs in BYBIT_RUNS (#5)."""
    if run in BYBIT_RUNS:
        w = wb if wb is not None else w.iloc[:0]
    db = DATA / "trader" / run / "trader.db"
    if not db.exists() or w.empty:
        return None
    con = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)
    try:
        d0 = int(dt.datetime.combine(day, dt.time(), dt.timezone.utc).timestamp() * 1000)
        q = "SELECT body FROM rows WHERE tbl = ? AND event_ms >= ? AND event_ms < ?"
        evs = [json.loads(b) for (b,) in con.execute(q, ("speed_events", d0, d0 + 86_400_000))]
        fills = [json.loads(b) for (b,) in con.execute(q, ("fills", d0, d0 + 86_400_000))]
    finally:
        con.close()
    g = pnl(w[(w.cfg == RUN_CFG[run]) & (w.lag == lag)])
    if g.empty:
        return None
    ts = g.t.to_numpy()
    order = np.argsort(ts, kind="stable")
    missed, matched = {}, 0
    for e in evs:
        i = bisect.bisect_left(ts[order], e["binance_ms"] - 1500)
        near = g.iloc[order[i:bisect.bisect_right(ts[order], e["binance_ms"] + 1500)]]
        matched += not near.empty
        for cid, why in e["markets"].items():
            r = near[near.cid == cid]
            if why != "trade" and len(r) and pd.notna(r.hold.iloc[0]):
                m = missed.setdefault(why, [0, 0.0])
                m[0], m[1] = m[0] + 1, m[1] + r.hold.iloc[0]
    buys = [f for f in fills if f.get("strategy") == speed.NAME and f.get("side") == "BUY"]
    gaps = {L: fill_gaps(buys, w[(w.cfg == RUN_CFG[run]) & (w.lag == L)]) for L in LAGS}   # #4: every delay
    gap = gaps[lag]
    return {"events": len(evs), "matched": matched, "missed": missed, "buys": len(buys),
            "price_gap_c": 100 * float(np.mean(gap)) if gap else None, "gap_n": len(gap), "gaps": gaps}


def fill_gaps(buys: list, g: pd.DataFrame) -> list[float]:
    """Live fill price minus the replay's arrival ask for the same market within 5 s, one per fill."""
    out = []
    for f in buys:
        r = g[(g.cid == f["cid"]) & (abs(g.t - f["ts_ms"]) < 5000)]
        if len(r) and pd.notna(r.ask.iloc[0]):
            out.append(f["price"] - r.ask.iloc[0])
    return out


def matched_lag(rows: pd.DataFrame, default: int) -> tuple[int, dict]:
    """#4: the delay in LAGS whose mean live-minus-replay gap is nearest zero, once MIN_GAP_N fills exist, and only if
    it beats the default's gap by more than one SE of that gap (13 Oct: gaps of -0.8c vs -0.6c on 12 fills moved the
    whole report to 1000 ms on noise)."""
    by = {L: (g.gap.mean(), len(g)) for L, g in rows.groupby("lag")} if len(rows) else {}
    ok = {L: m for L, (m, n) in by.items() if n >= MIN_GAP_N}
    if not ok or default not in ok:
        return default, by
    best = min(ok, key=lambda L: abs(ok[L]))
    d = rows[rows.lag == default].gap
    se = d.std(ddof=1) / len(d) ** 0.5 if len(d) > 1 else float("inf")
    return (best if abs(ok[default]) - abs(ok[best]) > se else default), by


def save_gaps(path, day: dt.date, live: dict) -> pd.DataFrame:
    """Append this day's gaps (replacing any earlier rows for the same day) and return every day's."""
    new = pd.DataFrame([{"day": str(day), "run": run, "lag": L, "gap": x} for run, v in live.items() if v
                        for L, xs in v["gaps"].items() for x in xs], columns=["day", "run", "lag", "gap"])
    old = pd.read_parquet(path) if path.exists() else new.iloc[:0]
    allg = pd.concat([old[old.day != str(day)], new], ignore_index=True)
    allg.to_parquet(path, index=False)
    return allg


def week_end_ms(iso_week: str) -> int:
    """End (exclusive, UTC ms) of an ISO week like "2026-W41": the next Monday 00:00."""
    monday = pd.to_datetime(iso_week + "-1", format="%G-W%V-%u").tz_localize("UTC")
    return int((monday + pd.Timedelta(days=7)).timestamp() * 1000)


def weekly(w_all: pd.DataFrame, lag: int, run_dirs: dict) -> list[str]:
    """#7: per ISO week, v4/v5 per trade as signal (0 ms), at our matched delay, and live paper (Bybit runs)."""
    from nightly.scorer import score
    L = ["## Signal vs execution, weekly (Bybit replay; live = the Bybit paper run)", "",
         f"| week | v5 signal (0 ms) | v5 at {lag} ms | v5 live | v4 signal (0 ms) | v4 at {lag} ms | v4 live |",
         "|---|---|---|---|---|---|---|"]
    if w_all.empty:
        return L + ["| - | no Bybit replay days yet | | | | | |", ""]
    wk = pd.to_datetime(w_all.day).dt.strftime("%G-W%V")
    cum = {}
    for name, run in run_dirs.items():   # live: cumulative pre-registered statistic at each week's end
        d = DATA / "trader" / run
        cum[name] = {} if not (d / "trader.db").exists() else {
            k: score(d, 0, week_end_ms(k))["speed"] for k in sorted(set(wk))}
    cell = lambda t: "-" if len(t) < 1 else f"{t.pnl.mean():+.2f} ({len(t)})"
    prev = {n: (0.0, 0) for n in run_dirs}
    for k in sorted(set(wk)):
        g, row = w_all[wk == k], [k]
        for name, rule in (("v5", LIVE["v5"]), ("v4", LIVE["v4"])):
            for L_ in (0, lag):
                h = pnl(g[(g.lag == L_) & (g.cfg == rule[0])])
                row.append(cell(trades(h, *rule[1:])))
            sp = cum.get(name, {}).get(k)
            if sp and sp["n"] > prev[name][1]:
                row.append(f"{(sp['total'] - prev[name][0]) / (sp['n'] - prev[name][1]):+.2f} ({sp['n'] - prev[name][1]})")
                prev[name] = (sp["total"], sp["n"])
            else:
                row.append("-")
        L.append("| " + " | ".join(row) + " |")
    return L + ["", "Signal falling week after week: the market is crowding the edge out. Only the gaps to it growing: "
                "our delay or competition at the ask.", ""]


# ---------- 5. report ----------

def overfit_lines(res: dict, days: list, live_rules: dict, top) -> list[str]:
    """16 Oct: how much of the in-sample result the search itself explains (research/loop/overfit.py)."""
    from research.loop import overfit
    daily = pd.DataFrame({r: t.groupby("day").pnl.sum() for r, t in res.items()}).reindex(days).fillna(0.0)
    srs = [overfit.sharpe(daily[r]) for r in daily if len(res[r]) >= 3]
    var_sr = float(np.nanvar(srs)) if srs else float("nan")
    n_rules = daily.shape[1]
    L = [f"## Overfitting checks ({n_rules} rules searched, per-day P&L over {len(days)} days)", "",
         f"- Probability of backtest overfitting (picking the in-sample best): **{overfit.pbo(daily.to_numpy()):.2f}** "
         "(above 0.50: the pick is worse than a random rule out of sample).", "",
         "| rule | daily Sharpe | deflated Sharpe (vs the best of all rules by luck) |", "|---|---|---|"]
    for name, r in [*((f"live {k}", v) for k, v in live_rules.items()), ("best in sample", top)]:
        L.append(f"| {name} | {overfit.sharpe(daily[r]):+.2f} | {overfit.dsr(daily[r], n_rules, var_sr):.2f} |")
    return L + ["", "Deflated Sharpe above 0.95 = the edge survives the search that found it. It is exact for the "
                "best-in-sample row and conservative for the live rules (they were pre-registered, not picked here).", ""]


def report(day: dt.date, lag: int, w_all: pd.DataFrame, live: dict, live_rules: dict = LIVE, coin: str = "BTC",
           wb_all: pd.DataFrame | None = None, lag_note: str = "", weekly_lines: list | None = None):
    res, oos, picks = grid(w_all, lag, live_rules)
    days = sorted(w_all.day.unique())
    L = [f"# Research loop{'' if coin == 'BTC' else ' ' + coin}: {day} (replay delay {lag} ms, {len(days)} days: "
         f"{days[0]} .. {days[-1]})", "",
         "Replay P&L is an upper bound: top of book, 5 shares assumed at the ask, no queue behind other bots.", "",
         "## Live rules vs the best challenger (all days in sample; the challenger also out of sample)", "",
         "| rule | detector | cap | slip | filter | exit | per trade ± SE | n | total |", "|---|---|---|---|---|---|---|---|---|"]
    for name, r in live_rules.items():
        m, se, n = stat(res[r])
        L.append(f"| live {name} | {' | '.join(map(str, r))} | {m:+.3f} ± {se:.3f} | {n} | {res[r].pnl.sum():+.1f} |")
    top = max(res, key=lambda r: res[r].pnl.sum())
    m, se, n = stat(res[top])
    L.append(f"| best in sample | {' | '.join(map(str, top))} | {m:+.3f} ± {se:.3f} | {n} | {res[top].pnl.sum():+.1f} |")
    m, se, n = stat(oos)
    L += [f"| **selection, out of sample** | (picked per held-out day) | | | | | {m:+.3f} ± {se:.3f} | {n} | "
          f"{oos.pnl.sum():+.1f} |", "",
          "Picks across folds: " + ", ".join(f"{k} x{c}" for k, c in
                                             pd.Series([" ".join(map(str, p)) for p in picks]).value_counts().items()),
          ""]
    L += overfit_lines(res, days, live_rules, top)
    if lag_note:
        L += [lag_note, ""]
    if wb_all is not None and len(wb_all):
        L += [f"## Live rules on the Bybit replay ({wb_all.day.nunique()} days)", "", "| rule | per trade ± SE | n | total |",
              "|---|---|---|---|"]
        for name, r in live_rules.items():
            t = trades(pnl(wb_all[(wb_all.lag == lag) & (wb_all.cfg == r[0])]), *r[1:])
            m, se, n = stat(t)
            L.append(f"| {name} | {m:+.3f} ± {se:.3f} | {n} | {t.pnl.sum():+.1f} |")
        L.append("")
    L += ["## Live runs on this day", "", "| run | events | matched in replay | buys | price paid vs replay ask | "
          "missed (held, by skip reason) |", "|---|---|---|---|---|---|"]
    for run, v in live.items():
        if v is None:
            L.append(f"| {run} | no data | | | | |")
            continue
        miss = "; ".join(f"{k} {n} = {s:+.2f}" for k, (n, s) in sorted(v["missed"].items(), key=lambda x: x[1][1]))
        gap = "-" if v["price_gap_c"] is None else f"{v['price_gap_c']:+.1f}c (n {v['gap_n']})"
        L.append(f"| {run} | {v['events']} | {v['matched']} | {v['buys']} | {gap} | {miss or '-'} |")
    L += ["", "A large price gap or few matched events means the replay is not describing live trading: fix that "
              "before trusting any proposal.", ""] + (weekly_lines or [])
    return "\n".join(L) + "\n", res, oos, picks


def proposal(day: dt.date, res: dict, oos: pd.DataFrame, picks: list, live_rules: dict = LIVE) -> str | None:
    """A challenger picked in most folds, beating every live rule per trade by > 2 SE out of sample, n >= MIN_N."""
    best = pd.Series([" ".join(map(str, p)) for p in picks]).value_counts()
    if best.iloc[0] < 0.6 * len(picks):
        return None
    rule = picks[[" ".join(map(str, p)) for p in picks].index(best.index[0])]
    if rule in live_rules.values():
        return None
    m, se, n = stat(oos)   # the selection's own out-of-sample trades
    # shortcut: compares against each live rule as if independent (they share signals), so the 2 SE bar is rough;
    # a paired test by signal is the upgrade once a proposal is close.
    beats = all(m - stat(res[r])[0] > 2 * np.hypot(se, stat(res[r])[1]) for r in live_rules.values())
    if n < MIN_N or not beats:
        return None
    return (f"# Proposal {day}: btc-speed rule {' '.join(map(str, rule))}\n\nOut of sample {m:+.3f} ± {se:.3f} USD per "
            f"trade over {n} trades; picked in {best.iloc[0]} of {len(picks)} folds; beats every live rule by > 2 SE.\n\n"
            "Next, by a person: re-check it in the system backtest (research/backtest/system.py), write its "
            "pre-registration in trader/engines/speed.py, and start it as its own paper run. Nothing was changed.\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--day", type=dt.date.fromisoformat, default=dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1))
    ap.add_argument("--lag", type=int, default=None, help="extra replay delay in ms (default: matched to live fills, else 500)")
    ap.add_argument("--backfill", nargs=2, type=dt.date.fromisoformat, metavar=("FIRST", "LAST"))
    ap.add_argument("--asset", choices=tuple(ASSETS), default="btc")
    a = ap.parse_args(argv)
    _, live_rules, runs, _, sub = ASSETS[a.asset]
    out, rep = OUT / sub, REP / sub
    (out / "wide").mkdir(parents=True, exist_ok=True)
    (out / "wide_bybit").mkdir(parents=True, exist_ok=True)
    sym = ASSETS[a.asset][0]
    if a.backfill:
        d = a.backfill[0]
        while d <= a.backfill[1]:
            got = load_day(d, a.asset)
            if got:
                if not (out / "wide" / f"{d}.parquet").exists():
                    wide(got[0], got[1], got[2], d, source="archive").to_parquet(out / "wide" / f"{d}.parquet", index=False)
                if not (out / "wide_bybit" / f"{d}.parquet").exists():
                    bybit_wide(d, sym, got[1], got[2]).to_parquet(out / "wide_bybit" / f"{d}.parquet", index=False)
                print(d, "written", flush=True)
            d += dt.timedelta(days=1)
        return 0
    ticks, cat, tob, hours = ingest(a.day, a.asset)
    if tob is None or not hours:
        print(f"{a.day}: no recorded top of book; nothing to replay")
        return 1
    w = wide(ticks, cat, tob, a.day, hours)
    w.to_parquet(out / "wide" / f"{a.day}.parquet", index=False)
    wb = bybit_wide(a.day, sym, cat, tob, hours)
    wb.to_parquet(out / "wide_bybit" / f"{a.day}.parquet", index=False)
    w_all = pd.concat([pd.read_parquet(p) for p in sorted((out / "wide").glob("*.parquet"))], ignore_index=True)
    wb_all = pd.concat([pd.read_parquet(p) for p in sorted((out / "wide_bybit").glob("*.parquet"))], ignore_index=True)
    live = {run: live_day(run, a.day, w, a.lag or 500, wb) for run in runs}
    lag, by = matched_lag(save_gaps(out / "gaps.parquet", a.day, live), 500)
    lag = a.lag or lag
    how = "--lag" if a.lag else "matched to live fills" if lag != 500 else "default; the live gaps do not clearly favour another delay"
    note = (f"Replay delay: {lag} ms ({how}); mean live minus "
            "replay price by delay: " + (", ".join(f"{L} ms {m * 100:+.1f}c (n {n})" for L, (m, n) in sorted(by.items()))
                                         or f"no live fills yet (default 500 ms until {MIN_GAP_N})"))
    live = {run: live_day(run, a.day, w, lag, wb) for run in runs}
    runs_by = {"v5": "paper_v5b", "v4": "paper_v4b"} if a.asset == "btc" else {"v4": "paper_ethb"}
    text, res, oos, picks = report(a.day, lag, w_all, live, live_rules, a.asset.upper(), wb_all, note,
                                   weekly(wb_all, lag, runs_by) if a.asset == "btc" else None)
    rep.mkdir(parents=True, exist_ok=True)
    (rep / f"{a.day}.md").write_text(text, encoding="utf-8")
    prop = proposal(a.day, res, oos, picks, live_rules)
    if prop:
        (rep / "proposals").mkdir(exist_ok=True)
        (rep / "proposals" / f"{a.day}.md").write_text(prop, encoding="utf-8")
    print(f"wrote {rep / f'{a.day}.md'}" + (" and a proposal" if prop else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
