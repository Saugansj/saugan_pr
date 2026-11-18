"""Qualified clearance board (WP4-C, task 4.8): role 27 (resolution auditor) and role 28 (wording adversary).

clear_template() asks each role with vendors=2. A template clears only if both roles got parsed "clear" answers from two
different vendors whose (vendor, model) pairs are in QUALIFIED. A parse failure, timeout, missing or empty item, error,
same-vendor pair or unqualified model is a veto. The LLM never prices, sizes or places anything: it can only withhold.

A clearance is written in tools/clearance_cli.py's exact shape (its write() is reused), signed with trader.kernel.sign
under env ROSTER_ADVISOR_KEY (never the human key), into data/advisor/llm_clearances.db (never data/trader/advice.db).
Cleared keys also go to a JSONL that `python -m tools.clearance_cli sign --keys` accepts, so a human can co-sign.

  # run-alongside: board vs your clearances on the kernel's uncleared backlog
  python -m advisor.board agree --backlog data/trader/uncleared.jsonl --snapshot data/markets/<latest>Z.jsonl \\
      --human-db data/trader/advice.db --out reports/phase4_agreement.md
"""
import argparse
import collections
import datetime
import json
import os
import pathlib
import sys

from advisor.contracts import LLMResult, RoleVerdict
from advisor.gateway import LLMGateway, valid
from advisor.gateway import DB as GATEWAY_DB
from common import DATA, REPORTS, append_jsonl, now_ms
from tools.clearance_cli import write
from trader.kernel import ADVICE_DB, KEY_FIELDS, key_id, load_advice

LLM_DB = DATA / "advisor" / "llm_clearances.db"
KEYS_OUT = DATA / "advisor" / "cleared_keys.jsonl"
# (vendor, model) pairs allowed to clear. Changing a model in gateway.VENDORS without adding it here leaves that vendor
# veto-only until the new model has been run alongside your clearances (agreement report) and added.
QUALIFIED = frozenset({("gemini", "gemini-2.5-flash"), ("groq", "llama-3.3-70b-versatile"),
                       ("openrouter", "deepseek/deepseek-chat-v3.1:free")})

POINTS = ("resolution_source", "cutoff_time", "comparison", "price_method", "tie_rule", "cancellation_rule",
          "postponement_rule", "neg_risk_exactly_one_yes", "augmented_other")
NA3 = {"type": "string", "enum": ["yes", "no", "not applicable"]}
R27 = {"type": "object", "required": [*POINTS, "dispute_risk", "verdict", "reasons"], "properties": {
    "resolution_source": {"type": "string"}, "cutoff_time": {"type": "string"},
    "comparison": {"type": "string", "enum": [">", ">=", "<", "<=", "not applicable"]},
    "price_method": {"type": "string", "enum": ["snapshot", "twap", "not applicable"]},
    "tie_rule": {"type": "string"}, "cancellation_rule": {"type": "string"}, "postponement_rule": {"type": "string"},
    "neg_risk_exactly_one_yes": NA3, "augmented_other": NA3,
    "dispute_risk": {"type": "string", "enum": ["low", "medium", "high"]},
    "verdict": {"type": "string", "enum": ["clear", "veto"]}, "reasons": {"type": "array", "items": {"type": "string"}}}}
R28 = {"type": "object", "required": ["verdict", "reading", "scenario"], "properties": {
    "verdict": {"type": "string", "enum": ["clear", "veto"]}, "reading": {"type": "string"},
    "scenario": {"type": "string"}}}

