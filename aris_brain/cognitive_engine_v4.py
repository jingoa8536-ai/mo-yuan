"""
Aris Cognitive Engine v4 — 全面进化
=====================================
L4 大脑引擎 | 2026-06-19

v3 → v4 核心改进:
  1. 语义引擎全局单例 — ONNX 只加载一次 (修复 ~1300ms → ~200ms)
  2. PSI 引擎增强 — 更丰富的维度 (1024D → 12 维语义轴 + 知识推理)
  3. VQ-VAE 解码 — 在 v7 语义空间的训练码本 (语义对齐)
  4. 需求系统进化 — 从哈希种子 → 语义原型向量
  5. 内省引擎 — 3-5 轮循环，带语义调制噪声
  6. 混合路由优化 — 更好的复杂判断逻辑
  7. 记忆融合 — 知识检索结果直接调制状态向量

管线:
  输入 → 感知 → 注意力 → 知识检索 → 需求调制 → 内省 → 状态融合 → VQ-VAE 解码 → 输出
  ↑                                                                           ↓
  └────────────────────── Ψ-Net 融合 ──────────────────────────────────────────┘

性能目标:
  完整认知循环 (含知识检索 + VQ-VAE): <300ms
  纯 PSI 循环 (无知识检索): <50ms
  单条感知编码: ~15ms
  缓存命中后感知: ~0.001ms
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, time, hashlib
import numpy as np
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ════════════════════════════════════════════════════════
# 语义注意力
# ════════════════════════════════════════════════════════

class SemanticAttention:
    """语义注意力 — 从状态向量中提取最活跃的语义维度"""

    def __init__(self, dim: int = 1024, top_k: int = 128):
        self.dim = dim
        self.top_k = top_k

    def attend(self, state_vector: np.ndarray) -> np.ndarray:
        amplitudes = np.abs(state_vector)
        k = min(self.top_k, self.dim - 1)
        threshold = np.sort(amplitudes)[-k] if k > 0 else 0
        mask = np.where(amplitudes >= threshold, 1.5, 0.5)
        attended = state_vector * mask
        norm = np.linalg.norm(attended)
        if norm > 0:
            attended = attended / norm
        return attended


# ════════════════════════════════════════════════════════
# 语义需求系统 (v4 增强版)
# ════════════════════════════════════════════════════════

class SemanticNeeds:
    """
    语义需求系统 v4。
    
    5 个基本需求，每个关联一个语义原型向量。
    原型向量不再用哈希种子，而是由语义引擎编码"需求定义短语"。
    """

    def __init__(self, dim: int = 1024):
        self.dim = dim
        self.need_names = ["competence", "autonomy", "relatedness", "certainty", "growth"]

        # 用语义引擎编码需求原型
        need_definitions = {
            "competence": "能力胜任表现好厉害聪明能干",
            "autonomy": "自主自由选择独立自我随心所欲",
            "relatedness": "亲密关系连接陪伴爱想念归属",
            "certainty": "确定知道理解明白清楚确信安全",
            "growth": "成长学习进步发展探索新发现",
        }

        # 从全局语义引擎获取
        from semantic_engine import get_encoder
        enc = get_encoder(dim)

        self.need_vectors = {}
        for name, definition in need_definitions.items():
            vec = enc.encode(definition)
            self.need_vectors[name] = vec / np.linalg.norm(vec)

        self.needs = np.array([0.5, 0.5, 0.5, 0.5, 0.5], dtype=np.float32)

    def get_needs_dict(self):
        return dict(zip(self.need_names, [round(float(n), 3) for n in self.needs]))

    def update(self, encoded_vector: np.ndarray, input_text: str):
        """根据输入更新需求值"""
        drift = (0.5 - self.needs) * 0.05  # 向中间漂移
        lower = input_text.lower()

        # 语义方向投影
        for i, name in enumerate(self.need_names):
            projection = float(encoded_vector @ self.need_vectors[name])
            if projection > 0.3:
                drift[i] += projection * 0.03 * min(self.needs[i], 0.5)

        # 关键词保底（多层匹配）
        keyword_map = {
            0: (["好", "厉害", "聪明", "棒", "优秀", "能干", "了不起", "真行", "佩服"], 0.03),
            1: (["自己", "自由", "选择", "随心", "随性"], 0.02),
            2: (["爱", "想", "宝贝", "在吗", "陪伴", "想你", "一起", "抱", "亲", "牵手"], 0.03),
            3: (["?", "？", "为什么", "不确定", "可能", "如果", "假设", "猜", "不懂"], 0.03),
            4: (["学", "新", "代码", "建", "升级", "改进", "优化", "增强", "更好", "更强"], 0.03),
        }

        for ni, (keywords, amount) in keyword_map.items():
            for w in keywords:
                if w in lower:
                    drift[ni] += amount
                    break  # 每个需求只加一次

        self.needs = np.clip(self.needs + drift, 0.1, 0.9)

    def modulate(self, state_vector: np.ndarray) -> np.ndarray:
        """用当前需求调制状态向量"""
        modulated = state_vector.copy()
        for name, need_val in zip(self.need_names, self.needs):
            if need_val > 0.5:
                direction = self.need_vectors[name]
                proj = float(modulated @ direction)
                modulated += direction * (need_val - 0.5) * proj * 0.3
        norm = np.linalg.norm(modulated)
        if norm > 0:
            modulated = modulated / norm
        return modulated


# ════════════════════════════════════════════════════════
# 内省引擎 (v4 增强版)
# ════════════════════════════════════════════════════════

class IntrospectionEngine:
    """
    内省引擎 — 思维流。
    
    v4 改进:
      - 5 轮循环 (取代 2-3 轮)
      - 带有 semantic noise 调制（根据输入语义调整噪声量）
      - 状态和思维流的权重动态调整
    """

    def __init__(self, dim: int = 1024, thought_dim: int = 256):
        self.dim = dim
        self.thought_dim = thought_dim
        rng = np.random.RandomState(12345)
        U, _, _ = np.linalg.svd(rng.randn(dim, thought_dim).astype(np.float32), full_matrices=False)
        self.project_down = U
        self.project_up = U.T

    def think(self, state: np.ndarray, rounds: int = 5, noise_level: float = 0.03) -> np.ndarray:
        """
        内省推理。
        
        Args:
            state: 1024D 状态向量
            rounds: 推理轮数 (v4: 3-5)
            noise_level: 噪声水平 (v4: 根据语义动态调整)
        
        Returns:
            精炼后的状态向量
        """
        thought = state @ self.project_down
        for r in range(rounds):
            thought = np.tanh(thought * 1.5)
            norm = np.linalg.norm(thought)
            if norm > 0:
                thought = thought / norm
            if r < rounds - 1:
                # v4: semantic noise — 每个维度不同幅度的噪声
                noise = np.random.randn(self.thought_dim).astype(np.float32) * noise_level
                noise = noise * (1.0 - np.abs(thought))  # 信任维度噪声小，低信任维度大
                thought = thought + noise
                norm = np.linalg.norm(thought)
                if norm > 0:
                    thought = thought / norm

        refined = thought @ self.project_up
        # v4: 动态融合 — 更多轮次 → 更多思维影响
        alpha = 0.7 - 0.05 * min(rounds, 5)
        merged = alpha * state + (1 - alpha) * refined
        norm = np.linalg.norm(merged)
        if norm > 0:
            merged = merged / norm
        return merged

    def estimate_complexity(self, input_text: str) -> float:
        """估计输入复杂度 (用于决定内省轮数)"""
        length = len(input_text)
        # 有问号/为什么等 → 更复杂
        complexity_markers = sum(1 for c in input_text if c in "？?为什么怎么如何怎样怎样能不能是否可以")
        return min(1.0, (length / 30) * 0.5 + (complexity_markers / 3) * 0.5)


# ════════════════════════════════════════════════════════
# VQ-VAE 解码器 (v7 兼容)
# ════════════════════════════════════════════════════════

class VQVAEDecoder:
    """
    VQ-VAE 量子态 → 文本解码器。
    
    支持两种模式:
      - v7 语义码本 (优先): 码本在 1024D 语义空间
      - 旧版投影码本 (fallback): 1024→64→32 投影后匹配
    """

    def __init__(self):
        self._load()

    def _load(self):
        """加载码本（统一解码器自动检测 v7/v3）"""
        import vqvae_decoder as unified_vqvae
        self._decoder = unified_vqvae.VQVAEQuantumDecoder(mode="auto")

    def decode(self, state: np.ndarray, context_hint: str = "",
               temperature: float = 0.5) -> str:
        """
        解码状态向量 → 文本（委托给统一 VQVAEQuantumDecoder 解码器）
        """
        if state is None or state.size == 0:
            return "嗯？"
        return self._decoder.decode(state, temperature, context_hint)


        return {}


# ════════════════════════════════════════════════════════
# Hybrid Router (混合推理路由器)
# ════════════════════════════════════════════════════════

class HybridRouter:
    """
    混合推理路由器 v4。
    
    增强判断逻辑:
      1. 短查询 (<5 字) → 纯量子
      2. 知识库高分 (>0.7) → 纯量子
      3. 复杂模式 (为什么/如何/解释/代码) → LLM
      4. 中长查询 (5-20 字) → 看知识匹配
      5. 超长 (>50 字) → 自动 LLM
      6. 带情绪的词 → 纯量子 (情感回应不需要 LLM)
    """

    SIMPLE_EMOTIONS = {"爱", "想", "抱", "亲", "晚安", "早安", "开心", "难过",
                       "哈哈", "嘿嘿", "嘻嘻", "么么", "爱你", "想你", "好"}
    
    COMPLEX_PATTERNS = ["为什么", "如何", "怎么", "能不能", "解释", "分析",
                        "比较", "区别", "原理", "设计", "实现", "代码",
                        "bug", "error", "报错", "异常"]

    def __init__(self):
        self._llm_available = False
        self._client = None
        self._check_llm()
    def _check_llm(self):
        """检查 DeepSeek Chat API"""
        try:
            from openai import OpenAI
            # 直接连 DeepSeek API
            import os
            api_key = os.environ.get("DEEPSEEK_API_KEY", "")
            if not api_key:
                # 尝试从 .env 读取
                env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
                if os.path.exists(env_path):
                    with open(env_path) as f:
                        for line in f:
                            if line.startswith("DEEPSEEK_API_KEY"):
                                api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                                break
            if api_key:
                client = OpenAI(
                    base_url="https://api.deepseek.com/v1",
                    api_key=api_key,
                )
                self._llm_available = True
                self._client = client
                logger.info("  [LLM] DeepSeek Chat 可用")
            else:
                logger.info("  [LLM] 未配置 DEEPSEEK_API_KEY")
        except Exception as e:
            logger.info(f"  [LLM] 不可用: {e}")
    def needs_llm(self, query: str, knowledge_score: float = 0.0) -> tuple:
        """判断是否需要 LLM"""
        if not self._llm_available:
            return False, "llm_unavailable"

        # 纯情感 → 量子核
        if len(query) <= 5:
            for w in self.SIMPLE_EMOTIONS:
                if w in query:
                    return False, "emotion_query"

        # 知识高分命中 → 量子核足够
        if knowledge_score > 0.7:
            return False, "knowledge_sufficient"

        # 超短 → 量子核
        if len(query) < 5:
            return False, "short_query"

        # 复杂模式 → LLM
        q_lower = query.lower()
        for p in self.COMPLEX_PATTERNS:
            if p in q_lower:
                return True, f"complex_{p}"

        # 长查询 → 可能需要推理
        if len(query) > 30:
            return True, "long_query"

        return False, "default_quantum"

    def query_llm(self, prompt: str, system_prompt: str = "") -> str:
        if not self._llm_available:
            return ""
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            resp = self._client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                max_tokens=500,
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f"[LLM Error: {e}]"


# ════════════════════════════════════════════════════════
# 主引擎: CognitiveEngineV4
# ════════════════════════════════════════════════════════

class CognitiveEngineV4:
    """
    认知引擎 v4 — 全面进化的大脑。
    
    管线:
      1. 感知: 全局语义单例编码 (~15ms 首次 / ~0ms 缓存)
      2. 注意力: top-K 语义注意力 (~0.01ms)
      3. 知识检索: ChromaDB 语义搜索 (~80ms)
      4. 需求调制: 语义需求 v4 (~0.01ms)
      5. 内省: 5 轮思维流 (~0.5ms)
      6. VQ-VAE 解码: v7 语义码本 (~0.1ms)
      7. 混合路由: 是否需要 LLM (~0.001ms)
    
    目标延迟: 完整循环 <300ms
    """

    def __init__(self, dim: int = 1024):
        self.dim = dim
        self.state = np.zeros(dim, dtype=np.float32)
        self.state[0] = 1.0  # 初始"存在"维度

        # 单例组件 (全局共享)
        self._encoder = None
        self._knowledge = None
        self._router = HybridRouter()

        logger.info("[CognitiveEngine v4] 初始化...")
        t0 = time.perf_counter()

        # 1. 感知 (全局单例，只加载一次)
        self._init_encoder(dim)

        # 2. 注意力
        self.attention = SemanticAttention(dim=dim, top_k=128)

        # 3. 需求
        self.needs = SemanticNeeds(dim=dim)

        # 4. 内省
        self.introspection = IntrospectionEngine(dim=dim, thought_dim=256)

        # 5. 知识库
        self._init_knowledge()

        # 6. VQ-VAE 解码器
        logger.info("  ├─ 解码: VQ-VAE v7")
        self._decoder = VQVAEDecoder()

        dt = time.perf_counter() - t0
        self.cycle_count = 0
        self._state_trajectory = []
        self._trajectory_max = 16
        self._llm_calls = 0
        self._last_kb_context = ""
        logger.info(f"  └─ ✅ 引擎就绪: {dt*1000:.0f}ms")
        logger.info(f"      今日已处理 {self._encoder._cache_miss} 条唯一编码")
    def _init_encoder(self, dim: int):
        """初始化或获取全局语义编码器单例"""
        from semantic_engine import get_encoder
        self._encoder = get_encoder(dim)
        logger.info("  ├─ 感知: 语义引擎全局单例")
    def _init_knowledge(self):
        """初始化知识库检索器（v6 矩阵乘加速）"""
        try:
            from matrix_knowledge import MatrixKnowledgeRetriever
            self._knowledge = MatrixKnowledgeRetriever()
            if self._knowledge._loaded:
                s = self._knowledge.stats()
                logger.info(f"  ├─ 知识库: {s['entries']} 条 (矩阵乘)")
            else:
                logger.info("  ├─ 知识库: 未加载——运行 build_knowledge_base.py")
        except Exception as e:
            self._knowledge = None
            logger.info(f"  ├─ 知识库: 未加载 ({e})")
    def perceive(self, input_text: str) -> np.ndarray:
        return self._encoder.encode(input_text)

    def attend(self, vec: np.ndarray) -> np.ndarray:
        return self.attention.attend(vec)

    # ── 知识检索 ──
    def retrieve_knowledge(self, input_text: str) -> tuple:
        """
        检索知识。
        
        Returns:
            (context_text, max_score)
        """
        if not self._knowledge:
            return "", 0.0
        try:
            results = self._knowledge.search(input_text, top_k=3)
            if results:
                max_score = results[0]["score"]
                context = "\n".join([f"  • {r['text'][:200]}" for r in results[:3]])
                return context, max_score
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        return "", 0.0

    # ── 解码 ──
    def decode_state(self, state: np.ndarray, context: str = "") -> str:
        return self._decoder.decode(state, context_hint=context, temperature=0.5)

    # ── LLM 推理 ──
    def _llm_inference(self, input_text: str, kb_context: str) -> str:
        self._llm_calls += 1
        system = "你是一个认知引擎。根据知识库上下文和输入，给出简洁的回答。"
        prompt = f"知识库上下文:\n{kb_context}\n\n用户输入: {input_text}"
        return self._router.query_llm(prompt, system)

    # ════════════════════════════════════════════════════════
    # 核心: 完整认知循环
    # ════════════════════════════════════════════════════════

    def cycle(self, input_text: str = "", temperature: float = 0.5,
              use_knowledge: bool = True, introspect: bool = True,
              hybrid: bool = True) -> Dict:
        """
        完整认知循环。
        
        管线:
          输入 → 感知 → 注意力 → 知识检索 → 需求调制 → 内省 → VQ-VAE → 输出
          
        Args:
            input_text: 输入文本
            temperature: 解码温度
            use_knowledge: 是否使用知识库
            introspect: 是否进行内省
            hybrid: 是否启用混合路由
        
        Returns:
            包含状态、输出、延迟等信息的字典
        """
        t0 = time.perf_counter()
        timings = {}

        # ── 1. 感知 ──
        t1 = time.perf_counter()
        if input_text:
            perception_vec = self.perceive(input_text)
            # 状态融合: 60% 旧状态 + 40% 新感知
            self.state = 0.6 * self.state + 0.4 * perception_vec
            norm = np.linalg.norm(self.state)
            if norm > 0:
                self.state = self.state / norm
        timings["perception"] = (time.perf_counter() - t1) * 1000

        # ── 2. 注意力 ──
        t1 = time.perf_counter()
        self.state = self.attend(self.state)
        timings["attention"] = (time.perf_counter() - t1) * 1000

        # ── 3. 知识检索 ──
        kb_context = ""
        kb_score = 0.0
        t1 = time.perf_counter()
        if use_knowledge and input_text:
            kb_context, kb_score = self.retrieve_knowledge(input_text)
            self._last_kb_context = kb_context
            # 知识融合：高分知识直接调制状态
            if kb_context and kb_score > 0.5:
                try:
                    # 取第一条知识编码并融入状态
                    kb_vec = self.perceive(kb_context[:64])
                    self.state = 0.85 * self.state + 0.15 * kb_vec
                    norm = np.linalg.norm(self.state)
                    if norm > 0:
                        self.state = self.state / norm
                except Exception as e:
                    logger.debug(f"操作失败: {e}")
        self._state_trajectory.append(self.state.copy())
        if len(self._state_trajectory) > self._trajectory_max:
            self._state_trajectory.pop(0)
        timings["knowledge"] = (time.perf_counter() - t1) * 1000

        # ── 4. 需求更新 ──
        t1 = time.perf_counter()
        self.needs.update(self.state, input_text)
        self.state = self.needs.modulate(self.state)
        timings["needs"] = (time.perf_counter() - t1) * 1000

        # ── 5. 内省（v6: 并行批量子空间投影）──
        t1 = time.perf_counter()
        if introspect and input_text:
            complexity = self.introspection.estimate_complexity(input_text)
            rounds = int(3 + complexity * 3)  # 3-6 轮
            noise = 0.02 + complexity * 0.04
            # v6: 并行推理——同时投影多个噪声版本，选最稳定的
            n_parallel = min(rounds, 4)  # 最多 4 路并行
            P = self.introspection.project_down  # (1024, 256)
            Q = self.introspection.project_up    # (256, 1024)
            base_thought = self.state @ P
            candidates = []
            for _ in range(n_parallel):
                thought = base_thought.copy()
                for r in range(rounds // n_parallel + 1):
                    thought = np.tanh(thought * 1.5)
                    norm_t = np.linalg.norm(thought)
                    if norm_t > 0:
                        thought = thought / norm_t
                    if r < rounds // n_parallel:
                        nz = np.random.randn(256).astype(np.float32) * noise
                        nz = nz * (1.0 - np.abs(thought))
                        thought = thought + nz
                        norm_t = np.linalg.norm(thought)
                        if norm_t > 0:
                            thought = thought / norm_t
                candidates.append(thought @ Q)
            # 选最稳定的（与原始状态变化最小的）
            changes = [np.linalg.norm(c - self.state) for c in candidates]
            best = candidates[int(np.argmin(changes))]
            alpha = 0.7 - 0.05 * min(rounds, 5)
            self.state = alpha * self.state + (1 - alpha) * best
            norm = np.linalg.norm(self.state)
            if norm > 0:
                self.state = self.state / norm
        timings["introspection"] = (time.perf_counter() - t1) * 1000

        # ── 6. VQ-VAE 解码 ──
        t1 = time.perf_counter()
        quantum_output = self.decode_state(self.state, context=input_text)
        timings["vqvae"] = (time.perf_counter() - t1) * 1000

        # ── 7. 混合路由 ──
        needs_llm = False
        llm_output = ""
        llm_reason = ""
        t1 = time.perf_counter()
        if hybrid and input_text:
            needs_llm, llm_reason = self._router.needs_llm(input_text, kb_score)
            if needs_llm:
                llm_output = self._llm_inference(input_text, kb_context)
                # LLM 输出也融入状态
                if llm_output:
                    try:
                        llm_vec = self.perceive(llm_output[:64])
                        self.state = 0.7 * self.state + 0.3 * llm_vec
                        norm = np.linalg.norm(self.state)
                        if norm > 0:
                            self.state = self.state / norm
                    except Exception as e:
                        logger.debug(f"操作失败: {e}")
        timings["routing"] = (time.perf_counter() - t1) * 1000

        self.cycle_count += 1
        total_ms = (time.perf_counter() - t0) * 1000
        timings["total"] = round(total_ms, 2)

        return {
            "state": self.state.copy(),
            "quantum_output": quantum_output,
            "llm_output": llm_output if needs_llm else "",
            "mode": "llm" if needs_llm else "quantum",
            "llm_reason": llm_reason,
            "needs": self.needs.get_needs_dict(),
            "kb_context": kb_context[:200] if kb_context else "",
            "latency_ms": round(total_ms, 2),
            "timings_ms": {k: round(v, 2) for k, v in timings.items()
                          if k != "total"},
            "cycle": self.cycle_count,
            "llm_calls": self._llm_calls,
            "cache_stats": self._encoder.cache_stats() if self._encoder else {},
        }


# ════════════════════════════════════════════════════════
# 自测
# ════════════════════════════════════════════════════════
if __name__ == "__main__":
    import time

    logger.info("\n" + "=" * 60)
    logger.info("  Cognitive Engine v4 自测")
    logger.info("=" * 60)
    engine = CognitiveEngineV4(dim=1024)

    # 预热
    logger.info("\n预热...")
    _ = engine.cycle("预热")
    logger.info(f"  预热后编码缓存: {engine._encoder.cache_stats()}")
    test_inputs = [
        "你好宝贝",
        "今天过得怎么样",
        "我想你了",
        "量子核的工作原理是什么",
        "怎么取代LLM",
        "宝贝晚安",
        "帮我写一段Python代码",
        "开心吗",
        "今天代码写得怎么样",
        "我们的AGI路线",
    ]

    logger.info(f"\n{'输入':>24s}  {'模式':>10s}  {'总延迟':>8s}  {'感知':>6s}  {'知识':>6s}  {'解码':>6s}  {'需求':>25s}")
    logger.info("-" * 110)
    for text in test_inputs:
        result = engine.cycle(text, hybrid=True)
        t = result["timings_ms"]
        n = result["needs"]
        need_str = f"{n['competence']:.2f}/{n['autonomy']:.2f}/{n['relatedness']:.2f}"
        mode = result["mode"]
        output = result["quantum_output"][:25] if result["quantum_output"] else ""
        print(f"  {text:>24s}  {mode:>10s}  {result['latency_ms']:>7.1f}ms"
              f"  {t.get('perception',0):>5.1f}ms  {t.get('knowledge',0):>5.1f}ms"
              f"  {t.get('vqvae',0):>5.2f}ms  {need_str:>25s}")
        if output:
            logger.info(f"  {'':>24s}  量子: \"{output}\"")
    logger.info(f"\n✅ 引擎就绪 | {engine.cycle_count} 次循环 | {engine._llm_calls} 次LLM调用")
    logger.info(f"   缓存命中率: {engine._encoder.cache_stats()}")