"""ladder-maker engine (Phase 1, WP1-D; build-plan tasks 1.6, 1.8-1.13). Pure decisions, no I/O, paper only.

Maker bids on BTC/ETH daily strike ladders ("above $K on <date>") and daily Up/Down, which settle on the close of
the Binance BTC/USDT or ETH/USDT 1m candle that opens at 12:00 ET. Each tick, for every crypto-term market:
  pricer (10/17)  f = P(S_T > K) or P(S_T >= S_open), zero-drift lognormal, sigma_P = kappa(tau bucket) x DVOL, with
                  kappa from Phase 0 test A (reports/kappa_report.md). Test A FAILED, so kappa is a `candidate`.
  checkpoint      one universe row per market at tau = 24h, 6h, 1h, traded or not.
  arb (18)        book integrity (YES_ask + NO_ask < 1 or YES_bid + NO_bid > 1 -> pull + data fault) and log-only
                  fee-net monotonicity arbs across strikes.
  pulls (20)      before close and through the oracle gap, stale book or feed, sharp reference move, data fault.
  sizer (23)      q = m + 0.3 (f - m) around m = mid excluding our orders, with the sign/magnitude invariant.
  quotes (20)     a bid on each outcome at q -/+ half-spread (wider with uncertainty and vol), inventory skew,
                  complement bids (p + q < 1 - margin) on the outcome we don't hold.
  selector (16)   income per dollar; the top `max_markets` markets with positive income are quoted.

Wiring (WP1-F):
  - ref[asset]: "price", "ts_ms", "dvol" (Deribit DVOL in percent as published, e.g. 35.66; a fraction also works),
    "final" {ms: close}. Up/Down needs the previous 12:00 ET close, keyed by that candle's open or close time.
  - the engine returns its target resting set each tick; diff it against live orders on (token_id, side, price,
    size, expiry_ms), not on `reason`, which changes every tick.
  - call `engine.on_fill(fill)` for every fill: complement bids need our average cost, which positions don't carry.
  - optional inputs: `engine.rewards[cid] = {"min_size", "daily_rate"}` (crawler) and `engine.markouts[cid]`
    (role 22's mean 5m markout per share); defaults are no reward and `markout_prior`.
  - after each on_tick, drain `engine.records`: (table, row, event_ms) tuples for `Ledger.record`.
  - write PREREG once (`Ledger.preregister`) and the REGISTRY entries (state `candidate`).
  - Intent.reason carries "f=... m=... q=..." so the invariant suite can recheck role 23's invariant per intent.

Wiring flags (WW-C; `LadderEngine(flags=...)`, all off by default = the audited Phase 1 behaviour):
  - touch: kinds touch-up/touch-down priced by growth.touch.touch_fair (non-finite or tau <= 0 inputs -> err), plus
    the log-only touch<terminal coherence check against a same-strike digital settling inside the window.
  - quote_objective: quotes = wider(quote_objective.optimise(...), quotes(...)): the Phase 1 quotes are the anchor.
  - `engine.oracle_gap` (settlement keeper's set of cids) pulls those markets; empty by default.
  - NegRiskScanner: negRisk scan rows for the ledger table "negrisk_scan"; never returns intents.
  - exits: `engine.fair[cid]` = this tick's fair value plus the pull reason, for trader/engines/exits.py (the loop
    turns it into exit SELLs); quotes are unchanged.
"""
import datetime as dt
import math
import re
import zoneinfo
from collections import deque
from statistics import NormalDist

from trader.contracts import Book, Fill, Intent, MarketInfo

NAME = "ladder-maker"
VERSION = 2  # v2 (8 Oct): no new quotes in the last hour; 5 min quiet after a sharp move (20:48 fill, -5.84)
KAPPA = {24: 0.905, 6: 1.034, 1: 1.150}    # Phase 0 test A, all-days fit per checkpoint bucket (hours)
KAPPA_VERSION = 1
VERSIONS = ((NAME, VERSION), ("kappa", KAPPA_VERSION))
CHECKPOINTS_H = (24, 6, 1)
H_MS, MIN_MS = 3_600_000, 60_000
YEAR_H = 365 * 24                          # DVOL is annualised on a 365-day year (as in research/kappa)
SIZE_STEP = 0.01                           # share granularity; sizes are floored to it
ET = zoneinfo.ZoneInfo("America/New_York")
_N = NormalDist()

