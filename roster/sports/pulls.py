"""Role 20 sports pull rules (Phase 4 task 4.4, WP4-B). Pure functions.

pull_reasons() lists every reason the soccer maker must hold no quotes on a market right now; an empty list means it may
quote. It never relies on the venue's auto-cancel at the start. maker_expiry() is the GTD cap for sports makers.
Records are the Phase 4 dispatch's plain dicts (MarketMap, GameState); cautions are advisor.contracts.CautionSignal.
"""
MIN = 60_000
PARAMS = {
    "start_margin_ms": 5 * MIN,        # pull from scheduled start - 5 min (the kernel's start - 5 min resting rule)
    "start_tol_ms": 60_000,            # game-state start vs the markets' start_ms
    "book_stale_ms": 30_000,           # Phase 1 kernel's bound for the "polymarket" feed
    "gamestate_stale_ms": 120_000,     # WP4-A cancel rule's stale_ms
    "sharp_max_age_ms": 22 * 60 * MIN,  # same as sports-sigma max_age
}
BOOK_FEED, GAME_FEED = "polymarket", "sports"   # feed_age_ms keys (Phase 1 kernel; WP4-A game-state feed)


def pull_reasons(now_ms: int, market_map: dict, game_state: dict | None, lineup_ms: int | None,
                 last_sharp_obs_ms: int | None, cautions, feed_age_ms: dict, gate: tuple | None,
                 params: dict = PARAMS) -> list[str]:
    """Reasons to pull this market's quotes now (empty = may quote).

    - start: from min(market start, game-state scheduled start) - start_margin_ms
    - lineup: from lineup_ms until a sharp snapshot with obs_ms > lineup_ms (an older one does not clear it)
    - game state: missing, start moved by > start_tol_ms, or any status other than "scheduled" (covers early
      in_progress, postponed, delayed, suspended, cancelled; unknown statuses fail closed)
    - cautions: in arrival order, the last signal per (role, scope) for this cid or event_key is current; a current
      "pull" holds until expires_ms, or with resume_requires_fresh_observation until the sentinel replaces it with
      action "none" (a timeout never resumes)
    - stale or missing book ("polymarket") or game-state ("sports") feed age, or sharp snapshot older than its bound
    - the quote gate (fair.quote_allowed's (ok, reason)) refusing or missing
    """
    p = params
    r = []
    sched = (game_state or {}).get("scheduled_start_ms")
    start = min(market_map["start_ms"], sched) if sched is not None else market_map["start_ms"]
    if now_ms >= start - p["start_margin_ms"]:
        r.append(f"pre-start: at or after scheduled start - {p['start_margin_ms'] // MIN} min")
    if lineup_ms is not None and now_ms >= lineup_ms and (last_sharp_obs_ms is None or last_sharp_obs_ms <= lineup_ms):
        r.append("lineup released: waiting for a sharp snapshot taken after the lineup")
    if game_state is None:
        r.append("game state: none")
    else:
        if sched is None or abs(sched - market_map["start_ms"]) > p["start_tol_ms"]:
            r.append(f"game state: scheduled start {sched} differs from market start {market_map['start_ms']}")
        status = game_state.get("status")
        if status != "scheduled":
            early = status == "in_progress" and sched is not None and now_ms < sched
            r.append(f"game state: {status}" + (" before scheduled start" if early else ""))
    scopes = {market_map["cid"], market_map["event_key"]}
    current = {}
    for c in cautions or ():
        if c.scope in scopes:
            current[(c.role, c.scope)] = c
    for c in current.values():
        if c.action == "pull" and (c.resume_requires_fresh_observation or now_ms < c.expires_ms):
            r.append(f"caution {c.role} on {c.scope}: {c.reason}")
    for feed, bound in ((BOOK_FEED, p["book_stale_ms"]), (GAME_FEED, p["gamestate_stale_ms"])):
        age = (feed_age_ms or {}).get(feed)
        if age is None or age > bound:
            r.append(f"stale feed {feed}: age {age} ms > {bound} ms")
    if last_sharp_obs_ms is None or now_ms - last_sharp_obs_ms > p["sharp_max_age_ms"]:
        r.append("no fresh sharp reference")
    if not gate or not gate[0]:
        r.append(f"quote gate: {gate[1] if gate else 'no result'}")
    return r


def maker_expiry(start_ms: int, end_ms: int) -> int:
    """GTD expiry cap for a sports maker order: min(start - 5 min, end - 2 min)."""
    return min(start_ms - 5 * MIN, end_ms - 2 * MIN)
