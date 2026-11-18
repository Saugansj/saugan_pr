@echo off
rem Side-by-side PAPER run (30 Oct, user approved): v4b's rule (v4 on a Bybit BTC price) with no buy at a seen ask above
rem 0.50, limit unchanged (flag speed_v8, prereg btc-speed-v8-bybit; trader/engines/speed.py PARAMS_V8_BYBIT).
rem Run from the roster folder with ROSTER_HUMAN_KEY set (ops\paper_tasks.ps1 startv8b does this for you).

setlocal
if "%ROSTER_HUMAN_KEY%"=="" (
  echo ROSTER_HUMAN_KEY is not set in this window.
  exit /b 2
)
set DIR=data\trader\paper_v8b
if not exist %DIR% mkdir %DIR%

.venv\Scripts\python.exe -m nightly.drills keys > %DIR%\keys.jsonl || exit /b 1
.venv\Scripts\python.exe -m tools.clearance_cli --db %DIR%\advice.db sign --keys %DIR%\keys.jsonl --signer %USERNAME% --days 15 || exit /b 1

.venv\Scripts\python.exe -m trader.loop --paper --minutes 20160 --dir %DIR% --enable speed_v4 --enable ref_bybit --enable speed_only --enable speed_v8 --global-cap 1000 --enable feed_hub
