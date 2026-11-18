"""fast-updown-maker engine (Phase 3, WP3-D; build-plan 3.5; roles 17, 20, 23). Pure decisions, no I/O; unwired.

Maker-first quotes on crypto-fast 5m / 15m / 4h Up/Down markets ("Up" if the Chainlink 60 s TWAP close >= the open),
for assets whose own E6 latency stats pass the pre-registered rule (latency_gate). With no passing asset the engine
emits nothing. The Phase 0 free-data PASS (reports/latency_test.md) does not count and is never read.

Per tick, for each open window of a passing asset (window start = end - duration, duration from event_group):
  open     the reference's trailing twap_w_s average ending at the window start (16 Oct: Polymarket's priceToBeat is
           the Chainlink 60 s TWAP at the start, not a point price; a trailing mean of spot reproduced it to ~$1),
           recorded in _on_ref when a tick crosses the boundary (within open_tol_ms), so a market seen late still
           gets its own open. The USD/USDT basis cancels: the open
           and x share a feed. Start and close are both shifted settle_offset_ms earlier: the Chainlink TWAP series
           lines up with Bybit/Binance spot 3-4 s early.
  fair     f = twap_up(open, x, realised_avg, tau_s, kappa_fast x sigma_Q x x / sqrt(seconds per year)).
  shrink   q = ladder.shrink(f, mid_ex_own(Up), c_shrink), checked with ladder.invariant_ok.
  pulls    ladder.pull_reason: close, stale book, stale feed, sharp move, book integrity. Pulled = no maker, no taker.
  maker    post-only bids on Up at <= q - half and on Down at <= 1 - q - half, floored to the tick, size = min_size,
           held + in-flight taker + bid <= max_shares; GTD expiry in [now + 2 min + gtd_margin_ms, end - 2 min] or none.
  taker    only if the asset's E6 measured edge > 0 and q_token - ask - fee(1, ask, rate) - slippage > min_edge;
           size min_size, give-up deadline now + give_up_ms, one per market at a time; it uses max_shares room first.

Up/Down tokens: token_yes = "Up", token_no = "Down" (crawler order, as trader.engines.speed notes).

Wiring later (nothing is wired here):
  - write LATENCY_PREREG and FAST_PREREG once (Ledger.preregister) before the E6 data is analysed; REGISTRY (candidate).
  - role 22 or 35 writes the one E6 row: Ledger.record("test_results", {test: "latency-e6-v1", n, mean, se,
    cap_usd, evidence, by_asset: {asset: {n, mean, se}}}, event_ms).
  - engine = FastUpDownMaker(latency_gate(ledger, now), edges=e6_edges(ledger, now)); STRATEGIES gains
    fast-updown-maker with a canary-sized budget. ref[asset] needs price, ts_ms and dvol (or a precomputed sigma_q).
  - kernel.starts must stay unset for crypto-fast markets, or the start - 5 min GTD bound refuses every maker order.
  - kernel gtd_margin_ms must stay <= this module's gtd_margin_ms (30 s vs 45 s by default: 15 s of loop slack).
"""
import math
import re
from collections import deque
from statistics import NormalDist

from trader.contracts import Book, Intent, MarketInfo
from trader.engines.ladder import (MIN_MS, YEAR_H, book_fault, floor_to, invariant_ok, pull_reason, sharp_move,
                                   shrink, sigma_q)
from trader.fees import fee
from trader.growth import capital

NAME = "fast-updown-maker"
VERSION = 2                      # 16 Oct: open = trailing TWAP, settle_offset_ms
MAX_SHARES = 5.0                 # hard cap per token held + bid, whatever the params say
TAKER_DELAY_MS = 150             # Phase 0 / E6 taker delay
SEC_PER_YEAR = YEAR_H * 3600
_N = NormalDist()

