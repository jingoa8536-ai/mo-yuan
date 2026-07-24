"""Check gateway process status"""
import subprocess

# Method 1: Use subprocess with raw bytes
r = subprocess.run(
    ['wmic', 'process', 'where', "name='python.exe'", 'get', 'CommandLine', '/format:csv'],
    capture_output=True, timeout=8,
    creationflags=subprocess.CREATE_NO_WINDOW
)
# Decode raw bytes with latin-1 to avoid cp950/cp936 issues
raw = r.stdout.decode('latin-1')
lines = raw.split('\n')
gw_lines = [l for l in lines if 'gateway' in l.lower()]

print(f"Gateway processes found: {len(gw_lines)}")
for l in gw_lines:
    print(f"  PID/CMD: {l[:200]}")

# Also check with tasklist
print("\n--- tasklist check ---")
r2 = subprocess.run(
    ['tasklist', '/FI', 'IMAGENAME eq python.exe', '/FO', 'CSV', '/V'],
    capture_output=True, text=True, timeout=8
)
# Just count gateway matches
print(f"tasklist output lines: {len(r2.stdout.split(chr(10)))}")
print(f"gateway mentions: {r2.stdout.lower().count('gateway')}")
