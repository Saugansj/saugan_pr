"""WP0-A tests: crawler hashing/diff/modes, recorder path + reconnect, compaction, shed rule, gapcheck, ops files."""
import asyncio
import datetime as dt
import json
import pathlib
import re

import duckdb
import websockets

from common import sha256_text
from recorder import compact, crawler, gapcheck, recorder

OPS = pathlib.Path(__file__).resolve().parent.parent / "ops"


def row(cid, rules="Resolves YES if ...", tick=0.01, **kw):
    return {"condition_id": cid, "market_slug": cid, "rules_text": rules, "rules_sha256": sha256_text(rules),
            "tick_size": tick, **kw}


def test_mode_of_slug():
    assert crawler.mode_of("bitcoin-above-on-october-2-2026") == "crypto-term"
    assert crawler.mode_of("ethereum-up-or-down-on-october-1-2026") == "crypto-term"
    assert crawler.mode_of("bitcoin-up-or-down-october-1-2026-10am-et") == "crypto-hourly"
    assert crawler.mode_of("btc-updown-5m-1790863200") == "crypto-fast"
    assert crawler.mode_of("eth-updown-15m-1790863200") == "crypto-fast"
    for other in ("bitcoin-above-on-september-30-2026-11am-et",  # hourly strike ladder: not a target mode
                  "btc-updown-4h-1790769600", "solana-up-or-down-on-october-1-2026", "bitcoin-price-on-october-2-2026"):
        assert crawler.mode_of(other) is None


def test_build_row_hashes_verbatim_rules_and_reads_clob_fields():
    rules = 'This market will resolve to "Up" if ...\n\nThe resolution source is Binance.'
    gm = {"conditionId": "0xc", "description": rules, "clobTokenIds": '["1", "2"]', "outcomes": '["Up", "Down"]',
          "orderPriceMinTickSize": 0.01, "orderMinSize": 5, "negRisk": False, "rewardsMinSize": 50}
    clob = {"tokens": [{"token_id": "1", "outcome": "Up"}, {"token_id": "2", "outcome": "Down"}],
            "minimum_tick_size": 0.001, "minimum_order_size": 5, "neg_risk": False, "seconds_delay": 0,
            "rewards": {"rates": [{"rewards_daily_rate": 20}, {"rewards_daily_rate": 5}], "min_size": 20, "max_spread": 3.5}}
    r = crawler.build_row("crypto-term", {"slug": "e", "negRiskAugmented": False}, gm, clob, "stamp")
    assert r["rules_text"] == rules and r["rules_sha256"] == sha256_text(rules)
    assert (r["yes_token_id"], r["no_token_id"], r["outcomes"]) == ("1", "2", ["Up", "Down"])
    assert r["tick_size"] == 0.001  # CLOB wins over Gamma
    assert (r["reward_daily_rate"], r["reward_min_size"], r["reward_max_spread"]) == (25.0, 20, 3.5)
    no_clob = crawler.build_row("crypto-term", {"slug": "e"}, gm, None, "stamp")
    assert no_clob["tick_size"] == 0.01 and no_clob["yes_token_id"] == "1" and no_clob["reward_daily_rate"] is None
    no_pool = crawler.build_row("crypto-term", {"slug": "e"}, gm, {**clob, "rewards": {"rates": None}}, "stamp")
    assert no_pool["reward_daily_rate"] == 0.0


def test_snapshot_diff_detects_rules_hash_and_tick_changes(tmp_path):
    expired, kept = tmp_path / "2026-08-30T230000Z.jsonl", tmp_path / "2026-08-31T000000Z.jsonl"
    expired.write_text(""), kept.write_text("")
    crawler.save([row("a"), row("b"), row("c")], "2026-09-30T100000Z", tmp_path)
    assert not expired.exists() and kept.exists()  # 30-day retention
    path, changes = crawler.save([row("a"), row("b", rules="Resolves YES if ... (clarified)"), row("c", tick=0.001),
                                  row("d")], "2026-09-30T110000Z", tmp_path)
    assert path.name == "2026-09-30T110000Z.jsonl" and len(crawler.read_snapshot(path)) == 4
    assert {(c["condition_id"], c["field"]) for c in changes} == {("b", "rules_sha256"), ("c", "tick_size")}
    logged = [json.loads(line) for line in (tmp_path / "changes.jsonl").read_text().splitlines()]
    assert len(logged) == 2 and all(c["previous"] == "2026-09-30T100000Z" for c in logged)
    assert crawler.latest_snapshot(tmp_path) == path and not list(tmp_path.glob("*.tmp"))


