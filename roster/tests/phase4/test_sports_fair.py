"""WP4-B tests: devig and per-league choice, fair value and sigma, quote gate, consensus, universe checkpoints, pull drills
and the soccer pre-registration (B1-B9). No network: an autouse fixture makes every socket connect fail."""
import json
import socket
import statistics

import numpy as np
import pandas as pd
import pytest

from advisor.contracts import CautionSignal
from sports import fair as F
from sports import pulls as P
from trader.contracts import Book

NOW = 1_790_000_000_000
HOUR, MIN = 3_600_000, 60_000
START = NOW + 3 * HOUR
METHODS = {"E0": "odds_ratio", "SP1": "power"}
MAX_AGE = F.SIGMA["params"]["max_age_ms"]
CONT_AGE = F.SIGMA["params"]["continuous_max_age_ms"]
EK = "E0:Arsenal:Leeds:2026-10-10"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise RuntimeError("network disabled in unit tests")
    monkeypatch.setattr(socket.socket, "connect", refuse)


def mmap(outcome="H", ek=EK, cid=None, league="E0"):
    return {"cid": cid or f"0x{ek}-{outcome}", "token_yes": f"y-{ek}-{outcome}", "token_no": f"n-{ek}-{outcome}",
            "event_key": ek, "league": league, "home": "Arsenal", "away": "Leeds", "outcome": outcome,
            "start_ms": START, "rule_flags": ["postponed_open_until_completed", "cancelled_resolves_no"]}


def snap(source="sgo", book="pinnacle", odds=None, probs=None, age=HOUR, ek=EK):
    s = {"source": source, "book": book, "league": ek.split(":")[0], "event_key": ek, "home": "Arsenal",
         "away": "Leeds", "start_ms": START, "obs_ms": NOW - age, "recv_ms": NOW - age + 200}
    s.update({"odds": odds} if odds else {"probs": probs})
    return s


SHARP_ODDS = {"H": 1.80, "D": 3.90, "A": 4.60}


# ---------- B1, B2: devig and method choice ----------

def test_all_seven_methods_give_probability_vectors():
    assert len(F.METHODS) == 7
    for m in F.METHODS:
        p = F.devig_odds({"H": 2.10, "D": 3.40, "A": 3.75}, m)
        assert p is not None and abs(sum(p.values()) - 1) < 1e-9 and all(0 < v < 1 for v in p.values()), m
    assert F.devig_odds({"H": 0.95, "D": 3.4, "A": 3.75}, "power") is None  # odds <= 1 are not odds
    assert F.devig_odds({"H": float("nan"), "D": 3.4, "A": 3.75}, "shin") is None


def matches(seed=0):
    """Synthetic opening odds with a margin and a longshot bias; outcomes drawn from the true probabilities."""
    rng = np.random.default_rng(seed)
    rows = []
    for lg in ("E0", "SP1"):
        for season in ("2019/20", "2020/21", "2021/22", "2022/23", "2023/24", "2024/25"):
            for _ in range(40):
                p = rng.dirichlet([4, 2.5, 3])
                imp = p ** 0.93
                imp = imp / imp.sum() * 1.05
                rows.append({"league": lg, "season": season, "FTR": "HDA"[rng.choice(3, p=p)],
                             **dict(zip(F.OPENING, 1 / imp))})
    return pd.DataFrame(rows)


