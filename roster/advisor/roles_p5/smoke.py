"""python -m advisor.roles_p5.smoke: roles 24, 30, 31 and 26 against a scripted fake gateway (no vendor, no network).
Uses public question and rules text from the latest data/markets/ snapshot and synthetic sample headlines, and writes
reports/phase5_advisor_smoke.md. The shadow log of this run goes to advisor/roles_p5/out/shadow_smoke.jsonl (rewritten
each run), never to the permanent research log.
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib

from advisor.contracts import LLMResult
from advisor.roles_p5 import board, shadow, shock
from common import DATA, REPORTS

REPORT = REPORTS / "phase5_advisor_smoke.md"
LOG = pathlib.Path(__file__).resolve().parent / "out" / "shadow_smoke.jsonl"
FAKE_SECRET = "smoke-fake-secret-value-0001"  # set in env only while the secret case runs


class Scripted:
    """Fake Gateway. answer(task, prompt, i) -> dict (ok answer) or str (error) for the i-th vendor asked. Vendors
    with no quota left answer ok=False "quota exhausted". Records every call."""

    def __init__(self, answer, vendors: int = 8, quota: int = 1000):
        self.answer, self.calls = answer, []
        self.quota = {f"fake{i + 1}": quota for i in range(vendors)}

    def complete(self, task, prompt, schema, vendors=1):
        self.calls.append((task, prompt))
        out, names = [], list(self.quota)
        for i in range(vendors):
            v = names[i % len(names)]
            if self.quota[v] <= 0:
                out.append(LLMResult(v, f"{v}-model", False, None, "quota exhausted", False, 0))
                continue
            self.quota[v] -= 1
            a = self.answer(task, prompt, i)
            ok = isinstance(a, dict)
            out.append(LLMResult(v, f"{v}-model", ok, a if ok else None, None if ok else a, False, 10))
        return out

    def quota_left(self):
        return dict(self.quota)


def latest_snapshot() -> tuple[str, list[dict]]:
    path = sorted((DATA / "markets").glob("*Z.jsonl"))[-1]
    return path.stem, [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def table(head: list[str], rows: list[list]) -> list[str]:
    cell = lambda x: str(x).replace("|", "/").replace("\n", " ")
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head), *("| " + " | ".join(map(cell, r)) + " |" for r in rows)]


def verdict_row(name: str, v, calls: int) -> list:
    return [name, calls, v.verdict, ", ".join(f"{a}:{b}" for a, b in v.vendor_votes) or "-", "; ".join(v.reasons)[:300]]


SHOCK = {"is_shock": True, "underlyings": ["ETH"], "severity": "high", "reason": "exchange exploit", "direction": "down"}
CLEAR30 = {"verdict": "clear", "hidden_links": []}
CLEAR31 = {"verdict": "clear", "violations": []}
CASES = ("ok=False", "malformed", "missing field", "quota exhausted", "secret in prompt")


def headlines(now: int) -> list[dict]:
    """Synthetic sample headlines (not real news), one per path through role 24."""
    h = lambda i, title, rec=now - 60_000: {"id": f"n{i}", "source": "sample", "ts_ms": rec - 30_000,
                                            "recorded_ms": rec, "title": title, "body": ""}
    return [h(1, "Exchange hot-wallet exploit: ETH withdrawals paused"),
            h(2, "Largest dollar stablecoin depegs as issuer reports insolvency"),
            h(3, "Spot bitcoin ETF inflows rise for a third day"),
            h(4, "Exchange schedules a two-hour maintenance outage for Sunday"),
            h(5, "DeFi lending protocol hack drains a liquidity pool"),
            h(6, "Second exchange reports a hack", rec=now + 60_000)]


def answer_24(task, prompt, i):
    if "hot-wallet" in prompt:
        return SHOCK                                     # carries an extra "direction" the reader must drop
    if "depegs" in prompt:
        return {"is_shock": True, "underlyings": ["ALL"], "severity": "medium", "reason": "stablecoin depeg"}
    if "maintenance" in prompt:
        return {"is_shock": False, "underlyings": [], "severity": "low", "reason": "scheduled maintenance"}
    return {"is_shock": True}                            # malformed: fail closed


def run_24(now: int, out: list[str]) -> None:
    gw, items = Scripted(answer_24), headlines(now)
    sigs = shock.ShockReader().read(items, now, gw)
    out += ["## Role 24, crypto shock reader (LLM part)", "",
            f"Enabled underlyings {shock.ENABLED}. {len(items)} synthetic headlines, {len(gw.calls)} gateway calls "
            "(unmatched and late items make none). Prompt sha256 `" + shock.PROMPT_SHA256 + "`.", ""]
    out += table(["item", "title", "keyword match", "recorded after now", "signals"],
                 [[it["id"], it["title"], shock.matches(it), it["recorded_ms"] > now,
                   ", ".join(f"{s.action} {s.scope} x{s.shrink_factor} {(s.expires_ms - now) // 60_000} min "
                             f"fresh-obs={s.resume_requires_fresh_observation}"
                             for s in sigs if f"item {it['id']}" in s.reason) or "-"] for it in items])
    fields = sorted({k for s in sigs for k in vars(s)})
    out += ["", f"Signal fields: {fields}. No direction field exists; the vendor's extra \"direction\" was dropped.", ""]


def run_30(snapshot: list[dict], out: list[str]) -> None:
    groups: dict[str, list[dict]] = {}
    for m in snapshot:
        groups.setdefault(m["event_slug"], []).append(m)
    new = next(g for g in groups if g.startswith("bitcoin-above"))
    eth = next((g for g in groups if g.startswith("ethereum")), None)
    sport = next((g for g, ms in groups.items() if ms[0]["mode"].startswith("sports")), None)
    held = {g: groups[g] for g in (eth, sport) if g}
    link = {"verdict": "veto", "hidden_links": [{"other_group": eth or "-", "mechanism": "BTC and ETH strikes settle "
                                                 "on the same noon ET Binance print; one crypto move hits both"}]}
    gw, adv = Scripted(lambda t, p, i: CLEAR30), board.CorrelationAdversary()
    rows = [verdict_row("first entry, cap 100", adv.review(new, groups[new], held, 100, gw), len(gw.calls))]
    for _ in range(100):
        adv.review(new, groups[new], held, 100, gw)
    rows.append(verdict_row("100 repeats at cap 100, then cap 50", adv.review(new, groups[new], held, 50, gw), len(gw.calls)))
    gw.answer = lambda t, p, i: link if i == 1 else CLEAR30   # the second vendor finds a hidden link
    rows.append(verdict_row("cap raise to 250", adv.review(new, groups[new], held, 250, gw), len(gw.calls)))
    out += ["## Role 30, correlation adversary", "",
            f"New group `{new}` ({len(groups[new])} markets); held: {', '.join(f'`{g}`' for g in held) or 'none'}. "
            "The cap is a cache key only and never reaches a prompt. `calls` is the cumulative gateway call count.", ""]
    out += table(["review", "calls", "verdict", "votes", "reasons"], rows) + [""]


CHANGES = [
    ("lower quote_size (not flagged)", {"kind": "learned", "name": "btc-eth-ladder", "old": {"quote_size": 10.0},
                                        "new": {"quote_size": 8.0}}),
    ("raise quote_size, no pre-registration", {"kind": "learned", "name": "btc-eth-ladder",
                                               "old": {"quote_size": 10.0}, "new": {"quote_size": 12.0}}),
    ("raise c_shrink, evidence below n", {"kind": "learned", "name": "btc-eth-ladder", "old": {"c_shrink": 0.3},
                                          "new": {"c_shrink": 0.4}, "prereg": {"n": 60, "pass_z": 2.0},
                                          "evidence": {"n": 41, "mean": 0.02, "se": 0.005}}),
    ("kappa change, failed test", {"kind": "learned", "name": "kappa", "old": {"24": 0.95}, "new": {"24": 1.02},
                                   "prereg": {"n": 60, "pass_z": 2.0}, "evidence": {"n": 75, "mean": 0.001, "se": 0.004}}),
    ("raise c_shrink, passing evidence", {"kind": "learned", "name": "btc-eth-ladder", "old": {"c_shrink": 0.3},
                                          "new": {"c_shrink": 0.4}, "prereg": {"n": 60, "pass_z": 2.0},
                                          "evidence": {"n": 64, "mean": 0.03, "se": 0.01}}),
    ("code change to trader/kernel.py", {"kind": "code", "name": "kernel-retry", "paths": ["trader/kernel.py"],
                                         "diff": "-    raise UnknownState(order_id)\n+    return self.resubmit(order_id)"}),
]


def run_31(out: list[str]) -> None:
    gate, rows = board.ChangeGate(), []
    veto_retry = {"verdict": "veto", "violations": ["no retry on unknown order state: resubmit after UnknownState"]}
    for name, ch in CHANGES:
        gw = Scripted(lambda t, p, i: veto_retry if "resubmit" in p and i == 1 else CLEAR31)
        rows.append([name, ", ".join(board.rule7(ch)) or "-", *verdict_row(name, gate.review(ch, gw), len(gw.calls))[1:]])
    out += ["## Role 31, change gate", "",
            "Rule 7 first, then the evidence check (flagged learned changes only, judged from the numbers), then a "
            "2-vendor review that sees directions and relative moves, never values or evidence.", ""]
    out += table(["change", "rule-7 flags", "calls", "verdict", "votes", "reasons"], rows) + [""]


def sample_markets(snapshot: list[dict], n: int = 4) -> list[dict]:
    """Public question and rules text; mid_ex_own is a synthetic placeholder (the smoke has no live price)."""
    picks = [m for m in snapshot if m["mode"] == "sports-pregame"][:2] + [m for m in snapshot if m["mode"] == "crypto-term"][:n - 2]
    return [{"cid": m["condition_id"], "cluster_id": m["event_slug"], "mode": m["mode"], "question": m["question"],
             "rules_text": m["rules_text"], "end_time": m["end_time"], "mid_ex_own": 0.5} for m in picks]


def answer_26(task, prompt, i):
    p = int(hashlib.sha256(f"{prompt}{i}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    if "fail-half" in prompt and i % 2:
        return "HTTP 429 from vendor"
    return {"p": round(0.15 + 0.7 * p, 3), "rationale": "base rate"}


def run_26(snapshot: list[dict], now: int, log: pathlib.Path, out: list[str]) -> None:
    mk = sample_markets(snapshot)
    mk[-1] = {**mk[-1], "question": mk[-1]["question"] + " (fail-half)"}   # 3 of 6 vendors fail -> insufficient
    gw = Scripted(answer_26)
    rows = [shadow.forecast(m, now, gw, method="median" if i % 2 == 0 else "trimmed", log_path=log)
            for i, m in enumerate(mk)]
    out += ["## Role 26, shadow forecaster", "",
            f"{len(mk)} markets from the snapshot, 6 fake vendors each ({len(gw.calls)} gateway calls). Platt is the "
            "identity (no resolved rows yet); the mid is a synthetic 0.5 placeholder. Prompt sha256 `"
            + shadow.PROMPT_SHA256 + "`.", ""]
    out += table(["market", "mode", "status", "usable", "method", "combined", "calibrated", "blended"],
                 [[r["cluster_id"], r["mode"], r["status"], sum(m["p"] is not None for m in r["models"]), r["method"],
                   r["combined"] and round(r["combined"], 3), r["calibrated"] and round(r["calibrated"], 3),
                   r["blended"] and round(r["blended"], 3)] for r in rows])
    gw2 = Scripted(answer_26, vendors=6, quota=2)
    batch = shadow.run_batch(sample_markets(snapshot, 6), now, gw2, max_markets=6, log_path=log)
    out += ["", f"run_batch with 6 vendors x 2 requests of quota: {len(batch)} forecasts, then it stopped "
            f"(quota left {gw2.quota_left()}, fewer than {shadow.MIN_MODELS} vendors with quota).",
            f"Log: `{log.name}`, {len(log.read_text().splitlines())} lines.", ""]


def fail_closed(snapshot: list[dict], now: int, log: pathlib.Path, out: list[str]) -> None:
    good = {"24": SHOCK, "30": CLEAR30, "31": CLEAR31, "26": {"p": 0.6, "rationale": "x"}}
    malformed = {"24": {"underlyings": "ETH"}, "30": {"verdict": "maybe"}, "31": {"violations": "none"}, "26": {"p": "0.6"}}
    missing = {"24": "severity", "30": "hidden_links", "31": "violations", "26": "p"}
    item = headlines(now)[0]
    m = sample_markets(snapshot)[0]
    group = [{"question": m["question"], "rules_text": m["rules_text"]}]
    change = CHANGES[0][1]
    rows = []
    for case in CASES:
        def answer(role):
            g = good[role]
            if case == "ok=False":
                return "HTTP 503 from vendor"
            if case == "malformed":
                return {**g, **malformed[role]}
            if case == "missing field":
                return {k: v for k, v in g.items() if k != missing[role]}
            return g

        def gw(role):
            return Scripted(lambda t, p, i: answer(role), quota=0 if case == "quota exhausted" else 1000)

        secret = case == "secret in prompt"
        if secret:
            os.environ["POLY_API_SECRET"] = FAKE_SECRET
        try:
            tag = f" {FAKE_SECRET}" if secret else ""
            g24, g30, g31, g26 = gw("24"), gw("30"), gw("31"), gw("26")
            s = shock.ShockReader().read([{**item, "body": tag}], now, g24)
            v30 = board.CorrelationAdversary().review("g", [{**group[0], "question": group[0]["question"] + tag}], {}, 1, g30)
            v31 = board.ChangeGate().review({**change, "name": change["name"] + tag}, g31)
            r26 = shadow.forecast({**m, "question": m["question"] + tag}, now, g26, log_path=log)
        finally:
            os.environ.pop("POLY_API_SECRET", None)
        rows.append([case, f"{len(s)} pulls ({', '.join(x.scope for x in s)}), calls {len(g24.calls)}",
                     f"{v30.verdict}, calls {len(g30.calls)}", f"{v31.verdict}, calls {len(g31.calls)}",
                     f"{r26['status']}, {sum(x['p'] is None for x in r26['models'])} excluded, calls {len(g26.calls)}"])
    out += ["## Fail-closed cases", "",
            "Every vendor answers the same failure. Role 24 pulls every enabled underlying, roles 30 and 31 veto, and role "
            "26 excludes the answers (status `insufficient` below 4 usable). A prompt holding the value of an env var "
            "named like a secret is never sent (0 calls).", ""]
    out += table(["case", "role 24", "role 30", "role 31", "role 26"], rows) + [""]


def main(report: pathlib.Path = REPORT, log: pathlib.Path = LOG) -> str:
    snap_name, snapshot = latest_snapshot()
    now = int(datetime.datetime.strptime(snap_name, "%Y-%m-%dT%H%M%SZ").replace(tzinfo=datetime.timezone.utc).timestamp() * 1000)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.unlink(missing_ok=True)
    out = ["# Phase 5 advisor roles smoke (WP5-D)", "",
           f"All four roles run against a scripted fake gateway (no vendor call, no network, no key). Market text comes "
           f"from `data/markets/{snap_name}.jsonl` ({len(snapshot)} markets); headlines are synthetic samples. "
           f"`now` = the snapshot time. Prompt hashes: board `{board.PROMPT_SHA256[:16]}`, shock "
           f"`{shock.PROMPT_SHA256[:16]}`, shadow `{shadow.PROMPT_SHA256[:16]}`.", ""]
    run_24(now, out)
    run_30(snapshot, out)
    run_31(out)
    run_26(snapshot, now, log, out)
    fail_closed(snapshot, now, log, out)
    out += ["## How to reproduce", "", "From the code root (`roster/`):", "", "```",
            r".venv\Scripts\python.exe -m advisor.roles_p5.smoke",
            r".venv\Scripts\python.exe -m pytest tests/phase5/test_advisor_roles.py -q", "```", "",
            "The smoke reads the latest `data/markets/*Z.jsonl` snapshot, makes no network call and needs no key. It "
            "rewrites this report and `advisor/roles_p5/out/shadow_smoke.jsonl`.", ""]
    text = "\n".join(out)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report", type=pathlib.Path, default=REPORT)
    ap.add_argument("--log", type=pathlib.Path, default=LOG)
    a = ap.parse_args()
    main(a.report, a.log)
    print(f"wrote {a.report}")