def test_path_for_hourly_utc_scheme(tmp_path):
    t = int(dt.datetime(2026, 9, 30, 23, 59, 59, tzinfo=dt.timezone.utc).timestamp() * 1000)
    assert recorder.path_for("crypto-term", t, tmp_path) == tmp_path / "crypto-term" / "2026-09-30" / "23.jsonl"
    assert recorder.path_for("crypto-term", t + 1000, tmp_path).parts[-2:] == ("2026-10-01", "00.jsonl")


def test_token_sets_respects_shed():
    rows = [{"mode": "crypto-term", "yes_token_id": "1", "no_token_id": "2"},
            {"mode": "sports-pregame", "yes_token_id": "3", "no_token_id": "4"}]
    sets = recorder.token_sets(rows, ("crypto-term", "sports-pregame"), shed=["sports-pregame"])
    assert sets == {"crypto-term": frozenset({"1", "2"}), "sports-pregame": frozenset()}


def test_reconnect_after_disconnect_resumes_writing_and_shed_stops_it(tmp_path):
    """A local server drops the first connection after 2 messages; the recorder must reconnect and keep writing.
    Then compact.shed() lists the stream in shed.json: the recorder must close the connection and its file."""
    connections, closed = [], []

    async def handler(ws):
        connections.append(json.loads(await ws.recv()))  # the subscribe message
        n = len(connections)
        for i in range(2):
            await ws.send(f'{{"conn":{n},"i":{i}}}')
        if n == 1:
            await ws.close()  # simulated disconnect
        else:
            await ws.wait_closed()
            closed.append(n)

    async def main():
        async with websockets.serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            subs = {"crypto-term": frozenset({"tok1", "tok2"})}
            task = asyncio.create_task(recorder.ws_stream("crypto-term", subs, tmp_path, f"ws://127.0.0.1:{port}",
                                                          ping_every=0.2))
            for _ in range(100):
                await asyncio.sleep(0.1)
                lines = [json.loads(x) for f in tmp_path.rglob("*.jsonl") for x in f.read_text().splitlines()]
                if sum('"conn":2' in x["raw"] for x in lines) == 2:
                    break
            (tmp_path / "shed.json").write_text('["crypto-term"]')
            for _ in range(50):
                await asyncio.sleep(0.1)
                if closed and (tmp_path, "crypto-term") not in recorder._files:
                    break
            task.cancel()
            return lines

    lines = asyncio.run(main())
    raws = [x["raw"] for x in lines if x["raw"] != "PONG"]
    assert raws == ['{"conn":1,"i":0}', '{"conn":1,"i":1}', '{"conn":2,"i":0}', '{"conn":2,"i":1}']
    assert all(isinstance(x["t"], int) and x["t"] > 1.7e12 for x in lines)
    assert len(connections) == 2 and connections[1]["assets_ids"] == ["tok1", "tok2"]
    assert closed == [2] and (tmp_path, "crypto-term") not in recorder._files  # shed: closed, no reconnect


def _write_hour(root, stream, day, hour, ts):
    f = root / stream / day / f"{hour:02d}.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("".join(json.dumps({"t": t, "raw": '{"event_type":"book"}'}) + "\n" for t in ts))
    return f


