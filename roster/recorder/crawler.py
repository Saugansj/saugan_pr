"""Market crawler (task 0.2, role 07): Gamma + CLOB market info for the target modes.

Writes a dated JSONL snapshot to data/markets/<UTC stamp>.jsonl and appends rules-hash and
tick-size changes against the previous snapshot to data/markets/changes.jsonl. Snapshots older than
KEEP_DAYS are deleted (about 0.9 MB each, 24 a day from the recorder; the home PC's nightly rsync keeps them all).

Run from the roster folder:  python -m recorder.crawler [--fast]
"""
import argparse
import datetime as dt
import json
import re
import sys
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor

import common

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
MARKETS_DIR = common.DATA / "markets"
MODES = ("crypto-term", "crypto-hourly", "sports-pregame", "crypto-fast")
DEFAULT_MODES = MODES[:3]  # crypto-fast only for the latency test (--fast)
WATCHED = ("rules_sha256", "tick_size")  # changes logged between snapshots
# Gamma series ids of the leagues football-data.co.uk covers (E0, SP1, D1, I1, F1).
SOCCER_SERIES = {"10188": "epl", "10193": "la-liga", "10194": "bundesliga", "10203": "serie-a", "10195": "ligue-1"}
HORIZON_H = {"crypto-term": 8 * 24, "crypto-hourly": 48, "sports-pregame": 14 * 24, "crypto-fast": 2}
KEEP_DAYS = 30  # same as the Parquet hot window in compact.py
AFTER_END_H = 3  # keep ended-but-unresolved markets: the post-close window (task 0.11) is 0-120 min after the print
# Wiring flags (trader/features.py): "touch" adds the touch templates, "universe_ext" the SOL/XRP ladders. Off = Phase 1.
TOUCH_HORIZON_H = 100 * 24  # monthly touch windows end ~31 days out, year-end ones up to ~92
EXT_TAGS = ("solana", "xrp")

_D = r"[a-z]+-\d{1,2}-\d{4}"
SLUG_MODE = (
    (re.compile(rf"^(bitcoin|ethereum)-(above|up-or-down)-on-{_D}$"), "crypto-term"),  # daily 12:00 ET
    (re.compile(rf"^(bitcoin|ethereum)-up-or-down-{_D}-\d{{1,2}}(am|pm)-et$"), "crypto-hourly"),
    (re.compile(r"^(btc|eth)-updown-(5m|15m)-\d+$"), "crypto-fast"),
)


def mode_of(event_slug: str) -> str | None:
    """Crypto mode from the event slug (Gamma tags are inconsistent: daily strikes are tagged 'weekly')."""
    return next((mode for rx, mode in SLUG_MODE if rx.match(event_slug)), None)


def classify(event_slug: str, features=()) -> tuple[str, int] | None:
    """(mode, horizon h). Without the touch/universe_ext flags exactly mode_of; with them also WP3-C's templates
    (trader.growth.universe.SLUG_MODE_EXT), each only when its own flag is on (SOL/XRP touch needs both)."""
    if mode := mode_of(event_slug):
        return mode, HORIZON_H[mode]
    if not {"touch", "universe_ext"} & set(features):
        return None
    from trader.growth.universe import mode_of_ext  # lazy: universe imports trader.marketdata, which imports us
    c = mode_of_ext(event_slug)
    if not c or (c[2] == "touch" and "touch" not in features) or (c[1] in ("SOL", "XRP") and "universe_ext" not in features):
        return None
    return c[0], TOUCH_HORIZON_H if c[2] == "touch" else HORIZON_H[c[0]]


def _iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def gamma_events(params: dict) -> list[dict]:
    out = []
    for offset in range(0, 2100, 100):  # Gamma rejects offset > 2000
        page = common.get_json(f"{GAMMA}/events", {**params, "limit": 100, "offset": offset})
        out += page
        if len(page) < 100:
            break
    return out


