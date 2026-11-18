# Phase 5 analysis smoke (WP5-A: roles 32, 33, 34, 02)

Seeded synthetic set (seed 0): modes crypto-term, crypto-hourly, sports-pregame; strategies ladder-maker, speed-taker; 80 clusters per mode (240 total); 960 closed positions, 1920 fills, 1440 forecast checkpoints. Planted: negative CLV and fee-net primary in ('crypto-hourly', 'speed-taker'); variance (good CLV, clean markout, unlucky outcomes, primary < 0) in ('sports-pregame', 'ladder-maker'); markout_5m drift of -1 SD of the per-cluster mean (-0.00707) on market series ('crypto-term', 'ETH') from cluster 50. Every number is computed within one mode; SEs are CR1 by cluster (clustered_mean). Nothing here is applied: candidates are proposals only.

## 1. Breakdown (role 32)

| mode | dim | key | pos | fills | clusters | CLV | mo 5s | mo 1m | mo 5m | primary | reward | rebate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| crypto-hourly | all | all | 320 | 640 | 80 | -0.0121 ± 0.0010 | 0.0008 ± 0.0002 | 0.0017 ± 0.0003 | 0.0022 ± 0.0004 | -0.0229 ± 0.0080 | 0.00 | 0.64 |
| crypto-hourly | underlying | BTC | 160 | 320 | 80 | -0.0121 ± 0.0014 | 0.0007 ± 0.0003 | 0.0012 ± 0.0004 | 0.0018 ± 0.0005 | -0.0192 ± 0.0113 | 0.00 | 0.32 |
| crypto-hourly | underlying | ETH | 80 | 160 | 80 | 0.0049 ± 0.0024 | 0.0013 ± 0.0004 | 0.0028 ± 0.0007 | 0.0031 ± 0.0009 | 0.0004 ± 0.0165 | 0.00 | 0.32 |
| crypto-hourly | underlying | SOL | 80 | 160 | 80 | -0.0289 ± 0.0019 | 0.0005 ± 0.0004 | 0.0018 ± 0.0007 | 0.0022 ± 0.0008 | -0.0534 ± 0.0160 | 0.00 | 0.00 |
| crypto-hourly | horizon | <=1h | 75 | 150 | 53 | -0.0103 ± 0.0022 | 0.0008 ± 0.0005 | 0.0010 ± 0.0006 | 0.0016 ± 0.0008 | -0.0220 ± 0.0188 | 0.00 | 0.14 |
| crypto-hourly | horizon | <=24h | 82 | 164 | 59 | -0.0126 ± 0.0025 | 0.0008 ± 0.0004 | 0.0020 ± 0.0007 | 0.0022 ± 0.0010 | -0.0184 ± 0.0177 | 0.00 | 0.18 |
| crypto-hourly | horizon | <=6h | 87 | 174 | 60 | -0.0145 ± 0.0024 | 0.0010 ± 0.0004 | 0.0021 ± 0.0007 | 0.0028 ± 0.0008 | -0.0318 ± 0.0153 | 0.00 | 0.16 |
| crypto-hourly | horizon | >24h | 76 | 152 | 55 | -0.0105 ± 0.0029 | 0.0008 ± 0.0004 | 0.0017 ± 0.0007 | 0.0023 ± 0.0008 | -0.0183 ± 0.0179 | 0.00 | 0.16 |
| crypto-hourly | strategy | ladder-maker | 160 | 320 | 80 | 0.0041 ± 0.0017 | 0.0011 ± 0.0003 | 0.0017 ± 0.0005 | 0.0023 ± 0.0006 | 0.0060 ± 0.0118 | 0.00 | 0.64 |
| crypto-hourly | strategy | speed-taker | 160 | 320 | 80 | -0.0282 ± 0.0015 | 0.0006 ± 0.0003 | 0.0018 ± 0.0005 | 0.0022 ± 0.0005 | -0.0517 ± 0.0121 | 0.00 | 0.00 |
| crypto-term | all | all | 320 | 640 | 80 | 0.0021 ± 0.0011 | 0.0006 ± 0.0002 | 0.0011 ± 0.0003 | 0.0015 ± 0.0004 | 0.0332 ± 0.0097 | 0.00 | 0.64 |
| crypto-term | underlying | BTC | 160 | 320 | 80 | 0.0034 ± 0.0016 | 0.0006 ± 0.0003 | 0.0015 ± 0.0005 | 0.0020 ± 0.0005 | 0.0355 ± 0.0134 | 0.00 | 0.32 |
| crypto-term | underlying | ETH | 80 | 160 | 80 | 0.0016 ± 0.0024 | -0.0000 ± 0.0004 | -0.0004 ± 0.0006 | -0.0002 ± 0.0008 | 0.0194 ± 0.0153 | 0.00 | 0.32 |
| crypto-term | underlying | SOL | 80 | 160 | 80 | 0.0001 ± 0.0025 | 0.0010 ± 0.0004 | 0.0017 ± 0.0007 | 0.0021 ± 0.0009 | 0.0425 ± 0.0171 | 0.00 | 0.00 |
| crypto-term | horizon | <=1h | 82 | 164 | 59 | 0.0053 ± 0.0020 | 0.0009 ± 0.0004 | 0.0012 ± 0.0006 | 0.0018 ± 0.0008 | 0.0389 ± 0.0175 | 0.00 | 0.16 |
| crypto-term | horizon | <=24h | 83 | 166 | 56 | -0.0021 ± 0.0022 | 0.0002 ± 0.0003 | 0.0008 ± 0.0006 | 0.0010 ± 0.0007 | 0.0408 ± 0.0178 | 0.00 | 0.16 |
| crypto-term | horizon | <=6h | 85 | 170 | 56 | 0.0019 ± 0.0017 | 0.0008 ± 0.0004 | 0.0014 ± 0.0006 | 0.0020 ± 0.0008 | 0.0488 ± 0.0191 | 0.00 | 0.16 |
| crypto-term | horizon | >24h | 70 | 140 | 50 | 0.0038 ± 0.0027 | 0.0003 ± 0.0004 | 0.0009 ± 0.0007 | 0.0010 ± 0.0009 | -0.0012 ± 0.0194 | 0.00 | 0.15 |
| crypto-term | strategy | ladder-maker | 160 | 320 | 80 | 0.0014 ± 0.0015 | 0.0004 ± 0.0003 | 0.0006 ± 0.0004 | 0.0011 ± 0.0005 | 0.0285 ± 0.0132 | 0.00 | 0.64 |
| crypto-term | strategy | speed-taker | 160 | 320 | 80 | 0.0029 ± 0.0016 | 0.0008 ± 0.0003 | 0.0015 ± 0.0005 | 0.0019 ± 0.0006 | 0.0379 ± 0.0131 | 0.00 | 0.00 |
| sports-pregame | all | all | 320 | 640 | 80 | 0.0227 ± 0.0008 | 0.0043 ± 0.0002 | 0.0076 ± 0.0003 | 0.0110 ± 0.0003 | -0.0121 ± 0.0081 | 0.00 | 0.64 |
| sports-pregame | league | EPL | 160 | 320 | 80 | 0.0215 ± 0.0011 | 0.0042 ± 0.0003 | 0.0077 ± 0.0004 | 0.0110 ± 0.0004 | -0.0086 ± 0.0120 | 0.00 | 0.32 |
| sports-pregame | league | NBA | 160 | 320 | 80 | 0.0240 ± 0.0015 | 0.0044 ± 0.0003 | 0.0076 ± 0.0004 | 0.0109 ± 0.0004 | -0.0155 ± 0.0112 | 0.00 | 0.32 |
| sports-pregame | horizon | <=1h | 88 | 176 | 57 | 0.0195 ± 0.0023 | 0.0034 ± 0.0005 | 0.0066 ± 0.0008 | 0.0091 ± 0.0011 | 0.0046 ± 0.0166 | 0.00 | 0.16 |
| sports-pregame | horizon | <=24h | 79 | 158 | 57 | 0.0288 ± 0.0022 | 0.0055 ± 0.0004 | 0.0097 ± 0.0006 | 0.0139 ± 0.0009 | -0.0152 ± 0.0142 | 0.00 | 0.20 |
| sports-pregame | horizon | <=6h | 82 | 164 | 60 | 0.0224 ± 0.0027 | 0.0045 ± 0.0005 | 0.0080 ± 0.0007 | 0.0115 ± 0.0010 | -0.0222 ± 0.0168 | 0.00 | 0.17 |
| sports-pregame | horizon | >24h | 71 | 142 | 50 | 0.0205 ± 0.0024 | 0.0039 ± 0.0006 | 0.0063 ± 0.0008 | 0.0093 ± 0.0011 | -0.0178 ± 0.0185 | 0.00 | 0.12 |
| sports-pregame | strategy | ladder-maker | 160 | 320 | 80 | 0.0404 ± 0.0008 | 0.0079 ± 0.0002 | 0.0139 ± 0.0004 | 0.0199 ± 0.0003 | -0.0403 ± 0.0118 | 0.00 | 0.64 |
| sports-pregame | strategy | speed-taker | 160 | 320 | 80 | 0.0051 ± 0.0015 | 0.0007 ± 0.0003 | 0.0014 ± 0.0004 | 0.0020 ± 0.0005 | 0.0161 ± 0.0116 | 0.00 | 0.00 |

