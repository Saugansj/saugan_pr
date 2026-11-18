# Recorder smoke run: WP0-A (data collection)

Build-plan tasks 0.1 to 0.4. Run on the build PC (Windows 11, Python 3.13) on 2026-09-30, against the live public APIs. No keys were used and no orders were placed.

## 1. Crawler (task 0.2)

`python -m recorder.crawler --fast` started at 14:34:49 UTC. It took 99 s and wrote 462 markets to `data/markets/2026-09-30T143449Z.jsonl` (933 KB).

| Mode | Rows | Events | What it covers | Tick size | negRisk | Taker fee rate | seconds_delay |
|---|---|---|---|---|---|---|---|
| `crypto-term` | 158 | 18 | BTC and ETH daily strike ladders ("above $X on <date>", 12:00 ET), 7 days ahead, plus daily Up/Down | 0.001 on 110, 0.01 on 48 | false | 0.07 | 0 |
| `crypto-hourly` | 96 | 96 | BTC and ETH hourly Up/Down, 48 h ahead | 0.01 | false | 0.07 | 0 |
| `sports-pregame` | 144 | 48 | Moneyline (home, draw, away) for EPL, La Liga, Bundesliga, Serie A and Ligue 1, 14 days ahead | 0.01 on 142, 0.001 on 2 | true | 0.05 | 1 |
| `crypto-fast` (`--fast`) | 64 | 64 | BTC and ETH 5m/15m Up/Down, 2 h ahead | 0.01 | false | 0.07 | 0 |

Every enabled mode that exists live has rows, and all 462 CLOB calls succeeded (`clob_ok` is true on every row). This crawl found no rules-hash or tick-size changes against the previous snapshot. Detecting a change is covered by a test with fixture snapshots.

A later crawl ran at 17:02:24 UTC, inside the fix-round live check (section 6). It wrote `data/markets/2026-09-30T170224Z.jsonl` with 467 markets: crypto-term 158, crypto-hourly 97, sports-pregame 144, crypto-fast 68. `clob_ok` was true on all of them, and the only null was again `event_start_time` on the strike rows. Compared with the 14:34 snapshot, it logged 3 real `tick_size` changes (0.01 -> 0.001) to `data/markets/changes.jsonl`, on `ethereum-above-2800-on-october-1-2026`, `ethereum-above-2900-on-october-4-2026` and `ethereum-up-or-down-september-30-2026-12pm-et`. Snapshots are now written to `<stamp>.tmp` and renamed into place, so a crash mid-write cannot leave a truncated snapshot that the recorder would fail to seed from.

**Where each field comes from.** A market is found through Gamma `/events`. Crypto markets are found by the `bitcoin` and `ethereum` tags plus a slug pattern, because Gamma tags daily strikes as "weekly". Soccer markets are found by Gamma series id plus `sportsMarketType == "moneyline"`. The crawler then calls CLOB `/markets/{condition_id}` for each market. Where both APIs have a field, the CLOB value is used.

| Field | Source |
|---|---|
| condition id, question, market and event slug | Gamma |
| YES/NO token ids and outcome names | CLOB `tokens` (for Up/Down markets, YES = Up and NO = Down) |
| verbatim rules text, `rules_sha256` | Gamma `description`, sha256 of the exact UTF-8 text |
| fee parameters | Gamma `feeSchedule` {rate, exponent, takerOnly, rebateRate}, `feeType`, `feesEnabled`; CLOB `maker_base_fee` / `taker_base_fee` |
| tick size, minimum order size, negRisk | CLOB `minimum_tick_size`, `minimum_order_size`, `neg_risk` |
| augmented flag | Gamma event `negRiskAugmented`; the market-level `negRiskOther` is also kept |
| reward min size, max spread, daily rate | CLOB `rewards` {min_size, max_spread, rates[].rewards_daily_rate} |
| holding-reward eligibility | Gamma `holdingRewardsEnabled` |
| open, event start and end time | Gamma `startDate`; CLOB `game_start_time` or Gamma `eventStartTime`; Gamma `endDate` |
| taker delay | CLOB `seconds_delay` |

