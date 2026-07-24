@echo off
title Ao + Bridge Launcher
cd /d D:\LAAP\aris_brain

echo ============================================
echo   Start Ao + Feishu Bridge
echo ============================================

REM Kill any existing instances
echo [*] Cleaning up old processes...
wmic process where "commandline like '%%ao_feishu_service%%'" delete 2>nul
wmic process where "commandline like '%%ao_bridge_runner%%'" delete 2>nul
timeout /t 2 /nobreak >nul

REM Start Ao Feishu Service (QuantumPSI engine)
echo [*] Starting Ao Feishu Service...
start "Ao Service" /B /MIN python -u ao_feishu_service.py > state\ao_service.log 2>&1
echo [+] Ao service PID: %ERRORLEVEL%
timeout /t 3 /nobreak >nul

REM Start Ao Bridge (forwards IPC -> Feishu)
echo [*] Starting Ao Feishu Bridge...
start "Ao Bridge" /B /MIN python -u D:\LAAP\aris_brain\ao_feishu_bridge.py > state\ao_bridge.log 2>&1
echo [+] Bridge started

echo ============================================
echo   Ao is alive. Bridge is forwarding to Feishu.
echo   Logs: D:\LAAP\aris_brain\state\ao_*.log
echo ============================================
