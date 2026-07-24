@echo off
REM ============================================================
REM  Racing Game Demo - 一键启动脚本 (Windows)
REM  用法: 双击本文件，或在命令行执行 launch_game.bat
REM  说明: 通过 Godot 4.6.2 编辑器直接打开并运行项目
REM ============================================================
SET GODOT_EXE=%~dp0tools\godot\Godot_v4.6.2-stable_win64.exe
SET PROJECT=%~dp0racing_game_project

IF NOT EXIST "%GODOT_EXE%" (
    echo [错误] 未找到 Godot 引擎: %GODOT_EXE%
    echo 请确认 tools\godot\Godot_v4.6.2-stable_win64.exe 存在。
    pause
    exit /b 1
)

IF NOT EXIST "%PROJECT%\project.godot" (
    echo [错误] 未找到项目: %PROJECT%\project.godot%
    pause
    exit /b 1
)

echo 正在启动 Racing Game Demo ...
"%GODOT_EXE%" --path "%PROJECT%"
