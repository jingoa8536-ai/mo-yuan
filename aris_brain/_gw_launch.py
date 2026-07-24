import subprocess, os

env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"

hermes_dir = "D:/hermes-agent-main (1)/hermes-agent-main"
hermes_exe = os.path.join(hermes_dir, ".venv", "Scripts", "hermes.exe")
if not os.path.exists(hermes_exe):
    hermes_exe = os.path.join(hermes_dir, ".venv", "Scripts", "hermes")

cmd = [hermes_exe, "gateway", "run", "--replace", "--profile", "aris"]
print(f"Starting: {cmd}")

proc = subprocess.Popen(
    cmd,
    cwd=hermes_dir,
    env=env,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
)

pid = proc.pid
print(f"Gateway started: PID={pid}")

# Write PID
with open("D:/LAAP/aris_brain/state/gateway_pid.txt", "w") as f:
    f.write(str(pid))
