"""Settlement keeper (role 06, build-plan 2.6). A watcher that never signs: public GETs only.

For every held market past its end it derives the outcome from the market's named source and compares it with the UMA
proposal from the Data API. A mismatch, a source still unreadable 10 min after the print, or a dispute pages the human
(ntfy, with the challenge deadline) and locks the market (`trip(cid, ..., REDUCING)`). It emits merge and redeem as
`FundIntent`s (contracts.Intent has no fund kinds); `gate()` is the kernel-side check before role 05 executes them.

Candle timing is Phase 0's `research/measure/postclose.py::binance_check` (8,669 of 8,669 strikes agreed):
  - daily strike:  close of the 1m candle opening at 12:00 ET on the settlement date > strike -> YES (strict)
  - daily Up/Down: that close vs the close of the 12:00 ET candle the day before (prev_noon_ms): > Up, < Down, = 50-50
  - hourly Up/Down: close of the hour's last 1m candle >= open of its first (= the 1H candle) -> Up
  - anything else (chainlink crypto-fast, sports) -> None: the source cannot be read here ([ops] D13)
YES is token_yes, the first outcome (Up for Up/Down).
"""
import datetime as dt
import logging
import os
import urllib.request
import zoneinfo
from dataclasses import dataclass

from trader.contracts import Decision, MarketInfo, Order, TradingState
from trader.engines.ladder import prev_noon_ms
from trader.router import OPEN, round_size

log = logging.getLogger(__name__)
ET = zoneinfo.ZoneInfo("America/New_York")
KLINES = "https://api.binance.com/api/v3/klines"
RESOLUTIONS = "https://data-api.polymarket.com/v2/resolutions"
NTFY = "https://ntfy.sh"
MIN_MS, H_MS = 60_000, 3_600_000
GRACE_MS = 600_000          # source still unreadable this long after the print -> page + lock
SETTLE_MS = 60_000          # read the print candle only this long after it closed, so its close is final (cached)
CHALLENGE_MS = 7_200_000    # UMA challenge window after a proposal
PRICE = {"1000000000000000000": "YES", "0": "NO", "500000000000000000": "50-50"}  # UMA prices (1e18 = 1)
EPS = 1e-9
A, R, H = TradingState.ACTIVE, TradingState.REDUCING, TradingState.HALTED


# ---- outcome from the named source ---------------------------------------------------------------------------------
def candles(m: MarketInfo) -> list[int]:
    """Open times (ms) of the Binance 1m candles the outcome depends on, the print candle last; [] if not Binance."""
    if not m.source_id.startswith("binance:"):
        return []
    if m.mode == "crypto-hourly":
        return [m.end_ms - H_MS, m.end_ms - MIN_MS]
    noon = int(dt.datetime.combine(dt.datetime.fromtimestamp(m.end_ms / 1000, ET).date(), dt.time(12), ET).timestamp() * 1000)
    return [noon] if m.kind == "strike" else [prev_noon_ms(m.end_ms), noon]


def print_ms(m: MarketInfo) -> int:
    """When the source prints: the close of the last candle for Binance markets, else the market end."""
    ts = candles(m)
    return ts[-1] + MIN_MS if ts else m.end_ms


def derive_outcome(m: MarketInfo, klines: list) -> str | None:
    """"YES" | "NO" | "50-50" from raw Binance kline rows ([open_time, open, high, low, close, ...]); None when the
    source can't be read here or a needed candle is missing."""
    ts = candles(m)
    k = {int(r[0]): (float(r[1]), float(r[4])) for r in klines or ()}
    if not ts or any(t not in k for t in ts):
        return None
    if m.mode == "crypto-hourly":
        return "YES" if k[ts[1]][1] >= k[ts[0]][0] else "NO"
    c = k[ts[-1]][1]
    if m.kind == "strike":
        return None if m.strike is None else ("YES" if c > m.strike else "NO")
    if m.kind == "updown":
        c0 = k[ts[0]][1]
        return "YES" if c > c0 else "NO" if c < c0 else "50-50"
    return None


def proposal(rec) -> str | None:
    """The current UMA proposal of a Data API /v2/resolutions record; a reproposal (after a dispute) supersedes the
    first. reproposed_price "69" means none. Anything unrecognised -> None."""
    if not isinstance(rec, dict):
        return None
    return PRICE.get(str(rec.get("reproposed_price"))) or PRICE.get(str(rec.get("proposed_price")))


# ---- paging --------------------------------------------------------------------------------------------------------
def _post(url: str, body: bytes) -> None:
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "text/plain"})
    urllib.request.urlopen(req, timeout=5).close()


