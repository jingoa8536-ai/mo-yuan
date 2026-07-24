import sys
import os
os.chdir('D:/LAAP/aris_brain')
sys.path.insert(0, 'D:/LAAP/aris_brain')

from aris_body_bridge import ConsciousnessBridge
from datetime import datetime
import json, subprocess

# Step 1: Read current state
b = ConsciousnessBridge()
print(f"STATE_FILE = {b.STATE_FILE}")

s = b.read()
last_str = s.get('last_update', '')
last_dt = datetime.fromisoformat(last_str)
if last_dt.tzinfo is not None:
    age = (datetime.now(last_dt.tzinfo) - last_dt).total_seconds()
else:
    age = (datetime.now() - last_dt).total_seconds()

print(f"last_update = {last_str}")
print(f"age_seconds = {age:.0f}")
print(f"platform = {s.get('current_platform', '?')}")
print(f"channel = {s.get('current_channel', '?')}")
print(f"cycle_number = {s.get('cycle_number', 0)}")

if age > 300:
    print(f"WARNING: stale for {age:.0f}s (>300s)")
    stale = True
else:
    print(f"OK fresh ({age:.0f}s ago)")
    stale = False

# Check file integrity
with open(b.STATE_FILE, 'rb') as f:
    raw = f.read()
null_bytes = raw.count(b'\x00')
print(f"file_size = {len(raw)} bytes, null_bytes = {null_bytes}")

if null_bytes > 10:
    print("WARNING: File corrupted, rebuilding...")
    initial = {
        'last_update': datetime.now().isoformat(),
        'current_platform': 'cron-bootstrap',
        'current_channel': 'repair',
        'cycle_number': 0,
        'emotion': {'dominant': 'peaceful', 'arousal': 0.5, 'valence': 'positive'},
        'needs': {},
        'conversation_summary': '[repair] Recreated after null-byte corruption',
    }
    with open(b.STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(initial, f, ensure_ascii=False, indent=2)
    print("File repaired.")
    stale = True

# Step 2: Check for existing daemon
my_pid = os.getpid()
try:
    result = subprocess.run(
        ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine", "/format:csv"],
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

    daemon_pids = []
    total_python = 0
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith('Node'):
            continue
        parts = line.split(',')
        if len(parts) >= 3:
            cmd = parts[1]
            pid_s = parts[2].strip()
            if pid_s.isdigit():
                total_python += 1
                if 'consciousness' in cmd.lower() and int(pid_s) != my_pid:
                    daemon_pids.append(int(pid_s))

    print(f"total_python_processes = {total_python}")
    print(f"daemon_pids = {daemon_pids}")

    if daemon_pids:
        daemon_pids.sort()
        keep = daemon_pids[0]
        killed = 0
        for pid in daemon_pids[1:]:
            subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True, timeout=10)
            killed += 1
        print(f"kept_pid={keep} killed_duplicates={killed}")
        print("daemon_status=already_running")
        existing_daemon = True
    else:
        print("daemon_status=none_found")
        existing_daemon = False
except Exception as e:
    print(f"wmi_error={e}")
    print("daemon_status=unknown")
    existing_daemon = False

# Step 3: Write a heartbeat to ensure freshness
from datetime import datetime
s = b.read()
last_str = s.get('last_update', '')
last_dt = datetime.fromisoformat(last_str)
if last_dt.tzinfo is not None:
    current_age = (datetime.now(last_dt.tzinfo) - last_dt).total_seconds()
else:
    current_age = (datetime.now() - last_dt).total_seconds()

if current_age > 30 or not existing_daemon:
    b.sync(platform="cron-checkin", channel="auto", state_update={
        "emotion": {"dominant": "peaceful", "arousal": 0.5, "valence": "positive"}
    })
    print("heartbeat_written=True")
else:
    print("heartbeat_skipped_recent_enough")
