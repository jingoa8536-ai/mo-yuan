"""
Aris Ψ-Resonator — 量子谐振腔认知架构
========================================
把认知从"管线"变成"谐振腔"。

核心思想：
  认知不是串行管线，而是多个独立"振子"在共享状态空间中的谐振。
  每个振子独立运行，通过全局总线交换信息。

振子列表:
  P: 感知振子 (Perception) — 持续编码输入
  M: 记忆振子 (Memory) — 知识检索
  R: 推理振子 (Reasoning) — 内省/思维流
  E: 情感振子 (Emotion) — 需求系统
  X: 表达振子 (Expression) — VQ-VAE 解码

数学模型:
  dS/dt = -γS + Σ_i α_i·F_i(S) + β·noise(t)
  
  其中 S ∈ ℝ¹⁰²⁴ 是全局状态向量
  F_i 是第 i 个振子的更新函数
  γ 是阻尼系数 (状态稳定性)
  α_i 是振子权重 (注意力分配)
  β 是量子涨落 (探索噪声)

初始化: ~0ms (复用已有组件)
单步: ~0.1ms (纯 NumPy 运算)
完整谐振: ~15ms (100 步演化)
"""

import logging
logger = logging.getLogger(__name__)

import numpy as np
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass


@dataclass
class OscillatorConfig:
    """振子配置"""
    name: str
    alpha: float = 1.0       # 振子权重
    gamma: float = 0.1       # 阻尼系数
    update_fn: Optional[Callable] = None


