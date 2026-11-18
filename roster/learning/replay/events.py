"""Replay lab event store (role 35, build-plan 5.4): the recorded feeds, as known at each moment.

Every event has recorded_ms (when this PC had it). `Store.as_of(t)` and the runner apply only events with
recorded_ms <= t, in recorded order (file order within a millisecond):
- Polymarket market WS: recorder rows {t, raw} from data/recordings/<stream>/<date>/<HH>.jsonl or
  data/recordings/parquet/stream=<stream>/date=<date>/<HH>.parquet (Parquet wins when both exist), parsed by
  trader.marketdata.Books.apply(raw, t), the live parser. recorded_ms = t; event_ms = the message timestamp.
- Markets: crawler snapshots data/markets/<ts>Z.jsonl through trader.marketdata.market_info, recorded at <ts>.
- Reference: Binance closes {asset, ts_ms, price} recorded at the candle close (data/history/binance 1m, or a list such
  as 1s klines fetched for the window); DVOL 1h candles (data/history/deribit) recorded at their close; the final print
  (12:00 ET 1m candle close, keyed by its open ms as trader.marketdata.Ref keys it) recorded at the candle close.
"""
import bisect
import dataclasses
import datetime as dt
import json
import pathlib
from collections import Counter

import duckdb
import pandas as pd

import common
from recorder import crawler
from trader.marketdata import ET, SYMBOL, Books, market_info

REC = common.DATA / "recordings"
HIST = common.DATA / "history"
MIN_MS, H_MS = 60_000, 3_600_000
ASSETS = ("BTC", "ETH")


class State:
    """Everything known at one moment: books (trader.marketdata.Books), trades, ref (the Engine's ref dict), markets,
    the snapshot time in force, and rec = recorded time of every reference value (tripwire and feed ages)."""

    def __init__(self):
        self.books = Books()
        self.trades: list[dict] = []
        self.ref: dict[str, dict] = {}
        self.rec: dict = {}            # "polymarket:<stream>" | "binance:<a>" | "dvol:<a>" | ("final", a, open_ms) -> ms
        self.markets: dict = {}        # cid -> MarketInfo; updated in place (the fill model holds it)
        self.snapshot_ms: int | None = None
        self.cid_of: dict[str, str] = {}

    def _ref(self, asset: str) -> dict:
        return self.ref.setdefault(asset, {"price": None, "ts_ms": None, "recv_ms": None, "dvol": None,
                                           "dvol_ts_ms": None, "final": {}})


class Store:
    """Events as (recorded_ms, kind, data), sorted by recorded_ms. kinds: pm (raw, stream), markets (snap_ms, {cid:
    MarketInfo}), ref (asset, ts_ms, price), dvol (asset, ts_ms, value), final (asset, open_ms, price)."""

    def __init__(self, pm=(), markets=(), ref=(), dvol=(), finals=()):
        ev = [(int(t), "pm", (raw, s)) for t, raw, s in pm]
        ev += [(int(ms), "markets", (int(ms), mk)) for ms, mk in markets]
        ev += [(int(r.get("recorded_ms", r["ts_ms"])), "ref", (r["asset"], int(r["ts_ms"]), float(r["price"]))) for r in ref]
        ev += [(int(r["recorded_ms"]), "dvol", (r["asset"], int(r["ts_ms"]), float(r["value"]))) for r in dvol]
        ev += [(int(r["recorded_ms"]), "final", (r["asset"], int(r["open_ms"]), float(r["price"]))) for r in finals]
        ev.sort(key=lambda e: e[0])  # stable: file order within one millisecond
        self.events = ev
        self._t = [e[0] for e in ev]
        self.counts = Counter(e[1] for e in ev)

    def until(self, t_ms: int) -> list:
        """Events recorded at or before t_ms."""
        return self.events[:bisect.bisect_right(self._t, t_ms)]

    def apply(self, st: State, e) -> list[tuple]:
        """Apply one event to st. Returns what changed: Books events ("book", token), ("trade", token, price, size,
        taker_side, event_ms), ("tick", token, tick), plus ("ref", asset) and ("markets",)."""
        t, kind, d = e
        if kind == "pm":
            evs = st.books.apply(d[0], t)
            st.rec[f"polymarket:{d[1]}"] = t
            for ev in evs:
                if ev[0] == "trade":
                    st.trades.append({"token": ev[1], "price": ev[2], "size": ev[3], "side": ev[4], "event_ms": ev[5],
                                      "recorded_ms": t})
                elif ev[0] == "tick" and (cid := st.cid_of.get(ev[1])) and st.markets[cid].tick_size != ev[2]:
                    st.markets[cid] = dataclasses.replace(st.markets[cid], tick_size=ev[2])  # as the live loop does
            return evs
        if kind == "markets":
            # ponytail: a newer snapshot reverts a WS tick change made after it was crawled; live keeps ws_tick
            st.markets.clear()
            st.markets.update(d[1])
            st.snapshot_ms = d[0]
            st.cid_of = {tok: m.cid for m in d[1].values() for tok in (m.token_yes, m.token_no)}
            return [("markets",)]
        asset, ts, v = d
        r = st._ref(asset)
        if kind == "ref":
            r.update(price=v, ts_ms=ts, recv_ms=t)
            st.rec[f"binance:{asset}"] = t
            return [("ref", asset)]
        if kind == "dvol":
            r.update(dvol=v, dvol_ts_ms=ts)
            st.rec[f"dvol:{asset}"] = t
        else:
            r["final"][ts] = v
            st.rec[("final", asset, ts)] = t
        return []

    def as_of(self, t_ms: int) -> State:
        """Books, trades, reference values and markets as known at t_ms: only events with recorded_ms <= t_ms."""
        st = State()
        for e in self.until(t_ms):
            self.apply(st, e)
        return st

    def pm_span(self) -> tuple[int, int] | None:
        ts = [e[0] for e in self.events if e[1] == "pm"]
        return (ts[0], ts[-1]) if ts else None

    @classmethod
    def load(cls, start_ms: int, end_ms: int, streams=("crypto-term",), ref=None, warm_ms=10 * MIN_MS):
        """Everything recorded on this PC for [start_ms - warm_ms, end_ms]. ref: a {asset, ts_ms, price} list in
        place of the Binance 1m history (e.g. klines fetched for a window the history does not cover)."""
        lo = start_ms - warm_ms
        return cls(pm=load_pm(streams, lo, end_ms), markets=load_markets(streams, start_ms, end_ms),
                   ref=load_ref(lo, end_ms) if ref is None else ref, dvol=load_dvol(lo, end_ms),
                   finals=load_finals(lo, end_ms))


