# Phase 0 Dispatch — Record and test (no keys)

Source: [build-plan-v4.md](../../../build-plan-v4.md) Phase 0, tasks 0.1–0.12, and [36-agent-roles-polymarket-v4.md](../../../36-agent-roles-polymarket-v4.md). Process: [../README.md](../README.md).

- Code root: `C:\Users\DELL\Downloads\saugan_pr\market_updated\roster`
- Python: `roster\.venv\Scripts\python.exe` (numpy, scipy, pandas, duckdb, pyarrow, websockets, httpx, pytest, penaltyblog, eth-account preinstalled)
- Shared helpers: `roster/common.py` (`get_json`, `sha256_text`, `append_jsonl`, `now_ms`, `DATA`, `REPORTS`). Read-only.

## Work packages and order

| WP | Build-plan tasks | Owns | Starts after |
|---|---|---|---|
| **WP0-A** Data collection | 0.1, 0.2, 0.3, 0.4 | `recorder/`, `ops/`, `data/markets/`, `data/recordings/`, `reports/recorder_smoke.md` | — |
| **WP0-B** History downloads | 0.5 | `history/`, `data/history/`, `reports/history_manifest.md` | — |
| **WP0-F** SDK spike + competitors | 0.8, 0.9 | `research/spike/`, `research/competitors/`, `reports/sdk_decision.md`, `reports/competitors.md` | — |
| **WP0-C** Go/no-go test A (κ) | 0.6 | `research/kappa/`, `reports/kappa_report.md` | WP0-B |
| **WP0-D** Go/no-go test B (devig) | 0.7 | `research/devig/`, `reports/devig_report.md` | WP0-B |
| **WP0-E** Measurements | 0.10, 0.11, 0.12 | `research/measure/`, `reports/reward_income.md`, `reports/postclose_window.md`, `reports/latency_test.md` | WP0-A, WP0-B |

Operational items that cannot be met inside the build (they need real running time) are marked **[ops]**. Auditors mark them `operational_pending`, not `fail`.

---

## WP0-A — Data collection (0.1–0.4)

**Requirements**
- `recorder/crawler.py`: pull active markets from Gamma plus CLOB market info for the target modes: BTC/ETH daily strike ("above") and daily Up/Down (`crypto-term`), hourly Up/Down (`crypto-hourly`), 5m/15m Up/Down (`crypto-fast`), and soccer (`sports-pregame`). For each market, store: condition id, YES/NO token ids, question, verbatim rules text and its sha256, mode tag, fee parameters as exposed, tick size, minimum order size, negRisk flag, augmented flag if exposed, reward parameters (minimum size, maximum spread, daily rate) if exposed, start and end time. Write a dated JSONL snapshot under `data/markets/` and compare with the previous snapshot, logging rules-hash and tick-size changes.
- `recorder/recorder.py`: subscribe to the Polymarket market WebSocket for the selected markets (`crypto-term`, `crypto-hourly` and soccer by default; `crypto-fast` behind a flag for the latency test). Append every raw message with a local receive timestamp in ms to `data/recordings/<stream>/<YYYY-MM-DD>/<HH>.jsonl`. Snapshot Deribit BTC and ETH option summaries every 60s (public REST). Reconnect with backoff, and refresh subscriptions when the crawler finds new markets.
- `recorder/compact.py`: convert closed hourly JSONL to zstd Parquet with DuckDB, partitioned by date and stream; print bytes per day per stream. Shed rule: at ≥ 85% of a configured volume budget, drop the lowest-priority stream first (configurable order).
- `recorder/gapcheck.py`: report gaps (no message for N minutes on a stream with active markets) per day.
- `ops/`: `setup.sh` (create `recorder`, `trader` and `advisor` users, install chrony, create directories, with block-volume mount steps as comments), `roster-recorder.service` (systemd, `Restart=always`, `User=recorder`), and an rsync cron line for the nightly copy to the home PC. Not executed here.

