# Go/no-go test B: soccer devig (WP0-D, build-plan task 0.7)

Generated 2026-09-30 17:17 UTC by `research/devig/devig.py` from WP0-B's `data/history/footballdata/matches.parquet` (25,491 played matches, 5 leagues E0/SP1/D1/I1/F1, 2012/13 to 2026/27). penaltyblog 1.12.3.

## Verdict: **FAIL**

- Current season (2026/27) PSCH/PSCD/PSCA filled on 0% of played matches (needs >= 95%): **FAIL**.
- Pinnacle closing, chosen method per league: **calibration FAIL: 1 of 3 held-out seasons in 0.9-1.1, leagues outside the band: SP1**.
- Pinnacle opening, same rule (supporting): calibration FAIL: 1 of 3 held-out seasons in 0.9-1.1, leagues outside the band: SP1.
- Sensitivity, closing with the linear reliability slope instead of the logistic one: calibration FAIL: 3 of 3 held-out seasons in 0.9-1.1, leagues outside the band: SP1.
- Rule (fixed before the run): PASS needs the chosen method's calibration slope, pooled over the five leagues, in 0.9-1.1 on at least two held-out seasons, every league's slope pooled over its held-out seasons in the band, **and** the current season's Pinnacle closing columns filled (the build plan's second condition).
- Pinnacle closing, all held-out matches: slope 1.081 +/- 0.036 (training seasons, in-sample: 1.020 +/- 0.016); log loss 0.9576, -0.0005 vs multiplicative.
- The data condition fails whatever the calibration says: football-data.co.uk stopped publishing Pinnacle odds in January 2026, so there is no current-season Pinnacle close to devig. The strategy needs another sharp closing source before this test can pass (the D4 table shows what football-data still publishes).

## Setup

- Training seasons (method choice only): 2012/13 to 2022/23 (11 seasons). Held-out seasons: 2023/24, 2024/25, 2025/26 (2025/26 is partial: Pinnacle columns end mid-January 2026).
- Outcome: full-time result FTR (H/D/A). Log loss = mean of -ln p(outcome) over matches (natural log).
- Reliability (calibration) slope: logistic regression of 1{outcome = k} on logit(p_k), stacking the three outcomes of each match; SE clustered by match. Slope 1 = calibrated; < 1 = over-confident, > 1 = under-confident (favourites win more and longshots less than the devigged odds say). `linear_slope` = OLS slope of the same indicators on p_k (sensitivity check only).
- Methods are compared on the matches where all 7 succeed. "Opening" is football-data's PSH/PSD/PSA, collected on Friday afternoon (Tuesday for midweek games), not the very first line.

## D1: all 7 methods ran

| odds set | matches with odds | all 7 succeeded | multiplicative | additive | power | shin | differential_margin_weighting | odds_ratio | logarithmic |
|---|---|---|---|---|---|---|---|---|---|
| closing | 24,383 | 24,383 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| opening | 24,364 | 24,364 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| avg_closing | 12,709 | 12,708 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |

Cells are failure counts (exception or not a probability vector). First failure per method:
- avg_closing / shin: odds [8.7, 5.79, 1.56]: ValueError: f(a) and f(b) must have different signs

In penaltyblog 1.12.3, `differential_margin_weighting` is algebraically the same as `additive` (1/o - margin/n) and `logarithmic` the same as `odds_ratio` (a constant shift in log-odds), so their log losses match to about 1e-12 and only 5 methods are really distinct; which member of an identical pair is chosen is rounding noise and changes nothing.

## D2: method choice on training seasons, Pinnacle closing (mean log loss)

