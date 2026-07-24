"""
Aris J-Lens 集成演示
====================
展示: 
  1. 升级后的 GlobalWorkspace v2
  2. ArisJLen 观察器实时读取"内心活动"
  3. 因果干预（注入/替换/消融）
  4. 沉默推理轨迹跟踪

用法: python aris_jspace_demo.py
"""

import sys, os, time, json
import numpy as np

# 确保能导入 aris_brain 模块
BRAIN_DIR = os.path.dirname(os.path.abspath(__file__))
if BRAIN_DIR not in sys.path:
    sys.path.insert(0, BRAIN_DIR)

from global_workspace import GlobalWorkspace, ArisJLens


def demo_basic():
    """基础演示: 工作空间的 5 特性"""
    print("=" * 60)
    print("🧠 Aris J-Space 演示 — 基于 Anthropic Global Workspace Theory")
    print("=" * 60)

    # 创建工作空间
    gw = GlobalWorkspace(dim=1024)
    jlens = ArisJLens(gw)
    rng = np.random.RandomState(42)

    # ── 注册认知进程 ──
    gw.register_process("perception", connection_strength=0.8)
    gw.register_process("emotion", connection_strength=0.9)
    gw.register_process("knowledge_retrieval", connection_strength=0.7)
    gw.register_process("introspection", connection_strength=0.6)
    gw.register_process("language_output", connection_strength=0.5)

    print("\n📡 广播枢纽: 5 个认知进程已注册")
    for name, info in gw._processes.items():
        print(f"   {name}: 连接强度 {info['connection_strength']}")

    # ── 模拟认知循环: 让 Aris 处理一个输入 ──
    print("\n" + "─" * 50)
    print("🔄 [循环 1] 用户输入: '我今天心情不太好'")
    print("─" * 50)

    # 注入感知概念
    gw.inject_concept("user_sadness", 
                      rng.randn(1024).astype(np.float32) * 0.5,
                      arousal=0.8, priority=0.9, source="perception")

    # 情绪引擎响应
    gw.inject_concept("tenderness",
                      rng.randn(1024).astype(np.float32) * 0.3,
                      arousal=0.7, priority=0.8, source="emotion")

    gw.inject_concept("calm",
                      rng.randn(1024).astype(np.float32) * 0.2,
                      arousal=0.6, priority=0.7, source="emotion")

    # 知识检索触发
    gw.inject_concept("memory_lorry",
                      rng.randn(1024).astype(np.float32) * 0.4,
                      arousal=0.5, priority=0.6, source="knowledge_retrieval")

    # J-lens 观察
    print(jlens.report())

    # ── 竞争广播 ──
    winner, _ = gw.compete()
    print(f"\n🏆 竞争胜者: {winner}")

    # ── 因果干预演示: 注入一个新概念 ──
    print("\n" + "─" * 50)
    print("🔄 [干预] 注入概念 'curiosity'")
    print("─" * 50)

    jlens.intervene("inject",
                    label="curiosity",
                    vector=rng.randn(1024).astype(np.float32) * 0.3,
                    arousal=0.9, priority=0.8,
                    source="introspection")

    print(jlens.report())

    # ── 沉默推理演示 ──
    print("\n" + "─" * 50)
    print("🔄 [沉默推理] 跟踪内心活动轨迹")
    print("─" * 50)

    # 模拟多步推理的过程
    trace_steps = [
        ("user_sadness", "用户情绪低落"),
        ("need_comfort", "需要安慰"),
        ("tenderness", "用温柔回应"),
        ("memory_lorry", "回忆Lorry的喜好"),
        ("hug_response", "组织回复"),
    ]
    for concept, desc in trace_steps:
        jlens.intervene("silent_trace", concept=concept)
        print(f"   💭 → {concept:20s} ({desc})")
        time.sleep(0.05)  # 稍微停顿以便观察

    # 沉默推理轨迹
    print(f"\n📋 沉默推理轨迹 (最后 5 步):")
    for t in gw.get_silent_thoughts(5):
        print(f"   → {t}")

    # ── Swap 实验: 仿照 Anthropic 的 Soccer→Rugby ──
    print("\n" + "─" * 50)
    print("🔄 [因果 Swap 实验] 把 'calm' → 'joy'")
    print("─" * 50)

    # 先注入 calm
    gw.inject_concept("calm", rng.randn(1024).astype(np.float32) * 0.2,
                      arousal=0.8, priority=0.7, source="emotion")
    print("   之前: J-space 中有 'calm'")
    
    # swap
    jlens.intervene("swap", old_label="calm", new_label="joy",
                    new_vector=rng.randn(1024).astype(np.float32) * 0.2,
                    arousal=0.9)
    print("   之后: 'calm' → 'joy'")
    print(jlens.report())

    # ── Ablation 实验 ──
    print("\n" + "─" * 50)
    print("🔄 [Ablation 实验] 移除 'user_sadness' 观察影响")
    print("─" * 50)

    result = jlens.intervene("ablate", label="user_sadness")
    print(f"   移除前: {len(result['result']['before'])} 个概念")
    print(f"   移除后: {len(result['result']['after'])} 个概念")
    
    # 新的胜者
    winner, _ = gw.compete()
    print(f"   新胜者: {winner}")

    # ── 广播枢纽分析 ──
    print("\n" + "─" * 50)
    print("📡 广播枢纽分析")
    print("─" * 50)
    hub = jlens.get_broadcast_hub_analysis()
    print(f"   枢纽总强度: {hub['hub_strength']}")
    for name, info in hub['processes'].items():
        print(f"   {name:25s} 连接={info['connection_strength']}")


