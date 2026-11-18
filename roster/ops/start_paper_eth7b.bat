@echo off
rem Side-by-side PAPER run of btc-speed v7 on ETH, ETH price from Bybit (flags speed_v7 + speed_eth + ref_bybit, prereg
rem btc-speed-v7-eth-bybit): paper_ethb's rule with the fair-value skip and limit instead of v6's skips
rem (reports/research/v7_test_2026-10-23.md). Not in ops\keeper.py ACTIVE until the user approves it.
rem Run from the roster folder with ROSTER_HUMAN_KEY set (ops\paper_tasks.ps1 starteth7b does this for you).

setlocal
if "%ROSTER_HUMAN_KEY%"=="" (
  echo ROSTER_HUMAN_KEY is not set in this window.
  exit /b 2
)
set DIR=data\trader\paper_eth7b
if not exist %DIR% mkdir %DIR%

.venv\Scripts\python.exe -m nightly.drills keys > %DIR%\keys.jsonl || exit /b 1
.venv\Scripts\python.exe -m tools.clearance_cli --db %DIR%\advice.db sign --keys %DIR%\keys.jsonl --signer %USERNAME% --days 15 || exit /b 1

.venv\Scripts\python.exe -m trader.loop --paper --minutes 20160 --dir %DIR% --enable speed_v7 --enable speed_eth --enable ref_bybit --enable speed_only --global-cap 1000 --enable feed_hub
