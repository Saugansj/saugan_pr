"""Universe extension (Phase 3, WP3-C; build-plan 3.4; roles 16, 17). Configuration plus pure helpers, no I/O.

Adds SOL/XRP daily ladders (strike + Up/Down), BTC/ETH strikes dated beyond tomorrow inside a moneyness band, and
BTC/ETH touch templates ("will X reach / dip to $H"), each as its own `candidate` entry with its own pre-registration.
The baseline entry is exactly Phase 1's universe. Nothing here is wired; see reports/phase3_universe.md.

Slug shapes (Gamma, checked live 2026-10-01):
  daily strike     solana-above-on-october-2-2026            "Will the price of Solana be above $95 on October 2?"
  daily Up/Down    xrp-up-or-down-on-october-1-2026          "XRP Up or Down on October 1?"
  touch, day       what-price-will-bitcoin-hit-on-october-1-2026         "Will Bitcoin reach $91,000 on October 1?"
  touch, week      what-price-will-solana-hit-september-28-october-4-2026 / ...-hit-september-21-27-2026
  touch, month     what-price-will-xrp-hit-in-october-2026               "Will XRP dip to $1.40 in October?"
  touch, year      what-price-will-bitcoin-hit-before-2027               "... by December 31, 2026?"
SOL/XRP hourly, 4h, 5m and 15m Up/Down and the "price-on" range buckets exist but are not classified (no entry).
Older (closed) touch events had no year in the slug (what-price-will-bitcoin-hit-january-5-11); not classified.

Wiring later:
  - recorder.crawler.SLUG_MODE adopts SLUG_MODE_EXT (via mode_of_ext); the crawler's crypto-term horizon must reach the
    touch windows (a month is ~31 days, a year-end window up to 92 days); marketdata.load_markets falls back to
    market_info_ext; marketdata subscribes to ASSETS[...]["symbol"] and keeps each touch window's running 1m high/low
    from window_start_ms(row).
  - kernel: STRATEGIES[...]["sources"] gains ASSETS[a]["source_id"] for SOL/XRP; the cross-instant stress cap adds XRP.
  - role 16's selector keeps a market only if accepts(entry, ...) for an entry whose REGISTRY name is live in the
    ledger; the scorer clusters evidence with cluster_id. Write REGISTRY and each entry's PREREG once via the Ledger.

Smoke (public GETs only, never run by the tests): python -m trader.growth.universe --smoke
"""
import calendar
import dataclasses
import datetime as dt
import itertools
import math
import re

import numpy as np

from trader.contracts import MarketInfo
from trader.engines.ladder import ET, H_MS, YEAR_H, sigma_q
from trader.marketdata import _utc, iso_ms, market_info, source_id

ASSETS = {  # vol: "dvol" where Deribit publishes a DVOL index (smoke 2026-10-01: BTC, ETH yes; SOL, XRP empty)
    "BTC": {"symbol": "BTCUSDT", "slugs": ("bitcoin", "btc"), "source_id": "binance:BTC/USDT", "vol": "dvol",
            "state": "baseline", "loop_b": False},
    "ETH": {"symbol": "ETHUSDT", "slugs": ("ethereum", "eth"), "source_id": "binance:ETH/USDT", "vol": "dvol",
            "state": "baseline", "loop_b": False},
    "SOL": {"symbol": "SOLUSDT", "slugs": ("solana",), "source_id": "binance:SOL/USDT", "vol": "realized",
            "state": "candidate", "loop_b": True},
    "XRP": {"symbol": "XRPUSDT", "slugs": ("xrp",), "source_id": "binance:XRP/USDT", "vol": "realized",
            "state": "candidate", "loop_b": True},
}
ASSET_OF = {s: a for a, v in ASSETS.items() for s in v["slugs"]}

