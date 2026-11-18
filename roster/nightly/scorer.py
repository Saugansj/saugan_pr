"""Role 22 scorer (build-plan 1.19): reads the paper trader's ledger (read-only) and scores each strategy.

- markouts at 5 s / 1 m / 5 m against mid_ex_own, per strategy and horizon (per share, signed by side)
- ladder-maker's pre-registered statistic per cluster (settlement instant): size x 5m markout + maker rebate
  (+ reward share: 0, no pools on these markets), summed per cluster; mean, SE across clusters, verdict
- btc-speed's pre-registered statistic once its markets resolve: per trade (one taker order) size x (outcome - fill
  price) - taker fee, mean with a cluster-robust SE (one cluster per market), verdict
- universe vs traded subset: ladder-maker's universe checkpoints (every tradable market at tau 24h/6h/1h) against the
  markets it filled, on the fair-vs-mid gap and, where resolved, the Brier score of fair and of mid

Resolutions come from the ledger's settlements, then (unless offline) from public CLOB GET /markets/<cid>, cached in
<dir>/outcomes.json. No order, no key, no authenticated call.
"""
import json
import math
import pathlib
import sqlite3
import statistics

import common
from trader.engines import ladder, speed

ALL = 2 ** 62
HORIZONS = (5, 60, 300)
CLOB_MARKET = "https://clob.polymarket.com/markets/"


def tables(d, t0: int = 0, t1: int = ALL) -> dict[str, list[dict]]:
    """Ledger rows by table with t0 <= event_ms < t1 (and recorded by now), read-only."""
    p = pathlib.Path(d) / "trader.db"
    out: dict[str, list[dict]] = {}
    if not p.exists():
        return out
    con = sqlite3.connect(f"{p.resolve().as_uri()}?mode=ro", uri=True)
    try:
        for tbl, body, ev, rec in con.execute("SELECT tbl, body, event_ms, recorded_ms FROM rows WHERE event_ms >= ? "
                                              "AND event_ms < ? ORDER BY id", (t0, t1)):
            out.setdefault(tbl, []).append({**json.loads(body), "event_ms": ev, "recorded_ms": rec})
    finally:
        con.close()
    return out


def mean_se(xs: list[float]) -> tuple[float | None, float | None]:
    if not xs:
        return None, None
    return statistics.fmean(xs), (statistics.stdev(xs) / math.sqrt(len(xs)) if len(xs) > 1 else None)


def cluster_se(xs: list[float], groups: list) -> float | None:
    """CR0 cluster-robust SE of the mean: sqrt(sum over clusters of (sum of residuals)^2) / n."""
    n = len(xs)
    if n < 2 or len(set(groups)) < 2:
        return None
    m = statistics.fmean(xs)
    by: dict = {}
    for x, g in zip(xs, groups):
        by[g] = by.get(g, 0.0) + x - m
    return math.sqrt(sum(v * v for v in by.values())) / n


def verdict(mean, se, n: int, pre: dict) -> str:
    """The pre-registration's own rule: PASS once n >= n and mean > pass_z SE; FAIL (futility) once n >= futility_n
    and mean < futility_z SE; else running."""
    if mean is None or se is None or se == 0:
        return f"running ({n} of {pre['n']})"
    if n >= pre["n"] and mean > pre["pass_z"] * se:
        return "PASS"
    if n >= pre["futility_n"] and mean < pre["futility_z"] * se:
        return "FAIL (futility)"
    return f"running ({n} of {pre['n']})"


def markouts(rows: list[dict]) -> dict:
    """{strategy: {horizon_s: {"n", "mean", "se", "missing"}}}, per share."""
    out: dict = {}
    for s in sorted({r["strategy"] for r in rows}):
        for h in HORIZONS:
            xs = [r["markout"] for r in rows if r["strategy"] == s and r["horizon_s"] == h and r["markout"] is not None]
            m, se = mean_se(xs)
            out.setdefault(s, {})[h] = {"n": len(xs), "mean": m, "se": se,
                                        "missing": sum(r["strategy"] == s and r["horizon_s"] == h and r["markout"] is None
                                                       for r in rows)}
    return out


