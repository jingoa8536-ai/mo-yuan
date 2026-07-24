@echo off
title Aris Fusion Engine v13
cd /d D:\LAAP\aris_brain
echo ========================================
echo   Aris Fusion Engine v13 — 启动
echo ========================================
echo.
echo  融合引擎: V7语义 + 矩阵知识 + 量子PSI
echo           + 量子解码 + QFusion + Markov
echo.
echo [1/2] 启动引擎...
start /MIN "" "C:\Python313\python.exe" "D:\LAAP\aris_brain\aris_fusion_v13.py"
echo [2/2] 等待就绪...
timeout /t 5 /nobreak >nul
echo.
echo  服务: http://127.0.0.1:11522
echo  模型: aris-fusion-v13
echo  状态: 零LLM | 零GPU | 无限上下文
echo.
echo  按任意键查看状态...
pause >nul
curl -s http://127.0.0.1:11522/health
echo.
pause
