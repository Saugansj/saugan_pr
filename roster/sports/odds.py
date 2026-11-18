"""Role 11 sports-odds-collector (WP4-A): Kalshi public books, football-data closing lines, SportsGameOdds (Pinnacle) and
odds-api.io clients, the snapshot schedule, Polymarket market mapping, the quota book and the per-league quota projection.

Records are the dispatch-level dicts OddsSnapshot and MarketMap. Records keep each source's display team names; event_key
uses norm_team(). All HTTP goes through one injectable fetch(url, params, headers) -> json. Keys come from env at call
time; no key -> error result and zero fetch calls. Raw responses go to <raw_dir>/<source>/<YYYY-MM-DD>.jsonl with keys
stripped. CLI: python -m sports.odds quota | smoke
"""
import argparse
import json
import os
import pathlib
import re
import time
import unicodedata
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx

from common import DATA, REPORTS, now_ms as _now_ms

RAW = DATA / "sports" / "raw"
QUOTA_FILE = DATA / "sports" / "quota.json"
PARQUET = DATA / "history" / "footballdata" / "matches.parquet"
H_MS, MIN_MS = 3_600_000, 60_000
LEAGUES = ("E0", "SP1", "D1", "I1", "F1")
PM_LEAGUES = {"epl": "E0", "lal": "SP1", "bun": "D1", "sea": "I1", "fl1": "F1"}  # Polymarket sport codes (slug + sports WS)
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_SERIES = {"E0": "KXEPLGAME", "SP1": "KXLALIGAGAME", "D1": "KXBUNDESLIGAGAME", "I1": "KXSERIEAGAME", "F1": "KXLIGUE1GAME"}
SGO = "https://api.sportsgameodds.com/v2/events"
SGO_LEAGUES = {"E0": "EPL", "SP1": "LA_LIGA", "D1": "BUNDESLIGA", "I1": "IT_SERIE_A", "F1": "FR_LIGUE_1"}
SGO_ODDS = {"H": "points-home-reg-ml3way-home", "D": "points-all-reg-ml3way-draw", "A": "points-away-reg-ml3way-away"}
ODDSAPI = "https://api.odds-api.io/v3"
ODDSAPI_LEAGUES = {"E0": "england-premier-league", "SP1": "spain-laliga", "D1": "germany-bundesliga",
                   "I1": "italy-serie-a", "F1": "france-ligue-1"}
ENV_KEYS = {"sgo": "SPORTSGAMEODDS_API_KEY", "odds-api": "ODDS_API_IO_KEY"}
QUOTA_LIMITS = {"sgo": (2500, "month"), "odds-api": (500, "day")}  # units per period; SGO units are events

# ---------------------------------------------------------------- team names and event keys

_STOP = set("fc afc cf cfc acf sc ac as ss ssc us rc rcd bc sv vfb vfl tsg bv fsv ud ca sco osc ogc aj es calcio club de".split())
# normalized variant -> canonical (football-data's name, normalized). Seen across Polymarket, ESPN, Kalshi on 2026-10-01.
_ALIASES = {
    "brighton hove albion": "brighton", "coventry city": "coventry", "hull city": "hull", "ipswich town": "ipswich",
    "leeds united": "leeds", "manchester city": "man city", "manchester united": "man united",
    "newcastle united": "newcastle", "nottingham forest": "nott m forest", "tottenham hotspur": "tottenham",
    "west ham united": "west ham", "wolverhampton wanderers": "wolves",
    "deportivo alaves": "alaves", "athletic": "ath bilbao", "athletic bilbao": "ath bilbao", "bilbao": "ath bilbao",
    "atletico madrid": "ath madrid", "atletico": "ath madrid", "real betis": "betis", "real betis balompie": "betis",
    "celta vigo": "celta", "espanyol": "espanol", "espanyol barcelona": "espanol", "deportivo": "la coruna",
    "deportivo a coruna": "la coruna", "deportivo la coruna": "la coruna", "racing santander": "santander",
    "real racing": "santander", "rayo vallecano": "vallecano", "rayo vallecano madrid": "vallecano",
    "real sociedad": "sociedad", "real sociedad futbol": "sociedad", "real oviedo": "oviedo",
    "borussia dortmund": "dortmund", "borussia monchengladbach": "m gladbach", "monchengladbach": "m gladbach",
    "cologne": "koln", "eintracht frankfurt": "ein frankfurt", "frankfurt": "ein frankfurt", "bremen": "werder bremen",
    "hamburger": "hamburg", "leipzig": "rb leipzig", "bayer leverkusen": "leverkusen", "bayern munchen": "bayern munich",
    "internazionale": "inter", "internazionale milano": "inter", "hellas verona": "verona",
    "racing lens": "lens", "olympique lyonnais": "lyon", "olympique marseille": "marseille",
    "paris saint germain": "paris sg", "psg": "paris sg", "stade rennais": "rennes", "strasbourg alsace": "strasbourg",
    "stade brestois": "brest", "stade brest": "brest",
}


