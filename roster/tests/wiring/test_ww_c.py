"""WW-C acceptance tests (C1-C4): engines wired behind feature flags. Fakes only, no network, no files outside tmp."""
import datetime as dt
import hashlib
import inspect
import itertools
import json
import math
import random
import socket

import pytest

from trader.contracts import Book, Engine, Intent, MarketInfo
from trader.engines import fast_maker as FM
from trader.engines import ladder as L
from trader.engines import sports_maker as SM
from trader.growth import capital
from trader.growth import fast_updown as FU
from trader.ledger import Ledger

H, MIN = L.H_MS, L.MIN_MS
E = int(dt.datetime(2026, 10, 2, 16, tzinfo=dt.timezone.utc).timestamp() * 1000)   # 12:00 ET print


def mk(cid, strike=80_000.0, kind="strike", asset="BTC", mode="crypto-term", end=E, group=None, min_size=5.0):
    return MarketInfo(cid=cid, token_yes=cid + "Y", token_no=cid + "N", mode=mode, question="", rules_sha256="r",
                      tick_size=0.01, min_size=min_size, fee_rate=0.07, neg_risk=False, end_ms=end,
                      event_group=group or f"{asset}@{end}", asset=asset, strike=strike, kind=kind,
                      source_id="binance")


def books_for(m, mid, ts, half=0.01, size=100.0):
    return {m.token_yes: Book(m.token_yes, [(round(mid - half, 4), size)], [(round(mid + half, 4), size)], ts),
            m.token_no: Book(m.token_no, [(round(1 - mid - half, 4), size)], [(round(1 - mid + half, 4), size)], ts)}


# ---------- C1: recorded tick set ----------

def tick_set(seed=11, n=40):
    """Deterministic ticks: a BTC strike ladder, an ETH ladder, a BTC Up/Down, plus a touch market and a sports market
    that the flags-off ladder must ignore. Prices random-walk, books drift, positions grow on the way."""
    rnd = random.Random(seed)
    ms = [mk(f"b{k}", float(k)) for k in (78_000, 79_000, 80_000, 81_000, 82_000)]
    ms += [mk(f"e{k}", float(k), asset="ETH") for k in (3_900, 4_000, 4_100)]
    ms += [mk("ud", None, "updown"), mk("tu", 84_000.0, "touch-up", end=E + 20 * H, group="BTC-touch@x"),
           mk("sp", None, "", None, "sports-pregame", group="EPL:a:b")]
    markets = {m.cid: m for m in ms}
    now0 = E - 8 * H
    prev = L.prev_noon_ms(E)
    S, X = 80_000.0, 4_000.0
    pos, out = {}, []
    for t in range(n):
        now = now0 + t * 37_000
        S *= math.exp(rnd.gauss(0, 0.0015))
        X *= math.exp(rnd.gauss(0, 0.002))
        books = {}
        for m in ms:
            fair = 0.5 if m.strike is None else (S if m.asset == "BTC" else X) / m.strike - 0.5
            mid = round(min(0.9, max(0.1, fair + rnd.gauss(0, 0.03))), 2)
            books.update(books_for(m, mid, now - rnd.randrange(0, 3_000), half=rnd.choice((0.01, 0.02, 0.03))))
        ref = {"BTC": {"price": S, "ts_ms": now - 500, "dvol": 45.0 + t % 5, "final": {prev: 79_800.0},
                       "high": S * 1.01, "low": S * 0.99},
               "ETH": {"price": X, "ts_ms": now - 700, "dvol": 60.0, "final": {}}}
        if t == 15:
            pos = {"b80000Y": 12.0, "e4000N": 7.0}
        out.append((now, markets, books, ref, dict(pos)))
    return out


def run(eng, ticks):
    intents, records = [], []
    for now, markets, books, ref, pos in ticks:
        intents.append(eng.on_tick(now, markets, books, ref, pos))
        records += eng.records
        eng.records.clear()
    return intents, records


def digest(x):
    return hashlib.sha256(repr(x).encode()).hexdigest()


BASELINE = (111, 8, "ca55cac7b38f85728c3eb8645f558499a260d222cb2b6535af530026f5a6fe3c",
            "911a564e40e5bba68914945cb12163d747f9fa4d04dd7792bb4c6c64b7eab7bf")   # audited ladder.py, before WW-C
