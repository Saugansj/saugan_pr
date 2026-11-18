"""WP4-C: LLM gateway and clearance board. Fake vendors only; any network attempt fails the test."""
import ast
import json
import pathlib
import socket

import pytest

from advisor import board, gateway
from advisor.board import QUALIFIED, R27, clear_template, parse_27, parse_28
from advisor.contracts import LLMResult
from advisor.gateway import VENDORS, LLMGateway
from common import ROOT, sha256_text
from tools import clearance_cli
from trader.contracts import MarketInfo
from trader.kernel import clearance_key, key_id, load_advice, verify

DAY = 86_400_000
T0 = 1_790_000_000_000  # a fixed UTC instant
KEYS = {"gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY", "openrouter": "OPENROUTER_API_KEY"}
SCHEMA = {"type": "object", "required": ["verdict"], "properties": {"verdict": {"type": "string", "enum": ["clear", "veto"]}}}
CLEAR27 = {"resolution_source": "Binance BTC/USDT 1m candle close", "cutoff_time": "12:00 ET", "comparison": ">",
           "price_method": "snapshot", "tie_rule": "equal is No", "cancellation_rule": "not stated in rules",
           "postponement_rule": "not applicable", "neg_risk_exactly_one_yes": "not applicable",
           "augmented_other": "no", "dispute_risk": "low", "verdict": "clear", "reasons": []}
CLEAR28 = {"verdict": "clear", "reading": "", "scenario": ""}
RULES = "This market will resolve to Yes if the Binance 1 minute candle for BTC/USDT 12:00 in the ET timezone closes higher."


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise RuntimeError("network disabled in tests")
    monkeypatch.setattr(socket.socket, "connect", refuse)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in [*KEYS.values(), "ROSTER_ADVISOR_KEY", "ROSTER_HUMAN_KEY"]:
        monkeypatch.delenv(k, raising=False)


def set_keys(monkeypatch, *vendors):
    for v in vendors:
        monkeypatch.setenv(KEYS[v], f"fake-{v}-key-123")


def vendor_of(url: str) -> str:
    return next(v for v in VENDORS if v in url.replace("googleapis", "gemini"))


def body(vendor: str, content: str) -> str:
    if vendor == "gemini":
        return json.dumps({"candidates": [{"content": {"parts": [{"text": content}]}}], "usageMetadata": {"totalTokenCount": 7}})
    return json.dumps({"choices": [{"message": {"content": content}}], "usage": {"total_tokens": 7}})


class Transport:
    """Fake vendor HTTP. `answer(vendor, prompt)` returns a dict (JSON answer), a str (raw content), an
    (status, text) tuple, or an exception to raise."""

    def __init__(self, answer=None):
        self.calls = []
        self.answer = answer or (lambda v, p: CLEAR28 if "wording adversary" in p else CLEAR27 if "auditor" in p
                                 else {"verdict": "clear"})

    def __call__(self, url, headers, payload):
        v = vendor_of(url)
        prompt = payload["contents"][0]["parts"][0]["text"] if v == "gemini" else payload["messages"][0]["content"]
        self.calls.append((v, prompt))
        a = self.answer(v, prompt)
        if isinstance(a, Exception):
            raise a
        if isinstance(a, tuple):
            return a
        return 200, body(v, a if isinstance(a, str) else json.dumps(a))


class Clock:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t


def gw(tmp_path, transport=None, clock=None):
    return LLMGateway(tmp_path / "gw.db", transport or Transport(), clock or Clock())


