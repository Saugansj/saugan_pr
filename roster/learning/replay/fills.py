"""Replay fill model (role 35): role 05's paper rules (trader/router.py docstring), standalone, with Phase 1's three
execution issues fixed. Simulated only: nothing here can reach a venue.

Orders: price rounded to the tick in the passive direction, size floored to 0.01, refused below the market minimum or
off the tick range. Makers are post-only (refused if they would cross the last book) and GTD (expiry capped at close
- 2 min, refused under 60 s). Order ids follow PaperRouter's formula, so strict-mode fills compare one to one.
- maker: live from created + rtt. Queue ahead = displayed size at its price at posting, less our own (Book.own).
  mode="strict" (paper): the whole remaining size fills on a trade strictly through its price, or once volume traded
  at its price by the other side reaches queue ahead + own size.
  mode="queue": displayed size at its price that disappears without a trade moves it up the queue by cancel_ahead x
  the drop; volume beyond the queue fills it partially.
- taker: arrives at decision + 150 ms + rtt and fills against the book in force at arrival, level by level up to its
  limit and size; the rest is killed. Fee = trader.fees.fee per level.
Fixes: (1) a maker never fills on a trade at or after its GTD expiry; (2) liquidity is used once: our takers deplete
the levels they took until that token's next book update, and one trade's volume is allocated once across our makers
at that price, oldest first; (3) a taker arriving with no book in force, or past its give-up time, is killed unfilled.
"""
import dataclasses
import hashlib
import json
import math

from trader.contracts import Book, Fill, Intent, Order
from trader.fees import fee as venue_fee

TAKER_DELAY_MS = 150
GTD_CLOSE_MS = 120_000
GTD_MIN_MS = 60_000
EPS = 1e-9


def round_price(price: float, tick: float, side: str) -> float:
    n = price / tick
    return round((math.floor(n + 1e-9) if side == "BUY" else math.ceil(n - 1e-9)) * tick, 10)


def round_size(size: float) -> float:
    return math.floor(size * 100 + 1e-9) / 100


def _size_at(levels, own: dict, price: float) -> float:
    return next((s - own.get(p, 0.0) for p, s in levels if abs(p - price) < EPS), 0.0)


