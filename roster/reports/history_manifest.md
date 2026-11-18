# History manifest (WP0-B, build-plan task 0.5)

Generated 2026-09-30 16:43 UTC by `history/manifest.py`. All data is public and
read-only; nothing here needs a key.

| Dataset                     | Path (under roster/)                      | Date range (UTC)         | Rows          | Gaps                                                              |
|:----------------------------|:------------------------------------------|:-------------------------|:--------------|:------------------------------------------------------------------|
| Binance BTCUSDT 1m          | data/history/binance/BTCUSDT/             | 2022-01-01 to 2026-09-29 | 2,495,440     | 1 days not 1,440 rows                                             |
| Binance ETHUSDT 1m          | data/history/binance/ETHUSDT/             | 2022-01-01 to 2026-09-29 | 2,495,440     | 1 days not 1,440 rows                                             |
| Deribit dvol_BTC_1D         | data/history/deribit/dvol_BTC_1D.parquet  | 2022-01-01 to 2026-09-30 | 1,734         | none                                                              |
| Deribit dvol_BTC_1h         | data/history/deribit/dvol_BTC_1h.parquet  | 2022-01-01 to 2026-09-30 | 41,609        | none                                                              |
| Deribit dvol_ETH_1D         | data/history/deribit/dvol_ETH_1D.parquet  | 2022-01-01 to 2026-09-30 | 1,734         | none                                                              |
| Deribit dvol_ETH_1h         | data/history/deribit/dvol_ETH_1h.parquet  | 2022-01-01 to 2026-09-30 | 41,609        | none                                                              |
| Polymarket markets catalog  | data/history/polymarket/markets.parquet   | 2022-09-23 to 2026-09-30 | 9,809 markets | —                                                                 |
| Polymarket 1m price history | data/history/polymarket/prices/           | 2025-10-05 to 2026-09-30 | 156,828,147   | 0 downloaded markets without prices; 655 events pending           |
| Polymarket trades           | data/history/polymarket/trades/           | 2025-10-05 to 2026-09-30 | 8,040,741     | 0 downloaded markets without trades                               |
| football-data matches       | data/history/footballdata/matches.parquet | 2012-08-10 to 2026-09-20 | 25,491        | 2026/27: no Pinnacle columns; 2025/26 Pinnacle stops mid-Jan 2026 |

## Binance spot 1m klines

Source: data.binance.vision monthly zips (daily zips for the current month). Every zip is checked against its `.CHECKSUM` (sha256) before its Parquet is written; a mismatch writes nothing. Timestamps are UTC epoch ms (files from 2025 on ship microseconds; converted).

### BTCUSDT

- Path: `data/history/binance/BTCUSDT/` (56 monthly + 29 daily Parquet files)
- Range: 2022-01-01 00:00:00 to 2026-09-29 23:59:00 UTC, 1733 days, 2,495,440 rows (2,495,440 distinct minutes)
- Checksum-verified files: 85 of 85
- Days without exactly 1,440 rows (rows): 2023-03-24 (1360; Binance halted spot trading for about 80 minutes that day)

### ETHUSDT

- Path: `data/history/binance/ETHUSDT/` (56 monthly + 29 daily Parquet files)
- Range: 2022-01-01 00:00:00 to 2026-09-29 23:59:00 UTC, 1733 days, 2,495,440 rows (2,495,440 distinct minutes)
- Checksum-verified files: 85 of 85
- Days without exactly 1,440 rows (rows): 2023-03-24 (1360; Binance halted spot trading for about 80 minutes that day)

## Deribit DVOL

Source: `public/get_volatility_index_data` (1000 candles per call, paged backwards by `continuation`). Columns ts (UTC epoch ms, candle start), open, high, low, close. Historical option IVs by strike are not available free from Deribit's public API; DVOL is the proxy.

| File | Range (UTC) | Rows | Gaps (missing candles) |
|---|---|---|---|
| `data/history/deribit/dvol_BTC_1D.parquet` | 2022-01-01 00:00 to 2026-09-30 00:00 | 1,734 | none |
| `data/history/deribit/dvol_BTC_1h.parquet` | 2022-01-01 00:00 to 2026-09-30 16:00 | 41,609 | none |
| `data/history/deribit/dvol_ETH_1D.parquet` | 2022-01-01 00:00 to 2026-09-30 00:00 | 1,734 | none |
| `data/history/deribit/dvol_ETH_1h.parquet` | 2022-01-01 00:00 to 2026-09-30 16:00 | 41,609 | none |

