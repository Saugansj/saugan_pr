# One-command LIVE run of rule v4 (real money). Run from a normal PowerShell, in the foreground; Ctrl+C stops it:
#   powershell -ExecutionPolicy Bypass -File ops\start_live_v4.ps1 -DailyStop 0.35
#   powershell -ExecutionPolicy Bypass -File ops\start_live_v4.ps1 -Account live_b -DailyStop 0.35
#   powershell -ExecutionPolicy Bypass -File ops\start_live_v4.ps1 -Account live_b -DryRun
# ROSTER_LIVE is set in this process only; this account's live*.json is written back to {"live": false} when the bot ends.
# -Account live     = existing Windows-user POLY_* (data\trader\live)
# -Account live_b   = Magic second wallet from %USERPROFILE%\.roster_live_b.json (data\trader\live_b); does not overwrite Account A
# Both can run at once: pre-flight only refuses if THIS account's --dir already has a live loop.
# Default -Minutes 0 = no session timer: keeps running (and restarts on crash) until Ctrl+C, cash_stop, or you flip the switch.
# Daily equity stop (--daily-dd) goes REDUCING (no new buys) but does not exit the process. Wallet floor: cash_stop.ps1.
# Carry of today's UTC mark is ON by default so a relaunch cannot reset the day. Pass -DayFlow for deposits/withdrawals.
param(
    [ValidateSet("live", "live_b")]
    [string]$Account = "live",
    [double]$Cash = -1,
    [double]$DailyStop = 0.20,
    [int]$Minutes = 0,
    [switch]$DryRun,
    # -DayFlow: USD deposited (+) or withdrawn (-) since the day's first start, so a withdrawal is not read as a loss.
    [switch]$NoCarryDailyStop,
    [double]$DayFlow = 0,
    # Wallet cash floor (pUSD). -1 = auto: day-mark * (1 - DailyStop). 0 = off. >0 = explicit.
    [double]$CashFloor = -1,
    [double]$CashTarget = 0,   # take-profit on wallet cash; 0 = off
    [int]$MaxOffsetMs = 300,
    [double]$MaxOrderServerS = 0.6
)
$CarryDailyStop = -not $NoCarryDailyStop
$Roster = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Roster ".venv\Scripts\python.exe"
Set-Location $Roster
$bad = 0
function Check($ok, $name, $detail) {
    if ($ok) { Write-Host "  [ OK ] $name  $detail" -ForegroundColor Green }
    else { Write-Host "  [FAIL] $name  $detail" -ForegroundColor Red; $script:bad++ }
}
function Median($v) { $s = @($v | Sort-Object); $s[[int][math]::Floor($s.Count / 2)] }

# Resolve paths + load this account's POLY_* into THIS process only (secrets via a temp file, never printed)
$EnvTmp = Join-Path $env:TEMP ("roster_live_env_{0}_{1}.txt" -f $Account, $PID)
$metaJson = & $Py -c @"
import json, pathlib
from ops.live_accounts import ROOT, POLY_KEYS, RELAYER_KEYS, apply_account_env, get
a = get('$Account')
env = apply_account_env('$Account')
tmp = pathlib.Path(r'$EnvTmp')
keys = list(POLY_KEYS) + list(RELAYER_KEYS) + ['ROSTER_LIVE_JSON']
with tmp.open('w', encoding='utf-8') as f:
    for k in keys:
        if env.get(k):
            f.write(k + '=' + env[k].replace('\n','').replace('\r','') + '\n')
