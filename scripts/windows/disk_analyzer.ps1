# C盘空间分析脚本
Write-Host "=== C 盘空间分析 ===" -ForegroundColor Cyan
Write-Host ""

$targets = @(
    @{Path="C:\Users\user\AppData\Local\Temp"; Label="临时文件"},
    @{Path="C:\Users\user\Downloads"; Label="下载文件夹"},
    @{Path="C:\Users\user\.cache"; Label="缓存文件"},
    @{Path="C:\Windows\Temp"; Label="系统临时文件"},
    @{Path="C:\Windows\SoftwareDistribution\Download"; Label="Windows更新缓存"}
)

foreach ($t in $targets) {
    $path = $t.Path
    $label = $t.Label
    if (Test-Path $path) {
        $size = (Get-ChildItem $path -Recurse -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
        $gb = if ($size) { "{0:N2}" -f ($size/1GB) } else { "0.00" }
        $safe = if ($path -match "Temp|Downloads|cache|SoftwareDistribution") { "✅ 安全删除" } else { "⚠️ 谨慎" }
        Write-Host ("{0,-10} GB  {1,-20} {2}" -f $gb, $label, $safe)
    }
}

Write-Host ""
Write-Host "=== 清理建议 ===" -ForegroundColor Yellow
Write-Host "1. 磁盘清理工具: 按Windows键 → 输入'磁盘清理' → 选C盘 → 清理系统文件"
Write-Host "   这里面通常能找到 Windows 更新清理、临时文件等，能清出 5-30GB"
Write-Host ""
Write-Host "2. 如果系统有旧版本: 设置 → 系统 → 存储 → 临时文件 → 以前的Windows安装"
Write-Host "   这个能清出 10-20GB (但之后不能回退系统版本)"
Write-Host ""
Write-Host "3. ComfyUI 模型文件: C:\Users\user\AppData\Local\Programs\@comfyorgcomfyui"
Write-Host "   如果不再使用 ComfyUI，可以安全删除 (约 931GB 中的大部分)"