| league   |   matches |   multiplicative |   additive |   power |    shin |   differential_margin_weighting |   odds_ratio |   logarithmic | chosen         |
|:---------|----------:|-----------------:|-----------:|--------:|--------:|--------------------------------:|-------------:|--------------:|:---------------|
| D1       |      3365 |          0.98176 |    0.98217 | 0.98224 | 0.98204 |                         0.98217 |      0.98203 |       0.98203 | multiplicative |
| E0       |      4180 |          0.95405 |    0.95407 | 0.95399 | 0.95404 |                         0.95407 |      0.95395 |       0.95395 | odds_ratio     |
| F1       |      4079 |          0.98546 |    0.98524 | 0.98521 | 0.98527 |                         0.98524 |      0.98527 |       0.98527 | power          |
| I1       |      4178 |          0.94847 |    0.94801 | 0.94799 | 0.9481  |                         0.94801 |      0.94815 |       0.94815 | power          |
| SP1      |      4179 |          0.95349 |    0.95353 | 0.9535  | 0.95349 |                         0.95353 |      0.95345 |       0.95345 | odds_ratio     |

## D2: method choice on training seasons, Pinnacle opening (mean log loss)

| league   |   matches |   multiplicative |   additive |   power |    shin |   differential_margin_weighting |   odds_ratio |   logarithmic | chosen         |
|:---------|----------:|-----------------:|-----------:|--------:|--------:|--------------------------------:|-------------:|--------------:|:---------------|
| D1       |      3365 |          0.98274 |    0.9832  | 0.98326 | 0.98305 |                         0.9832  |      0.98303 |       0.98303 | multiplicative |
| E0       |      4180 |          0.95655 |    0.95659 | 0.9565  | 0.95655 |                         0.95659 |      0.95645 |       0.95645 | odds_ratio     |
| F1       |      4070 |          0.98757 |    0.98732 | 0.98725 | 0.98736 |                         0.98732 |      0.98733 |       0.98733 | power          |
| I1       |      4169 |          0.95226 |    0.95187 | 0.95184 | 0.95194 |                         0.95187 |      0.95197 |       0.95197 | power          |
| SP1      |      4174 |          0.95793 |    0.95787 | 0.95784 | 0.95786 |                         0.95787 |      0.95783 |       0.95783 | odds_ratio     |

## D3: held-out log loss and reliability slope, Pinnacle closing

`vs_multiplicative` = chosen method's log loss minus multiplicative's on the same matches (negative = chosen is better).

