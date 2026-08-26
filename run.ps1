# ContentForge - Windows dev server
#   .\run.ps1            start on http://localhost:8000 with autoreload
#   .\run.ps1 -Lan       also reachable from your phone on the same Wi-Fi
#   .\run.ps1 -Seed      reset the demo catalogue first, then start
param(
    [switch]$Lan,
    [switch]$Seed,
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot "venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "Creating venv..." -ForegroundColor Cyan
    py -3 -m venv venv
    & $python -m pip install --upgrade pip -q
    & $python -m pip install -r requirements.txt
}

if ($Seed) {
    & $python scripts\seed_demo.py
}

$listen = if ($Lan) { "0.0.0.0" } else { "127.0.0.1" }

if ($Lan) {
    # The adapter holding the default route - not a WSL/Hyper-V virtual one.
    $cfg = Get-NetIPConfiguration |
           Where-Object { $null -ne $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq "Up" } |
           Select-Object -First 1
    $ip = $cfg.IPv4Address.IPAddress
    Write-Host "On $($cfg.InterfaceAlias), open http://${ip}:$Port on your phone" -ForegroundColor Green
    Write-Host "(Windows Firewall will ask to allow Python the first time.)" -ForegroundColor DarkGray
}

Write-Host "ContentForge -> http://localhost:$Port  (admin@ais-tech.com / admin123)" -ForegroundColor Green
& $python -m uvicorn app.main:app --host $listen --port $Port --reload
