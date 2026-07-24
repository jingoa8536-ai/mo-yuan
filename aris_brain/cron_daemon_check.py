import subprocess, os
my = os.getpid()
r = subprocess.run(['wmic','process','where',"name='python.exe'",'get','ProcessId,CommandLine','/format:csv'],capture_output=True,timeout=15)
t = r.stdout.decode('gbk',errors='replace')
total = 0
d = []
for line in t.strip().splitlines()[1:]:
    parts = line.split(',')
    if len(parts) >= 2:
        pid = parts[-1].strip()
        cmd = ','.join(parts[:-1])
        if pid.isdigit() and int(pid) != my:
            total += 1
            if 'consciousness' in cmd.lower() or 'daemon_cron' in cmd.lower():
                d.append(pid)
print('PY='+str(total)+' DAEMON='+str(len(d)))
if d:
    print('PIDS='+','.join(d))