PARAMS = {
    "kappa_fast": 1.0,           # sigma_P = kappa_fast x sigma_Q; candidate, unfitted
    "twap_w_s": 60,              # Chainlink TWAP window (s)
    "c_shrink": 0.3,             # role 23
    "half": 0.02,                # maker half-spread (probability)
    "max_shares": MAX_SHARES,
    "max_book_width": 0.10,      # no quotes when the book (ex own) is wider: its mid is no anchor
    "min_edge": 0.02,            # taker: fee-net edge per share at the ask must exceed this
    "slippage": 0.005,           # taker slippage per share
    "give_up_ms": 2000,          # taker deadline after decision
    "open_tol_ms": 2000,         # the open must be a tick within this long after the window start
    "settle_offset_ms": 4000,    # Chainlink TWAP vs exchange spot: the settlement window ends ~4 s before the close
    "gtd_margin_ms": 45_000,     # >= the kernel's GTD margin (30 s) plus loop slack
    "ttl_step_ms": MIN_MS,       # maker expiry rounded up to this step (stable across ticks)
    "pull_before_close_ms": MIN_MS,
    "book_stale_ms": 5000,
    "ref_stale_ms": 2000,
    "move_window_ms": 10_000,    # sharp move: > move_k x sigma_Q sqrt(window) within the window
    "move_k": 4.0,
    "move_cooldown_ms": 30_000,
}
REGISTRY = {NAME: {"version": VERSION, "state": "candidate", "params": PARAMS,
                   "source": "unfitted defaults; kappa_fast = 1.0 until FAST_PREREG's replay"}}
LATENCY_PREREG = {
    "name": "latency-e6-v1",
    "hypothesis": "On our own recordings, buying the favoured side of a BTC/ETH 5m or 15m Up/Down market at the "
                  "arrival-time ask after a causal 10 bp / 5 s Binance move earns a positive fee-net edge, per asset.",
    "statistic": "fee-net edge per event in USD per share: favoured mid 30 s after entry - ask at arrival - "
                 "fee(1, ask, rate), entering at decision + 150 ms + measured RTT (Phase 0 method, "
                 "research.measure.latency)",
    "cluster": "market (cid)",
    "se": "cluster-robust standard error of the mean, one cluster per market",
    "judged": "per asset, on the result row's by_asset[asset] = {n, mean, se} only; a pooled pass counts for nothing",
    "alpha": 0.0228,             # one-sided, z = 2
    "pass_z": 2.0, "n": 200,     # PASS (per asset) if mean > 2 SE with n >= 200 events
    "futility_z": -1.0, "futility_n": 100,  # stop (FAIL) for an asset if mean < -1 SE once n >= 100 events
    "data": "4 weeks of our own recordings (recorder --fast plus Binance), measured from our machine; the Phase 0 "
            "free-data PASS (reports/latency_test.md) does not count",
    "duration_days": 28,
}
FAST_PREREG = {
    "name": f"{NAME}-v{VERSION}",
    "strategy": NAME,
    "hypothesis": "Maker-first bids around q = m + 0.3 (f - m) on fast Up/Down of E6-passing assets, with takers only "
                  "above min_edge, earn a positive fee-net P&L held to resolution.",
    "statistic": "per market: sum over our fills of size x (outcome - price) - taker fees, outcome from the "
                 "Chainlink TWAP resolution",
    "cluster": "market (cid)",
    "se": "cluster-robust standard error of the mean per market",
    "alpha": 0.0228,
    "pass_z": 2.0, "n": 200,     # PASS if mean > 2 SE with n >= 200 markets
    "futility_z": -1.0, "futility_n": 100,
    "data": "replay on recorded books, then shadow, then canary (paper fills from the strict simulator)",
    "params": {"name": NAME, "version": VERSION},
}


# ---------- gate ----------

def e6_edges(ledger, now_ms: int) -> dict[str, float]:
    """{asset: measured fee-net edge} for assets whose own by_asset stats in the single latency-e6-v1 row pass the
    ledger's pre-registered rule (capital's checks: one row, after the pre-registration, n, se > 0, mean > z x se)."""
    row, pre, _ = capital.single_result(ledger, LATENCY_PREREG["name"], now_ms)
    by = (row or {}).get("by_asset")
    if not isinstance(by, dict):
        return {}
    return {a: float(st["mean"]) for a, st in by.items() if not capital.judge(pre, st)}


def latency_gate(ledger, now_ms: int) -> set[str]:
    return set(e6_edges(ledger, now_ms))


# ---------- pricer (17) ----------

