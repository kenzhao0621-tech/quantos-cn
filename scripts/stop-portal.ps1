#Requires -Version 5.1
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PidFile = Join-Path $Root "data\gateway\portal.pid"
if (Test-Path $PidFile) {
    $pid = Get-Content $PidFile -Raw
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    Remove-Item $PidFile -Force
    Write-Host "Stopped portal PID $pid"
} else {
    Write-Host "No portal.pid found"
}
