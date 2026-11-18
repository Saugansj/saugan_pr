"""WX-C: counterfactual exit study. Offline; synthetic positions and a synthetic ledger in tmp_path."""
import hashlib
import random
import sqlite3

import pytest

from research.exits import study
from trader.ledger import Ledger

M, H = 60_000, 3_600_000
LOT = {"token": "Y", "cid": "c1", "cost": 0.50, "shares": 10.0, "ts_ms": 30_000, "end_ms": 10 * H, "fee_rate": 0.07,
       "cluster": "g1", "strategy": "ladder-maker"}


def path(*mids, start=1):
    return [((start + i) * M, m) for i, m in enumerate(mids)]


def sell(mid, h=0.01, rate=0.07):
    bid = mid - h
    return bid - rate * bid * (1 - bid)


# ---- C1: each rule exits at the right minute; the improvement maths is exact ----

def test_r2_take_profit_minute_and_exact_improvement():
    p = path(0.50, 0.53, 0.56, 0.60)                       # bid >= 0.55 first at minute 3 (mid 0.56)
    ex = study.first_exit(LOT, p, [], {"tp": 0.10}, 0.01)
    assert ex[0] == 3 * M and ex[2] == "R2" and ex[1] == pytest.approx(sell(0.56), abs=1e-12)
    assert study.improvement(LOT, ex, 1.0) == pytest.approx(10 * (sell(0.56) - 1.0), abs=1e-12)
    assert study.improvement(LOT, ex, 0.0) == pytest.approx(10 * sell(0.56), abs=1e-12)
    assert study.improvement(LOT, None, 1.0) == 0.0
    assert study.first_exit(LOT, p, [], {"tp": 0.25}, 0.01) is None
    late = dict(LOT, end_ms=3 * M + H - 1)                 # minute 3 has tau < 1 h, minute 4 too: no take-profit
    assert study.first_exit(late, p, [], {"tp": 0.10}, 0.01) is None


def test_r1_fair_value_fires_only_above_fair_plus_margin():
    p = path(0.50, 0.53, 0.56)
    fairs = [(2 * M, 0.45, 0.0)]                           # sell(0.53) = 0.5025 > 0.45 + 0.02
    assert study.first_exit(LOT, p, fairs, {"r1": True}, 0.01)[:1] == (2 * M,)
    edge = sell(0.53) - 0.02                               # fires only strictly above f + margin
    assert study.first_exit(LOT, p[:2], [(1 * M, edge + 1e-9, 0.0)], {"r1": True}, 0.01) is None
    assert study.first_exit(LOT, p[:2], [(1 * M, edge - 1e-9, 0.0)], {"r1": True}, 0.01)[0] == 2 * M
    fairs = [(1 * M, 0.45, 0.06)]                          # k_unc x unc = 0.06 > margin: 0.5025 < 0.51, 0.5327 > 0.51
    assert study.first_exit(LOT, p, fairs, {"r1": True}, 0.01)[0] == 3 * M
    later = path(0.50, 0.53, 0.56, start=7)                # the minute-1 fair is 6 min old by minute 7
    assert study.first_exit(LOT, later, [(1 * M, 0.10, 0.0)], {"r1": True}, 0.01) is None  # a stale fair is no fair
    assert study.first_exit(LOT, p, [], {"r1": True}, 0.01) is None      # no fair, no R1


def test_r3_model_stop_and_r4_release():
    p = path(0.45, 0.38, 0.30)
    fairs = [(1 * M, 0.45, 0.0), (2 * M, 0.35, 0.0), (3 * M, 0.20, 0.0)]
    ex = study.first_exit(LOT, p, fairs, {"sl": 0.10}, 0.01)   # f 0.35 < 0.40 and sell(0.38)=0.3537 >= 0.33
    assert ex[0] == 2 * M and ex[2] == "R3"
    far = [(2 * M, 0.35, 0.0)]
    assert study.first_exit(LOT, path(0.45, 0.30), far, {"sl": 0.10}, 0.01) is None  # market pays < f - tolerance
    assert study.first_exit(LOT, p, fairs, {"sl": 0.15}, 0.01)[0] == 3 * M   # f 0.35 is not < 0.35; 0.20 is
    hi = path(0.90, 0.96, 0.98)
    assert study.first_exit(LOT, hi, [], {"rel": 0.95}, 0.01)[:1] == (2 * M,)   # bid 0.95
    assert study.first_exit(LOT, hi, [], {"rel": 0.97}, 0.01)[:1] == (3 * M,)   # bid 0.97
    assert study.first_exit(dict(LOT, end_ms=3 * M + H - 1), hi, [], {"rel": 0.97}, 0.01) is None


def test_no_exit_before_the_fill_or_inside_the_pull_window():
    end = 10 * H
    lot = dict(LOT, ts_ms=2 * M, end_ms=end)
    assert study.first_exit(lot, path(0.99, 0.50), [], {"tp": 0.10}, 0.01) is None   # minute 1 is before the fill
    late = [(end - study.PULL_MS, 0.99), (end - M, 0.99)]
    assert study.first_exit(lot, late, [], {"tp": 0.10, "rel": 0.95}, 0.01) is None


def test_lots_fifo_net_of_sells_and_merges():
    fills = [{"side": "BUY", "token_id": t, "cid": "c", "price": px, "size": n, "ts_ms": ts, "end_ms": 9, "fee_rate": 0.07,
              "cluster_id": "k"} for t, px, n, ts in [("Y", 0.5, 10, 1), ("Y", 0.6, 10, 2), ("N", 0.4, 5, 3)]]
    fills.append({"side": "SELL", "token_id": "Y", "size": 4, "ts_ms": 4})
    out = study.lots({"fills": fills, "merges": [{"yes": "Y", "no": "N", "size": 5, "ts_ms": 3}]})
    # Y 10@0.5 -5 merged -4 sold = 1 left; Y 10@0.6 untouched; N 5 all merged
    assert [(x["token"], x["cost"], x["shares"]) for x in out] == [("Y", 0.5, 1), ("Y", 0.6, 10)]