**Acceptance criteria**
- **A1** A crawler run produces at least one row per enabled mode that currently exists live, with every required field (null only where the API does not expose it; list those fields in the report).
- **A2** Rules hash = sha256 of the verbatim text, and a changed hash between two snapshots is detected (test with fixtures).
- **A3** A 120-second recorder smoke run writes ≥ 1 raw market-WebSocket message and ≥ 2 Deribit snapshots, each line with a receive timestamp, in the hourly path scheme.
- **A4** Reconnect logic is tested: a simulated disconnect resumes writing.
- **A5** `compact.py` converts the smoke JSONL to Parquet that DuckDB reads back with the same row count, and prints bytes per day per stream.
- **A6** Shed-rule test: at ≥ 85% of budget, the lowest-priority stream is dropped first.
- **A7** `gapcheck.py` flags a synthetic 10-minute gap in a fixture.
- **A8** Ops files exist; the unit has `Restart=always` and `User=recorder`; no secrets in any file.
- **A9** `reports/recorder_smoke.md` records the smoke run: messages per stream, bytes, gaps, and fields the APIs don't expose.
- **A10 [ops]** 7 consecutive gap-free recording days on the VM.

## WP0-B — History downloads (0.5)

**Requirements**
- `history/binance.py`: BTCUSDT and ETHUSDT 1m klines from data.binance.vision (monthly zips, daily files for the current month), verified against the `.CHECKSUM` files, stored as Parquet. At least 24 months.
- `history/deribit.py`: DVOL history for BTC and ETH (`public/get_volatility_index_data`, 1h and 1D) over the same span, stored as Parquet.
- `history/polymarket.py`: find closed daily BTC/ETH strike ("above $X") and daily Up/Down markets via Gamma; store strike, settlement time, outcome and token ids; fetch CLOB `/prices-history` per token at the finest fidelity available; fetch Data API trades for them (needed by WP0-E). Stored as Parquet, with coverage and API limits documented.
- `history/footballdata.py`: football-data.co.uk CSVs for at least E0, SP1, D1, I1 and F1, ≥ 5 seasons including the current one, keeping Pinnacle opening (PSH/PSD/PSA) and closing (PSCH/PSCD/PSCA) odds and results. Stored as Parquet.
- Every downloader is idempotent, resumable and rate-limited.

**Acceptance criteria**
- **B1** Binance: ≥ 24 months × 2 symbols stored; checksum verification implemented and passing; about 1,440 rows per day, with gap days listed.
- **B2** Deribit DVOL for BTC and ETH over the same span, with coverage reported.
- **B3** Polymarket: ≥ 100 closed daily strike or Up/Down markets with strike, settlement time and outcome; price history and trades stored for them; limits documented.
- **B4** football-data: ≥ 5 leagues × ≥ 5 seasons with Pinnacle closing columns, and a report of whether the current season's PSCH/PSCD/PSCA are filled.
- **B5** A second run of each downloader skips completed files (test, or shown by a second run).
- **B6** `reports/history_manifest.md` lists every dataset with path, date range, row count and gaps.

## WP0-C — Go/no-go test A: κ (0.6)