CONTEXT = "Question: {question}\nTemplate fields: {fields}\nRules text:\n{rules}"
PROMPT_27 = """You are a resolution auditor for one Polymarket market template. You audit the rules text, not the forecast.
Answer every field from the rules text below. Never leave a field empty: write "not stated in rules" where it is silent.
- resolution_source: the named source (exchange and pair, candle or feed, official body or website).
- cutoff_time: the print or cutoff time with its timezone, e.g. "12:00 ET" for a noon candle close.
- comparison: strict ">" or inclusive ">=" (or "<", "<="); "not applicable" if there is no threshold.
- price_method: "snapshot" (one print) or "twap" (time-weighted average); "not applicable" if no price is read.
- tie_rule: what happens on an exact tie, including any 50-50 resolution.
- cancellation_rule: what happens if the event is cancelled, including any 50-50 resolution.
- postponement_rule: what happens if the event is postponed, e.g. the market "remains open until completed".
- neg_risk_exactly_one_yes: in a negRisk event, does exactly one listed outcome resolve YES in every contingency?
- augmented_other: can an augmented "Other" or unlisted outcome win?
- dispute_risk: low, medium or high (e.g. a vague "official" definition, or an event inside the window disclosed after it).
- verdict: "veto" if any point that could decide the outcome is unclear or not stated, else "clear"; reasons: why.

""" + CONTEXT
PROMPT_28 = """You are a wording adversary for one Polymarket market template. Look for a specific, concrete reading of the
rules under which someone who forecast the real-world outcome correctly still loses (e.g. ">" read as ">=", a different
candle, source or timezone, a postponed or abandoned game, an unlisted outcome).
Veto only if you can state that reading and a concrete scenario; otherwise clear.
- verdict: "clear" or "veto".
- reading: the losing reading of the rules ("" when clear).
- scenario: the concrete sequence of events in which the forecast is right but the position loses ("" when clear).

""" + CONTEXT


def parse_27(r: LLMResult, neg_risk: bool = False) -> tuple[str, list[str]]:
    """("clear" | "veto" | "error", reasons). Silence (empty answer) on any material point or dispute risk high vetoes."""
    if not r.ok or not valid(r.data, R27):
        return "error", [r.error or "schema mismatch"]
    d = r.data
    why = [f"silent on {p}" for p in POINTS if not d[p].strip()]
    if neg_risk and d["neg_risk_exactly_one_yes"] == "not applicable":
        why.append("silent on neg_risk_exactly_one_yes for a negRisk market")
    if d["dispute_risk"] == "high":
        why.append("dispute risk high")
    if d["verdict"] != "clear":
        why += ["auditor veto", *d["reasons"]]
    return ("veto" if why else "clear"), why


def parse_28(r: LLMResult) -> tuple[str, list[str]]:
    """A veto needs a concrete losing reading and scenario; without them it is malformed, which is still a veto."""
    if not r.ok or not valid(r.data, R28):
        return "error", [r.error or "schema mismatch"]
    d = r.data
    if d["verdict"] == "clear":
        return "clear", []
    if not (d["reading"].strip() and d["scenario"].strip()):
        return "veto", ["malformed veto: no concrete losing reading"]
    return "veto", [f"losing reading: {d['reading'].strip()}; scenario: {d['scenario'].strip()}"]


def _role(gateway, role: str, prompt: str, schema: dict, parse, qualified) -> tuple[RoleVerdict, list[LLMResult]]:
    results = gateway.complete(role, prompt, schema, vendors=2)
    votes, reasons = [], []
    for r in results:
        vote, why = parse(r)
        votes.append((r.vendor, vote))
        who = f"{r.vendor}/{r.model}" if r.model else r.vendor
        reasons += [f"{who}: {w}" for w in why]
        if vote == "clear" and (r.vendor, r.model) not in qualified:
            reasons.append(f"{who}: model not qualified")
    if len({r.vendor for r in results}) < 2:
        reasons.append("needs two different vendors")
    ok = len(results) == 2 and all(v == "clear" for _, v in votes) and not reasons
    return RoleVerdict(role, "clear" if ok else "veto", tuple(dict.fromkeys(reasons)), tuple(votes)), results


