"""WW-B wiring: market data and execution (B1-B5). Fixtures only, no network."""
import dataclasses
import datetime as dt
import hashlib
import json

import pytest

from recorder import crawler
from trader import marketdata as md
from trader.contracts import Book, Intent, MarketInfo
from trader.router import PaperRouter

WE, LOAD = md.window_extremes, md.load_markets  # the real ones, before a test replaces them

NOW = dt.datetime(2026, 10, 7, 12, 0, tzinfo=dt.timezone.utc)
NOW_MS = int(NOW.timestamp() * 1000)
STAMP = NOW.strftime("%Y-%m-%dT%H%M%SZ")
FS = {"exponent": 1, "rate": 0.07, "takerOnly": True, "rebateRate": 0.2}
STRIKE = ('This market will resolve to "Yes" if the Binance 1 minute candle for {p}/USDT 12:00 in the ET timezone '
          '(noon) on the date specified in the title has a final "Close" price higher than the price specified.')
UPDOWN = ('This market will resolve to "Up" if the "Close" price for the Binance 1 minute candle for {p}/USDT '
          "Oct 7 '26 12:00 in the ET timezone (noon) is lower than the final \"Close\" price for the Oct 8 candle.")
HOURLY = "This market will resolve to \"Up\" if the BTC/USDT 1 hour candle on Binance closes above its open."
FAST = ("... The resolution source for this market is information from Chainlink, specifically the BTC/USD TWAP data "
        "stream.")
TOUCH = ('This market will immediately resolve to "Yes" if any Binance 1-minute candle for {n} ({p}/USDT) during the '
         'month specified in the title (from 00:00 AM ET on the first day to 11:59 PM ET on the last), has a final '
         '"{f}" price equal to or {cmp} than the price specified in the title.')
TOUCH_DAY = ('This market will immediately resolve to "Yes" if any Binance 1-minute candle for Bitcoin (BTC/USDT) on '
             'the date specified in the title, between 12:00 AM ET and 11:59 PM ET has a final "High" price equal to or '
             'greater than the price specified in the title.')
TOUCH_YEAR = ('This market will resolve to "Yes" if any Binance 1 minute candle for SOL/USDT from the creation of this '
              'market through 11:59 PM ET on the last day of the year specified in the title has a final Low price '
              "equal to or lower than the price specified in the title. Price action before this market's creation "
              'will not be considered.')
SPORT = "This market refers to 90 minutes of regular play plus stoppage time."
_n = iter(range(10_000))


def gm(question, end, rules, slug=None, start="2026-09-20T00:00:00Z", **kw):
    k = next(_n)
    return {"conditionId": f"0x{k:04d}", "question": question, "slug": slug or f"m{k}", "endDate": end,
            "clobTokenIds": json.dumps([f"{k}1", f"{k}2"]), "outcomes": json.dumps(["Yes", "No"]),
            "description": rules, "feeSchedule": FS, "feesEnabled": True, "orderPriceMinTickSize": 0.01,
            "orderMinSize": 5, "negRisk": False, "active": True, "closed": False, "startDate": start, **kw}


def ev(slug, end, *markets):
    return {"slug": slug, "endDate": end, "markets": list(markets)}


