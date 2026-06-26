#Requires -Version 5.1
<#
.SYNOPSIS
  make app equivalent on Windows — doctor check + start portal.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Venv = Join-Path $Root ".venv-china-quant"
$Python = Join-Path $Venv "Scripts\python.exe"
$Log = Join-Path $Root "data\gateway\app-start.log"

New-Item -ItemType Directory -Force -Path (Join-Path $Root "data\gateway") | Out-Null

function Log($msg) {
    $line = "$(Get-Date -Format o) $msg"
    Write-Host $line
    Add-Content -Path $Log -Value $line
}

Log "=== QuantOS CN app start ==="

if (-not (Test-Path $Python)) {
    Log "FAIL: venv missing — run scripts\bootstrap.ps1"
    exit 1
}

Log "Step: editable install"
& $Python -m pip install -e $Root -q

Log "Step: import gateway"
Push-Location $env:TEMP
& $Python -c "import gateway; print('import ok', gateway.__version__)"
Pop-Location

Log "Step: doctor"
& $Python -c "import gateway, quant; print('gateway', gateway.__version__)"

Log "Step: start portal"
& (Join-Path $Root "scripts\start-portal.ps1")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$HostAddr = "127.0.0.1"
$Port = 8787
for ($i = 1; $i -le 10; $i++) {
    try {
        Invoke-WebRequest -Uri "http://${HostAddr}:${Port}/ready" -UseBasicParsing -TimeoutSec 2 | Out-Null
        Log "READY ok"
        break
    } catch {
        Start-Sleep -Seconds 1
    }
}

Log "Portal: http://${HostAddr}:${Port}/portal"
Log "Docs:   http://${HostAddr}:${Port}/docs"
Log "APP_START PASS"