def twap_up(open_px: float, x: float, realised_avg: float | None, tau_s: float, sigma_abs: float,
            w: float = 60) -> float:
    """P(TWAP_close >= open), ties Up. TWAP = average of the price over the last w s before the close; arithmetic
    Brownian motion with sigma_abs (price units per sqrt(s)). tau >= w: mean x, var sigma^2 (tau - 2w/3);
    tau < w: mean ((w - tau) realised_avg + tau x) / w, var sigma^2 tau^3 / (3 w^2)."""
    if tau_s >= w:
        mean, var = x, sigma_abs ** 2 * (tau_s - 2 * w / 3)
    else:
        tau_s = max(tau_s, 0.0)
        mean, var = ((w - tau_s) * realised_avg + tau_s * x) / w, sigma_abs ** 2 * tau_s ** 3 / (3 * w * w)
    if var <= 0:
        return 1.0 if mean >= open_px else 0.0
    return _N.cdf((mean - open_px) / math.sqrt(var))


def duration_ms(event_group: str) -> int | None:
    """Window length from a crypto-fast event_group such as "BTC-5m@2026-09-30T16:45Z" or "ETH-4h@..."."""
    m = re.search(r"-(\d+)([mh])@", event_group or "")
    return None if not m else int(m[1]) * (MIN_MS if m[2] == "m" else 60 * MIN_MS)


def twa(hist, t0: int, t1: int) -> float | None:
    """Time-weighted average of the forward-filled tick prices over [t0, t1]; None without a tick at or before t0."""
    if not hist or hist[0][0] > t0 or t1 <= t0:
        return None
    total, pt, px = 0.0, t0, None
    for t, x in hist:
        if t <= t0:
            px = x
            continue
        if t >= t1:
            break
        total += px * (t - pt)
        pt, px = t, x
    return (total + px * (t1 - pt)) / (t1 - t0)


