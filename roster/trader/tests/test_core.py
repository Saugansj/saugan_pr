"""WP1-A tests: fees (A1), ledger as_of (A2), registry (A3), pre-registrations (A4), audit chain (A5)."""
import json
import os
import random
import sqlite3

import pytest

from trader import audit, fees, ledger
from trader.audit import AuditChainError, AuditLog, AuditWriteError
from trader.ledger import Ledger, human_token


class Clock:
    """Fake clock: returns the values it is given, then repeats the last."""
    def __init__(self, *ts):
        self.ts, self.i = list(ts), 0

    def __call__(self):
        t = self.ts[min(self.i, len(self.ts) - 1)]
        self.i += 1
        return t


# ---------------- A1 fees ----------------

@pytest.mark.parametrize("rate, p, want", [
    (0.07, 0.1, 0.63), (0.07, 0.5, 1.75), (0.07, 0.9, 0.63),   # 100 x 0.07 x 0.1 x 0.9 = 0.63; docs example: 1.75
    (0.05, 0.1, 0.45), (0.05, 0.5, 1.25), (0.05, 0.9, 0.45),
])
def test_fee_hand_values(rate, p, want):
    assert fees.fee(100, p, rate) == pytest.approx(want, abs=1e-12)


def test_fee_from_real_schedules():
    crypto = {"exponent": 1, "rate": 0.07, "rebateRate": 0.2, "takerOnly": True}   # as returned by Gamma
    sports = {"exponent": 1, "rate": 0.05, "rebateRate": 0.15, "takerOnly": True}
    assert fees.taker_rate(crypto) == 0.07 and fees.taker_rate(sports) == 0.05
    assert fees.fee(5, 0.5, crypto) == pytest.approx(0.0875)


@pytest.mark.parametrize("schedule", [
    {"exponent": 1, "rate": 0.07, "takerOnly": True, "minFee": 0.01},   # unknown field
    {"exponent": 2, "rate": 0.07},                                       # different formula
    {"rate": 0.07, "takerOnly": False},                                  # makers charged
    {"exponent": 1, "takerOnly": True},                                  # no rate
    {"rate": "0.07"}, {"rate": True}, {"rate": 1.5},
    None, {},
])
def test_unmodelled_schedule_refused(schedule):
    with pytest.raises(fees.UnmodelledFee):
        fees.fee(5, 0.5, schedule)


@pytest.mark.parametrize("C, p, rate", [(-1, 0.5, 0.07), (5, 1.2, 0.07), (5, -0.1, 0.07), (5, float("nan"), 0.07),
                                        (5, 0.5, -0.01)])
def test_fee_bad_inputs(C, p, rate):
    with pytest.raises(ValueError):
        fees.fee(C, p, rate)


# ---------------- A2 ledger: bitemporal as_of ----------------

def test_as_of_hides_rows_recorded_later(tmp_path):
    lg = Ledger(tmp_path / "t.db", clock=Clock(100, 200, 300))
    lg.record("forecasts", {"cid": "a", "p": 0.4, "cluster_id": "BTC@d1"}, event_ms=90)
    lg.record("forecasts", {"cid": "b", "p": 0.6, "cluster_id": "BTC@d1"}, event_ms=190)
    lg.record("forecasts", {"cid": "c", "p": 0.5, "cluster_id": "BTC@d1"}, event_ms=50)   # backdated: known only at 300
    assert lg.as_of("forecasts", 99) == []
    assert [r["cid"] for r in lg.as_of("forecasts", 250)] == ["a", "b"]   # "c" happened at 50 but was not known yet
    assert [r["cid"] for r in lg.as_of("forecasts", 300)] == ["a", "b", "c"]
    assert lg.as_of("forecasts", 300)[2] == {"cid": "c", "p": 0.5, "cluster_id": "BTC@d1",
                                                  "event_ms": 50, "recorded_ms": 300}
    assert lg.as_of("fills", 300) == []


def test_as_of_property_with_clock_jumps(tmp_path):
    rng = random.Random(7)
    ts = [rng.randint(0, 10_000) for _ in range(300)]          # clock jumps backwards and forwards
    lg = Ledger(tmp_path / "t.db", clock=Clock(*ts))
    for i in range(300):
        lg.record("x", {"i": i}, event_ms=rng.randint(0, 10_000))
    stamps = [r["recorded_ms"] for r in lg.as_of("x", 10**12)]
    assert stamps == sorted(stamps)                              # recorded time never steps back
    for t in [rng.randint(-1, 10_001) for _ in range(200)]:
        got = lg.as_of("x", t)
        assert all(r["recorded_ms"] <= t for r in got)
        assert len(got) == sum(s <= t for s in stamps)


