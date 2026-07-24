import subprocess, sys, os
from datetime import datetime
python_exe = r"C:\Users\user\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
b2_script = r"D:\LAAP\aris_brain\consciousness_daemon_cron.py"
log_path = r"D:\LAAP\aris_brain\daemon_cron_popen.log"
log = open(log_path, 'a')
log.write('[' + datetime.now().isoformat() + '] Launcher starting...\n')
log.flush()
p = subprocess.Popen(
    [python_exe, '-u', b2_script],
    cwd='D:/LAAP/aris_brain',
    stdout=log,
    stderr=subprocess.STDOUT,
    creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
)
log.write('[' + datetime.now().isoformat() + '] Daemon started: PID=' + str(p.pid) + '\n')
log.flush()
print('PID=' + str(p.pid))
