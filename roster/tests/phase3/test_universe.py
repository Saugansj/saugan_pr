"""WP3-C: universe extension (C1-C6). Fixtures follow the slug, question and rules shapes Gamma returned on 2026-10-01."""
import dataclasses
import math

import numpy as np
import pytest

from recorder import crawler
from trader.engines.ladder import H_MS, sigma_q
from trader.growth.universe import (ASSETS, ENTRIES, PREREG, REGISTRY, accepts, cluster_id, market_info_ext,
                                    mode_of_ext, sigma_q_for, window_start_ms)
from trader.ledger import Ledger
from trader.marketdata import iso_ms, market_info

STRIKE_RULES = ('This market will resolve to "Yes" if the Binance 1 minute candle for {p}/USDT 12:00 in the ET timezone '
                '(noon) on the date specified in the title has a final "Close" price higher than the price specified.')
UPDOWN_RULES = ('This market will resolve to "Up" if the "Close" price for the Binance 1 minute candle for {p}/USDT '
                "Sep 30 '26 12:00 in the ET timezone (noon) is lower than the final \"Close\" price for the Oct 1 candle.")
TOUCH_UP_DAY = ('This market will immediately resolve to "Yes" if any Binance 1-minute candle for Solana (SOL/USDT) on the '
                'date specified in the title, between 12:00 AM ET and 11:59 PM ET has a final "High" price equal to or '
                'greater than the price specified in the title.')
TOUCH_DOWN_MONTH = ('This market will immediately resolve to "Yes" if any Binance 1 minute candle for XRP/USDT during the '
                    'month specified in the title (from 00:00 AM ET on the first day to 11:59 PM ET on the last), has a '
                    'final Low price equal to or lower than the price specified in the title.')
TOUCH_DOWN_YEAR = ('This market will resolve to "Yes" if any Binance 1 minute candle for BTC/USDT from the creation of this '
                   'market through 11:59 PM ET on the last day of the year specified in the title has a final Low price '
                   "equal to or lower than the price specified in the title. Price action before this market's creation "
                   'will not be considered.')
TOUCH_UP_EXPLICIT = ('This market will immediately resolve to “Yes” if any Binance 1-minute candle for Bitcoin '
                     '(BTC/USDT) between November 24, 2025, 14:00 and December 31, 2026, 23:59 in the ET timezone has a '
                     'final “High” price equal to or greater than the price specified in the title.')


def row(slug, question, rules, end, mode=None, **kw):
    """Crawler-shaped row (recorder.crawler.build_row fields the trader reads)."""
    return {"mode": mode, "event_slug": slug, "condition_id": "0x" + slug[:20], "question": question,
            "yes_token_id": "111", "no_token_id": "222", "rules_text": rules, "rules_sha256": "ab" * 32,
            "fee_schedule": {"exponent": 1, "rate": 0.07, "takerOnly": True, "rebateRate": 0.2}, "fees_enabled": True,
            "tick_size": 0.01, "min_order_size": 5, "neg_risk": False, "open_time": None, "end_time": end, **kw}


# ---------- C1: slug classification ----------

def test_snapshot_slugs_match_crawler_mode():
    snap = crawler.latest_snapshot()
    if snap is None:
        pytest.skip("no data/markets/*.jsonl snapshot")
    slugs = {r["event_slug"] for r in crawler.read_snapshot(snap)}
    assert slugs
    for s in slugs:
        c = mode_of_ext(s)
        assert (c[0] if c else None) == crawler.mode_of(s), s
        if c:
            assert c[1] in ("BTC", "ETH") and c[2] in ("strike", "updown"), s


