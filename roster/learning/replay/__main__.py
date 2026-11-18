"""Replay-lab smoke on the recorded window, with the real trader.engines classes, unmodified.

    python -m learning.replay --engine ladder      # crypto-term books; about 3 minutes (the ladder's own arb scan)
    python -m learning.replay --engine speed       # crypto-fast books
    python -m learning.replay --engine ladder speed --no-fetch

Each run appends one row to learning/replay/out/trials.jsonl (a failed run included), writes
learning/replay/out/smoke_<engine>.json and renders reports/phase5_replay_smoke.md from every smoke_*.json there.
A LookAheadError fails the run before any summary or report is written. The reference feed is Binance 1s klines for
the window, fetched in memory by a public GET through common.get_json (the 1m history ends 2026-09-29); with
--no-fetch or when the GET fails, the history is used and the report says so.
"""
import argparse
import datetime as dt
import json
import math
import pathlib
from collections import Counter

import numpy as np

import common
from learning.replay.events import ASSETS, H_MS, Store, load_dvol, load_finals, load_markets, load_pm, load_ref
from learning.replay.run import LABEL, replay
from learning.replay.validate import TrialLog, deflated_sharpe, pbo, random_entry
from trader.engines.ladder import LadderEngine
from trader.engines.speed import SpeedEngine
from trader.marketdata import BINANCE_KLINES, SYMBOL, Books

ENGINES = {"ladder": (LadderEngine, "crypto-term", "trader/engines/ladder.py"),
           "speed": (SpeedEngine, "crypto-fast", "trader/engines/speed.py")}
OUT = pathlib.Path(__file__).resolve().parent / "out"
REPORT = common.REPORTS / "phase5_replay_smoke.md"
WARM_MS = 120_000


def fetch_ref(lo: int, hi: int, get=common.get_json) -> list[dict]:
    """Binance 1s closes for [lo, hi], recorded at each candle's close."""
    out = []
    for a in ASSETS:
        t = lo
        while t <= hi:
            k = get(BINANCE_KLINES, {"symbol": SYMBOL[a], "interval": "1s", "startTime": t, "endTime": hi, "limit": 1000})
            if not k:
                break
            out += [{"asset": a, "ts_ms": int(r[6]), "price": float(r[4]), "recorded_ms": int(r[6])} for r in k
                    if int(r[6]) <= hi]
            t = int(k[-1][0]) + 1000
    return out


def b1_check(store: Store, pm: list, t: int) -> dict:
    """The store's books at t equal trader.marketdata.Books fed the same raw messages directly up to t."""
    direct = Books()
    for rt, raw, _ in pm:
        if rt <= t:
            direct.apply(raw, rt)
    got = store.as_of(t).books.books
    same = got.keys() == direct.books.keys() and all(
        (b.bids, b.asks, b.ts_ms) == (direct.books[k].bids, direct.books[k].asks, direct.books[k].ts_ms)
        for k, b in got.items())
    return {"t": t, "tokens": len(got), "equal": same}


