$env:PYTHONPATH = "C:\OH-WorkSpace\laap-AGI"
$logDir = "C:\OH-WorkSpace\laap-AGI"

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "python"
$psi.Arguments = "-m aris_brain.laap_brain_api --port 11546"
$psi.WorkingDirectory = "C:\OH-WorkSpace\laap-AGI"
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $false
$psi.RedirectStandardError = $false
$psi.CreateNoWindow = $true

# Write output to files instead of pipe buffers
$psi.ArgumentList.Add("-m")
$psi.ArgumentList.Add("aris_brain.laap_brain_api")
$psi.ArgumentList.Add("--port")
$psi.ArgumentList.Add("11546")

$process = [System.Diagnostics.Process]::Start($psi)
Write-Host "LAAP server started with PID: $($process.Id)"