## Polymarket closed daily BTC/ETH markets

Catalog: Gamma `/events?series_id=…&closed=true` for series 41/40 (BTC/ETH Up or Down Daily), 45/42 (BTC/ETH
"above ___ on <date>" ladders; Gamma files them under a "weekly" series slug) and 12043/12044 (BTC/ETH Multi
Strikes Daily, no closed events yet). Kept: markets on the Binance-1m-close-at-12:00-ET template ("above" strikes and
Up/Down; range buckets dropped). Settlement time = 12:00 America/New_York on the date named in the question.

- `data/history/polymarket/markets.parquet`: one row per market: condition_id, asset, mode, question, strike,
  settle_date, settle_ts_ms, start/end/closed times, yes/no token ids and outcome labels, yes_final_price, winner,
  uma_status, volume, tick_size, min_size, neg_risk, verbatim rules and rules_sha256.
- `data/history/polymarket/prices/<event_slug>.parquet`: CLOB `/prices-history`, fidelity=1 (1 minute), both
  tokens, market start − 1h to close + 1h. Columns condition_id, token_id, outcome, t (UTC epoch s), p.
- `data/history/polymarket/trades/<event_slug>.parquet`: Data API `/trades` taker fills. Columns condition_id,
  token_id, outcome, outcome_index, side, price, size, timestamp (UTC epoch s), transaction_hash, proxy_wallet.

| asset   | mode   |   markets |   events |   settle_days | first_settle   | last_settle   |   with_outcome |   uma_not_resolved |   downloaded |
|:--------|:-------|----------:|---------:|--------------:|:---------------|:--------------|---------------:|-------------------:|-------------:|
| BTC     | strike |      4330 |      440 |           440 | 2023-04-12     | 2026-09-30    |           4330 |                 11 |         3804 |
| BTC     | updown |       563 |      563 |           563 | 2025-03-15     | 2026-09-30    |            563 |                  1 |          358 |
| ETH     | strike |      4361 |      500 |           499 | 2022-09-23     | 2026-09-30    |           4361 |                 18 |         3786 |
| ETH     | updown |       555 |      555 |           555 | 2025-03-19     | 2026-09-30    |            555 |                  1 |          357 |

Events downloaded: 1403 of 2058. Markets with price history for both tokens, trades and a known outcome: **8,305**.

- Price history: 156,828,147 rows, 16,610 tokens, 8,305 markets, 2025-10-05 16:03 to 2026-09-30 16:21 UTC
- Trades: 8,040,741 rows, 8,305 markets, 1,714,804,418 shares, 2025-10-05 16:11 to 2026-09-30 16:21 UTC
- Markets whose trades hit the offset cap (truncated): 10. `/trades` returns newest first, so these keep their
  newest 11,000 taker fills up to market close (the post-resolution window is complete); their oldest fills are missing.

Coverage of downloaded markets by settlement year (gaps = markets with no price or trade rows):

| asset   | mode   |   yr |   downloaded |   with_prices |   with_trades |
|:--------|:-------|-----:|-------------:|--------------:|--------------:|
| BTC     | strike | 2025 |          836 |           836 |           836 |
| BTC     | strike | 2026 |         2968 |          2968 |          2968 |
| BTC     | updown | 2025 |           86 |            86 |            86 |
| BTC     | updown | 2026 |          272 |           272 |           272 |
| ETH     | strike | 2025 |          853 |           853 |           853 |
| ETH     | strike | 2026 |         2933 |          2933 |          2933 |
| ETH     | updown | 2025 |           85 |            85 |            85 |
| ETH     | updown | 2026 |          272 |           272 |           272 |

### Polymarket API limits found

- `/prices-history`: `interval=max` (and `all`, `1d`) returns an **empty** history for closed markets; an explicit
  `startTs`/`endTs` works. The span may be at most **15 days** per call (400 "interval is too long"), so longer lives
  are fetched in 15-day windows. `fidelity=1` (1 minute) is the finest; points are the token's mid about once a
  minute. Markets older than the CLOB (pre late-2022) have no history.
