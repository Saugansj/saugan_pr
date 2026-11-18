@echo off
rem Weather NO PAPER run (2 Nov, user asked): $10 account buying NO on temperature buckets that won't happen
rem (weather/paper.py; dead + far arms, real NO books, shadow log of every signal). No keys or clearances needed.
rem Run from the roster folder (ops\paper_tasks.ps1 startwx does this for you).

setlocal
rem bucket titles carry a degree sign: cp1252 stdout into the console log would raise on it
set PYTHONIOENCODING=utf-8
set DIR=data\trader\paper_wx
if not exist %DIR% mkdir %DIR%
.venv\Scripts\python.exe -u -m weather.paper run --dir %DIR%
