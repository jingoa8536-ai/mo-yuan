@echo off
chcp 65001 >nul
title LAAP Voice Clone - GPT-SoVITS
cd /d D:\LAAP

echo ========================================
echo   GPT-SoVITS Voice Clone Deployment
echo ========================================
echo.

:: Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] Docker is not running!
    echo Starting Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo Waiting for Docker to start...
    timeout /t 20 /nobreak >nul
)

echo [1/3] Checking GPT-SoVITS image...
docker image inspect sn00pypanda/gpt-sovits:latest >nul 2>&1
if %errorlevel% neq 0 (
    echo Downloading GPT-SoVITS (~8GB, may take 30min)...
    docker pull sn00pypanda/gpt-sovits:latest
) else (
    echo Image already downloaded
)

echo [2/3] Creating voice directories...
if not exist voices mkdir voices
if not exist gptsovits_output mkdir gptsovits_output

echo [3/3] Starting GPT-SoVITS server...
docker compose up -d gptsovits

echo.
echo Waiting for server to start...
timeout /t 10 /nobreak >nul

:: Test if it's running
curl -s http://127.0.0.1:9880/status >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ GPT-SoVITS is running on http://127.0.0.1:9880
) else (
    echo ⚠️ Server may still be starting. Check with: docker compose logs gptsovits
)

echo.
echo ========================================
echo   Voice Clone Ready!
echo   API: http://127.0.0.1:9880
echo.
echo   Usage:
echo   1. Put WAV voice samples in D:\LAAP\voices\
echo   2. Create transcript.txt with text of the audio
echo   3. Our LAAP system will auto-clone and use the voice
echo ========================================
pause
