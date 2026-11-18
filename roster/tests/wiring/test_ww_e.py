"""WW-E: nightly learning run and advisor process. Offline: every test blocks sockets."""
import json
import socket

import pytest

from advisor import run as advisor_run
from advisor.contracts import LLMResult
from learning.replay.events import Store
from nightly import run as nightly
from trader.contracts import MarketInfo
from trader.ledger import Ledger

T0 = 1_790_000_000_000
H = 3_600_000
N_CL = 30


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("network call attempted")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def make_run(d):
    """A run dir with 30 settled ladder-maker clusters: fills, markouts, marks, checkpoints, outcomes and a journal."""
    led = Ledger(d / "trader.db", clock=lambda: T0 + 400 * H)
    oc, journal = {}, []
    for i in range(N_CL):
        cid, y, n, end = f"c{i:02d}", f"y{i:02d}", f"n{i:02d}", T0 + (i + 1) * H
        cl, ts, oid = f"crypto-term@{end}", end - H // 2, f"o{i:02d}"
        win = y if i % 3 else n
        oc[cid] = {"winner": win, "yes": win == y}
        led.record("fills", dict(cid=cid, cluster_id=cl, end_ms=end, fee=0.0, fee_rate=0.07, maker=True, order_id=oid,
                                 price=0.40, size=10.0, side="BUY", strategy="ladder-maker", token_id=y, ts_ms=ts), ts)
        for h, mk in ((5, 0.001), (60, 0.002), (300, -0.01 * (i % 2))):
            led.record("markouts", dict(cid=cid, cluster_id=cl, fill_ms=ts, horizon_s=h, markout=mk, order_id=oid,
                                        strategy="ladder-maker", token_id=y, maker=True), ts + h * 1000)
        led.record("marks", {y: 0.42 + 0.01 * (i % 4)}, end - 60_000)
        led.record("universe_checkpoint", dict(id=f"{cid}:1", cid=cid, bucket_h=1, asset="BTC", kind="strike",
                                               end_ms=end, cluster=cl, mid_ex_own=0.41, fair=0.45 + 0.01 * (i % 5),
                                               tau_h=1.0), end - H)
        intent = dict(strategy="ladder-maker", cid=cid, token_id=y, side="BUY", price=0.40, size=10.0, kind="maker",
                      expiry_ms=end, fair=0.45, reason="t")
        journal += [{"op": "new", "id": oid, "ts": ts - 1000, "intent": intent, "queue_ahead": 5.0 * (i % 4)},
                    {"op": "fill", "id": oid, "fill": dict(order_id=oid, strategy="ladder-maker", cid=cid, token_id=y,
                                                           side="BUY", price=0.40, size=10.0, ts_ms=ts, maker=True,
                                                           fee=0.0)}]
    led.close()
    (d / "outcomes.json").write_text(json.dumps(oc), encoding="utf-8")
    (d / "journal.jsonl").write_text("".join(json.dumps(e) + "\n" for e in journal), encoding="utf-8")
    return d


def snapshot(d):
    return {p.name: p.read_bytes() for p in sorted(d.iterdir()) if p.is_file() and not p.name.endswith(("-shm", "-wal"))}  # SQLite sidecars


# ---------------------------------------------------------------- E1: every section on fixture data, offline

def test_e1_nightly_sections_offline(tmp_path):
    d = make_run(tmp_path / "run")
    before = snapshot(d)
    md, cands = nightly.build(d, tmp_path / "out", now=T0 + 500 * H, live_journal=d / "journal.jsonl")
    for head in ("## Canary", "## Analyst", "## Postmortems", "## CUSUM scans", "## Loop A", "## Replay job"):
        assert head in md, head
    assert "Section failed" not in md
    assert "Positions 30 (resolved 30)" in md and "checkpoint forecasts 30 (resolved 30)" in md
    assert "verdict **" in md                                   # canary evaluated against the given journal
    assert "| role 02 markout lock, per (strategy, underlying) series | 1 | 1 |" in md  # 30 clusters >= 20 burn-in
    assert "Resolved checkpoint rows 30 in 30 clusters" in md
    assert all(c.get("state", "candidate") == "candidate" for c in cands)
    assert snapshot(d) == before                                # run dir untouched (read-only)
    assert not (tmp_path / "out").exists()                      # build() writes nothing; main() writes the outputs


