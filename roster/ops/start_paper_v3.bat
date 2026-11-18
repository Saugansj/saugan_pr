@echo off
rem Side-by-side PAPER run of btc-speed v3 (quick exit 8 s after the fill, buys capped at 0.75), next to paper14.
rem No ladder-maker here (flag speed_only), so paper14 keeps the v2 baseline and the ladder results stay in one place.
rem Run from the roster folder with ROSTER_HUMAN_KEY set (ops\paper_tasks.ps1 startv3 does this for you).

setlocal
if "%ROSTER_HUMAN_KEY%"=="" (
  echo ROSTER_HUMAN_KEY is not set in this window.
  exit /b 2
)
set DIR=data\trader\paper_v3
if not exist %DIR% mkdir %DIR%

.venv\Scripts\python.exe -m nightly.drills keys > %DIR%\keys.jsonl || exit /b 1
.venv\Scripts\python.exe -m tools.clearance_cli --db %DIR%\advice.db sign --keys %DIR%\keys.jsonl --signer %USERNAME% --days 15 || exit /b 1

.venv\Scripts\python.exe -m trader.loop --paper --minutes 20160 --dir %DIR% --enable speed_v3 --enable speed_only --enable record_tob --enable feed_hub