FAST_S = NOW_MS // 1000 + 60
EVENTS = {
    "bitcoin": [
        ev("bitcoin-above-on-october-8-2026", "2026-10-08T16:00:00Z",
           gm("Will the price of Bitcoin be above $120,000 on October 8?", "2026-10-08T16:00:00Z", STRIKE.format(p="BTC")),
           gm("Will the price of Bitcoin be above $122,000 on October 8?", "2026-10-08T16:00:00Z", STRIKE.format(p="BTC"))),
        ev("bitcoin-above-on-october-20-2026", "2026-10-20T16:00:00Z",  # past the 8-day horizon: never crawled
           gm("Will the price of Bitcoin be above $120,000 on October 20?", "2026-10-20T16:00:00Z", STRIKE.format(p="BTC"))),
        ev("bitcoin-up-or-down-october-7-2026-3pm-et", "2026-10-07T20:00:00Z",
           gm("Bitcoin Up or Down - October 7, 3PM ET", "2026-10-07T20:00:00Z", HOURLY)),
        ev(f"btc-updown-5m-{FAST_S}", "2026-10-07T12:06:00Z",
           gm("Bitcoin Up or Down - October 7, 8:01AM-8:06AM ET", "2026-10-07T12:06:00Z", FAST)),
        ev("what-price-will-bitcoin-hit-in-october-2026", "2026-11-01T04:00:00Z",  # 25 days out: touch horizon only
           gm("Will Bitcoin reach $130,000 in October?", "2026-11-01T04:00:00Z",
              TOUCH.format(n="Bitcoin", p="BTC", f="High", cmp="greater")),
           gm("Will Bitcoin dip to $100,000 in October?", "2026-11-01T04:00:00Z",
              TOUCH.format(n="Bitcoin", p="BTC", f="Low", cmp="lower"))),
        ev("what-price-will-bitcoin-hit-on-october-8-2026", "2026-10-09T04:00:00Z",
           gm("Will Bitcoin reach $125,000 on October 8?", "2026-10-09T04:00:00Z", TOUCH_DAY)),
    ],
    "ethereum": [
        ev("ethereum-up-or-down-on-october-8-2026", "2026-10-08T16:00:00Z",
           gm("Ethereum Up or Down on October 8?", "2026-10-08T16:00:00Z", UPDOWN.format(p="ETH"))),
    ],
    "solana": [
        ev("solana-above-on-october-8-2026", "2026-10-08T16:00:00Z",
           gm("Will the price of Solana be above $200 on October 8?", "2026-10-08T16:00:00Z", STRIKE.format(p="SOL"))),
        ev("what-price-will-solana-hit-before-2027", "2027-01-01T05:00:00Z",
           gm("Will Solana dip to $100 by December 31, 2026?", "2027-01-01T05:00:00Z", TOUCH_YEAR,
              start="2026-09-01T15:30:00Z")),
    ],
    "xrp": [
        ev("xrp-up-or-down-on-october-8-2026", "2026-10-08T16:00:00Z",
           gm("XRP Up or Down on October 8?", "2026-10-08T16:00:00Z", UPDOWN.format(p="XRP"))),
    ],
    "10188": [
        ev("epl-ars-che-2026-10-10", "2026-10-10T16:00:00Z",
           gm("Will Arsenal win on 2026-10-10?", "2026-10-10T16:00:00Z", SPORT, slug="epl-ars-che-2026-10-10-ars",
              sportsMarketType="moneyline", eventStartTime="2026-10-10T14:00:00Z"),
           gm("Will Arsenal vs. Chelsea end in a draw?", "2026-10-10T16:00:00Z", SPORT,
              slug="epl-ars-che-2026-10-10-draw", sportsMarketType="moneyline", eventStartTime="2026-10-10T14:00:00Z"),
           gm("Will Chelsea win on 2026-10-10?", "2026-10-10T16:00:00Z", SPORT, slug="epl-ars-che-2026-10-10-che",
              sportsMarketType="moneyline", eventStartTime="2026-10-10T14:00:00Z")),
    ],
}


def fake_gamma(params):
    evs = EVENTS.get(params.get("tag_slug") or params.get("series_id"), [])
    return [e for e in evs if params["end_date_min"] <= e["endDate"] <= params["end_date_max"]]


def crawl_rows(monkeypatch, modes=crawler.MODES, **kw):
    monkeypatch.setattr(crawler, "gamma_events", fake_gamma)
    return [crawler.build_row(mode, e, g, None, STAMP) for mode, e, g in crawler.candidates(modes, NOW, **kw)]


def digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def snapshot_dir(tmp_path, rows):
    p = tmp_path / f"{STAMP}.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return tmp_path


def b1_state(tmp_path, monkeypatch, rows):
    """Market set, raw rows and books as the flags-off market data builds them from a fixture snapshot."""
    def no_crawl(*a, **k):
        raise AssertionError("fresh snapshot: no crawl")
    d = snapshot_dir(tmp_path, rows)
    markets, raw = md.load_markets(markets_dir=d, crawl=no_crawl, now_s=NOW.timestamp())
    monkeypatch.setattr(md, "load_markets", lambda *a, **k: (dict(markets), dict(raw)))
    monkeypatch.setattr(md.common, "now_ms", lambda: NOW_MS)
    m = md.MarketData(rtt_log=tmp_path / "rtt.jsonl")
    toks = sorted(t for mi in markets.values() for t in (mi.token_yes, mi.token_no))
    msg = [{"event_type": "book", "asset_id": t, "bids": [{"price": "0.40", "size": "10"}, {"price": "0.45", "size": "5"}],
            "asks": [{"price": "0.55", "size": "7"}], "tick_size": "0.01"} for t in toks]
    m._on_pm(json.dumps(msg), NOW_MS)
    m._on_pm(json.dumps({"event_type": "price_change", "price_changes": [
        {"asset_id": toks[0], "price": "0.46", "size": "3", "side": "BUY"}]}), NOW_MS + 5)
    return {"markets": [dataclasses.asdict(markets[c]) for c in sorted(markets)],
            "rows": sorted(raw), "subs": {k: sorted(v) for k, v in m.subs.items()},
            "books": {t: (b.bids, b.asks, b.ts_ms) for t, b in sorted(m.books.items())},
            "ref": sorted(m.ref), "feeds": m.feed_age_ms(NOW_MS + 10)}


# Captured from the audited Phase 1 code (before any WW-B edit) on these fixtures.
GOLD_B1 = "d4d3794a1c16d20bac6538751fa70e154aad999ec0180499c8dbdf7f63f212ea"
GOLD_B5 = "83798ff73659166732783b0709685b13f29a2f32be8d82c44afa3f45434706a7"


EXT = {"what-price-will-bitcoin-hit-in-october-2026", "what-price-will-bitcoin-hit-on-october-8-2026",
       "solana-above-on-october-8-2026", "what-price-will-solana-hit-before-2027", "xrp-up-or-down-on-october-8-2026"}


def snapshot_rows(monkeypatch):
    """The flags-off crawl plus the touch and SOL/XRP rows a flagged crawl adds to the shared snapshot."""
    ext = [crawler.build_row("crypto-term", e, g, None, STAMP) for evs in EVENTS.values() for e in evs
           if e["slug"] in EXT for g in e["markets"]]
    return crawl_rows(monkeypatch) + ext


# ---------- B5: crawler changes are additive ----------

def test_b5_crawler_flags_off_rows_unchanged(monkeypatch):
    rows = crawl_rows(monkeypatch)
    assert sorted(r["event_slug"] for r in rows) == sorted(
        ["bitcoin-above-on-october-8-2026"] * 2 + ["bitcoin-up-or-down-october-7-2026-3pm-et", f"btc-updown-5m-{FAST_S}",
         "ethereum-up-or-down-on-october-8-2026"] + ["epl-ars-che-2026-10-10"] * 3)
    assert digest(rows) == GOLD_B5
    assert crawl_rows(monkeypatch, features=()) == rows
    assert crawl_rows(monkeypatch, features=("sports", "live_risk")) == rows  # other flags never touch the crawler


# ---------- B1: flags off, same market set and books ----------

def test_b1_marketdata_flags_off_unchanged(tmp_path, monkeypatch):
    s = b1_state(tmp_path, monkeypatch, snapshot_rows(monkeypatch))
    assert len(s["markets"]) == 4 and s["ref"] == ["BTC", "ETH"]
    assert digest(s) == GOLD_B1


