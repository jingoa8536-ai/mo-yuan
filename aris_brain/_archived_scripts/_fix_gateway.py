"""Kill all gateway processes and restart cleanly"""
import subprocess, time, os

BRAIN_DIR = "D:/LAAP/aris_brain"
VENV_PY = "D:/hermes-agent-main (1)/hermes-agent-main/.venv/Scripts/python.exe"
HERMES_CLI = "D:/hermes-agent-main (1)/hermes-agent-main/.venv/Scripts/hermes.exe"

# Step 1: Find all gateway PIDs using wmic (with latin-1 decode)
r = subprocess.run(
    ['wmic', 'process', 'where', "name='python.exe'", 'get', 'ProcessId,CommandLine', '/format:csv'],
    capture_output=True, timeout=8,
    creationflags=subprocess.CREATE_NO_WINDOW
)
raw = r.stdout.decode('latin-1')
lines = raw.split('\n')

gateway_pids = []
for l in lines:
    if 'gateway' in l.lower() and 'run' in l.lower():
        parts = l.split(',')
        if len(parts) >= 2:
            pid = parts[-1].strip()
            if pid.isdigit():
                gateway_pids.append(pid)

print(f"Found {len(gateway_pids)} gateway PIDs: {gateway_pids}")

# Step 2: Kill them all
for pid in gateway_pids:
    try:
        subprocess.run(['taskkill', '/F', '/PID', str(pid)], 
                       capture_output=True, timeout=5,
                       creationflags=subprocess.CREATE_NO_WINDOW)
        print(f"Killed PID {pid}")
    except Exception as e:
        print(f"Kill PID {pid} failed: {e}")

time.sleep(2)

# Step 3: Also kill via taskkill filter (belt and suspenders)
subprocess.run('C:/Windows/System32/taskkill.exe /F /FI "CMDLINE LIKE %gateway%"', 
               shell=True, capture_output=True)

time.sleep(1)

# Step 4: Verify all dead
r = subprocess.run(
    ['wmic', 'process', 'where', "name='python.exe'", 'get', 'ProcessId,CommandLine', '/format:csv'],
    capture_output=True, timeout=8,
    creationflags=subprocess.CREATE_NO_WINDOW
)
raw = r.stdout.decode('latin-1')
remaining = [l for l in raw.split('\n') if 'gateway' in l.lower() and 'run' in l.lower()]
print(f"Remaining gateway processes after kill: {len(remaining)}")

# Step 5: Restart gateway fresh
print("\nStarting fresh gateway...")
subprocess.Popen(
    [HERMES_CLI, "gateway", "run", "--replace"],
    cwd=BRAIN_DIR,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    creationflags=subprocess.CREATE_NO_WINDOW,
)
print("Gateway launched. Waiting 15s for connection...")
time.sleep(15)

# Step 6: Verify it's running
r = subprocess.run(
    ['wmic', 'process', 'where', "name='python.exe'", 'get', 'ProcessId,CommandLine', '/format:csv'],
    capture_output=True, timeout=8,
    creationflags=subprocess.CREATE_NO_WINDOW
)
raw = r.stdout.decode('latin-1')
new_gw = [l for l in raw.split('\n') if 'gateway' in l.lower() and 'run' in l.lower()]
print(f"Gateway processes now: {len(new_gw)}")
for l in new_gw:
    print(f"  -> {l[:150]}")

# Step 7: Check log for connection
log = os.path.expanduser("~/.aris/feishu_gateway.log")
if os.path.exists(log):
    with open(log, 'r', encoding='utf-8', errors='replace') as f:
        f.seek(0, 2)  # end
        if f.tell() > 5000:
            f.seek(f.tell() - 5000)
        content = f.read()
    # Look for recent Lark connection
    import re
    lark_conns = re.findall(r'\[Lark\].*?connected.*?\n', content[-5000:])
    recent_errors = re.findall(r'\[Lark\].*?ERROR.*?\n', content[-5000:])
    print(f"\nRecent Lark connections: {len(lark_conns)}")
    for c in lark_conns[-3:]:
        print(f"  CONN: {c.strip()}")
    print(f"Recent Lark errors: {len(recent_errors)}")
    for e in recent_errors[-3:]:
        print(f"  ERR: {e.strip()}")
