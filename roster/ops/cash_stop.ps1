# Stop one live account on a cash level, measured on the WALLET CASH (pUSD balance, not portfolio value):
#   powershell -ExecutionPolicy Bypass -File ops\cash_stop.ps1 -Target 40 -Floor 30
#   powershell -ExecutionPolicy Bypass -File ops\cash_stop.ps1 -Account live_b -Target 40 -Floor 30
#   powershell -ExecutionPolicy Bypass -File ops\cash_stop.ps1 -Account live_b -Target 40 -Floor 30 -DryRun
# Target: take-profit, stop once cash is at or above it. Floor: stop-loss, stop once cash is at or below it.
# Cash is read with ops\live_session.py balance (GET /balance-allowance: pUSD actually in the wallet), so a buy lowers
# it and a settled winner raises it. Two consecutive readings must agree, so one bad read cannot stop the run.
# The floor also waits for a flat book (ops\live_session.py check: no unsettled bet), because a buy drops cash by
# ~3.82 for a few minutes without any loss; only a settlement makes a loss real.
# The stop is the same as Ctrl+C in that account's launcher window: that loop ends and the launcher's finally stops
# its claimer and writes its live*.json back to {"live": false}. Only THIS -Account is touched (the other can keep running).
param(
    [ValidateSet("live", "live_b")]
    [string]$Account = "live",
    [double]$Target = 40,         # take-profit level; 0 disables it
    [double]$Floor = 0,           # stop-loss level; 0 disables it
    [int]$EveryS = 20,
    [int]$ConfirmChecks = 2,      # consecutive readings before acting
    [switch]$DryRun
)
$Roster = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Roster ".venv\Scripts\python.exe"
Set-Location $Roster

$metaJson = & $Py -c "import json; from ops.live_accounts import ROOT, get; a=get('$Account'); print(json.dumps({'dir':str(a['dir'].relative_to(ROOT)).replace(chr(92),'/'), 'switch':str(a['switch']), 'claims':str(a['claims'])}))"
if ($LASTEXITCODE -ne 0) { Write-Host "REFUSED: unknown account $Account"; exit 1 }
$meta = $metaJson | ConvertFrom-Json
$Dir = ($meta.dir -replace '/', '\')
$LiveJson = $meta.switch
$ClaimsLog = $meta.claims
$Log = Join-Path $Roster ("data\trader\cash_stop_{0}.log" -f $Account)
function Log($m) { "{0:o}  {1}" -f (Get-Date), $m | Out-File $Log -Append -Encoding utf8 }

function WalletCash {
    $out = & $Py "ops\live_session.py" balance --account $Account 2>$null | Select-Object -Last 1
    $s = "$out".Trim()
    if (-not $s) { return $null }
    $v = 0.0
    if ([double]::TryParse($s, [System.Globalization.NumberStyles]::Float,
                           [Globalization.CultureInfo]::InvariantCulture, [ref]$v)) { return $v }
    return $null
}

function LiveLoop {
    # only the loop whose --dir is this account (the other account may run in parallel)
    @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
        $_.CommandLine -match '-m\s+trader\.loop' -and $_.CommandLine -match '--live' -and (
            $_.CommandLine -match [regex]::Escape($Dir) -or
            $_.CommandLine -match [regex]::Escape(($Dir -replace '\\', '/')))
    })
}

function Test-Flat {
    & $Py "ops\live_session.py" check --account $Account 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function StopLive {
    $loop = LiveLoop
    if (-not $loop) { Log "stop: no live loop to stop for $Account"; return }
    Log ("stop: ending $Account live loop pid(s) " + (($loop.ProcessId) -join ', '))
    foreach ($p in $loop) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 8
    $left = LiveLoop
    if ($left) {
        Log ("stop: still running " + (($left.ProcessId) -join ', ') + "; second attempt")
        foreach ($p in $left) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 5
    }
    $claimers = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
        $_.CommandLine -match 'claimer\.py' -and (
            $_.CommandLine -match [regex]::Escape($ClaimsLog) -or
            $_.CommandLine -match [regex]::Escape(($ClaimsLog -replace '\\', '/')))
    })
    foreach ($c in $claimers) { Stop-Process -Id $c.ProcessId -Force -ErrorAction SilentlyContinue }
    if ($claimers) { Log ("stop: stopped $Account claimer pid(s) " + (($claimers.ProcessId) -join ', ')) }
    $txt = (Get-Content $LiveJson -Raw -ErrorAction SilentlyContinue)
    if ($txt -and $txt.Trim() -ne '{"live": false}') {
        [IO.File]::WriteAllText($LiveJson, '{"live": false}', (New-Object Text.UTF8Encoding $false))
        Log ("stop: $LiveJson forced back to {`"live`": false}")
    }
    Log ("stop: $Account live loop gone (" + ((LiveLoop).Count) + " left)")
}

Log ("watcher start: account=$Account target {0:N2} pUSD cash, floor {1:N2} (0 = off), every {2}s, dry run={3}" -f $Target, $Floor, $EveryS, $DryRun)
$hits = 0
$floorHits = 0
$lastNote = [datetime]::MinValue
while ($true) {
    if (-not (LiveLoop)) { Log "no $Account live loop running; watcher exits"; break }
    $cash = WalletCash
    if ($null -eq $cash) {
        Log 'balance read failed; ignored'
        $hits = 0
        $floorHits = 0
    } else {
        $stop = ''
        if ($Target -gt 0 -and $cash -ge $Target) { $hits++ } else { $hits = 0 }
        if ($hits -ge $ConfirmChecks) {
            Log ("target reached: cash {0:N2} >= {1:N2} ({2} checks)" -f $cash, $Target, $hits)
            $stop = 'take-profit'
        }
        if (-not $stop -and $Floor -gt 0 -and $cash -le $Floor) {
            if (Test-Flat) {
                $floorHits++
                if ($floorHits -ge $ConfirmChecks) {
                    Log ("floor reached: cash {0:N2} <= {1:N2} and no open bet ({2} checks)" -f $cash, $Floor, $floorHits)
                    $stop = 'stop-loss'
                }
            } else {
                if ($floorHits -eq 0) { Log ("cash {0:N2} at or under the floor but a bet is open; waiting" -f $cash) }
                $floorHits = 0
            }
        } elseif ($Floor -gt 0) {
            $floorHits = 0
        }
        if ($stop) {
            if ($DryRun) { Log ("dry run: would stop the $Account live loop now ({0})" -f $stop); }
            else { StopLive; Log ("watcher done ({0})" -f $stop); }
            break
        }
        if (((Get-Date) - $lastNote).TotalSeconds -ge 300) {
            $lastNote = Get-Date
            Log ("cash {0:N2} (target {1:N2}, floor {2:N2})" -f $cash, $Target, $Floor)
        }
    }
    $wait = $EveryS
    if ($null -ne $cash -and $Floor -gt 0 -and $cash -le ($Floor + 1)) { $wait = [Math]::Min(5, $EveryS) }
    Start-Sleep -Seconds $wait
}
