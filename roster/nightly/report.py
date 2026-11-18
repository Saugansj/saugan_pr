"""Role 36 daily report (build-plan 1.19): reports/phase1_daily_<date>.md from the paper trader's ledger.

  python -m nightly.report [--dir data/trader] [--date 2026-10-01]          # one UTC day (default: yesterday)
  python -m nightly.report --dir data/trader/smoke60 --all --out reports/phase1_smoke.md --title "Phase 1 smoke run"
  add --offline to skip the public CLOB GETs for resolutions; --ntfy to push a one-line summary to ntfy.sh/$NTFY_TOPIC

Sections: paper P&L per strategy, intents and kernel decisions (rejections by reason), orders and fills, markouts,
the pre-registered statistics and universe vs traded (nightly/scorer.py), btc-speed events and trades, latency,
trips / reconciles / invariant violations / audit chain, and time to evidence. Read-only on the ledger.
The ntfy alert carries only the summary line (no key, no account); the topic comes from env NTFY_TOPIC.
"""
import argparse
import collections
import datetime as dt
import json
import os
import pathlib
import sqlite3
import statistics
import urllib.request

import common
from nightly import scorer
from trader.audit import AuditChainError, verify
from trader.engines import ladder, speed

DAY_MS = 86_400_000


def _utc(ms) -> str:
    return dt.datetime.fromtimestamp(ms / 1000, dt.UTC).strftime("%Y-%m-%d %H:%M:%S") if ms else "-"


def _f(x, nd=4) -> str:
    return "-" if x is None else f"{x:.{nd}f}"


def _c(x) -> str:
    return "-" if x is None else f"{100 * x:+.2f}c"


def dist(xs: list[float]) -> str:
    if not xs:
        return "n 0"
    xs = sorted(xs)
    p90 = statistics.quantiles(xs, n=10)[8] if len(xs) > 1 else xs[0]
    return f"n {len(xs)}, median {statistics.median(xs):.0f}, p90 {p90:.0f}, min {xs[0]:.0f}, max {xs[-1]:.0f}"


def counts(t: dict) -> collections.Counter:
    c = collections.Counter()
    for r in t.get("decision_counts", []):
        c.update({k: v for k, v in r.items() if k not in ("event_ms", "recorded_ms")})
    return c


def pnl(cum: dict) -> dict:
    """Per strategy, cumulative: cash from fills, merges and redemptions, plus open shares at the last mid."""
    strat, pos = {}, collections.defaultdict(float)
    out = collections.defaultdict(lambda: collections.Counter())
    for f in cum.get("fills", []):
        s = strat.setdefault(f["token_id"], f["strategy"])
        sign = 1 if f["side"] == "BUY" else -1
        pos[f["token_id"]] += sign * f["size"]
        o = out[s]
        o["fills"] += 1
        o["bought" if sign > 0 else "sold"] += f["price"] * f["size"]
        o["fees"] += f["fee"]
    for m in cum.get("merges", []):
        o = out[strat.get(m["yes"], ladder.NAME)]
        o["merged"] += m["size"]
        pos[m["yes"]] -= m["size"]
        pos[m["no"]] -= m["size"]
    for s in cum.get("settlements", []):
        o = out[strat.get(s["token_id"], "?")]
        o["redeemed"] += s["shares"] * s["payout"]
        pos[s["token_id"]] -= s["shares"]
    mark = {}
    for r in cum.get("marks", []):
        mark.update({k: v for k, v in r.items() if k not in ("event_ms", "recorded_ms") and v is not None})
    for tok, sh in pos.items():
        if abs(sh) > 1e-9:
            o = out[strat[tok]]
            o["open_shares"] += sh
            if tok in mark:
                o["open_value"] += sh * mark[tok]
            else:
                o["unmarked"] += 1
    for o in out.values():
        o["pnl"] = o["sold"] - o["bought"] - o["fees"] + o["merged"] + o["redeemed"] + o["open_value"]
    return out


def prereg(d) -> list[tuple[str, str, str]]:
    p = pathlib.Path(d) / "trader.db"
    if not p.exists():
        return []
    con = sqlite3.connect(f"{p.resolve().as_uri()}?mode=ro", uri=True)
    try:
        return [(n, common.sha256_text(b)[:16], _utc(r)) for n, b, r in con.execute("SELECT name, body, recorded_ms FROM prereg")]
    finally:
        con.close()


