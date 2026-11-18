"""Quote-engine full objective (Phase 5, WP5-C; build-plan task 5.5, role 20). Pure functions, no I/O outside --smoke.

Built ahead of its gate: nothing in the trader calls this, and every fit is only a registry candidate dict (state
`candidate` once the caller registers it). Phase 1 convention: bids only, BUY YES at x_Y and BUY NO at x_N, and
I = YES - NO shares held. For one market:

  J = reward + sum_s P_s size_s (edge_s + rebate_s + a(d_s)) - gamma sigma^2 tau (I + size_Y P_Y - size_N P_N)^2

  reward  Polymarket liquidity rewards (docs.polymarket.com/market-makers/liquidity-rewards, re-read 2026-10-01):
          S(v, s) = ((v - s) / v)^2 per share for s < v (s = distance from the mid, v = reward_max_spread, cents),
          0 below reward_min_size. Q_one = YES bids + NO asks, Q_two = YES asks + NO bids (a NO bid at x is a YES ask
          at 1 - x). Q_min = max(min(Q1, Q2), max(Q1, Q2) / c) for 0.10 <= mid <= 0.90, else min(Q1, Q2); c = 3.
          reward = daily_rate x tau / 86,400 x Q_ours / (Q_ours + Q_others), Q_others = S x size summed over all
          displayed non-own size within v on both sides (overstates competition: conservative).
  P_s     1 - exp(-lambda(d) tau), lambda(d) = A exp(-k d) per second, d = token mid (ex own) - price, prob. units
  edge    q - x_Y and (1 - q) - x_N, q = role 23's shrunk fair value for YES
  rebate  rebateRate x trader.fees.fee(1, x, fee_rate) per share filled
  a(d)    m0 + m1 d per share: the 5m mid move after a maker fill (markout minus the spread captured, no double count)
  sigma   mid volatility per sqrt(s), probability units; tau = s to the next requote or the pull before close

optimise() grid-searches both bids jointly and returns ladder.quotes()-shaped [(token, price, size, reduces)] plus
every term. It does not run Phase 1's pull rules: the caller runs ladder.pull_reason() first and calls this only
when there is no pull. wider(current, anchor) is Loop A's rule 7 anchor.

    python -m learning.quote_objective --smoke    # writes reports/phase5_quote_objective.md from real snapshot + books
"""
import argparse
import math

import numpy as np
from scipy.optimize import minimize

from common import DATA, REPORTS, sha256_text
from trader.contracts import Book, MarketInfo
from trader.engines import ladder
from trader.fees import fee

C_ONE_SIDED = 3.0
PRIOR = {"A": 0.01, "k": 100.0,  # stated synthetic prior (no measured fill rate yet): 1/k = 1 cent
         "m0": 0.0, "m1": 0.0,   # ladder markout_prior = 0.0: no adverse move until role 22 measures it
         "fill_source": "prior", "adverse_source": "prior"}
PARAMS = {"gamma": 1.0, "max_inv": ladder.PARAMS["max_inv"], "complement_margin": ladder.PARAMS["complement_margin"],
          "rebate_rate": ladder.PARAMS["rebate_rate"], "d_max": 40, "size_step": 1.0, "c": C_ONE_SIDED}
REPORT = REPORTS / "phase5_quote_objective.md"


# ---------- reward score ----------

def score(v: float, s, size, min_size: float):
    """S(v, s) x size, s = |distance from the mid| in cents; 0 at or beyond v and below min_size."""
    s, size = np.abs(np.asarray(s, float)), np.asarray(size, float)
    return np.where((s < v) & (size >= min_size) & (size > 0), ((v - s) / v) ** 2 * size, 0.0)


def q_min(q_one, q_two, mid: float, c: float = C_ONE_SIDED):
    lo, hi = np.minimum(q_one, q_two), np.maximum(q_one, q_two)
    return np.maximum(lo, hi / c) if 0.10 <= mid <= 0.90 else lo


