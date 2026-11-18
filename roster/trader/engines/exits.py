"""Exit manager (role 20/23 extension; build/exits/dispatch.md WX-A), flag `exits`, OFF by default. Pure decisions, no I/O.

Per held ladder token, each ladder round: hold value per share = the engine's fair f for that token (YES f, NO 1 - f);
sell value = bid - taker fee(bid). Rules, first that fires wins (R1, R3, R2, R4):
  R1 fair-value exit (on):       bid - fee(bid) > f + max(fv_margin, k_unc x unc)
  R2 take-profit (tp_pct):       (bid - cost) / cost >= tp_pct and tau_h >= tp_min_tau_h
  R3 model stop (sl_drop):       f < cost - sl_drop and bid - fee(bid) >= f - sl_tolerance
  R4 capital release (release_bid): bid >= release_bid, tau_h >= 1 and the strategy's free room < release_room_usd
A rule with its parameter None never fires. Execution: a SELL with reduces_exposure=True, taker at the best bid
(limit = bid) when the bid's size covers the market minimum, else a post-only GTD maker at
max(ask - tick, f + fv_margin, bid + tick). Sizes are floored and never exceed what is held net of in-flight SELLs;
below the minimum size nothing is sent. Skipped while the ladder's pull rule holds for the market (pre-close window,
oracle gap, stale book or feed, sharp move, book fault) and when it has no fair value.

Wiring (trader/loop.py, flag exits): the ladder engine keeps `fair[cid]` (its fair value plus that pull reason) and
`cost`; the loop passes positions net of in-flight SELL takers (`available`), appends the exit intents to the
ladder's targets and drops the ladder's complement BUY on the other outcome of any token a rule fired on (`merge`):
the exit takes precedence, so no share is both offered and committed to a complement pair. Every evaluation is a row
for ledger table "exit_decisions" (the loop rate-limits repeats to one a minute).
"""
import math

from trader import fees
from trader.contracts import Book, Intent, MarketInfo
from trader.engines.ladder import MIN_MS, NAME, SIZE_STEP, VERSIONS, floor_to

VERSION = 1
PARAMS = {
    "fv_margin": 0.02, "k_unc": 1.0,                 # R1
    "tp_pct": None, "tp_min_tau_h": 2.0,             # R2 (candidate)
    "sl_drop": None, "sl_tolerance": 0.02,           # R3 (candidate)
    "release_bid": None, "release_room_usd": 5.0,    # R4 (candidate)
    "taker_give_up_ms": 2000,                        # as btc-speed
    "ttl_step_ms": 5 * MIN_MS,                       # maker GTD as the ladder: 5-10 min ahead, never past end - 3 min
}
REGISTRY = {"exit-manager": {"version": VERSION, "state": "candidate", "params": PARAMS}}
PREREG = {
    "test_id": f"exit-manager-v{VERSION}", "name": f"exit-manager-v{VERSION}", "strategy": NAME,
    "hypothesis": "Selling a held ladder position when an exit rule fires beats holding it to settlement, net of fees.",
    "statistic": "per closed position: realised exit value - hold-to-settlement value, net of fees",
    "cluster": "event group", "se": "cluster-robust standard error of the mean",
    "pass_rule": "PASS if mean > 2 SE with n >= 100 positions", "pass_z": 2.0, "n": 100,
    "futility_rule": "stop (FAIL) if mean < -1 SE once n >= 50 positions", "futility_z": -1.0, "futility_n": 50,
    "data": "paper positions replayed per minute (research/exits/study.py) and exit_decisions rows",
    "params": {"name": "exit-manager", "version": VERSION},
}
EPS = 1e-9


def available(positions: dict[str, float], open_orders) -> dict[str, float]:
    """Shares held net of in-flight SELL takers (unknown orders in full). Resting maker SELLs are not netted: they are
    the exit targets the loop re-proposes each round (the requote diff keeps or replaces them)."""
    out = {}
    for t, s in positions.items():
        live = sum(o.intent.size - (0.0 if o.status == "unknown" else o.filled) for o in open_orders
                   if o.intent.token_id == t and o.intent.side == "SELL" and o.intent.kind == "taker")
        if s > EPS:
            out[t] = max(0.0, s - live)
    return out


