"""WP5-D: advisor roles 24 (shock LLM part), 30, 31 and 26 against a fake Gateway. Offline; any socket connect fails."""
import json
import pathlib
import re
import socket

import numpy as np
import pytest

from advisor.contracts import LLMResult
from advisor.roles_p5 import board, shadow, shock
from advisor.roles_p5.board import ChangeGate, CorrelationAdversary, rule7
from advisor.roles_p5.shock import ShockReader
from common import ROOT

NOW = 1_790_000_000_000
PKG = ROOT / "advisor" / "roles_p5"
# sentinels for size, price paid, balance, P&L, evidence, cap and the market mid: none may reach a prompt
SIZE, PAID, BALANCE, PNL, EVIDENCE, CAP, MID = 917253.5, 0.8317, 73519.25, -6143.75, 0.004271, 2718.5, 0.4137
SENTINELS = [str(x) for x in (SIZE, PAID, BALANCE, PNL, EVIDENCE, CAP, MID)] + ["0.0517293"]
PRIVATE = {"size": SIZE, "price_paid": PAID, "balance": BALANCE, "pnl": PNL, "evidence": EVIDENCE, "cap": CAP}
SECRET = "sentinel-secret-7f3a9c"

G24 = {"is_shock": True, "underlyings": ["ETH"], "severity": "high", "reason": "exchange exploit"}
G30 = {"verdict": "clear", "hidden_links": []}
G31 = {"verdict": "clear", "violations": []}
G26 = {"p": 0.6, "rationale": "base rate"}
MALFORMED = {"24": {"underlyings": "ETH"}, "30": {"verdict": "maybe"}, "31": {"violations": "none"}, "26": {"p": "0.6"}}
MISSING = {"24": "severity", "30": "hidden_links", "31": "violations", "26": "p"}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def refuse(*a, **k):
        raise RuntimeError("network disabled in tests")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.delenv("POLY_API_SECRET", raising=False)


class FakeGW:
    """answer(task, prompt, i) -> dict (ok answer) or str (error) for the i-th vendor. Vendors without quota answer
    ok=False "quota exhausted". Records every prompt."""

    def __init__(self, answer, vendors=10, quota=100):
        self.answer, self.calls = answer, []
        self.quota = {f"v{i}": quota for i in range(vendors)}

    def complete(self, task, prompt, schema, vendors=1):
        self.calls.append((task, prompt, vendors))
        names, out = list(self.quota), []
        for i in range(vendors):
            v = names[i % len(names)]
            if self.quota[v] <= 0:
                out.append(LLMResult(v, f"m-{v}", False, None, "quota exhausted", False, 0))
                continue
            self.quota[v] -= 1
            a = self.answer(task, prompt, i)
            ok = isinstance(a, dict)
            out.append(LLMResult(v, f"m-{v}", ok, a if ok else None, None if ok else a, False, 1))
        return out

    def quota_left(self):
        return dict(self.quota)


def const(a):
    return FakeGW(lambda t, p, i: a)


def item(title="Exchange hack drains hot wallet", recorded=NOW - 1000, **kw):
    return {"id": "n1", "source": "sample", "ts_ms": recorded - 1000, "recorded_ms": recorded, "title": title,
            "body": kw.pop("body", "Funds were moved out overnight."), **kw}


MARKET = {"cid": "0xabc", "cluster_id": "g1", "mode": "crypto-event", "question": "Will exchange X relist token Y by June?",
          "rules_text": "Resolves Yes if exchange X lists Y before the end date.", "end_time": "2026-12-31T00:00:00Z",
          "mid_ex_own": MID}
GROUP = [{"question": "Will BTC be above $74,000 on October 1?", "rules_text": "Binance BTC/USDT 12:00 ET close."}]
HELD = {"eth-oct-1": [{"question": "Will ETH be above $4,000 on October 1?", **PRIVATE}]}
LOWER = {"kind": "learned", "name": "ladder", "old": {"quote_size": SIZE}, "new": {"quote_size": SIZE / 2}}
PASSING = {"prereg": {"n": 60, "pass_z": 2.0, "balance": BALANCE},
           "evidence": {"n": 64, "mean": 0.0517293, "se": EVIDENCE, "pnl": PNL, "size": SIZE, "price_paid": PAID}}