def ladder_stat(fills: list[dict], marks: list[dict]) -> dict:
    """Pre-registered ladder-maker statistic per cluster."""
    m5 = {(r["order_id"], r["fill_ms"]): r["markout"] for r in marks if r["horizon_s"] == 300}
    per, missing = {}, 0
    for f in fills:
        if f["strategy"] != ladder.NAME:
            continue
        mo = m5.get((f["order_id"], f["ts_ms"]))
        if mo is None:
            missing += 1
            continue
        rebate = ladder.PARAMS["rebate_rate"] * (f.get("fee_rate") or 0.0) * f["price"] * (1 - f["price"]) * f["size"]
        per[f["cluster_id"]] = per.get(f["cluster_id"], 0.0) + f["size"] * mo + rebate
    m, se = mean_se(list(per.values()))
    return {"clusters": per, "n": len(per), "mean": m, "se": se, "missing_5m": missing,
            "verdict": verdict(m, se, len(per), ladder.PREREG)}


def prereg_since(d, test_id: str) -> int:
    """When a pre-registration was written (ms); 0 if absent. A version's statistic counts only trades after it."""
    p = pathlib.Path(d) / "trader.db"
    if not p.exists():
        return 0
    con = sqlite3.connect(f"{p.resolve().as_uri()}?mode=ro", uri=True)
    try:
        r = con.execute("SELECT recorded_ms FROM prereg WHERE name = ?", (test_id,)).fetchone()
    except sqlite3.OperationalError:
        r = None
    finally:
        con.close()
    return r[0] if r else 0


def speed_stat(fills: list[dict], outcomes: dict, since_ms: int = 0) -> dict:
    """Pre-registered btc-speed statistic: one trade per taker order, held to resolution. Only fills at or after
    since_ms (the current version's pre-registration), so a new version never inherits the old version's trades."""
    trades: dict = {}
    last_buy: dict = {}  # token -> order_id of its latest BUY: a v3 exit SELL closes that trade
    for f in sorted(fills, key=lambda f: f["ts_ms"]):
        if f["strategy"] == speed.NAME and f.get("recorded_ms", f["ts_ms"]) >= since_ms:  # same clock as prereg
            if f.get("side") == "SELL":
                t = trades.get(last_buy.get(f["token_id"]))
                if t:
                    t["sold"] += f["size"]
                    t["proceeds"] += f["size"] * f["price"]
                    t["fee"] += f["fee"]
                continue
            last_buy[f["token_id"]] = f["order_id"]
            t = trades.setdefault(f["order_id"], {"cid": f["cid"], "token_id": f["token_id"], "size": 0.0, "cost": 0.0,
                                                  "fee": 0.0, "ts_ms": f["ts_ms"], "sold": 0.0, "proceeds": 0.0,
                                                  "maker": bool(f.get("maker"))})
            t["size"] += f["size"]
            t["cost"] += f["size"] * f["price"]
            t["fee"] += f["fee"]
    done, pending = [], 0
    for oid, t in trades.items():
        o, left = outcomes.get(t["cid"]), t["size"] - t["sold"]
        if left > 1e-9 and (not o or not o.get("winner")):
            pending += 1
            continue
        win = 1.0 if left > 1e-9 and o["winner"] == t["token_id"] else 0.0
        t["pnl"] = left * win + t["proceeds"] - t["cost"] - t["fee"]
        done.append({"order_id": oid, **t})
    xs, gs = [t["pnl"] for t in done], [t["cid"] for t in done]
    m = statistics.fmean(xs) if xs else None
    se = cluster_se(xs, gs)
    return {"trades": done, "n": len(done), "pending": pending, "mean": m, "se": se, "total": sum(xs),
            "markets": len(set(gs)), "verdict": verdict(m, se, len(done), speed.PREREG)}


