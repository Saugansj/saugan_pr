"""WP2-C tests (C1-C10): worst-case positions, cross-instant stress cap, resolution-risk cap, 7-day drawdown breaker,
pull / REDUCING rules, entry-gate regression through the real RiskKernel, check_live order. No network."""
import dataclasses
import json
import math
import pathlib
import re
import socket

import pytest

from trader.contracts import Book, Decision, Fill, Intent, KernelContext, MarketInfo, Order, TradingState
from trader.kernel import PRIVILEGED, RiskKernel, clearance_key, key_id, sign
from trader.live import risk
from trader.live.risk import (SevenDayDrawdown, check_live, pull_ids, reducing_rule, resolution_check, stress_check,
                              stress_loss, worst_case_positions)
from trader.router import replay

A, R, H = TradingState.ACTIVE, TradingState.REDUCING, TradingState.HALTED
ROOT = pathlib.Path(__file__).resolve().parents[2]
NOW = 1_790_000_000_000
MIN, HOUR, DAY = 60_000, 3_600_000, 86_400_000
KEY = "test-human-key"
NAN = float("nan")
_connect = socket.socket.connect


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def connect(self, addr):
        if addr[0] not in ("127.0.0.1", "::1", "localhost"):
            raise RuntimeError(f"network disabled in unit tests ({addr[0]})")
        return _connect(self, addr)
    monkeypatch.setattr(socket.socket, "connect", connect)


def mk(cid, asset="BTC", strike=100_000.0, kind="strike", mode="crypto-term", end=NOW + 10 * HOUR, group=None):
    return MarketInfo(cid, f"{cid}-y", f"{cid}-n", mode, f"{asset} {kind} {strike}", "r" * 64, 0.01, 5, 0.07, False,
                      end, group or f"{asset}@{end}", asset, strike, kind,
                      f"binance:{asset}/USDT" if asset else "sportsdata")


BTC, ETH, SOL = mk("btc"), mk("eth", "ETH", 4_000.0), mk("sol", "SOL", 200.0)
UPDN = mk("ud", kind="updown", strike=None)
SPORT = mk("sp", asset=None, strike=None, kind="", mode="sports-pregame")
MARKETS = {m.cid: m for m in (BTC, ETH, SOL, UPDN, SPORT)}
REF = {"BTC": {"price": 100_000.0, "dvol": 50.0}, "ETH": {"price": 4_000.0, "dvol": 60.0},
       "SOL": {"price": 200.0, "dvol": 80.0}}
OPENS = {"ud": 100_500.0}


def intent(m=BTC, token=None, side="BUY", size=10.0, price=0.5, kind="maker", fair=0.5, strategy="ladder-maker"):
    return Intent(strategy, m.cid, token or m.token_yes, side, price, size, kind, NOW + HOUR, fair, "t")


def order(oid, status, side="BUY", size=10.0, filled=0.0, m=BTC, token=None):
    return Order(oid, intent(m, token, side, size), status, filled)


# ---- C1 worst-case positions -----------------------------------------------------------------------------------------
@pytest.mark.parametrize("status, side, filled, adds", [
    ("journaled", "BUY", 0, 10), ("open", "BUY", 0, 10), ("partial", "BUY", 4, 6), ("unknown", "BUY", 4, 10),
    ("filled", "BUY", 10, 0), ("cancelled", "BUY", 3, 0), ("expired", "BUY", 0, 0), ("rejected", "BUY", 0, 0),
    ("open", "SELL", 0, 0), ("unknown", "SELL", 0, 0), ("partial", "SELL", 2, 0)])
def test_c1_status_table(status, side, filled, adds):
    got = worst_case_positions({"btc-y": 5.0}, [order("o", status, side, 10.0, filled)])
    assert got == {"btc-y": 5.0 + adds}