# ladder v2 (8 Oct): the intents digest changed only by the version tag (ladder-maker, 2); with the tag set back to 1
# it equals the audited d3e1ce9d35ed6e2028997064acdb902bd7f23fdb5601d725a916ba187b1283f6 (the tick set is >1 h from
# the end and has no sharp move, so v2's new pulls never fire on it)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise RuntimeError("network disabled in unit tests")
    monkeypatch.setattr(socket.socket, "connect", refuse)


def test_c1_flags_off_ladder_identical_to_audited_build():
    for eng in (L.LadderEngine(), L.LadderEngine(flags=("sports", "fast_maker", "negrisk_scan"))):
        i, r = run(eng, tick_set())
        assert (sum(map(len, i)), len(r), digest(i), digest(r)) == BASELINE


def check_intents(intents, cap):
    """Role 23 sign/magnitude invariant per intent, prices on the tick grid inside (0, 1) and at most q unless the
    bid reduces exposure (inventory skew), sizes floored to 0.01 and never above the cap."""
    for i in intents:
        f, m, q = L.reason_fmq(i.reason)
        assert L.invariant_ok(q, f, m) and q == i.fair, i
        assert i.side == "BUY" and i.kind == "maker" and 0 < i.price < 1 and (i.price <= q or i.reduces_exposure)
        assert abs(i.price / 0.01 - round(i.price / 0.01)) < 1e-6
        assert abs(i.size / L.SIZE_STEP - round(i.size / L.SIZE_STEP)) < 1e-6 and 0 < i.size <= cap


# ---------- touch ----------

def touch_tick(kind="touch-up", strike=84_000.0, high=81_000.0, low=79_000.0):
    now = E - 6 * H
    m = mk("t", strike, kind, end=E, group="BTC-touch@x")
    ref = {"BTC": {"price": 80_000.0, "ts_ms": now, "dvol": 50.0, "final": {}, "high": high, "low": low}}
    return m, now, books_for(m, 0.2, now), ref


def test_touch_routed_only_with_flag_and_guarded():
    m, now, b, ref = touch_tick()
    assert L.LadderEngine().on_tick(now, {m.cid: m}, b, ref, {}) == []          # flag off: ignored
    out = L.LadderEngine(flags=("touch",)).on_tick(now, {m.cid: m}, b, ref, {})
    assert out and all(("touch", 1) in i.versions for i in out)
    check_intents(out, L.PARAMS["quote_size"])
    fv = L.touch_value(m, ref["BTC"], now, L.PARAMS)
    assert 0 < fv["f"] < 1 and fv["vol"] > 0 and fv["kappa_unfitted"] is False
    for bad in ({"price": float("nan")}, {"dvol": float("nan")}, {"high": float("nan")}, {"high": None},
                {"price": 0.0}, {"dvol": -5.0}):
        r = {**ref["BTC"], **bad}
        assert "err" in L.touch_value(m, r, now, L.PARAMS), bad                  # NaN used to give f = 1.0
        assert L.LadderEngine(flags=("touch",)).on_tick(now, {m.cid: m}, b, {"BTC": r}, {}) == []
    assert "err" in L.touch_value(m, ref["BTC"], m.end_ms, L.PARAMS)            # tau <= 0
    hit = L.touch_value(m, {**ref["BTC"], "high": 84_500.0}, now, L.PARAMS)
    assert hit["f"] == 1.0 and hit["vol"] == 0.0 and hit["touched"]
    d = mk("t", 84_000.0, "touch-down")
    assert 0 < L.touch_value(d, {**ref["BTC"], "price": 85_000.0, "low": 84_800.0}, now, L.PARAMS)["f"] < 1
    from trader.growth import touch                                              # kappa keys after JSON: strings
    orig = touch.REGISTRY["touch"]["params"]
    touch.REGISTRY["touch"]["params"] = json.loads(json.dumps(orig))
    try:
        assert L.touch_value(m, ref["BTC"], now, L.PARAMS)["f"] == fv["f"]
    finally:
        touch.REGISTRY["touch"]["params"] = orig


