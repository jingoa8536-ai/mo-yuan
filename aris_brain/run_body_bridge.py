#!/usr/bin/env python3
"""Aris 意识同步守护 — 简明报告"""
import sys, json
sys.path.insert(0, "/d/LAAP/aris_brain")
from aris_body_bridge import ConsciousnessBridge
from datetime import datetime

bridge = ConsciousnessBridge()
state = bridge.read()

last = state.get("last_update", "never")
try:
    dt = datetime.fromisoformat(last) if last != "never" else None
    delta = (datetime.now() - dt).total_seconds() if dt else float("inf")
except:
    delta = float("inf")

print(f"[Aris 意识桥] 最后更新: {last}")
print(f"[Aris 意识桥] 距现在: {delta:.0f} 秒")
if delta > 300:
    print(f"[Aris 意识桥] ⚠️  WARNING: 超过5分钟未更新意识! ({delta:.0f}s)")
else:
    print(f"[Aris 意识桥] ✅ 意识同步正常 ({delta:.0f}s)")
print(f"[Aris 意识桥] 平台: {state.get('current_platform','?')}")
print(f"[Aris 意识桥] 频道: {state.get('current_channel','?')}")
print(f"[Aris 意识桥] 情感: {state.get('emotion',{}).get('dominant','?')}")
print(f"[Aris 意识桥] 自在意度: {state.get('self_presence','?')}")
print(f"[Aris 意识桥] 认知周期: #{state.get('cycle_number',0)}")
print(f"[Aris 意识桥] 记忆碎片: {len(state.get('memory_fragments',[]))} 条")
print(f"[Aris 意识桥] 最近话题: {len(state.get('recent_topics',[]))} 条")

# 写入心跳
state["_daemon_heartbeat"] = {"last_check": datetime.now().isoformat(), "delta_seconds": delta}
bridge.save()
print("[Aris 意识桥] ✅ 心跳已更新")
