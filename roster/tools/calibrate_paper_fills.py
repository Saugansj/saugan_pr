"""Calibrate the paper_realism fill model (trader/realism.py) from LIVE order data. Read-only.

    .venv\\Scripts\\python.exe -m tools.calibrate_paper_fills [--live data\\trader\\live_archive data\\trader\\live]
                                                          [--paper data\\trader\\paper_v4b] [--out data\\trader\\paper_realism.json]

Reads every <session>/order_timing.jsonl ("post" rows: decision_ms .. post_end_ms) and <session>/journal.jsonl
(new / fill / cancel / done) under the live folders, and prints / writes:
  - latency_ms: quantiles of decision -> venue response (post_end_ms - decision_ms), the arrival delay the paper model
    samples from (live orders are matched somewhere inside that window; using the response time is conservative)
  - outcome counts of marketable BUYs: filled / partial / fak_no_match / rejected (invalid amounts, min size, other)
  - fill rate among orders the venue accepted (rejects excluded: the paper model refuses those itself)
  - FAK rate by latency bucket, and the price paid over the ask seen at decision (fill VWAP - intent.fair)
With --paper: the same fill rate / price premium for that paper run, and the suggested extra_kill_p: the share of
accepted orders the live venue killed beyond what the paper simulator already misses,
  extra_kill_p = 1 - live_fill_rate / paper_fill_rate  (clipped to [0, 0.9]).
Re-run it after each live batch. --realism-out writes the settings a paper_realism run loads (latency_knots,
target_fill_rate, prior_fill_rate): save it as data\\trader\\paper_v9fix\\realism.json and ops\\start_paper_v9fix.bat
passes it with --realism at the next (re)start (or copy the numbers into trader/realism.py DEFAULTS).
"""
import argparse
import json
import pathlib
import statistics

EPS = 1e-9


def _lines(p: pathlib.Path):
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            yield json.loads(line)
        except ValueError:
            continue


def sessions(paths) -> list[pathlib.Path]:
    out = []
    for p in map(pathlib.Path, paths):
        if (p / "journal.jsonl").exists():
            out.append(p)
        elif p.is_dir():
            out += sorted(d for d in p.iterdir() if (d / "journal.jsonl").exists())
    return out


def orders(d: pathlib.Path, strategy="btc-speed") -> dict:
    """order id -> {fair, limit, size, filled, cost, reason} for marketable (taker) BUYs of `strategy`."""
    o = {}
    for e in _lines(d / "journal.jsonl"):
        op, oid = e.get("op"), str(e.get("id") or "").lower()
        if op == "new":
            i = e.get("intent") or {}
            if i.get("kind") == "taker" and i.get("side") == "BUY" and i.get("strategy") == strategy:
                o[oid] = {"fair": i.get("fair"), "limit": i.get("price"), "size": i.get("size"), "filled": 0.0,
                          "cost": 0.0, "reason": None, "ts": e.get("ts"), "arrival_ms": e.get("arrival_ms")}
        elif oid in o and op == "fill":
            f = e["fill"]
            o[oid]["filled"] += f["size"]
            o[oid]["cost"] += f["size"] * f["price"]
        elif oid in o and op == "cancel" and e.get("reason"):
            o[oid]["reason"] = e["reason"]
    return o


def status(r: dict) -> str:
    if r["filled"] > EPS:
        return "filled" if r["filled"] >= r["size"] - 0.01 else "partial"
    why = (r["reason"] or "").lower()
    if "invalid amount" in why or "min size" in why or "minimum" in why:
        return "rejected"
    return "fak_no_match" if ("fak" in why or "no orders found" in why or not why) else "rejected"


def q(v: list[float]) -> dict:
    if not v:
        return {"n": 0}
    s = sorted(v)
    pick = lambda p: s[min(len(s) - 1, int(round(p * (len(s) - 1))))]
    return {"n": len(s), "p10": pick(0.10), "p25": pick(0.25), "p50": pick(0.50), "p75": pick(0.75),
            "p90": pick(0.90), "p99": pick(0.99), "max": s[-1]}


def summarize(rows: list[dict]) -> dict:
    st = {}
    for r in rows:
        st[status(r)] = st.get(status(r), 0) + 1
    acc = [r for r in rows if status(r) != "rejected"]
    filled = [r for r in acc if r["filled"] > EPS]
    prem = [r["cost"] / r["filled"] - r["fair"] for r in filled if r.get("fair") is not None]
    return {"orders": len(rows), "status": st, "accepted": len(acc),
            "fill_rate_accepted": round(len(filled) / len(acc), 4) if acc else None,
            "premium_over_ask_seen": {"mean": round(statistics.fmean(prem), 4) if prem else None, **q(prem)}}


def live_rows(paths) -> list[dict]:
    rows = []
    for d in sessions(paths):
        o = orders(d)
        for e in _lines(d / "order_timing.jsonl"):
            if e.get("kind") != "post" or "post_end_ms" not in e:
                continue
            for x in e.get("orders") or []:
                r = o.get(str(x.get("id") or "").lower())
                if r is not None:
                    r["latency_ms"] = e["post_end_ms"] - e["decision_ms"]
                    r["batch"] = len(e["orders"])
                    rows.append(r)
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--live", nargs="+", default=["data/trader/live_archive", "data/trader/live"])
    ap.add_argument("--paper", default=None, help="a paper run folder to compare with (e.g. data/trader/paper_v4b)")
    ap.add_argument("--out", type=pathlib.Path, default=None, help="the full report as JSON")
    ap.add_argument("--realism-out", type=pathlib.Path, default=None,
                    help="settings file for trader.loop --realism (paper_realism)")
    a = ap.parse_args(argv)
    rows = live_rows(a.live)
    lat = [r["latency_ms"] for r in rows]
    res = {"source": a.live, "latency_ms": q(lat), "live": summarize(rows)}
    buckets = [(0, 1000), (1000, 1500), (1500, 2000), (2000, 3000), (3000, 1e9)]
    res["by_latency"] = {}
    for lo, hi in buckets:
        b = [r for r in rows if lo <= r["latency_ms"] < hi]
        res["by_latency"][f"{lo}-{hi if hi < 1e9 else 'inf'}"] = summarize(b)
    if a.paper:
        prow = [r for d in sessions([a.paper]) for r in orders(d).values()]
        res["paper"] = summarize(prow)
        lf, pf = res["live"]["fill_rate_accepted"], res["paper"]["fill_rate_accepted"]
        if lf is not None and pf:
            res["suggested_extra_kill_p"] = round(min(0.9, max(0.0, 1 - lf / pf)), 4)
    # the inverse CDF the paper model samples: (cumulative probability, ms) knots
    if lat:
        s = sorted(lat)
        res["latency_knots"] = [[p, s[min(len(s) - 1, int(round(p * (len(s) - 1))))]]
                                for p in (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 1.0)]
    txt = json.dumps(res, indent=1, default=str)
    print(txt)
    if a.out:
        a.out.write_text(txt, encoding="utf-8")
    if a.realism_out and lat:
        rz = {"comment": f"tools/calibrate_paper_fills.py: {len(rows)} live orders from {a.live}",
              "latency_knots": res["latency_knots"]}
        if res["live"]["fill_rate_accepted"] is not None:
            rz["target_fill_rate"] = res["live"]["fill_rate_accepted"]
        if a.paper and res["paper"]["fill_rate_accepted"]:
            rz["prior_fill_rate"] = res["paper"]["fill_rate_accepted"]
        a.realism_out.write_text(json.dumps(rz, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
