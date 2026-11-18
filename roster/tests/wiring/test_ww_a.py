"""WW-A wiring tests: kernel and breakers behind their feature flags (build/wiring/dispatch.md, A1-A5)."""
import dataclasses
import hashlib
import json
import math
import random

import pytest

from trader.breakers import CUSUM_BURN_IN, Breakers
from trader.contracts import Book, Intent, KernelContext, MarketInfo, Order, TradingState
from trader.kernel import PRIVILEGED, STRATEGIES, RiskKernel, clearance_key, key_id, series_scope, sign
from trader.ledger import Ledger

A, R, H = TradingState.ACTIVE, TradingState.REDUCING, TradingState.HALTED
KEY = "test-human-key"
NOW = 1_790_000_000_000
MIN = 60_000
DAY = 86_400_000
FAST = MarketInfo(cid="c-fast", token_yes="fy", token_no="fn", mode="crypto-fast", question="BTC Up or Down 5m",
                  rules_sha256="r" * 64, tick_size=0.01, min_size=5, fee_rate=0.07, neg_risk=False,
                  end_ms=NOW + 4 * MIN, event_group="BTC-5m@x", asset="BTC", kind="updown", source_id="chainlink:BTC/USD")
TERM = MarketInfo(cid="c-term", token_yes="ty", token_no="tn", mode="crypto-term", question="BTC above 74k Oct 2",
                  rules_sha256="s" * 64, tick_size=0.001, min_size=5, fee_rate=0.07, neg_risk=False,
                  end_ms=NOW + 20 * 60 * MIN, event_group="BTC@2026-10-02T16:00Z", asset="BTC", kind="strike",
                  strike=74000.0, source_id="binance:BTC/USDT")
TERM2 = dataclasses.replace(TERM, cid="c-term2", token_yes="t2y", token_no="t2n", strike=76000.0,
                            event_group="BTC@2026-10-03T16:00Z")
SOL = dataclasses.replace(TERM, cid="c-sol", token_yes="sy", token_no="sn", asset="SOL", strike=200.0,
                          question="SOL above 200", source_id="binance:SOL/USDT", event_group="SOL@2026-10-02T16:00Z")
SPORT = MarketInfo(cid="c-sport", token_yes="py", token_no="pn", mode="sports-pregame", question="Arsenal win?",
                   rules_sha256="p" * 64, tick_size=0.01, min_size=5, fee_rate=0.0, neg_risk=True,
                   end_ms=NOW + 3 * DAY, event_group="epl-ars-che", kind="")
LEG = dataclasses.replace(SPORT, cid="c-leg", token_yes="ly", token_no="ln", kind="negrisk")
ALL = (FAST, TERM, TERM2, SOL, SPORT, LEG)
FEEDS = {"polymarket": 100, "binance:BTC": 100, "binance:SOL": 100, "dvol:BTC": 1000, "basis:USDT": 1000,
         "sports": 30_000}
ON = ("live_risk", "dd7", "clock_gate", "heartbeat", "settlement", "capital_ladder", "touch", "universe_ext",
      "quote_objective", "negrisk_scan", "fast_maker", "sports", "markout_cusum")


def clr(m, expiry=NOW + DAY, **change):
    rec = {"type": "clearance", "key": {**clearance_key(m), **change}, "signer": "me", "nonce": "n-" + m.cid,
           "expiry_ms": expiry, "signed_ms": NOW}
    rec["sig"] = sign(rec, KEY)
    return {key_id(rec["key"]): rec}


def ctx(markets=ALL, positions=None, orders=(), bankroll_usd=50.0, feeds=None, clearances=None):
    if clearances is None:
        clearances = {k: v for m in markets for k, v in clr(m).items()}
    return KernelContext(now_ms=NOW, markets={m.cid: m for m in markets},
                         books={t: Book(t, [(0.50, 100)], [(0.52, 100)], NOW) for m in markets
                                for t in (m.token_yes, m.token_no)},
                         positions=positions or {}, open_orders=list(orders), clearances=clearances,
                         bankroll_usd=bankroll_usd, feed_age_ms=FEEDS if feeds is None else feeds)


def intent(m=TERM, strategy="ladder-maker", token=None, side="BUY", price=0.5, size=5.0, kind="taker", expiry=None,
           fair=0.6):
    expiry = expiry or (NOW + 5_000 if kind == "taker" else NOW + 60 * MIN)
    return Intent(strategy=strategy, cid=m.cid, token_id=token or m.token_yes, side=side, price=price, size=size,
                  kind=kind, expiry_ms=expiry, fair=fair, reason="t")


