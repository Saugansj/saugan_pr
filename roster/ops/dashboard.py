"""Local paper-runs dashboard: http://127.0.0.1:8790 (page reloads every 60 s; local data only, no internet use).

Live part, read from the run ledgers on each load: alive / ACTIVE / paused, today's signals, orders and fills, the hub's
data meter and the keeper's last notes. Returns part: the live estimate per IST day and run, balances and the 2 SE
progress, from reports/research/real_outcomes_trades.csv, which a background thread refreshes every REFRESH_S
(ops/real_outcomes.py: one small tape lookup per newly settled trade).

  .venv\\Scripts\\python.exe ops\\dashboard.py        # or: ops\\paper_tasks.ps1 dashboard
"""
import csv
import datetime as dt
import html
import json
import math
import pathlib
import sqlite3
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nightly import scorer  # noqa: E402
from ops.keeper import ACTIVE  # noqa: E402
from ops.live_accounts import ACCOUNTS, get as live_account  # noqa: E402
from ops.status import IST, RUNS  # noqa: E402

PORT, REFRESH_S = 8790, 600
T = ROOT / "data" / "trader"
CSV = ROOT / "reports" / "research" / "real_outcomes_trades.csv"
LABEL = {"paper_ethb": "ETH v4", "paper_eth6b": "ETH v6", "paper_v7b": "BTC v7", "paper_eth7b": "ETH v7", "paper_eth7c": "ETH cap 0.70", "paper_v4b": "BTC v4", "paper_v5b": "BTC v5", "paper_v6b": "BTC v6", "paper_v8b": "BTC v8 (ask <= 0.50, retired)", "paper_v4add": "BTC v4 + one add",
         "paper_v4sz50": "BTC v4 8sh $50", "paper_v4sz100": "BTC v4 8sh $100",
         "paper_v9fix": "BTC v9 (min ask 0.35)",
         "paper_mk": "BTC maker", "paper_ethmk": "ETH maker", "paper14": "v2 + ladder (retired)", "paper_v3": "v3 (retired)",
         "paper_eth": "ETH v4 Binance (retired)", "paper_ethc": "ETH compounding (retired)"}
state = {"refreshed": None, "error": None}


def _account_label(account: str) -> str:
    a = live_account(account)
    if a["env_file"] and a["env_file"].exists():
        try:
            return json.loads(a["env_file"].read_text(encoding="utf-8")).get("label") or a["label"]
        except (OSError, ValueError):
            pass
    return a["label"]


def live(run: str, now_ms: int, d0: int) -> dict:
    db = T / run / "trader.db"
    if not db.exists():
        return {"run": run, "alive_s": None, "signals": 0, "orders": 0, "fills": 0, "pauses": "no ledger"}
    con = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True, timeout=5)
    try:
        lat = con.execute("SELECT MAX(event_ms) FROM rows WHERE tbl='latency'").fetchone()[0]
        n = {t: con.execute("SELECT count(*) FROM rows WHERE tbl=? AND event_ms >= ?", (t, d0)).fetchone()[0]
             for t in ("speed_events", "orders", "fills")}
        last = {}
        for b, ev in con.execute("SELECT body, event_ms FROM rows WHERE tbl='trips' ORDER BY id"):
            x = json.loads(b)
            last[x["scope"]] = (ev, x.get("state") or x.get("level"), x.get("reason", ""))
    finally:
        con.close()
    paused = [f"{scope}: {why[:60]} (since {dt.datetime.fromtimestamp(ev / 1000, IST):%d %b %H:%M})"
              for scope, (ev, st, why) in last.items() if st != "ACTIVE"]
    return {"run": run, "alive_s": (now_ms - lat) / 1000 if lat else None, "signals": n["speed_events"],
            "orders": n["orders"], "fills": n["fills"], "pauses": "; ".join(paused)}


def live_money(d: pathlib.Path) -> dict:
    """The REAL-money run (trader.loop --live --dir data/trader/live): start cash and every fill with its result.
    Winners are paid on the ledger at settlement, but the wallet gets the cash only after a manual redeem."""
    db = d / "trader.db"
    if not db.exists():
        return {"cash0": None, "fills": []}
    con = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True, timeout=5)
    try:
        q = lambda t: [(json.loads(b), ev) for b, ev in con.execute("SELECT body, event_ms FROM rows WHERE tbl=? ORDER BY id", (t,))]
        runs, fills, sets, orders = q("runs"), q("fills"), q("settlements"), q("orders")
    finally:
        con.close()
    won = {s["cid"]: s["winner"] for s, _ in sets}
    limit = {o["order_id"]: o["price"] for o, _ in orders if o.get("side") == "BUY"}
    out = []
    for f, ev in fills:
        f = dict(f)
        lim = limit.get(f.get("order_id")) if f.get("strategy") != "doctor" else None
        if f["side"] == "BUY" and lim:   # the venue spends size x limit and pays the price improvement in extra shares
            f["size"], f["price"] = f["size"] * lim / f["price"], f["price"]
            cost = f["size"] * f["price"] + f["fee"]
        else:
            cost = f["price"] * f["size"] + f["fee"] if f["side"] == "BUY" else -(f["price"] * f["size"] - f["fee"])
        res = None if f["cid"] not in won else (won[f["cid"]] == f.get("token_id"))
        pay = 0.0 if res is None else (f["size"] if res else 0.0) * (1 if f["side"] == "BUY" else -1)
        ev = _ms(ev)
        out.append({"t": ev, "side": f["side"], "price": f["price"], "size": f["size"], "cost": cost, "won": res,
                    "pnl": None if res is None else pay - cost, "cid": f["cid"], "token": f.get("token_id"),
                    "strategy": f.get("strategy", "")})
    return {"cash0": runs[0][0].get("cash0") if runs else None, "fills": out}


