# Paper-run automation for this PC (paper14 + the paper_v3 and paper_v4 side runs; no real money). Entry points:
#   powershell -ExecutionPolicy Bypass -File ops\paper_tasks.ps1 hub      # first: the shared Binance/Bybit feed relay
#   powershell -ExecutionPolicy Bypass -File ops\paper_tasks.ps1 start    # at logon: start the trader if not already running
#   powershell -ExecutionPolicy Bypass -File ops\paper_tasks.ps1 sign     # 08:15: sign uncleared templates (2-day expiry),
#                                                                          # then reset breaker pauses (never a HALT)
#   powershell -ExecutionPolicy Bypass -File ops\paper_tasks.ps1 report   # 21:50 and at logon: daily report with catch-up
#   powershell -ExecutionPolicy Bypass -File ops\paper_tasks.ps1 startv3  # at logon: the btc-speed v3 side run, if not running
#   powershell -ExecutionPolicy Bypass -File ops\paper_tasks.ps1 startv4  # the btc-speed v4 side run, if not running
#   powershell -ExecutionPolicy Bypass -File ops\paper_tasks.ps1 starteth # v4's rule on ETH (paper_eth), if not running
#   powershell -ExecutionPolicy Bypass -File ops\paper_tasks.ps1 startv5  # v5 = v4 + calm filter (paper_v5), if not running
#   powershell -ExecutionPolicy Bypass -File ops\paper_tasks.ps1 resume   # every 10 min: lift feed-gap-only pauses
#   powershell -ExecutionPolicy Bypass -File ops\paper_tasks.ps1 loop     # 16:00: research loop on yesterday (UTC), BTC then ETH
#   powershell -ExecutionPolicy Bypass -File ops\paper_tasks.ps1 keep     # at logon: ops\keeper.py (starts hub + active runs,
#                                                                          # restarts dead ones, resume every 10 min)
# The approval key is read from %USERPROFILE%\.roster_human_key into this process only.
param([Parameter(Mandatory = $true)][ValidateSet("start", "sign", "report", "startv3", "startv4", "startv5", "startv5b", "starteth", "startv4b", "startethb", "startethc", "startv6b", "starteth6b", "startmk", "startethmk", "startv7b", "starteth7b", "starteth7c", "startv8b", "startv4add", "startv4sz50", "startv4sz100", "startv9fix", "hub", "resume", "loop", "keep", "dashboard")][string]$Action)

$Roster = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Roster ".venv\Scripts\python.exe"
$Runs = @("paper14", "paper_v3", "paper_v4", "paper_v4b", "paper_v5", "paper_v5b", "paper_eth", "paper_ethb", "paper_ethc", "paper_v6b", "paper_eth6b", "paper_mk", "paper_ethmk", "paper_v7b", "paper_eth7b", "paper_eth7c", "paper_v8b", "paper_v4add", "paper_v4sz50", "paper_v4sz100", "paper_v9fix")
$Log = Join-Path $Roster "data\trader\paper_tasks.log"
Set-Location $Roster
function Note($msg) { "$(Get-Date -Format s) [$Action] $msg" | Out-File -Append -Encoding utf8 $Log }
# Python output into the log as UTF-8 (a plain *>> wrote UTF-16 into this UTF-8 file)
function Run-Py { & $Py @args 2>&1 | ForEach-Object { "$_" } | Out-File -Append -Encoding utf8 $Log }

function Load-Key {
    $f = Join-Path $env:USERPROFILE ".roster_human_key"
    if (-not (Test-Path $f)) { Note "no key file at $f"; exit 2 }
    $env:ROSTER_HUMAN_KEY = (Get-Content $f -Raw).Trim()
}

# Detached via WMI, not Start-Process: a child of the launching shell dies with it (14 Oct: closing the Claude app
# killed four runs it had started). A WMI child inherits no environment, so each run reads the key file itself.
function Detach($cmd) {
    $null = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine = "cmd.exe /c $cmd"; CurrentDirectory = $Roster}
}