def gtd_expiry(now_ms: int, end_ms: int, p: dict) -> int | None:
    """Maker expiry in the kernel's resting-order window [now + 2 min + margin, end - 2 min], or None if empty."""
    lo, hi, step = now_ms + 2 * MIN_MS + p["gtd_margin_ms"], end_ms - 2 * MIN_MS, p["ttl_step_ms"]
    e = min(-(-lo // step) * step, hi)
    return e if e >= lo else None


def _sigma(r: dict) -> float | None:
    return r.get("sigma_q") or (sigma_q(r["dvol"]) if r.get("dvol") else None)


# ---------- engine ----------

class FastUpDownMaker:
    name = NAME

    def __init__(self, passing_assets, params: dict | None = None, edges: dict | None = None):
        self.p = {**PARAMS, **(params or {})}
        if not 0 < self.p["max_shares"] <= MAX_SHARES:
            raise ValueError(f"max_shares must be in (0, {MAX_SHARES}]")
        self.assets = frozenset(passing_assets)
        self.edges = dict(edges or {})                  # asset -> E6 measured edge; taker needs > 0
        self.versions = ((NAME, VERSION),)
        self._hist: dict[str, deque] = {}               # asset -> [(ts_ms, price)] over the TWAP/move windows
        self._opens: dict[tuple, float] = {}            # (asset, window start ms) -> open
        self._sharp_until: dict[str, int] = {}
        self._pending: dict[str, tuple] = {}            # cid -> (give-up deadline, token, size) of our last taker

    def on_tick(self, now_ms: int, markets: dict[str, MarketInfo], books: dict[str, Book], ref: dict,
                positions: dict[str, float]) -> list[Intent]:
        if not self.assets:
            return []
        self._pending = {c: v for c, v in self._pending.items() if v[0] > now_ms}
        for a in self.assets:
            self._on_ref(a, ref.get(a) or {}, now_ms)
        out = []
        for m in markets.values():
            if m.mode == "crypto-fast" and m.kind == "updown" and m.asset in self.assets:
                out += self._market(m, books, ref.get(m.asset) or {}, positions, now_ms)
        self._opens = {k: v for k, v in self._opens.items() if k[1] > now_ms - 24 * 60 * MIN_MS}
        return out

    def _on_ref(self, asset: str, r: dict, now_ms: int) -> None:
        ts, px = r.get("ts_ms"), r.get("price")
        if ts is None or not px:
            return
        h = self._hist.setdefault(asset, deque())
        if h and ts <= h[-1][0]:
            return                                      # same or older tick
        p, step = self.p, 5 * MIN_MS                    # every 5m / 15m / 4h window starts on the 5-minute grid
        b = (ts + p["settle_offset_ms"]) // step * step - p["settle_offset_ms"]   # last settlement boundary <= ts
        if h and h[-1][0] < b and ts - b <= p["open_tol_ms"]:   # this tick crossed it: the trailing TWAP is the open
            k = twa(h, b - p["twap_w_s"] * 1000, b)     # ticks before this one, forward-filled to the boundary
            if k is not None:
                self._opens[(asset, b + p["settle_offset_ms"])] = k   # shortcut: spot proxy for the Chainlink TWAP
        h.append((ts, px))
        keep = max(p["twap_w_s"] * 1000 + p["open_tol_ms"], p["move_window_ms"])   # the open's window at the crossing
        while len(h) > 1 and h[1][0] <= ts - keep:
            h.popleft()                                 # keeps one tick at or before ts - keep for forward fill
        sq = _sigma(r)
        if sq and sharp_move([e for e in h if e[0] >= ts - self.p["move_window_ms"]], sq, self.p):
            self._sharp_until[asset] = now_ms + self.p["move_cooldown_ms"]

    def _market(self, m: MarketInfo, books: dict, r: dict, positions: dict, now_ms: int) -> list[Intent]:
        p, h = self.p, self._hist.get(m.asset) or ()
        dur = duration_ms(m.event_group)
        if dur is None or not m.end_ms - dur <= now_ms < m.end_ms:
            return []
        off, w_ms = p["settle_offset_ms"], p["twap_w_s"] * 1000
        start = m.end_ms - dur
        key = (m.asset, start)
        open_px, x, sq = self._opens.get(key), r.get("price"), _sigma(r)
        yes, no = books.get(m.token_yes), books.get(m.token_no)
        if open_px is None or not x or not sq or yes is None or no is None:
            return []
        if pull_reason(m, yes, no, r, now_ms, self._sharp_until.get(m.asset, 0), p):
            return []
        tau_s, w = (m.end_ms - off - now_ms) / 1000, p["twap_w_s"]
        avg = twa(h, m.end_ms - off - w_ms, now_ms) if tau_s < w else None
        if tau_s < w and avg is None:
            return []                                   # realised part of the TWAP unknown: never guess
        f = twap_up(open_px, x, avg, tau_s, p["kappa_fast"] * sq * x / math.sqrt(SEC_PER_YEAR), w)
        mid = yes.mid_ex_own()
        if mid is None or 2 * (yes.best_ask() - mid) > p["max_book_width"]:
            return []
        q = shrink(f, mid, p["c_shrink"])
        if not invariant_ok(q, f, mid):
            return []
        size, expiry, out = m.min_size, gtd_expiry(now_ms, m.end_ms, p), []
        pend = self._pending.get(m.cid)
        for token, book, ff, mm, qq in ((m.token_yes, yes, f, mid, q), (m.token_no, no, 1 - f, 1 - mid, 1 - q)):
            # held + in-flight taker + this tick's taker + bid never pass max_shares (the taker draws on room first)
            room = p["max_shares"] - positions.get(token, 0.0) - (pend[2] if pend and pend[1] == token else 0.0)
            fmq = f"f={ff} m={mm} q={qq}"
            ask = book.best_ask()
            if ask is not None and self.edges.get(m.asset, 0.0) > 0 and pend is None and size <= room:
                edge = qq - ask - fee(1, ask, m.fee_rate) - p["slippage"]
                if edge > p["min_edge"] and book.asks[0][1] >= size:
                    pend = self._pending[m.cid] = (now_ms + p["give_up_ms"], token, size)
                    room -= size
                    out.append(Intent(NAME, m.cid, token, "BUY", ask, size, "taker", pend[0], qq,
                                      f"take {fmq} edge={edge:.4f} e6={self.edges[m.asset]:g}", self.versions))
            if expiry is not None and size <= room:
                px = floor_to(min(qq - p["half"], ask - m.tick_size if ask is not None else 1.0), m.tick_size)
                px = min(px, round(1 - m.tick_size, 10))
                if px >= m.tick_size:
                    out.append(Intent(NAME, m.cid, token, "BUY", px, size, "maker", expiry, qq,
                                      f"quote {fmq} half={p['half']}", self.versions))
        return out


if __name__ == "__main__":
    assert twap_up(100, 100, None, 300, 0.01) == 0.5
    assert twap_up(100, 100, 100, 0, 0.01) == 1.0       # tie at the close resolves Up
    assert abs(twap_up(100, 101, None, 60, 0.05) - twap_up(100, 101, 101, 60 - 1e-9, 0.05)) < 1e-6
    assert duration_ms("BTC-15m@2026-09-30T16:45Z") == 15 * MIN_MS
    print("fast_updown self-check ok")