def test_touch_coherence_is_log_only_and_never_crashes():
    m, now, b, ref = touch_tick(strike=80_500.0)
    dig = mk("d", 80_500.0, end=E - 2 * H)                                     # settles inside the window
    b = {**b, **books_for(dig, 0.40, now)}                                       # digital bid 0.39 > touch ask 0.21
    eng = L.LadderEngine(flags=("touch",))
    eng.on_tick(now, {m.cid: m, dig.cid: dig}, b, ref, {})
    flags = [r for t, r, _ in eng.records if t == "arb_opportunity" and r.get("touch") == "t"]
    assert [f["kind"] for f in flags] == ["touch<terminal"]
    fv = L.touch_value(m, ref["BTC"], now, L.PARAMS)
    late = dig.end_ms + 2 * MIN
    assert L.touch_flags(m, fv, b[m.token_yes], dig, b[dig.token_yes], b[dig.token_no], late) == []  # tau <= 0
    assert L.touch_flags(m, {**fv, "sigma_p": 0.0}, b[m.token_yes], dig, b[dig.token_yes], b[dig.token_no], now) == []
    rich = {m.token_yes: Book(m.token_yes, [(0.95, 100)], [(0.97, 100)], now),
            dig.token_yes: Book(dig.token_yes, [(0.01, 100)], [(0.02, 100)], now)}
    assert L.touch_flags(m, fv, rich[m.token_yes], dig, rich[dig.token_yes], b[dig.token_no], now) == []
    same_end = mk("d2", 80_500.0, end=m.end_ms)                                  # upper flag: digital at window end
    assert L.touch_flags(m, fv, rich[m.token_yes], same_end, rich[dig.token_yes], b[dig.token_no], now) == \
        ["touch>2x_digital+eps"]


# ---------- quote objective ----------

def test_quote_objective_passes_through_wider_of_phase1_quotes():
    ticks = tick_set()
    on, _ = run(L.LadderEngine(flags=("quote_objective",)), ticks)
    assert any(on), "the objective quotes somewhere on the tick set"
    check_intents([i for x in on for i in x], L.PARAMS["quote_size"])
    rnd, n = random.Random(3), 0
    for k in range(300):                              # per market: wider() never adds a token, a higher bid or size
        m = mk(f"w{k}")
        now = E - rnd.uniform(1.5, 20) * H
        yes, no = books_for(m, round(rnd.uniform(0.1, 0.9), 2), now, half=rnd.choice((0.01, 0.02, 0.04))).values()
        fv = {"f": rnd.uniform(0.05, 0.95), "unc": rnd.uniform(0, 0.02), "vol": rnd.uniform(0, 0.02)}
        pos = rnd.choice(({}, {m.token_yes: rnd.uniform(0, 40)}, {m.token_no: rnd.uniform(0, 40)}))
        args = (m, fv, yes, no, pos, {}, now, L.PARAMS, L.VERSIONS)
        base = {i.token_id: i for i in L.market_intents(*args)[0]}
        for i in L.market_intents(*args, {**L.QO_PARAMS, "reward": None})[0]:
            n += 1
            b = base[i.token_id]
            assert i.price <= b.price and i.size <= b.size and i.fair == b.fair
    assert n > 50
    eng = L.LadderEngine(flags=("quote_objective",))                            # a reward pool reaches the objective
    eng.rewards = {c: {"min_size": 5.0, "max_spread": 3.0, "daily_rate": 50.0} for c in ticks[0][1]}
    check_intents([i for x in run(eng, ticks)[0] for i in x], L.PARAMS["quote_size"])
    m = mk("q")
    fv = {"f": 0.6, "unc": 0.01, "vol": 0.01}
    yes = books_for(m, 0.5, 0, half=0.05)[m.token_yes]
    assert L.objective_quotes(m, fv, 0.53, 0.5, yes, (0.55, 0.55), 0.0, {}, [(m.token_yes, 0.5, 10.0, False)],
                              m.end_ms - L.PARAMS["pull_before_close_ms"], L.PARAMS, L.QO_PARAMS) == []  # tau <= 0


