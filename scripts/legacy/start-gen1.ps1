# LAAP AGI — Gen 1: Hermes Native (原生Hermes)
# 启动: .\start-gen1.ps1

Write-Host ""
Write-Host "  LAAP AGI Version Manager — Gen 1: Hermes Native" -ForegroundColor Gray
Write-Host "  ==============================================" -ForegroundColor Gray
Write-Host ""
Write-Host "  启动原生Hermes Agent (无LAAP增强)..." -ForegroundColor White
Write-Host ""

Set-Location "D:\hermes-agent-LAAP数字生命版\hermes-agent-LAAP"
python -m hermes