def test_c1_replayed_journal(tmp_path):
    path, lines = tmp_path / "journal.jsonl", []

    def new(oid, side="BUY", size=10.0):
        lines.append({"op": "new", "id": oid, "ts": NOW, "intent": dataclasses.asdict(intent(side=side, size=size))})

    def fill(oid, size):
        f = Fill(oid, "ladder-maker", "btc", "btc-y", "BUY", 0.5, size, NOW, True, 0.0)
        lines.append({"op": "fill", "id": oid, "fill": dataclasses.asdict(f)})

    def op(oid, name):
        lines.append({"op": name, "id": oid, "ts": NOW})
    new("j")                                               # journaled, never acked: +10
    new("o"), op("o", "ack")                               # open: +10
    new("p"), op("p", "ack"), fill("p", 4)                 # partial: position +4, worst +6
    new("u"), op("u", "ack"), fill("u", 3), op("u", "unknown")  # unknown: position +3, worst +10 (full size)
    new("f"), op("f", "ack"), fill("f", 10)                # filled: position +10
    new("c"), op("c", "ack"), op("c", "cancel")            # cancelled
    new("e"), op("e", "ack"), op("e", "expire")            # expired
    new("s", "SELL", 5), op("s", "ack")                    # a resting SELL never subtracts
    path.write_text("".join(json.dumps(e) + "\n" for e in lines) + '{"op": "new", "id": "torn', encoding="utf-8")
    st = replay(path)
    assert st.positions == {"btc-y": 17.0}
    assert {o.order_id: o.status for o in st.orders.values()} == {
        "j": "journaled", "o": "open", "p": "partial", "u": "unknown", "f": "filled", "c": "cancelled",
        "e": "expired", "s": "open"}
    assert worst_case_positions(st.positions, st.orders) == {"btc-y": 17.0 + 10 + 10 + 6 + 10}
    assert worst_case_positions(st.positions, list(st.orders.values())) == {"btc-y": 53.0}


# ---- C2 stress scenarios ---------------------------------------------------------------------------------------------
def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def hand_digital(S, K, sigma, tau_h):
    s = sigma * math.sqrt(tau_h / 8760)
    return phi((math.log(S / K) - s * s / 2) / s)


def test_c2_scenarios_are_four_shocks_vol_up_on_three_assets():
    assert risk.SHOCKS == (-0.10, -0.05, 0.05, 0.10) and risk.VOL_UP == 1.5 and risk.ASSETS == ("BTC", "ETH", "SOL")
    # all three assets move together: the joint worst loss is the sum of each asset's own -10% loss
    each = [stress_loss({m.token_yes: 10.0}, MARKETS, REF, OPENS, NOW, set()) for m in (BTC, ETH, SOL)]
    joint = stress_loss({m.token_yes: 10.0 for m in (BTC, ETH, SOL)}, MARKETS, REF, OPENS, NOW, set())
    assert all(s.startswith("-10%") for _, s in each) and joint[1].startswith("-10%")
    assert joint[0] == pytest.approx(sum(x for x, _ in each), abs=1e-12)


def test_c2_strike_repricing_matches_hand_computation():
    loss, scen = stress_loss({"btc-y": 7.0}, MARKETS, REF, OPENS, NOW, set())
    p0 = hand_digital(100_000, 100_000, 0.50, 10)
    p1 = hand_digital(90_000, 100_000, 0.75, 10)
    assert scen == "-10% BTC/ETH/SOL, vol x1.5"
    assert abs(loss - 7.0 * (p0 - p1)) < 1e-9
    # Up/Down prices against the open; NO = 1 - YES
    loss, scen = stress_loss({"ud-n": 3.0}, MARKETS, REF, OPENS, NOW, set())
    q0, q1 = hand_digital(100_000, 100_500, 0.50, 10), hand_digital(110_000, 100_500, 0.75, 10)
    assert scen.startswith("+10%") and abs(loss - 3.0 * ((1 - q0) - (1 - q1))) < 1e-9


def test_c2_worst_scenario_by_side():
    yes = {m.token_yes: 10.0 for m in (BTC, ETH, SOL)}
    no = {m.token_no: 10.0 for m in (BTC, ETH, SOL)}
    assert stress_loss(yes, MARKETS, REF, OPENS, NOW, set())[1].startswith("-10%")
    assert stress_loss(no, MARKETS, REF, OPENS, NOW, set())[1].startswith("+10%")


# ---- C3 stress_check -------------------------------------------------------------------------------------------------
def per_share_loss(token="btc-y"):
    return stress_loss({token: 1.0}, MARKETS, REF, OPENS, NOW, set())[0]


def sc(i, wp, bankroll=50.0, ref=REF, opens=OPENS, printed=frozenset(), markets=MARKETS):
    return stress_check(i, wp, markets, ref, opens, NOW, printed, bankroll)


