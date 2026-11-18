# Shadow scores: proposed btc-speed changes on the control runs

Written 18 Nov 2026 21:53 IST by ops/shadow.py. Each filter is scored on the trades it would have skipped in the control run (v4b for BTC, ethb for ETH), each limit on the same trades repriced with that order limit, all at the live estimate (real tape, behind the race). Judged from 17 Oct IST: a change is adopted only after 60 eligible trades and 2 cluster SE (skip: the skipped trades lost; limit: beats ask+10c paired). Nothing here changes a run; adopting means a new pre-registration.

### BTC, since 17 Oct (690 trades)

| Filter | Skipped | Skipped mean $/trade | Kept mean | Verdict |
|---|---|---|---|---|
| v6 band: skip ask 0.30-0.50 | 170 | +0.353 +/- 0.177 | +0.307 | no change: not 2 SE |
| skip > 600 s left | 195 | +0.340 +/- 0.149 | +0.310 | no change: not 2 SE |
| 15m: skip 5-10 min left | 58 | +0.488 +/- 0.224 | +0.303 | collecting (58/60) |
| cap: skip ask > 0.70 | 147 | +0.088 +/- 0.139 | +0.381 | no change: not 2 SE |

| Limit (ask + c, cap 0.85) | Live total $ | Mean vs ask+10c, paired $/trade | Verdict |
|---|---|---|---|
| +3c | +194.61 | -0.036 +/- 0.044 | no change: not 2 SE |
| +4c | +208.44 | -0.016 +/- 0.039 | no change: not 2 SE |
| +10c (live rule) | +219.69 | - | control |

### ETH, since 17 Oct (342 trades)

| Filter | Skipped | Skipped mean $/trade | Kept mean | Verdict |
|---|---|---|---|---|
| v6 band: skip ask 0.30-0.50 | 89 | -0.010 +/- 0.210 | +0.100 | no change: not 2 SE |
| skip move >= 7 bp | 27 | -0.357 +/- 0.271 | +0.108 | collecting (27/60) |
| 15m: skip 5-10 min left | 25 | -0.080 +/- 0.316 | +0.083 | collecting (25/60) |

| Limit (ask + c, cap 0.85) | Live total $ | Mean vs ask+10c, paired $/trade | Verdict |
|---|---|---|---|
| +3c | +21.11 | -0.010 +/- 0.066 | no change: not 2 SE |
| +4c | +17.00 | -0.022 +/- 0.059 | no change: not 2 SE |
| +10c (live rule) | +24.36 | - | control |

## Context only (every control trade, includes the days the leads were found in: not a test)

### BTC, all days (783 trades)

| Filter | Skipped | Skipped mean $/trade | Kept mean | Verdict |
|---|---|---|---|---|
| v6 band: skip ask 0.30-0.50 | 197 | +0.307 +/- 0.159 | +0.288 | no change: not 2 SE |
| skip > 600 s left | 223 | +0.313 +/- 0.138 | +0.284 | no change: not 2 SE |
| 15m: skip 5-10 min left | 72 | +0.311 +/- 0.198 | +0.291 | no change: not 2 SE |
| cap: skip ask > 0.70 | 167 | +0.063 +/- 0.130 | +0.355 | no change: not 2 SE |

| Limit (ask + c, cap 0.85) | Live total $ | Mean vs ask+10c, paired $/trade | Verdict |
|---|---|---|---|
| +3c | +209.81 | -0.024 +/- 0.042 | no change: not 2 SE |
| +4c | +224.74 | -0.005 +/- 0.038 | no change: not 2 SE |
| +10c (live rule) | +228.98 | - | control |

### ETH, all days (548 trades)

| Filter | Skipped | Skipped mean $/trade | Kept mean | Verdict |
|---|---|---|---|---|
| v6 band: skip ask 0.30-0.50 | 135 | +0.172 +/- 0.170 | +0.060 | no change: not 2 SE |
| skip move >= 7 bp | 39 | -0.493 +/- 0.211 | +0.132 | collecting (39/60) |
| 15m: skip 5-10 min left | 44 | -0.216 +/- 0.226 | +0.114 | collecting (44/60) |

| Limit (ask + c, cap 0.85) | Live total $ | Mean vs ask+10c, paired $/trade | Verdict |
|---|---|---|---|
| +3c | +19.45 | -0.052 +/- 0.054 | no change: not 2 SE |
| +4c | +13.13 | -0.064 +/- 0.049 | no change: not 2 SE |
| +10c (live rule) | +48.09 | - | control |
