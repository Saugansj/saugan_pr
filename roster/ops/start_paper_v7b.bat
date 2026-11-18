@echo off
rem Side-by-side PAPER run of btc-speed v7 on a Bybit BTC price (flags speed_v7 + ref_bybit, prereg btc-speed-v7-bybit): v4b's
rem rule, but v6's skips are replaced by a fair-value rule: buy only when the ask <= FV - fee - margin, limit capped at
rem FV - fee - margin (reports/research/v7_test_2026-10-23.md). In ops\keeper.py ACTIVE since 23 Oct (user approved).
rem Run from the roster folder with ROSTER_HUMAN_KEY set (ops\paper_tasks.ps1 startv7b does this for you).

setlocal
if "%ROSTER_HUMAN_KEY%"=="" (
  echo ROSTER_HUMAN_KEY is not set in this window.
  exit /b 2
)
set DIR=data\trader\paper_v7b
if not exist %DIR% mkdir %DIR%

.venv\Scripts\python.exe -m nightly.drills keys > %DIR%\keys.jsonl || exit /b 1
.venv\Scripts\python.exe -m tools.clearance_cli --db %DIR%\advice.db sign --keys %DIR%\keys.jsonl --signer %USERNAME% --days 15 || exit /b 1

.venv\Scripts\python.exe -m trader.loop --paper --minutes 20160 --dir %DIR% --enable speed_v7 --enable ref_bybit --enable speed_only --global-cap 1000 --enable feed_hub