def test_compact_to_parquet_same_row_count_and_skips_open_hour(tmp_path):
    closed = _write_hour(tmp_path, "crypto-term", "2026-09-30", 13, range(1_790_000_000_000, 1_790_000_000_500))
    open_ = _write_hour(tmp_path, "crypto-term", "2026-09-30", 14, [1])
    torn = _write_hour(tmp_path, "crypto-hourly", "2026-09-30", 13, [1])
    fragment = '{"t": 2, "raw": "{\\"event_ty'  # killed mid-write ...
    with torn.open("a") as f:  # ... restarted: the next message lands on the same line; then killed again
        f.write(fragment + json.dumps({"t": 3, "raw": "x"}) + "\n" + json.dumps({"t": 4, "raw": "y"}) + "\n" + fragment)
    blank = _write_hour(tmp_path, "sports-pregame", "2026-09-30", 13, [1])
    blank.write_text(blank.read_text() + "\n")  # DuckDB skips it: counts differ, so the JSONL must stay
    done = compact.compact(tmp_path, now=dt.datetime(2026, 9, 30, 14, 30, tzinfo=dt.timezone.utc))
    assert sorted((pathlib.Path(d[0]).parent.parent.name, *d[1:]) for d in done) == [
        ("crypto-hourly", 4, 4, 2, True), ("crypto-term", 500, 500, 0, True), ("sports-pregame", 2, 1, 0, False)]
    assert not closed.exists() and open_.exists() and not torn.exists() and blank.exists()
    torn_pq = tmp_path / "parquet" / "stream=crypto-hourly" / "date=2026-09-30" / "13.parquet"
    assert duckdb.sql(f"SELECT list(t ORDER BY t) FROM read_parquet('{torn_pq.as_posix()}')").fetchone()[0] == [1, 4, None, None]
    assert torn_pq.with_suffix(".bad.jsonl").read_text().splitlines() == [
        fragment + json.dumps({"t": 3, "raw": "x"}), fragment]  # raw bytes of both NULL rows kept
    pq = tmp_path / "parquet" / "stream=crypto-term" / "date=2026-09-30" / "13.parquet"
    assert duckdb.sql(f"SELECT count(*) FROM read_parquet('{pq.as_posix()}')").fetchone()[0] == 500
    sizes = compact.bytes_per_day(tmp_path)
    assert sizes[("crypto-term", "2026-09-30")]["parquet"] == pq.stat().st_size > 0
    assert sizes[("crypto-term", "2026-09-30")]["jsonl"] == open_.stat().st_size
    assert compact.expire(tmp_path, keep_days=30, today=dt.date(2026, 10, 30)) == []  # 30 days old: kept
    assert len(compact.expire(tmp_path, keep_days=30, today=dt.date(2026, 10, 31))) == 3 and not pq.exists()


def test_shed_drops_lowest_priority_first_at_85_percent(tmp_path):
    for stream, size in (("crypto-term", 400), ("crypto-hourly", 300), ("crypto-fast", 300)):
        (tmp_path / stream / "2026-09-30").mkdir(parents=True)
        (tmp_path / stream / "2026-09-30" / "00.jsonl").write_bytes(b"x" * size)
    assert compact.shed(tmp_path, budget_bytes=1200) == []  # 1000/1200 = 83%: below threshold
    assert compact.shed(tmp_path, budget_bytes=1000) == ["crypto-fast"]  # 100% -> drop lowest; 70% after
    assert not (tmp_path / "crypto-fast").exists() and (tmp_path / "crypto-hourly").exists()
    assert compact.load_shed(tmp_path) == ["crypto-fast"]
    assert compact.shed(tmp_path, budget_bytes=400) == ["crypto-hourly", "crypto-term"]  # skips empty streams, keeps going


def test_gapcheck_flags_synthetic_10_minute_gap(tmp_path):
    day0 = int(dt.datetime(2026, 9, 30, tzinfo=dt.timezone.utc).timestamp() * 1000)
    ts = list(range(day0, day0 + 3_600_000, 10_000))  # a message every 10s for an hour ...
    ts = [t for t in ts if not day0 + 1_200_000 <= t < day0 + 1_800_000]  # ... minus 20:00-30:00
    f = _write_hour(tmp_path, "crypto-term", "2026-09-30", 0, ts)
    f.write_text(f.read_text() + '{"t": 5, "raw": "{\\"event_ty')  # torn last line
    markets = tmp_path / "markets"
    res = gapcheck.check("2026-09-30", tmp_path, gap_minutes=5, now_ms=day0 + 3_600_000, markets=markets)
    assert res["crypto-term"]["gaps"] == [(day0 + 1_190_000, day0 + 1_800_000)]
    compact.compact(tmp_path, now=dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc))  # same answer from Parquet (NULL row)
    assert gapcheck.check("2026-09-30", tmp_path, 5, day0 + 3_600_000, markets)["crypto-term"]["gaps"] == res["crypto-term"]["gaps"]
    assert gapcheck.check("2026-09-30", tmp_path, 11, day0 + 3_600_000, markets)["crypto-term"]["gaps"] == []  # 10m10s < 11


