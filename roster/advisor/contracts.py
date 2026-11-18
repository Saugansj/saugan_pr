"""Shared interface for the advisor (LLM) side. Owned by the orchestrator: work packages import this, never edit it.

Rules every LLM role follows (v4 plan, rules 1, 2 and 7):
- An LLM never places, sizes or prices an order. Its output can only shrink edge, pull quotes, or veto.
- Prompts carry public market text only: never keys, balances, positions or P&L.
- Fail closed: a parse failure, timeout, missing field or exhausted quota counts as a veto (or "no signal"), never a pass.
"""
from dataclasses import dataclass
from typing import Literal, Protocol

Verdict = Literal["clear", "veto"]


@dataclass(frozen=True)
class LLMResult:
    vendor: str            # "gemini" | "groq" | "openrouter" | "local" | "fake"
    model: str
    ok: bool               # False on timeout, HTTP error, quota exhausted or schema parse failure
    data: dict | None      # parsed JSON matching the requested schema when ok
    error: str | None
    cached: bool           # answered from the input-hash cache
    tokens: int


class Gateway(Protocol):
    """The shared LLM gateway (advisor process). Rotates free-tier vendors, caches by input hash, never raises."""

    def complete(self, task: str, prompt: str, schema: dict, vendors: int = 1) -> list[LLMResult]:
        """Ask `vendors` distinct vendors; returns one LLMResult per vendor asked (ok=False ones included)."""
        ...

    def quota_left(self) -> dict[str, int]:
        """Remaining requests today per vendor."""
        ...


@dataclass(frozen=True)
class RoleVerdict:
    role: str                                   # e.g. "27-resolution", "28-wording", "30-correlation", "31-change-gate"
    verdict: Verdict
    reasons: tuple[str, ...]
    vendor_votes: tuple[tuple[str, str], ...]   # (vendor, "clear" | "veto" | "error")


@dataclass(frozen=True)
class CautionSignal:
    """Output of T3 estimators (24, 25): may only shrink edge toward 0 or pull quotes."""
    role: str                     # "24-crypto-event" | "25-sports-news"
    scope: str                    # market cid, event group or underlying it applies to
    action: Literal["none", "shrink", "pull"]
    shrink_factor: float          # in [0, 1]; 1.0 = no change. Never above 1.
    expires_ms: int
    resume_requires_fresh_observation: bool
    reason: str
