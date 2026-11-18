"""WP4-D tests: role 25 sentinel (D1-D4) and Loop A (D5-D9). No network: the autouse guard makes connect() raise."""
import pathlib
import re
import socket

import numpy as np
import pytest
from scipy.special import expit

from advisor.contracts import LLMResult
from advisor.sentinel import Sentinel
from learning import loop_a

H = 3_600_000
T0 = 1_790_000_000_000
ARS = "E0:Arsenal:Chelsea:2026-10-03"
ATM = "SP1:Atletico Madrid:Sevilla:2026-10-04"
MAPS = [
    {"cid": "0xa", "token_yes": "1", "token_no": "2", "event_key": ARS, "league": "E0", "home": "Arsenal",
     "away": "Chelsea", "outcome": "H", "start_ms": T0 + 48 * H, "rule_flags": [], "players": ["Bukayo Saka"]},
    {"cid": "0xb", "token_yes": "3", "token_no": "4", "event_key": ARS, "league": "E0", "home": "Arsenal",
     "away": "Chelsea", "outcome": "A", "start_ms": T0 + 48 * H, "rule_flags": []},
    {"cid": "0xc", "token_yes": "5", "token_no": "6", "event_key": ATM, "league": "SP1", "home": "Atlético Madrid",
     "away": "Sevilla", "outcome": "H", "start_ms": T0 + 72 * H, "rule_flags": []},
]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network disabled in unit tests")
    monkeypatch.setattr(socket.socket, "connect", boom)


class FakeGateway:
    """Answers are dicts (ok), None (ok=False, e.g. timeout/quota), or an Exception (raised). Last answer repeats."""
    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def complete(self, task, prompt, schema, vendors=1):
        self.calls.append((task, prompt, schema, vendors))
        a = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(a, Exception):
            raise a
        return [LLMResult("fake", "f1", a is not None, a, None if a else "timeout", False, 10)]

    def quota_left(self):
        return {"fake": 100}


MAT = {"material": True, "team": "Arsenal", "kind": "injury"}
NOT = {"material": False, "team": "Arsenal", "kind": "other"}


def news(text, t=T0, family="bbc", published=None):
    return {"text": text, "source_family": family, "published_ms": t - 60_000 if published is None else published,
            "recv_ms": t, "url": "https://example.invalid/secret-path"}


def test_guard_blocks_network():
    with pytest.raises(RuntimeError):
        socket.create_connection(("example.com", 80), timeout=1)


# ---- D1 prefilter ----
def test_prefilter_calls_llm_only_on_name_and_keyword():
    gw = FakeGateway(MAT)
    s = Sentinel(gw, MAPS)
    assert s.on_news(news("Liverpool striker ruled out for a month")) == []          # no tracked name
    assert s.on_news(news("Arsenal unveil their new kit")) == []                     # no keyword
    assert s.on_news(news("Arsenal fans travel without tickets")) == []              # 'without' is not 'out'
    assert gw.calls == []
    out = s.on_news(news("ATLETICO  MADRID defender injured in training"))          # accents/case/spaces ignored
    assert len(gw.calls) == 1 and [sig.scope for sig, _ in out] == [ATM]
    task, prompt, schema, vendors = gw.calls[0]
    assert task == "25-sports-news" and vendors == 1 and set(schema["required"]) == {"material", "team", "kind"}
    assert "Atlético Madrid" in prompt and "Sevilla" in prompt and "injured in training" in prompt
    assert "example.invalid" not in prompt and "bbc" not in prompt                   # text + team names only
    s.on_news(news("Bukayo Saka doubtful for the weekend"))                           # player name from the map
    assert len(gw.calls) == 2 and ARS in s.active


# ---- D2 pulls ----
def test_material_news_pulls_the_right_event():
    s = Sentinel(FakeGateway(MAT), MAPS)
    [(sig, req)] = s.on_news(news("Arsenal captain ruled out of Chelsea clash"))
    assert sig.role == "25-sports-news" and sig.scope == ARS and sig.action == "pull"
    assert sig.resume_requires_fresh_observation and 0.0 <= sig.shrink_factor <= 1.0
    assert sig.expires_ms == T0 + 48 * H and sig.reason == "injury, bbc"
    assert req == {"event_key": ARS, "priority": "news"}
    assert not hasattr(sig, "size") and not hasattr(sig, "price")


@pytest.mark.parametrize("answer", [None, RuntimeError("boom"), {"material": "yes", "team": "x", "kind": "injury"},
                                    {"material": True, "team": "x", "kind": "gossip"}, {"material": True}])
def test_llm_or_parse_failure_pulls(answer):
    s = Sentinel(FakeGateway(answer), MAPS)
    [(sig, req)] = s.on_news(news("Arsenal lineup leaked"))
    assert sig.action == "pull" and sig.scope == ARS and "llm-failure" in sig.reason and req["priority"] == "news"


