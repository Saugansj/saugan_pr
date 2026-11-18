"""Role 01 risk kernel (WP1-B, task 1.14). The only gate between an engine's Intent and the paper router.

check() runs, in order: trading state -> clearance -> provenance_checks() -> resting-order (GTD) rule -> 1.1x bankroll
refusal -> per-strategy budget and per-event-group cap. Caps apply only to risk-increasing intents; whether an intent
reduces exposure is judged here from positions and open orders, never taken from the engine's flag.

Human signatures (clearances in advice.db, reset tokens) are HMAC-SHA256 under the human's key in env ROSTER_HUMAN_KEY,
the same key trader/ledger.py uses for promotions. No key -> nothing verifies -> nothing is cleared (fail closed).
Paper only: nothing here talks to a venue.
"""
import hashlib
import hmac
import json
import os
import pathlib
import sqlite3

from common import DATA
from trader.contracts import Decision, Intent, KernelContext, MarketInfo, TradingState

A, R, H = TradingState.ACTIVE, TradingState.REDUCING, TradingState.HALTED
RANK = {A: 0, R: 1, H: 2}
MIN = 60_000
ADVICE_DB = DATA / "trader" / "advice.db"
NONCES = DATA / "trader" / "used_nonces.txt"
LIVE = ("journaled", "open", "partial", "unknown")  # non-terminal orders count as filled at their worst-case price
# Sources allowed to set HALTED (T0 code, breakers, humans). Anything else, AI roles included, is capped at REDUCING.
PRIVILEGED = {"human", "kernel", "breaker", "audit", "journal", "router", "reconciler", "heartbeat", "loop"}
KEY_FIELDS = ("template", "rules_sha256", "fee_rate", "tick_size", "min_size", "neg_risk", "source_id")
# Max feed age (ms) for an intent to rely on it; feed names are "<feed>" or "<feed>:<asset>", bound looked up by <feed>.
STALE_MS = {"polymarket": 30_000, "binance": 5_000, "dvol": 180_000, "basis": 600_000}
BASIS_FEED = "basis:USDT"
# Per strategy: modes it trades (positions are attributed by mode), budget, the resolution source its engine models
# per asset, feeds it reads, and whether USD-index option inputs (Deribit DVOL) price it.
STRATEGIES = {
    "ladder-maker": {"modes": ("crypto-term",), "budget_usd": 25.0, "usd_index": True,
                     "sources": {"BTC": "binance:BTC/USDT", "ETH": "binance:ETH/USDT"},
                     "feeds": ("polymarket", "binance:{asset}", "dvol:{asset}")},
    "btc-speed": {"modes": ("crypto-fast",), "budget_usd": 25.0, "usd_index": False,
                  # Binance moves lead the Chainlink TWAP these markets settle on; ETH only in the speed_eth run
                  "sources": {"BTC": "chainlink:BTC/USD", "ETH": "chainlink:ETH/USD"},
                  "feeds": ("polymarket", "binance:{asset}")},
}
# Wiring (build/wiring/dispatch.md, WW-A): strategies added only while their feature flag is on. A source keyed by
# None (asset-less sports/negRisk markets) requires source_id == "" (no parsed source); the mode check still binds.
# "stale_ms" and "asset_feeds" override STALE_MS and "feeds" for that strategy only.
FLAG_STRATEGIES = {
    "negrisk_scan": {"negrisk-arb": {"modes": ("sports-pregame",), "budget_usd": 10.0, "usd_index": False,
                                     "sources": {None: ""}, "feeds": ("polymarket",)}},
    "fast_maker": {"fast-updown-maker": {"modes": ("crypto-fast",), "budget_usd": 5.0, "usd_index": False,
                                         "sources": {"BTC": "chainlink:BTC/USD", "ETH": "chainlink:ETH/USD"},
                                         "feeds": ("polymarket", "binance:{asset}")}},
    "sports": {"sports-maker": {"modes": ("sports-pregame",), "budget_usd": 5.0, "usd_index": False,
                                "sources": {None: ""}, "feeds": ("polymarket", "sports"),
                                "stale_ms": {"sports": 120_000}}},  # sports.pulls gamestate_stale_ms
}
# universe_ext: ladder-maker also trades SOL/XRP, priced from realised vol (no Deribit DVOL for them).
UNIVERSE_EXT = {a: f"binance:{a}/USDT" for a in ("SOL", "XRP")}


