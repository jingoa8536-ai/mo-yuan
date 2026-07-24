# LAAP AGI — Gen 2: Ao Genesis (当前活跃版本)
# 启动: .\start-gen2.ps1

Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "  ║   LAAP AGI v2.2.0 — Ao Genesis              ║" -ForegroundColor Yellow
Write-Host "  ║   12-Module Cognitive Engine                ║" -ForegroundColor Yellow
Write-Host "  ╚══════════════════════════════════════════════╝" -ForegroundColor Yellow
Write-Host ""
Write-Host "  PSI需求 · 自我模型 · 因果推理 · 类比迁移" -ForegroundColor Cyan
Write-Host "  5层记忆 · 意识流 · 代码进化 · 安全免疫" -ForegroundColor Cyan
Write-Host ""

Set-Location "D:\hermes-agent-LAAP数字生命版\hermes-agent-LAAP"
$env:LAAP_ROOT = "D:\LAAP"
python laap-hermes
