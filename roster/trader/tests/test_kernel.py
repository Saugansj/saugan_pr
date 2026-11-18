"""WP1-B tests: kernel states, caps, clearances, provenance, GTD rule, 1.1x refusal, breakers, clearance CLI (B1-B8)."""
import dataclasses
import json
import os
import sqlite3
import subprocess
import sys

import pytest

from common import ROOT
from tools import clearance_cli
from trader.breakers import Breakers
from trader.contracts import Book, Fill, Intent, KernelContext, MarketInfo, Order, TradingState
from trader.kernel import RiskKernel, bankroll, clearance_key, key_id, load_advice, sign

KEY = "test-human-key"
NOW = 1_790_000_000_000
MIN = 60_000
FAST = MarketInfo(cid="c-fast", token_yes="fy", token_no="fn", mode="crypto-fast", question="BTC Up or Down 5m",
                  rules_sha256="r" * 64, tick_size=0.01, min_size=5, fee_rate=0.07, neg_risk=False,
                  end_ms=NOW + 4 * MIN, event_group="BTC-5m@x", asset="BTC", kind="updown", source_id="chainlink:BTC/USD")
TERM = MarketInfo(cid="c-term", token_yes="ty", token_no="tn", mode="crypto-term", question="BTC above 74k Oct 2",
                  rules_sha256="s" * 64, tick_size=0.001, min_size=5, fee_rate=0.07, neg_risk=False,
                  end_ms=NOW + 20 * 60 * MIN, event_group="BTC@2026-10-02T16:00Z", asset="BTC", kind="strike",
                  strike=74000.0, source_id="binance:BTC/USDT")
FEEDS = {"polymarket": 100, "binance:BTC": 100, "dvol:BTC": 1000, "basis:USDT": 1000}


def clr(m, expiry=NOW + 86_400_000, **change):
    rec = {"type": "clearance", "key": {**clearance_key(m), **change}, "signer": "me", "nonce": "n-" + m.cid,
           "expiry_ms": expiry, "signed_ms": NOW}
    rec["sig"] = sign(rec, KEY)
    return {key_id(rec["key"]): rec}


def ctx(markets=(FAST, TERM), clearances=None, positions=None, orders=(), bankroll_usd=50.0, feeds=None, books=None):
    if clearances is None:
        clearances = {k: v for m in markets for k, v in clr(m).items()}
    return KernelContext(now_ms=NOW, markets={m.cid: m for m in markets},
                         books=books if books is not None else {t: Book(t, [(0.50, 100)], [(0.52, 100)], NOW)
                                                                 for m in markets for t in (m.token_yes, m.token_no)},
                         positions=positions or {}, open_orders=list(orders), clearances=clearances,
                         bankroll_usd=bankroll_usd, feed_age_ms=FEEDS if feeds is None else feeds)


def buy(m=FAST, token=None, size=5.0, price=0.5, kind="taker", expiry=None, side="BUY", strategy=None, **kw):
    strategy = strategy or ("btc-speed" if m.mode == "crypto-fast" else "ladder-maker")
    expiry = expiry or (NOW + 5_000 if kind == "taker" else NOW + 60 * MIN)
    return Intent(strategy=strategy, cid=m.cid, token_id=token or m.token_yes, side=side, price=price, size=size,
                  kind=kind, expiry_ms=expiry, fair=0.6, reason="t", **kw)


@pytest.fixture
def k(tmp_path):
    return RiskKernel(secret=KEY, nonce_path=tmp_path / "nonces.txt")


def token(scope="global", nonce="abc", expiry=NOW + MIN, typ="reset", key=KEY):
    t = {"type": typ, "scope": scope, "signer": "me", "nonce": nonce, "expiry_ms": expiry, "signed_ms": NOW}
    t["sig"] = sign(t, key)
    return t


