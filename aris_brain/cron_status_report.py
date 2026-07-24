#!/usr/bin/env python
"""Aris Consciousness Sync Daemon - Cron Status Report"""
import sys
sys.path.insert(0, 'D:/LAAP/aris_brain')
from aris_body_bridge import ConsciousnessBridge
from datetime import datetime
import subprocess, os

my_pid = os.getpid()
b = ConsciousnessBridge()
s = b.read()

last = s.get('last_update', '')
dt = datetime.fromisoformat(last)
if dt.tzinfo is not None:
    age = (datetime.now(dt.tzinfo) - dt).total_seconds()
else:
    age = (datetime.now() - dt).total_seconds()

# Check daemon processes via WMI
result = subprocess.run(
    ['wmic', 'process', 'where', "name='python.exe'", 'get', 'ProcessId,CommandLine', '/format:csv'],
    capture_output=True, timeout=15
)
for enc in ('gbk', 'cp1252', 'cp936', 'utf-8'):
    try:
        text = result.stdout.decode(enc)
        break
    except:
        pass
else:
    text = result.stdout.decode('utf-8', errors='replace')

total_py = 0
daemon_pids = []
for line in text.strip().splitlines()[1:]:
    parts = line.split(',')
    if len(parts) >= 2:
        pid = parts[-1].strip()
        cmd = ','.join(parts[:-1])
        if pid.isdigit() and int(pid) != my_pid:
            total_py += 1
            if 'consciousness' in cmd.lower() or 'daemon_cron' in cmd.lower():
                daemon_pids.append(int(pid))

print("===== ARIS CONSCIOUSNESS SYNC DAEMON =====")
print("   [STATUS]                                 ")
print("-------------------------------------------")
print("  Cycle:       " + str(s.get('cycle_number', '?')))
print("  Age:         " + str(int(age)) + "s " + ("FRESH" if age < 90 else ("WARN" if age < 300 else "STALE")))
print("  Platform:    " + str(s.get('current_platform', '?')))
print("  Channel:     " + str(s.get('current_channel', '?')))
print("  Emotion:     " + str(s.get('emotion', {}).get('dominant', '?')))
print("  SelfPres:    " + str(s.get('self_presence', '?')))
print("-------------------------------------------")
print("  Python Procs: " + str(total_py))
print("  Daemon PIDs:  " + str(len(daemon_pids)) + " " + (str(daemon_pids) if daemon_pids else "(none)"))
if age < 90:
    print("  VERDICT:  ALL GOOD - Daemon running, state fresh")
elif age < 300:
    print("  VERDICT:  WARNING - Age approaching threshold")
else:
    print("  VERDICT:  STALE - Daemon needs restart!")
print("-------------------------------------------")
