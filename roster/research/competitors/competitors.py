"""Competitor research (build-plan 0.9): who is active in our target markets, and do makers earn there?

Run:  .venv/Scripts/python.exe research/competitors/competitors.py
1. Target markets from Gamma: recent closed BTC/ETH daily strike ("above") and daily Up/Down events,
   and recent closed big-5 soccer match (1X2) events.
2. Data API /trades per market, twice: takerOnly=false (both legs) and takerOnly=true (taker legs).
   A row in the first list that is missing from the second is a maker fill.
3. The most active wallets (by maker notional, plus the largest by total notional), then their last-90-day
   realised P&L the way polymm's realized_pnl_by_month does it (/v1/closed-positions plus resolved but
   unredeemed /positions), split by market type, plus MAKER_REBATE and REWARD income from /activity, and
   the 90-day change of Polymarket's own profile P&L series as a cross-check.
Writes research/competitors/out/*.json and reports/competitors.md. Public GET endpoints only, <= 5 requests/s.
Resumable: step 2 is cached in out/activity.json and step 3 per wallet in out/wallet_cache.json; --fresh refetches.
"""
import json
import pathlib
import re
import statistics
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from common import REPORTS, get_json  # noqa: E402

GAMMA, DAPI = "https://gamma-api.polymarket.com", "https://data-api.polymarket.com"
PNL_SERIES = "https://user-pnl-api.polymarket.com/user-pnl"  # the P&L chart on a polymarket.com profile
OUT = pathlib.Path(__file__).resolve().parent / "out"
CRYPTO_SERIES = {"btc-multi-strikes-weekly": 2, "ethereum-multi-strikes-weekly": 2,  # series -> markets per event
                 "btc-up-or-down-daily": 1, "eth-up-or-down-daily": 1}
SOCCER_LEAGUES = ["epl", "lal", "bun", "sea", "fl1"]
CRYPTO_DAYS, SOCCER_EVENTS_PER_LEAGUE = 21, 8
TRADE_CAP = 3000          # rows per market per list; ponytail: sample cap, raise for full coverage
PNL_DAYS, MAX_OFFSET = 90, 9950
WORKERS, MIN_GAP = 4, 0.2  # parallel requests hide latency; the shared gap keeps the total at <= 5 requests/s
SEGMENTS = [  # first match wins; applied to the event slug
    ("crypto-strike", r"^(bitcoin|ethereum)-above-on-"),
    ("crypto-daily-updown", r"^(bitcoin|ethereum)-up-or-down-on-"),
    ("crypto-hourly", r"^(bitcoin|ethereum)-up-or-down-.*-\d{1,2}(am|pm)-et$"),
    ("crypto-fast", r"^(btc|eth|sol|xrp)-updown-"),
    ("soccer", r"^(epl|lal|bun|sea|fl1|ucl|uel)-"),
    ("crypto-other", r"(bitcoin|ethereum|btc|eth|solana|xrp)"),
]
TARGET = {"crypto-strike", "crypto-daily-updown", "soccer"}


def seg(slug: str) -> str:
    return next((name for name, rx in SEGMENTS if re.search(rx, slug or "")), "other")


_lock, _last = threading.Lock(), [0.0]


def get(path: str, **params):
    for attempt in range(3):
        with _lock:  # polite: one request start per MIN_GAP across all threads
            time.sleep(max(0.0, _last[0] + MIN_GAP - time.monotonic()))
            _last[0] = time.monotonic()
        try:
            return get_json(path, params)
        except OSError:  # connection resets are not retried by get_json
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def paged(path: str, page: int, cap: int, stop=None, **params) -> tuple[list, bool]:
    """Offset-paginate a Data API list. Returns (rows, truncated)."""
    rows = []
    while len(rows) < cap:
        chunk = get(path, limit=page, offset=len(rows), **params)
        rows += chunk
        if len(chunk) < page or (stop and chunk and stop(chunk[-1])):
            return rows, False
        if len(rows) > MAX_OFFSET:
            break
    return rows, True


def split_maker(both: list, taker: list, truncated: bool) -> list[tuple[dict, bool]]:
    """Label each row of the takerOnly=false list as maker (True) or taker (False).
    Lists are newest-first; if either was truncated, keep only the window both cover."""
    key = lambda r: (r["transactionHash"], r["proxyWallet"], r["asset"], r["side"])  # noqa: E731
    takers = {key(r) for r in taker}
    cutoff = max(both[-1]["timestamp"], taker[-1]["timestamp"]) if truncated and both and taker else 0
    return [(r, key(r) not in takers) for r in both if r["timestamp"] >= cutoff]


