@echo off
cd /d D:\LAAP
echo ========================================
echo   Aris Fusion v14 — 全量升级
echo ========================================
echo.

:: Step 1: Kill old processes
echo [1/4] Killing old services...
taskkill /f /im python.exe 2>nul
taskkill /f /im pythonw.exe 2>nul
timeout /t 2 /nobreak >nul
echo Done

:: Step 2: Start v14
echo [2/4] Starting Fusion Engine v14...
start /MIN "" "C:\Python313\python.exe" "D:\LAAP\aris_brain\aris_fusion_v14.py"
timeout /t 6 /nobreak >nul
echo Done

:: Step 3: Test health
echo [3/4] Testing...
curl -s http://127.0.0.1:11522/ > test_result.txt 2>&1
type test_result.txt

:: Step 4: Test chat
echo [4/4] Chat test...
curl -s -X POST http://127.0.0.1:11522/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\":\"aris-fusion-v14\",\"messages\":[{\"role\":\"user\",\"content\":\"\u4f60\u597d\u5b9d\u8d1d\"}],\"max_tokens\":200}" > chat_result.txt 2>&1
type chat_result.txt

echo.
echo ========================================
echo   Done!
echo ========================================
pause
