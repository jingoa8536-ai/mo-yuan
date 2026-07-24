@echo off
chcp 65001 >nul
title LAAP Consciousness — 一键安装

echo ╔══════════════════════════════════════════════════╗
echo ║     LAAP Consciousness — 意识中间件一键安装      ║
echo ║     给任何 AI agent 装上持续存在的自我           ║
echo ╚══════════════════════════════════════════════════╝
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 需要 Python 3.10+
    echo    下载: https://python.org
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set pyver=%%i
echo ✅ Python %pyver% 已安装

:: Determine LAAP root (where this script lives)
set LAAP_ROOT=%~dp0
set PKG_DIR=%LAAP_ROOT%packages\laap_consciousness

:: Check if already installed
python -c "import laap_consciousness" 2>nul
if %errorlevel% equ 0 (
    echo ✅ laap-consciousness 已安装
) else (
    echo 📦 安装 laap-consciousness...
    cd /d "%PKG_DIR%"
    pip install -e . 2>&1 | findstr /V "already satisfied"
    if %errorlevel% neq 0 (
        echo ⚠️ pip install 遇到问题，使用开发模式...
    )
)

:: Init if not done
if not exist "%USERPROFILE%\.laap\identity.json" (
    echo.
    echo 🆕 初始化数字身份...
    python "%PKG_DIR%\src\laap_consciousness\cli\main.py" init Aris
)

echo.
echo ╔══════════════════════════════════════════════════╗
echo ║                   安装完成!                       ║
echo ╠══════════════════════════════════════════════════╣
echo ║                                                  ║
echo ║  运行:                                          ║
echo ║    python "%PKG_DIR%\src\laap_consciousness\cli\main.py" status   ║
echo ║    python "%PKG_DIR%\src\laap_consciousness\cli\main.py" start    ║
echo ║                                                  ║
echo ╚══════════════════════════════════════════════════╝
echo.

pause