# ---- C1 rotation
def test_c1_rotation_distinct_most_quota_first_and_fixed_length(tmp_path, monkeypatch):
    set_keys(monkeypatch, "gemini", "groq", "openrouter")
    t = Transport()
    g = gw(tmp_path, t)
    assert [r.vendor for r in g.complete("t", "p1", SCHEMA, 1)] == ["gemini"]  # 1000 vs 1000 vs 50: tie -> name
    assert [r.vendor for r in g.complete("t", "p2", SCHEMA, 1)] == ["groq"]    # gemini now has 999 left
    two = g.complete("t", "p3", SCHEMA, vendors=2)
    assert len(two) == 2 and len({r.vendor for r in two}) == 2 and all(r.ok for r in two)
    assert g.quota_left() == {"gemini": 998, "groq": 998, "openrouter": 50}
    monkeypatch.delenv(KEYS["openrouter"])
    monkeypatch.delenv(KEYS["groq"])
    three = g.complete("t", "p4", SCHEMA, vendors=3)
    assert len(three) == 3 and [r.vendor for r in three] == ["gemini", "none", "none"]
    assert [r.error for r in three[1:]] == ["no vendor available"] * 2 and not any(r.ok for r in three[1:])


# ---- C2 quota persistence, UTC-day reset, exhausted vendor never called
def test_c2_quota_persists_across_instances_and_resets_next_utc_day(tmp_path, monkeypatch):
    set_keys(monkeypatch, "gemini")
    clock = Clock()
    a = gw(tmp_path, clock=clock)
    for i in range(3):
        a.complete("t", f"p{i}", SCHEMA)
    b = gw(tmp_path, clock=clock)
    assert b.quota_left()["gemini"] == 997
    clock.t += DAY
    assert b.quota_left()["gemini"] == 1000


def test_c2_exhausted_vendor_transport_never_called(tmp_path, monkeypatch):
    set_keys(monkeypatch, "gemini")
    monkeypatch.setitem(VENDORS["gemini"], "cap", 2)
    t = Transport(lambda v, p: (500, "boom"))  # failed requests still count: a request counts when sent
    g = gw(tmp_path, t)
    g.complete("t", "a", SCHEMA)
    g.complete("t", "b", SCHEMA)
    assert len(t.calls) == 2 and g.quota_left()["gemini"] == 0
    r = g.complete("t", "c", SCHEMA)
    assert len(t.calls) == 2 and r[0].error == "no vendor available" and not r[0].ok


# ---- C3 cache
def test_c3_cache_hit_spends_nothing_and_failures_are_not_cached(tmp_path, monkeypatch):
    set_keys(monkeypatch, "gemini")
    t = Transport()
    g = gw(tmp_path, t)
    first = g.complete("t", "same", SCHEMA)[0]
    left = g.quota_left()
    second = g.complete("t", "same", SCHEMA)[0]
    assert first.ok and not first.cached and second.ok and second.cached and second.data == first.data
    assert len(t.calls) == 1 and g.quota_left() == left
    assert not g.complete("other-task", "same", SCHEMA)[0].cached  # task is part of the input hash

    answers = iter([(500, "err"), {"verdict": "veto"}])
    t2 = Transport(lambda v, p: next(answers))
    g2 = LLMGateway(tmp_path / "gw2.db", t2, Clock())
    assert not g2.complete("t", "x", SCHEMA)[0].ok
    again = g2.complete("t", "x", SCHEMA)[0]
    assert again.ok and not again.cached and len(t2.calls) == 2


# ---- C4 fail closed, one case each
@pytest.mark.parametrize("answer,error", [
    (TimeoutError("read timed out"), "timeout"),
    ((429, '{"error": "rate limited"}'), "http 429"),
    ((500, "internal"), "http 500"),
    ("I think the answer is clear.", "non-JSON answer"),
    ({"other": 1}, "schema mismatch"),               # missing required field
    ({"verdict": "maybe"}, "schema mismatch"),       # outside the enum
    ((200, "<html>not json</html>"), "non-JSON answer"),
], ids=["timeout", "http429", "http500", "non_json", "missing_field", "out_of_enum", "non_json_body"])
def test_c4_fail_closed(tmp_path, monkeypatch, answer, error):
    set_keys(monkeypatch, "groq")
    t = Transport(lambda v, p: answer)
    r = gw(tmp_path, t).complete("t", "p", SCHEMA)
    assert len(r) == 1 and not r[0].ok and r[0].error == error and r[0].data is None and len(t.calls) == 1