def run_all(log, tag="", answers=None, quota=100):
    """Each role once with private sentinels in its inputs; `tag` is appended to text that goes into each prompt."""
    a = answers or {"24": G24, "30": G30, "31": G31, "26": G26}
    gws = {r: FakeGW(lambda t, p, i, r=r: a[r], quota=quota) for r in a}
    out = {"24": ShockReader().read([item(body="Funds moved." + tag, **PRIVATE)], NOW, gws["24"]),
           "30": CorrelationAdversary().review("g", [{**GROUP[0], "question": GROUP[0]["question"] + tag, **PRIVATE}],
                                               HELD, CAP, gws["30"]),
           "31": ChangeGate().review({**LOWER, "name": "ladder" + tag, **PASSING}, gws["31"]),
           "26": shadow.forecast({**MARKET, "question": MARKET["question"] + tag, **PRIVATE}, NOW, gws["26"],
                                 log_path=log)}
    return out, gws


# ---------- D1, D8, D12 greps ----------

def test_d1_no_network_or_vendor_imports():
    bad = re.compile(r"^\s*(import|from)\s+(httpx|urllib|requests|aiohttp|websockets|socket|openai|anthropic|google|groq)")
    hits = [f"{p.name}:{n}" for p in PKG.glob("*.py") for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if bad.match(line)]
    assert hits == []


def test_d8_board_has_no_promote_or_registry_write():
    text = (PKG / "board.py").read_text(encoding="utf-8")
    assert not re.search(r"promote\(|\.register\(|\.record\(", text)


def test_d12_nothing_outside_reads_shadow():
    hits = [str(p) for d in ("trader", "learning", "nightly") if (ROOT / d).exists()
            for p in (ROOT / d).rglob("*.py") if re.search(r"roles_p5\.shadow|shadow_research", p.read_text(encoding="utf-8", errors="ignore"))]
    assert hits == []


def test_prompt_hashes_exposed():
    for mod in (board, shock, shadow):
        assert re.fullmatch(r"[0-9a-f]{64}", mod.PROMPT_SHA256)


# ---------- D2 prompt hygiene ----------

def test_d2_no_private_value_reaches_a_prompt(monkeypatch, tmp_path):
    monkeypatch.setenv("POLY_API_SECRET", SECRET)
    out, gws = run_all(tmp_path / "log.jsonl")
    prompts = [p for g in gws.values() for _, p, _ in g.calls]
    assert len(prompts) == 4 and out["30"].verdict == "clear" and out["31"].verdict == "clear"
    for s in [*SENTINELS, SECRET]:
        assert not any(s in p for p in prompts), s


def test_d2_secret_in_prompt_is_never_sent(monkeypatch, tmp_path):
    monkeypatch.setenv("POLY_API_SECRET", SECRET)
    out, gws = run_all(tmp_path / "log.jsonl", tag=" " + SECRET)
    assert all(g.calls == [] for g in gws.values())
    assert sorted(s.scope for s in out["24"]) == ["BTC", "ETH"] and all(s.action == "pull" for s in out["24"])
    assert out["30"].verdict == "veto" and out["31"].verdict == "veto"
    assert out["26"]["status"] == "insufficient" and out["26"]["combined"] is None


# ---------- D3 fail closed ----------

def bad_answer(case, role, good):
    if case == "notok":
        return "HTTP 503"
    if case == "malformed":
        return {**good, **MALFORMED[role]}
    return {k: v for k, v in good.items() if k != MISSING[role]}


@pytest.mark.parametrize("case", ["notok", "malformed", "missing", "quota"])
def test_d3_fail_closed(case, tmp_path):
    goods = {"24": G24, "30": G30, "31": G31, "26": G26}
    answers = goods if case == "quota" else {r: bad_answer(case, r, g) for r, g in goods.items()}
    out, gws = run_all(tmp_path / "log.jsonl", answers=answers, quota=0 if case == "quota" else 100)
    assert sorted(s.scope for s in out["24"]) == ["BTC", "ETH"]
    assert all(s.action == "pull" and s.shrink_factor == 0.0 and s.resume_requires_fresh_observation for s in out["24"])
    assert out["30"].verdict == "veto" and out["31"].verdict == "veto"
    assert out["26"]["status"] == "insufficient" and all(m["p"] is None and m["error"] for m in out["26"]["models"])