def page(text: str, topic: str | None = None, send=_post) -> bool:
    """Plain-text POST to ntfy.sh/<ROSTER_NTFY_TOPIC>. No topic -> local log only, False, no network call.
    Errors are swallowed. The topic is never logged."""
    topic = topic or os.environ.get("ROSTER_NTFY_TOPIC", "").strip()
    if not topic:
        log.warning("PAGE (no ROSTER_NTFY_TOPIC; local only)\n%s", text)
        return False
    try:
        send(f"{NTFY}/{topic}", text.encode("utf-8"))
        return True
    except Exception as e:  # noqa: BLE001 - a failed page must never break the keeper
        log.warning("page to ntfy.sh failed: %s", type(e).__name__)
        return False


def _iso(ms) -> str:
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ") if ms else "unknown"


# ---- the keeper ----------------------------------------------------------------------------------------------------
@dataclass
class Status:
    m: MarketInfo
    state: str = "waiting"      # waiting -> printed -> proposed -> matched | mismatch | disputed -> resolved
    derived: str | None = None
    proposed: str | None = None
    deadline_ms: int | None = None  # proposal time + 2 h
    outcome: str | None = None      # final, once resolved
    mismatch: bool = False
    disputed: bool = False
    locked: bool = False            # we tripped the market (mismatch, unreadable source or dispute)


class SettlementKeeper:
    def __init__(self, markets: dict[str, MarketInfo], get, page, trip, grace_ms: int = GRACE_MS):
        """markets: the live {cid: MarketInfo} dict. get(url, params) -> json (common.get_json). page(text) -> bool.
        trip(scope, reason, source, level): RiskKernel.trip."""
        self.markets, self.get, self.page, self.trip, self.grace_ms = markets, get, page, trip, grace_ms
        self.statuses: dict[str, Status] = {}
        self.sent: set[tuple[str, str]] = set()     # (cid, kind) already paged and locked
        self._kl: dict[tuple[str, int], list] = {}  # (symbol, open ms) -> kline row; a print is shared by its strikes
        self._gap: set[str] = set()

    def oracle_gap(self) -> set[str]:
        """Markets that have printed but not resolved (as of the last step), held or not: role 20 pulls, WP2-C cap."""
        return set(self._gap)

    def step(self, now_ms: int, positions: dict[str, float]) -> None:
        gap = set()
        for cid, m in {**{c: s.m for c, s in self.statuses.items()}, **self.markets}.items():
            s = self.statuses.get(cid)
            if now_ms < m.end_ms or (s and s.state == "resolved"):
                continue
            held = any(positions.get(t, 0.0) > EPS for t in (m.token_yes, m.token_no))
            printed = now_ms >= print_ms(m)
            if printed:
                gap.add(cid)
            if not (held or s):
                continue  # ponytail: unheld markets stay in the gap until they leave `markets`; no GET spent on them
            s = self.statuses.setdefault(cid, Status(m))
            if printed:
                self._check(s, now_ms, held)
                if s.state == "resolved":
                    gap.discard(cid)
        self._gap = gap

    def _check(self, s: Status, now_ms: int, held: bool) -> None:
        cid, m = s.m.cid, s.m
        try:
            rec = (self.get(RESOLUTIONS, {"condition": cid}).get("data") or [{}])[0]
        except Exception as e:  # noqa: BLE001 - public GET failed: look again next step
            log.warning("resolution GET failed for %s: %s", cid, type(e).__name__)
            rec = {}
        rec = rec if isinstance(rec, dict) else {}
        prop = proposal(rec)
        if prop and prop != s.proposed:
            s.proposed = prop
            ts = rec.get("last_update_timestamp")
            s.deadline_ms = int(ts) * 1000 + CHALLENGE_MS if str(ts).isdigit() else None
        s.disputed |= str(rec.get("was_disputed")).lower() == "true" or rec.get("status") == "disputed"
        if held and s.derived is None and now_ms >= print_ms(m) + SETTLE_MS:
            s.derived = derive_outcome(m, self._klines(m))
        if held:
            if s.disputed:
                self._alarm(s, "dispute", "breaker:dispute")
            if s.derived is None and now_ms >= print_ms(m) + self.grace_ms:  # counts as a mismatch
                s.mismatch = True
                self._alarm(s, "unreadable", "breaker:settlement")
            elif s.derived and s.proposed and s.derived != s.proposed:
                s.mismatch = True
                self._alarm(s, "mismatch", "breaker:settlement")
        if rec.get("status") == "resolved":
            s.outcome, s.state = PRICE.get(str(rec.get("price"))) or prop, "resolved"
        else:
            s.state = ("disputed" if s.disputed else "mismatch" if s.mismatch else
                       "matched" if s.proposed and s.proposed == s.derived else "proposed" if s.proposed else "printed")

    def _klines(self, m: MarketInfo) -> list:
        ts = candles(m)
        if not ts:
            return []
        sym = m.source_id.split(":", 1)[1].replace("/", "")
        for t in ts:
            if (sym, t) not in self._kl:
                try:
                    rows = self.get(KLINES, {"symbol": sym, "interval": "1m", "startTime": t, "limit": 1})
                    hit = [r for r in rows if int(r[0]) == t and min(float(r[1]), float(r[4])) > 0]
                    if hit:
                        self._kl[(sym, t)] = hit[0]
                except Exception as e:  # noqa: BLE001 - unreadable for now; the grace timer decides
                    log.warning("klines GET failed for %s: %s", sym, type(e).__name__)
        return [self._kl[(sym, t)] for t in ts if (sym, t) in self._kl]

    def _alarm(self, s: Status, kind: str, source: str) -> None:
        """Lock the market and page, once per (cid, kind)."""
        if (s.m.cid, kind) in self.sent:
            return
        self.sent.add((s.m.cid, kind))
        s.locked = True
        self.trip(s.m.cid, f"settlement {kind}: proposed {s.proposed}, derived {s.derived}", source, R)
        self.page(page_text(kind, s))