@pytest.mark.parametrize("slug,want", [
    ("solana-above-on-october-2-2026", ("crypto-term", "SOL", "strike")),
    ("xrp-above-on-october-2-2026", ("crypto-term", "XRP", "strike")),
    ("solana-up-or-down-on-october-1-2026", ("crypto-term", "SOL", "updown")),
    ("xrp-up-or-down-on-october-1-2026", ("crypto-term", "XRP", "updown")),
    ("bitcoin-above-on-october-2-2026", ("crypto-term", "BTC", "strike")),
    ("ethereum-up-or-down-october-1-2026-3am-et", ("crypto-hourly", "ETH", "updown")),
    ("btc-updown-5m-1790841600", ("crypto-fast", "BTC", "updown")),
    ("what-price-will-bitcoin-hit-on-october-1-2026", ("crypto-term", "BTC", "touch")),
    ("what-price-will-ethereum-hit-in-october-2026", ("crypto-term", "ETH", "touch")),
    ("what-price-will-solana-hit-september-28-october-4-2026", ("crypto-term", "SOL", "touch")),
    ("what-price-will-solana-hit-september-21-27-2026", ("crypto-term", "SOL", "touch")),
    ("what-price-will-xrp-hit-before-2027", ("crypto-term", "XRP", "touch")),
    # not classified: no entry covers them, or not a crypto price template
    ("sol-updown-5m-1790841600", None), ("xrp-updown-4h-1790841600", None),
    ("solana-up-or-down-october-1-2026-3am-et", None), ("solana-price-on-october-2-2026", None),
    ("what-price-will-ethbtc-hit-september-28-october-4-2026", None), ("will-solana-hit-100-or-200-first", None),
    ("what-price-will-bitcoin-hit-january-5-11", None), ("dogecoin-above-on-october-2-2026", None),
    ("arsenal-vs-chelsea-2026-10-04", None), ("", None),
])
def test_mode_of_ext_fixtures(slug, want):
    assert mode_of_ext(slug) == want
    if want and want[1] in ("BTC", "ETH") and want[2] != "touch":
        assert crawler.mode_of(slug) == want[0]


# ---------- C2: MarketInfo for the new templates ----------

@pytest.mark.parametrize("r,kind,strike,asset,group,src", [
    (row("solana-above-on-october-2-2026", "Will the price of Solana be above $95 on October 2?",
         STRIKE_RULES.format(p="SOL"), "2026-10-02T16:00:00Z"),
     "strike", 95.0, "SOL", "SOL@2026-10-02T16:00Z", "binance:SOL/USDT"),
    (row("xrp-above-on-october-1-2026", "Will the price of XRP be above $1.00 on October 1?",
         STRIKE_RULES.format(p="XRP"), "2026-10-01T16:00:00Z"),
     "strike", 1.0, "XRP", "XRP@2026-10-01T16:00Z", "binance:XRP/USDT"),
    (row("xrp-up-or-down-on-october-1-2026", "XRP Up or Down on October 1?", UPDOWN_RULES.format(p="XRP"),
         "2026-10-01T16:00:00Z"),
     "updown", None, "XRP", "XRP@2026-10-01T16:00Z", "binance:XRP/USDT"),
    (row("solana-up-or-down-on-october-1-2026", "Solana Up or Down on October 1?", UPDOWN_RULES.format(p="SOL"),
         "2026-10-01T16:00:00Z"),
     "updown", None, "SOL", "SOL@2026-10-01T16:00Z", "binance:SOL/USDT"),
    (row("what-price-will-solana-hit-on-october-1-2026", "Will Solana reach $140 on October 1?", TOUCH_UP_DAY,
         "2026-10-02T04:00:00Z"),
     "touch-up", 140.0, "SOL", "SOL-touch@2026-10-02T04:00Z", "binance:SOL/USDT"),
    (row("what-price-will-xrp-hit-in-october-2026", "Will XRP dip to $1.40 in October?", TOUCH_DOWN_MONTH,
         "2026-11-01T04:00:00Z"),
     "touch-down", 1.4, "XRP", "XRP-touch@2026-11-01T04:00Z", "binance:XRP/USDT"),
    (row("what-price-will-bitcoin-hit-before-2027", "Will Bitcoin dip to $60,000 by December 31, 2026?",
         TOUCH_DOWN_YEAR, "2027-01-01T05:00:00Z"),
     "touch-down", 60000.0, "BTC", "BTC-touch@2027-01-01T05:00Z", "binance:BTC/USDT"),
])
def test_market_info_ext_new_templates(r, kind, strike, asset, group, src):
    m = market_info_ext(r)
    assert (m.kind, m.strike, m.asset, m.event_group, m.source_id) == (kind, strike, asset, group, src)
    assert m.mode == "crypto-term" and m.end_ms == iso_ms(r["end_time"]) and m.fee_rate == 0.07
    assert (m.cid, m.token_yes, m.token_no, m.min_size, m.tick_size) == (r["condition_id"], "111", "222", 5.0, 0.01)


