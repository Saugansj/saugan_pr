@echo off
rem Side-by-side PAPER run (23 Oct, user approved): ethb's rule (v4 on ETH, Bybit price) with the price cap at 0.70
rem instead of 0.85 (flag speed_cap70, prereg btc-speed-v7c-eth-bybit; trader/engines/speed.py PARAMS_V7C_ETH_BYBIT).
rem Run from the roster folder with ROSTER_HUMAN_KEY set (ops\paper_tasks.ps1 starteth7c does this for you).

setlocal
if "%ROSTER_HUMAN_KEY%"=="" (
  echo ROSTER_HUMAN_KEY is not set in this window.
  exit /b 2
)
set DIR=data\trader\paper_eth7c
if not exist %DIR% mkdir %DIR%

.venv\Scripts\python.exe -m nightly.drills keys > %DIR%\keys.jsonl || exit /b 1
.venv\Scripts\python.exe -m tools.clearance_cli --db %DIR%\advice.db sign --keys %DIR%\keys.jsonl --signer %USERNAME% --days 15 || exit /b 1

.venv\Scripts\python.exe -m trader.loop --paper --minutes 20160 --dir %DIR% --enable speed_v4 --enable speed_eth --enable ref_bybit --enable speed_only --enable speed_cap70 --global-cap 1000 --enable feed_hub
