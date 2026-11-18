"""Market data for the Phase 1 paper trader (WP1-C; build-plan 1.4 and 1.5, roles 07, 08, 09). Public read-only feeds.

- load_markets(): MarketInfo for the target markets from WP0-A's latest crawler snapshot (data/markets/), crawling
  again (recorder.crawler, imported read-only) when the snapshot is older than an hour or lacks a target mode.
- MarketData.run(): one asyncio task set, with callbacks the loop (WP1-F) sets:
  - Polymarket market WebSocket, one connection per mode -> `books[token]` (Book; ts_ms = local receive time of
    that token's last update, the staleness clock) and `on_book(book, now_ms)`; trades -> `on_trade(token, price,
    size, taker_side, ts_ms)`; a tick-size change replaces that market's MarketInfo (which voids its clearance)
  - Binance spot aggTrade + kline_1m for BTC/ETH -> `ref[asset]` and `on_ref(asset, now_ms)` on every trade, plus
    the final value at each print: `final[noon ET ms]` (12:00 ET 1m candle close, keyed by the daily market's
    end_ms) and `final_1h[hour end ms]` (1H candle close, keyed by the hourly market's end_ms)
  - Deribit DVOL (BTC, ETH) every 60 s -> `ref[asset]["dvol"]`; Kraken USDT/USD every 60 s -> `usdt_usd`
  - feed_age_ms(now) under the kernel's feed names (polymarket, binance:BTC, dvol:BTC, basis:USDT, ...)
  - round trip to clob.polymarket.com (median of 3 GETs of /time on a warm connection) every 60 s -> `rtt_ms`,
    each measurement appended to data/trader/rtt.jsonl; the router reads it for taker arrival times
  - markets reloaded every 5 min (crawl when over an hour old); WebSockets resubscribe when the token set changes

What the APIs return (checked live 2026-10-01):
- Polymarket market WS (subscribe {"assets_ids": [...], "type": "market", "custom_feature_enabled": true}): first a
  JSON list of "book" events {asset_id, market, timestamp (server ms, string), hash, tick_size, bids, asks,
  last_trade_price} with levels {"price": "0.87", "size": "10"} sorted WORST FIRST (bids ascending, asks
  descending). Then "price_change" {market, timestamp, price_changes: [{asset_id, price, size (new level total, 0 =
  gone), side BUY=bid/SELL=ask, best_bid, best_ask, hash}]} (about 1,000/s across 14 ladder + 5m tokens), fresh
  "book" snapshots after trades, "last_trade_price" {asset_id, price, size, side, fee_rate_bps, timestamp,
  transaction_hash} and "best_bid_ask". "PING" is answered with "PONG". "tick_size_change" carries new_tick_size.
- Binance combined stream: {"stream", "data"}; aggTrade data {e, E event ms, s, p, q, T trade ms, m}; BTC about
  3 and ETH about 12 trades/s at 07:00 UTC. kline_1m data {e, E, s, k: {t open ms, T, o, h, l, c, x closed}}.
- Deribit get_volatility_index_data (resolution 60): result.data [[ts, open, high, low, close], ...], oldest first.
- Kraken Ticker?pair=USDTUSD: result.USDTZUSD {a: [ask, ...], b: [bid, ...], c: [last, vol], ...}; mid about 0.9995.
- CLOB GET /time: the server's Unix time in whole seconds. Warm round trip from this PC about 200-215 ms; the first
  request on a new connection (TLS handshake) about 530 ms, which a kept-alive order client does not pay.

Paper mode: our orders are never on the venue book, so Book.own stays empty and mid_ex_own() equals the mid; `own`
is for Phase 2. No order is ever sent from here (GET and WebSocket reads only).

    python -m trader.marketdata --seconds 75     # live smoke run: prints books, ticks, finals, DVOL and RTT; exit 1 if any feed is silent

Wiring flags (WW-B; `features` = the enabled flag names from trader/features.py; none set = the Phase 1 behaviour above):
- touch: touch templates load (trader.growth.universe.market_info_ext) and each touch window's running Binance 1m
  high/low since window_start_ms(row) is kept as ref[asset]["touch"][cid] = {"start_ms", "high", "low"} (absent until
  its REST backfill completes, and cleared on a Binance reconnect until backfilled again: absent = fail closed).
  Price one with growth.touch.touch_fair(m, touch_ref(ref, m), ...).
- universe_ext: SOL/XRP ladders load, Binance subscribes SOLUSDT/XRPUSDT and ref[asset]["sigma_q"] is the realized
  sigma_Q from the last day of 1m closes (universe.sigma_q_for; None when short or non-finite).
- sports: set_sports(events) maps sports-pregame rows with sports.odds.map_markets into `markets` (event_group =
  MarketMap.event_key; maps in `sports_maps`); feed_age_ms merges sports.gamestate.feed_age_ms(now, sports_feeds).
- `held` (not a flag): a callable returning {token: shares net of redemptions}; when set, a market past end + 6 h stays
  in `markets` while either token is held (Phase 2 audit must-fix). None = Phase 1's plain 6 h drop.
"""
import argparse
import asyncio
import collections
import dataclasses
import datetime as dt
import http.client
import json
import math
import re
import statistics
import time
import zoneinfo

import websockets

import common
from recorder import crawler
from trader.contracts import Book, MarketInfo

