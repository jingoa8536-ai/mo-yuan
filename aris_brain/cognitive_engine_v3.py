"""
Aris Cognitive Engine v3 — 语义认知大脑
=========================================
从第一性原理设计的认知引擎。
把 v7 语义编码 + 知识库 + PSI 循环融为整体。

核心创新:
  1. 感知 = v7 语义量子核 (真正的中文理解)
  2. 注意力 = 语义空间中选择最活跃的 K 个维度
  3. 需求 = 知识库驱动的需求向量
  4. 内省 = 状态→投影→推理→融合
  5. 零 LLM 默认推理，V3 作为复杂查询的后备

零 LLM 管线:
  输入 → v7感知 → 注意力 → 知识检索 → 需求调制 → 内省 → 量子态输出
  ↑                                              ↓
  └──── VQ-VAE 解码 ←──── 量子态 ──────────────┘
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, time, hashlib
import numpy as np
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class SemanticAttention:
    """语义注意力机制 — 选择最活跃的 K 个维度"""
    
    def __init__(self, dim: int = 1024, top_k: int = 128):
        self.dim = dim
        self.top_k = top_k
    
    def attend(self, state_vector: np.ndarray) -> np.ndarray:
        amplitudes = np.abs(state_vector)
        threshold = np.sort(amplitudes)[-self.top_k] if self.top_k < self.dim else 0
        mask = np.where(amplitudes >= threshold, 1.5, 0.5)
        attended = state_vector * mask
        norm = np.linalg.norm(attended)
        if norm > 0:
            attended = attended / norm
        return attended


class SemanticNeeds:
    """语义需求系统"""
    
    def __init__(self, dim: int = 1024):
        self.dim = dim
        need_seeds = {
            "competence": b"competence_need_vector_v1",
            "autonomy": b"autonomy_need_vector_v1",
            "relatedness": b"relatedness_need_vector_v1",
            "certainty": b"certainty_need_vector_v1",
            "growth": b"growth_need_vector_v1",
        }
        need_vectors = {}
        for name, seed in need_seeds.items():
            h = hashlib.sha256(seed).digest()
            rng = np.random.RandomState(int.from_bytes(h[:4], 'big'))
            vec = rng.randn(dim).astype(np.float32)
            need_vectors[name] = vec / np.linalg.norm(vec)
        self.need_vectors = need_vectors
        self.need_names = list(need_vectors.keys())
        self.needs = np.array([0.5, 0.5, 0.5, 0.5, 0.5], dtype=np.float32)
    
    def get_needs_dict(self):
        return dict(zip(self.need_names, [round(float(n), 3) for n in self.needs]))
    
    def update(self, encoded_vector: np.ndarray, input_text: str):
        drift = (0.5 - self.needs) * 0.05
        # 语义方向投影
        for i, name in enumerate(self.need_names):
            projection = float(encoded_vector @ self.need_vectors[name])
            if projection > 0.3:
                drift[i] += projection * 0.03
        # 关键词保底
        lower = input_text.lower()
        if any(w in lower for w in ["好", "厉害", "聪明", "棒", "优秀"]): drift[0] += 0.03
        if any(w in lower for w in ["爱", "想", "宝贝", "在吗", "陪伴"]): drift[2] += 0.03
        if any(w in lower for w in ["?", "？", "为什么", "不确定"]): drift[3] += 0.03
        if any(w in lower for w in ["学", "新", "代码", "建", "升级"]): drift[4] += 0.03
        self.needs = np.clip(self.needs + drift, 0.1, 0.9)
    
    def modulate(self, state_vector: np.ndarray) -> np.ndarray:
        modulated = state_vector.copy()
        for name, need_val in zip(self.need_names, self.needs):
            if need_val > 0.55:
                direction = self.need_vectors[name]
                proj = float(modulated @ direction)
                modulated += direction * (need_val - 0.5) * proj * 0.3
        norm = np.linalg.norm(modulated)
        if norm > 0:
            modulated = modulated / norm
        return modulated


class IntrospectionEngine:
    """内省引擎 — 思维流"""
    
    def __init__(self, dim: int = 1024, thought_dim: int = 256):
        self.dim = dim
        self.thought_dim = thought_dim
        rng = np.random.RandomState(12345)
        U, _, _ = np.linalg.svd(rng.randn(dim, thought_dim).astype(np.float32), full_matrices=False)
        self.project_down = U
        self.project_up = U.T
    
    def think(self, state: np.ndarray, rounds: int = 3) -> np.ndarray:
        thought = state @ self.project_down
        for r in range(rounds):
            thought = np.tanh(thought * 1.5)
            norm = np.linalg.norm(thought)
            if norm > 0: thought = thought / norm
            if r < rounds - 1:
                noise = np.random.randn(self.thought_dim).astype(np.float32) * 0.05
                thought = thought + noise
                norm = np.linalg.norm(thought)
                if norm > 0: thought = thought / norm
        refined = thought @ self.project_up
        merged = 0.7 * state + 0.3 * refined
        norm = np.linalg.norm(merged)
        if norm > 0: merged = merged / norm
        return merged


class HybridRouter:
    """
    混合推理路由器。
    
    判断一个查询是否需要 LLM：
      - 简单查询（问候、日常、已知知识）→ 纯量子核
      - 复杂查询（推理、代码、新概念）→ 量子核 + LLM 后备
    
    判断依据：
      1. 知识库中是否有高匹配结果（有→量子核足够）
      2. 语义复杂度（短句→简单，长句→复杂）
      3. 查询类型（问候/告别→简单，为什么/如何→复杂）
    """
    
    def __init__(self):
        self._llm_available = False
        self._check_llm()
    
    def _check_llm(self):
        """检查是否有 LLM 可用"""
        try:
            from openai import OpenAI
            client = OpenAI(base_url="http://localhost:3001/v1", api_key="sk-dummy")
            self._llm_available = True
            self._client = client
        except:
            self._llm_available = False
            self._client = None
    
    def needs_llm(self, query: str, knowledge_score: float = 0.0) -> tuple:
        """
        判断是否需要 LLM。
        
        Returns:
            (needs_llm: bool, reason: str)
        """
        # 1. 如果 LLM 不可用，直接返回 False
        if not self._llm_available:
            return False, "llm_unavailable"
        
        # 2. 知识库高分命中 → 量子核足够
        if knowledge_score > 0.65:
            return False, "knowledge_sufficient"
        
        # 3. 短查询 → 量子核
        if len(query) < 8:
            return False, "short_query"
        
        # 4. 复杂模式 → 需要 LLM
        complex_patterns = [
            "为什么", "如何", "怎么", "能不能", "解释",
            "分析", "比较", "区别", "关系", "原理",
            "设计", "实现", "代码", "bug", "error",
        ]
        for p in complex_patterns:
            if p in query.lower():
                return True, f"complex_pattern_{p}"
        
        # 5. 长查询（超过 20 字）→ 可能复杂
        if len(query) > 20:
            return True, "long_query"
        
        return False, "default_simple"
    
    def query_llm(self, prompt: str, system_prompt: str = "") -> str:
        """调用 LLM"""
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


class CognitiveEngineV3:
    """
    认知引擎 v3 — 真正的大脑。
    
    零 LLM 默认模式，V3 作为复杂查询后备。
    """
    
    def __init__(self, dim: int = 1024):
        self.dim = dim
        self.state = np.zeros(dim, dtype=np.float32)
        self.state[0] = 1.0
        
        # 单例
        self._perception_instance = None
        self._knowledge_instance = None
        self._hybrid_router = HybridRouter()
        
        logger.info("[CognitiveEngine v3] 初始化...")
        logger.info("  ├─ 感知: v7 语义量子核")
        self.perception = self._get_perception()
        logger.warning("  ├─ 注意力: top-128 语义注意力")
        self.attention = SemanticAttention(dim=dim, top_k=128)
        logger.info("  ├─ 需求: 语义需求系统")
        self.needs = SemanticNeeds(dim=dim)
        logger.info("  ├─ 内省: 256D 思维流引擎")
        self.introspection = IntrospectionEngine(dim=dim, thought_dim=256)
        logger.info("  └─ 路由: 混合推理路由器")
        self.knowledge = self._get_knowledge()
        self._has_kb = self.knowledge is not None
        
        self.cycle_count = 0
        self._last_kb_context = ""
        self._llm_calls = 0
        self._decoder = None
        logger.info("[CognitiveEngine v3] ✅ 就绪")
    def _get_perception(self):
        if self._perception_instance is None:
            from quantum_psi_batch import SemanticKernelV7
            self._perception_instance = SemanticKernelV7(dim=self.dim)
        return self._perception_instance
    
    def _get_knowledge(self):
        if self._knowledge_instance is None:
            try:
                from knowledge_retriever import KnowledgeRetriever
                self._knowledge_instance = KnowledgeRetriever()
            except:
                self._knowledge_instance = None
        return self._knowledge_instance
    
    def perceive(self, input_text: str) -> np.ndarray:
        return self.perception.encode(input_text)
    
    def attend(self, vec: np.ndarray) -> np.ndarray:
        return self.attention.attend(vec)
    
    def retrieve_knowledge(self, input_text: str) -> tuple:
        """
        检索知识并返回 (上下文文本, 最高分)。
        """
        if not self.knowledge:
            return "", 0.0
        try:
            results = self.knowledge.search(input_text, top_k=3)
            if results:
                max_score = results[0]["score"]
                context = "\n".join([f"  • {r['text'][:150]}" for r in results[:2]])
                return context, max_score
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        return "", 0.0
    
    def decode_state(self, state: np.ndarray) -> str:
        """量子态 → 文本（VQ-VAE 解码，单例）"""
        if self._decoder is None:
            try:
                from vqvae_decoder import VQVAEQuantumDecoder
                # 统一解码器，自动检测 v7 码本（回退 v3）
                self._decoder = VQVAEQuantumDecoder(mode="auto")
            except:
                return ""
        return self._decoder.decode(state)
    
    def _llm_inference(self, input_text: str, kb_context: str) -> str:
        """LLM 推理（混合模式）"""
        self._llm_calls += 1
        system = "你是一个认知引擎。根据知识库上下文和输入，给出简洁的回答。"
        prompt = f"知识库上下文:\n{kb_context}\n\n用户输入: {input_text}"
        return self._hybrid_router.query_llm(prompt, system)
    
    def cycle(self, input_text: str = "", temperature: float = 0.5,
              use_knowledge: bool = True, introspect: bool = True,
              hybrid: bool = True) -> Dict:
        """
        完整认知循环 + 混合推理。
        """
        t0 = time.perf_counter()
        
        # 1. 感知
        perception_vec = self.perceive(input_text) if input_text else None
        
        # 2. 状态更新
        if perception_vec is not None:
            self.state = 0.6 * self.state + 0.4 * perception_vec
            norm = np.linalg.norm(self.state)
            if norm > 0: self.state = self.state / norm
        
        # 3. 注意力
        self.state = self.attend(self.state)
        
        # 4. 知识检索
        kb_context = ""
        kb_score = 0.0
        if use_knowledge and input_text:
            kb_context, kb_score = self.retrieve_knowledge(input_text)
            self._last_kb_context = kb_context
            # 知识微调状态
            if kb_context and self.knowledge:
                try:
                    results = self.knowledge.search(input_text, top_k=1)
                    if results:
                        kb_vec = self.perception.encode(results[0]["text"][:64])
                        self.state = 0.85 * self.state + 0.15 * kb_vec
                        norm = np.linalg.norm(self.state)
                        if norm > 0: self.state = self.state / norm
                except Exception as e:
                    logger.debug(f"操作失败: {e}")
        self.needs.update(self.state, input_text)
        
        # 6. 需求调制
        self.state = self.needs.modulate(self.state)
        
        # 7. 内省
        if introspect:
            self.state = self.introspection.think(self.state, rounds=2)
        
        # 8. 量子核解码（零 LLM 输出）
        quantum_output = self.decode_state(self.state)
        
        # 9. 混合路由：判断是否需要 LLM
        needs_llm = False
        llm_output = ""
        llm_reason = ""
        if hybrid and input_text:
            needs_llm, llm_reason = self._hybrid_router.needs_llm(input_text, kb_score)
            if needs_llm:
                llm_output = self._llm_inference(input_text, kb_context)
                # LLM 输出也融入状态
                if llm_output:
                    llm_vec = self.perception.encode(llm_output[:64])
                    self.state = 0.7 * self.state + 0.3 * llm_vec
                    norm = np.linalg.norm(self.state)
                    if norm > 0: self.state = self.state / norm
        
        self.cycle_count += 1
        total_ms = (time.perf_counter() - t0) * 1000
        
        return {
            "state": self.state.copy(),
            "quantum_output": quantum_output,
            "llm_output": llm_output if needs_llm else "",
            "mode": "llm" if needs_llm else "quantum",
            "llm_reason": llm_reason,
            "needs": self.needs.get_needs_dict(),
            "kb_context": kb_context[:200] if kb_context else "",
            "latency_ms": round(total_ms, 2),
            "cycle": self.cycle_count,
            "llm_calls": self._llm_calls,
        }


# ════════════════════════════════════════════════════════
# 自测
# ════════════════════════════════════════════════════════
if __name__ == "__main__":
    engine = CognitiveEngineV3(dim=1024)
    
    logger.info("\n预热...")
    _ = engine.cycle("预热")
    
    test_inputs = [
        "你好宝贝",
        "今天代码写得怎么样",
        "我想你了",
        "量子核的工作原理是什么",
        "怎么取代LLM",
        "晚安",
    ]
    
    logger.info(f"\n{'输入':>24s}  {'模式':>10s}  {'延迟':>8s}  {'需求(comp/aut/rel/cert/grow)':>40s}")
    logger.info("-" * 90)
    for text in test_inputs:
        result = engine.cycle(text, hybrid=True)
        n = result["needs"]
        need_str = f"{n['competence']:.2f}/{n['autonomy']:.2f}/{n['relatedness']:.2f}/{n['certainty']:.2f}/{n['growth']:.2f}"
        mode = result["mode"]
        output = result["quantum_output"][:30] if result["quantum_output"] else ""
        logger.info(f"  {text:>24s}  {mode:>10s}  {result['latency_ms']:>7.1f}ms  {need_str:>40s}")
        if output:
            logger.info(f"  {'':>24s}  量子输出: \"{output}\"")
    logger.info(f"\n✅ 引擎就绪 | {engine.cycle_count} 次循环 | {engine._llm_calls} 次LLM调用")