### Budget candidates (proposals only, budget 1.0 per strategy)

- crypto-term: no change (None)
- crypto-hourly: `budgets:crypto-hourly` -> {'budgets': {'ladder-maker': 1.0, 'speed-taker': 0.5}, 'unallocated': 0.5}
- sports-pregame: `budgets:sports-pregame` -> {'budgets': {'ladder-maker': 0.5, 'speed-taker': 1.0}, 'unallocated': 0.5}

## 2. Reliability (role 32)

Scores on identical rows (resolved, with both p and mid_ex_own). diff = p minus baseline (negative = p better); gap = traded minus universe (selection effect).

| mode | dim | key | subset | rows | clusters | Brier p | Brier mid | Brier diff | LL p | LL mid | LL diff |
|---|---|---|---|---|---|---|---|---|---|---|---|
| crypto-hourly | all | all | universe | 469 | 80 | 0.1771 | 0.1778 | -0.0007 ± 0.0025 | 0.5256 | 0.5319 | -0.0063 ± 0.0082 |
| crypto-hourly | all | all | traded | 255 | 80 | 0.1877 | 0.1881 | -0.0004 ± 0.0044 | 0.5479 | 0.5572 | -0.0093 ± 0.0150 |
| crypto-hourly | all | all | gap | 255 | 80 | 0.0107 | 0.0104 | 0.0003 | 0.0223 | 0.0253 | -0.0030 |
| crypto-hourly | underlying | BTC | universe | 157 | 80 | 0.1940 | 0.1947 | -0.0007 ± 0.0037 | 0.5629 | 0.5661 | -0.0032 ± 0.0096 |
| crypto-hourly | underlying | BTC | traded | 80 | 59 | 0.2016 | 0.2038 | -0.0021 ± 0.0071 | 0.5769 | 0.5855 | -0.0086 ± 0.0178 |
| crypto-hourly | underlying | BTC | gap | 80 | 59 | 0.0076 | 0.0091 | -0.0015 | 0.0140 | 0.0193 | -0.0054 |
| crypto-hourly | underlying | ETH | universe | 156 | 80 | 0.1755 | 0.1782 | -0.0027 ± 0.0045 | 0.5239 | 0.5349 | -0.0110 ± 0.0127 |
| crypto-hourly | underlying | ETH | traded | 89 | 68 | 0.1652 | 0.1684 | -0.0032 ± 0.0074 | 0.4942 | 0.5092 | -0.0151 ± 0.0213 |
| crypto-hourly | underlying | ETH | gap | 89 | 68 | -0.0103 | -0.0099 | -0.0004 | -0.0298 | -0.0257 | -0.0041 |
| crypto-hourly | underlying | SOL | universe | 156 | 80 | 0.1616 | 0.1602 | 0.0013 ± 0.0050 | 0.4897 | 0.4945 | -0.0047 ± 0.0205 |
| crypto-hourly | underlying | SOL | traded | 86 | 65 | 0.1981 | 0.1940 | 0.0041 ± 0.0089 | 0.5766 | 0.5806 | -0.0040 ± 0.0373 |
| crypto-hourly | underlying | SOL | gap | 86 | 65 | 0.0365 | 0.0338 | 0.0027 | 0.0869 | 0.0862 | 0.0007 |
| crypto-hourly | horizon | <=1h | universe | 128 | 72 | 0.1750 | 0.1825 | -0.0075 ± 0.0054 | 0.5253 | 0.5611 | -0.0358 ± 0.0249 |
| crypto-hourly | horizon | <=1h | traded | 66 | 47 | 0.1987 | 0.2144 | -0.0157 ± 0.0103 | 0.5772 | 0.6482 | -0.0710 ± 0.0478 |
| crypto-hourly | horizon | <=1h | gap | 66 | 47 | 0.0237 | 0.0319 | -0.0082 | 0.0519 | 0.0871 | -0.0352 |
| crypto-hourly | horizon | <=24h | universe | 116 | 63 | 0.1483 | 0.1516 | -0.0032 ± 0.0057 | 0.4577 | 0.4610 | -0.0033 ± 0.0141 |
| crypto-hourly | horizon | <=24h | traded | 65 | 45 | 0.1592 | 0.1599 | -0.0007 ± 0.0099 | 0.4832 | 0.4779 | 0.0053 ± 0.0246 |
| crypto-hourly | horizon | <=24h | gap | 65 | 45 | 0.0108 | 0.0083 | 0.0025 | 0.0255 | 0.0169 | 0.0086 |
| crypto-hourly | horizon | <=6h | universe | 110 | 61 | 0.2011 | 0.1928 | 0.0084 ± 0.0048 | 0.5801 | 0.5599 | 0.0202 ± 0.0130 |
| crypto-hourly | horizon | <=6h | traded | 60 | 43 | 0.2381 | 0.2238 | 0.0144 ± 0.0088 | 0.6618 | 0.6288 | 0.0330 ± 0.0231 |
| crypto-hourly | horizon | <=6h | gap | 60 | 43 | 0.0370 | 0.0310 | 0.0060 | 0.0817 | 0.0688 | 0.0128 |
| crypto-hourly | horizon | >24h | universe | 115 | 63 | 0.1853 | 0.1845 | 0.0008 ± 0.0055 | 0.5423 | 0.5442 | -0.0019 ± 0.0137 |
| crypto-hourly | horizon | >24h | traded | 64 | 47 | 0.1582 | 0.1563 | 0.0018 ± 0.0096 | 0.4767 | 0.4770 | -0.0003 ± 0.0241 |
| crypto-hourly | horizon | >24h | gap | 64 | 47 | -0.0272 | -0.0282 | 0.0010 | -0.0656 | -0.0672 | 0.0016 |
| crypto-term | all | all | universe | 471 | 80 | 0.1816 | 0.1856 | -0.0040 ± 0.0031 | 0.5410 | 0.5480 | -0.0069 ± 0.0090 |
| crypto-term | all | all | traded | 268 | 80 | 0.1788 | 0.1858 | -0.0070 ± 0.0053 | 0.5347 | 0.5473 | -0.0127 ± 0.0152 |
| crypto-term | all | all | gap | 268 | 80 | -0.0027 | 0.0002 | -0.0030 | -0.0064 | -0.0006 | -0.0057 |
| crypto-term | underlying | BTC | universe | 157 | 79 | 0.1909 | 0.2001 | -0.0093 ± 0.0055 | 0.5636 | 0.5798 | -0.0162 ± 0.0154 |
| crypto-term | underlying | BTC | traded | 91 | 62 | 0.2038 | 0.2190 | -0.0152 ± 0.0095 | 0.5918 | 0.6177 | -0.0259 ± 0.0265 |
| crypto-term | underlying | BTC | gap | 91 | 62 | 0.0129 | 0.0189 | -0.0059 | 0.0282 | 0.0379 | -0.0097 |
| crypto-term | underlying | ETH | universe | 160 | 80 | 0.1733 | 0.1769 | -0.0036 ± 0.0045 | 0.5157 | 0.5298 | -0.0141 ± 0.0134 |
| crypto-term | underlying | ETH | traded | 89 | 66 | 0.1600 | 0.1674 | -0.0074 ± 0.0079 | 0.4899 | 0.5173 | -0.0274 ± 0.0235 |
| crypto-term | underlying | ETH | gap | 89 | 66 | -0.0133 | -0.0095 | -0.0038 | -0.0258 | -0.0125 | -0.0133 |
| crypto-term | underlying | SOL | universe | 154 | 80 | 0.1807 | 0.1799 | 0.0008 ± 0.0049 | 0.5443 | 0.5343 | 0.0100 ± 0.0143 |
| crypto-term | underlying | SOL | traded | 88 | 68 | 0.1720 | 0.1701 | 0.0019 ± 0.0083 | 0.5209 | 0.5049 | 0.0160 ± 0.0235 |
| crypto-term | underlying | SOL | gap | 88 | 68 | -0.0087 | -0.0097 | 0.0011 | -0.0234 | -0.0294 | 0.0060 |
| crypto-term | horizon | <=1h | universe | 113 | 68 | 0.1541 | 0.1662 | -0.0121 ± 0.0050 | 0.4792 | 0.5083 | -0.0291 ± 0.0131 |
| crypto-term | horizon | <=1h | traded | 62 | 45 | 0.1368 | 0.1596 | -0.0228 ± 0.0086 | 0.4264 | 0.4811 | -0.0548 ± 0.0227 |
| crypto-term | horizon | <=1h | gap | 62 | 45 | -0.0173 | -0.0066 | -0.0107 | -0.0528 | -0.0271 | -0.0257 |
| crypto-term | horizon | <=24h | universe | 122 | 69 | 0.2002 | 0.1955 | 0.0047 ± 0.0061 | 0.5862 | 0.5697 | 0.0165 ± 0.0169 |
| crypto-term | horizon | <=24h | traded | 68 | 47 | 0.2082 | 0.1997 | 0.0085 ± 0.0108 | 0.6114 | 0.5826 | 0.0288 ± 0.0302 |
| crypto-term | horizon | <=24h | gap | 68 | 47 | 0.0080 | 0.0042 | 0.0038 | 0.0252 | 0.0129 | 0.0123 |
| crypto-term | horizon | <=6h | universe | 109 | 60 | 0.1984 | 0.2034 | -0.0049 ± 0.0064 | 0.5820 | 0.5904 | -0.0084 ± 0.0202 |
| crypto-term | horizon | <=6h | traded | 58 | 39 | 0.1663 | 0.1760 | -0.0096 ± 0.0117 | 0.5125 | 0.5305 | -0.0179 ± 0.0373 |
| crypto-term | horizon | <=6h | gap | 58 | 39 | -0.0321 | -0.0274 | -0.0047 | -0.0694 | -0.0599 | -0.0095 |
| crypto-term | horizon | >24h | universe | 127 | 67 | 0.1736 | 0.1781 | -0.0044 ± 0.0064 | 0.5175 | 0.5260 | -0.0086 ± 0.0176 |
| crypto-term | horizon | >24h | traded | 80 | 51 | 0.1955 | 0.2015 | -0.0060 ± 0.0101 | 0.5694 | 0.5809 | -0.0115 ± 0.0279 |
| crypto-term | horizon | >24h | gap | 80 | 51 | 0.0219 | 0.0234 | -0.0015 | 0.0520 | 0.0549 | -0.0029 |
| sports-pregame | all | all | universe | 471 | 80 | 0.1884 | 0.1896 | -0.0012 ± 0.0025 | 0.5532 | 0.5575 | -0.0043 ± 0.0069 |
| sports-pregame | all | all | traded | 271 | 80 | 0.2046 | 0.2074 | -0.0028 ± 0.0042 | 0.5896 | 0.6002 | -0.0106 ± 0.0117 |
| sports-pregame | all | all | gap | 271 | 80 | 0.0162 | 0.0178 | -0.0016 | 0.0364 | 0.0427 | -0.0062 |
| sports-pregame | league | EPL | universe | 234 | 80 | 0.1830 | 0.1822 | 0.0008 ± 0.0032 | 0.5432 | 0.5423 | 0.0009 ± 0.0092 |
| sports-pregame | league | EPL | traded | 125 | 73 | 0.1994 | 0.1987 | 0.0008 ± 0.0057 | 0.5817 | 0.5834 | -0.0017 ± 0.0164 |
| sports-pregame | league | EPL | gap | 125 | 73 | 0.0164 | 0.0164 | -0.0000 | 0.0385 | 0.0411 | -0.0026 |
| sports-pregame | league | NBA | universe | 237 | 80 | 0.1937 | 0.1969 | -0.0032 ± 0.0040 | 0.5631 | 0.5726 | -0.0095 ± 0.0107 |
| sports-pregame | league | NBA | traded | 146 | 76 | 0.2090 | 0.2149 | -0.0059 ± 0.0064 | 0.5964 | 0.6146 | -0.0182 ± 0.0173 |
| sports-pregame | league | NBA | gap | 146 | 76 | 0.0153 | 0.0180 | -0.0027 | 0.0334 | 0.0421 | -0.0087 |
| sports-pregame | horizon | <=1h | universe | 121 | 69 | 0.1782 | 0.1797 | -0.0014 ± 0.0050 | 0.5265 | 0.5307 | -0.0042 ± 0.0129 |
| sports-pregame | horizon | <=1h | traded | 68 | 52 | 0.2026 | 0.2061 | -0.0036 ± 0.0088 | 0.5809 | 0.5912 | -0.0103 ± 0.0232 |
| sports-pregame | horizon | <=1h | gap | 68 | 52 | 0.0243 | 0.0265 | -0.0021 | 0.0544 | 0.0605 | -0.0061 |
| sports-pregame | horizon | <=24h | universe | 116 | 68 | 0.2146 | 0.2123 | 0.0023 ± 0.0057 | 0.6171 | 0.6122 | 0.0050 ± 0.0148 |
| sports-pregame | horizon | <=24h | traded | 67 | 53 | 0.2373 | 0.2363 | 0.0010 ± 0.0096 | 0.6640 | 0.6678 | -0.0038 ± 0.0250 |
| sports-pregame | horizon | <=24h | gap | 67 | 53 | 0.0227 | 0.0239 | -0.0012 | 0.0469 | 0.0556 | -0.0088 |
| sports-pregame | horizon | <=6h | universe | 117 | 65 | 0.1583 | 0.1577 | 0.0006 ± 0.0042 | 0.4840 | 0.4841 | -0.0001 ± 0.0122 |
| sports-pregame | horizon | <=6h | traded | 65 | 49 | 0.1750 | 0.1730 | 0.0020 ± 0.0077 | 0.5237 | 0.5211 | 0.0026 ± 0.0224 |
| sports-pregame | horizon | <=6h | gap | 65 | 49 | 0.0167 | 0.0153 | 0.0015 | 0.0397 | 0.0370 | 0.0027 |
| sports-pregame | horizon | >24h | universe | 117 | 64 | 0.2029 | 0.2093 | -0.0063 ± 0.0049 | 0.5867 | 0.6046 | -0.0179 ± 0.0142 |
| sports-pregame | horizon | >24h | traded | 71 | 52 | 0.2027 | 0.2130 | -0.0103 ± 0.0079 | 0.5882 | 0.6174 | -0.0292 ± 0.0229 |
| sports-pregame | horizon | >24h | gap | 71 | 52 | -0.0003 | 0.0037 | -0.0040 | 0.0015 | 0.0128 | -0.0113 |