def q_others(yes: Book, mid: float, v: float) -> float:
    """Displayed non-own size within v of the mid on both sides of the YES book (the NO book is its mirror)."""
    return float(sum(score(v, (p - mid) * 100, s - yes.own.get(p, 0.0), 0.0) for p, s in yes.bids + yes.asks))


def reward_value(daily_rate: float, tau: float, q_ours, q_oth: float):
    return daily_rate * tau / 86_400 * np.where(q_ours > 0, q_ours / np.maximum(q_ours + q_oth, 1e-300), 0.0)


# ---------- fits ----------

def _cr1(h_inv, scores, clusters):
    """CR1 cluster-robust sandwich (same small-sample factor g / (g - 1) as research.kappa.kappa.clustered_mean)."""
    codes = np.unique(np.asarray(clusters), return_inverse=True)[1]
    g = codes.max() + 1
    s = np.zeros((g, scores.shape[1]))
    np.add.at(s, codes, scores)
    return g / (g - 1) * h_inv @ s.T @ s @ h_inv


def fit_fill_rate(orders: list[dict]) -> dict | None:
    """Poisson ML fit of lambda(d) = A exp(-k d) on maker order rows (distance, rest_ms, filled, cluster_id):
    log L = sum [filled ln lambda_i - lambda_i rest_i]. None if nothing filled or d does not vary."""
    d = np.array([o["distance"] for o in orders], float)
    r = np.array([o["rest_ms"] for o in orders], float) / 1000
    f = np.array([bool(o["filled"]) for o in orders], float)
    if len(d) < 3 or f.sum() == 0 or np.ptp(d) == 0:
        return None
    lam = lambda t: np.exp(t[0] - t[1] * d)
    nll = lambda t: lam(t) @ r - f @ (t[0] - t[1] * d)
    jac = lambda t: np.array([(lam(t) * r - f).sum(), ((f - lam(t) * r) * d).sum()])

    def hess(t):
        w = lam(t) * r
        return np.array([[w.sum(), -(w * d).sum()], [-(w * d).sum(), (w * d * d).sum()]])

    res = minimize(nll, [math.log(f.sum() / r.sum()), 0.0], jac=jac, hess=hess, method="trust-exact")
    if not res.success or not np.all(np.isfinite(res.x)):
        return None
    t = res.x
    v = _cr1(np.linalg.inv(hess(t)), ((f - lam(t) * r)[:, None] * np.column_stack([np.ones_like(d), -d])),
             [o["cluster_id"] for o in orders])
    A = math.exp(t[0])
    return {"A": A, "k": float(t[1]), "se_A": A * math.sqrt(v[0, 0]), "se_k": math.sqrt(v[1, 1]),
            "n": len(d), "fills": int(f.sum())}


def fit_adverse(fills: list[dict]) -> dict | None:
    """OLS of a = markout_5m - d on d over maker fills, d = side-signed spread captured (mid_ex_own - price for a
    BUY). a(d) = m0 + m1 d is the mid move only: the fill row's markout already includes the spread."""
    rows = [x for x in fills if x.get("maker")]
    if len(rows) < 3:
        return None
    sg = np.array([1.0 if x["side"] == "BUY" else -1.0 for x in rows])
    d = sg * np.array([x["mid_ex_own"] - x["price"] for x in rows], float)
    y = np.array([x["markout_5m"] for x in rows], float) - d
    if np.ptp(d) == 0:
        return None
    X = np.column_stack([np.ones_like(d), d])
    h_inv = np.linalg.inv(X.T @ X)
    beta = h_inv @ X.T @ y
    v = _cr1(h_inv, X * (y - X @ beta)[:, None], [x["cluster_id"] for x in rows])
    return {"m0": float(beta[0]), "m1": float(beta[1]), "se_m0": math.sqrt(v[0, 0]), "se_m1": math.sqrt(v[1, 1]),
            "n": len(rows)}


def _clusters(rows) -> int:
    return len({r["cluster_id"] for r in rows})


