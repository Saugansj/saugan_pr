@echo off
rem Side-by-side PAPER run of btc-speed v4's exact rule on ETH 5m/15m Up/Down (flag speed_eth), so BTC is not the only
rem coin tested. Pre-registered as btc-speed-v4-eth. Phase 0 ETH lost with the old 10 bp / 5 s detector; this tests v4's.
rem record_tob: the ETH research loop replays this run's own book (paper_v3 records BTC only).
rem Run from the roster folder with ROSTER_HUMAN_KEY set (ops\paper_tasks.ps1 starteth does this for you).

setlocal
if "%ROSTER_HUMAN_KEY%"=="" (
  echo ROSTER_HUMAN_KEY is not set in this window.
  exit /b 2
)
set DIR=data\trader\paper_eth
if not exist %DIR% mkdir %DIR%

.venv\Scripts\python.exe -m nightly.drills keys > %DIR%\keys.jsonl || exit /b 1
.venv\Scripts\python.exe -m tools.clearance_cli --db %DIR%\advice.db sign --keys %DIR%\keys.jsonl --signer %USERNAME% --days 15 || exit /b 1

.venv\Scripts\python.exe -m trader.loop --paper --minutes 20160 --dir %DIR% --enable speed_v4 --enable speed_eth --enable speed_only --enable record_tob --global-cap 1000