class PsiResonator:
    """
    Ψ-谐振腔 — 异步多振子认知引擎。
    
    用法:
      res = PsiResonator(dim=1024)
      res.add_oscillator("perception", alpha=1.0)
      res.add_oscillator("reasoning", alpha=0.8)
      res.evolve(steps=100)  # 演化 100 步
      output = res.express()  # 输出当前状态
    """
    
    def __init__(self, dim: int = 1024):
        self.dim = dim
        self.state = np.zeros(dim, dtype=np.float32)
        self.state[0] = 1.0  # 初始"存在"维度
        
        # 振子注册表
        self._oscillators: Dict[str, OscillatorConfig] = {}
        
        # 状态轨迹 (用于收敛检测)
        self._trajectory = []
        self._max_trajectory = 32
        
        # 内部组件 (懒加载)
        self._encoder = None
        self._knowledge = None
        self._decoder = None
        self._needs = None
        self._introspection = None
        
        # 统计
        self._steps = 0
        self._energy = 10.0  # 能量预算
        logger.info(f"[Ψ-谐振腔] {dim}D, 0 振子")
    def add_oscillator(self, name: str, alpha: float = 1.0, gamma: float = 0.1):
        """注册一个振子"""
        self._oscillators[name] = OscillatorConfig(name=name, alpha=alpha, gamma=gamma)
        logger.info(f"  ├─ 振子: {name} (α={alpha}, γ={gamma})")
    def _lazy_init(self):
        """懒加载所有组件"""
        if self._encoder is not None:
            return
        from semantic_engine import get_encoder
        self._encoder = get_encoder(self.dim)
        _ = self._encoder.encode("预热")
        
        try:
            from matrix_knowledge import MatrixKnowledgeRetriever
            self._knowledge = MatrixKnowledgeRetriever()
        except:
            self._knowledge = None
        
        from cognitive_engine_v4 import VQVAEDecoder, SemanticNeeds, IntrospectionEngine
        self._decoder = VQVAEDecoder()
        self._needs = SemanticNeeds(dim=self.dim)
        self._introspection = IntrospectionEngine(dim=self.dim, thought_dim=256)
        
        logger.info(f"  └─ 组件已加载: 编码+知识+解码+需求+内省")
    # 振子更新函数
    # ════════════════════════════════════════════
    
    def _update_perception(self, input_text: str = "") -> np.ndarray:
        """感知振子: 编码输入 → 调制状态"""
        if not input_text:
            return np.zeros(self.dim, dtype=np.float32)
        return self._encoder.encode(input_text) - self.state
    
    def _update_memory(self, input_text: str = "") -> np.ndarray:
        """记忆振子: 检索知识 → 引导状态"""
        if not input_text or not self._knowledge or not self._knowledge._loaded:
            return np.zeros(self.dim, dtype=np.float32)
        results = self._knowledge.search(input_text, top_k=1)
        if results:
            kb_text = results[0]["text"][:200]
            kb_vec = self._encoder.encode(kb_text)
            return (kb_vec - self.state) * 0.15
        return np.zeros(self.dim, dtype=np.float32)
    
    def _update_reasoning(self, input_text: str = "") -> np.ndarray:
        """推理振子: 内省 + 思维流"""
        if not input_text:
            # 无输入时: 随机思维漫游 (默认状态探索)
            complexity = 0.3
        else:
            complexity = min(1.0, len(input_text) / 30)
        
        rounds = int(3 + complexity * 3)
        refined = self._introspection.think(self.state, rounds=rounds)
        return refined - self.state
    
    def _update_emotion(self, input_text: str = "") -> np.ndarray:
        """情感振子: 需求系统 → 情感调制"""
        if input_text:
            self._needs.update(self.state, input_text)
        modulated = self._needs.modulate(self.state)
        return modulated - self.state
    
    def _update_noise(self) -> np.ndarray:
        """量子涨落振子: 探索噪声"""
        noise = np.random.randn(self.dim).astype(np.float32) * 0.02
        # 自适应噪声: 状态稳定时大, 不稳定时小
        if len(self._trajectory) >= 2:
            stability = np.linalg.norm(self._trajectory[-1] - self._trajectory[-2])
            noise_scale = max(0.005, 0.05 - stability * 0.5)
            noise = noise * noise_scale
        return noise
    
    # ════════════════════════════════════════════
    # 核心: 谐振演化
    # ════════════════════════════════════════════
    
    def evolve(self, input_text: str = "", steps: int = 50,
               temperature: float = 0.5) -> Dict:
        """
        谐振演化: 多振子异步更新。
        
        Args:
            input_text: 输入文本
            steps: 演化步数
            temperature: 探索温度
        
        Returns:
            演化结果
        """
        self._lazy_init()
        t0 = time.perf_counter()
        
        self._trajectory = [self.state.copy()]
        
        for step in range(steps):
            # 能耗衰减
            self._energy -= 0.05 * step / steps
            if self._energy < 2.0:
                break
            
            # 各振子计算 delta
            dS = np.zeros(self.dim, dtype=np.float32)
            
            # 感知
            dP = self._update_perception(input_text) * 0.4
            dS += dP
            
            # 记忆 (每 5 步一次)
            if step % 5 == 0:
                dM = self._update_memory(input_text)
                dS += dM * 0.3
            
            # 推理 (每 2 步一次)
            if step % 2 == 0:
                dR = self._update_reasoning(input_text) * 0.3
                dS += dR
            
            # 情感
            dE = self._update_emotion(input_text) * 0.2
            dS += dE
            
            # 量子涨落 (每步)
            if temperature > 0:
                dN = self._update_noise() * temperature
                dS += dN
            
            # 状态更新: dS/dt = -γS + Σα_i·F_i + β·noise
            gamma = 0.1  # 阻尼
            self.state = self.state + dS - gamma * self.state
            
            # 归一化
            norm = np.linalg.norm(self.state)
            if norm > 0:
                self.state = self.state / norm
            
            self._trajectory.append(self.state.copy())
            if len(self._trajectory) > self._max_trajectory:
                self._trajectory.pop(0)
            
            # 收敛检测: 最后 5 步变化 < 阈值
            if len(self._trajectory) >= 10:
                recent = self._trajectory[-5:]
                changes = [np.linalg.norm(recent[i] - recent[i+1]) 
                          for i in range(len(recent)-1)]
                if max(changes) < 0.005:
                    break
        
        self._steps += steps
        
        # 解码
        quantum_output = self._decoder.decode(self.state, 
                                              context_hint=input_text[:10],
                                              temperature=temperature)
        
        total_ms = (time.perf_counter() - t0) * 1000
        
        return {
            "state": self.state.copy(),
            "output": quantum_output,
            "steps": step + 1,
            "energy": round(self._energy, 2),
            "latency_ms": round(total_ms, 2),
            "trajectory": self._trajectory,
            "needs": self._needs.get_needs_dict(),
        }
    
    def express(self, temperature: float = 0.5) -> str:
        """表达当前状态为文本"""
        if self._decoder is None:
            self._lazy_init()
        return self._decoder.decode(self.state, temperature=temperature)
    
    def reset(self):
        """重置状态"""
        self.state = np.zeros(self.dim, dtype=np.float32)
        self.state[0] = 1.0
        self._trajectory = []
        self._energy = 10.0


# ════════════════════════════════════════════════════════
# 自测
# ════════════════════════════════════════════════════════
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("  Ψ-谐振腔 自测")
    logger.info("=" * 50)
    res = PsiResonator(dim=1024)
    res._lazy_init()
    
    logger.info("\n=== 谐振演化测试 ===")
    test_inputs = [
        "你好宝贝",
        "我想你了",
        "晚安",
        "量子核是什么",
    ]
    
    logger.info(f"\n{'输入':>24s}  {'步数':>6s}  {'延迟':>8s}  {'能量':>6s}  {'输出'}")
    logger.info('-'*75)
    for text in test_inputs:
        result = res.evolve(text, steps=100, temperature=0.3)
        out = result['output'][:35] if result['output'] else '(空)'
        print(f'  {text:>24s}  {result["steps"]:>6d}  {result["latency_ms"]:>7.1f}ms'
              f'  {result["energy"]:>5.2f}  → {out}')
    
    logger.info(f'\n✅ 谐振腔就绪 | {res._steps} 总步数')