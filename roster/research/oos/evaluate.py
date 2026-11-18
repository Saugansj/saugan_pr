"""Out-of-sample test of v4/v5 on 2026-04-13 .. 2026-07-26, exactly as pre-registered in
reports/research/oos/prereg_2026-10-12.md (sha256 6b0b8454...). Run it when history.pm_fast has finished those days.

For each day with all 24 archive hours: the research loop's wide replay (research.loop.nightly.wide) on Binance and on
Bybit spot ticks, cached in data/research/oos/ (never in data/research/loop/wide: these days must not reach the loop's
selection). Then the pre-registered statistics and verdict -> reports/research/oos/result.md.

    python -m research.oos.evaluate [2026-04-13 2026-07-26]
"""
import datetime as dt
import sys

import pandas as pd

import pyarrow.parquet as pq

from common import DATA, REPORTS
from research.feeds.bybit_replay import ticks as bybit_ticks
from research.loop import nightly as N
from research.replay.replay import load_day

OUT, REP = DATA / "research" / "oos", REPORTS / "research" / "oos"
V5, V4 = (0.85, 0.10, "calm55", "hold"), (0.85, 0.10, "none", "hold")


def verdict(m: float, se: float, n: int) -> str:
    """The pre-registered rule: PASS n >= 200 and mean > 2 SE; FAIL mean <= 0; else INCONCLUSIVE."""
    if not m == m or n == 0:  # NaN: no trades
        return "INCONCLUSIVE (no trades)"
    if m <= 0:
        return "FAIL"
    return "PASS" if n >= 200 and m > 2 * se else "INCONCLUSIVE"


def has_books(day: dt.date) -> bool:
    """Every archive hour of the day holds rows for our markets. The pmxt archive lacks the BTC 5m/15m markets on some
    days (e.g. 2026-06-15, 06-21); history.pm_fast still writes an empty file for such an hour, so an empty hour is a
    missing hour here, as the pre-registration excludes days with missing archive hours."""
    hours = sorted((DATA / "history" / "pm_fast" / "tob").glob(f"{day}T*.parquet"))
    return len(hours) >= 24 and all(pq.ParquetFile(h).metadata.num_rows > 0 for h in hours)


def build(first: dt.date, last: dt.date) -> tuple[pd.DataFrame, pd.DataFrame, list]:
    (OUT / "binance").mkdir(parents=True, exist_ok=True)
    (OUT / "bybit").mkdir(parents=True, exist_ok=True)
    skipped, d = [], first
    while d <= last:
        pb, py = OUT / "binance" / f"{d}.parquet", OUT / "bybit" / f"{d}.parquet"
        if not (pb.exists() and py.exists()):
            got = load_day(d) if has_books(d) else None  # complete days only: catalog + 24 non-empty hours
            if got is None:
                skipped.append(str(d))
            else:
                N.wide(got[0], got[1], got[2], d, source="oos-binance").to_parquet(pb, index=False)
                t = pd.concat([bybit_ticks(d - dt.timedelta(days=1)), bybit_ticks(d)]).sort_values("ts_ms", kind="stable")
                N.wide(t, got[1], got[2], d, source="oos-bybit").to_parquet(py, index=False)
                print(d, "replayed", flush=True)
        d += dt.timedelta(days=1)
    load = lambda sub: pd.concat([pd.read_parquet(p) for p in sorted((OUT / sub).glob("*.parquet"))
                                  if first <= dt.date.fromisoformat(p.stem) <= last], ignore_index=True)
    return load("binance"), load("bybit"), skipped


def stats(w: pd.DataFrame, rule, lag: int) -> tuple[float, float, int, float, pd.DataFrame]:
    tr = N.trades(N.pnl(w[(w.lag == lag) & (w.cfg == "2s/6bp")]), *rule)
    m, se, n = N.stat(tr)
    return m, se, n, tr.pnl.sum(), tr


def main(argv) -> int:
    first, last = (dt.date.fromisoformat(a) for a in (argv[:2] or ["2026-04-13", "2026-07-26"]))
    bn, by, skipped = build(first, last)
    days = sorted(bn.day.unique())
    m, se, n, tot, tr5 = stats(bn, V5, 500)
    L = [f"# Out-of-sample result: {first} .. {last}", "",
         f"Pre-registration: reports/research/oos/prereg_2026-10-12.md. Days with complete data: {len(days)}; "
         f"excluded (missing archive hours): {len(skipped)}.", "",
         f"## Primary: v5, Binance, 500 ms: {m:+.3f} ± {se:.3f} USD per trade, n {n}, total {tot:+.1f} -> "
         f"**{verdict(m, se, n)}**", "", "## Secondary (not decisive)", "",
         "| rule | feed | delay | per trade ± SE | n | total |", "|---|---|---|---|---|---|"]
    for name, rule in (("v5", V5), ("v4", V4)):
        for feed, w in (("Binance", bn), ("Bybit", by)):
            for lag in (500, 1000):
                a, b, c, t, _ = stats(w, rule, lag)
                L.append(f"| {name} | {feed} | {lag} ms | {a:+.3f} ± {b:.3f} | {c} | {t:+.1f} |")
    m4 = stats(bn, V4, 500)[0]
    L += ["", f"v5 minus v4 per trade (Binance, 500 ms): {m - m4:+.3f} USD.", "",
          "## v5 per month (Binance, 500 ms): edge decay over time", "", "| month | per trade | n | total |", "|---|---|---|---|"]
    for mo, g in tr5.groupby(tr5.day.str[:7]):
        a, b, c = N.stat(g)
        L.append(f"| {mo} | {a:+.3f} ± {b:.3f} | {c} | {g.pnl.sum():+.1f} |")
    L += ["", "Replay P&L is an upper bound: top of book, 5 shares at the ask, no queue behind other bots."]
    REP.mkdir(parents=True, exist_ok=True)
    (REP / "result.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
