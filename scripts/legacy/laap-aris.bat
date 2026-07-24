@echo off
REM laap-aris — Aris V10 PsiLang LM 完全体
start /B python D:\LAAP\aris_brain\pi_psi_server.py 11531
hermes -p aris %*
