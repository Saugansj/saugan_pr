"""Role 12 game-state-feed (WP4-A): Polymarket sports WebSocket and ESPN soccer scoreboard -> GameState records, the
cancel rule and the early-start cancel through the trader.contracts.Router protocol. Feed age is exposed as "sports"."""
import asyncio
import json
from collections import Counter
import pathlib
from datetime import datetime, timezone

from common import now_ms as _now_ms
from sports import odds

WS_URL = "wss://sports-api.polymarket.com/ws"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/{}/scoreboard"
ESPN_LEAGUES = {"E0": "eng.1", "SP1": "esp.1", "D1": "ger.1", "I1": "ita.1", "F1": "fra.1"}
HALT_STATUSES = {"postponed", "delayed", "suspended", "cancelled"}
_ESPN_STATUS = {
    "STATUS_SCHEDULED": "scheduled", "STATUS_IN_PROGRESS": "in_progress", "STATUS_FIRST_HALF": "in_progress",
    "STATUS_HALFTIME": "in_progress", "STATUS_SECOND_HALF": "in_progress", "STATUS_END_OF_REGULATION": "in_progress",
    "STATUS_OVERTIME": "in_progress", "STATUS_EXTRA_TIME": "in_progress", "STATUS_SHOOTOUT": "in_progress",
    "STATUS_FULL_TIME": "final", "STATUS_FINAL": "final", "STATUS_FINAL_AET": "final", "STATUS_FINAL_PEN": "final",
    "STATUS_POSTPONED": "postponed", "STATUS_DELAYED": "delayed", "STATUS_SUSPENDED": "suspended",
    "STATUS_ABANDONED": "suspended", "STATUS_CANCELED": "cancelled", "STATUS_CANCELLED": "cancelled",
}
_WS_STATUS = {
    "scheduled": "scheduled", "not_started": "scheduled", "notstarted": "scheduled",
    "inprogress": "in_progress", "running": "in_progress", "live": "in_progress", "halftime": "in_progress",
    "break": "in_progress", "finished": "final", "ended": "final", "final": "final", "closed": "final",
    "postponed": "postponed", "delayed": "delayed", "start_delayed": "delayed", "suspended": "suspended",
    "interrupted": "suspended", "abandoned": "suspended", "cancelled": "cancelled", "canceled": "cancelled",
}
LAST_RECV: dict[str, int] = {}  # feed -> last receive ms


def feed_age_ms(now_ms: int, feeds=("espn", "polymarket-ws")) -> dict[str, int]:
    """{"sports:<feed>": each feed's age, "sports": the oldest of `feeds`}. Same convention as trader/marketdata.py's
    "polymarket": a feed never heard from is absent, and "sports" is absent until every one of `feeds` has reported, so
    the kernel sees it stale (fail closed). Pass feeds=("espn",) when the WS is not run."""
    ages = {f"sports:{k}": now_ms - v for k, v in LAST_RECV.items()}
    if feeds and all(f"sports:{f}" in ages for f in feeds):
        ages["sports"] = max(ages[f"sports:{f}"] for f in feeds)
    return ages


def _state(source, league, home, away, sched, status, obs, recv, start_for_key):
    return {"source": source, "league": league, "event_key": odds.event_key(league, home, away, start_for_key),
            "home": home, "away": away, "scheduled_start_ms": sched, "status": status, "obs_ms": obs, "recv_ms": recv}


def parse_espn(payload: dict, league: str, recv_ms: int) -> list[dict]:
    out = []
    for e in payload.get("events") or []:
        teams = {c["homeAway"]: c["team"]["displayName"] for c in e["competitions"][0]["competitors"]}
        st = e["status"]["type"]
        status = _ESPN_STATUS.get(st.get("name")) or {"pre": "scheduled", "in": "in_progress", "post": "final"}.get(
            st.get("state"), "suspended")  # an unknown status fails closed (cancels)
        sched = odds.iso_ms(e["date"])
        out.append(_state("espn", league, teams["home"], teams["away"], sched, status, recv_ms, recv_ms, sched))
    return out


def parse_ws(msg: dict, recv_ms: int) -> dict | None:
    """One Polymarket sports WS message -> GameState for our leagues, else None. The feed carries no scheduled start, so
    scheduled_start_ms is None and the event_key date is the receive date."""
    # ponytail: receive-date key mismatches a game that crosses UTC midnight; join on maps by teams if leagues kick off late
    league = odds.PM_LEAGUES.get((msg.get("leagueAbbreviation") or "").lower())
    if not league or not msg.get("homeTeam") or not msg.get("awayTeam"):
        return None
    raw = (msg.get("status") or "").lower()
    status = _WS_STATUS.get(raw) or ("final" if msg.get("ended") else "in_progress" if msg.get("live") else
                                     "suspended" if raw else "scheduled")  # unknown status string fails closed
    if msg.get("ended") and status not in HALT_STATUSES:
        status = "final"
    return _state("polymarket-ws", league, msg["homeTeam"], msg["awayTeam"], None, status, recv_ms, recv_ms, recv_ms)


