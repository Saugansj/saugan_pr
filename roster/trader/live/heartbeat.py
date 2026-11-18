"""Role 03 heartbeat warden (task 2.1) and the external dead-man ping (task 2.2).

The loop sends Polymarket's CLOB heartbeat at the end of a tick only when health_failures() is empty. The venue cancels
every order ~10 s after the last heartbeat, so a hung or unhealthy loop clears its resting orders on the server side.
HALTED = cancel-all every 2 s until zero open orders is confirmed; no confirmation within 10 s latches `stopped` (no
heartbeat until rearm()). The venue calls (send, cancel_all, confirm_zero_open) are injected; nothing here holds keys.
"""
import logging
import os
import urllib.parse
import urllib.request

from trader.contracts import Book, Order, TradingState
from trader.kernel import LIVE, STALE_MS
from trader.live.clock import HALT_MS

log = logging.getLogger(__name__)
MAX_TICK_MS = 2_000
UNKNOWN_FEED_MS = 10_000  # as the kernel: a feed name without a STALE_MS entry gets 10 s
HALTED_CHECK = "halted"   # the entry health_failures() adds while HALTED; end_of_tick() reads it to end a halt episode


def _over(x, bound) -> bool:
    """True when x is missing, NaN or above bound."""
    return x is None or not x <= bound


def health_failures(now_ms: int, tick_ms: float, ws_connected: bool, reconcile_clean: bool, open_orders: list[Order],
                    books: dict[str, Book], feed_age_ms: dict[str, int], journal_ok: bool, audit_ok: bool,
                    clock_offset_ms: float | None, state: TradingState) -> list[str]:
    """One "<check>: detail" entry per failing check; [] means the heartbeat may be sent."""
    out = []
    if _over(tick_ms, MAX_TICK_MS):
        out.append(f"tick: {tick_ms} ms > {MAX_TICK_MS} ms")
    if not ws_connected:
        out.append("user_ws: disconnected")
    if not reconcile_clean:
        out.append("reconcile: last reconcile not clean")
    for tok in sorted({o.intent.token_id for o in open_orders if o.status in LIVE}):
        b = books.get(tok)
        if b is None:
            out.append(f"book: {tok} has a resting order and no book")
        elif _over(now_ms - b.ts_ms, STALE_MS["polymarket"]):
            out.append(f"book: {tok} stale ({now_ms - b.ts_ms} ms)")
    for name, age in sorted(feed_age_ms.items()):
        if _over(age, STALE_MS.get(name.split(":")[0], UNKNOWN_FEED_MS)):
            out.append(f"feed: {name} stale ({age} ms)")
    if not journal_ok:
        out.append("journal: last journal write failed")
    if not audit_ok:
        out.append("audit: last audit write failed")
    if _over(None if clock_offset_ms is None else abs(clock_offset_ms), HALT_MS):
        out.append(f"clock: offset {clock_offset_ms} ms unknown or > {HALT_MS} ms")
    if state == TradingState.HALTED:
        out.append(f"{HALTED_CHECK}: state is HALTED")
    return out