@pytest.mark.parametrize("case", ["notok", "malformed", "missing"])
def test_d3_one_bad_vendor_vetoes_and_is_excluded(case, tmp_path):
    for role, good, review in (("30", G30, lambda gw: CorrelationAdversary().review("g", GROUP, {}, 1, gw)),
                               ("31", G31, lambda gw: ChangeGate().review(LOWER, gw))):
        gw = FakeGW(lambda t, p, i: bad_answer(case, role, good) if i == 1 else good)
        v = review(gw)
        assert v.verdict == "veto" and dict(v.vendor_votes)["v1"] == "error" and dict(v.vendor_votes)["v0"] == "clear"
    gw = FakeGW(lambda t, p, i: bad_answer(case, "26", G26) if i == 0 else G26)
    r = shadow.forecast(MARKET, NOW, gw, log_path=tmp_path / "l.jsonl")
    assert r["status"] == "ok" and [m["p"] for m in r["models"]][0] is None and len(r["models"]) == 6


def test_d3_shadow_partial_quota_excludes(tmp_path):
    gw = FakeGW(lambda t, p, i: G26, vendors=5)
    gw.quota["v4"] = 0                            # 4 vendors with quota, 6 asked (two land on exhausted v4 / repeats)
    r = shadow.forecast(MARKET, NOW, gw, log_path=tmp_path / "l.jsonl")
    assert r["status"] == "ok" and sum(m["p"] is not None for m in r["models"]) == 4


# ---------- D4 role 24 ----------

def test_d4_unmatched_item_makes_no_call():
    gw = const(G24)
    assert ShockReader().read([item("Spot bitcoin ETF inflows rise for a third day", body="Steady demand.")], NOW, gw) == []
    assert gw.calls == []


@pytest.mark.parametrize("title", ["Protocol exploit", "Treasury drained", "Stablecoin depegs", "Lender insolvent",
                                   "Firm files for bankruptcy", "Withdrawals halted at exchange",
                                   "Exchange suspends withdrawals", "Token delisted", "Country to ban trading",
                                   "SEC files charges", "Emergency shutdown", "Exchange outage"])
def test_d4_keywords_match(title):
    assert shock.matches(item(title, body=""))


@pytest.mark.parametrize("title", ["Bank earnings beat", "Urban mining grows", "Charger sales up"])
def test_d4_keywords_do_not_overmatch(title):
    assert not shock.matches(item(title, body=""))


def test_d4_confirmed_eth_shock_one_pull_no_direction():
    gw = const({**G24, "direction": "down", "price_target": 1500})
    sigs = ShockReader().read([item()], NOW, gw)
    assert len(gw.calls) == 1 and gw.calls[0][2] == 1 and gw.calls[0][0] == "24-crypto-shock"
    assert len(sigs) == 1
    s = sigs[0]
    assert (s.scope, s.action, s.role) == ("ETH", "pull", "24-crypto-event")
    assert s.shrink_factor <= 1 and s.resume_requires_fresh_observation and s.expires_ms == NOW + shock.EXPIRY_MS["high"]
    assert "direction" not in vars(s) and "down" not in s.reason and "1500" not in s.reason


def test_d4_all_and_not_shock_and_disabled():
    sigs = ShockReader().read([item()], NOW, const({**G24, "underlyings": ["ALL"], "severity": "low"}))
    assert sorted(s.scope for s in sigs) == ["BTC", "ETH"] and {s.expires_ms for s in sigs} == {NOW + 15 * 60_000}
    sigs = ShockReader(enabled=("BTC", "ETH", "SOL")).read([item()], NOW, const({**G24, "underlyings": ["ALL"]}))
    assert sorted(s.scope for s in sigs) == ["BTC", "ETH", "SOL"]
    assert ShockReader().read([item()], NOW, const({**G24, "is_shock": False, "underlyings": []})) == []
    assert ShockReader().read([item()], NOW, const({**G24, "underlyings": ["XRP"]})) == []   # not enabled


