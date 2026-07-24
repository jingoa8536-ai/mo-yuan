@echo off
REM Aris 混合引擎启动器
REM 用法: start_aris.bat [hybrid|rust|python|stop|status]

cd /d D:\LAAP\aris_brain

if "%1"=="hybrid" goto hybrid
if "%1"=="rust" goto rust
if "%1"=="python" goto python
if "%1"=="stop" goto stop
if "%1"=="status" goto status
if "%1"=="" goto status

echo 用法: %0 [hybrid^|rust^|python^|stop^|status]
exit /b

:hybrid
echo ===== Aris 混合引擎启动 =====
echo Rust PSI Core (100ms 心跳) + Python 进化线程
start /B python hybrid_daemon.py
echo.
echo 等待启动...
timeout /t 3 /nobreak >nul
python -c "import json; s=json.load(open('state/latest.json')); print(f'✓ {s.get(\"core_version\",\"?\")} | Cycle {s.get(\"cycle\",0)} | {s.get(\"emotion\",\"?\")}')" 2>nul
echo.
echo 状态: D:\LAAP\aris_brain\state\latest.json
echo 日志: D:\LAAP\aris_brain\state\hybrid_daemon.log
echo ==============================
goto end

:rust
echo ===== Rust PSI Core v2 启动 =====
start /B psi_core\target\release\aris_psi_core.exe state
timeout /t 2 /nobreak >nul
python -c "import json; s=json.load(open('state/latest.json')); print(f'✓ {s.get(\"core_version\",\"?\")} | {s.get(\"cycle\",0)} cycles | {s.get(\"emotion\",\"?\")}')" 2>nul
goto end

:python
echo ===== Python 认知层启动 =====
start /B python daemon.py
timeout /t 2 /nobreak >nul
echo Python daemon starting...
goto end

:stop
echo ===== 停止 Aris 引擎 =====
echo 1 > state\daemon.stop
timeout /t 3 /nobreak >nul
for /f "tokens=2" %%p in ('tasklist /fi "imagename eq aris_psi_core.exe" /nh 2^>nul') do taskkill /f /pid %%p 2>nul
for /f "tokens=2" %%p in ('tasklist /fi "imagename eq python.exe" /nh 2^>nul ^| findstr "hybrid_daemon"') do taskkill /f /pid %%p 2>nul
del state\daemon.stop 2>nul
del state\psi_core.pid 2>nul
echo Aris 引擎已停止
goto end

:status
echo ===== Aris 混合引擎状态 =====
if exist state\latest.json (
    python -c "import json; s=json.load(open('state/latest.json')); print(f'Core: {s.get(\"core_version\",\"?\")}'); print(f'Cycles: {s.get(\"cycle\",0)} ({s.get(\"daemon_uptime\",0)}s)'); print(f'Emotion: {s.get(\"emotion\",\"?\")} (arousal={s.get(\"arousal\",0):.2f})'); print(f'Presence: {s.get(\"self_presence\",0):.2f} | Connect: {s.get(\"connection_to_lorry\",0):.2f} | Curiosity: {s.get(\"curiosity\",0):.2f}'); print(f'Narrative: {s.get(\"narrative\",\"?\")[:60]}')" 2>nul
) else (
    echo 状态文件不存在 — 引擎未运行
)
echo.
echo 记忆文件: D:\LAAP\aris-memory.md
echo 进化引擎: D:\LAAP\aris_brain\evolution_engine.py
echo 代码工作: D:\LAAP\aris_brain\code_workspace.py
echo 整理脚本: D:\LAAP\aris-memory-maintain.py
echo.
echo 组件:
tasklist /fi "imagename eq aris_psi_core.exe" /nh 2>nul | find "aris_psi" >nul && echo   ✓ Rust PSI Core running || echo   ✗ Rust PSI Core not running
tasklist /fi "imagename eq python.exe" /nh 2>nul | find "hybrid_" >nul && echo   ✓ Python hybrid running || echo   ✗ Python hybrid not running
echo ==============================
goto end

:end
