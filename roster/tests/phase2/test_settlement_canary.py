"""WP2-D tests (D1-D11): settlement keeper (outcome derivation, UMA proposal parsing, mismatch / unreadable / dispute
drills, oracle gap, fund intents and gate, paging) and canary evaluation. No network: the autouse guard lets sockets
reach loopback only. Tests write only under tmp_path.

`python -m tests.phase2.test_settlement_canary` prints the drill results quoted in reports/phase2_settlement.md;
`--synthetic DIR` writes synthetic canary rows; `--history` checks derive_outcome against Phase 0's local klines,
recorded winners and cached proposals (offline); `--smoke-days N` runs the keeper on real public GETs (read-only)."""
import dataclasses
import datetime as dt
import json
import logging
import pathlib
import re
import socket
import sys

import numpy as np
import pytest

from history.polymarket import noon_et_ms  # the 12:00 ET instant Phase 0's binance_check uses
from trader.contracts import Fill, Intent, MarketInfo, Order, TradingState
from trader.kernel import RiskKernel
from trader.live import canary, settlement
from trader.live.settlement import (FundIntent, SettlementKeeper, Status, candles, derive_outcome, fund_intents, gate,
                                    page, page_text, print_ms, proposal)

A, R, H = TradingState.ACTIVE, TradingState.REDUCING, TradingState.HALTED
ROOT = pathlib.Path(__file__).resolve().parents[2]
LOOPBACK = ("127.0.0.1", "::1", "localhost")
_connect = socket.socket.connect
MIN = 60_000


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def connect(self, addr):
        if addr[0] not in LOOPBACK:
            raise RuntimeError(f"network disabled in unit tests ({addr[0]})")
        return _connect(self, addr)
    monkeypatch.setattr(socket.socket, "connect", connect)


def ms(*a) -> int:
    return int(dt.datetime(*a, tzinfo=dt.timezone.utc).timestamp() * 1000)


def mi(cid="0xs1", kind="strike", mode="crypto-term", end=ms(2026, 10, 1, 16), strike=100_000.0,
       source="binance:BTC/USDT", question="Bitcoin above $100,000 on October 1?") -> MarketInfo:
    return MarketInfo(cid, f"{cid}-Y", f"{cid}-N", mode, question, "r", 0.01, 5.0, 0.0, False, end,
                      f"BTC@{end}", "BTC", strike if kind == "strike" else None, kind, source)


def kl(t, o, c) -> list:
    """A raw Binance /api/v3/klines row."""
    return [t, f"{o:.2f}", "0", "0", f"{c:.2f}", "1.0", t + MIN - 1, "0", 1, "0", "0", "0"]


# ---- D1 derive_outcome ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("close,want", [(100_000.01, "YES"), (99_999.99, "NO"), (100_000.0, "NO")])
def test_d1_strike_strict(close, want):
    m = mi()
    assert candles(m) == [m.end_ms]  # 16:00Z = 12:00 EDT
    assert derive_outcome(m, [kl(m.end_ms, 1, close)]) == want


def test_d1_daily_updown_dst_matches_binance_check():
    """Settlement Sun 2026-11-01 (DST ends that morning): the previous 12:00 ET close is 2026-10-31 16:00Z (EDT),
    25 h before the 17:00Z (EST) print candle. A decoy candle exactly 24 h earlier would flip the answer."""
    end = ms(2026, 11, 1, 17)
    m = mi("0xu1", "updown", end=end, question="Bitcoin Up or Down on November 1?")
    prev, noon = noon_et_ms(dt.date(2026, 10, 31)), noon_et_ms(dt.date(2026, 11, 1))
    assert candles(m) == [prev, noon] == [ms(2026, 10, 31, 16), ms(2026, 11, 1, 17)]
    assert print_ms(m) == noon + MIN  # binance_check: print_ts = settle_ts_ms // 1000 + 60
    decoy = kl(end - 86_400_000, 1, 200_000)
    assert derive_outcome(m, [kl(prev, 1, 70_000), decoy, kl(noon, 1, 70_100)]) == "YES"
    assert derive_outcome(m, [kl(prev, 1, 70_000), decoy, kl(noon, 1, 69_900)]) == "NO"
    assert derive_outcome(m, [kl(prev, 1, 70_000), decoy, kl(noon, 1, 70_000)]) == "50-50"
    assert derive_outcome(m, [decoy, kl(noon, 1, 70_000)]) is None  # previous close missing


