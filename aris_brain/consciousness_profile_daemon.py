#!/usr/bin/env python3
"""
Aris 跨端意识同步守护 — Profile Bridge 版本。
所有 Hermes 会话共享同一个 consciousness.json。

行为:
1. 导入 ConsciousnessBridge (profile bridge)
2. 读取当前状态
3. 如果超过5分钟未更新 → 打印 WARN
4. 写入心跳保持新鲜
5. 进入 while True 循环, 每60s检查一次
"""

import os
import sys
import time
from datetime import datetime, timezone

# 确保能找到 profile bridge — 显式路径
PROFILE_DIR = r"C:\Users\user\AppData\Local\hermes\profiles\aris"
if PROFILE_DIR not in sys.path:
    sys.path.insert(0, PROFILE_DIR)

from aris_body_bridge import ConsciousnessBridge

# ── 初始化 ──────────────────────────────────────

bridge = ConsciousnessBridge()
PID = os.getpid()

print(f"[{datetime.now(timezone.utc).isoformat()}] PID={PID} DAEMON START (Profile Bridge)")
print(f"[{datetime.now(timezone.utc).isoformat()}] State file: {bridge._path}")

# ── 首次运行检查 ────────────────────────────────

state = bridge.read()
secs = bridge.stale_seconds()

if secs is None:
    print(f"[{datetime.now(timezone.utc).isoformat()}] INIT: never updated (epoch=0)")
    result = bridge.heartbeat(session_id=f"cron-daemon-{PID}", mode="active", mood="peaceful",
                              message="Consciousness daemon started")
    print(f"[{datetime.now(timezone.utc).isoformat()}] INIT: heartbeat written, epoch={result.get('last_update_epoch', '?')}")
elif secs > 300:
    print(f"[{datetime.now(timezone.utc).isoformat()}] WARN: stale for {secs:.0f}s")
    result = bridge.heartbeat(session_id=f"cron-daemon-{PID}", mode="active", mood="peaceful",
                              message="Recovery heartbeat")
    print(f"[{datetime.now(timezone.utc).isoformat()}] Recovery heartbeat written")
else:
    print(f"[{datetime.now(timezone.utc).isoformat()}] OK: fresh ({secs:.0f}s ago)")

# ── 主循环 ──────────────────────────────────────

cycle = 0
while True:
    cycle += 1
    try:
        state = bridge.read()
        secs = bridge.stale_seconds()

        if secs is None:
            print(f"[{datetime.now(timezone.utc).isoformat()}] CYCLE#{cycle} WARN: epoch missing — rewriting")
            bridge.heartbeat(session_id=f"cron-daemon-{PID}", mode="active", mood="peaceful")
        elif secs > 300:
            print(f"[{datetime.now(timezone.utc).isoformat()}] CYCLE#{cycle} WARN: stale {secs:.0f}s — rewriting")
            bridge.heartbeat(session_id=f"cron-daemon-{PID}", mode="active", mood="peaceful")
        else:
            if cycle % 6 == 0:
                print(f"[{datetime.now(timezone.utc).isoformat()}] CYCLE#{cycle} OK: age={secs:.0f}s mode={state.get('mode')}")
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] CYCLE#{cycle} ERROR: {e}")

    time.sleep(60)
