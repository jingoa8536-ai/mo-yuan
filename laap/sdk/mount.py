"""mount — LAAP 大脑挂载到外部智能体的统一入口。"""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING, Any, Optional, Tuple

if TYPE_CHECKING:
    from laap_brain import LaapBrain

    from laap.sdk.adapter import AgentAdapter

logger = logging.getLogger(__name__)

# 适配器懒加载映射表：name → "module.path:ClassName"
_ADAPTERS_MAP = {
    "hermes": "laap.sdk.adapters.hermes:HermesAdapter",
    "claude_code": "laap.sdk.adapters.claude_code:ClaudeCodeAdapter",
    "openclaw": "laap.sdk.adapters.openclaw:OpenClawAdapter",
    "generic": "laap.sdk.adapters.generic:GenericAdapter",
}

# auto 模式检测顺序：Hermes → Claude Code → OpenClaw → Generic
_AUTO_DETECT_ORDER = ("hermes", "claude_code", "openclaw", "generic")


def _load_adapter(name: str):
    """懒加载适配器类。

    使用 importlib.import_module + getattr 解析 ``module:Class`` 形式的映射条目，
    适配器模块不存在时优雅返回 None。

    Args:
        name: 适配器名称（hermes / claude_code / openclaw / generic）。

    Returns:
        适配器类对象；若模块不存在或导入失败则返回 None。
    """
    spec = _ADAPTERS_MAP.get(name)
    if not spec:
        return None
    try:
        module_path, class_name = spec.split(":")
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        logger.debug(f"Failed to load adapter '{name}': {e}")
        return None


def mount_brain_to_agent(
    brain: "LaapBrain",
    agent_type: str = "auto",
    agent: Optional[Any] = None,
) -> Tuple["LaapBrain", Optional["AgentAdapter"]]:
    """将 LAAP 大脑挂载到外部智能体。

    Args:
        brain: LaapBrain 实例。
        agent_type: 智能体类型。"auto" 自动检测；或 "hermes" / "claude_code" /
            "openclaw" / "generic"。
        agent: 可选的智能体对象（仅 generic 与 openclaw 模式使用，预留参数）。

    Returns:
        (brain, adapter) 元组；若 auto 全部失败则 adapter 为 None
        （仅在 GenericAdapter 也失败时，不应发生）。

    Raises:
        NotImplementedError: 若显式指定的 agent_type 未实现。
    """
    if agent_type == "auto":
        for name in _AUTO_DETECT_ORDER:
            adapter_cls = _load_adapter(name)
            if adapter_cls is None:
                continue
            try:
                if adapter_cls.detect():
                    adapter = adapter_cls()
                    adapter.install_hooks(brain)
                    logger.info(f"Auto-mounted adapter: {name}")
                    return brain, adapter
            except Exception as e:
                logger.debug(f"Adapter '{name}' detect failed: {e}")
                continue
        logger.warning("No adapter detected; returning brain without mount")
        return brain, None

    # 显式模式：直接实例化，不调 detect()
    adapter_cls = _load_adapter(agent_type)
    if adapter_cls is None:
        raise NotImplementedError(f"Adapter '{agent_type}' not implemented")
    adapter = adapter_cls()
    adapter.install_hooks(brain)
    logger.info(f"Explicitly mounted adapter: {agent_type}")
    return brain, adapter