# ---- B1 states ------------------------------------------------------------------------------------------------------
def test_b1_states(k):
    c = ctx(positions={"fy": 10.0})
    assert k.check(buy(), c).approved
    k.trip("global", "dd", "breaker:drawdown", TradingState.REDUCING)
    d = k.check(buy(), c)
    assert not d.approved and "REDUCING" in d.reason                     # risk-increasing rejected
    assert k.check(buy(side="SELL", size=5), c).approved                 # selling held shares accepted
    assert k.check(buy(token="fn", size=5), c).approved                  # buying the complement of held shares accepted
    assert not k.check(buy(token="fn", size=11), c).approved             # more complement than held = new risk
    assert not k.check(buy(reduces_exposure=True), c).approved           # the engine's flag is not trusted
    k.trip("global", "manual", "human")
    assert k.state == TradingState.HALTED
    assert "HALTED" in k.check(buy(side="SELL", size=5), c).reason       # HALTED rejects everything


def test_b1_ai_trips_capped_at_reducing(k):
    for src in ("ai:25", "advisor:27", "something-unknown"):
        k.trip("global", "ai says stop", src)                           # default level is HALTED
        assert k.state == TradingState.REDUCING
    k.trip("global", "x", "kernel", TradingState.ACTIVE)                 # a trip never lowers a state
    assert k.state == TradingState.REDUCING


def test_b1_reducing_nets_live_orders_on_both_routes(k):
    k.trip("global", "dd", "breaker:drawdown", TradingState.REDUCING)
    c = ctx(positions={"fy": 10.0}, orders=[Order("s1", buy(side="SELL", size=10), "open")])
    assert "REDUCING" in k.check(buy(token="fn", size=10), c).reason     # the live SELL already uses all 10 YES
    assert "REDUCING" in k.check(buy(side="SELL", size=1), c).reason
    c = ctx(positions={"fy": 10.0}, orders=[Order("b1", buy(token="fn", size=10), "open")])
    assert "REDUCING" in k.check(buy(side="SELL", size=10), c).reason    # the reverse order: live complement BUY
    c = ctx(positions={"fy": 10.0}, orders=[Order("b1", buy(token="fn", size=10), "partial", filled=4.0)])
    assert k.check(buy(side="SELL", size=4), c).approved                 # 6 still live, 4 free
    c = ctx(positions={"fy": 10.0}, orders=[Order("b1", buy(token="fn", size=10), "unknown", filled=4.0)])
    assert not k.check(buy(side="SELL", size=1), c).approved             # unknown counts in full
    c = ctx(positions={"fy": 10.0}, orders=[Order("b1", buy(token="fn", size=10), "cancelled")])
    assert k.check(buy(side="SELL", size=10), c).approved                # dead orders don't count


def test_b1_market_lock_is_scoped(k):
    k.trip("c-fast", "markout", "breaker:markout", TradingState.REDUCING)
    c = ctx()
    assert "REDUCING" in k.check(buy(FAST), c).reason
    assert k.check(buy(TERM, kind="maker"), c).approved
    k.trip(TERM.event_group, "group", "breaker:x", TradingState.REDUCING)  # an event-group trip blocks that group
    assert "REDUCING" in k.check(buy(TERM, kind="maker"), c).reason


def test_strategy_outside_its_modes_rejected(k):
    hourly = dataclasses.replace(FAST, cid="c-h", token_yes="hy", token_no="hn", mode="crypto-hourly")
    assert "does not trade mode" in k.check(buy(hourly, strategy="btc-speed"), ctx(markets=(hourly,))).reason


def test_nan_inputs_fail_closed(k):
    c = ctx(positions={"ty": 1.0})
    c.books["ty"] = Book("ty", [(float("nan"), 9)], [(0.52, 9)], NOW)
    assert not k.check(buy(TERM, kind="maker", size=5), c).approved      # NaN room
    assert not k.check(buy(), ctx(bankroll_usd=float("nan"))).approved


def test_exposure_marks_and_ignores_sell_orders():
    c = ctx(positions={"ty": 10.0}, orders=[Order("s", buy(TERM, side="SELL", size=10), "open")])
    grp = lambda mk: mk.event_group == TERM.event_group                   # noqa: E731
    assert RiskKernel.exposure(c, grp) == pytest.approx(5.0)              # 10 at bid 0.50; the live SELL adds nothing
    c.books["ty"] = Book("ty", [], [(0.9, 100)], NOW)
    assert RiskKernel.exposure(c, grp) == pytest.approx(10.0)             # empty bid side counts like no book: 1.0