def test_non_material_changes_nothing():
    s = Sentinel(FakeGateway(NOT), MAPS)
    assert s.on_news(news("Arsenal: no injury worries, says coach")) == [] and s.active == {}


# ---- D3 resume drill (4.7) ----
def test_resume_only_after_fresh_observation():
    s = Sentinel(FakeGateway(MAT), MAPS)
    s.on_news(news("Arsenal striker ruled out", t=T0))
    for dt in (1 * H, 23 * H):                       # time passing alone never resumes; other games' observations neither
        assert s.on_sharp_observation(ATM, T0 + dt) is None
        assert s.active[ARS].action == "pull" and s.active[ARS].expires_ms == T0 + 48 * H
    assert s.on_sharp_observation(ARS, T0 - 5_000) is None   # older than the news
    assert s.on_sharp_observation(ARS, T0) is None           # not later than the news time
    res = s.on_sharp_observation(ARS, T0 + 1)
    assert res.action == "none" and res.shrink_factor == 1.0 and res.scope == ARS and ARS not in s.active
    assert s.on_sharp_observation(ARS, T0 + 2) is None       # nothing left to resume
    # newer news re-arms: an observation later than the old news but before the new one does not resume
    s.on_news(news("Arsenal keeper doubtful", t=T0 + 5 * H))
    s.on_news(news("Arsenal keeper ruled out", t=T0 + 7 * H))
    assert s.on_sharp_observation(ARS, T0 + 6 * H) is None
    assert s.on_sharp_observation(ARS, T0 + 7 * H + 1).action == "none"


def test_news_time_is_max_of_published_and_received():
    s = Sentinel(FakeGateway(MAT), MAPS)
    s.on_news(news("Arsenal match postponed", t=T0, published=T0 + 10_000))   # source clock ahead of ours
    assert s.on_sharp_observation(ARS, T0 + 5_000) is None
    assert s.on_sharp_observation(ARS, T0 + 10_001).action == "none"


# ---- D4 source families ----
@pytest.mark.parametrize("order", [("bbc", "sky"), ("sky", "bbc")])
def test_disagreeing_families_keep_pull_and_flag(order):
    answers = {"bbc": MAT, "sky": NOT}
    s = Sentinel(FakeGateway(*[answers[f] for f in order]), MAPS)
    for i, fam in enumerate(order):
        s.on_news(news("Arsenal winger injured?", t=T0 + i * 60_000, family=fam))
    sig = s.active[ARS]
    assert sig.action == "pull" and "sources disagree" in sig.reason and sig.reason.startswith("injury, bbc")


