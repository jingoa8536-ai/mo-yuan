@echo off
REM LAAP AGI — Gen 3: Ao Complete (内核级集成)
REM 直接修改Hermes源码，LAAP作为AIAgent原生方法
echo.
echo   ╔══════════════════════════════════════════════╗
echo   ║   LAAP AGI v3.0.0 — Ao Complete            ║
echo   ║   Kernel-Level Integration                 ║
echo   ╚══════════════════════════════════════════════╝
echo.
echo   应用内核补丁...
cd /d "D:\hermes-agent-LAAP数字生命版\hermes-agent-LAAP"
python kernel_patch.py apply
echo.
echo   启动 Hermes (内核级 LAAP AGI)...
set LAAP_ROOT=D:\LAAP
python laap-hermes