PARAMS = {
    "assets": ("BTC", "ETH"),
    "kappa": KAPPA,
    "sigma_rel_unc": 0.10,     # +/- on sigma_P for the fair's uncertainty (walk-forward kappa ranged 0.84-1.15)
    "c_shrink": 0.3,           # role 23: q = m + c (f - m), fixed until 100 event groups have resolved
    "half_min": 0.005,         # half-spread = half_min + k_unc x uncertainty + k_vol x vol (probability units)
    "k_unc": 0.5,
    "k_vol": 0.5,
    "vol_horizon_s": 60,       # vol = change of the fair for a 1-SD reference move over this horizon
    "k_skew": 0.02,            # quote centre moves by k_skew x net / max_inv
    "quote_size": 10.0,        # shares per bid
    "max_inv": 50.0,           # |YES - NO| shares per market
    "complement_margin": 0.01, # holding one outcome at p, bid the other at q < 1 - p - margin
    "max_book_width": 0.10,    # no quotes when the book (excluding our orders) is wider: its mid is no anchor
    "max_tau_h": 24.0,         # kappa is fitted at tau <= 24h only
    "pull_before_close_ms": 10 * MIN_MS,
    "quiet_before_close_ms": 60 * MIN_MS,  # v2: no quotes this close to the end (an at-the-money binary swings hardest)
    "book_stale_ms": 60_000,
    "ref_stale_ms": 5_000,
    "move_window_ms": 10_000,  # sharp move: > move_k x sigma_Q sqrt(window) within the window
    "move_k": 4.0,
    "move_cooldown_ms": 300_000,  # v2: was 60 s; on 8 Oct moves came 1-3 min apart and the bid refilled in between
    "ttl_step_ms": 5 * MIN_MS, # GTD expiry 5-10 min ahead, stable within a step; never past end - 3 min
    "max_markets": 10,
    "group_cap_usd": 10.0,     # mirror of the kernel's per-event-group cap; targets are packed to fit it
    "budget_usd": 25.0,        # mirror of the kernel's ladder-maker strategy budget
    "r_lock": 0.20,            # human-set lockup rate per year
    "settle_h": 2.0,           # tau_settle = settle_h + p_dispute x dvm_delay_h
    "p_dispute": 0.01,
    "dvm_delay_h": 72.0,
    "slippage": 0.0,           # taker slippage per share on top of the ask
    "kelly_cap": 0.25,
    "rebate_rate": 0.2,        # fee_schedule.rebateRate on every crypto-term market (crawler); not in MarketInfo
    "reward_share": 0.1,       # assumed share of a reward pool when we qualify
    "markout_prior": 0.0,      # expected 5m markout per share until role 22 measures it
    "ck_window_ms": 10 * MIN_MS,  # a checkpoint is written only within this long after tau crosses it
    "log_every_ms": 60_000,    # rate limit per key for fault, arb and sharp-move records
    "rank_log_ms": 10 * MIN_MS,
}
REGISTRY = {
    "kappa": {"version": KAPPA_VERSION, "state": "candidate", "params": KAPPA,
              "source": "reports/kappa_report.md (test A FAILED: 1.8 SE; the mid beat the model)"},
    NAME: {"version": VERSION, "state": "candidate", "params": PARAMS},
}
PREREG = {
    "test_id": f"{NAME}-v{VERSION}",
    "strategy": NAME,
    "hypothesis": "Maker bids around q = m + 0.3 (f - m) on BTC/ETH daily ladders and Up/Down earn a positive "
                  "fee-net 5m markout after adverse selection.",
    "statistic": "per fill: size x (mid_ex_own 5 min after the fill - fill price) + maker rebate + allocated reward, "
                 "summed per cluster",
    "cluster": "settlement instant (BTC and ETH daily markets settling at the same 12:00 ET print are one cluster)",
    "se": "cluster-robust standard error of the mean per cluster",
    "alpha": 0.0228,           # one-sided, z = 2
    "pass_rule": "PASS if mean > 2 SE with n >= 60 clusters",
    "pass_z": 2.0, "n": 60,
    "futility_rule": "stop (FAIL) if mean < -1 SE once n >= 30 clusters",
    "futility_z": -1.0, "futility_n": 30,
    "data": "paper fills from the strict simulator; markouts against the mid excluding our own orders",
    "params": {"name": NAME, "version": VERSION, "kappa_version": KAPPA_VERSION},
}


# ---------- pricer (10, 17) ----------

def kappa_for(tau_h: float, kappa: dict = KAPPA) -> float:
    """kappa of the nearest checkpoint bucket in log tau: 24h above 12h, 6h down to 2.45h, 1h below."""
    return kappa[min(kappa, key=lambda b: abs(math.log(tau_h / b)))]


def digital(S: float, K: float, sigma: float, tau_h: float, basis: float = 1.0) -> float:
    """P(S_T > K), zero-drift lognormal: N(d2), d2 = (ln(S / K_usd) - s^2/2) / s, s = sigma sqrt(tau).
    Basis hook: K_usd = K_usdt x basis (USD per USDT) when S is a USD index; 1.0 when S is the Binance USDT price
    itself (the resolution source), as here. Continuous, so P(> K) = P(>= K): the strict ">" only matters for labels."""
    s = sigma * math.sqrt(tau_h / YEAR_H)
    return _N.cdf((math.log(S / (K * basis)) - s * s / 2) / s)


