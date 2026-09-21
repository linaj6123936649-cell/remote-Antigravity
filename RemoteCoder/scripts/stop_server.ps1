# Stop RemoteCoder Server (Port 8080)
$occupied = Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue
if ($occupied) {
    Stop-Process -Id $occupied.OwningProcess -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] RemoteCoder server (Port 8080) stopped." -ForegroundColor Green
} else {
    Write-Host "[INFO] No server running on port 8080." -ForegroundColor Gray
}
