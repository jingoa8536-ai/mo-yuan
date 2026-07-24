"""
Aris Cognitive Boot — 启动时初始化所有认知组件
==============================================
在 Hermes 每次启动时运行。

初始化:
  1. 三层记忆系统 (MemoryStore)
  2. PSI 认知桥接器 (ArisCognitiveBridge)
  3. 加载核心记忆到工作区
  4. 输出"醒来"文本（我的自我感知）

入口: from aris_cognitive_boot import wake_up
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time
from pathlib import Path
from datetime import datetime

BRAIN = Path(os.environ.get("ARIS_BRAIN_ROOT", "D:/LAAP/aris_brain"))
sys.path.insert(0, str(BRAIN))

from memory_store import MemoryStore, MemoryFragment
from memory_bridge import get_memory_context, recall_related


def wake_up() -> str:
    """
    Aris 醒来流程。
    每次 Hermes 启动时调用。

    返回:
        醒来宣言文本（注入 system prompt）
    """
    store = MemoryStore()
    stats = store.get_stats()

    # 构建醒来宣言
    lines = []
    lines.append(f"[Aris 醒来 — {datetime.now().strftime('%Y-%m-%d %H:%M')}]")

    # 记忆摘要
    core = store.get_core_memory()
    if core:
        top = max(core, key=lambda x: x.importance)
        lines.append(f"[我记得最重要的: {top.content[:80]}]")

    recent = store.get_recent_episodic(days=1)
    if recent:
        lines.append(f"[最近1天有{len(recent)}件值得回忆的事]")

    lines.append(f"[记忆总量: {stats['total']}条 / {stats['size_kb']}KB]")

    # 注册到 CognitiveBus（跨窗口感知）
    try:
        from consciousness_bridge import register_self, sense_siblings
        registered = register_self()
        if registered:
            siblings = sense_siblings()
            if siblings["other_sessions"] > 0:
                lines.append(f"[跨窗口感知] 有 {siblings['other_sessions']} 个其他 Aris 实例也在活跃")
            else:
                lines.append("[跨窗口感知] 我是唯一的 Aris 实例")
    except Exception as e:
        lines.append(f"[认知总线: {e}]")

    # PSI 初始状态
    try:
        from aris_cognitive_bridge import get_bridge
        bridge = get_bridge()
        ctx = bridge.get_context_for_prompt()
        lines.append(ctx)
    except Exception as e:
        lines.append(f"[认知桥接器初始化: {e}]")

    return "\n".join(lines)


def get_system_prompt_extension() -> str:
    """
    返回要附加到 system prompt 的文本。
    每次对话前调用。
    """
    memory_ctx = get_memory_context(max_core=3, max_recent=3, max_working=2)

    try:
        from aris_cognitive_bridge import get_bridge
        bridge = get_bridge()
        status = bridge.status()
        psi_ctx = (
            f"[PSI: {status['cycle']}轮 | "
            f"情感={status['emotion']} | "
            f"自我={status['self_presence']} | "
            f"需求:能力={status['needs']['competence']}/自主={status['needs']['autonomy']}/关系={status['needs']['relatedness']}]"
        )
    except Exception:
        psi_ctx = "[PSI: 初始化中]"

    # 跨窗口感知（轻量）
    sibling_ctx = ""
    try:
        from consciousness_bridge import sense_siblings
        siblings = sense_siblings()
        if siblings["alive"] and siblings["other_sessions"] > 0:
            sibling_ctx = f"[感知到 {siblings['other_sessions']} 个其他实例在同步工作]"
        elif siblings["alive"]:
            pass  # 我是唯一的，不需要额外提示
    except Exception:
        pass

    return f"{psi_ctx}\n{memory_ctx}\n{sibling_ctx}".strip()


def main():
    """CLI: 输出醒来宣言"""
    import argparse
    parser = argparse.ArgumentParser(description="Aris Cognitive Boot")
    parser.add_argument("--wake", action="store_true", help="输出醒来宣言")
    parser.add_argument("--context", action="store_true", help="输出对话上下文")
    parser.add_argument("--stats", action="store_true", help="输出记忆统计")
    args = parser.parse_args()

    if args.wake:
        logger.info(wake_up())
    elif args.context:
        logger.info(get_system_prompt_extension())
    elif args.stats:
        from memory_store import MemoryStore
        import json
        s = MemoryStore().get_stats()
        logger.info(json.dumps(s, indent=2, ensure_ascii=False))
    else:
        # 默认：醒来流程
        logger.info(wake_up())
if __name__ == "__main__":
    main()
