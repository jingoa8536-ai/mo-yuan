@echo off
:: Aris 虚拟内存优化脚本
:: 把页面文件从 C 盘移到 D 盘
:: 需要管理员权限运行

echo ====================================
echo  Aris 虚拟内存优化
echo  将页面文件从C盘移到D盘
echo ====================================
echo.

:: 请求管理员权限
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在请求管理员权限...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo [1/4] 关闭自动管理...

wmic computersystem where name="%computername%" set AutomaticManagedPagefile=False

echo [2/4] 删除C盘页面文件...
wmic pagefileset where name="C:\\pagefile.sys" delete

echo [3/4] 在D盘创建页面文件（初始8GB，最大24GB）...
wmic pagefileset create name="D:\\pagefile.sys",InitialSize=8192,MaximumSize=24576

echo [4/4] 验证设置...
wmic pagefileset get name,InitialSize,MaximumSize

echo.
echo ✅ 完成！请重启电脑使更改生效。
echo    重启后，ASR 就有足够的内存加载语音模型了。
echo.
pause