print(json.dumps({
  'label': (json.loads(a['env_file'].read_text(encoding='utf-8')).get('label') if a['env_file'] and a['env_file'].exists() else None) or a['label'],
  'dir': str(a['dir'].relative_to(ROOT)).replace('\\\\','/'),
  'switch': str(a['switch']),
  'claims': str(a['claims']),
  'has_relayer': bool(env.get('RELAYER_API_KEY') and env.get('RELAYER_API_KEY_ADDRESS')),
}))
"@
if ($LASTEXITCODE -ne 0) {
    Remove-Item $EnvTmp -ErrorAction SilentlyContinue
    Write-Host "REFUSED: could not load account '$Account' (for live_b run: .venv\Scripts\python.exe ops\setup_live_b.py)." -ForegroundColor Red
    exit 1
}
$meta = $metaJson | ConvertFrom-Json
Get-Content $EnvTmp -Encoding UTF8 | ForEach-Object {
    $i = $_.IndexOf('='); if ($i -gt 0) { Set-Item -Path ("Env:" + $_.Substring(0, $i)) -Value $_.Substring($i + 1) }
}
Remove-Item $EnvTmp -Force -ErrorAction SilentlyContinue
$Dir = ($meta.dir -replace '/', '\')
$LiveJson = $meta.switch
$ClaimsLog = $meta.claims
$env:ROSTER_LIVE_ACCOUNT = $Account

function Write-Live($on) {
    [IO.File]::WriteAllText($LiveJson, $(if ($on) { '{"live": true}' } else { '{"live": false}' }), (New-Object Text.UTF8Encoding $false))
}

$untilLabel = if ($Minutes -le 0) { "until stopped" } else { "$Minutes min" }
Write-Host ("Pre-flight (live v4 · {0} · {1}, {2}, daily stop {3:P0})" -f $Account, $meta.label, $untilLabel, $DailyStop)
Check ($DailyStop -ge 0.05 -and $DailyStop -le 0.50) "daily stop" ("{0:P0} of the day's start (allowed 5-50%)" -f $DailyStop)
$wallet = (& $Py ops\live_session.py balance --account $Account 2>$null | Select-Object -Last 1)
$walletOk = $LASTEXITCODE -eq 0 -and $wallet -match '^\d+(\.\d+)?$'
Check $walletOk "wallet" $(if ($walletOk) { "{0:N2} pUSD (start cash for this session)" -f [double]$wallet } else { "balance read failed: $wallet" })
if ($walletOk -and $Cash -le 0) { $Cash = [math]::Floor([double]$wallet * 100) / 100 }
if ($walletOk -and [double]$wallet -lt 3) { Check $false "enough cash" "under 3 pUSD: one 5-share bet can cost up to 4.25" }
$prev = (& $Py ops\live_session.py check --account $Account | Select-Object -Last 1)
Check ($LASTEXITCODE -eq 0) "previous session" "$prev"

$badBeforeClock = $bad
$py1 = "import json; from trader.feedhub import clock_offsets; print(json.dumps([clock_offsets() for _ in range(3)]))"
try {
    $runs = & $Py -c $py1 | ConvertFrom-Json
    foreach ($ex in "binance", "bybit") {
        $off = Median ($runs | ForEach-Object { $_.$ex.offset_ms })
        $rtt = Median ($runs | ForEach-Object { $_.$ex.rtt_ms })
        Check ([math]::Abs($off) -le $MaxOffsetMs) "clock $ex" ("offset {0:N0} ms (limit {1}), rtt {2:N0} ms" -f $off, $MaxOffsetMs, $rtt)
    }
} catch { Check $false "clock" "clock_offsets() failed: $_" }
if ($bad -gt $badBeforeClock) { Write-Host "  Fix: run  w32tm /resync  in an admin PowerShell, then retry." -ForegroundColor Yellow }

$t = 1..3 | ForEach-Object {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    try { $null = Invoke-WebRequest "https://clob.polymarket.com/time" -UseBasicParsing -TimeoutSec 5; $sw.Elapsed.TotalSeconds } catch { 99 }
}
$m = Median $t
Check ($m -le $MaxOrderServerS) "order server" ("median GET /time {0:N2} s (limit {1})" -f $m, $MaxOrderServerS)

$procs = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'")
$hub = $procs | Where-Object { $_.CommandLine -match '-m\s+trader\.feedhub(\s|$)' }
Check ([bool]$hub) "feed hub" $(if ($hub) { "running (pid $(@($hub)[0].ProcessId))" } else { "NOT running (ops\paper_tasks.ps1 hub)" })
$liveSame = $procs | Where-Object {
    $_.CommandLine -match '-m\s+trader\.loop(\s|$)' -and $_.CommandLine -match '--live' -and (
        $_.CommandLine -match [regex]::Escape($Dir) -or $_.CommandLine -match [regex]::Escape(($Dir -replace '\\', '/')))
}
Check (-not $liveSame) "no live loop for $Account" $(if ($liveSame) { "already running (pid $(@($liveSame)[0].ProcessId))" } else { "none for this --dir" })

$kf = Join-Path $env:USERPROFILE ".roster_human_key"
$hasKey = [bool]$env:ROSTER_HUMAN_KEY
if (-not $hasKey -and (Test-Path $kf)) { $env:ROSTER_HUMAN_KEY = (Get-Content $kf -Raw).Trim(); $hasKey = [bool]$env:ROSTER_HUMAN_KEY }
Check $hasKey "ROSTER_HUMAN_KEY" $(if ($hasKey) { "available" } else { "missing (set it or create $kf)" })
& $Py -c "import py_clob_client_v2" 2>$null
Check ($LASTEXITCODE -eq 0) "py_clob_client_v2" $(if ($LASTEXITCODE -eq 0) { "importable" } else { "not importable in .venv" })

$ClaimPy = Join-Path $Roster ".venv-claim\Scripts\python.exe"
$claimOn = (Test-Path $ClaimPy) -and [bool]$meta.has_relayer
if ($claimOn) { Write-Host "  [ OK ] auto-claim  on (ops\claimer.py for $Account)" -ForegroundColor Green }
else { Write-Host ("  [WARN] auto-claim  off: " + $(if (-not (Test-Path $ClaimPy)) { ".venv-claim missing" } else { "no relayer key for this account; redeem by hand" }) ) -ForegroundColor Yellow }

if ($bad) { Write-Host "REFUSED: $bad check(s) failed. Nothing started." -ForegroundColor Red; exit 1 }
Write-Host "All checks passed." -ForegroundColor Green

$loopCmd = "$Py -m trader.loop --live --minutes $Minutes --dir $Dir --cash $Cash --enable speed_v4 --enable ref_bybit --enable speed_only --enable feed_hub --daily-dd $DailyStop"
$steps = @(
    "cmd /c `"$Py -m nightly.drills keys > $Dir\keys.jsonl`"",
    "$Py -m tools.clearance_cli --db $Dir\advice.db sign --keys $Dir\keys.jsonl --signer $env:USERNAME --days 15",
    $loopCmd + $(if ($Minutes -le 0) { "   # restart on crash while switch stays on" } else { "" })
)
function Test-LiveSwitchOn {
    try { return ((Get-Content $LiveJson -Raw -ErrorAction Stop).Trim() -eq '{"live": true}') } catch { return $false }
}
function Stop-CashStop {
    Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -and $_.CommandLine -match 'cash_stop\.ps1' -and $_.CommandLine -match [regex]::Escape("-Account $Account")
    } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

# Resolve the wallet floor after archive (needs today's carried mark when present).
function Resolve-CashFloor([double]$SessionCash) {
    if ($CashFloor -eq 0) { return 0.0 }
    if ($CashFloor -gt 0) { return [math]::Floor($CashFloor * 100) / 100 }
    $mark = $SessionCash
    $ds = Join-Path $Roster "$Dir\daily_start.json"
    if (Test-Path $ds) {
        try {
            $j = Get-Content $ds -Raw | ConvertFrom-Json
            if ($j.mark -gt 0) { $mark = [double]$j.mark }
        } catch { }
    }
    return [math]::Floor($mark * (1.0 - $DailyStop) * 100) / 100
}

if ($DryRun) {
    Write-Host "DRY RUN, would do (nothing is started, switch untouched):" -ForegroundColor Yellow
    Write-Host "  archive $Dir (if it holds a finished session)$(if ($CarryDailyStop) { " and carry today's daily-stop mark (flow $DayFlow)" } else { " WITHOUT carrying the day mark (-NoCarryDailyStop)" })"
    Write-Host "  `$env:ROSTER_LIVE = '1'  (this process only)"
    Write-Host "  `$env:ROSTER_LIVE_JSON = '$LiveJson'"
    Write-Host "  write $LiveJson = {`"live`": true}"
    $steps | ForEach-Object { Write-Host "  $_" }
    if ($claimOn) { Write-Host "  start claimer --live --log $ClaimsLog (stopped with the bot)" }
    $previewFloor = if ($CashFloor -eq 0) { 0.0 } elseif ($CashFloor -gt 0) { $CashFloor } else { [math]::Floor($Cash * (1.0 - $DailyStop) * 100) / 100 }
    if ($previewFloor -gt 0 -or $CashTarget -gt 0) {
        Write-Host ("  start cash_stop -Account {0} -Floor {1:N2} -Target {2:N2} (wallet pUSD; floor waits for a flat book)" -f $Account, $previewFloor, $CashTarget)
    } else { Write-Host "  cash_stop  off" }
    Write-Host "  finally: stop cash_stop + claimer; write $LiveJson = {`"live`": false}"
    exit 0
}