def strategies_for(features=()) -> dict:
    """STRATEGIES itself with no strategy flag on; otherwise a copy with the flagged additions."""
    features = set(features)
    if not features & ({"universe_ext"} | FLAG_STRATEGIES.keys()):
        return STRATEGIES
    out = {k: dict(v) for k, v in STRATEGIES.items()}
    if "universe_ext" in features:
        lm = out["ladder-maker"]
        lm["sources"] = {**lm["sources"], **UNIVERSE_EXT}
        lm["asset_feeds"] = {a: ("polymarket", "binance:{asset}") for a in UNIVERSE_EXT}
    for flag, add in FLAG_STRATEGIES.items():
        if flag in features:
            out.update(add)
    return out


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sign(record: dict, secret: str) -> str:
    """HMAC over every field except 'sig'."""
    body = _canon({k: v for k, v in record.items() if k != "sig"})
    return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


def verify(record: dict, secret: str) -> bool:
    return bool(secret) and hmac.compare_digest(str(record.get("sig", "")), sign(record, secret))


def clearance_key(m: MarketInfo) -> dict:
    return dict(zip(KEY_FIELDS, (f"{m.mode}:{m.asset or ''}:{m.kind}", m.rules_sha256, m.fee_rate, m.tick_size,
                                 m.min_size, m.neg_risk, m.source_id)))


def series_scope(m: MarketInfo) -> str:
    """Kernel scope of a recurring market series (the clearance template), e.g. "series:crypto-term:BTC:strike"."""
    return f"series:{m.mode}:{m.asset or ''}:{m.kind}"


def key_id(key: dict) -> str:
    """Ints become floats first, so min_size 5 and 5.0 (crawler typing) give the same id."""
    return hashlib.sha256(_canon({k: float(v) if type(v) is int else v for k, v in key.items()}).encode()).hexdigest()[:16]


def load_advice(path=ADVICE_DB) -> tuple[dict[str, dict], list[dict]]:
    """(clearances by key_id, other signed records such as reset tokens). Opens advice.db read-only; a missing file or
    an unparseable row means not cleared. Of several clearances for one key, the latest expiry wins."""
    p = pathlib.Path(path)
    if not p.exists():
        return {}, []
    con = sqlite3.connect(f"{p.resolve().as_uri()}?mode=ro", uri=True)
    try:
        raw = [r for (r,) in con.execute("SELECT rec FROM advice ORDER BY rowid")]
    finally:
        con.close()
    clear, other = {}, []
    for text in raw:
        try:
            rec = json.loads(text)
            if rec.get("type") != "clearance":
                other.append(rec)
                continue
            kid = key_id(rec["key"])
            if kid not in clear or rec["expiry_ms"] >= clear[kid]["expiry_ms"]:
                clear[kid] = rec
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
    return clear, other


def bankroll(cash_usd: float, positions: dict[str, float], books: dict) -> float:
    """Redeemable pUSD + positions marked at best bid (no bid or no book = 0)."""
    total = cash_usd
    for tok, shares in positions.items():
        b = books.get(tok)
        total += shares * ((b.best_bid() if b else None) or 0.0)
    return total