|                              |   matches | method                          |   log_loss |   vs_multiplicative |   slope |   slope_se |   intercept |   linear_slope |
|:-----------------------------|----------:|:--------------------------------|-----------:|--------------------:|--------:|-----------:|------------:|---------------:|
| ('D1', '2023/24')            |       306 | multiplicative                  |     0.9442 |              0      |  1.0726 |     0.1289 |      0.0462 |         1.0511 |
| ('D1', '2024/25')            |       306 | multiplicative                  |     0.9882 |              0      |  0.9004 |     0.1194 |     -0.064  |         0.9105 |
| ('D1', '2025/26')            |       149 | multiplicative                  |     0.9205 |              0      |  1.4491 |     0.2599 |      0.289  |         1.3104 |
| ('E0', '2023/24')            |       380 | odds_ratio                      |     0.8985 |             -0.0011 |  1.1659 |     0.1173 |      0.1041 |         1.119  |
| ('E0', '2024/25')            |       380 | odds_ratio                      |     0.9666 |              0.0002 |  0.9511 |     0.107  |     -0.031  |         0.9545 |
| ('E0', '2025/26')            |       210 | odds_ratio                      |     0.9871 |             -0.0004 |  1.0263 |     0.1566 |      0.0169 |         1.0025 |
| ('F1', '2023/24')            |       306 | power                           |     1.0145 |              0.0003 |  0.9096 |     0.1371 |     -0.0587 |         0.9076 |
| ('F1', '2024/25')            |       306 | power                           |     0.9545 |             -0.0006 |  1.0663 |     0.1352 |      0.0421 |         1.0585 |
| ('F1', '2025/26')            |       153 | power                           |     0.9581 |             -0.0011 |  1.1189 |     0.1928 |      0.0762 |         1.0837 |
| ('I1', '2023/24')            |       380 | power                           |     0.9636 |             -0.0003 |  1.1099 |     0.1371 |      0.0703 |         1.0912 |
| ('I1', '2024/25')            |       380 | power                           |     0.9499 |             -0.0015 |  1.1504 |     0.1204 |      0.0951 |         1.1039 |
| ('I1', '2025/26')            |       198 | power                           |     0.9908 |              0.0001 |  0.9459 |     0.1628 |     -0.0345 |         0.9469 |
| ('SP1', '2023/24')           |       380 | odds_ratio                      |     0.9501 |             -0.0008 |  1.2093 |     0.132  |      0.1334 |         1.154  |
| ('SP1', '2024/25')           |       380 | odds_ratio                      |     0.9456 |             -0.0007 |  1.1524 |     0.1303 |      0.0967 |         1.1179 |
| ('SP1', '2025/26')           |       188 | odds_ratio                      |     0.947  |             -0.0013 |  1.2155 |     0.1838 |      0.1378 |         1.1538 |
| ('D1', 'held-out')           |       761 | multiplicative                  |     0.9572 |              0      |  1.0528 |     0.0836 |      0.0338 |         1.0367 |
| ('E0', 'held-out')           |       970 | odds_ratio                      |     0.9443 |             -0.0005 |  1.053  |     0.0703 |      0.0336 |         1.0356 |
| ('F1', 'held-out')           |       765 | power                           |     0.9792 |             -0.0003 |  1.0201 |     0.0855 |      0.0129 |         1.0128 |
| ('I1', 'held-out')           |       958 | power                           |     0.9638 |             -0.0007 |  1.0906 |     0.0794 |      0.0576 |         1.0666 |
| ('SP1', 'held-out')          |       948 | odds_ratio                      |     0.9477 |             -0.0009 |  1.1866 |     0.0829 |      0.1188 |         1.1386 |
| ('all', '2023/24')           |      1752 | multiplicative,odds_ratio,power |     0.952  |             -0.0004 |  1.1052 |     0.0577 |      0.0671 |         1.0782 |
| ('all', '2024/25')           |      1752 | multiplicative,odds_ratio,power |     0.9601 |             -0.0005 |  1.041  |     0.0545 |      0.0261 |         1.0285 |
| ('all', '2025/26')           |       898 | multiplicative,odds_ratio,power |     0.9635 |             -0.0005 |  1.1212 |     0.0816 |      0.0776 |         1.087  |
| ('all', 'held-out')          |      4402 | multiplicative,odds_ratio,power |     0.9576 |             -0.0005 |  1.0813 |     0.0357 |      0.0518 |         1.0592 |
| ('all', 'train (in-sample)') |     19981 | multiplicative,odds_ratio,power |     0.9637 |             -0.0002 |  1.0203 |     0.0164 |      0.0129 |         1.0165 |

Reliability table (all held-out matches and outcomes, chosen method, closing):

| bin        |    n |   mean_p |   observed |
|:-----------|-----:|---------:|-----------:|
| (0.0, 0.1] |  503 |   0.074  |     0.0497 |
| (0.1, 0.2] | 2082 |   0.1571 |     0.1422 |
| (0.2, 0.3] | 4685 |   0.2553 |     0.2566 |
| (0.3, 0.4] | 2245 |   0.3389 |     0.3332 |
| (0.4, 0.5] | 1369 |   0.4463 |     0.4529 |
| (0.5, 0.6] | 1086 |   0.5475 |     0.5608 |
| (0.6, 0.7] |  630 |   0.6466 |     0.6619 |
| (0.7, 0.8] |  427 |   0.7431 |     0.7705 |
| (0.8, 0.9] |  171 |   0.8379 |     0.8655 |
| (0.9, 1.0] |    8 |   0.9163 |     1      |

## Held-out results, Pinnacle opening (supporting)