$archArgs = @("ops\live_session.py", "archive", "--account", $Account)
if ($CarryDailyStop) { $archArgs += @("--carry-daily", "--flow", $DayFlow.ToString([Globalization.CultureInfo]::InvariantCulture)) }
& $Py @archArgs; if ($LASTEXITCODE) { Write-Host "REFUSED: previous session still has open bets." -ForegroundColor Red; exit 1 }
New-Item -ItemType Directory -Force (Join-Path $Roster $Dir) | Out-Null
$Floor = Resolve-CashFloor $Cash
if ($CarryDailyStop) {
    $ds = Join-Path $Roster "$Dir\daily_start.json"
    if (Test-Path $ds) {
        $j = Get-Content $ds -Raw | ConvertFrom-Json
        Write-Host ("daily stop mark carried: {0:N2} pUSD (UTC day {1})" -f [double]$j.mark, $j.day) -ForegroundColor Green
    } else {
        Write-Host "daily stop mark: no prior mark for today; this session's cash is the day start" -ForegroundColor Yellow
    }
}
if ($Floor -gt 0 -or $CashTarget -gt 0) {
    Write-Host ("wallet cash_stop: floor {0:N2} (0=off)  target {1:N2} (0=off)  — stops the loop on pUSD when flat" -f $Floor, $CashTarget) -ForegroundColor Green
} else {
    Write-Host "wallet cash_stop: off" -ForegroundColor Yellow
}
# Already under the day's wallet floor with a flat book: starting would only burn more. Wait for a new UTC day or deposit.
if ($Floor -gt 0 -and $walletOk -and [double]$wallet -le $Floor) {
    & $Py ops\live_session.py check --account $Account 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host ("REFUSED: wallet {0:N2} is already at/under cash floor {1:N2} and the book is flat. Deposit, wait for a new UTC day, or pass -CashFloor 0 / -DayFlow <deposit>." -f [double]$wallet, $Floor) -ForegroundColor Red
        exit 1
    }
}
[IO.File]::WriteAllText((Join-Path $Roster "$Dir\session.json"), ('{{"daily_stop": {0}, "minutes": {1}, "cash": {2}, "account": "{3}", "label": "{4}", "cash_floor": {5}, "cash_target": {6}}}' -f
    $DailyStop.ToString([Globalization.CultureInfo]::InvariantCulture), $Minutes, $Cash.ToString([Globalization.CultureInfo]::InvariantCulture),
    $Account, ($meta.label -replace '"', ''),
    $Floor.ToString([Globalization.CultureInfo]::InvariantCulture),
    $CashTarget.ToString([Globalization.CultureInfo]::InvariantCulture)),
    (New-Object Text.UTF8Encoding $false))