def universe(checkpoints: list[dict], fills: list[dict], outcomes: dict) -> dict:
    """Universe checkpoints vs the subset ladder-maker traded: |fair - mid|, fair - mid, Brier of fair and of mid."""
    traded = {f["cid"] for f in fills if f["strategy"] == ladder.NAME}
    out = {}
    for name, rows in (("universe", checkpoints), ("traded", [r for r in checkpoints if r["cid"] in traded])):
        ok = [r for r in rows if r.get("fair") is not None and r.get("mid_ex_own") is not None]
        res = [r for r in ok if (outcomes.get(r["cid"]) or {}).get("yes") is not None]
        y = [float(outcomes[r["cid"]]["yes"]) for r in res]
        out[name] = {"rows": len(rows), "markets": len({r["cid"] for r in rows}), "priced": len(ok),
                     "mean_abs_gap": statistics.fmean(abs(r["fair"] - r["mid_ex_own"]) for r in ok) if ok else None,
                     "mean_gap": statistics.fmean(r["fair"] - r["mid_ex_own"] for r in ok) if ok else None,
                     "resolved": len(res),
                     "brier_fair": statistics.fmean((r["fair"] - v) ** 2 for r, v in zip(res, y)) if res else None,
                     "brier_mid": statistics.fmean((r["mid_ex_own"] - v) ** 2 for r, v in zip(res, y)) if res else None}
    return out


def fetch_outcome(cid: str, get=common.get_json) -> dict | None:
    """{"winner": token id, "yes": bool} once CLOB /markets/<cid> is closed with a winner, else None. Read-only GET."""
    r = get(CLOB_MARKET + cid)
    if not r.get("closed"):
        return None
    toks = r.get("tokens", [])
    win = next((t for t in toks if t.get("winner")), None)
    if win is None:
        return None
    return {"winner": win["token_id"], "yes": str(win.get("outcome", "")).lower() in ("yes", "up") if win.get("outcome")
            else (toks.index(win) == 0)}


TAPE = "https://data-api.polymarket.com/v2/trades"   # v1 was retired on 4 Nov: every /trades call returns 410 Gone
TAPE_PAGES = 40  # cursor pages of 500; a btc-speed market ran ~1k taker legs in 4 Nov checks
TAPE_LAG_S = (2, 4)  # public-tape stamps trail the match by ~2-3 s (13 Oct fit of 100k prints against the tob logs)
CRYPTO_TAKER_RATE = 0.07  # trader/fees.py: every btc-speed market is a crypto fast market


RACE_AHEAD = 0.31  # share of our window's taker volume matched before our order arrived (research/measure/tape_calib.py, 27 Jul-
# 9 Aug archive at 500 ms: median 0.31, q25 0.11, q75 0.52; 0.09 at 0 ms). There the tape estimator gave +0.33/trade vs the
# replay's +0.40 (fill at the real arrival ask). shortcut: archive stamps come in ~0.5 s batches; refit with TAPE_LAG_S


def fetch_tape(cid: str, since_s: int, until_s: int, get=common.get_json) -> list[list]:
    """Taker legs (one row per taker fill) of one market in [since_s, until_s]:
    [[asset, side, price, ts_s, size], ...]. Data API v2 pages newest first by cursor and ignores start/end, so the
    window is filtered here and the walk stops once a page runs past it. Raises when TAPE_PAGES cuts the window.
    Read-only GET."""
    rows, seen, cursor = [], set(), None
    for _ in range(TAPE_PAGES):
        page = get(TAPE, {"condition": cid, "limit": 500, "taker_only": "true", **({"cursor": cursor} if cursor else {})})
        data, pag = page.get("data") or [], page.get("pagination") or {}
        for r in data:
            ts, key = int(r["timestamp"]), (r["token_id"], r["side"], r["price"], r["timestamp"], r["size"])
            if key not in seen and since_s <= ts <= until_s:   # a cursor page repeats the previous page's last print
                seen.add(key)
                rows.append([r["token_id"], r["side"], float(r["price"]), ts, float(r["size"])])
        cursor = pag.get("next_cursor")
        if not data or not pag.get("has_more") or not cursor or min(int(r["timestamp"]) for r in data) < since_s:
            return rows
    raise RuntimeError(f"tape window cut by the {TAPE_PAGES}-page cursor cap")   # never cache a partial window