# ---- Loop A synthetic data ----
def synth(n_clusters, a=0.2, b=0.9, c=0.6, per=20, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for k in range(n_clusters):
        m = rng.uniform(0.1, 0.9, per)
        lm = np.log(m / (1 - m))
        d = rng.normal(0, 0.8, per)
        y = rng.random(per) < expit(a + b * lm + c * d)
        rows += [{"y": int(y[i]), "m": float(m[i]), "f": float(expit(lm[i] + d[i])), "cluster_id": f"c{k}",
                  "resolved_ms": T0 + k * H} for i in range(per)]
    return rows


# ---- D5 blend fit ----
def test_blend_fit_recovers_parameters_and_bounds_c():
    fit = loop_a.fit_blend(synth(300))
    assert abs(fit["a"] - 0.2) < 0.15 and abs(fit["b"] - 0.9) < 0.15 and abs(fit["c"] - 0.6) < 0.15
    assert fit["n_clusters"] == 300
    assert loop_a.fit_blend(synth(300, c=1.8))["c"] == pytest.approx(1.0)
    assert loop_a.fit_blend(synth(300, c=-0.8))["c"] == pytest.approx(0.0)
    assert loop_a.fit_blend(synth(99)) is None


# ---- D6 switch rule ----
def test_c_switch():
    assert loop_a.c_in_force(None) == 0.3 and loop_a.c_in_force({}) == 0.3
    assert loop_a.c_in_force({"name": "kelly-c", "version": "2", "params": {"c": 0.45}}) == 0.45
    assert loop_a.c_in_force({"params": {"c": 1.7}}) == 0.3            # corrupt live value -> default
    assert loop_a.c_candidate(synth(99)) is None
    rows = synth(300)
    cand = loop_a.c_candidate(rows)
    lo, point = loop_a.bootstrap_c(rows)
    assert cand == {"name": "kelly-c", "params": {"c": lo, "quantile": 0.2, "n_clusters": 300}, "state": "candidate"}
    assert 0.0 <= cand["params"]["c"] <= point <= 1.0
    assert point == pytest.approx(loop_a.fit_blend(rows)["c"], abs=1e-4)
    src = (pathlib.Path(loop_a.__file__)).read_text(encoding="utf-8")
    assert not re.search(r"promot|regist|\.record\(|sqlite|open\(", src, re.I)


# ---- D7 refit gate ----
def test_refit_gate():
    rng = np.random.default_rng(3)
    cl = np.repeat(np.arange(120), 5)
    cur = np.full(cl.size, 0.70)
    cand = 0.60 + rng.normal(0, 0.05, cl.size)
    ok, gain, se, n = loop_a.accept_refit(cur, cand, cl)
    g = np.bincount(cl, weights=cur - cand)
    assert ok and n == 120 and gain == pytest.approx(g.mean()) and se == pytest.approx(g.std(ddof=1) / np.sqrt(120))
    keep = cl < 99
    assert not loop_a.accept_refit(cur[keep], cand[keep], cl[keep])[0]          # same gain, 99 clusters
    # correlated rows: every row of a cluster shares its cluster's gain -> significant per row, not per cluster
    cl = np.repeat(np.arange(120), 50)
    g_k = 0.01 + 0.1 * np.where(np.arange(120) % 2 == 0, 1.0, -1.0)
    row_gain = (g_k / 50)[cl]
    assert row_gain.mean() / (row_gain.std(ddof=1) / np.sqrt(row_gain.size)) > 2   # naive per-row t-stat
    ok, gain, se, n = loop_a.accept_refit(np.full(cl.size, 0.7), 0.7 - row_gain, cl)
    assert not ok and n == 120 and gain == pytest.approx(0.01) and gain < 2 * se


def test_refit_step_takes_candidate_only_when_gate_passes():
    rows = [{"y": int(i % 5 != 0), "cluster_id": i // 2, "m": 0.5} for i in range(400)]  # 200 clusters, P(y)=0.8
    anchor, current, better, worse = (lambda r: 0.55), (lambda r: 0.6), (lambda r: 0.8), (lambda r: 0.3)
    assert loop_a.refit_step(anchor, current, better, rows) is better
    assert loop_a.refit_step(anchor, current, worse, rows) is current
    assert loop_a.refit_step(anchor, current, better, rows[:150]) is current     # 75 clusters < 100


# ---- D8 anchor rule (4.9 done-when) ----
def test_anchor_rule_property_over_random_refit_chains():
    rng = np.random.default_rng(7)
    for _ in range(10_000):
        anchor, cur = rng.uniform(0.02, 0.98, 2)
        for _ in range(rng.integers(1, 10)):                     # a chain of accepted refits, drifting anywhere
            cur = float(np.clip(cur + rng.normal(0, 0.1), 0.01, 0.99))
            mid = float(rng.uniform(0.02, 0.98))
            p = loop_a.anchored_p(anchor, cur, mid)
            assert abs(p - mid) <= abs(anchor - mid) + 1e-12
            assert min(mid, anchor) - 1e-12 <= p <= max(mid, anchor) + 1e-12   # never past the anchor's side
            if (anchor - mid) * (cur - mid) < 0:
                assert p == mid
            s_a, s_c = rng.uniform(0, 0.1, 2)
            assert loop_a.anchored_spread(s_a, s_c) == max(s_a, s_c)
    assert loop_a.anchored_p(0.6, 0.4, 0.5) == 0.5 and loop_a.anchored_p(0.6, 0.55, 0.5) == 0.55


def test_chain_of_real_refits_cannot_raise_edge_past_anchor():
    rows = [{"y": int(i % 10 != 0), "cluster_id": i // 2} for i in range(400)]   # truth 0.9: every step is better
    anchor = current = (lambda r: 0.55)
    for q in (0.6, 0.65, 0.7, 0.75, 0.8, 0.85):
        cand = (lambda r, q=q: q)
        current = loop_a.refit_step(anchor, current, cand, rows)
        assert current is cand                                     # each refit accepted
        assert loop_a.anchored_p(anchor({}), current({}), 0.5) == 0.55   # edge stays at the anchor's


# ---- D9 walk-forward ----
def test_walk_forward_split():
    rng = np.random.default_rng(5)
    rows = [{"cluster_id": k, "resolved_ms": int(T0 + k * H + rng.integers(0, 3 * H)), "y": 1} for k in range(200)
            for _ in range(4)]
    t = T0 + 100 * H
    train, test = loop_a.walk_forward(rows, t)
    assert train and test
    assert max(r["resolved_ms"] for r in train) < t <= min(r["resolved_ms"] for r in test)
    assert not {r["cluster_id"] for r in train} & {r["cluster_id"] for r in test}
    assert len(train) == sum(r["resolved_ms"] < t for r in rows)                 # nothing earlier is dropped
    straddle = {r["cluster_id"] for r in train} & {r["cluster_id"] for r in rows if r["resolved_ms"] >= t}
    assert straddle                                                              # the fixture does exercise the rule