def test_e1_no_live_journal_and_main_writes_only_out_dir(tmp_path):
    d = make_run(tmp_path / "run")
    before = snapshot(d)
    assert nightly.main(["--dir", str(d), "--out-dir", str(tmp_path / "out"),
                         "--live-journal", str(tmp_path / "missing.jsonl")]) == 0
    (rep,) = (tmp_path / "out").glob("nightly_*.md")
    text = rep.read_text(encoding="utf-8")
    assert "**Not evaluated**: no live journal" in text and text.rstrip().endswith("```")
    assert "## How to reproduce" in text
    assert snapshot(d) == before


def test_e1_rows_shapes(tmp_path):
    d = make_run(tmp_path / "run")
    cum = nightly.scorer.tables(d)
    pos, fills, fc, la = nightly.build_rows(cum, json.loads((d / "outcomes.json").read_text()))
    p = pos[0]
    assert p["side"] == "BUY" and p["entry_price"] == 0.40 and p["clv"] == pytest.approx(0.02)
    assert p["outcome"] == 0 and p["pnl"] == pytest.approx(-4.0) and p["primary"] == p["pnl"]  # c00: NO won
    assert pos[1]["outcome"] == 1 and pos[1]["pnl"] == pytest.approx(6.0)
    assert fills[1]["markout_5m"] == -0.01 and fills[0]["mode"] == "crypto-term" and fills[0]["underlying"] == "BTC"
    assert len(fc) == 30 and all(r["traded"] for r in fc) and la[0] == dict(y=0, m=0.41, f=0.45, cluster_id=fc[0]["cluster_id"],
                                                                         resolved_ms=T0 + H)


def test_e1_section_failure_is_contained(tmp_path, monkeypatch):
    d = make_run(tmp_path / "run")
    monkeypatch.setattr(nightly, "cusum_section", lambda *a: 1 / 0)
    md, _ = nightly.build(d, tmp_path / "out", now=T0 + 500 * H)
    assert "**Section failed**: ZeroDivisionError" in md and "## Loop A" in md and "## Replay job" in md


class OneMaker:
    name, p = "fixture-maker", {"x": 1}

    def on_tick(self, now, markets, books, ref, positions):
        from trader.contracts import Intent
        return [Intent("ladder-maker", "c1", "Y" * 8, "BUY", 0.44, 10.0, "maker", now + H, 0.5, "t")]


def test_e1_replay_job_real_kernel_and_trial_log(tmp_path):
    m = MarketInfo("c1", "Y" * 8, "N" * 8, "crypto-term", "q", "h", 0.01, 5.0, 0.07, False, T0 + 10 * H, "g", "BTC",
                   1.0, "strike")
    book = json.dumps({"event_type": "book", "asset_id": "Y" * 8, "bids": [{"price": "0.43", "size": "50"}],
                       "asks": [{"price": "0.47", "size": "50"}]})
    store = Store(pm=[(T0 + 10, book, "crypto-term"), (T0 + 20, book, "crypto-term")], markets=[(T0, {"c1": m})])
    trials = tmp_path / "trials.jsonl"
    lines = nightly.replay_job(OneMaker(), store, T0, T0 + 1000, 50.0, trials, {})
    assert any("kernel decisions" in x and "approved" not in x.split("kernel decisions")[1] for x in lines)  # no clearance
    assert any("family N = 1" in x for x in lines)
    nightly.replay_job(OneMaker(), store, T0, T0 + 1000, 50.0, trials, {})
    rows = [json.loads(x) for x in trials.read_text().splitlines()]
    assert [r["trial_id"] for r in rows] == ["t000001", "t000002"] and rows[0]["family"] == "replay:fixture-maker"


