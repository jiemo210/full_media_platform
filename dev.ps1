# ============================================================
# Full Media Platform - One-click Frontend+Backend Manager
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\dev.ps1 start    (default)
#   powershell -ExecutionPolicy Bypass -File .\dev.ps1 stop
#   powershell -ExecutionPolicy Bypass -File .\dev.ps1 restart
#   powershell -ExecutionPolicy Bypass -File .\dev.ps1 status
# ============================================================
param([string]$action = 'start')

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root 'backend'
$frontendDir = Join-Path $root 'frontend'
$logDir = Join-Path $root 'logs'
$bp = 8012
$fp = 5174

if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

# ---------- helpers ----------
function Get-PortPid([int]$port) {
    foreach ($raw in (netstat -ano)) {
        $t = ($raw.Trim() -split '\s+')
        if ($t.Count -lt 5) { continue }
        if ($t[1] -notmatch ("^.*:" + $port + "$")) { continue }
        if ($t[$t.Count - 2] -ne 'LISTENING') { continue }
        return [int]$t[$t.Count - 1]
    }
    return $null
}

function Test-PortHttp([int]$port, [int]$timeoutSec = 2) {
    foreach ($hostName in @('127.0.0.1', 'localhost')) {
        try {
            $r = Invoke-WebRequest -Uri ("http://" + $hostName + ":" + $port + "/") -TimeoutSec $timeoutSec -UseBasicParsing
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { return $true }
        } catch {}
    }
    return $false
}