def test_market_info_ext_none_on_missing_fields():
    sol = row("solana-above-on-october-2-2026", "Will the price of Solana be above $95 on October 2?",
              STRIKE_RULES.format(p="SOL"), "2026-10-02T16:00:00Z")
    touch = row("what-price-will-solana-hit-on-october-1-2026", "Will Solana reach $140 on October 1?", TOUCH_UP_DAY,
                "2026-10-02T04:00:00Z")
    assert market_info_ext(sol) and market_info_ext(touch)
    for base in (sol, touch):
        for f in ("yes_token_id", "no_token_id", "end_time", "tick_size", "min_order_size", "fee_schedule"):
            assert market_info_ext({**base, f: None}) is None, f
    assert market_info_ext({**sol, "question": "Will the price of Solana be high on October 2?"}) is None
    assert market_info_ext({**touch, "question": "Will Solana hit a new high on October 1?"}) is None
    assert market_info_ext({**sol, "event_slug": "dogecoin-above-on-october-2-2026"}) is None
    # touch-up whose rules only name the Low field: no source, so the kernel's provenance check refuses it
    assert market_info_ext({**touch, "rules_text": TOUCH_UP_DAY.replace("High", "Low")}).source_id == ""
    assert market_info_ext({**touch, "rules_text": ""}).source_id == ""


def test_btc_eth_rows_match_marketdata():
    for slug, q, rules in (("bitcoin-above-on-october-2-2026", "Will the price of Bitcoin be above $74,000 on October 2?",
                            STRIKE_RULES.format(p="BTC")),
                           ("ethereum-up-or-down-on-october-2-2026", "Ethereum Up or Down on October 2?",
                            UPDOWN_RULES.format(p="ETH"))):
        r = row(slug, q, rules, "2026-10-02T16:00:00Z", mode="crypto-term")
        assert market_info_ext(r) == market_info(r) is not None
    snap = crawler.latest_snapshot()
    for r in crawler.read_snapshot(snap) if snap else []:
        if mode_of_ext(r["event_slug"]):
            assert market_info_ext(r) == market_info(r), r["event_slug"]


def test_window_start_ms():
    def ws(slug, end, **kw):
        return window_start_ms(row(slug, "", "", end, **kw))
    assert ws("what-price-will-solana-hit-on-october-1-2026", "2026-10-02T04:00:00Z") == iso_ms("2026-10-01T04:00:00Z")
    # month: 00:00 ET on the 1st, not the (later) market creation
    assert ws("what-price-will-xrp-hit-in-october-2026", "2026-11-01T04:00:00Z",
              open_time="2026-10-01T05:07:26Z") == iso_ms("2026-10-01T04:00:00Z")
    assert ws("what-price-will-solana-hit-september-28-october-4-2026",
              "2026-10-05T04:00:00Z") == iso_ms("2026-09-28T04:00:00Z")
    assert ws("what-price-will-solana-hit-september-21-27-2026", "2026-09-28T04:00:00Z") == iso_ms("2026-09-21T04:00:00Z")
    assert ws("what-price-will-bitcoin-hit-december-28-january-3-2027",
              "2027-01-04T05:00:00Z") == iso_ms("2026-12-28T05:00:00Z")  # EST
    # creation clause: the market's own start; without it, unknown
    yr = row("what-price-will-bitcoin-hit-before-2027", "", TOUCH_DOWN_YEAR, "2027-01-01T05:00:00Z",
             open_time="2026-06-08T04:57:16.471Z")
    assert window_start_ms(yr) == iso_ms("2026-06-08T04:57:16.471Z")
    assert window_start_ms({**yr, "open_time": None}) is None
    assert window_start_ms({**yr, "rules_text": ""}) is None
    # explicit ET start in the rules (older year-end markets): 14:00 EST = 19:00Z
    explicit = {**yr, "rules_text": TOUCH_UP_EXPLICIT}
    assert window_start_ms(explicit) == iso_ms("2025-11-24T19:00:00Z")
    assert window_start_ms({**explicit, "rules_text": TOUCH_UP_EXPLICIT.replace("ET timezone", "UTC timezone")}) is None
    assert market_info_ext({**explicit, "question": "Will Bitcoin reach $150,000 by December 31, 2026?"}).source_id \
        == "binance:BTC/USDT"   # curly quotes around High
    # fail closed: slug dates that don't fit the end (another year convention), no end, not a touch slug
    assert ws("what-price-will-bitcoin-hit-december-28-january-3-2026", "2027-01-04T05:00:00Z") is None
    assert ws("what-price-will-solana-hit-on-october-1-2026", "2026-10-09T04:00:00Z") is None
    assert ws("what-price-will-solana-hit-on-october-1-2026", None) is None
    assert ws("solana-above-on-october-2-2026", "2026-10-02T16:00:00Z") is None


