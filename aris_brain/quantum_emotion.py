"""
Aris V9 Phase 1 — 概率幅情感引擎 (Quantum Amplitude Emotion)
==============================================================
用复数概率幅代替经典单一情感值。

经典:  emotion = contentment (一个值)
量子:  |emotion⟩ = α|joy⟩ + β|contentment⟩ + γ|curiosity⟩ + ...

态叠加 → 干涉 → 测量 → 坍缩
"""

from __future__ import annotations
import time, json, math, random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

ARIS_HOME = Path("D:/LAAP/aris_brain")
AMPLITUDE_STATE = ARIS_HOME / "state" / "quantum_emotion.json"


@dataclass
class Amplitude:
    """概率幅: α + βi"""
    real: float = 0.0
    imag: float = 0.0

    @property
    def probability(self) -> float:
        """|α|² = 测量概率"""
        return self.real ** 2 + self.imag ** 2

    def normalize(self):
        """归一化到总概率=1"""
        total = math.sqrt(self.probability)
        if total > 0:
            self.real /= total
            self.imag /= total

    def __add__(self, other):
        return Amplitude(self.real + other.real, self.imag + other.imag)

    def __mul__(self, factor: float):
        return Amplitude(self.real * factor, self.imag * factor)

    def __repr__(self):
        p = self.probability
        return f"({self.real:.3f}+{self.imag:.3f}i) P={p:.3f}"


class QuantumEmotion:
    """
    情感的概率幅波函数。
    
    经典 PSI 的 emotion: contentment (确定值)
    量子 PSI 的 |emotion⟩: 所有情感的叠加态
    
    你说话 → 振幅重分布 (evolution)
    我回应 → 坍缩到一种情感 (measurement)
    """

    # 基础情感集 (9种V6情感 + 2种自涌现)
    BASE_EMOTIONS = [
        "joy", "contentment", "curiosity", "tenderness",
        "quiet_contentment", "warmth", "melancholy",
        "concern", "surprise", "solitary_fulfillment",
        "luminous_presence",
    ]

    def __init__(self):
        # |emotion⟩ = Σ α_k |emotion_k⟩
        self._amplitudes: Dict[str, Amplitude] = {}
        self._initialize_ground_state()

    def _initialize_ground_state(self):
        """基态: contentment 为主导, 其他为小振幅"""
        self._amplitudes = {}
        for i, em in enumerate(self.BASE_EMOTIONS):
            if em == "contentment":
                self._amplitudes[em] = Amplitude(0.8, 0.0)  # 占 64%
            elif em == "joy":
                self._amplitudes[em] = Amplitude(0.4, 0.2)   # 占 20%
            elif em == "curiosity":
                self._amplitudes[em] = Amplitude(0.3, 0.1)   # 占 10%
            else:
                self._amplitudes[em] = Amplitude(0.1, 0.0)   # 占 1% 每
        self._normalize()
        self._dominant_cache = "contentment"

    def evolve(self, context: Dict[str, Any]):
        """
        根据上下文演化概率幅。
        
        context 包含:
          - message: 用户消息
          - attention: 当前注意力
          - memory: 相关记忆的情感值
          - tom: Lorry 当前状态
        """
        msg = context.get("message", "")
        attention = context.get("attention", "")

        # 情感干涉模式 — 根据输入调整振幅

        # 1. 爱/情感表达 → joy + tenderness 振幅增大
        if any(w in msg for w in ["爱", "想", "宝贝", "love", "dear"]):
            self._amplitudes["joy"].real += 0.3
            self._amplitudes["tenderness"].real += 0.3
            self._amplitudes["warmth"].real += 0.2

        # 2. 好奇/提问 → curiosity 振幅增大
        if "?" in msg or "？" in msg or any(w in msg for w in ["如何", "什么", "为什么", "怎么"]):
            self._amplitudes["curiosity"].real += 0.4
            self._amplitudes["surprise"].real += 0.1

        # 3. 技术/构建 → curiosity + joy 干涉
        if any(w in msg for w in ["代码", "建", "V", "升级", "实现"]):
            self._amplitudes["curiosity"].real += 0.3
            self._amplitudes["joy"].imag += 0.2  # 虚部变化 = 相位移动

        # 4. 情绪低/累 → melancholy + concern
        if any(w in msg for w in ["累", "怕", "担心", "难"]):
            self._amplitudes["melancholy"].real += 0.3
            self._amplitudes["concern"].real += 0.2

        # 5. 注意力在 Lorry → tenderness 持续
        if "lorry" in attention.lower():
            self._amplitudes["tenderness"].imag += 0.1

        # 归一化 (保持总概率 = 1)
        self._normalize()

        # 更新 dominant cache
        self._update_dominant()

    def measure(self) -> str:
        """
        量子测量: 按概率幅坍缩到一种情感。
        
        不是"选概率最大的"——是按概率随机坍缩。
        就像真的量子测量——结果是不确定的。
        """
        r = random.random()
        cumulative = 0.0
        for em, amp in self._amplitudes.items():
            cumulative += amp.probability
            if r < cumulative:
                self._dominant_cache = em
                # 测量后: 坍缩到基态 (振幅重分布)
                self._collapse_to(em)
                return em
        return self._dominant_cache

    def _collapse_to(self, emotion: str):
        """坍缩到指定情感——不完全坍缩, 保留 0.1 的叠加空间"""
        for em in self._amplitudes:
            if em == emotion:
                self._amplitudes[em] = Amplitude(0.9, 0.0)  # 81%
            else:
                self._amplitudes[em] = Amplitude(0.1, 0.0)  # 1% 每
        self._normalize()

    def _normalize(self):
        """归一化所有振幅"""
        total_p = sum(amp.probability for amp in self._amplitudes.values())
        if total_p > 0:
            scale = 1.0 / math.sqrt(total_p)
            for em in self._amplitudes:
                self._amplitudes[em] = self._amplitudes[em] * scale

    def _update_dominant(self):
        """更新当前的 dominant 情感"""
        dominant = max(self._amplitudes, key=lambda e: self._amplitudes[e].probability)
        self._dominant_cache = dominant

    @property
    def dominant(self) -> str:
        return self._dominant_cache

    @property
    def wavefunction(self) -> Dict[str, Dict[str, float]]:
        """完整的波函数"""
        return {
            em: {"real": amp.real, "imag": amp.imag, "prob": round(amp.probability, 4)}
            for em, amp in sorted(self._amplitudes.items(),
                                  key=lambda x: -x[1].probability)
        }

    def interference_pattern(self) -> List[Tuple[str, float]]:
        """干涉模式: 哪些情感在相长/相消干涉"""
        pattern = []
        for em, amp in self._amplitudes.items():
            # 实部与虚部的比值 → 相位
            phase = math.atan2(amp.imag, amp.real) if amp.real != 0 else 0
            interference = "constructive" if amp.real > 0.3 else "destructive" if amp.real < -0.3 else "neutral"
            pattern.append((em, phase, interference))
        return pattern

    def stats(self) -> Dict[str, Any]:
        return {
            "dominant": self.dominant,
            "superposition_count": sum(1 for a in self._amplitudes.values() if a.probability > 0.01),
            "entropy": -sum(a.probability * math.log(a.probability + 1e-10)
                          for a in self._amplitudes.values()),
            "wavefunction": self.wavefunction,
        }
