@echo off
chcp 65001 >nul
title LAAP Control Panel
cd /d D:\LAAP

echo ========================================
echo   LAAP Control Panel
echo ========================================
echo.
echo  [1] Start LAAP (DeepSeek)
echo  [2] Start Hermes Engine
echo  [3] Start FishSpeech TTS (Docker)
echo  [4] Start ALL (LAAP + TTS)
echo  [5] Open Browser
echo  [6] Stop All
echo  [7] Debug Bones
echo  [0] Exit
echo.

set /p choice="Select (0-7): "

if "%choice%"=="1" (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8081') do taskkill /F /PID %%a >nul 2>&1
    start /MIN "" python D:\LAAP\laap_web.py
    timeout /t 5 /nobreak >nul
    start http://localhost:8081
    echo LAAP started. Close window to stop.
    pause
)
if "%choice%"=="2" (
    echo LAAP_ENGINE=hermes
    set LAAP_ENGINE=hermes
    start /MIN "" python D:\LAAP\laap_web.py
    timeout /t 5 /nobreak >nul
    start http://localhost:8081
    pause
)
if "%choice%"=="3" (
    docker compose up -d fish-speech
    timeout /t 5 /nobreak >nul
    echo FishSpeech on :9991
    pause
)
if "%choice%"=="4" (
    docker compose up -d fish-speech >nul 2>&1
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8081') do taskkill /F /PID %%a >nul 2>&1
    start /MIN "" python D:\LAAP\laap_web.py
    timeout /t 6 /nobreak >nul
    start http://localhost:8081
    pause
)
if "%choice%"=="5" start http://localhost:8081
if "%choice%"=="6" (
    docker compose down >nul 2>&1
    taskkill /F /IM python.exe /FI "CPUTIME gt 00:00:05" >nul 2>&1
    echo All stopped.
    pause
)
if "%choice%"=="7" start http://localhost:8081/debug_bones.html
if "%choice%"=="0" exit /b