**Fields the APIs don't expose, or expose only partly**

- `event_start_time` is null on the 154 strike-ladder rows ("above $X"). A strike market has no start period: neither Gamma nor CLOB gives one, and it settles at `end_time`. The daily Up/Down, hourly, fast and soccer rows all have it.
- `reward_daily_rate` is 0.0 on all 462 rows. CLOB returns `rewards.rates: null` for every target market today, which means there is no reward pool. The `min_size` of 50 and `max_spread` of 4.5 are platform defaults. The public `/rewards/markets/current` list (18,482 markets) agrees: it contains none of our markets. This matters for task 0.10 (reward income).
- The crypto taker delay (150 ms in the plan) is not exposed. `seconds_delay` is a whole number of seconds and shows 0 for crypto. For soccer it shows 1.
- `maker_base_fee` / `taker_base_fee` are 1000 on every market, whatever the real fee. The real fee is in `feeSchedule` (rate 0.07 crypto, 0.05 sports, takerOnly, rebate 0.20 / 0.15).
- There is no separate field for clarifications. They are appended to `description`, so they change `rules_sha256`, and the change is logged.
- Tick size is not fixed: 48 daily-strike rows are at 0.01, not the 0.001 the plan expects. The market WebSocket sent 12 `tick_size_change` events during the 2-minute smoke run.

## 2. Recorder smoke run (task 0.3)

`python -m recorder.recorder --fast --seconds 120` ran from 14:28:58 to 14:31:00 UTC. It started recording at once, using the latest snapshot's token sets:

- `crypto-term`: 316 tokens
- `crypto-hourly`: 192 tokens
- `sports-pregame`: 288 tokens
- `crypto-fast`: 128 tokens

The process exited about 50 s after the 120 s stop, because it waited for the background crawl thread to finish.

| Stream | Lines | JSONL bytes | Span | Longest silence | Message types |
|---|---|---|---|---|---|
| crypto-term | 46,643 | 32,397,701 | 117 s | 0.7 s | price_change 42,174; best_bid_ask 4,278; book 116; last_trade_price 58; PONG 8; tick_size_change 8; initial book list 1 |
| crypto-hourly | 14,768 | 10,777,408 | 117 s | 1.1 s | price_change 13,604; best_bid_ask 1,120; book 18; PONG 12; last_trade_price 9; tick_size_change 4; initial book list 1 |
| sports-pregame | 1,059 | 1,279,283 | 117 s | 3.5 s | price_change 1,036; PONG 12; best_bid_ask 4; book 4; last_trade_price 2; initial book list 1 |
| crypto-fast | 40,763 | 31,667,701 | 116 s | 4.0 s | price_change 38,069; best_bid_ask 1,652; book 689; last_trade_price 343; PONG 8; initial book list 2 |
| deribit-btc | 2 | 935,741 | 60 s | 59.8 s | 2 snapshots of 946 option summaries |
| deribit-eth | 2 | 781,684 | 60 s | 59.9 s | 2 snapshots of 800 option summaries |

- Each line is `{"t": <local receive ms>, "raw": "<verbatim message>"}` in `data/recordings/<stream>/2026-09-30/14.jsonl`.
- **Gaps inside the run:** none. The longest silence on a WebSocket stream was 4.0 s, against a 5-minute gap threshold.
- **Reconnects:** one. The server dropped `crypto-fast` without a close frame at 14:30:39 UTC, just after a 5-minute market closed. The recorder reconnected, got a fresh book list and was writing again 1.1 s later. The reconnect path is also tested offline with a local server that drops the connection.
- **Write speed:** an earlier run of the same smoke test reopened the file for every message, which costs 1.5 ms each. At about 800 messages/s across the streams, that saturated the event loop, and the server dropped the two busiest connections. The recorder now keeps the current hour's file open and line-buffered, which costs 0.05 ms per message. That earlier run's data was deleted.

## 3. Compaction, bytes per day and shed rule (task 0.4)