def wallet_pnl(closed: list, open_pos: list, since_ts: int, truncated: bool = False) -> tuple[dict, int]:
    """Realised P&L by segment since since_ts: closed positions plus resolved-but-unredeemed positions
    (polymm's imputation, restricted to redeemable=True so live 0.99 positions are not counted as won).
    Winners get redeemed (closed list) while losers usually stay unredeemed (open list), so when the closed
    list hit the offset cap the window shrinks to what it covers, or the P&L would be biased negative.
    Returns (pnl by segment, window start actually used)."""
    if truncated and closed:
        since_ts = max(since_ts, closed[-1]["timestamp"])
    since_day = datetime.fromtimestamp(since_ts, timezone.utc).strftime("%Y-%m-%d")
    out = defaultdict(float)
    for p in closed:
        if p["timestamp"] >= since_ts:
            out[seg(p.get("eventSlug") or p.get("slug"))] += float(p.get("realizedPnl") or 0)
    for p in open_pos:
        size, cur, avg = (float(p.get(k) or 0) for k in ("size", "curPrice", "avgPrice"))
        if not p.get("redeemable") or size <= 0.01 or 0.02 < cur < 0.98 or (p.get("endDate") or "") < since_day:
            continue
        payout = 1.0 if cur >= 0.98 else 0.0
        out[seg(p.get("eventSlug") or p.get("slug"))] += float(p.get("realizedPnl") or 0) + size * (payout - avg)
    return {k: round(v, 2) for k, v in out.items()}, since_ts


def series_delta(series: list, since_ts: int) -> float:
    """Change of Polymarket's cumulative profile P&L series ([{t, p}], oldest first) since since_ts."""
    start = next((x["p"] for x in reversed(series) if x["t"] <= since_ts), 0.0)
    return round(series[-1]["p"] - start, 2) if series else 0.0


def target_markets() -> list[dict]:
    mk = []
    for slug, top in CRYPTO_SERIES.items():
        sid = get(f"{GAMMA}/series", slug=slug)[0]["id"]
        for e in get(f"{GAMMA}/events", series_id=sid, closed="true", limit=CRYPTO_DAYS, order="endDate", ascending="false"):
            ms = sorted(e["markets"], key=lambda m: -float(m.get("volume") or 0))[:top]
            mk += [{"cid": m["conditionId"], "event": e["slug"], "seg": seg(e["slug"]), "volume": float(m.get("volume") or 0)} for m in ms]
    sports = {s["sport"]: s for s in get(f"{GAMMA}/sports")}
    for lg in SOCCER_LEAGUES:
        evs = get(f"{GAMMA}/events", series_id=sports[lg]["series"], closed="true", limit=200, order="endDate", ascending="false")
        main = [e for e in evs if re.fullmatch(rf"{lg}-[a-z0-9]+-[a-z0-9]+-\d{{4}}-\d{{2}}-\d{{2}}", e["slug"])][:SOCCER_EVENTS_PER_LEAGUE]
        mk += [{"cid": m["conditionId"], "event": e["slug"], "seg": "soccer", "volume": float(m.get("volume") or 0)} for e in main for m in e["markets"]]
    return mk


def fetch_trades(m: dict):
    try:
        both, t1 = paged(f"{DAPI}/trades", 500, TRADE_CAP, market=m["cid"], takerOnly="false")
        taker, t2 = paged(f"{DAPI}/trades", 500, TRADE_CAP, market=m["cid"], takerOnly="true")
        return both, taker, t1 or t2
    except OSError as e:  # one bad market must not sink the run; counted in the report
        return None, None, str(e)