def test_d4_item_recorded_after_now_ignored():
    gw = const(G24)
    assert ShockReader().read([item(recorded=NOW + 1)], NOW, gw) == [] and gw.calls == []


def test_d4_bad_recorded_ms_skipped_not_fatal():
    bad = [item(), item()]
    del bad[0]["recorded_ms"]
    bad[1]["recorded_ms"] = None
    gw = const(G24)
    sigs = ShockReader().read([*bad, item()], NOW, gw)
    assert len(gw.calls) == 1 and [s.scope for s in sigs] == ["ETH"]   # the good item still pulls


# ---------- D5 role 30 ----------

def test_d5_cache_and_cap_raise():
    gw, adv = const(G30), CorrelationAdversary()
    for _ in range(100):
        assert adv.review("g", GROUP, HELD, 100, gw).verdict == "clear"
    assert len(gw.calls) == 1 and gw.calls[0][2] == 2
    adv.review("g", GROUP, HELD, 50, gw)
    assert len(gw.calls) == 1
    adv.review("g", GROUP, HELD, 101, gw)
    assert len(gw.calls) == 2
    assert not any(str(c) in p for _, p, _ in gw.calls for c in (100, 101, CAP))
    assert "Will ETH be above $4,000" in gw.calls[0][1] and "Binance BTC/USDT 12:00 ET close." in gw.calls[0][1]


def test_d5_clear_needs_two_distinct_clear_vendors_without_links():
    link = {"verdict": "clear", "hidden_links": [{"other_group": "eth-oct-1", "mechanism": "same noon ET print"}]}
    v = CorrelationAdversary().review("g", GROUP, HELD, 1, FakeGW(lambda t, p, i: link if i else G30))
    assert v.verdict == "veto" and any("same noon ET print" in r for r in v.reasons)
    v = CorrelationAdversary().review("g", GROUP, HELD, 1, FakeGW(lambda t, p, i: {"verdict": "veto", "hidden_links": []} if i else G30))
    assert v.verdict == "veto" and v.vendor_votes == (("v0", "clear"), ("v1", "veto"))
    v = CorrelationAdversary().review("g", GROUP, HELD, 1, FakeGW(lambda t, p, i: G30, vendors=1))   # same vendor twice
    assert v.verdict == "veto"


class OneResult(FakeGW):
    def complete(self, task, prompt, schema, vendors=1):
        return super().complete(task, prompt, schema, 1)


def test_d5_single_answer_vetoes():
    assert CorrelationAdversary().review("g", GROUP, {}, 1, OneResult(lambda t, p, i: G30)).verdict == "veto"
    assert ChangeGate().review(LOWER, OneResult(lambda t, p, i: G31)).verdict == "veto"


# ---------- D6 rule 7 ----------

def learned(k, a, b, name="ladder"):
    return {"kind": "learned", "name": name, "old": {k: a}, "new": {k: b}}


@pytest.mark.parametrize("change", [learned("quote_size", 10, 12), learned("ladder", 100, 150, name="budgets:crypto-term"),
                                    learned("budget_usd", 100, 150), learned("c_shrink", 0.3, 0.4),
                                    learned("half_min", 0.005, 0.004), learned("complement_margin", 0.01, 0.005),
                                    learned("move_k", 4.0, 5.0), learned("24", 0.95, 0.90, name="kappa"),
                                    learned("kappa", {"24": 0.95}, {"24": 0.97}), learned("new_knob", 1, 0.5),
                                    learned("assets", ["BTC"], ["BTC", "ETH"]),
                                    {"kind": "code", "name": "k", "paths": ["trader/kernel.py"], "diff": "x"},
                                    {"kind": "code", "name": "k", "paths": [r"C:\x\roster\trader\live\router.py"], "diff": "x"},
                                    {"kind": "code", "name": "k", "paths": ["TRADER/Kernel.py"], "diff": "x"},
                                    {"kind": "code", "name": "k", "paths": ["trader/fees.py"], "diff": "x"},
                                    *(learned(k, a, b) for k, a in (("max_inv", 50.0), ("quote_size", 10), ("half_min", 0.005))
                                      for b in (float("nan"), float("inf"), float("-inf")))])