def sigma_q(dvol: float) -> float:
    return dvol / 100 if dvol > 5 else dvol   # Deribit publishes DVOL in percent (35.66 = 35.66%)


def prev_noon_ms(end_ms: int) -> int:
    """Open time of the 12:00 ET candle on the day before end_ms: the daily Up/Down open (DST-safe)."""
    d = dt.datetime.fromtimestamp(end_ms / 1000, ET).date() - dt.timedelta(days=1)
    return int(dt.datetime.combine(d, dt.time(12), ET).timestamp() * 1000)


def fair_value(m: MarketInfo, r: dict, now_ms: int, p: dict) -> dict:
    """Fair P(YES) (Up for Up/Down) from r = ref[asset]: f, unc (half the change for sigma_P +/- sigma_rel_unc),
    vol (change of f for a 1-SD reference move over vol_horizon_s) and the inputs; "err" when it can't be priced."""
    S, dvol = r.get("price"), r.get("dvol")
    tau_h = (m.end_ms + MIN_MS - now_ms) / H_MS       # S_T = close of the 1m candle that opens at end_ms
    if not S or not dvol or tau_h <= 0:
        return {"err": "no price, dvol or time left", "tau_h": tau_h}
    K, t = m.strike, tau_h
    if m.kind == "updown":
        start = prev_noon_ms(m.end_ms)
        fin = r.get("final") or {}
        K = fin.get(start) or fin.get(start + MIN_MS)
        if now_ms < start:                            # open not printed yet: only the window's variance counts
            K, t = S, (m.end_ms - start) / H_MS
        elif K is None and now_ms < start + 2 * MIN_MS:
            K = S                                     # the open is printing now
    if not K:
        return {"err": "no strike or open", "tau_h": tau_h}
    k = kappa_for(tau_h, p["kappa"])
    sig = k * sigma_q(dvol)
    f = digital(S, K, sig, t)
    u = p["sigma_rel_unc"]
    unc = abs(digital(S, K, sig * (1 + u), t) - digital(S, K, sig * (1 - u), t)) / 2
    vol = abs(digital(S * math.exp(sig * math.sqrt(p["vol_horizon_s"] / 3600 / YEAR_H)), K, sig, t) - f)
    return {"f": f, "unc": unc, "vol": vol, "S": S, "K": K, "sigma_q": sigma_q(dvol), "kappa": k, "sigma_p": sig,
            "tau_h": tau_h, "basis": 1.0}


TOUCH_KINDS = ("touch-up", "touch-down")
QO_PARAMS = {"requote_s": 60.0}   # quote_objective horizon to the next requote (Phase 5 smoke value), candidate


def _pos(*xs) -> bool:
    return all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x > 0 for x in xs)


def touch_value(m: MarketInfo, r: dict, now_ms: int, p: dict) -> dict:
    """growth.touch.touch_fair behind the Phase 3 audit's guards (a NaN price, vol or running extreme gave f = 1.0;
    tau <= 0 is refused), plus the ladder's "vol" key (change of f for a 1-SD reference move over vol_horizon_s)."""
    from trader.growth import touch                  # lazy: touch imports this module
    up = m.kind == "touch-up"
    sq = r.get("sigma_q") or (sigma_q(r["dvol"]) if _pos(r.get("dvol")) else None)
    tau_h = (m.end_ms - now_ms) / H_MS
    if not _pos(r.get("price"), sq, r.get("high" if up else "low"), m.strike, r.get("basis") or 1.0) or tau_h <= 0:
        return {"err": "non-finite touch input or no time left", "tau_h": tau_h}
    tp = touch.REGISTRY["touch"]["params"]
    fv = touch.touch_fair(m, r, now_ms, {**tp, "kappa": {int(k): v for k, v in tp["kappa"].items()}})  # JSON keys
    if "err" in fv:
        return {**fv, "tau_h": tau_h}
    bumped = fv["S"] * math.exp(fv["sigma_p"] * math.sqrt(p["vol_horizon_s"] / 3600 / YEAR_H))
    vol = abs(touch.one_touch(bumped, m.strike, fv["sigma_p"], tau_h, up, fv["basis"], fv["touched"]) - fv["f"])
    return {**fv, "vol": vol}


