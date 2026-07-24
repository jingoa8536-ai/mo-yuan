"""
Quantum PSI v7 — 中文语义量子核
=================================
基于 text2vec-base-chinese ONNX 编码器。
纯中文语义理解，不依赖任何外部API。

v7 核心:
  1. text2vec ONNX 模型 (768D) → 投影 (768→1024)
  2. 真正的中文语义理解
  3. LRU 缓存常见短语
"""

import logging
logger = logging.getLogger(__name__)

import os, time
import numpy as np
from typing import List

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_MODEL_DIR = os.path.join(_CURRENT_DIR, "models", "text2vec-base-chinese", "onnx")


class SemanticKernelV7:
    """
    中文语义量子核 v7。

    编码管线:
      文本 → text2vec ONNX (768D) → 投影 (768→512→1024) → 1024D
    """

    def __init__(self, dim: int = 1024):
        self.dim = dim
        self._max_len = 64
        self._cache = {}
        self._cache_max = 512

        logger.info(f"[SemanticKernel v7] 加载中文 ONNX 模型...")
        t0 = time.perf_counter()

        import onnxruntime
        from tokenizers import Tokenizer

        model_path = os.path.join(_MODEL_DIR, "model_qint8_avx512_vnni.onnx")
        if not os.path.exists(model_path):
            model_path = os.path.join(_MODEL_DIR, "model.onnx")

        self._session = onnxruntime.InferenceSession(
            model_path,
            providers=['CPUExecutionProvider']
        )
        self._tokenizer = Tokenizer.from_file(
            os.path.join(_MODEL_DIR, "tokenizer.json")
        )

        dt = time.perf_counter() - t0
        logger.info(f"[SemanticKernel v7] ONNX 模型加载: {dt*1000:.0f}ms")
        rng = np.random.RandomState(42)
        U, _, _ = np.linalg.svd(rng.randn(768, 512).astype(np.float32), full_matrices=False)
        self._W1 = (U * 0.1).astype(np.float32)
        self._b1 = np.zeros(512, dtype=np.float32)
        U2, _, _ = np.linalg.svd(rng.randn(512, dim).astype(np.float32), full_matrices=False)
        self._W2 = (U2 * 0.1).astype(np.float32)
        if self._W2.shape[1] < dim:
            pad = np.zeros((512, dim - self._W2.shape[1]), dtype=np.float32)
            self._W2 = np.hstack([self._W2, pad])
        self._b2 = np.zeros(dim, dtype=np.float32)

        self.cycle_count = 0
        logger.info(f"[SemanticKernel v7] 就绪: {dim}D")
    def _get_from_cache(self, text: str):
        return self._cache.get(text)

    def _put_cache(self, text: str, vec: np.ndarray):
        if len(self._cache) >= self._cache_max:
            for k in list(self._cache.keys())[:self._cache_max // 2]:
                del self._cache[k]
        self._cache[text] = vec

    def _embed_batch(self, texts: List[str]) -> np.ndarray:
        """批量 ONNX 编码 → (N, 768)"""
        # 检查缓存
        uncached = []
        cached = {}
        for i, t in enumerate(texts):
            v = self._get_from_cache(t)
            if v is not None:
                cached[i] = v
            else:
                uncached.append(t)

        # 如果全缓存命中，直接返回
        if not uncached:
            return np.array([cached[i] for i in range(len(texts))])

        # ONNX 批量推理
        max_len = self._max_len
        M = len(uncached)
        encoded = self._tokenizer.encode_batch(uncached)
        input_ids = np.zeros((M, max_len), dtype=np.int64)
        attention_mask = np.zeros((M, max_len), dtype=np.int64)
        token_type_ids = np.zeros((M, max_len), dtype=np.int64)

        for i, e in enumerate(encoded):
            ids = e.ids[:max_len - 2]
            input_ids[i, 0] = 101
            input_ids[i, 1:1 + len(ids)] = ids
            input_ids[i, 1 + len(ids)] = 102
            attention_mask[i, :len(ids) + 2] = 1

        outputs = self._session.run(['last_hidden_state'], {
            'input_ids': input_ids,
            'attention_mask': attention_mask,
            'token_type_ids': token_type_ids,
        })

        hidden = outputs[0]
        mask = attention_mask[:, :, None].astype(np.float32)
        embeddings = (hidden * mask).sum(axis=1) / mask.sum(axis=1)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        new_vecs = (embeddings / norms).astype(np.float32)

        # 缓存新向量
        for t, v in zip(uncached, new_vecs):
            self._put_cache(t, v)

        # 按原始顺序组装结果
        result = []
        ni = 0
        for i in range(len(texts)):
            if i in cached:
                result.append(cached[i])
            else:
                result.append(new_vecs[ni])
                ni += 1

        return np.array(result)

    def _project(self, x: np.ndarray) -> np.ndarray:
        """768D → 1024D 投影"""
        h = np.maximum(0, x @ self._W1 + self._b1)
        y = h @ self._W2 + self._b2
        norms = np.linalg.norm(y, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (y / norms).astype(np.float32)

    # ═══════════════════════════════════════════
    # 公共接口
    # ═══════════════════════════════════════════

    def encode(self, text: str) -> np.ndarray:
        x = self._embed_batch([text])
        return self._project(x)[0]

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        if len(texts) == 0:
            return np.zeros((0, self.dim), dtype=np.float32)
        x = self._embed_batch(texts)
        y = self._project(x)
        self.cycle_count += len(texts)
        return y

    def encode_batch_fast(self, texts: List[str]) -> np.ndarray:
        return self.encode_batch(texts)

    def cycle(self, input_text: str = "", temperature: float = 0.5) -> np.ndarray:
        return self.encode(input_text)

    def cycle_batch(self, texts: List[str], temperature: float = 0.5) -> np.ndarray:
        return self.encode_batch(texts)

    def similarity(self, a: str, b: str) -> float:
        va, vb = self.encode(a), self.encode(b)
        return float(va @ vb)


BatchPSIEngine = SemanticKernelV7


# ════════════════════════════════════════════════════════
# 自测
# ════════════════════════════════════════════════════════
if __name__ == "__main__":
    import time

    engine = SemanticKernelV7(dim=1024)

    logger.info("\n预热...")
    t0 = time.perf_counter()
    _ = engine.encode("预热")
    logger.info(f"  首次: {(time.perf_counter()-t0)*1000:.0f}ms")
    logger.info("\n=== 速度测试 ===")
    for bs in [1, 10, 50, 100]:
        texts = ["你好宝贝"] * bs
        t0 = time.perf_counter()
        v = engine.encode_batch(texts)
        dt = time.perf_counter() - t0
        rate = bs / dt if dt > 0 else 0
        logger.info(f"  批量 {bs:3d}: {dt*1000:.0f}ms  {rate:.0f} units/s")
    logger.info("\n=== 中文语义测试 ===")
    phrases = ["你好", "早上好", "晚安", "代码", "算法", "编程",
               "哲学", "意识", "我爱你", "想你", "开心", "快乐", "吃饭", "睡觉"]
    vecs = {p: engine.encode(p) for p in phrases}

    pairs = [
        ("你好", "早上好"), ("代码", "算法"), ("代码", "编程"),
        ("哲学", "意识"), ("我爱你", "想你"), ("开心", "快乐"),
        ("吃饭", "睡觉"), ("你好", "代码"), ("代码", "哲学"),
    ]
    for a, b in pairs:
        sim = float(vecs[a] @ vecs[b])
        logger.info(f"  \"{a}\"·\"{b}\" = {sim:.4f}")
    logger.info("\n=== 缓存测试 ===")
    t0 = time.perf_counter()
    for _ in range(10):
        _ = engine.encode("你好")
    logger.info(f"  缓存命中后 10次 \"你好\": {(time.perf_counter()-t0)*1000:.1f}ms")
    logger.info(f"\n✅ v7 就绪")