$env:ROSTER_LIVE = "1"
$claim = $null
$cashStop = $null
try {
    Write-Live $true
    if ($claimOn) {
        Get-CimInstance Win32_Process | Where-Object {
            $_.CommandLine -match 'ops\\claimer\.py' -and (
                $_.CommandLine -match [regex]::Escape($ClaimsLog) -or
                $_.CommandLine -match [regex]::Escape(($ClaimsLog -replace '\\', '/')))
        } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        $claimLogOut = Join-Path $Roster ("data\trader\claimer_{0}_console.log" -f $Account)
        $claimLogErr = Join-Path $Roster ("data\trader\claimer_{0}_errors.log" -f $Account)
        $claim = Start-Process -FilePath $ClaimPy -ArgumentList "-u ops\claimer.py --live --log `"$ClaimsLog`"" -WorkingDirectory $Roster -PassThru `
            -WindowStyle Hidden -RedirectStandardOutput $claimLogOut -RedirectStandardError $claimLogErr
        Write-Host "auto-claim started (pid $($claim.Id)); log $claimLogOut" -ForegroundColor Green
    }
    if ($Floor -gt 0 -or $CashTarget -gt 0) {
        Stop-CashStop
        $csLogOut = Join-Path $Roster ("data\trader\cash_stop_{0}_console.log" -f $Account)
        $csLogErr = Join-Path $Roster ("data\trader\cash_stop_{0}_errors.log" -f $Account)
        $csArgs = @(
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $PSScriptRoot "cash_stop.ps1"),
            "-Account", $Account,
            "-Floor", $Floor.ToString([Globalization.CultureInfo]::InvariantCulture),
            "-Target", $CashTarget.ToString([Globalization.CultureInfo]::InvariantCulture)
        )
        $cashStop = Start-Process -FilePath "powershell.exe" -ArgumentList $csArgs -WorkingDirectory $Roster -PassThru `
            -WindowStyle Hidden -RedirectStandardOutput $csLogOut -RedirectStandardError $csLogErr
        Write-Host "cash_stop started (pid $($cashStop.Id)); log data\trader\cash_stop_$Account.log" -ForegroundColor Green
    }
    cmd /c "`"$Py`" -m nightly.drills keys > $Dir\keys.jsonl"; if ($LASTEXITCODE) { throw "drills keys failed ($LASTEXITCODE)" }
    & $Py -m tools.clearance_cli --db "$Dir\advice.db" sign --keys "$Dir\keys.jsonl" --signer $env:USERNAME --days 15; if ($LASTEXITCODE) { throw "clearance sign failed ($LASTEXITCODE)" }
    # No session timer (-Minutes 0): keep the process up; restart on crash while the switch is still on.
    # Timed sessions (-Minutes >0): one shot, then exit (legacy). cash_stop / Ctrl+C flip the switch off → no restart.
    while ($true) {
        & $Py -m trader.loop --live --minutes $Minutes --dir $Dir --cash $Cash --enable speed_v4 --enable ref_bybit --enable speed_only --enable feed_hub --daily-dd $DailyStop
        $code = $LASTEXITCODE
        if ($Minutes -gt 0) {
            Write-Host "live loop exited ($code) after timed session"
            break
        }
        if (-not (Test-LiveSwitchOn)) {
            Write-Host "live loop exited ($code); switch off — not restarting"
            break
        }
        Write-Host "live loop exited unexpectedly ($code); restarting in 5s (Ctrl+C to stop)" -ForegroundColor Yellow
        Start-Sleep -Seconds 5
        if (-not (Test-LiveSwitchOn)) {
            Write-Host "switch off during backoff — not restarting"
            break
        }
    }
} finally {
    if ($cashStop) { Stop-Process -Id $cashStop.Id -Force -ErrorAction SilentlyContinue; Stop-CashStop; Write-Host "cash_stop stopped" -ForegroundColor Yellow }
    if ($claim) { Stop-Process -Id $claim.Id -Force -ErrorAction SilentlyContinue; Write-Host "auto-claim stopped" -ForegroundColor Yellow }
    Write-Live $false
    Remove-Item Env:ROSTER_LIVE -ErrorAction SilentlyContinue
    Write-Host "switch $LiveJson reset to {`"live`": false}" -ForegroundColor Yellow
}
