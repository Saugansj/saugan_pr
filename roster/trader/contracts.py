"""Shared types and interfaces for the Phase 1 trader. Owned by the orchestrator: work packages import this, never edit it.

Flow (wired by trader/loop.py, WP1-F):
  marketdata (08/09/07) -> engines (ladder-maker, btc-speed) -> Intent -> kernel.check (01/02) -> router.submit (05, paper)
  -> Fill -> reconciler (14) + ledger (15) + audit log (04)
Maker engines return their *target* resting set each tick; the loop diffs targets against live orders (cancel what is no
longer wanted, kernel-check and submit what is new). Taker engines return immediate intents.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Protocol

Side = Literal["BUY", "SELL"]
Kind = Literal["maker", "taker"]
OrderStatus = Literal["journaled", "open", "partial", "filled", "cancelled", "expired", "rejected", "unknown"]


class TradingState(str, Enum):
    ACTIVE = "ACTIVE"      # all order types within caps
    REDUCING = "REDUCING"  # only exposure-reducing orders
    HALTED = "HALTED"      # cancels only


@dataclass(frozen=True)
class MarketInfo:
    """One market from role 07's latest crawler snapshot (data/markets/*.jsonl)."""
    cid: str
    token_yes: str
    token_no: str
    mode: str               # crypto-term | crypto-hourly | crypto-fast | sports-pregame
    question: str
    rules_sha256: str
    tick_size: float
    min_size: float
    fee_rate: float         # taker fee rate; fee per share = fee_rate * p * (1 - p)
    neg_risk: bool
    end_ms: int             # market close / settlement time
    event_group: str        # role 01 exposure key, e.g. "BTC@2026-10-02T16:00Z" or "BTC-5m@<start>"
    asset: str | None = None      # "BTC" | "ETH" for crypto
    strike: float | None = None   # strike in USDT for "above $X" markets
    kind: str = ""                # "strike" | "updown"
    source_id: str = ""           # resolution source parsed from the rules text


@dataclass
class Book:
    """Role 08 view of one token's order book. Levels are (price, size), best first."""
    token_id: str
    bids: list[tuple[float, float]]
    asks: list[tuple[float, float]]
    ts_ms: int                                   # local receive time of the last update
    own: dict[float, float] = field(default_factory=dict)  # our resting size by price (excluded from mid)

    def best_bid(self) -> float | None:
        return self.bids[0][0] if self.bids else None

    def best_ask(self) -> float | None:
        return self.asks[0][0] if self.asks else None

    def mid_ex_own(self) -> float | None:
        """Mid with our own resting size removed from each side (levels left empty are skipped)."""
        def first(levels):
            for p, s in levels:
                if s - self.own.get(p, 0.0) > 1e-9:
                    return p
            return None
        b, a = first(self.bids), first(self.asks)
        return None if b is None or a is None else (a + b) / 2


@dataclass(frozen=True)
class Intent:
    """An order an engine wants. Engines never size above role 23's output and never bypass the kernel."""
    strategy: str           # "ladder-maker" | "btc-speed"
    cid: str
    token_id: str
    side: Side
    price: float
    size: float             # shares
    kind: Kind
    expiry_ms: int          # GTD expiry for makers; give-up deadline for takers
    fair: float             # engine's fair probability for this token
    reason: str
    versions: tuple = ()    # (name, version) pairs from the registry used for this decision
    reduces_exposure: bool = False


@dataclass(frozen=True)
class Decision:
    approved: bool
    reason: str
    binding_cap: str | None = None


@dataclass
class Order:
    order_id: str           # EIP-712-style hash of the intent fields (paper: sha256), journaled before "sending"
    intent: Intent
    status: OrderStatus
    filled: float = 0.0
    created_ms: int = 0
    queue_ahead: float = 0.0  # maker: book size ahead of us at posting (strict fill model)


@dataclass(frozen=True)
class Fill:
    order_id: str
    strategy: str
    cid: str
    token_id: str
    side: Side
    price: float
    size: float
    ts_ms: int
    maker: bool
    fee: float              # USD paid (0 for makers)


class Ledger(Protocol):
    """Role 15 (WP1-A). Bitemporal: every row has event_ms (when it happened) and recorded_ms (when we wrote it)."""
    def record(self, table: str, row: dict, event_ms: int) -> None: ...
    def as_of(self, table: str, t_ms: int) -> list[dict]: ...          # rows with recorded_ms <= t_ms only
    def registry_live(self, name: str) -> dict: ...                     # live version of a parameter set
    def preregister(self, test: dict) -> None: ...                      # immutable once written


class Kernel(Protocol):
    """Role 01 + 02 (WP1-B)."""
    state: TradingState
    def check(self, intent: Intent, ctx: "KernelContext") -> Decision: ...
    def trip(self, scope: str, reason: str, source: str) -> None: ...  # AI sources are capped at REDUCING


@dataclass
class KernelContext:
    now_ms: int
    markets: dict[str, MarketInfo]          # by cid
    books: dict[str, Book]                  # by token_id
    positions: dict[str, float]             # token_id -> shares held
    open_orders: list[Order]
    clearances: dict[str, dict]             # template key -> clearance record (from advice.db)
    bankroll_usd: float                     # redeemable pUSD + positions at best bid
    feed_age_ms: dict[str, int]             # feed name -> ms since last update


class Router(Protocol):
    """Role 05 in paper mode (WP1-C). Live mode is impossible in Phase 1."""
    def submit(self, intent: Intent, now_ms: int) -> Order: ...
    def cancel(self, order_id: str, now_ms: int) -> None: ...
    def cancel_all(self, now_ms: int) -> None: ...
    def on_book(self, book: Book, now_ms: int) -> list[Fill]: ...
    def on_trade(self, token_id: str, price: float, size: float, taker_side: Side, ts_ms: int) -> list[Fill]: ...
    def open_orders(self) -> list[Order]: ...


class Engine(Protocol):
    """Role 17/20/23 bundle (WP1-D) or the speed engine (WP1-E). Pure decisions, no I/O."""
    name: str
    def on_tick(self, now_ms: int, markets: dict[str, MarketInfo], books: dict[str, Book], ref: dict,
                positions: dict[str, float]) -> list[Intent]: ...
    # ref = {"BTC": {"price": float, "ts_ms": int, "dvol": float | None, "final": {settle_ms: price}}, "ETH": {...}}
