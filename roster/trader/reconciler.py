"""Inventory reconciler, paper mode (WP1-C; build-plan 1.7, role 14).

Positions and open orders are rebuilt independently from the journal on disk (and, when the loop passes them, from
the ledger's fills) and compared with the router's in-memory state. Any mismatch trips a breaker through
Kernel.trip("global", reason, "reconciler"). Run reconcile() on every restart and continuously while running.
On a restart, resolve_unknown() cancels every unknown order by id (the paper venue never received it), which is
what lets the router accept orders on that token and side again. merge_pairs() merges completed YES+NO pairs back
into pUSD at once (simulated) and returns the locked edge of each merge.
"""
from trader.contracts import Fill
from trader.router import PaperRouter, replay, round_size

TOL = 1e-6


def positions_from(fills: list[Fill], merges: list[dict]) -> dict[str, float]:
    pos: dict[str, float] = {}
    for f in fills:
        pos[f.token_id] = pos.get(f.token_id, 0.0) + (f.size if f.side == "BUY" else -f.size)
    for mg in merges:
        for t in (mg["yes"], mg["no"]):
            pos[t] = pos.get(t, 0.0) - mg["size"]
    return pos


def _key(o):
    return o and (o.status, round(o.filled, 6))


def _diff(name: str, a: dict, b: dict) -> list[str]:
    return [f"{name} {k[:12]}: {a.get(k, 0.0):g} vs {b.get(k, 0.0):g}"
            for k in set(a) | set(b) if abs(a.get(k, 0.0) - b.get(k, 0.0)) > TOL]


class Reconciler:
    def __init__(self, router: PaperRouter, trip):
        """trip: Kernel.trip(scope, reason, source)."""
        self.router, self.trip = router, trip

    def reconcile(self, fills: list[Fill] | None = None) -> list[str]:
        """Mismatches between the router's memory, the journal on disk and (if given) the ledger's fills; trips on any."""
        # ponytail: replays the whole journal each call; replay from a byte offset if the 14-day journal makes it slow
        mem, disk = self.router.state, replay(self.router.path)
        bad = [f"order {oid[:12]}: memory {_key(mem.orders.get(oid))} vs journal {_key(disk.orders.get(oid))}"
               for oid in set(mem.orders) | set(disk.orders) if _key(mem.orders.get(oid)) != _key(disk.orders.get(oid))]
        bad += _diff("position (journal)", mem.positions, disk.positions)
        if fills is not None:
            bad += _diff("position (fills)", mem.positions, positions_from(fills, mem.merges))
        if bad:
            self.trip("global", f"reconcile mismatch ({len(bad)}): " + "; ".join(sorted(bad)[:5]), "reconciler")
        return bad

    def resolve_unknown(self, now_ms: int) -> list[str]:
        ids = [o.order_id for o in self.router.open_orders() if o.status == "unknown"]
        for oid in ids:
            self.router.cancel(oid, now_ms)
        return ids

    def confirm_zero_open(self) -> bool:
        """A halt is complete only when this is True."""
        return not self.router.open_orders()

    def merge_pairs(self, now_ms: int) -> list[dict]:
        pos, out = self.router.positions, []
        offered = {}
        for o in self.router.open_orders():
            if o.intent.side == "SELL":
                offered[o.intent.token_id] = offered.get(o.intent.token_id, 0.0) + o.intent.size - o.filled
        for cid, m in self.router.markets.items():
            n = round_size(min(pos.get(t, 0.0) - offered.get(t, 0.0) for t in (m.token_yes, m.token_no)))
            if n > 0:
                out.append(self.router.merge(cid, n, now_ms))
        return out