def max_move_bp(ref: list, asset: str, lo: int, hi: int, window_s: int = 5) -> float | None:
    """Largest |log move| in bp over window_s seconds between ref closes in [lo, hi] (why btc-speed did not fire)."""
    px = {r["ts_ms"] // 1000: r["price"] for r in ref if r["asset"] == asset and lo <= r["ts_ms"] <= hi}
    moves = [abs(math.log(p / px[s - window_s])) * 1e4 for s, p in px.items() if s - window_s in px]
    return max(moves) if moves else None


def _num(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else x


def run_engine(name: str, hour: str, rtt: float, R: int, seed: int, fetch: bool, out_dir: pathlib.Path,
               trials: pathlib.Path) -> dict:
    cls, stream, src = ENGINES[name]
    h0 = int(dt.datetime.strptime(hour, "%Y-%m-%dT%H").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
    pm = load_pm((stream,), h0, h0 + H_MS - 1)
    if not pm:
        raise SystemExit(f"no {stream} recording for {hour}")
    start, end = min(r[0] for r in pm), max(r[0] for r in pm)
    lo, ref, note = start - WARM_MS, None, ""
    if fetch:
        try:
            ref = fetch_ref(lo, end)
            note = "Binance 1s klines for the window, fetched in memory by a public GET (common.get_json)"
        except Exception as e:  # noqa: BLE001 - offline or blocked: fall back to the history and say so
            note = f"the public GET failed ({type(e).__name__}); "
    if not ref:
        ref = load_ref(lo, end)
        note += "Binance 1m closes from data/history/binance (they end 2026-09-29: no reference tick in the window)"
    store = Store(pm=pm, markets=load_markets((stream,), start, end), ref=ref, dvol=load_dvol(lo, end),
                  finals=load_finals(lo, end))
    engine = cls()
    family = f"replay:{engine.name}"
    params = {"engine": engine.p, "rtt_ms": rtt, "fill_mode": "strict"}
    dataset = {"stream": stream, "start_ms": start, "end_ms": end, "pm_rows": len(pm), "ref": note,
               "ref_rows": len(ref)}
    log = TrialLog(trials)
    try:
        res = replay(engine, store, start, end, rtt, modes={stream})
    except Exception:
        log.append(family, params, dataset, status="failed")  # failed runs count toward the DSR's N
        raise
    stat = res["stat"]
    log.append(family, params, dataset, statistic=_num(stat["mean"]), sharpe=stat["sharpe"], clusters=stat["clusters"])
    rnd = random_entry(store, res, R, seed)
    fills = res["fills"]
    dec = Counter(d.reason if not d.approved else "approved: " + d.reason for _, _, d in res["decisions"])
    summary = {
        "engine": name, "class": f"{cls.__module__}.{cls.__name__}", "source": src,
        "source_sha256": common.sha256_text((common.ROOT / src).read_text(encoding="utf-8")),
        "window": [start, end], "rtt_ms": rtt, "ref_note": note, "label": LABEL,
        "events": {k: v for k, v in sorted(res["counts"].items())},
        "ticks": res["ticks"], "tripwire_checks": res["checks"], "tripwire_violations": res["violations"],
        "intents": dict(Counter(i.kind for _, i in res["intents"])), "decisions": dict(dec),
        "orders": len(res["orders"]), "rejected": dict(Counter(res["reasons"].values())), "cancels": len(res["cancels"]),
        "fills": {"maker": sum(f.maker for f in fills), "taker": sum(not f.maker for f in fills),
                  "maker_shares": round(sum(f.size for f in fills if f.maker), 2),
                  "taker_shares": round(sum(f.size for f in fills if not f.maker), 2)},
        "fees": round(sum(f.fee for f in fills), 6), "positions": len(res["positions"]),
        "stat": {k: _num(v) for k, v in stat.items()},
        "clusters": [{**c, "pnl": round(c["pnl"], 6), "fees": round(c["fees"], 6)} for c in res["clusters"]],
        "random_entry": {"R": R, "seed": seed, "percentile": rnd["percentile"],
                         "baseline_mean": _num(float(np.mean(rnd["baseline"]))) if rnd["baseline"] else None,
                         "baseline_fees": round(rnd["fees"], 6), "entries": len(res["entries"])},
        "trials": log.count(family), "trial_family": family,
        "b1": b1_check(store, pm, (start + end) // 2),
        "detector_events": len(getattr(engine, "events", [])),
        "max_5s_move_bp": {a: _num(max_move_bp(ref, a, start, end)) for a in ASSETS},
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"smoke_{name}.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    return summary


def synthetic(seed: int = 7, T: int = 500, N: int = 20) -> dict:
    """DSR and PBO on a seeded synthetic trial set: N iid N(0,1) trials, trial 0 with a 0.2 SD edge per period."""
    rng = np.random.default_rng(seed)
    X = rng.normal(0, 1, (T, N))
    X[:, 0] += 0.2
    sr = list(X.mean(0) / X.std(0, ddof=1))
    best_noise = int(np.argmax(sr[1:])) + 1
    return {"seed": seed, "T": T, "N": N, "pbo_with_edge": pbo(X)["pbo"], "pbo_noise_only": pbo(X[:, 1:])["pbo"],
            "dsr_edge": deflated_sharpe(X[:, 0], sr), "dsr_best_noise": deflated_sharpe(X[:, best_noise], sr[1:]),
            "psr_best_noise": deflated_sharpe(X[:, best_noise], [sr[best_noise]])}


def _utc(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _why_zero(s: dict) -> str:
    if s["engine"] == "speed":
        return (f"btc-speed fires on a >= 10 bp move within 5 s; the largest 5 s move in the window was "
                f"{s['max_5s_move_bp']['BTC'] if s['max_5s_move_bp']['BTC'] is not None else 'n/a (no reference ticks)'}"
                f" bp for BTC, and its detector fired {s['detector_events']} time(s).")
    return "the ladder pulled or skipped every market on every tick (see its pull rules: close, stale book or feed, " \
           "tau > 24h, book wider than 0.10)."


def render(out_dir: pathlib.Path, report: pathlib.Path) -> str:
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(out_dir.glob("smoke_*.json"))]
    L = ["# Phase 5 replay-lab smoke (WP5-B, role 35)", "",
         f"Every number here is **{LABEL}**: about two minutes of recorded books, unresolved positions marked at the "
         "last mid excluding our orders, no kernel. Nothing was sent anywhere; fills come from "
         "`learning/replay/fills.py` in strict (paper) mode.", ""]
    for s in runs:
        st, f, rnd = s["stat"], s["fills"], s["random_entry"]
        L += [f"## Engine `{s['engine']}` ({s['class']}, unmodified)", "",
              f"- Window: {_utc(s['window'][0])} to {_utc(s['window'][1])}; round trip {s['rtt_ms']} ms.",
              f"- Engine source `{s['source']}` sha256 `{s['source_sha256'][:16]}...` (imported, not copied).",
              f"- Reference feed: {s['ref_note']}. DVOL from data/history/deribit (1h, recorded at candle close).",
              f"- Look-ahead tripwire: {s['ticks']} engine calls, {s['tripwire_checks']} input checks, "
              f"**{s['tripwire_violations']} violations**.",
              f"- B1 on the real file: the store's books at {_utc(s['b1']['t'])} ({s['b1']['tokens']} tokens) "
              f"{'equal' if s['b1']['equal'] else 'DIFFER FROM'} `trader.marketdata.Books` fed the same messages.", "",
              "| events read | count |", "|---|---|"]
        L += [f"| {k} | {v} |" for k, v in s["events"].items()]
        n_int = sum(s["intents"].values())
        L += ["", "| result | value |", "|---|---|",
              f"| intents | {n_int} ({', '.join(f'{k} {v}' for k, v in s['intents'].items()) or 'none'}) |",
              f"| kernel decisions | {'; '.join(f'{k}: {v}' for k, v in s['decisions'].items()) or 'none'} |",
              f"| orders accepted by the fill model | {s['orders'] - sum(s['rejected'].values())} of {s['orders']} |",
              f"| refused by the fill model | {'; '.join(f'{k}: {v}' for k, v in s['rejected'].items()) or 'none'} |",
              f"| maker cancels (target diff) | {s['cancels']} |",
              f"| fills maker / taker | {f['maker']} ({f['maker_shares']} sh) / {f['taker']} ({f['taker_shares']} sh) |",
              f"| fees paid (USD) | {s['fees']} |",
              f"| open positions at the end | {s['positions']} |",
              f"| fee-net P&L per cluster ({LABEL}) | mean {st['mean']} USD, SE {st['se']}, clusters {st['clusters']}, "
              f"unresolved {st.get('unresolved', 0)} |",
              f"| random-entry baseline | " + (f"strategy at the {rnd['percentile']:.1f}th percentile of R = {rnd['R']} "
                                              f"runs (seed {rnd['seed']}, baseline mean {rnd['baseline_mean']}, "
                                              f"baseline fees {rnd['baseline_fees']} USD)"
                                              if rnd["percentile"] is not None else
                                              "no strategy entries filled, so there is nothing to permute") + " |",
              f"| trials logged in family `{s['trial_family']}` | {s['trials']} |", ""]
        if n_int == 0:
            L += [f"Zero intents: {_why_zero(s)}", ""]
        elif f["maker"] + f["taker"] == 0:
            L += [f"Zero fills: {s['events'].get('trade', 0)} trades were recorded in the window and none traded "
                  "through a resting maker's price or cleared its queue ahead before the target diff cancelled it "
                  f"({s['cancels']} cancels).", ""]
        if s["clusters"]:
            L += ["| cluster | P&L (USD) | fees | unresolved |", "|---|---|---|---|"]
            L += [f"| {c['cluster_id']} | {c['pnl']} | {c['fees']} | {c['unresolved']} |" for c in s["clusters"]]
            L += [""]
    sy = synthetic()
    L += ["## DSR and PBO on a seeded synthetic trial set", "",
          f"{sy['N']} trials x {sy['T']} periods of iid N(0, 1), trial 0 with a +0.2 SD edge per period (seed {sy['seed']}).",
          "", "| check | value |", "|---|---|",
          f"| PBO (S = 16), edge trial included | {sy['pbo_with_edge']:.3f} |",
          f"| PBO (S = 16), noise trials only | {sy['pbo_noise_only']:.3f} |",
          f"| edge trial: SR, SR0, DSR (N = {sy['N']}) | {sy['dsr_edge']['sr']:.4f}, {sy['dsr_edge']['sr0']:.4f}, "
          f"{sy['dsr_edge']['dsr']:.4f} |",
          f"| best noise trial: SR, SR0, DSR (N = {sy['N'] - 1}) | {sy['dsr_best_noise']['sr']:.4f}, "
          f"{sy['dsr_best_noise']['sr0']:.4f}, {sy['dsr_best_noise']['dsr']:.4f} |",
          f"| best noise trial undeflated: PSR(0) | {sy['psr_best_noise']['dsr']:.4f} |", "",
          "## How to reproduce", "", "From `roster/`:", "", "```",
          ".venv\\Scripts\\python.exe -m learning.replay --engine ladder",
          ".venv\\Scripts\\python.exe -m learning.replay --engine speed",
          ".venv\\Scripts\\python.exe -m pytest tests/phase5/test_replay.py -q", "```", "",
          "Data read (read-only): `data/recordings/parquet/stream=crypto-term|crypto-fast/date=2026-09-30/14.parquet`, "
          "`data/markets/2026-09-30T142859Z.jsonl`, `data/history/deribit/dvol_*_1h.parquet`, "
          "`data/history/binance/*` (finals). Written: `learning/replay/out/` and this report.", ""]
    text = "\n".join(L)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(text, encoding="utf-8")
    return text


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--engine", nargs="+", choices=sorted(ENGINES), default=["ladder", "speed"])
    ap.add_argument("--hour", default="2026-09-30T14", help="recorded UTC hour, YYYY-MM-DDTHH")
    ap.add_argument("--rtt", type=float, default=210.0, help="round trip ms (Phase 1 measured about 200-215)")
    ap.add_argument("--R", type=int, default=100, help="random-entry baseline runs")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-fetch", action="store_true", help="no public GET; reference from data/history only")
    ap.add_argument("--out", type=pathlib.Path, default=OUT)
    ap.add_argument("--report", type=pathlib.Path, default=REPORT)
    a = ap.parse_args(argv)
    for name in a.engine:
        s = run_engine(name, a.hour, a.rtt, a.R, a.seed, not a.no_fetch, a.out, a.out / "trials.jsonl")
        print(f"{name}: {s['ticks']} ticks, {sum(s['intents'].values())} intents, fills {s['fills']}, "
              f"{s['tripwire_violations']} tripwire violations, stat {s['stat']['mean']}")
    render(a.out, a.report)
    print(f"wrote {a.report}")


if __name__ == "__main__":
    main()
