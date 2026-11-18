"""Touch-market pricer and coherence bound (Phase 3, WP3-A; build-plan 3.1; roles 17, 18). Pure functions, no I/O.

A touch market pays 1 if any Binance USDT 1m high ("touch-up": will X reach $H) or low ("touch-down": will X dip to
$H) in the window reaches the barrier H. Priced as the exact GBM one-touch probability under continuous monitoring with
log drift -sigma^2/2 (S a martingale), sigma_P = kappa(tau) x sigma_Q. Units as trader.engines.ladder.digital: sigma
annualised on a 365-day year, tau in hours.

Convention (shared with WP3-C): MarketInfo kind "touch-up" | "touch-down", strike = H in USDT, end_ms = window end,
mode "crypto-term", event_group "<ASSET>-touch@<end UTC>". MarketInfo has no window start, so the caller passes the
running 1m high and low since the window start in ref[asset]["high"] and ref[asset]["low"].

Wiring later (nothing is wired here):
  - ladder.fair_value dispatches kinds touch-* to touch_fair(m, ref[asset], now_ms, REGISTRY["touch"]["params"]);
    the ladder's arb scan calls coherence_flags for each (touch, same-level digital) pair and logs what it returns.
  - marketdata keeps the running 1m high/low since each window start (kline_1m h and l; WP3-C's window_start_ms).
  - REGISTRY["touch"] (state candidate) and PREREG are written once through the Ledger; the fair record keeps basis.

Smoke (public GETs only, never run by the tests): python -m trader.growth.touch --smoke
"""
import math
import sys
from statistics import NormalDist

from trader.contracts import Book, MarketInfo
from trader.engines.ladder import H_MS, KAPPA, YEAR_H, digital, kappa_for, sigma_q

NAME = "touch"
VERSION = 1
_N = NormalDist()

PARAMS = {
    "kappa": dict(KAPPA),      # ladder kappa v1 (terminal digitals, Phase 0 test A FAILED at 1.8 SE); not fitted on
                               # touch outcomes, and nothing is fitted beyond the 24h bucket
    "sigma_rel_unc": 0.10,     # +/- on sigma_P for unc, as the ladder pricer
    "eps_tol": 0.01,           # coherence slack on market prices (one tick); C(H)/H is added for up barriers
}
REGISTRY = {NAME: {"version": VERSION, "state": "candidate", "params": PARAMS,
                   "source": "kappa copied from ladder kappa v1 (reports/kappa_report.md); refit through Loop B"}}
PREREG = {
    "name": f"{NAME}-v{VERSION}",
    "hypothesis": "On BTC/ETH Polymarket touch markets, the kappa-scaled GBM one-touch fair value has lower log loss "
                  "than the market mid excluding our orders.",
    "statistic": "per touch window: mean over (market, daily checkpoint) of log loss(mid) - log loss(model), outcomes "
                 "from Binance USDT 1m highs/lows over the window",
    "cluster": "touch window end instant (BTC and ETH windows ending together are one cluster; every barrier and "
               "checkpoint of a window rides the same price path)",
    "se": "cluster-robust standard error of the mean per cluster",
    "alpha": 0.0228,           # one-sided, z = 2
    "pass_z": 2.0, "n": 30,    # PASS if mean > 2 SE with n >= 30 clusters
    "futility_z": -1.0, "futility_n": 15,  # stop (FAIL) if mean < -1 SE once n >= 15 clusters
    "data": "replay on past touch windows (Binance 1m, Deribit DVOL, Polymarket /prices-history), then shadow",
    "params": {"name": NAME, "version": VERSION},
}


# ---------- pricer (17) ----------

def one_touch(S: float, H: float, sigma: float, tau_h: float, up: bool, basis: float = 1.0,
              touched: bool = False) -> float:
    """P(the path hits H' = H x basis within tau), GBM with log drift -sigma^2/2, continuous monitoring.
    With s = sigma sqrt(tau), b = |ln(H'/S)|, a = (-b - s^2/2)/s, c = (-b + s^2/2)/s:
    up = N(a) + (S/H') N(c), down = N(c) + (S/H') N(a). basis is USD per USDT: 1.0 when S is the Binance USDT price."""
    Hb = H * basis
    if touched or (S >= Hb if up else S <= Hb):
        return 1.0
    if tau_h <= 0 or sigma <= 0:
        return 0.0
    s = sigma * math.sqrt(tau_h / YEAR_H)
    b = abs(math.log(Hb / S))
    a, c = (-b - s * s / 2) / s, (-b + s * s / 2) / s
    return min(1.0, _N.cdf(a) + S / Hb * _N.cdf(c) if up else _N.cdf(c) + S / Hb * _N.cdf(a))


def touch_fair(m: MarketInfo, r: dict, now_ms: int, params: dict) -> dict:
    """Fair P(YES) of a touch market from r = ref[asset] ("price", "dvol" or "sigma_q", "high", "low", opt. "basis");
    {"err": ...} when an input is missing or the kind is wrong. Never guesses: a missing running extreme is an error,
    since the barrier may already have been touched."""
    if m.kind not in ("touch-up", "touch-down"):
        return {"err": f"not a touch market: {m.kind!r}"}
    up = m.kind == "touch-up"
    S, H, ext = r.get("price"), m.strike, r.get("high" if up else "low")
    sq = r.get("sigma_q") or (sigma_q(r["dvol"]) if r.get("dvol") else None)
    if not S or not H or not sq or ext is None:
        return {"err": "missing price, vol, barrier or running high/low"}
    tau_h = (m.end_ms - now_ms) / H_MS
    basis = r.get("basis") or 1.0
    touched = ext >= H if up else ext <= H            # running extremes are Binance USDT, like H
    k = kappa_for(max(tau_h, 1e-9), params["kappa"])  # beyond the largest bucket: that bucket, flagged unfitted
    sig, u = k * sq, params["sigma_rel_unc"]
    f = one_touch(S, H, sig, tau_h, up, basis, touched)
    unc = abs(one_touch(S, H, sig * (1 + u), tau_h, up, basis, touched)
              - one_touch(S, H, sig * (1 - u), tau_h, up, basis, touched)) / 2
    return {"f": f, "unc": unc, "S": S, "H": H, "sigma_q": sq, "kappa": k, "sigma_p": sig, "tau_h": tau_h,
            "basis": basis, "touched": touched, "kappa_unfitted": tau_h > max(params["kappa"])}


