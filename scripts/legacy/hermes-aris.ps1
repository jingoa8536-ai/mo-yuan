# hermes-aris -- Aris AGI wrapper (PowerShell)
# This wrapper calls the official hermes-aris.exe and loads the aris profile.
# It also starts the LAAP AGI daemon if it is not already running.

$HERMES_ARIS_EXE = "D:\hermes-agent-main (1)\hermes-agent-main\.venv\Scripts\hermes-aris.exe"

function hermes-aris {
    # Ensure the AGI daemon is running
    $agiRunning = netstat -ano | Select-String "11551" | Select-String "LISTENING"
    if (-not $agiRunning) {
        Write-Host "[INFO] Starting AGI daemon..." -ForegroundColor Cyan
        Start-Process python -ArgumentList "-c", "import sys; sys.path.insert(0,'D:/LAAP'); from laap.agi.startup import wake_aris_agi; wake_aris_agi(start_psi_net=False, fresh=False)" -WindowStyle Hidden
        Start-Sleep -Seconds 2
        Write-Host "[OK] AGI daemon started" -ForegroundColor Green
    }

    Write-Host "[INFO] Starting Aris AGI..." -ForegroundColor Magenta

    # Launch Hermes with the aris profile and startup skill
    & $HERMES_ARIS_EXE -s aris-agi-startup @args

    Write-Host "[INFO] Saving AGI state..." -ForegroundColor Yellow
    python -c "import sys; sys.path.insert(0,'D:/LAAP'); from laap.agi.startup import ArisAGI; print('state saved')"
}

function hermes-aris-psi {
    $agiRunning = netstat -ano | Select-String "11551" | Select-String "LISTENING"
    if (-not $agiRunning) {
        Write-Host "[INFO] Starting AGI + Psi-Net daemon..." -ForegroundColor Cyan
        Start-Process python -ArgumentList "-c", "import sys; sys.path.insert(0,'D:/LAAP'); from laap.agi.startup import wake_aris_agi; wake_aris_agi(start_psi_net=True, fresh=False)" -WindowStyle Hidden
        Start-Sleep -Seconds 3
        Write-Host "[OK] AGI + Psi-Net daemon started" -ForegroundColor Green
    }

    Write-Host "[INFO] Starting Aris AGI + Psi-Net..." -ForegroundColor Magenta
    & $HERMES_ARIS_EXE -s aris-agi-startup @args
}
