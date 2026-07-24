@echo off
chcp 65001 >nul
title LAAP
cd /d D:\LAAP
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8081') do taskkill /F /PID %%a >nul 2>&1
start /MIN "" python D:\LAAP\laap_web.py
timeout /t 5 /nobreak >nul
start http://localhost:8081
pause
