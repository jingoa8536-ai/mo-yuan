"""
知识推理链 v4.2 — 多跳语义推理引擎
=====================================
基于知识向量的多跳推理链。

核心创新：
1. 从查询出发，每跳根据知识图谱相似度扩展
2. 自收敛检测（当相邻两跳变化<阈值时停止）
3. 最大 10 跳，典型 3-5 跳收敛
4. 每跳产生一个"推理子结论"向量
5. 最终结论 = 所有子结论的注意力融合

全部纯 NumPy，零外部依赖。
"""

import logging
logger = logging.getLogger(__name__)

import os, time, hashlib
import numpy as np
from typing import List, Dict, Tuple, Optional
from collections import OrderedDict

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_STATE_DIR = os.path.join(_CURRENT_DIR, "state")


class InferenceChain:
    """多跳推理链。

    工作流程:
      input_vector (1024D)
        → hop 1: query @ knowledge_matrix → top3 知识片段
        → hop 2: top3 知识 + 原查询 → 新查询
        → hop 3: 继续...直到收敛
        → 最终: 所有跳的注意力融合
    """

    def __init__(self, max_hops: int = 10, convergence_threshold: float = 0.95):
        self.max_hops = max_hops
        self.convergence_threshold = convergence_threshold

        # 加载知识矩阵
        self._load_knowledge()

        # 编码器（懒加载）
        self._encoder = None

        # 推理链缓存
        self._cache: OrderedDict = OrderedDict()
        self._cache_max = 128

    def _load_knowledge(self):
        """加载知识矩阵和元数据"""
        km_path = os.path.join(_STATE_DIR, "kb_matrix.npz")
        meta_path = os.path.join(_STATE_DIR, "kb_index.json")

        if os.path.exists(km_path):
            data = np.load(km_path, allow_pickle=True)
            keys = [k for k in data.keys() if k.startswith("arr_")]
            if keys:
                self._knowledge_matrix = np.vstack([data[k] for k in keys])
            else:
                self._knowledge_matrix = data[list(data.keys())[0]]
            logger.info(f"  [推理链] 知识矩阵: {self._knowledge_matrix.shape[0]} 条, {self._knowledge_matrix.shape[1]}D")
        else:
            # 也尝试 knowledge_matrix.npz
            alt_path = os.path.join(_STATE_DIR, "knowledge_matrix.npz")
            if os.path.exists(alt_path):
                data = np.load(alt_path, allow_pickle=True)
                self._knowledge_matrix = data[data.files[0]]
                logger.info(f"  [推理链] 知识矩阵: {self._knowledge_matrix.shape[0]} 条 (secondary)")
            else:
                self._knowledge_matrix = np.zeros((1, 1024), dtype=np.float32)
                logger.info(f"  [推理链] ⚠ 无知识矩阵，使用空矩阵")
        self._knowledge_matrix = self._knowledge_matrix.astype(np.float32)
        self._n_knowledge = self._knowledge_matrix.shape[0]

    @property
    def encoder(self):
        if self._encoder is None:
            from multi_granular_encoder import get_encoder
            self._encoder = get_encoder(1024)
        return self._encoder

    def infer(self, query: str) -> Dict:
        """对查询进行多跳推理。

        Returns:
            {
                "conclusion_vector": 最终融合向量,
                "hops": 实际跳数,
                "converged": 是否收敛,
                "hop_vectors": 每跳子结论,
                "hop_scores": 每跳置信度,
                "inference_time_ms": 推理耗时,
            }
        """
        cache_key = hashlib.md5(query.encode('utf-8')).hexdigest()[:16]
        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            return self._cache[cache_key]

        t0 = time.perf_counter()

        # 编码查询
        q_vec = self.encoder.encode(query)  # (1024,)

        # 推理链
        hop_vectors = [q_vec.copy()]
        hop_scores = [1.0]
        converged = False

        for hop in range(1, self.max_hops + 1):
            # 从知识矩阵检索 top-K 相关向量
            sims = q_vec @ self._knowledge_matrix.T  # (N,)
            topk = min(5, self._n_knowledge)
            top_indices = np.argsort(-sims)[:topk]
            top_scores = sims[top_indices]

            # 只取正相似度的
            positive = top_scores > 0.1
            if positive.sum() == 0:
                break  # 没有相关知识，停止

            top_indices = top_indices[positive]
            top_scores = top_scores[positive]

            # 每跳的子结论 = 加权平均相关知识
            weights = top_scores / (top_scores.sum() + 1e-10)
            knowledge_vec = np.sum(
                self._knowledge_matrix[top_indices] * weights[:, np.newaxis],
                axis=0
            )
            # 归一化
            knorm = np.linalg.norm(knowledge_vec)
            if knorm > 0:
                knowledge_vec = knowledge_vec / knorm

            # 跳跃 — 新查询 = 原查询 + 0.5 * 知识（加阻尼防震荡）
            hop_vec = q_vec + 0.5 * knowledge_vec
            hnorm = np.linalg.norm(hop_vec)
            if hnorm > 0:
                hop_vec = hop_vec / hnorm

            # 置信度 = 知识相似度的均值
            score = float(np.mean(top_scores))

            hop_vectors.append(hop_vec)
            hop_scores.append(score)

            # 更新查询为当前 hop 结果
            q_vec = hop_vec

            # 收敛检测：当前 hop 与上一 hop 的相似度
            if len(hop_vectors) >= 2:
                sim_prev = float(hop_vectors[-1] @ hop_vectors[-2])
                if sim_prev > self.convergence_threshold:
                    converged = True
                    break

        # 最终融合 = 注意力加权的 hop 向量
        attention = np.array(hop_scores) ** 2  # 平方放大高置信度
        attention = attention / (attention.sum() + 1e-10)
        conclusion = np.sum(
            np.array(hop_vectors) * attention[:, np.newaxis],
            axis=0
        )
        cnorm = np.linalg.norm(conclusion)
        if cnorm > 0:
            conclusion = conclusion / cnorm

        result = {
            "conclusion_vector": conclusion,
            "hops": len(hop_vectors) - 1,
            "converged": converged,
            "hop_vectors": hop_vectors,
            "hop_scores": hop_scores,
            "inference_time_ms": (time.perf_counter() - t0) * 1000,
        }

        # 缓存
        self._cache[cache_key] = result
        if len(self._cache) > self._cache_max:
            self._cache.popitem(last=False)

        return result

    def chain_summary(self, result: Dict) -> str:
        """生成推理链人类可读摘要"""
        lines = []
        lines.append(f"推理 {result['hops']} 跳, {'收敛' if result['converged'] else '未收敛'}")
        lines.append(f"耗时: {result['inference_time_ms']:.2f}ms")
        for i, (v, s) in enumerate(zip(result['hop_vectors'], result['hop_scores'])):
            lines.append(f"  跳{i}: 置信度={s:.3f}")
        lines.append(f"  结论向量前5维: {result['conclusion_vector'][:5].round(3)}")
        return '\n'.join(lines)


# ── 全局单例 ──
_global_chain: InferenceChain = None


def get_chain(max_hops: int = 10) -> InferenceChain:
    global _global_chain
    if _global_chain is None:
        _global_chain = InferenceChain(max_hops)
    return _global_chain


if __name__ == "__main__":
    chain = get_chain(10)

    tests = [
        "量子计算",
        "你好宝贝",
        "神经网络在自然语言处理中的应用",
        "量子纠缠与经典关联的区别",
    ]

    for query in tests:
        result = chain.infer(query)
        logger.info(f"\n查询: {query}")
        logger.info(chain.chain_summary(result))