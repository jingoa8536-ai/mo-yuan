"""Clean gateway restart"""
import subprocess, time, os

VENV_PY = "D:/hermes-agent-main (1)/hermes-agent-main/.venv/Scripts/python.exe"
HERMES_CLI = "D:/hermes-agent-main (1)/hermes-agent-main/.venv/Scripts/hermes.exe"
BRAIN_DIR = "D:/LAAP/aris_brain"
LOG_FILE = os.path.expanduser("~/.aris/feishu_gateway.log")

# Kill any remaining gateway using native CMD
subprocess.run(
    ['cmd', '/c', 'taskkill /F /FI "CMDLINE LIKE %gateway%" 2>nul'],
    capture_output=True, timeout=10
)
time.sleep(2)

# Verify all dead
r = subprocess.run(
    ['wmic', 'process', 'where', "name='python.exe'", 'get', 'CommandLine', '/format:csv'],
    capture_output=True, timeout=8
)
raw = r.stdout.decode('latin-1')
remaining = [l for l in raw.split('\n') if 'gateway' in l.lower()]
print(f"Gateway processes remaining: {len(remaining)}")

# Note current log size
old_size = os.path.getsize(LOG_FILE) if os.path.exists(LOG_FILE) else 0
print(f"Current log size: {old_size}")

# Start fresh
print("Starting gateway...")
proc = subprocess.Popen(
    [HERMES_CLI, "gateway", "run", "--replace"],
    cwd=BRAIN_DIR,
    stdout=open(LOG_FILE, "a", encoding="utf-8", errors="replace"),
    stderr=subprocess.STDOUT,
    creationflags=subprocess.CREATE_NO_WINDOW,
)
print(f"Gateway PID: {proc.pid}")

# Wait and check
time.sleep(20)
new_size = os.path.getsize(LOG_FILE) if os.path.exists(LOG_FILE) else 0
print(f"New log size: {new_size} (delta: {new_size - old_size})")

# Check process still alive
alive = proc.poll() is None
print(f"Process alive: {alive}")
if proc.poll() is not None:
    print(f"Exit code: {proc.returncode}")

# Read last lines for connection status
if new_size > old_size:
    with open(LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
        f.seek(max(0, new_size - 3000))
        tail = f.read()
    conn_lines = [l for l in tail.split('\n') if 'lark' in l.lower() or 'connected' in l.lower() or 'starting' in l.lower() or 'error' in l.lower()]
    for l in conn_lines[-10:]:
        print(f"  >> {l.strip()}")
