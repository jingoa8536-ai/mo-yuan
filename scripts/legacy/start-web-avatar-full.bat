@echo off
chcp 65001 >nul
title LAAP Web Avatar (Full)
cd /d D:\LAAP

echo ========================================
echo   LAAP Virtual Character Engine - Web
echo   Full mode (with Agent)
echo ========================================
echo.

set PYTHON=C:\Python313\python.exe
if not exist %PYTHON% ( set PYTHON=python )

echo Killing old processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8081 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8766 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1

echo Starting server with Agent...
start "LAAP Server" /B /MIN %PYTHON% -m laap.web.avatar_server
timeout /t 5 /nobreak >nul

start http://localhost:8081

echo.
echo LAAP Full Mode running at http://localhost:8081
echo Close this window to stop.
pause