def market_data(tmp_path, monkeypatch, rows, features=()):
    """MarketData over a fixture snapshot (no crawl, no network), at NOW."""
    d = snapshot_dir(tmp_path, rows)
    monkeypatch.setattr(md.common, "now_ms", lambda: NOW_MS)
    def load(modes, features=()):
        return LOAD(modes, markets_dir=d, crawl=lambda *a, **k: pytest.fail("no crawl"), now_s=NOW.timestamp(),
                    features=features)
    monkeypatch.setattr(md, "load_markets", load)
    return md.MarketData(rtt_log=tmp_path / "rtt.jsonl", features=features)


# ---------- B2: held markets stay until redeemed ----------

def test_b2_held_market_past_end_stays_until_position_is_zero(tmp_path, monkeypatch):
    m = market_data(tmp_path, monkeypatch, snapshot_rows(monkeypatch))
    old = dataclasses.replace(next(iter(m.markets.values())), cid="0xold", token_yes="oy", token_no="on",
                              end_ms=NOW_MS - 7 * 3_600_000)  # ended 7 h ago
    m._set_markets(({"0xold": old}, {}))  # a reload that still lists it
    assert "0xold" not in m.markets       # held = None: Phase 1's plain 6 h drop
    pos = {"on": 5.0}
    m.held = lambda: pos
    m._set_markets(({"0xold": old}, {}))
    assert "0xold" in m.markets
    m._set_markets(({}, {}))              # gone from the snapshot, still held: stays
    assert "0xold" in m.markets
    pos["on"] = 0.0                       # redeemed
    m._set_markets(({}, {}))
    assert "0xold" not in m.markets


# ---------- B3: touch and SOL/XRP rows with their flags on ----------

def test_b3_crawler_adds_each_template_only_with_its_flag(monkeypatch):
    base = {r["condition_id"] for r in crawl_rows(monkeypatch)}

    def added(f):
        return {r["event_slug"] for r in crawl_rows(monkeypatch, features=f) if r["condition_id"] not in base}
    assert added(("touch",)) == {"what-price-will-bitcoin-hit-in-october-2026",
                                 "what-price-will-bitcoin-hit-on-october-8-2026"}
    assert added(("universe_ext",)) == {"solana-above-on-october-8-2026", "xrp-up-or-down-on-october-8-2026"}
    assert added(("touch", "universe_ext")) == EXT  # SOL touch needs both; the Oct 20 strike stays past 8 days
    assert {r["mode"] for r in crawl_rows(monkeypatch, features=("touch", "universe_ext"))
            if r["event_slug"] in EXT} == {"crypto-term"}


def test_b3_marketdata_maps_touch_and_sol_xrp_rows(tmp_path, monkeypatch):
    rows = snapshot_rows(monkeypatch)
    m = market_data(tmp_path, monkeypatch, rows, features=("touch", "universe_ext"))
    got = {(x.asset, x.kind, x.strike, x.event_group, x.source_id) for x in m.markets.values()}
    assert got >= {
        ("BTC", "touch-up", 130000.0, "BTC-touch@2026-11-01T04:00Z", "binance:BTC/USDT"),
        ("BTC", "touch-down", 100000.0, "BTC-touch@2026-11-01T04:00Z", "binance:BTC/USDT"),
        ("BTC", "touch-up", 125000.0, "BTC-touch@2026-10-09T04:00Z", "binance:BTC/USDT"),
        ("SOL", "touch-down", 100.0, "SOL-touch@2027-01-01T05:00Z", "binance:SOL/USDT"),
        ("SOL", "strike", 200.0, "SOL@2026-10-08T16:00Z", "binance:SOL/USDT"),
        ("XRP", "updown", None, "XRP@2026-10-08T16:00Z", "binance:XRP/USDT")}
    assert len(m.markets) == 4 + 6 and sorted(m.ref) == ["BTC", "ETH", "SOL", "XRP"]
    month = next(c for c, x in m.markets.items() if x.strike == 130000.0)
    sol = next(c for c, x in m.markets.items() if x.asset == "SOL" and x.kind == "touch-down")
    assert m.window_start[month] == md.iso_ms("2026-10-01T04:00:00Z")  # 00:00 ET on the 1st
    assert m.window_start[sol] == md.iso_ms("2026-09-01T15:30:00Z")    # "from the creation of this market"
    t = market_data(tmp_path, monkeypatch, rows, features=("touch",))  # one flag: the other template stays out
    assert {x.asset for x in t.markets.values()} == {"BTC", "ETH"} and sorted(t.ref) == ["BTC", "ETH"]
    u = market_data(tmp_path, monkeypatch, rows, features=("universe_ext",))
    assert not any(x.kind.startswith("touch") for x in u.markets.values()) and len(u.markets) == 6


