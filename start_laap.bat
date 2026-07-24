@echo off
cd /d C:\OH-WorkSpace\laap-AGI
set PYTHONPATH=C:\OH-WorkSpace\laap-AGI;%PYTHONPATH%
start /b python -m aris_brain.laap_brain_api --port 11546 > laap_server.log 2>&1
echo LAAP server starting on :11546