def _ms(t: int) -> int:
    return t // 1000 if t > 10**14 else t   # live venue fills arrive stamped in microseconds (12 Nov)


_MKT: dict = {}


def market_label(cid: str, token: str | None) -> dict:
    """{'side': 'Up'/'Down', 'len': '5-min', 'window': '20:15-20:20'} from the crawler snapshots (cached per cid)."""
    if cid not in _MKT:
        for snap in sorted((ROOT / "data" / "markets").glob("*Z.jsonl"), reverse=True)[:40]:
            for line in snap.read_text(encoding="utf-8").splitlines():
                if cid in line:
                    r = json.loads(line)
                    if r.get("condition_id") == cid:
                        _MKT[cid] = r
                        break
            if cid in _MKT:
                break
    r = _MKT.get(cid)
    if not r:
        return {"side": "?", "len": "", "window": "unknown market"}
    outs = r.get("outcomes") or ["Up", "Down"]
    side = outs[0] if token == r.get("yes_token_id") else outs[1] if token == r.get("no_token_id") else "?"
    slug = r.get("event_slug", "")
    mins = 15 if "-15m-" in slug else 5 if "-5m-" in slug else None
    try:
        start = dt.datetime.fromtimestamp(int(slug.rsplit("-", 1)[1]), IST)
        window = f"{start:%H:%M}-{start + dt.timedelta(minutes=mins or 0):%H:%M}"
    except (ValueError, IndexError):
        window = r.get("question", "")
    return {"side": side, "len": f"{mins}-min" if mins else "", "window": window}


def plain_reason(reason: str) -> str:
    if reason.startswith("daily drawdown"):
        lim = reason.split("> ")[1].split(" ")[0] if "> " in reason else "the limit"
        return (f"the account fell more than {lim} below today's start (settled losses; open 5/15-min bets count at what "
                "was paid). This is the daily safety stop.")
    if reason.startswith("strategy daily loss"):
        lim = reason.split("> ")[1].split(" ")[0] if "> " in reason else "the limit"
        return f"the strategy lost more than ${lim} today. This is the daily loss stop."
    if reason.startswith("stale feed"):
        return "a price feed went quiet. It lifts itself once the feed has been back for a few minutes."
    if "unresolved" in reason:
        return "an order got no answer from Polymarket within 30 s. Check the bot window before resetting."
    return reason


def _q(db: pathlib.Path, tbls) -> list[tuple[str, int, dict]]:
    if not db.exists():
        return []
    con = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True, timeout=5)
    try:
        return [(t, _ms(ev), json.loads(b)) for t, ev, b in con.execute(
            f"SELECT tbl, event_ms, body FROM rows WHERE tbl IN ({','.join('?' * len(tbls))}) ORDER BY id", tbls)]
    finally:
        con.close()


def claims(path: pathlib.Path | None = None) -> list[dict]:
    """ops/claimer.py's log: one row per claim attempt (per-account path when two wallets run)."""
    p = path or (T / "claims.jsonl")
    try:
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    except (OSError, ValueError):
        return []


