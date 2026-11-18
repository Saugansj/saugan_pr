@echo off
rem Side-by-side PAPER run of btc-speed v6 on ETH, ETH price from Bybit (flags speed_v6 + speed_eth + ref_bybit, prereg
rem btc-speed-v6-eth-bybit): paper_ethb's rule + no buy at a seen ask in (0.30, 0.50]. ETH keeps its >600 s trades.
rem No record_tob: paper_ethb records the ETH book. Replaces paper_ethc (compounding, frozen 14 Oct).
rem Run from the roster folder with ROSTER_HUMAN_KEY set (ops\paper_tasks.ps1 starteth6b does this for you).

setlocal
if "%ROSTER_HUMAN_KEY%"=="" (
  echo ROSTER_HUMAN_KEY is not set in this window.
  exit /b 2
)
set DIR=data\trader\paper_eth6b
if not exist %DIR% mkdir %DIR%

.venv\Scripts\python.exe -m nightly.drills keys > %DIR%\keys.jsonl || exit /b 1
.venv\Scripts\python.exe -m tools.clearance_cli --db %DIR%\advice.db sign --keys %DIR%\keys.jsonl --signer %USERNAME% --days 15 || exit /b 1

.venv\Scripts\python.exe -m trader.loop --paper --minutes 20160 --dir %DIR% --enable speed_v6 --enable speed_eth --enable ref_bybit --enable speed_only --global-cap 1000 --enable feed_hub