def _hours(lo: int, hi: int):
    h = lo // H_MS * H_MS
    while h <= hi:
        yield dt.datetime.fromtimestamp(h / 1000, dt.timezone.utc)
        h += H_MS


def load_pm(streams, lo: int, hi: int, root=REC) -> list[tuple]:
    """(t, raw, stream) recorder rows with lo <= t <= hi."""
    out = []
    for s in streams:
        for h in _hours(lo, hi):
            date, hh = h.strftime("%Y-%m-%d"), h.strftime("%H")
            pq, js = root / "parquet" / f"stream={s}" / f"date={date}" / f"{hh}.parquet", root / s / date / f"{hh}.jsonl"
            if pq.exists():
                df = pd.read_parquet(pq, columns=["t", "raw"])
                rows = zip(df["t"].tolist(), df["raw"].tolist())
            elif js.exists():
                rows = ((r["t"], r["raw"]) for r in map(json.loads, js.read_text(encoding="utf-8").splitlines()) if r)
            else:
                continue
            out += [(int(t), raw, s) for t, raw in rows if lo <= t <= hi]
    return out


def snapshot_ms(path: pathlib.Path) -> int:
    return int(dt.datetime.strptime(path.stem, "%Y-%m-%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def load_markets(modes, start_ms: int, end_ms: int, markets_dir=crawler.MARKETS_DIR) -> list[tuple]:
    """(snap_ms, {cid: MarketInfo}) for the snapshot in force at start_ms and every later one up to end_ms."""
    snaps = sorted((snapshot_ms(p), p) for p in markets_dir.glob("*Z.jsonl"))
    keep = [s for s in snaps if start_ms < s[0] <= end_ms]
    before = [s for s in snaps if s[0] <= start_ms]
    out = []
    for ms, p in before[-1:] + keep:
        mk = {m.cid: m for m in map(market_info, crawler.read_snapshot(p)) if m and m.mode in modes}
        out.append((ms, mk))
    return out


def _klines(asset: str, where: str) -> pd.DataFrame:
    d = (HIST / "binance" / SYMBOL[asset]).as_posix()
    return duckdb.sql(f"select distinct open_time, close, close_time from read_parquet('{d}/*.parquet') "
                      f"where {where} order by open_time").df()


def load_ref(lo: int, hi: int) -> list[dict]:
    """Binance 1m closes from data/history/binance, recorded at the candle close."""
    out = []
    for a in ASSETS:
        df = _klines(a, f"close_time between {lo} and {hi}")
        out += [{"asset": a, "ts_ms": int(c), "price": float(p), "recorded_ms": int(c)}
                for p, c in zip(df["close"], df["close_time"])]
    return out


def noon_opens(lo: int, hi: int) -> list[int]:
    """Open ms of every 12:00 ET 1m candle from two days before lo to hi (Up/Down opens and daily settlements)."""
    d0 = dt.datetime.fromtimestamp(lo / 1000, ET).date() - dt.timedelta(days=2)
    d1 = dt.datetime.fromtimestamp(hi / 1000, ET).date()
    days = [d0 + dt.timedelta(days=i) for i in range((d1 - d0).days + 1)]
    return [int(dt.datetime.combine(d, dt.time(12), ET).timestamp() * 1000) for d in days]


def load_finals(lo: int, hi: int) -> list[dict]:
    opens = [o for o in noon_opens(lo, hi) if o + MIN_MS <= hi]
    out = []
    for a in ASSETS:
        if opens:
            df = _klines(a, f"open_time in ({','.join(map(str, opens))})")
            out += [{"asset": a, "open_ms": int(o), "price": float(p), "recorded_ms": int(o) + MIN_MS}
                    for o, p in zip(df["open_time"], df["close"])]
    return out


def load_dvol(lo: int, hi: int) -> list[dict]:
    """Deribit DVOL 1h candles (percent, as published), recorded at their close; from 2h before lo."""
    out = []
    for a in ASSETS:
        p = HIST / "deribit" / f"dvol_{a}_1h.parquet"
        if p.exists():
            d = pd.read_parquet(p)
            d = d[(d["ts"] + H_MS >= lo - 2 * H_MS) & (d["ts"] + H_MS <= hi)]
            out += [{"asset": a, "ts_ms": int(t), "value": float(v), "recorded_ms": int(t) + H_MS}
                    for t, v in zip(d["ts"], d["close"])]
    return out