# ---------- C3: sigma_Q ----------

def gbm_closes(sigma, n, seed, s0=150.0):
    dt_y = 1 / (365 * 1440)
    r = np.random.default_rng(seed).normal(-sigma ** 2 * dt_y / 2, sigma * math.sqrt(dt_y), n - 1)
    return s0 * np.exp(np.concatenate([[0.0], np.cumsum(r)]))


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_realized_sigma_on_synthetic_gbm(seed):
    c = gbm_closes(0.6, 1441, seed)  # one day of 1m bars
    assert abs(sigma_q_for("SOL", {}, c) / 0.6 - 1) < 0.10
    # only the last vol_bars closes count: a 3x calmer old segment doesn't move it
    old = gbm_closes(0.2, 2000, seed + 10, s0=c[0])
    assert abs(sigma_q_for("XRP", {}, np.concatenate([old, c[1:]])) / 0.6 - 1) < 0.10


def test_sigma_q_none_and_dvol():
    assert sigma_q_for("SOL", {}, gbm_closes(0.6, 719, 4)) is None   # fewer than min_bars
    assert sigma_q_for("SOL", {}, None) is None
    assert sigma_q_for("SOL", {}, gbm_closes(0.6, 720, 4)) is not None
    assert sigma_q_for("BTC", {"dvol": 36.66}) == sigma_q(36.66) == pytest.approx(0.3666)
    assert sigma_q_for("ETH", {"dvol": 0.5056}, gbm_closes(2.0, 2000, 5)) == sigma_q(0.5056)  # closes ignored
    assert sigma_q_for("BTC", {}) is None and sigma_q_for("ETH", {"dvol": None}) is None
    assert {a: v["vol"] for a, v in ASSETS.items()} == {"BTC": "dvol", "ETH": "dvol", "SOL": "realized",
                                                       "XRP": "realized"}


# ---------- C4: accepts ----------

NOW = iso_ms("2026-10-01T16:00:00Z")
E = {e["id"]: e for e in ENTRIES}


BASE = market_info(row("bitcoin-above-on-october-2-2026", "Will the price of Bitcoin be above $60,000 on October 2?",
                       STRIKE_RULES.format(p="BTC"), "2026-10-02T16:00:00Z", mode="crypto-term"))


def mi(asset, kind, tau_h, strike=None):
    return dataclasses.replace(BASE, asset=asset, kind=kind, strike=strike, end_ms=NOW + int(tau_h * H_MS))


def test_baseline_entry():
    b = E["baseline"]
    for a in ("BTC", "ETH"):
        for k in ("strike", "updown"):
            assert accepts(b, mi(a, k, 24, 60000), 60000, 0.4, NOW)
            assert accepts(b, mi(a, k, 0.1, 60000), 60000, 0.4, NOW)
            assert not accepts(b, mi(a, k, 24.01, 60000), 60000, 0.4, NOW)
            assert not accepts(b, mi(a, k, 0, 60000), 60000, 0.4, NOW)
            assert not accepts(b, mi(a, k, -1, 60000), 60000, 0.4, NOW)
    for a in ("SOL", "XRP"):
        assert not accepts(b, mi(a, "strike", 12, 150), 150, 0.6, NOW)
    for k in ("touch-up", "touch-down"):
        assert not accepts(b, mi("BTC", k, 12, 70000), 60000, 0.4, NOW)
    for mode in ("crypto-hourly", "crypto-fast"):   # Phase 1's ladder trades crypto-term only
        assert not accepts(b, dataclasses.replace(mi("BTC", "updown", 0.5), mode=mode), None, None, NOW)
    assert (b["asset"], b["kinds"], b["max_tau_h"], b["band_z"]) == (("BTC", "ETH"), ("strike", "updown"), 24.0, None)


