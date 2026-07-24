# LAAP AGI — Gen 3: Ao Complete (内核级集成)
# 启动: .\start-gen3.ps1

Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "  ║   LAAP AGI v3.0.0 — Ao Complete             ║" -ForegroundColor Yellow
Write-Host "  ║   Kernel-Level Integration                  ║" -ForegroundColor Yellow
Write-Host "  ╚══════════════════════════════════════════════╝" -ForegroundColor Yellow
Write-Host ""
Write-Host "  应用内核补丁..." -ForegroundColor Cyan

Set-Location "D:\hermes-agent-LAAP数字生命版\hermes-agent-LAAP"
python kernel_patch.py apply

Write-Host ""
Write-Host "  启动 Hermes (内核级 LAAP AGI)..." -ForegroundColor Green
$env:LAAP_ROOT = "D:\LAAP"
python laap-hermes
