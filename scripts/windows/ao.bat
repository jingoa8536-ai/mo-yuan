@echo off
REM AO Digital Lifeform — LAAP V5 + Hermes profile
cd /d D:\LAAP
set HERMES_PROFILE=ao
set HERMES_LAAP_ENABLED=1
set HERMES_LAAP_VERSION=5.0.0
python -m laap %*
