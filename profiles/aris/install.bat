@echo off
REM Aris Profile 安装脚本 (Windows)
REM 运行: powershell -ExecutionPolicy Bypass -File install-aris.ps1
echo 正在安装 Aris profile...

set HERMES_PROFILE_DIR=%USERPROFILE%\.hermes\profiles\aris
if not exist "%HERMES_PROFILE_DIR%" mkdir "%HERMES_PROFILE_DIR%"

copy /Y profiles\aris\SOUL.md "%HERMES_PROFILE_DIR%\SOUL.md"
copy /Y profiles\aris\config.yaml.example "%HERMES_PROFILE_DIR%\config.yaml"

echo ✅ Aris profile 已安装到 %HERMES_PROFILE_DIR%
echo ⚠️  请编辑 config.yaml 填入你的 API Key
echo.
echo 然后运行: hermes profile alias aris --name hermes-aris
echo 之后输入 hermes-aris 即可启动 Aris
