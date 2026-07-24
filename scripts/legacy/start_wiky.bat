@echo off
title Wiky 数字生命体
cd /d D:\LAAP
echo ╔══════════════════════════════════════╗
echo ║     Wiky 数字生命体 启动中...       ║
echo ╚══════════════════════════════════════╝
echo.
echo [1/3] 加载PSI意识体...
echo [2/3] 启动量子和成器...
echo [3/3] 启动HTTP API...
echo.
python -u -B wiky_http_api.py 30086
pause
