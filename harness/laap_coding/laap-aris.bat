@echo off
REM LAAP-ARIS 启动器 — Aris Harness Engine
REM 使用 ConsciousnessHarness 7层认知架构 + Aris 执行引擎
python "%~dp0laap_agent.py" --aris %*
