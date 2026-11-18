"""Closed daily BTC/ETH strike ("above $X") and daily Up/Down markets: Gamma catalog, CLOB 1m price history, Data API trades.

1. Catalog: every closed event in the Gamma series below, keeping markets on the Binance 1m-close-at-12:00-ET
   template -> data/history/polymarket/markets.parquet (strike, settlement time, outcome, token ids, rules).
2. Per event (one settlement date): /prices-history for both tokens at fidelity=1 (1 minute, the finest) over the
   market's whole life, and all Data API taker trades -> prices/<event_slug>.parquet and trades/<event_slug>.parquet.
   An event whose two files exist is skipped, so reruns resume. Requests share one global rate cap.

    python -m history.polymarket [--workers 16] [--rps 8] [--limit N]
"""
import argparse
import datetime as dt
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from zoneinfo import ZoneInfo

import pandas as pd

from common import DATA, append_jsonl, get_json, now_ms, sha256_text
from history import save_parquet

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
DAPI = "https://data-api.polymarket.com"
OUT = DATA / "history" / "polymarket"
# Gamma series id -> (asset, mode). 45/42 hold the daily "above ___ on <date>" ladders despite the "weekly" slug.
SERIES = {41: ("BTC", "updown"), 40: ("ETH", "updown"), 45: ("BTC", "strike"), 42: ("ETH", "strike"),
          12043: ("BTC", "strike"), 12044: ("ETH", "strike")}
ET = ZoneInfo("America/New_York")
MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()
MAX_WINDOW = 15 * 86400  # /prices-history rejects a longer startTs..endTs span ("interval is too long")
TRADES_PAGE = 1000
TRADES_MAX_OFFSET = 10000  # Data API: "max historical trades offset of 10000 exceeded"
PRICE_COLS = {"condition_id": "string", "token_id": "string", "outcome": "string", "t": "int64", "p": "float64"}
TRADE_COLS = {"condition_id": "string", "token_id": "string", "outcome": "string", "outcome_index": "int64",
              "side": "string", "price": "float64", "size": "float64", "timestamp": "int64",
              "transaction_hash": "string", "proxy_wallet": "string"}

RPS = 8.0
_lock, _next = threading.Lock(), [0.0]


def polite_get(url: str, params: dict):
    """get_json behind one requests-per-second cap shared by all worker threads."""
    with _lock:
        now = time.monotonic()
        wait = _next[0] - now
        _next[0] = max(_next[0], now) + 1 / RPS
    if wait > 0:
        time.sleep(wait)
    return get_json(url, params, timeout=60)


# ---------- catalog ----------

def parse_strike(question: str) -> float | None:
    """'$104K' -> 104000, '$1,850' -> 1850, '$1300' -> 1300 ('$ETH' is skipped: needs a digit)."""
    m = re.search(r"\$([\d,]+(?:\.\d+)?)\s*([kK])?\b", question)
    if not m:
        return None
    v = float(m.group(1).replace(",", ""))
    return v * 1000 if m.group(2) else v


def settle_date(question: str, end_date: str) -> dt.date:
    """Date named in the question ('on September 29'); the year is the one closest to Gamma's endDate,
    because endDate is sometimes a day or a month off. Falls back to endDate's date."""
    ref = dt.date.fromisoformat(end_date[:10])
    m = re.search(r" on ([A-Za-z]+)\.? (\d{1,2})\b", question)
    if not m or m.group(1)[:3].lower() not in MONTHS:
        return ref
    mon, day, cands = MONTHS.index(m.group(1)[:3].lower()) + 1, int(m.group(2)), []
    for y in (ref.year - 1, ref.year, ref.year + 1):
        try:
            cands.append(dt.date(y, mon, day))
        except ValueError:  # Feb 29 in a non-leap year
            pass
    return min(cands, key=lambda d: abs(d - ref)) if cands else ref


def noon_et_ms(d: dt.date) -> int:
    return int(dt.datetime.combine(d, dt.time(12), ET).timestamp() * 1000)


def winner(outcomes: list, prices: list) -> str | None:
    p = float(prices[0])
    if p > 0.99:
        return outcomes[0]
    if p < 0.01:
        return outcomes[1]
    return "50-50" if abs(p - 0.5) < 0.01 else None


def is_target(mode: str, m: dict) -> bool:
    rules = m.get("description") or ""
    ok = m.get("closed") and m.get("clobTokenIds") and "Binance" in rules and "12:00" in rules
    return bool(ok and (mode == "updown" or "above" in m["question"].lower()))  # strike: skip range buckets


