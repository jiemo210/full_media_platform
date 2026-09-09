# Full Media Platform - Backend Stop Script
# Note: run as Administrator if the backend was started elevated
$ErrorActionPreference = 'SilentlyContinue'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$port = 8012
$pidFile = Join-Path $dir '.server.pid'
$stopped = $false

if (Test-Path $pidFile) {
    $oldPid = (Get-Content $pidFile -Raw).Trim()
    if ($oldPid -match '^\d+$') {
        $proc = Get-Process -Id ([int]$oldPid) -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id ([int]$oldPid) -Force -ErrorAction SilentlyContinue
            $stopped = $true
            Write-Host "Stopped recorded backend process $oldPid"
        }
    }
}

$lines = netstat -ano | Select-String -Pattern "TCP\s+127\.0\.0\.1:$port\s.*LISTENING"
foreach ($ln in $lines) {
    $parts = ($ln.ToString() -split '\s+') | Where-Object { $_ }
    if ($parts.Count -lt 5) { continue }
    $ownerPid = [int]$parts[4]
    Write-Host "Stopping process $ownerPid which holds port $port ..."
    Stop-Process -Id $ownerPid -Force -ErrorAction SilentlyContinue
    $stopped = $true
}

if (Test-Path $pidFile) { Remove-Item $pidFile -Force }
if ($stopped) {
    Write-Host "[OK] Backend stopped, port $port released."
} else {
    Write-Host 'Backend is not running.'
}
