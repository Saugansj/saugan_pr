# Phase 4 devig report: per-league devig method on opening odds (WP4-B, task 4.3)

Generated 2026-10-01 09:09 UTC by `python -m sports.fair devig-report` from `data/history/footballdata/matches.parquet` (25,491 played matches; 19,958 training and 4,406 held-out matches where all 7 methods succeed on PSH/PSD/PSA). penaltyblog 1.12.3.

**Data note: football-data.co.uk stopped publishing Pinnacle (PS*) odds in January 2026.** 2025/26 is partial (last PS* match per league: D1 2026-01-15, E0 2026-01-08, F1 2026-01-04, I1 2026-01-15, SP1 2026-01-12) and 2026/27 has no PS* columns at all. This choice is fitted on history only. Live quoting devigs SportsGameOdds Pinnacle snapshots (needs an API key; [ops]); CLV closes fall back to Betfair Exchange closing (BFEC*), then market average (AvgC*).

## Chosen method per league (registry candidate)

| league   | method         |   train_ll |   held_ll |   held_vs_multiplicative |   train_n |   held_n | train_seasons    | phase0_closing_choice   |
|:---------|:---------------|-----------:|----------:|-------------------------:|----------:|---------:|:-----------------|:------------------------|
| D1       | multiplicative |    0.98274 |   0.95915 |                  0       |      3365 |      762 | 2012/13..2022/23 | multiplicative          |
| E0       | odds_ratio     |    0.95645 |   0.94971 |                 -0.0004  |      4180 |      970 | 2012/13..2022/23 | odds_ratio              |
| F1       | power          |    0.98725 |   0.97937 |                 -0.00062 |      4070 |      765 | 2012/13..2022/23 | power                   |
| I1       | power          |    0.95184 |   0.9645  |                 -0.00076 |      4169 |      960 | 2012/13..2022/23 | power                   |
| SP1      | odds_ratio     |    0.95783 |   0.94854 |                 -0.00123 |      4174 |      949 | 2012/13..2022/23 | odds_ratio              |

- Rule: per league, the method with the lowest mean log loss -ln p(full-time result) on the full 1X2, using Pinnacle opening odds (PSH/PSD/PSA; early quotes are priced before the close) and training seasons strictly before the held-out seasons (2023/24, 2024/25, 2025/26; the last is partial). Never scored against the closing line.
- `train_ll` / `held_ll`: the chosen method's mean log loss (natural log) on training / held-out matches. `held_vs_multiplicative`: chosen minus multiplicative on the same held-out matches (negative = chosen better).
- `phase0_closing_choice`: Phase 0's choice on Pinnacle *closing* odds (reports/devig_report.md), for comparison only. Closing odds are used for CLV, never for the quoting choice.
- In penaltyblog 1.12.3 `differential_margin_weighting` equals `additive` and `logarithmic` equals `odds_ratio` algebraically; ties within 1e-9 go to the first-listed method. The methods differ by ~1e-4 in log loss, so the choice per league is weakly identified and matters little.

Parameter set for role 15's registry (state `candidate`; the version is a hash of the params):

```json
{
  "name": "sports-devig",
  "version": "ee7d3af0e9a5",
  "params": {
    "D1": "multiplicative",
    "E0": "odds_ratio",
    "F1": "power",
    "I1": "power",
    "SP1": "odds_ratio"
  },
  "state": "candidate"
}
```

## Training log loss of all 7 methods (opening odds)

| league   |   multiplicative |   additive |   power |    shin |   differential_margin_weighting |   odds_ratio |   logarithmic |
|:---------|-----------------:|-----------:|--------:|--------:|--------------------------------:|-------------:|--------------:|
| D1       |          0.98274 |    0.9832  | 0.98326 | 0.98305 |                         0.9832  |      0.98303 |       0.98303 |
| E0       |          0.95655 |    0.95659 | 0.9565  | 0.95655 |                         0.95659 |      0.95645 |       0.95645 |
| F1       |          0.98757 |    0.98732 | 0.98725 | 0.98736 |                         0.98732 |      0.98733 |       0.98733 |
| I1       |          0.95226 |    0.95187 | 0.95184 | 0.95194 |                         0.95187 |      0.95197 |       0.95197 |
| SP1      |          0.95793 |    0.95787 | 0.95784 | 0.95786 |                         0.95787 |      0.95783 |       0.95783 |

## sigma_fair default check

sigma_fair = sqrt(s0^2 + k * age_hours), candidate `sports-sigma` v1: s0 = 0.015, k = 2e-05, max_age = 22 h, continuous sources fresh for 10 min. At 0 h, 3 h and 21 h sigma is 0.0150, 0.0169 and 0.0254.

Check against how far Pinnacle's devigged probability moves from opening (football-data's PS*, collected Friday afternoon, or Tuesday for midweek games) to closing, held-out seasons, chosen method, over the H, D and A probabilities. `k_if_24h` / `k_if_48h` = rms^2 / hours if the move took 24 h / 48 h:

| league   |   matches |   rms_open_to_close |   k_if_24h |   k_if_48h |
|:---------|----------:|--------------------:|-----------:|-----------:|
| D1       |       761 |            0.023462 |    2.3e-05 |    1.1e-05 |
| E0       |       970 |            0.022982 |    2.2e-05 |    1.1e-05 |
| F1       |       765 |            0.02705  |    3e-05   |    1.5e-05 |
| I1       |       958 |            0.022853 |    2.2e-05 |    1.1e-05 |
| SP1      |       948 |            0.023621 |    2.3e-05 |    1.2e-05 |

Default k = 2e-05 is inside the range 1.09e-05 to 3.05e-05 (smallest k_if_48h to largest k_if_24h). s0 cannot be checked this way (the close is noisy itself). Loop B refits s0 and k from universe checkpoint rows once they exist.

## How to reproduce

From `roster/` (needs WP0-B's `data/history/footballdata/matches.parquet`):

```
.venv\Scripts\python.exe -m sports.fair devig-report          # ~2 min, rewrites this report
.venv\Scripts\python.exe -m pytest tests/phase4/test_sports_fair.py -q
```
