# Same live v4 launcher as ops\start_live_v4.ps1, locked to the second wallet (winsorwills / live_b).
# Identical flags, preflight, claimer, drills, clearance — only credentials + data\trader\live_b differ.
#   powershell -ExecutionPolicy Bypass -File ops\start_live_v4_b.ps1 -DailyStop 0.35
#   powershell -ExecutionPolicy Bypass -File ops\start_live_v4_b.ps1 -DailyStop 0.35 -DryRun
# Default -Minutes 0 = until Ctrl+C / cash_stop (same as start_live_v4.ps1).
param(
    [double]$Cash = -1,
    [double]$DailyStop = 0.20,
    [int]$Minutes = 0,
    [switch]$DryRun,
    [switch]$NoCarryDailyStop,
    [double]$DayFlow = 0,
    [double]$CashFloor = -1,
    [double]$CashTarget = 0,
    [int]$MaxOffsetMs = 300,
    [double]$MaxOrderServerS = 0.6
)
$here = $PSScriptRoot
$forward = @{
    Account = "live_b"
    Cash = $Cash
    DailyStop = $DailyStop
    Minutes = $Minutes
    DayFlow = $DayFlow
    CashFloor = $CashFloor
    CashTarget = $CashTarget
    MaxOffsetMs = $MaxOffsetMs
    MaxOrderServerS = $MaxOrderServerS
}
if ($DryRun) { $forward.DryRun = $true }
if ($NoCarryDailyStop) { $forward.NoCarryDailyStop = $true }
& (Join-Path $here "start_live_v4.ps1") @forward
exit $LASTEXITCODE