def test_method_choice_uses_training_seasons_only_and_scores_against_outcomes():
    df, held = matches(), ["2023/24", "2024/25"]  # no closing columns at all: the choice cannot use the close
    ps, table, tr = F.choose_methods(df, held)
    assert ps["name"] == "sports-devig" and ps["state"] == "candidate" and set(ps["params"]) == {"E0", "SP1"}
    assert set(ps["params"].values()) <= set(F.METHODS) and ps["version"]
    # scored against the match outcome: the chosen method's training log loss is mean -ln p(FTR), recomputed by hand
    row = table.set_index("league").loc["E0"]
    t = df[(df.league == "E0") & (df.season < held[0])]
    assert row.train_n == len(t) and row.train_seasons == "2019/20..2022/23"
    by_hand = np.mean([-np.log(F.devig_odds({"H": r.PSH, "D": r.PSD, "A": r.PSA}, row.method)[r.FTR])
                       for r in t.itertuples()])
    assert row.train_ll == pytest.approx(by_hand, rel=1e-12)
    assert tr.loc["E0"].min() == pytest.approx(row.train_ll)
    # corrupting every held-out row (odds and outcomes) leaves the choice and the training numbers unchanged
    bad = df.copy()
    h = bad.season.isin(held)
    bad.loc[h, list(F.OPENING)] = np.random.default_rng(9).uniform(1.2, 12, (h.sum(), 3))
    bad.loc[h, "FTR"] = "A"
    ps2, table2, tr2 = F.choose_methods(bad, held)
    assert ps2 == ps and np.allclose(tr2.to_numpy(), tr.to_numpy())
    assert (table2.train_ll == table.train_ll).all() and not np.allclose(table2.held_ll, table.held_ll)


# ---------- B4: sigma and fair refusals ----------

def test_sigma_fair_non_decreasing_in_age():
    rng = np.random.default_rng(1)
    for params in (F.SIGMA["params"], {"s0": 0.0, "k": 1e-3}, {"s0": 0.05, "k": 0.0}):
        ages = np.sort(rng.uniform(-HOUR, 30 * HOUR, 2000))
        s = [F.sigma_fair(a, params) for a in ages]
        assert all(b >= a for a, b in zip(s, s[1:]))
    sp = F.SIGMA["params"]
    assert F.sigma_fair(0) == pytest.approx(sp["s0"])
    assert F.sigma_fair(4 * HOUR) == pytest.approx((sp["s0"] ** 2 + 4 * sp["k"]) ** 0.5)
    assert F.SIGMA["state"] == "candidate" and {"s0", "k", "max_age_ms"} <= set(sp)


def test_fair_refuses_without_a_fresh_sharp_snapshot():
    m = mmap("H")
    for sharp in (None, [], snap(age=MAX_AGE + 1, odds=SHARP_ODDS),
                  snap(source="football-data", book="PSC", odds=SHARP_ODDS),   # closing odds never price quotes
                  snap(odds=SHARP_ODDS, ek="E0:Chelsea:Leeds:2026-10-10"),     # another match
                  snap(source="kalshi", book="kalshi", probs={"H": 0.5, "D": 0.3, "A": 0.2})):
        f = F.fair(m, sharp, METHODS, NOW)
        assert f["fair"] is None and f["sigma"] is None and f["reason"] == F.NO_SHARP
    ok = F.fair(m, snap(age=MAX_AGE, odds=SHARP_ODDS), METHODS, NOW)  # exactly at max_age is still usable
    assert ok["reason"] is None and ok["age_ms"] == MAX_AGE and ok["method"] == "odds_ratio"
    assert ok["fair"] == pytest.approx(F.devig_odds(SHARP_ODDS, "odds_ratio")["H"])
    assert ok["sigma"] == pytest.approx(F.sigma_fair(MAX_AGE)) and ok["source"] == "sgo:pinnacle"
    # the latest snapshot wins, even when an older one is listed after it
    latest = F.fair(m, [snap(age=HOUR, odds={"H": 2.5, "D": 3.3, "A": 3.0}), snap(age=5 * HOUR, odds=SHARP_ODDS)],
                    METHODS, NOW)
    assert latest["age_ms"] == HOUR and latest["fair"] == pytest.approx(
        F.devig_odds({"H": 2.5, "D": 3.3, "A": 3.0}, "odds_ratio")["H"])
    assert F.fair(mmap(league="I1", ek="I1:Inter:Roma:2026-10-10"), snap(odds=SHARP_ODDS, ek="I1:Inter:Roma:2026-10-10"),
                  METHODS, NOW)["fair"] is None  # no devig method for the league -> fail closed


