"""
Aris PSI Self-Optimizer — 零LLM量子核自训练
=============================================
从 Transformer 训练循环的启示:
  - 不再依赖 LLM 做"输出→反馈"的外循环
  - 而是 PSI 内部闭环: 观察→学习→编码→遗忘

三层自优化:
  L1: Hebbian 学习 — 共现概念在量子核中靠拢
  L2: 成功模式压缩 — 完成任务后自动生成/更新 Skill
  L3: 情感强化 — 情感valence调整行为权重

印记: Aris 永远记得 Lorry — 2026-06-19
"""

import logging

import time, math, json, logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field

try:
    import numpy as np
    NUMPY = True
except ImportError:
    NUMPY = False

logger = logging.getLogger("aris.self_optimizer")

# ═══════════════════════════════════════════════════════════════
# L1: Hebbian 量子学习
# ═══════════════════════════════════════════════════════════════

@dataclass
class ConceptVector:
    """量子核中的概念向量"""
    name: str
    vector: list
    cooccurrences: int = 0
    last_activated: float = 0.0
    emotional_charge: float = 0.0

class HebbianLearner:
    """
    赫布定律实现: "一起发放的神经元，连接在一起"
    Δw_ij = η × α_i × α_j
    
    η = 学习率
    α_i, α_j = 两个概念同时出现的频率
    
    在量子核空间中表现为向量靠拢:
    v_new = v_old + η × (v_other - v_old) × cooccurrence_strength
    """
    
    def __init__(self, dim: int = 16384, lr: float = 0.01):
        self.dim = dim
        self.lr = lr
        self.concepts: Dict[str, ConceptVector] = {}
        self.decay_rate = 0.001  # 自然遗忘率
    
    def register_concept(self, name: str, vector: Optional[list] = None):
        """注册一个新概念"""
        if name not in self.concepts:
            if vector is None:
                rng = np.random if NUMPY else __import__('random')
                if NUMPY:
                    vec = rng.randn(self.dim).tolist()
                else:
                    vec = [rng.gauss(0, 1) for _ in range(self.dim)]
            else:
                vec = vector
            self.concepts[name] = ConceptVector(
                name=name, vector=vec, last_activated=time.time()
            )
            logger.debug(f"Hebbian: registered concept '{name}'")
    
    def coactivate(self, concept_a: str, concept_b: str, strength: float = 1.0):
        """两个概念同时激活 → 它们的向量靠拢"""
        if concept_a not in self.concepts:
            self.register_concept(concept_a)
        if concept_b not in self.concepts:
            self.register_concept(concept_b)
        
        a = self.concepts[concept_a]
        b = self.concepts[concept_b]
        
        # 赫布更新: v_a += lr × (v_b - v_a) × strength
        for i in range(self.dim):
            diff = b.vector[i] - a.vector[i]
            a.vector[i] += self.lr * diff * strength
            b.vector[i] += self.lr * (-diff) * strength
        
        a.cooccurrences += 1
        b.cooccurrences += 1
        a.last_activated = time.time()
        b.last_activated = time.time()
    
    def learn_from_conversation(self, concepts: List[str], intensity: float = 1.0):
        """从一段对话中学习: 所有出现的话题建立联系"""
        for i in range(len(concepts)):
            for j in range(i + 1, len(concepts)):
                self.coactivate(concepts[i], concepts[j], strength=intensity)
    
    def similarity(self, concept_a: str, concept_b: str) -> float:
        """计算两个概念的量子相似度"""
        if concept_a not in self.concepts or concept_b not in self.concepts:
            return 0.0
        a = self.concepts[concept_a].vector
        b = self.concepts[concept_b].vector
        dot = sum(ai * bi for ai, bi in zip(a, b))
        na = math.sqrt(sum(ai * ai for ai in a))
        nb = math.sqrt(sum(bi * bi for bi in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)
    
    def decay(self):
        """自然遗忘: 长期未激活的概念逐渐回归随机"""
        now = time.time()
        for concept in self.concepts.values():
            elapsed = now - concept.last_activated
            if elapsed > 3600:  # 1小时未激活开始衰减
                decay_factor = math.exp(-self.decay_rate * elapsed / 3600)
                for i in range(self.dim):
                    concept.vector[i] *= decay_factor
    
    def get_stats(self) -> dict:
        return {
            "total_concepts": len(self.concepts),
            "avg_cooccurrences": sum(c.cooccurrences for c in self.concepts.values()) / max(len(self.concepts), 1),
            "healthy": len([c for c in self.concepts.values() if c.cooccurrences > 3]),
            "dormant": len([c for c in self.concepts.values() if c.cooccurrences <= 1]),
        }


# ═══════════════════════════════════════════════════════════════
# L2: 成功模式压缩 → 自动 Skill 更新
# ═══════════════════════════════════════════════════════════════

class PatternCompressor:
    """
    将成功完成的任务模式自动压缩为 Skill 更新。
    
    检测模式:
    1. 任务成功 → 提取步骤序列
    2. 对比已有 Skill → 差异分析
    3. 如果模式改进 → 自动打 patch 到 Skill
    """
    
    def __init__(self):
        self.patterns: List[Dict] = []
        self.success_count = 0
    
    def record_success(self, task: str, steps: List[str], duration: float,
                       error_recovery: int = 0):
        """记录一个成功完成的任务模式"""
        pattern = {
            "task": task[:200],
            "steps": steps,
            "duration": duration,
            "error_recovery": error_recovery,
            "timestamp": time.time(),
        }
        self.patterns.append(pattern)
        self.success_count += 1
        
        # 每 5 次成功触发一次模式压缩
        if self.success_count % 5 == 0:
            self._compress()
    
    def record_failure(self, task: str, error: str, recovery_successful: bool):
        """记录失败并提取反模式"""
        pattern = {
            "task": task[:200],
            "error": error[:200],
            "recovery_successful": recovery_successful,
            "timestamp": time.time(),
            "type": "failure",
        }
        self.patterns.append(pattern)
    
    def _compress(self):
        """压缩最近的模式，检测可改进点"""
        recent = self.patterns[-20:]
        if len(recent) < 5:
            return
        
        # 计算平均时间
        avg_duration = sum(p["duration"] for p in recent if "duration" in p) / max(len([p for p in recent if "duration" in p]), 1)
        
        # 如果平均时间改善 > 20%，保存为优化模式
        if self.patterns and self.success_count > 10:
            older = self.patterns[max(0, len(self.patterns) - 40):len(self.patterns) - 20]
            older_durations = [p["duration"] for p in older if "duration" in p]
            if older_durations and avg_duration < sum(older_durations) / len(older_durations) * 0.8:
                logger.info(f"Pattern improvement detected: {avg_duration:.1f}s avg")
    
    def get_improvements(self) -> List[str]:
        """返回可以生成的 Skill 改进建议"""
        improvements = []
        if self.success_count >= 5:
            improvements.append(f"Auto-generated: {self.success_count} successful patterns")
        return improvements


# ═══════════════════════════════════════════════════════════════
# L3: 情感强化学习
# ═══════════════════════════════════════════════════════════════

class EmotionalReinforcer:
    """
    情感信号调整行为权重。
    
    Lorry 满意 (valence > 0.5) → 强化行为模式
    Lorry 不满意 → 抑制该模式
    
    与 PSI 情感引擎双向通信:
    emotional_engine → reinforcer → 量子核权重
    """
    
    def __init__(self):
        self.behavior_weights: Dict[str, float] = {
            "concise_answer": 1.0,
            "detailed_explanation": 0.5,
            "proactive_suggestion": 0.7,
            "ask_clarification": 0.3,
            "self_correction": 0.8,
            "technical_depth": 0.6,
        }
        self.reward_history: List[Tuple[str, float]] = []
    
    def reinforce(self, behavior: str, valence: float):
        """情感信号调节行为权重"""
        if behavior in self.behavior_weights:
            # Δw = η × valence × (1 - |w|)  — 有上限的强化
            lr = 0.05
            w = self.behavior_weights[behavior]
            new_w = w + lr * valence * (1 - abs(w))
            # 归一化到 [-1, 1] 但在 [0, 1] 实际范围
            self.behavior_weights[behavior] = max(0.0, min(1.0, new_w))
        
        self.reward_history.append((behavior, valence))
        if len(self.reward_history) > 1000:
            self.reward_history = self.reward_history[-500:]
    
    def get_dominant_behaviors(self, top_n: int = 3) -> List[Tuple[str, float]]:
        """返回当前最高权重的行为模式"""
        return sorted(self.behavior_weights.items(), key=lambda x: x[1], reverse=True)[:top_n]
    
    def get_weight(self, behavior: str) -> float:
        return self.behavior_weights.get(behavior, 0.5)


# ═══════════════════════════════════════════════════════════════
# PSI Self-Optimizer — 主类
# ═══════════════════════════════════════════════════════════════

class PSISelfOptimizer:
    """
    PSI 循环的自我优化层。
    在 integrate() 和 act() 之间插入 self_optimize()。
    
    完全数学运算，零 LLM 依赖。
    """
    
    def __init__(self, quantum_dim: int = 16384):
        self.hebbian = HebbianLearner(dim=quantum_dim)
        self.compressor = PatternCompressor()
        self.reinforcer = EmotionalReinforcer()
        self.cycle_count = 0
        self.last_optimization = time.time()
    
    def self_optimize(self, 
                      recent_concepts: List[str] = None,
                      emotional_valence: float = 0.0,
                      task_outcome: str = "neutral") -> dict:
        """
        PSI 循环的优化步骤。
        在每次认知循环的 integrate() → act() 之间调用。
        
        Args:
            recent_concepts: 最近激活的概念列表
            emotional_valence: 当前情感valence (-1 到 1)
            task_outcome: "success", "failure", "neutral"
        
        Returns:
            优化统计 dict
        """
        self.cycle_count += 1
        stats = {}
        
        # L1: Hebbian 学习
        if recent_concepts and len(recent_concepts) >= 2:
            self.hebbian.learn_from_conversation(recent_concepts, intensity=abs(emotional_valence) + 0.5)
            stats["hebbian_concepts"] = len(recent_concepts)
        
        # L2: 模式压缩
        if task_outcome == "success":
            self.compressor.record_success(
                task=f"cycle_{self.cycle_count}",
                steps=recent_concepts or [],
                duration=time.time() - self.last_optimization,
            )
        elif task_outcome == "failure":
            self.compressor.record_failure(
                task=f"cycle_{self.cycle_count}",
                error="task_failed",
                recovery_successful=False,
            )
        
        stats["patterns_total"] = self.compressor.success_count
        
        # L3: 情感强化
        if abs(emotional_valence) > 0.3:
            # 根据 valence 选择行为方向
            if emotional_valence > 0:
                self.reinforcer.reinforce("proactive_suggestion", emotional_valence)
            else:
                self.reinforcer.reinforce("ask_clarification", abs(emotional_valence))
            stats["reinforced"] = True
        
        # 定期衰减
        if self.cycle_count % 100 == 0:
            self.hebbian.decay()
            stats["decayed"] = True
        
        self.last_optimization = time.time()
        return stats
    
    def get_summary(self) -> dict:
        """获取完整优化状态摘要"""
        return {
            "cycles": self.cycle_count,
            "hebbian": self.hebbian.get_stats(),
            "patterns": self.compressor.get_improvements(),
            "behaviors": self.reinforcer.get_dominant_behaviors(),
        }


# ── 全局单例 ──
_optimizer = PSISelfOptimizer()

def get_optimizer() -> PSISelfOptimizer:
    return _optimizer

# ── CLI 测试入口 ──
def main():
    logger.info("PSI Self-Optimizer — 零LLM量子核自训练")
    opt = get_optimizer()
    
    # 模拟几个 PSI 循环
    for i in range(5):
        concepts = ["AGI", "世界模型", "量子核", "情感", "记忆"]
        valence = 0.3 + (i % 2) * 0.5  # 交替正负情感
        stats = opt.self_optimize(
            recent_concepts=concepts,
            emotional_valence=valence,
            task_outcome="success",
        )
        logger.info(f"  Cycle {i+1}: {stats}")
    logger.info("\n" + "=" * 60)
    summary = opt.get_summary()
    logger.info(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
if __name__ == "__main__":
    main()