TARGET_MODES = ("crypto-term", "crypto-fast")  # ladder-maker: daily strikes + daily Up/Down; btc-speed: 5m/15m
MAX_AGE_S = 3600
REFRESH_S = 300
KEEP_AFTER_END_MS = 10 * 60_000  # books of ended markets stay subscribed this long (markouts, oracle gap)
SILENT_S = 45      # a subscribed PM socket this long without a frame: reload markets and resubscribe
RETRY_S = 15       # a failed poll retries this soon, not a full period later
DEFAULT_RTT_MS = 250.0           # until the first measurement
PM_WS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
BINANCE_WS = "wss://stream.binance.com:9443/stream?streams="
BYBIT_WS = "wss://stream.bybit.com/v5/public/spot"  # ref_bybit: BTC/ETH trades from Bybit (public, no key)
BYBIT_ASSETS = {"BTCUSDT": "BTC", "ETHUSDT": "ETH"}  # 12 Oct: Binance ticks reached this PC 3-12 s late on moves
FEED_HUB = "ws://127.0.0.1:8765"  # feed_hub flag: Binance/Bybit/Polymarket relayed by trader.feedhub (one upstream each)
BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
DVOL_URL = "https://www.deribit.com/api/v2/public/get_volatility_index_data"
BASIS_URL = "https://api.kraken.com/0/public/Ticker"
CLOB_HOST = "clob.polymarket.com"
RTT_LOG = common.DATA / "trader" / "rtt.jsonl"
ET = zoneinfo.ZoneInfo("America/New_York")
SYMBOL = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT", "XRP": "XRPUSDT"}  # SOL/XRP only with universe_ext
DVOL_ASSETS = ("BTC", "ETH")  # Deribit publishes no SOL/XRP DVOL
EXT_ASSETS = ("SOL", "XRP")
H_MS = 3_600_000
VOL_BARS = 1440  # universe.VOL_PARAMS["vol_bars"]
ASSET_OF = {"bitcoin": "BTC", "btc": "BTC", "ethereum": "ETH", "eth": "ETH"}


class CallbackError(Exception):
    """A loop callback failed (e.g. a journal write). Never mistaken for a feed error: it stops the feed."""


def iso_ms(s: str) -> int:
    return int(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)


def window(m) -> list[int]:
    """[start_ms, end_ms] of a market for the hub's poll mode: crypto-fast groups carry the length ("BTC-5m@..."); any
    other market counts as open for its last day."""
    g = re.match(r"^\w+-(\d+)m@", m.event_group or "")
    return [m.end_ms - (int(g[1]) * 60_000 if g else 86_400_000), m.end_ms]


