# Phase 0 Audit — Record and test

Contract: [dispatch.md](dispatch.md). Process: [../README.md](../README.md). Every acceptance criterion below was checked by an independent auditor agent that did not write the code; the orchestrator then re-ran every test suite.

## Summary

| Work package | Code audit | Fix rounds | Tests (orchestrator re-run) | Result |
|---|---|---|---|---|
| **WP0-A** Data collection (0.1–0.4) | PASS (ops pending) | 1 | 11 passed | 462 live markets crawled; recorder, compactor, gap checker and VM ops files working |
| **WP0-B** History downloads (0.5) | PASS | 0 | 10 passed | 4.7 years of Binance 1m and Deribit DVOL; 1,403 of 2,058 Polymarket events; 25,491 soccer matches |
| **WP0-C** Go/no-go test A: κ (0.6) | PASS | 0 | 6 passed | **Test A FAILED**: κ gain 1.8 SE (needs > 2); Polymarket mid beats the model (0.1129 vs 0.1168 log loss) |
| **WP0-D** Go/no-go test B: soccer devig (0.7) | PASS | 0 | 5 passed | **Test B FAILED**: no free Pinnacle closing odds since Jan 2026; SP1 calibration slope 1.19 |
| **WP0-E** Measurements (0.10–0.12) | PASS (ops pending) | 4 (2 void) | 14 passed | Rewards $0/day in target markets; post-close gate NOT MET (0.9% of prints, about $0.28/day at $50); latency PASS at 2.02c ± 0.34c but only within about 2 s, and only BTC (+6.67c) while ETH loses (-1.18c) |
| **WP0-F** SDK spike + competitors (0.8, 0.9) | PASS | 0 | 9 passed | SDK pick `py-clob-client-v2`; a minority of makers earn in target markets |

All 55 tests pass, and the `common.py` self-check passes.

## Phase 0 exit gate: **NOT MET**

The build plan's gate is **7 gap-free recording days and at least one go/no-go test passed**.

