"""Live execution router (task 2.3, role 05): trader.contracts.Router plus submit_batch, poll, on_user_event,
reconcile_venue and confirm_zero_open. Built now, wired later: constructing it needs the three-flag live guard, and
every venue call goes through trader.live.clob.L2Client, which checks the guard again at call time.

Journal: the same JSONL schema as trader/router.py (replayed by trader.router.replay), each entry flushed and fsync'd
before it takes effect; a failed write raises. `new` carries the EIP-712 order id, the intent (expiry_ms = the GTD
expiry actually sent), queue_ahead (book size at our price when posted), expiration (s) and order_type. Fill entries
carry the venue trade ids they cover ("trades"), so a fill is journaled once per trade id, across restarts too.

Flow: check + sign every order (no side effects), journal every `new`, then ONE post_orders call (5 s timeout):
  accepted with the venue id equal to ours -> ack | explicit rejection (success false / errorMsg, or HTTP 4xx other
  than 408) -> cancel with the reason, terminal, never resent | exception, timeout, missing result or another id ->
  unknown. Nothing is ever posted twice: the post happens once, inside submit_batch, for freshly signed ids only.

poll(now): every unknown or unacked order (and every acked taker, whose fills only the venue knows) at least 5 s old is cancelled
by id and then queried by id. GET /data/order/<id> status mapping (fixtures in tests/phase2/test_live_exec.py):
  size_matched above what we journaled -> fill entries for the difference at the order's price (taker fee via
  trader.fees.fee), then: CANCELED* / INVALID -> cancel (taker: done) | EXPIRED -> expire | MATCHED -> done unless
  fully filled | LIVE / DELAYED / UNMATCHED / no answer -> keep resolving.
30 s after submission an order still unresolved trips trip("global", ..., "router") (HALTED) and sends ONE
cancel_all(); it stays unknown until reconcile_venue finds it absent from the venue after that cancel-all.

User channel (docs.polymarket.com, user channel; fixtures in the tests):
  trade {event_type: "trade", id, status MATCHED|MINED|CONFIRMED|RETRYING|FAILED, taker_order_id, size, price,
  maker_orders: [{order_id, matched_amount, price}], matchtime} -> one fill per trade id, the first time it is seen
  (ours as taker: size at price, taker fee; ours as maker: matched_amount at the maker price, no fee); FAILED ->
  revert the fills booked for that trade id and trip(cid, ..., "reconciler") for each of its markets (global when
  none is ours); a FAILED seen first is journaled, so a later MATCHED for it books nothing.
  order {event_type: "order", id, type PLACEMENT|UPDATE|CANCELLATION, size_matched} -> CANCELLATION: cancel;
  PLACEMENT of an order we hold as unknown: ack (the venue has it).
"""
import dataclasses
import json
import logging
import math
import os
import pathlib

import common
from trader.contracts import Book, Fill, Intent, MarketInfo, Order
from trader.fees import fee
from trader.live.clob import CredentialsMissing, LiveGuardError, VenueError
from trader.router import OPEN, buy_amounts_ok, replay, round_price, round_size

log = logging.getLogger(__name__)
MIN = 60_000
MAX_BATCH = 15
GTD_MARGIN_MS = 30_000   # as RiskKernel.gtd_margin_ms: a GTD order needs >= 2 min + this left
RESOLVE_AFTER_MS = 5_000
HALT_AFTER_MS = 30_000
MIN_BUY_NOTIONAL = 1.00   # venue: "invalid amount for a marketable BUY order ($0.7), min size: 1" (size x limit)
EPS = 1e-9


def gtd_expiry_ms(requested_ms: int, end_ms: int, start_ms: int | None, now_ms: int,
                  margin_ms: int = GTD_MARGIN_MS) -> int | None:
    """min(requested, start - 5 min while the start is ahead, close - 2 min), floored to whole seconds; None (refuse)
    when that leaves under 2 min + margin."""
    exp = min(requested_ms, end_ms - 2 * MIN)
    if start_ms is not None and start_ms > now_ms:
        exp = min(exp, start_ms - 5 * MIN)
    exp = exp // 1000 * 1000
    return exp if exp >= now_ms + 2 * MIN + margin_ms else None