def exit_intents(now_ms: int, held: dict[str, float], cost: dict[str, tuple[float, float]], books: dict[str, Book],
                 fair: dict[str, dict], markets: dict[str, MarketInfo], params: dict = PARAMS,
                 room_usd: float = math.inf) -> tuple[list[Intent], list[dict]]:
    """(SELL intents, exit_decisions rows) for every held token of a market in `fair`. held: shares available to sell
    (see `available`); cost: token -> (shares, avg cost) as LadderEngine.cost; fair: cid -> ladder fair value with
    "pull"; room_usd: the strategy's free capital room (R4)."""
    p = {**PARAMS, **params}
    by_tok = {t: m for m in markets.values() for t in (m.token_yes, m.token_no)}
    intents, rows = [], []
    for tok, n in sorted(held.items()):
        m = by_tok.get(tok)
        fv = fair.get(m.cid) if m else None
        if fv is None:
            continue                                    # not a ladder market this tick (or ended): nothing to judge
        f = fv["f"] if tok == m.token_yes else 1 - fv["f"]
        unc, tau_h, b = fv.get("unc") or 0.0, fv["tau_h"], books.get(tok)
        bid, ask = (b.best_bid(), b.best_ask()) if b else (None, None)
        row = {"cid": m.cid, "token_id": tok, "held": n, "f": f, "unc": unc, "tau_h": tau_h, "bid": bid, "ask": ask,
               "cost": cost.get(tok, (0, None))[1], "hold_value": f, "sell_value": None, "rule": None, "action": "skip",
               "size": 0.0, "price": None}
        rows.append(row)
        why = fv.get("pull") or ("no bid" if bid is None else None) or \
            (None if all(map(math.isfinite, (f, unc, tau_h))) else "non-finite fair")
        if why:
            row["reason"] = why
            continue
        sell = bid - fees.fee(1, bid, m.fee_rate)
        c = row["cost"]
        row["sell_value"] = sell
        rule = ("R1" if sell > f + max(p["fv_margin"], p["k_unc"] * unc) + EPS else
                "R3" if p["sl_drop"] is not None and c and f < c - p["sl_drop"] and sell >= f - p["sl_tolerance"] else
                "R2" if p["tp_pct"] is not None and c and (bid - c) / c >= p["tp_pct"] and tau_h >= p["tp_min_tau_h"]
                else "R4" if p["release_bid"] is not None and bid >= p["release_bid"] and tau_h >= 1
                and room_usd < p["release_room_usd"] else None)
        row["rule"] = rule
        if rule is None:
            row["action"] = "hold"
            continue
        top = b.bids[0][1]
        if top >= m.min_size:                           # taker at the bid, never more than the bid shows
            kind, px, size, exp = "taker", bid, floor_to(min(n, top), SIZE_STEP), now_ms + p["taker_give_up_ms"]
        else:                                           # post-only maker above the bid, at least fair + margin
            px = max(f + p["fv_margin"], bid + m.tick_size, (ask - m.tick_size) if ask is not None else 0.0)
            px = min(math.ceil(px / m.tick_size - 1e-9) * m.tick_size, 1 - m.tick_size)
            kind, size = "maker", floor_to(n, SIZE_STEP)
            exp = min((now_ms // p["ttl_step_ms"] + 2) * p["ttl_step_ms"], m.end_ms - 3 * MIN_MS)
        px = round(px, 10)
        row.update(price=px, size=size, kind=kind)
        if size < m.min_size:
            row["action"] = "below_min"
            continue
        if kind == "maker" and px < bid + m.tick_size - EPS:
            row["reason"] = "maker would cross"         # bid at 1 - tick: no post-only room above it
            continue
        row["action"] = f"sell_{kind}"
        intents.append(Intent(NAME, m.cid, tok, "SELL", px, size, kind, exp, f,
                              f"exit {rule} f={f:.4f} unc={unc:.4f} bid={bid} sell={sell:.4f} cost={c}",
                              VERSIONS + (("exit-manager", VERSION),), True))
    return intents, rows


def merge(targets: list[Intent], exits: list[Intent], rows: list[dict], markets: dict[str, MarketInfo]) -> list[Intent]:
    """Ladder targets without the BUY on the other outcome of any token a rule fired on, plus the exit SELLs."""
    fired = {i.token_id for i in exits}  # only where a SELL is sent: a residual below min size keeps its complement bid
    drop = set()
    for t in fired:
        m = next((m for m in markets.values() if t in (m.token_yes, m.token_no)), None)
        if m:
            drop.add(m.token_no if t == m.token_yes else m.token_yes)
    return [i for i in targets if not (i.side == "BUY" and i.token_id in drop)] + exits
