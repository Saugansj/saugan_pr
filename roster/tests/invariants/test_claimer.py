"""ops/claimer.py and tools/live_tools/setup_relayer_key.py with fakes: no network, no wallet (15 Nov)."""
import json
import types

import pytest

from ops import claimer as C

ROWS = [{"condition_id": "W", "current_value": 5.52, "current_size": 5.52, "title": "BTC 15m", "outcome": "Down"},
        {"condition_id": "L", "current_value": 0.0, "current_size": 5.24, "title": "BTC 5m", "outcome": "Down"}]


def test_claimable_keeps_winners_only():
    c = C.claimable(ROWS)
    assert list(c) == ["W"] and c["W"]["value"] == pytest.approx(5.52) and c["W"]["outcome"] == "Down"


def test_fetch_follows_the_cursor():
    pages = iter([{"data": ROWS[:1], "pagination": {"next_cursor": "c2"}}, {"data": ROWS[1:], "pagination": {}}])
    seen = []
    rows = C.fetch_redeemable("0xW", get=lambda url: seen.append(url) or next(pages))
    assert len(rows) == 2 and "status=REDEEMABLE" in seen[0] and "cursor=c2" in seen[1]


class FakeClient:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def redeem_positions(self, *, condition_id, metadata=None):
        self.calls.append(condition_id)
        if self.fail:
            raise RuntimeError("relayer said no")
        return types.SimpleNamespace(wait=lambda: types.SimpleNamespace(transaction_hash="0xabc"))


def test_run_once_claims_logs_and_waits_before_a_retry(tmp_path):
    log, made, t = tmp_path / "claims.jsonl", [], [1_000.0]
    get = lambda url: {"data": ROWS, "pagination": {}}
    ok = FakeClient()
    r = C.run_once("0xW", lambda: made.append(1) or ok, get=get, tried={}, path=log, now_s=lambda: t[0], out=lambda *_: None)
    assert r == {"claimed": 1, "failed": 0, "waiting": 1} and ok.calls == ["W"] and len(made) == 1
    row = json.loads(log.read_text().splitlines()[0])
    assert row["ok"] and row["cid"] == "W" and row["tx"] == "0xabc" and row["value"] == pytest.approx(5.52)

    bad, tried = FakeClient(fail=True), {}
    r = C.run_once("0xW", lambda: bad, get=get, tried=tried, path=log, now_s=lambda: t[0], out=lambda *_: None)
    assert r["failed"] == 1 and not json.loads(log.read_text().splitlines()[1])["ok"]
    t[0] += 60                                      # inside RETRY_S: not tried again
    assert C.run_once("0xW", lambda: bad, get=get, tried=tried, path=log, now_s=lambda: t[0], out=lambda *_: None)["waiting"] == 0
    t[0] += C.RETRY_S                               # after it: tried again
    assert C.run_once("0xW", lambda: bad, get=get, tried=tried, path=log, now_s=lambda: t[0], out=lambda *_: None)["waiting"] == 1


def test_no_client_is_made_when_nothing_is_claimable(tmp_path):
    made = []
    r = C.run_once("0xW", lambda: made.append(1), get=lambda url: {"data": ROWS[1:]}, path=tmp_path / "c.jsonl",
                   out=lambda *_: None)
    assert r == {"claimed": 0, "failed": 0, "waiting": 0} and made == []


def test_setup_relayer_key_validates_and_saves_names_only():
    from tools.live_tools import setup_relayer_key as K
    saved, said = {}, []
    assert K.main(ask=lambda p: "0x" + "a" * 40, ask_secret=lambda p: "k" * 20, save=saved.update, out=said.append) == 0
    assert set(saved) == {"RELAYER_API_KEY", "RELAYER_API_KEY_ADDRESS"} and "k" * 20 not in " ".join(said)
    assert K.main(ask=lambda p: "nope", ask_secret=lambda p: "k" * 20, save=saved.update, out=said.append) == 2
    assert K.main(ask=lambda p: "0x" + "a" * 40, ask_secret=lambda p: "short", save=saved.update, out=said.append) == 2