def test_sell_without_shares_and_bad_input_rejected(k):
    c = ctx()
    assert "sell exceeds" in k.check(buy(side="SELL"), c).reason
    assert "bad price/size" in k.check(buy(size=-5), c).reason          # negative size can't slip under a cap
    assert "unknown strategy" in k.check(buy(strategy="other"), c).reason


# ---- B2 caps ----------------------------------------------------------------------------------------------------------
def test_b2_group_cap_binds(k):
    c = ctx(positions={"ty": 18.0})                                      # 18 x bid 0.50 = 9.00 of the 10.00 group cap
    d = k.check(buy(TERM, kind="maker", size=5, price=0.5), c)
    assert not d.approved and d.binding_cap == "group:BTC@2026-10-02T16:00Z"
    ok = k.check(buy(TERM, kind="maker", size=2, price=0.5), c)
    assert ok.approved and ok.binding_cap == "group:BTC@2026-10-02T16:00Z"   # approved decisions name the tightest cap


def test_b2_strategy_budget_binds_and_unknown_orders_count_full(k):
    other = dataclasses.replace(FAST, cid="c-fast2", token_yes="gy", token_no="gn", event_group="BTC-15m@y")
    orders = [Order("o1", buy(other, size=40, price=0.55), "unknown", filled=10.0)]   # unknown -> all 40 count: 22.00
    c = ctx(markets=(FAST, other, TERM), orders=orders)
    d = k.check(buy(FAST, size=10, price=0.5), c)                        # 5.00 more > 25 - 22 = 3.00 room
    assert not d.approved and d.binding_cap == "strategy:btc-speed"
    assert k.check(buy(TERM, kind="maker", size=5), c).approved          # the other strategy's budget is separate


# ---- B3 clearances ----------------------------------------------------------------------------------------------------
def test_b3_clearance(k):
    assert k.check(buy(), ctx()).approved
    for field, new in (("rules_sha256", "x" * 64), ("tick_size", 0.001), ("fee_rate", 0.05)):
        c = ctx(markets=(dataclasses.replace(FAST, **{field: new}),), clearances=clr(FAST))
        d = k.check(buy(), c)
        assert not d.approved and f"{field} changed" in d.reason
    assert "no clearance" in k.check(buy(), ctx(clearances={})).reason
    assert "expired" in k.check(buy(), ctx(markets=(FAST,), clearances=clr(FAST, expiry=NOW - 1))).reason
    forged = clr(FAST)
    next(iter(forged.values()))["expiry_ms"] += 1                        # edited after signing
    assert "signature invalid" in k.check(buy(), ctx(markets=(FAST,), clearances=forged)).reason
    assert "signature invalid" in RiskKernel(secret="", nonce_path=None).check(buy(), ctx()).reason  # no key: fail closed
    fine = dataclasses.replace(FAST, tick_size=0.001)
    misfiled = {key_id(clearance_key(fine)): next(iter(clr(FAST).values()))}   # 0.01-tick record under the 0.001 id
    assert "different key" in k.check(buy(fine), ctx(markets=(fine,), clearances=misfiled)).reason
    as_float = dataclasses.replace(FAST, min_size=5.0)                   # crawler typing 5 vs 5.0 keeps the clearance
    assert key_id(clearance_key(as_float)) == key_id(clearance_key(FAST))
    assert k.check(buy(as_float), ctx(markets=(as_float,), clearances=clr(FAST))).approved


def test_uncleared_keys_are_collected_for_signing(k, tmp_path):
    k.check(buy(), ctx(clearances={}))
    k.dump_uncleared(tmp_path / "u.jsonl")
    row = json.loads((tmp_path / "u.jsonl").read_text())
    assert row["key"] == clearance_key(FAST) and row["cid"] == "c-fast"