def build(d, t0: int, t1: int, title: str, fetch=scorer.fetch_outcome, now_ms: int | None = None) -> tuple[str, str]:
    """(markdown, one-line summary)."""
    d = pathlib.Path(d)
    now_ms = common.now_ms() if now_ms is None else now_ms
    t, cum = scorer.tables(d, t0, t1), scorer.tables(d, 0, t1)
    sc = scorer.score(d, t0, t1, fetch, now_ms)
    c = counts(t)
    runs, ends = t.get("runs", []), t.get("runs_end", [])
    viol = t.get("invariant_violations", [])
    fills = t.get("fills", [])
    pn = pnl(cum)
    span = [r["event_ms"] for k in t for r in t[k]]
    L = [f"# {title}", "",
         f"Ledger `{d.relative_to(common.ROOT).as_posix() if d.is_relative_to(common.ROOT) else d}`, window {_utc(t0) if t0 else 'start'} "
         f"to {_utc(t1) if t1 < scorer.ALL else 'now'} UTC (data from {_utc(min(span) if span else None)} to "
         f"{_utc(max(span) if span else None)}). Paper only: no order ever left this PC.", "",
         "## Summary", "",
         f"- Runs started: {len(runs)}; clean shutdowns: {len(ends)}; still running or ended by a crash or kill: "
         f"{len(runs) - len(ends)} (a killed run's journal is replayed and reconciled at the next start).",
         f"- **Invariant violations: {len(viol)}.**",
         f"- Intents {sum(v for k, v in c.items() if k.startswith('intent:'))}, approved "
         f"{sum(v for k, v in c.items() if k.startswith('decision:') and k.endswith(':approved'))}, orders "
         f"{sum(v for k, v in c.items() if k.startswith('order:'))}, paper fills {len(fills)}, btc-speed events "
         f"{len(t.get('speed_events', []))} and trades {len(t.get('speed_trades', []))}.",
         "- Paper P&L to the end of the window: " + (", ".join(f"{s} {o['pnl']:+.2f} USD" for s, o in sorted(pn.items()))
                                                     or "no fills yet") + ".", ""]
    summary = (f"{title}: violations {len(viol)}, fills {len(fills)}, "
               + ", ".join(f"{s} {o['pnl']:+.2f}" for s, o in sorted(pn.items())))

    L += ["## Paper P&L per strategy (cumulative to the end of the window)", "",
          "| Strategy | Fills | Bought USD | Sold USD | Fees | Merged USD | Redeemed USD | Open shares | Open value at mid | P&L USD |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for s, o in sorted(pn.items()):
        L.append(f"| {s} | {o['fills']} | {o['bought']:.2f} | {o['sold']:.2f} | {o['fees']:.4f} | {o['merged']:.2f} | "
                 f"{o['redeemed']:.2f} | {o['open_shares']:g} | {o['open_value']:.2f}"
                 f"{' (+' + str(o['unmarked']) + ' unmarked)' if o['unmarked'] else ''} | {o['pnl']:+.4f} |")
    L += ["", "Open shares are marked at the last per-minute mid_ex_own; held to resolution, they pay 1 or 0.", ""]

    L += ["## Intents and kernel decisions", ""]
    for s in (ladder.NAME, speed.NAME):
        rej = sorted(((k.split(":", 2)[2], v) for k, v in c.items() if k.startswith(f"decision:{s}:")
                      and not k.endswith(":approved")), key=lambda kv: -kv[1])
        L.append(f"- **{s}**: {c[f'intent:{s}']} intents, {c[f'decision:{s}:approved']} approved, "
                 f"{sum(v for _, v in rej)} rejected" + (": " + "; ".join(f"{k} {v}" for k, v in rej) if rej else "") + ".")
        extra = {k: v for k, v in c.items() if k.split(":")[0] in ("pulled", "router", "cancel") and f":{s}" in k}
        if extra:
            L.append("  Also: " + "; ".join(f"{k} {v}" for k, v in sorted(extra.items())) + ".")
    L += ["", "Counts are exact (per-minute counters). A rejection repeated for the same order and reason is written to the "
          "`decisions` table at most once a minute. `pulled` = a resting quote the kernel no longer approves; `router` = "
          "refused by the router's order rules. Reasons without a kernel prefix (\"own order already live ...\", \"no book "
          "for a taker\", \"book snapshot already taken ...\") are the loop's guards against a flattering fill simulator.", ""]
    dec = [r for r in t.get("decisions", []) if not r["approved"]]
    if dec:
        L += ["Latest distinct rejections:", "", "| Time UTC | Strategy | Reason | Binding cap |", "|---|---|---|---|"]
        seen = {}
        for r in dec:
            seen[(r["strategy"], r["class"])] = r
        L += [f"| {_utc(r['event_ms'])} | {r['strategy']} | {r['reason'][:110]} | {r['binding_cap'] or '-'} |"
              for r in seen.values()]
        L.append("")

    L += ["## Orders and fills", "",
          "| Strategy | Kind | Orders | Fills | Shares | Avg price | Fees USD |", "|---|---|---|---|---|---|---|"]
    for s in (ladder.NAME, speed.NAME):
        for kind in ("maker", "taker"):
            fs = [f for f in fills if f["strategy"] == s and f["maker"] == (kind == "maker")]
            sh = sum(f["size"] for f in fs)
            if c[f"order:{s}:{kind}"] or fs:
                L.append(f"| {s} | {kind} | {c[f'order:{s}:{kind}']} | {len(fs)} | {sh:g} | "
                         f"{_f(sum(f['price'] * f['size'] for f in fs) / sh if sh else None)} | "
                         f"{sum(f['fee'] for f in fs):.4f} |")
    L += ["", f"Merges of YES+NO pairs: {len(t.get('merges', []))}; paper redemptions: {len(t.get('settlements', []))}.", ""]

    L += ["## Markouts against mid_ex_own", "", "Per share, signed by side (positive = the mid moved our way).", "",
          "| Strategy | Horizon | n | Mean | SE | No mid |", "|---|---|---|---|---|---|"]
    for s, hs in sc["markouts"].items():
        for h, m in hs.items():
            L.append(f"| {s} | {h} s | {m['n']} | {_c(m['mean'])} | {_c(m['se'])} | {m['missing']} |")
    if not sc["markouts"]:
        L.append("| - | - | 0 | - | - | - |")
    L.append("")

    lad, spd = sc["ladder"], sc["speed"]
    sp = spd.get("prereg", speed.PREREG)
    L += ["## Pre-registered statistics (all data to the end of the window)", "",
          f"- **{ladder.PREREG['test_id']}**: {ladder.PREREG['statistic']}. Clusters {lad['n']} (needs "
          f"{ladder.PREREG['n']}), mean {_f(lad['mean'])} USD, SE {_f(lad['se'])}, fills still without a 5 m markout "
          f"{lad['missing_5m']}. Verdict: **{lad['verdict']}**.",
          f"- **{sp['test_id']}**: {sp['statistic']}. Resolved trades {spd['n']} in {spd['markets']} "
          f"markets (needs {sp['n']}), unresolved {spd['pending']}, mean {_f(spd['mean'])} USD, cluster SE "
          f"{_f(spd['se'])}, total {spd['total']:+.4f} USD. Verdict: **{spd['verdict']}**.",
          *([f"- **Paper-fill realism** (btc-speed at real tape prices): {tp['n']} of {spd['n']} resolved trades "
             f"repriced at what real takers paid in our order's second. Paper {tp['paper']:+.2f} USD -> best case "
             f"{tp['best']:+.2f} (cheapest real price), typical {tp['typical']:+.2f} (median real price), **live estimate "
             f"{tp['live']:+.2f}** (our order behind the real takers that beat us, partial fills; "
             f"{100 * tp['live_shares'] / tp['shares']:.0f}% of our shares filled); real takers paid "
             f"a median {100 * tp['gap_median']:+.1f}c over our fill. Paper assumes we win every race for the cheapest ask. Not comparable with reports before 15 Oct."]
            if (tp := spd.get("tape")) and tp["n"] else []),
          "- Pre-registrations in the ledger (immutable): " + (", ".join(f"`{n}` (sha256 {h}, written {w})"
                                                                     for n, h, w in prereg(d)) or "none") + ".", ""]

    L += ["## Universe vs traded subset (ladder-maker checkpoints at tau 24 h / 6 h / 1 h)", "",
          "| Set | Rows | Markets | Priced | Mean abs(fair - mid) | Mean fair - mid | Resolved | Brier fair | Brier mid |",
          "|---|---|---|---|---|---|---|---|---|"]
    for k, u in sc["universe"].items():
        L.append(f"| {k} | {u['rows']} | {u['markets']} | {u['priced']} | {_f(u['mean_abs_gap'])} | {_f(u['mean_gap'])} | "
                 f"{u['resolved']} | {_f(u['brier_fair'])} | {_f(u['brier_mid'])} |")
    L.append("")

    ev, tr = t.get("speed_events", []), t.get("speed_trades", [])
    why = collections.Counter(v for e in ev for v in e["markets"].values())
    L += ["## btc-speed events and trades", "",
          f"{len(ev)} causal {'/'.join(sp['params']['assets'])} moves (>= {sp['params']['bp']} bp in "
          f"{sp['params']['window_s']} s) and {len(tr)} trades "
          "sent to the kernel. Per mapped market: " + (", ".join(f"{k} {v}" for k, v in why.most_common()) or "none") + ".", ""]
    if ev:
        L += ["| Event UTC | Move bp | Markets |", "|---|---|---|"]
        L += [f"| {_utc(e['decision_ms'])} | {e['move_bp']:+.1f} | {'; '.join(f'{k[:10]}: {v}' for k, v in e['markets'].items()) or '-'} |"
              for e in ev[-30:]]
        L.append("")
    if tr:
        res = {x["order_id"]: x for x in spd["trades"]}
        fl = collections.defaultdict(list)
        for f in fills:
            fl[f["order_id"]].append(f)
        L += ["| Decision UTC | Market | Dur | Ask seen | Kernel | Order | Filled | Avg fill | Fee | P&L held to resolution |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for x in tr[-40:]:
            fs = fl.get(x["order_id"], [])
            sh = sum(f["size"] for f in fs)
            r = res.get(x["order_id"])
            L.append(f"| {_utc(x['decision_ms'])} | {x['cid'][:10]} | {x['duration_min']}m | {x['ask']} | "
                     f"{'approved' if x['approved'] else (x['reason'] or '')[:60]} | {x['status'] or '-'}"
                     f"{' (' + x['router_reason'] + ')' if x.get('router_reason') else ''} | {sh:g} | "
                     f"{_f(sum(f['price'] * f['size'] for f in fs) / sh if sh else None, 3)} | "
                     f"{_f(sum(f['fee'] for f in fs))} | {_f(r['pnl']) if r else 'unresolved'} |")
        L.append("")

    rtt = []
    p = d / "rtt.jsonl"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if t0 <= r.get("t", 0) < t1:
                rtt.append(r["rtt_ms"])
    L += ["## Latency (ms)", "",
          f"- Round trip to clob.polymarket.com (GET /time, median of 3 warm requests, every 60 s): {dist(rtt)}.",
          "", "Every Binance tick and every 100 ms timer, summarised per minute by the loop:", ""]
    lat = t.get("latency", [])
    for k, label in (("tick_ms", "Decision lag: local receive of a Binance tick to both engines decided and orders sent"),
                     ("binance_ms", "Binance event time to local receive (network + clock offset)"),
                     ("loop_ms", "Event-loop lag: a 100 ms timer firing late (time a message can wait unread)")):
        q = [r[k] for r in lat if k in r]
        L.append(f"- {label}: " + (f"n {sum(x['n'] for x in q)}, median of minute medians "
                                   f"{statistics.median(x['p50'] for x in q):.1f}, worst minute p90 "
                                   f"{max(x['p90'] for x in q):.1f}, worst minute p99 {max(x['p99'] for x in q):.1f}, "
                                   f"max {max(x['max'] for x in q):.1f}" if q else "no samples") + ".")
    L += ["", "btc-speed events (one sample per event, traded or not):", "",
          f"- Binance event to local receive: {dist([e['recv_ms'] - e['binance_ms'] for e in ev])}.",
          f"- Local receive to decision: {dist([e['decision_ms'] - e['recv_ms'] for e in ev])}.",
          f"- Decision to simulated arrival (150 ms taker delay + measured round trip): "
          f"{dist([e['arrival_ms'] - e['decision_ms'] for e in ev])}.", ""]

    trips = t.get("trips", [])
    rec = t.get("reconciles", [])
    faults = collections.Counter(r.get("kind") for r in t.get("data_fault", []))
    try:
        n, head = verify(d / "audit.jsonl") if (d / "audit.jsonl").exists() else (0, None)
        chain = f"verifies: {n} records, head {head[:16] if head else '-'}"
    except AuditChainError as e:
        chain = f"**BROKEN**: {e}"
    heads = cum.get("audit_heads", [])
    L += ["## Risk, reconciliation, invariants and audit", "",
          f"- Trips: {len(trips)}" + (": " + "; ".join(f"{r['scope'][:16]} {r['level']} ({r['reason'][:70]}, {r['source']})"
                                                     for r in trips[:15]) if trips else "") + ".",
          f"- Human resets: {len(t.get('resets', []))}; halts confirmed by zero open orders: {len(t.get('halt_confirmed', []))}.",
          f"- Reconciles: {len(rec)} ({', '.join(f'{k} {v}' for k, v in collections.Counter(r['phase'] for r in rec).items())}); "
          f"with mismatches: {sum(bool(r['mismatches']) for r in rec)}; unknown orders cancelled at startup: "
          f"{sum(r.get('unknown_resolved', 0) for r in rec)}; journaled fills backfilled into the ledger: "
          f"{sum(r.get('fills_backfilled', 0) for r in rec)}.",
          f"- **Invariant violations: {len(viol)}**" + (": " + "; ".join(f"{r['kind']}: {r['detail'][:80]}" for r in viol[:20])
                                                          if viol else "") + ".",
          f"- Data faults flagged by ladder-maker (quotes pulled): {sum(faults.values())}"
          + (f" ({', '.join(f'{k} {v}' for k, v in faults.items())})" if faults else "") +
          f"; log-only arb opportunities: {len(t.get('arb_opportunity', []))}.",
          f"- Audit chain {chain}; last head anchored in the ledger: "
          + (f"{heads[-1]['records']} records, {str(heads[-1]['head'])[:16]} ({heads[-1]['phase']}, {_utc(heads[-1]['event_ms'])})"
             if heads else "none") + ".", ""]

    first = min((r["event_ms"] for r in cum.get("runs", [])), default=None)
    days = max((min(t1, now_ms) - first) / DAY_MS, 1 / 24) if first else None
    L += ["## Time to evidence", "", "| Test | Have | Needs (pass / futility) | Rate per day so far | Days to the pass n |",
          "|---|---|---|---|---|"]
    for pre, have in ((ladder.PREREG, lad["n"]), (sp, spd["n"])):
        rate, left = (have / days if days else 0.0), max(pre["n"] - have, 0)
        eta = left / rate if rate > 0 else None
        if pre is ladder.PREREG and eta is not None:
            eta = max(eta, left)  # one cluster per settlement instant: a new daily 16:00Z settle appears once a day
        L.append(f"| {pre['test_id']} | {have} | {pre['n']} / {pre['futility_n']} | {rate:.2f} | "
                 f"{'no evidence yet' if eta is None else f'{eta:.0f}'} |")
    L += ["", f"Elapsed since the first run: {days:.2f} days. ladder-maker's clusters are settlement instants (one per "
          "daily 16:00Z settle), so its pass n takes at least that many days of trading whatever the fill rate."
          if days else "", ""]
    return "\n".join(L), summary


def ntfy(text: str, topic: str) -> None:
    """Push one line to ntfy.sh/<topic>. Nothing secret is sent: the topic is a name, the text a summary."""
    urllib.request.urlopen(urllib.request.Request(f"https://ntfy.sh/{topic}", data=text.encode()), timeout=10)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", type=pathlib.Path, default=common.DATA / "trader")
    ap.add_argument("--date", help="UTC day YYYY-MM-DD (default: yesterday)")
    ap.add_argument("--all", action="store_true", help="the whole ledger instead of one day")
    ap.add_argument("--out", type=pathlib.Path)
    ap.add_argument("--title")
    ap.add_argument("--offline", action="store_true", help="no CLOB GETs for resolutions")
    ap.add_argument("--ntfy", action="store_true", help="push the summary to ntfy.sh/$NTFY_TOPIC if set")
    ap.add_argument("--step", action="append", default=[], help="a command that made the data (How to reproduce)")
    ap.add_argument("--note", action="append", default=[], help="a line for a Notes section")
    a = ap.parse_args(argv)
    from trader.loop import prefer_ipv4
    prefer_ipv4()
    if a.all:
        t0, t1, tag = 0, scorer.ALL, "all"
    else:
        day = dt.date.fromisoformat(a.date) if a.date else dt.datetime.now(dt.UTC).date() - dt.timedelta(days=1)
        t0 = int(dt.datetime(day.year, day.month, day.day, tzinfo=dt.UTC).timestamp() * 1000)
        t1, tag = t0 + DAY_MS, day.isoformat()
    title = a.title or f"Phase 1 daily paper report {tag}"
    out = a.out or common.REPORTS / f"phase1_daily_{tag}.md"
    md, summary = build(a.dir.resolve(), t0, t1, title, None if a.offline else scorer.fetch_outcome)
    if a.note:
        md += "\n## Notes\n\n" + "".join(f"- {n}\n" for n in a.note)
    md += ("\n## How to reproduce\n\n```\ncd roster\n" + "".join(s + "\n" for s in a.step)
           + ".venv\\Scripts\\python.exe -m nightly.report --dir "
           f"{a.dir.as_posix()} " + ("--all" if a.all else f"--date {tag}") + (f" --out {out.as_posix()}" if a.out else "")
           + (f' --title "{a.title}"' if a.title else "") + "\n```\n")
    out.write_text(md, encoding="utf-8")
    print(f"wrote {out}\n{summary}")
    if a.ntfy and os.environ.get("NTFY_TOPIC"):
        ntfy(summary, os.environ["NTFY_TOPIC"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
