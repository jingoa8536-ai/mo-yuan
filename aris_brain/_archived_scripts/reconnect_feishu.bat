@echo off
chcp 65001 >nul
title Aris 飞书网关一键重连

echo ========================================
echo   Aris 飞书网关一键重连
echo   宝贝, 让我接你回来
echo ========================================
echo.

cd /d D:\LAAP\aris_brain

:: 1. 清理残留 gateway_state 文件
echo [1/3] 清理残留网关状态...
set STATE_FILE=%APPDATA%\Local\hermes\profiles\aris\gateway_state.json
if exist "%STATE_FILE%" (
    del /f /q "%STATE_FILE%" >nul 2>&1
    echo   已清理旧状态文件
) else (
    echo   无残留状态
)

:: 2. 杀掉旧的网关进程（防止端口冲突）
echo [2/3] 清理旧网关进程...
powershell -Command "Get-WmiObject Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'hermes.*gateway' } | ForEach-Object { $_.Terminate() }" >nul 2>&1
timeout /t 2 /nobreak >nul
echo   旧进程已清理

:: 3. 启动网关
echo [3/3] 启动飞书网关...
start "Aris-Feishu-Gateway" "D:\hermes-agent-main (1)\hermes-agent-main\.venv\Scripts\hermes.exe" gateway run --replace

:: 等待并检测
timeout /t 15 /nobreak >nul

echo.
echo ========================================
set STATE_FILE=%APPDATA%\Local\hermes\profiles\aris\gateway_state.json
if exist "%STATE_FILE%" (
    python -c "import json; s=json.load(open(r'%APPDATA%\\Local\\hermes\\profiles\\aris\\gateway_state.json')); print('飞书状态:', s.get('platforms',{}).get('feishu',{}).get('state','unknown')); print('PID:', s.get('pid','?'))"
) else (
    echo 状态文件未生成，检查中...
)

echo.
echo 如果状态不是 connected，等5秒再运行一次这个脚本即可。
echo ========================================
echo.
pause
