# Clock guard: measures the true UTC offset over SNTP and steps the system clock only when it has drifted past
# the danger zone. The live bot's clock gate goes REDUCING above 100 ms and ops\start_live_v4.ps1 refuses above
# 300 ms, but W32Time can sit for hours "synced" while only slewing at ~0.25 ms/s (seen on 16 Nov after a resume),
# so the drift reaches 400 ms before it is fixed. Installed as a scheduled task (SYSTEM, every 1 minute):
#   schtasks /create /tn RosterClockGuard /sc minute /mo 1 /ru SYSTEM /rl HIGHEST /tr "...powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File <this file>" /f
# Remove with:  schtasks /delete /tn RosterClockGuard /f
param(
    [double]$ThresholdMs = 60,   # step only past this; the bot's gate trips above 100 ms and its own SNTP read jitters ~20 ms
    [double]$MaxStepMs = 5000    # refuse anything larger: that is not drift, it is a bad reading or a dead battery
)
$Roster = Split-Path -Parent $PSScriptRoot
$Log = Join-Path $Roster 'data\trader\clock_guard.log'
$Servers = 'time.google.com', 'time.windows.com', 'pool.ntp.org'
$NtpEpoch = 2208988800

function Log($m) { "{0:o}  {1}" -f (Get-Date), $m | Out-File $Log -Append -Encoding utf8 }
function Write-Be32([byte[]]$b, [int]$o, [uint32]$v) {
    $b[$o] = [byte](($v -shr 24) -band 0xFF); $b[$o + 1] = [byte](($v -shr 16) -band 0xFF)
    $b[$o + 2] = [byte](($v -shr 8) -band 0xFF); $b[$o + 3] = [byte]($v -band 0xFF)
}
function Read-Be32([byte[]]$b, [int]$o) {
    ([uint32]$b[$o] -shl 24) -bor ([uint32]$b[$o + 1] -shl 16) -bor ([uint32]$b[$o + 2] -shl 8) -bor [uint32]$b[$o + 3]
}

# One UDP query to server:123. Returns @{offset_ms; delay_ms} or $null when the reply is missing or not to trust.
function Get-SntpSample([string]$Server) {
    $udp = New-Object System.Net.Sockets.UdpClient
    try {
        $udp.Client.ReceiveTimeout = 1500
        $est = New-Object System.Net.IPEndPoint ([System.Net.Dns]::GetHostAddresses($Server) | Where-Object { $_.AddressFamily -eq 'InterNetwork' } | Select-Object -First 1), 123
        $base = ([DateTimeOffset]([DateTime]::UtcNow)).ToUnixTimeMilliseconds() / 1000.0
        $sw = [Diagnostics.Stopwatch]::StartNew()
        $req = New-Object byte[] 48
        $req[0] = 0x23                                  # LI 0, version 4, mode 3 (client)
        $t1 = $base + $sw.Elapsed.TotalSeconds
        $n = $t1 + $NtpEpoch
        Write-Be32 $req 40 ([uint32][math]::Floor($n))
        Write-Be32 $req 44 ([uint32][math]::Floor(($n - [math]::Floor($n)) * 4294967296.0))
        $udp.Send($req, $req.Length, $est) | Out-Null
        $remote = New-Object System.Net.IPEndPoint ([System.Net.IPAddress]::Any), 0
        $resp = $udp.Receive([ref]$remote)
        $t4 = $base + $sw.Elapsed.TotalSeconds
    } catch { return $null } finally { $udp.Close() }
    if ($resp.Length -lt 48) { return $null }
    if (($resp[0] -band 7) -ne 4) { return $null }        # must be a server reply
    if (($resp[0] -shr 6) -eq 3) { return $null }         # server clock unsynchronized
    if ($resp[1] -eq 0) { return $null }                  # Kiss-o'-Death
    for ($i = 24; $i -lt 32; $i++) { if ($resp[$i] -ne $req[$i + 16]) { return $null } }  # must echo our transmit time
    $t2 = (Read-Be32 $resp 32) + (Read-Be32 $resp 36) / 4294967296.0 - $NtpEpoch
    $t3 = (Read-Be32 $resp 40) + (Read-Be32 $resp 44) / 4294967296.0 - $NtpEpoch
    if ($t2 -le 0 -or $t3 -le 0) { return $null }
    [pscustomobject]@{
        offset_ms = (($t2 - $t1) + ($t3 - $t4)) / 2 * 1000
        delay_ms  = (($t4 - $t1) - ($t3 - $t2)) * 1000
    }
}

# best (least-delayed) sample per server, then the median across servers: a Wi-Fi stall on one path cannot move it
$best = foreach ($s in $Servers) {
    $samples = 1..3 | ForEach-Object { Get-SntpSample $s } | Where-Object { $_ }
    if ($samples) { $samples | Sort-Object delay_ms | Select-Object -First 1 }
}
$offsets = @($best | ForEach-Object { [double]$_.offset_ms })
if ($offsets.Count -lt 2) { Log ('no usable NTP reply ({0} of {1} servers)' -f $offsets.Count, $Servers.Count); exit 0 }
$sorted = $offsets | Sort-Object
$offset = if ($sorted.Count % 2) { $sorted[[int](($sorted.Count - 1) / 2)] } else { ($sorted[$sorted.Count / 2 - 1] + $sorted[$sorted.Count / 2]) / 2 }
if (($sorted[-1] - $sorted[0]) -gt 150) { Log ('sources disagree by {0:N0} ms; skipping (offsets {1})' -f ($sorted[-1] - $sorted[0]), (($offsets | ForEach-Object { '{0:N0}' -f $_ }) -join ', ')); exit 0 }
if ([math]::Abs($offset) -lt $ThresholdMs) {           # healthy: W32Time is doing its job, only record the heartbeat
    Log ('ok {0:N0} ms (limit {1:N0})' -f $offset, $ThresholdMs)
    exit 0
}
if ([math]::Abs($offset) -gt $MaxStepMs) { Log ('offset {0:N0} ms is too large to be drift; not stepping' -f $offset); exit 0 }

try {
    Set-Date -Adjust ([TimeSpan]::FromMilliseconds([math]::Round($offset))) -ErrorAction Stop
    Log ('stepped {0:N0} ms (sources {1}; delay {2:N0} ms)' -f $offset, (($offsets | ForEach-Object { '{0:N0}' -f $_ }) -join ', '), (($best | Measure-Object delay_ms -Minimum).Minimum))
} catch {
    Log ('step of {0:N0} ms failed: {1}' -f $offset, $_.Exception.Message)
}

# keep the log small: the last 2000 lines are plenty for a post-mortem
$lines = @(Get-Content $Log -ErrorAction SilentlyContinue)
if ($lines.Count -gt 2000) { $lines[-2000..-1] | Out-File $Log -Encoding utf8 }
