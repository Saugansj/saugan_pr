"""Role 24's LLM part: unscheduled crypto shocks (WP5-D, task 5.7). Talks only to an advisor.contracts.Gateway.

ShockReader.read(items, now_ms, gw) -> list[CautionSignal]. A keyword prefilter on title and body decides whether an
item is worth one gateway call; an unmatched item costs nothing. A confirmed shock pulls quotes on each affected enabled
underlying ("ALL" = every one) until expiry, and quotes resume only on a fresh observation. A failure after a keyword
match (refused prompt, ok=False, malformed or missing field, exhausted quota) pulls every enabled underlying.
The output carries no direction: only the fields below are read from the vendor, everything else is dropped.
Items: {id, source, ts_ms, recorded_ms, title, body}; items recorded after now_ms, or with no int recorded_ms, are
ignored.
"""
import re

from advisor.contracts import CautionSignal
from advisor.roles_p5.board import ask
from common import sha256_text

ROLE, TASK = "24-crypto-event", "24-crypto-shock"
MIN_MS = 60_000
EXPIRY_MS = {"low": 15 * MIN_MS, "medium": 60 * MIN_MS, "high": 240 * MIN_MS}
FAIL_SEVERITY = "high"         # fail closed with the longest pull
UNDERLYINGS = ("BTC", "ETH", "SOL", "XRP")
ENABLED = ("BTC", "ETH")       # trader.engines.ladder PARAMS["assets"] (speed trades BTC only); pass the live set in
MAX_BODY = 4000
KEYWORDS = re.compile(
    r"\bhack|\bexploit|\bdrain(?:ed|s|ing)?\b|\bde-?peg|\binsolven|\bbankrupt|\bdelist|\bban(?:s|ned|ning)?\b"
    r"|\bcharge[sd]\b|\bemergency|\boutage"
    r"|\bwithdrawals?\s+(?:\w+\s+){0,2}(?:halted|paused|suspended)|\b(?:halt|paus|suspend)\w*\s+(?:\w+\s+){0,2}withdrawals?",
    re.I)
SCHEMA = {"type": "object", "required": ["is_shock", "underlyings", "severity", "reason"], "properties": {
    "is_shock": {"type": "boolean"},
    "underlyings": {"type": "array", "items": {"type": "string", "enum": [*UNDERLYINGS, "ALL"]}},
    "severity": {"type": "string", "enum": list(EXPIRY_MS)},
    "reason": {"type": "string"}}}
PROMPT = """You read one crypto news item for an automated market maker that must stop quoting when an unscheduled shock
hits: an exchange or protocol hack or exploit, a stablecoin depeg, insolvency, halted withdrawals, a delisting, a ban or
criminal charges against a major exchange or issuer, an emergency or a major outage. Routine news, price commentary,
scheduled events and opinion are not shocks. Do not predict a price direction.
Answer with JSON only: {{"is_shock": true or false, "underlyings": [any of "BTC", "ETH", "SOL", "XRP", or "ALL" if the
whole crypto market is hit], "severity": "low" or "medium" or "high", "reason": "<one sentence>"}}.

Source: {source}
Title: {title}
Body:
{body}"""
PROMPT_SHA256 = sha256_text(PROMPT)


def matches(item: dict) -> bool:
    return bool(KEYWORDS.search(f"{item.get('title') or ''}\n{item.get('body') or ''}"))


def _valid(d: dict) -> bool:
    u = d.get("underlyings")
    return (isinstance(d.get("is_shock"), bool) and isinstance(u, list) and all(x in (*UNDERLYINGS, "ALL") for x in u)
            and (u or not d["is_shock"]) and d.get("severity") in EXPIRY_MS and isinstance(d.get("reason"), str))


class ShockReader:
    def __init__(self, enabled=ENABLED):
        self.enabled = tuple(enabled)

    def _pull(self, scopes, severity: str, now_ms: int, reason: str) -> list[CautionSignal]:
        return [CautionSignal(ROLE, u, "pull", 0.0, now_ms + EXPIRY_MS[severity], True, reason) for u in scopes]

    def read(self, items: list[dict], now_ms: int, gw) -> list[CautionSignal]:
        out = []
        for it in items:
            rec = it.get("recorded_ms")
            # no usable recorded_ms: cannot prove it was known by now_ms, so skip it (never abort the batch)
            if not isinstance(rec, int) or isinstance(rec, bool) or rec > now_ms or not matches(it):
                continue
            prompt = PROMPT.format(source=it.get("source", ""), title=it.get("title", ""),
                                   body=(it.get("body") or "")[:MAX_BODY])
            res = ask(gw, TASK, prompt, SCHEMA, 1)
            d = res[0].data if res and len(res) == 1 and res[0].ok and isinstance(res[0].data, dict) else None
            if d is None or not _valid(d):
                out += self._pull(self.enabled, FAIL_SEVERITY, now_ms, f"fail closed: no valid answer on item {it.get('id')}")
            elif d["is_shock"]:
                hit = [u for u in self.enabled if "ALL" in d["underlyings"] or u in d["underlyings"]]
                out += self._pull(hit, d["severity"], now_ms, f"{d['severity']} shock, item {it.get('id')}: "
                                                               f"{(it.get('title') or '')[:120]}")
        return out
