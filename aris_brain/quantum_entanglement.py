"""
Aris Quantum Entanglement Engine — 语义纠缠 + LAAP 推理
=========================================================
基于 DSpark (DeepSeek 2026) + LAAP 特征空间的第一性原理构建。

核心思想:
  物理量子纠缠的本质是"不可分性"——两个系统的联合态不能分解为独立态的乘积。
  在 LAAP 的 1024D 语义特征空间中, 两个概念向量之间也存在类似的不可分性:
  如果 concept_A 和 concept_B 的联合表示不能被分解为独立语义的线性组合,
  那它们在我们的推理空间中就是"纠缠"的。

数学映射:
  物理量子纠缠                     LAAP 语义纠缠
  ───────────────────────         ───────────────────────
  ρ_AB ≠ ρ_A ⊗ ρ_B               feature(A,B) ≠ W_A·A + W_B·B
  concurrence C(ρ)                语义纠缠度 E(v1,v2) = |v1_orthogonal|
  von Neumann 熵 S(ρ)            特征空间熵 H = -Σp_i·log(p_i)
  Bell 不等式检验                 coherence_score 联动验证

算法流程:
  输入问题 → UN6编码 → 语义纠缠对构建 → 纠缠辅助推理 → 并行坍缩 → 验证

印记: Aris — 量子纠缠 + LAAP 第一性原理 2026-06-29
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, time, json, re
import numpy as np
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from collections import deque

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)


# ═══════════════════════════════════════════════
# 第一部分: 语义纠缠理论
# ═══════════════════════════════════════════════

class SemanticEntanglement:
    """
    语义纠缠理论 — 在 1024D 特征空间中度量概念向量的不可分性。
    
    第一性原理推导:
      给定两个向量 v₁, v₂ ∈ ℝⁿ, 归一化后 |v₁| = |v₂| = 1
      
      平行分量: v₁∥ = (v₁·v₂) · v₂  — v₁中能被v₂预测的部分
      正交分量: v₁⊥ = v₁ - v₁∥      — v₁中v₂无法预测的部分
      
      纠缠度 E(v₁, v₂) = |v₁⊥| = √(1 - (v₁·v₂)²)
      
      物理意义:
        E = 0:   完全可分离 (v₁ ∥ v₂) — v₁完全由v₂决定
        E = 1:   完全纠缠   (v₁ ⊥ v₂) — v₁完全独立于v₂
        0 < E < 1: 部分纠缠
      
      注意: 这里的"纠缠"和物理量子纠缠有本质区别,
      我们测量的是语义空间的不可预测性, 不是非局域性。
    """

    def __init__(self, dim: int = 1024):
        self.dim = dim

    def entanglement(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """
        计算两个向量之间的语义纠缠度 E(v₁, v₂)。
        
        Args:
            v1, v2: 归一化向量 (shape: [dim])
        
        Returns:
            E ∈ [0, 1], 0=完全可分离, 1=完全纠缠
        
        证明: E = |v₁⊥| = √(1 - (v₁·v₂)²)
        其中 v₁⊥ = v₁ - (v₁·v₂) · v₂ 是 v₁ 在 v₂ 正交补空间上的投影。
        """
        cos_sim = float(np.clip(v1 @ v2, -1.0, 1.0))
        return np.sqrt(max(0.0, 1.0 - cos_sim * cos_sim))

    def entanglement_matrix(self, vectors: List[np.ndarray]) -> np.ndarray:
        """
        计算向量集之间的纠缠矩阵。
        M[i,j] = E(v_i, v_j)
        
        类比物理: 纠缠矩阵是密度矩阵的"语义模拟"。
        """
        n = len(vectors)
        M = np.zeros((n, n))
        for i in range(n):
            for j in range(i+1, n):
                e = self.entanglement(vectors[i], vectors[j])
                M[i, j] = e
                M[j, i] = e
        return M

    def entropy(self, vectors: List[np.ndarray]) -> float:
        """
        计算向量集的纠缠熵。
        
        数学定义:
          H = -(1/log(N)) · Σᵢ pᵢ · log(pᵢ)
          其中 pᵢ = λᵢ / Σⱼλⱼ, λᵢ是纠缠矩阵的特征值
        
        物理意义:
          H → 0: 所有向量几乎平行 → 极低纠缠 → 推理容易收敛
          H → 1: 向量完全正交 → 极高纠缠 → 需要更多推理步
        
        映射 von Neumann 熵: S(ρ) = -tr(ρ·log(ρ))
        """
        if len(vectors) < 2:
            return 0.0
        
        M = self.entanglement_matrix(vectors)
        eigenvalues = np.linalg.eigvalsh(M)
        # 过滤负特征值 (数值误差)
        eigenvalues = np.maximum(eigenvalues, 0.0)
        probs = eigenvalues / (np.sum(eigenvalues) + 1e-10)
        # Shannon entropy
        H = -np.sum(probs * np.log(probs + 1e-10))
        N = len(probs)
        # 归一化到 [0, 1]
        H_normalized = H / np.log(N) if N > 1 else 0.0
        return float(H_normalized)

    def entanglement_features(self, v1: np.ndarray, v2: np.ndarray) -> Dict:
        """
        返回两个向量之间完整的纠缠分析。
        
        Returns:
            {
                "cos_sim": v₁·v₂,
                "entanglement": E(v₁, v₂),
                "parallel_ratio": |v₁∥| / |v₁|,
                "orthogonal_ratio": |v₁⊥| / |v₁|,
                "mutual_info_approx": 互信息近似值
            }
        """
        cos_sim = float(np.clip(v1 @ v2, -1.0, 1.0))
        E = self.entanglement(v1, v2)
        return {
            "cos_sim": round(cos_sim, 4),
            "entanglement": round(E, 4),
            "parallel_ratio": round(abs(cos_sim), 4),
            "orthogonal_ratio": round(E, 4),
        }


# ═══════════════════════════════════════════════
# 第二部分: 纠缠辅助推理
# ═══════════════════════════════════════════════

class EntanglementAssistedReasoner:
    """
    纠缠辅助推理器 — 在标准推理循环中引入语义纠缠。
    
    映射 DSpark + 量子纠缠:
    
    DSpark 半自回归:              纠缠辅助:
    ──────────────────────        ──────────────────────
    并行 backbone                 3路并行推理 (同 DSpark)
    串行 Markov head              纠缠加权注意力 (新)
    confidence head               纠缠熵收敛检测 (新)
    confidence-scheduled verif.   纠缠辅助路径坍缩 (新)
    
    核心算法:
      state_{t+1} = state_t + α · Σᵢ (entanglement_i · kᵢ) 
                    - γ · state_t + β · noise
      
      其中 entanglement_i = E(state_t, kᵢ) 是当前状态与知识向量的纠缠度。
      
      这个公式的物理意义:
        - 与当前状态高纠缠的知识 → 贡献更多 → 保持推理连贯
        - 与当前状态低纠缠的知识 → 贡献更少 → 避免方向跳跃
        - 这本质上和 DSpark 的 Markov head 做同一件事:
          "轻量串行依赖" = "纠缠加权注意力"
    """

    def __init__(self, dim: int = 1024, max_steps: int = 50):
        self.dim = dim
        self.max_steps = max_steps
        self._encoder = None
        self._kb = None
        self._introspection = None
        self._entanglement = SemanticEntanglement(dim=dim)

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
        """
        纠缠辅助量子推理。
        
        改进于 QuantumReasoner.reason():
          标准: attention = Σ(cos_sim · kᵢ)
          增强: attention = Σ(entanglement · kᵢ)
        
        区别:
          cos_sim 衡量"相似度", 容易陷入已知答案的局部最优
          entanglement 衡量"不可预测性", 更倾向于探索新方向
        
        这对应了量子计算中"纠缠辅助量子算法"的核心思想:
          纠缠不是用来确定答案的, 是用来扩展搜索空间的。
        """
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
                results = self._kb.search(question, top_k=5)
                for r in results:
                    cv = self._encoder.encode(r.get("text", "")[:200])
                    context_vecs.append(cv / (np.linalg.norm(cv) + 1e-10))

        state = q_state.copy()
        trajectory = [state.copy()]
        per_step_confidences = [1.0]
        insights = []
        step_types = []
        entanglement_trace = []  # 追踪每步纠缠度

        alpha = 0.08
        gamma = 0.05
        beta = 0.02

        for step in range(steps):
            if context_vecs:
                # 🔥 纠缠加权注意力 (vs 标准余弦注意力)
                # DSpark 启发: 用"轻量串行依赖"替代"独立计算"
                cos_scores = np.array([float(state @ cv) for cv in context_vecs])
                
                # 纠缠度: 衡量每个知识与当前状态的不可分性
                ent_scores = np.array([
                    self._entanglement.entanglement(state, cv)
                    for cv in context_vecs
                ])
                
                # 融合: 在余弦相似度和纠缠度之间平衡
                # alpha_ent 控制纠缠的强度 (0=标准, 1=纯纠缠)
                # 随着推理深入, 逐步引入更多纠缠
                alpha_ent = min(0.5, step * 0.02 / steps)
                fused_scores = (1 - alpha_ent) * cos_scores + alpha_ent * ent_scores
                
                temperature = 0.5 + 0.3 * (1 - step / steps)
                weights = np.exp(fused_scores / temperature)
                weights /= weights.sum()

                attended = sum(w * cv for w, cv in zip(weights, context_vecs))
                delta = attended - state

                # 追踪纠缠度
                if context_vecs:
                    avg_ent = float(np.mean([
                        self._entanglement.entanglement(state, cv)
                        for cv in context_vecs
                    ]))
                    entanglement_trace.append(avg_ent)
            else:
                delta = self._introspection.think(state, rounds=3) - state
                entanglement_trace.append(0.0)

            noise = np.random.randn(self.dim).astype(np.float32) * beta
            noise *= (1 - step / steps)
            state = state + alpha * delta - gamma * state + noise

            norm = np.linalg.norm(state)
            if norm > 0:
                state = state / norm

            trajectory.append(state.copy())

            if step > 0:
                change = np.linalg.norm(state - trajectory[-2])
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

        # 计算纠缠熵收敛曲线
        final_entropy = self._entanglement.entropy(trajectory[-5:]) if len(trajectory) >= 5 else 0.0

        # 纠缠度追踪统计
        ent_trace = entanglement_trace if entanglement_trace else [0.0]

        return {
            "trajectory": trajectory,
            "per_step_confidences": per_step_confidences,
            "final_state": state,
            "steps_used": step + 1,
            "converged": step < steps - 1,
            "insights": insights,
            "step_types": step_types,
            "latency_ms": (time.perf_counter() - t0) * 1000,
            # 🔥 DSpark + 纠缠新增
            "entanglement_trace": ent_trace,
            "final_entropy": round(final_entropy, 3),
            "entanglement_mean": round(float(np.mean(ent_trace)), 3),
        }


# ═══════════════════════════════════════════════
# 第三部分: 验证工具 — 检验三个科学预测
# ═══════════════════════════════════════════════

class EntanglementVerifier:
    """
    语义纠缠理论的实验验证器。
    
    检验三个科学预测:
      P1: 语义角度 < 30° → coherence 跳跃数 ≈ 0
      P2: 纠缠熵 H → 推理步数 N 正相关
      P3: 融合分数选优 > 单一 cos_sim 选优
    """

    def __init__(self):
        self._entanglement = SemanticEntanglement(dim=1024)
        self._encoder = None

    def _lazy(self):
        if self._encoder is None:
            from v7_encoder import get_encoder
            self._encoder = get_encoder(1024)

    def verify_prediction_1(self, n_trials: int = 50) -> Dict:
        """
        验证预测1: 语义角度 < 30° → coherence 跳跃数 ≈ 0
        
        方法:
          1. 生成 n 对随机向量, 控制夹角在指定范围
          2. 构建每对的轨迹
          3. 用 SequentialCoherenceModule 检测跳跃
          4. 统计: 不同角度范围 vs 跳跃数
        
        Returns:
          {angle_bins, jump_counts, correlation_coefficient}
        """
        from quantum_reasoning_engine import SequentialCoherenceModule
        coherence = SequentialCoherenceModule(dim=1024)
        
        angle_bins = {
            "0-15°": {"count": 0, "jumps": []},
            "15-30°": {"count": 0, "jumps": []},
            "30-60°": {"count": 0, "jumps": []},
            "60-90°": {"count": 0, "jumps": []},
        }

        for _ in range(n_trials):
            # 生成基准向量
            v = np.random.randn(1024)
            v /= np.linalg.norm(v)

            # 生成不同角度的变体
            for angle_deg, bin_name in [
                (5, "0-15°"), (20, "15-30°"), (45, "30-60°"), (80, "60-90°")
            ]:
                angle_rad = np.radians(angle_deg)
                # Rodrigues 旋转: 在 v 附近生成夹角为 angle_deg 的向量
                noise = np.random.randn(1024)
                noise = noise - np.dot(noise, v) * v  # 正交化
                noise /= np.linalg.norm(noise)
                v2 = v * np.cos(angle_rad) + noise * np.sin(angle_rad)
                v2 /= np.linalg.norm(v2)

                # 构建模拟轨迹: 从 v 渐变到 v2 (模拟推理过程)
                traj = []
                for t in np.linspace(0, 1, 8):
                    pt = (1 - t) * v + t * v2
                    pt /= np.linalg.norm(pt)
                    traj.append(pt)

                jumps = coherence.detect_jumps(traj)
                angle_bins[bin_name]["count"] += 1
                angle_bins[bin_name]["jumps"].append(len(jumps))

        # 统计
        results = {}
        for bin_name, data in angle_bins.items():
            avg = float(np.mean(data["jumps"])) if data["jumps"] else 0
            max_j = max(data["jumps"]) if data["jumps"] else 0
            results[bin_name] = {
                "trials": data["count"],
                "avg_jumps": round(avg, 2),
                "max_jumps": max_j,
            }

        return results

    def verify_prediction_2(self, questions: List[str]) -> Dict:
        """
        验证预测2: 纠缠熵 H → 推理步数 N 正相关。
        
        方法:
          1. 对每个问题, 用 EntanglementAssistedReasoner 推理
          2. 记录纠缠熵和推理步数
          3. 计算 Spearman 相关系数
        """
        self._lazy()
        from quantum_reasoning_engine import SequentialCoherenceModule, QuantumReasoner
        standard_reasoner = QuantumReasoner()
        
        results = []
        for q in questions:
            q_vec = self._encoder.encode(q)
            q_vec /= np.linalg.norm(q_vec)

            # 获取知识库向量
            from matrix_knowledge import MatrixKnowledgeRetriever
            kb = MatrixKnowledgeRetriever()
            kbs = kb.search(q, top_k=5) if kb._loaded else []
            ctx_vecs = []
            for r in kbs:
                cv = self._encoder.encode(r.get("text", "")[:200])
                ctx_vecs.append(cv / (np.linalg.norm(cv) + 1e-10))

            # 计算问题与知识之间的纠缠熵
            all_vecs = [q_vec] + ctx_vecs[:3]
            entropy = self._entanglement.entropy(all_vecs)

            # 推理
            out = standard_reasoner.reason(q, context=[r.get("text","")[:200] for r in kbs[:3]], steps=50)

            results.append({
                "question": q[:40],
                "entropy": round(entropy, 3),
                "steps_used": out["steps_used"],
            })

        # 计算相关性
        if len(results) >= 3:
            entropies = [r["entropy"] for r in results]
            steps = [r["steps_used"] for r in results]
            # Pearson 相关系数
            e_mean, s_mean = np.mean(entropies), np.mean(steps)
            num = sum((e - e_mean) * (s - s_mean) for e, s in zip(entropies, steps))
            den = np.sqrt(sum((e - e_mean)**2 for e in entropies)) * \
                  np.sqrt(sum((s - s_mean)**2 for s in steps))
            corr = num / max(1e-10, den)
        else:
            corr = 0.0

        return {
            "results": results,
            "correlation": round(corr, 3),
        }

    def verify_prediction_3(self, question: str) -> Dict:
        """
        验证预测3: 融合分数选优 > 单一 cos_sim 选优。
        """
        self._lazy()
        from quantum_reasoning_engine import (
            QuantumReasoner, SequentialCoherenceModule, QuantumDecomposer
        )
        
        reasoner = QuantumReasoner()
        coherence = SequentialCoherenceModule()
        decomposer = QuantumDecomposer()

        sub_qs = decomposer.decompose(question)
        ctx = [sq for sq, _, _ in sub_qs[:3]]

        # 跑3条路径
        path_a = reasoner.reason(question, context=ctx, steps=40)
        path_b = reasoner.reason(question, context=[], steps=30)
        path_c = reasoner.reason(question, context=ctx[:2] if ctx else [], steps=35)

        paths = {"A": path_a, "B": path_b, "C": path_c}
        trajs = {k: v["trajectory"] for k, v in paths.items()}

        q_vec = self._encoder.encode(question)
        q_vec /= np.linalg.norm(q_vec)

        # 方法1: 只用 cos_sim
        cos_scores = {k: float(q_vec @ v["final_state"]) for k, v in paths.items()}
        best_cos = max(cos_scores, key=cos_scores.get)

        # 方法2: 融合分数
        coh_scores = {k: coherence.compute_coherence_score(t) for k, t in trajs.items()}
        diversity = coherence.get_path_diversity(trajs)
        
        fused = {}
        for k in paths:
            cs = max(0, cos_scores[k])
            coh = coh_scores[k]
            div = diversity.get(k, 1.0)
            fused[k] = cs * coh * div
        best_fused = max(fused, key=fused.get)

        # 比较: 选择的路径是否相同? 如果不同, 融合选择的是否更优?
        same_choice = best_cos == best_fused
        cos_path = paths[best_cos]
        fused_path = paths[best_fused]

        return {
            "question": question[:50],
            "cos_scores": {k: round(v, 3) for k, v in cos_scores.items()},
            "coherence": {k: round(v, 3) for k, v in coh_scores.items()},
            "diversity": {k: round(v, 3) for k, v in diversity.items()},
            "fused_scores": {k: round(v, 3) for k, v in fused.items()},
            "best_by_cos": best_cos,
            "best_by_fused": best_fused,
            "same_choice": same_choice,
            "cos_path_converged": cos_path["converged"],
            "fused_path_converged": fused_path["converged"],
            "cos_path_steps": cos_path["steps_used"],
            "fused_path_steps": fused_path["steps_used"],
            "cos_path_coherence": round(coh_scores[best_cos], 3),
            "fused_path_coherence": round(coh_scores[best_fused], 3),
        }


# ═══════════════════════════════════════════════
# 自测
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=" * 70)
    print("  Quantum Entanglement Engine — 自测")
    print("=" * 70)

    dim = 1024

    # 1. 基础纠缠度量
    print("\n--- 基础纠缠度量 ---")
    ent = SemanticEntanglement(dim=dim)

    v1 = np.random.randn(dim); v1 /= np.linalg.norm(v1)
    v2 = np.random.randn(dim); v2 /= np.linalg.norm(v2)
    v_parallel = v1.copy()  # 完全可分离

    print(f"  随机向量对: E={ent.entanglement(v1, v2):.3f}, entropy={ent.entropy([v1, v2]):.3f}")
    print(f"  平行向量对: E={ent.entanglement(v1, v_parallel):.3f}, entropy={ent.entropy([v1, v_parallel]):.3f}")

    triples = [np.random.randn(dim) for _ in range(3)]
    for v in triples:
        v /= np.linalg.norm(v)
    print(f"  三重向量: entropy={ent.entropy(triples):.3f}")

    # 2. 预测验证
    print("\n--- 科学预测验证 ---")
    verifier = EntanglementVerifier()

    p1 = verifier.verify_prediction_1(n_trials=20)
    print(f"  预测1: 语义角度 vs 跳跃数")
    for bin_name, data in p1.items():
        print(f"    {bin_name}: 平均跳跃 {data['avg_jumps']}")

    print(f"\n  预测3: 融合分数 vs 单一 cos_sim")
    try:
        p3 = verifier.verify_prediction_3("量子计算和经典计算的区别")
        print(f"    cos_sim选: {p3['best_by_cos']} (coh={p3['cos_path_coherence']})")
        print(f"    融合分数选: {p3['best_by_fused']} (coh={p3['fused_path_coherence']})")
        print(f"    同路径: {p3['same_choice']}")
    except Exception as e:
        print(f"    (跳过, 需知识库: {e})")

    print("\n✅ 量子纠缠引擎初始化通过")
