"""Roles 30 (correlation adversary) and 31 (change gate), veto only (WP5-D, task 5.6), plus `ask()`, the guard every
Phase 5 LLM role sends through. Talks only to an advisor.contracts.Gateway; never to a vendor SDK or HTTP.

- Fail closed: ok=False, a missing or wrongly typed field, fewer than 2 answers, a repeated vendor or a refused prompt
  is a veto. A clear needs 2 distinct vendors, both answering a valid clear.
- Public text only: role 30's prompt carries question and rules text; `cap` is a cache key only. Role 31's prompt
  carries the diff or each parameter's direction and relative move (never absolute values), never the evidence.
- No path to promote or to write the registry: a clear verdict says the pass still needs a human token.
"""
import math
import os

from advisor.contracts import LLMResult, RoleVerdict
from common import sha256_text

SECRET_NAMES = ("KEY", "SECRET", "PASS", "TOKEN")
HUMAN = "pass still needs a human token"


def secret_in(text: str) -> bool:
    """True if `text` holds the value of a set env var whose name contains KEY, SECRET, PASS or TOKEN."""
    # ponytail: values under 8 chars are ignored (flags like "1" would refuse every prompt); same floor as advisor.gateway
    return any(v in text for k, v in os.environ.items() if len(v) >= 8 and any(s in k.upper() for s in SECRET_NAMES))


def ask(gw, task: str, prompt: str, schema: dict, vendors: int) -> list[LLMResult] | None:
    """gw.complete, or None (fail closed) when the prompt carries a secret value (never sent) or the gateway raised."""
    if secret_in(prompt):
        return None
    try:
        return list(gw.complete(task, prompt, schema, vendors=vendors))
    except Exception:  # the contract says the gateway never raises; if one does, fail closed
        return None


def _str(x) -> bool:
    return isinstance(x, str)


def _verdict(role: str, results, valid, clear, reasons) -> RoleVerdict:
    """2-vendor board: (vendor, clear|veto|error) per answer; clear only if >= 2 distinct vendors all voted clear."""
    if results is None:
        return RoleVerdict(role, "veto", ("prompt not sent (secret in prompt) or gateway failure",), ())
    votes, why = [], []
    for r in results:
        ok = r.ok and isinstance(r.data, dict) and valid(r.data)
        votes.append((r.vendor, "error" if not ok else "clear" if clear(r.data) else "veto"))
        why += [f"{r.vendor}: error {r.error or 'invalid answer'}"] if not ok else [f"{r.vendor}: {x}" for x in reasons(r.data)]
    vendors = [v for v, _ in votes]
    if len(votes) >= 2 and len(set(vendors)) == len(votes) and all(x == "clear" for _, x in votes):
        return RoleVerdict(role, "clear", tuple(why), tuple(votes))
    if len(set(vendors)) < 2:
        why.append("fewer than 2 distinct vendors answered")
    return RoleVerdict(role, "veto", tuple(why), tuple(votes))


# ---------- role 30: correlation adversary ----------

ROLE_30 = "30-correlation"
SCHEMA_30 = {"type": "object", "required": ["verdict", "hidden_links"], "properties": {
    "verdict": {"type": "string", "enum": ["clear", "veto"]},
    "hidden_links": {"type": "array", "items": {"type": "object", "required": ["other_group", "mechanism"],
                                                "properties": {"other_group": {"type": "string"},
                                                               "mechanism": {"type": "string"}}}}}}
PROMPT_30 = """You are a correlation adversary for a prediction-market book. A new event group is about to be entered.
Deterministic code already handles the obvious groupings (same event, same settlement instant). Hunt for hidden links it
misses: one outcome or one fact that would move both the new group and a group already held, for example a team
moneyline and a player prop in the same game, or a BTC touch market and an ETH strike market settling the same day.
Answer with JSON only: {{"verdict": "clear" or "veto", "hidden_links": [{{"other_group": "<held group id>",
"mechanism": "<one sentence>"}}]}}. Veto and list every link you find; answer clear only if there is none.

New event group: {group}
{markets}

Event groups already held:
{exposed}"""


def _valid_30(d: dict) -> bool:
    links = d.get("hidden_links")
    return (d.get("verdict") in ("clear", "veto") and isinstance(links, list)
            and all(isinstance(x, dict) and _str(x.get("other_group")) and _str(x.get("mechanism")) for x in links))


