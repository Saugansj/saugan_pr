# Start the paper_v9fix run (18 Nov) detached, the same way ops\paper_tasks.ps1 starts every paper run (WMI child,
# key read from %USERPROFILE%\.roster_human_key, console log data\trader\paper_v9fix_console.log). Paper only.
#   powershell -ExecutionPolicy Bypass -File ops\start_paper_v9fix.ps1               # min price 0.35
#   powershell -ExecutionPolicy Bypass -File ops\start_paper_v9fix.ps1 -MinPrice 0.50
#   powershell -ExecutionPolicy Bypass -File ops\start_paper_v9fix.ps1 -Foreground   # in this window (Ctrl+C stops)
param([double]$MinPrice = 0.35, [switch]$Foreground)
$Roster = Split-Path -Parent $PSScriptRoot
Set-Location $Roster
$kf = Join-Path $env:USERPROFILE ".roster_human_key"
if (-not (Test-Path $kf)) { Write-Host "no key file at $kf" -ForegroundColor Red; exit 2 }
$mp = $MinPrice.ToString([Globalization.CultureInfo]::InvariantCulture)
$dir = Join-Path $Roster "data\trader\paper_v9fix"
New-Item -ItemType Directory -Force $dir | Out-Null
$mpFile = Join-Path $dir "min_price.txt"
if ((Test-Path (Join-Path $dir "trader.db")) -and (Test-Path $mpFile) -and ((Get-Content $mpFile -Raw).Trim() -ne $mp)) {
    Write-Host "paper_v9fix already ran with min price $((Get-Content $mpFile -Raw).Trim()); a different one is a new test: use a new folder" -ForegroundColor Red
    exit 2
}
[IO.File]::WriteAllText($mpFile, $mp, (New-Object Text.ASCIIEncoding))
$running = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='cmd.exe'" |
    Where-Object { $_.CommandLine -like "*trader.loop*paper_v9fix*" -or $_.CommandLine -like "*ops\start_paper_v9fix.bat*" }
if ($running) { Write-Host "paper_v9fix already running (pid $($running.ProcessId))"; exit 0 }
if ($Foreground) {
    $env:ROSTER_HUMAN_KEY = (Get-Content $kf -Raw).Trim()
    cmd /c "ops\start_paper_v9fix.bat $mp"
    exit $LASTEXITCODE
}
$cmd = "cmd.exe /c set /p ROSTER_HUMAN_KEY=<`"$kf`" & ops\start_paper_v9fix.bat $mp >> data\trader\paper_v9fix_console.log 2>&1"
$null = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine = $cmd; CurrentDirectory = $Roster}
"$(Get-Date -Format s) [startv9fix] paper_v9fix started (min price $mp)" | Out-File -Append -Encoding utf8 (Join-Path $Roster "data\trader\paper_tasks.log")
Write-Host "paper_v9fix started (min price $mp). Log: data\trader\paper_v9fix_console.log" -ForegroundColor Green