# ---- B4 provenance ----------------------------------------------------------------------------------------------------
def test_b4_provenance(k):
    wrong = dataclasses.replace(FAST, source_id="binance:BTC/USDT")
    assert "provenance: market source" in k.check(buy(wrong), ctx(markets=(wrong,))).reason
    blank = dataclasses.replace(FAST, source_id="")
    assert "provenance: market source" in k.check(buy(blank), ctx(markets=(blank,))).reason
    assert "feed binance:BTC stale" in k.check(buy(), ctx(feeds={**FEEDS, "binance:BTC": 6_000})).reason
    assert "feed polymarket stale" in k.check(buy(), ctx(feeds={"binance:BTC": 1})).reason      # missing = stale
    no_basis = {f: a for f, a in FEEDS.items() if f != "basis:USDT"}
    d = k.check(buy(TERM, kind="maker"), ctx(feeds=no_basis))
    assert "basis:USDT" in d.reason                                      # DVOL pricing a Binance USDT market
    assert k.check(buy(FAST), ctx(feeds=no_basis)).approved              # btc-speed has no USD-index inputs


# ---- B5 GTD -----------------------------------------------------------------------------------------------------------
def test_b5_gtd(k):
    c = ctx()
    assert k.check(buy(TERM, kind="maker", expiry=TERM.end_ms - 2 * MIN), c).approved
    assert "GTD" in k.check(buy(TERM, kind="maker", expiry=TERM.end_ms - 2 * MIN + 1), c).reason   # past end - 2 min
    assert "GTD" in k.check(buy(TERM, kind="maker", expiry=NOW + 2 * MIN), c).reason               # too soon
    k.starts["c-term"] = NOW + 30 * MIN                                   # a start ahead caps expiry at start - 5 min
    assert "GTD" in k.check(buy(TERM, kind="maker", expiry=NOW + 26 * MIN), c).reason
    assert k.check(buy(TERM, kind="maker", expiry=NOW + 25 * MIN), c).approved
    assert k.check(buy(FAST, expiry=FAST.end_ms + MIN), c).approved       # takers: expiry is a give-up time, not GTD


# ---- B6 1.1x cap ------------------------------------------------------------------------------------------------------
def test_b6_bankroll_over_1_1x_global_cap(k):
    assert k.check(buy(), ctx(bankroll_usd=55.0)).approved
    d = k.check(buy(), ctx(bankroll_usd=55.01, positions={"fy": 10}))
    assert not d.approved and d.binding_cap == "global"
    assert k.check(buy(side="SELL"), ctx(bankroll_usd=99, positions={"fy": 10})).approved  # reducing still allowed
    books = {"a": Book("a", [(0.4, 9)], [], NOW), "b": Book("b", [], [(0.3, 9)], NOW)}
    assert bankroll(10.0, {"a": 10, "b": 10, "c": 10}, books) == pytest.approx(14.0)   # best bid; no bid/book = 0


# ---- B7 breakers ------------------------------------------------------------------------------------------------------
def test_b7_stale_feed_trips_once(k):
    b = Breakers(k)
    b.check_feeds({"binance:BTC": 1_000})
    assert k.state == TradingState.ACTIVE
    b.check_feeds({"binance:BTC": 61_000})
    b.check_feeds({"binance:BTC": 62_000})
    assert k.state == TradingState.REDUCING and len(k.trips) == 1


def test_b7_daily_drawdown(k):
    b = Breakers(k)
    b.on_equity(50.0, NOW)                                                # start of the day
    b.on_equity(58.49, NOW + 1)                                           # paper marks run up...
    b.on_equity(50.24, NOW + 2)                                           # ...and give it back: 14% off the high,
    assert k.state == TradingState.ACTIVE                                 # but above the start: no trip (7 Oct case)
    b.on_equity(45.5, NOW + 3)                                            # 9% below the start
    assert k.state == TradingState.ACTIVE
    b.on_equity(44.9, NOW + 4)                                            # 10.2% below the start
    assert k.state == TradingState.REDUCING and "start of day 50.00" in k.trips[-1]["reason"]
    assert k.reset("global", token(nonce="dd"), NOW).approved
    b.on_equity(44.0, NOW + 5)                                            # the same loss does not undo the reset
    assert k.state == TradingState.ACTIVE
    b.on_equity(40.0, NOW + 6)                                            # a further 10.9% drop below 44.9 trips again
    assert k.state == TradingState.REDUCING