def live_state(now_ms: int | None = None, account: str = "live") -> dict:
    """Everything the /live page shows, as JSON: status, stop gauge, money, P&L curve, bets, signal feed, comparison.
    Money uses the venue's sizing (live_money); session.json (written by the launcher) gives the stop and length."""
    from ops import live_vs_paper as V
    acct = live_account(account)
    now_ms = now_ms or int(time.time() * 1000)
    now = dt.datetime.fromtimestamp(now_ms / 1000, IST)
    d0 = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
    d = acct["dir"]
    try:
        switch = json.loads(acct["switch"].read_text(encoding="utf-8")).get("live") is True
    except (OSError, ValueError):
        switch = False
    try:
        sess = json.loads((d / "session.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        sess = {}
    m, st = live_money(d), live(account, now_ms, d0)
    rows = _q(d / "trader.db", ("marks", "trips", "speed_events", "decisions", "settlements", "runs"))
    up = st["alive_s"] is not None and st["alive_s"] < 180
    trips = {}
    for t, ev, b in rows:
        if t == "trips":
            trips[b["scope"]] = (ev, b.get("state") or b.get("level"), b.get("reason", ""))
    paused = [(s, ev, why) for s, (ev, stt, why) in trips.items() if stt != "ACTIVE"]
    marks = next((b for t, _, b in reversed(rows) if t == "marks"), {})
    started = next((ev for t, ev, _ in rows if t == "runs"), None)
    settle_t = {(b["cid"], b.get("token_id")): ev for t, ev, b in rows if t == "settlements"}
    bets = [f for f in m["fills"] if f["strategy"] != "doctor" and f["side"] == "BUY"]
    cash0 = m["cash0"]
    label = sess.get("label") or _account_label(account)
    if not up:
        state, head = "stopped", "Not running"
        why = "Nothing is being bought or sold." + (" The live switch is still ON: check the bot window." if switch else "")
    elif paused:
        state, head = "paused", f"PAUSED since {dt.datetime.fromtimestamp(paused[0][1] / 1000, IST):%H:%M}"
        why = "Why: " + plain_reason(paused[0][2]) + " Bets already placed still settle; it buys nothing new until reset."
    elif started and now_ms < started + 120_000:
        state, head = "warmup", "Warming up"
        why = "The first 2 minutes after a start it only watches, so it cannot buy into a move others already priced."
    else:
        state, head = "running", "Running and trading"
        why = "Watching BTC. A move of about 0.06% in 2 seconds triggers a bet on the 5- and 15-minute BTC markets."
    open_b, done = [f for f in bets if f["won"] is None], [f for f in bets if f["won"] is not None]
    settled = sum(f["pnl"] for f in done)
    dd = float(sess.get("daily_stop", 0.20))
    limit = dd * cash0 if cash0 else None
    series, cum = [], 0.0
    for f in sorted(done, key=lambda f: settle_t.get((f["cid"], f["token"]), f["t"])):
        cum += f["pnl"]
        series.append([settle_t.get((f["cid"], f["token"]), f["t"]), round(cum, 4)])

    def bet(f):
        lab = market_label(f["cid"], f["token"])
        end = _MKT.get(f["cid"], {}).get("end_time")
        end_ms = int(dt.datetime.fromisoformat(end.replace("Z", "+00:00")).timestamp() * 1000) if end else None
        mins = 15 if lab["len"] == "15-min" else 5
        return {"t": f["t"], "side": lab["side"], "len": lab["len"], "window": lab["window"], "price": f["price"],
                "shares": f["size"], "cost": f["cost"], "won": f["won"], "pnl": f["pnl"], "end_ms": end_ms,
                "start_ms": end_ms - mins * 60_000 if end_ms else None, "bid": marks.get(f["token"]),
                "win_pnl": f["size"] - f["cost"], "lose_pnl": -f["cost"]}

    orders = V.live_orders(d) if (d / "journal.jsonl").exists() else []
    feed = []
    for t, ev, b in rows:
        if t != "speed_events" or ev < (started or 0):
            continue
        mk = []
        for cid, skip in (b.get("markets") or {}).items():
            lab = market_label(cid, None)
            o = next((x for x in orders if x["cid"] == cid and abs(x["ts"] - ev) <= 5_000), None)
            if skip == "trade" and o:
                res, cls = (f"bought at {o['price']:.2f}", "pos") if o["filled"] else (
                    V.refusal_label(o["why"]), "neg") if o["refused"] else ("missed: shares gone", "neg")
            elif skip == "trade":
                res, cls = "refused: paused", "neg"
            else:
                res, cls = skip, "mut"
            mk.append({"len": lab["len"] or "market", "window": lab["window"], "res": res, "cls": cls})
        feed.append({"t": ev, "bp": b.get("move_bp", 0.0), "dir": "UP" if b.get("dir", 0) > 0 else "DOWN", "markets": mk})
    try:
        _, cmp = V.compare(account)
    except Exception:  # noqa: BLE001
        cmp = None
    try:
        speed = V.timing(d)
    except Exception:  # noqa: BLE001
        speed = None
    cl = claims(acct["claims"])
    return {"now": now_ms, "account": account, "label": label, "accounts": [
                {"id": k, "label": _account_label(k)} for k in ACCOUNTS],
            "state": state, "head": head, "why": why, "switch": switch, "alive_s": st["alive_s"],
            "started": started,
            "ends": (started + int(sess.get("minutes") or 0) * 60_000
                     if started and int(sess.get("minutes") or 0) > 0 else None),
            "cash0": cash0, "settled": settled, "daily_stop": dd, "limit": limit,
            "open_cost": sum(f["cost"] for f in open_b), "best": sum(f["size"] - f["cost"] for f in open_b),
            "redeem": sum(f["size"] for f in done if f["won"] and f["cid"] not in {c["cid"] for c in cl if c.get("ok")}),
            "claimed": [c for c in cl if c.get("ok") and c["ts"] >= (started or 0)][::-1][:10],
            "claim_errors": [c for c in cl if not c.get("ok") and c["ts"] >= (started or 0)][::-1][:3],
            "wins": sum(1 for f in done if f["won"]),
            "losses": sum(1 for f in done if not f["won"]), "series": series,
            "open": [bet(f) for f in sorted(open_b, key=lambda f: f["t"])],
            "done": [bet(f) for f in sorted(done, key=lambda f: -f["t"])], "feed": feed[::-1][:30], "cmp": cmp,
            "speed": speed}


def live_section(now_ms: int, d0: int, account: str = "live") -> list[str]:
    """One real-money account, explained in plain words: status, money, open and settled bets, to-dos, timeline."""
    acct = live_account(account)
    d, e = acct["dir"], html.escape
    label = _account_label(account)
    hm = lambda t: f"{dt.datetime.fromtimestamp(t / 1000, IST):%H:%M:%S}"
    try:
        switch = json.loads(acct["switch"].read_text(encoding="utf-8")).get("live") is True
    except (OSError, ValueError):
        switch = False
    m, st = live_money(d), live(account, now_ms, d0)
    rows = _q(d / "trader.db", ("marks", "trips", "speed_events", "decisions", "settlements", "runs"))
    up = st["alive_s"] is not None and st["alive_s"] < 180
    trips = {}
    for t, ev, b in rows:
        if t == "trips":
            trips[b["scope"]] = (ev, b.get("state") or b.get("level"), b.get("reason", ""))
    paused = [(s, ev, why) for s, (ev, stt, why) in trips.items() if stt != "ACTIVE"]
    marks = next((b for t, _, b in reversed(rows) if t == "marks"), {})
    bets = [f for f in m["fills"] if f["strategy"] != "doctor" and f["side"] == "BUY"]
    test = [f for f in m["fills"] if f["strategy"] == "doctor"]
    open_b = [f for f in bets if f["won"] is None]
    done = [f for f in bets if f["won"] is not None]
    pnl_done = sum(f["pnl"] for f in done)   # the doctor's test trade is left out: it happened before cash0 was read
    test_cost = sum(f["cost"] for f in test)
    cash0 = m["cash0"]
    start_cmd = f"ops\\start_live_v4.ps1" + ("" if account == "live" else f" -Account {account}")

    # 1. status banner
    if not up:
        cls, head, body = "warn", "The live bot is not running", (
            f"Nothing is being bought or sold. Start it with <code>{e(start_cmd)}</code>."
            + (" The live switch is still ON: the launcher turns it off when it stops, so check the bot window." if switch else ""))
    elif paused:
        s, ev, why = paused[0]
        cls, head = "warn", f"Running, but PAUSED since {hm(ev)}: it will not buy anything new"
        body = (f"Why: {e(plain_reason(why))} The bot keeps watching BTC and logs every signal it refuses. Bets already "
                "placed still settle normally. It stays paused until someone resets it.")
    else:
        cls, head, body = "ok", "Running and trading", (
            "It watches the BTC price every moment. When BTC moves about 0.06% in 2 seconds it buys the matching "
            "Up or Down bet on Polymarket's 5- and 15-minute BTC markets, 5 shares each, and holds it until the market settles.")
    L = [f"<h2>LIVE: {e(label)} ({e(account)}) · BTC v4 · <a href='/live?account={e(account)}'>open the live view →</a></h2>",
         f"<div class='banner {cls}'><b>{head}</b><br>{body}</div>"]

    # 2. money
    if cash0 is not None:
        open_cost = sum(f["cost"] for f in open_b)
        now_val = sum((marks.get(f["token"]) or 0.0) * f["size"] for f in open_b)   # a mark is None when nobody bids
        best = sum(f["size"] - f["cost"] for f in open_b)
        L.append("<div class=cards>"
                 f"<div class=card><div class=k>Started with</div><div class=v>${cash0:.2f}</div></div>"
                 f"<div class=card><div class=k>Settled so far</div><div class=v>{money(pnl_done)}</div>"
                 f"<div class=sub>{len(done)} bet(s) settled"
                 + (f"; the pre-start test trade cost ${test_cost:.2f} (already out of the start cash)" if test else "")
                 + "</div></div>"
                 f"<div class=card><div class=k>Open bets</div><div class=v>{len(open_b)}</div>"
                 f"<div class=sub>${open_cost:.2f} paid · worth ${now_val:.2f} if sold now</div></div>"
                 f"<div class=card><div class=k>Today ends between</div><div class=v>{money(pnl_done - open_cost)} "
                 f"and {money(pnl_done + best)}</div><div class=sub>if every open bet loses / wins · "
                 f"wallet ${cash0 + pnl_done - open_cost:.2f} to ${cash0 + pnl_done + best:.2f}</div></div>"
                 "</div>")

    # 3. open bets
    if open_b:
        L.append("<h3>Open bets</h3>")
        for f in sorted(open_b, key=lambda f: f["t"]):
            lab, bid = market_label(f["cid"], f["token"]), marks.get(f["token"])
            end = _MKT.get(f["cid"], {}).get("end_time")
            left = ""
            if end:
                secs = dt.datetime.fromisoformat(end.replace("Z", "+00:00")).timestamp() - now_ms / 1000
                left = f" · settles in {int(secs // 60)} min {int(secs % 60)} s" if secs > 0 else " · market closed, waiting for the result"
            L.append(f"<div class=bet><b>BTC goes {e(lab['side']).upper()}</b> in the {lab['len']} market {e(lab['window'])} IST{left}<br>"
                     f"Bought {f['size']:.2f} shares at {f['price']:.2f} at {hm(f['t'])} → paid ${f['cost']:.2f}. "
                     f"Pays <b>${f['size']:.2f}</b> if BTC goes {e(lab['side'])}, $0 if not "
                     f"(<span class=pos>+${f['size'] - f['cost']:.2f}</span> / <span class=neg>−${f['cost']:.2f}</span>)."
                     + (f" Right now you could sell for {bid:.2f} a share (${bid * f['size']:.2f})." if bid is not None else "")
                     + "</div>")

    # 4. settled bets, with paper_v4b's price for the same bet
    paper = {}
    for t, ev, b in _q(T / "paper_v4b" / "trader.db", ("fills",)):
        if b.get("side") == "BUY" and ev >= d0:
            paper.setdefault(b.get("token_id"), b["price"])
    if done:
        L.append("<h3>Settled bets</h3><table><tr><th>Bought (IST)</th><th>Bet</th><th>Price</th><th>Paid</th>"
                 "<th>Result</th><th>P&amp;L</th><th>Paper v4b paid</th></tr>")
        for f in sorted(done, key=lambda f: -f["t"]):
            lab, pp = market_label(f["cid"], f["token"]), paper.get(f["token"])
            L.append(f"<tr><td>{hm(f['t'])}</td><td>BTC {e(lab['side'])} · {lab['len']} {e(lab['window'])}</td>"
                     f"<td>{f['price']:.2f}</td><td>${f['cost']:.2f}</td>"
                     f"<td class={'pos' if f['won'] else 'neg'}>{'WON' if f['won'] else 'lost'}</td><td>{money(f['pnl'])}</td>"
                     f"<td>{'' if pp is None else f'{pp:.2f}'}</td></tr>")
        L.append("</table>")

    # 5. to-do
    todo = []
    claimed_cids = {c["cid"] for c in claims(acct["claims"]) if c.get("ok")}
    redeem = sum(f["size"] for f in done if f["won"] and f["cid"] not in claimed_cids)
    if redeem:
        todo.append(f"Redeem <b>${redeem:.2f}</b> of winnings on polymarket.com (the bot cannot do it yet).")
    if paused:
        todo.append("The bot is paused. Ask Claude before resetting it.")
    if switch and not up:
        rel = acct["switch"].relative_to(ROOT)
        todo.append(f"The live switch is ON but no bot is running: set <code>{e(str(rel))}</code> back to "
                    "<code>{\"live\": false}</code>.")
    if todo:
        L.append("<div class='banner todo'><b>To do</b><ul>" + "".join(f"<li>{x}</li>" for x in todo) + "</ul></div>")

    # 6. timeline, newest first
    ev_l = []
    for t, ev, b in rows:
        if ev < d0:
            continue
        if t == "runs":
            ev_l.append((ev, f"Bot started with ${b.get('cash0', 0):.2f}.", ""))
        elif t == "speed_events":
            what = "UP" if b.get("dir", 0) > 0 else "DOWN"
            parts = []
            for cid, why in (b.get("markets") or {}).items():
                lab = market_label(cid, None)
                parts.append(f"{lab['len'] or 'market'}: " + ("tried to buy" if why == "trade" else e(why)))
            ev_l.append((ev, f"Signal: BTC moved {b.get('move_bp', 0):+.1f} bp ({b.get('move_bp', 0) / 100:+.2f}%) in 2 s "
                             f"→ look for {what} bets. " + "; ".join(parts) + ".", ""))
        elif t == "decisions" and not b.get("approved"):
            ev_l.append((ev, f"Refused to buy at {b.get('price', 0):.2f}: "
                             + ("paused by the safety stop." if b.get("class") == "REDUCING" else e(b.get("reason", "")[:80])), "neg"))
        elif t == "trips" and (b.get("state") or b.get("level")) != "ACTIVE":
            ev_l.append((ev, "PAUSED: " + e(plain_reason(b.get("reason", ""))), "neg"))
        elif t == "trips":
            ev_l.append((ev, "Pause lifted.", "pos"))
        elif t == "settlements":
            f = next((x for x in bets if x["token"] == b.get("token_id")), None)
            lab = market_label(b["cid"], b.get("token_id"))
            res = "won" if b.get("winner") == b.get("token_id") else "lost"
            ev_l.append((ev, f"Settled: BTC {e(lab['side'])} {lab['len']} {e(lab['window'])} {res}"
                             + (f" ({'+' if f['pnl'] >= 0 else '−'}${abs(f['pnl']):.2f})." if f and f["pnl"] is not None else "."),
                         "pos" if res == "won" else "neg"))
    for f in bets:
        if f["t"] >= d0:
            lab = market_label(f["cid"], f["token"])
            ev_l.append((f["t"], f"BOUGHT {f['size']:.2f} × BTC {e(lab['side'])} ({lab['len']} {e(lab['window'])}) at "
                                 f"{f['price']:.2f}, paid ${f['cost']:.2f}.", ""))
    if ev_l:
        L.append("<h3>What happened today</h3><ul class=tl>" + "".join(
            f"<li><span class=t>{hm(ev)}</span> <span class={c}>{txt}</span></li>" for ev, txt, c in sorted(ev_l, key=lambda x: -x[0])[:25])
            + "</ul>")
    L += live_vs_paper_section(account)
    L.append("<p class=sub>A share pays $1 if its side wins and $0 if not, so price 0.53 = the market thinks a 53% chance. "
             "bp = basis point = 0.01%. Times are IST. The bot never redeems: winnings reach the wallet when you redeem them. "
             "A buy spends 5 x its limit price; filling cheaper gives extra shares, which the figures here include.</p>")
    return L


def live_vs_paper_section(account: str = "live") -> list[str]:
    """Real orders vs paper_v4b on the same signals, all sessions of this live account."""
    from ops import live_vs_paper as V
    try:
        rows, s = V.compare(account)
    except Exception as ex:  # noqa: BLE001 - the comparison must never take the page down
        return [f"<p class=neg>live vs paper: {html.escape(repr(ex))[:200]}</p>"]
    if not rows:
        return []
    gap = "" if s["gap"] is None else f"{s['gap']:+.3f}"
    pct = lambda p, c: f" ({100 * p / c:+.1f}% of the money put in)" if c else ""
    return ["<h3>Live vs the paper twin (same signals, every live session)</h3>",
            "<div class=cards>"
            f"<div class=card><div class=k>Live orders</div><div class=v>{s['orders']}</div>"
            f"<div class=sub>{s['filled']} filled · {s['paused']} while paused (not counted)</div></div>"
            f"<div class=card><div class=k>Missed where paper filled</div><div class=v>{s['missed_paper_filled']} of {s['paper_had']}</div>"
            "<div class=sub>lost races only: faster traders took the shares first</div></div>"
            f"<div class=card><div class=k>Refused by Polymarket</div><div class=v>{s['refused']}</div>"
            f"<div class=sub>not a race: the venue rejected the order ({s['refused_paper_filled']} where paper filled)</div></div>"
            f"<div class=card><div class=k>Live paid more than paper</div><div class=v>{gap}</div>"
            f"<div class=sub>per share, when both filled (n {s['n_gap']})</div></div>"
            f"<div class=card><div class=k>Settled result</div><div class=v>{money(s['live_pnl'])}</div>"
            f"<div class=sub>live{pct(s['live_pnl'], s['live_spend'])} · paper on the same markets {s['paper_pnl']:+.2f}</div></div>"
            "</div><p class=sub>Judge v4 after about 50 live orders: if live keeps missing or paying well over paper, the edge "
            "is not reachable from this PC. Full table: reports/research/live_vs_paper.md (nightly).</p>"]


def returns(rows: list[dict]) -> tuple[list[str], list[str], dict, dict]:
    """(days, runs, cell[(day, run)] -> live $, per-run summary) from the per-trade CSV rows."""
    cell = {}
    per = {r: {"x": [], "g": [], "paper": 0.0} for r in ACTIVE}   # an active run with no settled trade yet still gets its column
    for r in rows:
        k = (r["day_ist"], r["run"])
        cell[k] = cell.get(k, 0.0) + float(r["live_est_pnl"])
        p = per.setdefault(r["run"], {"x": [], "g": [], "paper": 0.0})
        p["x"].append(float(r["live_est_pnl"]))
        p["g"].append(r["market"])
        p["paper"] += float(r["paper_pnl"])
    for run, p in per.items():
        n, total = len(p["x"]), sum(p["x"])
        p.update(n=n, total=total, mean=total / n if n else None, se=scorer.cluster_se(p["x"], p["g"]) if n else None,
                 start=RUNS.get(run, 50.0))
    days = sorted({d for d, _ in cell})
    runs = sorted(per, key=lambda r: (r not in ACTIVE, -per[r]["total"]))
    return days, runs, cell, per


def refresher() -> None:
    from ops import real_outcomes
    while True:
        try:
            real_outcomes.main([])   # every run, as the day-wise report does
            state.update(refreshed=dt.datetime.now(IST), error=None)
        except Exception as e:  # noqa: BLE001 - keep serving the last good CSV
            state["error"] = repr(e)[:200]
        time.sleep(REFRESH_S)


def hub_line() -> str:
    try:
        lines = (T / "feedhub_console.log").read_text(encoding="utf-8", errors="replace").splitlines()[-400:]
    except OSError:
        return "hub log not found"
    return next((l for l in reversed(lines) if l.startswith("hub data:")), "no data-meter line yet")


def keeper_lines(k: int = 4) -> list[str]:
    try:
        lines = (T / "paper_tasks.log").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return [l for l in lines if "[keep]" in l][-k:]


def money(x) -> str:
    return "" if x is None else f'<span class="{"pos" if x > 0 else "neg" if x < 0 else ""}">{x:+.2f}</span>'


def page() -> str:
    now = dt.datetime.now(IST)
    now_ms, d0 = int(now.timestamp() * 1000), int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
    lv = [live(r, now_ms, d0) for r in ACTIVE]
    try:
        with open(CSV, newline="", encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r["run"] in ACTIVE]   # 15 Nov: retired runs off the page (data kept)
    except OSError:
        rows = []
    days, runs, cell, per = returns(rows)
    e = html.escape
    L = [f"<h1>Live + paper runs</h1><p class=sub>{now:%a %d %b %Y, %H:%M:%S} IST · reloads every 60 s · "
         f"returns refreshed {state['refreshed']:%H:%M} IST" if state["refreshed"] else
         f"<h1>Live + paper runs</h1><p class=sub>{now:%a %d %b %Y, %H:%M:%S} IST · reloads every 60 s · "
         "returns: first refresh running"]
    L[-1] += (f" · <span class=neg>refresh error: {e(state['error'])}</span>" if state["error"] else "") + "</p>"
    for acct_id in ACCOUNTS:
        L += live_section(now_ms, d0, acct_id)
    L += ["<h2>Now</h2><table><tr><th>Run</th><th>Strategy</th><th>Loop</th><th>State</th><th>Signals today</th>"
          "<th>Orders</th><th>Fills</th></tr>"]
    for r in lv:
        up = r["alive_s"] is not None and r["alive_s"] < 180
        L.append(f"<tr><td>{r['run']}</td><td>{LABEL.get(r['run'], '')}</td>"
                 f"<td class={'pos' if up else 'neg'}>{'alive' if up else 'DOWN'}"
                 f"{f' ({r['alive_s']:.0f} s)' if r['alive_s'] is not None else ''}</td>"
                 f"<td class={'neg' if r['pauses'] else 'pos'}>{e(r['pauses']) or 'ACTIVE'}</td>"
                 f"<td>{r['signals']}</td><td>{r['orders']}</td><td>{r['fills']}</td></tr>")
    L += [f"</table><p class=sub>{e(hub_line())}</p>",
          "<p class=sub>Keeper: " + " · ".join(e(k) for k in keeper_lines()) + "</p>"]
    L += ["<h2>Live estimate per day (USD, real Polymarket prices)</h2><table><tr><th>Day</th>"
          + "".join(f"<th>{LABEL.get(r, r)}</th>" for r in runs) + "<th>Day total</th></tr>"]
    for d in days:
        vals = [cell.get((d, r)) for r in runs]
        L.append(f"<tr><td>{d}</td>" + "".join(f"<td>{money(v)}</td>" for v in vals)
                 + f"<td><b>{money(sum(v for v in vals if v is not None))}</b></td></tr>")
    L.append("<tr class=tot><td>Total</td>" + "".join(f"<td>{money(per[r]['total'])}</td>" for r in runs)
             + f"<td>{money(sum(per[r]['total'] for r in runs))}</td></tr></table>")
    L += ["<h2>Balances and evidence</h2><table><tr><th>Run</th><th>Start</th><th>Live balance</th><th>Return</th>"
          "<th>Trades</th><th>Live $/trade</th><th>± SE</th><th>Over 2 SE?</th><th>Paper P&amp;L</th></tr>"]
    for r in runs:
        p = per[r]
        over = p["mean"] is not None and p["se"] and p["mean"] > 2 * p["se"]
        L.append(f"<tr><td>{r}{'' if r in ACTIVE else ' <span class=sub>(retired)</span>'}</td><td>${p['start']:.2f}</td>"
                 f"<td>${p['start'] + p['total']:.2f}</td><td>{money(100 * p['total'] / p['start'])}%</td><td>{p['n']}</td>"
                 f"<td>{money(p['mean'])}</td><td>{'' if p['se'] is None else f'{p['se']:.2f}'}</td>"
                 f"<td class={'pos' if over else ''}>{'yes' if over else 'not yet'}</td><td>{money(p['paper'])}</td></tr>")
    L.append("</table><p class=sub>Live estimate: each paper trade repriced at real tape prices, our order behind the "
             "real takers that beat us. Maker runs show here once they have fills. Days are IST; a trade counts once "
             "its market has settled.</p>")
    return ("<!doctype html><html lang=en><head><meta charset=utf-8><meta http-equiv=refresh content=60>"
            "<meta name=viewport content='width=device-width,initial-scale=1'><title>Live + paper runs</title><style>"
            ":root{--bg:#fafaf9;--fg:#1c1917;--mut:#78716c;--line:#e7e5e4;--pos:#15803d;--neg:#b91c1c;--card:#fff}"
            "@media (prefers-color-scheme:dark){:root{--bg:#1c1917;--fg:#f5f5f4;--mut:#a8a29e;--line:#44403c;"
            "--pos:#4ade80;--neg:#f87171;--card:#292524}}"
            "body{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;margin:0 auto;max-width:1100px;"
            "padding:16px}h1{margin:0 0 4px}h2{margin:24px 0 8px;font-size:16px}.sub{color:var(--mut);font-size:12px}"
            "table{border-collapse:collapse;width:100%;background:var(--card);display:block;overflow-x:auto}"
            "th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:right;white-space:nowrap}"
            "th:first-child,td:first-child,td:nth-child(2){text-align:left}th{color:var(--mut);font-weight:600}"
            ".pos{color:var(--pos)}.neg{color:var(--neg)}tr.tot td{font-weight:700;border-top:2px solid var(--line)}"
            "h3{margin:18px 0 6px;font-size:14px}code{font-size:12px}"
            ".banner{border-radius:8px;padding:10px 14px;margin:8px 0;border:1px solid var(--line);background:var(--card)}"
            ".banner.ok{border-left:6px solid var(--pos)}.banner.warn{border-left:6px solid #d97706}"
            ".banner.todo{border-left:6px solid #2563eb}.banner ul{margin:4px 0 0 18px;padding:0}"
            ".cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px;margin:8px 0}"
            ".card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px}"
            ".card .k{color:var(--mut);font-size:12px}.card .v{font-size:20px;font-weight:700}"
            ".bet{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin:6px 0}"
            "ul.tl{list-style:none;padding:0;margin:0;background:var(--card);border:1px solid var(--line);border-radius:8px}"
            "ul.tl li{padding:6px 10px;border-bottom:1px solid var(--line)}ul.tl .t{color:var(--mut);font-variant-numeric:tabular-nums;margin-right:8px}"
            "</style></head><body>" + "\n".join(L) + "</body></html>")


def summary() -> dict:
    """The "Now" rows plus today's and the total live estimate per run, for the Claude pane (/status.json)."""
    now = dt.datetime.now(IST)
    now_ms, d0 = int(now.timestamp() * 1000), int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
    try:
        with open(CSV, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except OSError:
        rows = []
    _, _, cell, per = returns(rows)
    today = f"{now:%Y-%m-%d}"
    runs = [{**live(r, now_ms, d0), "label": LABEL.get(r, ""), "today": cell.get((today, r)),
             "total": per[r]["total"] if r in per else None, "n": per[r]["n"] if r in per else 0} for r in ACTIVE]
    return {"at": f"{now:%d %b %H:%M:%S} IST", "runs": runs, "hub": hub_line(),
            "today_total": sum(v for (d, _), v in cell.items() if d == today),
            "all_total": sum(p["total"] for p in per.values()),
            "refreshed": f"{state['refreshed']:%H:%M}" if state["refreshed"] else None, "error": state["error"]}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        from urllib.parse import parse_qs, urlparse
        u = urlparse(self.path)
        path, qs = u.path, parse_qs(u.query)
        if path not in ("/", "/index.html", "/status.json", "/live", "/live.json"):
            self.send_error(404)
            return
        account = (qs.get("account") or ["live"])[0]
        if account not in ACCOUNTS:
            self.send_error(404, f"unknown account {account}")
            return
        kind = "application/json" if path.endswith(".json") else "text/html; charset=utf-8"
        try:
            body = (json.dumps(summary()) if path == "/status.json" else json.dumps(live_state(account=account), default=str)
                    if path == "/live.json" else (ROOT / "ops" / "live_page.html").read_text(encoding="utf-8")
                    if path == "/live" else page())
            body, code = body.encode("utf-8"), 200
        except Exception as ex:  # noqa: BLE001 - a broken read shows as a page, never kills the server
            body, code = f"<pre>dashboard error: {html.escape(repr(ex))}</pre>".encode(), 500
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def main() -> int:
    threading.Thread(target=refresher, daemon=True).start()
    print(f"paper-runs dashboard on http://127.0.0.1:{PORT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()   # localhost only
    return 0


if __name__ == "__main__":
    sys.exit(main())
