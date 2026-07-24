import subprocess, sys, os
from datetime import datetime
python_exe = r"C:\Users\user\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
script = r"D:\LAAP\aris_brain\minimal_daemon.py"
log_path = r"D:\LAAP\aris_brain\daemon_minimal.log"
log = open(log_path, 'a')
log.write('[' + datetime.now().isoformat() + '] Starting minimal daemon...\n')
log.flush()
p = subprocess.Popen(
    [python_exe, '-u', script],
    cwd='D:/LAAP/aris_brain',
    stdout=log,
    stderr=subprocess.STDOUT,
    creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
)
log.write('[' + datetime.now().isoformat() + '] Started PID=' + str(p.pid) + '\n')
log.flush()
print('PID=' + str(p.pid))