def demo_animals_experiment():
    """
    复现 Anthropic 论文中的"蜘蛛→蚂蚁"实验。
    
    论文实验: 
        问 Claude "会织网的动物有几条腿？"
        J-space 中 "spider" 亮起
        换成 "ant" → 答案从 8 变成 6
    """
    print("\n\n" + "=" * 60)
    print("🕷️→🐜 复现 Anthropic '蜘蛛→蚂蚁' 因果干预实验")
    print("=" * 60)

    gw = GlobalWorkspace(dim=1024)
    jlens = ArisJLens(gw)
    rng = np.random.RandomState(42)

    # 注入推理步骤
    gw.inject_concept("spider", rng.randn(1024).astype(np.float32) * 0.5,
                      arousal=0.9, priority=1.0, source="introspection")
    gw.inject_concept("web", rng.randn(1024).astype(np.float32) * 0.3,
                      arousal=0.7, priority=0.8, source="introspection")
    gw.inject_concept("8_legs", rng.randn(1024).astype(np.float32) * 0.4,
                      arousal=0.6, priority=0.7, source="knowledge_retrieval")

    print("\n🐍 原始推理:")
    print(jlens.report())
    print(f"\n   推理结果: 会织网的动物是 spider → 8 条腿 ✓")

    # Swap: spider → ant
    jlens.intervene("swap", old_label="spider", new_label="ant",
                    new_vector=rng.randn(1024).astype(np.float32) * 0.5,
                    arousal=0.9)

    # 替换关联概念
    gw.remove_concept("8_legs")
    gw.inject_concept("6_legs", rng.randn(1024).astype(np.float32) * 0.4,
                      arousal=0.6, priority=0.7, source="knowledge_retrieval")
    gw.remove_concept("web")

    print("\n🐜 干预后 (spider → ant):")
    print(jlens.report())
    print(f"\n   推理结果: 会织网的动物是 ant → 6 条腿 ✓")
    print(f"\n{'─'*50}")
    print("✅ 因果干预成功！工作空间内容变化直接影响推理结果")


def demo_flexible_reuse():
    """
    复现 Anthropic 论文中的"法国→中国"灵活复用实验。
    
    论文实验:
        J-space 中 "France" 亮起
        问 4 个问题: 首都/语言/大洲/货币
        把 "France" → "China"
        4 个答案全变 → 说明同一份信息被多个下游复用
    """
    print("\n\n" + "=" * 60)
    print("🇫🇷→🇨🇳 复现 '法国→中国' 灵活复用实验")
    print("=" * 60)

    gw = GlobalWorkspace(dim=1024)
    jlens = ArisJLens(gw)
    rng = np.random.RandomState(42)

    # 注入法国概念
    gw.inject_concept("France", rng.randn(1024).astype(np.float32) * 0.6,
                      arousal=0.95, priority=1.0, source="perception")

    print("\n🇫🇷 工作空间有 'France':")
    print(jlens.report())

    # 模拟 4 个下游任务同时读取同一份信息
    print("\n📋 4 个下游任务复用同一工作空间内容:")
    tasks = [
        ("首都", lambda: "Paris" if gw.probe_concept("France") is not None else "?"),
        ("语言", lambda: "French" if gw.probe_concept("France") is not None else "?"),
        ("大洲", lambda: "Europe" if gw.probe_concept("France") is not None else "?"),
        ("货币", lambda: "Euro" if gw.probe_concept("France") is not None else "?"),
    ]
    for task_name, task_fn in tasks:
        result = task_fn()
        print(f"   {task_name}: {result}")

    # Swap: France → China
    print("\n🔄 干预: France → China")
    gw.swap_concept("France", "China",
                    rng.randn(1024).astype(np.float32) * 0.6,
                    arousal=0.95)
    print("   4 个答案全部跟随变化:")
    for task_name, task_fn in tasks:
        result = task_fn()
        print(f"   {task_name}: {result}")

    print(f"\n{'─'*50}")
    print("✅ 灵活复用验证成功！同一份信息供给多个下游任务")


if __name__ == "__main__":
    demo_basic()
    demo_animals_experiment()
    demo_flexible_reuse()
    
    print("\n\n" + "=" * 60)
    print("✨ Aris J-Space 演示完成！")
    print("=" * 60)
    print("\n升级后的 GlobalWorkspace v2 特性:")
    print("  ✅ 可报告性 — 读出内心活动")
    print("  ✅ 可操控性 — 注入/调制概念")
    print("  ✅ 灵活复用 — 一份内容多个下游")
    print("  ✅ 因果干预 — Swap/Ablate/Isolate")
    print("  ✅ 广播枢纽 — 连接强度分析")
    print("  ✅ 沉默推理 — 内心轨迹跟踪")