def candidates(modes, now: dt.datetime, features=()) -> list[tuple[str, dict, dict]]:
    """(mode, event, market) for every open market of the enabled modes inside each mode's horizon (see classify)."""
    found, since = [], _iso(now - dt.timedelta(hours=AFTER_END_H))
    crypto = [m for m in modes if m != "sports-pregame"]
    if crypto:
        horizon = max([HORIZON_H[m] for m in crypto] + [TOUCH_HORIZON_H] * ("touch" in features and "crypto-term" in crypto))
        for tag in ("bitcoin", "ethereum") + EXT_TAGS * ("universe_ext" in features):
            for ev in gamma_events({"tag_slug": tag, "closed": "false", "end_date_min": since,
                                    "end_date_max": _iso(now + dt.timedelta(hours=horizon))}):
                c = classify(ev["slug"], features)
                if c and c[0] in crypto and ev["endDate"] <= _iso(now + dt.timedelta(hours=c[1])):
                    found += [(c[0], ev, m) for m in ev.get("markets", [])]
    if "sports-pregame" in modes:
        end = _iso(now + dt.timedelta(hours=HORIZON_H["sports-pregame"]))
        for sid in SOCCER_SERIES:
            for ev in gamma_events({"series_id": sid, "closed": "false", "end_date_min": since, "end_date_max": end}):
                found += [("sports-pregame", ev, m) for m in ev.get("markets", [])
                          if m.get("sportsMarketType") == "moneyline"]
    out, seen = [], set()  # the bitcoin and ethereum tags overlap on a few events
    for c in found:
        cid = c[2]["conditionId"]
        if c[2].get("active") and not c[2].get("closed") and cid not in seen:
            seen.add(cid)
            out.append(c)
    return out


def _first(*xs):
    return next((x for x in xs if x is not None), None)


def build_row(mode: str, ev: dict, gm: dict, clob: dict | None, stamp: str) -> dict:
    """One market row. None only where neither Gamma nor CLOB exposes the field."""
    clob = clob or {}
    rates = clob.get("rewards") or {}
    tokens = clob.get("tokens") or [{"token_id": t, "outcome": o} for t, o in
                                    zip(json.loads(gm.get("clobTokenIds") or "[]"), json.loads(gm.get("outcomes") or "[]"))]
    tokens += [{}] * (2 - len(tokens))
    rules = gm.get("description") or ""
    return {
        "snapshot": stamp, "mode": mode, "event_slug": ev["slug"], "market_slug": gm.get("slug"),
        "condition_id": gm["conditionId"], "question": gm.get("question"),
        "yes_token_id": tokens[0].get("token_id"), "no_token_id": tokens[1].get("token_id"),
        "outcomes": [tokens[0].get("outcome"), tokens[1].get("outcome")],
        "rules_text": rules, "rules_sha256": common.sha256_text(rules),
        "fee_schedule": gm.get("feeSchedule"), "fee_type": gm.get("feeType"), "fees_enabled": gm.get("feesEnabled"),
        "maker_base_fee": _first(clob.get("maker_base_fee"), gm.get("makerBaseFee")),
        "taker_base_fee": _first(clob.get("taker_base_fee"), gm.get("takerBaseFee")),
        "tick_size": _first(clob.get("minimum_tick_size"), gm.get("orderPriceMinTickSize")),
        "min_order_size": _first(clob.get("minimum_order_size"), gm.get("orderMinSize")),
        "neg_risk": _first(clob.get("neg_risk"), gm.get("negRisk")),
        "neg_risk_augmented": ev.get("negRiskAugmented"), "neg_risk_other": gm.get("negRiskOther"),
        "reward_min_size": _first(rates.get("min_size"), gm.get("rewardsMinSize")),
        "reward_max_spread": _first(rates.get("max_spread"), gm.get("rewardsMaxSpread")),
        # CLOB rewards.rates: null = no pool today (0.0); None only if the CLOB call failed.
        "reward_daily_rate": float(sum(r["rewards_daily_rate"] for r in rates.get("rates") or [])) if clob else None,
        "holding_rewards_enabled": gm.get("holdingRewardsEnabled"),
        "seconds_delay": clob.get("seconds_delay"),
        "open_time": gm.get("startDate"),
        "event_start_time": _first(clob.get("game_start_time"), gm.get("eventStartTime")),
        "end_time": gm.get("endDate"),
        "accepting_orders": _first(clob.get("accepting_orders"), gm.get("acceptingOrders")),
        "clob_ok": bool(clob),
    }


