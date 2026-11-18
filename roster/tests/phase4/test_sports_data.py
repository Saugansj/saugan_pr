"""WP4-A tests: Kalshi, football-data closing, SportsGameOdds and odds-api.io parsers and key handling, snapshot schedule,
market mapping, quota book, game state, cancel rule and the early-start drill (A1-A8). No network: an autouse fixture makes
every socket connect fail."""
import json
import pathlib
import socket
from datetime import datetime, timezone

import pandas as pd
import pytest

from sports import gamestate as G
from sports import odds as O
from trader.contracts import Intent, Order

FX = pathlib.Path(__file__).parent / "fixtures" / "sports_data"
H, MIN = 3_600_000, 60_000


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise RuntimeError("network disabled in unit tests")
    monkeypatch.setattr(socket.socket, "connect", refuse)


def ms(iso):
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


def load(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


def raw_text(raw_dir):
    return "".join(p.read_text(encoding="utf-8") for p in pathlib.Path(raw_dir).rglob("*.jsonl"))


START = ms("2026-10-10T11:30:00Z")
EK = "E0:arsenal:leeds:2026-10-10"

# ---------------------------------------------------------------- A1 Kalshi


def test_kalshi_probs_equal_hand_computed_mids():
    fx = load("kalshi_event.json")
    s = O.parse_kalshi("E0", fx["event"], fx["books"], 123)
    # best bids from the captured books: ARS yes .72 / no .27, LEE yes .11 / no .88, TIE yes .17 / no .82
    assert s["probs"] == pytest.approx({"H": (0.72 + 1 - 0.27) / 2, "A": (0.11 + 1 - 0.88) / 2, "D": (0.17 + 1 - 0.82) / 2})
    assert s["source"] == "kalshi" and s["event_key"] == EK and s["start_ms"] == START and "odds" not in s
    assert s["home"] == "Arsenal" and s["away"] == "Leeds United" and s["recv_ms"] == 123


def test_kalshi_empty_side_gives_no_snapshot_and_legacy_cents():
    fx = load("kalshi_event.json")
    books = json.loads(json.dumps(fx["books"]))
    books["KXEPLGAME-26OCT10ARSLEE-TIE"]["orderbook_fp"]["no_dollars"] = []
    assert O.parse_kalshi("E0", fx["event"], books, 1) is None
    assert O._kalshi_mid({"orderbook": {"yes": [[70, 10], [72, 5]], "no": [[27, 3], [20, 9]]}}) == pytest.approx(0.725)
    assert O._kalshi_mid({"orderbook": {"yes": [[70, 10]], "no": None}}) is None


def test_kalshi_client_uses_fetch_and_records_raw(tmp_path):
    fx = load("kalshi_event.json")
    calls = []

    def fetch(url, params, headers):
        calls.append(url)
        if url.endswith("/events"):
            return {"events": [fx["event"]]} if params["series_ticker"] == "KXEPLGAME" else {"events": []}
        return fx["books"][url.split("/markets/")[1].split("/")[0]]

    r = O.kalshi_snapshots(fetch=fetch, raw_dir=tmp_path)
    assert r["ok"] and len(r["snapshots"]) == 1 and r["snapshots"][0]["event_key"] == EK
    assert len(calls) == 5 + 3 and len(raw_text(tmp_path).splitlines()) == 8

# ---------------------------------------------------------------- A2 football-data closing


def fd_row(**kw):
    r = {"league": "E0", "season": "2024/25", "Date": pd.Timestamp("2024-12-26"), "Time": "15:00", "HomeTeam": "Man United",
         "AwayTeam": "Nott'm Forest", "PSH": 2.0, "PSD": 3.5, "PSA": 4.0, "PSCH": 1.9, "PSCD": 3.6, "PSCA": 4.4,
         "BFEH": 2.0, "BFED": 3.5, "BFEA": 4.0, "BFECH": 1.95, "BFECD": 3.7, "BFECA": 4.5,
         "AvgH": 2.0, "AvgD": 3.4, "AvgA": 3.9, "AvgCH": 1.9, "AvgCD": 3.5, "AvgCA": 4.2}
    r.update(kw)
    return r


def test_closing_priority_and_close_equal_open_is_missing():
    nan = float("nan")
    df = pd.DataFrame([
        fd_row(),                                                          # PSC present -> PSC
        fd_row(PSCH=2.0, PSCD=3.5, PSCA=4.0),                              # PSC == PS on all three -> BFEC
        fd_row(PSCH=2.0, PSCD=3.5, PSCA=4.1),                              # differs on one outcome -> still PSC
        fd_row(PSCH=nan, PSCD=nan, PSCA=nan, BFECH=2.0, BFECD=3.5, BFECA=4.0),  # no PSC, BFEC == BFE -> AvgC
        fd_row(PSCH=nan, BFECH=nan, AvgCH=2.0, AvgCD=3.4, AvgCA=3.9),      # every family missing or == open -> none
    ])
    out = O.closing_odds(df)
    assert [s["book"] for s in out] == ["PSC", "BFEC", "PSC", "AvgC"]
    assert out[0]["odds"] == {"H": 1.9, "D": 3.6, "A": 4.4} and out[1]["odds"] == {"H": 1.95, "D": 3.7, "A": 4.5}
    assert out[0]["event_key"] == "E0:man united:nott m forest:2024-12-26" and out[0]["source"] == "football-data"
    assert out[0]["start_ms"] == ms("2024-12-26T15:00:00Z")  # UK local == UTC in winter
    assert O.closing_odds(pd.DataFrame([fd_row(Date=pd.Timestamp("2025-08-16"), Time="12:30")]))[0]["start_ms"] == \
        ms("2025-08-16T11:30:00Z")  # BST


def test_closing_on_real_parquet_never_psc_for_2026_27():
    df = pd.read_parquet(O.PARQUET)
    cur = O.closing_odds(df[df["season"] == "2026/27"])
    assert len(cur) > 200 and all(s["book"] != "PSC" for s in cur)
    old = O.closing_odds(df[(df["season"] == "2024/25") & (df["league"] == "E0")])
    assert sum(s["book"] == "PSC" for s in old) > 300

# ---------------------------------------------------------------- A3 SportsGameOdds and odds-api.io


def test_sgo_and_oddsapi_fixtures_parse():
    s = O.parse_sgo(load("sgo_events_mock.json"), "E0", 5)
    assert len(s) == 1  # second event: pinnacle draw unavailable
    assert s[0]["odds"] == {"H": 1.4, "D": 5.0, "A": 8.5} and s[0]["book"] == "pinnacle" and s[0]["source"] == "sgo"
    assert s[0]["event_key"] == EK and s[0]["obs_ms"] == ms("2026-10-09T11:01:00Z") and s[0]["start_ms"] == START
    oa = O.parse_oddsapi(load("oddsapi_mock.json")["odds"], "E0", 5)
    assert {x["book"]: x["odds"] for x in oa} == {"Bet365": {"H": 1.36, "D": 5.0, "A": 8.5},
                                                   "Unibet": {"H": 1.38, "D": 4.9, "A": 8.0}}
    assert all(x["event_key"] == EK and x["source"] == "odds-api" for x in oa)
    assert O.american_to_decimal("+150") == 2.5 and O.american_to_decimal(-200) == 1.5


def test_no_key_means_error_and_zero_fetch_calls(tmp_path):
    def fetch(*a):
        raise AssertionError("fetch must not be called without a key")
    a = O.sgo_snapshots("E0", 0, 1, fetch=fetch, raw_dir=tmp_path, env={})
    b = O.oddsapi_snapshots("E0", fetch=fetch, raw_dir=tmp_path, env={"OTHER": "x"})
    assert not a["ok"] and "SPORTSGAMEODDS_API_KEY" in a["error"] and not b["ok"] and "ODDS_API_IO_KEY" in b["error"]
    assert not list(tmp_path.rglob("*.jsonl"))


def test_fake_key_never_stored_in_raw_lines(tmp_path):
    key = "FAKEKEY-0123456789abcdef"
    seen = []

    def fetch(url, params, headers):
        seen.append((url, dict(params or {}), dict(headers or {})))
        echo = {"echo_url": f"{url}?apiKey={key}", "echo_header": key}  # worst case: the body echoes the key
        if "sportsgameodds" in url:
            return {**load("sgo_events_mock.json"), **echo}
        if url.endswith("/events"):
            return [{**load("oddsapi_mock.json")["events"][0], **echo}]
        return [{**e, **echo} for e in load("oddsapi_mock.json")["odds"]]

    q = O.Quota(tmp_path / "q.json")
    a = O.sgo_snapshots("E0", 0, 1, limit=5, fetch=fetch, quota=q, raw_dir=tmp_path / "raw",
                        env={"SPORTSGAMEODDS_API_KEY": key})
    b = O.oddsapi_snapshots("E0", fetch=fetch, quota=q, raw_dir=tmp_path / "raw", env={"ODDS_API_IO_KEY": key})
    assert a["ok"] and len(a["snapshots"]) == 1 and b["ok"] and len(b["snapshots"]) == 2
    assert seen[0][2] == {"X-Api-Key": key} and seen[1][1]["apiKey"] == key  # the key was used ...
    text = raw_text(tmp_path / "raw")
    assert len(text.splitlines()) == 3 and key not in text  # ... and never stored
    assert all("apiKey" not in json.loads(line)["params"] for line in text.splitlines())
    assert q.used("sgo") == 5 and q.used("odds-api") == 2

    def boom(url, params, headers):
        raise RuntimeError(f"401 for url {url}?apiKey={key}")
    c = O.oddsapi_snapshots("E0", fetch=boom, raw_dir=tmp_path / "raw", env={"ODDS_API_IO_KEY": key})
    assert not c["ok"] and key not in c["error"]

# ---------------------------------------------------------------- A4 snapshot schedule


def labels(now, done=(), lineup=None):
    return [d["label"] for d in O.due(START, lineup, set(done), now)]


def test_schedule_each_label_once_at_its_time():
    lineup = START - 75 * MIN
    assert labels(START - 24 * H - 1, lineup=lineup) == []
    assert labels(START - 24 * H, lineup=lineup) == ["T-24h"]
    assert labels(START - 20 * H, {"T-24h"}, lineup) == []
    assert labels(START - 3 * H - 1, {"T-24h"}, lineup) == []
    assert labels(START - 3 * H, {"T-24h"}, lineup) == ["T-3h"]
    assert labels(lineup + 10 * MIN - 1, {"T-24h", "T-3h"}, lineup) == []
    d = O.due(START, lineup, {"T-24h", "T-3h"}, lineup + 10 * MIN)
    assert d == [{"label": "lineup+10m", "due_ms": lineup + 10 * MIN, "lineup_assumed": False}]
    assert labels(START - 1, {"T-24h", "T-3h", "lineup+10m"}, lineup) == []
    assert labels(START, (), lineup) == [] and labels(START + H) == []
    assert labels(START - 2 * H) == ["T-3h"]  # starting late: the overdue T-24h is superseded, not doubled up


def test_schedule_unknown_lineup_assumed_and_flagged():
    assert labels(START - 50 * MIN - 1, {"T-24h", "T-3h"}) == []
    d = O.due(START, None, {"T-24h", "T-3h"}, START - 50 * MIN)
    assert d == [{"label": "lineup+10m", "due_ms": START - 50 * MIN, "lineup_assumed": True}]
    assert O.due(START, None, set(), START - 3 * H)[0]["lineup_assumed"] is False

# ---------------------------------------------------------------- A5 mapping


def crawler_rows():
    return [json.loads(x) for x in (FX / "crawler_rows.jsonl").read_text(encoding="utf-8").splitlines()]


def ev(league, home, away, iso, key=None):
    e = {"league": league, "home": home, "away": away, "start_ms": ms(iso)}
    e["event_key"] = key or O.event_key(league, home, away, e["start_ms"])
    return e


def test_mapping_real_rows_outcomes_event_key_and_flags():
    espn = G.parse_espn(load("espn_eng1_scoreboard.json"), "E0", 1)
    alaves = ev("SP1", "Alavés", "Atlético Madrid", "2026-10-10T14:15:00Z")
    maps, unmapped = O.map_markets(crawler_rows(), espn + [alaves])
    assert unmapped == [] and len(maps) == 6
    by = {(m["event_key"], m["outcome"]): m for m in maps}
    h = by[(EK, "H")]
    assert h["cid"] == "0x9f1a28479d9a01e771994b2aa667e574140e26f2720030fae2ce8f9019fc8f6f"
    assert h["home"] == "Arsenal FC" and h["away"] == "Leeds United FC" and h["start_ms"] == START and h["league"] == "E0"
    assert by[(EK, "A")]["cid"].startswith("0xce4511") and by[(EK, "D")]["cid"].startswith("0x42e69c")
    assert set(by) >= {("SP1:alaves:ath madrid:2026-10-10", o) for o in "HDA"}
    assert h["rule_flags"] == ["postponed_open_until_completed", "cancelled_resolves_no", "regulation_90_plus_stoppage"]
    assert "cancelled_resolves_yes" in by[(EK, "D")]["rule_flags"]
    assert {"cid", "token_yes", "token_no", "event_key", "league", "home", "away", "outcome", "start_ms",
            "rule_flags"} == set(h)


@pytest.mark.parametrize("events,reason", [
    ([ev("E0", "Arsenal", "Leeds United", "2026-10-10T13:30:00Z")], "no candidate"),          # kickoff 2 h off
    ([ev("E0", "Arsenal", "Leicester City", "2026-10-10T11:30:00Z")], "no candidate"),        # team mismatch
    ([ev("E0", "Leeds United", "Arsenal", "2026-10-10T11:30:00Z")], "no candidate"),          # home/away swapped
    ([ev("E0", "Arsenal", "Leeds United", "2026-10-10T11:30:00Z"),
      ev("E0", "Arsenal", "Leeds", "2026-10-10T11:40:00Z", key="E0:arsenal:leeds:2026-10-11")], "2 candidates"),
])
def test_mapping_refuses_to_guess(events, reason):
    rows = [r for r in crawler_rows() if r["event_slug"].startswith("epl")]
    maps, unmapped = O.map_markets(rows, events)
    assert maps == [] and unmapped == [{"event_slug": "epl-ars-lee-2026-10-10", "reason": reason}]
    ok, _ = O.map_markets(rows, [ev("E0", "Arsenal", "Leeds United", "2026-10-10T11:44:00Z")])  # within 15 min
    assert len(ok) == 3


def test_team_names_normalize_across_sources():
    groups = [("Manchester United FC", "Manchester United", "Man United"), ("1. FC Köln", "FC Cologne", "FC Koln"),
              ("Paris Saint-Germain FC", "PSG", "Paris SG"), ("RC Deportivo A Coruña", "Deportivo", "La Coruna"),
              ("Athletic Club", "Bilbao", "Ath Bilbao"), ("FC Internazionale Milano", "Internazionale", "Inter"),
              ("Borussia Mönchengladbach", "M'gladbach", "M'gladbach"), ("Stade Brestois 29", "Stade Brest 29", "Brest")]
    for g in groups:
        assert len({O.norm_team(n) for n in g}) == 1, g
    assert O.norm_team("Paris FC") != O.norm_team("Paris Saint-Germain FC")

# ---------------------------------------------------------------- A6 quota


def test_quota_thresholds_and_persistence(tmp_path):
    p, limits = tmp_path / "quota.json", {"sgo": (10, "month"), "odds-api": (10, "day")}
    q, t = O.Quota(p, limits), ms("2026-10-15T12:00:00Z")
    assert all(q.take("sgo", now_ms=t) for _ in range(8))
    assert not q.take("sgo", now_ms=t)                          # routine refused at 80%
    assert q.take("sgo", priority="news", now_ms=t) and q.take("sgo", priority="news", now_ms=t)
    assert not q.take("sgo", priority="news", now_ms=t)         # 100%: everything refused
    q2 = O.Quota(p, limits)                                      # a second instance on the same file
    assert q2.used("sgo", t) == 10 and not q2.take("sgo", now_ms=t) and not q2.take("sgo", priority="news", now_ms=t)
    assert not q2.take("odds-api", units=9, now_ms=t) and q2.take("odds-api", units=8, now_ms=t)
    assert q.used("odds-api", t) == 8 and q.used("odds-api", t + 24 * H) == 0   # daily period
    assert q2.take("sgo", now_ms=ms("2026-11-01T00:00:00Z"))   # monthly period resets


def test_quota_cli_report(tmp_path):
    out = tmp_path / "q.md"
    O.main(["quota", "--out", str(out)])
    text = out.read_text(encoding="utf-8")
    assert "| League | Peak month | Fixtures | Projected units | Cumulative share of quota | Enabled |" in text
    for lg in O.LEAGUES:
        assert f"| {lg} | " in text
    assert "## Assumptions" in text and text.rstrip().endswith("```") and "## How to reproduce" in text.splitlines()[-5]


def test_quota_projection_stops_at_first_overflow():
    df = pd.DataFrame({"league": ["E0"] * 60 + ["SP1"] * 40 + ["D1"] * 5, "season": "2024/25",
                       "Date": pd.to_datetime(["2024-12-01"] * 105)})
    rows = O.project_quota(df, monthly_quota=500, per_event=3, priority=("E0", "SP1", "D1"), seasons=("2024/25",))
    assert [(r["units"], r["enabled"]) for r in rows] == [(180, True), (120, True), (15, True)]
    rows = O.project_quota(df, monthly_quota=300, per_event=3, priority=("E0", "SP1", "D1"), seasons=("2024/25",))
    assert [r["enabled"] for r in rows] == [True, False, False] and rows[0]["cum_share"] == pytest.approx(0.6)

# ---------------------------------------------------------------- A7 game state and cancel rule


def test_espn_and_ws_fixtures_parse():
    st = G.parse_espn(load("espn_eng1_scoreboard.json"), "E0", 77)
    assert len(st) == 6 and st[0] == {"source": "espn", "league": "E0", "event_key": EK, "home": "Arsenal",
                                      "away": "Leeds United", "scheduled_start_ms": START, "status": "scheduled",
                                      "obs_ms": 77, "recv_ms": 77}
    fx = load("espn_eng1_scoreboard.json")
    fx["events"][0]["status"]["type"].update(name="STATUS_POSTPONED", state="post")
    fx["events"][1]["status"]["type"].update(name="STATUS_SOMETHING_NEW", state="in")
    st = G.parse_espn(fx, "E0", 1)
    assert st[0]["status"] == "postponed" and st[1]["status"] == "in_progress"
    ws = load("ws_messages.json")
    recv = ms("2026-10-10T11:20:00Z")
    assert [G.parse_ws(m, recv) for m in ws["captured"]] == [None, None, None]  # not our leagues
    a, b, c = (G.parse_ws(m, recv) for m in ws["soccer_shaped"])
    assert a["event_key"] == EK and a["status"] == "in_progress" and a["scheduled_start_ms"] is None
    assert b["event_key"] == "SP1:alaves:ath madrid:2026-10-10" and b["status"] == "postponed"
    assert c["status"] == "final" and G.parse_ws({"leagueAbbreviation": "epl", "homeTeam": "A", "awayTeam": "B",
                                                  "status": "weird", "live": False}, 1)["status"] == "suspended"


def test_feed_age_under_sports(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "LAST_RECV", {})
    assert G.feed_age_ms(10) == {}
    st = G.poll_espn("E0", fetch=lambda u, p, h: load("espn_eng1_scoreboard.json"), raw_dir=tmp_path)
    assert len(st) == 6 and "espn" in raw_text(tmp_path)
    t = G.LAST_RECV["espn"] + 1000
    assert G.feed_age_ms(t) == {"sports:espn": 1000}                 # WS never heard from -> no "sports" (stale)
    assert G.feed_age_ms(t, feeds=("espn",))["sports"] == 1000
    G.LAST_RECV["polymarket-ws"] = G.LAST_RECV["espn"] - 5000
    assert G.feed_age_ms(t) == {"sports": 6000, "sports:espn": 1000, "sports:polymarket-ws": 6000}  # the oldest


def mm(ek, outcome, start=START):
    return {"cid": f"cid-{ek}-{outcome}", "token_yes": "y", "token_no": "n", "event_key": ek, "league": ek.split(":")[0],
            "home": "h", "away": "a", "outcome": outcome, "start_ms": start, "rule_flags": []}


EK2 = "E0:chelsea:bournemouth:2026-10-10"
MAPS = [mm(EK, o) for o in "HDA"] + [mm(EK2, o, START + 150 * MIN) for o in "HDA"]


def gs(status="scheduled", sched=START, recv=None, ek=EK, now=START - H):
    return {"source": "espn", "league": "E0", "event_key": ek, "home": "Arsenal", "away": "Leeds United",
            "scheduled_start_ms": sched, "status": status, "obs_ms": recv or now, "recv_ms": recv or now}


def test_cancel_rule_fires_and_holds():
    now = START - H
    assert G.cancel_signal(gs(), MAPS, now) is None                                  # on-time scheduled game
    assert G.cancel_signal(gs(sched=START + 30_000), MAPS, now) is None              # within 60 s
    s = G.cancel_signal(gs(sched=START - 30 * MIN), MAPS, now)                       # changed start
    assert s == {"event_key": EK, "cids": sorted(m["cid"] for m in MAPS[:3]), "reason": "scheduled start changed",
                 "ts_ms": now}
    assert "in progress before scheduled start" in G.cancel_signal(gs("in_progress"), MAPS, now)["reason"]
    assert G.cancel_signal(gs("in_progress", now=START + MIN), MAPS, START + MIN) is None  # normal in-play
    for st in ("postponed", "delayed", "suspended", "cancelled"):
        assert G.cancel_signal(gs(st), MAPS, now)["reason"] == st
    assert G.cancel_signal(gs(recv=now - 121_000), MAPS, now)["reason"] == "stale game state"
    assert G.cancel_signal(gs(recv=now - 119_000), MAPS, now) is None
    assert G.cancel_signal(gs("postponed", ek="E0:x:y:2026-10-10"), MAPS, now) is None  # no mapped market
    ws_state = {**gs("in_progress"), "scheduled_start_ms": None}                      # WS: no scheduled start
    assert G.cancel_signal(ws_state, MAPS, now)["reason"] == "in progress before scheduled start"

# ---------------------------------------------------------------- A8 early-start drill


class FakeRouter:
    def __init__(self, orders):
        self.orders, self.cancelled = orders, []

    def open_orders(self):
        return [o for o in self.orders if o.order_id not in self.cancelled]

    def cancel(self, order_id, now_ms):
        self.cancelled.append(order_id)

    def submit(self, *a):
        raise AssertionError("no submits in a cancel drill")

    cancel_all = on_book = on_trade = submit


def order(oid, cid, status="open"):
    i = Intent("soccer-maker", cid, "tok-" + cid, "BUY", 0.4, 10, "maker", START - 5 * MIN, 0.42, "quote")
    return Order(oid, i, status)


def test_early_start_drill_cancels_only_that_game():
    orders = [order(f"a{i}", m["cid"]) for i, m in enumerate(MAPS[:3])] + [order("a9", MAPS[0]["cid"], "partial")] + \
             [order(f"b{i}", m["cid"]) for i, m in enumerate(MAPS[3:])] + [order("x1", "cid-other-market")]
    r = FakeRouter(orders)
    now = START - 20 * MIN
    sig = G.cancel_signal(gs("in_progress", now=now), MAPS, now)                     # early kick-off reported
    done = G.cancel_game(sig, r, now)
    assert sorted(done) == ["a0", "a1", "a2", "a9"] and sorted(r.cancelled) == sorted(done)
    assert {o.order_id for o in r.open_orders()} == {"b0", "b1", "b2", "x1"}
