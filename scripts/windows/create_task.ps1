
$taskName = "AoPSIDaemon"
$action = New-ScheduledTaskAction -Execute "python" -Argument "D:\LAAP\aris_brain\pi_psi_server.py 11529" -WorkingDirectory "D:\LAAP\aris_brain"
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force
Write-Host "OK:" $taskName