def page_text(kind: str, s: Status) -> str:
    """Only the cid, question, both outcomes and the challenge deadline: never balances, positions or keys."""
    return (f"ROSTER settlement {kind.upper()}\ncid: {s.m.cid}\nquestion: {s.m.question}\n"
            f"proposed: {s.proposed or 'none yet'}\nderived: {s.derived or 'source cannot be read'}\n"
            f"challenge deadline: {_iso(s.deadline_ms) if s.deadline_ms else 'unknown (proposal time + 2h)'}")


# ---- fund intents --------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class FundIntent:
    kind: str               # "merge" | "redeem"
    cid: str
    token_ids: tuple
    size: float             # pairs to merge, or shares of the token to redeem
    reason: str


def fund_intents(positions: dict[str, float], open_orders: list[Order], markets: dict[str, MarketInfo],
                 statuses: dict[str, Status]) -> list[FundIntent]:
    """Merges of completed pairs net of open SELL offers (Phase 1 Reconciler.merge_pairs) in unresolved markets;
    redeems of winning shares (both tokens on 50-50) in resolved markets that are not disputed, mismatched or locked."""
    offered: dict[str, float] = {}
    for o in open_orders:
        if o.intent.side == "SELL" and o.status in OPEN:
            offered[o.intent.token_id] = offered.get(o.intent.token_id, 0.0) + o.intent.size - o.filled
    out = []
    for cid, m in {**{c: s.m for c, s in statuses.items()}, **markets}.items():
        s = statuses.get(cid)
        if s and s.state == "resolved":
            if s.outcome is None or s.disputed or s.mismatch or s.locked:
                continue
            toks = {"YES": (m.token_yes,), "NO": (m.token_no,), "50-50": (m.token_yes, m.token_no)}[s.outcome]
            out += [FundIntent("redeem", cid, (t,), round_size(positions[t]), f"resolved {s.outcome}")
                    for t in toks if round_size(positions.get(t, 0.0)) > 0]
            continue
        n = round_size(min(positions.get(t, 0.0) - offered.get(t, 0.0) for t in (m.token_yes, m.token_no)))
        if n > 0:
            out.append(FundIntent("merge", cid, (m.token_yes, m.token_no), n, "completed pairs net of open SELL offers"))
    return out


def gate(fi: FundIntent, scope_state: dict, status: Status | None = None) -> Decision:
    """scope_state: {scope: TradingState}, e.g. RiskKernel.scopes. HALTED (global or this market) allows cancels only.
    Merge and redeem reduce exposure, so ACTIVE and REDUCING allow them, except a redeem on a locked (market scope not
    ACTIVE), mismatched or disputed market."""
    g, mk = scope_state.get("global", A), scope_state.get(fi.cid, A)
    if fi.kind not in ("merge", "redeem"):
        return Decision(False, f"unknown fund intent kind {fi.kind!r}")
    if H in (g, mk):
        return Decision(False, "HALTED: cancels only", "halted")
    if fi.kind == "redeem" and (mk != A or (status and (status.mismatch or status.disputed or status.locked))):
        return Decision(False, "redeem refused: market locked, mismatched or disputed", f"settlement:{fi.cid}")
    return Decision(True, f"{fi.kind} reduces exposure")
