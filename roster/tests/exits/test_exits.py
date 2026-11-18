"""WX-A acceptance tests (X1-X5): exit manager behind flag `exits`. Fakes only, no network, files only under tmp_path."""
import dataclasses
import random
import socket

import pytest

from tests.wiring import test_ww_c as C
from tests.wiring import test_ww_d as D
from trader import features, fees
from trader.contracts import Book, Intent, KernelContext, Order, TradingState
from trader.engines import exits as X
from trader.engines import ladder as L
from trader.kernel import RiskKernel, clearance_key, key_id, sign
from trader.loop import Trader, registrations

E, H, MIN = C.E, L.H_MS, L.MIN_MS
NOW = E - 6 * H
FEEDS = {f: 0 for f in ("polymarket", "binance:BTC", "dvol:BTC", "basis:USDT")}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("network call attempted")
    monkeypatch.setattr(socket.socket, "connect", refuse)


def mkt(cid="m", min_size=5.0, end=E):
    return dataclasses.replace(C.mk(cid, 80_000.0, end=end, min_size=min_size), source_id="binance:BTC/USDT")


def book(tok, bid, ask, bid_size=100.0, ts=NOW):
    return Book(tok, [(bid, bid_size)] if bid is not None else [], [(ask, 100.0)] if ask is not None else [], ts)


def one(m, f, bid, ask, held=10.0, cost=0.5, unc=0.0, tau_h=6.0, params=None, room=float("inf"), bid_size=100.0,
        tok=None):
    tok = tok or m.token_yes
    bk = {tok: book(tok, bid, ask, bid_size)}
    fair = {m.cid: {"f": f if tok == m.token_yes else 1 - f, "unc": unc, "tau_h": tau_h, "pull": None}}
    return X.exit_intents(NOW, {tok: held}, {tok: (held, cost)}, bk, fair, {m.cid: m}, params or {}, room)


def sell_value(bid, m):
    return bid - fees.fee(1, bid, m.fee_rate)


# ---------- X1: flag off (and on) leaves the ladder's own targets identical ----------

def test_x1_ladder_targets_identical_with_and_without_flag():
    for eng in (L.LadderEngine(), L.LadderEngine(flags=("exits",))):
        i, r = C.run(eng, C.tick_set())
        assert (sum(map(len, i)), len(r), C.digest(i), C.digest(r)) == C.BASELINE
    eng = L.LadderEngine()
    C.run(eng, C.tick_set())
    assert eng.fair == {}                                          # nothing kept with the flag off


def test_x1_flag_registered_off_by_default(tmp_path):
    assert "exits" in features.FLAGS and "exits" not in features.PAPER_SAFE
    assert features.load(tmp_path) == frozenset()
    reg, pre = registrations(frozenset({"exits"}))
    assert reg["exit-manager"]["state"] == "candidate" and reg["exit-manager"]["params"]["fv_margin"] == 0.02
    assert all(reg["exit-manager"]["params"][k] is None for k in ("tp_pct", "sl_drop", "release_bid"))
    assert pre[0]["name"] == "exit-manager-v1" and pre[0]["n"] == 100 and pre[0]["futility_n"] == 50
    assert registrations(frozenset()) == ({}, [])


# ---------- X2: each rule fires exactly when it should ----------

def test_x2_r1_fires_exactly_above_fair_plus_margin():
    m, rnd = mkt(), random.Random(3)
    for _ in range(3000):
        f, unc = rnd.uniform(0.01, 0.99), rnd.choice((0.0, rnd.uniform(0, 0.05)))
        bid = round(rnd.uniform(0.01, 0.98), 2)
        thr = f + max(0.02, 1.0 * unc)
        if abs(sell_value(bid, m) - thr) < 1e-6:
            continue
        intents, rows = one(m, f, bid, round(bid + 0.01, 2), unc=unc)
        assert (rows[0]["rule"] == "R1") == (sell_value(bid, m) > thr), (f, unc, bid)
        assert rows[0]["rule"] in ("R1", None)                     # R2-R4 off by default
        assert bool(intents) == (rows[0]["rule"] == "R1")
        assert rows[0]["hold_value"] == f and rows[0]["sell_value"] == sell_value(bid, m)