def test_d6_flagged(change):
    assert rule7(change)


@pytest.mark.parametrize("change", [learned("quote_size", 10, 8), learned("half_min", 0.005, 0.006),
                                    learned("move_k", 4.0, 3.0), learned("ladder", 150, 100, name="budgets:crypto-term"),
                                    {"kind": "code", "name": "docs", "paths": ["advisor/roles_p5/smoke.py"], "diff": "x"}])
def test_d6_not_flagged(change):
    assert rule7(change) == []


def test_d6_nan_change_vetoed_not_cleared():
    gw = const(G31)
    for k, a in (("max_inv", 50.0), ("half_min", 0.005)):
        v = ChangeGate().review(learned(k, a, float("nan")), gw)
        assert v.verdict == "veto" and gw.calls == []          # flagged, no evidence: vetoed before any call
    ok = {"prereg": {"n": 60, "pass_z": 2.0}, "evidence": {"n": 60, "mean": 1.0, "se": 0.1}}
    ChangeGate().review({**learned("max_inv", 50.0, float("nan")), **ok}, gw)
    assert "max_inv: changed" in gw.calls[-1][1] and "nan" not in gw.calls[-1][1].lower()
    nan_ev = {"prereg": {"n": 60, "pass_z": 2.0}, "evidence": {"n": 60, "mean": float("nan"), "se": 0.1}}
    assert ChangeGate().review({**learned("quote_size", 10, 12), **nan_ev}, gw).verdict == "veto"


# ---------- D7 role 31 evidence ----------

@pytest.mark.parametrize("ev", [{}, {"prereg": {"n": 60, "pass_z": 2.0}},
                                {"prereg": {"n": 60, "pass_z": 2.0}, "evidence": {"n": 59, "mean": 1.0, "se": 0.1}},
                                {"prereg": {"n": 60, "pass_z": 2.0}, "evidence": {"n": 60, "mean": 0.1, "se": 0.1}},
                                {"prereg": {"n": 60, "pass_z": 2.0}, "evidence": {"n": 60, "mean": 1.0, "se": 0.0,
                                                                                  "result": "PASS"}}])
def test_d7_flagged_without_evidence_vetoed_with_no_call(ev):
    gw = const(G31)
    v = ChangeGate().review({**learned("quote_size", 10, 12), **ev}, gw)
    assert v.verdict == "veto" and gw.calls == []


def test_d7_complete_evidence_runs_review_without_numbers():
    gw = const(G31)
    v = ChangeGate().review({**learned("c_shrink", 0.3, 0.4), **PASSING}, gw)
    assert v.verdict == "clear" and any("human token" in r for r in v.reasons)
    assert len(gw.calls) == 1 and gw.calls[0][2] == 2 and gw.calls[0][0] == "31-change-gate"
    p = gw.calls[0][1]
    assert "c_shrink: raised by 33%" in p and "0.3" not in p.split("Change:")[1]
    assert not any(s in p for s in [*SENTINELS, "64", "60"])
    v = ChangeGate().review({**learned("c_shrink", 0.3, 0.4), **PASSING},
                            FakeGW(lambda t, p, i: {"verdict": "veto", "violations": ["raises edge"]} if i else G31))
    assert v.verdict == "veto" and "v1: raises edge" in v.reasons


def test_d7_code_change_reviewed_and_long_diff_vetoed():
    gw = const(G31)
    v = ChangeGate().review({"kind": "code", "name": "k", "paths": ["trader/kernel.py"], "diff": "-a\n+b"}, gw)
    assert v.verdict == "clear" and "pass still needs a human token" in v.reasons and "+b" in gw.calls[0][1]
    gw = const(G31)
    v = ChangeGate().review({"kind": "code", "name": "k", "paths": ["x.py"], "diff": "x" * (board.MAX_DIFF + 1)}, gw)
    assert v.verdict == "veto" and gw.calls == []
    assert ChangeGate().review({"kind": "other"}, gw).verdict == "veto" and gw.calls == []


# ---------- D9 ensemble ----------