def clear_template(gateway, key: dict, question: str, rules_text: str, now_ms: int, qualified=QUALIFIED,
                   db=LLM_DB, keys_out=KEYS_OUT, days: float = 7.0) -> tuple[bool, list[RoleVerdict]]:
    # The rules hash is 64 hex (the gateway refuses that shape as a possible private key): the prompt carries the rules
    # text itself plus the resolution-relevant key fields, so a tick or fee change reuses the cached audit.
    ctx = dict(question=question, rules=rules_text,
               fields=json.dumps({k: key[k] for k in ("template", "neg_risk", "source_id")}))
    v27, r27 = _role(gateway, "27-resolution", PROMPT_27.format(**ctx), R27,
                     lambda r: parse_27(r, bool(key["neg_risk"])), qualified)
    v28, r28 = _role(gateway, "28-wording", PROMPT_28.format(**ctx), R28, parse_28, qualified)
    cleared = v27.verdict == v28.verdict == "clear"
    if cleared:
        append_jsonl(pathlib.Path(keys_out), {"key": key, "question": question})
        secret = os.environ.get("ROSTER_ADVISOR_KEY", "")
        if (secret and secret != os.environ.get("ROSTER_HUMAN_KEY")
                and pathlib.Path(db).resolve() != ADVICE_DB.resolve()):
            signer = "llm-board:" + "+".join(sorted({f"{r.vendor}/{r.model}" for r in (*r27, *r28)}))
            write(pathlib.Path(db), {"type": "clearance", "key": key, "signer": signer,
                                     "expiry_ms": now_ms + int(days * 86_400_000)}, secret)
    return cleared, [v27, v28]


def _rows(path: pathlib.Path) -> list[dict]:
    """The kernel's {"key", "cid", "question"} JSONL, a JSONL of key dicts, or a JSON list of either."""
    text = path.read_text(encoding="utf-8").strip()
    return json.loads(text) if text.startswith("[") else [json.loads(x) for x in text.splitlines() if x.strip()]


def _cell(s: str) -> str:
    return s.replace("|", "/").replace("\n", " ")[:400]


