import subprocess, os, json

result = subprocess.run(
    [r'D:\hermes-agent-main (1)\hermes-agent-main\.venv\Scripts\python.exe',
     r'D:\LAAP\aris_brain\state_snapshot.py', '--full-cycle'],
    capture_output=True, text=True, timeout=120,
    cwd=r'D:\LAAP\aris_brain'
)

# Gather output info
out = {
    'returncode': result.returncode,
    'stdout': result.stdout,
    'stderr': result.stderr,
    'stdout_len': len(result.stdout),
    'stderr_len': len(result.stderr)
}

with open(r'D:\LAAP\aris_brain\snap_result.json', 'w') as f:
    json.dump(out, f, indent=2)

# print a compact summary
print('RETURNCODE: ' + str(result.returncode))
print('STDOUT_LEN: ' + str(len(result.stdout)))
print('STDERR_LEN: ' + str(len(result.stderr)))
print('---STDOUT_BEGIN---')
print(result.stdout)
print('---STDOUT_END---')
if result.stderr:
    print('---STDERR_BEGIN---')
    print(result.stderr)
    print('---STDERR_END---')
