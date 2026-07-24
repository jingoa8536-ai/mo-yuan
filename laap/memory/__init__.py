"""LAAP — Memory System"""

import logging
logger = logging.getLogger(__name__)

try:
    from laap.memory.hierarchical import HierarchicalMemory, MemoryItem, Skill, Reflection
except ImportError:
    pass  # 可选模块，降级处理
from laap.memory.persistent import PersistentMemoryEngine, MemoryEntry
from laap.memory.provider import MemoryProvider
from laap.memory.manager import MemoryManager
from laap.memory.long_term import (
    LongTermMemory, MemoryEntry as LTMMemoryEntry, 
    MemoryType, ProceduralMemory, ProceduralStep
)
try:
    from laap.memory.providers.builtin import BuiltinMemoryProvider
except ImportError:
    pass  # 可选模块，降级处理
__all__ = [
    # Hierarchical Memory
    "HierarchicalMemory", "MemoryItem", "Skill", "Reflection",
    # Persistent Memory
    "PersistentMemoryEngine", "MemoryEntry",
    # Provider & Manager
    "MemoryProvider", "MemoryManager",
    # Long-Term Memory (Phase 2)
    "LongTermMemory", "LTMMemoryEntry", "MemoryType", "ProceduralMemory", "ProceduralStep",
    # Builtin Provider
    "BuiltinMemoryProvider",
]
