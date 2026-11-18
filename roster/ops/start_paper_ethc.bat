@echo off

rem COMPOUNDING paper run (flag compound, prereg btc-speed-v4-eth-bybit-c): paper_ethb's rule, trade size = 5 shares per 50 USD

rem of account value (5..14, at most the ask). Starts with 80.86 USD = paper_ethb's balance on 13 Oct (reinvested profit).



rem record_tob: the ETH research loop replays this run's own book (paper_v3 records BTC only).

rem Run from the roster folder with ROSTER_HUMAN_KEY set (ops\paper_tasks.ps1 starteth does this for you).



setlocal

if "%ROSTER_HUMAN_KEY%"=="" (

  echo ROSTER_HUMAN_KEY is not set in this window.

  exit /b 2

)

set DIR=data\trader\paper_ethc

if not exist %DIR% mkdir %DIR%



.venv\Scripts\python.exe -m nightly.drills keys > %DIR%\keys.jsonl || exit /b 1

.venv\Scripts\python.exe -m tools.clearance_cli --db %DIR%\advice.db sign --keys %DIR%\keys.jsonl --signer %USERNAME% --days 15 || exit /b 1



.venv\Scripts\python.exe -m trader.loop --paper --minutes 20160 --dir %DIR% --enable speed_v4 --enable speed_eth --enable ref_bybit --enable compound --enable speed_only --global-cap 1000 --cash 80.86 --enable feed_hub

