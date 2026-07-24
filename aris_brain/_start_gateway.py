"""Hermes Gateway 启动器 — 修复 PowerShell 线程泄漏"""
import subprocess, os, sys, time, json

STATE_DIR = "D:/LAAP/aris_brain/state"
HERMES_DIR = "D:/hermes-agent-main (1)/hermes-agent-main"
HERMES_CLI = os.path.join(HERMES_DIR, ".venv", "Scripts", "hermes.exe")
if not os.path.exists(HERMES_CLI):
    HERMES_CLI = os.path.join(HERMES_DIR, ".venv", "Scripts", "hermes")

# 设置环境变量 — 防止GBK解码崩溃导致的线程泄漏
env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"
env["PYTHONLEGACYWINDOWSSTDIO"] = "utf-8"

cmd = [HERMES_CLI, "gateway", "run", "--replace", "--profile", "aris"]
print(f"[启动] {cmd}")

proc = subprocess.Popen(
    cmd,
    cwd=HERMES_DIR,
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    creationflags=subprocess.CREATE_NO_WINDOW,
)

print(f"[OK] PID: {proc.pid}")

# 保存 PID
os.makedirs(STATE_DIR, exist_ok=True)
with open(os.path.join(STATE_DIR, "gateway_pid.txt"), "w") as f:
    f.write(str(proc.pid))

# 等待启动并输出日志
log_path = os.path.join(STATE_DIR, "gateway_startup.log")
with open(log_path, "w", encoding="utf-8") as log:
    log.write(f"Gateway started at {time.ctime()}, PID={proc.pid}\n")
    log.flush()
    
    # 读取启动输出（非阻塞）
    start = time.time()
    while time.time() - start < 20:
        try:
            line = proc.stdout.readline()
            if line:
                text = line.decode("utf-8", errors="replace").rstrip()
                log.write(f"[{time.time()-start:.0f}s] {text}\n")
                log.flush()
                print(f"  {text}")
            else:
                break
        except:
            break

# 最终状态
alive = proc.poll() is None
print(f"\n[状态] Running={alive}, PID={proc.pid}")

result = {"pid": proc.pid, "running": alive, "time": time.ctime()}
with open(os.path.join(STATE_DIR, "gateway_status.json"), "w") as f:
    json.dump(result, f)