_D = r"[a-z]+-\d{1,2}-\d{4}"
_TOUCH = re.compile(r"^what-price-will-(?P<a>bitcoin|ethereum|solana|xrp)-hit-(?:on-(?P<m>[a-z]+)-(?P<d>\d{1,2})"
                    r"|in-(?P<mo>[a-z]+)|(?P<m1>[a-z]+)-(?P<d1>\d{1,2})-(?:(?P<m2>[a-z]+)-)?\d{1,2}|before)"
                    r"-(?P<y>\d{4})$")
SLUG_MODE_EXT = (  # (pattern, mode, kind); the first three BTC/ETH shapes are recorder.crawler.SLUG_MODE's
    (re.compile(rf"^(?P<a>bitcoin|ethereum|solana|xrp)-above-on-{_D}$"), "crypto-term", "strike"),
    (re.compile(rf"^(?P<a>bitcoin|ethereum|solana|xrp)-up-or-down-on-{_D}$"), "crypto-term", "updown"),
    (re.compile(rf"^(?P<a>bitcoin|ethereum)-up-or-down-{_D}-\d{{1,2}}(am|pm)-et$"), "crypto-hourly", "updown"),
    (re.compile(r"^(?P<a>btc|eth)-updown-(5m|15m)-\d+$"), "crypto-fast", "updown"),
    (_TOUCH, "crypto-term", "touch"),  # one event holds both touch-up and touch-down markets
)
MONTH = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
CORR_SPLIT = 0.3   # assets settling at one instant are separate evidence clusters only below this residual correlation

VOL_NAME, VOL_VERSION = "universe-vol", 1
VOL_PARAMS = {"vol_bars": 1440, "min_bars": 720}   # realized sigma_Q: last day of 1m closes, at least 12 h of them


def _prereg(eid: str, hypothesis: str, data: str) -> dict:
    return {
        "name": f"universe-{eid}-v1", "strategy": "ladder-maker", "hypothesis": hypothesis,
        "statistic": "per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated "
                     "reward, summed per cluster",
        "cluster": "settlement instant; assets at one instant merged unless residual correlation < 0.3 (cluster_id)",
        "se": "cluster-robust standard error of the mean per cluster",
        "alpha": 0.0228, "pass_rule": "PASS if mean > 2 SE with n >= 60 clusters", "pass_z": 2.0, "n": 60,
        "futility_rule": "stop (FAIL) if mean < -1 SE once n >= 30 clusters", "futility_z": -1.0, "futility_n": 30,
        "data": data, "params": {"entry": eid, "version": 1, "vol": [VOL_NAME, VOL_VERSION]},
    }


_ADD = {"version": 1, "mode": "crypto-term", "state": "candidate", "loop_b": True}
ENTRIES = [  # "asset" is the set of assets the entry covers; Phase 1's ladder trades crypto-term only
    {"id": "baseline", "version": 1, "mode": "crypto-term", "asset": ("BTC", "ETH"), "kinds": ("strike", "updown"),
     "max_tau_h": 24.0, "band_z": None, "state": "baseline", "loop_b": False, "prereg": None},  # Phase 1's universe
    {"id": "sol-ladder", **_ADD, "asset": ("SOL",), "kinds": ("strike", "updown"), "max_tau_h": 24.0, "band_z": None,
     "prereg": _prereg("sol-ladder", "Maker bids on SOL daily strike ladders and Up/Down, priced with realized "
                       "sigma_Q x kappa fitted on recorded SOL data, earn a positive fee-net 5m markout.",
                       "paper then canary fills on SOL daily markets; kappa and vol fitted on recorded SOL data")},
    {"id": "xrp-ladder", **_ADD, "asset": ("XRP",), "kinds": ("strike", "updown"), "max_tau_h": 24.0, "band_z": None,
     "prereg": _prereg("xrp-ladder", "Maker bids on XRP daily strike ladders and Up/Down, priced with realized "
                       "sigma_Q x kappa fitted on recorded XRP data, earn a positive fee-net 5m markout.",
                       "paper then canary fills on XRP daily markets; kappa and vol fitted on recorded XRP data")},
    {"id": "btc-eth-wide-strikes", **_ADD, "asset": ("BTC", "ETH"), "kinds": ("strike",), "max_tau_h": 168.0,
     "band_z": 2.0,
     "prereg": _prereg("btc-eth-wide-strikes", "Maker bids on BTC/ETH strikes dated beyond tomorrow (tau 24-168 h) "
                       "within 2 sigma sqrt(tau) of spot earn a positive fee-net 5m markout.",
                       "fills on markets this entry accepts at tau > 24 h (the baseline covers tau <= 24 h); "
                       "kappa refitted for tau > 24 h")},
    {"id": "btc-eth-touch", **_ADD, "asset": ("BTC", "ETH"), "kinds": ("touch-up", "touch-down"), "max_tau_h": 24.0,
     "band_z": None,
     "prereg": _prereg("btc-eth-touch", "Maker bids on BTC/ETH touch markets priced with the WP3-A one-touch fair "
                       "value earn a positive fee-net 5m markout.",
                       "fills on BTC/ETH touch markets at tau <= 24 h; running 1m high/low since window_start_ms")},
]
REGISTRY = {VOL_NAME: {"version": VOL_VERSION, "state": "candidate", "params": VOL_PARAMS}} | {
    f"universe-{e['id']}": {"version": e["version"], "state": e["state"],
                            "params": {k: v for k, v in e.items() if k not in ("prereg", "state")}}
    for e in ENTRIES if e["loop_b"]}
