# Start RemoteCoder Standalone Autonomous Coding Server (Port 8080)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

# Locate Python with required packages dynamically
$python = ""
$localVenv = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path $localVenv) {
    $python = $localVenv
} else {
    # Check if system python has required packages
    $sysPy = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    if ($sysPy) {
        & $sysPy -c "import fastapi, uvicorn" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $python = $sysPy
        }
    }
    # Check parent directories for any available virtualenv
    if (-not $python) {
        $parent = Split-Path -Parent $root
        $candidate = (Get-ChildItem $parent -Recurse -Depth 3 -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq "python.exe" -and $_.FullName -like "*venv*" } | Select-Object -First 1).FullName
        if ($candidate) {
            $python = $candidate
        }
    }
}
if (-not $python) { $python = "python" }

# Check if port 8080 is occupied
$occupied = Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue
if ($occupied) {
    Write-Host "[WARNING] Port 8080 is in use. Stopping previous instance..." -ForegroundColor Yellow
    Stop-Process -Id $occupied.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

# Find local LAN IP
$lanIp = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127*" -and $_.IPAddress -notlike "169.254*" } | Select-Object -First 1).IPAddress

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host " RemoteCoder Standalone Coding Engine (Port 8080)" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "[Local PC]    : http://localhost:8080" -ForegroundColor Green
if ($lanIp) {
    Write-Host "[Phone / LAN] : http://$($lanIp):8080 (Plain HTTP, Zero Cert Warnings)" -ForegroundColor Yellow
}
Write-Host "Using Python : $python" -ForegroundColor Gray
Write-Host "Starting server in background..." -ForegroundColor Gray

$logFile = Join-Path $root "outputs\server.log"
$errFile = Join-Path $root "outputs\server_err.log"
if (Test-Path $logFile) { Remove-Item $logFile -Force -ErrorAction SilentlyContinue }
if (Test-Path $errFile) { Remove-Item $errFile -Force -ErrorAction SilentlyContinue }

$pyw = $python -replace "python\.exe$", "pythonw.exe"
if (-not (Test-Path $pyw)) { $pyw = $python }

$cmd = "`"$pyw`" -m app.server"
$res = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = $cmd
    CurrentDirectory = $root
}

$checkScript = Join-Path $root "scripts\check_health.py"
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 400
    & $python $checkScript 2>$null
    if ($LASTEXITCODE -eq 0) {
        $ready = $true
        break
    }
}

if ($ready) {
    Write-Host ""
    Write-Host "[OK] RemoteCoder server is ready in background!" -ForegroundColor Green
    Write-Host "Open in browser: http://localhost:8080 or phone: http://$($lanIp):8080" -ForegroundColor Cyan
} else {
    Write-Host "[ERROR] Server startup timed out. Log output:" -ForegroundColor Red
    if (Test-Path $logFile) {
        Get-Content $logFile -Tail 20
    }
}