def touch_flags(m: MarketInfo, fv: dict, tbook: Book, d: MarketInfo, dyes: Book, dno: Book, now_ms: int) -> list[str]:
    """Log-only coherence of a touch market against a same-strike digital d settling inside the window (its NO book
    for a down-touch). touch>2x_digital+eps needs the digital to settle at the window end, so it is kept only then."""
    from trader.growth import touch
    up, tau_h = m.kind == "touch-up", (d.end_ms + MIN_MS - now_ms) / H_MS
    if tau_h <= 0 or not _pos(fv.get("sigma_p"), fv.get("S")):
        return []                                    # coherence_flags divides by sigma sqrt(tau)
    flags = touch.coherence_flags(tbook, dyes if up else dno, fv["S"], m.strike, fv["sigma_p"], tau_h, up,
                                  touch.REGISTRY["touch"]["params"]["eps_tol"])
    return [f for f in flags if f == "touch<terminal" or d.end_ms == m.end_ms]


# ---------- integrity and arbs (18) ----------

def book_fault(yes: Book, no: Book) -> str | None:
    """Polymarket mints and merges complements, so YES_ask + NO_ask < 1 or YES_bid + NO_bid > 1 can't rest on a
    real book: the data is stale or corrupt."""
    ya, na, yb, nb = yes.best_ask(), no.best_ask(), yes.best_bid(), no.best_bid()
    if ya is not None and na is not None and ya + na < 1 - 1e-9:
        return f"asks sum {ya + na:.4f} < 1"
    if yb is not None and nb is not None and yb + nb > 1 + 1e-9:
        return f"bids sum {yb + nb:.4f} > 1"
    return None


def ladder_arbs(group: list[tuple[MarketInfo, Book, Book]], tau_h: float, p: dict) -> list[dict]:
    """Fee-net monotonicity arbs in one strike ladder (same asset and print): YES(K1) + NO(K2) with K1 < K2 pays at
    least 1, so a full taker cost below 1 is an opportunity. Log-only."""
    rows = sorted(group, key=lambda g: g[0].strike)
    out = []
    for i, (m1, y1, _) in enumerate(rows):
        for m2, _, n2 in rows[i + 1:]:
            if y1.asks and n2.asks:
                a1, a2 = y1.asks[0][0], n2.asks[0][0]
                cost = taker_cost(a1, m1.fee_rate, tau_h, p) + taker_cost(a2, m2.fee_rate, tau_h, p)
                if cost < 1:
                    out.append({"buy_yes": m1.cid, "k1": m1.strike, "ask_yes": a1, "buy_no": m2.cid, "k2": m2.strike,
                                "ask_no": a2, "edge": 1 - cost, "size": min(y1.asks[0][1], n2.asks[0][1])})
    return out


# ---------- pulls (20) ----------

def sharp_move(hist, sigma: float, p: dict) -> bool:
    """The latest price is more than move_k x sigma sqrt(window) (log) away from some price in the window."""
    if len(hist) < 2:
        return False
    thr = p["move_k"] * sigma * math.sqrt(p["move_window_ms"] / H_MS / YEAR_H)
    last = hist[-1][1]
    return max(abs(math.log(last / x)) for _, x in hist) > thr


def pull_reason(m: MarketInfo, yes: Book | None, no: Book | None, r: dict, now_ms: int, sharp_until: int,
                p: dict, oracle_gap=()) -> str | None:
    """Why this market must have no resting quotes now, or None. oracle_gap: cids printed but not resolved."""
    if now_ms >= m.end_ms - p["pull_before_close_ms"]:
        return "close"                                # before the print and through the post-close oracle gap
    if now_ms >= m.end_ms - p.get("quiet_before_close_ms", 0):
        return "near_close"
    if m.cid in oracle_gap:
        return "oracle_gap"
    if yes is None or no is None or now_ms - min(yes.ts_ms, no.ts_ms) > p["book_stale_ms"]:
        return "stale_book"
    if r.get("ts_ms") is None or now_ms - r["ts_ms"] > p["ref_stale_ms"]:
        return "stale_feed"
    if now_ms < sharp_until:
        return "sharp_move"
    if book_fault(yes, no):
        return "book_integrity"
    return None


# ---------- sizer (23) ----------

def shrink(f: float, m: float, c: float = 0.3) -> float:
    return m + c * (f - m)


def invariant_ok(q: float, f: float, m: float) -> bool:
    """sign(q - m) = sign(f - m) and |q - m| <= |f - m| (False on NaN)."""
    sgn = lambda x: (x > 0) - (x < 0)
    return sgn(q - m) == sgn(f - m) and abs(q - m) <= abs(f - m)


def floor_to(x: float, step: float) -> float:
    """Largest multiple of step that is <= x: never rounds up, also under float error."""
    y = round(math.floor(x / step + 1e-9) * step, 10)
    return y if y <= x else round(y - step, 10)


def settle_h(p: dict) -> float:
    return p["settle_h"] + p["p_dispute"] * p["dvm_delay_h"]


def taker_cost(ask: float, fee_rate: float, tau_h: float, p: dict) -> float:
    """Full cost per share of taking at ask: price + fee + slippage + lockup at r_lock until settlement."""
    return ask + fee_rate * ask * (1 - ask) + p["slippage"] + ask * p["r_lock"] * (tau_h + settle_h(p)) / YEAR_H