def norm_team(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = " ".join(t for t in re.sub(r"[^a-z0-9]+", " ", s).split() if t not in _STOP and not t.isdigit())
    return _ALIASES.get(s, s)


def utc_date(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d")


def iso_ms(s: str | None) -> int | None:
    if not s:
        return None
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)


def event_key(league: str, home: str, away: str, start_ms: int) -> str:
    return f"{league}:{norm_team(home)}:{norm_team(away)}:{utc_date(start_ms)}"


def snapshot(source, book, league, home, away, start_ms, obs_ms, recv_ms, odds=None, probs=None) -> dict:
    s = {"source": source, "book": book, "league": league, "event_key": event_key(league, home, away, start_ms),
         "home": home, "away": away, "start_ms": start_ms, "obs_ms": obs_ms, "recv_ms": recv_ms}
    s.update({"odds": odds} if odds is not None else {"probs": probs})
    return s

# ---------------------------------------------------------------- HTTP and raw recording

_client = None


def http_get(url, params=None, headers=None, retries=4):
    """Default fetch: public GET via httpx (urllib is refused by ESPN). Retries transport errors, 429 and 5xx."""
    global _client
    _client = _client or httpx.Client(timeout=20, headers={"User-Agent": "roster/0.1"}, follow_redirects=True)
    for i in range(retries):
        try:
            r = _client.get(url, params=params, headers=headers)
            if r.status_code != 429 and r.status_code < 500:
                r.raise_for_status()
                return r.json()
            err = httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
        except httpx.TransportError as e:
            err = e
        if i == retries - 1:
            raise err
        time.sleep(2 ** i)


def _scrub(text: str, secrets) -> str:
    for s in secrets:
        if s:
            text = text.replace(s, "***")
    return text


def get_raw(source, url, params, fetch, raw_dir, headers=None, secret=None, secret_params=()):
    """fetch() and append {recv_ms, source, url, params, body} to the day's raw file. Headers are never written; secret
    params are dropped and any remaining occurrence of the secret is replaced before writing."""
    body = fetch(url, params, headers)
    recv = _now_ms()
    line = json.dumps({"recv_ms": recv, "source": source, "url": url,
                       "params": {k: v for k, v in (params or {}).items() if k not in secret_params}, "body": body},
                      separators=(",", ":"))
    p = pathlib.Path(raw_dir) / source / f"{utc_date(recv)}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(_scrub(line, [secret]) + "\n")
    return body, recv

# ---------------------------------------------------------------- Kalshi (public, no key)


def _kalshi_mid(book: dict) -> float | None:
    """YES mid = (best YES bid + (1 - best NO bid)) / 2. Handles orderbook_fp (dollars) and legacy orderbook (cents)."""
    ob = book.get("orderbook_fp")
    if ob is not None:
        yes, no = [float(p) for p, _ in ob.get("yes_dollars") or []], [float(p) for p, _ in ob.get("no_dollars") or []]
    else:
        ob = book.get("orderbook") or {}
        yes, no = [p / 100 for p, _ in ob.get("yes") or []], [p / 100 for p, _ in ob.get("no") or []]
    return None if not yes or not no else (max(yes) + 1 - max(no)) / 2


def parse_kalshi(league: str, event: dict, books: dict, recv_ms: int) -> dict | None:
    """One Kalshi game event (with nested markets) plus {ticker: orderbook} -> OddsSnapshot with probs, or None when any
    outcome lacks a two-sided book."""
    home, _, away = event["title"].partition(" vs ")
    probs, start = {}, None
    for m in event.get("markets", []):
        sub = m.get("yes_sub_title", "")
        k = "D" if sub == "Tie" else {norm_team(home): "H", norm_team(away): "A"}.get(norm_team(sub))
        mid = _kalshi_mid(books.get(m["ticker"]) or {})
        if k is None or mid is None:
            return None
        probs[k] = round(mid, 6)
        # ponytail: Kalshi soccer occurrence_datetime = kickoff + 3h (observed 2026-10-01); /milestones start_date if it drifts
        start = iso_ms(m.get("occurrence_datetime"))
    if set(probs) != {"H", "D", "A"} or start is None:
        return None
    return snapshot("kalshi", "kalshi", league, home, away, start - 3 * H_MS, recv_ms, recv_ms, probs=probs)


def kalshi_snapshots(leagues=LEAGUES, fetch=http_get, raw_dir=RAW) -> dict:
    out, errors = [], []
    for lg in leagues:
        try:
            evs, _ = get_raw("kalshi", f"{KALSHI}/events", {"series_ticker": KALSHI_SERIES[lg], "status": "open",
                             "with_nested_markets": "true", "limit": 200}, fetch, raw_dir)
            for e in evs.get("events", []):
                books, recv = {}, None
                for m in e.get("markets", []):
                    books[m["ticker"]], recv = get_raw("kalshi", f"{KALSHI}/markets/{m['ticker']}/orderbook", None,
                                                       fetch, raw_dir)
                s = parse_kalshi(lg, e, books, recv)
                if s:
                    out.append(s)
        except Exception as ex:  # one league failing must not hide the others
            errors.append(f"{lg}: {type(ex).__name__}: {ex}")
    return {"ok": not errors, "error": "; ".join(errors) or None, "snapshots": out}

# ---------------------------------------------------------------- football-data closing lines (CLV only, never quoting)

_CLOSE_FAMILIES = (("PSC", "PS"), ("BFEC", "BFE"), ("AvgC", "Avg"))


def closing_odds(df=None) -> list[dict]:
    """Closing H/D/A per match, PSC* -> BFEC* -> AvgC*; a close equal to its open on all three outcomes is missing."""
    import pandas as pd
    df = pd.read_parquet(PARQUET) if df is None else df
    out, uk = [], ZoneInfo("Europe/London")  # football-data kickoff times are UK local
    for r in df.to_dict("records"):
        for close, open_ in _CLOSE_FAMILIES:
            c = [r.get(close + k) for k in "HDA"]
            o = [r.get(open_ + k) for k in "HDA"]
            if any(v is None or pd.isna(v) for v in c) or all(not pd.isna(x) and x == y for x, y in zip(o, c)):
                continue
            t = r.get("Time")
            hh, mm = (int(x) for x in t.split(":")) if isinstance(t, str) and ":" in t else (0, 0)
            ko = pd.Timestamp(r["Date"]).to_pydatetime().replace(hour=hh, minute=mm, tzinfo=uk)
            start = int(ko.timestamp() * 1000)
            # obs = kickoff (a closing line); recv unknown for a historical file
            out.append(snapshot("football-data", close, r["league"], r["HomeTeam"], r["AwayTeam"], start, start, None,
                                odds=dict(zip("HDA", map(float, c)))))
            break
    return out

# ---------------------------------------------------------------- SportsGameOdds (Pinnacle) and odds-api.io (keyed)


def american_to_decimal(a) -> float:
    a = float(a)
    return round(1 + (a / 100 if a > 0 else 100 / -a), 6)


def parse_sgo(payload: dict, league: str, recv_ms: int, book: str = "pinnacle") -> list[dict]:
    out = []
    for ev in payload.get("data") or []:
        odds, obs = {}, []
        for k, oid in SGO_ODDS.items():
            b = (((ev.get("odds") or {}).get(oid) or {}).get("byBookmaker") or {}).get(book)
            if not b or not b.get("available", True) or b.get("odds") is None:
                break
            odds[k] = american_to_decimal(b["odds"])
            obs.append(iso_ms(b.get("lastUpdatedAt")) or recv_ms)
        else:
            t = ev["teams"]
            out.append(snapshot("sgo", book, league, t["home"]["names"]["long"], t["away"]["names"]["long"],
                                iso_ms(ev["status"]["startsAt"]), max(obs), recv_ms, odds=odds))
    return out


def parse_oddsapi(payload, league: str, recv_ms: int) -> list[dict]:
    """odds-api.io /odds or /odds/multi body -> one OddsSnapshot per (event, bookmaker) with a 1X2 ('ML') market."""
    out = []
    for ev in payload if isinstance(payload, list) else [payload]:
        for book, markets in (ev.get("bookmakers") or {}).items():
            ml = next((m for m in markets if m.get("name") == "ML" and m.get("odds")), None)
            if not ml:
                continue
            o = ml["odds"][0]
            try:
                odds = {"H": float(o["home"]), "D": float(o["draw"]), "A": float(o["away"])}
            except (KeyError, TypeError, ValueError):
                continue
            out.append(snapshot("odds-api", book, league, ev["home"], ev["away"], iso_ms(ev["date"]),
                                iso_ms(ml.get("updatedAt")) or recv_ms, recv_ms, odds=odds))
    return out


def _keyed(source, env, quota, units, priority):
    key = (env if env is not None else os.environ).get(ENV_KEYS[source])
    if not key:
        return None, {"ok": False, "error": f"no key: {ENV_KEYS[source]} not set", "snapshots": []}
    if quota is not None and not quota.take(source, units, priority):
        return None, {"ok": False, "error": "quota refused", "snapshots": []}
    return key, None


def sgo_snapshots(league, starts_after_ms, starts_before_ms, limit=10, fetch=http_get, quota=None, raw_dir=RAW,
                  priority="routine", env=None) -> dict:
    # ponytail: charges `limit` events up front (fail closed); refund the unused part if quota gets tight
    key, err = _keyed("sgo", env, quota, limit, priority)
    if err:
        return err
    params = {"leagueID": SGO_LEAGUES[league], "bookmakerID": "pinnacle", "oddID": ",".join(SGO_ODDS.values()),
              "startsAfter": datetime.fromtimestamp(starts_after_ms / 1000, timezone.utc).isoformat(),
              "startsBefore": datetime.fromtimestamp(starts_before_ms / 1000, timezone.utc).isoformat(), "limit": limit}
    try:
        body, recv = get_raw("sgo", SGO, params, fetch, raw_dir, headers={"X-Api-Key": key}, secret=key)
        return {"ok": True, "error": None, "snapshots": parse_sgo(body, league, recv)}
    except Exception as ex:
        return {"ok": False, "error": _scrub(f"{type(ex).__name__}: {ex}", [key]), "snapshots": []}


def oddsapi_snapshots(league, bookmakers=("Bet365", "Unibet"), fetch=http_get, quota=None, raw_dir=RAW,
                      priority="routine", env=None) -> dict:
    """1 request for the league's pending events, then 1 per 10 events for odds; each request is one quota unit."""
    key, err = _keyed("odds-api", env, quota, 1, priority)
    if err:
        return err
    out = []
    try:
        evs, _ = get_raw("odds-api", f"{ODDSAPI}/events", {"apiKey": key, "sport": "football",
                         "league": ODDSAPI_LEAGUES[league], "status": "pending"}, fetch, raw_dir,
                         secret=key, secret_params=("apiKey",))
        ids = [str(e["id"]) for e in evs]
        for i in range(0, len(ids), 10):
            if quota is not None and not quota.take("odds-api", 1, priority):
                return {"ok": False, "error": "quota refused", "snapshots": out}
            body, recv = get_raw("odds-api", f"{ODDSAPI}/odds/multi", {"apiKey": key, "eventIds": ",".join(ids[i:i + 10]),
                                 "bookmakers": ",".join(bookmakers)}, fetch, raw_dir, secret=key,
                                 secret_params=("apiKey",))
            out += parse_oddsapi(body, league, recv)
        return {"ok": True, "error": None, "snapshots": out}
    except Exception as ex:
        return {"ok": False, "error": _scrub(f"{type(ex).__name__}: {ex}", [key]), "snapshots": out}

# ---------------------------------------------------------------- snapshot schedule


def due(start_ms, lineup_ms, done_labels, now_ms, assumed_lineup_min=60) -> list[dict]:
    """Labels due now among T-24h, T-3h, lineup+10m, each at most once (done_labels). A label is due from its time until
    the next label's time (a later due label supersedes an overdue earlier one), and never at or after the start."""
    assumed = lineup_ms is None
    lineup = start_ms - assumed_lineup_min * MIN_MS if assumed else lineup_ms
    times = sorted([(start_ms - 24 * H_MS, "T-24h"), (start_ms - 3 * H_MS, "T-3h"), (lineup + 10 * MIN_MS, "lineup+10m")])
    out = []
    for i, (t, label) in enumerate(times):
        end = min(times[i + 1][0] if i + 1 < len(times) else start_ms, start_ms)
        if t <= now_ms < end and label not in done_labels:
            out.append({"label": label, "due_ms": t, "lineup_assumed": assumed and label == "lineup+10m"})
    return out

# ---------------------------------------------------------------- Polymarket market mapping

_WIN = re.compile(r"Will (.+) win on \d{4}-\d{2}-\d{2}\?$")
_DRAW = re.compile(r"Will (.+) vs\. (.+) end in a draw\?$")


def rule_flags(rules: str) -> list[str]:
    flags = []
    if re.search(r"postponed.{0,80}remain open until the game has been completed", rules, re.I | re.S):
        flags.append("postponed_open_until_completed")
    m = re.search(r"cancel+ed entirely.{0,80}?resolve(?: to)? \"(\w+)\"", rules, re.I | re.S)
    if m:
        flags.append(f"cancelled_resolves_{m[1].lower()}")
    if re.search(r"90 minutes of regular play plus stoppage time", rules, re.I):
        flags.append("regulation_90_plus_stoppage")
    return flags


def map_markets(rows, events, tol_ms=15 * MIN_MS):
    """Crawler sports-pregame rows -> (MarketMap list, unmapped list). events: any records with league, home, away,
    start_ms (OddsSnapshot, GameState). A match needs the same league, kickoff within tol and both normalized names equal;
    zero or several candidates -> unmapped, never guessed. GameState records use scheduled_start_ms."""
    groups = {}
    for r in rows:
        if r.get("mode") == "sports-pregame":
            groups.setdefault(r["event_slug"], []).append(r)
    cands = {}
    for e in events:
        if e.get("start_ms", e.get("scheduled_start_ms")) is None:
            continue
        cands.setdefault((e["league"], norm_team(e["home"]), norm_team(e["away"])), {})[e["event_key"]] = e
    maps, unmapped = [], []
    for slug, rs in groups.items():
        parts = slug.split("-")
        league = PM_LEAGUES.get(parts[0])
        side = {parts[1]: "H", parts[2]: "A", "draw": "D"} if len(parts) >= 3 else {}
        names, outcome = {}, {}
        for r in rs:
            k = side.get(r["market_slug"].rsplit("-", 1)[-1])
            m = _WIN.match(r["question"]) if k in ("H", "A") else _DRAW.match(r["question"]) if k == "D" else None
            if m:
                outcome[r["condition_id"]] = k
                if k != "D":
                    names[k] = m[1]
        start = iso_ms(rs[0].get("event_start_time"))
        if league is None or start is None or set(names) != {"H", "A"}:
            unmapped.append({"event_slug": slug, "reason": "unparsed"})
            continue
        hits = [e for e in cands.get((league, norm_team(names["H"]), norm_team(names["A"])), {}).values()
                if abs(e.get("start_ms", e.get("scheduled_start_ms")) - start) <= tol_ms]
        if len(hits) != 1:
            unmapped.append({"event_slug": slug, "reason": "no candidate" if not hits else f"{len(hits)} candidates"})
            continue
        ek = hits[0]["event_key"]
        for r in rs:
            if r["condition_id"] in outcome:
                maps.append({"cid": r["condition_id"], "token_yes": r["yes_token_id"], "token_no": r["no_token_id"],
                             "event_key": ek, "league": league, "home": names["H"], "away": names["A"],
                             "outcome": outcome[r["condition_id"]], "start_ms": start,
                             "rule_flags": rule_flags(r.get("rules_text") or "")})
    return maps, unmapped

# ---------------------------------------------------------------- quota book and projection


class Quota:
    """Usage per source per period, persisted to JSON and re-read on every call (instances share the file). Routine
    requests stop at 80% of quota; priority "news" may use the last 20%; at 100% everything is refused."""

    def __init__(self, path=QUOTA_FILE, limits=QUOTA_LIMITS, routine_share=0.8):
        self.path, self.limits, self.share = pathlib.Path(path), limits, routine_share

    def _period(self, source, now_ms):
        fmt = "%Y-%m" if self.limits[source][1] == "month" else "%Y-%m-%d"
        return datetime.fromtimestamp(now_ms / 1000, timezone.utc).strftime(fmt)

    def _load(self):
        return json.loads(self.path.read_text()) if self.path.exists() else {}

    def used(self, source, now_ms=None):
        rec = self._load().get(source)
        return rec["used"] if rec and rec["period"] == self._period(source, now_ms or _now_ms()) else 0

    def take(self, source, units=1, priority="routine", now_ms=None) -> bool:
        # ponytail: read-check-replace without a file lock; two processes taking at once can lose one unit. One collector
        # process owns the file today; add a lock file (os.O_EXCL) if a second writer appears.
        now_ms = now_ms or _now_ms()
        limit = self.limits[source][0]
        used = self.used(source, now_ms)
        if used + units > (limit if priority == "news" else self.share * limit):
            return False
        state = self._load()
        state[source] = {"period": self._period(source, now_ms), "used": used + units}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state))
        os.replace(tmp, self.path)
        return True