def venue_status(rec) -> str:
    """GET /data/order status, upper-cased, without the ORDER_STATUS_ prefix some responses carry; "" if unreadable."""
    return str(rec.get("status") or "").upper().removeprefix("ORDER_STATUS_") if isinstance(rec, dict) else ""


def _num(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


class LiveRouter:
    def __init__(self, markets: dict[str, MarketInfo], client, signer, trip, journal, now_ms=common.now_ms):
        """client: trader.live.clob.L2Client. signer: .sign(intent, market, expiration_s, order_type) -> (id, payload).
        trip(scope, reason, source): the kernel's trip (HALTED by default). journal: the JSONL path (the loop picks it)."""
        client.require_live()
        self.markets, self.client, self.signer, self.trip = markets, client, signer, trip
        self.path = pathlib.Path(journal)
        self.state = replay(self.path)  # restart: rebuild every order's state
        self.trades: set[str] = set()   # venue trade ids already journaled
        self.booked: dict[str, list[dict]] = {}  # trade id -> its fill entries, until it FAILS (then reverted)
        raw = self.path.read_bytes() if self.path.exists() else b""
        for line in raw.decode("utf-8", "replace").splitlines():
            try:
                e = json.loads(line)
                self.trades.update(e.get("trades", ()))
            except (ValueError, AttributeError):
                continue  # torn last line
            for t in e.get("trades", ()):
                if e.get("op") == "fill":
                    self.booked.setdefault(t, []).append(e)
                elif e.get("op") in ("revert", "failed"):
                    self.booked.pop(t, None)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._f = open(self.path, "a", encoding="utf-8")
        if raw and not raw.endswith(b"\n"):
            self._f.write("\n")  # end a line torn by a crash, so the next entry starts on its own line
        now = now_ms()
        for o in list(self.state.orders.values()):  # never acknowledged, or a taker in flight: it may be at the venue
            if o.status == "journaled" or (o.intent.kind == "taker" and o.status in ("open", "partial")):
                self._log({"op": "unknown", "id": o.order_id, "ts": now, "reason": "restart: no ack, or taker in flight"})
        self.books: dict[str, Book] = {}
        self.starts: dict[str, int] = {}     # cid -> start_ms, as RiskKernel.starts (MarketInfo has no start field)
        self.reasons: dict[str, str] = {}    # rejected / cancelled order id -> why
        self.cancel_all_ms: int | None = None
        self._tripped: set[str] = set()      # order ids already counted in a 30 s trip
        self.recon_fills: list[Fill] = []    # journaled by reconcile_venue; the loop records them to the ledger
        self._seq = 0
        # 15 Nov: where do the seconds go between a signal and a match? Wall-clock stamps of each step, the venue's raw
        # answer and the raw trade events of our orders. Best effort, never fsync'd, never replayed.
        self.timing_path = self.path.with_name("order_timing.jsonl")

    def _time(self, e: dict) -> None:
        try:
            with open(self.timing_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(e, separators=(",", ":"), default=str) + "\n")
        except OSError:
            pass

    # ---- journal and state --------------------------------------------------------------------------------------
    def _log(self, e: dict) -> None:
        self._f.write(json.dumps(e, separators=(",", ":")) + "\n")
        self._f.flush()
        os.fsync(self._f.fileno())  # raises on a failed write: the change never takes effect, the caller halts
        self.state.apply(e)

    @property
    def positions(self) -> dict[str, float]:
        return self.state.positions

    def open_orders(self) -> list[Order]:
        """Non-terminal orders, unknown included (the kernel counts them as filled)."""
        return [o for o in self.state.orders.values() if o.status in OPEN]

    def _fill(self, o: Order, size: float, price: float, ts: int, maker: bool, trades=()) -> Fill:
        m = self.markets.get(o.intent.cid)
        f = Fill(o.order_id, o.intent.strategy, o.intent.cid, o.intent.token_id, o.intent.side, price, size, ts, maker,
                 0.0 if maker or m is None else fee(size, price, m.fee_rate))
        e = {"op": "fill", "id": o.order_id, "fill": dataclasses.asdict(f), "trades": list(trades)}
        self._log(e)
        self.trades.update(trades)
        for t in trades:
            self.booked.setdefault(t, []).append(e)
        return f

    def _spent(self, order_id: str) -> float:
        """USDC already booked on this order (its fills' size x price)."""
        return sum(f.size * f.price for f in self.state.fills if f.order_id == order_id)

    # ---- order rules (as paper) ---------------------------------------------------------------------------------
    def _check(self, i: Intent, m: MarketInfo | None, now_ms: int, batch: list[Intent]) -> str | None:
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
            offered += sum(b.size for b in batch if b.token_id == i.token_id and b.side == "SELL")
            if i.size > self.positions.get(i.token_id, 0.0) - offered + EPS:
                return "sell exceeds the position not already offered"
        if i.kind == "maker":
            bk = self.books.get(i.token_id)
            opp = (bk.asks if i.side == "BUY" else bk.bids) if bk else []
            if opp and (i.price >= opp[0][0] - EPS if i.side == "BUY" else i.price <= opp[0][0] + EPS):
                return "post-only order would cross"
        elif i.expiry_ms <= now_ms:
            return "taker past its give-up deadline"
        elif i.side == "BUY" and i.price * i.size < MIN_BUY_NOTIONAL - EPS:
            # 16 Nov: the venue answers 400 for the WHOLE batch, which killed the valid other leg too: refuse it here
            return f"under Polymarket's ${MIN_BUY_NOTIONAL:.2f} minimum for a marketable buy ({i.price * i.size:.2f})"
        elif i.side == "BUY" and not buy_amounts_ok(i.size, i.price):
            # 18 Nov: the venue refuses it anyway ("maker amount supports a max accuracy of 2 decimals"); refusing it
            # here saves the round trip and keeps it out of the batch
            return f"size x limit not in whole cents ({i.size:g} x {i.price:g}); the venue would refuse it"
        return None

    # ---- Router -------------------------------------------------------------------------------------------------
    def submit(self, intent: Intent, now_ms: int) -> Order:
        return self.submit_batch([intent], now_ms)[0]

    def submit_batch(self, intents: list[Intent], now_ms: int) -> list[Order]:
        if len(intents) > MAX_BATCH:
            raise ValueError(f"batch of {len(intents)} orders; the CLOB takes at most {MAX_BATCH}")
        out, send, accepted = [], [], []  # send: (order id, intent, payload, order type, queue ahead)
        t = {"decision_ms": now_ms, "enter_ms": common.now_ms(), "sign_ms": []}
        for i in intents:
            m, reason = self.markets.get(i.cid), None
            if m:
                i = dataclasses.replace(i, price=round_price(i.price, m.tick_size, i.side), size=round_size(i.size))
                if i.kind == "maker":
                    exp = gtd_expiry_ms(i.expiry_ms, m.end_ms, self.starts.get(i.cid), now_ms)
                    if exp is None:
                        reason = "GTD expiry leaves under 2 min + margin (after the start and close bounds)"
                    else:
                        i = dataclasses.replace(i, expiry_ms=exp)
            reason = reason or self._check(i, m, now_ms, accepted)
            if reason:
                self._seq += 1
                oid = f"rejected-{self._seq}"
                self.reasons[oid] = reason
                out.append(Order(oid, i, "rejected", 0.0, now_ms))
                continue
            otype = "GTD" if i.kind == "maker" else "FAK"
            s0 = common.now_ms()
            oid, payload = self.signer.sign(i, m, i.expiry_ms // 1000 if otype == "GTD" else 0, otype)
            t["sign_ms"].append(common.now_ms() - s0)
            bk = self.books.get(i.token_id)
            q = next((s for p, s in (bk.bids if i.side == "BUY" else bk.asks) if abs(p - i.price) < EPS), 0.0) if bk else 0.0
            send.append((oid, i, payload, otype, q))
            accepted.append(i)
            out.append(oid)
        t["signed_ms"] = common.now_ms()
        for oid, i, _, otype, q in send:  # write-ahead: every new line is on disk before the post
            self._log({"op": "new", "id": oid, "ts": now_ms, "intent": dataclasses.asdict(i), "queue_ahead": q,
                       "expiration": i.expiry_ms // 1000 if otype == "GTD" else 0, "order_type": otype})
        t["journaled_ms"] = common.now_ms()
        if send:
            self._post(send, now_ms, t)
        return [self.state.orders[o] if isinstance(o, str) else o for o in out]

    def _post(self, send: list, now_ms: int, t: dict | None = None) -> None:
        why = "no result for this order"
        t = t if t is not None else {"decision_ms": now_ms}
        t["post_start_ms"] = common.now_ms()
        res = None
        try:
            try:
                res = self.client.post_orders([(p, ot) for _, _, p, ot, _ in send], post_only=True)
            finally:
                t["post_end_ms"] = common.now_ms()
                self._time({"kind": "post", **t, "orders": [{"id": oid, "cid": i.cid, "token": i.token_id,
                                                              "limit": i.price, "size": i.size, "reason": i.reason}
                                                             for oid, i, *_ in send], "response": res})
        except (LiveGuardError, CredentialsMissing) as e:  # raised before the transport: nothing was sent
            for oid, *_ in send:
                self._log({"op": "cancel", "id": oid, "ts": now_ms, "reason": f"not sent: {e}"})
            raise
        except VenueError as e:
            explicit = 400 <= e.status < 500 and e.status != 408
            res = [{"success": False, "errorMsg": str(e)}] * len(send) if explicit else []
            why = str(e)
        except Exception as e:  # timeout, connection reset, ...: the venue may have it
            res, why = [], f"post failed: {type(e).__name__}"
        res = res if isinstance(res, list) else []
        for k, (oid, *_rest) in enumerate(send):
            item = res[k] if k < len(res) else None
            if not isinstance(item, dict):
                self._log({"op": "unknown", "id": oid, "ts": now_ms, "reason": why})
            elif item.get("success") is False or item.get("errorMsg") or item.get("error"):
                self.reasons[oid] = str(item.get("errorMsg") or item.get("error") or "rejected")
                self._log({"op": "cancel", "id": oid, "ts": now_ms, "reason": self.reasons[oid]})
            elif str(item.get("orderID") or "").lower() == oid.lower():
                self._log({"op": "ack", "id": oid, "ts": now_ms})
            else:
                self._log({"op": "unknown", "id": oid, "ts": now_ms, "reason": "accepted under another venue id"})

    def cancel(self, order_id: str, now_ms: int | None = None) -> None:
        """Cancel by id; journaled once the venue confirms it (else poll / reconcile resolves it)."""
        o = self.state.orders.get(order_id)
        if not o or o.status not in OPEN:
            return
        try:
            r = self.client.cancel(order_id)
        except Exception as e:
            log.warning("cancel %s: %s", order_id[:12], type(e).__name__)
            return
        if isinstance(r, dict) and order_id in (r.get("canceled") or []) and o.status in OPEN:
            self._log({"op": "cancel", "id": order_id, "ts": now_ms or common.now_ms(), "reason": "cancelled"})

    def cancel_all(self, now_ms: int | None = None) -> None:
        now = now_ms or common.now_ms()
        try:
            r = self.client.cancel_all()
        except Exception as e:
            log.warning("cancel-all: %s", type(e).__name__)
            return
        self.cancel_all_ms = now
        for oid in (r.get("canceled") or []) if isinstance(r, dict) else []:
            o = self.state.orders.get(oid)
            if o and o.status in OPEN:
                self._log({"op": "cancel", "id": oid, "ts": now, "reason": "cancel-all"})

    def on_book(self, book: Book, now_ms: int) -> list[Fill]:
        self.books[book.token_id] = book  # queue_ahead and the post-only pre-check
        return []

    def on_trade(self, token_id: str, price: float, size: float, taker_side: str, ts_ms: int) -> list[Fill]:
        return []  # live fills arrive only through on_user_event (or poll / reconcile queries)

    # ---- resolution ---------------------------------------------------------------------------------------------
    def _resolve(self, o: Order, rec, now_ms: int) -> list[Fill]:
        """Journal what GET /data/order/<id> reports (mapping in the module docstring)."""
        st = venue_status(rec)
        if not st:
            return []
        fills = []
        delta = round_size(min(_num(rec.get("size_matched")), o.intent.size) - o.filled)
        if delta >= 0.01:
            fills.append(self._fill(o, delta, o.intent.price, now_ms, o.intent.kind == "maker",
                                    rec.get("associate_trades") or ()))
        taker = o.intent.kind == "taker"
        if o.status not in OPEN:
            pass
        elif st.startswith("CANCEL") or st == "INVALID":
            self._log({"op": "done" if taker else "cancel", "id": o.order_id, "ts": now_ms, "reason": f"venue {st}"})
        elif st == "EXPIRED":
            self._log({"op": "expire", "id": o.order_id, "ts": now_ms})
        elif st == "MATCHED":
            self._log({"op": "done", "id": o.order_id, "ts": now_ms})
        return fills

    def poll(self, now_ms: int) -> list[Fill]:
        # ponytail: cancel + query on every call; space them out if the venue rate-limits (unknown orders are rare)
        fills = []
        pending = [o for o in self.open_orders() if now_ms - o.created_ms >= RESOLVE_AFTER_MS
                   and (o.status in ("unknown", "journaled") or (o.intent.kind == "taker" and o.status in ("open", "partial")))]
        for o in pending:
            try:
                self.client.cancel(o.order_id)
            except Exception as e:
                log.warning("poll cancel %s: %s", o.order_id[:12], type(e).__name__)
            try:
                rec = self.client.get_order(o.order_id)
            except Exception as e:
                log.warning("poll query %s: %s", o.order_id[:12], type(e).__name__)
                rec = None
            fills += self._resolve(o, rec, now_ms)
        late = [o for o in pending if o.status in OPEN and now_ms - o.created_ms >= HALT_AFTER_MS
                and o.order_id not in self._tripped]
        if late:
            self._tripped.update(o.order_id for o in late)
            self.trip("global", f"{len(late)} order(s) unresolved {HALT_AFTER_MS // 1000} s after submission", "router")
            self.cancel_all(now_ms)
        return fills

    def on_user_event(self, msg: dict, now_ms: int | None = None) -> list[Fill]:
        now, orders = now_ms or common.now_ms(), self.state.orders
        et, fills = str(msg.get("event_type") or "").lower(), []
        if et == "trade":
            tid, st = str(msg.get("id") or ""), str(msg.get("status") or "").upper()
            legs = [(msg.get("taker_order_id"), _num(msg.get("size")), _num(msg.get("price")), False)]
            legs += [(mo.get("order_id"), _num(mo.get("matched_amount")), _num(mo.get("price")), True)
                     for mo in msg.get("maker_orders") or [] if isinstance(mo, dict)]
            if st == "FAILED":
                return self._failed(tid, legs, now)
            if any(oid in orders for oid, *_ in legs):
                self._time({"kind": "trade_event", "recv_ms": now, "msg": msg})   # every status of our trades
            if not tid or tid in self.trades:
                return []  # later status updates of a trade already journaled add nothing
            # match_time is the documented field (15 Nov); matchtime was our old reading of it
            raw = _num(msg.get("match_time") or msg.get("matchtime") or msg.get("timestamp"))
            ts = int(raw * 1000 if raw < 1e11 else raw) or now  # seconds in the docs, milliseconds on the wire (12 Nov)
            for oid, size, price, maker in legs:
                o = orders.get(oid)
                if o and not maker and o.intent.side == "BUY" and o.intent.kind == "taker" and price > 0:
                    # 18 Nov (bug fix): a marketable BUY spends size x limit USDC and gets MORE shares when it matches
                    # under the limit (venue trade events: 5 @ 0.84 -> 5.25 shares at 0.80). Book what the venue
                    # delivered, capped by the USDC the order may still spend, not by the share count asked for
                    # (that cap under-booked ~37 shares and over-stated cash 12-18 Nov).
                    left = o.intent.size * o.intent.price - self._spent(o.order_id)
                    size = math.floor(min(size, max(0.0, left) / price) * 1e6 + 1e-6) / 1e6
                else:
                    size = round_size(min(size, o.intent.size - o.filled)) if o else 0.0  # never past the order's size
                if size >= 0.01:
                    fills.append(self._fill(o, size, price, ts, maker, [tid]))
        elif et == "order":
            o, typ = orders.get(msg.get("id")), str(msg.get("type") or "").upper()
            if o and o.status in OPEN:
                if typ == "CANCELLATION":
                    self._log({"op": "cancel", "id": o.order_id, "ts": now, "reason": "venue cancellation"})
                elif typ == "PLACEMENT" and o.status in ("journaled", "unknown"):
                    self._log({"op": "ack", "id": o.order_id, "ts": now})
        return fills

    def _failed(self, tid: str, legs: list, now: int) -> list[Fill]:
        """A trade that matched off-chain but FAILED on-chain (arXiv 2606.16852: attackers revert fills on purpose).
        Reverts the fills booked for it and halts only its market(s), so one revert cannot stop every strategy.
        A FAILED we cannot tie to any of our markets still halts globally."""
        booked = self.booked.pop(tid, [])
        if booked:
            for e in booked:
                self._log({"op": "revert", "id": e["id"], "fill": e["fill"], "trades": [tid], "ts": now})
        elif tid and tid not in self.trades:
            self._log({"op": "failed", "trades": [tid], "ts": now})  # a MATCHED arriving after this books nothing
        self.trades.add(tid)
        cids = {e["fill"]["cid"] for e in booked} or {self.state.orders[oid].intent.cid for oid, *_ in legs
                                                      if oid in self.state.orders}
        for scope in sorted(cids) or ["global"]:
            self.trip(scope, f"trade {tid} FAILED on-chain ({len(booked)} fill(s) reverted)", "reconciler")
        return []

    def reconcile_venue(self, venue_open: list, now_ms: int | None = None) -> list[str]:
        """venue_open: GET /data/orders rows (or ids). Returns one line per mismatch."""
        now = now_ms or common.now_ms()
        ids = {v.get("id") if isinstance(v, dict) else v for v in venue_open}
        mine = {o.order_id: o for o in self.open_orders()}
        out = []
        for vid in sorted(i for i in ids if i not in mine):
            out.append(f"open at the venue, not open in the journal: {vid}")
            self.trip("global", out[-1], "reconciler")
            try:
                self.client.cancel(vid)
            except Exception as e:
                log.warning("reconcile cancel %s: %s", str(vid)[:12], type(e).__name__)
        for oid, o in mine.items():
            if oid in ids:
                continue
            try:
                rec = self.client.get_order(oid)
            except Exception as e:
                log.warning("reconcile query %s: %s", oid[:12], type(e).__name__)
                rec = None
            got = self._resolve(o, rec, now)
            self.recon_fills.extend(got)  # the loop must record these: memory has them, the ledger does not yet
            if o.status in OPEN and self.cancel_all_ms is not None and o.created_ms <= self.cancel_all_ms:
                self._log({"op": "cancel", "id": oid, "ts": now, "reason": "absent at the venue after cancel-all"})
            out.append(f"open in the journal, absent at the venue: {oid} -> {o.status}")
        return out

    def confirm_zero_open(self) -> bool:
        """True only when the venue reports zero open orders and the journal has no non-terminal order."""
        try:
            venue = self.client.open_orders()
        except Exception as e:
            log.warning("confirm zero open: %s", type(e).__name__)
            return False
        self.reconcile_venue(venue)
        return not venue and not self.open_orders()
