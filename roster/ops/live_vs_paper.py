"""Live vs paper v4b on the same signals (12 Nov): did the real order fill, at what price, and what would the paper
twin and the live estimate have had for the same market?

Live sizing is the venue's: a taker BUY of 5 shares at limit L spends 5 x L (+ fee) and, when it matches cheaper, the
wallet gets extra shares (spend / fill price); the live ledger still books 5 shares at the fill price (open bug), so
the live P&L here is recomputed. Signals that arrived while live was paused (REDUCING) are listed but left out of the
statistics: paper v4b has a far larger account and keeps trading through live's daily stop. An order Polymarket refused
(16 Nov: a marketable BUY under its $1 minimum) is counted as refused, never as a lost race: it never reached the book.

  python ops/live_vs_paper.py          # writes reports/research/live_vs_paper.md
"""
import collections
import csv
import datetime as dt
import json
import pathlib
import sqlite3
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
T = ROOT / "data" / "trader"
OUT = ROOT / "reports" / "research" / "live_vs_paper.md"
CSV = ROOT / "reports" / "research" / "real_outcomes_trades.csv"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
MATCH_MS = 15_000   # a paper fill on the same market within this of the live order is the same signal


def _ms(t: int) -> int:
    return t // 1000 if t > 10**14 else t   # live venue fills were stamped in microseconds before the 12 Nov fix


def _rows(db: pathlib.Path, tbls) -> list[tuple[str, int, dict]]:
    if not db.exists():
        return []
    con = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True, timeout=5)
    try:
        return [(t, _ms(e), json.loads(b)) for t, e, b in con.execute(
            f"SELECT tbl, event_ms, body FROM rows WHERE tbl IN ({','.join('?' * len(tbls))}) ORDER BY id", tbls)]
    finally:
        con.close()


def sessions(account: str = "live") -> list[pathlib.Path]:
    """Finished + current session folders for one live account (live or live_b)."""
    cur = T / account
    arch_name = "live_archive" if account == "live" else f"{account}_archive"
    arch_root = T / arch_name
    arch = sorted(p for p in arch_root.glob("*") if p.is_dir()) if arch_root.exists() else []
    return [p for p in arch + [cur] if (p / "journal.jsonl").exists()]


def paused_spans(rows) -> list[tuple[int, int]]:
    """[start, end) of REDUCING/HALTED periods from the global trip rows (end = far future while still paused)."""
    spans, start = [], None
    for t, e, b in rows:
        if t != "trips" or b.get("scope") != "global":
            continue
        st = b.get("state") or b.get("level")
        if st != "ACTIVE" and start is None:
            start = e
        elif st == "ACTIVE" and start is not None:
            spans.append((start, e))
            start = None
    if start is not None:
        spans.append((start, 10**15))
    return spans


def refusal_label(why: str) -> str:
    """A short label for a venue refusal: the journal keeps Polymarket's whole error text (16 Nov)."""
    w = (why or "").replace("|", "/").strip()   # the label lands in a markdown table cell and in HTML
    if "invalid amount" in w.lower() or "minimum" in w.lower():
        return "refused: under $1"
    return f"refused: {w[:40]}" if w else "refused"


