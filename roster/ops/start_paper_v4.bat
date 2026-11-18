@echo off
rem Side-by-side PAPER run of btc-speed v4 (2 s / 6 bp detector, cap 0.85, 10c slippage, hold), next to paper14.
rem No ladder-maker here (flag speed_only), so paper14 keeps the v2 baseline and the ladder results stay in one place.
rem --global-cap 1000: a winning paper run is not refused at 1.1x the $50 cap (reports/research/missed_money_2026-10-09.md).
rem No record_tob here: paper_v3 already records the book, and the writer may cost latency.
rem Run from the roster folder with ROSTER_HUMAN_KEY set (ops\paper_tasks.ps1 startv4 does this for you).

setlocal
if "%ROSTER_HUMAN_KEY%"=="" (
  echo ROSTER_HUMAN_KEY is not set in this window.
  exit /b 2
)
set DIR=data\trader\paper_v4
if not exist %DIR% mkdir %DIR%

.venv\Scripts\python.exe -m nightly.drills keys > %DIR%\keys.jsonl || exit /b 1
.venv\Scripts\python.exe -m tools.clearance_cli --db %DIR%\advice.db sign --keys %DIR%\keys.jsonl --signer %USERNAME% --days 15 || exit /b 1

.venv\Scripts\python.exe -m trader.loop --paper --minutes 20160 --dir %DIR% --enable speed_v4 --enable speed_only --global-cap 1000
