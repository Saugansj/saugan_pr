"""Live-micro kernel and breaker additions (WP2-C; build-plan 2.4 except the clock gate, 2.5; roles 01 and 02).

Pure functions and small classes, no I/O. They run after trader.kernel.RiskKernel.check approves an intent and add the
caps Phase 1 lacks, fed the same worst case (every non-terminal order counted as filled, `unknown` in full):
  worst_case_positions  positions + the remaining size of every live BUY
  stress_check          cross-instant stress cap: BTC/ETH/SOL shocked together by -10/-5/+5/+10% with vol x1.5;
                        the worst loss must stay <= 5% of bankroll
  resolution_check      post-close exposure in printed, unsettled markets <= 10% of bankroll per market, 20% in total
  check_live            stress, then resolution, on risk-increasing intents; reducing intents pass straight through
  SevenDayDrawdown      rolling 7-day drawdown > 10% -> global REDUCING until a human reset (RiskKernel.reset)
  pull_ids              the risk-increasing live orders to cancel when a scope enters REDUCING
  reducing_rule         REDUCING exits are makers priced at fair -/+ fee; a taker exit needs a token or a group over cap
Every comparison is written so a NaN input rejects.
"""
import math
from collections import deque
from types import SimpleNamespace

from trader.contracts import Decision, Intent, MarketInfo, TradingState
from trader.engines.ladder import digital, sigma_q
from trader.fees import fee
from trader.kernel import LIVE, RiskKernel

R = TradingState.REDUCING
ASSETS = ("BTC", "ETH", "SOL")          # shocked together in every scenario
SHOCKS = (-0.10, -0.05, 0.05, 0.10)     # spot moves
VOL_UP = 1.5                            # sigma x 1.5 in every scenario
STRESS_LIMIT = 0.05                     # worst loss <= 5% of bankroll
H_MS = 3_600_000
WEEK_MS = 7 * 86_400_000
EPS = 1e-9


def worst_case_positions(positions: dict[str, float], orders) -> dict[str, float]:
    """Positions + the remaining size of every non-terminal BUY (`unknown` counts its full size). SELLs never reduce
    it. `orders`: router.open_orders(), or a replayed trader.router.State's `orders` dict."""
    out = dict(positions)
    for o in (orders.values() if isinstance(orders, dict) else orders):
        if o.status in LIVE and o.intent.side == "BUY":
            out[o.intent.token_id] = out.get(o.intent.token_id, 0.0) + o.intent.size - (
                0.0 if o.status == "unknown" else o.filled)
    return out


def _with(intent: Intent, worst_positions: dict[str, float]) -> dict[str, float]:
    """The worst case with a BUY intent counted as filled."""
    out = dict(worst_positions)
    if intent.side == "BUY":
        out[intent.token_id] = out.get(intent.token_id, 0.0) + intent.size
    return out


def _reduces(intent: Intent, m: MarketInfo, positions: dict[str, float], orders) -> bool:
    """RiskKernel.reduces (it reads no instance state), so live and paper judge 'reduces exposure' the same way."""
    return RiskKernel.reduces(None, intent, m, SimpleNamespace(positions=positions, open_orders=list(orders)))


# ---- cross-instant stress cap ----------------------------------------------------------------------------------------
def _yes(m: MarketInfo, S, sigma, tau_h: float, opens: dict) -> float | None:
    """Model P(YES): strike -> digital(S, strike), Up/Down -> digital(S, open). None when it can't be priced."""
    K = m.strike if m.kind == "strike" else opens.get(m.cid) if m.kind == "updown" else None
    if not K or not S or not sigma or tau_h <= 0:
        return None
    try:
        return digital(S, K, sigma, tau_h)
    except (ValueError, ZeroDivisionError):  # non-positive spot or strike
        return None