def test_ledger_rows_append_only_and_persist(tmp_path):
    lg = Ledger(tmp_path / "t.db", clock=Clock(500))
    lg.record("fills", {"order_id": "o1", "cluster_id": "BTC@d1"}, event_ms=499)
    with pytest.raises(ValueError):
        lg.record("fills", {"order_id": "o2"}, event_ms=499)     # no cluster id
    with pytest.raises(sqlite3.DatabaseError):
        lg.db.execute("UPDATE rows SET recorded_ms = 1")
    with pytest.raises(sqlite3.DatabaseError):
        lg.db.execute("DELETE FROM rows")
    lg.close()
    lg = Ledger(tmp_path / "t.db", clock=Clock(10))              # clock behind the stored max
    lg.record("fills", {"order_id": "o3", "cluster_id": "BTC@d1"}, event_ms=5)
    assert [(r["order_id"], r["recorded_ms"]) for r in lg.as_of("fills", 500)] == [("o1", 500), ("o3", 500)]


# ---------------- A3 registry ----------------

def test_registry_states_tokens_nonces_anchor(tmp_path, monkeypatch):
    monkeypatch.setenv(ledger.KEY_ENV, "human-secret")
    lg = Ledger(tmp_path / "t.db", clock=Clock(1000))
    tok = lambda v, n: {"nonce": n, "sig": human_token("human-secret", f"promote:kappa:{v}:live", n)}

    lg.register("kappa", 1, {"T-1h": 1.150, "T-6h": 1.034, "T-24h": 0.905})
    lg.register("kappa", 1, {"T-1h": 1.150, "T-6h": 1.034, "T-24h": 0.905})   # identical: no-op
    with pytest.raises(ValueError):
        lg.register("kappa", 1, {"T-1h": 9.0})                                   # params of a version never change
    with pytest.raises(ValueError):
        lg.promote("kappa", 1, "live", **tok(1, "n1"))                           # no skipping states
    lg.promote("kappa", 1, "shadow")
    lg.promote("kappa", 1, "canary")
    with pytest.raises(KeyError):
        lg.registry_live("kappa")

    with pytest.raises(PermissionError):
        lg.promote("kappa", 1, "live")                                           # no token
    with pytest.raises(PermissionError):
        lg.promote("kappa", 1, "live", nonce="n1", sig="0" * 64)                 # forged signature
    with pytest.raises(PermissionError):
        lg.promote("kappa", 1, "live", **tok(2, "n1"))                           # signed for another version
    monkeypatch.delenv(ledger.KEY_ENV)
    with pytest.raises(PermissionError):
        lg.promote("kappa", 1, "live", **tok(1, "n1"))                           # no key to verify against
    monkeypatch.setenv(ledger.KEY_ENV, "human-secret")
    assert lg.versions("kappa")[0]["state"] == "canary"                          # refusals changed nothing

    lg.promote("kappa", 1, "live", **tok(1, "n1"))
    assert lg.registry_live("kappa") == {"name": "kappa", "version": "1",
                                         "params": {"T-1h": 1.150, "T-6h": 1.034, "T-24h": 0.905}}

    lg.register("kappa", 2, {"T-1h": 1.1})
    for s in ("shadow", "canary"):
        lg.promote("kappa", 2, s)
    with pytest.raises(PermissionError, match="already used"):
        lg.promote("kappa", 2, "live", **tok(2, "n1"))                           # valid signature, reused nonce
    assert lg.registry_live("kappa")["version"] == "1"
    assert [v["anchor"] for v in lg.versions("kappa")] == [True, False]          # anchor kept on refusal

    lg.promote("kappa", 2, "live", **tok(2, "n2"))
    assert {v["version"]: v["state"] for v in lg.versions("kappa")} == {"1": "retired", "2": "live"}
    lg.promote("kappa", 2, "retired")                                            # automatic demotion, no token
    with pytest.raises(KeyError):
        lg.registry_live("kappa")
    assert [v["anchor"] for v in lg.versions("kappa")] == [False, True]          # anchor survives demotion
    with pytest.raises(ValueError):
        lg.promote("kappa", 2, "canary")                                         # retired is final
    with pytest.raises(sqlite3.DatabaseError):
        lg.db.execute("DELETE FROM nonces")                                      # used nonces cannot be freed

    events = [(r["version"], r.get("from"), r["to"]) for r in lg.as_of("registry", 10**12)]
    assert events[-3:] == [("1", "live", "retired"), ("2", "canary", "live"), ("2", "live", "retired")]


# ---------------- A4 pre-registrations ----------------

