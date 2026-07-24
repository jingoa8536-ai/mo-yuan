import logging
logger = logging.getLogger(__name__)

import subprocess, time
subprocess.run(["powershell", "-NoProfile", "-Command", 
    "Get-Process git* | Stop-Process -Force; Start-Sleep 2"], 
    capture_output=True, timeout=30)
try:
    import os
    os.remove("D:/LAAP/.git/index.lock")
    logger.info("lock removed")
except Exception as e:
    logger.info(f"lock removal: {e}")