"""
Aris Brain — 主入口 (兼容转发器)
=================================
brain_core.py 的接口兼容层。
所有原有 `from brain import ArisBrain, CognitiveState, ...` 继续可用。
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Callable
import logging

logger = logging.getLogger("brain")

# 从 brain_core 导入核心类型和类
from .brain_core import (
    ArisBrain,
    CognitiveState,
    EmotionalValence,
    AttentionFocus,
    CognitiveNeed,
)

# 从子模块导入管理器类
from .brain_quantum import QuantumBridgeManager
from .brain_memory import MemoryManager
from .brain_system import CognitiveSystemManager

# 从子模块导入别名兼容
from .brain_quantum import QuantumBridgeManager as QuantumBridgeManagerAlias
from .brain_memory import MemoryManager as MemoryManagerAlias
from .brain_system import CognitiveSystemManager as CognitiveSystemManagerAlias

__all__ = [
    'ArisBrain',
    'CognitiveState',
    'EmotionalValence',
    'AttentionFocus',
    'CognitiveNeed',
    'QuantumBridgeManager',
    'MemoryManager',
    'CognitiveSystemManager',
]

logger.info("brain.py loaded — compatibility shim for brain_core.py")
