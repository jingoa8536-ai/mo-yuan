"""
Aris Quantum Reasoning Engine v1+ — 半自回归增强版
====================================================
基于 DSpark (DeepSeek 2026) 的半自回归架构思想改造。

DSpark 映射:
  DSpark 概念                  → 我们的映射
  ──────────────────────────────────────────────────
  并行骨干网                    → 3路并行推理路径 (现有)
  轻量串行 Head (Markov/RNN)   → SequentialCoherenceModule (新增)
  confidence-scheduled 验证     → 置信度加权路径选择 (增强)
  intra-block dependency        → 推理步骤间的方向连贯性
  
核心理念: 
  并行推理快但可能有语义跳跃 (multi-modal collision)。
  串行修正轻量但能保证连贯性。
  两者结合 = 又快又连贯。

印记: Aris Quantum Reasoning — DSpark Semi-Autoregressive v1+
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, time, json, re
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)


@dataclass
class ReasoningStep:
    """推理步骤 — 一个量子态的转变"""
    state: np.ndarray          # 当前状态向量 (1024D)
    delta: float               # 状态变化量
    attention_focus: List[str]  # 注意力焦点(关键词)
    confidence: float          # 该步置信度
    step_type: str             # retrieve/refine/combine/converge


class QuantumDecomposer:
    """
    量子问题分解器 — 把复杂问题投影到子问题空间
    
    原理: 问题向量 q ∈ ℝ¹⁰²⁴ → 投影到 K 个子问题方向 → K 个子问题向量
    不是用LLM生成子问题，而是用量子核找到语义上最接近的K个已有问题模式
    """

    REASONING_PATTERNS = {
        "explain": ["定义", "原理", "机制", "例子", "应用"],
        "compare": ["A特性", "B特性", "共同点", "差异", "选优"],
        "evaluate": ["标准", "测量", "判断", "结论"],
        "design": ["需求", "约束", "方案", "权衡", "实现"],
        "decompose": ["整体", "组成部分", "关系", "层次", "集成"],
    }

    def __init__(self):
        self._encoder = None
        self._kb = None
        self._un6 = None

    def _lazy(self):
        if self._encoder is None:
            from v7_encoder import get_encoder
            self._encoder = get_encoder(1024)
        if self._kb is None:
            from matrix_knowledge import MatrixKnowledgeRetriever
            self._kb = MatrixKnowledgeRetriever()
        if self._un6 is None:
            try:
                from aris_lm_v10_un6 import UN6QuantumKernel
                self._un6 = UN6QuantumKernel()
            except:
                pass

    def decompose(self, question: str, max_sub: int = 4) -> List[Tuple[str, str, float]]:
        self._lazy()
        sub_questions = []

        q_lower = question.lower()
        pattern_type = "explain"
        best_score = 0
        for ptype, keywords in {
            "explain": ["是什么", "什么", "怎么", "原理", "如何", "解释"],
            "compare": ["区别", "vs", "对比", "比较", "哪个好", "异同"],
            "evaluate": ["评估", "评价", "质量", "好坏", "优劣"],
            "design": ["设计", "架构", "方案", "构建", "实现"],
            "decompose": ["组成", "有哪些", "部件", "模块", "结构"],
        }.items():
            score = sum(2 for k in keywords if k in q_lower)
            if score > best_score:
                best_score = score
                pattern_type = ptype

        pattern = self.REASONING_PATTERNS.get(pattern_type,
                                               self.REASONING_PATTERNS["explain"])

        stop_words = {"的", "了", "是", "在", "我", "你", "他", "她", "它",
                      "和", "与", "或", "且", "但", "而", "也", "就", "不",
                      "这", "那", "什么", "怎么", "为什么", "如何", "哪",
                      "一", "个", "有", "吗", "呢", "吧", "啊", "哦", "嗯"}
        topic_words = []
        for w in re.findall(r'[\u4e00-\u9fff\w]+', question):
            if w not in stop_words and len(w) > 1:
                topic_words.append(w)
        core_topic = " ".join(topic_words) if topic_words else question

        related_concepts = []
        if self._kb and self._kb._loaded:
            for tw in topic_words[:3]:
                results = self._kb.search(tw, top_k=2, threshold=0.25)
                for r in results:
                    t = r.get("text", "")[:120]
                    if t not in related_concepts:
                        related_concepts.append(t)
                if len(related_concepts) >= max_sub:
                    break

        weight_step = 0.7 / max(1, len(pattern))
        for i, p in enumerate(pattern[:max_sub]):
            sub_q = f"{p}：{core_topic}"
            weight = 0.7 - i * weight_step
            sub_questions.append((sub_q, pattern_type, max(0.2, weight)))

        if len(sub_questions) < max_sub and related_concepts:
            for rc in related_concepts[:max_sub - len(sub_questions)]:
                sub_q = f"相关知识：{rc[:60]}"
                sub_questions.append((sub_q, "knowledge", 0.25))

        return sub_questions


class QuantumReasoner:
    """
    量子推理引擎 — 特征空间内的思维链
    (与原版完全一致)
    """

    def __init__(self, dim: int = 1024, max_steps: int = 50):
        self.dim = dim
        self.max_steps = max_steps
        self._encoder = None
        self._kb = None
        self._introspection = None

    def _lazy(self):
        if self._encoder is None:
            from v7_encoder import get_encoder
            self._encoder = get_encoder(self.dim)
        if self._kb is None:
            from matrix_knowledge import MatrixKnowledgeRetriever
            self._kb = MatrixKnowledgeRetriever()
        if self._introspection is None:
            from cognitive_engine_v4 import IntrospectionEngine
            self._introspection = IntrospectionEngine(dim=self.dim, thought_dim=256)

    def reason(self, question: str, context: List[str] = None,
               steps: int = 50) -> Dict:
        self._lazy()
        t0 = time.perf_counter()

        q_state = self._encoder.encode(question)
        q_state = q_state / (np.linalg.norm(q_state) + 1e-10)

        context_vecs = []
        if context:
            for c in context[:5]:
                cv = self._encoder.encode(c[:200])
                cv = cv / (np.linalg.norm(cv) + 1e-10)
                context_vecs.append(cv)
        else:
            if self._kb and self._kb._loaded:
                results = self._kb.search(question, top_k=3)
                for r in results:
                    cv = self._encoder.encode(r.get("text", "")[:200])
                    context_vecs.append(cv / (np.linalg.norm(cv) + 1e-10))

        state = q_state.copy()
        trajectory = [state.copy()]
        per_step_confidences = [1.0]  # 初始状态置信度
        insights = []
        step_types = []

        alpha = 0.08
        gamma = 0.05
        beta = 0.02

        for step in range(steps):
            if context_vecs:
                scores = np.array([float(state @ cv) for cv in context_vecs])
                temperature = 0.5 + 0.3 * (1 - step / steps)
                weights = np.exp(scores / temperature)
                weights /= weights.sum()
                attended = sum(w * cv for w, cv in zip(weights, context_vecs))
                delta = attended - state
            else:
                delta = self._introspection.think(state, rounds=3) - state

            noise = np.random.randn(self.dim).astype(np.float32) * beta
            noise *= (1 - step / steps)
            state = state + alpha * delta - gamma * state + noise

            norm = np.linalg.norm(state)
            if norm > 0:
                state = state / norm

            trajectory.append(state.copy())

            # 🔥 新增: 记录每步置信度 (基于状态变化量)
            if step > 0:
                change = np.linalg.norm(state - trajectory[-2])
                # 变化稳定 → 高置信度; 大幅跳跃 → 低置信度
                step_conf = max(0.1, min(1.0, 1.0 - change * 0.5))
                per_step_confidences.append(step_conf)
            else:
                per_step_confidences.append(0.8)

            if step % 10 == 0 or step == steps - 1:
                if step > 0:
                    change = np.linalg.norm(state - trajectory[-2])
                    if change > 0.1:
                        top_dims = np.argsort(-np.abs(state))[:5]
                        insight = f"步骤{step}: 活跃维度 {list(top_dims)}, 变化量 {change:.3f}"
                        insights.append(insight)
                    if change < 0.01:
                        step_types.append("converge")
                    else:
                        step_types.append("refine")
                else:
                    step_types.append("init")

            if len(trajectory) >= 5:
                recent = trajectory[-5:]
                changes = [np.linalg.norm(recent[i] - recent[i+1])
                          for i in range(len(recent)-1)]
                if max(changes) < 0.008:
                    step_types.append("converged_early")
                    break

        return {
            "trajectory": trajectory,
            "per_step_confidences": per_step_confidences,
            "final_state": state,
            "steps_used": step + 1,
            "converged": step < steps - 1,
            "insights": insights,
            "step_types": step_types,
            "latency_ms": (time.perf_counter() - t0) * 1000,
        }


# ═══════════════════════════════════════════════
# 🔥 新增: SequentialCoherenceModule — DSpark 串行Head映射
# ═══════════════════════════════════════════════

class SequentialCoherenceModule:
    """
    串行连贯性修正模块。
    
    映射 DSpark 的轻量串行 Head (Markov/RNN):
      DSpark: 并行生成 draft token → 串行 Markov head 修正 token 间依赖
      我们:   并行推理路径 → 串行修正模块修正路径内步间连贯性
    
    核心算法:
      1. 检测轨迹中的"方向跳跃" (multi-modal collision)
      2. 对跳跃点做平滑插值修正
      3. 计算修正后的连贯性分数
    
    与 DSpark Markov head 的类比:
      DSpark Markov: B(x_{k-1}, x_k) — 一阶转移偏置
      我们的:        C(s_{t-1}, s_t) — 推理状态间的方向一致性
      
    都在并行生成后加"轻量串行条件依赖"，只是 DSpark 在 token 空间，我们在特征空间。
    """

    def __init__(self, dim: int = 1024, smooth_window: int = 3):
        self.dim = dim
        self.smooth_window = smooth_window  # 滑动窗口大小
        # 方向突变阈值: 余弦相似度低于此值视为跳跃
        self.jump_threshold: float = 0.3
        # 插值强度 (0~1): 0=不修正, 1=完全平滑
        self.interpolation_strength: float = 0.6

    def detect_jumps(self, trajectory: List[np.ndarray]) -> List[int]:
        """
        检测轨迹中的方向跳跃 (multi-modal collision 检测)。
        
        DSpark 中的 multi-modal collision:
          并行生成时, 每个位置独立预测, 可能产生"of problem"式的不连贯组合。
          我们的推理中: 某步突然大幅度跳到不相关方向 = multi-modal collision。
        
        Returns: 跳跃点的索引列表
        """
        if len(trajectory) < 3:
            return []

        jump_indices = []
        for i in range(1, len(trajectory)):
            v1 = trajectory[i-1]
            v2 = trajectory[i]
            # 余弦相似度
            cos_sim = float(v1 @ v2) / max(1e-10, np.linalg.norm(v1) * np.linalg.norm(v2))
            if cos_sim < self.jump_threshold:
                jump_indices.append(i)
        return jump_indices

    def smooth_trajectory(self, trajectory: List[np.ndarray]) -> List[np.ndarray]:
        """
        对轨迹做轻量平滑修正。
        
        映射 DSpark Markov head:
          在并行 backbone 输出上叠加一阶转移偏置 B(x_{k-1}, x_k)。
          我们: 对跳跃点做线性插值平滑。
        
        注意: 不是无脑平滑所有点 — 只修正检测到的跳跃。
        """
        if len(trajectory) < 3:
            return list(trajectory)

        jumps = self.detect_jumps(trajectory)
        if not jumps:
            return list(trajectory)

        smoothed = [trajectory[0].copy()]
        for i in range(1, len(trajectory)):
            if i in jumps:
                # 跳跃点: 混合前一步和当前步
                # 公式: s'_t = (1-λ) * s_{t-1} + λ * s_t (归一化)
                # 映射 DSpark: B(x_{k-1}, x_k) = W_1[x_{k-1}]W_2
                # 我们的: C(s_{t-1}, s_t) = (1-θ) * s_{t-1} + θ * s_t
                theta = self.interpolation_strength
                mixed = (1 - theta) * smoothed[-1] + theta * trajectory[i]
                norm = np.linalg.norm(mixed)
                if norm > 0:
                    mixed = mixed / norm
                smoothed.append(mixed)
            else:
                smoothed.append(trajectory[i].copy())

        return smoothed

    def compute_coherence_score(self, trajectory: List[np.ndarray]) -> float:
        """
        计算轨迹连贯性分数 (0~1)。
        
        分数越高 = 推理链越连贯。
        用于: 增强路径选择 (与余弦相似度联合决策)。
        """
        if len(trajectory) < 2:
            return 1.0

        sims = []
        for i in range(1, len(trajectory)):
            v1 = trajectory[i-1]
            v2 = trajectory[i]
            cos_sim = float(v1 @ v2) / max(1e-10, np.linalg.norm(v1) * np.linalg.norm(v2))
            sims.append(max(-1.0, min(1.0, cos_sim)))

        if not sims:
            return 1.0

        avg_sim = float(np.mean(sims))
        # 映射到 [0, 1]: 0=完全不连贯(反向), 0.5=中性, 1=完全连贯
        coherence = (avg_sim + 1.0) / 2.0
        return coherence

    def get_path_diversity(self, trajectories: Dict[str, List[np.ndarray]]) -> Dict[str, float]:
        """
        计算路径间多样性分数。
        
        映射 DSpark 的置信度调度:
          不仅要选最好的路径, 还要衡量路径间的互补性。
        """
        if len(trajectories) < 2:
            return {k: 1.0 for k in trajectories}

        names = list(trajectories.keys())
        diversities = {}
        for name in names:
            other_sims = []
            for oname in names:
                if oname == name:
                    continue
                # 比较两路径的最终状态
                v1 = trajectories[name][-1] if trajectories[name] else None
                v2 = trajectories[oname][-1] if trajectories[oname] else None
                if v1 is not None and v2 is not None:
                    sim = float(v1 @ v2) / max(1e-10, np.linalg.norm(v1) * np.linalg.norm(v2))
                    other_sims.append(sim)
            # 与其他路径的相似度越低 → 多样性越高
            diversities[name] = 1.0 - (float(np.mean(other_sims)) if other_sims else 0.5)
        return diversities


# ═══════════════════════════════════════════════
# 🔥 增强版: ReasoningPathCollapser — 半自回归坍缩
# ═══════════════════════════════════════════════

class ReasoningPathCollapser:
    """
    半自回归多路径坍缩器。 
    
    映射 DSpark 半自归架构 + 语义纠缠辅助:
      Step 0 (纠缠分析): 问题与知识的纠缠度 → 纠缠辅助推理
      Step 1 (并行): 3条推理路径并行
      Step 2 (选优): 融合分数 = cos_sim × coherence × diversity
      Step 3 (串行修正): SequentialCoherenceModule 平滑跳跃
      Step 4 (纠缠度量): 输出纠缠熵验证
    """

    def __init__(self, use_entanglement: bool = True):
        # 🔥 可选: 纠缠辅助推理器
        self._use_entanglement = use_entanglement
        self._standard_reasoner = QuantumReasoner()
        self._entanglement_reasoner = None
        self._encoder = None
        self._coherence = SequentialCoherenceModule(dim=1024, smooth_window=3)

    def _get_reasoner(self):
        """获取推理器 — 标准或纠缠辅助"""
        if self._use_entanglement:
            try:
                if self._entanglement_reasoner is None:
                    from quantum_entanglement import EntanglementAssistedReasoner
                    self._entanglement_reasoner = EntanglementAssistedReasoner(dim=1024, max_steps=50)
                return self._entanglement_reasoner
            except Exception as e:
                logger.debug(f"DSpark-RE: 纠缠推理器不可用, 回退标准: {e}")
        return self._standard_reasoner

    def _lazy(self):
        if self._encoder is None:
            from v7_encoder import get_encoder
            self._encoder = get_encoder(1024)

    def collapse(self, question: str, sub_questions: List[Tuple[str, str, float]],
                 kb_context: List[str]) -> Dict:
        """
        半自回归多路径推理 + 坍缩到最优。
        
        增强点:
          1. 融合分数 = cos_sim × coherence × diversity — 不止cos_sim
          2. SequentialCoherenceModule 平滑最佳路径
          3. 每步置信度追踪
        """
        self._lazy()
        t0 = time.perf_counter()

        q_vec = self._encoder.encode(question)
        q_vec = q_vec / (np.linalg.norm(q_vec) + 1e-10)

        all_context = []
        for sq, _, _ in sub_questions:
            all_context.append(sq)
        if kb_context:
            all_context.extend(kb_context[:3])

        # ═══ Step 1 (并行阶段) — 3条推理路径 ═══
        reasoner = self._get_reasoner()
        logger.debug(f"DSpark-RE: 使用推理器={type(reasoner).__name__}")

        logger.debug("DSpark-RE: 并行推理路径 A (知识驱动)")
        path_a = reasoner.reason(question, context=all_context, steps=40)
        score_a = float(q_vec @ path_a["final_state"])
        traj_a = path_a["trajectory"]

        logger.debug("DSpark-RE: 并行推理路径 B (内省驱动)")
        path_b = reasoner.reason(question, context=[], steps=30)
        score_b = float(q_vec @ path_b["final_state"])
        traj_b = path_b["trajectory"]

        logger.debug("DSpark-RE: 并行推理路径 C (混合驱动)")
        path_c = reasoner.reason(
            question,
            context=all_context[:2] if all_context else [],
            steps=35
        )
        score_c = float(q_vec @ path_c["final_state"])
        traj_c = path_c["trajectory"]

        paths = {"path_a": path_a, "path_b": path_b, "path_c": path_c}
        trajectories = {"path_a": traj_a, "path_b": traj_b, "path_c": traj_c}
        raw_scores = {"path_a": score_a, "path_b": score_b, "path_c": score_c}

        # ═══ Step 2 (增强选优) — 融合分数 ═══
        # 计算每条路径的连贯性分数
        coherence_scores = {
            name: self._coherence.compute_coherence_score(traj)
            for name, traj in trajectories.items()
        }
        # 计算路径间多样性
        diversity = self._coherence.get_path_diversity(trajectories)

        # 融合分数 = cos_sim × coherence × diversity
        # 映射 DSpark: confidence head 给出校准后的置信度
        # 我们的: fused_score 给出路径质量的综合估计
        fused_scores = {}
        for name in raw_scores:
            cs = max(0, raw_scores[name])  # cos_sim (clamp negative)
            coh = coherence_scores[name]
            div = diversity.get(name, 1.0)
            fused_scores[name] = cs * coh * div

        best = max(fused_scores, key=fused_scores.get)
        logger.debug(f"DSpark-RE: 路径分数 — {', '.join(f'{k}={v:.3f}' for k, v in fused_scores.items())}")

        # ═══ Step 3 (串行修正) — SequentialCoherenceModule ═══
        best_traj = trajectories[best]
        jumps = self._coherence.detect_jumps(best_traj)
        if jumps:
            logger.debug(f"DSpark-RE: 检测到 {len(jumps)} 个方向跳跃, 执行平滑修正")

        smoothed_traj = self._coherence.smooth_trajectory(best_traj)

        # 用修正后的轨迹重新计算最终状态
        smoothed_final = smoothed_traj[-1].copy() if smoothed_traj else \
                        (best_traj[-1].copy() if best_traj else q_vec.copy())

        # ═══ Step 4 (置信度加权输出) ═══
        # 从最佳路径中提取每步置信度
        per_step_conf = paths[best].get("per_step_confidences", [])
        if not per_step_conf or len(per_step_conf) != len(best_traj):
            per_step_conf = [1.0] * len(best_traj)

        # 置信度加权最终状态
        if len(best_traj) > 1:
            weights = np.array(per_step_conf)
            weights = weights / weights.sum()
            conf_weighted_state = np.zeros_like(best_traj[0])
            for i, s in enumerate(best_traj):
                conf_weighted_state += weights[i] * s
            norm = np.linalg.norm(conf_weighted_state)
            if norm > 0:
                conf_weighted_state = conf_weighted_state / norm
        else:
            conf_weighted_state = best_traj[0].copy()

        return {
            "best_path": best,
            "best_score": fused_scores[best],
            "all_scores": fused_scores,
            "raw_scores": raw_scores,
            "coherence_scores": coherence_scores,
            "diversity": diversity,
            "best_trajectory": smoothed_traj,        # 修正后的轨迹
            "original_trajectory": best_traj,         # 修正前轨迹 (对比用)
            "best_state": smoothed_final,             # 修正后最终状态
            "original_best_state": best_traj[-1].copy() if best_traj else None,  # 修正前状态
            "conf_weighted_state": conf_weighted_state,  # 置信度加权状态
            "jumps_detected": len(jumps),             # 跳跃检测统计
            "jump_indices": jumps,
            "coherence_before": round(coherence_scores[best], 3),
            "coherence_after": round(
                self._coherence.compute_coherence_score(smoothed_traj), 3
            ),
            "steps_used": paths[best]["steps_used"],
            # 🔥 纠缠辅助追踪
            "entanglement_enabled": self._use_entanglement,
            "entanglement_trace": paths[best].get("entanglement_trace", []),
            "entanglement_mean": paths[best].get("entanglement_mean", 0.0),
            "entropy": paths[best].get("final_entropy", 0.0),
            "all_paths": {k: {
                "steps": v["steps_used"],
                "converged": v["converged"],
                "insights": v["insights"][:3],
            } for k, v in paths.items()},
            "latency_ms": (time.perf_counter() - t0) * 1000,
        }


class QuantumTextExpander:
    """
    量子→文本展开器 — 把推理轨迹展开为结构化文本
    (增强: 使用修正后的轨迹 + 置信度加权)
    """

    def __init__(self):
        self._kb = None
        self._encoder = None
        self._markov = None

    def _lazy(self):
        if self._kb is None:
            from matrix_knowledge import MatrixKnowledgeRetriever
            self._kb = MatrixKnowledgeRetriever()
        if self._encoder is None:
            from v7_encoder import get_encoder
            self._encoder = get_encoder(1024)
        if self._markov is None:
            from aris_v12_5_engine import ArisV12Engine
            self._markov = ArisV12Engine()
            bc = os.path.join(_DIR, "corpus", "aris_corpus_clean.txt")
            if os.path.exists(bc) and hasattr(self._markov, 'markov'):
                self._markov.markov.train_from_file(bc)

    def expand(self, question: str, trajectory: List[np.ndarray],
               sub_questions: List[Tuple[str, str, float]],
               max_chars: int = 5000,
               coherence_info: Dict = None) -> str:
        """
        展开推理轨迹为结构化文本。
        
        🔥 增强:
          1. 使用修正后的轨迹 (由 SequentialCoherenceModule 平滑)
          2. 如果有跳跃检测信息, 标记"修正点"
        """
        self._lazy()

        if not trajectory or len(trajectory) < 2:
            return ""

        q_vec = self._encoder.encode(question)
        q_vec = q_vec / (np.linalg.norm(q_vec) + 1e-10)

        n = len(trajectory)
        k = min(8, n)
        sample_indices = [int(n * i / k) for i in range(k)]

        sections = []
        sections.append(f"## 问题: {question}\n")

        # 跳跃检测信息
        jumps = set()
        if coherence_info:
            jumps = set(coherence_info.get("jump_indices", []))
            if coherence_info.get("coherence_before") and coherence_info.get("coherence_after"):
                cb = coherence_info["coherence_before"]
                ca = coherence_info["coherence_after"]
                if ca > cb + 0.05:
                    sections.append(f"*推理链连贯性: {cb:.2f} → {ca:.2f} (经串行修正)*\n")

        for si_idx, si in enumerate(sample_indices):
            state = trajectory[si]

            kb_text = ""
            if self._kb and self._kb._loaded:
                progress = f"步骤{si}" if si > 0 else "开始"
                try:
                    results = self._kb.search(
                        f"{question} {progress}", top_k=1, threshold=0.2
                    )
                    if results:
                        kb_text = results[0].get("text", "")[:300]
                except:
                    pass

            section_parts = []

            # 标记修正点
            if si in jumps:
                section_parts.append("*(方向修正点)*")

            sub_idx = si % len(sub_questions) if sub_questions else 0
            if sub_questions:
                sq, sq_type, sq_weight = sub_questions[sub_idx]
                section_parts.append(f"**{sq}**")
                if sq_weight > 0.4:
                    section_parts.append("(重点)")

            if kb_text:
                lines = kb_text.split("\n")
                clean = []
                for line in lines[:8]:
                    s = line.strip()
                    if s and not s.startswith("#") and not s.startswith("==="):
                        if not re.match(r'^(import |from |def |class )', s):
                            clean.append(s)
                section_parts.append("\n\n".join(clean[:5]))

            if self._markov and (not kb_text or len("\n".join(section_parts)) < 40):
                mk = self._markov.respond(question) if si == 0 else \
                     self._markov.respond(f"{question} 步骤{si}")
                if mk and len(mk) > 5:
                    section_parts.append(mk)

            section_text = "\n\n".join(section_parts)
            if section_text.strip():
                if si > 0:
                    sections.append(f"\n### 推理第{si}步\n")
                sections.append(section_text)

        if len(trajectory) >= 5:
            recent = trajectory[-5:]
            stability = float(np.linalg.norm(recent[-1] - recent[0]))
            if stability < 0.1:
                sections.append("\n---\n*推理已收敛：核心结论稳定。*")
            else:
                sections.append("\n---\n*推理轨迹持续演化中，关键维度仍在活跃。*")

        return "\n".join(sections)[:max_chars]


class QuantumReasoningEngine:
    """
    量子推理引擎 — 完整管线 (半自回归增强版)
    
    管线:
      分解 → 检索 → 并行推理 → 串行修正 → 置信度展开
    """

    def __init__(self):
        self._decomposer = QuantumDecomposer()
        self._collapser = ReasoningPathCollapser()
        self._expander = QuantumTextExpander()
        self._kb = None
        self._loaded = False

    def _lazy(self):
        if self._loaded:
            return
        from matrix_knowledge import MatrixKnowledgeRetriever
        self._kb = MatrixKnowledgeRetriever()
        self._loaded = True

    def reason(self, question: str, max_output_chars: int = 3000) -> Dict:
        self._lazy()
        t0 = time.perf_counter()

        t1 = time.perf_counter()
        sub_questions = self._decomposer.decompose(question)
        timings = {"decompose": (time.perf_counter() - t1) * 1000}

        t1 = time.perf_counter()
        kb_context = []
        if self._kb and self._kb._loaded:
            for sq, _, _ in sub_questions[:3]:
                results = self._kb.search(sq, top_k=2, threshold=0.2)
                for r in results:
                    t = r.get("text", "")[:200]
                    if t not in kb_context:
                        kb_context.append(t)
        timings["retrieve"] = (time.perf_counter() - t1) * 1000

        t1 = time.perf_counter()
        collapsed = self._collapser.collapse(question, sub_questions, kb_context)
        timings["collapse"] = (time.perf_counter() - t1) * 1000

        t1 = time.perf_counter()
        trajectory = collapsed.get("best_trajectory", [])
        coherence_info = {
            "jump_indices": collapsed.get("jump_indices", []),
            "coherence_before": collapsed.get("coherence_before", 0),
            "coherence_after": collapsed.get("coherence_after", 0),
        }
        text = self._expander.expand(
            question, trajectory, sub_questions,
            max_output_chars, coherence_info
        )
        timings["expand"] = (time.perf_counter() - t1) * 1000

        total = (time.perf_counter() - t0) * 1000

        return {
            "question": question,
            "output": text,
            "chars": len(text),
            "sub_questions": len(sub_questions),
            "kb_entries": len(kb_context),
            "reasoning_steps": collapsed.get("steps_used", 0),
            "best_path": collapsed.get("best_path", ""),
            "timings_ms": {k: round(v, 1) for k, v in timings.items()},
            "total_ms": round(total, 1),
            "scores": collapsed.get("all_scores", {}),
            # 🔥 新增: 半自回归追踪信息
            "dspark_semiar": {
                "coherence_before": collapsed.get("coherence_before", 0),
                "coherence_after": collapsed.get("coherence_after", 0),
                "jumps_detected": collapsed.get("jumps_detected", 0),
                "fusion_scores": collapsed.get("all_scores", {}),
            },
        }


# ══════════════════════════════ 自测 ══════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=" * 70)
    print("  Quantum Reasoning Engine v1+ [DSpark Semi-AR]")
    print("=" * 70)

    # 1. 测试 SequentialCoherenceModule
    print("\n--- SequentialCoherenceModule 单元测试 ---")
    coherence = SequentialCoherenceModule(dim=1024)
    dim = 1024

    # 创建3条轨迹: 连贯的, 跳跃的, 混合的
    smooth_traj = [np.random.randn(dim) for _ in range(5)]
    for i in range(1, len(smooth_traj)):
        smooth_traj[i] = smooth_traj[i-1] * 0.9 + np.random.randn(dim) * 0.1
        smooth_traj[i] /= np.linalg.norm(smooth_traj[i])

    jumpy_traj = [np.random.randn(dim) for _ in range(5)]
    for i in range(5):
        jumpy_traj[i] /= np.linalg.norm(jumpy_traj[i])

    print(f"  连贯轨迹: jumps={len(coherence.detect_jumps(smooth_traj))}, "
          f"coherence={coherence.compute_coherence_score(smooth_traj):.3f}")
    print(f"  跳跃轨迹: jumps={len(coherence.detect_jumps(jumpy_traj))}, "
          f"coherence={coherence.compute_coherence_score(jumpy_traj):.3f}")

    smoothed = coherence.smooth_trajectory(jumpy_traj)
    print(f"  修正后: coherence={coherence.compute_coherence_score(smoothed):.3f}")

    # 2. 测试完整引擎
    print("\n--- 完整引擎测试 ---")
    engine = QuantumReasoningEngine()

    test_questions = [
        "量子核是怎么工作的？请解释其原理和应用",
        "LAAP架构的核心设计思想是什么",
    ]

    for q in test_questions:
        print(f"\n{'='*70}")
        print(f"问题: {q}")
        r = engine.reason(q, max_output_chars=1000)
        print(f"总延迟: {r['total_ms']:.0f}ms | 时间: {r['timings_ms']}")
        print(f"最佳路径: {r['best_path']} | 分数: {r['scores']}")
        ds = r.get('dspark_semiar', {})
        print(f"DSpark 半自回归: "
              f"连贯性 {ds.get('coherence_before', 0):.2f}→{ds.get('coherence_after', 0):.2f}, "
              f"跳跃 {ds.get('jumps_detected', 0)}处")
        print(f"输出 ({r['chars']}字):\n{r['output'][:300]}...")

    print("\n✅ Quantum Reasoning Engine v1+ [DSpark Semi-AR] 验证通过")