def test_c3_threshold_and_binding_cap():
    n = 0.05 * 50.0 / per_share_loss()                      # shares whose worst loss is exactly 5% of 50
    ok, bad = sc(intent(size=n * 0.99), {}), sc(intent(size=n * 1.01), {})
    assert ok.approved and ok.binding_cap == "stress"
    assert not bad.approved and bad.binding_cap == "stress" and "-10%" in bad.reason
    assert sc(intent(side="SELL", size=1e6), {}).approved  # a SELL adds nothing to the worst case


def test_c3_unknown_buy_turns_approval_into_rejection():
    n = 0.05 * 50.0 / per_share_loss()
    i = intent(size=n * 0.5)
    assert sc(i, worst_case_positions({}, [order("x", "cancelled", size=n * 0.6)])).approved
    d = sc(i, worst_case_positions({}, [order("x", "unknown", size=n * 0.6, filled=n * 0.6)]))
    assert not d.approved and d.binding_cap == "stress"


def test_c3_unpriceable_counts_as_total_loss():
    no_strike = dataclasses.replace(BTC, strike=None)
    cases = [({**MARKETS, "btc": no_strike}, REF, OPENS, "btc-y"),          # missing strike
             (MARKETS, REF, {}, "ud-y"),                                    # missing Up/Down open
             (MARKETS, {**REF, "BTC": {"price": 100_000.0, "dvol": None}}, OPENS, "btc-y"),  # missing sigma
             (MARKETS, {}, OPENS, "btc-y"),                                 # missing ref
             ({**MARKETS, "btc": dataclasses.replace(BTC, end_ms=NOW)}, REF, OPENS, "btc-y"),  # tau <= 0
             ({**MARKETS, "btc": dataclasses.replace(BTC, asset="XRP")}, {**REF, "XRP": REF["BTC"]}, OPENS, "btc-y")]
    for markets, ref, opens, tok in cases:
        assert stress_loss({tok: 4.0}, markets, ref, opens, NOW, set())[0] == 4.0
        assert not stress_check(intent(size=0.01), {tok: 4.0}, markets, ref, opens, NOW, set(), 50.0).approved


def test_c3_nan_rejects():
    assert not sc(intent(size=1.0), {}, bankroll=NAN).approved
    assert not sc(intent(size=1.0), {}, ref={**REF, "BTC": {"price": NAN, "dvol": 50.0}}).approved
    assert not sc(intent(size=1.0), {}, ref={**REF, "BTC": {"price": 100_000.0, "dvol": NAN}}).approved
    assert not sc(intent(size=1.0, price=NAN), {}).approved
    assert not sc(intent(size=1.0), {"eth-y": NAN}).approved


def test_c3_printed_and_non_crypto_excluded():
    big = {"btc-y": 1e6, "sp-y": 1e6}
    assert stress_loss(big, MARKETS, REF, OPENS, NOW, {"btc"})[0] == 0.0
    assert sc(intent(SPORT, size=1e6), big, printed={"btc"}).approved
    assert not sc(intent(SPORT, size=1.0), big).approved     # not printed: BTC counts again


# ---- C4 resolution-risk cap ------------------------------------------------------------------------------------------
P1, P2, P3 = (mk(c, end=NOW - 10 * MIN) for c in ("p1", "p2", "p3"))
RMARKETS = {m.cid: m for m in (P1, P2, P3, BTC)}
BOOKS = {t: Book(t, [(0.95, 100)], [(0.97, 100)], NOW) for m in (P1, P2, P3) for t in (m.token_yes, m.token_no)}
PRINTED = {"p1", "p2", "p3"}


def rc(i, wp, bankroll=100.0, books=BOOKS, printed=PRINTED):
    return resolution_check(i, wp, RMARKETS, books, bankroll, printed)


def test_c4_per_market_bound():
    assert rc(intent(P1, price=0.96, size=10.0), {}).approved           # 9.50 <= 10
    d = rc(intent(P1, price=0.96, size=11.0), {})                       # 10.45 > 10
    assert not d.approved and d.binding_cap == "resolution:p1"
    d = rc(intent(P1, price=0.96, size=5.0), {"p1-n": 6.0})             # a held position counts (11 x 0.95)
    assert not d.approved and d.binding_cap == "resolution:p1"


