"""System backtest: the real trader (trader.loop.Trader with its kernel, router, breakers, ledger, audit and btc-speed
engine) driven by recorded history instead of live feeds. Paper only; read-only on data/history; no network.

The replay (research/replay) asks "what would a rule earn"; this asks "what would our system have done": the same
caps, guards, breakers, fill simulator and reports that run live, on a sim clock.

Feeds:
  - Binance BTCUSDT aggTrades (history/binance.py --aggtrades) -> ref["BTC"], received `--lag-ms` after trade time
    (live median about 50-70 ms).
  - Polymarket top of book of every BTC 5m/15m market (history/pm_fast.py) -> one-level books of `--depth` shares per
    side (the archive has no depth). A market is listed 15 min before its window and dropped 10 min after its end.
  - Outcomes from the catalog; held shares settle at the first sim minute after the end.
  - The archive keeps top-of-book changes only, so a book is marked fresh at every Binance tick while its market's
    window is open (live, these books update many times a second); otherwise the 5 s stale-book guard would misfire.
Housekeeping runs on the sim clock: the 100 ms tick (on events), the per-minute advice reload, and the 08:15 IST
breaker reset (policy B, as ops/morning_reset.py; never a HALT). The run is 24 h a day (no PC sleep).

    python -m research.backtest.system 2026-07-27 2026-08-09 --name v3 --enable speed_only --enable speed_v3
    python -m research.backtest.system 2026-07-27 2026-08-09 --name v2 --enable speed_only

Output: data/research/backtest/<name>/ (the run dir: ledger, audit, journal) and reports/research/backtest_<name>.md
(the nightly daily report over the whole range, plus a per-day table).
"""
import argparse
import datetime as dt
import os
import pathlib
import shutil
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

KEY = "backtest-local-key"           # signs this run's own clearances and resets; never a real approval key
os.environ["ROSTER_HUMAN_KEY"] = KEY  # before the trader modules read it

from common import DATA, REPORTS  # noqa: E402
from nightly import report, scorer  # noqa: E402
from tools.clearance_cli import write as sign_record  # noqa: E402
from trader.contracts import Book, MarketInfo, TradingState  # noqa: E402
from trader.kernel import clearance_key  # noqa: E402
from trader.loop import Trader  # noqa: E402

H = DATA / "history"
ET, IST = ZoneInfo("America/New_York"), dt.timezone(dt.timedelta(hours=5, minutes=30))
LIST_BEFORE_MS, KEEP_AFTER_MS, MIN = 15 * 60_000, 10 * 60_000, 60_000


