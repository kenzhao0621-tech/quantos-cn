# MiniQMT / xtquant Windows installer helper (run inside Windows VM or PC)
# Usage: powershell -ExecutionPolicy Bypass -File scripts/install_miniqmt_windows.ps1

$ErrorActionPreference = "Stop"

Write-Host "== QuantOS MiniQMT Windows Setup ==" -ForegroundColor Cyan

$paths = @(
    "$env:USERPROFILE\国金证券QMT交易端\userdata_mini",
    "$env:USERPROFILE\迅投QMT交易端\userdata_mini",
    "C:\国金证券QMT交易端\userdata_mini",
    "C:\迅投QMT交易端\userdata_mini"
)

$found = $null
foreach ($p in $paths) {
    if (Test-Path $p) {
        $found = $p
        break
    }
}

if (-not $found) {
    Write-Host "未检测到 MiniQMT 安装。请先从开户券商下载 QMT 客户端：" -ForegroundColor Yellow
    Write-Host "  https://www.myquant.cn/"
    Write-Host "  或券商官方渠道（国金/华泰/中信等）"
    Write-Host ""
    Write-Host "安装后："
    Write-Host "  1. 勾选「极简模式/独立交易」登录"
    Write-Host "  2. QMT → 设置 → 模型设置 → 下载 Python 库"
    Write-Host "  3. 设置环境变量 MINIQMT_PATH=$found"
    exit 1
}

Write-Host "检测到 MiniQMT 路径: $found" -ForegroundColor Green

$xtPaths = @(
    (Join-Path (Split-Path $found -Parent) "bin.x64\Lib\site-packages\xtquant"),
    (Join-Path (Split-Path $found -Parent) "xtquant")
)

$xtDir = $null
foreach ($xp in $xtPaths) {
    if (Test-Path $xp) { $xtDir = $xp; break }
}

if ($xtDir) {
    Write-Host "xtquant 目录: $xtDir"
    pip install xtquant 2>$null
    Write-Host "建议: 将 xtquant 复制到 Python site-packages 或设置 PYTHONPATH=$xtDir"
} else {
    Write-Host "未找到 xtquant，请在 QMT 内下载 Python 库" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "环境变量（写入 .env 或系统环境）："
Write-Host "  MINIQMT_PATH=$found"
Write-Host "  XTQUANT_ACCOUNT_ID=<你的资金账号>"
Write-Host "  XTQUANT_SESSION_ID=1"

# Quick connect test
$py = @"
import os, sys
sys.path.insert(0, r'$xtDir') if r'$xtDir' else None
os.environ['MINIQMT_PATH'] = r'$found'
try:
    from xtquant.xttrader import XtQuantTrader
    print('xttrader import OK')
    t = XtQuantTrader(r'$found', 1)
    t.start()
    rc = t.connect()
    print('connect rc=', rc, '(0=成功, 需 MiniQMT 已登录)')
except Exception as e:
    print('connect test:', e)
"@

python -c $py