|                              |   matches | method                          |   log_loss |   vs_multiplicative |   slope |   slope_se |   intercept |   linear_slope |
|:-----------------------------|----------:|:--------------------------------|-----------:|--------------------:|--------:|-----------:|------------:|---------------:|
| ('D1', '2023/24')            |       306 | multiplicative                  |     0.9455 |              0      |  1.0856 |     0.1296 |      0.0546 |         1.0602 |
| ('D1', '2024/25')            |       306 | multiplicative                  |     0.9898 |              0      |  0.9031 |     0.123  |     -0.0624 |         0.9141 |
| ('D1', '2025/26')            |       150 | multiplicative                  |     0.9245 |              0      |  1.4017 |     0.2461 |      0.2584 |         1.2805 |
| ('E0', '2023/24')            |       380 | odds_ratio                      |     0.9073 |             -0.0012 |  1.1483 |     0.1143 |      0.0932 |         1.1045 |
| ('E0', '2024/25')            |       380 | odds_ratio                      |     0.9707 |              0.0004 |  0.9343 |     0.1063 |     -0.0418 |         0.9381 |
| ('E0', '2025/26')            |       210 | odds_ratio                      |     0.9884 |             -0.0004 |  1.001  |     0.1543 |      0.0007 |         0.9829 |
| ('F1', '2023/24')            |       306 | power                           |     1.0151 |              0.0003 |  0.9071 |     0.1386 |     -0.0604 |         0.9095 |
| ('F1', '2024/25')            |       306 | power                           |     0.9573 |             -0.0012 |  1.0873 |     0.1366 |      0.0557 |         1.0722 |
| ('F1', '2025/26')            |       153 | power                           |     0.952  |             -0.0012 |  1.1401 |     0.2004 |      0.0897 |         1.1051 |
| ('I1', '2023/24')            |       380 | power                           |     0.9669 |             -0.0003 |  1.1004 |     0.1342 |      0.0643 |         1.0839 |
| ('I1', '2024/25')            |       380 | power                           |     0.9489 |             -0.0016 |  1.1411 |     0.1194 |      0.0895 |         1.0969 |
| ('I1', '2025/26')            |       200 | power                           |     0.9896 |              0.0001 |  0.976  |     0.1677 |     -0.0154 |         0.9735 |
| ('SP1', '2023/24')           |       380 | odds_ratio                      |     0.9475 |             -0.0013 |  1.2777 |     0.1333 |      0.1775 |         1.2024 |
| ('SP1', '2024/25')           |       380 | odds_ratio                      |     0.9514 |             -0.001  |  1.1439 |     0.1269 |      0.0916 |         1.1091 |
| ('SP1', '2025/26')           |       189 | odds_ratio                      |     0.9448 |             -0.0015 |  1.2392 |     0.1852 |      0.1531 |         1.1699 |
| ('D1', 'held-out')           |       762 | multiplicative                  |     0.9592 |              0      |  1.0554 |     0.0842 |      0.0355 |         1.039  |
| ('E0', 'held-out')           |       970 | odds_ratio                      |     0.9497 |             -0.0004 |  1.0336 |     0.0691 |      0.0213 |         1.0186 |
| ('F1', 'held-out')           |       765 | power                           |     0.9794 |             -0.0006 |  1.0314 |     0.0868 |      0.0202 |         1.0231 |
| ('I1', 'held-out')           |       960 | power                           |     0.9645 |             -0.0008 |  1.0908 |     0.0789 |      0.0579 |         1.0672 |
| ('SP1', 'held-out')          |       949 | odds_ratio                      |     0.9485 |             -0.0012 |  1.2129 |     0.0826 |      0.1359 |         1.1558 |
| ('all', '2023/24')           |      1752 | multiplicative,odds_ratio,power |     0.9545 |             -0.0006 |  1.1121 |     0.0575 |      0.0716 |         1.0827 |
| ('all', '2024/25')           |      1752 | multiplicative,odds_ratio,power |     0.9628 |             -0.0007 |  1.0377 |     0.0543 |      0.0241 |         1.0245 |
| ('all', '2025/26')           |       902 | multiplicative,odds_ratio,power |     0.9627 |             -0.0006 |  1.1252 |     0.0818 |      0.0803 |         1.0914 |
| ('all', 'held-out')          |      4406 | multiplicative,odds_ratio,power |     0.9595 |             -0.0006 |  1.0834 |     0.0356 |      0.0533 |         1.0602 |
| ('all', 'train (in-sample)') |     19958 | multiplicative,odds_ratio,power |     0.9665 |             -0.0002 |  1.0187 |     0.0164 |      0.0119 |         1.0153 |