def agree(backlog, snapshot, human_db, out, gateway, db=LLM_DB, keys_out=KEYS_OUT, now: int | None = None) -> dict:
    now = now or now_ms()
    snap = [json.loads(x) for x in pathlib.Path(snapshot).read_text(encoding="utf-8").splitlines() if x.strip()]
    by_cid = {s.get("condition_id"): s for s in snap}
    by_hash = {s.get("rules_sha256"): s for s in snap}
    human, _ = load_advice(human_db)  # read-only; signatures are not checked here (the advisor never holds the human key)
    before = gateway.quota_left()
    counts, table = collections.Counter(), []
    for row in _rows(pathlib.Path(backlog)):
        key = row.get("key", row)
        if sorted(key) != sorted(KEY_FIELDS):
            counts["skipped (bad key)"] += 1
            continue
        s = by_cid.get(row.get("cid"))
        if not s or s.get("rules_sha256") != key["rules_sha256"]:  # the cid's rules changed: use the key's own text
            s = by_hash.get(key["rules_sha256"])
        if s is None:
            cleared, reasons, votes = False, ["no rules text for this rules hash in the snapshot"], ""
        else:
            cleared, vs = clear_template(gateway, key, row.get("question") or s.get("question", ""),
                                         s["rules_text"], now, db=db, keys_out=keys_out)
            reasons = [f"{v.role}: {w}" for v in vs for w in v.reasons]
            votes = "; ".join(f"{v.role[:2]} " + ",".join(f"{a}={b}" for a, b in v.vendor_votes) for v in vs)
        rec = human.get(key_id(key))
        h = bool(rec and rec.get("key") == key and rec.get("expiry_ms", 0) > now)
        cat = {(True, True): "agree-cleared", (False, False): "agree-not-cleared",
               (True, False): "board-only", (False, True): "human-only"}[(cleared, h)]
        counts[cat] += 1
        table.append(f"| {_cell(key['template'])} | {key['rules_sha256'][:10]} | tick {key['tick_size']} fee "
                     f"{key['fee_rate']} | {'clear' if cleared else 'veto'} | {'clear' if h else '-'} | {cat} | "
                     f"{_cell(votes)} | {_cell('; '.join(reasons)) or '-'} |")
    after = gateway.quota_left()
    used = {v: max(0, before[v] - after.get(v, before[v])) for v in before}  # ponytail: wrong across UTC midnight
    iso = datetime.datetime.fromtimestamp(now / 1000, datetime.UTC).strftime("%Y-%m-%dT%H:%MZ")
    signing = "set: cleared templates were signed" if os.environ.get("ROSTER_ADVISOR_KEY") else "unset: nothing signed"
    lines = [
        "# Phase 4 agreement report: LLM clearance board vs human clearances", "",
        f"Run {iso}. Backlog `{backlog}`; snapshot `{snapshot}`; human clearances `{human_db}` "
        f"({len(human)} records, read-only); board records `{db}` (ROSTER_ADVISOR_KEY {signing}).", "",
        *([f"**No vendor had quota or a key** ({', '.join(f'{v}: 0' for v in before)}), so nothing could clear: the "
           "board failed closed. This is not a qualification run.", ""] if not any(before.values()) else []),
        "## Agreement", "",
        "| | Human cleared | Human not cleared |", "|---|---|---|",
        f"| **Board cleared** | agree-cleared: {counts['agree-cleared']} | board-only: {counts['board-only']} |",
        f"| **Board not cleared** | human-only: {counts['human-only']} | agree-not-cleared: {counts['agree-not-cleared']} |",
        "", f"Skipped (key fields not exactly {', '.join(KEY_FIELDS)}): {counts['skipped (bad key)']}.", "",
        "## Per template", "",
        "| Template | Rules | Key | Board | Human | Category | Vendor votes | Reasons |",
        "|---|---|---|---|---|---|---|---|", *table, "",
        "## Vendor calls used", "",
        "| Vendor | Calls sent this run | Left today |", "|---|---|---|",
        *[f"| {v} | {used[v]} | {after.get(v, 0)} |" for v in before],
        "", "Cache hits are free and not counted. A vendor without a key shows 0 left.", "",
        "## How to reproduce", "", "From the code root (the backlog is the kernel's `RiskKernel.dump_uncleared()` output "
        "or any JSONL of clearance keys; vendor keys come from env GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY):",
        "", "```",
        f".venv\\Scripts\\python.exe -m advisor.board agree --backlog {backlog} --snapshot {snapshot} "
        f"--human-db {human_db} --out {out}", "```", ""]
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(out).write_text("\n".join(lines), encoding="utf-8")
    return dict(counts, calls=sum(used.values()))


def main(argv=None, gateway=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("agree", help="run the board over a backlog and compare with human clearances")
    a.add_argument("--backlog", type=pathlib.Path, default=DATA / "trader" / "uncleared.jsonl")
    a.add_argument("--snapshot", type=pathlib.Path, default=None, help="crawler JSONL (default: latest)")
    a.add_argument("--human-db", type=pathlib.Path, default=ADVICE_DB)
    a.add_argument("--out", type=pathlib.Path, default=REPORTS / "phase4_agreement.md")
    a.add_argument("--db", type=pathlib.Path, default=LLM_DB)
    a.add_argument("--keys-out", type=pathlib.Path, default=KEYS_OUT)
    a.add_argument("--gateway-db", type=pathlib.Path, default=GATEWAY_DB)
    args = ap.parse_args(argv)
    snapshot = args.snapshot or sorted((DATA / "markets").glob("*Z.jsonl"))[-1]
    res = agree(args.backlog, snapshot, args.human_db, args.out, gateway or LLMGateway(args.gateway_db),
                db=args.db, keys_out=args.keys_out)
    print(json.dumps(res), f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