def live_orders(d: pathlib.Path) -> list[dict]:
    """One row per btc-speed order of a live session: limit, fill (or None = missed), real spend and shares, result."""
    orders, fills = {}, {}
    for line in (d / "journal.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e["op"] == "new" and e["intent"].get("strategy") == "btc-speed" and e["intent"].get("side") == "BUY":
            i = e["intent"]
            orders[e["id"]] = {"ts": e["ts"], "cid": i["cid"], "token": i["token_id"], "limit": i["price"],
                               "size": i["size"], "reason": i.get("reason", "")}
        elif e["op"] == "cancel" and e["id"] in orders:
            orders[e["id"]]["why"] = e.get("reason", "")
        elif e["op"] == "fill" and e["id"] in orders:
            f = e["fill"]
            g = fills.setdefault(e["id"], {"size": 0.0, "usd": 0.0, "fee": 0.0})
            g["size"] += f["size"]
            g["usd"] += f["price"] * f["size"]
            g["fee"] += f["fee"]
    won = {b["cid"]: b.get("winner") for t, _, b in _rows(d / "trader.db", ("settlements",))}
    out = []
    for oid, o in orders.items():
        g = fills.get(oid)
        why = o.pop("why", "")
        # 16 Nov: a refusal (e.g. under the $1 minimum) never raced anyone; only "no orders found" is a lost race
        r = {**o, "session": d.name, "filled": bool(g), "price": None, "spend": None, "shares": None, "won": None, "pnl": None,
             "refused": (not g) and bool(why) and "no orders found" not in why, "why": why}
        if g:
            r["price"] = g["usd"] / g["size"]
            r["spend"] = g["size"] * o["limit"] + g["fee"]                # the venue spends size x limit
            r["shares"] = g["size"] * o["limit"] / r["price"]             # and gives the price improvement as shares
            if o["cid"] in won:
                r["won"] = won[o["cid"]] == o["token"]
                r["pnl"] = (r["shares"] if r["won"] else 0.0) - r["spend"]
        out.append(r)
    return out


def paper_fills(run: str = "paper_v4b") -> dict[str, list[dict]]:
    rows = _rows(T / run / "trader.db", ("fills", "settlements"))
    won = {b["cid"]: b.get("winner") for t, _, b in rows if t == "settlements"}
    out: dict[str, list[dict]] = {}
    for t, e, b in rows:
        if t == "fills" and b.get("side") == "BUY":
            w = won.get(b["cid"])
            res = None if w is None else w == b.get("token_id")
            cost = b["price"] * b["size"] + b.get("fee", 0.0)
            out.setdefault(b["cid"], []).append({"ts": e, "token": b.get("token_id"), "price": b["price"], "cost": cost,
                                                  "won": res, "pnl": None if res is None else (b["size"] if res else 0) - cost})
    return out


def estimates() -> dict[str, dict]:
    """paper_v4b's live-estimate row per market (real_outcomes_trades.csv): the predicted live fill."""
    try:
        with open(CSV, newline="", encoding="utf-8") as f:
            return {r["market"]: r for r in csv.DictReader(f) if r["run"] == "paper_v4b"}
    except OSError:
        return {}


def timing(d: pathlib.Path = T / "live") -> dict | None:
    """Medians from order_timing.jsonl (15 Nov): pc_ms = signal -> post (sign + journal), post_ms = the POST round trip
    (network + venue, the taker delay included), match_ms = POST start -> the venue's match_time of our first trade."""
    p = d / "order_timing.jsonl"
    if not p.exists():
        return None
    posts, first_match = [], {}
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("kind") == "post" and e.get("post_end_ms"):
            posts.append(e)
        elif e.get("kind") == "trade_event":
            m = e.get("msg") or {}
            raw = float(m.get("match_time") or m.get("matchtime") or m.get("timestamp") or 0)
            ts = int(raw * 1000 if raw < 1e11 else raw)
            for oid in [m.get("taker_order_id")] + [x.get("order_id") for x in m.get("maker_orders") or []]:
                if oid and ts and (oid not in first_match or ts < first_match[oid]):
                    first_match[oid] = ts
    if not posts:
        return None
    med = lambda xs: statistics.median(xs) if xs else None
    match = [first_match[o["id"]] - e["post_start_ms"] for e in posts for o in e["orders"] if o["id"] in first_match]
    status = [str(r.get("status") or r.get("errorMsg") or "?")[:40] for e in posts for r in (e.get("response") or [])
              if isinstance(r, dict)]
    return {"n": len(posts), "pc_ms": med([e["post_start_ms"] - e["decision_ms"] for e in posts]),
            "post_ms": med([e["post_end_ms"] - e["post_start_ms"] for e in posts]), "match_ms": med(match),
            "n_match": len(match), "status": dict(collections.Counter(status).most_common(4))}


def compare(account: str = "live") -> tuple[list[dict], dict]:
    paper, est = paper_fills(), estimates()
    rows = []
    for d in sessions(account):
        spans = paused_spans(_rows(d / "trader.db", ("trips",)))
        for o in live_orders(d):
            p = next((x for x in paper.get(o["cid"], []) if abs(x["ts"] - o["ts"]) <= MATCH_MS and x["token"] == o["token"]), None)
            e = est.get(o["cid"]) if p else None   # the estimate belongs to paper's trade: only the same signal counts
            e = e if e and e.get("token") == o["token"] else None
            live_px = float(e["live_px"]) if e and e.get("live_px") not in (None, "") else None
            rows.append({**o, "paused": any(a <= o["ts"] < b for a, b in spans), "paper": p,
                         "est_px": live_px, "est_filled": None if e is None else float(e.get("live_shares") or 0) > 0})
    rows.sort(key=lambda r: r["ts"])
    act = [r for r in rows if not r["paused"]]
    both = [r for r in act if r["filled"] and r["paper"]]
    s = {"orders": len(act), "filled": sum(r["filled"] for r in act),
         "paper_had": sum(bool(r["paper"]) for r in act),
         "missed_paper_filled": sum(bool(r["paper"]) and not r["filled"] and not r["refused"] for r in act),
         "refused": sum(r["refused"] for r in act),
         "refused_paper_filled": sum(bool(r["paper"]) and r["refused"] for r in act),
         "gap": statistics.mean(r["price"] - r["paper"]["price"] for r in both) if both else None, "n_gap": len(both),
         "live_pnl": sum(r["pnl"] for r in act if r["pnl"] is not None),
         "live_spend": sum(r["spend"] for r in act if r["pnl"] is not None),
         "live_settled": sum(r["pnl"] is not None for r in act),
         "paper_pnl": sum(r["paper"]["pnl"] for r in act if r["paper"] and r["paper"]["pnl"] is not None),
         "paper_cost": sum(r["paper"]["cost"] for r in act if r["paper"] and r["paper"]["pnl"] is not None),
         "est_gap": None, "paused": len(rows) - len(act)}
    eg = [r["price"] - r["est_px"] for r in act if r["filled"] and r["est_px"]]
    if eg:
        s["est_gap"], s["n_est"] = statistics.mean(eg), len(eg)
    return rows, s


def report() -> str:
    rows, s = compare()
    f = lambda x, d=2: "" if x is None else f"{x:+.{d}f}"
    hm = lambda t: dt.datetime.fromtimestamp(t / 1000, IST).strftime("%d %b %H:%M:%S")
    per = lambda pnl, cost: f"{100 * pnl / cost:+.1f}%" if cost else ""
    L = [f"# Live vs paper v4b, same signals\n\nWritten {dt.datetime.now(IST):%d %b %Y %H:%M} IST. Live = real orders "
         "(`data/trader/live` and `live_archive`); paper = paper_v4b's fill on the same market within 15 s; estimate = "
         "the live estimate's predicted fill for that paper trade. Live P&L uses the venue's sizing (5 x limit spent, "
         "extra shares on price improvement). Signals while live was paused are listed, not counted.\n",
         "## Summary (live active only)\n",
         "| | |\n|---|---|",
         f"| Live orders | {s['orders']} ({s['filled']} filled) |",
         f"| Paper filled the same market | {s['paper_had']} |",
         f"| **Lost the race where paper filled** | **{s['missed_paper_filled']} of {s['paper_had']}** |",
         f"| **Refused by Polymarket (not a race)** | **{s['refused']}** ({s['refused_paper_filled']} where paper filled) |",
         f"| **Live price minus paper price** (both filled) | **{f(s['gap'], 3)}** per share (n {s['n_gap']}) |",
         f"| Live price minus live-estimate price | {f(s['est_gap'], 3)} (n {s.get('n_est', 0)}) |",
         f"| Live settled P&L | {f(s['live_pnl'])} USD on {s['live_spend']:.2f} spent ({per(s['live_pnl'], s['live_spend'])}), "
         f"{s['live_settled']} bets |",
         f"| Paper v4b on those markets | {f(s['paper_pnl'])} USD on {s['paper_cost']:.2f} ({per(s['paper_pnl'], s['paper_cost'])}) |",
         f"| Orders while live was paused (not counted) | {s['paused']} |",
         "\n## Every live order\n",
         "| Time (IST) | Signal | Limit | Live fill | Paper fill | Estimate | Live result | Live P&L | Paper P&L |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in rows[::-1]:
        # a batch POST that Polymarket refuses cancels its healthy partner leg too: say which one this was
        res = ("paused" if r["paused"] else
               "refused: other leg under $1" if r["refused"] and r["limit"] * r["size"] >= 1.0 else
               refusal_label(r["why"]) if r["refused"] else
               "missed" if not r["filled"] else "open" if r["won"] is None else "WON" if r["won"] else "lost")
        p = r["paper"]
        L.append(f"| {hm(r['ts'])} | {r['reason']} | {r['limit']:.2f} | {'' if r['price'] is None else f'{r['price']:.3f}'} | "
                 f"{'' if not p else f'{p['price']:.2f}'} | {'' if r['est_px'] is None else f'{r['est_px']:.3f}'} | {res} | "
                 f"{f(r['pnl'])} | {'' if not p else f(p['pnl'])} |")
    L.append("\nRead the price gap and the lost-race rate first: they decide whether v4 can work from this PC. "
             "A refused order never reached the book (Polymarket rejected it, e.g. under its $1 minimum for a "
             "marketable buy), so it is not a lost race; a refused batch also takes its healthy partner leg with it. "
             "Judge after about 50 live orders.")
    return "\n".join(L) + "\n"


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(report(), encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
