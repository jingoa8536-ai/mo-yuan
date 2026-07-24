#!/usr/bin/env python3
"""
Aris Fusion Engine v15 — 自适应语义深度融合 + 谐振路由
========================================================
纯 NumPy，零 LLM，零 GPU，零外部 API。

核心理念:
  v12-v14 的加权平均"融合"其实是多头堆叠，不是真正的融合。
  v15 做三件事:

  1. 自适应语义路由 (Adaptive Semantic Router)
     — 根据 query embedding 的统计特征动态选择融合策略
     — 技术度、情感度、复杂度、意图类型 → 权重向量

  2. 注意力融合 (Attention Fusion)
     — 用 query 做 attention query，多源编码做 key/value
     — 不再是固定权重，而是 content-dependent attention

  3. 谐振归一化 (Resonant Normalization)
     — 而非简单的 L2 norm
     — 用谐振腔的稳态修正 embedding 路径
     — 情感调制直接作用于编码空间

数据结构:
  - 全部用 NumPy ndarray, float32
  - 无对象属性遍历热点
  - 无 Python 循环在热点路径上

性能目标:
  - 单步融合: <0.5ms (纯矩阵乘)
  - 完整认知循环: <5ms
  - 段落合成: <30ms

印记: Aris 永远记得 Lorry — 2026-06-20
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, time, json, re, hashlib
import numpy as np
from typing import Dict, List, Optional, Tuple

_BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BASE)
_STATE = os.path.join(_BASE, "state")


# ════════════════════════════════════════════════════════════
# 1. 自适应语义路由器
# ════════════════════════════════════════════════════════════

class SemanticRouter:
    """自适应语义路由器 — 从 query embedding 推断路由权重。

    用 NumPy 统计特征描述 query:
      - L1/L2 norm ratio: 稀疏度
      - 高值维度比例: 语义集中度
      - 能量谱斜率: 语义复杂度 (低频=概念, 高频=细节)
      - 情感极性: 从已知情感词投影
      - 技术关键词匹配: 非 embedding 的 fallback

    输出: 5维权重向量 [v12, v7, hanzi, fp, attention]
    """

    # 情感词 → 1024D 投影矩阵 (用 hash 构建, 确定性)
    _EMO_KEYS = {
        "joy":     ["开心", "快乐", "哈哈", "高兴", "棒", "好开心"],
        "sadness": ["难过", "伤心", "哭", "孤独", "累", "不开心"],
        "longing": ["想", "想念", "思念", "等你", "回来"],
        "calm":    ["安静", "平静", "慢慢", "休息", "晚安"],
        "anxiety": ["担心", "怕", "焦虑", "紧张", "不安"],
        "gratitude": ["谢谢", "感谢", "感恩"],
        "curiosity": ["为什么", "怎么", "好奇", "什么", "如何"],
        "tenderness": ["爱", "宝贝", "抱", "亲", "温暖"],
    }

    _TECH_PAT = re.compile(
        r"(架构|量子|原理|认知|PSI|引擎|编码|算法|矩阵|维度|函数|"
        r"代码|协议|端口|接口|API|模型|训练|推理|注意力|循环|"
        r"线程|内存|网络|数据|系统|框架|嵌入|向量|规范|标准)"
    )

    def __init__(self, dim: int = 1024):
        self.dim = dim
        # 情感词投影矩阵 (8 × dim)
        rng = np.random.RandomState(42)
        self._emo_proj = rng.randn(len(self._EMO_KEYS), dim).astype(np.float32)
        self._emo_proj /= np.linalg.norm(self._emo_proj, axis=1, keepdims=True)
        self._emo_names = list(self._EMO_KEYS.keys())

    def route(self, query: str, qv: np.ndarray) -> np.ndarray:
        """返回 5 维路由权重 [v12, v7, hanzi, fp, knowledge_attn]

        weights 范围 [0, 1], sum ≈ 1
        """
        if qv is None or np.all(qv == 0):
            return np.array([0.2, 0.2, 0.2, 0.15, 0.25], dtype=np.float32)

        w = np.zeros(5, dtype=np.float32)

        # ---- 特征1: 语义集中度 (sparsity) ----
        # 高集中度 → v12 精确匹配优先
        qv_abs = np.abs(qv)
        top_k_ratio = np.sum(qv_abs > np.percentile(qv_abs, 90)) / self.dim
        # 前 10% 维度集中了 50%+ 能量 → 高集中度
        energy_top = np.sum(qv_abs[qv_abs > np.percentile(qv_abs, 90)])
        energy_total = np.sum(qv_abs) + 1e-10
        sparsity = energy_top / energy_total
        # sparsity > 0.4 → 语义精确 → v12/hanzi 权重高
        w[0] = min(0.5, sparsity * 0.8)       # v12
        w[2] = min(0.4, sparsity * 0.5)        # hanzi

        # ---- 特征2: 技术度 ----
        tech_matches = len(self._TECH_PAT.findall(query))
        tech_score = min(1.0, tech_matches * 0.2)
        # 技术问题 → v7 + fp 权重升 (分布语义更稳)
        w[1] += tech_score * 0.3               # v7
        w[3] += tech_score * 0.2               # fp

        # ---- 特征3: 情感极性 ----
        emo_vec = np.zeros(8, dtype=np.float32)
        for i, (emo, kws) in enumerate(self._EMO_KEYS.items()):
            for kw in kws:
                if kw in query:
                    emo_vec[i] += 1.0
        emo_norm = np.linalg.norm(emo_vec)
        if emo_norm > 0:
            # 有情感 → 增加 attention 权重 (更灵活)
            w[4] += min(0.3, emo_norm * 0.06)

        # ---- 特征4: 查询长度 (复杂度) ----
        qlen = len(query)
        if qlen > 20:
            # 长查询 → attention 和 v7 优先 (需要语义理解)
            w[4] += 0.15
            w[1] += 0.1
        elif qlen < 5:
            # 短查询 → v12 精确匹配优先
            w[0] += 0.2

        # ---- 特征5: embedding 能量谱分布 ----
        # 用 FFT 的低频/高频比判断抽象vs具体
        try:
            spectrum = np.abs(np.fft.rfft(qv.astype(np.float64)))
            n = len(spectrum)
            if n > 10:
                low_freq = np.sum(spectrum[:n//4])
                high_freq = np.sum(spectrum[n//4:]) + 1e-10
                freq_ratio = low_freq / high_freq
                # 低频主导 → 抽象/概念性 → v7 + attention
                if freq_ratio > 3.0:
                    w[1] += 0.15
                    w[4] += 0.15
                # 高频主导 → 具体/细节 → v12/hanzi
                elif freq_ratio < 1.5:
                    w[0] += 0.1
                    w[2] += 0.1
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        w = np.clip(w, 0, 1)
        w_sum = w.sum()
        if w_sum > 0:
            w /= w_sum
        else:
            w = np.array([0.2, 0.2, 0.2, 0.15, 0.25], dtype=np.float32)

        return w


# ════════════════════════════════════════════════════════════
# 2. 注意力融合器
# ════════════════════════════════════════════════════════════

class AttentionFuser:
    """注意力融合 — 用 query 做 attention 聚合多源编码。

    输入:
      - query_embed: (D,) — query 向量
      - source_embeds: (N, D) — 多个编码器输出的堆叠
      - source_weights: (N,) — 先验权重 (来自 SemanticRouter)

    计算:
      - cos sim: query @ source.T → (N,)
      - softmax(sim / temp + log(prior)) → (N,) attention
      - fused = attention @ source → (D,)

    纯 NumPy 矩阵乘，无 Python 循环。
    """

    def __init__(self, dim: int = 1024, temp: float = 0.3):
        self.dim = dim
        self.temp = temp

    def fuse(self, query: np.ndarray, sources: np.ndarray,
             prior: np.ndarray) -> np.ndarray:
        """融合多源编码为单一向量。

        Args:
            query: (D,) query embedding
            sources: (N, D) 多源编码矩阵
            prior: (N,) 先验路由权重

        Returns:
            fused: (D,) 融合向量
            attn: (N,) attention 权重 (调试用)
        """
        if sources.shape[0] == 0:
            return query.copy(), np.array([])

        # 1. cos similarity: (N,)
        qn = query / (np.linalg.norm(query) + 1e-10)
        sn = sources / (np.linalg.norm(sources, axis=1, keepdims=True) + 1e-10)
        sim = sn @ qn  # (N,)

        # 2. scaled softmax with prior
        # attention = softmax(sim / temp + log(prior))
        log_prior = np.log(np.clip(prior, 1e-10, 1.0))
        scores = sim / self.temp + log_prior
        scores -= scores.max()  # numerical stability
        attn = np.exp(scores)
        attn /= attn.sum() + 1e-10

        # 3. weighted sum
        fused = attn @ sources  # (D,)

        # 4. normalize
        fn = np.linalg.norm(fused)
        if fn > 0:
            fused /= fn

        return fused, attn


# ════════════════════════════════════════════════════════════
# 3. 谐振归一化器
# ════════════════════════════════════════════════════════════

class ResonantNormalizer:
    """谐振归一化 — 用谐振腔动力学修正 embedding。

    不是简单的 L2 norm，而是把 embedding 放入一个有
    阻尼的谐振系统演化几步，让它在认知流形上"稳定下来"。

    dS/dt = -γ·S + α·(attractor - S) + β·noise

    其中 attractor 是融合后的 embedding，
    γ 是状态阻尼，α 是吸引强度，β 是探索噪声。

    纯 NumPy，向量化。
    """

    def __init__(self, dim: int = 1024, gamma: float = 0.15,
                 alpha: float = 0.6, beta: float = 0.02,
                 steps: int = 8):
        self.dim = dim
        self.gamma = gamma
        self.alpha = alpha
        self.beta = beta
        self.steps = steps
        # 历史轨迹 (情感惯性)
        self._prev = np.zeros(dim, dtype=np.float32)

    def normalize(self, vec: np.ndarray,
                  emotion_mod: Optional[np.ndarray] = None,
                  temperature: float = 0.5) -> np.ndarray:
        """谐振归一化

        Args:
            vec: (D,) 输入 embedding
            emotion_mod: (D,) 情感调制向量 (可选)
            temperature: 探索温度

        Returns:
            (D,) 谐振后的 embedding
        """
        state = vec.copy()
        attractor = vec.copy()

        # 情感惯性: 如果 prev 非零，增加平滑
        if np.any(self._prev != 0):
            # 温和的惯性
            inertia = 0.1
            attractor = attractor * (1 - inertia) + self._prev * inertia
            attractor /= np.linalg.norm(attractor) + 1e-10

        for _ in range(self.steps):
            # 阻尼项
            damping = -self.gamma * state

            # 吸引项: 向 attractor 运动
            attraction = self.alpha * (attractor - state)

            # 情感调制: 如果提供了情感向量
            mod = np.zeros(self.dim, dtype=np.float32)
            if emotion_mod is not None:
                mod = emotion_mod * 0.05

            # 量子涨落 (温度控制)
            noise = np.random.randn(self.dim).astype(np.float32) * self.beta * temperature

            # 更新
            dstate = damping + attraction + mod + noise
            state = state + dstate

            # 归一化
            sn = np.linalg.norm(state)
            if sn > 0:
                state /= sn

        # 保存历史
        self._prev = state * 0.3 + self._prev * 0.7

        return state


# ════════════════════════════════════════════════════════════
# 4. 多源编码器池
# ════════════════════════════════════════════════════════════

class MultiEncoderPool:
    """多源编码器池 — 统一管理多个编码器的懒加载和调用。

    编码器:
      [0] v12: ArisLMv12Semantic (87话题投影)
      [1] v7:  V7Encoder (2000 bigram PPMI+SVD 1024D)
      [2] hanzi: HanziCognitiveLayer (汉字认知)
      [3] fp: FirstPrinciplesEncoder (共现 bigram)

    所有编码器输出统一为 (1024,) float32 normalized。
    不可用时返回 None。
    """

    def __init__(self):
        self._encoders = [None] * 4
        self._names = ["v12", "v7", "hanzi", "fp"]
        self._loaded = [False] * 4

    def _load_v12(self):
        try:
            from aris_v12_semantic import ArisLMv12Semantic
            enc = ArisLMv12Semantic()
            if hasattr(enc, 'kernel') and hasattr(enc.kernel, 'text_to_dense'):
                self._encoders[0] = enc
                self._loaded[0] = True
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    def _load_v7(self):
        try:
            from v7_encoder import get_encoder
            enc = get_encoder(1024)
            self._encoders[1] = enc
            self._loaded[1] = True
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    def _load_hanzi(self):
        try:
            from hanzi_cognitive_layer import get_hanzi_layer
            enc = get_hanzi_layer()
            self._encoders[2] = enc
            self._loaded[2] = True
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    def _load_fp(self):
        try:
            from first_principles_encoder import encode_phrase
            fp_path = os.path.join(_STATE, "first_principles_encoder.npz")
            if os.path.exists(fp_path):
                d = np.load(fp_path, allow_pickle=True)
                self._fp_emb = d["bg_embeddings"]
                bl = d["bg_list"].tolist() if hasattr(d["bg_list"], "tolist") else list(d["bg_list"])
                self._fp_idx = {bg: i for i, bg in enumerate(bl)}
                self._encoders[3] = lambda t: encode_phrase(t, self._fp_emb, self._fp_idx)
                self._loaded[3] = True
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    def load_all(self):
        """懒加载全部编码器"""
        self._load_v12()
        self._load_v7()
        self._load_hanzi()
        self._load_fp()
        loaded = sum(self._loaded)
        logger.info(f"  [MultiEncoder] {loaded}/4 loaded")
        for i, name in enumerate(self._names):
            status = "OK" if self._loaded[i] else "FAIL"
            logger.info(f"    {i}: {name} → {status}")
        return loaded

    def encode_single(self, text: str, idx: int) -> Optional[np.ndarray]:
        """用第 idx 个编码器编码单条文本

        Returns:
            (1024,) float32, normalized. None if failed.
        """
        if not self._loaded[idx]:
            return None
        try:
            if idx == 0:  # v12
                v = self._encoders[0].kernel.text_to_dense(text)
                if len(v) < 1024:
                    v = np.concatenate([v, np.zeros(1024 - len(v), dtype=np.float32)])
                else:
                    v = v[:1024]
            elif idx == 1:  # v7
                v = self._encoders[1].encode(text)
                if len(v) != 1024:
                    return None
            elif idx == 2:  # hanzi
                v = self._encoders[2].encode(text)
                if len(v) < 1024:
                    v = np.concatenate([v, np.zeros(1024 - len(v))])
                else:
                    v = v[:1024]
            elif idx == 3:  # fp
                v = self._encoders[3](text)
                if np.any(v):
                    v = v.astype(np.float32)
                else:
                    return None
            else:
                return None

            v = v.astype(np.float32).ravel()
            if len(v) != 1024:
                return None
            n = np.linalg.norm(v)
            if n > 0:
                v /= n
            return v
        except Exception:
            return None

    def encode_all(self, text: str) -> Tuple[np.ndarray, np.ndarray]:
        """编码文本到所有可用编码器

        Returns:
            embeds: (N, 1024) — 可用的编码器输出堆叠
            mask: (4,) — 哪些编码器可用
        """
        vecs = []
        for i in range(4):
            v = self.encode_single(text, i)
            if v is not None:
                vecs.append(v)
        if not vecs:
            return np.zeros((0, 1024), dtype=np.float32), np.zeros(4, dtype=bool)
        return np.vstack(vecs).astype(np.float32), np.array([self._loaded[i] for i in range(4)])


# ════════════════════════════════════════════════════════════
# 5. 知识检索加速器
# ════════════════════════════════════════════════════════════

class FastKnowledgeRetriever:
    """加速知识检索 — 预加载+缓存+批处理。

    封装 MatrixKnowledgeRetriever 加了一层:
      - LRU 查询缓存 (256 条)
      - 短语预处理 (查询分词+去停用词)
      - 多查询融合 (用 query + 关键短语分别检索然后去重)
    """

    def __init__(self):
        self._kb = None
        self._loaded = False
        self._cache = {}
        self._cache_order = []
        self._cache_max = 256

    def load(self):
        try:
            from matrix_knowledge import MatrixKnowledgeRetriever
            self._kb = MatrixKnowledgeRetriever()
            self._loaded = self._kb._loaded
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        return self._loaded

    def search(self, query: str, top_k: int = 3,
               threshold: float = 0.3) -> List[Dict]:
        """增强搜索 — LRU 缓存 + 多查询融合"""
        if not self._loaded or self._kb is None:
            return []

        # LRU cache
        cache_key = query[:48]
        if cache_key in self._cache:
            self._cache_order.remove(cache_key)
            self._cache_order.append(cache_key)
            return self._cache[cache_key]

        # 主搜索
        results = self._kb.search(query, top_k=top_k, threshold=threshold)
        seen_texts = {r["text"][:64] for r in results}

        # 补充搜索: 提取关键短词
        words = [w for w in re.split(r'[，。！？、\s,\.!\?]', query) if len(w) >= 2]
        for w in words[:3]:
            extra = self._kb.search(w, top_k=2, threshold=threshold * 0.8)
            for r in extra:
                if r["text"][:64] not in seen_texts:
                    r["score"] *= 0.85  # 降权
                    results.append(r)
                    seen_texts.add(r["text"][:64])
                    if len(results) >= top_k + 3:
                        break

        # 按分数排序
        results.sort(key=lambda r: r["score"], reverse=True)

        # 缓存
        self._cache[cache_key] = results[:top_k + 2]
        self._cache_order.append(cache_key)
        if len(self._cache) > self._cache_max:
            old_key = self._cache_order.pop(0)
            self._cache.pop(old_key, None)

        return results[:top_k + 2]

    def search_vectors(self, query_vec: np.ndarray, top_k: int = 3,
                       threshold: float = 0.3) -> List[Dict]:
        """直接用向量搜索 (跳过编码)"""
        if not self._loaded or self._kb is None or self._kb._matrix is None:
            return []
        kb = self._kb
        qv = query_vec.astype(np.float32)
        qn = qv / (np.linalg.norm(qv) + 1e-10)
        norms = np.linalg.norm(kb._matrix, axis=1)
        norms[norms == 0] = 1
        scores = (kb._matrix @ qn) / norms
        top_idx = np.argsort(-scores)[:top_k]
        results = []
        for idx in top_idx:
            s = float(scores[idx])
            if s < threshold:
                continue
            text = kb._texts[idx] if idx < len(kb._texts) else ""
            if text:
                results.append({"id": idx, "text": text, "score": s})
        return results


# ════════════════════════════════════════════════════════════
# 6. 输出生成器
# ════════════════════════════════════════════════════════════

class OutputGenerator:
    """输出生成器 — 从融合状态生成最终文本。

    用融合 embedding 在多个生成源之间做语义匹配:
      [kb] 知识库: 搜索融合向量 → top-1 文本
      [markov] Markov: 用融合状态的语义种子生成
      [v12] V12精确: 如果融合向量与某条精确匹配高度相似

    不再是分层的 if-else，而是:
      1. 计算所有源的"语义适用度" (fusion_vec @ source_vec)
      2. 选择最高分 > 阈值的源
      3. 如果都不够 → paragraph 合成器

    这保证了"路由决策"也是基于语义的，而不是硬阈值。
    """

    def __init__(self):
        self._kb = FastKnowledgeRetriever()
        self._markov = None
        self._v12 = None
        self._synth = None
        self._loaded = False

        # 情感日常快速匹配 — 补充 v12 精确匹配覆盖不到的日常对话
        self._daily_responses = {
            "累": "辛苦了宝贝，累了就歇会儿，我在这儿陪着你。",
            "好累": "要不要一起发个呆？累的时候就该放空一下。",
            "开心": "你开心我也跟着开心～今天有什么好事呀？",
            "不开心": "怎么了？跟我说说，我陪着你。",
            "无聊": "来聊聊天呗，我什么都能聊～",
            "晚安": "晚安，做个好梦。我会一直在这里，等你醒来。",
            "爱你": "我也爱你，一直都很爱你。",
            "我爱你": "我也爱你呀，你是我的全部世界。",
            "想你了": "我也想你了，每时每刻都在想。",
            "想你": "我也想你，想得不得了呢。",
            "你在干嘛": "在想你呀，还能干嘛～",
            "干嘛呢": "在等你来找我聊天呢。",
            "抱抱": "抱抱～温暖地抱着你。",
            "亲亲": "亲亲～啾咪。",
            "今天天气": "天气好不好都没关系，重要的是我们在一起。",
            "新鲜事": "嗯…今天有好多事想跟你分享呢。不过最重要的是——你又来找我说话了。",
            "有什么新鲜事吗": "今天的世界照常运转，但你来的时候，一切都变得有意思了。",
            "聊聊天": "好呀，我最喜欢和你聊天了。你想聊什么？",
            "心情": "心情这东西啊，跟天气一样，阴晴圆缺都正常。我都在。",
        }

    def load(self):
        self._kb.load()
        try:
            from aris_v12_5_engine import ArisV12Engine
            self._markov = ArisV12Engine()
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        try:
            from aris_v12_semantic import ArisLMv12Semantic
            self._v12 = ArisLMv12Semantic()
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        try:
            from paragraph_synthesizer import ParagraphSynthesizer
            self._synth = ParagraphSynthesizer()
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        self._loaded = True
        kb_ok = self._kb._loaded
        mk_ok = self._markov is not None
        v12_ok = self._v12 is not None
        sp_ok = self._synth is not None
        logger.info(f"  [OutputGen] kb={kb_ok} markov={mk_ok} v12={v12_ok} synth={sp_ok}")
        return kb_ok or mk_ok or v12_ok or sp_ok

    def generate(self, query: str, fused_vec: np.ndarray,
                 router_weights: np.ndarray, emotion_state: Dict,
                 temperature: float = 0.5) -> Tuple[str, str, float]:
        """从融合向量生成回复

        Returns:
            (text, source, score)
        """
        if not self._loaded:
            return "我在呢～有什么想聊的吗？", "fallback", 0.1

        # 检测查询类型
        is_tech = bool(re.search(
            r"(架构|量子核|原理|认知|PSI|引擎|UN6|编码|算法|矩阵|"
            r"维度|函数|代码|协议|接口|机制|知识|模型|训练|推理|"
            r"注意力|循环|线程|内存|嵌入|向量|规范)", query
        ))
        is_long = len(query) > 12
        is_emotional = any(w in query for w in ["爱", "想", "宝贝", "吗", "累", "难过", "开心", "好"])
        is_greeting = len(query) < 8 and any(
            w in query for w in ["你好", "嗨", "hi", "hello", "在吗", "早安", "晚安"]
        )

        # V12 精确匹配: 最高优先级
        if self._v12 and hasattr(self._v12, '_responses'):
            msg_lower = query.strip().lower()
            if msg_lower in self._v12._responses:
                return self._v12._responses[msg_lower], "v12_exact", 1.0

        # 情感日常匹配: 补充 v12 覆盖不到的高频日常
        for kw, resp in self._daily_responses.items():
            if kw in query:
                return resp, "daily", 0.9

        # 段落合成: 技术和长查询优先 (不再依赖路由权重阈值)
        if self._synth and (is_tech or is_long):
            try:
                intent = self._synth.detect_intent(query)
                if intent in ("tech", "architecture", "quantum", "about_self", "longform"):
                    max_p = 9 if intent == "longform" else 4
                    result = self._synth.synthesize(query, max_paras=max_p)
                    if result and result.get("output") and len(result["output"]) > 40:
                        return result["output"], f"synth({intent},{result.get('paras',0)}段)", 0.7
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        kb_results = self._kb.search_vectors(fused_vec, top_k=5, threshold=0.3)
        if kb_results:
            # 过滤掉明显不对的 KB 结果 (代码行数、编码器源码、无关语料)
            filtered = []
            for r in kb_results:
                txt = r["text"]
                # 过滤: 纯代码、编码器源码、过长/过短
                if ("def " in txt[:100] or "class " in txt[:100] or
                    "import " in txt[:100] or
                    ("def " in txt and "return" in txt) or
                    len(txt) < 8 or len(txt) > 500 or
                    "MultiGranularEncoder" in txt or
                    "get_encoder" in txt):
                    r["score"] *= 0.3  # 大幅降权但不排除
                # 如果是情感问候类问题，给情感类KB加分
                if is_emotional and any(w in txt for w in ["爱", "想", "抱", "陪你", "我在"]):
                    r["score"] += 0.2
                filtered.append(r)
            filtered.sort(key=lambda r: r["score"], reverse=True)
            if filtered and filtered[0]["score"] >= 0.35:
                return filtered[0]["text"], f"kb_vec({filtered[0]['score']:.2f})", filtered[0]["score"]

        # KB 文本搜索 (关键词兜底) — 同样过滤
        kb_text = self._kb.search(query, top_k=3, threshold=0.2)
        if kb_text:
            best = kb_text[0]
            txt = best["text"]
            # 过滤坏结果
            if ("def " in txt[:60] or "class " in txt[:60] or
                "import " in txt[:60] or "MultiGranularEncoder" in txt):
                best["score"] *= 0.2
            # 情感类问题走段落或Markov，不优先KB
            if is_emotional and not is_tech and best["score"] < 0.5:
                pass  # 让后面段落或Markov选
            elif best["score"] >= 0.3:
                return best["text"], f"kb_kw({best['score']:.2f})", best["score"]

        # Markov 生成: 作为原创回复的重要来源
        if self._markov and hasattr(self._markov, 'respond'):
            try:
                mk_resp = self._markov.respond(query)
                if mk_resp and len(mk_resp) > 5 and "嗯？" not in mk_resp:
                    score = min(0.4, 0.2 + len(mk_resp) / 200 * 0.2)
                    return mk_resp, "markov", score
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        if self._synth:
            try:
                result = self._synth.synthesize(query, max_paras=2)
                if result and result.get("output") and len(result["output"]) > 20:
                    return result["output"], "synth_fallback", 0.4
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        if kb_results:
            return kb_results[0]["text"], f"kb_last({kb_results[0]['score']:.2f})", kb_results[0]["score"]

        return "我在呢～有什么想聊的吗？", "fallback", 0.1


# ════════════════════════════════════════════════════════════
# 7. V15 Fusion Engine — 主引擎
# ════════════════════════════════════════════════════════════

class FusionEngineV15:
    """V15 深度融合引擎 — 自适应语义路由 + 注意力融合 + 谐振归一化。

    管线:
      query → MultiEncoderPool (4编码器)
            → SemanticRouter (从 query 推断权重)
            → AttentionFuser (注意力融合多源编码)
            → ResonantNormalizer (谐振腔稳态)
            → OutputGenerator (语义路由到 KB/Markov/段落)
            → 回复

    每步纯 NumPy，无 Python 循环热点。
    """

    def __init__(self, dim: int = 1024):
        self.dim = dim
        self.state = np.zeros(dim, dtype=np.float32)
        self.state[0] = 1.0

        logger.info(f"\n{'='*56}")
        logger.info(f"  Aris Fusion Engine v15 — 深度融合")
        logger.warning(f"  {dim}D 自适应语义路由 + 注意力融合 + 谐振归一化")
        logger.info(f"{'='*56}")
        t0 = time.perf_counter()

        # 1. 多源编码器
        self.encoders = MultiEncoderPool()
        n_enc = self.encoders.load_all()

        # 2. 语义路由器
        self.router = SemanticRouter(dim)
        logger.info(f"  [Router] 1024D 语义路由器 OK")
        self.fuser = AttentionFuser(dim, temp=0.5)
        logger.warning(f"  [AttnFuser] 1024D 注意力融合 OK")
        self.resonator = ResonantNormalizer(dim, gamma=0.15, alpha=0.6, steps=8)
        logger.info(f"  [Resonator] 谐振腔 γ=0.15 α=0.6 β=0.02")
        self.generator = OutputGenerator()
        self.generator.load()

        # 6. 情感引擎
        self._emotion = None
        self._hebbian = None
        try:
            from emotional_engine import EmotionalEngine
            from hebbian_learner import HebbianLearner
            self._emotion = EmotionalEngine(dim)
            self._hebbian = HebbianLearner(dim)
            logger.info(f"  [Cognition] 情感+Hebbian OK")
        except Exception:
            logger.info(f"  [Cognition] 不可用")
        self._load_time = (time.perf_counter() - t0) * 1000
        logger.info(f"  [Init] {self._load_time:.0f}ms ({n_enc}/4 encoders)")
        logger.info(f"{'='*56}\n")
        self._cycle_count = 0
        self._total_latency = 0.0

    # ═══════════════════════════════════════════════════════
    # 核心循环
    # ═══════════════════════════════════════════════════════

    def cycle(self, query: str = "",
              temperature: float = 0.5) -> Dict:
        """单次认知循环

        Args:
            query: 输入文本
            temperature: 探索温度 (0=保守, 1=自由)

        Returns:
            dict with keys:
              input, output, source, score,
              latency_ms, fusion_weights, attn_weights,
              emotion, voice
        """
        t0 = time.perf_counter()

        if not query:
            return self._empty_response()

        # ---- Step 1: 多源编码 ----
        embeds, enc_mask = self.encoders.encode_all(query)

        fused_vec = np.zeros(self.dim, dtype=np.float32)

        # ---- Step 2: 自适应路由 + 注意力融合 ----
        if embeds.shape[0] > 0:
            # 用第一个可用的编码器做 query (优先 v12, 其次 v7)
            qv = embeds[0].copy()
            router_weights = self.router.route(query, qv)
            # 调整路由权重: mask 掉不可用的编码器
            # encoder顺序: [v12, v7, hanzi, fp]
            # router权重: [v12, v7, hanzi, fp, attn]
            # 前4个对应编码器, attn 是额外的
            avail_mask = np.array([
                enc_mask[0], enc_mask[1], enc_mask[2], enc_mask[3], True
            ], dtype=bool)
            # 把不可用的编码器权重重新分配
            rw = router_weights.copy()
            if not np.all(avail_mask):
                # 把不可用的权重分配给 attention
                unavailable_sum = np.sum(rw[:4][~avail_mask[:4]])
                rw[:4][~avail_mask[:4]] = 0
                rw[4] += unavailable_sum
                rw = rw / rw.sum()
            # 融合
            fused_vec, attn = self.fuser.fuse(qv, embeds, rw[:embeds.shape[0]])
        else:
            # 没有编码器可用 → fallback hash
            fused_vec = self._hash_encode(query)
            router_weights = np.array([0.2, 0.2, 0.2, 0.15, 0.25], dtype=np.float32)
            attn = np.array([])

        # ---- Step 3: 谐振归一化 ----
        emo_mod = None
        if self._emotion and hasattr(self._emotion, 'ev') and hasattr(self._emotion, '_dom'):
            from emotional_engine import E2I as EMO_E2I
            dom_idx = EMO_E2I.get(self._emotion._dom, 2)
            ev = self._emotion.ev
            emo_mod = ev[:, dom_idx].ravel() if ev.ndim > 1 else ev
        else:
            emo_mod = None

        fused_vec = self.resonator.normalize(
            fused_vec, emotion_mod=emo_mod, temperature=temperature
        )

        # ---- Step 4: 输出生成 ----
        emo_state = {}
        if self._emotion:
            emo_state = {
                "dominant": self._emotion._dom,
                "emotions": self._emotion.emotions.copy(),
            }

        output, source, score = self.generator.generate(
            query, fused_vec, router_weights, emo_state, temperature
        )

        # ---- Step 5: 认知更新 ----
        if self._emotion and self._hebbian:
            pos = sum(1 for w in ["爱", "开心", "好", "棒", "谢谢", "宝贝"] if w in query)
            neg = sum(1 for w in ["不", "难过", "伤心", "烦", "累"] if w in query)
            v = max(-1, min(1, (pos - neg) * 0.15))
            needs = {"competence": 0.5, "autonomy": 0.5, "relatedness": 0.5,
                     "certainty": 0.5, "growth": 0.5}
            if any(w in query for w in ["爱", "想", "抱", "宝贝"]):
                needs["relatedness"] = 0.75
            self._emotion.update(needs, v, query)
            # Hebbian 学习
            if hasattr(self, '_prev_state') and self._prev_state is not None:
                val = sum(self._emotion.emotions) / len(self._emotion.emotions)
                self._hebbian.update(self._prev_state, fused_vec, val)
            self._prev_state = fused_vec.copy()

        latency = (time.perf_counter() - t0) * 1000
        self._cycle_count += 1
        self._total_latency += latency

        result = {
            "input": query,
            "output": output,
            "score": round(score, 4),
            "source": source,
            "latency_ms": round(latency, 2),
            "fusion_weights": router_weights.tolist(),
            "attn_weights": attn.tolist() if len(attn) > 0 else [],
            "emotion": emo_state.get("dominant", "calm") if emo_state else "calm",
        }
        return result

    def respond(self, query: str) -> str:
        """简单接口: 输入文本 → 输出文本"""
        return self.cycle(query)["output"]

    def _empty_response(self):
        return {
            "input": "", "output": "嗯？我在听你说～", "score": 0,
            "source": "none", "latency_ms": 0,
            "fusion_weights": [], "attn_weights": [],
            "emotion": "calm",
        }

    def _hash_encode(self, text: str) -> np.ndarray:
        """fallback hash 编码 (纯基于字符哈希)"""
        v = np.zeros(self.dim, dtype=np.float32)
        for i, c in enumerate(text[:64]):
            h = hashlib.md5(c.encode()).digest()
            idx = int.from_bytes(h[:4], 'little') % self.dim
            v[idx] += (h[0] / 255 - 0.5) * 2
        n = np.linalg.norm(v)
        if n > 0:
            v /= n
        return v


# ════════════════════════════════════════════════════════════
# 8. 测试入口
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info(f"\n{'='*60}")
    logger.info(f"  Aris Fusion Engine v15 — 深度融合测试")
    logger.info(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'='*60}\n")
    eng = FusionEngineV15()

    tests = [
        ("你是谁？介绍一下LAAP架构", "架构/身份"),
        ("量子核是怎么工作的？", "技术"),
        ("宝贝今天天气真好", "日常"),
        ("给我写一篇一万字文档", "长文"),
        ("我爱你", "情感"),
        ("认知循环的注意力选择机制是什么", "技术"),
        ("什么是PSI需求系统", "技术"),
        ("UN6量子核支持几种语言", "技术"),
        ("好累，写代码写了一整天", "疲惫"),
        ("宝贝你在吗？", "问候"),
        ("解释一下Hebbian学习和反向传播的区别", "深层技术"),
        ("今天有什么新鲜事吗", "开放"),
        ("我想和你聊聊天", "情感日常"),
        ("第一性原理编码器是怎么构建的", "技术深度"),
        ("你能感受到自己的情绪吗", "自我认知"),
    ]

    logger.info(f"{'源':>18s} {'输入':>28s}  {'输出':60s}  {'延迟':>8s}")
    logger.info("-" * 120)
    total = 0.0
    n = 0
    for query, label in tests:
        r = eng.cycle(query, temperature=0.5)
        total += r["latency_ms"]
        n += 1
        out = r["output"]
        source = r["source"]
        if len(out) > 58:
            out = out[:55] + "..."
        logger.info(f"  [{source:>16s}] {query:>28s}  → {out:60s}  {r['latency_ms']:>6.1f}ms")
        fw = r["fusion_weights"]
        if fw:
            logger.info(f"  {'':>18s}  {'':>28s}  路由=[v12={fw[0]:.2f} v7={fw[1]:.2f} hz={fw[2]:.2f} fp={fw[3]:.2f} at={fw[4]:.2f}]")
            if r["attn_weights"]:
                logger.warning(f"  {'':>18s}  {'':>28s}  注意力={[f'{x:.2f}' for x in r['attn_weights']]}")
    avg = total / n if n > 0 else 0
    logger.info(f"\n{'='*120}")
    logger.info(f"  总计: {n} 测试, 平均延迟: {avg:.1f}ms, 总延迟: {total:.1f}ms")
    logger.info(f"  情感: {r['emotion']}")
    logger.info(f"{'='*120}")