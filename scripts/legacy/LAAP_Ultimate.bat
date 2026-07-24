@echo off
chcp 65001 >nul
title LAAP Ultimate
cd /d D:\LAAP

echo ╔══════════════════════════════════════════════════════╗
echo ║     LAAP Digital Lifeform — Ultimate Edition        ║
echo ╠══════════════════════════════════════════════════════╣
echo ║  13 Characters · 15 Motions · 3 TTS Engines        ║
echo ║  FFT LipSync · AI Gestures · Voice Cloning         ║
echo ╚══════════════════════════════════════════════════════╝
echo.

:: Check Docker
docker info >nul 2>&1
if %errorlevel% equ 0 (
    echo [1/3] Starting FishSpeech TTS...
    docker compose up -d fish-speech >nul 2>&1
    timeout /t 3 /nobreak >nul
) else (
    echo [1/3] Docker not running - TTS will use EdgeTTS fallback
)

echo [2/3] Starting LAAP Agent + Web Server...
start "LAAP" /MIN python D:\LAAP\laap_web.py

echo [3/3] Waiting for server...
timeout /t 6 /nobreak >nul
start http://localhost:8081

echo.
echo ✅ LAAP Digital Lifeform is running!
echo.
echo   http://localhost:8081
echo.
echo   Features:
echo   - 13 game characters with personality
echo   - 15 motion presets with AI gestures
echo   - FFT LipSync during TTS
echo   - Voice cloning pipeline
echo   - Character memory system
echo.
echo   Press any key to show control panel...
pause >nul
start LAAP_Launcher.bat
