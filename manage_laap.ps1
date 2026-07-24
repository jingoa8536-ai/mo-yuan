param(
    [ValidateSet('start','stop','restart','status','bootstrap')]
    [string]$Action = "status",
    [string]$UserName = "duoduo",
    [int]$Port = 11546
)

$LAAP_ROOT = "C:\OH-WorkSpace\laap-AGI"

function Get-LaapProcess {
    Get-Process -Name python -ErrorAction SilentlyContinue |
        Where-Object { $_.Id -ne $pid } |
        ForEach-Object {
            $hasPort = netstat -ano 2>$null | findstr ":$Port" | findstr $_.Id
            if ($hasPort) { $_ }
        }
}

if ($Action -eq "start") {
    $existing = Get-LaapProcess
    if ($existing) {
        Write-Host "LAAP already running (PID: $($existing.Id))"
        exit 0
    }
    Write-Host "Starting LAAP Aris on port $Port ..."
    Write-Host "(first load takes ~90s for engine warmup)"
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "python"
    $psi.Arguments = "-m aris_brain.laap_brain_api --port $Port"
    $psi.WorkingDirectory = $LAAP_ROOT
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    [System.Diagnostics.Process]::Start($psi) | Out-Null

    $timeout = 150
    $elapsed = 0
    while ($elapsed -lt $timeout) {
        $listening = netstat -ano 2>$null | findstr ":$Port"
        if ($listening) {
            Write-Host "LAAP ready on port $Port !"
            Write-Host "API: http://localhost:$Port"
            exit 0
        }
        Start-Sleep 5
        $elapsed += 5
        Write-Host "  waiting... (${elapsed}s)"
    }
    Write-Host "Timeout: LAAP did not start in ${timeout}s"
}

elseif ($Action -eq "stop") {
    $existing = Get-LaapProcess
    if (-not $existing) {
        Write-Host "LAAP is not running"
        return
    }
    Write-Host "Stopping LAAP..."
    $existing | Stop-Process -Force
    Write-Host "LAAP stopped"
}

elseif ($Action -eq "restart") {
    & $PSCommandPath -Action stop
    Start-Sleep 2
    & $PSCommandPath -Action start -UserName $UserName -Port $Port
}

elseif ($Action -eq "status") {
    $existing = Get-LaapProcess
    if (-not $existing) {
        Write-Host "LAAP is not running"
        Write-Host "Start: manage_laap.ps1 -Action start"
        return
    }
    $mem = [math]::Round($existing.WorkingSet64 / 1MB, 1)
    Write-Host "LAAP is running"
    Write-Host "  PID: $($existing.Id)"
    Write-Host "  RAM: ${mem}MB"
    Write-Host "  Port: $Port"
    try {
        $health = curl.exe -s --connect-timeout 3 http://localhost:$Port/health 2>$null
        $h = $health | ConvertFrom-Json
        Write-Host "  Engines: $(if ($h.engines_loaded) { 'loaded' } else { 'pending' })"
    } catch {
        Write-Host "  Health: no response"
    }
}

elseif ($Action -eq "bootstrap") {
    Write-Host "Awakening Aris..."
    $body = "{`"user_name`":`"$UserName`"}"
    try {
        $resp = curl.exe -s -X POST "http://localhost:$Port/v1/bootstrap" -H "Content-Type: application/json" -d $body 2>$null
        $r = $resp | ConvertFrom-Json
        Write-Host "Aris awakened!"
        Write-Host "  Name: $($r.identity.name)"
        Write-Host "  User: $($r.identity.user_name)"
        Write-Host "  Bond: $($r.bond.attachment_stage)"
    } catch {
        Write-Host "Awakening failed: $_"
        Write-Host "Start LAAP first: manage_laap.ps1 -Action start"
    }
}