class RiskKernel:
    def __init__(self, global_cap_usd: float = 50.0, group_cap_usd: float = 10.0, strategies: dict | None = None,
                 secret: str | None = None, nonce_path=NONCES, gtd_margin_ms: int = 30_000, features=(), ledger=None):
        """features: enabled wiring flag names (trader.features). With none, behaviour is the audited Phase 1 kernel.
        ledger: required with capital_ladder (global cap = growth.capital.current_cap(ledger), re-read each minute)."""
        self.features = frozenset(features)
        self.global_cap, self.group_cap = global_cap_usd, group_cap_usd
        self.strategies = strategies_for(self.features) if strategies is None else strategies
        self.ledger, self.cap_read_ms = ledger, None
        if "capital_ladder" in self.features:
            if ledger is None:
                raise ValueError("capital_ladder needs the ledger")
            self.refresh_cap(0)
        # live_risk inputs, set by the loop: ref = md.ref, opens = {cid: Up/Down open}, printed = keeper.oracle_gap()
        self.ref, self.opens, self.printed = {}, {}, set()
        self._clock_gate = None
        self.secret = os.environ.get("ROSTER_HUMAN_KEY", "") if secret is None else secret
        self.nonce_path = pathlib.Path(nonce_path) if nonce_path else None
        self.used_nonces = set(self.nonce_path.read_text().split()) if self.nonce_path and self.nonce_path.exists() else set()
        self.gtd_margin_ms = gtd_margin_ms
        self.scopes: dict[str, TradingState] = {"global": A}  # "global", a cid (market lock), an event group or a strategy
        self.trips: list[dict] = []
        self.starts: dict[str, int] = {}     # cid -> start_ms; MarketInfo has no start field, so the loop fills this
        self.uncleared: dict[str, dict] = {}  # key_id -> {key, cid, question} seen without a clearance (to sign)

    @property
    def state(self) -> TradingState:
        return self.scopes["global"]

    # ---- states -------------------------------------------------------------------------------------------------
    def trip(self, scope: str, reason: str, source: str, level: TradingState = H) -> None:
        """Raise a scope's state (never lowers it). Sources outside PRIVILEGED are capped at REDUCING."""
        if source.split(":")[0] not in PRIVILEGED:
            level = min(level, R, key=RANK.get)
        self.scopes[scope] = max(self.scopes.get(scope, A), level, key=RANK.get)
        self.trips.append({"scope": scope, "level": level.value, "reason": reason, "source": source})

    def reset(self, scope: str, token: dict, now_ms: int) -> Decision:
        """Back to ACTIVE, only with a human-signed, unexpired reset token for this scope whose nonce was never used."""
        bad = ("signature invalid" if not verify(token, self.secret) else
               "no nonce" if not token.get("nonce") else
               "not a reset token" if token.get("type") != "reset" else
               f"token is for scope {token.get('scope')!r}" if token.get("scope") != scope else
               "token expired" if int(token.get("expiry_ms", 0)) <= now_ms else
               "nonce already used" if token["nonce"] in self.used_nonces else None)
        if bad:
            return Decision(False, f"reset refused: {bad}")
        if self.nonce_path:  # persist before acting, so a crash can't make the nonce reusable
            self.nonce_path.parent.mkdir(parents=True, exist_ok=True)
            with self.nonce_path.open("a", encoding="utf-8") as f:
                f.write(token["nonce"] + "\n")
                f.flush()
                os.fsync(f.fileno())
        self.used_nonces.add(token["nonce"])
        self.scopes[scope] = A
        self.trips.append({"scope": scope, "level": A.value, "reason": "reset", "source": f"human:{token.get('signer')}"})
        return Decision(True, f"reset {scope} by {token.get('signer')}")

    # ---- the check ------------------------------------------------------------------------------------------------
    def check(self, intent: Intent, ctx: KernelContext) -> Decision:
        m = ctx.markets.get(intent.cid)
        s = self.strategies.get(intent.strategy)
        if m is None or intent.token_id not in (m.token_yes, m.token_no):
            return Decision(False, "unknown market or token")
        if s is None:
            return Decision(False, f"unknown strategy {intent.strategy!r}")
        if m.mode not in s["modes"]:  # budgets attribute positions by mode; outside its modes they would escape it
            return Decision(False, f"{intent.strategy} does not trade mode {m.mode!r}")
        if not (0 < intent.price < 1 and intent.size > 0):
            return Decision(False, f"bad price/size {intent.price}/{intent.size}")
        state = self.scope_state(intent, m)
        reducing = self.reduces(intent, m, ctx)
        if state == H:
            return Decision(False, "HALTED: no new orders")
        if state == R and not reducing:
            return Decision(False, "REDUCING: only exposure-reducing orders")
        if intent.side == "SELL" and not reducing:
            return Decision(False, "sell exceeds shares held")
        why = self.clearance(m, ctx) or self.provenance_checks(intent, m, ctx) or self.gtd(intent, m, ctx.now_ms)
        if why:
            return Decision(False, why)
        if reducing:
            if state == R and "live_risk" in self.features:
                from trader.live.risk import reducing_rule  # lazy: trader/live stays out of the flags-off closure
                over = self.group_cap - self.exposure(ctx, lambda mk: mk.event_group == m.event_group) < 0
                why = reducing_rule(intent, m.fee_rate, over, False)  # no taker-exit token path yet: fail closed
                if why:
                    return Decision(False, why)
            return Decision(True, "reduces exposure")
        if "capital_ladder" in self.features and (self.cap_read_ms is None or ctx.now_ms - self.cap_read_ms >= MIN):
            self.refresh_cap(ctx.now_ms)
        if not ctx.bankroll_usd <= 1.1 * self.global_cap:  # written so NaN rejects
            return Decision(False, f"bankroll {ctx.bankroll_usd:.2f} > 1.1 x global cap {self.global_cap:.2f}", "global")
        room = {f"strategy:{intent.strategy}": s["budget_usd"] - self.exposure(ctx, lambda mk: mk.mode in s["modes"],
                                                                               intent.strategy),
                f"group:{m.event_group}": self.group_cap - self.exposure(ctx, lambda mk: mk.event_group == m.event_group)}
        cap = min(room, key=room.get)
        need = intent.price * intent.size
        if not need <= room[cap] + 1e-9:  # written so a NaN room (bad book) rejects
            return Decision(False, f"over {cap}: needs {need:.2f}, room {room[cap]:.2f}", cap)
        if "live_risk" in self.features:
            from trader.live.risk import check_live, worst_case_positions
            d = check_live(intent, ctx, worst_case_positions(ctx.positions, ctx.open_orders), self.ref, self.opens,
                           self.printed)
            if not d.approved:
                return d
        return Decision(True, f"within caps (tightest {cap}, room {room[cap] - need:.2f} after)", cap)

    def scope_state(self, intent: Intent, m: MarketInfo) -> TradingState:
        """Worst of global, market, event group, strategy and market series (the CUSUM markout lock's scope)."""
        return max((self.scopes.get(k, A) for k in ("global", intent.cid, m.event_group, intent.strategy,
                                                    series_scope(m))), key=RANK.get)

    # ---- wiring hooks (each a no-op unless its flag is on) ---------------------------------------------------------
    def refresh_cap(self, now_ms: int) -> None:
        """capital_ladder: global cap (and so the 1.1x refusal) = current_cap(ledger)."""
        from trader.growth.capital import current_cap
        self.global_cap, self.cap_read_ms = current_cap(self.ledger), now_ms

    def clock(self, offset_ms, measured_ms, now_ms: int, clob_offset_ms=None) -> None:
        """clock_gate: the loop's clock worker calls this with each SNTP measurement (trader.live.clock)."""
        if "clock_gate" not in self.features:
            return
        import math
        from trader.live.clock import ClockGate, clock_gate
        if not (isinstance(measured_ms, (int, float)) and math.isfinite(measured_ms)):
            measured_ms = None  # Phase 2 audit minor: a NaN timestamp must count as stale, not fresh
        self._clock_gate = self._clock_gate or ClockGate(self)
        self._clock_gate.apply(*clock_gate(offset_ms, measured_ms, now_ms, clob_offset_ms))

    def pull_ids(self, open_orders, positions: dict[str, float], markets: dict[str, MarketInfo]) -> list[str]:
        """live_risk: ids of risk-increasing live orders whose scope (any of scope_state's) is REDUCING or worse, to
        cancel through router.cancel. [] with the flag off."""
        if "live_risk" not in self.features:
            return []
        from trader.live.risk import pull_ids
        hit = {o.order_id for o in open_orders if (m := markets.get(o.intent.cid)) is None
               or self.scope_state(o.intent, m) != A}
        cids = {o.intent.cid for o in open_orders if o.order_id in hit}
        return [i for i in pull_ids(open_orders, positions, markets, cids) if i in hit]

    def reduces(self, intent: Intent, m: MarketInfo, ctx: KernelContext) -> bool:
        """Selling shares held, or buying the complement of shares held, net of every live order that already consumes
        the same holding by either route (SELL of the held token, BUY of its complement). Unknown orders count in full."""
        held_tok = intent.token_id if intent.side == "SELL" else (m.token_no if intent.token_id == m.token_yes else m.token_yes)
        comp_tok = m.token_yes if held_tok == m.token_no else m.token_no
        pending = sum(o.intent.size - (0.0 if o.status == "unknown" else o.filled) for o in ctx.open_orders
                      if o.status in LIVE and (o.intent.side, o.intent.token_id) in (("SELL", held_tok), ("BUY", comp_tok)))
        return intent.size <= ctx.positions.get(held_tok, 0.0) - pending + 1e-9

    @staticmethod
    def exposure(ctx: KernelContext, in_scope, strategy: str | None = None) -> float:
        """Worst-case USD loss: held shares at best bid (no book or no bid = 1.0, unknown) plus live BUY orders as if
        filled. SELL orders add nothing.
        ponytail: sums every leg's loss (an upper bound); net YES/NO and strike-ladder outcomes when caps bind too early."""
        by_tok = {t: mk for mk in ctx.markets.values() for t in (mk.token_yes, mk.token_no)}
        total = 0.0
        for tok, shares in ctx.positions.items():
            if shares > 0 and tok in by_tok and in_scope(by_tok[tok]):
                b = ctx.books.get(tok)
                bid = b.best_bid() if b else None
                total += shares * (1.0 if bid is None else bid)
        for o in ctx.open_orders:
            mk = ctx.markets.get(o.intent.cid)
            if (o.status in LIVE and o.intent.side == "BUY" and mk and in_scope(mk)
                    and (strategy is None or o.intent.strategy == strategy)):
                total += o.intent.price * (o.intent.size - (0.0 if o.status == "unknown" else o.filled))
        return total

    def clearance(self, m: MarketInfo, ctx: KernelContext) -> str | None:
        """Valid only if a signed, unexpired record's key equals this market's latest key (a tick change voids it)."""
        key = clearance_key(m)
        kid = key_id(key)
        rec = ctx.clearances.get(kid)
        if rec is None:
            self.uncleared.setdefault(kid, {"key": key, "cid": m.cid, "question": m.question})
            near = [[f for f in KEY_FIELDS if r["key"].get(f) != key[f]] for r in ctx.clearances.values()
                    if r.get("key", {}).get("template") == key["template"]]
            diff = min(near, key=len) if near else None
            if diff:
                return "not cleared: " + ", ".join(f"{f} changed" for f in diff)
            return f"not cleared: no clearance for {key['template']} rules {m.rules_sha256[:10]}"
        if rec.get("type") != "clearance" or rec.get("key") != key:  # never trust the dict key alone
            return "not cleared: clearance record is for a different key"
        if not verify(rec, self.secret):
            return "not cleared: clearance signature invalid"
        if int(rec.get("expiry_ms", 0)) <= ctx.now_ms:
            # list it for re-signing too, or an expired template would stop trading silently
            self.uncleared.setdefault(kid, {"key": key, "cid": m.cid, "question": m.question})
            return "not cleared: clearance expired"
        self.uncleared.pop(kid, None)
        return None

    def provenance_checks(self, intent: Intent, m: MarketInfo, ctx: KernelContext) -> str | None:
        s = self.strategies[intent.strategy]
        want = s["sources"].get(m.asset)
        if want is None or m.source_id != want:  # every Phase 1 source is non-empty, so "" never matches one
            return f"provenance: market source {m.source_id!r} != {intent.strategy} source {want!r}"
        stale = {**STALE_MS, **s.get("stale_ms", {})}
        for feed in (f.format(asset=m.asset) for f in s.get("asset_feeds", {}).get(m.asset, s["feeds"])):
            age = ctx.feed_age_ms.get(feed)
            if age is None or age > stale.get(feed.split(":")[0], 10_000):
                return f"provenance: feed {feed} stale ({age} ms)"
        if s["usd_index"] and "usdt" in m.source_id.lower():
            age = ctx.feed_age_ms.get(BASIS_FEED)
            if age is None or age > STALE_MS["basis"]:
                return f"provenance: USD-index inputs on a USDT-settled market need a fresh {BASIS_FEED} ({age} ms)"
        return None

    def gtd(self, intent: Intent, m: MarketInfo, now_ms: int) -> str | None:
        """Maker expiry <= min(end - 2 min, start - 5 min while the start is ahead) and >= now + 2 min + margin.
        ponytail: the start bound fails open once the start has passed or when the loop left kernel.starts empty. That
        suits crypto Up/Down (the window is the market). Sports modes never fail open: no start, or now > start - 5 min,
        rejects the maker."""
        if intent.kind != "maker":
            return None
        hi = m.end_ms - 2 * MIN
        start = self.starts.get(m.cid)
        if m.mode.startswith("sports"):  # sports: the start bound never fails open (no start known = no maker)
            if start is None:
                return "GTD: sports maker needs the market's start in kernel.starts"
            hi = min(hi, start - 5 * MIN)
        elif start is not None and start > now_ms:
            hi = min(hi, start - 5 * MIN)
        lo = now_ms + 2 * MIN + self.gtd_margin_ms
        if not lo <= intent.expiry_ms <= hi:
            return f"GTD expiry {intent.expiry_ms} outside [{lo}, {hi}]"
        return None

    def dump_uncleared(self, path=DATA / "trader" / "uncleared.jsonl") -> None:
        """Write the keys seen without a clearance, for `python -m tools.clearance_cli sign --keys <path>`."""
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("".join(json.dumps(v) + "\n" for v in self.uncleared.values()), encoding="utf-8")