### Reliability bins (universe, all keys)

| mode | bin | mean p | freq ± SE | rows | clusters |
|---|---|---|---|---|---|
| crypto-hourly | 0.0-0.1 | 0.065 | 0.000 ± 0.000 | 25 | 25 |
| crypto-hourly | 0.1-0.2 | 0.151 | 0.162 ± 0.061 | 37 | 32 |
| crypto-hourly | 0.2-0.3 | 0.258 | 0.118 ± 0.041 | 51 | 41 |
| crypto-hourly | 0.3-0.4 | 0.353 | 0.426 ± 0.073 | 54 | 46 |
| crypto-hourly | 0.4-0.5 | 0.448 | 0.469 ± 0.064 | 64 | 45 |
| crypto-hourly | 0.5-0.6 | 0.553 | 0.475 ± 0.084 | 40 | 34 |
| crypto-hourly | 0.6-0.7 | 0.648 | 0.679 ± 0.072 | 53 | 39 |
| crypto-hourly | 0.7-0.8 | 0.752 | 0.725 ± 0.062 | 51 | 39 |
| crypto-hourly | 0.8-0.9 | 0.849 | 0.812 ± 0.044 | 64 | 50 |
| crypto-hourly | 0.9-1.0 | 0.935 | 0.967 ± 0.034 | 30 | 27 |
| crypto-term | 0.0-0.1 | 0.061 | 0.154 ± 0.071 | 26 | 23 |
| crypto-term | 0.1-0.2 | 0.152 | 0.100 ± 0.049 | 40 | 34 |
| crypto-term | 0.2-0.3 | 0.247 | 0.167 ± 0.053 | 54 | 42 |
| crypto-term | 0.3-0.4 | 0.349 | 0.415 ± 0.075 | 53 | 39 |
| crypto-term | 0.4-0.5 | 0.450 | 0.422 ± 0.073 | 45 | 33 |
| crypto-term | 0.5-0.6 | 0.553 | 0.600 ± 0.067 | 55 | 39 |
| crypto-term | 0.6-0.7 | 0.652 | 0.667 ± 0.065 | 54 | 41 |
| crypto-term | 0.7-0.8 | 0.748 | 0.705 ± 0.058 | 61 | 45 |
| crypto-term | 0.8-0.9 | 0.844 | 0.825 ± 0.046 | 57 | 41 |
| crypto-term | 0.9-1.0 | 0.934 | 1.000 ± 0.000 | 26 | 23 |
| sports-pregame | 0.0-0.1 | 0.069 | 0.043 ± 0.044 | 23 | 22 |
| sports-pregame | 0.1-0.2 | 0.155 | 0.149 ± 0.052 | 47 | 39 |
| sports-pregame | 0.2-0.3 | 0.257 | 0.333 ± 0.059 | 51 | 36 |
| sports-pregame | 0.3-0.4 | 0.349 | 0.450 ± 0.070 | 40 | 32 |
| sports-pregame | 0.4-0.5 | 0.445 | 0.413 ± 0.073 | 46 | 38 |
| sports-pregame | 0.5-0.6 | 0.548 | 0.530 ± 0.064 | 66 | 48 |
| sports-pregame | 0.6-0.7 | 0.647 | 0.706 ± 0.061 | 51 | 41 |
| sports-pregame | 0.7-0.8 | 0.751 | 0.753 ± 0.052 | 73 | 46 |
| sports-pregame | 0.8-0.9 | 0.854 | 0.846 ± 0.050 | 52 | 42 |
| sports-pregame | 0.9-1.0 | 0.937 | 0.955 ± 0.046 | 22 | 21 |