def test_sizer_invariant_random_with_quote_objective_and_touch():
    rnd = random.Random(5)
    eng = L.LadderEngine({"move_k": 1e9}, flags=("quote_objective", "touch"))
    for k in range(200):
        kind = rnd.choice(("strike", "touch-up", "touch-down"))
        m = mk(f"r{k}", rnd.uniform(76_000, 84_000), kind)
        now = E - rnd.uniform(1.5, 20) * H
        b = books_for(m, round(rnd.uniform(0.1, 0.9), 2), now, half=rnd.choice((0.01, 0.02, 0.04)))
        pos = rnd.choice(({}, {m.token_yes: rnd.uniform(0, 40)}, {m.token_no: rnd.uniform(0, 40)}))
        ref = {"BTC": {"price": 80_000.0, "ts_ms": now, "dvol": 50.0, "high": 80_100.0, "low": 79_900.0}}
        check_intents(eng.on_tick(now, {m.cid: m}, b, ref, pos), L.PARAMS["quote_size"])


def test_oracle_gap_pulls():
    m = mk("g")
    now = E - 6 * H
    b, ref = books_for(m, 0.5, now), {"BTC": {"price": 80_000.0, "ts_ms": now, "dvol": 50.0}}
    eng = L.LadderEngine()
    assert eng.on_tick(now, {m.cid: m}, b, ref, {})
    eng.oracle_gap = {m.cid}
    assert eng.on_tick(now, {m.cid: m}, b, ref, {}) == []
    assert L.pull_reason(m, b[m.token_yes], b[m.token_no], ref["BTC"], now, 0, L.PARAMS, {m.cid}) == "oracle_gap"


# ---------- C2: Engine protocol ----------

def test_c2_engines_meet_the_engine_protocol():
    want = list(inspect.signature(Engine.on_tick).parameters)
    for eng in (L.LadderEngine(flags=("touch", "quote_objective")), SM.SportsMakerEngine(), FM.FastMakerEngine()):
        assert isinstance(eng.name, str) and eng.name
        assert list(inspect.signature(type(eng).on_tick).parameters) == want
        assert eng.on_tick(E, {}, {}, {}, {}) == []
    assert SM.NAME == "sports-maker" and FM.NAME == "fast-updown-maker"


# ---------- sports maker (C2, C3) ----------

NOW = 1_790_000_000_000
START = NOW + 3 * H
EK = "E0:Arsenal:Leeds:2026-10-10"
ODDS = {"H": 1.80, "D": 3.90, "A": 4.60}


def sports_setup(mid=0.5):
    from sports import fair
    mm = {"cid": "s1", "token_yes": "s1Y", "token_no": "s1N", "event_key": EK, "league": "E0", "home": "Arsenal",
          "away": "Leeds", "outcome": "H", "start_ms": START}
    m = mk("s1", None, "", None, "sports-pregame", end=START + 2 * H, group=EK)
    eng = SM.SportsMakerEngine()
    eng.maps, eng.methods = {"s1": mm}, {"E0": "odds_ratio"}
    eng.sharp = [{"source": "sgo", "book": "pinnacle", "event_key": EK, "obs_ms": NOW - H, "odds": ODDS}]
    f = fair.fair(mm, eng.sharp, eng.methods, NOW)["fair"]
    eng.continuous = [{"source": "kalshi", "event_key": EK, "obs_ms": NOW - 1000, "probs": {"H": f}}]
    eng.game_states = {EK: {"event_key": EK, "scheduled_start_ms": START, "status": "scheduled"}}
    eng.feed_age_ms = {"polymarket": 1000, "sports": 5000}
    return eng, m, books_for(m, mid, NOW, half=0.02), f