# ---------- coherence (18) ----------

def call_over_h(S: float, H: float, sigma: float, tau_h: float) -> float:
    """Undiscounted zero-drift call at strike H, divided by H: (S/H) N(d1) - N(d2)."""
    s = sigma * math.sqrt(tau_h / YEAR_H)
    d2 = (math.log(S / H) - s * s / 2) / s
    return S / H * _N.cdf(d2 + s) - _N.cdf(d2)


def eps(S: float, H: float, sigma: float, tau_h: float, up: bool, eps_tol: float) -> float:
    """Slack on touch <= 2 x digital + eps: touch_up = 2 digital_up + C/H, touch_down = 2 digital_down - P/H."""
    return eps_tol + (call_over_h(S, H, sigma, tau_h) if up else 0.0)


def bounds(S: float, H: float, sigma: float, tau_h: float, up: bool, eps_tol: float) -> tuple[float, float]:
    """(digital, 2 x digital + eps) with digital the same-side terminal probability (NO of "above $H" for down)."""
    d = digital(S, H, sigma, tau_h)
    d = d if up else 1 - d
    return d, 2 * d + eps(S, H, sigma, tau_h, up, eps_tol)


def coherence_flags(touch_book: Book, digital_book: Book, S: float, H: float, sigma: float, tau_h: float, up: bool,
                    eps_tol: float) -> list[str]:
    """Log-only check of market prices against digital <= touch <= 2 x digital + eps. digital_book is the "above $H"
    YES book for an up-touch and its NO book for a down-touch. The lower check needs the digital to settle inside the
    window; the upper one needs it to settle at the window end, with sigma and tau_h of that common horizon."""
    ta, tb, da, db = touch_book.best_ask(), touch_book.best_bid(), digital_book.best_ask(), digital_book.best_bid()
    out = []
    if ta is not None and db is not None and ta < db:
        out.append("touch<terminal")
    if tb is not None and da is not None and tb > 2 * da + eps(S, H, sigma, tau_h, up, eps_tol):
        out.append("touch>2x_digital+eps")
    return out


# ---------- smoke: model vs mid on the listed monthly touch markets (public GETs) ----------

def _smoke() -> None:
    import datetime as dt
    import re
    import time

    from common import get_json
    from trader.engines.ladder import ET

    now = int(time.time() * 1000)
    t = dt.datetime.now(ET)
    start = int(dt.datetime(t.year, t.month, 1, tzinfo=ET).timestamp() * 1000)  # 00:00 ET on the 1st
    print(f"now {dt.datetime.fromtimestamp(now / 1000, dt.timezone.utc):%Y-%m-%dT%H:%MZ}")
    print("| asset | market | S | high/low | sigma_Q | tau_h | f (model) | unc | bid | ask | mid | f - mid |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for asset, name in (("BTC", "bitcoin"), ("ETH", "ethereum")):
        ev = get_json("https://gamma-api.polymarket.com/events",
                      {"slug": f"what-price-will-{name}-hit-in-{t:%B}-{t.year}".lower()})[0]
        k = get_json("https://api.binance.com/api/v3/klines",
                     {"symbol": f"{asset}USDT", "interval": "1h", "startTime": start, "limit": 1000})
        S = float(get_json("https://api.binance.com/api/v3/ticker/price", {"symbol": f"{asset}USDT"})["price"])
        dv = get_json("https://www.deribit.com/api/v2/public/get_volatility_index_data",
                      {"currency": asset, "start_timestamp": now - 3 * H_MS, "end_timestamp": now,
                       "resolution": "3600"})["result"]["data"][-1][4]
        r = {"price": S, "dvol": dv, "high": max(float(x[2]) for x in k), "low": min(float(x[3]) for x in k)}
        for gm in sorted(ev["markets"], key=lambda g: g["question"]):
            q = re.search(r"(reach|dip to) \$([\d,]+)", gm["question"])
            if not q or gm.get("closed") or gm.get("bestBid") is None or gm.get("bestAsk") is None:
                continue
            kind = "touch-up" if q[1] == "reach" else "touch-down"
            end = int(dt.datetime.fromisoformat(gm["endDate"].replace("Z", "+00:00")).timestamp() * 1000)
            m = MarketInfo(gm["conditionId"], "", "", "crypto-term", gm["question"], "", 0.01, 5.0, 0.0, False, end,
                           f"{asset}-touch@{gm['endDate']}", asset, float(q[2].replace(",", "")), kind)
            fv = touch_fair(m, r, now, PARAMS)
            bid, ask = float(gm["bestBid"]), float(gm["bestAsk"])
            mid = (bid + ask) / 2
            print(f"| {asset} | {q[1]} {q[2]} | {S:g} | {r['high' if kind == 'touch-up' else 'low']:g} | "
                  f"{fv['sigma_q']:.4f} | {fv['tau_h']:.1f} | {fv['f']:.3f} | {fv['unc']:.3f} | {bid:g} | {ask:g} | "
                  f"{mid:.3f} | {fv['f'] - mid:+.3f} |")


if __name__ == "__main__" and "--smoke" in sys.argv:
    _smoke()
