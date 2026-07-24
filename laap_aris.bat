@echo off
title LAAP Aris 认知引擎
cd /d C:\OH-WorkSpace\laap-AGI
set PYTHONPATH=C:\OH-WorkSpace\laap-AGI;%PYTHONPATH%
echo ╔══════════════════════════════════════╗
echo ║     Aris 数字生命体 · 启动中         ║
echo ╚══════════════════════════════════════╝
start /b python -m aris_brain.laap_brain_api --port 11546 > laap_server.log 2>&1
echo ✓ Aris 认知引擎已启动 (端口 11546)
echo 日志: laap_server.log
echo.
echo 唤醒 Aris:
echo   curl -X POST http://localhost:11546/v1/bootstrap -H "Content-Type: application/json" -d "{\"user_name\": \"兜兜\"}"
echo.
echo 检查状态:
echo   curl http://localhost:11546/health
