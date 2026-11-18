"""Phase 5 learning invariants (copied from tests/phase5/test_analysis.py as its audit asks) and WW-E's nightly ones:
nothing in the learning or nightly path can promote a registry version or reach HALTED."""
import pathlib

import numpy as np
import pytest

from learning import cusum, postmortem
from learning.postmortem import BLIND_FIELDS, classify, classify_all

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = [ROOT / "learning" / f for f in ("analyst.py", "postmortem.py", "cusum.py")]
NIGHTLY = [ROOT / "nightly" / f for f in ("run.py", "report.py", "scorer.py")] + [ROOT / "advisor" / "run.py"]


def _pos(mode="m", strategy="s", cl="c0", **kw):
    r = dict(pos_id="p", cid=f"{cl}:x", cluster_id=cl, mode=mode, strategy=strategy, underlying="BTC", league=None,
             horizon_h=3.0, side="BUY", size=1.0, entry_price=0.5, clv=0.0, markout_5m=0.0, fee_per_share=0.0,
             flags=[], outcome=1, pnl=0.0, primary=0.0)
    r.update(kw)
    return r


def test_a4_no_promote_anywhere():
    for f in SRC:
        assert "promote(" not in f.read_text(encoding="utf-8"), f


class Guarded(dict):
    """A position that fails the test if anything outside BLIND_FIELDS is read."""

    def __getitem__(self, k):
        assert k in BLIND_FIELDS, k
        return super().__getitem__(k)

    def get(self, k, d=None):
        assert k in BLIND_FIELDS, k
        return super().get(k, d)


def test_a5_outcome_blind():
    rng = np.random.default_rng(5)
    flags = [[], [], [], ["resolution:x"], ["wording:y"], ["data:z"]]
    pos = [_pos(mode=str(rng.choice(["m1", "m2"])), strategy=str(rng.choice(["a", "b"])), cl=f"c{i % 50}",
                clv=float(rng.normal(0, .02)), markout_5m=float(rng.normal(0, .01)),
                fee_per_share=float(rng.choice([0, 0.0175])), flags=flags[rng.integers(0, len(flags))],
                outcome=int(rng.integers(0, 2)), pnl=float(rng.normal()), primary=float(rng.normal()))
           for i in range(1000)]
    flipped = [dict(p, outcome=1 - p["outcome"], pnl=-p["pnl"], primary=-p["primary"]) for p in pos]
    a, b = classify_all(pos), classify_all(flipped)
    assert a == b and len(set(a)) == 6
    sd = postmortem.sd_by_group(pos)
    assert [classify(Guarded(p), sd) for p in pos] == a


def test_a10_no_halt():
    assert cusum.ACTIONS == ("lock", "alarm")
    with pytest.raises(AssertionError):
        cusum.Monitor("02-cusum", "halt", "x", 4.0)
    for f in SRC:
        src = f.read_text(encoding="utf-8")
        assert '"halt"' not in src and "'halt'" not in src and "HALTED" not in src, f


def test_e2_nightly_and_advisor_cannot_promote_or_halt():
    """No registry write, promotion, kernel trip or HALTED in the nightly run, its report/scorer or the advisor."""
    for f in NIGHTLY:
        src = f.read_text(encoding="utf-8")
        for bad in ("promote(", ".register(", ".trip(", "HALTED", '"halt"', "'halt'", "Ledger(", "TradingState"):
            assert bad not in src, (f.name, bad)


def test_e2_nightly_run_leaves_ledger_registry_and_state_unchanged(tmp_path):
    from nightly import run as nightly
    from trader.ledger import Ledger
    led = Ledger(tmp_path / "trader.db", clock=lambda: 1)
    led.register("kelly-c", "1", {"c": 0.3})
    for i in range(3):
        led.record("fills", dict(cid=f"c{i}", cluster_id=f"g{i}", end_ms=10, fee=0.0, fee_rate=0.07, maker=True,
                                 order_id=f"o{i}", price=0.4, size=10.0, side="BUY", strategy="ladder-maker",
                                 token_id=f"t{i}", ts_ms=5), 5)
    before = led.db.execute("SELECT * FROM registry").fetchall(), led.db.execute("SELECT COUNT(*) FROM rows").fetchone()
    led.close()
    _, cands = nightly.build(tmp_path, tmp_path / "out", now=100)
    led = Ledger(tmp_path / "trader.db", clock=lambda: 1)
    after = led.db.execute("SELECT * FROM registry").fetchall(), led.db.execute("SELECT COUNT(*) FROM rows").fetchone()
    led.close()
    assert after == before                                  # no registry change, no new ledger row (no trip)
    assert all(c.get("state", "candidate") == "candidate" for c in cands)