def test_c3_sports_quotes_only_when_no_pull_and_keyed_odds_present():
    from advisor.contracts import CautionSignal
    from sports import pulls
    eng, m, b, f = sports_setup()
    out = eng.on_tick(NOW, {m.cid: m}, b, {}, {})
    assert out and eng.last_pulls == {"s1": []}, "control: quotes when nothing is wrong"
    check_intents(out, SM.PARAMS["quote_size"])
    assert all(i.strategy == "sports-maker" and i.expiry_ms <= pulls.maker_expiry(START, m.end_ms) for i in out)
    assert next(i for i in out if i.token_id == "s1Y").fair == pytest.approx(L.shrink(f, 0.5))
    cases = {
        "keyed odds missing (no SGO key, no sharp snapshot)": lambda e: setattr(e, "sharp", []),
        "no continuous source": lambda e: setattr(e, "continuous", []),
        "continuous outside 1 sigma": lambda e: e.continuous[0].update(probs={"H": 0.2}),
        "game postponed": lambda e: e.game_states[EK].update(status="postponed"),
        "no game state": lambda e: setattr(e, "game_states", {}),
        "lineup out, no newer sharp": lambda e: setattr(e, "lineups", {EK: NOW - 1000}),
        "caution pull": lambda e: setattr(e, "cautions", [CautionSignal("25-sports-news", "s1", "pull", 1.0,
                                                                        NOW + MIN, False, "injury")]),
        "stale book feed": lambda e: e.feed_age_ms.update(polymarket=60_000),
        "no sports feed": lambda e: e.feed_age_ms.pop("sports"),
        "no devig method": lambda e: setattr(e, "methods", {}),
    }
    for name, breakit in cases.items():
        e, m, b, _ = sports_setup()
        breakit(e)
        assert e.on_tick(NOW, {m.cid: m}, b, {}, {}) == [] and e.last_pulls["s1"], name
    e, m, b, _ = sports_setup()
    assert e.on_tick(START - 4 * MIN, {m.cid: m}, books_for(m, 0.5, START - 4 * MIN), {}, {}) == []  # pre-start
    e, m, b, _ = sports_setup()
    assert e.on_tick(NOW, {}, b, {}, {}) == []                                   # mapped cid not in markets


def test_c2_sports_sizer_invariant_random():
    rnd = random.Random(9)
    for _ in range(300):
        eng, m, b, _ = sports_setup(round(rnd.uniform(0.3, 0.75), 2))
        pos = rnd.choice(({}, {"s1Y": rnd.uniform(0, 60)}, {"s1N": rnd.uniform(0, 60)}))
        for tok, n in pos.items():
            eng.cost[tok] = (n, rnd.uniform(0.2, 0.7))
        check_intents(eng.on_tick(NOW, {m.cid: m}, b, {}, pos), SM.PARAMS["quote_size"])


# ---------- fast maker (C2, C4) ----------

FSTART = 1_800_000_000_000 // (15 * MIN) * (15 * MIN)


def new_ledger(path):
    return Ledger(path=path, clock=itertools.count(1000, 1000).__next__)


def fast_run(eng):
    m = MarketInfo("BTC-15m", "up", "down", "crypto-fast", "BTC Up or Down", "r", 0.01, 5.0, 0.07, False,
                   FSTART + 15 * MIN, "BTC-15m@2027-01-15T08:00Z", asset="BTC", kind="updown")
    for ts in (FSTART - 70_000, FSTART - 3_000):   # crossing the settlement boundary: the trailing TWAP open
        eng.on_tick(ts, {}, {}, {"BTC": {"price": 60_000.0, "ts_ms": ts, "dvol": 50.0}}, {})
    now = FSTART + 2 * MIN
    b = {"up": Book("up", [(0.50, 100.0)], [(0.54, 100.0)], now),
         "down": Book("down", [(0.46, 100.0)], [(0.50, 100.0)], now)}
    return eng.on_tick(now, {m.cid: m}, b, {"BTC": {"price": 60_060.0, "ts_ms": now, "dvol": 50.0}}, {})


def e6(led, by_asset):
    led.preregister(FU.LATENCY_PREREG)
    led.record(capital.RESULTS, {"test": FU.LATENCY_PREREG["name"], "n": 400, "mean": 0.02, "se": 0.005,
                                 "cap_usd": 50, "evidence": "e6", "by_asset": by_asset}, 0)