def poll_espn(league, fetch=odds.http_get, raw_dir=odds.RAW, date=None) -> list[dict]:
    """One scoreboard GET (optionally for a YYYYMMDD date) -> GameState list; marks the espn feed fresh."""
    body, recv = odds.get_raw("espn", ESPN.format(ESPN_LEAGUES[league]), {"dates": date} if date else None, fetch, raw_dir)
    LAST_RECV["espn"] = recv
    return parse_espn(body, league, recv)


async def listen_ws(seconds, on_state, raw_dir=odds.RAW, url=WS_URL) -> int:
    """Record the sports WS for `seconds`; every message marks the feed fresh, our leagues' states go to on_state."""
    import websockets
    n, end = 0, asyncio.get_running_loop().time() + seconds
    raw = pathlib.Path(raw_dir) / "polymarket-sports"
    raw.mkdir(parents=True, exist_ok=True)
    async with websockets.connect(url, open_timeout=15) as ws:
        while (left := end - asyncio.get_running_loop().time()) > 0:
            try:
                m = await asyncio.wait_for(ws.recv(), left)
            except asyncio.TimeoutError:
                break
            recv = _now_ms()
            LAST_RECV["polymarket-ws"], n = recv, n + 1
            with (raw / f"{odds.utc_date(recv)}.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps({"t": recv, "raw": m}) + "\n")
            try:
                gs = parse_ws(json.loads(m), recv)
            except (ValueError, AttributeError):
                continue
            if gs:
                on_state(gs)
    return n

# ---------------------------------------------------------------- cancel rule


def cancel_signal(game_state: dict, maps: list[dict], now_ms: int, stale_ms: int = 120_000) -> dict | None:
    ms = [m for m in maps if m["event_key"] == game_state["event_key"]]
    if not ms:
        return None
    sched, reasons = game_state.get("scheduled_start_ms"), []
    if sched is not None and any(abs(sched - m["start_ms"]) > 60_000 for m in ms):
        reasons.append("scheduled start changed")
    if game_state["status"] == "in_progress" and now_ms < max([m["start_ms"] for m in ms] + [sched or 0]):
        reasons.append("in progress before scheduled start")
    if game_state["status"] in HALT_STATUSES:
        reasons.append(game_state["status"])
    if now_ms - game_state["recv_ms"] > stale_ms:
        reasons.append("stale game state")
    if not reasons:
        return None
    return {"event_key": game_state["event_key"], "cids": sorted({m["cid"] for m in ms}), "reason": "; ".join(reasons),
            "ts_ms": now_ms}


def cancel_game(signal: dict, router, now_ms: int) -> list[str]:
    """Cancel every open order whose intent.cid is in the signal's cids, and nothing else. Returns the cancelled ids."""
    cids, done = set(signal["cids"]), []
    for o in router.open_orders():
        if o.intent.cid in cids and o.status in ("journaled", "open", "partial", "unknown"):
            router.cancel(o.order_id, now_ms)
            done.append(o.order_id)
    return done

# ---------------------------------------------------------------- smoke run (public GETs and the public WS only)


def smoke(ws_seconds=75, out=odds.REPORTS / "phase4_sports_smoke.md", raw_dir=odds.RAW):
    started = _now_ms()
    res = {}
    k = odds.kalshi_snapshots(raw_dir=raw_dir)
    res["kalshi"] = k
    states, espn_err = [], []
    snap = sorted(odds.DATA.glob("markets/*Z.jsonl"))[-1]
    rows = [json.loads(line) for line in snap.read_text(encoding="utf-8").splitlines()]
    sp = [r for r in rows if r.get("mode") == "sports-pregame"]
    dates = sorted({r["event_start_time"][:10].replace("-", "") for r in sp if r.get("event_start_time")})
    for lg in odds.LEAGUES:
        for d in [None] + dates:
            try:
                states += poll_espn(lg, raw_dir=raw_dir, date=d)
            except Exception as ex:
                espn_err.append(f"{lg} {d or 'today'}: {type(ex).__name__}: {ex}")
    espn_games = {s["event_key"]: s for s in states}
    ws_states, ws_err = [], None
    try:
        ws_n = asyncio.run(listen_ws(ws_seconds, ws_states.append, raw_dir))
    except Exception as ex:
        ws_n, ws_err = 0, f"{type(ex).__name__}: {ex}"
    ws_end = _now_ms()
    events = list(espn_games.values()) + k["snapshots"]
    maps, unmapped = odds.map_markets(sp, events)
    maps_k, unmapped_k = odds.map_markets(sp, k["snapshots"])
    signals = [s for g in espn_games.values() if (s := cancel_signal(g, maps, ws_end))]
    n_ev = len({r["event_slug"] for r in sp})
    outcomes = {o: sum(m["outcome"] == o for m in maps) for o in "HDA"}
    flags = sorted({f for m in maps for f in m["rule_flags"]})
    fmt = lambda ms: datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# Phase 4 sports smoke run (WP4-A)", "",
        f"Run {fmt(started)} to {fmt(ws_end)}. Public GETs and the public sports WebSocket only; no keys, no orders.", "",
        "## Counts per source", "",
        "| Source | Result | Count | Note |", "|---|---|---|---|",
        f"| Kalshi soccer game events (5 series) | {'ok' if k['ok'] else 'partial/unreachable'} | "
        f"{len(k['snapshots'])} OddsSnapshot (probs) | {k['error'] or 'books read for every outcome market'} |",
        f"| ESPN scoreboard (5 leagues, today + {len(dates)} crawler dates) | {'ok' if not espn_err else 'partial'} | "
        f"{len(espn_games)} games | {'; '.join(espn_err) or 'statuses: ' + json.dumps(Counter(s['status'] for s in espn_games.values()))} |",
        f"| Polymarket sports WebSocket ({ws_seconds} s) | {'ok' if ws_err is None else 'unreachable'} | {ws_n} messages, "
        f"{len(ws_states)} for our 5 leagues | {ws_err or 'leagues seen: ' + json.dumps(_ws_leagues(raw_dir, started))} |",
        f"| SportsGameOdds | not run | 0 | no SPORTSGAMEODDS_API_KEY on this machine ([ops] A11) |",
        f"| odds-api.io | not run | 0 | no ODDS_API_IO_KEY on this machine ([ops] A11) |", "",
        "## Market mapping", "",
        f"Crawler snapshot `{snap.name}`: {len(sp)} sports-pregame rows in {n_ev} events.", "",
        "| Matched against | Mapped markets | Mapped events | Unmapped events |", "|---|---|---|---|",
        f"| ESPN games + Kalshi events | {len(maps)} | {len({m['event_key'] for m in maps})} | {len(unmapped)} |",
        f"| Kalshi events only | {len(maps_k)} | {len({m['event_key'] for m in maps_k})} | {len(unmapped_k)} |", "",
        f"Outcomes of mapped markets: {json.dumps(outcomes)}. Rule flags seen: {', '.join(flags) or 'none'}.", "",
        "Unmapped events (ESPN + Kalshi): " + (", ".join(f"{u['event_slug']} ({u['reason']})" for u in unmapped) or "none") + ".",
        "", f"Cancel rule on the ESPN states at {fmt(ws_end)}: {len(signals)} signals"
        + (": " + "; ".join(f"{s['event_key']} ({s['reason']})" for s in signals[:10]) if signals else "") + ".", "",
        "Sample mapped markets:", "", "| cid | event_key | outcome | start | rule_flags |", "|---|---|---|---|---|",
    ]
    lines += [f"| {m['cid'][:12]}… | {m['event_key']} | {m['outcome']} | {fmt(m['start_ms'])} | {', '.join(m['rule_flags'])} |"
              for m in maps[:6]]
    lines += ["", "Kalshi sample:", ""] + [f"- {s['event_key']}: {json.dumps(s['probs'])} (sum {sum(s['probs'].values()):.3f})"
                                           for s in k["snapshots"][:5]]
    lines += ["", f"Raw responses: `{pathlib.Path(raw_dir).as_posix()}/<source>/<date>.jsonl` (kalshi, espn, polymarket-sports).",
              "", "## How to reproduce", "", "```", f".venv\\Scripts\\python.exe -m sports.odds smoke --ws-seconds {ws_seconds}",
              "```", ""]
    pathlib.Path(out).write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


def _ws_leagues(raw_dir, since_ms):
    p = pathlib.Path(raw_dir) / "polymarket-sports" / f"{odds.utc_date(_now_ms())}.jsonl"
    rows = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []
    return Counter(json.loads(r["raw"]).get("leagueAbbreviation") for r in rows if r["t"] >= since_ms and r["raw"][:1] == "{")
