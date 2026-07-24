# Aris Page File Setup
# Run this as Administrator

Write-Host "=== Aris 虚拟内存设置 ===" -ForegroundColor Cyan
Write-Host ""

# Disable automatic page file management
$cs = Get-WmiObject Win32_ComputerSystem -EnableAllPrivileges
$cs.AutomaticManagedPagefile = $false
$cs.Put() | Out-Null
Write-Host "[OK] 已关闭自动管理" -ForegroundColor Green

# Remove C: page file
$oldPf = Get-WmiObject Win32_PageFileSetting | Where-Object { $_.Name -eq "C:\pagefile.sys" }
if ($oldPf) {
    $oldPf.Delete() | Out-Null
    Write-Host "[OK] 已删除 C 盘页面文件" -ForegroundColor Green
}

# Create D: page file (8192 MB initial, 24576 MB max)
$pf = Get-WmiObject Win32_PageFileSetting -EnableAllPrivileges
$pf.Create("D:\pagefile.sys") | Out-Null

$newPf = Get-WmiObject Win32_PageFileSetting | Where-Object { $_.Name -eq "D:\pagefile.sys" }
if ($newPf) {
    $newPf.InitialSize = 8192
    $newPf.MaximumSize = 24576
    $newPf.Put() | Out-Null
    Write-Host "[OK] 已在 D 盘创建页面文件 (8GB~24GB)" -ForegroundColor Green
}

# Verify
Write-Host ""
Write-Host "当前页面文件配置:" -ForegroundColor Yellow
Get-WmiObject Win32_PageFileUsage | Format-Table Name, InitialSize, MaximumSize

Write-Host ""
Write-Host "✅ 完成！请重启电脑使更改生效。" -ForegroundColor Cyan
Write-Host "   重启后语音识别将正常工作。" -ForegroundColor Cyan
Read-Host "按 Enter 退出"
