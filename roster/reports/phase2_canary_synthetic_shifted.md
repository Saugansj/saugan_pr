# Phase 2 canary evaluation (2.8)

**SYNTHETIC rows with the [0, 1) live fill probability shifted 0.6 -> 0.98 (negative control); not live evidence**

- live rows: `C:\Users\DELL\AppData\Local\Temp\claude\c--Users-DELL-Downloads-saugan-pr-market-updated\9bf560a4-c423-4051-bcba-9ee1eb0199bf\scratchpad\wp2d\synthetic_live_shifted.jsonl`
- replay rows: `C:\Users\DELL\AppData\Local\Temp\claude\c--Users-DELL-Downloads-saugan-pr-market-updated\9bf560a4-c423-4051-bcba-9ee1eb0199bf\scratchpad\wp2d\synthetic_replay.jsonl`
- live clusters: 60 (60 with a fill; need 30); replay clusters: 400
- bootstrap: 2000 draws, seed 0; interval = replay's 5th-95th percentile with the live bucket's cluster count

## Verdict: FAIL

outside replay's 90% interval: [0, 1) fill_rate. recalibrate the fill simulator and re-run replay before continuing

## Per queue bucket (queue_ahead / own size)

| bucket | live orders | live clusters | with fill | replay clusters | fill rate | replay 90% PI | markout 5m | replay 90% PI | outside |
|---|---|---|---|---|---|---|---|---|---|
| [0, 1) | 130 | 57 | 57 | 367 | 0.9673 | [0.5198, 0.6710] | -0.0143 | [-0.0151, -0.0060] | fill_rate |
| [1, 5) | 121 | 55 | 30 | 357 | 0.3428 | [0.3138, 0.4816] | -0.0032 | [-0.0057, 0.0044] | - |
| [5, 20) | 117 | 54 | 16 | 351 | 0.1801 | [0.1152, 0.2480] | 0.0012 | [-0.0066, 0.0112] | - |
| [20, inf) | 112 | 53 | 5 | 370 | 0.0403 | [0.0207, 0.1027] | 0.0110 | [-0.0065, 0.0275] | - |

## How to reproduce

From `roster/`:

```
python -m trader.live.canary --live C:\Users\DELL\AppData\Local\Temp\claude\c--Users-DELL-Downloads-saugan-pr-market-updated\9bf560a4-c423-4051-bcba-9ee1eb0199bf\scratchpad\wp2d\synthetic_live_shifted.jsonl --replay C:\Users\DELL\AppData\Local\Temp\claude\c--Users-DELL-Downloads-saugan-pr-market-updated\9bf560a4-c423-4051-bcba-9ee1eb0199bf\scratchpad\wp2d\synthetic_replay.jsonl --seed 0 --n-boot 2000 --out <this file>
```