`python -m recorder.compact` ran at 15:00:28 UTC, once hour 14 had closed. Each file was converted with DuckDB `COPY ... (FORMAT parquet, COMPRESSION zstd)` to `data/recordings/parquet/stream=<s>/date=2026-09-30/14.parquet`. The JSONL was deleted only after the row counts matched.

| Stream | JSONL rows | Parquet rows (DuckDB read-back) | JSONL bytes | Parquet bytes | Ratio | Projected GB/day, compressed |
|---|---|---|---|---|---|---|
| crypto-term | 46,643 | 46,643 | 32,397,701 | 3,585,037 | 9.0x | 2.64 |
| crypto-hourly | 14,768 | 14,768 | 10,777,408 | 1,078,928 | 10.0x | 0.80 |
| sports-pregame | 1,059 | 1,059 | 1,279,283 | 146,489 | 8.7x | 0.11 |
| crypto-fast | 40,763 | 40,763 | 31,667,701 | 3,118,599 | 10.2x | 2.32 |
| deribit-btc | 2 | 2 | 935,741 | 76,956 | 12.2x | 0.06 |
| deribit-eth | 2 | 2 | 781,684 | 59,334 | 13.2x | 0.04 |

The per-day projection scales each stream's 2-minute rate up to 24 h. Deribit is projected as 1,440 snapshots a day.

**Storage finding: the default streams are over the plan's 1 GB/day target.** GB here means 10^9 bytes. Without `--fast`, they project to about 3.65 GB/day compressed; with `--fast`, about 6.0 GB/day. `price_change` makes up about 90% of all WebSocket messages. The sample was taken at 10:29 ET, 1.5 h before the 12:00 ET daily settlement, when the ladder is busiest.

The rate changes a lot through the day, so treat these figures as a range, not a daily average:

- **17:02 UTC (13:02 ET), after settlement:** a second 90 s sample on the current code, compacted the same way. The default streams projected to about 1.4 GB/day: crypto-term 0.78, crypto-hourly 0.43, sports-pregame 0.10, Deribit about 0.10. This run was seeded from the 14:34 snapshot, whose same-day ladder had already settled, so it is on the low side.
- **16:42 UTC, audit run:** the audit measured crypto-fast at about 5.5 GB/day and crypto-term at about 0.63 GB/day.

Both samples are still over 1 GB/day. The daily bytes-per-stream output on the VM will give the real figure.

What that means for the 150 GiB budget (`--budget-gb` is in GiB, 1024^3 bytes, so 150 GiB is about 161 GB):

- **Default streams, at the busy-hour rate:** 30 days hot is about 109.5 GB (102 GiB), 68% of the budget. That is under the 85% shed line because compaction also deletes Parquet days older than `--keep-days 30`.
- **4-week latency test (`--fast`):** at this rate, the 85% line is reached in about 23 days. The shed rule would then drop `crypto-fast` before the 4 weeks are up. Ways out, for a human to choose:
  - narrow the crypto-term horizon from 8 days, since most traffic is on today's ladder;
  - raise the budget;
  - accept a shorter latency window.

**Shed rule.** `compact` prints usage against `--budget-gb`. At 85% or more, it deletes the data of the lowest-priority stream that still has data, adds that stream to `data/recordings/shed.json` and repeats until usage is under 85%. The recorder checks `shed.json` every 10 s, together with its `PING`. When a stream is listed, it closes that stream's WebSocket and its open hourly file, so the space of the deleted file is freed. It does not reconnect that stream. Before the fix it only reacted at the next hourly crawl. The default order, lowest priority first, is:

`crypto-fast, sports-pregame, crypto-hourly, deribit-eth, deribit-btc, crypto-term`

It can be changed with `--shed-order`.

- **Real run:** usage 8,065,343 bytes, 0.01% of 150 GiB, so nothing was dropped.
- **Filled test volume:** the same smoke data was copied to a scratch folder with a 9,000,000-byte budget. Usage was 89.6%, the shed rule dropped `crypto-fast` only, and usage fell to 55.0%. The unit test `test_shed_drops_lowest_priority_first_at_85_percent` covers the thresholds, skipping streams with no data, and continuing until usage is under 85%.

