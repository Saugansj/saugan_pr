"""sports-maker engine (WW-C, flag `sports`): soccer 1X2 maker bids from sports.fair and sports.pulls, quoted and
sized with Phase 1's ladder functions (role 20 quotes, role 23 shrink + invariant). Pure decisions, paper only.

Per tick and mapped market (WP4-B's wiring notes): fair from the latest sharp (SportsGameOdds, keyed) snapshot, the
continuous sources and quote gate, then pulls.pull_reasons; any reason = no quotes. Without the SGO key there is no
sharp snapshot, so fair is None and the market is pulled (fail closed). Expiry <= pulls.maker_expiry(start, end).

Inputs the loop sets (WW-D), all empty by default: maps {cid: MarketMap}, sharp and continuous [OddsSnapshot],
methods (sports-devig params {league: method}), game_states {event_key: GameState}, lineups {event_key: ms},
cautions [CautionSignal] in arrival order, feed_age_ms {"polymarket", "sports"}. Call on_fill for every fill.
`last_pulls` {cid: reasons} is the latest pull list per mapped market, for reports.
"""
from trader.contracts import Book, Fill, Intent, MarketInfo
from trader.engines.ladder import PARAMS as LADDER, _pos, invariant_ok, quotes, shrink

NAME = "sports-maker"
VERSION = 1
VERSIONS = ((NAME, VERSION), ("sports-sigma", 1))
PARAMS = {**{k: LADDER[k] for k in ("c_shrink", "half_min", "k_unc", "k_skew", "quote_size", "max_inv",
                                    "complement_margin", "max_book_width")},
          "ttl_step_ms": 5 * 60_000}
REGISTRY = {NAME: {"version": VERSION, "state": "candidate", "params": PARAMS}}


class SportsMakerEngine:
    name = NAME

    def __init__(self, params: dict | None = None):
        self.p = {**PARAMS, **(params or {})}
        self.maps: dict[str, dict] = {}
        self.sharp: list[dict] = []
        self.continuous: list[dict] = []
        self.methods: dict[str, str] = {}
        self.game_states: dict[str, dict] = {}
        self.lineups: dict[str, int] = {}
        self.cautions: list = []
        self.feed_age_ms: dict[str, int] = {}
        self.cost: dict[str, tuple[float, float]] = {}  # token -> (shares, avg cost) of our buys
        self.last_pulls: dict[str, list[str]] = {}
        self.records: list[tuple[str, dict, int]] = []

    def on_fill(self, fill: Fill) -> None:
        if fill.strategy == NAME and fill.side == "BUY" and fill.size > 0:
            n, c = self.cost.get(fill.token_id, (0.0, 0.0))
            self.cost[fill.token_id] = (n + fill.size, (n * c + fill.size * fill.price) / (n + fill.size))

    def on_tick(self, now_ms: int, markets: dict[str, MarketInfo], books: dict[str, Book], ref: dict,
                positions: dict[str, float]) -> list[Intent]:
        from sports import fair, pulls                   # lazy: pandas/penaltyblog load only with the flag on
        for t, (n, c) in list(self.cost.items()):        # merges and redemptions shrink positions without fills
            held = positions.get(t, 0.0)
            if held <= 1e-9:
                del self.cost[t]
            elif held < n:
                self.cost[t] = (held, c)
        out = []
        for cid, mm in self.maps.items():
            m = markets.get(cid)
            if m is None or m.token_yes != mm.get("token_yes") or now_ms >= m.end_ms:
                continue
            f = fair.fair(mm, self.sharp, self.methods, now_ms)
            cs = fair.continuous_sources(mm, self.continuous, self.methods, now_ms)
            gate = fair.quote_allowed(f["fair"], f["sigma"], cs, now_ms)
            ek = mm["event_key"]
            reasons = pulls.pull_reasons(now_ms, mm, self.game_states.get(ek), self.lineups.get(ek), f["obs_ms"],
                                         self.cautions, self.feed_age_ms, gate)
            self.last_pulls[cid] = reasons
            if not reasons:
                out += self._quote(m, f["fair"], f["sigma"], books.get(m.token_yes), books.get(m.token_no),
                                   positions, min(pulls.maker_expiry(mm["start_ms"], m.end_ms),
                                                  (now_ms // self.p["ttl_step_ms"] + 2) * self.p["ttl_step_ms"]),
                                   now_ms)
        return out

    def _quote(self, m: MarketInfo, f, sigma, yes: Book | None, no: Book | None, positions: dict, expiry: int,
               now_ms: int) -> list[Intent]:
        p = self.p
        if yes is None or no is None or not _pos(f, sigma) or f >= 1 or expiry <= now_ms:
            return []
        mid = yes.mid_ex_own()
        if mid is None or 2 * (yes.best_ask() - mid) > p["max_book_width"]:
            return []
        q = shrink(f, mid, p["c_shrink"])
        if not invariant_ok(q, f, mid):
            return []
        net = positions.get(m.token_yes, 0.0) - positions.get(m.token_no, 0.0)
        half = p["half_min"] + p["k_unc"] * sigma
        cost = {t: c for t, (_, c) in self.cost.items()}
        out = []
        for token, px, size, reduces in quotes(q, half, net, cost, m, (yes.best_ask(), no.best_ask()), p):
            ff, mm, qq = (f, mid, q) if token == m.token_yes else (1 - f, 1 - mid, 1 - q)
            out.append(Intent(NAME, m.cid, token, "BUY", px, size, "maker", expiry, qq,
                              f"{'complement' if reduces else 'quote'} f={ff} m={mm} q={qq} half={half:.4f} "
                              f"net={net:g}", VERSIONS, reduces))
        return out
