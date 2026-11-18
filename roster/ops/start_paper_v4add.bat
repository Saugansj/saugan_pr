@echo off
rem Side-by-side PAPER run (15 Nov, user approved): v4b's rule plus ONE more same-side bet when a later signal hits
rem a market already held (never the other side, never a third bet; flag speed_add, prereg btc-speed-v4-bybit-add).
rem Run from the roster folder with ROSTER_HUMAN_KEY set (ops\paper_tasks.ps1 startv4add does this for you).

setlocal
if "%ROSTER_HUMAN_KEY%"=="" (
  echo ROSTER_HUMAN_KEY is not set in this window.
  exit /b 2
)
set DIR=data\trader\paper_v4add
if not exist %DIR% mkdir %DIR%

.venv\Scripts\python.exe -m nightly.drills keys > %DIR%\keys.jsonl || exit /b 1
.venv\Scripts\python.exe -m tools.clearance_cli --db %DIR%\advice.db sign --keys %DIR%\keys.jsonl --signer %USERNAME% --days 15 || exit /b 1

.venv\Scripts\python.exe -m trader.loop --paper --minutes 20160 --dir %DIR% --enable speed_v4 --enable ref_bybit --enable speed_only --enable speed_add --global-cap 1000 --enable feed_hub