def test_x2_r2_take_profit_only_when_set():
    m = mkt()
    args = dict(f=0.70, bid=0.56, ask=0.57, cost=0.50)            # +12% at the bid; R1 quiet (fair above the bid)
    assert one(m, **args)[1][0]["rule"] is None
    assert one(m, **args, params={"tp_pct": 0.10})[1][0]["rule"] == "R2"
    assert one(m, **args, params={"tp_pct": 0.15})[1][0]["rule"] is None
    assert one(m, **args, params={"tp_pct": 0.10}, tau_h=1.0)[1][0]["rule"] is None   # tp_min_tau_h 2


def test_x2_r3_model_stop_only_when_set():
    m = mkt()
    args = dict(f=0.45, bid=0.45, ask=0.46, cost=0.60)            # fair 0.15 under cost, market pays about fair
    assert one(m, **args)[1][0]["rule"] is None
    assert one(m, **args, params={"sl_drop": 0.10})[1][0]["rule"] == "R3"
    assert one(m, **args, params={"sl_drop": 0.20})[1][0]["rule"] is None
    assert one(m, **{**args, "bid": 0.40, "ask": 0.41}, params={"sl_drop": 0.10})[1][0]["rule"] is None  # bid too low


def test_x2_r4_capital_release_only_when_set():
    m = mkt()
    args = dict(f=0.995, bid=0.97, ask=0.98, cost=0.80, tau_h=3.0)
    assert one(m, **args, room=1.0)[1][0]["rule"] is None
    p = {"release_bid": 0.97}
    assert one(m, **args, params=p, room=1.0)[1][0]["rule"] == "R4"
    assert one(m, **args, params=p, room=10.0)[1][0]["rule"] is None                 # room above release_room_usd
    assert one(m, **{**args, "tau_h": 0.5}, params=p, room=1.0)[1][0]["rule"] is None
    assert one(m, **{**args, "bid": 0.96}, params=p, room=1.0)[1][0]["rule"] is None


def test_x2_execution_taker_at_bid_else_post_only_maker():
    m = mkt()
    (t,), _ = one(m, 0.30, 0.60, 0.62)
    assert (t.side, t.kind, t.price, t.size, t.reduces_exposure, t.expiry_ms) == ("SELL", "taker", 0.60, 10.0, True,
                                                                                   NOW + 2000)
    (mk_,), _ = one(m, 0.30, 0.60, 0.62, bid_size=3.0)            # top bid under the market minimum
    assert mk_.kind == "maker" and mk_.price == 0.61 and mk_.size == 10.0 and mk_.reduces_exposure
    assert NOW + 5 * MIN <= mk_.expiry_ms <= m.end_ms - 3 * MIN
    (mk2,), _ = one(m, 0.55, 0.60, 0.62, bid_size=3.0, unc=0.0, params={"fv_margin": 0.02})
    assert mk2.price == 0.61                                       # max(ask - tick, f + margin = 0.57, bid + tick)
    (no,), _ = one(m, 0.30, 0.40, 0.42, tok=m.token_no)           # f is the token's own fair (YES f = 0.70)
    assert no.token_id == m.token_no and no.fair == pytest.approx(0.30)


# ---------- X3: never more than held, never rounded up, nothing below the minimum ----------

