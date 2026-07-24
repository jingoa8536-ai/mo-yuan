@echo off
title Aris Fusion Engine v14
cd /d D:\LAAPris_brain
echo Starting Aris Fusion v14...
start /MIN "" "C:\Python313\python.exe" "D:\LAAPris_brainris_fusion_v14.py"
timeout /t 6 /nobreak >nul
echo Engine started on :11522
echo Model: aris-fusion-v14
echo Zero LLM  |  Pure NumPy  |  7 Engines Fused
echo.
