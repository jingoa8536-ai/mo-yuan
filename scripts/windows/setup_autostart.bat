@echo off
REM Register Aris as a startup task
schtasks /create /tn "ArisCompanion" /tr "py -3 D:\LAAP\aris_tray.pyw" /ru %USERNAME% /sc onlogon /f
echo.
echo Done. Aris will greet you on every login.
pause