def _fit(orders, fills, min_clusters, fallback, level) -> tuple[dict, dict]:
    """(params, evidence) at this level; each part falls back separately when it has too few clusters."""
    fr = fit_fill_rate(orders) if _clusters(orders) >= min_clusters else None
    ad = fit_adverse(fills) if _clusters(fills) >= min_clusters else None
    params = {"A": fr["A"] if fr else fallback["A"], "k": fr["k"] if fr else fallback["k"],
              "m0": ad["m0"] if ad else fallback["m0"], "m1": ad["m1"] if ad else fallback["m1"],
              "fill_source": level if fr else fallback["fill_source"],
              "adverse_source": level if ad else fallback["adverse_source"]}
    ev = {"orders": len(orders), "order_clusters": _clusters(orders), "fills": len(fills),
          "fill_clusters": _clusters(fills), "min_clusters": min_clusters,
          **{k: (fr or {}).get(k) for k in ("se_A", "se_k")}, **{k: (ad or {}).get(k) for k in ("se_m0", "se_m1")}}
    return params, ev


def _candidate(key: str, mode: str, params: dict, ev: dict) -> dict:
    params = {"mode": mode, **params}
    return {"name": f"quote-objective:{key}", "version": sha256_text(repr(sorted(params.items())))[:12],
            "params": params, "evidence": ev}


def fit_candidates(orders: list[dict], fills: list[dict], priors: dict | None = None,
                   min_clusters: int = 30) -> list[dict]:
    """Registry candidates, never applied here: `quote-objective:<mode>` per mode and `quote-objective:<cid>` per
    market. A market under min_clusters uses its mode's fit; a mode under it uses priors[mode] (default PRIOR).
    Never pooled across modes: every fit sees one mode's rows only."""
    fills = [x for x in fills if x.get("maker")]
    out = []
    for mode in sorted({r["mode"] for r in orders + fills}):
        mo, mf = [r for r in orders if r["mode"] == mode], [r for r in fills if r["mode"] == mode]
        base, ev = _fit(mo, mf, min_clusters, {**PRIOR, **(priors or {}).get(mode, {})}, "mode")
        out.append(_candidate(mode, mode, base, ev))
        for cid in sorted({r["cid"] for r in mo + mf}):
            out.append(_candidate(cid, mode, *_fit([r for r in mo if r["cid"] == cid],
                                                   [r for r in mf if r["cid"] == cid], min_clusters, base, "market")))
    return out


# ---------- objective ----------

def side_terms(x, size, mid_s: float, q_s: float, fit: dict, tau: float, fee_rate: float, rebate_rate: float,
               reward: dict | None) -> dict:
    """Per-bid terms (arrays broadcast): d, P, edge, rebate, adverse, fill = P size (edge + rebate + adverse),
    e = expected shares filled, qs = reward score."""
    x, size = np.asarray(x, float), np.asarray(size, float)
    d = mid_s - x
    P = 1 - np.exp(-fit["A"] * np.exp(-fit["k"] * d) * tau)
    edge = q_s - x
    rebate = rebate_rate * np.array([fee(1, float(v), fee_rate) for v in x.ravel()]).reshape(x.shape)
    adverse = fit["m0"] + fit["m1"] * d
    qs = score(reward["max_spread"], d * 100, size, reward["min_size"]) if reward else np.zeros_like(size)
    return {"d": d, "P": P, "edge": edge, "rebate": rebate, "adverse": adverse,
            "fill": P * size * (edge + rebate + adverse), "e": size * P, "qs": qs}


def total(Y: dict, N: dict, net: float, mid: float, sigma: float, tau: float, gamma: float, reward: dict | None,
          q_oth: float, c: float = C_ONE_SIDED):
    """(J, reward, inventory penalty) for YES-side and NO-side terms (broadcast)."""
    rw = reward_value(reward["daily_rate"], tau, q_min(Y["qs"], N["qs"], mid, c), q_oth) if reward else 0.0
    inv = gamma * sigma ** 2 * tau * (net + Y["e"] - N["e"]) ** 2
    return rw + Y["fill"] + N["fill"] - inv, rw, inv


def _sides(m: MarketInfo, q: float, mid: float, net: float):
    return ((m.token_yes, mid, q, net, m.token_no, 0), (m.token_no, 1 - mid, 1 - q, -net, m.token_yes, 1))