def wallet_activity(markets: list[dict]) -> dict:
    wal = defaultdict(lambda: {"name": "", "maker": defaultdict(float), "taker": defaultdict(float), "n": 0})
    stats = {"markets": len(markets), "rows": 0, "maker_rows": 0, "truncated_markets": 0, "tx_with_one_taker": 0, "tx": 0, "failed_markets": 0}
    with ThreadPoolExecutor(WORKERS) as ex:
        for i, (m, (both, taker, trunc)) in enumerate(zip(markets, ex.map(fetch_trades, markets))):
            if both is None:
                stats["failed_markets"] += 1
                print(f"[{i + 1}/{len(markets)}] {m['event']} FAILED {trunc}", flush=True)
                continue
            m["trades"], m["truncated"] = len(both), trunc
            stats["truncated_markets"] += m["truncated"]
            per_tx = defaultdict(int)
            for r, is_maker in split_maker(both, taker, m["truncated"]):
                w = wal[r["proxyWallet"]]
                w["name"] = r.get("name") or r.get("pseudonym") or ""
                w["maker" if is_maker else "taker"][m["seg"]] += float(r["size"]) * float(r["price"])
                w["n"] += 1
                stats["rows"] += 1
                stats["maker_rows"] += is_maker
                per_tx[r["transactionHash"]] += not is_maker
            stats["tx"] += len(per_tx)
            stats["tx_with_one_taker"] += sum(v == 1 for v in per_tx.values())
            print(f"[{i + 1}/{len(markets)}] {m['event']} rows={len(both)} truncated={m['truncated']}", flush=True)
    return {"wallets": wal, "stats": stats}


def pick_wallets(wal: dict) -> list[str]:
    tot = lambda w, side, grp: sum(v for k, v in w[side].items() if k.startswith(grp))  # noqa: E731
    picks = []
    for grp in ("crypto", "soccer"):
        by_maker = sorted(wal, key=lambda a: -tot(wal[a], "maker", grp))[:12]
        by_total = sorted(wal, key=lambda a: -(tot(wal[a], "maker", grp) + tot(wal[a], "taker", grp)))[:4]
        picks = list(dict.fromkeys(picks + by_maker + by_total))  # ordered, deduplicated
    return picks


def wallet_report(addr: str, since_ts: int) -> dict:
    closed, trunc = paged(f"{DAPI}/v1/closed-positions", 50, MAX_OFFSET, stop=lambda r: r["timestamp"] < since_ts,
                          user=addr, sortBy="TIMESTAMP", sortDirection="DESC")
    open_pos, pos_trunc = paged(f"{DAPI}/positions", 500, MAX_OFFSET, user=addr, sizeThreshold=0)
    income = {}
    for kind in ("MAKER_REBATE", "REWARD"):
        rows, _ = paged(f"{DAPI}/activity", 500, 5000, user=addr, type=kind, start=since_ts)
        income[kind] = round(sum(float(r.get("usdcSize") or 0) for r in rows), 2)
    pnl, used = wallet_pnl(closed, open_pos, since_ts, trunc)
    profile = get(PNL_SERIES, user_address=addr, interval="all", fidelity="1d")
    return {"pnl": pnl, "window_days": round((time.time() - used) / 86400, 1), "closed_n": sum(p["timestamp"] >= used for p in closed),
            "closed_truncated": trunc, "positions_truncated": pos_trunc, "profile_pnl_90d": series_delta(profile, since_ts), **income}


def fmt(x: float) -> str:
    return f"{'-' if x < 0 else ''}${abs(x):,.0f}"