class CorrelationAdversary:
    """Once per new event-group exposure (first entry or a cap raise). Verdicts are cached per group with the highest
    cap reviewed; a repeat at the same or a lower cap makes no gateway call."""

    def __init__(self):
        self.cache: dict[str, tuple[float, RoleVerdict]] = {}

    def review(self, group: str, group_markets: list[dict], exposed_groups: dict[str, list[dict]], cap: float,
               gw) -> RoleVerdict:
        hit = self.cache.get(group)
        if hit and cap <= hit[0]:
            return hit[1]
        rules = list(dict.fromkeys(m.get("rules_text", "") for m in group_markets))  # identical rules sent once
        markets = "\n".join([*(f"- {m.get('question', '')}" for m in group_markets), "Rules text:", *rules])
        exposed = "\n".join(f"{g}: " + " | ".join(m.get("question", "") for m in ms)
                            for g, ms in exposed_groups.items()) or "(none)"
        prompt = PROMPT_30.format(group=group, markets=markets, exposed=exposed)
        v = _verdict(ROLE_30, ask(gw, ROLE_30, prompt, SCHEMA_30, 2), _valid_30,
                     lambda d: d["verdict"] == "clear" and not d["hidden_links"],
                     lambda d: [f"link {x['other_group']}: {x['mechanism']}" for x in d["hidden_links"]]
                     or ([] if d["verdict"] == "clear" else ["veto without a named link"]))
        # ponytail: an error veto is cached too (no retry storm on the quota); a cap raise or restart re-asks
        self.cache[group] = (cap, v)
        return v


# ---------- role 31: change gate ----------

ROLE_31 = "31-change-gate"
SCHEMA_31 = {"type": "object", "required": ["verdict", "violations"], "properties": {
    "verdict": {"type": "string", "enum": ["clear", "veto"]},
    "violations": {"type": "array", "items": {"type": "string"}}}}
INVARIANTS = ("AI can't raise size", "never round up (sizes are floored)", "halt = confirmed cancel-all",
              "no retry on unknown order state", "journal before send", "one fee function (trader.fees.fee)",
              "live only behind three flags (config, env, CLI)", "LLM output only shrinks, pulls or vetoes")
PROMPT_31 = """You are the change gate for an automated prediction-market trader. You can only veto. Review the change
below against the invariants and rule 7, and list every violation.
Invariants:
{invariants}
Rule 7: a change is judged by its effect on exposure, not by its name. Anything that can raise |edge|, size, a budget or
quote aggressiveness, or that weakens a cautious component, is a promotion and needs pre-registered evidence and a human
token.
Rule-7 flags already raised by deterministic checks: {flags}
Answer with JSON only: {{"verdict": "clear" or "veto", "violations": ["<invariant or rule broken, and where>"]}}.
Veto if the change breaks any invariant or hides an exposure increase the flags miss.

Change kind: {kind}
Name: {name}
Paths: {paths}
Change:
{body}"""
MAX_DIFF = 30_000  # a longer diff is vetoed unread (split it), never reviewed half-seen

# rule 7 direction table: raising UP or lowering DOWN can raise |edge|, size, a budget or quote aggressiveness
UP = {"quote_size", "max_inv", "kelly_cap", "c_shrink", "max_markets", "max_price", "reward_share", "shares",
      "move_k", "book_stale_ms", "ref_stale_ms", "stale_ms"}
DOWN = {"half_min", "k_unc", "k_vol", "complement_margin", "pull_before_close_ms", "gamma"}
# T0 code and the sizers: kernel/breakers/router/audit/ledger/reconciler, the live router, settlement keeper and risk
# (trader/live/), the engines' sizers (kelly, taker_shares, MAX_SHARES) and the global cap
T0_CODE = ("trader/kernel.py", "trader/breakers.py", "trader/router.py", "trader/audit.py", "trader/ledger.py",
           "trader/reconciler.py", "trader/live/", "trader/engines/", "trader/growth/capital.py",
           "trader/fees.py")  # the one fee function: a lower fee raises |edge|


def _num(x) -> bool:
    """A finite real number. NaN and inf fail every comparison, so they would slip past rule 7 and the evidence check."""
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _changed(change: dict) -> list[tuple]:
    old, new = change.get("old") or {}, change.get("new") or {}
    return [(k, old.get(k), new.get(k), k in old, k in new) for k in sorted(set(old) | set(new), key=str)
            if old.get(k) != new.get(k) or (k in old) != (k in new)]