PREREG = {e["id"]: e["prereg"] for e in ENTRIES if e["prereg"]}


def mode_of_ext(event_slug: str) -> tuple[str, str, str] | None:
    """(mode, asset, kind) from the event slug; kind is "strike", "updown" or "touch" (the market decides up/down)."""
    for rx, mode, kind in SLUG_MODE_EXT:
        if m := rx.match(event_slug):
            return mode, ASSET_OF[m["a"]], kind
    return None


def _touch_source(rules: str, kind: str) -> str:
    """Touch rules phrasing ("Binance 1-minute candle for Bitcoin (BTC/USDT)") that marketdata.source_id misses;
    "" unless the rules name the candle field the kind needs (High for touch-up, Low for touch-down)."""
    m = re.search(r"Binance 1[- ]minute candle for (?:[A-Za-z]+ \()?([A-Z]+)/USDT", rules)
    field = "High" if kind == "touch-up" else "Low"
    return f"binance:{m[1]}/USDT" if m and re.search(rf"\b{field}\b", rules) else ""


def market_info_ext(r: dict) -> MarketInfo | None:
    """MarketInfo for a crawler row of any classified template; None if a needed field is missing (never guessed).
    BTC/ETH strike and Up/Down go through marketdata.market_info unchanged. Other rows reuse its field checks with a
    stand-in BTC slug, then get their own asset, kind, strike, event_group and source_id."""
    c = mode_of_ext(r.get("event_slug") or "")
    if not c:
        return None
    mode, asset, kind = c
    if asset in ("BTC", "ETH") and kind != "touch":
        return market_info(r)
    probe = "bitcoin-above-on-x" if kind == "strike" else "bitcoin-x"
    mi = market_info({**r, "event_slug": probe, "mode": mode})
    if mi is None:
        return None
    rules, strike, group = r.get("rules_text") or "", mi.strike, f"{asset}@{_utc(mi.end_ms)}"
    src = source_id(rules)
    if kind == "touch":
        t = re.search(r"\b(reach|dip to) \$([\d,]+(?:\.\d+)?)", r.get("question") or "")
        if not t:
            return None
        kind = "touch-up" if t[1] == "reach" else "touch-down"
        strike, group = float(t[2].replace(",", "")), f"{asset}-touch@{_utc(mi.end_ms)}"
        src = _touch_source(rules, kind)  # always: also checks the rules name the High/Low field the kind needs
    return dataclasses.replace(mi, asset=asset, kind=kind, strike=strike, event_group=group, source_id=src)