# ---------- B5: quote gate ----------

def test_quote_gate():
    f, s = 0.50, 0.02

    def c(src, p, age=1000):
        return {"source": src, "p": p, "obs_ms": NOW - age, "books": 1}

    assert F.quote_allowed(f, s, [], NOW) == (False, "no fresh continuous source")
    assert F.quote_allowed(f, s, [c("kalshi", 0.50, CONT_AGE + 1)], NOW) == (False, "no fresh continuous source")
    out = F.quote_allowed(f, s, [c("kalshi", 0.53)], NOW)
    assert not out[0] and "kalshi" in out[1]
    assert not F.quote_allowed(f, s, [c("kalshi", 0.51), c("odds-api", 0.47)], NOW)[0]  # one in, one out
    assert F.quote_allowed(f, s, [c("kalshi", 0.51), c("odds-api", 0.485), c("betfair", 0.519)], NOW) == (True, "ok")
    assert F.quote_allowed(f, s, [c("kalshi", 0.51), c("betfair", 0.90, CONT_AGE + 1)], NOW) == (True, "ok")
    assert not F.quote_allowed(f, s, [c("kalshi", float("nan"))], NOW)[0]
    assert not F.quote_allowed(None, s, [c("kalshi", 0.5)], NOW)[0]
    assert not F.quote_allowed(f, None, [c("kalshi", 0.5)], NOW)[0]


# ---------- B6: consensus and fair sum ----------

def test_consensus_is_median_of_per_book_devig_and_fair_sums_to_one():
    books = {"bet365": {"H": 1.85, "D": 3.6, "A": 4.2}, "unibet": {"H": 1.75, "D": 3.8, "A": 4.6},
             "williamhill": {"H": 1.90, "D": 3.5, "A": 4.0}}
    snaps = [snap("odds-api", b, odds=o, age=2 * MIN) for b, o in books.items()]
    snaps += [snap("odds-api", "bet365", odds={"H": 3.0, "D": 3.0, "A": 3.0}, age=5 * MIN),   # superseded record
              snap("odds-api", "stalebook", odds={"H": 9.0, "D": 5.0, "A": 1.3}, age=CONT_AGE + 1),
              snap("kalshi", "kalshi", probs={"H": 0.52, "D": 0.27, "A": 0.19}, age=MIN),
              snap(odds=SHARP_ODDS)]  # the sharp snapshot is not a continuous source
    cs = {c["source"]: c for c in F.continuous_sources(mmap("H"), snaps, METHODS, NOW)}
    assert set(cs) == {"odds-api", "kalshi"}
    want = statistics.median(F.devig_odds(o, "odds_ratio")["H"] for o in books.values())
    assert cs["odds-api"]["p"] == pytest.approx(want) and cs["odds-api"]["books"] == 3
    assert cs["odds-api"]["obs_ms"] == NOW - 2 * MIN
    assert cs["kalshi"]["p"] == 0.52  # Kalshi probs used as given
    # one Kalshi record per outcome market: a newer record for another outcome does not hide this outcome's
    per_outcome = [snap("kalshi", "kalshi", probs={"H": 0.50}, age=3 * MIN),
                   snap("kalshi", "kalshi", probs={"D": 0.3}, age=MIN)]
    assert F.continuous_sources(mmap("H"), per_outcome, METHODS, NOW)[0]["p"] == 0.50
    total = sum(F.fair(mmap(o), snap(odds=SHARP_ODDS), METHODS, NOW)["fair"] for o in "HDA")
    assert total == pytest.approx(1.0, abs=1e-9)


# ---------- B7: universe checkpoints ----------

