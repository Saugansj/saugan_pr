@echo off
rem Phase 1 exit gate: 14 days of PAPER trading on this PC (no real money, no keys to any venue).
rem Run from the roster folder:   ops\start_paper_14d.bat
rem
rem Before the first run (once):
rem   1. Keep the PC awake and plugged in for 14 days. To stop sleep on AC power (your choice, run it yourself):
rem        powercfg /change standby-timeout-ac 0
rem   2. Pick a private key string for your human approvals and keep it secret. It signs clearances and resets.
rem      Set it in THIS window only (it is never written to disk by these scripts):
rem        set ROSTER_HUMAN_KEY=<your secret>
rem   3. Optional daily report at 06:00 (Task Scheduler), run it yourself once:
rem        schtasks /create /tn RosterDailyReport /sc daily /st 06:00 /tr "cmd /c cd /d %CD% && .venv\Scripts\python.exe -m nightly.report --dir data\trader\paper14"

setlocal
if "%ROSTER_HUMAN_KEY%"=="" (
  echo ROSTER_HUMAN_KEY is not set in this window. See step 2 at the top of this file.
  exit /b 2
)
set DIR=data\trader\paper14
if not exist %DIR% mkdir %DIR%

echo Signing clearances for today's crypto templates (valid 15 days; re-run this file's two sign lines if rules text changes)...
.venv\Scripts\python.exe -m nightly.drills keys > %DIR%\keys.jsonl || exit /b 1
.venv\Scripts\python.exe -m tools.clearance_cli --db %DIR%\advice.db sign --keys %DIR%\keys.jsonl --signer %USERNAME% --days 15 || exit /b 1

echo Starting the paper trader for 14 days (20160 minutes). Close this window or press Ctrl+C to stop; it resumes from its journal.
.venv\Scripts\python.exe -m trader.loop --paper --minutes 20160 --dir %DIR% --enable feed_hub