def test_b7_markout_blacklist(k):
    b = Breakers(k)
    for i in range(30):                                                   # bought at 0.50, mid 5 min later ~0.48
        b.on_fill(Fill(f"o{i}", "ladder-maker", "c-term", "ty", "BUY", 0.50, 5, NOW + i, True, 0.0))
    b.on_books({"ty": Book("ty", [(0.47, 9)], [(0.49, 9)], NOW)}, NOW + 299_999)
    assert not k.trips                                                    # not due yet
    b.on_books({"ty": Book("ty", [(0.47, 9)], [(0.49, 9)], NOW)}, NOW + 400_000)
    assert k.scopes.get("c-term") == TradingState.REDUCING and k.state == TradingState.ACTIVE
    for i in range(30):                                                   # sold at 0.46, mid 5 min later 0.48: adverse
        b.on_fill(Fill(f"s{i}", "ladder-maker", "c-sold", "sy", "SELL", 0.46, 5, NOW + i, True, 0.0))
    b.on_books({"sy": Book("sy", [(0.47, 9)], [(0.49, 9)], NOW)}, NOW + 400_000)
    assert k.scopes.get("c-sold") == TradingState.REDUCING
    noisy = Breakers(k)
    for i in range(30):                                                   # mean -0.001, SE ~0.018: not significant
        noisy.add_markout("c-x", (-0.1 if i % 2 else 0.098))
    assert "c-x" not in k.scopes


def test_b7_manual_halt_and_reset_needs_valid_unused_nonce(k, tmp_path):
    Breakers(k).manual_halt("operator")
    assert k.state == TradingState.HALTED
    assert "signature invalid" in k.reset("global", token(key="not-the-human"), NOW).reason
    assert "signature invalid" in k.reset("global", {**token(), "scope": "c-x"}, NOW).reason
    assert "scope" in k.reset("global", token(scope="c-x"), NOW).reason
    assert "expired" in k.reset("global", token(expiry=NOW), NOW).reason
    assert "not a reset" in k.reset("global", token(typ="promote"), NOW).reason
    assert k.state == TradingState.HALTED
    assert k.reset("global", token(), NOW).approved and k.state == TradingState.ACTIVE
    k.trip("global", "again", "human")
    assert "nonce already used" in k.reset("global", token(), NOW).reason
    k2 = RiskKernel(secret=KEY, nonce_path=tmp_path / "nonces.txt")       # a restart keeps the used nonces
    k2.trip("global", "x", "human")
    assert "nonce already used" in k2.reset("global", token(), NOW).reason
    assert k2.reset("global", token(nonce="fresh"), NOW).approved


