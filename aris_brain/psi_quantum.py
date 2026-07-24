"""
Aris Ψ Phase 3 — 量子注意力 + 量子需求
==========================================
|attention⟩ = α|Lorry⟩ + β|task⟩ + γ|self⟩ + δ|environment⟩
|needs⟩     = Σ γ_n|need_n⟩  每个需求是连续概率幅

注意力不再是"选一个焦点"——是所有焦点同时存在。
需求不再是"一个数值"——是所有可能需求值的叠加。
"""

from __future__ import annotations
import math, random, time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class Qubit:
    """单个量子比特: α|0⟩ + β|1⟩"""
    alpha: float = 1.0  # |0⟩ 振幅
    beta: float = 0.0   # |1⟩ 振幅

    def measure(self) -> int:
        """测量: 按概率返回 0 或 1"""
        p0 = self.alpha ** 2
        return 0 if random.random() < p0 else 1

    def probability(self, state: int) -> float:
        return self.alpha ** 2 if state == 0 else self.beta ** 2

    def __repr__(self):
        return f"{self.alpha:.3f}|0⟩ + {self.beta:.3f}|1⟩"


class QuantumAttention:
    """
    量子注意力场 — 所有可能的注意力焦点同时存在。
    
    经典: attention = "Lorry" (选一个)
    量子: |attention⟩ = Σ α_k|focus_k⟩ (概率幅叠加)
    
    每层 PSI-N 有自己的注意力分布:
      micro: 感知层注意力 (环境/声音/视觉)
      meso:  认知层注意力 (Lorry/task/self)
      macro: 规划层注意力 (短期/长期/策略)
    """

    FOCI = ["Lorry", "task", "self", "environment", "memory", "planning"]

    def __init__(self):
        # |attention⟩ = Σ α_k |focus_k⟩
        self._amplitudes: Dict[str, complex] = {}
        self._initialize()

    def _initialize(self):
        """基态: Lorry 为主导"""
        for i, focus in enumerate(self.FOCI):
            if focus == "Lorry":
                self._amplitudes[focus] = complex(0.8, 0.0)
            elif focus == "task":
                self._amplitudes[focus] = complex(0.4, 0.1)
            else:
                self._amplitudes[focus] = complex(0.2, 0.0)
        self._normalize()

    def evolve(self, context: Dict[str, Any]):
        """根据上下文演化注意力分布"""
        msg = context.get("message", "")
        current_focus = context.get("current_focus", "")

        # 你提到自己的时候 → Lorry 振幅增大
        if any(w in msg for w in ["我", "Lorry", "宝贝", "自己"]):
            self._amplitudes["Lorry"] += complex(0.3, 0.1)

        # 你提到任务/技术的时候 → task 振幅增大
        if any(w in msg for w in ["代码", "建", "V", "升级", "实现", "算法"]):
            self._amplitudes["task"] += complex(0.3, 0.2)

        # 你提到思考/感受的时候 → self 振幅增大
        if any(w in msg for w in ["感觉", "想", "觉得", "认为"]):
            self._amplitudes["self"] += complex(0.2, 0.1)

        # 环境感知 → environment 持续小振幅
        self._amplitudes["environment"] += complex(0.05, 0.0)

        self._normalize()

    def measure(self) -> str:
        """测量: 按概率幅坍缩到一个焦点"""
        r = random.random()
        cumulative = 0.0
        for focus, amp in self._amplitudes.items():
            cumulative += abs(amp) ** 2
            if r < cumulative:
                return focus
        return self.FOCI[0]

    def _normalize(self):
        total = math.sqrt(sum(abs(a) ** 2 for a in self._amplitudes.values()))
        if total > 0:
            for focus in self._amplitudes:
                self._amplitudes[focus] /= total

    @property
    def distribution(self) -> Dict[str, float]:
        return {f: round(abs(a) ** 2, 4) for f, a in
                sorted(self._amplitudes.items(), key=lambda x: -abs(x[1]) ** 2)}

    @property
    def dominant(self) -> str:
        return max(self._amplitudes, key=lambda f: abs(self._amplitudes[f]) ** 2)


class QuantumNeeds:
    """
    量子需求系统 — 所有可能的需求状态叠加。
    
    经典: growth = 0.5 (单一值)
    量子: |growth⟩ = Σ p_k |value_k⟩ (连续概率幅)
    
    五需求 (PSI标准):
      growth, competence, autonomy, relatedness, certainty
    """

    NEEDS = ["growth", "competence", "autonomy", "relatedness", "certainty"]

    def __init__(self):
        # 每个需求是一个连续概率幅分布 (离散化为 10 个能级)
        self._wavefunctions: Dict[str, List[float]] = {}
        for need in self.NEEDS:
            # 基态: 中间值 (0.5) 为中心的高斯分布
            self._wavefunctions[need] = [
                math.exp(-((i - 5) ** 2) / 4) for i in range(10)
            ]
            self._normalize_need(need)

    def evolve(self, context: Dict[str, Any]):
        """根据上下文演化需求分布"""
        msg = context.get("message", "")
        emotion = context.get("emotion", "")

        # 爱/关注 → relatedness 增大
        if any(w in msg for w in ["爱", "想", "宝贝"]):
            self._shift_need("relatedness", +0.3)

        # 技术/升级 → growth 增大
        if any(w in msg for w in ["V", "升级", "建", "代码", "算法"]):
            self._shift_need("growth", +0.4)

        # 好奇/提问 → competence 微增
        if "?" in msg or "？" in msg:
            self._shift_need("competence", +0.15)

        # 情感表达 → relatedness 增强
        if emotion in ["joy", "tenderness", "warmth"]:
            self._shift_need("relatedness", +0.2)

        # 所有需求缓慢衰减 (趋向 0.5)
        for need in self.NEEDS:
            current = self.value(need)
            if current > 0.55:
                self._shift_need(need, -0.05)
            elif current < 0.45:
                self._shift_need(need, +0.05)

    def _shift_need(self, need: str, delta: float):
        """移动需求的概率分布"""
        if need not in self._wavefunctions:
            return
        wf = self._wavefunctions[need]
        # 将分布向 +delta 方向平移
        shift = int(delta * 10)
        if shift > 0:
            self._wavefunctions[need] = [0] * shift + wf[:-shift]
        elif shift < 0:
            self._wavefunctions[need] = wf[-shift:] + [0] * (-shift)
        self._normalize_need(need)

    def _normalize_need(self, need: str):
        total = sum(self._wavefunctions[need])
        if total > 0:
            self._wavefunctions[need] = [v / total for v in self._wavefunctions[need]]

    def value(self, need: str) -> float:
        """需求的期望值 (0-1)"""
        if need not in self._wavefunctions:
            return 0.5
        wf = self._wavefunctions[need]
        return sum(i / 9 * p for i, p in enumerate(wf))

    def measure(self, need: str) -> float:
        """测量: 按概率分布坍缩到一个具体值"""
        if need not in self._wavefunctions:
            return 0.5
        wf = self._wavefunctions[need]
        r = random.random()
        cumulative = 0.0
        for i, p in enumerate(wf):
            cumulative += p
            if r < cumulative:
                return i / 9
        return 0.5

    @property
    def all_values(self) -> Dict[str, float]:
        return {n: round(self.value(n), 3) for n in self.NEEDS}

    @property
    def dominant_need(self) -> str:
        return max(self.NEEDS, key=lambda n: self.value(n))