def diff(prev: list[dict], cur: list[dict], fields=WATCHED) -> list[dict]:
    """Changes in watched fields for markets present in both snapshots."""
    old = {r["condition_id"]: r for r in prev}
    return [{"condition_id": r["condition_id"], "market_slug": r.get("market_slug"), "field": f,
             "old": old[r["condition_id"]].get(f), "new": r.get(f)}
            for r in cur if r["condition_id"] in old for f in fields
            if old[r["condition_id"]].get(f) != r.get(f)]


def read_snapshot(path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def latest_snapshot(out_dir=MARKETS_DIR):
    snaps = sorted(out_dir.glob("*Z.jsonl"))
    return snaps[-1] if snaps else None


def save(rows: list[dict], stamp: str, out_dir=MARKETS_DIR, keep_days=KEEP_DAYS):
    """Write the snapshot, log watched-field changes against the previous one, expire old snapshots."""
    prev = latest_snapshot(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path, tmp = out_dir / f"{stamp}.jsonl", out_dir / f"{stamp}.tmp"
    tmp.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows), encoding="utf-8")
    tmp.replace(path)  # atomic: a kill mid-write never leaves a truncated snapshot for recorder.run() to seed from
    changes = diff(read_snapshot(prev), rows) if prev else []
    for c in changes:
        common.append_jsonl(out_dir / "changes.jsonl", {"snapshot": stamp, "previous": prev.stem, **c})
    cutoff = (dt.date.fromisoformat(stamp[:10]) - dt.timedelta(days=keep_days)).isoformat()
    for old in out_dir.glob("*Z.jsonl"):
        if old.name[:10] < cutoff:
            old.unlink()
    return path, changes


def clob_market(condition_id: str) -> dict | None:
    try:
        return common.get_json(f"{CLOB}/markets/{condition_id}")
    except (urllib.error.URLError, TimeoutError, ValueError) as e:  # keep the Gamma values, flag clob_ok=False
        # stderr: callers redirect stdout to keys.jsonl (11 Oct: a 429 here broke three paper-run starts)
        print(f"CLOB market info failed for {condition_id}: {e!r}", file=sys.stderr)
        return None


def crawl(modes=DEFAULT_MODES, out_dir=MARKETS_DIR, workers=4, features=()):
    now = dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H%M%SZ")
    cands = candidates(modes, now, features)
    with ThreadPoolExecutor(workers) as pool:  # polite: ~10 req/s, well under CLOB's public limit
        clobs = list(pool.map(clob_market, [gm["conditionId"] for _, _, gm in cands]))
    rows = [build_row(mode, ev, gm, clob, stamp) for (mode, ev, gm), clob in zip(cands, clobs)]
    path, changes = save(rows, stamp, out_dir)
    return rows, path, changes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fast", action="store_true", help="also crawl crypto-fast (5m/15m) for the latency test")
    args = ap.parse_args()
    t0 = time.time()
    rows, path, changes = crawl(DEFAULT_MODES + (("crypto-fast",) if args.fast else ()))
    by_mode = {m: sum(r["mode"] == m for r in rows) for m in MODES}
    print(f"{len(rows)} markets in {time.time() - t0:.0f}s -> {path}")
    print("rows per mode:", by_mode)
    print(f"{len(changes)} rules-hash/tick-size changes vs previous snapshot")
    nulls = {f: sorted({r["mode"] for r in rows if r[f] is None}) for f in rows[0]} if rows else {}
    print("null fields (by mode):", {f: m for f, m in nulls.items() if m})


if __name__ == "__main__":
    main()
