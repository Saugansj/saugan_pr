# Phase 4 sports smoke run (WP4-A)

Run 2026-10-01 09:20:08 UTC to 2026-10-01 09:43:38 UTC. Public GETs and the public sports WebSocket only; no keys, no orders.

## Counts per source

| Source | Result | Count | Note |
|---|---|---|---|
| Kalshi soccer game events (5 series) | ok | 48 OddsSnapshot (probs) | books read for every outcome market |
| ESPN scoreboard (5 leagues, today + 4 crawler dates) | ok | 48 games | statuses: {"scheduled": 48} |
| Polymarket sports WebSocket (75 s) | ok | 53 messages, 0 for our 5 leagues | leagues seen: {"cs2": 20, "val": 4, "r6siege": 3, "challenger": 10, "atp": 11, "wta challenger": 5} |
| SportsGameOdds | not run | 0 | no SPORTSGAMEODDS_API_KEY on this machine ([ops] A11) |
| odds-api.io | not run | 0 | no ODDS_API_IO_KEY on this machine ([ops] A11) |

## Market mapping

Crawler snapshot `2026-10-01T084927Z.jsonl`: 144 sports-pregame rows in 48 events.

| Matched against | Mapped markets | Mapped events | Unmapped events |
|---|---|---|---|
| ESPN games + Kalshi events | 144 | 48 | 0 |
| Kalshi events only | 144 | 48 | 0 |

Outcomes of mapped markets: {"H": 48, "D": 48, "A": 48}. Rule flags seen: cancelled_resolves_no, cancelled_resolves_yes, postponed_open_until_completed, regulation_90_plus_stoppage.

Unmapped events (ESPN + Kalshi): none.

Cancel rule on the ESPN states at 2026-10-01 09:43:38 UTC: 0 signals.

Sample mapped markets:

| cid | event_key | outcome | start | rule_flags |
|---|---|---|---|---|
| 0x9f1a28479d… | E0:arsenal:leeds:2026-10-10 | H | 2026-10-10 11:30:00 UTC | postponed_open_until_completed, cancelled_resolves_no, regulation_90_plus_stoppage |
| 0x42e69c6f58… | E0:arsenal:leeds:2026-10-10 | D | 2026-10-10 11:30:00 UTC | postponed_open_until_completed, cancelled_resolves_yes, regulation_90_plus_stoppage |
| 0xce4511220e… | E0:arsenal:leeds:2026-10-10 | A | 2026-10-10 11:30:00 UTC | postponed_open_until_completed, cancelled_resolves_no, regulation_90_plus_stoppage |
| 0x2dbfcec0b5… | E0:sunderland:brighton:2026-10-10 | H | 2026-10-10 14:00:00 UTC | postponed_open_until_completed, cancelled_resolves_no, regulation_90_plus_stoppage |
| 0x4e1d5fdef2… | E0:sunderland:brighton:2026-10-10 | D | 2026-10-10 14:00:00 UTC | postponed_open_until_completed, cancelled_resolves_yes, regulation_90_plus_stoppage |
| 0xe8b24aac14… | E0:sunderland:brighton:2026-10-10 | A | 2026-10-10 14:00:00 UTC | postponed_open_until_completed, cancelled_resolves_no, regulation_90_plus_stoppage |

Kalshi sample:

- E0:arsenal:leeds:2026-10-10: {"H": 0.725, "A": 0.115, "D": 0.175} (sum 1.015)
- E0:aston villa:brentford:2026-10-10: {"H": 0.365, "A": 0.365, "D": 0.265} (sum 0.995)
- E0:chelsea:bournemouth:2026-10-10: {"H": 0.575, "A": 0.205, "D": 0.225} (sum 1.005)
- E0:ipswich:fulham:2026-10-10: {"H": 0.36, "A": 0.37, "D": 0.265} (sum 0.995)
- E0:sunderland:brighton:2026-10-10: {"H": 0.32, "A": 0.405, "D": 0.265} (sum 0.990)

Raw responses: `C:/Users/DELL/Downloads/saugan_pr/market_updated/roster/data/sports/raw/<source>/<date>.jsonl` (kalshi, espn, polymarket-sports).

## How to reproduce

```
.venv\Scripts\python.exe -m sports.odds smoke --ws-seconds 75
```