def window_start_ms(r: dict) -> int | None:
    """Touch window start, from the rules when they name one, else 00:00 ET of the first day in the event slug:
    the market's creation (open_time) when price action before it doesn't count, or an explicit ET start
    ("between November 24, 2025, 14:00 and December 31, 2026, 23:59 in the ET timezone"). None if unknown."""
    t = _TOUCH.match(r.get("event_slug") or "")
    if not t or not r.get("end_time"):
        return None
    rules, end = r.get("rules_text") or "", iso_ms(r["end_time"])
    if "creation of this market" in rules:
        return iso_ms(r["open_time"]) if r.get("open_time") else None
    try:
        if x := re.search(r"between ([A-Z][a-z]+) (\d{1,2}), (\d{4}), (\d{1,2}):(\d{2}) and [^.]*? in the ET timezone",
                          rules):
            ms = int(dt.datetime(int(x[3]), MONTH[x[1].lower()], int(x[2]), int(x[4]), int(x[5]), tzinfo=ET).timestamp()
                     * 1000)
            return ms if ms < end else None
        y = int(t["y"])
        if t["m"]:
            day, days = dt.date(y, MONTH[t["m"]], int(t["d"])), 1
        elif t["mo"]:
            day, days = dt.date(y, MONTH[t["mo"]], 1), 31
        elif t["m1"]:  # assumed: the slug's year is the week's end year, so a December start is the year before
            m1 = MONTH[t["m1"]]
            day, days = dt.date(y - bool(t["m2"] and MONTH[t["m2"]] < m1), m1, int(t["d1"])), 7
        else:
            return None  # before-<year> whose rules name no start
    except (KeyError, ValueError):
        return None
    start = int(dt.datetime.combine(day, dt.time(0), ET).timestamp() * 1000)
    # fail closed when the slug's dates don't fit the market's end (e.g. a year convention not seen yet); +1 day: DST
    return start if 0 < end - start <= (days + 1) * 24 * H_MS else None


def sigma_q_for(asset: str, r: dict, closes_1m=None, p: dict = VOL_PARAMS) -> float | None:
    """Annualised sigma_Q: DVOL via ladder.sigma_q, else the sample SD of 1m log returns over the last vol_bars closes
    (365-day year); None when DVOL is missing or fewer than min_bars closes exist."""
    if ASSETS[asset]["vol"] == "dvol":
        return sigma_q(r["dvol"]) if r.get("dvol") else None
    c = np.asarray([] if closes_1m is None else closes_1m, float)[-p["vol_bars"]:]
    if len(c) < max(p["min_bars"], 3):
        return None
    return float(np.diff(np.log(c)).std(ddof=1) * math.sqrt(YEAR_H * 60))


def accepts(entry: dict, m: MarketInfo, S: float | None, sigma: float | None, now_ms: int) -> bool:
    """Mode, asset and kind match, 0 < tau <= max_tau_h, and |ln(K/S)| <= band_z sigma sqrt(tau) when band_z is set
    (fails closed when K, S or sigma is missing)."""
    tau_h = (m.end_ms - now_ms) / H_MS
    if (m.mode != entry["mode"] or m.asset not in entry["asset"] or m.kind not in entry["kinds"]
            or not 0 < tau_h <= entry["max_tau_h"]):
        return False
    if entry["band_z"] is None:
        return True
    if not (m.strike and S and sigma):
        return False
    return abs(math.log(m.strike / S)) <= entry["band_z"] * sigma * math.sqrt(tau_h / YEAR_H)


def cluster_id(m: MarketInfo, corr: dict, assets=tuple(ASSETS)) -> str:
    """Evidence cluster: the settlement instant plus the assets merged with m.asset there. Union-find over asset pairs:
    a pair stays apart only if its measured residual correlation corr[(a, b)] (either order) is below CORR_SPLIT;
    unmeasured (or NaN) pairs merge. `assets` = the assets settling at that instant (default: all, the conservative
    choice). The exposure event_group is unchanged."""
    names = sorted(set(assets) | {m.asset})
    parent = {a: a for a in names}

    def find(a):
        while parent[a] != a:
            a = parent[a]
        return a

    for a, b in itertools.combinations(names, 2):
        rho = corr.get((a, b), corr.get((b, a)))
        if rho is None or not rho < CORR_SPLIT:
            parent[find(a)] = find(b)
    root = find(m.asset)
    return f"{_utc(m.end_ms)}:{'+'.join(a for a in names if find(a) == root)}"