class FakeLedger:
    """Mimics Ledger.record's forecasts rule: rows need a cluster_id and must serialise as JSON."""
    def __init__(self):
        self.rows = []

    def record(self, table, row, event_ms):
        assert table == "forecasts" and row.get("cluster_id")
        json.dumps(row, allow_nan=False)
        self.rows.append((table, row, event_ms))


def test_checkpoint_rows_one_per_mapped_market_traded_or_not():
    ek2 = "E0:Chelsea:Fulham:2026-10-11"
    maps = [mmap(o) for o in "HDA"] + [mmap(o, ek=ek2) for o in "HA"]  # match 2 has no sharp snapshot yet
    books = {maps[0]["token_yes"]: Book(maps[0]["token_yes"], [(0.53, 100), (0.52, 50)], [(0.56, 80)], NOW,
                                        own={0.53: 100}),                 # our bid is the whole best level
             maps[1]["token_yes"]: Book(maps[1]["token_yes"], [(0.24, 10)], [(0.27, 10)], NOW)}
    cont = [snap("kalshi", "kalshi", probs={"H": 0.55, "D": 0.25, "A": 0.20}, age=MIN)]
    rows = F.checkpoint_rows(maps, [snap(odds=SHARP_ODDS)], cont, books, "T-3h", NOW, METHODS)
    assert [r["cid"] for r in rows] == [m["cid"] for m in maps]
    for r, m in zip(rows, maps):
        assert r["cluster_id"] == m["event_key"] and r["token_id"] == m["token_yes"] and r["label"] == "T-3h"
        assert r["mode"] == "sports-pregame" and r["ts_ms"] == NOW and "mid_ex_own" in r
    assert rows[0]["mid_ex_own"] == pytest.approx((0.52 + 0.56) / 2)  # own size removed from the mid
    assert rows[1]["mid_ex_own"] == pytest.approx(0.255) and rows[2]["mid_ex_own"] is None
    assert rows[0]["fair"] == pytest.approx(F.devig_odds(SHARP_ODDS, "odds_ratio")["H"])
    assert rows[0]["method"] == "odds_ratio" and rows[0]["source"] == "sgo:pinnacle" and rows[0]["sigma"] > 0
    assert rows[0]["continuous"] == {"kalshi": 0.55}
    assert all(r["fair"] is None and r["reason"] == F.NO_SHARP and r["continuous"] == {} for r in rows[3:])
    led = FakeLedger()
    for r in rows:
        led.record("forecasts", r, r["ts_ms"])
    assert len(led.rows) == 5


# ---------- B8: pull drills ----------

def gs(status="scheduled", start=START):
    return {"source": "espn", "league": "E0", "event_key": EK, "home": "Arsenal", "away": "Leeds",
            "scheduled_start_ms": start, "status": status, "obs_ms": NOW - 2000, "recv_ms": NOW - 1000}


def base(**kw):
    a = dict(now_ms=NOW, market_map=mmap("H"), game_state=gs(), lineup_ms=None, last_sharp_obs_ms=NOW - HOUR,
             cautions=[], feed_age_ms={"polymarket": 1000, "sports": 5000}, gate=(True, "ok"))
    a.update(kw)
    return P.pull_reasons(**a)


def caution(action="pull", scope=None, expires=NOW + MIN, fresh=False):
    return CautionSignal("25-sports-news", scope or mmap("H")["cid"], action, 1.0, expires, fresh, "injury news")