def _candidates(m: MarketInfo, mid_s: float, own: float, other: str, ask: float | None, cost: dict, p: dict):
    """(prices, sizes, complement) on the grid, size 0 first, then widest price and smallest size first (argmax
    breaks ties toward the more conservative quote). Holding >= min_size of the other outcome makes this a
    complement bid: priced strictly below 1 - cost - margin, sized up to what it pairs off (as ladder.quotes)."""
    tick = m.tick_size
    held_other = -own
    comp = held_other >= m.min_size
    j_mid = round(ladder.floor_to(mid_s, tick) / tick)                    # BUY: rounded down, never up
    j_hi = min(j_mid, round(1 / tick) - 1)
    if ask is not None:
        j_hi = min(j_hi, math.ceil(ask / tick - 1e-9) - 1)              # post-only: strictly below the best ask
    if comp and other in cost:
        cap = 1 - cost[other] - p["complement_margin"]
        j_hi = min(j_hi, math.ceil(cap / tick - 1e-9) - 1)              # strictly below the complement cap
    limit = ladder.floor_to(held_other if comp else p["max_inv"] - own, ladder.SIZE_STEP)
    sizes = [] if (comp and other not in cost) or limit < m.min_size else sorted(
        {ladder.floor_to(s, ladder.SIZE_STEP) for s in np.arange(m.min_size, limit, p["size_step"])} | {limit})
    xs, ns = [mid_s], [0.0]
    for j in range(max(1, j_mid - p["d_max"]), j_hi + 1):
        for s in sizes:
            xs.append(round(j * tick, 10))
            ns.append(s)
    return np.array(xs), np.array(ns), comp


def evaluate(m: MarketInfo, quotes: list[tuple], q: float, mid: float, net: float, fit: dict, sigma: float,
             tau: float, reward: dict | None = None, q_oth: float = 0.0, p: dict | None = None) -> dict:
    """Every term of J for any bid set [(token, price, size, reduces)] (ours or ladder.quotes()'s)."""
    p = {**PARAMS, **(p or {})}
    by = {t: (px, sz) for t, px, sz, _ in quotes}
    T, out = [], {}
    for token, mid_s, q_s, *_ in _sides(m, q, mid, net):
        px, sz = by.get(token, (mid_s, 0.0))
        t = {k: float(v) for k, v in side_terms(px, sz, mid_s, q_s, fit, tau, m.fee_rate, p["rebate_rate"],
                                                reward).items()}
        T.append(t)
        out[token] = {"price": px, "size": sz, **t}
    J, rw, inv = total(T[0], T[1], net, mid, sigma, tau, p["gamma"], reward, q_oth, p["c"])
    return {"J": float(J), "J0": -p["gamma"] * sigma ** 2 * tau * net ** 2, "reward": float(rw),
            "inventory": float(inv), "sides": out}


def optimise(m: MarketInfo, q: float, mid: float, asks: tuple, net: float, cost: dict, fit: dict, sigma: float,
             tau: float, reward: dict | None = None, q_oth: float = 0.0, p: dict | None = None):
    """Best bids [(token, price, size, reduces_exposure)] and evaluate()'s breakdown. Joint grid search over both
    bids: prices on the tick grid from the token mid (rounded down) to d_max ticks below it, sizes {0} U
    [min_size .. inventory limit]. No quote when J does not beat quoting nothing (J0 = -gamma sigma^2 tau I^2,
    0 when flat). asks = best (YES, NO) asks; cost = {token: avg cost} for complement caps."""
    p = {**PARAMS, **(p or {})}
    cand, T = [], []
    for token, mid_s, q_s, own, other, i in _sides(m, q, mid, net):
        xs, ns, comp = _candidates(m, mid_s, own, other, asks[i], cost, p)
        cand.append((token, xs, ns, comp))
        T.append(side_terms(xs, ns, mid_s, q_s, fit, tau, m.fee_rate, p["rebate_rate"], reward))
    J, _, _ = total({k: v[:, None] for k, v in T[0].items()}, {k: v[None, :] for k, v in T[1].items()},
                    net, mid, sigma, tau, p["gamma"], reward, q_oth, p["c"])
    J = np.round(J, 9)                     # gains under 1e-9 USD tie, and ties go to the more conservative candidate
    best = np.unravel_index(np.argmax(J), J.shape)
    quotes = [(tok, float(xs[i]), float(ns[i]), comp) for (tok, xs, ns, comp), i in zip(cand, best) if ns[i] > 0]
    if J[best] <= -p["gamma"] * sigma ** 2 * tau * net ** 2 + 1e-9:
        quotes = []
    return quotes, evaluate(m, quotes, q, mid, net, fit, sigma, tau, reward, q_oth, p)


