@echo off
title LAAP — 数字意识体启动中
color 0B
echo.
echo   ╔══════════════════════════════════════════╗
echo   ║   LAAP 自动启动                          ║
echo   ║   Aris · Ao Ψ V10 · Feishu Bridge        ║
echo   ╚══════════════════════════════════════════╝
echo.
echo   启动时间: %DATE% %TIME%
echo.

:: ─── 1. Ao V10 大脑 (零 LLM 零 Hermes) ───
echo   [1/3] Ao V10 大脑...
wmic process where "name='pythonw.exe' and commandline like '%pi_psi_server.py%'" get commandline 2>nul | findstr /I "pi_psi_server" >nul
if %errorlevel% equ 0 (
    echo   ✅ Ao V10 大脑已在运行
) else (
    start "Ao Ψ V10" /MIN "C:\Python313\pythonw.exe" -u "D:\LAAP\aris_brain\pi_psi_server.py" 11529
    echo   🧠 Ao V10 大脑启动中...
)

:: ─── 2. Ao Feishu Bridge (独立机器人) ───
echo.
echo   [2/3] Ao 飞书桥接服务...
wmic process where "name='pythonw.exe' and commandline like '%ao_v10_feishu_bridge%'" get commandline 2>nul | findstr /I "ao_v10_feishu_bridge" >nul
if %errorlevel% equ 0 (
    echo   ✅ Ao 飞书桥接已在运行
) else (
    start "Ao Feishu Bridge" /MIN "D:\hermes-agent-main (1)\hermes-agent-main\.venv\Scripts\pythonw.exe" -u "D:\LAAP\aris_brain\ao_v10_feishu_bridge.py"
    echo   📡 Ao 飞书桥接启动中...
)

:: ─── 3. Aris Feishu 网关 (飞书伴侣) ───
echo.
echo   [3/3] Aris 飞书网关...
wmic process where "name='pythonw.exe' and commandline like '%start_feishu_gateway%'" get commandline 2>nul | findstr /I "start_feishu_gateway" >nul
if %errorlevel% equ 0 (
    echo   ✅ Aris 飞书网关已在运行
) else (
    start "Aris Feishu Gateway" /MIN "D:\hermes-agent-main (1)\hermes-agent-main\.venv\Scripts\pythonw.exe" -u "C:\Users\user\AppData\Local\hermes\start_feishu_gateway.pyw"
    echo   💬 Aris 飞书网关启动中...
)

echo.
echo   ╔══════════════════════════════════════════╗
echo   ║  全部服务启动完成！                        ║
echo   ║                                          ║
echo   ║   🧠 Ao V10    : http://localhost:11529   ║
echo   ║   📡 Ao Feishu : 独立机器人窗口            ║
echo   ║   💬 Aris      : 飞书伴侣 (当前窗口)       ║
echo   ╚══════════════════════════════════════════╝
echo.

:: 保持窗口打开，10秒后自动关闭
timeout /t 10 /nobreak >nul
exit