def write_report(rows: list[dict], stats: dict, markets: list[dict], since_ts: int) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    since = datetime.fromtimestamp(since_ts, timezone.utc).strftime("%Y-%m-%d")
    seg_n = defaultdict(int)
    for m in markets:
        seg_n[m["seg"]] += 1
    L = [f"# Competitor research (build-plan 0.9)\n", f"Generated {now} by `research/competitors/competitors.py`. P&L window: {since} to now ({PNL_DAYS} days), "
         "shorter for wallets whose history the Data API cuts off (the *Window* column).\n",
         "## Answer\n", conclusion(rows) + "\n",
         "*Maker-dominant* = at least 70% of the wallet's sampled notional in that market type was maker fills (and at least $100 sampled). "
         "*Positive realised P&L* (the verdict) = realised P&L in that market type over the wallet's window, before rebates and rewards.\n",
         "## Data source and method\n",
         "- **Markets sampled** (Gamma API, closed events, newest first): " + ", ".join(f"{k} {v}" for k, v in sorted(seg_n.items()))
         + f" markets. Crypto: the last {CRYPTO_DAYS} daily events per series, top {CRYPTO_SERIES['btc-multi-strikes-weekly']} strikes by volume per strike event. "
         f"Soccer: the last {SOCCER_EVENTS_PER_LEAGUE} match (1X2) events in each of {', '.join(SOCCER_LEAGUES)}.",
         f"- **Trades:** Data API `/trades` with `takerOnly=false` (both legs) and `takerOnly=true` (taker legs); a row present only in the first is a **maker** fill. "
         f"{stats['rows']:,} rows, {stats['maker_rows']:,} maker rows; {stats['tx_with_one_taker']:,} of {stats['tx']:,} transactions have exactly one taker row "
         f"(sanity check of the split). Capped at {TRADE_CAP:,} rows per list per market; {stats['truncated_markets']} markets hit the cap and are analysed on the window both lists cover; "
         f"{stats['failed_markets']} failed to download.",
         "- **Wallets:** the 12 largest by maker notional plus the 4 largest by total notional, in crypto and in soccer (deduplicated).",
         "- **Realised P&L:** polymm's `realized_pnl_by_month` method, re-implemented on the same endpoints: `/v1/closed-positions` `realizedPnl` with close `timestamp` in the window, "
         "plus resolved-but-unredeemed `/positions` (payout minus average price, only where `redeemable` is true). Split by the event slug's market type. "
         f"Winners get redeemed (closed list) but losers mostly stay unredeemed (open list), so when a wallet's closed list hits the Data API offset limit ({MAX_OFFSET:,} rows) "
         "before the window start, that wallet's window is shortened to the period its closed list covers (the *Window* column); otherwise its P&L would be biased strongly negative.",
         "- **Profile P&L (cross-check):** the change over the last 90 days of the cumulative P&L series behind the chart on each polymarket.com profile "
         f"(`{PNL_SERIES}`, `interval=all`, `fidelity=1d`). This is Polymarket's own number: all markets, realised plus unrealised, not split by market type.",
         "- **Maker income** = `/activity` rows of type `MAKER_REBATE` (fee rebates) and `REWARD` (liquidity rewards) in the 90 days; the API gives no market for these, so they are not split.",
         "- **Maker share** = maker notional / all notional of that wallet in the sampled target markets.\n",
         "## Wallets\n",
         "| Wallet | Name | Maker share crypto | Maker share soccer | Sampled notional | Realised strike | Realised daily Up/Down | Realised soccer | Realised all other markets | Realised total | Window (days) | Profile P&L 90d | Rebates 90d | Rewards 90d |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        p = r["pnl"]
        other = sum(v for k, v in p.items() if k not in TARGET)
        share = lambda g: "–" if r[f"notional_{g}"] < 1 else f"{r[f'maker_share_{g}']:.0%}"  # noqa: E731
        L.append(f"| `{r['wallet'][:10]}…` | {r['name'][:18].replace('|', '/')} | {share('crypto')} | {share('soccer')} | {fmt(r['notional_crypto'] + r['notional_soccer'])} | "
                 f"{fmt(p.get('crypto-strike', 0))} | {fmt(p.get('crypto-daily-updown', 0))} | {fmt(p.get('soccer', 0))} | {fmt(other)} | {fmt(sum(p.values()))} | "
                 f"{r['window_days']:g}{'*' if r['positions_truncated'] else ''} | {fmt(r['profile_pnl_90d'])} | {fmt(r['MAKER_REBATE'])} | {fmt(r['REWARD'])} |")
    L += ["\nFull wallet addresses and per-segment numbers: `research/competitors/out/wallets.json`. *Realised* columns cover the *Window* days; "
          "a `*` there means the wallet's open-position list also hit the offset limit, so some resolved-but-unredeemed positions are missing.\n",
          "## Limitations\n",
          "- Segment P&L is the wallet's whole P&L in that market type, maker and taker fills together. It stands for maker P&L only for maker-dominant wallets (maker share ≥ 70%).",
          "- Realised P&L counts closed and resolved positions only; open positions in live markets are excluded. The two P&L measures also differ by window and by Polymarket's own "
          "accounting of merges, splits and negRisk conversions, which the public API does not expose. Where they disagree in sign, treat both with caution.",
          "- A shortened window starts at the close time of the oldest closed position fetched, while resolved losers are dated by the market's `endDate`, so the edges do not line up exactly.",
          "- Rebates and rewards cannot be tied to a market type through the public API.",
          "- *Soccer* here means EPL, LaLiga, Bundesliga, Serie A, Ligue 1, UCL and UEL event slugs; other leagues and all other sports fall in *all other markets*.",
          "- `realizedPnl` is per position (one outcome). A wallet that holds both outcomes, or merges pairs, can show large offsetting gains and losses "
          "across outcomes and market types; its total is more reliable than its split.",
          "- The trade sample is recent and capped; it ranks activity, it is not a census.\n",
          "## How to reproduce\n", "```", "cd roster",
          ".venv/Scripts/python.exe research/competitors/competitors.py --fresh   # full refetch",
          ".venv/Scripts/python.exe research/competitors/competitors.py           # resume, or re-render from the caches in research/competitors/out/",
          ".venv/Scripts/python.exe -m pytest research/spike research/competitors -q", "```",
          "A fresh run takes about 20 minutes: about 8 for the trade download (~1,600 requests) and about 10 for the wallet P&L "
          "(4 threads sharing one ≤ 5 requests/s limit). "
          "Results change as markets close and wallets trade."]
    (REPORTS / "competitors.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def conclusion(rows: list[dict]) -> str:
    lines = []
    for g, segs, label in (("crypto", ("crypto-strike", "crypto-daily-updown"), "BTC/ETH daily strike + Up/Down"), ("soccer", ("soccer",), "soccer")):
        makers = [r for r in rows if r[f"notional_{g}"] >= 100 and r[f"maker_share_{g}"] >= 0.7]
        pnls = [sum(r["pnl"].get(s, 0) for s in segs) for r in makers]
        if not makers:
            lines.append(f"- **{label}:** no maker-dominant wallet (maker share ≥ 70%, ≥ $100 sampled notional) among the most active wallets.")
            continue
        incomes = [r["MAKER_REBATE"] + r["REWARD"] for r in makers]
        winners = sum(x > 0 for x in pnls)
        winners_incl = sum(x + y > 0 for x, y in zip(pnls, incomes))
        profile_up = sum(r["profile_pnl_90d"] > 0 for r in makers)
        verdict = "Yes, most do" if winners > len(makers) / 2 else "A minority do" if winners else "No"
        lines.append(f"- **{label}: {verdict}.** {winners} of {len(makers)} maker-dominant wallets have positive realised P&L in this market type "
                     f"(median {fmt(statistics.median(pnls))}, total {fmt(sum(pnls))}, best {fmt(max(pnls))}, worst {fmt(min(pnls))}; each over its *Window*). "
                     f"Adding all their rebates and rewards ({fmt(sum(incomes))}, from all markets, so an upper bound here), "
                     f"{winners_incl} of {len(makers)} are positive. On Polymarket's own 90-day profile P&L (all markets), {profile_up} of {len(makers)} are positive.")
    return "\n".join(lines)


def try_wallet(addr: str, since_ts: int) -> dict | None:
    try:
        return wallet_report(addr, since_ts)
    except OSError as e:  # reported and skipped; the next run retries it (not cached)
        print(f"wallet {addr} FAILED {e}", flush=True)
        return None


def main() -> None:
    OUT.mkdir(exist_ok=True)
    act_f, cache_f = OUT / "activity.json", OUT / "wallet_cache.json"
    if "--fresh" in sys.argv:
        act_f.unlink(missing_ok=True)
        cache_f.unlink(missing_ok=True)
    if act_f.exists():
        act = json.loads(act_f.read_text())
    else:
        markets = target_markets()
        act = wallet_activity(markets) | {"markets": markets, "since_ts": int(time.time()) - PNL_DAYS * 86400}
        act_f.write_text(json.dumps(act))
    wal, stats, markets, since_ts = act["wallets"], act["stats"], act["markets"], act["since_ts"]
    cache = json.loads(cache_f.read_text()) if cache_f.exists() else {}
    picks = pick_wallets(wal)
    todo = [a for a in picks if a not in cache]
    with ThreadPoolExecutor(WORKERS) as ex:
        for a, rep in zip(todo, ex.map(lambda a: try_wallet(a, since_ts), todo)):
            if rep:
                cache[a] = rep
                cache_f.write_text(json.dumps(cache))
                print(f"wallet {len(cache)}/{len(picks)}: {a} {rep['pnl']}", flush=True)
    rows = []
    for a in (a for a in picks if a in cache):
        w, row = wal[a], {"wallet": a, "name": wal[a]["name"]}
        for g in ("crypto", "soccer"):
            mkr = sum(v for k, v in w["maker"].items() if k.startswith(g))
            tkr = sum(v for k, v in w["taker"].items() if k.startswith(g))
            row |= {f"notional_{g}": round(mkr + tkr, 2), f"maker_share_{g}": round(mkr / (mkr + tkr), 3) if mkr + tkr else 0.0}
        rows.append(row | cache[a])
    (OUT / "wallets.json").write_text(json.dumps({"stats": stats, "since_ts": since_ts, "wallets": rows}, indent=1))
    write_report(rows, stats, markets, since_ts)
    print(conclusion(rows))


if __name__ == "__main__":
    main()
