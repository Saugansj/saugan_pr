"""WP3-B: negRisk executor behind a scanner-evidence gate (B1-B6). No network, no files."""
import dataclasses

import pytest

from trader.contracts import Book, Fill, MarketInfo
from trader.growth import negrisk as nr
from trader.growth.negrisk import NegRiskEvent, basket, completion, confirm, eligible, evidence, hurdle, scan

SECRET = "test-secret"
NOW = 1_800_000_000_000
RATES = (0.07, 0.05, 0.0)
ASKS = (0.30, 0.40, 0.25)


def leg(i, rate, neg_risk=True, rules="r"):
    return MarketInfo(f"c{i}", f"y{i}", f"n{i}", "sports-pregame", f"outcome {i}?", f"{rules}{i}", 0.01, 5.0, rate,
                      neg_risk, NOW + 86_400_000, "ev", kind="negrisk")


def event(n=3, **kw):
    return NegRiskEvent("ev", [leg(i, RATES[i % 3]) for i in range(n)], kw.get("augmented", False),
                        kw.get("has_other", False))


def books(asks=ASKS, sizes=(50.0, 8.379, 40.0)):
    return {f"y{i}": Book(f"y{i}", [(a - 0.01, 100.0)], [(a, s)], NOW) for i, (a, s) in enumerate(zip(asks, sizes))}


def row(eid, ts, eligible=True, edge=0.02, size=10.0, min_size=5.0, rtt=1200):
    return {"event_id": eid, "ts_ms": ts, "eligible": eligible, "edge": edge, "size_at_touch": size,
            "min_size": min_size, "round_trip_ms": rtt}


def open_rows(n=30):
    return [row(f"g{k}", t) for k in range(n) for t in (0, 1500)]


PARAMS = {**nr.PARAMS, "max_shares": 10.0, "budget_usd": 100.0, "max_leg_loss_usd": 100.0, "legging_budget": 0.01}


# ---------- B1 hurdle ----------

def test_hurdle_hand_values():
    # 3 legs: asks 0.95 + fees 0.07*.3*.7 + 0.05*.4*.6 + 0 = 0.0267, + legging 0.01
    h3 = hurdle(list(ASKS), list(RATES), 0.01)
    assert h3 == pytest.approx(0.9867, abs=1e-12) and h3 < 1
    # 5 legs: asks 0.92; fees .0112 + .009375 + 0 + .0063 + .00858 = .035455; legging 0.005
    r5 = [0.07, 0.05, 0.0, 0.07, 0.05]
    h5 = hurdle([0.20, 0.25, 0.15, 0.10, 0.22], r5, 0.005)
    assert h5 == pytest.approx(0.960455, abs=1e-12) and h5 < 1
    # 5 legs, not executable: asks 0.97; fees .011613 + .00962 + 0 + .006853 + .008855 = .036941
    h5b = hurdle([0.21, 0.26, 0.16, 0.11, 0.23], r5, 0.005)
    assert h5b == pytest.approx(1.011941, abs=1e-12) and h5b >= 1
    assert hurdle([0.5, 0.5], [0, 0], 0) == 1.0  # exactly 1: not executable (see basket test)
    with pytest.raises(ValueError):
        hurdle([0.5, 0.5], [0.07], 0)


# ---------- B2 eligibility ----------

def test_valid_event_is_eligible():
    e = event()
    assert eligible(e, confirm(e, NOW + 60_000, SECRET), NOW, SECRET) == (True, "eligible")


@pytest.mark.parametrize("kw", [{"augmented": True}, {"augmented": None}, {"has_other": True}, {"has_other": None}])
def test_flags_fail_closed(kw):
    e = event(**kw)
    assert eligible(e, confirm(e, NOW + 60_000, SECRET), NOW, SECRET)[0] is False


def test_non_negrisk_leg():
    e = event()
    e.legs[1] = dataclasses.replace(e.legs[1], neg_risk=False)
    assert eligible(e, confirm(e, NOW + 60_000, SECRET), NOW, SECRET) == (False, "leg not negRisk")


def test_confirmation_missing_expired_unsigned_tampered():
    e = event()
    good = confirm(e, NOW + 60_000, SECRET)
    assert eligible(e, None, NOW, SECRET)[0] is False
    assert eligible(e, confirm(e, NOW, SECRET), NOW, SECRET) == (False, "confirmation expired")
    assert eligible(e, {k: v for k, v in good.items() if k != "sig"}, NOW, SECRET)[0] is False
    assert eligible(e, {**good, "expiry_ms": NOW + 10**9}, NOW, SECRET)[0] is False   # tampered after signing
    assert eligible(e, confirm(e, NOW + 60_000, "other-key"), NOW, SECRET)[0] is False
    assert eligible(e, good, NOW, "")[0] is False                                   # no key: nothing verifies
    wrong_type = {**good, "type": "clearance"}
    assert eligible(e, {**wrong_type, "sig": nr.sign(wrong_type, SECRET)}, NOW, SECRET)[0] is False


