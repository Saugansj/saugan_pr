"""Every resolved btc-speed paper trade, every run, every day: paper P&L next to the real-price P&L (nightly.scorer
.tape_reprice: best = cheapest real taker price in our order's second, typical = the median). ladder-maker is maker-only
and not repriced (paper only). Writes reports/research/real_outcomes.md and real_outcomes_trades.csv. live estimate =
what a live order would have made: behind the share of that second's real taker volume that beat us (scorer.RACE_AHEAD),
filling what is left at or under our limit, partial fills allowed (live_shares, live_px).

  .venv\\Scripts\\python.exe ops\\real_outcomes.py [run ...]
"""
import collections
import csv
import datetime as dt
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import common  # noqa: E402
from nightly import report, scorer  # noqa: E402
from ops.status import IST, RUNS  # noqa: E402

OUT = ROOT / "reports" / "research"
COLS = ["run", "day_ist", "time_ist", "market", "token", "won", "shares", "paper_fill", "real_min", "real_median",
        "real_prints", "limit", "paper_pnl", "real_best_pnl", "real_typical_pnl", "live_est_pnl", "live_shares", "live_px"]


def run_trades(name: str) -> tuple[list[dict], int, float]:
    """(repriced trade rows, resolved trades, ladder-maker paper P&L) for one run."""
    d = ROOT / "data" / "trader" / name
    t = scorer.tables(d)
    oc = scorer.outcomes(d, t, common.now_ms(), None)
    st = scorer.speed_stat(t.get("fills", []), oc)  # since 0: every version the run has traded
    arr = {s["order_id"]: s["arrival_ms"] for s in t.get("speed_trades", []) if s.get("order_id")}
    limit = {o["order_id"]: o["price"] for o in t.get("orders", [])}
    rows = []
    for r in scorer.tape_reprice(d, st["trades"], arr, scorer.fetch_tape, limit)["trades"]:
        ts = dt.datetime.fromtimestamp(r["ts_ms"] / 1000, IST)
        won = (oc.get(r["cid"]) or {}).get("winner") == r["token_id"] if r["size"] - r["sold"] > 1e-9 else "sold"
        rows.append({"run": name, "day_ist": ts.date().isoformat(), "time_ist": ts.strftime("%H:%M:%S"),
                     "market": r["cid"], "token": r["token_id"], "won": won, "shares": r["size"],
                     "paper_fill": round(r["fill"], 4), "real_min": r["tape_min"], "real_median": r["tape_median"],
                     "real_prints": r["tape_n"], "limit": limit.get(r["order_id"], 1.0), "paper_pnl": round(r["pnl"], 4), "real_best_pnl": round(r["best"], 4),
                     "real_typical_pnl": round(r["typical"], 4),
                     "live_est_pnl": round(r["live"], 4),
                     "live_shares": round(r["live_shares"], 2), "live_px": round(r["live_px"], 4) if r["live_px"] else ""})
    lad = report.pnl(t).get("ladder-maker", {}).get("pnl", 0.0)
    return rows, st["n"], lad


def main(argv=None) -> int:
    names = (argv if argv is not None else sys.argv[1:]) or list(RUNS)
    allrows, L = [], ["# Real outcome of every paper trade", "",
                      f"Written {dt.datetime.now(IST):%d %b %Y %H:%M} IST. Each resolved btc-speed trade's buy repriced at "
                      "what real takers paid for the same token in the second our order would have matched (Polymarket "
                      "public tape; its stamps trail matches ~2-3 s). **Best** = the cheapest real price (as if we won "
                      "the race), **typical** = the median real price. Paper assumes we always won. Per-trade detail: "
                      "`real_outcomes_trades.csv`. **Live estimate** = our 5-share limit order queued behind the real "
                      "takers that beat us, filling what real volume is left at or under the limit (partial fills "
                      "count). Not comparable with versions before 15 Oct (maker legs were mixed into the tape).", ""]
    summary = ["## Totals per run (USD, from the run's start)", "",
               "| Run | Start | Trades (repriced / resolved) | Paper | Real best | Real typical | Live estimate | "
               "ladder-maker (paper only) |", "|---|---|---|---|---|---|---|---|"]
    days = ["## Per day (IST), btc-speed trades that could be repriced", "",
            "| Run | Day | Trades | Paper | Real best | Real typical | Live estimate |", "|---|---|---|---|---|---|---|"]
    for name in names:
        if not (ROOT / "data" / "trader" / name / "trader.db").exists():
            continue
        rows, n, lad = run_trades(name)
        allrows += rows
        s = lambda k, rs=rows: sum(r[k] for r in rs)
        summary.append(f"| {name} | ${RUNS.get(name, 50.0):.2f} | {len(rows)} / {n} | {s('paper_pnl'):+.2f} | "
                       f"{s('real_best_pnl'):+.2f} | {s('real_typical_pnl'):+.2f} | {s('live_est_pnl'):+.2f} | {lad:+.2f} |")
        by = collections.defaultdict(list)
        for r in rows:
            by[r["day_ist"]].append(r)
        for day in sorted(by):
            g = by[day]
            days.append(f"| {name} | {day} | {len(g)} | {s('paper_pnl', g):+.2f} | {s('real_best_pnl', g):+.2f} | "
                        f"{s('real_typical_pnl', g):+.2f} | {s('live_est_pnl', g):+.2f} |")
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "real_outcomes_trades.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, COLS)
        w.writeheader()
        w.writerows(allrows)
    text = "\n".join(L + summary + [""] + days) + "\n"
    (OUT / "real_outcomes.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
