@echo off
rem Side-by-side PAPER run of btc-speed v6 on a Bybit BTC price (flags speed_v6 + ref_bybit, prereg btc-speed-v6-bybit): v4b's
rem rule + no buy at a seen ask in (0.30, 0.50] + none with more than 600 s left (reports/research/strategy_2026-10-14.md).
rem record_tob: from 14 Oct this run records the BTC book the research loop replays (paper_v3, the old recorder, retired).
rem Run from the roster folder with ROSTER_HUMAN_KEY set (ops\paper_tasks.ps1 startv6b does this for you).

setlocal
if "%ROSTER_HUMAN_KEY%"=="" (
  echo ROSTER_HUMAN_KEY is not set in this window.
  exit /b 2
)
set DIR=data\trader\paper_v6b
if not exist %DIR% mkdir %DIR%

.venv\Scripts\python.exe -m nightly.drills keys > %DIR%\keys.jsonl || exit /b 1
.venv\Scripts\python.exe -m tools.clearance_cli --db %DIR%\advice.db sign --keys %DIR%\keys.jsonl --signer %USERNAME% --days 15 || exit /b 1

.venv\Scripts\python.exe -m trader.loop --paper --minutes 20160 --dir %DIR% --enable speed_v6 --enable ref_bybit --enable speed_only --enable record_tob --global-cap 1000 --enable feed_hub
