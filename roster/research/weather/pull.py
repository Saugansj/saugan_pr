"""Weather "NO at 85-97c" test data (23 Oct): settled Polymarket highest-temperature markets and each NO token's hourly
price history, cached under data/research/weather/.

  .venv\\Scripts\\python.exe -m research.weather.pull --days 40      # ~4,000 events, ~60 MB, ~10-20 min

markets.parquet: one row per temperature bucket (cid, event slug, city, day, bucket question, lo/hi bounds, NO token,
won_no, end_ms, volume). prices/<NO token>.json: CLOB prices-history (t s, p) at 60 min fidelity, kept as returned.
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import json
import re

import pandas as pd

import common
from common import DATA

OUT = DATA / "research" / "weather"
GAMMA, CLOB = "https://gamma-api.polymarket.com", "https://clob.polymarket.com"
SLUG = re.compile(r"^highest-temperature-in-(?P<city>.+)-on-(?P<day>[a-z]+-\d+-\d{4})$")


def bounds(q: str) -> tuple[float | None, float | None]:
    """(lo, hi) degrees of a bucket question: 'be 15°C or below' -> (None, 15); 'be 16°C' -> (16, 16);
    'between 60-61°F' -> (60, 61); 'be 26°C or higher' -> (26, None)."""
    n = [float(x) for x in re.findall(r"(-?\d+(?:\.\d+)?)\s*°", q)] or [float(x) for x in re.findall(r"-?\d+", q)][-2:]
    if re.search(r"or below|or lower|or less", q):
        return None, n[-1]
    if re.search(r"or higher|or above|or more", q):
        return n[-1], None
    m = re.search(r"(-?\d+)\s*-\s*(-?\d+)\s*°", q)
    return (float(m[1]), float(m[2])) if m else (n[-1], n[-1])


def events(days: int) -> list[dict]:
    """Per city series: the weather tag list stops at offset ~2,000 (HTTP 422), so it only names the series."""
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).isoformat()
    series = {}
    for off in range(0, 1000, 100):
        for e in common.get_json(f"{GAMMA}/events", {"limit": 100, "offset": off, "closed": "true", "tag_slug": "weather",
                                                     "order": "endDate", "ascending": "false"}):
            if SLUG.match(e.get("slug", "")) and e.get("series"):
                series[e["series"][0]["id"]] = e["series"][0]["slug"]
    out = []
    for sid in series:
        page = common.get_json(f"{GAMMA}/events", {"limit": 100, "series_id": sid, "closed": "true",
                                                   "end_date_min": cutoff, "order": "endDate", "ascending": "false"})
        out += [e for e in page if SLUG.match(e.get("slug", "")) and e["endDate"] >= cutoff]
    return out


def rows(e: dict) -> list[dict]:
    s = SLUG.match(e["slug"])
    out = []
    for m in e.get("markets") or []:
        try:
            tok, px = json.loads(m["clobTokenIds"]), json.loads(m["outcomePrices"])
        except (KeyError, TypeError, ValueError):
            continue
        if not m.get("closed") or sorted(px) != ["0", "1"]:
            continue   # unresolved or voided
        lo, hi = bounds(m["question"])
        out.append({"cid": m["conditionId"], "event": e["slug"], "city": s["city"], "day": s["day"],
                    "question": m["question"], "lo": lo, "hi": hi, "unit": "F" if "°F" in m["question"] else "C",
                    "tail": lo is None or hi is None, "no_token": tok[1], "won_no": px[1] == "1",
                    "end_ms": int(dt.datetime.fromisoformat(e["endDate"].replace("Z", "+00:00")).timestamp() * 1000),
                    "volume": float(m.get("volumeNum") or m.get("volume") or 0)})
    return out


def history(token: str) -> None:
    f = OUT / "prices" / f"{token}.json"
    if f.exists():
        return
    h = common.get_json(f"{CLOB}/prices-history", {"market": token, "interval": "max", "fidelity": 60})
    f.write_text(json.dumps(h.get("history", [])), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=40)
    a = ap.parse_args()
    (OUT / "prices").mkdir(parents=True, exist_ok=True)
    ev = events(a.days)
    df = pd.DataFrame([r for e in ev for r in rows(e)])
    df.to_parquet(OUT / "markets.parquet")
    print(f"{len(ev)} events, {len(df)} resolved buckets, {df.city.nunique()} cities", flush=True)
    with cf.ThreadPoolExecutor(6) as pool:
        for i, _ in enumerate(pool.map(history, df.no_token)):
            if i % 2000 == 0:
                print(f"price histories {i}/{len(df)}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    assert bounds("Will the highest temperature in Jinan be 15°C or below on May 20?") == (None, 15.0)
    assert bounds("Will the highest temperature in Seoul be 16°C on Oct 1?") == (16.0, 16.0)
    assert bounds("Will the highest temperature in NYC be between 60-61°F on Oct 1?") == (60.0, 61.0)
    assert bounds("Will the highest temperature in Tokyo be 26°C or higher on Oct 1?") == (26.0, None)
    main()