# ---- B8 clearance CLI -------------------------------------------------------------------------------------------------
def test_b8_cli_record_accepted_and_tamper_rejected(k, tmp_path):
    db, keys = tmp_path / "advice.db", tmp_path / "keys.jsonl"
    assert load_advice(db) == ({}, []) and not db.exists()                # missing file = not cleared, never created
    keys.write_text(json.dumps({"key": clearance_key(FAST), "question": FAST.question}) + "\n")
    env = {**os.environ, "ROSTER_HUMAN_KEY": KEY}
    out = subprocess.run([sys.executable, "-m", "tools.clearance_cli", "--db", str(db), "sign", "--keys", str(keys),
                          "--signer", "me", "--days", "1"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    clear, _ = load_advice(db)
    c = ctx(markets=(FAST,), clearances=clear)
    c.now_ms = max(r["signed_ms"] for r in clear.values())
    fresh = buy(expiry=c.now_ms + 5_000)
    assert k.check(fresh, c).approved

    con = sqlite3.connect(db)
    rec = json.loads(con.execute("SELECT rec FROM advice").fetchone()[0])
    rec["expiry_ms"] += 86_400_000                                        # stretch the expiry without re-signing
    con.execute("UPDATE advice SET rec = ?", (json.dumps(rec),))
    con.commit()
    con.close()
    c.clearances = load_advice(db)[0]
    assert "signature invalid" in k.check(fresh, c).reason

    assert clearance_cli.main(["--db", str(db), "--key", KEY, "token", "--scope", "global", "--signer", "me"]) == 0
    tok = load_advice(db)[1][0]
    k.trip("global", "x", "human")
    assert k.reset("global", tok, c.now_ms).approved
    assert "nonce already used" in k.reset("global", tok, c.now_ms).reason
    assert clearance_cli.main(["--db", str(db), "--key", "", "token", "--scope", "g", "--signer", "me"]) == 2


def test_b7_nan_equity_does_not_disable_the_drawdown_breaker(k):
    """A NaN first reading of the day used to poison the high-water mark; it must be ignored."""
    b = Breakers(k)
    b.on_equity(float("nan"), NOW)
    b.on_equity(50.0, NOW + 1)
    b.on_equity(10.0, NOW + 2)
    assert k.state == TradingState.REDUCING and "drawdown" in k.trips[-1]["reason"]


def test_expired_clearance_is_listed_for_resigning(k, tmp_path):
    """An expired clearance must go to uncleared.jsonl, or the daily signing task never renews it and the
    template stops trading silently when its signature runs out."""
    assert "expired" in k.check(buy(), ctx(markets=(FAST,), clearances=clr(FAST, expiry=NOW - 1))).reason
    k.dump_uncleared(tmp_path / "u.jsonl")
    assert (tmp_path / "u.jsonl").read_text().strip()
    assert k.check(buy(), ctx(markets=(FAST,), clearances=clr(FAST))).approved   # renewed: approved again, list cleared
    k.dump_uncleared(tmp_path / "u2.jsonl")
    assert (tmp_path / "u2.jsonl").read_text().strip() == ""


def test_b7_start_of_day_mark_survives_a_restart(k, tmp_path):
    """A mid-day restart must not reset the day's mark, or restarting after a loss would hide it."""
    Breakers(k, run_dir=tmp_path).on_equity(50.0, NOW)
    b2 = Breakers(k, run_dir=tmp_path)                                    # restart later the same UTC day
    b2.on_equity(46.0, NOW + 3_600_000)                                   # 8% down: no trip
    assert k.state == TradingState.ACTIVE
    b2.on_equity(44.0, NOW + 3_600_001)                                   # 12% below the saved 50, not the 46 restart
    assert k.state == TradingState.REDUCING


def test_b7_strategy_loss_pauses_only_that_strategy(k, tmp_path):
    """8 Oct: one btc-speed loss tripped the account breaker and stopped ladder-maker too. A strategy's own daily
    loss over $5 now pauses only that strategy."""
    b = Breakers(k, run_dir=tmp_path, strategy_loss_usd=5.0)
    b.on_strategy_values({"btc-speed": 0.0, "ladder-maker": 0.0}, NOW)
    b.on_strategy_values({"btc-speed": -4.48, "ladder-maker": 0.3}, NOW + 1)      # under $5: nothing
    assert k.state == TradingState.ACTIVE and k.scopes.get("btc-speed", TradingState.ACTIVE) == TradingState.ACTIVE
    b.on_strategy_values({"btc-speed": -5.2, "ladder-maker": 0.3}, NOW + 2)       # over $5
    assert k.scopes["btc-speed"] == TradingState.REDUCING and k.state == TradingState.ACTIVE
    assert not k.check(buy(FAST), ctx()).approved                                  # btc-speed paused
    assert k.check(buy(TERM, kind="maker", price=0.4), ctx()).approved            # ladder-maker still trades
    b2 = Breakers(k, run_dir=tmp_path, strategy_loss_usd=5.0)                      # restart: start values kept
    b2.on_strategy_values({"btc-speed": -5.2, "ladder-maker": -4.0}, NOW + 3)     # ladder down 4.3 from 0.3: no trip
    assert k.scopes.get("ladder-maker", TradingState.ACTIVE) == TradingState.ACTIVE