def test_c4_httpx_timeout_type_and_internal_error_never_raise(tmp_path, monkeypatch):
    import httpx
    set_keys(monkeypatch, "groq")
    assert gw(tmp_path, Transport(lambda v, p: httpx.ReadTimeout("slow"))).complete("t", "p", SCHEMA)[0].error == "timeout"
    broken = gw(tmp_path)
    broken.db = tmp_path / "missing-dir" / "gw.db"  # sqlite cannot open it: quota and cache fail
    r = broken.complete("t", "p", SCHEMA, vendors=2)
    assert len(r) == 2 and not any(x.ok for x in r)
    assert broken.quota_left() == {v: 0 for v in VENDORS}


# ---- C5 public text only
@pytest.mark.parametrize("prompt", ["rules text plus s3cr3t-value-999", "key " + "ab" * 32, "our BankRoll is 50",
                                    "balance", "daily P&L", "position size 10"],
                         ids=["env_secret", "hex64", "bankroll", "balance", "p_and_l", "position_size"])
def test_c5_non_public_prompt_refused_before_transport(tmp_path, monkeypatch, prompt):
    set_keys(monkeypatch, "gemini", "groq")
    monkeypatch.setenv("SOME_VENUE_SECRET", "s3cr3t-value-999")
    t = Transport()
    g = gw(tmp_path, t)
    r = g.complete("t", prompt, SCHEMA, vendors=2)
    assert [x.error for x in r] == ["non-public content"] * 2 and not t.calls
    assert g.quota_left() == {"gemini": 1000, "groq": 1000, "openrouter": 0}


def test_c5_vendor_key_value_in_prompt_refused(tmp_path, monkeypatch):
    set_keys(monkeypatch, "gemini")
    t = Transport()
    assert gw(tmp_path, t).complete("t", "x fake-gemini-key-123", SCHEMA)[0].error == "non-public content"
    assert not t.calls


# ---- C6 no keys -> nothing sent; no trader <-> advisor imports
def test_c6_no_keys_no_vendor_no_transport(tmp_path):
    t = Transport()
    g = gw(tmp_path, t)
    r = g.complete("t", "p", SCHEMA, vendors=3)
    assert len(r) == 3 and all(x.error == "no vendor available" for x in r) and not t.calls
    assert g.quota_left() == {v: 0 for v in VENDORS}


def imports(path: pathlib.Path) -> set[str]:
    mods = set()
    for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
    return mods


def test_c6_gateway_off_trading_path():
    assert "trader" not in imports(ROOT / "advisor" / "gateway.py")
    for p in (ROOT / "trader").rglob("*.py"):
        assert "advisor" not in imports(p), p


# ---- C7 parsers
def res(data, ok=True, vendor="gemini", model="gemini-2.5-flash", error=None):
    return LLMResult(vendor, model, ok, data if ok else None, error, False, 0)


def test_c7_complete_clear_answers_parse_clear():
    assert parse_27(res(CLEAR27)) == ("clear", [])
    assert parse_28(res(CLEAR28)) == ("clear", [])


@pytest.mark.parametrize("point", board.POINTS)
def test_c7_role27_missing_or_empty_point_vetoes(point):
    missing = {k: v for k, v in CLEAR27.items() if k != point}
    assert parse_27(res(missing))[0] == "error"  # schema mismatch: missing item
    if R27["properties"][point].get("enum") is None:
        vote, why = parse_27(res({**CLEAR27, point: "  "}))
        assert vote == "veto" and f"silent on {point}" in why


def test_c7_role27_dispute_high_negrisk_silence_and_auditor_veto():
    assert parse_27(res({**CLEAR27, "dispute_risk": "high"})) == ("veto", ["dispute risk high"])
    assert parse_27(res(CLEAR27), neg_risk=True)[0] == "veto"
    assert parse_27(res({**CLEAR27, "neg_risk_exactly_one_yes": "yes"}), neg_risk=True)[0] == "clear"
    assert parse_27(res({**CLEAR27, "verdict": "veto", "reasons": ["vague"]})) == ("veto", ["auditor veto", "vague"])