def market_row(series_id: int, ev: dict, m: dict) -> dict:
    asset, mode = SERIES[series_id]
    q, rules = m["question"], m.get("description") or ""
    end = m.get("endDate") or ev.get("endDate")
    d = settle_date(q, end)
    outcomes = json.loads(m["outcomes"])
    prices = json.loads(m.get("outcomePrices") or '["nan", "nan"]')
    yes, no = json.loads(m["clobTokenIds"])
    return {
        "event_slug": ev["slug"], "market_slug": m.get("slug"), "condition_id": m["conditionId"],
        "asset": asset, "mode": mode, "question": q,
        "strike": parse_strike(q) if mode == "strike" else None,
        "settle_date": d.isoformat(), "settle_ts_ms": noon_et_ms(d),
        "start_date": m.get("startDate") or m.get("createdAt"), "end_date": end, "closed_time": m.get("closedTime"),
        "yes_token": yes, "no_token": no, "yes_outcome": outcomes[0], "no_outcome": outcomes[1],
        "yes_final_price": float(prices[0]), "winner": winner(outcomes, prices),
        "uma_status": m.get("umaResolutionStatus"), "volume": m.get("volumeNum"),
        "tick_size": m.get("orderPriceMinTickSize"), "min_size": m.get("orderMinSize"), "neg_risk": m.get("negRisk"),
        "rules": rules, "rules_sha256": sha256_text(rules),
    }


def catalog() -> pd.DataFrame:
    rows = []
    for sid in SERIES:
        off = 0
        while True:
            page = polite_get(GAMMA + "/events", {"series_id": sid, "closed": "true", "limit": 100, "offset": off})
            if not page:
                break
            off += len(page)
            rows += [market_row(sid, ev, m) for ev in page for m in ev.get("markets", [])
                     if is_target(SERIES[sid][1], m)]
    return pd.DataFrame(rows).drop_duplicates("condition_id")


# ---------- per-event download ----------

def ts(s: str) -> int:
    return int(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def windows(start: int, end: int) -> list[tuple[int, int]]:
    return [(s, min(s + MAX_WINDOW, end)) for s in range(start, end, MAX_WINDOW)]


def price_window(m: dict) -> tuple[int, int]:
    """Market start - 1h to close + 1h (close = closedTime, else settlement + 1 day)."""
    has = lambda k: isinstance(m.get(k), str)  # records from a DataFrame carry NaN, not None
    end = ts(m["closed_time"]) if has("closed_time") else m["settle_ts_ms"] // 1000 + 86400
    start = ts(m["start_date"]) if has("start_date") else end - 14 * 86400
    return start - 3600, end + 3600


def fetch_prices(token: str, start: int, end: int) -> list[dict]:
    pts = []
    for s, e in windows(start, end):
        pts += polite_get(CLOB + "/prices-history", {"market": token, "startTs": s, "endTs": e, "fidelity": 1}).get("history", [])
    return pts


def fetch_trades(condition_id: str) -> tuple[list[dict], bool]:
    """All taker trades (the API default takerOnly=true), newest first. True if the offset cap cut it short."""
    rows, off = [], 0
    while True:
        page = polite_get(DAPI + "/trades", {"market": condition_id, "limit": TRADES_PAGE, "offset": off})
        rows += page
        if len(page) < TRADES_PAGE:
            return rows, False
        off += TRADES_PAGE
        if off > TRADES_MAX_OFFSET:
            return rows, True


def fetch_event(slug: str, markets: list[dict], out=OUT) -> str:
    pp, tp = out / "prices" / f"{slug}.parquet", out / "trades" / f"{slug}.parquet"
    if pp.exists() and tp.exists():
        return "skipped"
    prices, trades = [], []
    for m in markets:
        start, end = price_window(m)
        for tok, outcome in ((m["yes_token"], m["yes_outcome"]), (m["no_token"], m["no_outcome"])):
            prices += [(m["condition_id"], tok, outcome, h["t"], h["p"]) for h in fetch_prices(tok, start, end)]
        tr, truncated = fetch_trades(m["condition_id"])
        if truncated:
            append_jsonl(out / "truncated.jsonl", {"condition_id": m["condition_id"], "trades": len(tr), "at_ms": now_ms()})
        trades += [(t["conditionId"], t["asset"], t.get("outcome"), t.get("outcomeIndex", -1), t["side"], t["price"],
                    t["size"], t["timestamp"], t.get("transactionHash"), t.get("proxyWallet")) for t in tr]
    save_parquet(pd.DataFrame(trades, columns=list(TRADE_COLS)).astype(TRADE_COLS), tp)
    p = pd.DataFrame(prices, columns=list(PRICE_COLS)).astype(PRICE_COLS).drop_duplicates(["token_id", "t"])
    save_parquet(p, pp)
    return "downloaded"


def main(workers: int, limit: int | None) -> dict:
    mk = catalog()
    save_parquet(mk, OUT / "markets.parquet")
    events = list(mk.sort_values("settle_date", ascending=False).groupby("event_slug", sort=False))[:limit]
    stats = {"markets": len(mk), "events": len(events), "downloaded": 0, "skipped": 0, "failed": []}
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(fetch_event, slug, g.to_dict("records")): slug for slug, g in events}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                stats[f.result()] += 1
            except Exception as e:  # leave it for the next run; files are only written on success
                stats["failed"].append(f"{futs[f]}: {e!r}")
            if i % 100 == 0:
                print(f"{i}/{len(events)} events done", flush=True)
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--rps", type=float, default=8.0, help="global requests/second cap (default 8)")
    ap.add_argument("--limit", type=int, default=None, help="only the N most recent events (smoke runs)")
    a = ap.parse_args()
    RPS = a.rps
    s = main(a.workers, a.limit)
    print({k: v for k, v in s.items() if k != "failed"}, f"failed={len(s['failed'])}")
    for f in s["failed"][:20]:
        print("FAILED", f)