def test_verdicts_and_cluster_se():
    assert study.verdict(1.0, 0.1, 99).startswith("INCONCLUSIVE")
    assert study.verdict(-1.0, 0.1, 60).startswith("INCONCLUSIVE") and "futility" in study.verdict(-1.0, 0.1, 60)
    assert study.verdict(1.0, 0.1, 100) == "PASS"
    assert study.verdict(0.1, 0.1, 100) == "INCONCLUSIVE (running)"
    assert study.verdict(-1.0, 0.1, 100) == "FAIL (futility)"
    assert study.verdict(None, None, 0).startswith("INCONCLUSIVE")


# ---- C2: no look-ahead ----

@pytest.mark.parametrize("seed", range(20))
def test_decision_at_t_uses_only_data_up_to_t(seed):
    rng = random.Random(seed)
    mids, m = [], 0.5
    for _ in range(120):
        m = min(0.99, max(0.01, m + rng.gauss(0, 0.03)))
        mids.append(m)
    p = path(*mids)
    fairs = [(ms - rng.randrange(0, 30_000), min(1, max(0, mid + rng.gauss(0, 0.05))), rng.random() * 0.02)
             for ms, mid in p if rng.random() < 0.7]
    fairs.sort()
    for rule in study.VARIANTS.values():
        full = study.first_exit(LOT, p, fairs, rule, 0.01)
        for k in range(1, len(p) + 1):
            t = p[k - 1][0]
            pre = study.first_exit(LOT, p[:k], [f for f in fairs if f[0] <= t], rule, 0.01)
            assert pre == (full if full is not None and full[0] <= t else None)
        if full is not None:                               # scrambling everything after the exit changes nothing
            junk = [(ms, rng.random()) if ms > full[0] else (ms, v) for ms, v in p]
            jf = [(ms, rng.random(), rng.random()) if ms > full[0] else (ms, f, u) for ms, f, u in fairs]
            assert study.first_exit(LOT, junk, sorted(jf), rule, 0.01) == full


# ---- C3 + C4: read-only ledgers, nothing written under the ledger root, report covers every variant ----

def test_end_to_end_read_only(tmp_path, monkeypatch):
    root, out, rep = tmp_path / "trader", tmp_path / "exits", tmp_path / "report.md"
    led = Ledger(root / "paper_x" / "trader.db", clock=lambda: 10 * H)
    t0, end = 0, 6 * H
    led.record("orders", {"cid": "c1", "token_id": "Y", "strategy": "ladder-maker", "side": "BUY",
                          "reason": "quote f=0.46 m=0.5 q=0.47 half=0.005 net=0"}, M)
    led.record("orders", {"cid": "c1", "token_id": "N", "strategy": "ladder-maker", "side": "BUY",
                          "reason": "quote f=0.54 m=0.5 q=0.53 half=0.005 net=0"}, M)
    led.record("fills", {"cid": "c1", "token_id": "Y", "side": "BUY", "price": 0.5, "size": 10.0, "ts_ms": M + 1,
                         "end_ms": end, "fee_rate": 0.07, "cluster_id": "k1", "strategy": "ladder-maker"}, M + 1)
    for i, mid in enumerate([0.50, 0.53, 0.60]):
        led.record("marks", {"Y": mid}, (2 + i) * M)
    led.record("settlements", {"cid": "c1", "token_id": "Y", "winner": "N", "shares": 10.0, "payout": 0.0}, end)
    led.close()
    db = root / "paper_x" / "trader.db"
    digest = hashlib.sha256(db.read_bytes()).hexdigest()

    uris, real = [], sqlite3.connect
    monkeypatch.setattr(sqlite3, "connect", lambda u, *a, **k: uris.append(str(u)) or real(u, *a, **k))
    r = study.study(root, out, fetch=None, now_ms=10 * H)
    monkeypatch.undo()
    assert uris and all(u.endswith("?mode=ro") for u in uris)
    con = real(uris[0], uri=True)
    with pytest.raises(sqlite3.OperationalError):
        con.execute("INSERT INTO rows (tbl, event_ms, recorded_ms, body) VALUES ('x', 0, 0, '{}')")
    con.close()
    # the ledger is byte-identical; the only other files are SQLite's own WAL index (-shm) and an empty -wal
    assert hashlib.sha256(db.read_bytes()).hexdigest() == digest
    assert {p.name for p in root.rglob("*") if p.is_file()} <= {"trader.db", "trader.db-wal", "trader.db-shm"}
    assert not (root / "paper_x" / "trader.db-wal").exists() or (root / "paper_x" / "trader.db-wal").stat().st_size == 0

    r1 = next(x for x in r["results"] if x["variant"] == "R1 fair-value" and x["h"] == 0.01)
    # R1 fires at minute 3 (sell(0.50)=0.4725 < 0.46 + 0.02 < sell(0.53)=0.5025), the token lost: +10 x 0.5025
    assert r1["n"] == 1 and r1["exited"] == 1 and r1["mean"] == pytest.approx(10 * sell(0.53), abs=1e-12)
    text = study.report(r)
    rep.write_text(text, encoding="utf-8")
    for name in study.VARIANTS:
        assert f"| {name} |" in text
    assert "too small" in text and "INCONCLUSIVE" in text and "How to reproduce" in text and "paper_x" in text
    assert text == study.report(study.study(root, out, fetch=None, now_ms=10 * H))   # idempotent
