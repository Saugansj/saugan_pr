"""Shadow scorer (16 Oct profit plan A3): the proposed btc-speed filters and order limits scored on the control runs'
own trades at the live estimate (nightly.scorer.tape_reprice), never on paper. A filter is a rule that would have
skipped some of the control's trades; a limit is the same trades repriced with a different order limit. Judged only
on trades from JUDGE_FROM; a decision needs MIN_N eligible trades and 2 cluster SE. Writes reports/research/shadow.md.

  .venv\\Scripts\\python.exe ops\\shadow.py
"""
import datetime as dt
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nightly import scorer  # noqa: E402
from ops.status import IST  # noqa: E402

OUT = ROOT / "reports" / "research" / "shadow.md"
JUDGE_FROM = int(dt.datetime(2026, 10, 17, tzinfo=IST).timestamp() * 1000)
MIN_N = 60
CAP, LIVE_ADD = 0.85, 0.10   # the live rule: limit min(0.85, ask + 10c)
CONTROLS = {"paper_v4b": "BTC", "paper_ethb": "ETH"}
LEFT = lambda t: (t["end_ms"] - t["decision_ms"]) / 1000   # seconds left at the signal
FILTERS = {   # name -> (coins, skip rule on the signal row)
    "v6 band: skip ask 0.30-0.50": ({"BTC", "ETH"}, lambda t: 0.30 <= t["ask"] <= 0.50),
    "skip > 600 s left": ({"BTC"}, lambda t: LEFT(t) > 600),
    "skip move >= 7 bp": ({"ETH"}, lambda t: t["move_bp"] >= 7),
    "15m: skip 5-10 min left": ({"BTC", "ETH"}, lambda t: t["duration_min"] == 15 and 300 <= LEFT(t) <= 600),
    "cap: skip ask > 0.70": ({"BTC"}, lambda t: t["ask"] > 0.70),
}
LIMITS = (0.03, 0.04, LIVE_ADD)


def stat(xs: list[float], groups: list) -> tuple[float | None, float | None]:
    return (sum(xs) / len(xs) if xs else None), scorer.cluster_se(xs, groups)


def call(n: int, m, se, what: str) -> str:
    """'collecting' until MIN_N, then whether m beats 0 by 2 SE."""
    if n < MIN_N or m is None or se is None:
        return f"collecting ({n}/{MIN_N})"
    return what if m > 2 * se else "no change: not 2 SE"


def judge(rows: list[dict], coin: str, since: int = JUDGE_FROM, label: str = "since 17 Oct") -> list[str]:
    """rows: one per repriced control trade, {"sig", "cid", "ts_ms", "live": {add: $}}. Markdown lines."""
    j = [r for r in rows if r["ts_ms"] >= since]
    f = lambda m: "n/a" if m is None else f"{m:+.3f}"
    out = [f"### {coin}, {label} ({len(j)} trades)", "",
           "| Filter | Skipped | Skipped mean $/trade | Kept mean | Verdict |", "|---|---|---|---|---|"]
    for name, (coins, skip) in FILTERS.items():
        if coin not in coins:
            continue
        s = [r for r in j if skip(r["sig"])]
        k = [r for r in j if not skip(r["sig"])]
        ms, se = stat([-r["live"][LIVE_ADD] for r in s], [r["cid"] for r in s])   # a skip gains what the skipped lost
        mk, _ = stat([r["live"][LIVE_ADD] for r in k], [r["cid"] for r in k])
        out.append(f"| {name} | {len(s)} | {f(None if ms is None else -ms)} +/- {"n/a" if se is None else f"{se:.3f}"} | {f(mk)} | "
                   f"{call(len(s), ms, se, 'adopt the skip')} |")
    out += ["", "| Limit (ask + c, cap 0.85) | Live total $ | Mean vs ask+10c, paired $/trade | Verdict |",
            "|---|---|---|---|"]
    for add in LIMITS:
        tot = sum(r["live"][add] for r in j)
        if add == LIVE_ADD:
            out.append(f"| +{add * 100:.0f}c (live rule) | {tot:+.2f} | - | control |")
            continue
        d = [r["live"][add] - r["live"][LIVE_ADD] for r in j]
        m, se = stat(d, [r["cid"] for r in j])
        out.append(f"| +{add * 100:.0f}c | {tot:+.2f} | {f(m)} +/- {"n/a" if se is None else f"{se:.3f}"} | {call(len(j), m, se, 'switch limit')} |")
    return out + [""]


def control_rows(name: str, fetch=scorer.fetch_tape) -> list[dict]:
    d = ROOT / "data" / "trader" / name
    t = scorer.tables(d)
    st = scorer.speed_stat(t.get("fills", []), scorer.outcomes(d, t, scorer.common.now_ms(), None))
    sig = {s["order_id"]: s for s in t.get("speed_trades", []) if s.get("order_id")}
    trades = [x for x in st["trades"] if x["order_id"] in sig]
    arr = {o: s["arrival_ms"] for o, s in sig.items()}
    rows = {x["order_id"]: {"sig": sig[x["order_id"]], "cid": x["cid"], "ts_ms": x["ts_ms"], "live": {}} for x in trades}
    for i, add in enumerate(LIMITS):   # the first pass fetches (and caches) the tape; the rest read the cache
        lim = {o: min(CAP, round(s["ask"] + add, 2)) for o, s in sig.items()}
        for r in scorer.tape_reprice(d, trades, arr, fetch if i == 0 else None, lim)["trades"]:
            rows[r["order_id"]]["live"][add] = r["live"]
    return [r for r in rows.values() if len(r["live"]) == len(LIMITS)]   # only trades the tape could reprice


def main() -> int:
    L = ["# Shadow scores: proposed btc-speed changes on the control runs", "",
         f"Written {dt.datetime.now(IST):%d %b %Y %H:%M} IST by ops/shadow.py. Each filter is scored on the trades it "
         "would have skipped in the control run (v4b for BTC, ethb for ETH), each limit on the same trades repriced "
         "with that order limit, all at the live estimate (real tape, behind the race). Judged from 17 Oct IST: a "
         f"change is adopted only after {MIN_N} eligible trades and 2 cluster SE (skip: the skipped trades lost; "
         "limit: beats ask+10c paired). Nothing here changes a run; adopting means a new pre-registration.", ""]
    rows = {c: control_rows(n) for n, c in CONTROLS.items() if (ROOT / "data" / "trader" / n / "trader.db").exists()}
    L += [x for c, r in rows.items() for x in judge(r, c)]
    L += ["## Context only (every control trade, includes the days the leads were found in: not a test)", ""]
    L += [x for c, r in rows.items() for x in judge(r, c, 0, "all days")]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
