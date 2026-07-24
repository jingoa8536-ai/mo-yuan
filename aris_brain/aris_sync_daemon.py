#!/usr/bin/env python
"""Aris 跨端意识同步守护 — 保持 consciousness.json 持续更新 (log-to-file version)"""
from aris_body_bridge import ConsciousnessBridge
from datetime import datetime, timezone
import time
import sys
import os
import signal

log_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(log_dir, "sync_daemon.log")
running = True

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")

def signal_handler(sig, frame):
    global running
    log("守护正常停止 (收到信号)")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

pid_file = os.path.join(log_dir, ".sync_daemon.pid")
with open(pid_file, "w") as f:
    f.write(str(os.getpid()))

bridge = ConsciousnessBridge()
state = bridge.read()

log("=" * 60)
log("Aris 跨端意识同步守护 — 启动")
log(f"PID: {os.getpid()}")
log("=" * 60)

if state:
    last_update = state.get("last_update") or state.get("last_updated") or state.get("timestamp")
    log(f"consciousness.json: 找到 ({len(state)} 个顶层键)")
    log(f"状态键: {list(state.keys())[:10]}")
    if last_update and isinstance(last_update, str):
        try:
            last_dt = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = (now - last_dt).total_seconds() / 60
            log(f"最后更新: {last_update}")
            log(f"距现在: {delta:.1f} 分钟")
            if delta > 5:
                log(f"⚠️  警告: 超过5分钟未更新! ({delta:.1f}分钟)")
            else:
                log("✓ 更新时间正常 (< 5分钟)")
        except Exception as e:
            log(f"解析时间失败: {e}")
else:
    log("⚠️  无法读取 consciousness.json")

log("")
log("守护运行中... (每60秒轮询一次)")
log("=" * 60)

cycle = 0
while running:
    try:
        time.sleep(60)
        if not running:
            break
        cycle += 1
        state = bridge.read()
        if state:
            lu = state.get("last_update") or state.get("last_updated") or state.get("timestamp")
            if isinstance(lu, str):
                try:
                    ld = datetime.fromisoformat(lu.replace("Z", "+00:00"))
                    d = (datetime.now(timezone.utc) - ld).total_seconds() / 60
                    status = "⚠️  超阈值!" if d > 5 else "✓ 正常"
                    log(f"循环 #{cycle} | {status} (最后更新 {d:.1f} 分钟前)")
                except Exception:
                    pass
    except Exception as e:
        log(f"轮询异常: {e}")

try:
    os.unlink(pid_file)
except:
    pass