def market(row) -> MarketInfo:
    s, e = (dt.datetime.fromtimestamp(x / 1000, ET) for x in (row.start_ms, row.end_ms))
    fmt = lambda t: t.strftime("%I:%M%p").lstrip("0")
    q = f"Bitcoin Up or Down - {s:%B} {s.day}, {fmt(s)}-{fmt(e)} ET"   # the live question format (duration parse)
    start = dt.datetime.fromtimestamp(row.start_ms / 1000, dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    return MarketInfo(row.cid, row.token_up, row.token_down, "crypto-fast", q, "backtest", 0.001, 5.0, 0.07, False,
                      int(row.end_ms), f"BTC-{row.dur_min}m@{start}", "BTC", None, "updown", "chainlink:BTC/USD")


class HistMD:
    """The MarketData surface the Trader uses, filled from history on a sim clock."""

    def __init__(self):
        self.markets, self.books, self.rtt_ms = {}, {}, 200.0
        self.ref = {"BTC": {"price": None, "ts_ms": None, "recv_ms": None, "dvol": None, "final": {}}}
        self.on_book = self.on_trade = self.on_ref = None
        self.last = {"polymarket": None, "binance:BTC": None}

    def feed_age_ms(self, now: int) -> dict:
        out = {k: now - v for k, v in self.last.items() if v is not None}
        if "polymarket" in out:
            out["polymarket:crypto-fast"] = out["polymarket"]
        return out


def load(day: dt.date):
    agg = H / "binance" / "BTCUSDT" / "aggTrades" / f"BTCUSDT-aggTrades-{day}.parquet"
    cat = H / "pm_fast" / "catalog" / f"{day}.parquet"
    tob = sorted((H / "pm_fast" / "tob").glob(f"{day}T*.parquet"))
    trades = sorted((H / "pm_fast" / "trades").glob(f"{day}T*.parquet"))
    if not agg.exists() or not cat.exists() or len(tob) < 24 or len(trades) < 24:
        return None
    return (pd.read_parquet(agg), pd.read_parquet(cat), pd.concat(pd.read_parquet(p) for p in tob),
            pd.concat(pd.read_parquet(p) for p in trades))


def run(first: dt.date, last: dt.date, name: str, features: set, lag_ms: int, rtt: float, depth: float,
        cash: float, global_cap: float | None = None) -> pathlib.Path:
    d = DATA / "research" / "backtest" / name
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    md = HistMD()
    md.rtt_ms = rtt
    t_start = int(dt.datetime.combine(first, dt.time(), dt.timezone.utc).timestamp() * 1000)
    t_end = int(dt.datetime.combine(last + dt.timedelta(days=1), dt.time(), dt.timezone.utc).timestamp() * 1000)
    probe = {dur: market(pd.Series({"cid": "x", "token_up": "u", "token_down": "d", "dur_min": dur,
                                    "start_ms": t_start, "end_ms": t_start + dur * MIN})) for dur in (5, 15)}
    for m in probe.values():  # one clearance per template (the key has no cid), valid for the whole range
        sign_record(d / "advice.db", {"type": "clearance", "key": clearance_key(m), "signer": "backtest",
                                      "expiry_ms": t_end + 86_400_000}, KEY)
    sim = {"now": t_start}
    tr = Trader(md, d, cash, fetch=lambda cid: None, features=features)
    tr.now = lambda: sim["now"]
    if global_cap is not None:  # research only: live, a person raises the cap; the kernel refuses buys above 1.1x it
        tr.kernel.global_cap = global_cap
    tr.start(t_start)
    winners, cats, last_tick, last_min, reset_day, open_toks, starts = {}, [], 0, 0, None, [], {}
    day, wall = first, time.monotonic()
    while day <= last:
        got = load(day)
        if got is None:
            print(f"{day}: skipped (data incomplete)", flush=True)
            day += dt.timedelta(days=1)
            continue
        agg, cat, tob, pm_trades = got
        for r in cat.itertuples():
            starts[r.cid] = int(r.start_ms)
            winners[r.cid] = r.token_up if r.winner == "up" else r.token_down if r.winner == "down" else None
        cats.append(cat)
        listing = sorted(((int(r.start_ms) - LIST_BEFORE_MS, r) for r in cat.itertuples()), key=lambda x: x[0])
        li = 0
        # one time-ordered stream: Binance ticks (kind 0), top-of-book changes (1), Polymarket trades (2: they only
        # show the feed is alive; the archive drops book events that leave the top unchanged)
        t_b = agg.ts_ms.to_numpy() + lag_ms
        t_p, t_t = tob.ts_ms.to_numpy(), pm_trades.ts_ms.to_numpy()
        times = np.concatenate([t_b, t_p, t_t])
        kind = np.concatenate([np.zeros(len(t_b), np.int8), np.ones(len(t_p), np.int8), np.full(len(t_t), 2, np.int8)])
        idx = np.concatenate([np.arange(len(t_b)), np.arange(len(t_p)), np.arange(len(t_t))])
        order = np.argsort(times, kind="stable")
        px, bts = agg.price.to_numpy(), agg.ts_ms.to_numpy()
        tok, bid, ask = tob.asset_id.astype(str).to_numpy(), tob.best_bid.to_numpy(), tob.best_ask.to_numpy()
        n0 = len(tr.router.state.fills)
        for o in order:
            now = int(times[o])
            sim["now"] = now
            while li < len(listing) and listing[li][0] <= now:          # list markets as their windows approach
                m = market(listing[li][1])
                md.markets[m.cid] = m
                li += 1
            if now - last_tick >= 100:
                tr.tick(now)
                last_tick = now
            if now - last_min >= MIN:
                last_min = now
                for cid in [c for c, m in md.markets.items() if m.end_ms + KEEP_AFTER_MS < now]:
                    del md.markets[cid]
                open_toks = [t for c, m in md.markets.items() if starts.get(c, m.end_ms) <= now < m.end_ms
                             for t in (m.token_yes, m.token_no)]
                due = tr.unsettled(now)
                if due:
                    tr.settle({c: winners.get(c) for c in due}, now)
                local = dt.datetime.fromtimestamp(now / 1000, IST)
                if local.hour == 8 and local.minute >= 15 and reset_day != local.date():  # policy B, never a HALT
                    reset_day = local.date()
                    for scope, st in list(tr.kernel.scopes.items()):
                        if st == TradingState.REDUCING:
                            sign_record(d / "advice.db", {"type": "reset", "scope": scope, "signer": "backtest-auto",
                                                          "expiry_ms": now + 30 * MIN}, KEY)
            if kind[o] == 0:
                i = idx[o]
                md.last["binance:BTC"] = now
                md.ref["BTC"].update(price=float(px[i]), ts_ms=int(bts[i]), recv_ms=now)
                for t in open_toks:
                    if t in md.books:
                        md.books[t].ts_ms = now
                tr.on_ref("BTC", now)
            elif kind[o] == 2:
                md.last["polymarket"] = now
            else:
                i = idx[o]
                md.last["polymarket"] = now
                b, a = bid[i], ask[i]
                book = Book(tok[i], [] if np.isnan(b) or b <= 0 else [(float(b), depth)],
                            [] if np.isnan(a) or a >= 1 else [(float(a), depth)], now)
                md.books[tok[i]] = book
                tr.on_book(book, now)
        print(f"{day}: {len(tr.router.state.fills) - n0} fills, state {tr.kernel.state.value}, "
              f"trips so far {len(tr.kernel.trips)}, "
              f"{time.monotonic() - wall:.0f} s so far", flush=True)
        day += dt.timedelta(days=1)
    sim["now"] = t_end
    tr.tick(t_end)
    due = tr.unsettled(t_end + 1)
    if due:
        tr.settle({c: winners.get(c) for c in due}, t_end)
    tr.shutdown(t_end)
    allcat = pd.concat(cats) if cats else pd.DataFrame()
    outcome = {r.cid: {"winner": winners[r.cid], "yes": r.winner == "up"} for r in allcat.itertuples() if winners.get(r.cid)}
    text, summary = report.build(d, t_start, t_end, f"System backtest {name}: {first} to {last}",
                                 fetch=lambda cid: outcome.get(cid), now_ms=t_end + 1)
    rep = REPORTS / "research" / f"backtest_{name}.md"
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text(f"Features: {sorted(features)}; global cap {tr.kernel.global_cap}; Binance receive lag {lag_ms} ms; RTT {rtt} ms; book depth "
                   f"{depth} shares per side (assumed); start cash {cash}. Sim clock, 24 h a day, 08:15 IST breaker "
                   f"reset.\n\n" + text + per_day(d), encoding="utf-8")
    print(summary)
    print("wrote", rep)
    return d


def per_day(d: pathlib.Path) -> str:
    t = scorer.tables(d)
    fills = pd.DataFrame(t.get("fills", []))
    if fills.empty:
        return "\n## Per day\n\nNo fills.\n"
    sets = pd.DataFrame(t.get("settlements", []))
    fills["day"] = pd.to_datetime(fills.ts_ms, unit="ms").dt.date
    fills["cash"] = np.where(fills.side == "BUY", -1, 1) * fills.price * fills["size"] - fills.fee
    pay = sets.assign(pay=sets.shares * sets.payout).groupby("token_id").pay.sum() if len(sets) else pd.Series(dtype=float)
    first_day = fills.groupby("token_id").day.min()
    fills["payout"] = 0.0
    rows = ["", "## Per day (cash flows of fills bought that day plus their settlement payouts)", "",
            "| UTC day | fills | buys | sells | P&L USD |", "|---|---|---|---|---|"]
    for day, g in fills.groupby("day"):
        toks = first_day[first_day == day].index
        p = g.cash.sum() + pay.reindex(toks).fillna(0).sum()
        rows.append(f"| {day} | {len(g)} | {(g.side == 'BUY').sum()} | {(g.side == 'SELL').sum()} | {p:+.2f} |")
    return "\n".join(rows) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("first")
    ap.add_argument("last")
    ap.add_argument("--name", required=True)
    ap.add_argument("--enable", action="append", default=[], help="trader feature flags (speed_only is required)")
    ap.add_argument("--lag-ms", type=int, default=60)
    ap.add_argument("--rtt", type=float, default=250.0)
    ap.add_argument("--depth", type=float, default=100.0)
    ap.add_argument("--cash", type=float, default=50.0)
    ap.add_argument("--global-cap", type=float, default=None, help="override the kernel's global cap (research only)")
    a = ap.parse_args(argv)
    if "speed_only" not in a.enable:
        sys.exit("history has no daily-market data for ladder-maker: pass --enable speed_only")
    run(dt.date.fromisoformat(a.first), dt.date.fromisoformat(a.last), a.name, set(a.enable), a.lag_ms, a.rtt,
        a.depth, a.cash, a.global_cap)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