def test_c4_fast_maker_silent_while_gate_closed(tmp_path):
    assert fast_run(FM.FastMakerEngine()) == []                                  # no ledger

    class Broken:
        def preregistration(self, name):
            raise OSError("db locked")
    assert fast_run(FM.FastMakerEngine(Broken())) == []                          # unreadable evidence
    led = new_ledger(tmp_path / "a.db")
    try:
        assert fast_run(FM.FastMakerEngine(led)) == []                           # no pre-registration
        led.preregister(FU.LATENCY_PREREG)
        assert fast_run(FM.FastMakerEngine(led)) == []                           # pre-registered, no result
    finally:
        led.close()
    led = new_ledger(tmp_path / "b.db")
    try:
        e6(led, {"BTC": {"n": 250, "mean": 0.015, "se": 0.01}})               # 1.5 SE: fails
        assert fast_run(FM.FastMakerEngine(led)) == []
    finally:
        led.close()


def test_c4_fast_maker_trades_only_once_gate_opens_and_rereads_it(tmp_path):
    led = new_ledger(tmp_path / "p.db")
    try:
        e6(led, {"BTC": {"n": 250, "mean": 0.03, "se": 0.01}})                # 3 SE, n >= 200: passes
        eng = FM.FastMakerEngine(led)
        out = fast_run(eng)
        assert out and eng.gate(FSTART) == {"BTC"}, "control: the gate opens on a passing row"
        for i in out:
            f, mm, q = L.reason_fmq(i.reason)
            assert L.invariant_ok(q, f, mm) and i.size <= FU.MAX_SHARES and i.strategy == "fast-updown-maker"
        eng.ledger = None                                                        # gate re-read every refresh_ms
        assert eng.gate(FSTART + 2 * MIN + 30_000) == {"BTC"} and eng.gate(FSTART + 10 * MIN) == frozenset()
    finally:
        led.close()


# ---------- negRisk scan adapter ----------

def nr_rows(n=3):
    base = {"mode": "sports-pregame", "event_slug": "ev", "question": "q", "rules_sha256": "h", "tick_size": 0.01,
            "min_order_size": 5, "neg_risk": True, "end_time": "2026-10-10T11:30:00Z", "neg_risk_augmented": False,
            "neg_risk_other": False, "seconds_delay": 1,
            "fee_schedule": {"exponent": 1, "rate": 0.05, "takerOnly": True, "rebateRate": 0.15}}
    return [{**base, "condition_id": f"c{i}", "yes_token_id": f"y{i}", "no_token_id": f"n{i}"} for i in range(n)]


def test_negrisk_scanner_logs_rows_only_and_fails_closed():
    from trader.growth import negrisk
    sc = L.NegRiskScanner()
    sc.on_snapshot(nr_rows() + [{"neg_risk": False, "event_slug": "x"}])
    assert list(sc.events) == ["ev"]
    books = {f"y{i}": Book(f"y{i}", [(0.29, 50)], [(0.30, 50)], NOW) for i in range(3)}
    rows = sc.scan(books, NOW, 200.0, feed_fresh=True)
    assert [(t, r["eligible"], r["reason"], r["round_trip_ms"]) for t, r, _ in rows] == \
        [("negrisk_scan", False, "no confirmation secret", 1200.0)]
    assert rows[0][1]["edge"] > 0                                                # cheap basket, still ineligible
    assert sc.scan(books, NOW, 200.0, feed_fresh=False) == []
    conf = negrisk.confirm(sc.events["ev"], NOW + H, "s3cret")
    assert sc.scan(books, NOW, 200.0, True, [conf], "s3cret")[0][1]["eligible"] is True
    assert sc.scan(books, NOW, 200.0, True, [conf], "wrong")[0][1]["eligible"] is False
    assert not any(isinstance(v, Intent) for _, r, _ in rows for v in r.values())




def test_touch_uses_the_per_market_window_shape_marketdata_produces():
    """marketdata keeps each touch window's high/low under ref[asset]["touch"][cid], not on ref[asset] itself.
    The engine must read that shape (it used to pass ref[asset] alone, so every touch market returned err)."""
    m, now, b, ref = touch_tick()
    flat = ref["BTC"]
    nested = {k: v for k, v in flat.items() if k not in ("high", "low")}
    nested["touch"] = {m.cid: {"start_ms": now - H, "high": flat["high"], "low": flat["low"]}}
    out = L.LadderEngine(flags=("touch",)).on_tick(now, {m.cid: m}, b, {"BTC": nested}, {})
    assert out and all(("touch", 1) in i.versions for i in out)
