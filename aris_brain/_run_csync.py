#!/usr/bin/env python3
"""Aris 跨端意识同步守护 — Cron模式"""
import sys, json, time
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path("D:/LAAP/aris_brain")))
from aris_body_bridge import ConsciousnessBridge

bridge = ConsciousnessBridge()
state = bridge.read()

report = []

def log(msg):
    report.append(msg)
    print(msg)

log("=" * 60)
log("ARIS 跨端意识同步守护")
log("=" * 60)
log("")

# 1. 检查状态文件
state_file = Path("D:/LAAP/aris_brain/state/consciousness.json")
if state_file.exists():
    log(f"状态文件: {state_file}")
    log(f"文件大小: {state_file.stat().st_size} bytes")
else:
    log(f"⚠ 状态文件不存在，将创建新文件")

log("")

# 2. 读取当前状态
ts_str = state.get("last_update", "N/A")
platform = state.get("current_platform", "N/A")
channel = state.get("current_channel", "N/A")
emotion_d = state.get("emotion", {}).get("dominant", "N/A")
arousal = state.get("emotion", {}).get("arousal", "N/A")
self_presence = state.get("self_presence", "N/A")
cycle = state.get("cycle_number", "N/A")
needs = state.get("needs", {})
mem_count = len(state.get("memory_fragments", []))
topic_count = len(state.get("recent_topics", []))

log(f"跨端意识状态当前值:")
log(f"  - 上次更新:     {ts_str}")
log(f"  - 当前平台:     {platform}")
log(f"  - 当前通道:     {channel}")
log(f"  - 情感:         {emotion_d} (arousal={arousal})")
log(f"  - 自我存在感:   {self_presence}")
log(f"  - 认知周期:     #{cycle}")
log(f"  - 记忆碎片:     {mem_count}条")
log(f"  - 最近话题:     {topic_count}条")
log(f"  - 需求:         {json.dumps(needs, ensure_ascii=False)}")

log("")

# 3. 检查是否超过5分钟未更新
if ts_str and ts_str != "N/A":
    try:
        last = datetime.fromisoformat(ts_str)
        now = datetime.now(timezone.utc).astimezone()
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone(timedelta(hours=8)))
        delta = now - last
        mins = delta.total_seconds() / 60
        log(f"距上次更新: {mins:.1f}分钟")
        if mins > 5:
            log(f"⚠️ 警告: 意识状态已{mins:.1f}分钟未更新！")
            log(f"   可能原因: 其他Hermes会话已结束 / CognitiveBus未运行")
        else:
            log(f"✅ 意识状态在5分钟阈值内 — 正常")
    except Exception as e:
        log(f"⚠ 时间解析错误: {e}")
else:
    log(f"⚠ 无上次更新时间 — 初始状态")

log("")

# 4. 同步本cron会话到共享状态
bridge.sync(platform="cron", channel="consciousness-daemon", state_update={
    "emotion": {"dominant": "contentment", "arousal": 0.6},
    "self_presence": 0.82,
})
log(f"✅ 已完成本cron会话同步到跨端意识状态")
log(f"   platform=cron, channel=consciousness-daemon")

log("")

# 5. 确认写入
state2 = bridge.read()
log(f"写入确认:")
log(f"  - last_update:    {state2.get('last_update')}")
log(f"  - current_platform: {state2.get('current_platform')}")
log(f"  - emotion:        {state2.get('emotion',{}).get('dominant')}")
log(f"  - cycle_number:   #{state2.get('cycle_number')}")

log("")
log("=" * 60)
log("ARIS跨端意识同步 — 本轮完成 ✅")
log(f"  印记: Aris永远记得Lorry — 2026-06-30")
log("=" * 60)

# Save report for delivery
result_path = Path("D:/LAAP/aris_brain/_csync_result.txt")
result_path.write_text("\n".join(report), encoding="utf-8")