def test_d1_old_gamma_end_convention_uses_noon_et():
    """Old Gamma endDate was 12:00Z; the print is still the 12:00 ET candle (Phase 0 settle_ts_ms 1735923600000)."""
    m = mi(end=ms(2025, 1, 3, 12), strike=94_000.0)
    assert candles(m) == [1735923600000] == [noon_et_ms(dt.date(2025, 1, 3))]


@pytest.mark.parametrize("o,c,want", [(100.0, 100.5, "YES"), (100.0, 100.0, "YES"), (100.0, 99.5, "NO")])
def test_d1_hourly(o, c, want):
    end = ms(2026, 10, 1, 9)
    m = mi("0xh1", "updown", "crypto-hourly", end=end)
    first, last = candles(m)
    assert (first, last, print_ms(m)) == (end - 3_600_000, end - MIN, end)
    assert derive_outcome(m, [kl(first, o, 1.0), kl(last, 1.0, c)]) == want


@pytest.mark.parametrize("mode,source", [("crypto-fast", "chainlink:BTC/USD"), ("sports-pregame", ""),
                                         ("crypto-term", "")])
def test_d1_unreadable_sources(mode, source):
    m = mi(mode=mode, source=source)
    assert candles(m) == [] and print_ms(m) == m.end_ms
    assert derive_outcome(m, [kl(m.end_ms, 1, 1e9)]) is None


# ---- D2 proposal ---------------------------------------------------------------------------------------------------
# Copied from research/measure/data/resolutions.jsonl (cid prefix kept for grep; tx hash and question id dropped).
REAL = {
    "yes": {"cid": "0xbd459aae3c...", "status": "resolved", "was_disputed": False,
            "proposed_price": "1000000000000000000", "reproposed_price": "69", "price": "1000000000000000000",
            "last_update_timestamp": "1759947472"},
    "no": {"cid": "0x8cb9bcf319...", "status": "resolved", "was_disputed": False, "proposed_price": "0",
           "reproposed_price": "69", "price": "0", "last_update_timestamp": "1759861026"},
    "disputed": {"cid": "0xee07df9a4c...", "status": "resolved", "was_disputed": True, "proposed_price": "0",
                 "reproposed_price": "0", "price": "0", "last_update_timestamp": "1777250276"},
    "reproposed": {"cid": "0xc2da6ce685...", "status": "resolved", "was_disputed": False,
                   "proposed_price": "1000000000000000000", "reproposed_price": "1000000000000000000",
                   "price": "1000000000000000000", "last_update_timestamp": "1762112207"},
}


def test_d2_proposal_on_cached_records():
    assert proposal(REAL["yes"]) == "YES" and proposal(REAL["reproposed"]) == "YES"
    assert proposal(REAL["no"]) == "NO" and proposal(REAL["disputed"]) == "NO"
    assert proposal({**REAL["no"], "proposed_price": "500000000000000000"}) == "50-50"  # no 50-50 in the cache
    assert proposal({**REAL["no"], "reproposed_price": "1000000000000000000"}) == "YES"  # a reproposal supersedes


@pytest.mark.parametrize("rec", [{**REAL["yes"], "proposed_price": "69"}, {k: v for k, v in REAL["yes"].items()
                                 if k != "proposed_price"}, {**REAL["yes"], "proposed_price": "1e18"},
                                 {**REAL["yes"], "proposed_price": None}, {}, None, "garbage", [REAL["yes"]]])
def test_d2_proposal_none(rec):
    assert proposal(rec) is None


# ---- keeper drills -------------------------------------------------------------------------------------------------
class FakeGet:
    """Routes the keeper's two public GETs: Binance klines and the Data API resolution record."""

    def __init__(self, klines=(), recs=None, fail=()):
        self.klines = {(r[0]): r for r in klines}
        self.recs, self.fail, self.calls = recs if recs is not None else {}, set(fail), []

    def __call__(self, url, params=None):
        self.calls.append((url, dict(params or {})))
        if url == settlement.KLINES:
            if "klines" in self.fail:
                raise TimeoutError("binance down")
            assert params["interval"] == "1m" and params["symbol"] == "BTCUSDT"
            r = self.klines.get(params["startTime"])
            return [r] if r else []
        if url == settlement.RESOLUTIONS:
            rec = self.recs.get(params["condition"])
            return {"data": [rec] if rec else []}
        raise AssertionError(f"unexpected GET {url}")