def stress_loss(worst_positions: dict[str, float], markets: dict[str, MarketInfo], ref: dict, opens: dict,
                now_ms: int, printed) -> tuple[float, str]:
    """(worst loss in USD, scenario). Loss = sum of shares x (p_now - p_shocked), both from the same pricer, so model
    error cancels. A crypto position that can't be priced (no strike/open/sigma/ref, an asset outside ASSETS, or
    tau <= 0) loses its whole value in every scenario; with no model price that value is taken as 1.0 per share
    (fail closed). Non-crypto markets and markets in `printed` are left to resolution_check.
    ponytail: tokens missing from `markets` are skipped, as in RiskKernel.exposure (no mode to tell crypto from not)."""
    by_tok = {t: (m, t == m.token_yes) for m in markets.values() for t in (m.token_yes, m.token_no)}
    loss = dict.fromkeys(SHOCKS, 0.0)
    for tok, shares in worst_positions.items():
        if tok not in by_tok or shares == 0:
            continue
        m, is_yes = by_tok[tok]
        if not m.mode.startswith("crypto") or m.cid in printed:
            continue
        r = (ref.get(m.asset) if m.asset in ASSETS else None) or {}
        S, dvol = r.get("price"), r.get("dvol")
        sig = sigma_q(dvol) if dvol else None
        tau = (m.end_ms - now_ms) / H_MS
        p0 = _yes(m, S, sig, tau, opens)
        for s in SHOCKS:
            if p0 is None:
                loss[s] += shares * 1.0
            else:
                p1 = _yes(m, S * (1 + s), sig * VOL_UP, tau, opens)
                loss[s] += shares * ((p0 - p1) if is_yes else (p1 - p0))  # NO = 1 - YES
    if any(math.isnan(v) for v in loss.values()):
        return math.nan, "NaN input"
    s = max(SHOCKS, key=loss.get)
    return loss[s], f"{s:+.0%} BTC/ETH/SOL, vol x{VOL_UP}"


def _stress(intent, worst_positions, markets, ref, opens, now_ms, printed, bankroll, limit=STRESS_LIMIT):
    loss, scen = stress_loss(_with(intent, worst_positions), markets, ref, opens, now_ms, printed)
    room = limit * bankroll - loss
    if not (room >= 0 and 0 < intent.price < 1 and intent.size > 0):  # written so NaN rejects
        return Decision(False, f"stress: worst loss {loss:.2f} ({scen}) > {limit:.0%} of bankroll {bankroll:.2f}",
                        "stress"), room
    return Decision(True, f"stress: worst loss {loss:.2f} ({scen}), room {room:.2f}", "stress"), room


def stress_check(intent: Intent, worst_positions: dict[str, float], markets: dict[str, MarketInfo], ref: dict,
                 opens: dict, now_ms: int, printed, bankroll: float, limit: float = STRESS_LIMIT) -> Decision:
    """Reject when the worst stress loss, with a BUY intent counted as filled, is > limit x bankroll."""
    return _stress(intent, worst_positions, markets, ref, opens, now_ms, printed, bankroll, limit)[0]


# ---- resolution-risk cap ---------------------------------------------------------------------------------------------
def _resolution(intent, worst_positions, markets, books, bankroll, printed, per_market=0.10, total=0.20):
    if intent.cid not in printed:
        return Decision(True, "resolution: market has not printed"), math.inf
    pos = _with(intent, worst_positions)

    def exposure(cid):  # shares x best bid; no book or no bid = 1.0
        m = markets.get(cid)
        if m is None:
            return 0.0
        out = 0.0
        for t in (m.token_yes, m.token_no):
            b = books.get(t)
            bid = b.best_bid() if b else None
            out += pos.get(t, 0.0) * (1.0 if bid is None else bid)
        return out

    rooms = {f"resolution:{intent.cid}": per_market * bankroll - exposure(intent.cid),
             "resolution:total": total * bankroll - sum(exposure(c) for c in set(printed))}
    for cap, room in rooms.items():
        if not room >= 0:  # written so NaN rejects
            return Decision(False, f"over {cap}: room {room:.2f} (bankroll {bankroll:.2f})", cap), room
    cap = min(rooms, key=rooms.get)
    return Decision(True, f"within {cap}, room {rooms[cap]:.2f}", cap), rooms[cap]


def resolution_check(intent: Intent, worst_positions: dict[str, float], markets: dict[str, MarketInfo], books: dict,
                     bankroll: float, printed, per_market: float = 0.10, total: float = 0.20) -> Decision:
    """For intents on printed, unsettled markets: exposure (shares x best bid, 1.0 with no bid) in that market
    <= per_market x bankroll and across all printed markets <= total x bankroll, with a BUY intent counted as filled.
    Markets that have not printed pass."""
    return _resolution(intent, worst_positions, markets, books, bankroll, printed, per_market, total)[0]