def test_load_markets_crawls_when_a_flagged_template_is_missing(tmp_path, monkeypatch):
    calls, full = [], snapshot_rows(monkeypatch)

    def crawl(modes, features=()):
        calls.append(features)
        return [full]
    d = snapshot_dir(tmp_path, crawl_rows(monkeypatch))  # the recorder's flags-off crawl: no touch rows
    md.load_markets(markets_dir=d, crawl=crawl, now_s=NOW.timestamp())
    assert calls == []
    markets, _ = md.load_markets(markets_dir=d, crawl=crawl, now_s=NOW.timestamp(), features=("touch", "sports"))
    assert calls == [("touch",)] and any(x.kind == "touch-up" for x in markets.values())


# ---------- touch: running 1m high/low per window ----------

def minute_bars(t0, t1):
    """Deterministic 1m candles [open ms, o, h, l, c] from t0 to t1."""
    out = []
    for t in range(t0, t1, 60_000):
        k = t // 60_000
        mid = 100_000 + 500 * ((k * 7919) % 97 - 48) / 48
        out.append([t, mid, mid + (k % 5) * 10, mid - (k % 3) * 10, mid + 1])
    return out


def fake_klines(bars):
    def get(url, p):
        lo, hi = p.get("startTime", 0), p.get("endTime", 2**62)
        if p["interval"] == "1m":
            sel = [b for b in bars if lo <= b[0] <= hi]
            return sel[:p["limit"]] if "startTime" in p else sel[-p["limit"]:]
        hours = {}
        for b in bars:
            hours.setdefault(b[0] // 3_600_000 * 3_600_000, []).append(b)
        return [[h, v[0][1], max(x[2] for x in v), min(x[3] for x in v), v[-1][4]]
                for h, v in sorted(hours.items()) if h >= lo][:p["limit"]]
    return get


def test_window_extremes_match_the_1m_candles_since_the_start():
    start = NOW_MS - 30 * 3_600_000 - 29 * 60_000 - 20_000  # mid-hour and mid-minute
    bars = minute_bars(NOW_MS - 40 * 3_600_000, NOW_MS)
    w = md.window_extremes("BTC", start, NOW_MS, get=fake_klines(bars))
    inside = [b for b in bars if b[0] >= -(-start // 60_000) * 60_000]
    assert (w["high"], w["low"]) == (max(b[2] for b in inside), min(b[3] for b in inside))
    assert md.window_extremes("BTC", NOW_MS + 60_000, NOW_MS, get=fake_klines(bars)) is None  # not started


def kline(t, h, lo, closed=False):
    return json.dumps({"data": {"e": "kline", "s": "BTCUSDT", "k": {"t": t, "h": str(h), "l": str(lo), "c": str(h),
                                                                   "x": closed}}})


def test_touch_ref_running_high_low_and_fail_closed():
    from trader.growth import touch
    r = md.Ref()
    tm = MarketInfo("0xt", "a", "b", "crypto-term", "q", "h", 0.01, 5, 0.07, False, NOW_MS + 24 * 3_600_000,
                    "BTC-touch@x", asset="BTC", strike=101_000.0, kind="touch-up", source_id="binance:BTC/USDT")
    r.ref["BTC"].update(price=100_000.0, dvol=50.0)
    params = touch.REGISTRY["touch"]["params"]
    assert "err" in touch.touch_fair(tm, md.touch_ref(r.ref, tm), NOW_MS, params)  # no window yet: fail closed
    r.track = True  # the touch flag
    r.apply(kline(NOW_MS - 120_000, 100_400, 99_000), NOW_MS)   # arrives while the backfill is in flight
    start = NOW_MS - 3_600_000
    r.add_window("BTC", {"start_ms": start, "high": 100_200.0, "low": 99_500.0})  # backfill done; recent folded in
    r.ref["BTC"]["touch"] = {"0xt": r.windows[("BTC", start)]}
    assert (md.touch_ref(r.ref, tm)["high"], md.touch_ref(r.ref, tm)["low"]) == (100_400.0, 99_000.0)
    r.apply(kline(start - 60_000, 102_000, 90_000), NOW_MS)     # a candle before the window never counts
    r.apply(kline(NOW_MS, 100_900, 99_800), NOW_MS)
    f = touch.touch_fair(tm, md.touch_ref(r.ref, tm), NOW_MS, params)
    assert "err" not in f and not f["touched"] and 0 < f["f"] < 1 and md.touch_ref(r.ref, tm)["high"] == 100_900.0
    r.apply(kline(NOW_MS + 60_000, 101_000, 100_000, True), NOW_MS)
    assert touch.touch_fair(tm, md.touch_ref(r.ref, tm), NOW_MS, params)["touched"]
    r.reset()  # a reconnect: candles may have been missed, so the window waits for a fresh backfill
    assert "err" in touch.touch_fair(tm, md.touch_ref(r.ref, tm), NOW_MS, params) and not r.windows


def test_marketdata_touch_backfill_publishes_per_cid(tmp_path, monkeypatch):
    m = market_data(tmp_path, monkeypatch, snapshot_rows(monkeypatch), features=("touch",))
    bars = minute_bars(md.iso_ms("2026-10-01T04:00:00Z") - 3_600_000, NOW_MS)
    monkeypatch.setattr(md, "window_extremes", lambda a, s, now: WE(a, s, now, get=fake_klines(bars)))
    m._touch_apply(m._touch_fetch())
    month = {c for c, x in m.markets.items() if x.kind.startswith("touch") and x.end_ms == md.iso_ms("2026-11-01T04:00:00Z")}
    assert set(m.ref["BTC"]["touch"]) == month and len(month) == 2  # the Oct 8 window has not started: absent
    month = next(c for c, x in m.markets.items() if x.strike == 130000.0)
    assert len(m.window_start) == 3
    inside = [b for b in bars if b[0] >= md.iso_ms("2026-10-01T04:00:00Z")]
    assert m.ref["BTC"]["touch"][month]["high"] == max(b[2] for b in inside)
    assert m._touch_fetch() == {}  # backfilled once


# ---------- universe_ext: realized sigma_Q for SOL/XRP ----------

def test_sigma_q_from_closes_and_nan_guard():
    from trader.growth.universe import sigma_q_for
    r = md.Ref(("BTC", "ETH", "SOL"))
    r.sigma = sigma_q_for
    bars = minute_bars(NOW_MS - 1440 * 60_000, NOW_MS)
    for b in bars[:700]:
        r.add_close("SOL", b[0], b[4] / 500)
    assert r.ref["SOL"]["sigma_q"] is None  # under min_bars
    for b in bars[700:]:
        r.add_close("SOL", b[0], b[4] / 500)
    s = r.ref["SOL"]["sigma_q"]
    assert s and s > 0 and len(r.closes["SOL"]) == 1440
    r.add_close("SOL", NOW_MS, float("nan"))
    assert r.ref["SOL"]["sigma_q"] is None  # NaN in, None out (never NaN)
    closes = md.fetch_closes("SOL", NOW_MS + 30_000, get=fake_klines(bars))
    assert len(closes) == 1440 and max(closes) == bars[-1][0]


# ---------- sports: MarketInfo from odds.map_markets, feed ages ----------

def test_sports_markets_and_feed_age(tmp_path, monkeypatch):
    from sports import gamestate, odds
    start = md.iso_ms("2026-10-10T14:00:00Z")
    events = [{"league": "E0", "home": "Arsenal", "away": "Chelsea", "start_ms": start,
               "event_key": odds.event_key("E0", "Arsenal", "Chelsea", start)}]
    rows = snapshot_rows(monkeypatch)
    off = market_data(tmp_path, monkeypatch, rows)
    off.set_sports(events)
    assert len(off.markets) == 4 and "sports" not in off.feed_age_ms(NOW_MS)  # flag off: nothing changes
    m = market_data(tmp_path, monkeypatch, rows, features=("sports",))
    assert "sports-pregame" in m.modes and len(m.markets) == 4
    m.set_sports(events)
    sp = [x for x in m.markets.values() if x.mode == "sports-pregame"]
    assert len(sp) == 3 and {x.event_group for x in sp} == {events[0]["event_key"]}
    assert {mm["outcome"] for mm in m.sports_maps.values()} == {"H", "D", "A"}
    assert all(x.fee_rate == 0.07 and x.end_ms == md.iso_ms("2026-10-10T16:00:00Z") for x in sp)
    assert len(m.subs["sports-pregame"]) == 6
    assert md.sports_markets(m.rows, [])[0] == {}  # no event: never guessed
    monkeypatch.setattr(gamestate, "LAST_RECV", {"espn": NOW_MS - 2000})
    assert "sports" not in m.feed_age_ms(NOW_MS)  # the WS feed never reported: stale (fail closed)
    m.sports_feeds = ("espn",)
    assert m.feed_age_ms(NOW_MS)["sports"] == 2000


# ---------- B4: router, own orders never share displayed liquidity ----------

RM = MarketInfo("c1", "Y", "N", "crypto-fast", "q", "h", 0.01, 5, 0.07, False, NOW_MS + 10**8, "BTC-5m@x",
                asset="BTC", kind="updown")


def order(price, size, kind, side="BUY"):
    return Intent("t", "c1", "Y", side, price, size, kind, NOW_MS + 10**7, 0.5, "test")


def bk(bids, asks, t):
    return Book("Y", bids, asks, t)


OPS = {
    "two_takers": [("book", bk([(0.50, 100)], [(0.52, 50), (0.53, 20)], NOW_MS)),
                   ("submit", order(0.53, 40, "taker"), NOW_MS + 100), ("submit", order(0.53, 40, "taker"), NOW_MS + 100),
                   ("poll", NOW_MS + 1000), ("book", bk([(0.50, 100)], [(0.52, 50)], NOW_MS + 1100)),
                   ("submit", order(0.52, 40, "taker"), NOW_MS + 1200), ("poll", NOW_MS + 2000)],
    "two_makers": [("book", bk([(0.50, 100)], [(0.52, 50)], NOW_MS)),
                   ("submit", order(0.50, 10, "maker"), NOW_MS), ("submit", order(0.50, 10, "maker"), NOW_MS),
                   ("trade", "Y", 0.50, 110, "SELL", NOW_MS + 500), ("trade", "Y", 0.50, 105, "SELL", NOW_MS + 600),
                   ("trade", "Y", 0.50, 5, "SELL", NOW_MS + 700)],
}


def drive(sim, ops):
    fills = []
    for op in ops:
        if op[0] == "book":
            fills += sim.on_book(op[1], op[1].ts_ms)
        elif op[0] == "submit":
            sim.submit(op[1], op[2])
        elif op[0] == "trade":
            fills += sim.on_trade(*op[1:])
        else:
            fills += sim.poll(op[1])
    return [(f.order_id, f.price, f.size, f.ts_ms) for f in fills]


def fee(C, p, rate):
    return C * rate * p * (1 - p)


@pytest.mark.parametrize("case", sorted(OPS))
def test_b4_own_orders_use_displayed_liquidity_once(case, tmp_path):
    from learning.replay.fills import FillModel
    on = drive(PaperRouter({"c1": RM}, 200, journal=tmp_path / "on.jsonl", fee=fee, liquidity_once=True), OPS[case])
    assert on == drive(FillModel({"c1": RM}, 200, fee=fee), OPS[case])  # paper == strict replay
    off = drive(PaperRouter({"c1": RM}, 200, journal=tmp_path / "off.jsonl", fee=fee), OPS[case])
    ids = list(dict.fromkeys(f[0] for f in on))
    if case == "two_takers":
        assert [(f[1], f[2]) for f in on] == [(0.52, 40.0), (0.52, 10.0), (0.53, 20.0), (0.52, 40.0)]
        assert sum(f[2] for f in off[:2]) == 80.0  # flag off (Phase 1): both took the same 50 displayed at 0.52
    else:  # 110 shares: 100 ahead of both, 10 for the older maker; the younger one needs 100 + 10 more
        assert [(f[0], f[3]) for f in on] == [(ids[0], NOW_MS + 500), (ids[1], NOW_MS + 700)]
        assert [f[3] for f in off] == [NOW_MS + 500, NOW_MS + 500]  # flag off (Phase 1): one trade filled both


def test_maker_realism_cancel_reaches_the_venue_after_half_the_round_trip(tmp_path):
    """16 Oct: an instant paper cancel flattered makers that defend by cancelling; with maker_realism a trade that
    reaches the venue before the cancel still fills."""
    for realism, want in ((False, 0), (True, 1)):
        r = PaperRouter({"c1": RM}, 200, journal=tmp_path / f"c{realism}.jsonl", fee=fee, liquidity_once=True,
                        maker_realism=realism)
        r.on_book(bk([(0.50, 0)], [(0.52, 50)], NOW_MS), NOW_MS)
        o = r.submit(order(0.50, 10, "maker"), NOW_MS)
        r.cancel(o.order_id, NOW_MS + 1000)
        fills = r.on_trade("Y", 0.49, 20, "SELL", NOW_MS + 1050)          # inside rtt/2 = 100 ms of the cancel
        assert len(fills) == want
        r.poll(NOW_MS + 1200)
        assert r.state.orders[o.order_id].status in ("cancelled", "filled") and not r.open_orders()


def test_maker_realism_mirrors_complement_prints_to_the_resting_bid(tmp_path):
    """A taker buying Up at 0.55 can fill our Down bid at 0.45; the venue prints it on the Up token only."""
    import types
    from trader import loop as L
    calls = []
    fake = types.SimpleNamespace(features={"maker_realism"}, maker_tokens={"N"}, _comp={"Y": "N", "N": "Y"},
                                 now=lambda: NOW_MS, fills=lambda f, now: None,
                                 router=types.SimpleNamespace(poll=lambda now: [],
                                                              on_trade=lambda *a: calls.append(a) or []))
    L.Trader.on_trade(fake, "Y", 0.55, 7.0, "BUY", NOW_MS)
    assert calls == [("N", 0.45, 7.0, "SELL", NOW_MS)]                    # mirrored: price 1 - p, taker side flipped
    calls.clear()
    fake.features = set()
    L.Trader.on_trade(fake, "Y", 0.55, 7.0, "BUY", NOW_MS)
    assert calls == []                                                     # flag off: only same-token prints, as before
