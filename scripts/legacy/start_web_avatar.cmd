@echo off
title LAAP Web Avatar Server
cd /d D:\LAAP

echo [LAAP] 正在清理旧进程...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8766') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8080') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo [LAAP] 启动 Web Avatar Server...
echo.
python -m laap.web.avatar_server
pause