def kern(*flags, **kw):
    return RiskKernel(secret=KEY, nonce_path=None, features=flags, **kw)


# ---- A1 flags off: identical decisions on a recorded intent set -----------------------------------------------------
# Digest of the decisions the audited Phase 1 kernel (trader/kernel.py before WW-A) gives on recorded_cases(); see
# the report's "How to reproduce" for regenerating it from that file.
PHASE1_DIGEST = "ca338f30e9b78e7f95d7194337c418b2882980dfdf9adda4a917756d3ec2cfba"
STRATS = ("ladder-maker", "btc-speed", "sports-maker", "negrisk-arb", "fast-updown-maker", "nope")


def recorded_cases(n=3000, seed=20261007):
    """Seeded intents over varied contexts: scope states, positions, live orders, clearances, feed ages, bankrolls,
    GTD starts, prices (NaN and out of range included), on every market kind the new flags touch."""
    rnd = random.Random(seed)
    toks = [t for m in ALL for t in (m.token_yes, m.token_no)]
    for i in range(n):
        m = rnd.choice(ALL)
        orders = []
        for j in range(rnd.randint(0, 3)):
            om = rnd.choice(ALL)
            oi = intent(om, rnd.choice(STRATS[:2]), token=rnd.choice((om.token_yes, om.token_no)),
                        side=rnd.choice(("BUY", "SELL")), size=rnd.choice((2.0, 5.0, 20.0)))
            orders.append(Order(f"o{i}-{j}", oi, rnd.choice(("open", "partial", "unknown", "journaled", "filled")),
                                filled=rnd.choice((0.0, 1.0))))
        clear = rnd.choice(("all",) * 6 + ("none", "tick", "expired", "badsig"))
        clearances = {k: v for mk in ALL for k, v in clr(mk).items()} if clear == "all" else \
            {} if clear == "none" else clr(m, tick_size=0.5) if clear == "tick" else \
            clr(m, expiry=NOW - 1) if clear == "expired" else {k: {**v, "sig": "x"} for k, v in clr(m).items()}
        feeds = {f: (100 if rnd.random() < 0.8 else rnd.choice((4_000, 6_000, 40_000, 200_000, 700_000))) for f in FEEDS
                 if rnd.random() < 0.97}
        c = ctx(positions={t: rnd.choice((0.0, 5.0, 30.0)) for t in toks if rnd.random() < 0.2}, orders=orders,
                bankroll_usd=rnd.choice((10.0, 50.0, 55.0, 56.0, math.nan)), feeds=feeds, clearances=clearances)
        kind = rnd.choice(("maker", "taker"))
        own = {"crypto-fast": "btc-speed", "crypto-term": "ladder-maker"}.get(m.mode, rnd.choice(STRATS[2:4]))
        it = intent(m, own if rnd.random() < 0.85 else rnd.choice(STRATS),
                    token=rnd.choice((m.token_yes, m.token_no)) if rnd.random() < 0.95 else "zz",
                    side=rnd.choice(("BUY", "BUY", "SELL")),
                    price=rnd.choice((0.01, 0.3, 0.5, 0.9)) if rnd.random() < 0.9 else rnd.choice((0.0, 1.2, math.nan)),
                    size=rnd.choice((1.0, 5.0, 20.0, 60.0)) if rnd.random() < 0.95 else -1.0, kind=kind,
                    expiry=NOW + rnd.choice((5_000, 2 * MIN, 3 * MIN, 60 * MIN, 3 * DAY)))
        trips = [(rnd.choice(("global", m.cid, m.event_group, it.strategy)), rnd.choice((R, H)),
                  rnd.choice(("breaker:x", "advisor", "human"))) for _ in range(rnd.choice((0, 0, 0, 1, 2)))]
        starts = {m.cid: NOW + rnd.choice((-MIN, 3 * MIN, 2 * 60 * MIN))} if rnd.random() < 0.3 else {}
        yield it, c, trips, starts


def decisions(make_kernel):
    out = []
    for it, c, trips, starts in recorded_cases():
        k = make_kernel()
        for scope, lv, src in trips:
            k.trip(scope, "t", src, lv)
        k.starts.update(starts)
        d = k.check(it, c)
        out.append([d.approved, d.reason, d.binding_cap])
    return hashlib.sha256(json.dumps(out).encode()).hexdigest()