def test_pull_drills_each_rule_fires_and_clears():
    assert base() == []
    # start: from start - 5 min, never waiting for the venue's auto-cancel
    assert base(now_ms=START - 5 * MIN - 1) == []
    assert any("pre-start" in r for r in base(now_ms=START - 5 * MIN))
    # game state: changed start, early in_progress, halting statuses, missing; clears when scheduled on time again
    assert any("differs" in r for r in base(game_state=gs(start=START + 2 * MIN)))
    assert base(game_state=gs(start=START + 60_000)) == []  # within the 60 s tolerance
    assert "game state: in_progress before scheduled start" in base(game_state=gs("in_progress"))
    for st in ("postponed", "delayed", "suspended", "cancelled"):
        assert f"game state: {st}" in base(game_state=gs(st))
    assert "game state: none" in base(game_state=None)
    assert base(game_state=gs("scheduled")) == []
    # stale feeds and sharp reference; clear when fresh
    assert any("polymarket" in r for r in base(feed_age_ms={"polymarket": 30_001, "sports": 5000}))
    assert any("sports" in r for r in base(feed_age_ms={"polymarket": 1000, "sports": 120_001}))
    assert any("polymarket" in r for r in base(feed_age_ms={"sports": 5000}))  # missing age fails closed
    assert base(feed_age_ms={"polymarket": 30_000, "sports": 120_000}) == []
    assert "no fresh sharp reference" in base(last_sharp_obs_ms=NOW - P.PARAMS["sharp_max_age_ms"] - 1)
    assert "no fresh sharp reference" in base(last_sharp_obs_ms=None)
    # quote gate
    assert "quote gate: no fresh continuous source" in base(gate=(False, "no fresh continuous source"))
    assert "quote gate: no result" in base(gate=None)


def test_lineup_pull_holds_until_a_newer_sharp_snapshot():
    lineup = NOW - 10 * MIN
    assert base(lineup_ms=NOW + MIN) == []  # lineup not out yet
    for older in (NOW - HOUR, lineup):  # an older snapshot, or one taken at the lineup instant, does not clear it
        assert any("lineup" in r for r in base(lineup_ms=lineup, last_sharp_obs_ms=older))
    assert base(lineup_ms=lineup, last_sharp_obs_ms=lineup + 1) == []


def test_caution_pulls_and_fresh_observation_resume():
    assert any("caution" in r for r in base(cautions=[caution()]))
    assert base(now_ms=NOW + MIN, cautions=[caution()]) == []  # plain pull ends at expires_ms
    assert any("caution" in r for r in base(cautions=[caution(scope=EK)]))  # event-level scope
    assert base(cautions=[caution(scope="E0:Chelsea:Fulham:2026-10-11")]) == []  # another match
    assert base(cautions=[caution(action="shrink")]) == []  # shrink is the sizer's business, not a pull
    sticky = caution(expires=NOW - HOUR, fresh=True)
    assert any("caution" in r for r in base(cautions=[sticky]))  # past expires_ms, still pulled
    assert any("caution" in r for r in base(now_ms=NOW + 10 * MIN, cautions=[sticky]))
    resumed = caution(action="none", expires=NOW + HOUR)
    assert base(cautions=[sticky, resumed]) == []  # the sentinel replaced it after a fresh observation
    assert any("caution" in r for r in base(cautions=[resumed, sticky]))  # order matters: last signal is current


def test_maker_expiry():
    assert P.maker_expiry(START, START + 2 * HOUR) == START - 5 * MIN
    assert P.maker_expiry(START, START - 10 * MIN) == START - 12 * MIN  # market ends before the start bound


# ---------- B9: soccer pre-registration ----------

def test_soccer_preregistration():
    p = F.SOCCER_PREREG
    assert p["name"] == "soccer-maker" and "markout" in p["statistic"] and "rebate" in p["statistic"]
    assert "reward" in p["statistic"] and "mid_ex_own" in p["statistic"] and "match" in p["cluster"]
    assert p["alpha"] == 0.0228 and p["n"] >= 100 and p["n_stage"] == "shadow" and p["pass_z"] == 2.0
    assert "2 cluster-robust SE" in p["pass_rule"] and (p["futility_z"], p["futility_n"]) == (-1.0, 50)
    assert p["guardrail"]["margin"] == 0.005 and set(p["guardrail"]["metrics"]) == {"brier", "log_loss"}
    json.dumps(p)  # role 15 stores it as JSON