def test_preregistration_immutable(tmp_path):
    test = {"name": "btc-speed", "statistic": "fee-net P&L per trade, clustered by market", "alpha": 0.05,
            "n": 200, "futility": "mean < -1 SE after 100 trades"}
    lg = Ledger(tmp_path / "t.db")
    lg.preregister(test)
    lg.preregister(dict(test))                                    # identical: no-op
    with pytest.raises(ValueError):
        lg.preregister({**test, "n": 100})
    with pytest.raises(ValueError):
        lg.preregister({"statistic": "x"})                        # needs a name
    with pytest.raises(sqlite3.DatabaseError):
        lg.db.execute("UPDATE prereg SET body = '{}'")
    with pytest.raises(sqlite3.DatabaseError):
        lg.db.execute("DELETE FROM prereg")
    lg.close()
    assert Ledger(tmp_path / "t.db").preregistration("btc-speed") == test


# ---------------- A5 audit log ----------------

def _log(tmp_path, n=5):
    log = AuditLog(tmp_path / "audit.jsonl", clock=Clock(1000))
    for i in range(n):
        log.append("intent", {"i": i, "price": 0.41}, versions=[("kappa", "1")])
    return log


def test_audit_chain_verifies_and_resumes(tmp_path):
    log = _log(tmp_path)
    assert audit.verify(log.path) == (5, log.head)
    log2 = AuditLog(log.path)                                     # restart continues the chain
    assert (log2.seq, log2.head) == (5, log.head)
    log2.append("fill", {"order_id": "o1"})
    assert audit.verify(log.path)[0] == 6


@pytest.mark.parametrize("tamper", ["edit", "edit_rehash", "delete", "swap", "insert"])
def test_audit_tamper_detected(tmp_path, tamper):
    log = _log(tmp_path)
    lines = log.path.read_bytes().splitlines(keepends=True)
    rec = json.loads(lines[2])
    if tamper == "edit":
        rec["data"]["price"] = 0.40
        lines[2] = (audit._canon(rec) + "\n").encode()
    elif tamper == "edit_rehash":                                 # attacker fixes that record's own hash
        rec["data"]["price"] = 0.40
        rec["hash"] = audit._hash(rec)
        lines[2] = (audit._canon(rec) + "\n").encode()
    elif tamper == "delete":
        del lines[2]
    elif tamper == "swap":
        lines[1], lines[2] = lines[2], lines[1]
    else:
        lines.insert(2, lines[2])
    log.path.write_bytes(b"".join(lines))
    with pytest.raises(AuditChainError):
        audit.verify(log.path)


def test_audit_tampered_tail_refused_on_open(tmp_path):
    log = _log(tmp_path)
    log.path.write_bytes(log.path.read_bytes().replace(b'"i":4', b'"i":9'))
    with pytest.raises(AuditChainError):
        AuditLog(log.path)


def test_audit_disk_dies_mid_write(tmp_path, monkeypatch):
    log = _log(tmp_path, 3)
    real_write = os.write
    monkeypatch.setattr(audit.os, "write", lambda fd, b: real_write(fd, b[: len(b) // 2]))   # half a record lands
    with pytest.raises(AuditWriteError):
        log.append("fill", {"order_id": "o9"})
    monkeypatch.setattr(audit.os, "write", real_write)
    with pytest.raises(AuditWriteError):
        log.append("cancel", {"order_id": "o9"})                  # latched: no write after a failure
    assert log.seq == 3

    log2 = AuditLog(log.path)                                     # restart: the torn half-record is cut off
    assert audit.verify(log.path) == (4, log2.head)
    last = json.loads(log.path.read_bytes().splitlines()[-1])
    assert last["kind"] == "recovery" and last["data"]["torn_bytes"] > 0


def test_audit_fsync_failure_raises(tmp_path, monkeypatch):
    log = _log(tmp_path, 1)
    def boom(fd):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(audit.os, "fsync", boom)
    with pytest.raises(AuditWriteError):
        log.append("decision", {"approved": False})
    assert log.failed


def test_audit_unwritable_path_raises(tmp_path):
    log = _log(tmp_path, 1)
    log.path.unlink()
    log.path.mkdir()                                              # the file is gone and cannot be reopened
    with pytest.raises(AuditWriteError):
        log.append("intent", {})


def test_audit_finds_last_line_beyond_first_window(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl", clock=Clock(1))
    log.append("intent", {"blob": "x" * 200_000})                 # one record bigger than the 64 KiB tail window
    log.append("intent", {"blob": "y" * 150_000})
    reopened = AuditLog(log.path)
    assert (reopened.seq, reopened.head) == (2, log.head)


def test_raw_replace_cannot_rewrite_a_preregistration_or_ledger_row(tmp_path):
    import sqlite3
    lg = Ledger(tmp_path / "t.db", clock=Clock(100, 200))
    lg.preregister({"name": "x", "n": 200})
    lg.record("forecasts", {"cluster_id": "c", "p": 0.5}, 50)
    for sql in ("INSERT OR REPLACE INTO prereg SELECT * FROM prereg", "REPLACE INTO rows SELECT * FROM rows"):
        with pytest.raises(sqlite3.DatabaseError):
            lg.db.execute(sql)