def test_a1_flags_off_identical_to_phase1():
    assert decisions(lambda: RiskKernel(secret=KEY, nonce_path=None)) == PHASE1_DIGEST
    assert RiskKernel(secret=KEY, nonce_path=None).strategies is STRATEGIES


def test_a1_breakers_only_flags_leave_kernel_identical(tmp_path):
    """Flags that act outside check() (and the breakers' flags) give the same check() decisions."""
    assert decisions(lambda: kern("dd7", "clock_gate", "heartbeat", "settlement", "markout_cusum")) == PHASE1_DIGEST


def test_a1_flags_off_hooks_are_noops(tmp_path):
    k = kern()
    k.clock(5_000, NOW, NOW)                                    # would HALT with clock_gate on
    assert k.state == A and k.trips == []
    o = Order("o1", intent(), "open")
    k.trip("global", "t", "breaker:x", R)
    assert k.pull_ids([o], {}, {TERM.cid: TERM}) == []
    b = Breakers(k)                                             # no run_dir needed with the flags off
    assert b.dd7 is None and b.cusum is None
    b.on_equity(100.0, NOW)
    b.on_equity(89.5, NOW + 2 * DAY)
    assert not any("7-day" in t["reason"] for t in k.trips)
    assert not list(tmp_path.iterdir())


# ---- A2 each flag's rule rejects its synthetic trigger ---------------------------------------------------------------
def test_a2_live_risk_stress_cap():
    it, c = intent(), ctx(positions={"t2y": 10.0})
    assert kern().check(it, c).approved
    d = kern("live_risk").check(it, c)                          # no ref: unpriceable crypto loses its whole value
    assert not d.approved and d.binding_cap == "stress"
    k = kern("live_risk")
    k.ref = {"BTC": {"price": 74_000.0, "dvol": 50.0}}
    assert k.check(intent(size=1.0, price=0.5), ctx()).approved  # priced, small: within 5% of bankroll


def test_a2_live_risk_resolution_cap():
    k = kern("live_risk")
    k.ref = {"BTC": {"price": 74_000.0, "dvol": 50.0}}
    k.printed = {TERM.cid}
    d = k.check(intent(size=5.0, price=0.5), ctx(positions={"ty": 8.0}))
    assert not d.approved and d.binding_cap.startswith("resolution:")


def test_a2_live_risk_reducing_rule_and_pulls():
    c = ctx(positions={"ty": 10.0})
    low_sell = intent(side="SELL", kind="maker", price=0.40, fair=0.6)   # maker exit far below fair - fee
    k_off, k_on = kern(), kern("live_risk")
    for k in (k_off, k_on):
        k.trip("global", "dd", "breaker:drawdown", R)
    assert k_off.check(low_sell, c).approved
    d = k_on.check(low_sell, c)
    assert not d.approved and "below fair - fee" in d.reason
    assert k_on.check(intent(side="SELL", kind="maker", price=0.59, fair=0.6), c).approved
    assert not k_on.check(intent(side="SELL", kind="taker", price=0.5), c).approved   # taker exit needs a token
    buy_o, sell_o = Order("b", intent(m=TERM2), "open"), Order("s", intent(side="SELL"), "open")
    k = kern("live_risk")
    assert k.pull_ids([buy_o, sell_o], c.positions, c.markets) == []                  # nothing REDUCING yet
    k.trip(TERM2.event_group, "t", "breaker:x", R)
    assert k.pull_ids([buy_o, sell_o, Order("b2", intent(), "open")], c.positions, c.markets) == ["b"]
    k.trip("global", "t", "breaker:x", R)
    assert k.pull_ids([buy_o, sell_o, Order("b2", intent(token="tn", size=20.0), "open")], c.positions,
                      c.markets) == ["b", "b2"]                  # SELLs stay; an over-sized complement BUY is pulled


def test_a2_dd7(tmp_path):
    k = kern("dd7")
    b = Breakers(k, run_dir=tmp_path)
    b.on_equity(100.0, NOW)
    b.on_equity(89.0, NOW + 2 * DAY)                            # new UTC day: the daily breaker sees no drop
    assert [t["source"] for t in k.trips] == ["breaker:drawdown7d"] and k.state == R
    with pytest.raises(ValueError):
        Breakers(kern("dd7"))                                   # persistence needs a run dir


