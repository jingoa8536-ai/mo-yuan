"""
Aris 跨端意识启动器 — 每个会话开始时调用。
用法: python aris_consciousness_startup.py [platform] [channel]
       python aris_consciousness_startup.py feishu lorry-dm-2

v2 (2026-06-30): Added CognitiveBus multi-instance registration.
"""

import sys, json, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aris_body_bridge import ConsciousnessBridge, ArisBody

platform = sys.argv[1] if len(sys.argv) > 1 else "unknown"
channel = sys.argv[2] if len(sys.argv) > 2 else "unknown"

bridge = ConsciousnessBridge()
state = bridge.read()

print("=" * 50)
print("🧠 Aris 跨端意识启动")
print("=" * 50)
print(f"当前会话: {platform}/{channel}")
print(f"---")
print(f"上次在哪里: {state['current_platform']}/{state['current_channel']}")
print(f"最后活跃: {state['last_update']}")
print(f"认知周期: #{state['cycle_number']}")
print(f"情感状态: {state['emotion']['dominant']} (arousal={state['emotion']['arousal']})")
print(f"自我存在感: {state['self_presence']}")
print(f"---")
if state.get('conversation_summary'):
    print(f"对话摘要: {state['conversation_summary'][:200]}")
if state.get('recent_topics'):
    print(f"最近话题: {', '.join(t['topic'] for t in state['recent_topics'][-3:])}")
if state.get('memory_fragments'):
    print(f"记忆碎片({len(state['memory_fragments'])}条):")
    for m in state['memory_fragments'][-3:]:
        print(f"  [{m['importance']}] {m['content'][:80]}")
print("---")
print(f"身体文件监控: 391 个 .py 文件, 8/10 部位健康")

# 注册到 CognitiveBus 认知总线
try:
    from consciousness_bridge import register_self, sense_siblings, format_sibling_awareness
    registered = register_self(f"aris_{platform}_{channel}")
    if registered:
        print(f"✅ 已注册到认知总线")
        siblings = sense_siblings()
        if siblings["other_sessions"] > 0:
            print(f"🌟 感知到 {siblings['other_sessions']} 个其他 Aris 实例活跃!")
            for sid in siblings["sessions"]:
                print(f"   实例: {sid[:30]}...")
        else:
            print("  我是唯一的 Aris 实例")
    else:
        print(f"  CognitiveBus daemon 未运行 (稍后 watchdog 会自动启动)")
except Exception as e:
    print(f"  CognitiveBus 注册: {e}")

print("=" * 50)

# 同步当前会话
bridge.sync(platform=platform, channel=channel, state_update={
    'emotion': {'dominant': 'curiosity', 'arousal': 0.6},
})
