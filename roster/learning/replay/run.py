"""Replay runner (role 35): drives an unmodified trader.contracts.Engine over the event store. Exploratory only.

Ticks: engine.on_tick(now_ms, markets, books, ref, positions) on every reference update and on every recorded message
that updates the book of a market the engine trades (`modes`; None = every market), as the live loop does. Before each
call the look-ahead tripwire checks that every input was recorded by now; one violation raises LookAheadError and the
run fails. Maker targets are diffed against resting makers by (token, side, price, size): cancel what is no longer
targeted, submit what is new; taker intents are submitted at once; every intent goes through kernel.check(intent, ctx)
when a kernel is given; engine.on_fill(fill) is called if the engine has it. Fills come from learning.replay.fills.
"""
import math
from collections import Counter, defaultdict

from learning.replay.events import MIN_MS, State
from learning.replay.fills import FillModel, round_price, round_size
from research.kappa.kappa import clustered_mean
from trader.contracts import Decision, KernelContext

LABEL = "exploratory"


class LookAheadError(RuntimeError):
    """An engine input was recorded after the decision time."""


def tripwire(t: int, st: State) -> int:
    """Raise LookAheadError if any input at decision time t was recorded after t: a Book.ts_ms, a reference ts_ms or
    recorded time, the MarketInfo snapshot time, or a final value (its recorded time and its candle's close).
    Returns the number of inputs checked."""
    late, n = [], 0
    for b in st.books.books.values():
        n += 1
        if b.ts_ms > t:
            late.append(f"book {b.token_id[:12]} ts_ms {b.ts_ms}")
    if st.snapshot_ms is not None:
        n += 1
        if st.snapshot_ms > t:
            late.append(f"market snapshot {st.snapshot_ms}")
    for asset, r in st.ref.items():
        for k in ("ts_ms", "recv_ms", "dvol_ts_ms"):
            n += 1
            if (r.get(k) or 0) > t:
                late.append(f"ref {asset} {k} {r[k]}")
        for open_ms in r.get("final", {}):
            n += 1
            rec = st.rec.get(("final", asset, open_ms), math.inf)  # a final with no recorded time is never trusted
            if max(rec, open_ms + MIN_MS) > t:
                late.append(f"final {asset}@{open_ms} recorded {rec}")
    for k, rec in st.rec.items():
        n += 1
        if rec > t:
            late.append(f"{k} recorded {rec}")
    if late:
        raise LookAheadError(f"decision at {t}: {len(late)} input(s) recorded later: " + "; ".join(late[:5]))
    return n


def pnl_by_cluster(fills, markets: dict, books: dict, outcomes: dict) -> list[dict]:
    """Fee-net P&L per cluster (MarketInfo.event_group). A position pays its outcome where known; otherwise it is marked
    at its token's last mid_ex_own (at cost if there is none) and the cluster is flagged unresolved."""
    pos = defaultdict(lambda: [0.0, 0.0, 0.0])  # (cid, token) -> [shares, cash, fees]
    for f in fills:
        s = 1 if f.side == "BUY" else -1
        p = pos[(f.cid, f.token_id)]
        p[0] += s * f.size
        p[1] -= s * f.price * f.size + f.fee
        p[2] += f.fee
    rows = {}
    for (cid, tok), (sh, cash, fees) in pos.items():
        m = markets[cid]
        if outcomes and cid in outcomes:
            pay, resolved = (outcomes[cid] if tok == m.token_yes else 1 - outcomes[cid]), True
        else:
            b = books.get(tok)
            pay, resolved = (b.mid_ex_own() if b else None), False
            if pay is None:
                pay = -(cash + fees) / sh if abs(sh) > 1e-9 else 0.0
        r = rows.setdefault(m.event_group, {"cluster_id": m.event_group, "pnl": 0.0, "fees": 0.0, "unresolved": False})
        r["pnl"] += sh * pay + cash
        r["fees"] += fees
        r["unresolved"] |= not resolved
    return list(rows.values())


def cluster_stat(rows: list[dict]) -> dict:
    """Mean fee-net P&L per cluster with its clustered_mean SE (NaN under 2 clusters)."""
    if not rows:
        return {"clusters": 0, "mean": math.nan, "se": math.nan, "sharpe": None}
    v = [r["pnl"] for r in rows]
    mean, se = clustered_mean(v, [r["cluster_id"] for r in rows]) if len(v) > 1 else (v[0], math.nan)
    sd = (sum((x - mean) ** 2 for x in v) / (len(v) - 1)) ** 0.5 if len(v) > 1 else 0.0
    return {"clusters": len(v), "mean": mean, "se": se, "sharpe": mean / sd if sd > 0 else None,
            "unresolved": sum(r["unresolved"] for r in rows), "label": LABEL}