def test_a2_clock_gate():
    k = kern("clock_gate")
    k.clock(20.0, NOW, NOW)
    assert k.state == A and k.check(intent(), ctx()).approved
    k.clock(300.0, NOW, NOW)                                    # this PC's ~300 ms offset -> REDUCING
    assert k.state == R and "REDUCING" in k.check(intent(), ctx()).reason
    k2 = kern("clock_gate")
    k2.clock(20.0, math.nan, NOW)                               # NaN timestamp = stale, not fresh (Phase 2 minor)
    assert k2.state == R
    k2.clock(1_500.0, NOW, NOW)
    assert k2.state == H and k2.trips[-1]["source"] == "kernel"


def test_a2_new_strategies_only_with_their_flag():
    k_off = kern()
    sm = intent(SPORT, "sports-maker", kind="maker", price=0.4)
    na = intent(LEG, "negrisk-arb", price=0.4)
    fu = intent(FAST, "fast-updown-maker", price=0.4)
    for it in (sm, na, fu):
        assert "unknown strategy" in k_off.check(it, ctx()).reason
    k = kern("sports", "negrisk_scan", "fast_maker")
    assert "needs the market's start" in k.check(sm, ctx()).reason   # sports GTD never fails open
    k.starts[SPORT.cid] = NOW + 2 * 60 * MIN
    assert k.check(sm, ctx()).approved
    assert "stale" in k.check(sm, ctx(feeds={**FEEDS, "sports": 130_000})).reason
    k.starts[SPORT.cid] = NOW + 4 * MIN                         # inside start - 5 min
    assert "GTD" in k.check(sm, ctx()).reason
    assert k.check(na, ctx()).approved
    assert "over strategy:negrisk-arb" in k.check(intent(LEG, "negrisk-arb", price=0.5, size=30.0), ctx()).reason
    assert k.check(fu, ctx()).approved
    assert "over strategy:fast-updown-maker" in k.check(dataclasses.replace(fu, size=13.0), ctx()).reason
    # a sports market with a parsed source, or a crypto market, is not theirs
    assert "provenance" in k.check(sm, ctx(markets=(dataclasses.replace(SPORT, source_id="x"),))).reason
    assert "does not trade mode" in k.check(intent(TERM, "sports-maker"), ctx()).reason


def test_a2_universe_ext_sol_sources():
    it = intent(SOL)
    assert "provenance" in kern().check(it, ctx()).reason
    k = kern("universe_ext")
    assert k.check(it, ctx()).approved                          # no dvol:SOL needed (realised vol)
    assert "stale" in k.check(it, ctx(feeds={**FEEDS, "binance:SOL": 6_000})).reason
    assert "dvol:BTC" in k.check(intent(TERM), ctx(feeds={**FEEDS, "dvol:BTC": 200_000})).reason
    assert STRATEGIES["ladder-maker"]["sources"] == {"BTC": "binance:BTC/USDT", "ETH": "binance:ETH/USDT"}


def _cusum_feed(b, m, means, start=0):
    """One fill markout per cluster; a cluster closes when the next starts (so feed one extra)."""
    for i, x in enumerate(means):
        mi = dataclasses.replace(m, event_group=f"{m.event_group}#{start + i}")
        b.markets[m.cid] = mi
        b.add_markout(m.cid, x, NOW + (start + i) * MIN)


def test_a2_markout_cusum(tmp_path):
    k = kern("markout_cusum")
    b = Breakers(k, run_dir=tmp_path, markets={})
    rnd = random.Random(1)
    _cusum_feed(b, TERM, [rnd.gauss(0, 0.01) for _ in range(CUSUM_BURN_IN + 1)])
    assert k.trips == []
    _cusum_feed(b, TERM, [-0.05] * 6, start=CUSUM_BURN_IN + 1)
    scope = series_scope(TERM)
    assert [(t["scope"], t["source"], t["level"]) for t in k.trips] == [(scope, "breaker:markout_cusum", "REDUCING")]
    k.starts.clear()
    assert "REDUCING" in k.check(intent(TERM2), ctx()).reason   # the whole series is locked, not one cid
    assert k.check(intent(FAST, "btc-speed"), ctx()).approved
    # the count blacklist is replaced: 30 bad markouts on one cid trip nothing per cid
    k2 = kern("markout_cusum")
    b2 = Breakers(k2, run_dir=tmp_path / "2", markets={TERM.cid: TERM})
    for _ in range(30):
        b2.add_markout(TERM.cid, -0.05)
    assert k2.trips == []
    k3 = kern()
    b3 = Breakers(k3)
    for _ in range(30):
        b3.add_markout(TERM.cid, -0.05 + random.Random(_).gauss(0, 0.001))
    assert k3.trips[0]["scope"] == TERM.cid                    # flags off: the Phase 1 blacklist still trips