def test_c7_role28_veto_needs_concrete_reading_and_non_json_vetoes():
    vote, why = parse_28(res({"verdict": "veto", "reading": "", "scenario": ""}))
    assert vote == "veto" and "malformed" in why[0]
    vote, why = parse_28(res({"verdict": "veto", "reading": "> read as >=", "scenario": "close equals strike"}))
    assert vote == "veto" and "close equals strike" in why[0]
    assert parse_27(res(None, ok=False, error="non-JSON answer")) == ("error", ["non-JSON answer"])
    assert parse_28(res(None, ok=False, error="non-JSON answer")) == ("error", ["non-JSON answer"])
    assert parse_28(res({"verdict": "clear"}))[0] == "error"  # unvalidated data from some other gateway


# ---- C8 board matrix
KEY = {"template": "crypto-term:BTC:strike", "rules_sha256": sha256_text(RULES), "fee_rate": 0.07, "tick_size": 0.001,
       "min_size": 5.0, "neg_risk": False, "source_id": "binance:BTC/USDT"}
GEM, GRQ = ("gemini", "gemini-2.5-flash"), ("groq", "llama-3.3-70b-versatile")


class FakeGateway:
    """Returns prepared results per task: {"27-resolution": [LLMResult, LLMResult], "28-wording": [...]}."""

    def __init__(self, by_task):
        self.by_task, self.asked = by_task, []

    def complete(self, task, prompt, schema, vendors=1):
        self.asked.append((task, vendors, prompt))
        return self.by_task[task]

    def quota_left(self):
        return {"gemini": 10, "groq": 10, "openrouter": 0}


def results(a27=CLEAR27, b27=CLEAR27, a28=CLEAR28, b28=CLEAR28, va=GEM, vb=GRQ):
    mk = lambda d, v: d if isinstance(d, LLMResult) else res(d, vendor=v[0], model=v[1])  # noqa: E731
    return {"27-resolution": [mk(a27, va), mk(b27, vb)], "28-wording": [mk(a28, va), mk(b28, vb)]}


TIMEOUT = LLMResult("groq", GRQ[1], False, None, "timeout", False, 0)
ERROR = LLMResult("none", "", False, None, "no vendor available", False, 0)


@pytest.mark.parametrize("case,expect", [
    (results(), True),
    (results(b27={**CLEAR27, "dispute_risk": "high"}), False),
    (results(a28={"verdict": "veto", "reading": "r", "scenario": "s"}), False),
    (results(b28=ERROR), False),
    (results(b27=TIMEOUT), False),
    (results(vb=("gemini", "gemini-2.5-flash")), False),
    (results(vb=("groq", "some-unqualified-model")), False),
], ids=["all_clear", "one_27_veto", "one_28_veto", "error", "timeout", "same_vendor", "unqualified"])
def test_c8_board_matrix(tmp_path, case, expect):
    g = FakeGateway(case)
    cleared, verdicts = clear_template(g, KEY, "Will BTC be above $74,000?", RULES, T0,
                                       db=tmp_path / "c.db", keys_out=tmp_path / "k.jsonl")
    assert cleared is expect
    assert [v.role for v in verdicts] == ["27-resolution", "28-wording"]
    assert all(n == 2 for _, n, _ in g.asked) and len(g.asked) == 2
    assert all(len(v.vendor_votes) == 2 for v in verdicts)
    assert not any(KEY["rules_sha256"] in p for _, _, p in g.asked)  # 64-hex hash never in a prompt
    if not expect:
        assert any(v.verdict == "veto" and v.reasons for v in verdicts)
        assert not (tmp_path / "k.jsonl").exists()


def test_c8_vendor_votes_record_clear_veto_error(tmp_path):
    g = FakeGateway(results(b27={**CLEAR27, "verdict": "veto", "reasons": ["x"]}, b28=ERROR))
    _, (v27, v28) = clear_template(g, KEY, "q", RULES, T0, db=tmp_path / "c.db", keys_out=tmp_path / "k.jsonl")
    assert v27.vendor_votes == (("gemini", "clear"), ("groq", "veto"))
    assert v28.vendor_votes == (("gemini", "clear"), ("none", "error"))
    assert not (tmp_path / "k.jsonl").exists()