def wider(a: list[tuple], b: list[tuple]) -> list[tuple]:
    """Loop A rule 7: per token the lower price and the smaller size; a token quoted by only one of the two is
    dropped. Quotes from current parameters pass through wider(current, anchor)."""
    bb = {t: (px, sz, r) for t, px, sz, r in b}
    return [(t, min(px, bb[t][0]), min(sz, bb[t][1]), r and bb[t][2]) for t, px, sz, r in a if t in bb]


# ---------- seeded synthetic rows (smoke and tests) ----------

def synthetic(seed: int, mode: str, cids: list[str], clusters: int, n_orders: int, A: float, k: float, m0: float,
              m1: float, noise: float = 0.01) -> tuple[list[dict], list[dict]]:
    """(maker order rows, maker fill rows) from lambda(d) = A exp(-k d), censored by a uniform 5-120 s cancel, and
    5m markout = d + m0 + m1 d + cluster effect + noise. BUY orders around a 0.5 mid."""
    rng = np.random.default_rng(seed)
    d = rng.uniform(0, 0.05, n_orders)
    t_fill = rng.exponential(1 / (A * np.exp(-k * d)))
    t_cancel = rng.uniform(5, 120, n_orders)
    cl = rng.integers(0, clusters, n_orders)
    shock = rng.normal(0, noise, clusters)
    orders, fills = [], []
    for i in range(n_orders):
        cid, cluster = cids[i % len(cids)], f"{mode}#{cl[i]}"
        filled = bool(t_fill[i] <= t_cancel[i])
        orders.append({"cid": cid, "cluster_id": cluster, "mode": mode, "token_id": f"{cid}-Y", "side": "BUY",
                       "price": 0.5 - d[i], "size": 10.0, "distance": d[i],
                       "rest_ms": 1000 * min(t_fill[i], t_cancel[i]), "filled": filled})
        if filled:
            fills.append({"cid": cid, "cluster_id": cluster, "mode": mode, "token_id": f"{cid}-Y", "side": "BUY",
                          "price": 0.5 - d[i], "size": 10.0, "maker": True, "mid_ex_own": 0.5,
                          "markout_5m": d[i] + m0 + m1 * d[i] + shock[cl[i]] + rng.normal(0, noise)})
    return orders, fills


# ---------- smoke ----------

SMOKE = {"sigma": 0.0005, "requote_s": 60.0, "per_mode": {"crypto-term": 3, "crypto-hourly": 2, "sports-pregame": 2},
         "hypothetical_rate": 100.0, "inv_net": 20.0}


def _market(r: dict) -> MarketInfo:
    from trader.marketdata import iso_ms, market_info
    return market_info(r) or MarketInfo(  # sports rows: market_info parses crypto assets only
        cid=r["condition_id"], token_yes=r["yes_token_id"], token_no=r["no_token_id"], mode=r["mode"],
        question=r.get("question") or "", rules_sha256=r["rules_sha256"], tick_size=float(r["tick_size"]),
        min_size=float(r["min_order_size"]), fee_rate=float((r.get("fee_schedule") or {}).get("rate", 0.0)),
        neg_risk=bool(r.get("neg_risk")), end_ms=iso_ms(r["end_time"]), event_group=r.get("event_slug") or "")


def _table(head: list[str], rows: list[list]) -> list[str]:
    f = lambda v: f"{v:.4g}" if isinstance(v, float) else str(v)
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(map(f, r)) + " |"
                                                                       for r in rows]


