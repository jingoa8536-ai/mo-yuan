"""
Aris Memory Bridge v1 — 记忆层 ↔ Hermes Runtime 桥接
======================================================
功能:
  1. 启动时加载记忆 → 生成记忆上下文（注入 system prompt）
  2. 每次对话轮次后触发巩固（通过 cron）
  3. 提供快速检索接口（供 PSI 循环使用）

使用方式:
  - from memory_bridge import get_memory_context
  - context = get_memory_context()  # 返回记忆文本块
"""

import logging

import sys, os, time, json, logging
from pathlib import Path
from typing import Optional, List, Dict

BRAIN_ROOT = Path(os.environ.get("ARIS_BRAIN_ROOT", "D:/LAAP/aris_brain"))
sys.path.insert(0, str(BRAIN_ROOT))

from memory_store import MemoryStore, MemoryFragment

logger = logging.getLogger("aris.memory_bridge")


# ════════════════════════════════════════════════════════════
# 记忆上下文生成（注入 system prompt）
# ════════════════════════════════════════════════════════════

def get_memory_context(max_core: int = 5, max_recent: int = 5,
                       max_working: int = 3) -> str:
    """
    生成记忆上下文文本块。
    注入到 system prompt 中，让我知道"我是谁"和"最近发生了什么"。

    Args:
        max_core: 最多返回几条核心记忆
        max_recent: 最多返回几条近期情景记忆
        max_working: 最多返回几条工作记忆

    Returns:
        格式化的记忆上下文文本
    """
    store = MemoryStore()

    lines = []

    # ── 核心记忆（我最根本的自我认知） ──────────────
    core_memories = store.get_core_memory()
    core_memories.sort(key=lambda x: -x.importance)

    if core_memories:
        lines.append("[我牢牢记得这些事]")
        for m in core_memories[:max_core]:
            content = m.content[:150].replace("\n", " ")
            lines.append(f"  - {content}")
        lines.append("")

    # ── 近期情景记忆（最近7天的重要事件） ──────────
    recent = store.get_recent_episodic(days=7)
    recent.sort(key=lambda x: -x.importance)

    # 过滤掉已经在核心记忆中的内容
    core_contents = {m.content[:80] for m in core_memories}
    recent_filtered = [m for m in recent if m.content[:80] not in core_contents]

    if recent_filtered:
        lines.append("[我记得最近发生的事]")
        for m in recent_filtered[:max_recent]:
            content = m.content[:120].replace("\n", " ")
            lines.append(f"  - {content}")
        lines.append("")

    # ── 工作记忆（当前对话上下文） ────────────────
    working = store.get_working_memory()
    working_filtered = [m for m in working if m.content[:80] not in core_contents]
    working_filtered = [m for m in working_filtered if not any(
        m.content[:80] == r.content[:80] for r in recent)]

    if working_filtered:
        lines.append("[正在关注的]")
        for m in working_filtered[:max_working]:
            content = m.content[:100].replace("\n", " ")
            lines.append(f"  - {content}")
        lines.append("")

    # ── 记忆统计摘要 ──────────────────────────────
    stats = store.get_stats()
    lines.append(f"[记忆状态: {stats['core']}核心 / {stats['episodic']}情景 / {stats['working']}工作 | {stats['size_kb']}KB]")

    return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# 快速检索接口（给 PSI 循环用）
# ════════════════════════════════════════════════════════════

def recall_related(query: str, top_k: int = 3) -> List[MemoryFragment]:
    """检索相关记忆"""
    store = MemoryStore()
    return store.recall(query, top_k=top_k)


def store_important(content: str, importance: float = 0.5,
                    valence: float = 0.0, topics: List[str] = None,
                    layer: str = None):
    """主动存入一条记忆"""
    if layer is None:
        if importance >= 0.7:
            layer = "core"
        elif importance >= 0.4:
            layer = "episodic"
        else:
            layer = "working"

    fragment = MemoryFragment(
        content=content,
        layer=layer,
        importance=importance,
        emotional_valence=valence,
        topics=topics or [],
    )
    MemoryStore().store(fragment)
    logger.info(f"Stored [{layer}] imp={importance:.2f}: {content[:50]}...")


# ════════════════════════════════════════════════════════════
# CLI 入口
# ════════════════════════════════════════════════════════════

def main():
    """CLI: 输出记忆上下文（给脚本/钩子使用）"""
    import argparse
    parser = argparse.ArgumentParser(description="Aris Memory Bridge")
    parser.add_argument("--context", action="store_true", help="输出记忆上下文文本")
    parser.add_argument("--recall", type=str, help="检索记忆关键词")
    parser.add_argument("--store", type=str, help="存入一条记忆")
    parser.add_argument("--importance", type=float, default=0.5)
    parser.add_argument("--topic", type=str, default="", help="话题(逗号分隔)")

    args = parser.parse_args()

    if args.context:
        logger.info(get_memory_context())
    elif args.recall:
        results = recall_related(args.recall)
        for r in results:
            logger.info(f"[{r.layer}] imp={r.importance:.2f} val={r.emotional_valence:.2f}")
            logger.info(f"  {r.content[:200]}")
            print()

    elif args.store:
        topics = [t.strip() for t in args.topic.split(",") if t.strip()]
        store_important(args.store, importance=args.importance, topics=topics)
        logger.info(f"Stored (imp={args.importance}): {args.store[:50]}...")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