# ---- C9 exhausted quota blocks clearances (4.6 done-when), end to end through the real gateway
def test_c9_exhausted_quota_blocks_clearance_and_writes_nothing(tmp_path, monkeypatch):
    set_keys(monkeypatch, "gemini", "groq", "openrouter")
    monkeypatch.setenv("ROSTER_ADVISOR_KEY", "advisor-test-key")
    for v in VENDORS:
        monkeypatch.setitem(VENDORS[v], "cap", 0)
    t = Transport()
    cleared, verdicts = clear_template(gw(tmp_path, t), KEY, "q", RULES, T0, db=tmp_path / "c.db",
                                       keys_out=tmp_path / "k.jsonl")
    assert not cleared and not t.calls and all(v.verdict == "veto" for v in verdicts)
    assert not (tmp_path / "c.db").exists() and not (tmp_path / "k.jsonl").exists()


def test_c9_real_gateway_two_vendors_clear_end_to_end(tmp_path, monkeypatch):
    set_keys(monkeypatch, "gemini", "groq")
    t = Transport()
    cleared, verdicts = clear_template(gw(tmp_path, t), KEY, "q", RULES, T0, db=tmp_path / "c.db",
                                       keys_out=tmp_path / "k.jsonl")
    assert cleared and len(t.calls) == 4 and (tmp_path / "k.jsonl").exists()
    assert not (tmp_path / "c.db").exists()  # no ROSTER_ADVISOR_KEY -> no signed record


# ---- C10 compatibility with the kernel and clearance_cli
def market():
    return MarketInfo(cid="0xabc", token_yes="1", token_no="2", mode="crypto-term", question="Will BTC be above $74,000?",
                      rules_sha256=sha256_text(RULES), tick_size=0.001, min_size=5.0, fee_rate=0.07, neg_risk=False,
                      end_ms=T0 + DAY, event_group="BTC@x", asset="BTC", strike=74000.0, kind="strike",
                      source_id="binance:BTC/USDT")


def test_c10_record_compatible_with_kernel_and_clearance_cli(tmp_path, monkeypatch):
    m = market()
    key = clearance_key(m)
    monkeypatch.setenv("ROSTER_ADVISOR_KEY", "advisor-test-key")
    db, jsonl = tmp_path / "llm.db", tmp_path / "keys.jsonl"
    cleared, _ = clear_template(FakeGateway(results()), key, m.question, RULES, T0, db=db, keys_out=jsonl)
    assert cleared
    clear, other = load_advice(db)
    rec = clear[key_id(key)]
    assert not other and rec["key"] == clearance_key(m)
    assert set(rec) == {"type", "key", "signer", "expiry_ms", "nonce", "signed_ms", "sig"} and rec["type"] == "clearance"
    assert rec["signer"] == "llm-board:gemini/gemini-2.5-flash+groq/llama-3.3-70b-versatile"
    assert rec["expiry_ms"] == T0 + 7 * DAY
    assert verify(rec, "advisor-test-key") and not verify(rec, "another-key")
    db2 = tmp_path / "cosign.db"
    assert clearance_cli.main(["--db", str(db2), "--key", "advisor-test-key", "sign", "--keys", str(jsonl),
                               "--signer", "t"]) == 0
    assert key_id(key) in load_advice(db2)[0]


def test_c10_no_signature_without_advisor_key_or_with_the_human_key(tmp_path, monkeypatch):
    key = clearance_key(market())
    db = tmp_path / "llm.db"
    assert clear_template(FakeGateway(results()), key, "q", RULES, T0, db=db, keys_out=tmp_path / "k.jsonl")[0]
    assert not db.exists()
    monkeypatch.setenv("ROSTER_ADVISOR_KEY", "same-key-1234")
    monkeypatch.setenv("ROSTER_HUMAN_KEY", "same-key-1234")
    clear_template(FakeGateway(results()), key, "q", RULES, T0, db=db, keys_out=tmp_path / "k.jsonl")
    assert not db.exists()