## 4. Gap check

`python -m recorder.gapcheck 2026-09-30` counts a gap as more than 5 minutes with no message. It reads both the JSONL and the Parquet, and it exits with code 1 when a day has gaps. For the smoke day, every stream shows the same two gaps, and both are correct:

- 00:00 to 14:29 UTC, before the run started;
- 14:31 UTC to the time of the check, after the run stopped.

**Inside the 2-minute run there are no gaps.** The longest silence per stream (a DuckDB window query over the Parquet, below) was:

| Stream | Longest silence |
|---|---|
| crypto-term | 0.68 s |
| crypto-hourly | 1.14 s |
| sports-pregame | 3.52 s |
| crypto-fast | 4.03 s |
| deribit-btc, deribit-eth | about 60 s (the snapshot interval) |

The recorder sends `PING` every 10 s and records the server's `PONG`, so a live connection is never silent for more than about 10 s, even on a quiet soccer market. A gap therefore means the recorder or the feed was down.

The gaps are computed inside DuckDB (`lag(t) OVER (ORDER BY t)`), and only the gap rows come back to Python. A synthetic 73-million-row stream-day took 6 to 9 s (two runs) at a 1.73 GiB peak. That is the audit's `--fast` crypto-fast rate of about 845 msg/s over 24 h, with a 10-minute hole, which was found. The first version pulled every timestamp into Python lists; the audit extrapolated that to about 10 GiB for such a day.

A synthetic 10-minute hole in a fixture is flagged, from both JSONL and Parquet, by `test_gapcheck_flags_synthetic_10_minute_gap`.

## 5. What is not covered here

- **[ops] A10:** 7 consecutive gap-free days on the VM. Start it with `ops/setup.sh`, then run `python -m recorder.gapcheck <day>` each day; the cron line in `ops/roster.cron` does this at 00:15 UTC.
- The Polymarket sports WebSocket and raw odds-API responses (plan task 0.3) are not in the WP0-A dispatch, so they are not recorded yet.
- `custom_feature_enabled` is on for every connection. Each connection therefore also gets the global `new_market` feed, a few 2.5 KB messages a minute each. It is small but duplicated across streams.
- The hourly strike ladders (`bitcoin-above-on-<date>-<H>am-et`, which appeared in 2026) are not a target mode, so the crawler skips them.

## 6. Fix round 1 (after the audit)

- **Test file:** `recorder/test_recorder.py` did not parse, because three `"\n"` literals had been turned into raw line breaks when the files were rewritten with CRLF. The suite now collects and runs: **11 passed**.
- **Line endings:** `ops/setup.sh`, `ops/roster.cron` and every `recorder/*.py` are now LF. Checked in WSL Ubuntu:
  - `bash -n setup.sh` passes;
  - both cron commands pass `dash -n`;
  - `file` reports plain ASCII with no CRLF.

  `test_ops_files` now fails if any ops file contains a `\r` byte.
- **gapcheck memory:** the gaps are now computed in DuckDB (section 4). The report's section 4 output is unchanged on the real smoke day: 2 gaps per stream, the same message counts, and exit code 1.
- **Atomic snapshot:** see section 1.
- **Shed:** the recorder now stops a shed stream within 10 s (section 3). The reconnect test now also writes `shed.json` and asserts that the connection and file are closed and that the stream does not reconnect. With the shed check disabled, the test fails.

  A live check on the current code redirected `recorder.run()` to a scratch folder. It seeded from the latest snapshot, crawled, and recorded all 4 WebSocket streams and both Deribit streams for 90 s. `crypto-fast` was shed at +45 s, its file was closed, and the other streams kept writing to the end. It wrote few `crypto-fast` lines, because the seeded 5m/15m markets had already expired.
