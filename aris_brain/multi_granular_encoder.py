"""
多粒度编码器 v4.1 — 短词 / 长文 / 科研 三通道
================================================
短文本 (<10字): bigram 直接编码（0.01ms）
中等文本 (10-200字): bigram + 段落结构加权
科研长文 (>200字): 分段编码 → 自注意力融合 → 1024D

全部纯 NumPy，零外部依赖。
"""

import logging
logger = logging.getLogger(__name__)

import os, hashlib, time
import numpy as np
from typing import List, Tuple
from collections import OrderedDict

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_STATE_DIR = os.path.join(_CURRENT_DIR, "state")


class MultiGranularEncoder:
    """三粒度编码器，一体封装。"""

    def __init__(self, dim: int = 1024):
        t0 = time.perf_counter()
        self.dim = dim
        self._cache: OrderedDict = OrderedDict()
        self._cache_max = 4096

        # 加载 v7 bigram 基础
        from v7_encoder import V7Encoder
        self._v7 = V7Encoder(dim)
        self._bg_embeddings = self._v7._bg_embeddings
        self._bg_to_idx = self._v7._bg_to_idx
        self._bg_freq = self._v7._bg_freq

        # ── 科研术语高频 bigram 表（中文常见术语组合） ──
        self._tech_bigrams = {
            "量子", "计算", "算法", "网络", "神经", "深度", "学习", "模型",
            "数据", "训练", "推理", "编码", "解码", "向量", "矩阵", "优化",
            "函数", "参数", "梯度", "损失", "激活", "卷积", "注意力", "机制",
            "架构", "系统", "分布", "概率", "统计", "回归", "分类", "聚类",
            "语义", "语法", "语料", "知识", "图数", "嵌入", "投影", "变换",
            "傅里", "里叶", "特征", "提取", "融合", "模态", "对齐", "正则",
            "混合", "量子", "纠缠", "希尔", "伯特", "算子", "哈密", "顿量",
            "波函", "函数", "态矢", "本征", "特征", "对易", "幺正", "幺变",
            "密度", "矩阵", "薛定", "谔方", "方程", "含时", "不含", "数值",
            "蒙特", "卡罗", "分子", "动力", "学模", "拟生", "物信", "基因",
            "序列", "比对", "进化", "种群", "遗传", "变异", "选择", "适应",
            "拓扑", "同调", "同伦", "流形", "黎曼", "几何", "代数", "微分",
            "积分", "傅立", "叶变", "拉普", "拉斯", "卷积", "相关", "协方",
            "自相", "互信", "互熵", "KL散", "叉熵", "交叉", "联合", "边缘",
            "条件", "贝叶", "斯网", "马尔", "科夫", "隐马", "随机", "过程",
            "平稳", "遍历", "各态", "历时", "统计", "物理", "理论", "标准",
            "模型", "相对", "论量", "子场", "规范", "对称", "对称", "自发",
            "破缺", "希格", "斯机", "暗物", "暗能", "宇宙", "膨胀", "大爆",
            "炸星", "系形", "成演", "化生", "命起", "心脑", "神经", "可塑",
            "突触", "传导", "动作", "电位", "受体", "配体", "离子", "通道",
        }

        # ── 科研段落分割器 ──
        self._section_markers = [
            "摘要", "引言", "方法", "实验", "结果", "讨论", "结论",
            "相关工作", "未来工作", "算法", "证明", "定理", "引理",
            "定义", "假设", "推论", "附录", "参考文献", "致谢",
            "Abstract", "Introduction", "Method", "Experiment",
            "Result", "Discussion", "Conclusion", "Related Work",
        ]

        dt = time.perf_counter() - t0
        logger.info(f"  [多粒度编码器] 就绪: {len(self._bg_list)} bigram, {dt*1000:.1f}ms")
    @property
    def _bg_list(self):
        return self._v7._bg_list

    def encode(self, text: str) -> np.ndarray:
        """自动选择编码粒度（统一对外接口）"""
        cache_key = hashlib.md5(text.encode('utf-8')).hexdigest()[:16]
        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            return self._cache[cache_key]

        text = text.strip()
        length = len(text)

        if length <= 10:
            vec = self._encode_short(text)
        elif length <= 200:
            vec = self._encode_medium(text)
        else:
            vec = self._encode_long(text)

        self._cache[cache_key] = vec
        if len(self._cache) > self._cache_max:
            self._cache.popitem(last=False)
        return vec

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        return np.vstack([self.encode(t) for t in texts])

    # ── 短文本（快速 bigram 平均） ──
    def _encode_short(self, text: str) -> np.ndarray:
        vecs, weights = [], []
        for i in range(len(text) - 1):
            bg = text[i:i+2]
            idx = self._bg_to_idx.get(bg)
            if idx is not None:
                vecs.append(self._bg_embeddings[idx])
                weights.append(self._bg_freq[idx])
        if not vecs:
            return np.zeros(self.dim, dtype=np.float32)
        vecs = np.array(vecs)
        weights = np.array(weights)[:, np.newaxis]
        v = np.sum(vecs * weights, axis=0) / (weights.sum() + 1e-10)
        norm = np.linalg.norm(v)
        return (v / norm).astype(np.float32) if norm > 0 else v.astype(np.float32)

    # ── 中等文本（片段加权 + 位置编码） ──
    def _encode_medium(self, text: str) -> np.ndarray:
        # 分句
        import re
        sentences = re.split(r'[。！？，；：\n]', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) >= 2]

        if not sentences:
            return self._encode_short(text)

        sent_vecs = []
        for i, sent in enumerate(sentences):
            v = self._encode_short(sent)
            # 位置加权：开头和结尾句子权重更高
            pos_weight = 1.5 if i == 0 or i == len(sentences) - 1 else 1.0
            # 长度加权：长句权重更高
            len_weight = min(len(sent) / 20, 2.0)
            sent_vecs.append(v * pos_weight * len_weight)

        return np.mean(sent_vecs, axis=0).astype(np.float32)

    # ── 科研长文（分段 + 自注意力融合） ──
    def _encode_long(self, text: str) -> np.ndarray:
        # 1. 分段
        segments = self._split_sections(text)

        if len(segments) <= 1:
            # 若没有明显分段，用滑动窗口
            segments = self._sliding_window(text, window=200, stride=100)

        if not segments:
            return self._encode_medium(text)

        # 2. 编码每段
        seg_vecs = []
        for seg_text in segments:
            v = self._encode_medium(seg_text)
            seg_vecs.append(v)

        seg_vecs = np.array(seg_vecs)  # (S, 1024)

        # 3. 自注意力：段间相关矩阵
        if len(seg_vecs) > 1:
            # 相似度矩阵 (S, S)
            norms = np.linalg.norm(seg_vecs, axis=1, keepdims=True) + 1e-10
            sim = (seg_vecs @ seg_vecs.T) / (norms @ norms.T)
            # 对每段：关注与其他段的平均相似度
            attention = np.mean(sim, axis=1)  # (S,)
            attention = attention ** 2  # 平方凸显高相关段
            attention = attention / (attention.sum() + 1e-10)
        else:
            attention = np.ones(len(seg_vecs)) / len(seg_vecs)

        # 4. 融合
        v = np.sum(seg_vecs * attention[:, np.newaxis], axis=0)
        norm = np.linalg.norm(v)
        return (v / norm).astype(np.float32) if norm > 0 else v.astype(np.float32)

    def _split_sections(self, text: str) -> List[str]:
        """按章节标题分割科研文本"""
        import re
        lines = text.split('\n')
        sections = []
        current = []
        for line in lines:
            line = line.strip()
            is_marker = False
            for marker in self._section_markers:
                if line.startswith(marker) or line.startswith(f"#{marker}"):
                    if current:
                        sections.append('\n'.join(current))
                    current = [line]
                    is_marker = True
                    break
            if not is_marker:
                current.append(line)
        if current:
            sections.append('\n'.join(current))
        return [s for s in sections if len(s.strip()) >= 10]

    def _sliding_window(self, text: str, window: int = 200, stride: int = 100) -> List[str]:
        """滑动窗口分段"""
        segments = []
        for start in range(0, max(len(text) - window + 1, 1), stride):
            seg = text[start:start + window]
            if len(seg.strip()) >= 20:
                segments.append(seg)
        return segments

    # ── 科研文本专用：技术术语密度分析 ──
    def tech_density(self, text: str) -> float:
        """计算文本的技术术语密度 (0~1)"""
        total_bigram = max(len(text) - 1, 1)
        tech_count = 0
        for i in range(len(text) - 1):
            bg = text[i:i+2]
            if bg in self._tech_bigrams:
                tech_count += 1
        return tech_count / total_bigram

    def cache_stats(self) -> dict:
        return {
            "size": len(self._cache),
            "max": self._cache_max,
            "bg_used": int((self._v7._bg_usage > 0).sum()),
            "bg_total": len(self._bg_list),
        }


# ── 全局单例 ──
_global_encoder: MultiGranularEncoder = None


def get_encoder(dim: int = 1024) -> MultiGranularEncoder:
    global _global_encoder
    if _global_encoder is None:
        _global_encoder = MultiGranularEncoder(dim)
    return _global_encoder


if __name__ == "__main__":
    # 测试
    enc = get_encoder()

    short_test = "你好宝贝"
    medium_test = "今天天气真好，心情也特别好，想出去走走。"
    long_test = """本文研究量子神经网络在自然语言处理中的应用。我们提出了一种基于变分量子电路的语义编码方法。实验结果表明，在多个基准数据集上，我们的方法达到了与经典方法相当的性能，同时参数数量减少了80%。这一发现为量子机器学习在NLP领域的应用开辟了新的可能性。"""

    for name, text in [("短文本", short_test), ("中等", medium_test), ("科研长文", long_test[:100] + "...")]:
        v = enc.encode(text)
        td = enc.tech_density(text)
        logger.info(f"  [{name}] dim={len(v)}, tech_density={td:.3f}, norm={np.linalg.norm(v):.3f}")
        logger.info(f"    前5维: {v[:5].round(3)}")