@echo off
chcp 65001 >nul
title LAAP Web Avatar (Full Mode)
cd /d D:\LAAP

echo [1/3] Killing old processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8081 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8766 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1

echo [2/3] Starting LAAP server with Agent...
set PYTHON=C:\Python313\python.exe
if not exist %PYTHON% set PYTHON=python
start /MIN "" "D:\hermes-agent-main (1)\hermes-agent-main\.venv\Scripts\python.exe" -m laap.web.server

echo [3/3] Opening browser...
timeout /t 8 /nobreak >nul
start http://localhost:8081

echo.
echo ========================================
echo   LAAP Full Mode - http://localhost:8081
echo   Agent chat enabled + Emotion sync
echo ========================================
echo.
pause