function Start-HiddenExe([string]$exe, [string[]]$argList, [string]$cwd, [string]$outLog, [string]$errLog) {
    $proc = $null
    try {
        $proc = Start-Process -FilePath $exe -ArgumentList $argList -WorkingDirectory $cwd -WindowStyle Hidden `
            -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru
    } catch {
        $psi = [System.Diagnostics.ProcessStartInfo]::new()
        $psi.FileName = $exe
        $psi.Arguments = ($argList -join ' ')
        $psi.WorkingDirectory = $cwd
        $psi.UseShellExecute = $true
        $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
        $proc = [System.Diagnostics.Process]::Start($psi)
    }
    return $proc
}

function Get-BackendPidFile() { return Join-Path $backendDir '.server.pid' }
function Get-FrontendPidFile() { return Join-Path $root '.vite.pid' }

function Wait-Ready([int]$port, [string]$name, [int]$maxSec = 30) {
    for ($i = 0; $i -lt $maxSec; $i++) {
        Start-Sleep -Milliseconds 1000
        if (Test-PortHttp $port) {
            Write-Host "[OK] $name ready: http://127.0.0.1:$port"
            return $true
        }
    }
    Write-Host "[WARN] $name not ready within ${maxSec}s: http://127.0.0.1:$port"
    return $false
}

function Start-Backend() {
    $owner = Get-PortPid $bp
    if ($owner -and (Test-PortHttp $bp)) {
        Write-Host "[OK] Backend already running on port $bp (PID $owner)"
        return
    }
    if ($owner) {
        Write-Host "[WARN] Port $bp occupied but not responding (zombie). Stopping PID $owner..."
        Stop-Process -Id $owner -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 800
    }
    $python = Join-Path $backendDir '.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) { $python = (Get-Command python -ErrorAction SilentlyContinue).Source }
    if (-not $python) { Write-Host '[ERROR] Python not found'; return $false }
    $out = Join-Path $logDir 'backend.out.log'
    $err = Join-Path $logDir 'backend.err.log'
    $p = Start-HiddenExe $python @('-m','uvicorn','main:app','--host','127.0.0.1','--port',"$bp") $backendDir $out $err
    if (-not $p) { Write-Host '[ERROR] Backend launch failed'; return $false }
    $p.Id | Set-Content -Path (Get-BackendPidFile) -Encoding ascii
    Write-Host "Backend starting (PID $($p.Id))..."
    return (Wait-Ready $bp 'Backend')
}

function Start-Frontend() {
    $owner = Get-PortPid $fp
    if ($owner -and (Test-PortHttp $fp)) {
        Write-Host "[OK] Frontend already running on port $fp (PID $owner)"
        return
    }
    if ($owner) {
        Write-Host "[WARN] Port $fp occupied but not responding (zombie). Stopping PID $owner..."
        Stop-Process -Id $owner -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 800
    }
    $npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
    if (-not $npm) { $npm = (Get-Command npm -ErrorAction SilentlyContinue).Source }
    if (-not $npm) { Write-Host '[ERROR] npm not found (install Node.js first)'; return $false }
    $out = Join-Path $logDir 'frontend.out.log'
    $err = Join-Path $logDir 'frontend.err.log'
    $p = Start-HiddenExe $npm @('run','dev','--','--host','127.0.0.1','--port',"$fp") $frontendDir $out $err
    if (-not $p) { Write-Host '[ERROR] Frontend launch failed'; return $false }
    $p.Id | Set-Content -Path (Get-FrontendPidFile) -Encoding ascii
    Write-Host "Frontend starting (PID $($p.Id))..."
    return (Wait-Ready $fp 'Frontend' 60)
}

function Stop-Service([int]$port, [string]$pidFile, [string]$name) {
    $stopped = $false
    if (Test-Path $pidFile) {
        $oldPid = (Get-Content $pidFile -Raw).Trim()
        if ($oldPid -match '^\d+$') {
            if (Get-Process -Id ([int]$oldPid) -ErrorAction SilentlyContinue) {
                Stop-Process -Id ([int]$oldPid) -Force -ErrorAction SilentlyContinue
                Write-Host "Stopped $name process $oldPid"
                $stopped = $true
            }
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
    $owner = Get-PortPid $port
    if ($owner) {
        # One-click stop: terminate whatever owns this project's dev port.
        Stop-Process -Id $owner -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped $name port owner PID $owner"
        $stopped = $true
    }
    return $stopped
}

# ---------- actions ----------
switch ($action.ToLower()) {
    'start' {
        Write-Host '===== Starting Full Media Platform ====='
        $okB = Start-Backend
        $okF = Start-Frontend
        Write-Host ''
        Write-Host "Backend : http://127.0.0.1:$bp  (docs: http://127.0.0.1:$bp/docs)"
        Write-Host "Frontend: http://127.0.0.1:$fp"
        if ($okB -and $okF) { Write-Host '[OK] Both services are running. Logs: logs\*.log' }
    }
    'stop' {
        Write-Host '===== Stopping Full Media Platform ====='
        $b = Stop-Service $bp (Get-BackendPidFile) 'Backend'
        $f = Stop-Service $fp (Get-FrontendPidFile) 'Frontend'
        if (-not $b -and -not $f) { Write-Host 'Nothing was running.' }
        else { Write-Host '[OK] Stopped.' }
    }
    'restart' {
        Write-Host '===== Restarting Full Media Platform ====='
        Stop-Service $bp (Get-BackendPidFile) 'Backend' | Out-Null
        Stop-Service $fp (Get-FrontendPidFile) 'Frontend' | Out-Null
        Start-Sleep -Milliseconds 1000
        Start-Backend | Out-Null
        Start-Frontend | Out-Null
        Write-Host 'Restart done.'
    }
    'status' {
        $bpOwner = Get-PortPid $bp
        $fpOwner = Get-PortPid $fp
        $bState = if ($bpOwner) { "LISTENING (PID $bpOwner)" } else { 'not running' }
        $fState = if ($fpOwner) { "LISTENING (PID $fpOwner)" } else { 'not running' }
        $bHttp = if (Test-PortHttp $bp) { '200 OK' } else { 'unreachable' }
        $fHttp = if (Test-PortHttp $fp) { '200 OK' } else { 'unreachable' }
        Write-Host "Backend  port $bp : $bState"
        Write-Host "Frontend port $fp : $fState"
        Write-Host "Backend  http: $bHttp"
        Write-Host "Frontend http: $fHttp"
    }
    default {
        Write-Host 'Usage:  .\dev.ps1 [start|stop|restart|status]'
    }
}