| Gate item | Status |
|---|---|
| Go/no-go test A, crypto ladders (κ) | **FAIL** |
| Go/no-go test B, soccer devig | **FAIL** |
| Post-close capture measurement (strategy #2 in v4) | **NOT MET**: 0.9% of prints against a 33% gate |
| Latency test, fast Up/Down (gates only Phase 3) | **PASS on the free dataset**, but fragile (see below); the 4-week test on our own data (E6) decides it |
| 7 gap-free recording days | **[ops] pending**: needs the recorder running on the VM |

The build plan's rule applies: *"If both fail: stop. Don't start Phase 1. Keep recording and revisit the strategy list."* The code works and is audited. What failed is the evidence that the first strategies have an edge, which is exactly what Phase 0 exists to find out before any money is at risk.

## What Phase 0 found

| Question | Answer | Evidence |
|---|---|---|
| Does the κ-corrected options model beat the market on BTC/ETH daily ladders? | **No** | κ improves the log score by 0.0072 nats per observation, only 1.8 SE (the bar is 2 SE) over 1,671 days. The Polymarket mid beats the model: log loss 0.1129 vs 0.1168 over 24,754 checkpoints (about 3.5 SE). The model used DVOL as a stand-in because free skew history doesn't exist |
| Can free Pinnacle closing odds anchor soccer? | **No longer** | football-data.co.uk stopped publishing Pinnacle odds in January 2026 (0% of 250 current-season matches). Historical calibration is close except Spain (SP1 slope 1.19) |
| Is post-close capture available? | **Rarely** | A winning-side ask ≤ 0.98 with ≥ 5 shares appeared after 0.9% of 2,075 prints; most post-print volume trades at 0.99–0.999. Expected income at $50: **$0.28/day** (daily $0.03 + hourly $0.25), an upper bound after removing mis-sided fills; the earlier $1.67 came almost entirely from one mis-sided $0.01 fill |
| Are resolutions reliable? | **Yes** | 0 of 8,919 markets disagree with the winner recomputed from Binance; 1 of 8,977 was disputed. The plan's P(wrong) of 0.5% is conservative (95% upper bound 0.034%) |
| Do the target markets pay liquidity rewards? | **No** | 0 of 398 target markets have a reward pool, and 5-share quotes earn rewards nowhere. Pools exist in other categories, with 20–50 share minimums |
| Do makers earn in the target markets? | **A minority do** | BTC/ETH strike and daily Up/Down: 2 of 6 maker-dominant wallets are positive (median −$4,168). Soccer: 3 of 11 (median −$14,653); counting all-market rebates, 9 of 11 are positive |
| Is there a latency edge on 5/15-minute markets? | **Yes on free data, but fragile** | +2.02¢ ± 0.34¢ per share over 2,165 events when entering 2 s after the Binance second; gone at 3 s, negative at 4 s. BTC +6.67¢, ETH −1.18¢. About $3.6/day at 5 shares, or about $5.4 BTC-only, before competition |
| Which SDK? | **`py-clob-client-v2`** | NautilusTrader's Polymarket adapter wraps it and adds about 550 MB |

## Orchestration notes

- **Interruptions:** the run hit the plan's usage limit once (resumed after 22:00 IST), and two Claude Code sessions ended mid-run. Completed agent work was cached and not repeated.
- **WP0-E fix rounds 1 and 2 did nothing:** the fixer agents read the user's "status" message as their instruction and changed no code. The orchestrator applied the auditor-verified one-line fix (`postclose.py:353`). A new independent audit then found the post-close $/day was not reproducible (unstable sort on tied timestamps) and that about 96% of it came from one mis-sided $0.01 fill. The orchestrator added a stable full-key sort, a filter for winning-side fills more than 0.20 below the winner's mid, and an order-independence test, re-ran the report, and sent it for a final independent audit (below). It also added a per-coin bullet to the latency verdict.
- **Data-location exception:** about 336 MB of WP0-E cache sits in `research/measure/data/` instead of `roster/data/`. Accepted for Phase 0; move it when Phase 1 starts.
- **Orchestrator re-run:** every work package's tests, run independently: 55 passed.

## Recommended next steps (your decision)

1. **Don't start Phase 1 with strategies 1–3 as specified.** That is the build plan's own rule.
2. **Deploy the recorder to the VM anyway.** It costs nothing and risks no money. It is needed for the 7-day gate and the 4-week latency test (E6), and its Deribit snapshots give a future κ test the real option skew that free history lacks.
3. **Revisit the strategy list with the evidence:**
   - **Latency, BTC only:** the only test that passed. Run E6 from the VM with our real round-trip time before trusting it.
   - **κ test v2:** after about 60 days of recorded Deribit snapshots (real skew), and judged on maker P&L after adverse selection rather than on beating the mid's forecast.
   - **Soccer:** needs a different sharp source (Betfair delayed prices, Kalshi), then a re-test.
   - **Reward-paying markets outside crypto and sports**, where pools exist at 20–50 share minimums. This is a scope change.


---

## WP0-A: Data collection (0.1–0.4)

**Final verdict:** PASS (ops pending) (from `reaudit1:WP0-A`). Agent sequence: build → audit → audit → fix1 → reaudit1.

| AC | Status | Evidence | Command |
|---|---|---|---|
| A1 Crawler row per enabled live mode with every required field (null only where API does … | pass | All 6 snapshots have all 22 required keys and 0 bad hashes, 0 clob failures, 0 duplicates and 0 empty rules. The latest snapshot (2026-09-30T170224Z) has 467 rows: crypto-term 158, crypto-hourly 97, sports-pregame 144, crypto-fast 68. The only null field is event_start_time, on 154 crypto-term rows, all of them '-abov… | `python script over data/markets/*Z.jsonl (required keys, sha256 recompute, clob_ok, nulls per mode); build/phase-0/audit-tmp/WP0-A/r1/spot.…` |
| A2 Rules hash = sha256 of verbatim text; changed hash between snapshots detected (fixture… | pass | test_build_row_hashes_verbatim_rules_and_reads_clob_fields PASSED: it hashes multi-line text containing quotes verbatim. test_snapshot_diff_detects_rules_hash_and_tick_changes PASSED: it asserts that exactly {(b, rules_sha256), (c, tick_size)} are detected and logged with 'previous', that 30-day retention works, and t… | `.venv/Scripts/python.exe -m pytest recorder ops -v -p no:cacheprovider` |
| A3 120 s smoke writes >=1 WS message and >=2 Deribit snapshots with receive timestamps in… | pass | My live 120 s run on the current code wrote rec/<stream>/2026-09-30/17.jsonl. Line counts: crypto-term 13,504 (price_change 12,462, book 6, ...), crypto-hourly 10,879, sports-pregame 1,358, deribit-btc 2 (948 summaries each), deribit-eth 2 (800 each). Every line has exactly the keys {t, raw}, t increases monotonically… | `build/phase-0/audit-tmp/WP0-A/r1/smoke.py (common.DATA redirected to scratch before import; recorder.run(DEFAULT_MODES, 60, 120)) plus JSON…` |
| A4 Reconnect logic tested: simulated disconnect resumes writing | pass | The test PASSED. A local server drops connection 1 after 2 messages, and the recorder reconnects and writes all 4 messages in order with the same subscribe ids. Two mutations each make the test fail: load_shed stubbed to [], and only the new inner-loop shed check disabled (via a frame-line filter). A live check (r1/li… | `pytest (test_reconnect_after_disconnect_resumes_writing_and_shed_stops_it); mutation tests in build/phase-0/audit-tmp/WP0-A/r1/test_audit.py` |
| A5 compact.py converts smoke JSONL to Parquet with same DuckDB row count; prints bytes/da… | pass | All 5 files verified. JSONL lines vs Parquet rows: 10879=10879, 13504=13504, 2=2, 2=2, 1358=1358, all with codec ZSTD. main() printed the stream/date/parquet_bytes/open_jsonl_bytes table plus usage and the shed line. The unit test (row counts, a torn line saved to .bad.jsonl, a blank line causing a mismatch that keeps… | `build/phase-0/audit-tmp/WP0-A/r1/compact_chk.py (compact.compact on my scratch recording with now=18:30, DuckDB read-back, parquet_metadata…` |
| A6 Shed-rule test: at >=85% lowest-priority stream dropped first | pass | The test PASSED: 83% drops nothing; 100% drops crypto-fast only, after which usage is 70%; then crypto-hourly and crypto-term, skipping empty streams; shed.json is written. The logic breaks only when usage < 0.85 * budget, so exactly 85% sheds. The report's filled-volume demo figures check out: 8,065,343/9e6 = 89.6%, … | `pytest (test_shed_drops_lowest_priority_first_at_85_percent); code read of compact.shed` |
| A7 gapcheck flags a synthetic 10-minute gap in a fixture | pass | Both tests PASSED: the gap is (19:50, 30:00), found from both JSONL and Parquet, and not flagged at an 11-minute threshold. The real-day CLI shows 6 of 6 streams with 2 gaps each (00:00 to run start, run end to now), the same message counts as the report, and exit=1. Scale: 72,493,055 messages, one gap from 720.0 to 7… | `pytest (test_gapcheck_flags_synthetic_10_minute_gap, test_gapcheck_flags_expected_streams_with_no_data); PYTHONIOENCODING=utf-8 python -m r…` |
| A8 Ops files exist; unit Restart=always and User=recorder; no secrets | pass | roster-recorder.service has Restart=always, User=recorder and Group=recorder. setup.sh creates recorder, trader and advisor, installs chrony, creates directories, and carries the block-volume steps as comments. roster.cron has the compact and gapcheck lines and a commented home-PC rsync pull line. All 3 ops files and … | `cat -A ops/*; byte CR count; MSYS_NO_PATHCONV=1 wsl -e bash r1/cronchk.sh (bash -n setup.sh, dash -n on each cron command); file; grep for …` |
| A9 reports/recorder_smoke.md records messages per stream, bytes, gaps, unexposed fields | pass | Section 1 matches the data: 158/18 events, tick 0.001 on 110 and 0.01 on 48, 96/96, 144/48 (0.01 on 142, 0.001 on 2), 64/64, fee rates 0.07/0.05, rebates 0.2/0.15, seconds_delay 0/1, base fees 1000, reward rate 0.0 on all rows, min 50 and max spread 4.5; the 99 s crawl matches the file mtime. Section 2: lines, spans, … | `cat -n reports/recorder_smoke.md; build/phase-0/audit-tmp/WP0-A/r1/reportchk.py (recompute section 1 from the 143449Z snapshot and section …` |
| A10 [ops] 7 consecutive gap-free recording days on the VM | operational_pending | The deployment blockers from round 0 (CRLF in setup.sh and roster.cron) are fixed and checked in WSL. The 7 days need real running time on the VM. | `n/a (needs VM deployment)` |

**Open defects at final audit** (none are blockers or majors unless marked):

- **minor**: A malformed shed.json crashes the whole recorder, and it stays down on every restart. Fix round 1 added load_shed() calls that sit outside any handler that catches ValueError. load_shed only catches FileNotFoundError. Four calls are affected: ws_stream's top-of-loop check (recorder.py:71), its inner-loop check (recorder.py:81, inside a try that only catches OSError, TimeoutError and WebSocketExce…
- **minor**: An empty crawl result drops every WebSocket subscription until the next successful crawl, and gapcheck then treats the market streams as not expected. If Gamma answers HTTP 200 with no events (a partial outage or an API change), crawl() saves a 0-row snapshot. crawl_loop (recorder.py:121-123) then replaces every mode's token set with frozenset(), so every ws_stream disconnects and idles for up to…

**Rules check:** I did not modify, create or delete any code-base file. My scratch files are only under build/phase-0/audit-tmp/WP0-A/r1/. I ran pytest with -p no:cacheprovider; the root .pytest_cache was written at 22:47 by another agent. I removed the 74 MB synthetic Parquet afterwards. Owned paths: every file modified since the fix round began (22:24:30 IST) that belongs to WP0-A is inside its owned paths: - recorder/compact.py, crawler.py, gapcheck.py, recorder.py, test_recorder.py - ops/setup.sh, ops/roster.cron - data/markets/2026-09-30T170224Z.jsonl and data/markets/changes.jsonl. These are the acciden…

---

## WP0-B: History downloads (0.5)

**Final verdict:** PASS (from `audit:WP0-B`). Agent sequence: build → audit.

| AC | Status | Evidence | Command |
|---|---|---|---|
| B1 Binance >=24 months x 2 symbols, checksum verified, ~1440 rows/day, gap days listed | pass | BTCUSDT and ETHUSDT each have 85 files (56 monthly + 29 daily), 2022-01-01 00:00 to 2026-09-29 23:59 UTC (57 months). Each has 2,495,440 rows, all distinct minutes, all aligned to the minute: 1,733 days x 1,440 - 80 = 2,495,440. checksums.jsonl has 170 entries, 0 unverified, and 85/85 files per symbol have a verified … | `audit-tmp/WP0-B/b1.py (duckdb over data/history/binance/*/*.parquet and checksums.jsonl); b1b.py (downloads 2024-02 monthly and 2026-09-15 …` |
| B2 Deribit DVOL BTC+ETH over same span, coverage reported | pass | All 4 files are unique and monotonic, with 0 gaps and 0 nulls. 1h: 41,609 rows each, 2022-01-01 00:00 to 2026-09-30 16:00 (= 1,733 x 24 + 17). 1D: 1,734 rows each, 2022-01-01 to 2026-09-30. Live comparison: BTC 1h for 2024-06-01 matched 24/24 candles with max diff 0.0; ETH 1D matched 10/10 with diff 0.0. The manifest … | `audit-tmp/WP0-B/b2.py (pandas over dvol_*.parquet; live get_volatility_index_data comparison)` |
| B3 Polymarket >=100 closed daily strike/UpDown markets with strike, settlement time, outc… | pass | Catalog: 9,809 unique markets in 2,058 events. Every strike market has a strike and every market has an outcome. I checked every outcome independently against the Binance 12:00 ET 1m close: strike 8,669/8,669 agree and Up/Down 1,116/1,116 agree (the 22 and 2 unchecked markets settle today). Files: 1,403 price and trad… | `audit-tmp/WP0-B/b3a.py, b3b.py, b3c.py (outcomes vs Binance), b3d.py, b3e.py, b3f.py (duckdb over prices/trades), b3g.py (Gamma series scan…` |
| B4 football-data >=5 leagues x >=5 seasons with Pinnacle closing, current-season PSCH fil… | pass | 25,491 matches across E0, SP1, D1, I1 and F1, seasons 2012/13 to 2026/27. 13 seasons per league have PSCH/D/A on at least 99% of matches. Parquet row counts equal the raw CSV counts for all 75 files, with 0 duplicate matches and a sample odds row identical to the raw CSV. 2026/27 CSVs have no PS* columns, only PPH/PPD… | `audit-tmp/WP0-B/b4.py (matches.parquet vs the 75 raw CSVs); fetched football-data.co.uk/notes.txt` |
| B5 Second run skips completed files | pass | binance {'downloaded': 0, 'skipped': 170} with zero network calls. Deribit: all 4 series requested start_timestamp == stored tail, result (0, total). football-data: 75 skipped, and only the 'current' code is re-requested. Polymarket: 1,403/1,403 events 'skipped' with zero calls. Files changed/added: 0, removed: 0. | `pytest history -q (4 skip tests); audit-tmp/WP0-B/b5.py runs each downloader on the real data dirs with network calls stubbed to raise and …` |
| B6 reports/history_manifest.md lists every dataset with path, date range, row count, gaps… | pass | The summary table has path, range, rows and gaps for Binance x2, DVOL x4, the Polymarket catalog, prices and trades, and football-data. The per-dataset sections all match my independent counts (2,495,440; 41,609/1,734; 9,809; 156,828,147; 8,040,741; 8,305; 25,491; uma_not_resolved 31; 46 endDate mismatches). All numbe… | `grep -n '^## ' reports/history_manifest.md; tail; compared every number with the independent queries above; read manifest.py` |

**Open defects at final audit** (none are blockers or majors unless marked):

- **minor**: The Polymarket download is partial: 655 of 2,058 events (8 from 2022, 58 from 2023, 589 from 2025 including all 403 pre-October-2025 Up/Down events) have no price or trade files. B3's threshold is met (8,305 complete markets) and the manifest reports the shortfall honestly, but the history starts at 2025-10-05 instead of spanning the catalog.
- **minor**: 103 of 16,610 tokens end their /prices-history series at a mid of about 0.5 after resolution, when the book is emptied (100 of them at exactly 0.5, e.g. 'Bitcoin Up or Down on September 12?' final p=0.45 for the winning No token). This is a source artifact, but the manifest does not warn about it, and WP0-E's post-close analysis uses post-resolution prices.
- **minor**: The manifest text hard-codes '(46 markets)' for Gamma endDate mismatches rather than computing it. It is correct today (46 = 45 one day off + 1 month off), but it will go stale when the catalog is refreshed.

**Rules check:** Owned paths: WP0-B files exist only in history/ (__init__, binance, deribit, footballdata, polymarket, manifest, test_history + __pycache__), data/history/ (binance 171 files incl. checksums.jsonl, deribit 4, footballdata 76, polymarket 2,808 incl. truncated.jsonl) and reports/history_manifest.md. No WP0-B file or reference exists outside those paths apart from dispatch.md and my own audit-tmp scratch. Secrets: a grep of history/*.py for private key, secret, api key, passphrase, mnemonic, 0x+64-hex, Authorization and Bearer found 0 matches. The data holds only public market data; the jsonl fi…

---

## WP0-C: Go/no-go test A: κ (0.6)

**Final verdict:** PASS (from `audit:WP0-C`). Agent sequence: build → audit.

| AC | Status | Evidence | Command |
|---|---|---|---|
| C1 digital matches closed form at known inputs; P(>K)+P(<=K)=1; decreasing in K | pass | 6 passed. test_digital_closed_form checks N(-0.25)=0.4012937 for S=K=100, sigma=0.5, tau=1, which I verified by hand: d2=(0-0.125)/0.5=-0.25. It also checks a second case (0.98794). test_digital_complement_and_monotone asserts digital+cdf=1 on a 301-point strike grid, strictly decreasing prices, and the right tail lim… | `PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe -m pytest research/kappa -q -p no:cacheprovider (from roster/); read research/kappa/test…` |
| C2 walk-forward: kappa for day d fitted only on days before d (test proves no look-ahead) | pass | walk_forward uses np.searchsorted(day, days[burn_in:]) with side='left', so it fits on rows strictly before d. The test perturbs data from day 20 on and asserts kappa for days <= 20 is unchanged and later days change. It also asserts kappa(day 10) equals a fit on exactly the rows before day 10. My independent fit repr… | `Read kappa.py:68-74 and test_walk_forward_has_no_look_ahead; re-implemented the walk-forward independently in audit-tmp/WP0-C/indep.py (own…` |
| C3 >= 500 settlement days used | pass | Binance 1m covers 2022-01-01 to 2026-09-29 (2,495,440 rows per symbol). DVOL 1h is continuous (41,609 rows). Rows built: 10,386, all complete. Scored rows: 10,026 over 1,671 days (2022-03-04 to 2026-09-29) after the 60-day burn-in. My independent build gives the same counts. The binary ladder covers 636 days. The mid … | `indep.py (independent row build) plus duckdb counts on data/history/binance and deribit` |
| C4 report shows kappa per bucket, log-score gain over kappa=1 with day-clustered SE, PIT … | pass | All four tables are present, and every number matches my independent recomputation. Gain: all 0.00716, SE 0.00404 (1.77); T-1h 0.01605/0.00903; T-6h -0.00149/0.00502; T-24h 0.00693/0.00516. PIT KS D and p for all six cells are identical (for example BTC T-1h D=0.075, p=1.41e-08, coverage 90.1%). Ladder: 0.1327 vs 0.13… | `Read reports/kappa_report.md; independent recomputation (indep.py, indep_mid.py) compared to the report tables` |
| C5 explicit PASS/FAIL/INCONCLUSIVE verdict against plan criterion, with limitations | pass | The verdict is FAIL. The report states the plan criterion correctly: beats kappa=1 by > 2 day-clustered SE AND beats the mid. Both legs fail on verified numbers: t=1.77 < 2, and the mid wins by +0.0039 (3.7 SE). The kappa=1 leg fails on the full 1,671 days, so the partial mid history cannot change the verdict. The Lim… | `Read the report's Verdict and Limitations sections; grep build-plan-v4.md line 74; read the summarise() verdict logic in kappa.py:223-229` |
| C6 reproducible with one documented command | pass | The re-run took 2m20s, exit 0, verdict FAIL. summary.json is byte-identical. density.parquet (10026x17) and binary.parquet (29355x25) are DataFrame-equal. The report differs only in the 'Generated ... UTC' timestamp line. The command `.venv\Scripts\python.exe -m research.kappa.kappa` is documented in the module docstr… | `build/phase-0/audit-tmp/WP0-C/rerun.py (imports research.kappa.kappa, redirects OUT and REPORT to the audit folder, calls run() and report(…` |

**Open defects at final audit** (none are blockers or majors unless marked):

- **minor**: DST edge case. The Up/Down reference price S_open is the close at settle_ms - 24h, not the previous calendar day's 12:00 ET candle the rules name. On the day after a DST switch these differ by 1h. In the outputs this affects 12 Up/Down market-checkpoints (4 markets, 2025-11-02 and 2026-03-08), with 0 label mismatches. Also, on 5 spring-forward days the T-24h checkpoint (16:01 UTC) comes before th…
- **minor**: Cross-package coupling: kappa.py imports noon_et_ms from WP0-B's history/polymarket.py. It is read-only use, but a change in WP0-B code could silently change WP0-C results. zoneinfo would do the same in one line.

**Rules check:** Owned paths (dispatch: research/kappa/, reports/kappa_report.md). WP0-C files found: research/kappa/kappa.py, research/kappa/test_kappa.py, research/kappa/out/{density.parquet, binary.parquet, summary.json}, reports/kappa_report.md, all inside owned paths. Other recently modified files (common.py, README.md, requirements.txt, other reports) belong to the orchestrator or other WPs and contain no kappa references. No evidence WP0-C touched them. Secrets: grep for private key, secret, api key, passphrase, mnemonic and 64-hex strings in research/kappa and the report found nothing. Orders and netw…

---

## WP0-D: Go/no-go test B: soccer devig (0.7)

**Final verdict:** PASS (from `audit:WP0-D`). Agent sequence: build → audit.

| AC | Status | Evidence | Command |
|---|---|---|---|
| D1 All 7 methods run; any per-method failures are reported | pass | All 7 methods are enumerated from the library. My independent count found 24,383 rows with valid PSC odds, the same number as the report's D1 table (24,383 closing, 0 failures for every method). The report shows 24,364 opening rows and 12,709/12,708 avg_closing rows, and it lists the 1 Shin failure with the odds and t… | `Read research/devig/devig.py (METHODS = [m.value for m in ImpliedMethod]; devig() catches exceptions and invalid vectors and counts them pe…` |
| D2 The method is chosen on training seasons only (test) | pass | test_method_choice_uses_training_seasons_only passes. It makes held-out data favour a different method, then corrupts the held-out rows, and the choice stays the same. My own training-only argmin gives D1 multiplicative, E0 odds_ratio, F1 power, I1 power, SP1 odds_ratio, and every training log loss matches the report'… | `.venv/Scripts/python.exe -m pytest research/devig -q -p no:cacheprovider; read choose_method/evaluate (line 65 filters ll.season.isin(TRAIN…` |
| D3 Held-out log loss and reliability slope per league | pass | Held-out seasons are 2023/24 and 2024/25 (full, 1,752 matches each) plus 2025/26 (partial, 898), which meets the >=2 requirement. Every row matches the report to 4 decimals, for example: D1 held-out LL 0.9572, slope 1.0528; SP1 held-out 0.9477, 1.1866; all held-out 4,402 matches, LL 0.9576, slope 1.0813, intercept 0.0… | `indep.py: my own multiplicative devig (1/o normalised) plus penaltyblog for power/odds_ratio, logistic slope fitted by scipy Nelder-Mead ML…` |
| D4 Current-season PSCH/PSCD/PSCA fill rate reported | pass | 2026/27 has 250 played matches (D1 36, E0 50, F1 45, I1 50, SP1 69; last played 2026-09-20). PSC fill is 0.0, PS fill 0.0, BFEC fill 1.0. 2025/26 PSC fill is 0.5126 (report: 0.51). None of the five 2627 CSV headers has a PS* column; they have PP*, BFE*, AvgC* and BFEC*. The last E0 row with PSCH in 2526 is 2026-01-08,… | `duckdb on data/history/footballdata/matches.parquet: fill rate by season and played count by league for 2026/27; header check of data/histo…` |
| D5 Explicit PASS/FAIL verdict (slope 0.9-1.1 on held-out seasons) | pass | The report states 'Verdict: **FAIL**' and gives both reasons. The rule follows the plan: calibrated on >=2 held-out seasons AND current-season closing columns filled. The builder also added a stricter per-league condition, but the FAIL does not depend on it: only 1 of 3 pooled seasons is inside 0.9-1.1 (1.105, 1.041, … | `Read report 'Verdict' section and functions calibrated()/verdict() in devig.py; test_verdict_rule in the pytest run; compared with build-pl…` |
| D6 Reproducible with one documented command | pass | The run took 1m59s and exited 0. The diff shows only line 3, the generation timestamp (17:17 vs 17:25 UTC); every number is identical. A first attempt ran at the same time as my independent script and died with a numpy _ArrayMemoryError: 8 GB machine, other agents running in parallel. The re-run on its own succeeded. … | `build/phase-0/audit-tmp/WP0-D/repro.py imports devig, redirects devig.REPORTS to audit-tmp and calls devig.main() (same code path as the do…` |

**Rules check:** Owned paths: WP0-D owns research/devig/ and reports/devig_report.md. Its only files are research/devig/devig.py, research/devig/test_devig.py, research/devig/__pycache__/ (byte cache) and reports/devig_report.md. A grep for 'devig' outside .venv/build/data finds only these three files. There is no stray probe.py in the repo; the only hit is inside research/spike/.venv/pip. The input matches.parquet (mtime 22:10) predates devig.py (22:34-22:43) and the report (22:47), and WP0-D writes nothing under data/. A roster/.pytest_cache has devig node ids in it; this is pytest's default cache from runn…

---

## WP0-E: Measurements (0.10–0.12)

**Final verdict:** PASS (ops pending) (from `final re-audit:WP0-E (after orchestrator fixes)`). Agent sequence: build → audit → fix1 (void) → reaudit1 → fix2 (void) → reaudit2 → orchestrator fix → final audit → orchestrator fix → final re-audit.

| AC | Status | Evidence | Command |
|---|---|---|---|
| E1 Reward table with >= 10 markets and clear assumptions | pass | reports/reward_income.md has not changed since Sep 30 23:18. It has 40 market rows sorted by $/day, plus Assumptions, 'Fields the APIs do not expose' and 'How to reproduce' sections. Result: 0 of 398 target markets have a pool, so $0.00/day, and 5-share quotes earn nothing anywhere. | `grep -c '^\| False\\|^\| True' reports/reward_income.md; grep -n '^## ' reports/reward_income.md` |
| E2 Post-close report: >= 50 prints, frequency and size statistics, $/day with assumptions | pass | 2075 prints (688 daily-strike, 715 daily-updown, 672 hourly-updown). Gate: ask<=0.98 (>=5sh) on 0.9% of prints, NOT MET; independent recompute 18/2075 = 0.87%. Filtered opportunities match the recompute: 102 at <=0.98 and 1005 at <=0.99. At $50: daily 82 captures, 412 shares, $9.74, $0.027/day; hourly 52 captures, 261… | `PYTHONPATH=. .venv/Scripts/python.exe build/phase-0/audit-tmp/WP0-E-final/check_fix.py (plus check_postclose.py, an independent duckdb reco…` |
| E3 Latency report: method, event count, fee-net edge +/- SE, verdict | pass | Recomputed exactly: 2165 events, 2.019c +/- 0.344c (t = 5.88), PASS. BTC 882 events +6.67c; ETH 1283 events -1.18c. The regenerated Verdict now states the per-coin split and that the rule fails from tick s + 3. | `pandas recompute on research/measure/data/latency_events.parquet, ask_size >= 5, cluster-robust SE by market` |
| E4 Unit test for each core computation (fee, reward score, edge) | pass | 14 passed in 1.46s: fee, reward score, edge, sizer and caps, test_simulate_is_order_independent_with_tied_timestamps, test_postclose_summary_table_renders. | `.venv\Scripts\python.exe -m pytest research/measure -q -p no:cacheprovider` |
| E5 Reproducible with one documented command per report | pass | All three reports end with 'How to reproduce'. postclose.main ran end to end (exit 0, about 24 min cached); output byte-identical to the report apart from the 'Generated' line. $/day deterministic: one value across 30 shuffles of trades and mids and 3 fresh duckdb reads. The suspect 0.01 fill at cid 0xee07df..., ts 17… | `PYTHONPATH=. .venv/Scripts/python.exe build/phase-0/audit-tmp/WP0-E-final/run_main_redirected.py, then diff against reports/postclose_windo…` |
| E6 [ops] 4-week latency recording on our own data | operational_pending | Needs recorder --fast plus Binance on the VM for 4 weeks. | `n/a (operations)` |

**Open defects at final audit** (none are blockers or majors unless marked):

- **minor**: The outlier filter applies only in opportunities(); print_stats() still counts mis-sided fills, so the gate frequency and the sizer use different fill sets. With the filter applied, ask<=0.98 (>=5sh) falls from 0.87% to 0.72% of prints. Conservative: NOT MET only becomes clearer.
- **minor**: The $/day is concentrated and the report does not say so: the top capture is 33% of expected P&L at $50, the top 3 are 65%, the top 10 are 77%.
- **minor**: test_postclose_summary_table_renders copies the to_markdown expression rather than calling write_report.
- **minor**: 'How to reproduce' implies later runs are fast; a cached rerun still takes about 24 min. postclose_run2.log (10:52) shows exit=1 with no traceback (likely the collision with the parallel latency run); runs 3 and the auditor's both exit 0.

**Rules check:** No secrets or private keys in research/measure/*.py. No order posting: only GET calls to public Gamma, CLOB /prices-history and Data API endpoints, plus downloads from Hugging Face and Binance. All three reports end with '## How to reproduce'. The ~336 MB cache in research/measure/data/ is an accepted, documented Phase 0 exception. No code-base file was modified by the auditor; scratch only in build/phase-0/audit-tmp/WP0-E-final/.

---

## WP0-F: SDK spike + competitors (0.8, 0.9)

**Final verdict:** PASS (from `audit:WP0-F`). Agent sequence: build → audit.

| AC | Status | Evidence | Command |
|---|---|---|---|
| F1 No order is ever posted (no network call that creates/posts an order exists, or it is … | pass | spike.py makes no posting call. The only 'post' hits are the REFUSED tuple and guard(). Every POST/DELETE in py-clob-client-v2 ClobClient goes through self._post or self._delete (client.py lines 282-1155), and guard() replaces both on the class. _post allows only endpoints ending in /books. Nautilus uses the same impo… | `grep -niE 'post\|urlopen\|requests\.\|httpx\|method=\|data=' research/spike/spike.py research/competitors/competitors.py; grep of research/…` |
| F2 No private key written to disk; throwaway key only in memory | pass | Only 3 distinct 64-hex values are on disk: the zero builder, the public Nautilus builder code 0x4f2c...9e63, and the market condition id. None is a key. Secret-like strings appear only as `private_key=key` and literal 'unused' dummies in spike.py source. The key comes from Account.create() inside the --probe process, … | `grep -rhoE '0x[0-9a-fA-F]{64}' over research/spike/*.json, research/competitors/out/*, both reports; grep for private_key/secret/passphrase…` |
| F3 Decision note compares both SDKs on >= 5 criteria and makes a clear pick | pass | The note has a 9-row comparison table and the pick 'py-clob-client-v2 (pin 1.2.0) ... Don't adopt NautilusTrader now'. I checked these claims and all are correct: install 74.5 s/+48.5 MB vs 252.6 s/+551.9 MB (install.json); nautilus package 326 MB (du); licences MIT vs LGPL-3.0-or-later; the Nautilus pin py-clob-clien… | `cat reports/sdk_decision.md; cross-checked its claims against research/spike/results.json, install.json, spike .venv METADATA, du -sm, PyPI…` |
| F4 Competitor report covers >= 10 wallets with P&L numbers, data source, plain conclusion | pass | 26 wallets, each with realised P&L by segment, the window, profile P&L 90d, rebates and rewards. The rebuilt rows equal wallets.json exactly, and the re-rendered report differs from the published one only in the 'Generated' timestamp. Stats check out: 246 markets (84 strike = 21x2x2, 42 Up/Down, 120 soccer = 8x5x3), 4… | `audit-tmp/WP0-F/recompute.py (rebuilds the rows from out/activity.json and out/wallet_cache.json the same way main() does, renders the repo…` |
| F5 Reproducible with one documented command per report | pass | sdk_decision.md: `.venv/Scripts/python.exe research/spike/spike.py` (my live probe reproduced every qualitative result on today's market, bitcoin-above-90k-on-october-1-2026). competitors.md: `.venv/Scripts/python.exe research/competitors/competitors.py --fresh` (the cache re-render is identical apart from the timesta… | `Read the 'How to reproduce' sections; re-rendered competitors.md from the caches into scratch; re-ran spike.py --probe live into scratch` |

**Open defects at final audit** (none are blockers or majors unless marked):

- **minor**: The 'with rebates' count in the Answer (soccer 9 of 11, crypto 3 of 6) adds 90-day, all-market rebates to realised P&L that covers only 6-11 days for 4 soccer makers (RN1, VeryLucky888, 38791873984189, SnakeBall). For example, RN1 is -$147k over 10.9 days plus $585k of 90-day rebates and rewards. The Answer calls it an upper bound, but it does not mention this window mismatch.
- **minor**: The soccer verdict uses 6-11-day windows for 4 of the 11 maker-dominant wallets, but the Answer does not say how many. 38791873984189 has $266k of sampled soccer maker notional yet $0 soccer realised P&L in its 6.1-day window, so it counts as not positive. The verdict needs 6 of 11 positive to flip, so the conclusion is fragile. The profile cross-check (4 of 11) agrees on 'minority'.
- **minor**: BreakTheBank's soccer split (-$1.87M) is the 'worst' figure and about 88% of the soccer total (-$2.11M). My live check shows it is the difference of about +$3.9M redeemed soccer winners (closed list) and about -$5.8M of imputed unredeemed losers, and its sign disagrees with the profile P&L (+$275k). The Limitations section warns about this in general, but the median, total and worst lines give it…
- **minor**: The 2.4 MB trade cache research/competitors/out/activity.json sits in the research folder instead of roster/data/ (the README rule), because data/ is not among WP0-F's owned paths. The builder disclosed this, and the two rules conflict.

**Rules check:** Owned paths: WP0-F files are research/spike/{spike.py, install.json, results.json, .venv/, __pycache__/}, research/competitors/{competitors.py, test_wp0f.py, out/activity.json, out/wallet_cache.json, out/wallets.json, out/run.log, __pycache__/}, reports/sdk_decision.md and reports/competitors.md, all inside the dispatch's owned paths. A find for spike/competitor/wallet/sdk_decision names found nothing outside them (apart from my own audit-tmp scratch). No secrets: the only 64-hex strings on disk are public (zero builder, Nautilus builder code, condition id), the key/secret words appear only a…