## Fallback: market-average closing odds (informational, not part of the verdict)

AvgCH/AvgCD/AvgCA exist from 2019/20 and are still published, so training here is 2019/20 to 2022/23.

|                              |   matches | method                                   |   log_loss |   vs_multiplicative |   slope |   slope_se |   intercept |   linear_slope |
|:-----------------------------|----------:|:-----------------------------------------|-----------:|--------------------:|--------:|-----------:|------------:|---------------:|
| ('D1', '2023/24')            |       306 | multiplicative                           |     0.9459 |              0      |  1.0847 |     0.13   |      0.054  |         1.0603 |
| ('D1', '2024/25')            |       306 | multiplicative                           |     0.987  |              0      |  0.9228 |     0.122  |     -0.0497 |         0.9277 |
| ('D1', '2025/26')            |       306 | multiplicative                           |     0.951  |              0      |  1.2699 |     0.1657 |      0.174  |         1.2116 |
| ('E0', '2023/24')            |       380 | multiplicative                           |     0.9007 |              0      |  1.2201 |     0.1206 |      0.1382 |         1.1576 |
| ('E0', '2024/25')            |       380 | multiplicative                           |     0.9667 |              0      |  0.992  |     0.1116 |     -0.0051 |         0.9873 |
| ('E0', '2025/26')            |       380 | multiplicative                           |     1.0118 |              0      |  0.9202 |     0.1193 |     -0.0518 |         0.9167 |
| ('F1', '2023/24')            |       306 | odds_ratio                               |     1.014  |              0.0004 |  0.9255 |     0.1391 |     -0.0484 |         0.9216 |
| ('F1', '2024/25')            |       306 | odds_ratio                               |     0.9549 |             -0.0006 |  1.0872 |     0.1374 |      0.0555 |         1.0743 |
| ('F1', '2025/26')            |       306 | odds_ratio                               |     0.975  |             -0.0004 |  1.009  |     0.1286 |      0.0058 |         0.9963 |
| ('I1', '2023/24')            |       380 | power                                    |     0.966  |             -0.0008 |  1.0955 |     0.135  |      0.0611 |         1.0794 |
| ('I1', '2024/25')            |       380 | power                                    |     0.9502 |             -0.0021 |  1.1555 |     0.121  |      0.0986 |         1.1082 |
| ('I1', '2025/26')            |       380 | power                                    |     0.9783 |             -0.0002 |  0.9812 |     0.1191 |     -0.0119 |         0.9873 |
| ('SP1', '2023/24')           |       380 | additive                                 |     0.9474 |             -0.0024 |  1.215  |     0.131  |      0.1368 |         1.1566 |
| ('SP1', '2024/25')           |       380 | additive                                 |     0.9449 |             -0.0013 |  1.1426 |     0.1281 |      0.0904 |         1.1092 |
| ('SP1', '2025/26')           |       379 | additive                                 |     0.9642 |             -0.0024 |  1.1832 |     0.1312 |      0.118  |         1.1335 |
| ('D1', 'held-out')           |       918 | multiplicative                           |     0.9613 |              0      |  1.0767 |     0.079  |      0.0492 |         1.0571 |
| ('E0', 'held-out')           |      1140 | multiplicative                           |     0.9597 |              0      |  1.0531 |     0.0667 |      0.0338 |         1.0357 |
| ('F1', 'held-out')           |       918 | odds_ratio                               |     0.9813 |             -0.0002 |  1.0125 |     0.0775 |      0.008  |         1.0045 |
| ('I1', 'held-out')           |      1140 | power                                    |     0.9648 |             -0.001  |  1.0742 |     0.0722 |      0.0472 |         1.0569 |
| ('SP1', 'held-out')          |      1139 | additive                                 |     0.9522 |             -0.002  |  1.179  |     0.0753 |      0.1142 |         1.1321 |
| ('all', '2023/24')           |      1752 | additive,multiplicative,odds_ratio,power |     0.9527 |             -0.0006 |  1.1217 |     0.058  |      0.0776 |         1.0906 |
| ('all', '2024/25')           |      1752 | additive,multiplicative,odds_ratio,power |     0.9599 |             -0.0009 |  1.0598 |     0.0552 |      0.0381 |         1.0428 |
| ('all', '2025/26')           |      1751 | additive,multiplicative,odds_ratio,power |     0.9772 |             -0.0006 |  1.0577 |     0.058  |      0.037  |         1.0426 |
| ('all', 'held-out')          |      5255 | additive,multiplicative,odds_ratio,power |     0.9632 |             -0.0007 |  1.0798 |     0.0329 |      0.051  |         1.0589 |
| ('all', 'train (in-sample)') |      7203 | additive,multiplicative,odds_ratio,power |     0.9752 |             -0.0002 |  1.0022 |     0.0279 |      0.0014 |         1.0051 |

