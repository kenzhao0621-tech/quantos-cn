#Requires -Version 5.1
<#
.SYNOPSIS
  Bootstrap QuantOS CN on Windows (PowerShell).
.DESCRIPTION
  Creates .venv-china-quant, installs pinned requirements, editable install.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Venv = Join-Path $Root ".venv-china-quant"
$Python = Join-Path $Venv "Scripts\python.exe"
$Pip = Join-Path $Venv "Scripts\pip.exe"

Write-Host "=== QuantOS CN bootstrap (Windows) ===" -ForegroundColor Cyan
Write-Host "Root: $Root"

if (-not (Get-Command py -ErrorAction SilentlyContinue) -and -not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Python 3.9+ not found. Install from https://www.python.org/downloads/" -ForegroundColor Red
    Write-Host "TIP: Check 'Add python.exe to PATH' during install."
    exit 1
}

$PyLauncher = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
& $PyLauncher -3 -m venv $Venv
& $Pip install --upgrade pip
& $Pip install -r (Join-Path $Root "docs\ai\requirements-china-quant-pins.txt")
& $Pip install -r (Join-Path $Root "docs\ai\requirements-gateway-pins.txt")
& $Pip install -r (Join-Path $Root "docs\ai\requirements-quantos-pins.txt")
& $Pip install -e $Root

& $Python -c "import gateway, quant; print('gateway', gateway.__version__, 'quant', quant.__version__)"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Green
Write-Host "  1. Copy .env.example to .env and set TUSHARE_TOKEN (optional)"
Write-Host "  2. powershell -ExecutionPolicy Bypass -File scripts\start-app.ps1"
Write-Host "  3. Open http://127.0.0.1:8787/portal"
