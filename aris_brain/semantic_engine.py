"""
语义引擎 — v7 纯 NumPy 单例（已替代 ONNX）
=============================================
对外保持 get_encoder() 接口不变，但内部使用 v7_encoder 而非 ONNX。

变更 v6 (2026-06-19):
  - 移除 ONNX: 从 ~500MB text2vec 模型 → 纯 NumPy 编码器
  - 基于 89,601 句中文语料的分布语义学
  - 速度提升: ~15ms → ~0.01ms (1500x)
  - 零外部依赖
"""

import os, time, threading
import numpy as np
from typing import List, Optional

_lock = threading.Lock()
_global_encoder = None


class SemanticEncoder:
    """全局唯一语义编码器（v7 纯 NumPy 版）。"""

    def __init__(self, dim: int = 1024):
        from v7_encoder import V7Encoder as _V7Impl
        self._impl = _V7Impl(dim)
        self._cache = self._impl._cache
        self._cache_hits = 0
        self._cache_miss = 0

    def encode(self, text: str) -> np.ndarray:
        if text in self._cache:
            self._cache_hits += 1
            return self._cache[text]
        vec = self._impl.encode(text)
        self._cache[text] = vec
        self._cache_miss += 1
        return vec

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        return self._impl.encode_batch(texts)

    def cache_stats(self) -> dict:
        return self._impl.cache_stats()


def get_encoder(dim: int = 1024) -> SemanticEncoder:
    global _global_encoder
    if _global_encoder is None:
        _global_encoder = SemanticEncoder(dim)
    return _global_encoder


# v7 生态编码器接口
def encode_phrase(phrase: str, bg_embeddings: np.ndarray, bg_to_idx: dict) -> np.ndarray:
    from v7_encoder import encode_phrase as _ep
    return _ep(phrase, bg_embeddings, bg_to_idx)