- **Accidental write:** that live check's crawl wrote the 17:02 snapshot and `changes.jsonl` to the real `data/markets/`, not to scratch, because the script did not redirect `crawl()`'s default folder. Both are genuine crawler output in a folder this work package owns, so they were kept and are reported in section 1. `data/recordings/` was not touched.
- **Not changed:** on Windows, `shed()` cannot delete a file the running recorder has open (`PermissionError`). The VM is Linux, where the delete succeeds and the recorder closes the file within 10 s.

## How to reproduce

From `C:\Users\DELL\Downloads\saugan_pr\market_updated\roster` (on the VM: `/srv/roster`, with `.venv/bin/python`):

```bash
.venv/Scripts/python.exe -m pytest recorder ops -q                  # 11 passed: hash/diff, reconnect + shed stop, compaction, shed, gapcheck, ops files (LF, no secrets)
.venv/Scripts/python.exe -m recorder.crawler --fast                  # section 1: snapshot in data/markets/, prints rows per mode and null fields
.venv/Scripts/python.exe -m recorder.recorder --fast --seconds 120   # section 2: 120 s smoke run into data/recordings/
# after the UTC hour of the smoke run has closed:
.venv/Scripts/python.exe -m recorder.compact                         # section 3: Parquet, row-count check, bytes per day per stream, shed rule
.venv/Scripts/python.exe -m recorder.gapcheck 2026-09-30             # section 4: gaps per stream for the day
```

The in-run silence figures (sections 2 and 4) come from:

```bash
.venv/Scripts/python.exe -c "import duckdb; [print(r) for r in duckdb.sql(\"SELECT stream, count(*) n, max(t)-min(t) span_ms, max(d) longest_silence_ms FROM (SELECT stream, t, t - lag(t) OVER (PARTITION BY stream ORDER BY t) d FROM read_parquet('data/recordings/parquet/*/*/*.parquet', hive_partitioning=true) WHERE date='2026-09-30') GROUP BY stream ORDER BY stream\").fetchall()]"
```

The filled-test-volume shed demonstration (section 3) runs on a copy, so real data is never touched:

```bash
.venv/Scripts/python.exe -c "import shutil, pathlib; from recorder import compact; d=pathlib.Path('C:/tmp/shedtest'); shutil.rmtree(d, ignore_errors=True); shutil.copytree('data/recordings', d); print(compact.usage(d)/9e6, compact.shed(d, budget_bytes=9_000_000), compact.usage(d)/9e6)"
```

The gapcheck scale check (section 4): build a synthetic 73M-row day with a 10-minute hole at 12:00, then time gapcheck on it in a fresh process. The peak figure uses `peak_wset`, which exists only on Windows.

```bash
.venv/Scripts/python.exe -c "import pathlib, duckdb; p=pathlib.Path('C:/tmp/gapscale/parquet/stream=crypto-fast/date=2026-09-30'); p.mkdir(parents=True, exist_ok=True); d0, N = 1790726400000, 73_000_000; duckdb.sql(f\"COPY (SELECT t, 'x' raw FROM (SELECT {d0} + i * 86399999 // {N} t FROM range({N}) r(i)) WHERE NOT t BETWEEN {d0 + 43_200_000} AND {d0 + 43_800_000}) TO '{p.as_posix()}/00.parquet' (FORMAT parquet, COMPRESSION zstd)\")"
.venv/Scripts/python.exe -c "import pathlib, time, psutil; from recorder import gapcheck; d, d0 = pathlib.Path('C:/tmp/gapscale'), 1790726400000; t = time.time(); r = gapcheck.check('2026-09-30', d, 5, d0 + 86_400_000, d / 'markets')['crypto-fast']; print(r['messages'], [((a - d0) / 6e4, (b - d0) / 6e4) for a, b in r['gaps']], f'{time.time() - t:.1f} s, peak {psutil.Process().memory_info().peak_wset / 2**30:.2f} GiB')"
```

The ops line endings (section 6), checked in WSL:

```bash
wsl -e bash -c 'cd ops && bash -n setup.sh && file setup.sh roster.cron roster-recorder.service'
```
