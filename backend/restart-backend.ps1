# Full Media Platform - Backend Restart Script
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $dir 'stop-backend.ps1')
Start-Sleep -Milliseconds 800
& (Join-Path $dir 'start-backend.ps1')