**Requirements** (reads WP0-B data; if data is missing, report it and mark `INCONCLUSIVE`, don't fabricate)
- `research/kappa/`: a pricer for daily strike digitals P(S_T > K) and daily Up/Down P(S_T ≥ S_open): lognormal, zero drift, σ_P = κ(τ bucket) × σ_Q, with σ_Q from DVOL (a documented proxy, because free historical skew is not available). Checkpoints at T−24h, T−6h and T−1h against the 12:00 ET Binance 1m close.
- Walk-forward fit of κ (3 parameters, one per τ bucket) by log score. PIT uniformity clustered by settlement day. Compare the κ-model with κ = 1 using day-clustered standard errors, and with the Polymarket mid from WP0-B's price history where available.

**Acceptance criteria**
- **C1** Tests: the digital price matches the closed form at known inputs; P(> K) + P(≤ K) = 1; price is decreasing in K.
- **C2** Walk-forward: κ for day d is fitted only on days before d (test proves no look-ahead).
- **C3** ≥ 500 settlement days used, or the report explains why fewer and marks the result partial.
- **C4** The report shows κ per bucket, the log-score gain over κ = 1 with a day-clustered SE, a PIT uniformity statistic, and model vs Polymarket-mid log loss on overlapping markets (with count).
- **C5** An explicit `PASS` / `FAIL` / `INCONCLUSIVE` verdict against the plan's criterion (beats κ = 1 by > 2 SE **and** beats the mid), with limitations stated.
- **C6** Reproducible with one documented command.

## WP0-D — Go/no-go test B: soccer devig (0.7)

**Requirements** (reads WP0-B's football-data Parquet)
- `research/devig/`: run penaltyblog `calculate_implied` with all 7 methods on the Pinnacle closing 1X2 odds (and opening). Choose the method per league on training seasons by log loss against match outcomes. Evaluate on ≥ 2 held-out seasons: log loss and reliability (calibration) slope. Check the current season's closing columns.

**Acceptance criteria**
- **D1** All 7 methods run; any per-method failures are reported.
- **D2** The method is chosen on training seasons only (test).
- **D3** Held-out log loss and reliability slope per league.
- **D4** Current-season PSCH/PSCD/PSCA fill rate reported.
- **D5** An explicit `PASS` / `FAIL` verdict (suggested threshold: slope 0.9–1.1 on held-out seasons).
- **D6** Reproducible with one documented command.

## WP0-E — Measurements (0.10, 0.11, 0.12)

**Requirements**
- `research/measure/reward_income.py`: from live CLOB reward parameters plus current order books for target markets, estimate whether a $50 account (5-share minimum orders) can meet each market's minimum reward size inside its maximum spread, and its approximate share of the daily pool (quadratic scoring, per Polymarket's docs). Output a table sorted by $/day.
- `research/measure/postclose.py`: for closed daily and hourly BTC/ETH markets (WP0-B data), use trades and price history after the resolution print: price and size traded on the winning side at ≤ 0.98 and ≤ 0.99 within 0–120 minutes, and how often that happened across prints. Add the rate of disputed or wrong resolutions from whatever source is available, and document it. Estimate $/day at the plan's sizing (quarter-Kelly with shrink c = 0.3, q = 1 − 0.005, resolution-risk cap 20% of $50).
- `research/measure/latency.py`: find the free 5-minute dataset published by polymm's author (kacho.io) if downloadable; otherwise use Polymarket 5m/15m trades or price history plus Binance aggTrades. Measure the lag between a Binance move and the Polymarket repricing, and the fee-net edge after a 150ms delay plus an assumed round trip. Give a verdict with the event count.

**Acceptance criteria**
- **E1** Reward table with ≥ 10 markets and clear assumptions.
- **E2** Post-close report with ≥ 50 prints analysed, frequency and size statistics, and a $/day estimate with assumptions.
- **E3** Latency report with method, event count, fee-net edge ± SE, and a `PASS` / `FAIL` / `INCONCLUSIVE` verdict (`PASS` needs mean > 0 by 2 SE over ≥ 200 events).
- **E4** A unit test for each analysis's core computation (fee, reward score, edge).
- **E5** Reproducible with one documented command per report.
- **E6 [ops]** The 4-week latency recording on our own data (the build uses the available datasets).

## WP0-F — SDK spike + competitor research (0.8, 0.9)

**Requirements**
- `research/spike/`: in a separate venv (`research/spike/.venv`), install `py-clob-client-v2` and try `nautilus_trader`. Read-only: fetch a market's book, tick size and fee info. Build and sign an order locally with a throwaway key generated in memory at runtime, and **never post it**. Record install time and size, and API ergonomics. Write a decision note.
- `research/competitors/`: find the most active wallets in the target markets (BTC/ETH daily strike, soccer) via the Data API, and their realised P&L over the last 90 days, split by market type where possible. Conclude plainly whether anyone earns as a maker there.

**Acceptance criteria**
- **F1** No order is ever posted: no network call that creates or posts an order exists, or it is guarded and never reached (auditor checks the code).
- **F2** No private key is written to disk; the throwaway key exists only in memory.
- **F3** The decision note compares both SDKs on ≥ 5 criteria and makes a clear pick.
- **F4** The competitor report covers ≥ 10 wallets with P&L numbers, the data source, and a plain conclusion.
- **F5** Reproducible with one documented command per report.

---

## Phase 0 exit gate (from the build plan)

7 consecutive gap-free recording days **and** at least one go/no-go test passed. The build can deliver the code and the free-history test results. The 7 recording days happen on the VM after deployment.