def project_quota(df=None, monthly_quota=2500, per_event=3, priority=LEAGUES, seasons=("2023/24", "2024/25", "2025/26"),
                  share=0.8) -> list[dict]:
    """Per league: peak calendar month of fixtures over `seasons` x snapshots per event. Leagues are enabled in priority
    order while the cumulative projected peak month stays <= share of the monthly quota (stops at the first overflow)."""
    import pandas as pd
    df = pd.read_parquet(PARQUET, columns=["league", "season", "Date"]) if df is None else df
    df = df[df["season"].isin(seasons)]
    rows, cum, open_ = [], 0, True
    for lg in priority:
        months = df[df["league"] == lg]["Date"].dt.strftime("%Y-%m").value_counts()
        month, n = (months.idxmax(), int(months.max())) if len(months) else ("-", 0)
        cum += n * per_event
        open_ = open_ and cum <= share * monthly_quota
        rows.append({"league": lg, "peak_month": month, "fixtures": n, "units": n * per_event,
                     "cum_share": cum / monthly_quota, "enabled": open_})
    return rows


def write_quota_report(rows, out, monthly_quota=2500, per_event=3, share=0.8, seasons=("2023/24", "2024/25", "2025/26")):
    lines = ["# Phase 4 odds quota projection (SportsGameOdds)", "",
             f"Monthly quota {monthly_quota:,} events; routine budget {share:.0%} = {share * monthly_quota:,.0f}; "
             f"the last {1 - share:.0%} is the news reserve (role 25).", "",
             "| League | Peak month | Fixtures | Projected units | Cumulative share of quota | Enabled |",
             "|---|---|---|---|---|---|"]
    lines += [f"| {r['league']} | {r['peak_month']} | {r['fixtures']} | {r['units']} | {r['cum_share']:.1%} | "
              f"{'yes' if r['enabled'] else 'no'} |" for r in rows]
    lines += ["", "## Assumptions", "",
              f"- Fixtures per calendar month from `data/history/footballdata/matches.parquet`, seasons {', '.join(seasons)} "
              "(the last complete seasons); the peak month is the maximum over those seasons.",
              f"- {per_event} snapshots per event (T-24h, T-3h, lineup+10m); each SportsGameOdds event returned counts "
              "as one unit per request.",
              "- Leagues are enabled in priority order " + " > ".join(r["league"] for r in rows) +
              f" while the cumulative projected peak month stays <= {share:.0%} of the quota; the first league that "
              "would overflow and every later one are disabled.",
              "- Peak months are summed across leagues even when they fall in different months (conservative).",
              "- News refreshes (priority `news`) are not projected; they draw on the reserve and are refused at 100%.",
              "- odds-api.io (500 requests/day) is request-based and polled continuously; it is not part of this "
              "projection.", "", "## How to reproduce", "", "```", ".venv\\Scripts\\python.exe -m sports.odds quota", "```", ""]
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(out).write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m sports.odds")
    sub = ap.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("quota")
    q.add_argument("--out", default=str(REPORTS / "phase4_quota.md"))
    q.add_argument("--quota", type=int, default=2500)
    q.add_argument("--per-event", type=int, default=3)
    s = sub.add_parser("smoke")
    s.add_argument("--ws-seconds", type=int, default=75)
    s.add_argument("--out", default=str(REPORTS / "phase4_sports_smoke.md"))
    a = ap.parse_args(argv)
    if a.cmd == "quota":
        rows = project_quota(monthly_quota=a.quota, per_event=a.per_event)
        write_quota_report(rows, a.out, a.quota, a.per_event)
        print(json.dumps(rows, indent=1))
    else:
        from sports.gamestate import smoke
        smoke(a.ws_seconds, a.out)


if __name__ == "__main__":
    main()