## D4: current-season (2026/27) closing-column fill rate

Share of played matches with all three columns of each 1X2 triple present:

| league   |   matches |   PSCH/PSCD/PSCA |   PSH/PSD/PSA |   AvgC* |   B365C* |   BFEC* | last PSC* match (any season)   |
|:---------|----------:|-----------------:|--------------:|--------:|---------:|--------:|:-------------------------------|
| D1       |        36 |                0 |             0 |       1 |        1 |       1 | 2026-01-14                     |
| E0       |        50 |                0 |             0 |       1 |        1 |       1 | 2026-01-08                     |
| F1       |        45 |                0 |             0 |       1 |        1 |       1 | 2026-01-04                     |
| I1       |        50 |                0 |             0 |       1 |        1 |       1 | 2026-01-14                     |
| SP1      |        69 |                0 |             0 |       1 |        1 |       1 | 2026-01-12                     |
| all      |       250 |                0 |             0 |       1 |        1 |       1 |                                |

Previous season (2025/26), same table:

| league   |   matches |   PSCH/PSCD/PSCA |   PSH/PSD/PSA |   AvgC* |   B365C* |   BFEC* | last PSC* match (any season)   |
|:---------|----------:|-----------------:|--------------:|--------:|---------:|--------:|:-------------------------------|
| D1       |       306 |             0.49 |          0.49 |       1 |        1 |    0.94 | 2026-01-14                     |
| E0       |       380 |             0.55 |          0.55 |       1 |        1 |    0.94 | 2026-01-08                     |
| F1       |       306 |             0.5  |          0.5  |       1 |        1 |    0.94 | 2026-01-04                     |
| I1       |       380 |             0.52 |          0.53 |       1 |        1 |    0.94 | 2026-01-14                     |
| SP1      |       380 |             0.49 |          0.5  |       1 |        1 |    0.92 | 2026-01-12                     |
| all      |      1752 |             0.51 |          0.51 |       1 |        1 |    0.94 |                                |

The 2026/27 raw CSVs have no PS* columns at all (`PP*` is Paddy Power, not Pinnacle).

## Limitations

- One bookmaker (Pinnacle) and five top leagues; results may not carry to lower leagues or other books.
- Per-league per-season slopes rest on 150-380 matches, so their SEs are about 0.1-0.26; the verdict therefore gates on pooled slopes and shows the per-league per-season rows for inspection only.
- The methods differ by tiny amounts in log loss (1e-4 range); the choice per league is weakly identified, and the chosen method beats multiplicative by only a few 1e-4 on held-out matches.
- 2025/26 is only the first half of the season (Pinnacle data ends mid-January 2026).
- No current-season Pinnacle data exists in the source, so calibration on the live season is untested.

## How to reproduce

From `roster/` (needs WP0-B's football-data Parquet; run `python -m history.footballdata` first if missing):

```
.venv\Scripts\python.exe research\devig\devig.py      # ~2-3 min, rewrites this report
.venv\Scripts\python.exe -m pytest research/devig -q  # unit tests
```