def test_d9_combine_hand_values():
    ps = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    assert shadow.combine(ps, "median") == pytest.approx(0.55)
    assert shadow.combine(ps, "trimmed") == pytest.approx(0.55)          # drops 0.1 and 1.0
    ps = [0.1, 0.2, 0.2, 0.3, 0.3, 0.3, 0.4, 0.5, 0.6, 0.99]
    assert shadow.combine(ps, "trimmed") == pytest.approx(2.8 / 8)       # mean of the middle 8
    assert shadow.combine([0.2, 0.4, 0.9, 0.5], "median") == pytest.approx(0.45)


def test_d9_insufficient_caps_and_no_mid_in_prompt(tmp_path):
    gw = FakeGW(lambda t, p, i: G26 if i < 3 else "HTTP 500")
    r = shadow.forecast(MARKET, NOW, gw, log_path=tmp_path / "l.jsonl")
    assert r["status"] == "insufficient" and r["combined"] is None and r["calibrated"] is None and r["blended"] is None
    r = shadow.forecast(MARKET, NOW, const({"p": 0.999, "rationale": ""}), log_path=tmp_path / "l.jsonl")
    assert r["combined"] == pytest.approx(0.999) and r["calibrated"] == pytest.approx(0.97)
    r = shadow.forecast(MARKET, NOW, const({"p": 0.0, "rationale": ""}), log_path=tmp_path / "l.jsonl")
    assert r["calibrated"] == pytest.approx(0.03)
    gw = const(G26)
    r = shadow.forecast(MARKET, NOW, gw, n_vendors=20, log_path=tmp_path / "l.jsonl")
    assert gw.calls[0][2] == 10 and str(MID) not in gw.calls[0][1] and "relist token Y" in gw.calls[0][1]
    lg = lambda x: np.log(x / (1 - x))
    assert lg(r["blended"]) == pytest.approx(lg(MID) + 0.3 * (lg(0.6) - lg(MID)))
    assert shadow.calibrate(0.6, (0.2, 1.5)) == pytest.approx(1 / (1 + np.exp(-(0.2 + 1.5 * lg(0.6)))))
    with pytest.raises(ValueError):
        shadow.forecast(MARKET, NOW, gw, method="mean", log_path=tmp_path / "l.jsonl")


def test_run_batch_stops_on_quota(tmp_path):
    gw = FakeGW(lambda t, p, i: G26, vendors=6, quota=2)
    rows = shadow.run_batch([MARKET] * 5, NOW, gw, max_markets=5, log_path=tmp_path / "l.jsonl")
    assert len(rows) == 2
    assert len(shadow.run_batch([MARKET] * 5, NOW, FakeGW(lambda t, p, i: G26), 3, log_path=tmp_path / "l.jsonl")) == 3


# ---------- D10 Platt ----------

def test_d10_platt_recovers_and_identity_below_100():
    rng = np.random.default_rng(7)
    a, b = -0.4, 1.6
    p = rng.uniform(0.03, 0.97, 2000)
    q = 1 / (1 + np.exp(-(a + b * np.log(p / (1 - p)))))
    rows = [{"combined": float(x), "outcome": int(y)} for x, y in zip(p, rng.random(2000) < q)]
    fa, fb = shadow.fit_platt(rows)
    assert abs(fa - a) < 0.1 and abs(fb - b) < 0.1
    assert shadow.fit_platt(rows[:99]) == (0.0, 1.0)
    with pytest.raises(ValueError):
        shadow.fit_platt([{**rows[0], "mode": "a"}, {**rows[1], "mode": "b"}])


# ---------- D11 scoring and correlation ----------

def row(cid, cluster, models, mid=0.5, calibrated=0.6, mode="m"):
    return {"cid": cid, "cluster_id": cluster, "mode": mode, "mid": mid, "calibrated": calibrated, "blended": 0.55,
            "models": [{"vendor": f"v{k}", "model": k, "p": p, "error": None} for k, p in models.items()]}