# ---- A3 dd7 state survives a restart --------------------------------------------------------------------------------
def test_a3_dd7_survives_restart(tmp_path):
    k1 = kern("dd7")
    b1 = Breakers(k1, run_dir=tmp_path)
    b1.on_equity(100.0, NOW)
    b1.on_equity(97.0, NOW + DAY)
    assert (tmp_path / "dd7_samples.json").exists() and k1.trips == []
    k2 = kern("dd7")                                            # restart: new kernel and board, same run dir
    b2 = Breakers(k2, run_dir=tmp_path)
    b2.on_equity(89.0, NOW + 3 * DAY)
    assert [t["source"] for t in k2.trips] == ["breaker:drawdown7d"]
    k3 = kern("dd7")                                            # control: without the saved samples, no trip
    Breakers(k3, run_dir=tmp_path / "fresh").on_equity(89.0, NOW + 3 * DAY)
    assert k3.trips == []
    # after the trip the window re-armed at 89 and was saved: a restart does not re-trip on the same loss
    k4 = kern("dd7")
    Breakers(k4, run_dir=tmp_path).on_equity(88.0, NOW + 3 * DAY + MIN)
    assert k4.trips == []


def test_a3_markout_cusum_survives_restart(tmp_path):
    rnd = random.Random(2)
    base = [rnd.gauss(0, 0.01) for _ in range(CUSUM_BURN_IN + 1)]
    k1 = kern("markout_cusum")
    b1 = Breakers(k1, run_dir=tmp_path, markets={})
    _cusum_feed(b1, TERM, base + [-0.05] * 2)
    k2 = kern("markout_cusum")                                  # restart mid-drift
    b2 = Breakers(k2, run_dir=tmp_path, markets={})
    _cusum_feed(b2, TERM, [-0.05] * 4, start=len(base) + 2)
    kc = kern("markout_cusum")                                  # control: the same drift in one process
    bc = Breakers(kc, run_dir=tmp_path / "c", markets={})
    _cusum_feed(bc, TERM, base + [-0.05] * 6)
    assert [t["reason"] for t in k1.trips + k2.trips] == [t["reason"] for t in kc.trips] != []


# ---- A4 the global cap follows current_cap, and so does the 1.1x refusal --------------------------------------------
def test_a4_capital_ladder(tmp_path):
    led = Ledger(tmp_path / "trader.db")
    k = kern("capital_ladder", ledger=led)
    assert k.global_cap == 50.0                                 # fresh ledger: $50
    assert k.check(intent(), ctx(bankroll_usd=55.0)).approved
    assert "1.1 x global cap 50.00" in k.check(intent(), ctx(bankroll_usd=56.0)).reason
    led.register("global-cap", "250", {"cap_usd": 250.0})
    with led.db:
        led.db.execute("UPDATE registry SET state = 'live' WHERE name = 'global-cap'")   # stands in for promote_step
    later = dataclasses.replace(ctx(bankroll_usd=270.0), now_ms=NOW + MIN)
    assert k.check(intent(), later).approved and k.global_cap == 250.0
    d = k.check(intent(), dataclasses.replace(later, bankroll_usd=276.0))
    assert not d.approved and "1.1 x global cap 250.00" in d.reason
    assert "1.1 x global cap 50.00" in kern().check(intent(), ctx(bankroll_usd=56.0)).reason   # flag off: fixed $50
    with pytest.raises(ValueError):
        kern("capital_ladder")                                  # no ledger: refuse to start


# ---- A5 no AI or T5 source can reach HALTED --------------------------------------------------------------------------
def test_a5_no_ai_halt_with_every_flag(tmp_path):
    led = Ledger(tmp_path / "trader.db")
    k = kern(*ON, ledger=led)
    b = Breakers(k, run_dir=tmp_path, markets={})
    for src in ("advisor:board", "02-cusum", "34-drift", "T5", "llm"):
        k.trip("global", "ai", src, H)
    assert k.state == R
    b.on_equity(100.0, NOW)
    b.on_equity(80.0, NOW + 2 * DAY)
    _cusum_feed(b, TERM, [random.Random(3).gauss(0, 0.01) for _ in range(CUSUM_BURN_IN + 1)] + [-0.05] * 6)
    k.clock(300.0, NOW, NOW)
    assert k.state == R
    assert all(t["source"].split(":")[0] in PRIVILEGED for t in k.trips if t["level"] == "HALTED")
    assert all(t["level"] != "HALTED" for t in k.trips if t["source"].split(":")[0] not in PRIVILEGED)
