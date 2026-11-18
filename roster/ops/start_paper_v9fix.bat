@echo off
rem Side-by-side PAPER run (18 Nov, user asked: "fix all issues, new paper run, same $50"): paper_v9fix.
rem v4b's rule (the live rule: flags speed_v4 ref_bybit speed_only, cap 0.85, limit ask + 10c, 5 shares, hold) plus:
rem   speed_v9       no buy at a seen ask below the min price (default 0.35; optional first argument, e.g. 0.50),
rem                  order size/limit picked so the venue accepts the amounts (whole-cent USDC leg, $1 minimum)
rem   paper_realism  fills like the live venue: live latency draw (median ~1.1 s), no give-up at arrival, spend
rem                  size x limit, venue amount rules, extra FAK no-match tracking the live fill rate (trader\realism.py)
rem   --daily-dd 0.35 as live; the start-of-day mark persists across restarts of this folder (trader\breakers.py)
rem $50 start (--cash 50, as paper_v4sz50). --global-cap 1000 as paper_v4b. Optional realism overrides:
rem   data\trader\paper_v9fix\realism.json (tools\calibrate_paper_fills.py --out ...) is used when it exists.
rem Run from the roster folder with ROSTER_HUMAN_KEY set (ops\paper_tasks.ps1 startv9fix does this for you).

setlocal
if "%ROSTER_HUMAN_KEY%"=="" (
  echo ROSTER_HUMAN_KEY is not set in this window.
  exit /b 2
)
set DIR=data\trader\paper_v9fix
if not exist %DIR% mkdir %DIR%
rem min price: first argument, else %DIR%\min_price.txt (written by start_paper_v9fix.ps1, so keeper restarts keep it), else 0.35
set MINP=%~1
if "%MINP%"=="" if exist %DIR%\min_price.txt set /p MINP=<%DIR%\min_price.txt
if "%MINP%"=="" set MINP=0.35
set RZ=
if exist %DIR%\realism.json set RZ=--realism %DIR%\realism.json

.venv\Scripts\python.exe -m nightly.drills keys > %DIR%\keys.jsonl || exit /b 1
.venv\Scripts\python.exe -m tools.clearance_cli --db %DIR%\advice.db sign --keys %DIR%\keys.jsonl --signer %USERNAME% --days 15 || exit /b 1

.venv\Scripts\python.exe -m trader.loop --paper --minutes 20160 --dir %DIR% --cash 50 --daily-dd 0.35 --enable speed_v4 --enable ref_bybit --enable speed_only --enable speed_v9 --enable paper_realism --min-price %MINP% %RZ% --global-cap 1000 --enable feed_hub