class HeartbeatWarden:
    def __init__(self, send, cancel_all, confirm_zero_open, retry_ms: int = 2_000, stop_after_ms: int = 10_000):
        self.send, self.cancel_all, self.confirm_zero_open = send, cancel_all, confirm_zero_open
        self.retry_ms, self.stop_after_ms = retry_ms, stop_after_ms
        self.hb_id, self.stopped, self.sent, self.errors, self.last_error = "", False, 0, 0, None
        self._halt_start = self._last_cancel = None
        self._confirmed = False

    def _err(self, what: str, e: Exception) -> None:
        self.errors += 1
        self.last_error = f"{what}: {type(e).__name__}"  # type only: a venue message is not ours to log
        log.warning("heartbeat warden %s", self.last_error)

    def end_of_tick(self, now_ms: int, failures: list[str]) -> bool:
        """Send one heartbeat if healthy and not latched. Returns whether it was sent; never raises."""
        if not any(f.startswith(HALTED_CHECK) for f in failures):  # a tick outside HALTED ends the halt episode
            self._halt_start, self._last_cancel, self._confirmed = None, None, False
        if failures or self.stopped:
            return False
        try:
            resp = self.send(self.hb_id)
        except Exception as e:
            self._err("send", e)
            return False
        if isinstance(resp, dict):
            self.hb_id = str(resp.get("heartbeat_id") or self.hb_id)
        elif isinstance(resp, str) and resp:
            self.hb_id = resp
        self.sent += 1
        return True

    def on_halted(self, now_ms: int) -> bool:
        """Call every tick while HALTED. Cancel-all now, then at most every retry_ms, until zero open is confirmed.
        Unconfirmed stop_after_ms after the halt began -> latch stopped. Returns whether zero open is confirmed."""
        if self._halt_start is None:
            self._halt_start = now_ms
        if self._confirmed:
            return True
        try:
            if self._last_cancel is None or now_ms - self._last_cancel >= self.retry_ms:
                self._last_cancel = now_ms
                self.cancel_all()
            self._confirmed = bool(self.confirm_zero_open())
        except Exception as e:  # a failed cancel-all or confirm counts as not confirmed
            self._err("halt", e)
            self._confirmed = False
        if not self._confirmed and now_ms - self._halt_start >= self.stop_after_ms and not self.stopped:
            self.stopped = True
            log.error("heartbeat warden: zero open orders not confirmed %d ms into the halt; heartbeat stopped",
                      now_ms - self._halt_start)
        return self._confirmed

    def rearm(self) -> None:
        """Human action after a halt: allow heartbeats again."""
        self.stopped, self._halt_start, self._last_cancel, self._confirmed = False, None, None, False


def freeze_drill(warden: HeartbeatWarden, healthy_failures, open_order_count, now, sleep, ticks_before_freeze: int,
                 budget_ms: int = 15_000, tick_ms: int = 1_000, poll_ms: int = 500) -> dict:
    """Healthy ticks (heartbeats sent), then the loop freezes (no end_of_tick); poll open_order_count() until zero or
    the budget is spent. now() -> ms, sleep(seconds); healthy_failures() -> the failures list of a healthy tick.
    Passes only if orders were open at the freeze (else the drill proves nothing)."""
    sent = 0
    for _ in range(ticks_before_freeze):
        sent += warden.end_of_tick(now(), healthy_failures() if callable(healthy_failures) else list(healthy_failures))
        sleep(tick_ms / 1000)
    t0 = now()
    open_at_freeze = n = open_order_count()
    while n > 0 and now() - t0 <= budget_ms:
        sleep(poll_ms / 1000)
        n = open_order_count()
    zero_after = now() - t0 if n == 0 else None
    passed = open_at_freeze > 0 and zero_after is not None and zero_after <= budget_ms
    return {"passed": passed, "zero_after_ms": zero_after, "heartbeats_sent": sent, "open_at_freeze": open_at_freeze}


def _get(url: str, timeout: float) -> None:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "roster/0.1"}), timeout=timeout):
        pass


class DeadMan:
    """External dead-man (healthchecks.io): GET the ping URL at most once per every_ms, only on a tick whose heartbeat
    was sent, so a hung or unhealthy loop stops pinging and the monitor alerts the human. No URL -> disabled, no
    network. The URL is a credential of sorts: only its host is ever logged or shown."""

    def __init__(self, url: str | None = None, every_ms: int = 60_000, get=_get):
        self._url = url or os.environ.get("ROSTER_DEADMAN_URL") or None
        self.host = urllib.parse.urlsplit(self._url).hostname if self._url else None
        self.every_ms, self.get = every_ms, get
        self.last_ms, self.pings, self.errors = None, 0, 0

    def __repr__(self) -> str:
        return f"DeadMan(host={self.host!r}, pings={self.pings}, errors={self.errors})"

    def maybe_ping(self, now_ms: int, heartbeat_sent: bool) -> bool:
        """Returns True only when a ping was sent and succeeded. Never raises."""
        if not self._url or not heartbeat_sent or (self.last_ms is not None and now_ms - self.last_ms < self.every_ms):
            return False
        self.last_ms = now_ms
        try:
            self.get(self._url, 5)
        except Exception as e:
            self.errors += 1
            log.warning("dead-man ping to %s failed: %s", self.host, type(e).__name__)
            return False
        self.pings += 1
        return True