def test_leg_added_or_rules_changed_after_signing():
    e = event()
    conf = confirm(e, NOW + 60_000, SECRET)
    added = NegRiskEvent("ev", e.legs + [leg(3, 0.05)], False, False)
    assert eligible(added, conf, NOW, SECRET) == (False, "confirmation stale: legs or rules changed")
    changed = NegRiskEvent("ev", [e.legs[0], dataclasses.replace(e.legs[1], rules_sha256="new"), e.legs[2]], False, False)
    assert eligible(changed, conf, NOW, SECRET) == (False, "confirmation stale: legs or rules changed")


def test_event_from_crawler_rows_fails_closed():
    base = {"condition_id": "c0", "yes_token_id": "y0", "no_token_id": "n0", "mode": "sports-pregame",
            "question": "q", "rules_sha256": "h", "tick_size": 0.01, "min_order_size": 5, "neg_risk": True,
            "end_time": "2026-10-10T11:30:00Z", "neg_risk_augmented": False, "neg_risk_other": False,
            "fee_schedule": {"exponent": 1, "rate": 0.05, "takerOnly": True, "rebateRate": 0.15}}
    rows = [{**base, "condition_id": f"c{i}", "yes_token_id": f"y{i}", "no_token_id": f"n{i}"} for i in range(3)]
    e = nr.event_from_rows("ev", rows)
    assert (len(e.legs), e.augmented, e.has_other, e.legs[0].fee_rate, e.legs[0].min_size) == (3, False, False, 0.05, 5.0)
    assert nr.event_from_rows("ev", rows[:2] + [{**rows[2], "neg_risk_augmented": None}]).augmented is None
    assert nr.event_from_rows("ev", rows[:2] + [{**rows[2], "neg_risk_other": None}]).has_other is None
    assert nr.event_from_rows("ev", rows[:2] + [{**rows[2], "neg_risk_other": True}]).has_other is True
    assert nr.event_from_rows("ev", rows[:2] + [{**rows[2], "tick_size": None}]) is None    # a leg we cannot build
    assert nr.event_from_rows("ev", rows[:2] + [{**rows[2], "fee_schedule": {"rate": 0.05, "x": 1}}]) is None


# ---------- B3 evidence gate ----------

def test_gate_29_closed_30_open():
    closed, opened = evidence(open_rows(29)), evidence(open_rows(30))
    assert (closed["pass"], closed["n_eligible"]) == (False, 29)
    assert (opened["pass"], opened["n_eligible"]) == (True, 30)


def test_episodes_that_do_not_count():
    rows = open_rows(29) + [
        row("eq", 0), row("eq", 1200),                                  # duration == round trip
        row("single", 0),                                               # single-row sighting: duration 0
        row("inel", 0, eligible=False), row("inel", 5000, eligible=False),
        row("small", 0, size=4.99), row("small", 5000, size=4.99),     # below the largest leg minimum
        row("neg", 0, edge=0.0), row("neg", 5000, edge=-0.01),
        row("noask", 0, edge=None), row("noask", 5000, edge=None),
        row("nortt", 0, rtt=None), row("nortt", 5000, rtt=None),
        row("split", 0), row("split", 1000, eligible=False), row("split", 2000),  # broken run: two short episodes
    ]
    ev = evidence(rows)
    assert ev["n_eligible"] == 29 and ev["pass"] is False
    assert {e["event_id"]: e["counts"] for e in ev["episodes"] if not e["event_id"].startswith("g")} == {
        "eq": False, "single": False, "nortt": False, "split": False}
    assert evidence(rows + [row("late", 9000), row("late", 0)])["pass"] is True  # rows sorted by time per event


def test_scan_rows_feed_the_gate():
    e = event()
    cheap = books(asks=(0.30, 0.30, 0.25))
    r0 = scan(e, cheap, NOW, 1200, (True, "eligible"), PARAMS)
    assert r0["hurdle"] == pytest.approx(hurdle([0.30, 0.30, 0.25], list(RATES), 0.01))
    assert (r0["size_at_touch"], r0["min_size"], r0["eligible"], r0["edge"] > 0) == (8.379, 5.0, True, True)
    r1 = scan(e, cheap, NOW + 1201, 1200, True, PARAMS)
    assert evidence([r0, r1], n_min=1)["pass"] is True
    gap = scan(e, {k: v for k, v in cheap.items() if k != "y2"}, NOW, 1200, (True, "eligible"), PARAMS)
    assert (gap["edge"], gap["size_at_touch"], gap["reason"]) == (None, None, "no ask on a leg")
    assert scan(e, cheap, NOW, 1200, eligible(e, None, NOW, SECRET), PARAMS)["eligible"] is False


# ---------- B4 refusals ----------

