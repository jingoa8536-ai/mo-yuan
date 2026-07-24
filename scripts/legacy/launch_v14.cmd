@echo off
cd /d D:\LAAPris_brain
taskkill /f /im python.exe 2>nul
start /MIN "" "C:\Python313\python.exe" "D:\LAAPris_brainris_fusion_v14.py"
exit