def check_live(intent: Intent, ctx, worst_positions: dict[str, float], ref: dict, opens: dict, printed) -> Decision:
    """After RiskKernel.check approves: stress, then resolution, on risk-increasing intents. Returns the first
    rejection, or an approval naming the tightest cap. Reducing intents (RiskKernel's rule) pass straight through."""
    m = ctx.markets.get(intent.cid)
    if m is None:
        return Decision(False, "unknown market")
    if _reduces(intent, m, ctx.positions, ctx.open_orders):
        return Decision(True, "reduces exposure")
    best = None
    for run in (lambda: _stress(intent, worst_positions, ctx.markets, ref, opens, ctx.now_ms, printed, ctx.bankroll_usd),
                lambda: _resolution(intent, worst_positions, ctx.markets, ctx.books, ctx.bankroll_usd, printed)):
        d, room = run()
        if not d.approved:
            return d
        if best is None or room < best[1]:
            best = (d, room)
    return Decision(True, f"live caps pass (tightest {best[0].reason})", best[0].binding_cap)


# ---- 7-day drawdown breaker ------------------------------------------------------------------------------------------
class SevenDayDrawdown:
    """(window max - equity) / window max > limit over the last 7 days -> kernel.trip("global", ..., REDUCING) once;
    the window then re-arms from the trip equity, so the same loss doesn't undo a human reset. Equity is
    trader.kernel.bankroll (pUSD + positions at best bid). The window keeps only samples that can still be its max
    (a sliding-window maximum), so samples() is small and rebuilding from it gives the same decisions."""

    def __init__(self, kernel, limit: float = 0.10, samples=()):
        self.k, self.limit = kernel, limit
        self._w: deque[tuple[int, float]] = deque()
        for ts, eq in samples:
            self._push(int(ts), float(eq))

    def _push(self, ts: int, equity: float) -> None:
        while self._w and self._w[0][0] < ts - WEEK_MS:
            self._w.popleft()
        while self._w and self._w[-1][1] <= equity:
            self._w.pop()
        self._w.append((ts, equity))

    def on_equity(self, equity: float, now_ms: int) -> None:
        if not math.isfinite(equity):  # a NaN max would blind the window for 7 days; a bad mark is skipped instead
            return
        self._push(now_ms, equity)
        hi = self._w[0][1]
        dd = (hi - equity) / hi if hi > 0 else 0.0
        if dd > self.limit:
            self.k.trip("global", f"7-day drawdown {dd:.1%} > {self.limit:.0%} (7-day high {hi:.2f})",
                        "breaker:drawdown7d", R)
            self._w.clear()
            self._w.append((now_ms, equity))

    def samples(self) -> list[tuple[int, float]]:
        return list(self._w)


# ---- pull and REDUCING rules (2.5) -----------------------------------------------------------------------------------
def pull_ids(open_orders, positions: dict[str, float], markets: dict[str, MarketInfo], cids) -> list[str]:
    """Ids of the non-terminal orders in `cids` that increase risk: every BUY except a complement BUY covered by held
    shares net of the other live orders (RiskKernel.reduces). SELLs stay. An order on an unknown market is pulled.
    ponytail: each covered BUY is netted against all other live orders, so two that only fit one at a time are both
    pulled (cautious); net in creation order if that pulls legitimate complement bids too often."""
    live = [o for o in open_orders if o.status in LIVE]
    out = []
    for o in live:
        if o.intent.cid not in cids or o.intent.side == "SELL":
            continue
        m = markets.get(o.intent.cid)
        if m is None or not _reduces(o.intent, m, positions, [x for x in live if x is not o]):
            out.append(o.order_id)
    return out


def reducing_rule(intent: Intent, fee_rate: float, group_over_cap: bool, human_token_ok: bool) -> str | None:
    """Why a reducing intent is refused in REDUCING, or None. Makers only: a SELL at >= fair - fee per share, a
    complement BUY at <= fair + fee per share. A taker exit needs a valid human token or its group over its cap."""
    if intent.kind == "taker":
        return None if human_token_ok or group_over_cap else \
            "REDUCING: a taker exit needs a human token or its group over its cap"
    try:
        f = fee(1.0, intent.price, fee_rate)
    except ValueError:
        return f"REDUCING: bad price {intent.price!r} or fee rate {fee_rate!r}"
    if intent.side == "SELL":
        if not intent.price >= intent.fair - f - EPS:
            return f"REDUCING: maker SELL at {intent.price} below fair - fee {intent.fair - f:.4f}"
    elif not intent.price <= intent.fair + f + EPS:
        return f"REDUCING: complement BUY at {intent.price} above fair + fee {intent.fair + f:.4f}"
    return None