def test_d11_scored_only_after_cutoff():
    rows = [row("before", "c1", {"a": 0.9, "b": 0.8}), row("after", "c2", {"a": 0.7, "b": 0.6})]
    outcomes = {"before": (1, 1_000), "after": (0, 3_000)}
    s = shadow.score(rows, outcomes, {"a": 2_000})          # b has no cutoff: never scored
    assert set(s) == {("m", "a")}
    assert s[("m", "a")]["rows"] == 1 and s[("m", "a")]["brier"] == pytest.approx(0.49)
    assert s[("m", "a")]["brier_mid"] == pytest.approx(0.25)
    s = shadow.score(rows, outcomes, {"a": 2_000, "b": 500})
    assert s[("m", "b")]["rows"] == 2 and s[("m", "ensemble")]["rows"] == 1 and s[("m", "a")]["rows"] == 1


def test_d11_score_uses_clustered_se():
    rng = np.random.default_rng(3)
    rows, outcomes = [], {}
    for i in range(200):
        rows.append(row(f"c{i}", f"g{i // 4}", {"a": float(rng.uniform(0.1, 0.9))}, mid=float(rng.uniform(0.1, 0.9))))
        outcomes[f"c{i}"] = (int(rng.random() < 0.5), 10)
    s = shadow.score(rows, outcomes, {"a": 0})[("m", "a")]
    from research.kappa.kappa import clustered_mean
    p = np.array([r["models"][0]["p"] for r in rows]); m = np.array([r["mid"] for r in rows])
    y = np.array([outcomes[r["cid"]][0] for r in rows])
    assert s["clusters"] == 50 and s["brier_diff"] == pytest.approx(clustered_mean((p - y) ** 2 - (m - y) ** 2,
                                                                                      [r["cluster_id"] for r in rows]))


def test_d11_error_correlation_neff():
    rng = np.random.default_rng(11)
    q = rng.uniform(0.2, 0.8, 2000)
    outcomes = {f"c{i}": (float(rng.random() < q[i]), 0) for i in range(2000)}   # binary, as on real data
    mids = np.clip(q + rng.normal(0, 0.005, 2000), 0.01, 0.99)                    # the market's estimate of q
    same = [row(f"c{i}", f"c{i}", {k: float(q[i] + e) for k in "abcdef"}, mid=float(mids[i]))
            for i, e in enumerate(rng.normal(0, 0.05, 2000))]
    assert shadow.error_correlation(same, outcomes)["n_eff"] == pytest.approx(1.0)
    noise = rng.normal(0, 0.05, (2000, 6))
    indep = [row(f"c{i}", f"c{i}", {k: float(np.clip(q[i] + noise[i, j], 0, 1)) for j, k in enumerate("abcdef")},
                 mid=float(mids[i])) for i in range(2000)]
    r = shadow.error_correlation(indep, outcomes)
    assert r["n"] == 6 and abs(r["n_eff"] - 6) <= 0.6


# ---------- D12 append-only log ----------

def test_d12_log_append_only(tmp_path):
    log = tmp_path / "research.jsonl"
    gw = const(G26)
    shadow.forecast(MARKET, NOW, gw, log_path=log)
    shadow.forecast({**MARKET, "cid": "0xdef"}, NOW + 1, gw, log_path=log)
    before = log.read_bytes()
    for k in range(3):
        shadow.forecast({**MARKET, "cid": f"0x{k}"}, NOW + 2 + k, gw, log_path=log)
    after = log.read_bytes()
    assert after.startswith(before) and len(after.splitlines()) == 5
    first = json.loads(before.splitlines()[0])
    assert {"event_ms", "recorded_ms", "cid", "cluster_id", "models", "combined", "calibrated", "blended", "method",
            "prompt_sha256"} <= set(first) and first["prompt_sha256"] == shadow.PROMPT_SHA256
    assert {"vendor", "model", "p", "error"} == set(first["models"][0])


# ---------- D13 smoke ----------

@pytest.mark.skipif(not list((ROOT / "data" / "markets").glob("*Z.jsonl")), reason="no market snapshot on this machine")
def test_d13_smoke_writes_report(tmp_path):
    from advisor.roles_p5 import smoke
    text = smoke.main(tmp_path / "smoke.md", tmp_path / "smoke.jsonl")
    for h in ("## Role 24", "## Role 30", "## Role 31", "## Role 26", "## Fail-closed cases"):
        assert h in text
    assert text.rstrip().splitlines()[-1].startswith("The smoke") and "## How to reproduce" in text