class FillModel:
    def __init__(self, markets: dict, rtt_ms: float, mode: str = "strict", cancel_ahead: float = 0.0, fee=venue_fee):
        if mode not in ("strict", "queue"):
            raise ValueError(f"mode {mode!r}")
        self.markets, self.rtt, self.mode, self.cancel_ahead, self.fee = markets, rtt_ms, mode, cancel_ahead, fee
        self.orders: dict[str, Order] = {}  # every order, insertion order = age
        self.open: dict[str, Order] = {}    # resting makers and takers in flight, oldest first
        self.meta: dict[str, dict] = {}     # id -> maker {ahead, got, disp} | taker {arrival}; both {m}
        self.books: dict[str, Book] = {}    # token -> copy of the last book seen
        self.used: dict[str, dict] = {}     # token -> {(side, price): shares our takers took since its last book}
        self.traded: dict[str, dict] = {}   # token -> {(resting side, price): volume traded since its last book}
        self.reasons: dict[str, str] = {}
        self.fills: list[Fill] = []
        self._seq = 0

    def open_orders(self) -> list[Order]:
        return list(self.open.values())

    def _close(self, o: Order, status: str) -> None:
        o.status = status
        self.open.pop(o.order_id, None)

    def _check(self, i: Intent, m, now_ms: int) -> str | None:
        if m is None or i.token_id not in (m.token_yes, m.token_no):
            return "unknown market or token"
        if not m.tick_size - EPS <= i.price <= 1 - m.tick_size + EPS:
            return "price outside the tick range"
        if i.size < m.min_size - EPS:
            return f"size below the market minimum {m.min_size}"
        if i.kind == "maker":
            bk = self.books.get(i.token_id)
            if bk is None:
                return "no book"
            opp = bk.asks if i.side == "BUY" else bk.bids
            if opp and (i.price >= opp[0][0] - EPS if i.side == "BUY" else i.price <= opp[0][0] + EPS):
                return "post-only order would cross"
            if i.expiry_ms < now_ms + GTD_MIN_MS:
                return "GTD expiry under the CLOB minimum (or past market close - 2 min)"
        return None

    def submit(self, intent: Intent, now_ms: int) -> Order:
        i, m = intent, self.markets.get(intent.cid)
        if m:
            exp = min(i.expiry_ms, m.end_ms - GTD_CLOSE_MS) if i.kind == "maker" else i.expiry_ms
            i = dataclasses.replace(i, price=round_price(i.price, m.tick_size, i.side), size=round_size(i.size),
                                    expiry_ms=exp)
        self._seq += 1
        oid = hashlib.sha256(json.dumps([dataclasses.asdict(i), now_ms, self._seq], default=str).encode()).hexdigest()
        reason = self._check(i, m, now_ms)
        o = self.orders[oid] = Order(oid, i, "rejected" if reason else "open", 0.0, now_ms)
        if reason:
            self.reasons[oid] = reason
            return o
        self.open[oid] = o
        if i.kind == "maker":
            bk = self.books[i.token_id]
            o.queue_ahead = _size_at(bk.bids if i.side == "BUY" else bk.asks, bk.own, i.price)
            self.meta[oid] = {"ahead": o.queue_ahead, "got": 0.0, "disp": o.queue_ahead, "m": m}
        else:
            self.meta[oid] = {"arrival": now_ms + TAKER_DELAY_MS + round(self.rtt), "m": m}
        return o

    def cancel(self, order_id: str, now_ms: int) -> None:
        """A resting maker is cancelled; a taker in flight cannot be recalled."""
        o = self.orders.get(order_id)
        if o and o.order_id in self.open and o.intent.kind == "maker":
            self._close(o, "cancelled")

    def _fill(self, o: Order, price: float, size: float, ts: int, maker: bool, fee: float) -> Fill:
        i = o.intent
        f = Fill(o.order_id, i.strategy, i.cid, i.token_id, i.side, price, size, ts, maker, fee)
        o.filled = round(o.filled + size, 6)
        if o.filled >= i.size - EPS:
            self._close(o, "filled")
        else:
            o.status = "partial"
        self.fills.append(f)
        return f

    def _expire(self, now_ms: int) -> None:
        for o in self.open_orders():
            if o.intent.kind == "maker" and o.intent.expiry_ms <= now_ms:
                self._close(o, "expired")

    def _takers(self, token: str, now_ms: int) -> list[Fill]:
        out = []
        for o in [o for o in self.open_orders() if o.intent.token_id == token and o.intent.kind == "taker"
                  and self.meta[o.order_id]["arrival"] <= now_ms]:
            i, arr, m = o.intent, self.meta[o.order_id]["arrival"], self.meta[o.order_id]["m"]
            bk = self.books.get(token)
            if arr > i.expiry_ms or bk is None or bk.ts_ms > arr:  # fix 3: killed with zero fill
                self._close(o, "cancelled")
                self.reasons[o.order_id] = "arrived past its give-up time" if arr > i.expiry_ms else "no book in force"
                continue
            used, left = self.used.setdefault(token, {}), i.size
            for p, s in (bk.asks if i.side == "BUY" else bk.bids):
                if left < 0.01 - EPS or (p > i.price + EPS if i.side == "BUY" else p < i.price - EPS):
                    break
                q = round_size(min(s - used.get((i.side, p), 0.0), left))  # fix 2: what our earlier takers took is gone
                if q <= 0:
                    continue
                used[(i.side, p)] = used.get((i.side, p), 0.0) + q
                out.append(self._fill(o, p, q, arr, False, self.fee(q, p, m.fee_rate)))
                left = round(left - q, 6)
            if o.order_id in self.open:
                self._close(o, "cancelled")  # FAK: the unfilled rest is killed
        return out

    def on_book(self, book: Book, now_ms: int) -> list[Fill]:
        """Every book update, in recorded order: takers that arrived since fill against the book it replaces."""
        t = book.token_id
        fills = self._takers(t, now_ms)
        if self.mode == "queue":
            traded = self.traded.get(t, {})
            for o in self.open_orders():
                i, md = o.intent, self.meta[o.order_id]
                if i.token_id != t or i.kind != "maker":
                    continue
                disp = _size_at(book.bids if i.side == "BUY" else book.asks, book.own, i.price)
                drop = md["disp"] - disp - traded.get((i.side, round(i.price, 6)), 0.0)
                if drop > EPS:  # displayed size gone without a trade: part of it was ahead of us
                    md["ahead"] = max(0.0, md["ahead"] - self.cancel_ahead * drop)
                md["disp"] = disp
        self.books[t] = Book(t, book.bids, book.asks, book.ts_ms, dict(book.own))
        self.used.pop(t, None)
        self.traded.pop(t, None)
        self._expire(now_ms)
        return fills

    def poll(self, now_ms: int) -> list[Fill]:
        """Takers whose arrival passed with no book update since; GTD expiries."""
        fills = [f for t in {o.intent.token_id for o in self.open_orders() if o.intent.kind == "taker"}
                 for f in self._takers(t, now_ms)]
        self._expire(now_ms)
        return fills

    def on_trade(self, token_id: str, price: float, size: float, taker_side: str, ts_ms: int) -> list[Fill]:
        self._expire(ts_ms)  # fix 1: a maker never fills on a trade at or after its GTD expiry
        rest = "BUY" if taker_side == "SELL" else "SELL"
        tr = self.traded.setdefault(token_id, {})
        tr[(rest, round(price, 6))] = tr.get((rest, round(price, 6)), 0.0) + size
        out, pool = [], size  # fix 2: this trade's volume, allocated once across our makers at its price
        for o in self.open_orders():
            i, md = o.intent, self.meta.get(o.order_id)
            if i.token_id != token_id or i.kind != "maker" or ts_ms < o.created_ms + self.rtt:
                continue
            left = round(i.size - o.filled, 6)
            if price < i.price - EPS if i.side == "BUY" else price > i.price + EPS:  # strictly through its price
                out.append(self._fill(o, i.price, left, ts_ms, True, 0.0))
                continue
            if abs(price - i.price) > EPS or taker_side == i.side or pool <= EPS:
                continue
            take = min(pool, md["ahead"])
            md["ahead"] -= take
            pool -= take
            g = min(pool, left - md["got"])
            pool -= g
            if self.mode == "strict":
                md["got"] += g
                if md["got"] >= left - EPS:
                    out.append(self._fill(o, i.price, left, ts_ms, True, 0.0))
            elif g > EPS:
                out.append(self._fill(o, i.price, round(g, 6), ts_ms, True, 0.0))
        return out
