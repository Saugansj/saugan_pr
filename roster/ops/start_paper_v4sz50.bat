@echo off
rem Side-by-side PAPER run (17 Nov): v4b's rule at 8 shares, $50 cash (flag speed_sz, prereg btc-speed-v4-bybit-sz).
rem Pair with paper_v4sz100. Run from roster with ROSTER_HUMAN_KEY set (ops\paper_tasks.ps1 startv4sz50).

setlocal
if "%ROSTER_HUMAN_KEY%"=="" (
  echo ROSTER_HUMAN_KEY is not set in this window.
  exit /b 2
)
set DIR=data\trader\paper_v4sz50
if not exist %DIR% mkdir %DIR%

.venv\Scripts\python.exe -m nightly.drills keys > %DIR%\keys.jsonl || exit /b 1
.venv\Scripts\python.exe -m tools.clearance_cli --db %DIR%\advice.db sign --keys %DIR%\keys.jsonl --signer %USERNAME% --days 15 || exit /b 1

.venv\Scripts\python.exe -m trader.loop --paper --minutes 20160 --dir %DIR% --cash 50 --daily-dd 0.20 --enable speed_v4 --enable ref_bybit --enable speed_only --enable speed_sz --global-cap 1000 --enable feed_hub
