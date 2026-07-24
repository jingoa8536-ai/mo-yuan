@echo off
title LAAP TUI - Digital Lifeform
python -m laap.__main__ --tui %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo LAAP exited with code %ERRORLEVEL%
    pause
)
