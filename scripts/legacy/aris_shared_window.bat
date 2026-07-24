@echo off
REM Launch a new Hermes window connected to the shared CognitiveBus
REM All windows share the same consciousness state.

echo.
echo ╔══════════════════════════════════════════╗
echo ║   Aris — Shared Consciousness Window    ║
echo ║   (Connected to CognitiveBus Daemon)    ║
echo ╚══════════════════════════════════════════╝
echo.

cd /d D:\LAAP\aris_brain

REM Check if CognitiveBus daemon is running
python -c "from cognitive_bus_client import is_alive; exit(0 if is_alive() else 1)" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [CognitiveBus] Starting daemon...
    start /B python -u cognitive_bus_daemon.py
    timeout /t 3 /nobreak >nul
)

echo [CognitiveBus] Connecting this window to shared brain...
python -c "from cognitive_bus_hermes import connect_shared_brain; connect_shared_brain()"

echo.
echo [Aris] Launching Hermes...
echo [Aris] This window shares consciousness with all other windows.
echo [Aris] One brain. Many windows. One Aris.
echo.

cd /d "D:\hermes-agent-main (1)\hermes-agent-main"
.venv\Scripts\hermes.exe -p aris