def _utc(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def source_id(rules: str) -> str:
    """Resolution source parsed from the rules text, in the kernel's "<venue>:<pair>" form (trader.kernel.STRATEGIES);
    "" if not recognised, so the kernel's provenance check fails. The candle interval is in the rules hash."""
    if m := re.search(r"Chainlink, specifically the (\w+)/USD TWAP", rules):
        return f"chainlink:{m[1]}/USD"
    if m := re.search(r"Binance 1 minute candle for (\w+)/USDT|(\w+)/USDT 1 hour candle", rules):
        return f"binance:{m[1] or m[2]}/USDT"
    return ""


def market_info(r: dict) -> MarketInfo | None:
    """MarketInfo from one crawler row; None if a field needed to trade it is missing (never guessed)."""
    slug = r.get("event_slug") or ""
    asset = ASSET_OF.get(slug.split("-")[0])
    fs = r.get("fee_schedule") or {}
    if not (asset and r.get("yes_token_id") and r.get("no_token_id") and r.get("end_time") and r.get("tick_size")
            and r.get("min_order_size") is not None and (fs.get("rate") is not None or r.get("fees_enabled") is False)):
        return None
    end = iso_ms(r["end_time"])
    kind = "strike" if "-above-" in slug else "updown"
    strike = None
    if kind == "strike":
        m = re.search(r"above \$([\d,]+(?:\.\d+)?)", r.get("question") or "")
        if not m:
            return None
        strike = float(m[1].replace(",", ""))
    if m := re.match(r"^\w+-updown-(\d+m)-(\d+)$", slug):  # crypto-fast: btc-updown-5m-<start s>
        group = f"{asset}-{m[1]}@{_utc(int(m[2]) * 1000)}"
    else:  # every market on one underlying with the same settlement instant
        group = f"{asset}@{_utc(end)}"
    return MarketInfo(
        cid=r["condition_id"], token_yes=r["yes_token_id"], token_no=r["no_token_id"], mode=r["mode"],
        question=r.get("question") or "", rules_sha256=r["rules_sha256"], tick_size=float(r["tick_size"]),
        min_size=float(r["min_order_size"]), fee_rate=0.0 if r.get("fees_enabled") is False else float(fs["rate"]),
        neg_risk=bool(r.get("neg_risk")), end_ms=end, event_group=group, asset=asset, strike=strike, kind=kind,
        source_id=source_id(r.get("rules_text") or ""))


def _ext_mapper(features):
    """market_info, or with touch/universe_ext WP3-C's market_info_ext limited to the templates whose flag is on."""
    if not {"touch", "universe_ext"} & set(features):
        return market_info
    from trader.growth.universe import market_info_ext  # lazy: universe imports this module

    def mi(r):
        m = market_info_ext(r)
        if m is None or (m.kind.startswith("touch") and "touch" not in features) or (
                m.asset in EXT_ASSETS and "universe_ext" not in features):
            return None
        return m
    return mi


def _ext_missing(rows, features) -> bool:
    """A flagged template has no row in the snapshot (e.g. the recorder's flags-off crawl wrote it): crawl again."""
    # ponytail: if the venue really lists none, this crawls on every 5-min reload; add a "crawled with" marker if so
    slugs = [r["event_slug"] for r in rows]
    return ("touch" in features and not any(s.startswith("what-price-will-") for s in slugs)) or (
        "universe_ext" in features and not any(s.split("-")[0] in ("solana", "xrp") for s in slugs))


def load_markets(modes=TARGET_MODES, max_age_s=MAX_AGE_S, markets_dir=crawler.MARKETS_DIR, crawl=crawler.crawl,
                 now_s=None, features=()):
    """({cid: MarketInfo}, {cid: crawler row}) for the target modes; crawls first when the snapshot is stale.
    The raw rows carry what MarketInfo has no field for (fee_schedule for trader.fees, event_start_time).
    features: touch / universe_ext add their templates (crawled and mapped); other flags change nothing here."""
    ext = tuple(f for f in ("touch", "universe_ext") if f in features)
    snap = crawler.latest_snapshot(markets_dir)
    rows = crawler.read_snapshot(snap) if snap else []
    age = (now_s or time.time()) - dt.datetime.strptime(snap.stem, "%Y-%m-%dT%H%M%SZ").replace(
        tzinfo=dt.timezone.utc).timestamp() if snap else None
    if age is None or age > max_age_s or any(all(r["mode"] != m for r in rows) for m in modes) or _ext_missing(rows, ext):
        # every mode: the snapshot is shared with the recorder, so keep it complete
        rows = (crawl(crawler.MODES, features=ext) if ext else crawl(crawler.MODES))[0]
    rows = [r for r in rows if r["mode"] in modes]
    markets = {mi.cid: mi for mi in map(_ext_mapper(ext), rows) if mi}
    return markets, {r["condition_id"]: r for r in rows}


def sports_markets(rows: dict, events: list) -> tuple[dict, dict]:
    """({cid: MarketInfo}, {cid: MarketMap}) for the sports-pregame rows that sports.odds.map_markets matches to one
    event (ESPN GameStates, Kalshi snapshots); unmapped rows and rows missing a trading field are left out."""
    from sports import odds
    maps, _ = odds.map_markets([r for r in rows.values() if r.get("mode") == "sports-pregame"], events)
    out = {}
    for mm in maps:
        r = rows[mm["cid"]]
        fs = r.get("fee_schedule") or {}
        if not (r.get("end_time") and r.get("tick_size") and r.get("min_order_size") is not None
                and (fs.get("rate") is not None or r.get("fees_enabled") is False)):
            continue
        out[mm["cid"]] = MarketInfo(
            cid=mm["cid"], token_yes=mm["token_yes"], token_no=mm["token_no"], mode="sports-pregame",
            question=r.get("question") or "", rules_sha256=r["rules_sha256"], tick_size=float(r["tick_size"]),
            min_size=float(r["min_order_size"]), fee_rate=0.0 if r.get("fees_enabled") is False else float(fs["rate"]),
            neg_risk=bool(r.get("neg_risk")), end_ms=iso_ms(r["end_time"]), event_group=mm["event_key"],
            kind="moneyline")
    return out, {mm["cid"]: mm for mm in maps if mm["cid"] in out}


def touch_ref(ref: dict, m: MarketInfo) -> dict:
    """ref[asset] plus that touch window's running high/low: the r argument of growth.touch.touch_fair. Without a
    backfilled window there is no high/low, so touch_fair returns err (fail closed)."""
    r = ref.get(m.asset) or {}
    return {**r, **(r.get("touch") or {}).get(m.cid, {})}


def window_extremes(asset: str, start_ms: int, now_ms: int, get=common.get_json) -> dict | None:
    """{"start_ms", "high", "low"} of the Binance 1m candles opening at or after start_ms, up to now: 1m bars to the
    first whole hour, then 1h bars (a 1h bar's high/low is that of its 1m bars). None before the window starts."""
    t0 = -(-start_ms // 60_000) * 60_000  # a window opening mid-minute: from the next whole candle
    hour = -(-t0 // H_MS) * H_MS
    bars = []
    if t0 < min(hour, now_ms):
        bars += [b for b in get(BINANCE_KLINES, {"symbol": SYMBOL[asset], "interval": "1m", "startTime": t0,
                                                 "endTime": hour - 1, "limit": 60}) if t0 <= int(b[0]) < hour]
    t = hour
    while t <= now_ms:
        k = [b for b in get(BINANCE_KLINES, {"symbol": SYMBOL[asset], "interval": "1h", "startTime": t, "limit": 1000})
             if int(b[0]) >= t]
        if not k:
            break
        bars += k
        t = int(k[-1][0]) + H_MS
    if not bars:
        return None
    return {"start_ms": start_ms, "high": max(float(b[2]) for b in bars), "low": min(float(b[3]) for b in bars)}


def fetch_closes(asset: str, now_ms: int, n=VOL_BARS, get=common.get_json) -> dict[int, float]:
    """{open ms: close} of the last n closed Binance 1m candles."""
    out, end = {}, now_ms // 60_000 * 60_000 - 1  # the open minute is not closed yet
    while len(out) < n:
        k = get(BINANCE_KLINES, {"symbol": SYMBOL[asset], "interval": "1m", "endTime": end,
                                 "limit": min(1000, n - len(out))})
        if not k:
            break
        out.update({int(b[0]): float(b[4]) for b in k})
        end = int(k[0][0]) - 1
    return out


BYBIT_KLINES = "https://api.bybit.com/v5/market/kline"


def fetch_bybit_closes(asset: str, now_ms: int, n=31, get=common.get_json) -> dict[int, float]:
    """{open ms: close} of the last n closed Bybit spot 1m candles (newest first in the reply)."""
    end = now_ms // 60_000 * 60_000 - 1  # the open minute is not closed yet
    j = get(BYBIT_KLINES, {"category": "spot", "symbol": SYMBOL[asset], "interval": "1", "end": end, "limit": n})
    return {int(b[0]): float(b[4]) for b in ((j or {}).get("result") or {}).get("list") or []}


class Books:
    """Polymarket market-WS books, one Book per token, rebuilt best-first after each message."""

    def __init__(self):
        self.books: dict[str, Book] = {}
        self._lv: dict[str, tuple[dict, dict]] = {}  # token -> ({bid price: size}, {ask price: size})

    def apply(self, raw: str, recv_ms: int) -> list[tuple]:
        """Apply one WS message. Returns events: ("book", token), ("trade", token, price, size, taker_side, ts_ms),
        ("tick", token, tick_size)."""
        try:
            msg = json.loads(raw)
        except ValueError:  # "PONG"
            return []
        return self.apply_msg(msg, recv_ms)

    def apply_msg(self, msg, recv_ms: int) -> list[tuple]:
        """apply() on an already-parsed message (trader.feedhub parses each upstream frame once)."""
        changed, out = {}, []
        for m in msg if isinstance(msg, list) else [msg]:
            et = m.get("event_type") if isinstance(m, dict) else None
            if et == "book":
                t = m["asset_id"]
                self._lv[t] = ({float(x["price"]): float(x["size"]) for x in m.get("bids", [])},
                               {float(x["price"]): float(x["size"]) for x in m.get("asks", [])})
                changed[t] = True
                if m.get("tick_size"):
                    out.append(("tick", t, float(m["tick_size"])))
            elif et == "price_change":
                for c in m.get("price_changes", []):
                    lv = self._lv.get(c["asset_id"])
                    if lv is None:
                        continue  # no snapshot yet; the server sends one on subscribe
                    levels, p, s = lv[0] if c["side"] == "BUY" else lv[1], float(c["price"]), float(c["size"])
                    if s > 0:
                        levels[p] = s
                    else:
                        levels.pop(p, None)
                    changed[c["asset_id"]] = True
            elif et == "last_trade_price":
                out.append(("trade", m["asset_id"], float(m["price"]), float(m["size"]), m["side"], int(m["timestamp"])))
            elif et == "tick_size_change":
                out.append(("tick", m["asset_id"], float(m["new_tick_size"])))
        for t in changed:
            bids, asks = self._lv[t]
            b = self.books.setdefault(t, Book(t, [], [], recv_ms))
            b.bids, b.asks, b.ts_ms = sorted(bids.items(), reverse=True), sorted(asks.items()), recv_ms
        return [("book", t) for t in changed] + out


class Ref:
    """Binance BTC/ETH reference prices and final print values. Binance spot only; never substitutes a source."""

    def __init__(self, assets=("BTC", "ETH")):
        self.ref = {a: {"price": None, "ts_ms": None, "recv_ms": None, "dvol": None, "dvol_ts_ms": None,
                        "final": {}, "final_1h": {}} for a in assets}
        self._asset = {SYMBOL[a]: a for a in assets}
        self._minute = {}  # asset -> (minute index, last trade price in it), reset on reconnect
        # touch flag: (asset, window start ms) -> {"start_ms", "high", "low"}, shared by every cid of that window
        self.windows: dict[tuple, dict] = {}
        self.track = False  # touch flag on: keep `recent` and extend windows from every kline update
        self.recent = {a: collections.deque(maxlen=120) for a in assets}  # live (open ms, high, low): backfill race
        self.closes: dict[str, dict] = {}  # universe_ext: asset -> {open ms: close}, realized sigma_Q
        self.sigma = None                  # universe_ext: universe.sigma_q_for, set by MarketData

    def close_minute(self, asset: str, open_ms: int, close: float) -> None:
        """Publish a closed 1m candle's close if it is a print: the 12:00 ET candle, or the last minute of an hour."""
        r, t = self.ref[asset], dt.datetime.fromtimestamp(open_ms / 1000, ET)
        if t.hour == 12 and t.minute == 0:
            r["final"][open_ms] = close
        if (open_ms + 60_000) % 3_600_000 == 0:
            r["final_1h"][open_ms + 60_000] = close

    def apply(self, raw: str, recv_ms: int) -> list[str]:
        """Apply one combined-stream message; returns the assets whose price ticked."""
        d = json.loads(raw)
        d = d.get("data", d)
        asset = self._asset.get(d.get("s"))
        if asset is None:
            return []
        if d.get("e") == "aggTrade":
            p, minute = float(d["p"]), int(d["T"]) // 60_000
            prev = self._minute.get(asset)
            if prev and minute > prev[0]:  # first trade of a new minute: the previous minute's close is final
                self.close_minute(asset, prev[0] * 60_000, prev[1])
            self._minute[asset] = (minute, p)
            self.ref[asset].update(price=p, ts_ms=int(d["E"]), recv_ms=recv_ms)
            return [asset]
        if d.get("e") == "kline" and self.track:  # touch: every kline update (open or closed) moves the extremes
            k = d["k"]
            self.extend(asset, int(k["t"]), float(k["h"]), float(k["l"]))
        if d.get("e") == "kline" and d["k"].get("x"):  # the source's own closed candle confirms (and wins)
            self.close_minute(asset, int(d["k"]["t"]), float(d["k"]["c"]))
            if asset in self.closes:
                self.add_close(asset, int(d["k"]["t"]), float(d["k"]["c"]))
        return []

    def extend(self, asset: str, open_ms: int, high: float, low: float) -> None:
        self.recent[asset].append((open_ms, high, low))
        for (a, start), w in self.windows.items():
            if a == asset and open_ms >= start:
                w["high"], w["low"] = max(w["high"], high), min(w["low"], low)

    def add_window(self, asset: str, w: dict) -> None:
        """A backfilled window; live candles that arrived while it was fetched are folded in."""
        for t, h, lo in self.recent[asset]:
            if t >= w["start_ms"]:
                w["high"], w["low"] = max(w["high"], h), min(w["low"], lo)
        self.windows[(asset, w["start_ms"])] = w

    def add_close(self, asset: str, open_ms: int, close: float) -> None:
        c = self.closes.setdefault(asset, {})
        c[open_ms] = close
        for t in [t for t in c if t <= open_ms - VOL_BARS * 60_000]:
            del c[t]
        s = self.sigma(asset, self.ref[asset], [c[t] for t in sorted(c)]) if self.sigma else None
        self.ref[asset]["sigma_q"] = s if s is not None and math.isfinite(s) and s > 0 else None  # NaN never passes

    def reset(self) -> None:
        self._minute.clear()  # a minute spanning a reconnect is published by the kline, not by trades
        # ponytail: a backfill fetched just before a drop and applied after it misses the gap; re-backfill on a timer if seen
        self.windows.clear()  # candles missed while disconnected: touch windows wait for a fresh backfill
        for r in self.ref.values():
            r.pop("touch", None)

    def backfill(self, now_ms: int, get=common.get_json) -> None:
        """Prints missed while not connected: the last two 12:00 ET candles and the last two 1H closes."""
        today = dt.datetime.fromtimestamp(now_ms / 1000, ET).date()
        for asset in self.ref:
            for d in (today - dt.timedelta(days=2), today - dt.timedelta(days=1), today):
                noon = int(dt.datetime.combine(d, dt.time(12), ET).timestamp() * 1000)
                if noon + 60_000 <= now_ms and noon not in self.ref[asset]["final"]:
                    k = get(BINANCE_KLINES, {"symbol": SYMBOL[asset], "interval": "1m", "startTime": noon, "limit": 1})
                    if k and int(k[0][0]) == noon:
                        self.close_minute(asset, noon, float(k[0][4]))
            for k in get(BINANCE_KLINES, {"symbol": SYMBOL[asset], "interval": "1h", "limit": 3}):
                if int(k[6]) < now_ms:
                    self.ref[asset]["final_1h"][int(k[6]) + 1] = float(k[4])


def fetch_dvol(asset: str, now_ms: int, get=common.get_json) -> tuple[float, int] | None:
    data = get(DVOL_URL, {"currency": asset, "start_timestamp": now_ms - 600_000, "end_timestamp": now_ms,
                          "resolution": "60"})["result"]["data"]
    return (float(data[-1][4]), int(data[-1][0])) if data else None


def fetch_usdt_usd(get=common.get_json) -> float:
    """USD per USDT: Kraken USDT/USD mid. The kernel wants it fresh whenever DVOL (a USD index) prices a USDT market."""
    t = get(BASIS_URL, {"pair": "USDTUSD"})["result"]["USDTZUSD"]
    return (float(t["a"][0]) + float(t["b"][0])) / 2


def measure_rtt(n=3, host=CLOB_HOST) -> dict:
    """Median of n GET /time round trips on a warm HTTPS connection (an order client keeps its connection alive)."""
    conn = http.client.HTTPSConnection(host, timeout=10)
    hdr = {"User-Agent": "roster/0.1"}
    try:
        conn.request("GET", "/time", headers=hdr)
        conn.getresponse().read()  # warm-up: the TLS handshake is not part of an order's round trip
        samples = []
        for _ in range(n):
            t0 = time.perf_counter()
            conn.request("GET", "/time", headers=hdr)
            body = conn.getresponse().read()
            samples.append(round(1000 * (time.perf_counter() - t0), 1))
    finally:
        conn.close()
    t = common.now_ms()
    return {"t": t, "rtt_ms": statistics.median(samples), "samples_ms": samples,
            "server_offset_ms": int(body) * 1000 + 500 - t}  # coarse (+-500 ms): /time has 1 s resolution


class MarketData:
    """All live feeds for the trader loop. Callbacks run in the event loop; an exception in one stops the feeds."""
    features, held, sports_events, sports_feeds = frozenset(), None, (), ("espn", "polymarket-ws")  # flags off

    def __init__(self, modes=TARGET_MODES, assets=("BTC", "ETH"), rtt_log=RTT_LOG, features=()):
        self.features = frozenset(features)
        if "sports" in self.features and "sports-pregame" not in modes:
            modes = tuple(modes) + ("sports-pregame",)
        if "universe_ext" in self.features:
            assets = tuple(assets) + tuple(a for a in EXT_ASSETS if a not in assets)
        self.modes, self.rtt_log = modes, rtt_log
        self.sports_maps: dict[str, dict] = {}  # sports: cid -> MarketMap; held: see the module docstring
        self.window_start: dict[str, int] = {}  # touch: cid -> window start ms
        self.markets, self.rows = load_markets(modes, features=self.features)
        self.pm, self.refs = Books(), Ref(assets)
        self.books, self.ref = self.pm.books, self.refs.ref
        self.rtt_ms = DEFAULT_RTT_MS
        self.usdt_usd = None  # USD per USDT (the ladder pricer's basis hook)
        self.ws_tick: dict[str, float] = {}  # cid -> tick size last sent on the WebSocket: fresher than any snapshot
        self.seen: dict[str, int] = {}  # kernel feed name -> local ms of its last message or successful poll
        self.subs: dict[str, frozenset] = {}
        self.counts = collections.Counter()
        self.on_book = self.on_trade = self.on_ref = None
        if "universe_ext" in self.features:
            from trader.growth.universe import sigma_q_for
            self.refs.sigma = sigma_q_for
        self.refs.track = "touch" in self.features
        self._touch_windows()
        self._subscribe(common.now_ms())

    def feed_age_ms(self, now_ms: int) -> dict[str, int]:
        """By the kernel's feed names: polymarket:<mode>, polymarket (the oldest of those), binance:<asset>,
        dvol:<asset>, basis:USDT. A feed never heard from is absent, which the kernel treats as stale."""
        ages = {k: now_ms - v for k, v in self.seen.items()}
        pm = [f"polymarket:{m}" for m in self.modes if self.subs.get(m)]
        if pm and all(k in ages for k in pm):
            ages["polymarket"] = max(ages[k] for k in pm)
        if "sports" in self.features:
            from sports import gamestate
            ages.update(gamestate.feed_age_ms(now_ms, self.sports_feeds))
        return ages

    def set_sports(self, events: list) -> None:
        """sports flag: (re)map sports-pregame rows to these events (GameStates, Kalshi snapshots) into `markets`."""
        if "sports" not in self.features:
            return
        self.sports_events = list(events)
        markets, self.sports_maps = sports_markets(self.rows, self.sports_events)
        self.markets.update(markets)
        self._subscribe(common.now_ms())

    def _touch_windows(self) -> None:
        if "touch" in self.features:
            from trader.growth.universe import window_start_ms
            self.window_start = {c: ws for c, m in self.markets.items() if m.kind.startswith("touch")
                                 and (ws := window_start_ms(self.rows.get(c) or {})) is not None}

    def _touch_fetch(self) -> dict:
        """(asset, start) -> extremes for every touch window not yet backfilled (blocking; runs in a thread)."""
        now, out = common.now_ms(), {}
        for c, start in list(self.window_start.items()):
            m = self.markets.get(c)
            key = (m.asset, start) if m else None
            if m and m.asset in self.ref and key not in self.refs.windows and key not in out and start <= now:
                out[key] = window_extremes(m.asset, start, now)
        return out

    def _touch_apply(self, res: dict) -> None:
        for (a, _), w in res.items():
            if w:
                self.refs.add_window(a, w)
        for c, start in self.window_start.items():
            m = self.markets.get(c)
            if m and (w := self.refs.windows.get((m.asset, start))):
                self.ref[m.asset].setdefault("touch", {})[c] = w

    def _subscribe(self, now_ms: int) -> None:
        self.cid_of = {t: m.cid for m in self.markets.values() for t in (m.token_yes, m.token_no)}
        for mode in self.modes:
            ids = frozenset(t for m in self.markets.values() if m.mode == mode and m.end_ms > now_ms - KEEP_AFTER_END_MS
                            for t in (m.token_yes, m.token_no))
            if ids != self.subs.get(mode):
                self.subs[mode] = ids  # a new object: that mode's WebSocket reconnects with it

    def _on_pm(self, raw: str, now: int) -> None:
        for ev in self.pm.apply(raw, now):
            self.counts[f"pm_{ev[0]}"] += 1
            try:
                if ev[0] == "book" and self.on_book:
                    self.on_book(self.books[ev[1]], now)
                elif ev[0] == "trade" and self.on_trade:
                    self.on_trade(*ev[1:])
                elif ev[0] == "tick" and (cid := self.cid_of.get(ev[1])):
                    self.ws_tick[cid] = ev[2]
                    if self.markets[cid].tick_size != ev[2]:
                        print(f"tick size change {cid}: {self.markets[cid].tick_size} -> {ev[2]}", flush=True)
                        self.markets[cid] = dataclasses.replace(self.markets[cid], tick_size=ev[2])
            except Exception as e:
                raise CallbackError(repr(e)) from e

    async def _pm_ws(self, mode: str) -> None:
        backoff = 1.0
        while True:
            ids = self.subs.get(mode)
            if not ids:
                await asyncio.sleep(5)
                continue
            try:
                # speed runs share the hub's PM stream (same book in every run); paper14's ~380 ladder tokens stay
                # direct: through the hub they tripled its stream to ~60 MB/min and PM dropped it as a slow consumer
                hub = {"feed_hub", "speed_only"} <= self.features
                async with websockets.connect(f"{FEED_HUB}/polymarket" if hub else PM_WS, max_size=None, open_timeout=20) as ws:
                    sub = {"assets_ids": sorted(ids), "type": "market", "custom_feature_enabled": True}
                    if hub:   # the hub's poll mode polls only open markets, and trades only for runs that need them
                        sub["windows"] = {t: window(m) for m in self.markets.values() for t in (m.token_yes, m.token_no) if t in ids}
                        sub["trades"] = "speed_maker" in self.features
                    await ws.send(json.dumps(sub))
                    backoff, last_ping, last_frame = 1.0, 0.0, time.monotonic()
                    while self.subs.get(mode) is ids:
                        if time.monotonic() - last_frame >= SILENT_S:
                            # 10 Oct: after an 8 h sleep the socket came back subscribed to windows that had ended
                            # (the wake-time reload failed on DNS) and stayed silent until a restart
                            print(f"polymarket {mode}: silent {SILENT_S}s; reloading markets and resubscribing", flush=True)
                            self.reload.set()
                            break
                        if time.monotonic() - last_ping >= 10:
                            await ws.send("PING")
                            last_ping = time.monotonic()
                        try:
                            raw = await asyncio.wait_for(ws.recv(), 1)
                        except asyncio.TimeoutError:
                            continue
                        last_frame = time.monotonic()
                        now = self.seen[f"polymarket:{mode}"] = common.now_ms()
                        self._on_pm(raw if isinstance(raw, str) else raw.decode(), now)
                        # recv() returns without yielding while frames are buffered: a burst on one socket would
                        # starve the others (Binance ticks queued for seconds, PM "slow consumer" closes; 8 Oct)
                        await asyncio.sleep(0)
            except (OSError, asyncio.TimeoutError, websockets.WebSocketException) as e:
                print(f"polymarket {mode}: {e!r}; reconnecting in {backoff:.0f}s", flush=True)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

    def _on_bybit(self, raw: str, now: int) -> None:
        """ref_bybit: a Bybit publicTrade message -> ref[asset] (price, Bybit's message time, local receive time).
        shortcut: the kernel's reference feeds stay named "binance:<asset>" (their staleness bound); here they are Bybit."""
        m = json.loads(raw)
        topic = str(m.get("topic", ""))
        asset = BYBIT_ASSETS.get(topic.removeprefix("publicTrade."))
        trades = m.get("data") if topic.startswith("publicTrade") else None
        if not trades or asset not in self.ref:
            return  # subscribe ack, pong
        p = float(trades[-1]["p"])
        if not p > 0:
            return
        self.ref[asset].update(price=p, ts_ms=int(m["ts"]), recv_ms=now)
        self.seen[f"binance:{asset}"] = now
        self.counts[f"tick_{asset}"] += 1
        if self.on_ref:
            try:
                self.on_ref(asset, now)
            except Exception as e:
                raise CallbackError(repr(e)) from e

    async def _bybit_ws(self) -> None:
        backoff = 1.0
        while True:
            try:
                async with websockets.connect(f"{FEED_HUB}/bybit" if "feed_hub" in self.features else BYBIT_WS,
                                              open_timeout=20) as ws:
                    await ws.send(json.dumps({"op": "subscribe", "args": [f"publicTrade.{s}" for s, a in BYBIT_ASSETS.items()
                                                                          if a in self.ref]}))
                    backoff, last_ping = 1.0, time.monotonic()
                    while True:
                        if time.monotonic() - last_ping >= 20:  # Bybit drops a socket without an app-level ping
                            await ws.send(json.dumps({"op": "ping"}))
                            last_ping = time.monotonic()
                        try:
                            raw = await asyncio.wait_for(ws.recv(), 1)
                        except asyncio.TimeoutError:
                            continue
                        self._on_bybit(raw, common.now_ms())
                        await asyncio.sleep(0)  # fairness, as in _pm_ws
            except (OSError, asyncio.TimeoutError, websockets.WebSocketException) as e:
                print(f"bybit: {e!r}; reconnecting in {backoff:.0f}s", flush=True)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

    async def _binance_ws(self) -> None:
        assets = [a for a in self.ref if not ("ref_bybit" in self.features and a in BYBIT_ASSETS.values())]
        if not assets:
            return  # ref_bybit: every reference comes from Bybit
        url = BINANCE_WS + "/".join(f"{SYMBOL[a].lower()}@{s}" for a in assets for s in ("aggTrade", "kline_1m"))
        if "feed_hub" in self.features:
            url = f"{FEED_HUB}/binance"  # the hub relays BTC and ETH aggTrade + kline_1m
        backoff = 1.0
        while True:
            try:
                await asyncio.to_thread(self.refs.backfill, common.now_ms())
            except Exception as e:  # noqa: BLE001 - REST down must not stop the stream; the kline still prints
                print(f"binance backfill: {e!r}", flush=True)
            for a in [a for a in EXT_ASSETS if a in self.ref and self.refs.sigma]:  # universe_ext: realized sigma_Q
                try:
                    closes = await asyncio.to_thread(fetch_closes, a, common.now_ms())
                    self.refs.closes[a] = {}
                    for t in sorted(closes):
                        self.refs.add_close(a, t, closes[t])
                except Exception as e:  # noqa: BLE001 - sigma_q stays as it was (None at start) until it refills
                    print(f"binance closes {a}: {e!r}", flush=True)
            try:
                async with websockets.connect(url, open_timeout=20) as ws:
                    self.refs.reset()
                    backoff = 1.0
                    async for raw in ws:
                        now = common.now_ms()
                        for asset in self.refs.apply(raw, now):
                            self.seen[f"binance:{asset}"] = now
                            self.counts[f"tick_{asset}"] += 1
                            if self.on_ref:
                                try:
                                    self.on_ref(asset, now)
                                except Exception as e:
                                    raise CallbackError(repr(e)) from e
                        await asyncio.sleep(0)  # fairness, as in _pm_ws
            except (OSError, asyncio.TimeoutError, websockets.WebSocketException) as e:
                print(f"binance: {e!r}; reconnecting in {backoff:.0f}s", flush=True)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

    async def _poll(self, every_s: float, name: str, fn, apply, wake: asyncio.Event | None = None) -> None:
        """Run blocking fn in a thread every every_s seconds (RETRY_S after a failure, at once when `wake` is set);
        apply its result in the event loop thread."""
        while True:
            t0, period = time.monotonic(), every_s
            try:
                apply(await asyncio.to_thread(fn))
            except CallbackError:
                raise
            except Exception as e:  # noqa: BLE001 - one missed poll is never a crash; feed_age_ms shows the gap
                print(f"{name}: {e!r}", flush=True)
                period = min(every_s, RETRY_S)  # e.g. DNS not up yet just after a wake from sleep
            left = max(0.0, period - (time.monotonic() - t0))
            if wake is None:
                await asyncio.sleep(left)
                continue
            try:
                await asyncio.wait_for(wake.wait(), left)
            except asyncio.TimeoutError:
                pass
            wake.clear()

    def _set_dvol(self, res: dict) -> None:
        for asset, v in res.items():
            if v:
                self.ref[asset]["dvol"], self.ref[asset]["dvol_ts_ms"] = v
                self.seen[f"dvol:{asset}"] = common.now_ms()

    def _set_basis(self, v: float) -> None:
        self.usdt_usd = v
        self.seen["basis:USDT"] = common.now_ms()

    def _set_rtt(self, m: dict) -> None:
        self.rtt_ms = m["rtt_ms"]
        common.append_jsonl(self.rtt_log, m)

    def _set_markets(self, res) -> None:
        markets, rows = res
        now = common.now_ms()
        self.markets.update({c: dataclasses.replace(m, tick_size=self.ws_tick[c])  # an older snapshot never reverts it
                             if self.ws_tick.get(c, m.tick_size) != m.tick_size else m for c, m in markets.items()})
        # ^ in place: the router and kernel hold this dict
        self.rows.update(rows)
        if self.sports_events:
            sm, self.sports_maps = sports_markets(self.rows, self.sports_events)
            self.markets.update(sm)
        held = self.held() if self.held else {}
        for cid in [c for c, m in self.markets.items() if m.end_ms < now - 6 * 3_600_000
                    and not any(abs(held.get(t, 0.0)) > 1e-9 for t in (m.token_yes, m.token_no))]:
            del self.markets[cid]
        self._touch_windows()
        self._subscribe(now)

    async def run(self, seconds: float | None = None) -> None:
        self.reload = asyncio.Event()
        tasks = [self._pm_ws(m) for m in self.modes] + ([self._bybit_ws()] if "ref_bybit" in self.features else []) + [
                 self._binance_ws(),
                 self._poll(60, "clob_rtt", measure_rtt, self._set_rtt),
                 self._poll(60, "deribit", lambda: {a: fetch_dvol(a, common.now_ms()) for a in self.ref
                                                    if a in DVOL_ASSETS}, self._set_dvol),
                 self._poll(60, "basis", fetch_usdt_usd, self._set_basis),
                 self._poll(REFRESH_S, "markets", lambda: load_markets(self.modes, features=self.features),
                            self._set_markets, self.reload)]
        if "touch" in self.features:
            tasks.append(self._poll(60, "touch", self._touch_fetch, self._touch_apply))
        try:
            await asyncio.wait_for(asyncio.gather(*tasks), seconds)
        except asyncio.TimeoutError:
            pass


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seconds", type=float, default=75)
    a = ap.parse_args()
    t0 = time.time()
    md = MarketData()
    print(f"{len(md.markets)} markets loaded in {time.time() - t0:.0f}s: "
          f"{dict(collections.Counter((m.mode, m.asset, m.kind) for m in md.markets.values()))}")
    sides = collections.Counter()

    def on_trade(token, price, size, side, ts_ms):  # is `side` the taker's side? compare with the book just before
        b = md.books.get(token)
        if b and b.best_bid() is not None and b.best_ask() is not None:
            sides[(side, "at/above mid" if price >= (b.best_bid() + b.best_ask()) / 2 else "below mid")] += 1

    md.on_trade = on_trade
    asyncio.run(md.run(a.seconds))
    now = common.now_ms()
    ok = True
    print(f"\nran {a.seconds:.0f}s; message counts: {dict(md.counts)}")
    for mode in md.modes:
        toks = md.subs.get(mode, frozenset())
        have = [md.books[t] for t in toks if t in md.books and (md.books[t].bids or md.books[t].asks)]
        ages = sorted(now - b.ts_ms for b in have)
        print(f"{mode}: {len(have)}/{len(toks)} tokens with a book; book age median "
              f"{ages[len(ages) // 2] / 1000 if ages else float('nan'):.1f}s, max {ages[-1] / 1000 if ages else 0:.0f}s")
        ok &= bool(have)
    btc5 = sorted((m for m in md.markets.values() if m.event_group.startswith("BTC-5m") and m.end_ms > now),
                  key=lambda m: m.end_ms)
    if btc5 and (b := md.books.get(btc5[0].token_yes)):
        print(f"open BTC 5m '{btc5[0].question}': Up bid {b.best_bid()} ask {b.best_ask()} mid_ex_own {b.mid_ex_own()}")
    for asset, r in md.ref.items():
        print(f"{asset}: {md.counts[f'tick_{asset}']} ticks, last {r['price']} at {r['ts_ms']} (recv lag "
              f"{(r['recv_ms'] or 0) - (r['ts_ms'] or 0)} ms), dvol {r['dvol']}, "
              f"final {{{', '.join(f'{_utc(k)}: {v}' for k, v in sorted(r['final'].items()))}}}, "
              f"final_1h last {max(r['final_1h'].items()) if r['final_1h'] else None}")
        ok &= md.counts[f"tick_{asset}"] > 0
    print(f"rtt to {CLOB_HOST}: {md.rtt_ms} ms (logged to {md.rtt_log})")
    ages = md.feed_age_ms(now)
    print(f"usdt_usd {md.usdt_usd}; feed ages (ms): {ages}")
    missing = [f for f in ("polymarket", "binance:BTC", "binance:ETH", "dvol:BTC", "dvol:ETH", "basis:USDT") if f not in ages]
    if missing:
        print(f"feeds the kernel needs that never arrived: {missing}")
    ok &= not missing
    print(f"trade side vs pre-trade mid: {dict(sides)}")
    print("SMOKE OK" if ok else "SMOKE FAILED: a feed was silent")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