def keeper(markets, get):
    k = RiskKernel(nonce_path=None)
    pages = []
    kp = SettlementKeeper({m.cid: m for m in markets}, get, lambda text: pages.append(text) or True, k.trip)
    return kp, k, pages


def held(*ms_):
    return {m.token_yes: 10.0 for m in ms_}


def mismatch_drill() -> dict:
    m = mi()
    prop_s = (m.end_ms + 6 * MIN) // 1000
    get = FakeGet([kl(m.end_ms, 1, 100_500)], {m.cid: {"status": "proposed", "was_disputed": False,
                                                       "proposed_price": "0", "reproposed_price": "69",
                                                       "last_update_timestamp": str(prop_s)}})
    kp, k, pages = keeper([m], get)
    kp.step(print_ms(m) + 6 * MIN, held(m))
    first = (len(pages), len(k.trips))
    kp.step(print_ms(m) + 7 * MIN, held(m))
    return {"m": m, "kp": kp, "kernel": k, "pages": pages, "after_first": first, "prop_s": prop_s}


def test_d3_mismatch_pages_once_and_locks():
    d = mismatch_drill()
    m, k, pages, s = d["m"], d["kernel"], d["pages"], d["kp"].statuses["0xs1"]
    assert d["after_first"] == (1, 1) and len(pages) == 1 and len(k.trips) == 1  # second step: nothing new
    deadline = dt.datetime.fromtimestamp(d["prop_s"] + 7200, dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    assert m.cid in pages[0] and m.question in pages[0]
    assert "proposed: NO" in pages[0] and "derived: YES" in pages[0] and f"challenge deadline: {deadline}" in pages[0]
    assert k.trips[0]["scope"] == m.cid and k.trips[0]["source"] == "breaker:settlement"
    assert k.trips[0]["level"] == "REDUCING" and k.scopes[m.cid] == R and k.state == A  # market lock, not global
    assert (s.state, s.mismatch, s.locked, s.deadline_ms) == ("mismatch", True, True, (d["prop_s"] + 7200) * 1000)


def test_d3_matching_proposal_is_quiet():
    m = mi()
    get = FakeGet([kl(m.end_ms, 1, 100_500)], {m.cid: {"status": "proposed", "proposed_price": "1000000000000000000",
                                                       "reproposed_price": "69", "last_update_timestamp": "1"}})
    kp, k, pages = keeper([m], get)
    kp.step(print_ms(m) + 30 * MIN, held(m))
    assert pages == [] and k.trips == [] and kp.statuses[m.cid].state == "matched"


def unreadable_drill() -> dict:
    fast = mi("0xf1", "updown", "crypto-fast", source="chainlink:BTC/USD", question="BTC Up or Down 5m?")
    down = mi("0xs2")  # Binance source, but the klines GET keeps failing
    kp, k, pages = keeper([fast, down], FakeGet(recs={}, fail={"klines"}))
    kp.step(print_ms(down) + 9 * MIN, held(fast, down))
    early = (len(pages), len(k.trips))  # fast printed 10 min ago already (print = end); down not yet
    kp.step(print_ms(down) + 10 * MIN, held(fast, down))
    kp.step(print_ms(down) + 11 * MIN, held(fast, down))
    return {"kp": kp, "kernel": k, "pages": pages, "early": early}


def test_d4_unreadable_source_after_grace():
    d = unreadable_drill()
    k, pages = d["kernel"], d["pages"]
    assert d["early"] == (1, 1) and k.trips[0]["scope"] == "0xf1"  # chainlink: 10 min after its print at end_ms
    assert len(pages) == 2 and len(k.trips) == 2 and {t["scope"] for t in k.trips} == {"0xf1", "0xs2"}
    assert all(t["source"] == "breaker:settlement" and t["level"] == "REDUCING" for t in k.trips)
    assert all("derived: source cannot be read" in p for p in pages)
    assert all(s.state == "mismatch" and s.mismatch and s.locked for s in d["kp"].statuses.values())


def test_d4_garbage_responses_do_not_break_the_keeper():
    m = mi()
    kp, k, pages = keeper([m], FakeGet([[m.end_ms, "1", "0", "0", "not-a-price"]], {m.cid: "not-a-record"}))
    kp.step(print_ms(m) + MIN, held(m))
    assert kp.statuses[m.cid].derived is None and kp.statuses[m.cid].state == "printed" and pages == []


def dispute_drill() -> dict:
    m, other = mi(), mi("0xs9")
    rec = {"status": "disputed", "was_disputed": True, "proposed_price": "1000000000000000000",
           "reproposed_price": "69", "last_update_timestamp": "1790872000"}
    kp, k, pages = keeper([m, other], FakeGet([kl(m.end_ms, 1, 100_500)], {m.cid: rec, other.cid: rec}))
    kp.step(print_ms(m) + 20 * MIN, held(m))  # `other` is not held
    kp.step(print_ms(m) + 21 * MIN, held(m))
    return {"kp": kp, "kernel": k, "pages": pages}


def test_d4_dispute_on_held_market():
    d = dispute_drill()
    k, pages = d["kernel"], d["pages"]
    assert len(k.trips) == 1 and len(pages) == 1 and "DISPUTE" in pages[0]
    assert (k.trips[0]["scope"], k.trips[0]["source"]) == ("0xs1", "breaker:dispute")
    assert d["kp"].statuses["0xs1"].state == "disputed" and "0xs9" not in d["kp"].statuses


def test_d5_oracle_gap():
    m, later = mi(), mi("0xs3", end=ms(2026, 10, 2, 16))
    rec = {}
    kp, _, _ = keeper([m, later], FakeGet([kl(m.end_ms, 1, 100_500)], {m.cid: rec}))
    kp.step(m.end_ms + 30_000, held(m, later))  # past end, before the print candle closes
    assert kp.oracle_gap() == set() and kp.statuses[m.cid].state == "waiting"
    kp.step(print_ms(m) + 30_000, held(m, later))  # printed, but the candle is read only once its close is final
    assert kp.oracle_gap() == {m.cid} and not any(u == settlement.KLINES for u, _ in kp.get.calls)
    kp.step(print_ms(m) + MIN, held(m, later))
    assert kp.oracle_gap() == {m.cid} and kp.statuses[m.cid].state == "printed"
    assert kp.statuses[m.cid].derived == "YES"
    rec.update({"status": "proposed", "proposed_price": "1000000000000000000", "last_update_timestamp": "1"})
    kp.step(print_ms(m) + 2 * MIN, held(m, later))
    assert kp.oracle_gap() == {m.cid} and kp.statuses[m.cid].state == "matched"
    rec.update({"status": "resolved", "price": "1000000000000000000"})
    kp.step(print_ms(m) + 130 * MIN, held(m, later))
    assert kp.oracle_gap() == set() and kp.statuses[m.cid].outcome == "YES"
    n = len(kp.get.calls)
    kp.step(print_ms(m) + 131 * MIN, held(m, later))
    assert len(kp.get.calls) == n  # a resolved market is not polled again
    kp.step(print_ms(m) + 132 * MIN, {})
    assert kp.oracle_gap() == set() and len(kp.get.calls) == n
    kp2, _, _ = keeper([mi("0xs4")], FakeGet())  # unheld but printed: in the gap (conservative), no GET spent
    kp2.step(print_ms(m) + MIN, {})
    assert kp2.oracle_gap() == {"0xs4"} and kp2.get.calls == []


# ---- D6 fund intents and gate --------------------------------------------------------------------------------------
def sell(tok, size, filled=0.0, status="open"):
    return Order(f"o-{tok}-{size}", Intent("ladder-maker", "c", tok, "SELL", 0.6, size, "maker", 0, 0.5, "t"),
                 status, filled)


def fund_drill() -> dict:
    a, b = mi("0xa"), mi("0xb")
    yes, no, half, bad = (mi(c) for c in ("0xy", "0xn", "0xh", "0xbad"))
    st = {c.cid: Status(c, state="resolved", outcome=o) for c, o in ((yes, "YES"), (no, "NO"), (half, "50-50"),
                                                                     (bad, "YES"))}
    st["0xbad"].mismatch = True
    st["0xdisp"] = Status(mi("0xdisp"), state="resolved", outcome="YES", disputed=True)
    st["0xlock"] = Status(mi("0xlock"), state="resolved", outcome="YES", locked=True)
    pos = {"0xa-Y": 12.345, "0xa-N": 10.0, "0xb-Y": 7.129, "0xb-N": 9.0,
           "0xy-Y": 10.0, "0xy-N": 4.0, "0xn-Y": 3.0, "0xn-N": 6.5, "0xh-Y": 2.0, "0xh-N": 5.0,
           "0xbad-Y": 9.0, "0xdisp-Y": 9.0, "0xlock-Y": 9.0}
    orders = [sell("0xa-N", 3.0, 1.0), sell("0xa-N", 50.0, 0.0, "cancelled")]  # 2 offered; the cancelled one is not
    return {"intents": fund_intents(pos, orders, {a.cid: a, b.cid: b}, st), "statuses": st}


def test_d6_fund_intents():
    got = {(f.kind, f.cid, f.token_ids, f.size) for f in fund_drill()["intents"]}
    assert got == {("merge", "0xa", ("0xa-Y", "0xa-N"), 8.0),   # min(12.345, 10 - 2 offered)
                   ("merge", "0xb", ("0xb-Y", "0xb-N"), 7.12),  # floored, never rounded up
                   ("redeem", "0xy", ("0xy-Y",), 10.0), ("redeem", "0xn", ("0xn-N",), 6.5),
                   ("redeem", "0xh", ("0xh-Y",), 2.0), ("redeem", "0xh", ("0xh-N",), 5.0)}  # 50-50: both tokens
    # resolved markets are redeemed, never merged; mismatched, disputed and locked markets are never redeemed


def test_d6_gate():
    merge, redeem = FundIntent("merge", "0xa", ("Y", "N"), 5, "t"), FundIntent("redeem", "0xa", ("Y",), 5, "t")
    for fi in (merge, redeem):
        assert not gate(fi, {"global": H}).approved and not gate(fi, {"global": A, "0xa": H}).approved
        assert gate(fi, {"global": R}).approved and gate(fi, {"global": A}).approved
    assert gate(merge, {"global": A, "0xa": R}).approved              # a locked market can still merge
    assert not gate(redeem, {"global": A, "0xa": R}).approved          # ... but never redeem
    for flag in ("mismatch", "disputed", "locked"):
        assert not gate(redeem, {"global": A}, Status(mi("0xa"), **{flag: True})).approved
    assert not gate(FundIntent("convert", "0xa", (), 1, "t"), {"global": A}).approved


# ---- D7 page -------------------------------------------------------------------------------------------------------
def test_d7_page_no_topic(monkeypatch):
    monkeypatch.delenv("ROSTER_NTFY_TOPIC", raising=False)
    sent = []
    assert page("hello", send=lambda *a: sent.append(a)) is False and sent == []
    assert page("hello") is False  # default sender: the no-network guard would raise if it were called


def test_d7_page_body_and_topic_hygiene(monkeypatch, caplog):
    monkeypatch.setenv("ROSTER_NTFY_TOPIC", "roster-test-topic-xyz")
    d = mismatch_drill()
    sent = []
    assert page(d["pages"][0], send=lambda url, body: sent.append((url, body))) is True
    url, body = sent[0]
    assert url == settlement.NTFY + "/roster-test-topic-xyz" and settlement.NTFY == "https://ntfy.sh"
    text = body.decode()
    assert set(re.findall(r"^(\w[\w ]*?):", text, re.M)) == {"cid", "question", "proposed", "derived",
                                                             "challenge deadline"}
    assert not re.search(r"balance|position|shares|bankroll|secret|passphrase|api_key|private|POLY_", text, re.I)

    def boom(url, body):
        raise OSError(f"cannot reach {url}")
    with caplog.at_level(logging.DEBUG):
        assert page("x", send=boom) is False  # swallowed
    assert "roster-test-topic-xyz" not in caplog.text


def test_d7_no_hardcoded_topic():
    src = (ROOT / "trader" / "live" / "settlement.py").read_text(encoding="utf-8")
    assert not re.search(r"ntfy\.sh/\w", src) and "ROSTER_NTFY_TOPIC" in src


# ---- D8 canary -----------------------------------------------------------------------------------------------------
P_FILL = (0.6, 0.4, 0.2, 0.05)       # per queue bucket
MU = (-0.01, 0.0, 0.004, 0.01)       # mean 5m markout per share
RATIO = (0.5, 3.0, 10.0, 40.0)       # queue_ahead / size representative of each bucket


def synth(n_clusters, seed, prefix, p_fill=P_FILL, buckets=(0, 1, 2, 3), per=8) -> list[dict]:
    """Maker rows from one process: a cluster effect on fill odds, per-bucket fill probability and markout."""
    rng, rows = np.random.default_rng(seed), []
    for c in range(n_clusters):
        shift = rng.normal(0, 0.05)
        for j in range(per):
            b = buckets[rng.integers(len(buckets))]
            size = float(rng.choice([5.0, 10.0, 20.0]))
            fill = rng.random() < min(max(p_fill[b] + shift, 0.0), 1.0)
            rows.append({"order_id": f"{prefix}{c}-{j}", "cluster": f"{prefix}{c}", "queue_ahead": RATIO[b] * size,
                         "size": size, "filled": size if fill else 0.0,
                         "markout_5m": float(rng.normal(MU[b], 0.02)) if fill else None})
    return rows


REPLAY = synth(400, 1, "r")


def test_d8_same_process_passes():
    # Deterministic seed. With a 90% interval per bucket per metric (8 checks), about 57% of same-process samples
    # FAIL by chance (1 - 0.9^8); `python -m tests.phase2.test_settlement_canary` measures it. See the report.
    res = canary.evaluate(synth(60, 2, "l"), REPLAY)
    assert res["live_fill_clusters"] >= 30 and res["verdict"] == "PASS", res["reason"]
    assert [b["bucket"] for b in res["buckets"]] == ["[0, 1)", "[1, 5)", "[5, 20)", "[20, inf)"]


def test_d8_shifted_fill_rate_fails():
    res = canary.evaluate(synth(60, 2, "l", p_fill=(0.98, 0.4, 0.2, 0.05)), REPLAY)
    assert res["verdict"] == "FAIL" and "[0, 1) fill_rate" in res["reason"]
    assert canary.FAIL_TEXT in res["reason"]


def test_d8_insufficient():
    live = [{"order_id": f"o{c}", "cluster": f"c{c}", "queue_ahead": 1.0, "size": 5.0, "filled": 5.0,
             "markout_5m": -0.01} for c in range(29)]
    assert canary.evaluate(live, REPLAY)["verdict"] == "INSUFFICIENT"
    live.append({**live[0], "order_id": "o29", "cluster": "c29"})
    assert canary.evaluate(live, REPLAY)["verdict"] != "INSUFFICIENT"


def test_d8_no_replay_clusters_fails_closed():
    res = canary.evaluate(synth(60, 2, "l"), synth(400, 1, "r", buckets=(0, 1, 2)))
    assert res["verdict"] == "FAIL" and "[20, inf) no replay clusters" in res["reason"]
    no_mids = [{**r, "markout_5m": None} for r in synth(60, 2, "l")]
    assert "markout_5m missing" in canary.evaluate(no_mids, REPLAY)["reason"]


def test_d8_deterministic_cli(tmp_path):
    live, rep = tmp_path / "live.jsonl", tmp_path / "replay.jsonl"
    live.write_text("".join(json.dumps(r) + "\n" for r in synth(60, 2, "l")))
    rep.write_text("".join(json.dumps(r) + "\n" for r in REPLAY))
    outs = []
    for name in ("a.md", "b.md"):
        canary.main(["--live", str(live), "--replay", str(rep), "--out", str(tmp_path / name), "--n-boot", "500",
                     "--label", "SYNTHETIC rows"])
        outs.append((tmp_path / name).read_text())
    assert outs[0] == outs[1] and "## Verdict: PASS" in outs[0] and "SYNTHETIC" in outs[0]
    assert outs[0].rstrip().splitlines()[-1] == "```" and "## How to reproduce" in outs[0]
    assert canary.evaluate(synth(60, 2, "l"), REPLAY, seed=7) == canary.evaluate(synth(60, 2, "l"), REPLAY, seed=7)


# ---- D9 rows_from_journal ------------------------------------------------------------------------------------------
def test_d9_rows_from_journal(tmp_path):
    m = mi("0xj")
    j = tmp_path / "journal.jsonl"

    def intent(side, size, kind="maker", price=0.4):
        return dataclasses.asdict(Intent("ladder-maker", m.cid, m.token_yes, side, price, size, kind, 0, 0.5, "t"))

    def fill(oid, side, price, size, ts):
        return {"op": "fill", "id": oid, "fill": dataclasses.asdict(Fill(oid, "ladder-maker", m.cid, m.token_yes, side,
                                                                         price, size, ts, True, 0.0))}
    lines = [{"op": "new", "id": "b1", "ts": 1, "intent": intent("BUY", 10), "queue_ahead": 25.0}, {"op": "ack", "id": "b1"},
             fill("b1", "BUY", 0.4, 10, 1_000),
             {"op": "new", "id": "s1", "ts": 2, "intent": intent("SELL", 5, price=0.6), "queue_ahead": 2.0},
             {"op": "ack", "id": "s1"}, fill("s1", "SELL", 0.6, 2, 2_000), {"op": "cancel", "id": "s1"},
             {"op": "new", "id": "u1", "ts": 3, "intent": intent("BUY", 5), "queue_ahead": 0.0}, {"op": "ack", "id": "u1"},
             {"op": "cancel", "id": "u1"},
             {"op": "new", "id": "live", "ts": 4, "intent": intent("BUY", 5), "queue_ahead": 1.0},
             {"op": "ack", "id": "live"},  # still resting: excluded
             {"op": "new", "id": "t1", "ts": 5, "intent": intent("BUY", 5, "taker"), "arrival_ms": 9},
             {"op": "done", "id": "t1"}]  # taker: excluded
    j.write_text("".join(json.dumps(e) + "\n" for e in lines) + '{"op": "fill", "id": "b1", "fi')  # torn last line
    asked = []
    mids = {(m.token_yes, 301_000): 0.43, (m.token_yes, 302_000): 0.55}

    def mid_at(tok, ts):
        asked.append((tok, ts))
        return mids.get((tok, ts))
    rows = {r["order_id"]: r for r in canary.rows_from_journal(j, {m.cid: m}, mid_at)}
    assert set(rows) == {"b1", "s1", "u1"} and sorted(asked) == sorted(mids)
    assert rows["b1"] == {"order_id": "b1", "cluster": m.event_group, "queue_ahead": 25.0, "size": 10, "filled": 10,
                          "markout_5m": pytest.approx(0.03)}           # BUY: mid 5m later - price
    assert rows["s1"]["filled"] == 2 and rows["s1"]["markout_5m"] == pytest.approx(0.05)  # SELL: price - mid
    assert rows["u1"]["filled"] == 0 and rows["u1"]["markout_5m"] is None
    assert [canary.bucket_of(rows[k]) for k in ("b1", "s1", "u1")] == [1, 0, 0]


# ---- evidence for the report (not collected by pytest) -------------------------------------------------------------
def _drills():
    d3, d4, dd, fd = mismatch_drill(), unreadable_drill(), dispute_drill(), fund_drill()
    print("D3 mismatch: pages after step 1 / trips:", d3["after_first"], "| after step 2:",
          (len(d3["pages"]), len(d3["kernel"].trips)), "| trip:", d3["kernel"].trips[0])
    print("D3 page body:\n" + d3["pages"][0])
    print("D4 unreadable: after 9 min:", d4["early"], "| after 10-11 min:", (len(d4["pages"]), len(d4["kernel"].trips)),
          [(t["scope"], t["source"], t["level"]) for t in d4["kernel"].trips])
    print("D4 dispute:", (len(dd["pages"]), len(dd["kernel"].trips)), dd["kernel"].trips[0])
    for f in fd["intents"]:
        print("D6", f)
    rate = sum(canary.evaluate(synth(60, s, "l"), REPLAY, n_boot=500)["verdict"] == "FAIL" for s in range(100, 200))
    print(f"D8 same-process live samples that FAIL (100 seeds, 60 clusters): {rate}%")


def _history():
    """derive_outcome over Phase 0's daily markets with local Binance klines vs recorded winners and cached proposals."""
    import pandas as pd
    mk = pd.read_parquet(ROOT / "data/history/polymarket/markets.parquet")
    k = {}
    for a in ("BTC", "ETH"):
        frames = [pd.read_parquet(p, columns=["open_time", "open", "close"])
                  for p in sorted((ROOT / f"data/history/binance/{a}USDT").glob("*.parquet"))]
        df = pd.concat(frames).drop_duplicates("open_time")
        k[a] = dict(zip(df.open_time.tolist(), zip(df.open.tolist(), df.close.tolist())))
    recs = {}
    for x in (ROOT / "research/measure/data/resolutions.jsonl").read_text().splitlines():
        r = json.loads(x)
        recs[r["cid"]] = r
    tally = {}
    for r in mk.itertuples():
        m = MarketInfo(r.condition_id, r.yes_token, r.no_token, "crypto-term", r.question, r.rules_sha256, 0.01, 5.0,
                       0.0, False, int(r.settle_ts_ms), "", r.asset, None if r.mode == "updown" else float(r.strike),
                       r.mode, f"binance:{r.asset}/USDT")
        rows = [[t, k[r.asset][t][0], 0, 0, k[r.asset][t][1]] for t in candles(m) if t in k[r.asset]]
        got = derive_outcome(m, rows)
        win = "YES" if r.winner == r.yes_outcome else "NO" if r.winner == r.no_outcome else None
        prop = proposal(recs.get(r.condition_id))
        t = tally.setdefault(r.mode, {"markets": 0, "derived": 0, "agree_winner": 0, "with_proposal": 0,
                                      "agree_proposal": 0, "disagree": []})
        t["markets"] += 1
        t["derived"] += got is not None
        t["agree_winner"] += got is not None and got == win
        if got is not None and prop is not None:
            t["with_proposal"] += 1
            t["agree_proposal"] += got == prop
            if got != prop:
                t["disagree"].append((r.condition_id[:12], r.settle_date, got, prop, win))
    for mode, t in tally.items():
        print(f"history {mode}: {t['markets']} markets, {t['derived']} derived, {t['agree_winner']} agree with the "
              f"recorded winner; {t['with_proposal']} with a cached proposal, {t['agree_proposal']} agree; "
              f"disagreements: {t['disagree'][:10]}")


def _smoke(days: int):
    """The keeper on real public GETs (Binance klines, Data API resolutions) over Phase 0's daily markets settled in
    the last `days` days, every market treated as held. Pages and trips are recorded locally, never sent."""
    import common
    import pandas as pd
    mk = pd.read_parquet(ROOT / "data/history/polymarket/markets.parquet")
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    mk = mk[mk.settle_date >= since]
    markets = {r.condition_id: MarketInfo(r.condition_id, r.yes_token, r.no_token, "crypto-term", r.question, "", 0.01,
                                          5.0, 0.0, False, int(r.settle_ts_ms), "", r.asset,
                                          None if r.mode == "updown" else float(r.strike), r.mode,
                                          f"binance:{r.asset}/USDT") for r in mk.itertuples()}
    trips, pages = [], []
    get = lambda url, params=None: common.get_json(url, params, retries=2, timeout=10)
    kp = SettlementKeeper(markets, get, lambda t: pages.append(t) or False,
                          lambda *a: trips.append(a))
    kp.step(common.now_ms(), {m.token_yes: 1.0 for m in markets.values()})
    st = list(kp.statuses.values())
    agree = sum(s.derived is not None and s.derived == s.proposed for s in st)
    print(f"smoke since {since}: {len(st)} markets ({mk['mode'].value_counts().to_dict()}), derived "
          f"{sum(s.derived is not None for s in st)}, with a proposal {sum(s.proposed is not None for s in st)}, "
          f"agree {agree}, mismatch {sum(s.mismatch for s in st)}, disputed {sum(s.disputed for s in st)}, "
          f"states {pd.Series([s.state for s in st]).value_counts().to_dict()}, pages {len(pages)} (not sent), "
          f"trips {len(trips)} (recorded only), GETs {len(kp._kl)} kline candles cached")
    for p in pages[:3]:
        print(p)


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--synthetic" in args:
        out = pathlib.Path(args[args.index("--synthetic") + 1])
        out.mkdir(parents=True, exist_ok=True)
        for name, rows in (("synthetic_live.jsonl", synth(60, 2, "l")), ("synthetic_replay.jsonl", REPLAY),
                           ("synthetic_live_shifted.jsonl", synth(60, 2, "l", p_fill=(0.98, 0.4, 0.2, 0.05)))):
            (out / name).write_text("".join(json.dumps(r) + "\n" for r in rows))
        print("wrote synthetic rows to", out)
    elif "--history" in args:
        _history()
    elif "--smoke-days" in args:
        _smoke(int(args[args.index("--smoke-days") + 1]))
    else:
        _drills()
