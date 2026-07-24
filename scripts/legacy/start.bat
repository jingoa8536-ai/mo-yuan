@echo off
chcp 65001 >nul
title LAAP Web Avatar
cd /d D:\LAAP

echo ========================================
echo   LAAP Digital Lifeform
echo ========================================
echo.

:: Find Python
set PYTHON=C:\Python313\python.exe
if not exist %PYTHON% set PYTHON=python

:: Kill old
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8081 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8766 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1

:: Start
echo Starting LAAP Server...
start /MIN "" %PYTHON% D:\LAAP\laap_web.py
timeout /t 6 /nobreak >nul
start http://localhost:8081

echo.
echo ========================================
echo   LAAP Running at http://localhost:8081
echo   13 Characters | 15 Motions | Voice
echo ========================================
echo.
pause