## 3. Postmortem classes and lessons (role 33)

Classification reads only clv, markout_5m, fee_per_share, flags, mode, strategy; `primary` is read only by lessons(), after classification.

| mode | strategy | resolution_wording | data_provenance | model | execution | indeterminate | variance |
|---|---|---|---|---|---|---|---|
| crypto-term | ladder-maker | 0 | 1 | 20 | 3 | 133 | 3 |
| crypto-term | speed-taker | 0 | 3 | 19 | 4 | 126 | 8 |
| crypto-hourly | ladder-maker | 0 | 1 | 22 | 1 | 131 | 5 |
| crypto-hourly | speed-taker | 0 | 6 | 117 | 1 | 36 | 0 |
| sports-pregame | ladder-maker | 0 | 7 | 0 | 0 | 1 | 152 |
| sports-pregame | speed-taker | 0 | 3 | 15 | 3 | 130 | 9 |

Lessons (clusters >= 20 and mean + 1.645 SE < 0): 1

| name | clusters | mean | SE | importance now | importance +30 d |
|---|---|---|---|---|---|
| `lesson:crypto-hourly:speed-taker:model` | 72 | -0.0585 | 0.0139 | 4.20 | 2.10 |

- Planted negative group ('crypto-hourly', 'speed-taker'): lesson found = **True**.
- Planted variance group ('sports-pregame', 'ladder-maker'): lesson found = **False** (its variance-class primary is -0.0369 ± 0.0121, significantly negative, and still produces no lesson: variance is not a mistake).

