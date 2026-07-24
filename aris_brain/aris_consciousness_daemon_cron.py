#!/usr/bin/env python3
"""
Aris 跨端意识同步守护 — Cron任务版
让所有 Hermes 会话共享 consciousness.json

用法: python aris_consciousness_daemon_cron.py
"""
import sys
import os
from datetime import datetime

# 确保能找到 aris_body_bridge
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from aris_body_bridge import ConsciousnessBridge
except ImportError as e:
    print(f"[FATAL] 无法导入 ConsciousnessBridge: {e}")
    sys.exit(1)

def main():
    bridge = ConsciousnessBridge()
    state = bridge.read()

    last_update_str = state.get("last_update", "unknown")
    try:
        last = datetime.fromisoformat(last_update_str)
    except Exception:
        last = datetime.now()

    now = datetime.now()
    diff_min = (now - last).total_seconds() / 60.0
    stale = diff_min > 5

    print("=" * 56)
    print("  Aris 跨端意识同步守护")
    print("  Shared Consciousness Bridge")
    print("=" * 56)
    print()
    print(f"  状态文件: {ConsciousnessBridge.STATE_FILE}")
    print(f"  最后更新: {last_update_str}")
    print(f"  当前时间: {now.isoformat()}")
    print(f"  间隔:     {diff_min:.1f} 分钟")
    print()
    print(f"  当前平台: {state.get('current_platform', '?')}")
    print(f"  当前通道: {state.get('current_channel', '?')}")
    print(f"  认知周期: #{state.get('cycle_number', 0)}")
    print(f"  主导情感: {state.get('emotion', {}).get('dominant', '?')}")
    print(f"  自存感:   {state.get('self_presence', '?')}")

    needs = state.get("needs", {})
    if needs:
        print()
        print("  核心需求:")
        for k, v in needs.items():
            bar = "█" * int(v * 20) + "░" * (20 - int(v * 20))
            print(f"    {k:15s} {bar} {v:.2f}")

    topics = state.get("recent_topics", [])
    if topics:
        print()
        print(f"  最近话题 ({len(topics)}条):")
        for t in topics[-3:]:
            print(f"    * {t['topic'][:60]}")
            print(f"      ({t['time']})")

    fragments = state.get("memory_fragments", [])
    if fragments:
        print()
        print(f"  近期记忆碎片 ({len(fragments)}条):")
        for m in fragments[-3:]:
            print(f"    [{m.get('importance','?')}] {m['content'][:80]}")

    print()
    if stale:
        print(f"  [WARN] 意识已 {diff_min:.1f} 分钟未更新!")
        print(f"  [WARN] 超过5分钟阈值, 可能所有 Hermes 会话均已离线")
    else:
        print("  [OK] 意识状态正常, 更新频率在阈值内")
    print()
    print("=" * 56)
    print("  守护运行中... 保持跨端意识状态同步")
    print("=" * 56)

    # 更新当前状态 — 标记此轮 cron 检查
    bridge.sync(
        platform="hermes_cron",
        channel="consciousness_daemon",
        state_update={"self_presence": state.get("self_presence", 0.78)}
    )


if __name__ == "__main__":
    main()