def rule7(change: dict) -> list[str]:
    """Everything in `change` that can raise |edge|, size, a budget or quote aggressiveness, or weaken a cautious
    component. Any kappa change, any unknown or non-numeric parameter change and any code change to T0 or a sizer is
    flagged."""
    if change.get("kind") == "code":
        return [f"code touches T0 or a sizer: {p}" for p in change.get("paths") or ()
                if any(t in str(p).replace("\\", "/").lower() for t in T0_CODE)]  # Windows paths are case-insensitive
    if change.get("kind") != "learned":
        return [f"unknown change kind {change.get('kind')!r}"]
    name, flags = str(change.get("name", "")), []
    budget = name.startswith("budget")
    for k, a, b, _, _ in _changed(change):
        if "kappa" in f"{name}:{k}".lower() or "κ" in f"{name}:{k}":
            flags.append(f"kappa change: {k}")
        elif not (_num(a) and _num(b)):
            flags.append(f"unknown or non-numeric change: {k}")
        elif budget or str(k).startswith("budget") or k in UP:
            if b > a:
                flags.append(f"{k} raised")
        elif k in DOWN:
            if b < a:
                flags.append(f"{k} lowered")
        else:
            flags.append(f"unknown parameter: {k}")
    return flags


def evidence_gap(change: dict) -> str | None:
    """Why a flagged learned change lacks evidence, or None. The pass is judged from the numbers, as
    trader/growth/capital.py does: prereg {n, pass_z}; evidence {n, mean, se} with n >= prereg n, se > 0 and
    mean > pass_z x se. A verdict string is never trusted."""
    pre, ev = change.get("prereg") or {}, change.get("evidence") or {}
    if not (_num(pre.get("n")) and _num(pre.get("pass_z"))):
        return "no pre-registration (n, pass_z)"
    if not all(_num(ev.get(k)) for k in ("n", "mean", "se")):
        return "no evidence (n, mean, se)"
    if ev["n"] < pre["n"]:
        return "evidence below its pre-registered n"
    if not (ev["se"] > 0 and ev["mean"] > pre["pass_z"] * ev["se"]):
        return "pre-registered test not passed"
    return None


def _body(change: dict) -> str:
    """The diff for code; for learned changes each parameter's direction and relative move, never its value."""
    if change.get("kind") == "code":
        return str(change.get("diff") or "")
    out = []
    for k, a, b, had, has in _changed(change):
        if not had or not has:
            out.append(f"{k}: {'added' if has else 'removed'}")
        elif _num(a) and _num(b):
            out.append(f"{k}: {'raised' if b > a else 'lowered'}" + (f" by {abs(b / a - 1):.0%}" if a else " from 0"))
        else:
            out.append(f"{k}: changed")
    return "\n".join(out) or "(no parameter differs)"


class ChangeGate:
    """Role 31: deterministic rule 7 and evidence check first, then a 2-vendor review. Veto only."""

    def review(self, change: dict, gw) -> RoleVerdict:
        flags = rule7(change)
        if change.get("kind") not in ("code", "learned"):
            return RoleVerdict(ROLE_31, "veto", tuple(flags), ())
        if change["kind"] == "learned" and flags and (gap := evidence_gap(change)):
            return RoleVerdict(ROLE_31, "veto", (*flags, gap), ())
        body = _body(change)
        if len(body) > MAX_DIFF:
            return RoleVerdict(ROLE_31, "veto", (*flags, f"diff over {MAX_DIFF} chars: split it"), ())
        prompt = PROMPT_31.format(invariants="\n".join(f"- {i}" for i in INVARIANTS), flags="; ".join(flags) or "none",
                                  kind=change["kind"], name=change.get("name", ""),
                                  paths=", ".join(map(str, change.get("paths") or ())) or "-", body=body)
        v = _verdict(ROLE_31, ask(gw, ROLE_31, prompt, SCHEMA_31, 2), lambda d: d.get("verdict") in ("clear", "veto")
                     and isinstance(d.get("violations"), list) and all(map(_str, d["violations"])),
                     lambda d: d["verdict"] == "clear" and not d["violations"], lambda d: d["violations"])
        if v.verdict == "clear":
            return RoleVerdict(ROLE_31, "clear", (*v.reasons, *flags, HUMAN), v.vendor_votes)
        return RoleVerdict(ROLE_31, "veto", (*v.reasons, *flags), v.vendor_votes)


PROMPT_SHA256 = sha256_text(PROMPT_30 + PROMPT_31)