def test_gapcheck_flags_expected_streams_with_no_data(tmp_path):
    day0 = int(dt.datetime(2026, 9, 30, tzinfo=dt.timezone.utc).timestamp() * 1000)
    markets, whole_day = tmp_path / "markets", [(day0, day0 + 86_400_000)]
    # a day with no data and no snapshot at all: Deribit is always expected, so it is two full-day gaps
    assert gapcheck.check("2026-09-30", tmp_path, 5, day0 + 86_400_000, markets) == {
        s: {"messages": 0, "gaps": whole_day} for s in ("deribit-btc", "deribit-eth")}
    # yesterday's last snapshot had crypto-term and sports-pregame markets; only crypto-term recorded today
    crawler.save([{"condition_id": "a", "mode": "crypto-term"}, {"condition_id": "b", "mode": "sports-pregame"}],
                 "2026-09-29T230000Z", markets)
    crawler.save([{"condition_id": "a", "mode": "crypto-term"}], "2026-09-30T100000Z", markets)
    _write_hour(tmp_path, "crypto-term", "2026-09-30", 0, range(day0, day0 + 86_400_000, 60_000))
    (tmp_path / "shed.json").write_text('["deribit-eth"]')  # shed on purpose: not expected
    res = gapcheck.check("2026-09-30", tmp_path, 5, day0 + 86_400_000, markets)
    assert sorted(res) == ["crypto-term", "deribit-btc", "sports-pregame"]
    assert res["crypto-term"]["gaps"] == [] and res["sports-pregame"] == {"messages": 0, "gaps": whole_day}


def test_ops_files():
    unit = (OPS / "roster-recorder.service").read_text()
    assert re.search(r"^Restart=always$", unit, re.M) and re.search(r"^User=recorder$", unit, re.M)
    setup, cron = (OPS / "setup.sh").read_text(), (OPS / "roster.cron").read_text()
    assert all(u in setup for u in ("recorder", "trader", "advisor")) and "chrony" in setup and "rsync" in cron
    for name in ("roster-recorder.service", "setup.sh", "roster.cron"):  # CRLF breaks bash and cron on the VM
        assert b"\r" not in (OPS / name).read_bytes(), name
    for text in (unit, setup, cron):
        assert not re.search(r"(?i)(private[_ ]?key\s*=|api[_-]?secret|passphrase\s*=|0x[0-9a-f]{64}|BEGIN [A-Z ]*PRIVATE KEY)", text)


def test_get_json_retries_resets_during_read_but_not_404(monkeypatch):
    import http.client
    import io
    import urllib.error
    import urllib.request

    import common
    monkeypatch.setattr(common.time, "sleep", lambda s: None)
    calls = []

    def flaky(req, timeout=None):
        calls.append(1)
        if len(calls) == 1:
            raise ConnectionResetError(10054, "forcibly closed")
        if len(calls) == 2:
            raise http.client.RemoteDisconnected("closed without response")
        return io.BytesIO(b'{"ok": 1}')   # BytesIO is a context manager with read()

    monkeypatch.setattr(urllib.request, "urlopen", flaky)
    assert common.get_json("http://x/y") == {"ok": 1} and len(calls) == 3

    import gzip  # Gamma serves big /events pages gzip-only since 12 Nov
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: io.BytesIO(gzip.compress(b'[{"a": 2}]')))
    assert common.get_json("http://x/y") == [{"a": 2}]

    calls.clear()

    def gone(req, timeout=None):
        calls.append(1)
        raise urllib.error.HTTPError("http://x/y", 404, "nf", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", gone)
    try:
        common.get_json("http://x/y")
        assert False, "404 must raise"
    except urllib.error.HTTPError:
        pass
    assert len(calls) == 1
