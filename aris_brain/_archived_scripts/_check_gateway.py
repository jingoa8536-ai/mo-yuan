"""Check gateway status"""
import os, subprocess

# 1. Check gateway log file
log = os.path.expanduser("~/.aris/feishu_gateway.log")
print(f"Gateway log: {log}")
print(f"Size: {os.path.getsize(log) if os.path.exists(log) else 'NOT FOUND'}")
print()

# 2. Check wmic for gateway processes
r = subprocess.run(
    ['wmic', 'process', 'where', "name='python.exe'", 'get', 'CommandLine', '/format:csv'],
    capture_output=True, text=True, timeout=8,
    creationflags=subprocess.CREATE_NO_WINDOW
)
gateways = [l for l in r.stdout.split('\n') if 'gateway' in l.lower()]
print(f"Gateway processes found: {len(gateways)}")
for g in gateways:
    print(f"  -> {g[:120]}")

# 3. Last 20 lines of gateway log
if os.path.exists(log):
    print("\n--- Last 20 lines of gateway log ---")
    with open(log, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
    for l in lines[-20:]:
        print(l.rstrip())