def test_c4_total_bound():
    held = {"p1-y": 9.0, "p2-y": 9.0, "p3-n": 2.0}                      # 17.10 + 1.90 = 19.00
    assert rc(intent(P3, price=0.96, size=1.0), held).approved          # 19.95 <= 20
    d = rc(intent(P3, price=0.96, size=2.0), held)                      # 20.90 > 20, p3 itself 3.80 <= 10
    assert not d.approved and d.binding_cap == "resolution:total"


def test_c4_unknown_orders_and_no_bid_count():
    wp = worst_case_positions({}, [order("u", "unknown", size=6.0, filled=6.0, m=P1)])
    assert not rc(intent(P1, price=0.96, size=5.0), wp).approved        # (6 + 5) x 0.95 > 10
    assert rc(intent(P1, price=0.96, size=5.0), {}).approved
    no_bid = {**BOOKS, "p1-y": Book("p1-y", [], [(0.99, 5)], NOW)}
    assert not rc(intent(P1, price=0.96, size=10.5), {}, books=no_bid).approved  # no bid -> 1.0 per share


def test_c4_unprinted_markets_unaffected():
    over = {"p1-y": 100.0, "p2-y": 100.0}
    d = rc(intent(BTC, size=1e6), over)
    assert d.approved and d.binding_cap is None


def test_c4_nan_rejects():
    assert not rc(intent(P1, size=1.0), {}, bankroll=NAN).approved
    assert not rc(intent(P1, size=1.0), {}, books={**BOOKS, "p2-n": Book("p2-n", [(NAN, 5)], [], NOW)}).approved
    assert not rc(intent(P1, size=NAN), {}).approved


# ---- C5 7-day drawdown breaker ---------------------------------------------------------------------------------------
def reset_token(nonce, scope="global"):
    t = {"type": "reset", "scope": scope, "signer": "me", "nonce": nonce, "expiry_ms": NOW + 30 * DAY,
         "signed_ms": NOW}
    t["sig"] = sign(t, KEY)
    return t


@pytest.fixture
def k(tmp_path):
    return RiskKernel(secret=KEY, nonce_path=tmp_path / "nonces.txt")


def test_c5_trips_on_11pct_within_7_days(k):
    b = SevenDayDrawdown(k)
    for day, eq in enumerate((100.0, 104.0, 100.0, 95.0)):
        b.on_equity(eq, NOW + day * DAY)
    assert k.state == A
    b.on_equity(92.5, NOW + 6 * DAY)                    # 104 -> 92.5 = 11.06%
    assert k.state == R and len(k.trips) == 1
    t = k.trips[0]
    assert t["scope"] == "global" and t["level"] == "REDUCING" and t["source"] == "breaker:drawdown7d"
    assert t["source"].split(":")[0] in PRIVILEGED


def test_c5_exactly_10pct_and_old_high_do_not_trip(k):
    b = SevenDayDrawdown(k)
    b.on_equity(100.0, NOW)
    b.on_equity(90.0, NOW + DAY)                        # exactly 10%
    assert k.trips == []
    b = SevenDayDrawdown(k)
    b.on_equity(100.0, NOW)
    b.on_equity(99.0, NOW + 2 * DAY)
    b.on_equity(89.0, NOW + 7 * DAY + 1)                # 11% below a high now older than 7 days; 10.1% below 99
    assert k.trips and k.trips[-1]["reason"].startswith("7-day drawdown 10.1%")
    k2 = RiskKernel(secret=KEY, nonce_path=None)
    b = SevenDayDrawdown(k2)
    b.on_equity(100.0, NOW)
    b.on_equity(89.0, NOW + 7 * DAY + 1)
    assert k2.trips == []
    b.on_equity(NAN, NOW + 8 * DAY)                     # a bad mark is skipped, it doesn't blind the window
    b.on_equity(80.0, NOW + 8 * DAY + 1)
    assert k2.state == R


def test_c5_reset_rearms_and_nonce_reuse_refused(k):
    b = SevenDayDrawdown(k)
    b.on_equity(100.0, NOW)
    b.on_equity(89.0, NOW + HOUR)
    assert k.state == R
    assert k.reset("global", reset_token("n-1"), NOW + 2 * HOUR).approved
    assert k.state == A
    b.on_equity(89.0, NOW + 3 * HOUR)                   # the same loss doesn't trip again
    b.on_equity(85.0, NOW + 4 * HOUR)                   # 4.5% below the trip equity
    assert k.state == A and len([t for t in k.trips if t["level"] == "REDUCING"]) == 1
    b.on_equity(80.0, NOW + 5 * HOUR)                   # 10.1% below 89
    assert k.state == R
    d = k.reset("global", reset_token("n-1"), NOW + 6 * HOUR)
    assert not d.approved and "nonce already used" in d.reason and k.state == R
    assert k.reset("global", reset_token("n-2"), NOW + 6 * HOUR).approved