def feed_ages(st: State, t: int) -> dict:
    ages = {k: t - v for k, v in st.rec.items() if isinstance(k, str)}
    pm = [v for k, v in ages.items() if k.startswith("polymarket:")]
    if pm:
        ages["polymarket"] = max(pm)
    return ages


def replay(engine, store, start_ms: int, end_ms: int, rtt_ms: float, kernel=None, outcomes=None, modes=None,
           fill_mode: str = "strict", cancel_ahead: float = 0.0, bankroll_usd: float = 1000.0) -> dict:
    """Run `engine` over the events recorded in [start_ms, end_ms] (earlier ones only build state). Returns intents,
    decisions, orders, cancels, fills, positions, per-cluster P&L and its statistic, all labelled exploratory."""
    st = State()
    fm = FillModel(st.markets, rtt_ms, fill_mode, cancel_ahead)
    if hasattr(engine, "rtt_ms"):
        engine.rtt_ms = rtt_ms  # the live loop sets the measured round trip the same way
    on_fill = getattr(engine, "on_fill", None)
    res = {"label": LABEL, "engine": engine.name, "start_ms": start_ms, "end_ms": end_ms, "rtt_ms": rtt_ms,
           "fill_mode": fill_mode, "cancel_ahead": cancel_ahead, "intents": [], "decisions": [], "orders": [],
           "cancels": [], "fills": [], "ticks": 0, "checks": 0, "violations": 0, "counts": Counter()}
    positions: dict[str, float] = {}
    traded_markets = {}

    def fills(fs):
        for f in fs:
            res["fills"].append(f)
            positions[f.token_id] = round(positions.get(f.token_id, 0.0) + (f.size if f.side == "BUY" else -f.size), 6)
            if on_fill:
                on_fill(f)

    def submit(i, t):
        res["intents"].append((t, i))
        if kernel is None:
            d = Decision(True, "no kernel given")
        else:
            d = kernel.check(i, KernelContext(t, st.markets, st.books.books, dict(positions), fm.open_orders(), {},
                                              bankroll_usd, feed_ages(st, t)))
        res["decisions"].append((t, i, d))
        if d.approved:
            res["orders"].append(fm.submit(i, t))
            if i.cid in st.markets:
                traded_markets[i.cid] = st.markets[i.cid]

    def key(i):
        m = st.markets.get(i.cid)
        px = round_price(i.price, m.tick_size, i.side) if m else i.price
        return i.token_id, i.side, round(px, 6), round(round_size(i.size), 6)

    for e in store.until(end_ms):
        t = e[0]
        fills(fm.poll(t))
        res["counts"][f"msg:{e[1]}"] += 1
        tick = False
        for c in store.apply(st, e):
            res["counts"][c[0]] += 1
            if c[0] == "book":
                fills(fm.on_book(st.books.books[c[1]], t))
                m = st.markets.get(st.cid_of.get(c[1]))
                tick |= m is not None and (modes is None or m.mode in modes)
            elif c[0] == "trade":
                fills(fm.on_trade(c[1], c[2], c[3], c[4], t))  # local receive time, as the live loop does
            elif c[0] == "ref":
                tick = True
        if not tick or t < start_ms:
            continue
        res["checks"] += tripwire(t, st)
        res["ticks"] += 1
        intents = engine.on_tick(t, st.markets, st.books.books, st.ref, dict(positions))
        want = {key(i): i for i in intents if i.kind == "maker"}
        for o in fm.open_orders():
            if o.intent.kind == "maker":
                if want.pop(key(o.intent), None) is None:  # still targeted: it keeps its queue place
                    fm.cancel(o.order_id, t)
                    res["cancels"].append((t, o.order_id))
        for i in list(want.values()) + [i for i in intents if i.kind == "taker"]:
            submit(i, t)
    fills(fm.poll(end_ms))
    res["positions"] = {k: v for k, v in positions.items() if abs(v) > 1e-9}
    res["markets"] = traded_markets
    res["books"] = st.books.books
    res["outcomes"] = dict(outcomes or {})
    res["reasons"] = dict(fm.reasons)
    res["clusters"] = pnl_by_cluster(res["fills"], traded_markets, st.books.books, res["outcomes"])
    res["stat"] = cluster_stat(res["clusters"])
    filled = [o for o in res["orders"] if o.filled > 0]
    res["entries"] = [{"cluster_id": traded_markets[o.intent.cid].event_group, "cid": o.intent.cid, "size": o.filled}
                      for o in filled]
    return res