def walk(prints, skip: float, limit: float, want: float) -> list[tuple]:
    """Our FAK behind `skip` shares of the race. prints [(ts, price, shares)] -> [(price, shares)] at <= limit, up to
    want: the racers that beat us matched first (time order, any price); our order then takes what is left, cheapest
    first. shortcut: printed volume is a lower bound on depth, and liquidity posted after our arrival counts."""
    left = []
    for _, p, q in sorted(prints):
        left.append((p, max(0.0, q - skip)))
        skip = max(0.0, skip - q)
    got = []
    for p, q in sorted(left):
        if p > limit + 1e-9 or want < 1e-9:
            break
        if q > 0:
            got.append((p, min(q, want)))
            want -= min(q, want)
    return got


def tape_reprice(d, trades: list[dict], arrival_ms: dict, fetch=fetch_tape, limits: dict | None = None) -> dict:
    """Paper-fill realism: each resolved btc-speed trade's buy repriced at what real takers paid for its token in the
    second our order would have matched (a v3 exit's sale keeps its paper price, so v3 stays optimistic). best = the
    cheapest real price (never better than our fill), typical = the median. live (15 Oct, volume-aware): our order
    queues behind RACE_AHEAD of that second's real taker volume, then fills what is left at or under its limit
    (limits: order id -> price), partial fills allowed; live_shares of the trade's shares filled. Paper assumes we win
    every race for the cheapest ask. Cached per order in <dir>/tape.json; fetch=None reads the cache only.
    shortcut: paper only; with live on, drop our own wallet's prints or we race ourselves."""
    cache_p = pathlib.Path(d) / "tape.json"
    try:
        cache = json.loads(cache_p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    cache = {k: v for k, v in cache.items() if v and len(v[0]) == 5}   # pre-15 Oct whole-market caches (maker legs mixed in) and empty windows: fetched again
    out = {"n": 0, "paper": 0.0, "best": 0.0, "typical": 0.0, "live": 0.0, "shares": 0.0, "live_shares": 0.0,
           "gap": [], "trades": []}
    for t in trades:
        a, oid = arrival_ms.get(t["order_id"], t["ts_ms"]) // 1000, t["order_id"]
        if t.get("maker"):   # speed_maker: the paper fill already came from a real print through our resting bid
            fill, n = t["cost"] / t["size"], t["size"]
            r = {**t, "arrival_s": a, "fill": fill, "tape_min": fill, "tape_median": fill, "tape_n": 0, "best": t["pnl"],
                 "typical": t["pnl"], "live": t["pnl"], "live_shares": n, "live_px": fill}
            out["trades"].append(r)
            out["n"] += 1
            for key in ("best", "typical", "live", "live_shares"):
                out[key] += r[key]
            out["paper"] += t["pnl"]
            out["shares"] += n
            out["gap"].append(0.0)
            continue
        rows = cache.get(oid)
        if rows is None and fetch:
            try:
                rows = cache[oid] = fetch(t["cid"], a - 10, a + 10)
            except Exception as e:  # noqa: BLE001 - a missed GET (or a cut window) is retried next night
                print(f"tape {t['cid'][:12]}: {e!r}", flush=True)
        tok = t["token_id"]
        hit = [(ts, p if x == tok else 1 - p, q) for x, side, p, ts, q in rows or ()
               if a + TAPE_LAG_S[0] <= ts <= a + TAPE_LAG_S[1] and (x == tok) == (side == "BUY")]   # lifting tok's ask
        px = sorted(p for _, p, _ in hit)
        if not px:
            continue
        fill, n = t["cost"] / t["size"], t["size"]
        val = lambda p: t["pnl"] - n * (p - fill) - n * CRYPTO_TAKER_RATE * (p * (1 - p) - fill * (1 - fill))  # buy at p
        got = [(max(p, fill), q) for p, q in walk(hit, RACE_AHEAD * sum(q for *_, q in hit), (limits or {}).get(oid, 1.0), n)]
        k = sum(q for _, q in got)
        r = {**t, "arrival_s": a, "fill": fill, "tape_min": px[0], "tape_median": statistics.median(px),
             "tape_n": len(px), "best": val(max(px[0], fill)), "typical": val(statistics.median(px)),
             "live": sum(q * val(p) for p, q in got) / n,   # per slice: a slice's fee is at its own price
             "live_shares": k, "live_px": sum(p * q for p, q in got) / k if k else None}
        out["trades"].append(r)
        out["n"] += 1
        for key in ("best", "typical", "live", "live_shares"):
            out[key] += r[key]
        out["paper"] += t["pnl"]
        out["shares"] += n
        out["gap"].append(r["tape_median"] - fill)
    if fetch:
        cache_p.write_text(json.dumps(cache), encoding="utf-8")
    out["gap_median"] = statistics.median(out.pop("gap")) if out["n"] else None
    return out


def outcomes(d, t: dict, now_ms: int, fetch=fetch_outcome) -> dict:
    """{cid: {"winner", "yes"}} for every ended market the ledger mentions; fetch=None stays offline."""
    cache_p = pathlib.Path(d) / "outcomes.json"
    try:
        out = json.loads(cache_p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        out = {}
    for s in t.get("settlements", []):
        out.setdefault(s["cid"], {"winner": s["winner"], "yes": None})
    ended = {r["cid"] for r in t.get("fills", []) + t.get("universe_checkpoint", [])
             if (r.get("end_ms") or ALL) < now_ms}
    if fetch:
        for cid in sorted(c for c in ended if c not in out or out[c].get("yes") is None):
            try:
                o = fetch(cid)
            except Exception as e:  # noqa: BLE001 - a missed GET is retried next night
                print(f"outcome {cid[:12]}: {e!r}", flush=True)
                continue
            if o:
                out[cid] = o
        cache_p.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def score(d, t0: int = 0, t1: int = ALL, fetch=fetch_outcome, now_ms: int | None = None, tape_fetch=fetch_tape) -> dict:
    """Everything above for one ledger. Evidence statistics use every row up to t1 (they accumulate across days);
    markouts use the window [t0, t1). fetch=None keeps the tape offline too."""
    now_ms = common.now_ms() if now_ms is None else now_ms
    cum, win = tables(d, 0, t1), tables(d, t0, t1)
    oc = outcomes(d, cum, now_ms, fetch)
    sp = next((p for p in (speed.PREREG_V3, speed.PREREG_MAKER_ETH_BYBIT, speed.PREREG_MAKER_BYBIT, speed.PREREG_V7_ETH_BYBIT, speed.PREREG_V7_BYBIT, speed.PREREG_V6_ETH_BYBIT, speed.PREREG_V6_BYBIT, speed.PREREG_V4_ETH_BYBIT_C, speed.PREREG_V4_ETH_BYBIT, speed.PREREG_V4_ETH, speed.PREREG_V5_BYBIT,
                                    speed.PREREG_V5, speed.PREREG_V4_BYBIT, speed.PREREG_V4)
               if prereg_since(d, p["test_id"])),
              speed.PREREG)  # the run's btc-speed version
    st = speed_stat(cum.get("fills", []), oc, prereg_since(d, sp["test_id"]))
    st["tape"] = tape_reprice(d, st["trades"], {s["order_id"]: s["arrival_ms"] for s in cum.get("speed_trades", [])
                                                if s.get("order_id")}, tape_fetch if fetch else None,
                       {o["order_id"]: o["price"] for o in cum.get("orders", [])})
    return {"markouts": markouts(win.get("markouts", [])),
            "ladder": ladder_stat(cum.get("fills", []), cum.get("markouts", [])),
            "speed": {**st, "prereg": sp},
            "universe": universe(cum.get("universe_checkpoint", []), cum.get("fills", []), oc),
            "outcomes": oc}