def test_band_z_entry():
    w = E["btc-eth-wide-strikes"]
    S, sig, tau = 60000.0, 0.6, 72.0
    band = w["band_z"] * sig * math.sqrt(tau / (365 * 24))           # 2 x 0.6 x sqrt(72/8760) = 0.1088
    inside, outside = S * math.exp(0.95 * band), S * math.exp(1.05 * band)
    assert accepts(w, mi("BTC", "strike", tau, inside), S, sig, NOW)
    assert accepts(w, mi("ETH", "strike", tau, S * math.exp(-0.95 * band)), S, sig, NOW)
    assert not accepts(w, mi("BTC", "strike", tau, outside), S, sig, NOW)
    assert not accepts(w, mi("BTC", "strike", tau, S * math.exp(-1.05 * band)), S, sig, NOW)
    assert not accepts(w, mi("BTC", "strike", tau, inside), S, None, NOW)       # no sigma: fail closed
    assert not accepts(w, mi("BTC", "strike", tau, inside), None, sig, NOW)
    assert not accepts(w, mi("BTC", "updown", tau), S, sig, NOW)
    assert not accepts(w, mi("BTC", "strike", 169, S), S, sig, NOW)
    assert accepts(E["sol-ladder"], mi("SOL", "updown", 20), None, None, NOW)
    assert not accepts(E["sol-ladder"], mi("XRP", "updown", 20), None, None, NOW)
    assert accepts(E["btc-eth-touch"], mi("ETH", "touch-down", 20, 2000), None, None, NOW)
    assert not accepts(E["btc-eth-touch"], mi("SOL", "touch-down", 20, 100), None, None, NOW)


# ---------- C5: additions are candidates with their own pre-registration ----------

PREREG_FIELDS = {"name", "hypothesis", "statistic", "cluster", "se", "alpha", "pass_z", "n", "futility_z",
                 "futility_n", "data", "params"}


def test_additions_are_candidates_with_own_prereg(tmp_path):
    adds = [e for e in ENTRIES if e["id"] != "baseline"]
    assert {e["id"] for e in adds} == {"sol-ladder", "xrp-ladder", "btc-eth-wide-strikes", "btc-eth-touch"}
    names = [e["prereg"]["name"] for e in adds]
    assert len(set(names)) == len(names) == 4
    for e in adds:
        assert e["state"] == "candidate" and e["loop_b"] is True
        p = e["prereg"]
        assert PREREG_FIELDS <= p.keys() and all(p[f] not in (None, "") for f in PREREG_FIELDS), e["id"]
        assert p["params"]["entry"] == e["id"] and p["n"] >= p["futility_n"] > 0 and p["pass_z"] > 0
        assert REGISTRY[f"universe-{e['id']}"]["state"] == "candidate"
    assert {a: (v["state"], v["loop_b"]) for a, v in ASSETS.items() if a in ("SOL", "XRP")} == {
        "SOL": ("candidate", True), "XRP": ("candidate", True)}
    assert REGISTRY["universe-vol"]["state"] == "candidate"
    assert "universe-baseline" not in REGISTRY and set(PREREG) == {e["id"] for e in adds}
    led = Ledger(path=tmp_path / "t.db")     # the registry and pre-registrations are writable as they are
    for name, v in REGISTRY.items():
        led.register(name, v["version"], v["params"])
    for p in PREREG.values():
        led.preregister(p)
        assert led.preregistration(p["name"])["name"] == p["name"]


# ---------- C6: evidence clusters ----------

def test_cluster_id():
    at = lambda a, end=NOW: dataclasses.replace(BASE, asset=a, end_ms=end)   # noqa: E731
    three = ("BTC", "ETH", "SOL")
    assert len({cluster_id(at(a), {}, three) for a in three}) == 1
    assert cluster_id(at("SOL"), {}) == cluster_id(at("XRP"), {}) == cluster_id(at("BTC"), {})  # all unmeasured
    split = {("SOL", "BTC"): 0.1, ("ETH", "SOL"): 0.2}
    assert cluster_id(at("SOL"), split, three) != cluster_id(at("BTC"), split, three) == cluster_id(at("ETH"), split,
                                                                                                    three)
    assert cluster_id(at("SOL"), split, three).endswith(":SOL")
    half = {("SOL", "BTC"): 0.1, ("SOL", "ETH"): 0.3}
    assert len({cluster_id(at(a), half, three) for a in three}) == 1
    assert cluster_id(at("BTC"), {}, three) != cluster_id(at("BTC", NOW + 5 * 60_000), {}, three)
    assert cluster_id(at("BTC"), {("BTC", "ETH"): float("nan")}, ("BTC", "ETH")) == cluster_id(at("ETH"), {},
                                                                                               ("BTC", "ETH"))