def _smoke() -> None:
    """Public read-only GETs: open SOL/XRP/BTC/ETH events on Gamma, how they classify, and Deribit DVOL per asset."""
    import collections
    import time

    from recorder import crawler
    from trader.marketdata import fetch_dvol

    now = dt.datetime.now(dt.timezone.utc)
    stamp, end_max = now.strftime("%Y-%m-%dT%H%M%SZ"), crawler._iso(now + dt.timedelta(days=100))
    events = {}
    for tag in ("solana", "xrp", "bitcoin", "ethereum"):
        for ev in crawler.gamma_events({"tag_slug": tag, "closed": "false", "end_date_min": crawler._iso(now),
                                        "end_date_max": end_max}):
            events[ev["slug"]] = ev
    print(f"{len(events)} open events (tags solana, xrp, bitcoin, ethereum; ending within 100 days)")
    mismatch = [s for s in events if ASSET_OF.get(s.split("-")[0]) in ("BTC", "ETH")  # touch slugs start "what-"
                and (mode_of_ext(s) or (None,))[0] != crawler.mode_of(s)]
    print(f"BTC/ETH slugs where mode_of_ext's mode != crawler.mode_of: {len(mismatch)} {mismatch[:5]}")
    by, rows_ok, rows_bad, examples = collections.Counter(), collections.Counter(), collections.Counter(), {}
    gaps = collections.Counter()  # MarketInfo built but not tradable as is (no source_id, no touch window start)
    for slug, ev in sorted(events.items()):
        c = mode_of_ext(slug)
        if not c or (c[1] in ("BTC", "ETH") and c[2] != "touch"):
            continue
        by[c] += 1
        for gm in ev.get("markets", []):
            if not gm.get("active") or gm.get("closed"):
                continue
            row = crawler.build_row(c[0], ev, gm, None, stamp)  # Gamma fields only: no CLOB calls in the smoke
            mi = market_info_ext(row)
            key = (c[1], mi.kind if mi else c[2])
            (rows_ok if mi else rows_bad)[key] += 1
            if mi and not mi.source_id:
                gaps[(*key, "no source_id")] += 1
            if mi and mi.kind.startswith("touch") and window_start_ms(row) is None:
                gaps[(*key, "no window start")] += 1
            if mi and mi.kind.startswith("touch") and slug not in examples:
                ws = window_start_ms(row)
                examples[slug] = (_utc(ws) if ws else None, _utc(mi.end_ms), mi.question, mi.strike, mi.source_id,
                                mi.event_group)
            if mi and not mi.kind.startswith("touch") and (c[1], mi.kind) not in examples:
                examples[(c[1], mi.kind)] = (slug, mi.question, mi.strike, mi.source_id, mi.event_group)
    print("new-template events by (mode, asset, kind):")
    for k, n in sorted(by.items()):
        print(f"  {k}: {n}")
    print(f"open markets -> MarketInfo by (asset, kind): {dict(sorted(rows_ok.items()))}")
    print(f"open markets with a missing field (None): {dict(sorted(rows_bad.items()))}")
    print(f"open markets with a gap: {dict(sorted(gaps.items()))}")
    for k, v in examples.items():
        print(f"  {k}: {v}")
    t = int(time.time() * 1000)
    for a, v in ASSETS.items():
        try:
            d = fetch_dvol(a, t)
        except Exception as e:  # noqa: BLE001 - smoke report only
            d = repr(e)[:80]
        print(f"DVOL {a}: {d} (configured vol source: {v['vol']})")


if __name__ == "__main__":
    import sys

    if "--smoke" in sys.argv:
        _smoke()
    else:
        print(__doc__)
