"""Execution router, PAPER ONLY (WP1-C; build-plan 1.16, roles 05 and 35). Implements trader.contracts.Router.

Live mode is impossible: nothing in this module (or anything it imports) can sign, send or post an order. Passing
live=True, setting `router.live`, or any of LIVE_ENV in the environment raises LiveTradingForbidden.

Order rules (as the CLOB applies them): price rounded to the market's tick in the passive direction (BUY down,
SELL up: never more aggressive than asked), size floored to 0.01 share (never rounded up), refused below the
market's minimum size, batches of at most 15. Makers are post-only (refused if they would cross) and GTD: expiry
capped at market close - 2 min, refused if that leaves under 60 s (the CLOB's GTD minimum; the kernel adds its own
2 min + margin rule). Takers are FAK. A SELL may not exceed the position not already offered.

Strict fill simulator (shared with role 35):
- maker: fills its whole remaining size, at its own price with no fee, on a trade strictly through its price, or
  once the volume traded at its price (by takers on the other side) reaches the queue ahead at posting plus its own
  size. Only trades from created + round trip on count (before that the order was not resting). A book that
  crosses it without a trade does not fill it. Queue progress is not journaled: after a restart it starts again
  from zero (conservative).
- taker: reaches the book at arrival = decision + 150 ms taker delay + measured round trip, and fills against the
  book in force at that moment (the last update before it), level by level up to its limit and size; the rest is
  killed. Taker fee = trader.fees.fee(size, price, market.fee_rate) per level.

Write-ahead journal (data/trader/journal.jsonl): every state change is one JSON line, flushed and fsync'd before it
takes effect; a failed write raises so the caller can halt. A new order's line (its sha256 id, the intent, queue
ahead, arrival and round trip) is on disk before the order counts as sent. On start the journal is replayed; an
order journaled but never acknowledged, or a taker still in flight, is `unknown`, and no new order is accepted on
that token and side until the reconciler resolves it (cancel by id). A torn last line (crash mid-write) is ignored.

liquidity_once=True (WW-B; off = the audited Phase 1 simulator) ports learning.replay.fills.FillModel's fix 2, so paper
and strict replay agree when our own orders compete: our takers deplete the levels they took until that token's next
book update, and one trade's volume at a price is allocated once across our makers there, oldest first (queue ahead
first, then each maker's own size). Fixes 1 and 3 (expire before trades, no-book/give-up kill) were already here.
"""
import dataclasses
import hashlib
import json
import math
import os
import pathlib

import common
from trader.contracts import Book, Fill, Intent, MarketInfo, Order

JOURNAL = common.DATA / "trader" / "journal.jsonl"
TAKER_DELAY_MS = 150
MAX_BATCH = 15
GTD_CLOSE_MS = 120_000
GTD_MIN_MS = 60_000
LIVE_ENV = ("ROSTER_LIVE", "TRADER_LIVE", "POLYMARKET_LIVE")
OPEN = ("journaled", "open", "partial", "unknown")  # not terminal: counted by open_orders() and the kernel
EPS = 1e-9


class LiveTradingForbidden(RuntimeError):
    pass


def round_price(price: float, tick: float, side: str) -> float:
    n = price / tick
    return round((math.floor(n + 1e-9) if side == "BUY" else math.ceil(n - 1e-9)) * tick, 10)


def round_size(size: float) -> float:
    return math.floor(size * 100 + 1e-9) / 100


# ---- venue amount precision for marketable BUYs (18 Nov, v9fix) ------------------------------------------------------
# Polymarket refuses a marketable (FAK/FOK) BUY whose USDC leg (maker amount = size x limit) has more than 2 decimals:
#   "invalid amounts, the market buy orders maker amount supports a max accuracy of 2 decimals, taker amount a max of
#    4 (or 5) decimals"   (live journals 12-18 Nov: e.g. 9.81 x 0.102 = 1.00062, 9.1 x 0.11 = 1.001)
# and one under $1 ("invalid amount for a marketable BUY order ($0.7), min size: 1"). Our sizes are whole cents of a share
# (2 decimals), so the taker leg (shares) is always within 4 decimals; only the maker leg needs care.
def _decimals(x: float, most: int = 6) -> int:
    for k in range(most + 1):
        if abs(x * 10 ** k - round(x * 10 ** k)) < 1e-6:
            return k
    return most