# ---- C11 agreement CLI end to end (fake vendors, tmp paths)
def test_c11_agreement_cli_end_to_end(tmp_path, monkeypatch):
    set_keys(monkeypatch, "gemini", "groq")
    base = clearance_key(market())
    rules_b = "Resolves Yes if the official league site lists the home team as winner. Postponed games remain open."
    k_both, k_board = base, {**base, "tick_size": 0.01}                 # same rules text, different tick
    k_human = {**base, "template": "crypto-term:ETH:strike", "rules_sha256": sha256_text(rules_b)}
    k_none = {**base, "template": "crypto-term:SOL:strike", "rules_sha256": "f" * 64}  # not in snapshot
    snapshot = tmp_path / "snap.jsonl"
    snapshot.write_text("".join(json.dumps(r) + "\n" for r in [
        {"condition_id": "0xa", "question": "Will BTC be above $74,000?", "rules_text": RULES, "rules_sha256": sha256_text(RULES)},
        {"condition_id": "0xb", "question": "Will ETH be above $3,000?", "rules_text": rules_b, "rules_sha256": sha256_text(rules_b)},
    ]), encoding="utf-8")
    backlog = tmp_path / "uncleared.jsonl"
    backlog.write_text("".join(json.dumps(r) + "\n" for r in [
        {"key": k_both, "cid": "0xa", "question": "Will BTC be above $74,000?"},
        {"key": k_board, "cid": "0xa", "question": "Will BTC be above $74,000?"},
        {"key": k_human, "cid": "0xb", "question": "Will ETH be above $3,000?"},
        k_none,                                                         # a bare key dict line
        {"key": {"template": "bad"}, "cid": "0xa"},
    ]), encoding="utf-8")
    human_db = tmp_path / "advice.db"
    for k in (k_both, k_human):
        clearance_cli.write(human_db, {"type": "clearance", "key": k, "signer": "me", "expiry_ms": T0 * 2}, "human-key")
    # the wording adversary vetoes the "official league site" rules with a concrete reading
    veto = lambda v, p: ({"verdict": "veto", "reading": "official site lists late", "scenario": "result revised"}  # noqa: E731
                         if "wording adversary" in p and "official league site" in p
                         else CLEAR28 if "wording adversary" in p else CLEAR27)
    g = gw(tmp_path, Transport(veto))
    out = tmp_path / "agreement.md"
    rc = board.main(["agree", "--backlog", str(backlog), "--snapshot", str(snapshot), "--human-db", str(human_db),
                     "--out", str(out), "--db", str(tmp_path / "llm.db"), "--keys-out", str(tmp_path / "k.jsonl"),
                     "--gateway-db", str(tmp_path / "unused.db")], gateway=g)
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    for s in ("agree-cleared: 1", "board-only: 1", "human-only: 1", "agree-not-cleared: 1", "Skipped", "## Per template",
              "## Vendor calls used", "## How to reproduce", "official site lists late",
              "no rules text for this rules hash in the snapshot"):
        assert s in text, s
    # k_both and k_board share a prompt: the second is answered from cache, so 2 roles x 2 vendors x 2 rules texts = 8
    assert "| gemini | 4 |" in text and "| groq | 4 |" in text
    assert len((tmp_path / "k.jsonl").read_text().splitlines()) == 2
    assert not (tmp_path / "llm.db").exists()  # no ROSTER_ADVISOR_KEY in env
    assert set(load_advice(human_db)[0]) == {key_id(k_both), key_id(k_human)}  # human db untouched


def test_qualified_matches_configured_models():
    assert {(v, c["model"]) for v, c in VENDORS.items()} <= QUALIFIED
    assert gateway.DB.parts[-2:] == ("advisor", "gateway.db") and board.LLM_DB.name == "llm_clearances.db"