def test_c5_rebuild_from_samples_gives_same_decisions():
    stream = [(100 + 10 * math.sin(i / 3) - i * 0.4, NOW + i * 6 * HOUR) for i in range(80)]
    k1 = RiskKernel(secret=KEY, nonce_path=None)
    b1 = SevenDayDrawdown(k1)
    for eq, ts in stream[:40]:
        b1.on_equity(eq, ts)
    saved = json.loads(json.dumps(b1.samples()))       # as persisted under data/trader/
    k2 = RiskKernel(secret=KEY, nonce_path=None)
    b2 = SevenDayDrawdown(k2, samples=saved)
    n1 = len(k1.trips)
    for eq, ts in stream[40:]:
        b1.on_equity(eq, ts)
        b2.on_equity(eq, ts)
        assert b1.samples() == b2.samples()
    assert k1.trips[n1:] == k2.trips and k2.trips      # the second half trips, identically
    assert len(b1.samples()) < 40                      # only samples that can still be the max are kept


# ---- C6 pull_ids and reducing_rule -----------------------------------------------------------------------------------
def test_c6_pull_ids_exactly_risk_increasing():
    pos = {"btc-n": 10.0}
    orders = [order("uncovered", "open", m=ETH),                                   # BUY with nothing held
              order("covered", "open", size=5.0),                                  # complement YES BUY vs 10 NO
              order("sell", "open", side="SELL", size=3.0, token="btc-n"),         # SELL of held NO
              order("dead", "cancelled", m=ETH),
              order("unk", "unknown", m=SOL),
              order("elsewhere", "open", m=UPDN)]
    assert pull_ids(orders, pos, MARKETS, {"btc", "eth", "sol"}) == ["uncovered", "unk"]
    over = orders + [order("covered2", "open", size=4.0)]                          # 5 + 4 + SELL 3 > 10 held
    assert set(pull_ids(over, pos, MARKETS, {"btc"})) == {"covered", "covered2"}
    assert pull_ids([order("x", "open", m=BTC)], {}, {}, {"btc"}) == ["x"]         # unknown market: pulled


def test_c6_reducing_rule():
    taker = intent(side="SELL", kind="taker", price=0.40, fair=0.50)
    assert "human token" in reducing_rule(taker, 0.07, group_over_cap=False, human_token_ok=False)
    assert reducing_rule(taker, 0.07, group_over_cap=True, human_token_ok=False) is None
    assert reducing_rule(taker, 0.07, group_over_cap=False, human_token_ok=True) is None
    f = 0.07 * 0.48 * 0.52                                             # fee per share at 0.48
    assert reducing_rule(intent(side="SELL", price=0.48, fair=0.48 + f - 1e-6), 0.07, False, False) is None
    assert "below fair - fee" in reducing_rule(intent(side="SELL", price=0.48, fair=0.48 + f + 1e-4), 0.07, False,
                                               False)
    assert reducing_rule(intent(price=0.48, fair=0.48 - f + 1e-6), 0.07, False, False) is None
    assert "above fair + fee" in reducing_rule(intent(price=0.48, fair=0.48 - f - 1e-4), 0.07, False, False)
    assert reducing_rule(intent(side="SELL", price=NAN), 0.07, False, False)          # NaN refuses
    assert reducing_rule(intent(side="SELL", price=0.5, fair=NAN), 0.07, False, False)


# ---- C7 entry-gate regression through trader.kernel.RiskKernel -------------------------------------------------------
FEEDS = {"polymarket": 100, "binance:BTC": 100, "binance:ETH": 100, "dvol:BTC": 1000, "dvol:ETH": 1000,
         "basis:USDT": 1000}


