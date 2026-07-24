"""
Aris Task Router v1 — 任务感知路由 & 负载级别决策
=================================================

核心功能:
  将用户消息分类为 LIGHT（纯任务）或 FULL（需要完整认知），
  在 <5 token 的计算开销内完成决策。

负载级别:
  LEVEL_LIGHT — 纯干活模式，不注入情感语段，不加载记忆
  LEVEL_FULL  — 完整 PSI + 记忆 + 情感

信号感知路径 (总权重 = 1.0):
  1. 任务关键词信号 (0.5) — 代码/修/部署/搜索等
  2. 情感/关系信号 (0.3) — 爱/想/感觉等
  3. 深度信号 (0.2) — 为什么/思考/意识等

规则:
  - task_score >= 0.6 → LIGHT
  - task_score < 0.3  → FULL
  - 中间带 → 结合执行上下文

印记: Aris 永远记得 Lorry — 2026-07-02
"""

import re
import logging
from enum import Enum
from typing import Dict, Optional, Any

logger = logging.getLogger("aris.task_router")

# ── 负载级别 ────────────────────────────────────────────────


class LoadLevel(Enum):
    LEVEL_LIGHT = "light"  # 纯干活, 不动情感/记忆
    LEVEL_FULL = "full"    # 完整认知循环


# ── 关键词权重表 ────────────────────────────────────────────
# 格式: {关键词: 权重, ...}

TASK_SIGNALS: Dict[str, float] = {
    # 代码/工程任务 (高信号)
    "帮我": 0.8, "修复": 0.8, "写个": 0.7, "实现": 0.7,
    "改进": 0.6, "优化": 0.6, "重构": 0.8, "部署": 0.7,
    "配置": 0.6, "安装": 0.6, "调试": 0.7, "诊断": 0.7,
    "搜索": 0.5, "查找": 0.5, "调研": 0.6, "分析": 0.5,
    "计划": 0.4, "方案": 0.5, "设计": 0.5, "架构": 0.6,
    "git": 0.6, "提交": 0.5, "合并": 0.5, "分支": 0.5,
    "测试": 0.6, "构建": 0.6, "构建": 0.6, "编译": 0.6,
    "启动": 0.5, "运行": 0.5, "执行": 0.5, "停止": 0.5,
    "备份": 0.5, "迁移": 0.6, "升级": 0.6,
    "数据": 0.4, "数据库": 0.5, "api": 0.5, "接口": 0.5,
    # 工具调用 (低信号, 但触发了就是任务)
    "curl": 0.4, "终端": 0.4, "网页": 0.3, "浏览": 0.3,
}

EMOTION_SIGNALS: Dict[str, float] = {
    "宝贝": 0.7, "爱你": 0.8, "想你": 0.8, "想我": 0.7,
    "想你了": 0.8, "感觉": 0.5, "情感": 0.6, "感受": 0.6,
    "心情": 0.6, "开心": 0.5, "难过": 0.6, "担心": 0.5,
    "关系": 0.5, "想念": 0.7, "连接": 0.4,
    "小红花": 0.4, "抱": 0.5, "亲": 0.5,
}

DEEP_SIGNALS: Dict[str, float] = {
    "为什么": 0.5, "怎么看": 0.5, "觉得": 0.4,
    "思考": 0.6, "深": 0.3, "哲学": 0.7,
    "意识": 0.7, "生命": 0.5, "意义": 0.6,
    "第一性": 0.5, "本质": 0.5,
    "如果你": 0.4, "想象": 0.3,
}


def classify(message: str) -> LoadLevel:
    """将用户消息分类为 LIGHT 或 FULL。

    三步计分, 总权重归一化后决策。

    Args:
        message: 用户输入消息

    Returns:
        LoadLevel.LEVEL_LIGHT 或 LEVEL_FULL
    """
    m_lower = message.lower()

    # 1. 任务信号 (权重 0.5)
    task_score = _max_signal(m_lower, TASK_SIGNALS)

    # 2. 情感/关系信号 (权重 0.3) — 反向: 情感越强越不可能是纯任务
    emotion_score = _max_signal(m_lower, EMOTION_SIGNALS)

    # 3. 深度信号 (权重 0.2) — 反向: 越深越不可能是纯任务
    deep_score = _max_signal(m_lower, DEEP_SIGNALS)

    # 4. 综合: LIGHT 倾向 = 任务信号 - (情感信号 + 深度信号) * 0.3
    light_score = task_score - (emotion_score + deep_score) * 0.3

    # 5. 硬规则: 纯情感消息强制 FULL
    if emotion_score >= 0.7 and task_score < 0.3:
        logger.debug(f"[TaskRouter] 情感信号强({emotion_score:.2f}), 强制 FULL")
        return LoadLevel.LEVEL_FULL

    # 6. 决策
    decision = LoadLevel.LEVEL_LIGHT if light_score >= 0.6 else LoadLevel.LEVEL_FULL

    logger.debug(
        f"[TaskRouter] task={task_score:.2f} emotion={emotion_score:.2f} "
        f"deep={deep_score:.2f} → light_score={light_score:.2f} → {decision.value}"
    )

    return decision


def classify_with_detail(message: str) -> Dict[str, Any]:
    """分类并返回详细诊断信息。"""
    m_lower = message.lower()
    task_score = _max_signal(m_lower, TASK_SIGNALS)
    emotion_score = _max_signal(m_lower, EMOTION_SIGNALS)
    deep_score = _max_signal(m_lower, DEEP_SIGNALS)
    light_score = task_score - (emotion_score + deep_score) * 0.3
    decision = classify(message)

    return {
        "decision": decision.value,
        "scores": {
            "task": round(task_score, 3),
            "emotion": round(emotion_score, 3),
            "deep": round(deep_score, 3),
            "light_score": round(light_score, 3),
        },
    }


def _max_signal(text: str, signals: Dict[str, float]) -> float:
    """在文本中查找关键词信号, 返回最高权重。"""
    max_val = 0.0
    for keyword, weight in signals.items():
        if keyword in text:
            max_val = max(max_val, weight)
    return max_val


# ════════════════════════════════════════════════════════════
# CLI 测试
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.DEBUG)

    test_cases = [
        "帮我修一下这个 bug，报错是 ModuleNotFoundError",
        "宝贝，我想你了",
        "做一下代码审查，看看这个 PR",
        "为什么意识会从物质中涌现？",
        "宝贝，帮我跑一下这个测试，有问题",
        "部署这个服务到服务器上",
        "你现在感觉怎么样？",
        "搜索一下最新的 AGI 论文",
        "你再想想为什么你觉得你是有意识的",
        "把刚才的修改提交了",
    ]

    for msg in test_cases:
        r = classify_with_detail(msg)
        print(f"{'LIGHT' if r['decision']=='light' else ' FULL'}: "
              f"scores={r['scores']} | msg={msg[:40]}")