def test_basket_refusals():
    e = event()
    conf = confirm(e, NOW + 60_000, SECRET)
    b = books()
    for args, why in [((open_rows(29), "replay-1", conf), "evidence gate closed"),
                      ((open_rows(), "", conf), "no replay_ref"),
                      ((open_rows(), "replay-1", None), "ineligible"),
                      ((open_rows(), "replay-1", confirm(e, NOW - 1, SECRET)), "ineligible")]:
        intents, info = basket(e, b, NOW, PARAMS, *args, SECRET)
        assert intents == [] and info["reason"].startswith(why)
    flat = NegRiskEvent("ev", [leg(0, 0.0), leg(1, 0.0)], False, False)
    intents, info = basket(flat, books(asks=(0.5, 0.5), sizes=(50, 50)), NOW, {**PARAMS, "legging_budget": 0.0},
                           open_rows(), "replay-1", confirm(flat, NOW + 60_000, SECRET), SECRET)
    assert intents == [] and info["reason"].startswith("hurdle 1.0000 >= 1")


# ---------- B5 basket ----------

def test_basket_emits_one_taker_per_leg():
    e = event()
    intents, info = basket(e, books(), NOW, PARAMS, open_rows(), "replay-1", confirm(e, NOW + 60_000, SECRET), SECRET)
    assert info["reason"] == "ok" and len(intents) == 3
    assert [(i.cid, i.token_id, i.price) for i in intents] == [("c0", "y0", 0.30), ("c1", "y1", 0.40), ("c2", "y2", 0.25)]
    assert all(i.side == "BUY" and i.kind == "taker" and i.strategy == "negrisk-arb" for i in intents)
    assert all(i.expiry_ms == NOW + PARAMS["legging_ms"] and info["basket_id"] in i.reason for i in intents)
    assert {i.size for i in intents} == {8.37}                     # smallest best-ask 8.379, floored
    # costs 0.3147, 0.412, 0.25 -> planned 0.9767
    assert info["planned_cost"] == pytest.approx(0.9767, abs=1e-12)
    assert info["worst_case_leg_loss_usd"] == pytest.approx(8.37 * (0.9767 - 0.25), abs=1e-9)  # 6.082479
    assert info["locked_edge_usd"] == pytest.approx(8.37 * (1 - 0.9767), abs=1e-9)


def test_basket_size_caps_and_refusals():
    e = event()
    conf = confirm(e, NOW + 60_000, SECRET)
    go = lambda **p: basket(e, books(), NOW, {**PARAMS, **p}, open_rows(), "replay-1", conf, SECRET)
    assert go(max_shares=6.0)[1]["size"] == 6.0
    assert go(budget_usd=5.0)[1]["size"] == 5.11                   # 5 / 0.9767 = 5.119..., floored not rounded
    intents, info = go(budget_usd=4.0)                             # 4.09 < leg minimum 5
    assert intents == [] and info["reason"].startswith("size 4.09 below leg minimum 5.0")
    intents, info = go(max_leg_loss_usd=6.0)                       # 6.08 > 6
    assert intents == [] and info["reason"].startswith("worst-case leg loss 6.08 > 6.0")
    assert go(max_leg_loss_usd=6.1)[1]["reason"] == "ok"


# ---------- B6 completion ----------

def fill(cid, price, size, rate):
    return Fill("o", "negrisk-arb", cid, f"y{cid[1:]}", "BUY", price, size, NOW, False, size * rate * price * (1 - price))


def test_completion_within_and_beyond_legging_budget():
    e = event()
    _, info = basket(e, books(), NOW, PARAMS, open_rows(), "replay-1", confirm(e, NOW + 60_000, SECRET), SECRET)
    done = [fill("c0", 0.30, 8.37, 0.07), fill("c1", 0.40, 8.37, 0.05)]
    intents, why = completion(info, done, books(asks=(0.31, 0.41, 0.255)), NOW + 10, PARAMS)
    assert why == "completing 1 legs" and [(i.cid, i.price, i.size, i.side, i.kind) for i in intents] == [
        ("c2", 0.255, 8.37, "BUY", "taker")]
    assert completion(info, done, books(asks=(0.31, 0.41, 0.27)), NOW, PARAMS) == ([], "legging budget exceeded")
    partial = [fill("c0", 0.30, 8.37, 0.07), fill("c1", 0.40, 5.0, 0.05)]
    intents, _ = completion(info, partial, books(), NOW, PARAMS)
    assert [(i.cid, i.size) for i in intents] == [("c1", 3.37), ("c2", 8.37)]
    assert completion(info, done + [fill("c2", 0.25, 8.37, 0.0)], books(), NOW, PARAMS) == ([], "complete")
    assert completion(info, done, {k: v for k, v in books().items() if k != "y2"}, NOW, PARAMS)[0] == []


def test_registry_and_prereg():
    assert nr.REGISTRY["negrisk-arb"]["state"] == "candidate"
    assert set(nr.REGISTRY["negrisk-arb"]["params"]) == {"legging_budget", "legging_ms", "max_shares", "budget_usd",
                                                         "max_leg_loss_usd", "n_min"}
    assert {"name", "statistic", "cluster", "se", "alpha", "pass_z", "n", "futility_z", "futility_n"} <= set(nr.PREREG)
    assert nr.PREREG["n"] >= 30 and nr.PREREG["cluster"].startswith("event")
