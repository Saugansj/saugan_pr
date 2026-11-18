# Phase C status

Written 18 Nov 2026 21:54 IST by ops/phase_c.py (plan: phase_c_plan_2026-10-20.md). Live estimate per trade, cluster SE by market; days to the bar assume the mean, spread and pace so far hold. Uptime: share of the last 7 days' minutes with a running, unpaused loop, counted over the 67 h the PC was on (the gate) and over all 168 h (for reference).

| Run | Trades | Live $/trade | SE | Over 2 SE? | Trades/day | Days to the bar | Uptime (PC on) | Uptime (24 h) |
|---|---|---|---|---|---|---|---|---|
| paper_v4b | 783 | +0.292 | 0.072 | yes | 27 | 0.0 | 98% | 39% |
| paper_v7b | 311 | +0.446 | 0.103 | yes | 15 | 0.0 | 98% | 39% |
| paper_v4add | 359 | +0.348 | 0.120 | yes | 90 | 0.0 | 80% | 32% |
| paper_v4sz50 | 65 | -0.162 | 0.419 | no | 32 | n/a | 20% | 8% |
| paper_v4sz100 | 75 | +0.011 | 0.389 | no | 38 | 9227.2 | 23% | 9% |
| paper_v9fix | 9 | +0.239 | 0.732 | no | 9 | 36.5 | 13% | 5% |

## Phase D gate (all three needed)

- [x] a run passes 2 SE at the live estimate over 200+ trades: paper_v4b, paper_v7b, paper_v4add
- [x] BTC: out-of-sample PASS and the forward BTC live estimate agrees (> 0): OOS PASS, forward BTC +0.303/trade
- [x] that run was trading-ready >= 90% of the hours the PC was on (last 7 days): paper_v4b 98%, paper_v7b 98%, paper_v4add 80%

Gate met is not a go-live: Phase D still needs the ToS check, a Dublin server, wallet funding and a 1-2 share canary, each decided by the user.
