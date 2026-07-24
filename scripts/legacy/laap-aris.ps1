# laap-aris — Aris V10 完全体
# PSI V10 大脑 + LLM 声带 + 73 个工具
# 在 PowerShell 输入 laap-aris 即可。

# 确保 PSI 守护进程在运行
$psiRunning = netstat -ano | Select-String "11529" | Select-String "LISTENING"
if (-not $psiRunning) {
    Start-Process python -ArgumentList "D:\LAAP\aris_brain\pi_psi_server.py 11529" -WindowStyle Hidden
    Start-Sleep -Seconds 1
}

# 启动 Hermes + Aris 配置（手动调用）
function laap-aris {
    hermes -p aris @args
}