def buy_amounts_ok(size: float, price: float, min_notional: float = 0.0) -> bool:
    """True when a marketable BUY of `size` shares at limit `price` passes the venue's amount rules: shares in whole
    hundredths, size x price in whole cents, and size x price >= min_notional."""
    s = round(size * 100)
    if abs(size * 100 - s) > 1e-6 or s <= 0:
        return False
    d = _decimals(price)
    pi = round(price * 10 ** d)
    if (s * pi) % (10 ** d):
        return False
    return s * pi / 10 ** (d + 2) >= min_notional - 1e-9


def marketable_buy(size: float, limit: float, tick: float, min_notional: float = 0.0, max_size: float = math.inf,
                   floor_price: float | None = None, max_down_ticks: int = 9) -> tuple[float, float] | None:
    """(limit, size) for a marketable BUY that the venue accepts, or None.

    Starts from `limit` floored to the tick and `size` rounded UP to 0.01 share. For each size from there upwards (0.01
    steps, at most `max_size`), tries the limit and then up to `max_down_ticks` ticks below it (never below
    `floor_price`, normally the ask seen, so the order stays marketable); the first pair whose USDC amount is in whole
    cents and >= min_notional wins. So: the smallest valid size >= the desired size, keeping the limit when possible,
    else shading the limit down by the fewest ticks. With 2-decimal prices any whole-share size is valid; with
    0.001-tick prices the search is at most 10 shares wide."""
    lim = round_price(limit, tick, "BUY")
    lo = max(tick, floor_price if floor_price is not None else tick)
    s0 = math.ceil(size * 100 - 1e-6)
    s_max = math.floor(max_size * 100 + 1e-6)
    prices = [round(lim - k * tick, 10) for k in range(max_down_ticks + 1) if lim - k * tick >= lo - 1e-9]
    for s in range(max(1, s0), s_max + 1):
        for p in prices:
            if buy_amounts_ok(s / 100, p, min_notional):
                return p, s / 100
    return None


def _intent(d: dict) -> Intent:
    return Intent(**{**d, "versions": tuple(tuple(v) for v in d.get("versions", ()))})


class State:
    """Orders, fills, positions and cash as rebuilt from journal entries (live and on replay alike)."""

    def __init__(self):
        self.orders: dict[str, Order] = {}
        self.arrival: dict[str, int] = {}     # taker order id -> arrival ms
        self.fills: list[Fill] = []
        self.positions: dict[str, float] = {}  # token -> shares
        self.cost: dict[str, float] = {}       # token -> USD paid for the shares held (fees included)
        self.cash = 0.0                        # pUSD change since the journal began
        self.merges: list[dict] = []

    def _add(self, token: str, shares: float, usd: float) -> None:
        held = self.positions.get(token, 0.0)
        if shares > 0:
            self.cost[token] = self.cost.get(token, 0.0) + usd
        elif held > EPS:
            self.cost[token] = self.cost.get(token, 0.0) * (held + shares) / held  # average cost of what is left
        self.positions[token] = round(held + shares, 6)

    def apply(self, e: dict) -> None:
        op, o = e["op"], self.orders.get(e.get("id"))
        if op == "new":
            self.orders[e["id"]] = Order(e["id"], _intent(e["intent"]), "journaled", 0.0, e["ts"], e.get("queue_ahead", 0.0))
            if "arrival_ms" in e:
                self.arrival[e["id"]] = e["arrival_ms"]
        elif op == "ack":
            o.status = "open"
        elif op == "fill":
            f = Fill(**e["fill"])
            self.fills.append(f)
            o.filled = round(o.filled + f.size, 6)
            o.status = "filled" if o.filled >= o.intent.size - EPS else "partial"
            sign = 1 if f.side == "BUY" else -1
            self.cash -= sign * f.price * f.size + f.fee
            self._add(f.token_id, sign * f.size, f.price * f.size + f.fee)
        elif op == "revert":  # a live trade matched off-chain, then FAILED on-chain: undo the fill booked for it
            f = Fill(**e["fill"])
            o.filled = round(o.filled - f.size, 6)
            if o.status == "filled":
                o.status = "cancelled"  # terminal; reconcile_venue cancels it if the venue still rests it
            sign = 1 if f.side == "BUY" else -1
            self.cash += sign * f.price * f.size + f.fee
            held = self.positions.get(f.token_id, 0.0)
            if sign > 0:
                self.cost[f.token_id] = self.cost.get(f.token_id, 0.0) - f.price * f.size - f.fee
                self.positions[f.token_id] = round(held - f.size, 6)
            else:
                # shortcut: a reverted SELL's shares come back at the current average cost, not the pre-sale cost
                self._add(f.token_id, f.size, self.cost.get(f.token_id, 0.0) / held * f.size if held > EPS else f.price * f.size)
        elif op == "done":  # FAK finished: the unfilled rest is killed
            o.status = "filled" if o.filled >= o.intent.size - EPS else "cancelled"
        elif op == "cancel":
            o.status = "cancelled"
        elif op == "expire":
            o.status = "expired"
        elif op == "unknown":
            o.status = "unknown"
        elif op == "merge":
            cost = 0.0
            for t in (e["yes"], e["no"]):
                held = self.positions.get(t, 0.0)
                cost += self.cost.get(t, 0.0) * e["size"] / held if held > EPS else 0.0
                self._add(t, -e["size"], 0.0)
            self.cash += e["size"]
            self.merges.append({"cid": e["cid"], "yes": e["yes"], "no": e["no"], "size": e["size"], "ts_ms": e["ts"],
                                "cost": round(cost, 6),
                                "edge": round(e["size"] - cost, 6)})  # locked edge = size x (1 - p - q) less fees


