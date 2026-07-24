"""Aris 任务队列处理器 — 被 cron 定时调用"""
import subprocess, sys, os

script = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "LAAP", "aris_brain", "aris_queue_processor.py")
script = os.path.abspath(script)

if os.path.exists(script):
    r = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=30)
    if r.returncode == 0 and r.stdout.strip():
        print(r.stdout.strip()[:500])
    elif r.stderr:
        print(f"[queue processor] {r.stderr.strip()[:300]}")
else:
    print(f"[queue processor] script not found: {script}")
