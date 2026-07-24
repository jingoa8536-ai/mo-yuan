"""
Aris V7 — 热缓存 (Memory Hot Cache)
======================================
LRU 缓存，预载最近和高情感值的记忆。
预测通道决定预载内容 → 0 延迟记忆检索。

V6 查 Archive 每次都要 SQLite 查询 (10-50ms)
V7 HotCache → 常用记忆常驻内存 (< 1μs)
"""

from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

import time, json
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import OrderedDict

ARIS_HOME = Path("D:/LAAP/aris_brain")
CACHE_FILE = ARIS_HOME / "state" / "hot_cache.json"


class MemoryHotCache:
    """
    LRU 热缓存 — 预载最近/高显著性记忆。
    
    容量: 200 条
    预载策略: 最近话题 / 高情感值 / ToM预测
    淘汰: LRU (最近最少使用)
    """

    def __init__(self, max_entries: int = 200):
        self._cache: OrderedDict = OrderedDict()
        self._max = max_entries
        self._hits = 0
        self._misses = 0
        self._start_time = time.time()

    def get(self, key: str) -> Optional[Dict]:
        """查询缓存 — 命中则移动到末尾 (LRU)"""
        if key in self._cache:
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]
        self._misses += 1
        return None

    def put(self, key: str, value: Dict):
        """写入缓存 — 超过容量淘汰最旧的"""
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self._max:
            self._cache.popitem(last=False)

    def remove(self, key: str):
        self._cache.pop(key, None)

    def clear(self):
        self._cache.clear()

    def preload_from_archive(self, archive, recent_count: int = 50):
        """从 Archive 预载最近的对话到热缓存"""
        try:
            recent = archive.recall_recent(recent_count)
            for entry in recent:
                key = f"exchange_{entry.get('id', '')}" if isinstance(entry, dict) else str(hash(str(entry)))
                self.put(key, entry if isinstance(entry, dict) else {"content": str(entry)})
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def size(self) -> int:
        return len(self._cache)

    def stats(self) -> Dict[str, Any]:
        return {
            "size": len(self._cache),
            "max": self._max,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate, 3),
            "uptime": round(time.time() - self._start_time),
        }