def replay(path) -> State:
    st = State()
    if pathlib.Path(path).exists():
        for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue  # torn last line: its write never completed, so it never took effect
            st.apply(e)
    return st


class PaperRouter:
    def __init__(self, markets: dict[str, MarketInfo], rtt_ms, journal=JOURNAL, fee=None, live=False,
                 liquidity_once=False, maker_realism=False, realism: dict | None = None):
        """markets: the live {cid: MarketInfo} dict (tick changes show up at once). rtt_ms: measured round trip in ms,
        a number or a zero-argument callable (e.g. lambda: md.rtt_ms). fee: fee(C, p, rate); default trader.fees.fee.
        realism: None (the audited simulator) or a trader.realism config (flag paper_realism): live latency, venue
        amount rules, spend semantics and the extra FAK no-match, for marketable BUYs (trader/realism.py)."""
        if live or any(os.environ.get(k, "").strip().lower() not in ("", "0", "false", "no") for k in LIVE_ENV):
            raise LiveTradingForbidden("Phase 1 is paper only: there is no live order path")
        if fee is None:
            from trader.fees import fee  # the one fee function (WP1-A)
        self.markets, self.fee = markets, fee
        self._rtt = rtt_ms if callable(rtt_ms) else (lambda: rtt_ms)
        self.path = pathlib.Path(journal)
        self.state = replay(self.path)  # restart: rebuild every order's state
        self.path.parent.mkdir(parents=True, exist_ok=True)
        torn = False
        if self.path.exists() and self.path.stat().st_size:
            with open(self.path, "rb") as f:
                f.seek(-1, os.SEEK_END)
                torn = f.read(1) != b"\n"
        self._f = open(self.path, "a", encoding="utf-8")
        if torn:
            self._f.write("\n")  # end a line torn by a crash, so the next entry starts on its own line
        for o in list(self.state.orders.values()):  # never acknowledged, or a taker in flight: it may have reached the venue
            if o.status == "journaled" or (o.intent.kind == "taker" and o.status in ("open", "partial")):
                self._log({"op": "unknown", "id": o.order_id, "ts": common.now_ms()})
        self.books: dict[str, tuple] = {}  # token -> (bids, asks, ts_ms) as last seen
        self.reasons: dict[str, str] = {}  # rejected order id -> why (Order has no reason field)
        self._cum: dict[str, float] = {}   # maker id -> volume traded at its price since it went live
        self._seq = 0
        self.liquidity_once = liquidity_once
        self._used: dict[str, dict] = {}   # liquidity_once: token -> {(side, price): shares our takers took since its book}
        self._q: dict[str, list] = {}      # liquidity_once: maker id -> [queue ahead left, own size reached]
        self.maker_realism = maker_realism
        self._cancel_at: dict[str, int] = {}  # maker_realism: maker id -> when its cancel reaches the venue
        self.realism = realism
        if realism is not None:
            from trader.realism import KillModel
            self.kill = KillModel(realism)
            if self.path.exists():   # restart: the running replay fill rate continues from the journal
                for line in self.path.read_text(encoding="utf-8").splitlines():
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    if e.get("op") == "done" and e.get("realism") in ("fill", "miss", "kill"):
                        self.kill.n += 1
                        self.kill.filled += e["realism"] != "miss"

    @property
    def live(self) -> bool:
        return False

    @live.setter
    def live(self, _):
        raise LiveTradingForbidden("Phase 1 is paper only: there is no live order path")

    @property
    def positions(self) -> dict[str, float]:
        return self.state.positions

    def _log(self, e: dict) -> None:
        self._f.write(json.dumps(e, separators=(",", ":")) + "\n")
        self._f.flush()
        os.fsync(self._f.fileno())  # raises on a failed write: the change never takes effect, the caller halts
        self.state.apply(e)

    def open_orders(self) -> list[Order]:
        return [o for o in self.state.orders.values() if o.status in OPEN]

    def _check(self, i: Intent, m: MarketInfo | None, now_ms: int) -> str | None:
        if m is None or i.token_id not in (m.token_yes, m.token_no):
            return "unknown market or token"
        if not m.tick_size - EPS <= i.price <= 1 - m.tick_size + EPS:
            return "price outside the tick range"
        if i.size < m.min_size - EPS:
            return f"size below the market minimum {m.min_size}"
        if any(o.status == "unknown" and o.intent.token_id == i.token_id and o.intent.side == i.side
               for o in self.state.orders.values()):
            return "an order on this token and side is in unknown state; not retried until reconciled"
        if i.side == "SELL":
            offered = sum(o.intent.size - o.filled for o in self.open_orders()
                          if o.intent.token_id == i.token_id and o.intent.side == "SELL")
            if i.size > self.positions.get(i.token_id, 0.0) - offered + EPS:
                return "sell exceeds the position not already offered"
        if i.kind == "maker":
            bk = self.books.get(i.token_id)
            if bk is None:
                return "no book"
            opp = bk[1] if i.side == "BUY" else bk[0]
            if opp and (i.price >= opp[0][0] - EPS if i.side == "BUY" else i.price <= opp[0][0] + EPS):
                return "post-only order would cross"
            if i.expiry_ms < now_ms + GTD_MIN_MS:
                return "GTD expiry under the CLOB minimum (or past market close - 2 min)"
        elif self.realism is not None and self.realism["venue_amounts"] and i.side == "BUY":
            if i.price * i.size < self.realism["min_notional"] - EPS:   # the venue's words (live journals, 16 Nov)
                return f"invalid amount for a marketable BUY order (${i.price * i.size:.2f}), min size: {self.realism['min_notional']:g}"
            if not buy_amounts_ok(i.size, i.price):
                return ("invalid amounts, the market buy orders maker amount supports a max accuracy of 2 decimals, "
                        "taker amount a max of 4 decimals")
        return None

    def submit(self, intent: Intent, now_ms: int) -> Order:
        return self.submit_batch([intent], now_ms)[0]

    def submit_batch(self, intents: list[Intent], now_ms: int) -> list[Order]:
        if len(intents) > MAX_BATCH:
            raise ValueError(f"batch of {len(intents)} orders; the CLOB takes at most {MAX_BATCH}")
        out, rtt = [], self._rtt()
        for i in intents:
            m = self.markets.get(i.cid)
            if m:
                exp = min(i.expiry_ms, m.end_ms - GTD_CLOSE_MS) if i.kind == "maker" else i.expiry_ms
                i = dataclasses.replace(i, price=round_price(i.price, m.tick_size, i.side), size=round_size(i.size),
                                        expiry_ms=exp)
            self._seq += 1
            oid = hashlib.sha256(json.dumps([dataclasses.asdict(i), now_ms, self._seq], default=str).encode()).hexdigest()
            reason = self._check(i, m, now_ms)
            if reason:
                self.reasons[oid] = reason
                out.append(Order(oid, i, "rejected", 0.0, now_ms))
                continue
            e = {"op": "new", "id": oid, "ts": now_ms, "intent": dataclasses.asdict(i)}
            if i.kind == "maker":
                bk = self.books[i.token_id]
                e["queue_ahead"] = next((s for p, s in (bk[0] if i.side == "BUY" else bk[1]) if abs(p - i.price) < EPS), 0.0)
            else:
                e["arrival_ms"], e["rtt_ms"] = now_ms + TAKER_DELAY_MS + round(rtt), rtt
                if self.realism is not None and i.side == "BUY":   # paper_realism: a draw from the live latency
                    from trader.realism import latency_ms
                    e["latency_ms"] = latency_ms(self.realism, oid)
                    e["arrival_ms"] = now_ms + e["latency_ms"]
            self._log(e)  # write-ahead: on disk before the order counts as sent
            out.append(self.state.orders[oid])
        for o in out:  # paper "send": nothing leaves this process; the simulated venue acknowledges at once
            if o.status == "journaled":
                self._log({"op": "ack", "id": o.order_id, "ts": now_ms})
        return out

    def cancel(self, order_id: str, now_ms: int) -> None:
        """Cancel by id. Also how an unknown order is resolved. A taker in flight cannot be recalled."""
        o = self.state.orders.get(order_id)
        if self.maker_realism and o and o.intent.kind == "maker" and o.status in ("open", "partial"):
            # the venue drops it only after half the round trip; trades before then can still fill it
            self._cancel_at.setdefault(order_id, now_ms + round(self._rtt() / 2))
            return
        if o and o.status in OPEN and not (o.intent.kind == "taker" and o.status != "unknown"):
            self._log({"op": "cancel", "id": order_id, "ts": now_ms})

    def cancel_all(self, now_ms: int) -> None:
        for o in self.open_orders():
            self.cancel(o.order_id, now_ms)

    def merge(self, cid: str, size: float, now_ms: int) -> dict:
        """Merge `size` YES+NO pairs of a market back into pUSD (simulated; role 06 does it from Phase 2)."""
        m = self.markets[cid]
        self._log({"op": "merge", "cid": cid, "yes": m.token_yes, "no": m.token_no, "size": size, "ts": now_ms})
        return self.state.merges[-1]

    def _expire(self, now_ms: int) -> None:
        for oid, t in list(self._cancel_at.items()):   # maker_realism: cancels that have reached the venue
            if t <= now_ms:
                del self._cancel_at[oid]
                o = self.state.orders.get(oid)
                if o and o.status in OPEN:
                    self._log({"op": "cancel", "id": oid, "ts": t})
        for o in self.open_orders():
            if o.intent.kind == "maker" and o.status in ("open", "partial") and o.intent.expiry_ms <= now_ms:
                self._log({"op": "expire", "id": o.order_id, "ts": now_ms})

    def _takers(self, token: str, now_ms: int) -> list[Fill]:
        """Fill takers on `token` whose arrival has passed, against the book as last seen (in force at arrival)."""
        out = []
        for o in [o for o in self.open_orders() if o.intent.token_id == token and o.intent.kind == "taker"
                  and o.status in ("open", "partial")]:
            i, arr = o.intent, self.state.arrival[o.order_id]
            if arr > now_ms:
                continue
            bk = self.books.get(token)
            late = arr > i.expiry_ms and not (self.realism and not self.realism["honor_give_up"])
            if late or bk is None:  # past its deadline, or no book to fill against at arrival: kill it
                self._log({"op": "expire", "id": o.order_id, "ts": now_ms})
                continue
            m = self.markets[i.cid]
            used = self._used.setdefault(token, {}) if self.liquidity_once else {}
            levels = self._walk(i, bk, used)
            if self.realism is not None and i.side == "BUY":   # paper_realism: the extra FAK no-match (trader/realism.py)
                if self.kill.decide(o.order_id, bool(levels)):
                    self._log({"op": "done", "id": o.order_id, "ts": arr, "realism": "kill"})
                    continue
            for p, q in levels:
                used[(i.side, p)] = used.get((i.side, p), 0.0) + q
                px = min(i.price, round(p + self.realism["extra_slip"], 6)) if self.realism and i.side == "BUY" else p
                f = Fill(o.order_id, i.strategy, i.cid, token, i.side, px, q, arr, False, self.fee(q, px, m.fee_rate))
                self._log({"op": "fill", "id": o.order_id, "fill": dataclasses.asdict(f)})
                out.append(f)
            done = {"op": "done", "id": o.order_id, "ts": arr}
            if self.realism is not None and i.side == "BUY":
                done["realism"] = "fill" if levels else "miss"
            self._log(done)
        return out

    def _walk(self, i: Intent, bk: tuple, used: dict) -> list[tuple[float, float]]:
        """[(price, shares)] a taker takes from the arrival book, level by level up to its limit. Default: up to its size
        (shares floored to 0.01). paper_realism with spend_limit_notional: a BUY spends at most size x limit USDC, as
        the venue's marketable BUY does, so a fill under the limit gets more shares (6-decimal shares, as the venue)."""
        spend = self.realism is not None and i.side == "BUY" and self.realism["spend_limit_notional"]
        out, left, budget = [], i.size, i.size * i.price
        slip = self.realism["extra_slip"] if self.realism is not None and i.side == "BUY" else 0.0
        for p, s in (bk[1] if i.side == "BUY" else bk[0]):
            if (p > i.price + EPS if i.side == "BUY" else p < i.price - EPS):
                break
            avail = s - used.get((i.side, p), 0.0)
            if spend:
                px = min(i.price, p + slip)
                if budget < 0.01 - EPS:
                    break
                q = math.floor(min(avail, budget / px) * 1e6 + 1e-6) / 1e6
                if q < 0.01:
                    continue
                budget = round(budget - q * px, 9)
            else:
                if left < 0.01 - EPS:
                    break
                q = round_size(min(avail, left))
                if q <= 0:
                    continue
                left = round(left - q, 6)
            out.append((p, q))
        return out

    def on_book(self, book: Book, now_ms: int) -> list[Fill]:
        """Call on every book update, before the engines see it."""
        fills = self._takers(book.token_id, now_ms)
        self.books[book.token_id] = (book.bids, book.asks, book.ts_ms)
        self._used.pop(book.token_id, None)  # a new book: its displayed sizes already net out what we took
        self._expire(now_ms)
        return fills

    def poll(self, now_ms: int) -> list[Fill]:
        """Takers whose arrival passed with no book update since (the last book is still in force); GTD expiries."""
        fills = [f for t in {o.intent.token_id for o in self.open_orders() if o.intent.kind == "taker"}
                 for f in self._takers(t, now_ms)]
        self._expire(now_ms)
        return fills

    def on_trade(self, token_id: str, price: float, size: float, taker_side: str, ts_ms: int) -> list[Fill]:
        self._expire(ts_ms)  # a GTD-expired maker must not fill on a later trade
        out, rtt, pool = [], self._rtt(), size
        for o in self.open_orders():
            i = o.intent
            if i.token_id != token_id or i.kind != "maker" or o.status not in ("open", "partial") \
                    or ts_ms < o.created_ms + rtt:
                continue
            through = price < i.price - EPS if i.side == "BUY" else price > i.price + EPS
            if not through:
                if abs(price - i.price) > EPS or taker_side == i.side:
                    continue
                if self.liquidity_once:  # this trade's volume is used once: queue ahead first, then our own size
                    q, left = self._q.setdefault(o.order_id, [o.queue_ahead, 0.0]), i.size - o.filled
                    take = min(pool, q[0])
                    q[0], pool = q[0] - take, pool - take
                    g = min(pool, left - q[1])
                    q[1], pool = q[1] + g, pool - g
                    if q[1] < left - EPS:
                        continue
                else:
                    self._cum[o.order_id] = self._cum.get(o.order_id, 0.0) + size
                    if self._cum[o.order_id] < o.queue_ahead + i.size - EPS:
                        continue
            f = Fill(o.order_id, i.strategy, i.cid, token_id, i.side, i.price, round(i.size - o.filled, 6), ts_ms, True, 0.0)
            self._log({"op": "fill", "id": o.order_id, "fill": dataclasses.asdict(f)})
            out.append(f)
        self._expire(ts_ms)
        return out
