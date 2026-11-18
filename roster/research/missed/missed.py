"""Missed-opportunity analysis for one IST day of one paper run (read-only on the ledger; public CLOB GETs for outcomes).

  python research\\missed\\missed.py [run, default paper14] [--day YYYY-MM-DD (IST), default today]

A. btc-speed fills: actual result (buy + any exit sale) vs hold to resolution vs exit at the 5 s / 60 s markout
   (mid - 1c, taker fee).
B. btc-speed signals not traded, by reason (kernel pause, guards, unfilled taker): how many would have won held, and
   the held P&L at the ask seen where the ledger has it (guard skips before the book check have no ask).
C. ladder-maker: fills and their settlement; model edge at the 24 h / 6 h / 1 h checkpoints vs the outcome (buying the
   side the model favoured, at mid, when |fair - mid| > 3c: what the model would have made); log-only arbitrage.
"""
import argparse
import collections
import datetime as dt
import json
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from nightly import scorer  # noqa: E402

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
fee = lambda p: 0.07 * p * (1 - p)
EDGE = 0.03


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", nargs="?", default="paper14")
    ap.add_argument("--day", default=str(dt.datetime.now(IST).date()))
    a = ap.parse_args(argv)
    d = ROOT / "data" / "trader" / a.run
    t0 = int(dt.datetime.fromisoformat(a.day).replace(tzinfo=IST).timestamp() * 1000)
    t1 = t0 + 86_400_000
    con = sqlite3.connect(f"{(d / 'trader.db').resolve().as_uri()}?mode=ro", uri=True)
    rows = lambda t: [(json.loads(b), e) for b, e in con.execute(
        "SELECT body, event_ms FROM rows WHERE tbl = ? AND event_ms >= ? AND event_ms < ? ORDER BY id", (t, t0, t1))]
    ist = lambda ms: dt.datetime.fromtimestamp(ms / 1000, IST).strftime("%H:%M:%S")
    p = d / "outcomes.json"
    oc = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    def outcome(cid):
        if cid not in oc:
            try:
                oc[cid] = scorer.fetch_outcome(cid)
            except Exception:  # noqa: BLE001 - offline: unknown
                oc[cid] = None
        return oc[cid] or {}

    print(f"# {a.run}, {a.day} (IST)\n")
    # ---- A ----
    fills = [f for f, _ in rows("fills")]
    mk = collections.defaultdict(dict)
    for m, _ in rows("markouts"):
        mk[m["order_id"]][m["horizon_s"]] = m
    sp = [f for f in fills if f["strategy"] == "btc-speed"]
    sells = collections.defaultdict(list)
    for f in sp:
        if f["side"] == "SELL":
            sells[f["token_id"]].append(f)
    print("## A. btc-speed fills")
    tot = collections.Counter()
    for f in [f for f in sp if f["side"] == "BUY"]:
        o = outcome(f["cid"])
        won = o.get("winner") == f["token_id"] if o else None
        hold = None if won is None else f["size"] * ((1.0 if won else 0.0) - f["price"]) - f["fee"]
        s = next((x for x in sells[f["token_id"]] if x["ts_ms"] >= f["ts_ms"]), None)
        if s:
            sells[f["token_id"]].remove(s)
        actual = (s["size"] * s["price"] - s["fee"] - f["size"] * f["price"] - f["fee"]) if s else hold
        ex = {}
        for h in (5, 60):
            m = mk[f["order_id"]].get(h)
            if m and m.get("mid") is not None:
                px = m["mid"] - 0.01
                ex[h] = f["size"] * (px - f["price"]) - f["fee"] - f["size"] * fee(px)
        for k, v in (("actual", actual), ("hold", hold), ("exit5", ex.get(5, hold)), ("exit60", ex.get(60, hold))):
            tot[k] += v or 0.0
        fmt = lambda x: "  n/a" if x is None else f"{x:+.2f}"
        print(f"- {ist(f['ts_ms'])} buy {f['size']:.0f} @ {f['price']:.2f}: actual {fmt(actual)}"
              f"{' (sold @ %.2f after %.0f s)' % (s['price'], (s['ts_ms'] - f['ts_ms']) / 1000) if s else ' (held)'}"
              f" | hold {fmt(hold)} | exit 5 s {fmt(ex.get(5))} | exit 60 s {fmt(ex.get(60))}")
    print(f"- **Total: actual {tot['actual']:+.2f} | hold {tot['hold']:+.2f} | exit 5 s {tot['exit5']:+.2f} | "
          f"exit 60 s {tot['exit60']:+.2f}**\n")

    # ---- B ----
    print("## B. btc-speed signals not traded")
    by = collections.defaultdict(lambda: {"n": 0, "won": 0, "known": 0, "pnl": 0.0, "priced": 0, "asks": []})
    filled_orders = {f["order_id"] for f in sp}
    traded = set()
    for t, _ in rows("speed_trades"):
        if t.get("approved") and t.get("order_id") in filled_orders:
            traded.add((t["cid"], t["decision_ms"]))
            continue
        why = "taker not filled (price moved)" if t.get("approved") else t.get("reason", "?").split(":")[0]
        o = outcome(t["cid"])
        r = by[why]
        r["n"] += 1
        if o.get("winner"):
            win = o["winner"] == t["token_id"]
            r["known"] += 1
            r["won"] += win
            if t.get("ask") is not None:
                r["priced"] += 1
                r["pnl"] += 5 * ((1.0 if win else 0.0) - t["ask"]) - 5 * fee(t["ask"])
                r["asks"].append(t["ask"])
    for ev, _ in rows("speed_events"):
        for cid, why in ev["markets"].items():
            if why == "trade":
                continue
            o = outcome(cid)
            r = by[why]
            r["n"] += 1
            if o.get("winner"):
                r["known"] += 1
                r["won"] += (o.get("yes") is True) == (ev["dir"] > 0)
    for why, r in sorted(by.items(), key=lambda kv: -kv[1]["n"]):
        priced = f"; held at the ask seen {r['pnl']:+.2f} over {r['priced']} (asks {min(r['asks']):.2f}-{max(r['asks']):.2f})" if r["priced"] else ""
        print(f"- {why}: {r['n']} market-signals; {r['won']} of {r['known']} resolved would have won{priced}")
    print()

    # ---- C ----
    print("## C. ladder-maker")
    for f in [f for f in fills if f["strategy"] == "ladder-maker"]:
        o = outcome(f["cid"])
        res = "open" if not o else ("WON" if o.get("winner") == f["token_id"] else "lost")
        pnl = "" if not o else f" {f['size'] * ((1.0 if res == 'WON' else 0.0) - f['price']):+.2f}"
        print(f"- fill {ist(f['ts_ms'])} {f['side']} {f['size']:.0f} @ {f['price']:.3f}, "
              f"{(f['end_ms'] - f['ts_ms']) / 60000:.0f} min before close: {res}{pnl}")
    cks = [c for c, _ in rows("universe_checkpoint") if c.get("fair") is not None and c.get("mid_ex_own") is not None]
    seen = collections.defaultdict(lambda: [0, 0, 0.0, 0])  # bucket -> [signals, right, pnl per share, resolved]
    for c in cks:
        e = c["fair"] - c["mid_ex_own"]
        if abs(e) <= EDGE:
            continue
        o = outcome(c["cid"])
        s = seen[c["bucket_h"]]
        s[0] += 1
        if o.get("winner"):
            yes = 1.0 if o.get("yes") else 0.0
            px = c["mid_ex_own"] if e > 0 else 1 - c["mid_ex_own"]
            got = yes if e > 0 else 1 - yes
            s[1] += got == 1.0
            s[2] += got - px - fee(px)
            s[3] += 1
    print(f"- Checkpoints today: {len(cks)}; with |fair - mid| > {EDGE:.2f}:")
    for b, (n, right, pnl, res) in sorted(seen.items(), reverse=True):
        print(f"  - {b} h before close: {n} (resolved {res}): model side right {right}; buying 1 share of the model's side "
              f"at mid (taker fee) each time: {pnl:+.2f} USD")
    arb = [x for x, _ in rows("arb_opportunity")]
    print(f"- Log-only arbitrage rows: {len(arb)}, edge x size {sum(x['edge'] * x['size'] for x in arb):+.2f} USD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