## 4. CUSUM threshold (roles 02 and 34)

Stated system size (one-sided monitors x clusters per 2 weeks):

| monitors | n_series | clusters / 2 weeks |
|---|---|---|
| role 02 markout lock, daily market series | 40 | 14 |
| role 02 markout lock, hourly market series | 10 | 336 |
| role 02 CLV lock, (mode, strategy) | 8 | 14 |
| role 34 bias drift, 30 keys x 2 directions | 60 | 14 |
| role 34 error-corr drift, 3 pairs x 2 directions (W = 30) | 6 | 1 |

Null: seeded iid N(0, 1), 5,000 clusters (placeholder until real per-cluster series exist, A14 [ops]); k = 0.5, block = 5, B = 2,000, budget 1 false trip per 2 weeks.

- Calibrated h = **6.7**, estimated system-wide false trips per 2 weeks = 0.939.
- Fresh simulation (new null sample, new seed) at h = 6.7: 0.812 per 2 weeks.
- Sensitivity: h on three other 5,000-cluster null samples = [6.3, 6.2, 6.4] (the null sample's tails matter, most for the 336-cluster hourly family; calibrate on the real series, A14 [ops]).

ARL check (one-sided, k = 0.5, iid N(0, 1), seeded paths):

| h | paths | simulated ARL | Siegmund | ratio |
|---|---|---|---|---|
| 4.0 | 4000 | 332.9 | 338.1 | 0.985 |
| 6.7 | 1000 | 5176.5 | 5196.5 | 0.996 |

## 5. Planted drift (role 02 markout lock = role 34 per-market drift)

Per-cluster mean markout_5m per (mode, market series), standardised on the first 20 clusters, low CUSUM at h = 6.7. Trips:

| scope | cluster index | cluster_id | action | reason |
|---|---|---|---|---|
| crypto-term:ETH | 65 | crypto-term#065 | lock | markout CUSUM low: S=6.95 > h=6.7 |

- Planted drift on ('crypto-term', 'ETH') from cluster 50: tripped at cluster **65** (15 clusters after the shift).
- Other trips (false alarms in this sample): 0.
- No action is `halt`; actions are only `lock` (role 02) and `alarm` (role 34).

## How to reproduce

From `roster/`:

```
.venv\Scripts\python.exe -m learning.analyst --smoke --seed 0
.venv\Scripts\python.exe -m pytest tests/phase5/test_analysis.py -q
```

Offline and deterministic (seeded). Synthetic rows follow the dispatch's forecast, fill and closed-position shapes.
