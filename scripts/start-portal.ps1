#Requires -Version 5.1
<#
.SYNOPSIS
  Start QuantOS CN Gateway + portal on Windows.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Venv = Join-Path $Root ".venv-china-quant"
$Python = Join-Path $Venv "Scripts\python.exe"
$HostAddr = "127.0.0.1"
$Port = 8787
$PidFile = Join-Path $Root "data\gateway\portal.pid"
$LogFile = Join-Path $Root "data\gateway\portal.log"

New-Item -ItemType Directory -Force -Path (Join-Path $Root "data\gateway") | Out-Null

if (-not (Test-Path $Python)) {
    Write-Host "ERROR: venv missing. Run: powershell -File scripts\bootstrap.ps1" -ForegroundColor Red
    exit 1
}

& $Python -m pip install -e $Root -q 2>$null

if (Test-Path $PidFile) {
    $OldPid = Get-Content $PidFile -Raw
    $proc = Get-Process -Id $OldPid -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Host "Portal already running (PID $OldPid) — http://${HostAddr}:${Port}/portal"
        exit 0
    }
    Remove-Item $PidFile -Force
}

try {
    $health = Invoke-WebRequest -Uri "http://${HostAddr}:${Port}/health" -UseBasicParsing -TimeoutSec 2
    if ($health.StatusCode -eq 200) {
        Write-Host "Portal already running on port $Port — http://${HostAddr}:${Port}/portal"
        exit 0
    }
} catch {}

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    Write-Host "ERROR: port $Port already in use" -ForegroundColor Red
    exit 1
}

$proc = Start-Process -FilePath $Python -ArgumentList @(
    "-m", "uvicorn", "gateway.api.app:app",
    "--app-dir", $Root,
    "--host", $HostAddr,
    "--port", $Port
) -WorkingDirectory $Root -RedirectStandardOutput $LogFile -RedirectStandardError $LogFile -PassThru -WindowStyle Hidden

$proc.Id | Set-Content $PidFile
Start-Sleep -Seconds 3

try {
    $ready = Invoke-WebRequest -Uri "http://${HostAddr}:${Port}/health" -UseBasicParsing -TimeoutSec 5
    if ($ready.StatusCode -eq 200) {
        Write-Host "Portal started PID $($proc.Id) — http://${HostAddr}:${Port}/portal"
        Write-Host "Log: $LogFile"
        Start-Process "http://${HostAddr}:${Port}/portal"
        exit 0
    }
} catch {}

Write-Host "ERROR: health check failed. Log tail:" -ForegroundColor Red
Get-Content $LogFile -Tail 20 -ErrorAction SilentlyContinue
exit 1