- Data API `/trades`: `offset` is capped at **10,000** (400 "max historical trades offset of 10000 exceeded");
  `limit` above 1,000 is accepted. Default `takerOnly=true` returns one row per taker fill (maker legs excluded,
  which avoids double counting volume). `start`/`end` filters work if more depth is ever needed.
- Cloudflare returns 403 (error 1010) to the default Python user agent; every call sends `User-Agent: roster/0.1`.
- Gamma `endDate` is sometimes a day or a month away from the date in the question (46 markets); settle_date uses
  the question's date. `umaResolutionStatus` is "proposed" or missing on some markets, but `outcomePrices` is final.
- Not exposed historically: the order book (only mids via `/prices-history`), reward parameters in force at the time,
  and fee parameters at the time. Resolution disputes are not in Gamma beyond `umaResolutionStatus(es)`.
- Rate: one shared cap of 8 requests/s across 16 threads (the calls are latency-bound at ~1-2 s each). Failed
  events are left unwritten and picked up by the next run.

## football-data.co.uk

Source: `https://www.football-data.co.uk/mmz4281/<season>/<league>.csv`. Raw CSVs in
`data/history/footballdata/csv/`, combined into `data/history/footballdata/matches.parquet` with league, season,
Date, Time, teams, full-time and half-time goals and result, and 1X2 odds: Pinnacle (PSH/PSD/PSA as first
collected, PSCH/PSCD/PSCA closing), Bet365 (B365*), market average (Avg*), market maximum (Max*) and Betfair
Exchange (BFE*), each with its closing (C) variant. Columns a season lacks are null.

**Current season (2026/27) Pinnacle closing columns: NOT filled.**
football-data.co.uk stopped publishing Pinnacle odds in January 2026: the 2025/26 files have PSCH/PSCD/PSCA only up to
the dates below, and the 2026/27 files have no PS* columns at all (their `PP*` columns are Paddy Power, not
Pinnacle). Bet365, market average/maximum and Betfair Exchange closing odds are present for 2026/27.

| league   | last_pinnacle_close   |
|:---------|:----------------------|
| D1       | 2026-01-14            |
| E0       | 2026-01-08            |
| F1       | 2026-01-04            |
| I1       | 2026-01-14            |
| SP1      | 2026-01-12            |

Seasons with Pinnacle closing odds on ≥ 99% of matches, per league: D1 13, E0 13, F1 13, I1 13, SP1 13.