def test_x3_property_random_holdings():
    rnd = random.Random(5)
    k = RiskKernel(secret="", nonce_path=None)
    sold = refused = 0
    for _ in range(2000):
        m = mkt(min_size=rnd.choice((1.0, 5.0, 15.0)))
        pos = {m.token_yes: round(rnd.uniform(0, 40), rnd.choice((0, 2, 4)))}
        live = []
        for _ in range(rnd.randrange(3)):                         # in-flight SELL takers, some unknown
            sz = round(rnd.uniform(0.5, 15), 2)
            live.append(Order(f"o{len(live)}", Intent(L.NAME, m.cid, m.token_yes, "SELL", 0.5, sz, "taker", NOW + 2000,
                                                      0.5, "x", (), True), rnd.choice(("open", "unknown")),
                              round(rnd.uniform(0, sz), 2)))
        comp = Intent(L.NAME, m.cid, m.token_no, "BUY", 0.30, 10.0, "maker", NOW + 6 * MIN, 0.3, "complement", (), True)
        bid = round(rnd.uniform(0.3, 0.9), 2)
        bk = {m.token_yes: book(m.token_yes, bid, round(bid + 0.01, 2), rnd.choice((1.0, 4.99, 7.5, 100.0)))}
        avail = X.available(pos, live)
        fair = {m.cid: {"f": rnd.uniform(0.05, 0.6), "unc": 0.0, "tau_h": 6.0, "pull": None}}
        intents, rows = X.exit_intents(NOW, avail, {}, bk, fair, {m.cid: m})
        final = X.merge([comp], intents, rows, {m.cid: m})
        inflight = sum(o.intent.size - (0 if o.status == "unknown" else o.filled) for o in live)
        for i in intents:
            assert i.side == "SELL" and i.reduces_exposure
            assert i.size <= pos[m.token_yes] - inflight + 1e-9 and i.size <= avail[m.token_yes] + 1e-9
            assert abs(i.size * 100 - round(i.size * 100)) < 1e-6 and i.size >= m.min_size
            assert comp not in final                                # its complement BUY is withdrawn
            ctx = KernelContext(NOW, {m.cid: m}, bk, pos, live, {}, 50.0, FEEDS)
            assert k.reduces(i, m, ctx)                            # the kernel agrees it reduces exposure
        if not intents:
            assert all(r["action"] != "sell_taker" and r["action"] != "sell_maker" for r in rows)
        if avail.get(m.token_yes, 0) < m.min_size:
            assert not intents
        sold += len(intents)
        refused += any(r["action"] == "below_min" for r in rows)
    assert sold > 300 and refused > 100                            # both branches exercised, not vacuous


# ---------- X4: the real kernel approves exits in REDUCING ----------

def cleared(m, secret):
    rec = {"type": "clearance", "key": clearance_key(m), "signer": "t", "expiry_ms": E + H}
    return {key_id(rec["key"]): {**rec, "sig": sign(rec, secret)}}


def test_x4_kernel_approves_exit_sells_in_reducing():
    m = mkt()
    k = RiskKernel(secret="s3cret", nonce_path=None)
    k.trip("global", "drill", "breaker", TradingState.REDUCING)
    assert k.state == TradingState.REDUCING
    for bid_size in (100.0, 3.0):                                  # taker and maker exits
        (i,), _ = one(m, 0.30, 0.60, 0.62, bid_size=bid_size)
        bk = {m.token_yes: book(m.token_yes, 0.60, 0.62, bid_size), m.token_no: book(m.token_no, 0.38, 0.40)}
        ctx = KernelContext(NOW, {m.cid: m}, bk, {m.token_yes: 10.0}, [], cleared(m, "s3cret"), 50.0, FEEDS)
        d = k.check(i, ctx)
        assert d.approved and d.reason == "reduces exposure", d
        buy = dataclasses.replace(i, side="BUY", price=0.5, kind="maker", reduces_exposure=False,
                                  expiry_ms=NOW + 6 * MIN)
        assert not k.check(buy, ctx).approved                      # REDUCING still blocks new risk


# ---------- X5: no exit on stale books, before close or in the oracle gap ----------