def test_e1_replay_failure_logged(tmp_path):
    class Boom(OneMaker):
        def on_tick(self, *a):
            raise RuntimeError("boom")
    trials = tmp_path / "t.jsonl"
    store = Store(ref=[{"asset": "BTC", "ts_ms": T0 + 5, "price": 1.0}])  # a reference update ticks the engine
    with pytest.raises(RuntimeError):
        nightly.replay_job(Boom(), store, T0, T0 + 1000, 50.0, trials, {})
    assert [json.loads(x)["status"] for x in trials.read_text().splitlines()] == ["failed"]


# ---------------------------------------------------------------- E3: advisor process

KEYS = ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY")


def adv_args(tmp_path, *extra):
    return ["--once", "--backlog", str(tmp_path / "backlog.jsonl"), "--out", str(tmp_path / "w" / "agree.md"),
            "--db", str(tmp_path / "w" / "llm.db"), "--keys-out", str(tmp_path / "w" / "keys.jsonl"),
            "--gateway-db", str(tmp_path / "w" / "gw.db"), "--news", str(tmp_path / "news.jsonl"),
            "--maps", str(tmp_path / "maps.json"), "--cautions", str(tmp_path / "w" / "cautions.jsonl"),
            "--human-db", str(tmp_path / "advice.db"), *extra]


def test_e3_advisor_no_keys_exits_cleanly_writes_nothing(tmp_path, monkeypatch, capsys):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ROSTER_ADVISOR_KEY", "advisor-test-key-0001")
    (tmp_path / "backlog.jsonl").write_text('{"key": {}}\n', encoding="utf-8")
    (tmp_path / "news.jsonl").write_text('{"text": "Arsenal striker ruled out"}\n', encoding="utf-8")
    built = []
    monkeypatch.setattr(advisor_run, "LLMGateway", lambda *a: built.append(a))
    assert advisor_run.main(adv_args(tmp_path)) == 0
    assert "no vendor key set" in capsys.readouterr().out
    assert not (tmp_path / "w").exists() and not built        # no gateway db, no clearance, no caution, no report


class FakeGW:
    def __init__(self, data):
        self.data, self.calls = data, []

    def complete(self, task, prompt, schema, vendors=1):
        self.calls.append(task)
        return [LLMResult("fake", "m", True, self.data, None, False, 1)] * vendors

    def quota_left(self):
        return {"fake": 5}


def test_e3_advisor_with_gateway_runs_sentinel_and_board(tmp_path, monkeypatch):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.delenv("ROSTER_ADVISOR_KEY", raising=False)
    (tmp_path / "maps.json").write_text(json.dumps([{"event_key": "e1", "home": "Arsenal", "away": "Chelsea",
                                                     "start_ms": T0}]), encoding="utf-8")
    (tmp_path / "news.jsonl").write_text(json.dumps({"text": "Arsenal striker ruled out", "source_family": "bbc",
                                                     "published_ms": T0 - 10}) + "\n{torn", encoding="utf-8")
    snap = tmp_path / "snap.jsonl"
    snap.write_text("", encoding="utf-8")
    (tmp_path / "backlog.jsonl").write_text('{"key": {"bad": 1}}\n', encoding="utf-8")
    gw = FakeGW({"material": True, "team": "Arsenal", "kind": "injury"})
    assert advisor_run.main(adv_args(tmp_path, "--snapshot", str(snap)), gateway=gw) == 0
    (sig,) = [json.loads(x) for x in (tmp_path / "w" / "cautions.jsonl").read_text().splitlines()]
    assert sig["action"] == "pull" and sig["scope"] == "e1" and sig["shrink_factor"] == 0.0
    assert gw.calls == ["25-sports-news"]                      # the bad backlog key was skipped by the board
    assert "Skipped (key fields not exactly" in (tmp_path / "w" / "agree.md").read_text(encoding="utf-8")
    assert not (tmp_path / "w" / "llm.db").exists()             # no ROSTER_ADVISOR_KEY: nothing signed
