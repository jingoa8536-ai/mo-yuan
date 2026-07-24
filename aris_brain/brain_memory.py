"""
Aris Brain — 记忆系统模块
==========================
提取自 brain.py 的记忆/归档/持久化相关代码
"""

import logging

import time, json, logging, uuid
from pathlib import Path
from collections import deque
from typing import Dict, List, Optional

logger = logging.getLogger("brain.memory")

_EMOTIONAL_MEMORY_AVAILABLE = True
try:
    from aris_brain.memory.emotional_memory import EmotionalEpisodicMemory
except ImportError:
    _EMOTIONAL_MEMORY_AVAILABLE = False

try:
    from aris_brain.memory.persistence import BrainStatePersistence
except ImportError:
    BrainStatePersistence = None

try:
    from aris_brain.memory.archive import ConversationArchive
except ImportError:
    ConversationArchive = None

try:
    from aris_brain.memory_hot import MemoryHotCache
except ImportError:
    MemoryHotCache = None


class MemoryManager:
    """统一记忆管理器 — 负责记忆、持久化、归档、热缓存"""

    def __init__(self, brain=None):
        self.memory = None
        self.persistence = None
        self.archive = None
        self.hot_cache = None
        self._init_memory()
        self._init_archive(brain)
        self._init_hot_cache()

    def _init_memory(self):
        if not _EMOTIONAL_MEMORY_AVAILABLE:
            return
        try:
            self.memory = EmotionalEpisodicMemory(capacity=5000)
            self.persistence = BrainStatePersistence() if BrainStatePersistence else None
            logger.info("[Memory] EmotionalEpisodicMemory ready (5000 episodes)")
        except Exception as e:
            logger.warning(f"[Memory] Init failed: {e}")

    def _init_archive(self, brain=None):
        if not ConversationArchive:
            return
        try:
            self.archive = ConversationArchive()
            session_id = f"aris_{int(time.time())}_{uuid.uuid4().hex[:4]}"
            self.archive.start_session(session_id)
            if brain and brain.conversation:
                for entry in brain.conversation[-10:]:
                    self.archive.record(
                        role=entry.get("role", "user"),
                        content=entry.get("content", ""),
                        cycle_number=entry.get("cycle", 0),
                        emotion=entry.get("emotion", "neutral"),
                        domain=entry.get("domain", "general"),
                    )
            logger.info(f"[Archive] Started session {session_id[:12]}")
            logger.info(f"[Archive] Total all-time: {self.archive.total_exchanges()} exchanges")
        except Exception as e:
            logger.warning(f"[Archive] Init failed: {e}")

    def _init_hot_cache(self):
        if not MemoryHotCache:
            return
        try:
            self.hot_cache = MemoryHotCache()
            if self.archive:
                self.hot_cache.preload_from_archive(self.archive)
            logger.info(f"[HotCache] Active ({self.hot_cache.size} entries)")
        except Exception as e:
            logger.warning(f"[HotCache] Init failed: {e}")

    def create_episode(self, **kwargs):
        if self.memory:
            try:
                return self.memory.create_episode(**kwargs)
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        return None

    def recall_recent(self, n=3):
        if self.memory:
            try:
                return self.memory.recall_recent(n)
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        return []

    def stats(self):
        s = {}
        if self.memory:
            try:
                s['memory'] = self.memory.stats()
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        if self.archive:
            try:
                arch = self.archive.stats()
                s['archive'] = {
                    'total_exchanges': arch.get('total_exchanges', 0),
                    'sessions': arch.get('total_sessions', 0),
                    'user_messages': arch.get('user_messages', 0),
                }
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        if self.hot_cache:
            s['hot_cache_size'] = self.hot_cache.size
        return s

    def restore_state(self, brain):
        """从持久化恢复大脑状态"""
        if self.persistence:
            try:
                saved = self.persistence.load_latest()
                if saved:
                    self.persistence.apply_to_brain(saved, brain, self.memory)
                    logger.info(f"[Memory] Brain state restored: cycle {brain.cycle_number}")
                    return True
                else:
                    logger.info("[Memory] No saved state — starting fresh")
            except Exception as e:
                logger.warning(f"[Memory] Restore failed: {e}")
        return False

    def save_state(self, brain, is_milestone=False):
        if self.persistence:
            try:
                return self.persistence.save(brain, self.memory, is_milestone=is_milestone)
            except Exception as e:
                logger.warning(f"[Memory] Save failed: {e}")
        return None