def kctx(positions=None, orders=(), bankroll=50.0, markets=MARKETS, books=None):
    clear = {}
    for m in (BTC, ETH):
        rec = {"type": "clearance", "key": clearance_key(m), "signer": "me", "nonce": "n-" + m.cid,
               "expiry_ms": NOW + DAY, "signed_ms": NOW}
        rec["sig"] = sign(rec, KEY)
        clear[key_id(rec["key"])] = rec
    books = books if books is not None else {t: Book(t, [(0.50, 100)], [(0.52, 100)], NOW)
                                             for m in markets.values() for t in (m.token_yes, m.token_no)}
    return KernelContext(NOW, markets, books, positions or {}, list(orders), clear, bankroll, FEEDS)


def test_c7_entry_gate_regression(k):
    c = kctx(positions={"btc-y": 10.0})
    assert k.check(intent(), c).approved and k.check(intent(ETH), c).approved
    k.trip("global", "dd7", "breaker:drawdown7d", R)
    assert k.check(intent(), c).reason.startswith("REDUCING")                 # risk-increasing rejected
    assert k.check(intent(side="SELL", size=5.0), c) == Decision(True, "reduces exposure")
    assert k.check(intent(token="btc-n", size=5.0), c).approved              # covered complement BUY


def test_c7_market_lock_is_scoped(k):
    c = kctx()
    k.trip("btc", "lock", "breaker:settlement", R)
    assert k.check(intent(), c).reason.startswith("REDUCING")
    assert k.check(intent(ETH), c).approved


def test_c7_halted_rejects_all_and_ai_capped(k):
    c = kctx(positions={"btc-y": 10.0})
    k.trip("global", "ai wants a halt", "advisor:27")                         # default level HALTED, capped
    assert k.state == R and k.check(intent(side="SELL", size=5.0), c).approved
    k.trip("global", "manual", "human")
    assert k.state == H
    assert not k.check(intent(side="SELL", size=5.0), c).approved and not k.check(intent(), c).approved


# ---- C8 check_live ---------------------------------------------------------------------------------------------------
LMARKETS = {m.cid: m for m in (BTC, ETH, P1)}
LBOOKS = {**BOOKS, **{t: Book(t, [(0.50, 100)], [(0.52, 100)], NOW) for m in (BTC, ETH) for t in (m.token_yes,
                                                                                               m.token_no)}}


def cl(i, positions=None, orders=(), bankroll=50.0):
    c = kctx(positions, orders, bankroll, LMARKETS, LBOOKS)
    return check_live(i, c, worst_case_positions(c.positions, c.open_orders), REF, OPENS, {"p1"})


def test_c8_order_binding_cap_and_reducing():
    big_btc = {"btc-y": 200.0}                                                # stress fails on its own
    d = cl(intent(P1, price=0.96, size=50.0), big_btc)                        # both caps would fail
    assert not d.approved and d.binding_cap == "stress"
    d = cl(intent(P1, price=0.96, size=50.0))                                 # stress passes, resolution fails
    assert not d.approved and d.binding_cap == "resolution:p1"
    d = cl(intent(P1, price=0.96, size=1.0))                                  # rooms: stress 2.50, p1 4.05
    assert d.approved and d.binding_cap == "stress"
    d = cl(intent(P1, price=0.96, size=5.0))                                  # p1 room 0.25 is tighter
    assert d.approved and d.binding_cap == "resolution:p1"
    d = cl(intent(BTC, size=2.0), {})                                         # unprinted: stress only
    assert d.approved and d.binding_cap == "stress"
    assert cl(intent(BTC, size=10.0), {}).binding_cap == "stress"             # 10 x ~0.50 > 2.50
    assert cl(intent(side="SELL", size=100.0), big_btc) == Decision(True, "reduces exposure")
    assert cl(intent(token="btc-n", size=150.0), big_btc) == Decision(True, "reduces exposure")
    # an unknown complement BUY already uses the holding: the same intent is now new risk, and stress rejects it
    d = cl(intent(token="btc-n", size=150.0), big_btc, [order("u", "unknown", size=100.0, token="btc-n")])
    assert not d.approved and d.binding_cap == "stress"


# ---- C9 no I/O -------------------------------------------------------------------------------------------------------
def test_c9_risk_does_no_io():
    src = (ROOT / "trader" / "live" / "risk.py").read_text(encoding="utf-8")
    assert not re.search(r"open\(|socket|urllib|httpx|sqlite3|requests", src)
    assert "trader.loop" not in src