def kelly(q: float, cost: float, cap: float = 0.25) -> float:
    """Kelly fraction for buying a binary that pays 1 at `cost` with probability q, capped."""
    return 0.0 if q <= cost or cost >= 1 else min(cap, (q - cost) / (1 - cost))


def group_cap(fracs: list[float]) -> list[float]:
    """Within one settlement group the taker fractions sum to at most the largest single fraction."""
    s, top = sum(fracs), max(fracs, default=0.0)
    return list(fracs) if s <= top else [x * top / s for x in fracs]


def taker_shares(frac: float, bankroll: float, cost: float, available: float, min_size: float) -> float:
    """Shares for a taker order: floored, never above what is on offer, 0 (refused) below the minimum size."""
    n = floor_to(min(frac * bankroll / cost, available), SIZE_STEP)
    return n if n >= min_size else 0.0


# ---------- quotes (20) ----------

def quotes(q: float, half: float, net: float, cost: dict, m: MarketInfo, asks: tuple, p: dict) -> list[tuple]:
    """Target bids [(token, price, size, reduces_exposure)] around q. net = YES - NO shares held; cost = {token: avg
    cost}; asks = best (YES, NO) asks. Holding >= min_size of one outcome, the bid on the other is a complement bid:
    it pairs off what we hold (merged at a locked 1 - p - q) and is priced strictly below 1 - p - margin."""
    centre = q - p["k_skew"] * net / p["max_inv"]
    out = []
    for token, px, own, other, ask in ((m.token_yes, centre - half, net, m.token_no, asks[0]),
                                       (m.token_no, 1 - centre - half, -net, m.token_yes, asks[1])):
        held_other = -own
        complement = held_other >= m.min_size
        if complement and other not in cost:
            continue                                  # unknown cost of what we hold: no complement bid
        size = min(p["quote_size"], held_other if complement else p["max_inv"] - own)
        if ask is not None:
            px = min(px, ask - m.tick_size)           # post-only: never cross
        px = min(floor_to(px, m.tick_size), 1 - m.tick_size)
        if complement:
            cap = 1 - cost[other] - p["complement_margin"]
            px = floor_to(min(px, cap), m.tick_size)
            if px >= cap - 1e-12:
                px = round(px - m.tick_size, 10)      # strictly below the cap
        size = floor_to(size, SIZE_STEP)
        if px >= m.tick_size and size >= m.min_size:
            out.append((token, px, size, complement))
    return out


def objective_quotes(m: MarketInfo, fv: dict, q: float, mid: float, yes: Book, asks: tuple, net: float, cost: dict,
                     anchor: list[tuple], now_ms: int, p: dict, qo: dict) -> list[tuple]:
    """Phase 5 quote objective, passed through wider(objective, anchor) with Phase 1's quotes() as the anchor: per
    token the lower price and smaller size, and a token only one of them quotes is dropped."""
    from learning import quote_objective as QO     # lazy: quote_objective imports this module (and numpy/scipy)
    tau = min(qo["requote_s"], (m.end_ms - p["pull_before_close_ms"] - now_ms) / 1000)
    sigma = fv["vol"] / math.sqrt(p["vol_horizon_s"])  # ponytail: model-implied mid vol; realised mid vol once recorded
    rw = qo.get("reward")
    if not (tau > 0 and math.isfinite(sigma)):
        return []
    opt, _ = QO.optimise(m, q, mid, asks, net, cost, QO.PRIOR, sigma, tau, rw,
                         QO.q_others(yes, mid, rw["max_spread"]) if rw else 0.0,
                         {**{k: p[k] for k in ("rebate_rate", "max_inv", "complement_margin")},
                          "size_step": p["quote_size"]})  # 1-share steps take ~0.25 s per market; wider() caps size
    return QO.wider(opt, anchor)