function Start-Run($name, $bat) {
    # the cmd wrapper counts too: during the 1-5 min drills crawl there is no trader.loop yet (no double start)
    $running = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='cmd.exe'" |
        Where-Object { $_.CommandLine -like "*trader.loop*$name *" -or $_.CommandLine -like "*trader.loop*$name" -or $_.CommandLine -like "*ops\$bat*" }
    if ($running) { Note "$name already running (pid $($running.ProcessId)); nothing to do"; return }
    $kf = Join-Path $env:USERPROFILE ".roster_human_key"
    if (-not (Test-Path $kf)) { Note "no key file at $kf"; exit 2 }
    Detach "set /p ROSTER_HUMAN_KEY=<`"$kf`" & ops\$bat >> data\trader\$($name)_console.log 2>&1"
    Note "$name started"
}

switch ($Action) {
    "hub" {  # trader.feedhub: one Binance + one Bybit upstream relayed to every run with the feed_hub flag; start it first
        $h = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*trader.feedhub*" }
        if ($h) { Note "feed hub already running (pid $($h.ProcessId)); nothing to do"; return }
        Detach ".venv\Scripts\python.exe -m trader.feedhub >> data\trader\feedhub_console.log 2>&1"
        Note "feed hub started"
    }
    "dashboard" {  # ops\dashboard.py on http://127.0.0.1:8790 (localhost only); one copy
        $d = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*ops\dashboard.py*" }
        if ($d) { Note "dashboard already running (pid $($d.ProcessId)); nothing to do"; return }
        Detach ".venv\Scripts\python.exe -u ops\dashboard.py >> data\trader\dashboard_console.log 2>&1"
        Note "dashboard started on http://127.0.0.1:8790"
    }
    "keep" {  # single-instance by its own lock, so a second launch just exits
        Detach ".venv\Scripts\python.exe -u ops\keeper.py >> data\trader\keeper_console.log 2>&1"
        Note "keeper launched"
    }
    "start" { Start-Run "paper14" "start_paper_14d.bat" }
    "startv3" { Start-Run "paper_v3" "start_paper_v3.bat" }
    "startv4" { Start-Run "paper_v4" "start_paper_v4.bat" }
    "startv5" { Start-Run "paper_v5" "start_paper_v5.bat" }
    "startv5b" { Start-Run "paper_v5b" "start_paper_v5b.bat" }
    "starteth" { Start-Run "paper_eth" "start_paper_eth.bat" }
    "startv4b" { Start-Run "paper_v4b" "start_paper_v4b.bat" }
    "startethb" { Start-Run "paper_ethb" "start_paper_ethb.bat" }
    "startethc" { Start-Run "paper_ethc" "start_paper_ethc.bat" }
    "startv6b" { Start-Run "paper_v6b" "start_paper_v6b.bat" }
    "starteth6b" { Start-Run "paper_eth6b" "start_paper_eth6b.bat" }
    "startmk" { Start-Run "paper_mk" "start_paper_mk.bat" }        # btc-speed maker, BTC (20 Oct, profit plan B6)
    "startethmk" { Start-Run "paper_ethmk" "start_paper_ethmk.bat" }  # btc-speed maker, ETH
    "startv7b" { Start-Run "paper_v7b" "start_paper_v7b.bat" }      # btc-speed v7 (fair-value rule), BTC (23 Oct; not in keeper ACTIVE)
    "starteth7c" { Start-Run "paper_eth7c" "start_paper_eth7c.bat" }  # ethb's rule with a 0.70 cap (23 Oct)
    "starteth7b" { Start-Run "paper_eth7b" "start_paper_eth7b.bat" }  # btc-speed v7, ETH
    "startv8b" { Start-Run "paper_v8b" "start_paper_v8b.bat" }      # v4b + skip asks above 0.50, BTC (30 Oct)
    "startv4add" { Start-Run "paper_v4add" "start_paper_v4add.bat" }   # v4b + one same-side add per market, BTC (15 Nov)
    "startv4sz50" { Start-Run "paper_v4sz50" "start_paper_v4sz50.bat" }   # v4b at 8 shares, $50 (17 Nov)
    "startv4sz100" { Start-Run "paper_v4sz100" "start_paper_v4sz100.bat" }  # v4b at 8 shares, $100 (17 Nov)
    "startv9fix" { Start-Run "paper_v9fix" "start_paper_v9fix.bat" }  # v4b + min ask 0.35 + venue amounts + live-like fills, $50 (18 Nov)
    # startwx removed 15 Nov: the weather NO paper run is retired (user); data stays in data\trader\paper_wx
    "sign" {
        Load-Key
        foreach ($r in $Runs) {
            $unc = Join-Path $Roster "data\trader\$r\uncleared.jsonl"
            if (-not (Test-Path $unc) -or (Get-Item $unc).Length -eq 0) { Note "$r nothing uncleared"; continue }
            Run-Py -m tools.clearance_cli --db "data\trader\$r\advice.db" sign --keys $unc --signer "$env:USERNAME-auto" --days 2
            Note "$r signed uncleared templates (exit $LASTEXITCODE)"
        }
        Run-Py ops\morning_reset.py @Runs
        Note "morning breaker reset (exit $LASTEXITCODE)"
    }
    "resume" {
        Load-Key
        Run-Py ops\feed_resume.py @Runs   # writes to the log only when it lifts a pause
    }
    "loop" {
        Run-Py -m research.loop.nightly
        Note "research loop (exit $LASTEXITCODE)"
        Run-Py -m research.loop.nightly --asset eth
        Note "research loop ETH (exit $LASTEXITCODE)"
    }
    "report" {
        foreach ($r in $Runs) {
            if (-not (Test-Path (Join-Path $Roster "data\trader\$r\rtt.jsonl"))) { continue }
            Run-Py ops\daily_report.py $r
            Note "$r report run (exit $LASTEXITCODE)"
        }
        Run-Py ops\shadow.py   # proposed filters/limits on the control runs at the live estimate (reports\research\shadow.md)
        Note "shadow scores run (exit $LASTEXITCODE)"
        Run-Py ops\maker_rescore.py   # maker bids filled from the real tape (poll mode cannot fill them in paper)
        Note "maker re-score run (exit $LASTEXITCODE)"
        Run-Py ops\phase_c.py   # Phase C tracker: 2 SE progress, uptime, Phase D gate (reports\research\phase_c_status.md)
        Note "phase C status run (exit $LASTEXITCODE)"
        Run-Py ops\live_vs_paper.py   # real orders vs paper_v4b on the same signals (reports\research\live_vs_paper.md)
        Note "live vs paper run (exit $LASTEXITCODE)"
    }
}