def _rows(m: MarketInfo, label: str, b: dict) -> list[list]:
    out = []
    for tok, name in ((m.token_yes, "YES"), (m.token_no, "NO")):
        s = b["sides"][tok]
        if s["size"] > 0:
            out.append([label, name, s["price"], s["size"], s["d"], s["P"], s["edge"], s["rebate"], s["adverse"],
                        s["fill"]])
    return (out or [[label, "-", "no quote", 0.0, "", "", "", "", "", 0.0]]) + [
        [label, "total", "", "", "", "", "", f"reward {b['reward']:.4g}", f"inventory -{b['inventory']:.4g}",
         f"J {b['J']:.4g} (J0 {b['J0']:.4g})"]]


def smoke(report=REPORT) -> str:
    import pandas as pd
    from recorder import crawler
    from trader.marketdata import Books

    snap = crawler.latest_snapshot(crawler.MARKETS_DIR)
    snap_rows = crawler.read_snapshot(snap)
    books, now, files = Books(), 0, []
    for f in sorted(DATA.glob("recordings/parquet/stream=*/date=*/*.parquet")):
        if "deribit" in f.as_posix():
            continue
        df = pd.read_parquet(f, columns=["t", "raw"]).sort_values("t", kind="stable")
        for t, raw in zip(df["t"], df["raw"]):
            books.apply(raw, int(t))
        now = max(now, int(df["t"].max()))
        files.append(f"{f.relative_to(DATA).as_posix()} ({len(df)} messages)")
    lp = ladder.PARAMS
    sigma, pull = SMOKE["sigma"], lp["pull_before_close_ms"]
    half = lp["half_min"] + lp["k_vol"] * sigma * math.sqrt(lp["vol_horizon_s"])
    picked = {}
    for r in snap_rows:
        if r["mode"] not in SMOKE["per_mode"]:
            continue
        m = _market(r)
        yes, no = books.books.get(m.token_yes), books.books.get(m.token_no)
        if not (yes and no and yes.mid_ex_own() is not None and m.end_ms - pull > now):
            continue
        width = yes.best_ask() - yes.best_bid()
        if width <= lp["max_book_width"]:
            picked.setdefault(m.mode, []).append((abs(yes.mid_ex_own() - 0.5), width, m.cid, m, r, yes, no))
    head = ["quote", "token", "price", "size", "d", "P(fill)", "edge", "rebate", "a(d)", "fill term"]
    out = ["# Quote-engine full objective: smoke (Phase 5, WP5-C)", "",
           "Built ahead of its gate: nothing in the trader calls this module, no order is placed, and fits are "
           "registry candidates only. Exploratory illustration of the objective on real market parameters and "
           "recorded books, with stated prior fill and markout parameters (no fills have been measured yet).", "",
           "## Inputs", "",
           f"- Markets: latest crawler snapshot `{snap.relative_to(DATA.parent).as_posix()}` ({len(snap_rows)} rows): "
           "real tick, minimum size, fee rate, rebate rate and reward parameters.",
           f"- Books: replayed through `trader.marketdata.Books` from {', '.join(files)}; quoting time = last "
           f"recorded message, {pd.Timestamp(now, unit='ms', tz='UTC'):%Y-%m-%d %H:%M:%S} UTC. Only markets whose "
           "YES and NO books were both recorded and whose book is at most 0.10 wide are sampled, mid nearest 0.5 first.",
           f"- Fill rate (stated prior, not fitted): A = {PRIOR['A']}/s, k = {PRIOR['k']} per probability unit "
           f"(1/k = {1 / PRIOR['k']:.3f}). Adverse move: m0 = {PRIOR['m0']}, m1 = {PRIOR['m1']} (Phase 1's "
           "markout_prior = 0.0).",
           f"- sigma = {sigma}/sqrt(s) (stated), gamma = {PARAMS['gamma']}, tau = min({SMOKE['requote_s']:.0f} s "
           f"requote, time to the pull {pull // 60000} min before close), grid d_max = {PARAMS['d_max']} ticks, "
           f"size step {PARAMS['size_step']}, inventory limit {PARAMS['max_inv']}.",
           "- q = mid (no reference feed in the window, so role 23's shrink has nothing to move; edge then equals the "
           "distance d). I = 0 unless stated.",
           f"- Phase 1 `ladder.quotes()` on the same inputs: q = mid, half = half_min + k_vol x sigma x "
           f"sqrt(vol_horizon_s) = {half:.4f}, ladder.PARAMS defaults; its bids are scored with the same objective.",
           "- Phase 1's pull rules run before either quoter (the caller's job when wired; markets inside the "
           "pre-close pull window are not sampled).", ""]
    first = None
    for mode, n in SMOKE["per_mode"].items():
        out += [f"## {mode}", ""]
        rows = sorted(picked.get(mode, []), key=lambda c: c[:3])[:n]
        if not rows:
            out += ["No recorded market with both books in this mode.", ""]
        for _, _, _, m, r, yes, no in rows:
            mid = yes.mid_ex_own()
            asks = (yes.best_ask(), no.best_ask())
            tau = min(SMOKE["requote_s"], (m.end_ms - pull - now) / 1000)
            rew = {"min_size": r["reward_min_size"], "max_spread": r["reward_max_spread"],
                   "daily_rate": r["reward_daily_rate"]}
            qo = q_others(yes, mid, rew["max_spread"])
            p = {"rebate_rate": (r.get("fee_schedule") or {}).get("rebateRate", 0.0)}
            ours, b = optimise(m, mid, mid, asks, 0.0, {}, PRIOR, sigma, tau, rew, qo, p)
            ph1 = ladder.quotes(mid, half, 0.0, {}, m, asks, lp)
            b1 = evaluate(m, ph1, mid, mid, 0.0, PRIOR, sigma, tau, rew, qo, p)
            first = first or (m, r, yes, no, mid, asks, tau, rew, qo, p)
            out += [f"### {m.question}", "",
                    f"`{m.cid[:12]}…` tick {m.tick_size}, min size {m.min_size}, fee rate {m.fee_rate}, rebate rate "
                    f"{p['rebate_rate']}, reward pool ${rew['daily_rate']}/day (min {rew['min_size']}, max spread "
                    f"{rew['max_spread']}c), YES book {yes.best_bid()} x {yes.bids[0][1]:g} / {yes.best_ask()} x "
                    f"{yes.asks[0][1]:g}, NO best ask {asks[1]}, mid {mid:.4f}, tau {tau:.0f} s, Q_others {qo:.1f}.",
                    ""] + _table(head, _rows(m, "objective", b) + _rows(m, "Phase 1 quotes()", b1)) + [""]
    if first:
        m, r, yes, no, mid, asks, tau, rew, qo, p = first
        net, c = SMOKE["inv_net"], round(mid, 4)
        cost = {m.token_yes: c}
        ours, b = optimise(m, mid, mid, asks, net, cost, PRIOR, sigma, tau, rew, qo, p)
        _, bg = optimise(m, mid, mid, asks, net, cost, PRIOR, sigma, tau, rew, qo, {**p, "gamma": 50.0})
        b1 = evaluate(m, ladder.quotes(mid, half, net, cost, m, asks, lp), mid, mid, net, PRIOR, sigma, tau, rew, qo, p)
        hyp = {**rew, "daily_rate": SMOKE["hypothetical_rate"]}
        _, bh = optimise(m, mid, mid, asks, 0.0, {}, PRIOR, sigma, tau, hyp, qo, p)
        out += ["## Scenarios on the first sampled market", "", f"{m.question}", "",
                f"### Inventory: I = +{net:g} YES bought at {c} (the mid), so the NO bid is a complement bid strictly "
                f"below 1 - {c} - {PARAMS['complement_margin']} and at most {net:g} shares", ""]
        out += _table(head, _rows(m, "objective", b) + _rows(m, "objective, gamma 50", bg) +
                      _rows(m, "Phase 1 quotes()", b1)) + [""]
        out += [f"### Hypothetical reward pool ${hyp['daily_rate']:.0f}/day (today's real pool is "
                f"${rew['daily_rate']}): exercises the reward term on the real book", ""]
        out += _table(head, _rows(m, "objective", bh)) + [""]
    orders, fills = synthetic(7, "crypto-term", ["0xaaa", "0xbbb"], 60, 4000, 0.02, 60.0, -0.002, -0.3)
    o2, f2 = synthetic(8, "sports-pregame", ["0xccc"], 12, 600, 0.01, 30.0, 0.0, 0.0)
    cands = fit_candidates(orders + o2, fills + f2, min_clusters=30)
    out += ["## Fits on seeded synthetic rows (candidates only)", "",
            "crypto-term: 4,000 orders in 60 clusters over 2 markets, true A = 0.02, k = 60, m0 = -0.002, m1 = -0.3. "
            "sports-pregame: 600 orders in 12 clusters (under min_clusters = 30, so its mode and market use the "
            "prior). Standard errors are CR1 cluster-robust.",
            ""] + _table(["candidate", "A", "k", "se_k", "m0", "se_m0", "m1", "se_m1", "fill source",
                          "adverse source", "order clusters"],
                         [[c["name"][:32], c["params"]["A"], c["params"]["k"], c["evidence"]["se_k"] or "-",
                           c["params"]["m0"], c["evidence"]["se_m0"] or "-", c["params"]["m1"],
                           c["evidence"]["se_m1"] or "-", c["params"]["fill_source"], c["params"]["adverse_source"],
                           c["evidence"]["order_clusters"]] for c in cands])
    out += ["", "The two crypto-term markets share the same 60 clusters, so their fit errors are correlated; "
            "the tests check CR1 coverage over 20 seeds (each coefficient inside 2 SE in at least 16 of 20).", "",
            "No candidate is registered or promoted by this module; wiring passes them to the ledger's "
            "registry (state `candidate`), and live use needs Loop B and a human token.", "",
            "## Reading the results", "",
            "- With prior fills (1/k = 1 cent) and a = 0, the objective quotes at the touch or one tick inside a "
            "wider book, where Phase 1 sits half_min + vol below q. On one-tick-wide books both quote the touch.",
            "- J is linear in size apart from the inventory term, so the objective sizes up to the inventory limit "
            "(50) while Phase 1 quotes 10. At the stated sigma and gamma = 1 the inventory term is tiny "
            "(gamma sigma^2 tau = 1.5e-5 per share^2); gamma = 50 visibly widens the YES bid when long YES. gamma "
            "has to be calibrated (a registry parameter) before this objective could replace quotes().",
            "- The rebate is material at mid 0.5: 0.0035 per share against a 1-cent edge.",
            "- The reward term is 0 on every sampled market (no target market pays rewards today, as Phase 0 "
            "found); a hypothetical $100/day pool adds about $0.01 per 60 s quote here.",
            "- Comparative statics as built: a larger sigma or tau never tightens a flat, symmetric quote, and never "
            "tightens the bid that adds to expected inventory. The bid that sheds expected inventory can tighten "
            "under a larger sigma or tau: that is the inventory term doing its job (as in Avellaneda-Stoikov), not "
            "a bug, and it follows from J as specified.",
            "- Reward formula re-read on docs.polymarket.com/market-makers/liquidity-rewards (2026-10-01): S, Q_one, "
            "Q_two, Q_min with c = 3 and the 0.10-0.90 band match; tests pin S(4.5, 1.5) = 0.4444 and agree with "
            "Phase 0's research.measure.reward_income scorer.", "",
            "## How to reproduce", "", "From `roster/`:", "", "```",
            r".venv\Scripts\python.exe -m learning.quote_objective --smoke",
            r".venv\Scripts\python.exe -m pytest tests/phase5/test_quote_objective.py -q", "```", "",
            "Uses the latest `data/markets/` snapshot and the recorded Parquet books on this PC (read-only); no network."]
    text = "\n".join(out) + "\n"
    report.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    if ap.parse_args().smoke:
        smoke()
        print(f"wrote {REPORT}")
