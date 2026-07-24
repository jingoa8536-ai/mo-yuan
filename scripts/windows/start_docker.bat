@echo off
chcp 65001 >nul
title LAAP Docker
cd /d D:\LAAP
docker info >nul 2>&1
if %errorlevel% neq 0 (
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo Waiting for Docker...
    :wait
    timeout /t 5 /nobreak >nul
    docker info >nul 2>&1
    if %errorlevel% neq 0 goto wait
)
docker compose up -d fish-speech
timeout /t 8 /nobreak >nul
echo FishSpeech on :9991
pause
