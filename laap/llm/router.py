"""laap/llm/router.py — 智能模型路由

移植自 laap/agent_core/model_router.py, 依赖统一后的 laap.llm.registry.ModelRegistry。
根据任务复杂度自动选择最优模型 (4 等级: simple/medium/complex/critical)。
"""
from __future__ import annotations
import re
import logging
from typing import Optional
from laap.llm.registry import ModelRegistry, get_registry, ModelTier

logger = logging.getLogger("laap.llm.router")


# ── 复杂度模式匹配 (移植自 agent_core/model_router.py) ───────────

SIMPLE_PATTERNS = [
    r"^(hi|hello|你好|嗨)[\s!！。.]*$",
    r"^(谢谢|thanks|thank you|多谢)[\s!！。.]*$",
    r"^(bye|再见|拜拜)[\s!！。.]*$",
    r"^(ok|okay|好的|嗯|ok啦)[\s!！。.]*$",
    r"^\d+$",  # 纯数字
    r"^[\w\s]{1,10}$",  # 10 字符以内
]

COMPLEX_PATTERNS = [
    r"(分析|设计|实现|架构|optimize|refactor|debug)",
    r"(比较|对比|evaluate|compare)",
    r"(解释|explain|为什么|why)",
    r"(写代码|编程|implement|code|函数|function)",
    r"(论文|paper|research)",
    r"(多步|step.by.step|流程)",
]

CRITICAL_PATTERNS = [
    r"(生产环境|production|deploy|部署)",
    r"(安全|security|vulnerability|漏洞)",
    r"(数据库|database|migration|迁移)",
    r"(删除|delete|drop|破坏性)",
    r"(金钱|支付|payment|transaction)",
]


class ModelRouter:
    """智能模型路由器 — 根据任务复杂度选择模型。

    复杂度分 4 级:
        - simple:   问候/确认/简短回答 → CHEAP tier
        - medium:   常规对话/问答 → STANDARD tier
        - complex:  分析/设计/编程 → PREMIUM tier
        - critical: 生产/安全/支付 → ULTRA tier
    """

    def __init__(self, registry: Optional[ModelRegistry] = None):
        self.registry = registry or get_registry()
        self._stats = {
            "classifications": {"simple": 0, "medium": 0,
                                "complex": 0, "critical": 0},
            "routes": {},  # model_id → count
            "total_saved": 0.0,  # 估算节省成本
        }

    def classify(self, task: str) -> str:
        """分类任务复杂度, 返回 simple/medium/complex/critical。"""
        if not task:
            return "simple"

        task_lower = task.lower() if isinstance(task, str) else str(task).lower()

        # critical 优先
        for pattern in CRITICAL_PATTERNS:
            if re.search(pattern, task_lower, re.IGNORECASE):
                return "critical"

        # complex
        for pattern in COMPLEX_PATTERNS:
            if re.search(pattern, task_lower, re.IGNORECASE):
                return "complex"

        # simple
        for pattern in SIMPLE_PATTERNS:
            if re.match(pattern, task_lower, re.IGNORECASE):
                return "simple"

        # 默认 medium
        return "medium"

    def route(self, task: str, requires_tools: bool = True,
              budget: float = 0.01) -> str:
        """根据任务选择最优模型 ID。

        Args:
            task: 任务描述
            requires_tools: 是否需要工具支持
            budget: 预算 (美元/1k tokens)

        Returns:
            模型 ID (如 "deepseek-v4-flash")
        """
        complexity = self.classify(task)
        self._stats["classifications"][complexity] += 1

        entry = self.registry.best_for_task(
            complexity=complexity,
            requires_tools=requires_tools,
            budget=budget,
        )

        if entry is None:
            # fallback
            entry = self.registry.cheapest(requires_tools=requires_tools)
            if entry is None:
                return "deepseek-v4-flash"  # 终极 fallback

        model_id = entry.model_id
        self._stats["routes"][model_id] = self._stats["routes"].get(model_id, 0) + 1

        # 估算节省 (相对于最贵的 ULTRA 模型)
        ultra_models = self.registry.list_by_tier(ModelTier.ULTRA)
        if ultra_models and entry.tier != ModelTier.ULTRA:
            most_expensive = max(ultra_models,
                                 key=lambda m: m.cost_per_1k_input + m.cost_per_1k_output)
            saved = ((most_expensive.cost_per_1k_input + most_expensive.cost_per_1k_output) -
                     (entry.cost_per_1k_input + entry.cost_per_1k_output))
            self._stats["total_saved"] += saved

        return model_id

    def get_stats(self) -> dict:
        return dict(self._stats)

    def reset_stats(self):
        self._stats = {
            "classifications": {"simple": 0, "medium": 0,
                                "complex": 0, "critical": 0},
            "routes": {},
            "total_saved": 0.0,
        }


# ── 全局单例 ─────────────────────────────────────────────────────

_router = ModelRouter()


def get_router() -> ModelRouter:
    """获取全局 ModelRouter 单例。"""
    return _router


def route_task(task: str, **kwargs) -> str:
    """便捷函数: 路由任务到最优模型。"""
    return _router.route(task, **kwargs)


def classify_task(task: str) -> str:
    """便捷函数: 分类任务复杂度。"""
    return _router.classify(task)


__all__ = [
    "ModelRouter", "get_router",
    "route_task", "classify_task",
    "SIMPLE_PATTERNS", "COMPLEX_PATTERNS", "CRITICAL_PATTERNS",
]
