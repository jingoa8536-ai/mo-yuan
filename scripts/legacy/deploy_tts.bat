@echo off
chcp 65001 >nul
title LAAP TTS Engine Deployer
cd /d D:\LAAP

echo ========================================
echo   Deploy TTS Engines
echo ========================================
echo.
echo  [1] FishSpeech  (CPU, 4GB, stable)
echo  [2] CosyVoice   (GPU, 8GB, best quality)
echo  [3] GPT-SoVITS  (GPU, 4GB, voice clone)
echo  [4] ALL engines
echo  [5] Stop all
echo.

set /p choice="Select (1-5): "

if "%choice%"=="1" docker compose up -d fish-speech
if "%choice%"=="2" docker compose up -d cosyvoice
if "%choice%"=="3" docker compose up -d gptsovits
if "%choice%"=="4" docker compose up -d
if "%choice%"=="5" docker compose down

echo.
if "%choice%"=="5" (
    echo All engines stopped.
) else (
    echo Waiting for startup...
    timeout /t 5 /nobreak >nul
    docker compose ps
)
pause
