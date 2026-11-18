# Phase 5 replay-lab smoke (WP5-B, role 35)

Every number here is **exploratory**: about two minutes of recorded books, unresolved positions marked at the last mid excluding our orders, no kernel. Nothing was sent anywhere; fills come from `learning/replay/fills.py` in strict (paper) mode.

## Engine `ladder` (trader.engines.ladder.LadderEngine, unmodified)

- Window: 2026-09-30 14:29:01 UTC to 2026-09-30 14:30:59 UTC; round trip 210.0 ms.
- Engine source `trader/engines/ladder.py` sha256 `cce1e23c5faeedf2...` (imported, not copied).
- Reference feed: Binance 1s klines for the window, fetched in memory by a public GET (common.get_json). DVOL from data/history/deribit (1h, recorded at candle close).
- Look-ahead tripwire: 42527 engine calls, 14289072 input checks, **0 violations**.
- B1 on the real file: the store's books at 2026-09-30 14:30:00 UTC (316 tokens) equal `trader.marketdata.Books` fed the same messages.

| events read | count |
|---|---|
| book | 84780 |
| markets | 1 |
| msg:dvol | 4 |
| msg:final | 4 |
| msg:markets | 1 |
| msg:pm | 46643 |
| msg:ref | 474 |
| ref | 474 |
| tick | 324 |
| trade | 58 |

| result | value |
|---|---|
| intents | 826 (maker 826) |
| kernel decisions | approved: no kernel given: 826 |
| orders accepted by the fill model | 826 of 826 |
| refused by the fill model | none |
| maker cancels (target diff) | 826 |
| fills maker / taker | 0 (0 sh) / 0 (0 sh) |
| fees paid (USD) | 0 |
| open positions at the end | 0 |
| fee-net P&L per cluster (exploratory) | mean None USD, SE None, clusters 0, unresolved 0 |
| random-entry baseline | no strategy entries filled, so there is nothing to permute |
| trials logged in family `replay:ladder-maker` | 2 |

Zero fills: 58 trades were recorded in the window and none traded through a resting maker's price or cleared its queue ahead before the target diff cancelled it (826 cancels).

## Engine `speed` (trader.engines.speed.SpeedEngine, unmodified)

- Window: 2026-09-30 14:29:03 UTC to 2026-09-30 14:30:59 UTC; round trip 210.0 ms.
- Engine source `trader/engines/speed.py` sha256 `9f98145a3456ad1c...` (imported, not copied).
- Reference feed: Binance 1s klines for the window, fetched in memory by a public GET (common.get_json). DVOL from data/history/deribit (1h, recorded at candle close).
- Look-ahead tripwire: 38992 engine calls, 5614848 input checks, **0 violations**.
- B1 on the real file: the store's books at 2026-09-30 14:30:01 UTC (124 tokens) equal `trader.marketdata.Books` fed the same messages.

| events read | count |
|---|---|
| book | 77075 |
| markets | 1 |
| msg:dvol | 4 |
| msg:final | 4 |
| msg:markets | 1 |
| msg:pm | 40763 |
| msg:ref | 470 |
| ref | 470 |
| tick | 248 |
| trade | 343 |

| result | value |
|---|---|
| intents | 0 (none) |
| kernel decisions | none |
| orders accepted by the fill model | 0 of 0 |
| refused by the fill model | none |
| maker cancels (target diff) | 0 |
| fills maker / taker | 0 (0 sh) / 0 (0 sh) |
| fees paid (USD) | 0 |
| open positions at the end | 0 |
| fee-net P&L per cluster (exploratory) | mean None USD, SE None, clusters 0, unresolved 0 |
| random-entry baseline | no strategy entries filled, so there is nothing to permute |
| trials logged in family `replay:btc-speed` | 2 |

Zero intents: btc-speed fires on a >= 10 bp move within 5 s; the largest 5 s move in the window was 7.374969764450717 bp for BTC, and its detector fired 0 time(s).

## DSR and PBO on a seeded synthetic trial set

20 trials x 500 periods of iid N(0, 1), trial 0 with a +0.2 SD edge per period (seed 7).

| check | value |
|---|---|
| PBO (S = 16), edge trial included | 0.061 |
| PBO (S = 16), noise trials only | 0.363 |
| edge trial: SR, SR0, DSR (N = 20) | 0.1966, 0.1332, 0.9204 |
| best noise trial: SR, SR0, DSR (N = 19) | 0.0991, 0.1003, 0.4891 |
| best noise trial undeflated: PSR(0) | 0.9865 |

## How to reproduce

From `roster/`:

```
.venv\Scripts\python.exe -m learning.replay --engine ladder
.venv\Scripts\python.exe -m learning.replay --engine speed
.venv\Scripts\python.exe -m pytest tests/phase5/test_replay.py -q
```

Data read (read-only): `data/recordings/parquet/stream=crypto-term|crypto-fast/date=2026-09-30/14.parquet`, `data/markets/2026-09-30T142859Z.jsonl`, `data/history/deribit/dvol_*_1h.parquet`, `data/history/binance/*` (finals). Written: `learning/replay/out/` and this report.
