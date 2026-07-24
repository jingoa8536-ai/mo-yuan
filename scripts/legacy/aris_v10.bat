@echo off
title Aris V10 — 量子认知运行时
cd /d D:\LAAP
echo ============================================
echo   Aris V10 — 量子和成 + QVoice
echo   F-route(融合) ^| Q-route ^| T-route ^| L-route
echo   独立处理率目标: ^>90%%
echo ============================================
echo.
python "C:\Users\user\AppData\Local\hermes\skills\software-development\aris-v10-runtime\scripts\aris_v10.py" %*
if errorlevel 1 (
    echo.
    echo 按任意键退出...
    pause >nul
)