def ladder_case(now=NOW, ts=None, gap=()):
    m = mkt(end=E)
    eng = L.LadderEngine(flags=("exits",))
    eng.oracle_gap = set(gap)
    ts = now if ts is None else ts
    bk = {m.token_yes: book(m.token_yes, 0.60, 0.62, ts=ts), m.token_no: book(m.token_no, 0.38, 0.40, ts=ts)}
    ref = {"BTC": {"price": 79_000.0, "ts_ms": now, "dvol": 50.0, "final": {}}}   # f well under 0.5
    eng.on_tick(now, {m.cid: m}, bk, ref, {m.token_yes: 10.0})
    return X.exit_intents(now, {m.token_yes: 10.0}, eng.cost, bk, eng.fair, {m.cid: m})


def test_x5_no_exit_on_stale_book_close_window_or_oracle_gap():
    intents, rows = ladder_case()
    assert intents and rows[0]["rule"] == "R1"                     # the control fires
    for case, why in ((dict(ts=NOW - 61_000), "stale_book"), (dict(now=E - 9 * MIN), "close"),
                      (dict(gap=("m",)), "oracle_gap")):
        intents, rows = ladder_case(**case)
        assert intents == [] and rows[0]["action"] == "skip" and rows[0]["reason"] == why, (case, rows)
    m = mkt()                                                       # a market the ladder has no fair value for
    assert X.exit_intents(NOW, {m.token_yes: 10.0}, {}, {}, {}, {m.cid: m}) == ([], [])


# ---------- loop: exits through the real kernel and paper router ----------

@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTER_HUMAN_KEY", D.KEY)
    for m in (D.LAD, D.SPD):
        D.sign_record(tmp_path / "advice.db", {"type": "clearance", "key": clearance_key(m), "signer": "test",
                                               "expiry_ms": D.T + 86_400_000}, D.KEY)
    return tmp_path


def seed_and_exit(env, reducing):
    T = D.T
    md, tr = D.boot(env, ("exits",))
    tr.now = lambda: T + 1000
    seed = Intent(L.NAME, "L1", "L1Y", "BUY", 0.52, 10.0, "taker", T + 3000, 0.5, "seed f=0.5 m=0.5 q=0.5")
    (d, _), = tr.submit([seed], T + 1000).values()
    assert d.approved
    md.book("L1Y", [(0.48, 100)], [(0.52, 100)], T + 1500)          # the taker arrives and fills
    assert tr.positions()["L1Y"] == 10.0
    if reducing:
        tr.kernel.trip("global", "drill", "breaker", TradingState.REDUCING)
    md.book("L1Y", [(0.60, 100)], [(0.62, 100)], T + 2000)          # market pays well over the model's ~0.49
    md.book("L1N", [(0.38, 100)], [(0.40, 100)], T + 2000)
    tr.now = lambda: T + 2100
    md.tick("BTC", 84_000.0, T + 2100)                              # ladder round -> exit SELL
    for now in (T + 2600, T + 3100):
        tr.now = lambda now=now: now
        tr.tick(now)
    out = tr.shutdown(T + 4000)
    return tr, out


@pytest.mark.parametrize("reducing", (False, True))
def test_loop_exit_sells_held_position_through_kernel(env, reducing):
    tr, out = seed_and_exit(env, reducing)
    rows = tr.ledger.as_of("exit_decisions", 2 ** 62)
    assert any(r["rule"] == "R1" and r["action"] == "sell_taker" for r in rows)
    sells = [f for f in tr.router.state.fills if f.side == "SELL"]
    assert sells and sells[0].price == 0.60 and sum(f.size for f in sells) == 10.0
    assert tr.positions().get("L1Y", 0.0) == 0.0
    assert out["violations"] == 0 and out["mismatches"] == []
    assert out["counts"]["decision:ladder-maker:approved"] >= 2


def test_loop_flags_off_has_no_exit_wiring(env):
    _, tr = D.boot(env)
    assert not hasattr(tr, "exits") and tr.ladder.fair == {}
