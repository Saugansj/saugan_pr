# Phase 4 odds quota projection (SportsGameOdds)

Monthly quota 2,500 events; routine budget 80% = 2,000; the last 20% is the news reserve (role 25).

| League | Peak month | Fixtures | Projected units | Cumulative share of quota | Enabled |
|---|---|---|---|---|---|
| E0 | 2023-12 | 66 | 198 | 7.9% | yes |
| SP1 | 2024-05 | 50 | 150 | 13.9% | yes |
| D1 | 2026-01 | 42 | 126 | 19.0% | yes |
| I1 | 2026-01 | 58 | 174 | 25.9% | yes |
| F1 | 2023-12 | 38 | 114 | 30.5% | yes |

## Assumptions

- Fixtures per calendar month from `data/history/footballdata/matches.parquet`, seasons 2023/24, 2024/25, 2025/26 (the last complete seasons); the peak month is the maximum over those seasons.
- 3 snapshots per event (T-24h, T-3h, lineup+10m); each SportsGameOdds event returned counts as one unit per request.
- Leagues are enabled in priority order E0 > SP1 > D1 > I1 > F1 while the cumulative projected peak month stays <= 80% of the quota; the first league that would overflow and every later one are disabled.
- Peak months are summed across leagues even when they fall in different months (conservative).
- News refreshes (priority `news`) are not projected; they draw on the reserve and are refused at 100%.
- odds-api.io (500 requests/day) is request-based and polled continuously; it is not part of this projection.

## How to reproduce

```
.venv\Scripts\python.exe -m sports.odds quota
```
