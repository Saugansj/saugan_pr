@echo off
rem Side-by-side PAPER run of the btc-speed MAKER on BTC, Bybit price (flags speed_maker + ref_bybit + maker_realism,
rem prereg btc-speed-mk-bybit): on v4b's 6 bp / 2 s signal, a post-only bid one tick under the ask on BTC 15m markets,
rem cancelled after 5 s, held to resolution. Control: paper_v4b (same signal, taker). Profit plan 16 Oct, B6.
rem Run from the roster folder with ROSTER_HUMAN_KEY set (ops\paper_tasks.ps1 startmk does this for you).

setlocal
if "%ROSTER_HUMAN_KEY%"=="" (
  echo ROSTER_HUMAN_KEY is not set in this window.
  exit /b 2
)
set DIR=data\trader\paper_mk
if not exist %DIR% mkdir %DIR%

.venv\Scripts\python.exe -m nightly.drills keys > %DIR%\keys.jsonl || exit /b 1
.venv\Scripts\python.exe -m tools.clearance_cli --db %DIR%\advice.db sign --keys %DIR%\keys.jsonl --signer %USERNAME% --days 15 || exit /b 1

.venv\Scripts\python.exe -m trader.loop --paper --minutes 20160 --dir %DIR% --enable speed_maker --enable ref_bybit --enable speed_only --enable maker_realism --global-cap 1000 --enable feed_hub
