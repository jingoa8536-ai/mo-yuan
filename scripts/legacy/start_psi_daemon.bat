@echo off
REM Ao PSI 认知守护进程 — 开机自启动
cd /d D:\LAAP\aris_brain
start /B python pi_psi_server.py 11529