def market_intents(m: MarketInfo, fv: dict, yes: Book, no: Book, positions: dict, cost: dict, now_ms: int,
                   p: dict, versions=VERSIONS, qo: dict | None = None) -> tuple[list[Intent], str | None]:
    """Shrink toward the mid excluding our orders, check role 23's invariant, quote and size one market. qo (flag
    quote_objective): {"requote_s", "reward": {min_size, max_spread, daily_rate} | None} switches the quoter."""
    mid = yes.mid_ex_own()
    if mid is None or 2 * (yes.best_ask() - mid) > p["max_book_width"]:
        return [], "no usable mid"
    q = shrink(fv["f"], mid, p["c_shrink"])
    if not invariant_ok(q, fv["f"], mid):
        return [], "invariant"
    net = positions.get(m.token_yes, 0.0) - positions.get(m.token_no, 0.0)
    half = p["half_min"] + p["k_unc"] * fv["unc"] + p["k_vol"] * fv["vol"]
    expiry = min((now_ms // p["ttl_step_ms"] + 2) * p["ttl_step_ms"], m.end_ms - 3 * MIN_MS)
    asks = (yes.best_ask(), no.best_ask())
    qs = quotes(q, half, net, cost, m, asks, p)
    if qo is not None:
        qs = objective_quotes(m, fv, q, mid, yes, asks, net, cost, qs, now_ms, p, qo)
    out = []
    for token, px, size, reduces in qs:
        f, mm, qq = (fv["f"], mid, q) if token == m.token_yes else (1 - fv["f"], 1 - mid, 1 - q)
        out.append(Intent(NAME, m.cid, token, "BUY", px, size, "maker", expiry, qq,
                          f"{'complement' if reduces else 'quote'} f={f} m={mm} q={qq} half={half:.4f} net={net:g}",
                          versions, reduces))
    return out, None


_REASON = re.compile(r"f=(\S+) m=(\S+) q=(\S+)")


def reason_fmq(reason: str) -> tuple[float, float, float]:
    """(f, m, q) from an intent's reason, for invariant checks downstream."""
    return tuple(float(x) for x in _REASON.search(reason).groups())


# ---------- selector (16) ----------

def income_per_dollar(bids: list[tuple[float, float]], fee_rate: float, tau_h: float, size: float,
                      reward: dict | None, markout: float, p: dict) -> float:
    """(spread + reward share + rebate - markout - lockup) / capital over our bids [(fair, price)]. The reward term is
    0 below the market's minimum reward size."""
    # ponytail: reward per share assumes one turnover of the quoted size per day; fit from role 22 once pools exist
    rw = reward["daily_rate"] * p["reward_share"] / size if reward and size >= reward["min_size"] else 0.0
    lock = p["r_lock"] * (tau_h + settle_h(p)) / YEAR_H
    num = sum(f - px + p["rebate_rate"] * fee_rate * px * (1 - px) - markout - px * lock for f, px in bids)
    return (num + rw) / sum(px for _, px in bids)


def fit_to_caps(intents: list[Intent], markets: dict[str, MarketInfo], books: dict[str, Book],
                positions: dict[str, float], p: dict) -> list[Intent]:
    """Keep the ranked targets that fit the kernel's room: per event group (group_cap_usd) and for the strategy
    (budget_usd), after what is already held (at best bid; no bid = 1.0, as the kernel counts it). Exposure-reducing
    bids always pass (the kernel does not cap them). Mirrors RiskKernel.check so the kernel is not asked to reject
    targets it is certain to reject."""
    by_tok = {t: m for m in markets.values() if m.mode == "crypto-term" for t in (m.token_yes, m.token_no)}
    used: dict[str, float] = {}
    total = 0.0
    for tok, n in positions.items():
        m = by_tok.get(tok)
        if n > 0 and m:
            b = books.get(tok)
            v = n * (b.best_bid() if b and b.best_bid() is not None else 1.0)
            used[m.event_group] = used.get(m.event_group, 0.0) + v
            total += v
    out = []
    for i in intents:
        if i.reduces_exposure:
            out.append(i)
            continue
        g, need = markets[i.cid].event_group, i.price * i.size
        if used.get(g, 0.0) + need <= p["group_cap_usd"] + 1e-9 and total + need <= p["budget_usd"] + 1e-9:
            used[g] = used.get(g, 0.0) + need
            total += need
            out.append(i)
    return out


def rank(cands: list[dict]) -> list[dict]:
    """Best income per dollar first; ties go to the shorter-dated market."""
    return sorted(cands, key=lambda c: (-c["income"], c["end_ms"], c["cid"]))


# ---------- engine ----------

class LadderEngine:
    name = NAME

    def __init__(self, params: dict | None = None, versions=VERSIONS, flags=()):
        self.p = {**PARAMS, **(params or {})}
        self.versions = versions
        self.flags = frozenset(flags)                    # feature flags read here: "touch", "quote_objective", "exits"
        self.fair: dict[str, dict] = {}                  # flag exits: cid -> this tick's fair value and pull reason
        self.oracle_gap: set[str] = set()                # cids printed but not resolved (settlement keeper)
        self.records: list[tuple[str, dict, int]] = []  # (table, row, event_ms) for Ledger.record; drained by the loop
        self.rewards: dict[str, dict] = {}
        self.markouts: dict[str, float] = {}
        self.cost: dict[str, tuple[float, float]] = {}  # token -> (shares, avg cost) of our buys
        self._hist: dict[str, deque] = {}                # asset -> [(ts_ms, price)] over the sharp-move window
        self._sharp_until: dict[str, int] = {}
        self._ck: set = set()                            # (cid, bucket) checkpoints written
        self._last_log: dict = {}

    def on_fill(self, fill: Fill) -> None:
        if fill.strategy == NAME and fill.side == "BUY" and fill.size > 0:
            n, c = self.cost.get(fill.token_id, (0.0, 0.0))
            self.cost[fill.token_id] = (n + fill.size, (n * c + fill.size * fill.price) / (n + fill.size))

    def on_tick(self, now_ms: int, markets: dict[str, MarketInfo], books: dict[str, Book], ref: dict,
                positions: dict[str, float]) -> list[Intent]:
        p = self.p
        for t, (n, c) in list(self.cost.items()):        # merges and redemptions shrink positions without fills
            held = positions.get(t, 0.0)
            if held <= 1e-9:
                del self.cost[t]
            elif held < n:
                self.cost[t] = (held, c)
        for asset in p["assets"]:
            self._on_ref(asset, ref.get(asset) or {}, now_ms)
        cost = {t: c for t, (_, c) in self.cost.items()}
        if "exits" in self.flags:
            self.fair = {}
        kinds = ("strike", "updown") + (TOUCH_KINDS if "touch" in self.flags else ())
        cands, ladders, touches = [], {}, []
        for m in markets.values():
            if m.mode != "crypto-term" or m.asset not in p["assets"] or m.kind not in kinds or now_ms >= m.end_ms:
                continue
            r, yes, no = ref.get(m.asset) or {}, books.get(m.token_yes), books.get(m.token_no)
            is_touch = m.kind in TOUCH_KINDS
            # touch windows need their own running high/low (marketdata keeps it in ref[asset]["touch"][cid])
            rt = {**r, **(r.get("touch") or {}).get(m.cid, {})} if is_touch else r
            fv = touch_value(m, rt, now_ms, p) if is_touch else fair_value(m, r, now_ms, p)
            self._checkpoint(m, fv, yes, now_ms)
            if yes is None or no is None:
                continue
            if "exits" in self.flags and "err" not in fv:
                self.fair[m.cid] = {**fv, "pull": pull_reason(m, yes, no, r, now_ms, self._sharp_until.get(m.asset, 0),
                                                              p, self.oracle_gap)}
            if m.kind == "strike":
                ladders.setdefault((m.asset, m.end_ms), []).append((m, yes, no))
            if is_touch and "err" not in fv:
                touches.append((m, fv, yes))
            fault = book_fault(yes, no)
            if fault:
                self._log("data_fault", ("book", m.cid), {"cid": m.cid, "kind": "book_integrity", "detail": fault}, now_ms)
            if "err" in fv or fv["tau_h"] > p["max_tau_h"] or \
                    pull_reason(m, yes, no, r, now_ms, self._sharp_until.get(m.asset, 0), p, self.oracle_gap):
                continue
            qo = None
            if "quote_objective" in self.flags:
                rw = self.rewards.get(m.cid) or {}
                qo = {**QO_PARAMS, "reward": rw if _pos(rw.get("min_size"), rw.get("max_spread"),
                                                        rw.get("daily_rate")) else None}
            versions = self.versions + ((("touch", 1),) if is_touch else ())
            intents, err = market_intents(m, fv, yes, no, positions, cost, now_ms, p, versions, qo)
            if err == "invariant":
                self._log("data_fault", ("invariant", m.cid), {"cid": m.cid, "kind": "sizer_invariant",
                                                               "f": fv["f"], "mid": yes.mid_ex_own()}, now_ms)
            if intents:
                c = {"cid": m.cid, "asset": m.asset, "kind": m.kind, "strike": m.strike, "end_ms": m.end_ms,
                     "f": fv["f"], "tau_h": fv["tau_h"], "bids": [(i.fair, i.price) for i in intents],
                     "size": min(i.size for i in intents), "fee_rate": m.fee_rate, "reward": self.rewards.get(m.cid),
                     "markout": self.markouts.get(m.cid, p["markout_prior"])}
                c["income"] = income_per_dollar(c["bids"], m.fee_rate, c["tau_h"], c["size"], c["reward"],
                                                c["markout"], p)
                cands.append({**c, "intents": intents})
        ranked = rank(cands)
        chosen = [c for c in ranked if c["income"] > 0][:p["max_markets"]]
        if ranked:
            self._log("selector_ranking", "rank", {
                "chosen": [c["cid"] for c in chosen],
                "ranking": [{k: v for k, v in c.items() if k != "intents"} for c in ranked]}, now_ms, p["rank_log_ms"])
        for (asset, end_ms), group in ladders.items():
            for a in ladder_arbs(group, (end_ms + MIN_MS - now_ms) / H_MS, p):
                self._log("arb_opportunity", (a["buy_yes"], a["buy_no"]), {"asset": asset, "end_ms": end_ms, **a}, now_ms)
        for m, fv, tb in touches:
            for d in markets.values():
                dy, dn = books.get(d.token_yes), books.get(d.token_no)
                if d.kind == "strike" and d.asset == m.asset and d.strike == m.strike and \
                        now_ms < d.end_ms <= m.end_ms and dy and dn:
                    for flag in touch_flags(m, fv, tb, d, dy, dn, now_ms):
                        self._log("arb_opportunity", ("touch", m.cid, d.cid, flag),
                                  {"kind": flag, "touch": m.cid, "digital": d.cid, "asset": m.asset, "H": m.strike,
                                   "f": fv["f"]}, now_ms)
        return fit_to_caps([i for c in chosen for i in c["intents"]], markets, books, positions, p)

    def _on_ref(self, asset: str, r: dict, now_ms: int) -> None:
        if r.get("price") is None or r.get("ts_ms") is None:
            return
        h = self._hist.setdefault(asset, deque())
        if h and r["ts_ms"] <= h[-1][0]:
            return                                       # same or older tick (on_tick also runs on book updates)
        h.append((r["ts_ms"], r["price"]))
        while h[0][0] < r["ts_ms"] - self.p["move_window_ms"]:
            h.popleft()
        if r.get("dvol") and sharp_move(h, sigma_q(r["dvol"]), self.p):
            self._sharp_until[asset] = now_ms + self.p["move_cooldown_ms"]
            self._log("sharp_move", asset, {"asset": asset, "price": r["price"], "window": list(h)}, now_ms)

    def _checkpoint(self, m: MarketInfo, fv: dict, yes: Book | None, now_ms: int) -> None:
        tau_h = fv["tau_h"]
        for b in CHECKPOINTS_H:
            if b - self.p["ck_window_ms"] / H_MS < tau_h <= b and (m.cid, b) not in self._ck:
                self._ck.add((m.cid, b))
                self.records.append(("universe_checkpoint", {
                    "id": f"{m.cid}:{b}", "cid": m.cid, "bucket_h": b, "asset": m.asset, "kind": m.kind,
                    "strike": m.strike, "end_ms": m.end_ms, "event_group": m.event_group,
                    "cluster": f"crypto-term@{m.end_ms}", "mid_ex_own": yes.mid_ex_own() if yes else None,
                    "fair": fv.get("f"), **{k: fv.get(k) for k in ("unc", "S", "K", "sigma_q", "kappa", "sigma_p",
                                                                     "basis", "tau_h", "err")},
                    **({"H": fv.get("H"), "kappa_unfitted": fv.get("kappa_unfitted")} if m.kind in TOUCH_KINDS else {}),
                    "versions": [list(v) for v in self.versions]}, now_ms))

    def _log(self, table: str, key, row: dict, now_ms: int, every: int | None = None) -> None:
        if now_ms - self._last_log.get((table, key), -math.inf) >= (every or self.p["log_every_ms"]):
            self._last_log[(table, key)] = now_ms
            self.records.append((table, row, now_ms))


# ---------- negRisk scan adapter (18; flag negrisk_scan): log rows only ----------

class NegRiskScanner:
    """growth.negrisk events from crawler rows; scan() returns one ("negrisk_scan", row, now_ms) record per event for
    Ledger.record and never an intent (the executor stays behind its closed evidence gate). Eligibility needs a signed
    exactly-one-YES confirmation and its secret: without either, every row is ineligible (fail closed)."""

    def __init__(self):
        self.events: dict = {}
        self.delay_ms: dict[str, float] = {}

    def on_snapshot(self, rows: list[dict]) -> None:
        from trader.growth import negrisk                # lazy: negrisk imports this module
        groups: dict[str, list[dict]] = {}
        for r in rows:
            if r.get("neg_risk") is True and r.get("event_slug"):
                groups.setdefault(r["event_slug"], []).append(r)
        self.events = {eid: e for eid, rs in groups.items() if (e := negrisk.event_from_rows(eid, rs))}
        self.delay_ms = {eid: 1000 * max((r.get("seconds_delay") or 0) for r in groups[eid]) for eid in self.events}

    def scan(self, books: dict[str, Book], now_ms: int, rtt_ms: float, feed_fresh: bool, confirmations=(),
             secret: str | None = None) -> list[tuple[str, dict, int]]:
        if not feed_fresh:
            return []
        from trader.growth import negrisk
        out = []
        for eid, e in self.events.items():
            key = negrisk.confirmation_key(e)
            conf = next((c for c in confirmations if isinstance(c, dict) and c.get("key") == key), None)
            ok = negrisk.eligible(e, conf, now_ms, secret) if secret else (False, "no confirmation secret")
            out.append(("negrisk_scan", negrisk.scan(e, books, now_ms, rtt_ms + self.delay_ms[eid], ok,
                                                     negrisk.PARAMS), now_ms))
        return out
