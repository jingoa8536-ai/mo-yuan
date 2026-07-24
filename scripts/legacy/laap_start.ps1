# LAAP Digital Lifeform Launcher (PowerShell)
Write-Host "LAAP Digital Lifeform" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# Kill old processes
Get-Process -Name "python*" -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -eq "" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 1

# Start server
$python = "C:\Python313\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

Write-Host "Starting LAAP Server..." -ForegroundColor Yellow
$job = Start-Process -FilePath $python -ArgumentList "D:\LAAP\laap_web.py" -WindowStyle Hidden -PassThru

Start-Sleep 5

# Open browser
Start-Process "http://localhost:8081"

Write-Host ""
Write-Host "LAAP Running at http://localhost:8081" -ForegroundColor Green
Write-Host "13 Characters | 15 Motions | Voice TTS" -ForegroundColor Green
Write-Host ""
Write-Host "Press any key to stop server..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
Stop-Process -Id $job.Id -ErrorAction SilentlyContinue
