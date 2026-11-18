@echo off
rem Side-by-side PAPER run of btc-speed v5 on a Bybit BTC price (flag ref_bybit) = v4 + calm filter (skip when BTC 30-min vol >= 5.5 bp/min), flag speed_v5,
rem pre-registered as btc-speed-v5-bybit (trader/engines/speed.py). --global-cap 1000 as paper_v4. No record_tob (paper_v3 records).
rem Run from the roster folder with ROSTER_HUMAN_KEY set (ops\paper_tasks.ps1 startv5b does this for you).

setlocal
if "%ROSTER_HUMAN_KEY%"=="" (
  echo ROSTER_HUMAN_KEY is not set in this window.
  exit /b 2
)
set DIR=data\trader\paper_v5b
if not exist %DIR% mkdir %DIR%

.venv\Scripts\python.exe -m nightly.drills keys > %DIR%\keys.jsonl || exit /b 1
.venv\Scripts\python.exe -m tools.clearance_cli --db %DIR%\advice.db sign --keys %DIR%\keys.jsonl --signer %USERNAME% --days 15 || exit /b 1

.venv\Scripts\python.exe -m trader.loop --paper --minutes 20160 --dir %DIR% --enable speed_v5 --enable ref_bybit --enable speed_only --global-cap 1000 --enable feed_hub
