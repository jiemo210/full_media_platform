# Full Media Platform - Backend Start Script
# Usage: powershell -ExecutionPolicy Bypass -File .\start-backend.ps1
$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $dir
$port = 8012
$python = Join-Path $dir '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    $python = (Get-Command python -ErrorAction SilentlyContinue).Source
}
if (-not $python) { Write-Host '[ERROR] Python not found. Please create backend/.venv first.'; exit 1 }

# 1) Port check: responding service means already running
$ownerPid = $null
$line = netstat -ano | Select-String -Pattern "TCP\s+127\.0\.0\.1:$port\s.*LISTENING" | Select-Object -First 1
if ($line) {
    $parts = ($line.ToString() -split '\s+') | Where-Object { $_ }
    if ($parts.Count -ge 5) { $ownerPid = [int]$parts[4] }
}
if ($ownerPid) {
    $responds = $false
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/" -TimeoutSec 3 -UseBasicParsing
        if ($r.StatusCode -eq 200) { $responds = $true }
    } catch {}
    if ($responds) {
        Write-Host "[OK] Backend already running (PID $ownerPid): http://127.0.0.1:$port"
        exit 0
    }
    Write-Host "[WARN] Port $port occupied but service not responding (zombie). Stopping PID $ownerPid..."
    Stop-Process -Id $ownerPid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 800
}

# 2) Launch hidden, redirect output to log files
$outLog = Join-Path $dir 'server_8012.out.log'
$errLog = Join-Path $dir 'server_8012.err.log'
$p = $null
try {
    $p = Start-Process -FilePath $python -ArgumentList @('-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', "$port") `
        -WorkingDirectory $dir -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru
} catch {
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $python
    $psi.Arguments = '-m uvicorn main:app --host 127.0.0.1 --port ' + $port
    $psi.WorkingDirectory = $dir
    $psi.UseShellExecute = $true
    $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $p = [System.Diagnostics.Process]::Start($psi)
    Write-Host '[INFO] Compatibility launch mode (logs go to backend/logs/app.log only).'
}
if (-not $p) { Write-Host '[ERROR] Failed to start process.'; exit 1 }
$p.Id | Set-Content -Path (Join-Path $dir '.server.pid') -Encoding ascii
Write-Host "Backend process started (PID $($p.Id)). Waiting for readiness..."

# 3) Wait for readiness
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 1000
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/" -TimeoutSec 2 -UseBasicParsing
        if ($r.StatusCode -eq 200) {
            Write-Host "[OK] Backend ready: http://127.0.0.1:$port (logs: backend/logs/app.log)"
            exit 0
        }
    } catch {}
}
Write-Host "[ERROR] Startup timeout. Check $errLog"
exit 1