| league   | season   |   matches | first_match   | last_match   |   PSH % |   PSCH/D/A % |   AvgCH % |   BFECH % |
|:---------|:---------|----------:|:--------------|:-------------|--------:|-------------:|----------:|----------:|
| D1       | 2012/13  |       306 | 2012-08-24    | 2013-05-18   |     100 |          100 |         0 |         0 |
| D1       | 2013/14  |       306 | 2013-08-09    | 2014-05-10   |     100 |          100 |         0 |         0 |
| D1       | 2014/15  |       306 | 2014-08-22    | 2015-05-23   |     100 |          100 |         0 |         0 |
| D1       | 2015/16  |       306 | 2015-08-14    | 2016-05-14   |     100 |          100 |         0 |         0 |
| D1       | 2016/17  |       306 | 2016-08-26    | 2017-05-20   |     100 |          100 |         0 |         0 |
| D1       | 2017/18  |       306 | 2017-08-18    | 2018-05-12   |     100 |          100 |         0 |         0 |
| D1       | 2018/19  |       306 | 2018-08-24    | 2019-05-18   |     100 |          100 |         0 |         0 |
| D1       | 2019/20  |       306 | 2019-08-16    | 2020-06-27   |     100 |          100 |       100 |         0 |
| D1       | 2020/21  |       306 | 2020-09-18    | 2021-05-22   |     100 |          100 |       100 |         0 |
| D1       | 2021/22  |       306 | 2021-08-13    | 2022-05-14   |     100 |          100 |       100 |         0 |
| D1       | 2022/23  |       306 | 2022-08-05    | 2023-05-27   |     100 |          100 |       100 |         0 |
| D1       | 2023/24  |       306 | 2023-08-18    | 2024-05-18   |     100 |          100 |       100 |         0 |
| D1       | 2024/25  |       306 | 2024-08-23    | 2025-05-17   |     100 |          100 |       100 |       100 |
| D1       | 2025/26  |       306 | 2025-08-22    | 2026-05-16   |      49 |           49 |       100 |        94 |
| D1       | 2026/27  |        36 | 2026-08-28    | 2026-09-20   |       0 |            0 |       100 |       100 |
| E0       | 2012/13  |       380 | 2012-08-18    | 2013-05-19   |     100 |          100 |         0 |         0 |
| E0       | 2013/14  |       380 | 2013-08-17    | 2014-05-11   |     100 |          100 |         0 |         0 |
| E0       | 2014/15  |       380 | 2014-08-16    | 2015-05-24   |     100 |          100 |         0 |         0 |
| E0       | 2015/16  |       380 | 2015-08-08    | 2016-05-17   |     100 |          100 |         0 |         0 |
| E0       | 2016/17  |       380 | 2016-08-13    | 2017-05-21   |     100 |          100 |         0 |         0 |
| E0       | 2017/18  |       380 | 2017-08-11    | 2018-05-13   |     100 |          100 |         0 |         0 |
| E0       | 2018/19  |       380 | 2018-08-10    | 2019-05-12   |     100 |          100 |         0 |         0 |
| E0       | 2019/20  |       380 | 2019-08-09    | 2020-07-26   |     100 |          100 |       100 |         0 |
| E0       | 2020/21  |       380 | 2020-09-12    | 2021-05-23   |     100 |          100 |       100 |         0 |
| E0       | 2021/22  |       380 | 2021-08-13    | 2022-05-22   |     100 |          100 |       100 |         0 |
| E0       | 2022/23  |       380 | 2022-08-05    | 2023-05-28   |     100 |          100 |       100 |         0 |
| E0       | 2023/24  |       380 | 2023-08-11    | 2024-05-19   |     100 |          100 |       100 |         0 |
| E0       | 2024/25  |       380 | 2024-08-16    | 2025-05-25   |     100 |          100 |       100 |       100 |
| E0       | 2025/26  |       380 | 2025-08-15    | 2026-05-24   |      55 |           55 |       100 |        94 |
| E0       | 2026/27  |        50 | 2026-08-21    | 2026-09-20   |       0 |            0 |       100 |       100 |
| F1       | 2012/13  |       380 | 2012-08-10    | 2013-05-26   |     100 |          100 |         0 |         0 |
| F1       | 2013/14  |       380 | 2013-08-09    | 2014-05-17   |     100 |          100 |         0 |         0 |
| F1       | 2014/15  |       380 | 2014-08-08    | 2015-05-23   |     100 |          100 |         0 |         0 |
| F1       | 2015/16  |       380 | 2015-08-07    | 2016-05-14   |     100 |          100 |         0 |         0 |
| F1       | 2016/17  |       380 | 2016-08-12    | 2017-05-20   |      99 |          100 |         0 |         0 |
| F1       | 2017/18  |       380 | 2017-08-04    | 2018-05-19   |      99 |          100 |         0 |         0 |
| F1       | 2018/19  |       380 | 2018-08-10    | 2019-05-24   |     100 |          100 |         0 |         0 |
| F1       | 2019/20  |       279 | 2019-08-09    | 2020-03-08   |     100 |          100 |       100 |         0 |
| F1       | 2020/21  |       380 | 2020-08-21    | 2021-05-23   |      99 |          100 |       100 |         0 |
| F1       | 2021/22  |       380 | 2021-08-06    | 2022-05-21   |     100 |          100 |       100 |         0 |
| F1       | 2022/23  |       380 | 2022-08-05    | 2023-06-03   |     100 |          100 |       100 |         0 |
| F1       | 2023/24  |       306 | 2023-08-11    | 2024-05-19   |     100 |          100 |       100 |         0 |
| F1       | 2024/25  |       306 | 2024-08-16    | 2025-05-17   |     100 |          100 |       100 |       100 |
| F1       | 2025/26  |       306 | 2025-08-15    | 2026-05-17   |      50 |           50 |       100 |        94 |
| F1       | 2026/27  |        45 | 2026-08-21    | 2026-09-20   |       0 |            0 |       100 |       100 |
| I1       | 2012/13  |       380 | 2012-08-25    | 2013-05-19   |      99 |           99 |         0 |         0 |
| I1       | 2013/14  |       380 | 2013-08-24    | 2014-05-18   |     100 |          100 |         0 |         0 |
| I1       | 2014/15  |       380 | 2014-08-30    | 2015-05-31   |     100 |          100 |         0 |         0 |
| I1       | 2015/16  |       380 | 2015-08-22    | 2016-05-15   |     100 |          100 |         0 |         0 |
| I1       | 2016/17  |       380 | 2016-08-20    | 2017-05-28   |      99 |          100 |         0 |         0 |
| I1       | 2017/18  |       380 | 2017-08-19    | 2018-05-20   |     100 |          100 |         0 |         0 |
| I1       | 2018/19  |       380 | 2018-08-18    | 2019-05-26   |     100 |          100 |         0 |         0 |
| I1       | 2019/20  |       380 | 2019-08-24    | 2020-08-02   |     100 |          100 |       100 |         0 |
| I1       | 2020/21  |       380 | 2020-09-19    | 2021-05-23   |      99 |          100 |       100 |         0 |
| I1       | 2021/22  |       380 | 2021-08-21    | 2022-05-22   |     100 |          100 |       100 |         0 |
| I1       | 2022/23  |       380 | 2022-08-13    | 2023-06-04   |     100 |          100 |       100 |         0 |
| I1       | 2023/24  |       380 | 2023-08-19    | 2024-06-02   |     100 |          100 |       100 |         0 |
| I1       | 2024/25  |       380 | 2024-08-17    | 2025-05-25   |     100 |          100 |       100 |       100 |
| I1       | 2025/26  |       380 | 2025-08-23    | 2026-05-24   |      53 |           52 |       100 |        94 |
| I1       | 2026/27  |        50 | 2026-08-22    | 2026-09-20   |       0 |            0 |       100 |       100 |
| SP1      | 2012/13  |       380 | 2012-08-18    | 2013-06-01   |     100 |          100 |         0 |         0 |
| SP1      | 2013/14  |       380 | 2013-08-17    | 2014-05-18   |     100 |          100 |         0 |         0 |
| SP1      | 2014/15  |       380 | 2014-08-23    | 2015-05-23   |      99 |          100 |         0 |         0 |
| SP1      | 2015/16  |       380 | 2015-08-21    | 2016-05-15   |     100 |          100 |         0 |         0 |
| SP1      | 2016/17  |       380 | 2016-08-19    | 2017-05-21   |     100 |          100 |         0 |         0 |
| SP1      | 2017/18  |       380 | 2017-08-18    | 2018-05-20   |     100 |          100 |         0 |         0 |
| SP1      | 2018/19  |       380 | 2018-08-17    | 2019-05-19   |     100 |          100 |         0 |         0 |
| SP1      | 2019/20  |       380 | 2019-08-16    | 2020-07-19   |      99 |          100 |       100 |         0 |
| SP1      | 2020/21  |       380 | 2020-09-12    | 2021-05-23   |     100 |          100 |       100 |         0 |
| SP1      | 2021/22  |       380 | 2021-08-13    | 2022-05-22   |     100 |          100 |       100 |         0 |
| SP1      | 2022/23  |       380 | 2022-08-12    | 2023-06-04   |     100 |          100 |       100 |         0 |
| SP1      | 2023/24  |       380 | 2023-08-11    | 2024-05-26   |     100 |          100 |       100 |         0 |
| SP1      | 2024/25  |       380 | 2024-08-15    | 2025-05-25   |     100 |          100 |       100 |       100 |
| SP1      | 2025/26  |       380 | 2025-08-15    | 2026-05-24   |      50 |           49 |       100 |        92 |
| SP1      | 2026/27  |        69 | 2026-08-15    | 2026-09-20   |       0 |            0 |       100 |       100 |

## How to reproduce

From `roster/` with `.venv\Scripts\python.exe` (each downloader is idempotent: a rerun skips finished files and
resumes after an interruption):

```
.venv\Scripts\python.exe -m history.binance        # ~2 min; --start 2022-01 --symbols BTCUSDT ETHUSDT
.venv\Scripts\python.exe -m history.deribit        # ~1 min; --start 2022-01-01
.venv\Scripts\python.exe -m history.footballdata   # ~2 min; --leagues E0 SP1 D1 I1 F1 --first 2012
.venv\Scripts\python.exe -m history.polymarket     # ~1-2 h at 8 req/s; --limit N for a smoke run
.venv\Scripts\python.exe -m history.manifest       # rewrites this file
.venv\Scripts\python.exe -m pytest history -q      # unit tests
```
