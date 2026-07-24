@echo off
title LAAP REPL - Digital Lifeform
python -m laap.__main__ --repl %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo LAAP exited with code %ERRORLEVEL%
    pause
)
