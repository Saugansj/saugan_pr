"""fast-updown-maker adapter (WW-C, flag `fast_maker`). Pure decisions, paper only.

Wraps growth.fast_updown.FastUpDownMaker behind its latency gate: the passing assets and their E6 edges are re-read
from the ledger (e6_edges: the single latency-e6-v1 result judged against its pre-registration) every refresh_ms.
No ledger, no result row, a failing row or an unreadable ledger = gate closed = no intents.

Wiring (WW-D): FastMakerEngine(ledger).on_tick(...) like any Engine; write fast_updown.LATENCY_PREREG, FAST_PREREG and
REGISTRY once; kernel.starts stays unset for crypto-fast markets (fast_updown's notes).
"""
from trader.contracts import Book, Intent, MarketInfo
from trader.growth import fast_updown as F

NAME = F.NAME


class FastMakerEngine:
    name = NAME

    def __init__(self, ledger=None, params: dict | None = None, refresh_ms: int = 60_000):
        self.ledger = ledger
        self.inner = F.FastUpDownMaker((), params)
        self.refresh_ms = refresh_ms
        self._checked: int | None = None

    def gate(self, now_ms: int) -> frozenset:
        """Assets whose own E6 stats pass, refreshed every refresh_ms."""
        if self._checked is None or now_ms - self._checked >= self.refresh_ms:
            self._checked = now_ms
            try:
                edges = F.e6_edges(self.ledger, now_ms) if self.ledger is not None else {}
            except Exception:                            # unreadable evidence never opens the gate
                edges = {}
            self.inner.assets, self.inner.edges = frozenset(edges), dict(edges)
        return self.inner.assets

    def on_tick(self, now_ms: int, markets: dict[str, MarketInfo], books: dict[str, Book], ref: dict,
                positions: dict[str, float]) -> list[Intent]:
        if not self.gate(now_ms):
            return []
        return self.inner.on_tick(now_ms, markets, books, ref, positions)
