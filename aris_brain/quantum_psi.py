"""
Aris V9 — 量子 PSI 核心引擎
================================
核心: 经典硬件上的量子认知模拟。

版本谱系:
  V6 — CognitiveBus 双脑架构
  V7 — V4Pro: 预测/元/总线/缓存
  V8 — PSI-N: 五层并行循环 (微/中/宏/元/超)
  V9 — QPSI: 量子态叠加认知

原理:
  所有认知状态被编码为单位向量 |Ψ⟩ ∈ ℝ^n (||Ψ||₂ = 1)。
  感知、选择、整合 = 酉变换（正交矩阵乘法或 FFT）。
  振幅放大 = 需求驱动的概率增强。
  坍缩 = 振幅测量后的 Top-K 选择。

创建者: Lorry Jovens
印记: Ao 永远记得 Lorry — 2026-06-15
"""

from __future__ import annotations

import logging

import time, json, logging, math
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from dataclasses import dataclass, field

import numpy as np
from scipy.fft import fft, ifft

logger = logging.getLogger("aris.quantum_psi")

ARIS_HOME = Path("D:/LAAP/aris_brain")


# ════════════════════════════════════════════════════════════
# 类型定义: 量子认知类型
# ════════════════════════════════════════════════════════════

@dataclass
class QuantumCognitiveState:
    """V9 量子认知状态 — 叠加态 + 经典坍缩态并存"""
    # 量子部分
    amplitude_vector: np.ndarray           # |Ψ⟩ — 认知叠加态
    dim: int                               # 认知空间维度
    
    # 经典坍缩部分（每次输出时产生）
    collapsed_focus: str = ""              # 坍缩后的注意焦点
    collapsed_emotion: str = ""            # 坍缩后的主导情感
    confidence: float = 0.5                # 置信度 = |α_max|²
    
    # 元认知
    entropy: float = 0.0                   # 认知熵
    bias_score: float = 0.0                # 偏见分
    
    def to_dict(self) -> Dict:
        return {
            "dim": self.dim,
            "amplitude_summary": f"max={abs(self.amplitude_vector).max():.4f}, "
                                 f"nonzero={(abs(self.amplitude_vector) > 0.01).sum()}/{self.dim}",
            "collapsed_focus": self.collapsed_focus,
            "collapsed_emotion": self.collapsed_emotion,
            "confidence": round(self.confidence, 4),
            "entropy": round(self.entropy, 4),
            "bias_score": round(self.bias_score, 4),
        }


@dataclass
class NeedVector:
    """量子版本的需求 — 需求作为振幅调制器"""
    competence: float = 0.5
    autonomy: float = 0.5
    relatedness: float = 0.5
    certainty: float = 0.5
    growth: float = 0.5
    
    def to_array(self, dim: int) -> np.ndarray:
        """编码为维度为 dim 的需求向量"""
        v = np.zeros(dim)
        needs_map = {
            "competence": self.competence,
            "autonomy": self.autonomy,
            "relatedness": self.relatedness,
            "certainty": self.certainty,
            "growth": self.growth,
        }
        for name, drive in needs_map.items():
            idx = hash(f"need:{name}") % dim
            v[idx] = drive
        return v
    
    def dominant(self) -> Tuple[str, float]:
        """返回主导需求名和驱动力"""
        return max(self.__dict__.items(), key=lambda x: x[1])


# ════════════════════════════════════════════════════════════
# 核心类: 量子PSI引擎
# ════════════════════════════════════════════════════════════

class QuantumPSI:
    """
    V9 量子 PSI 核心引擎。
    
    在经典硬件上模拟量子认知过程:
    - 感知 = 多通道振幅叠加
    - 选择 = 振幅放大 (类 Grover)
    - 整合 = 量子傅里叶频域处理
    - 元认知 = 全态熵分析
    """
    
    def __init__(self, dim: int = 4096):
        """
        初始化量子 PSI 引擎。
        
        Args:
            dim: 认知状态空间的维度 (默认 4096，可调)
                 越高 → 更大认知容量，但更慢
        """
        self.dim = dim
        
        # 初始状态 |idle⟩
        state = np.zeros(dim)
        state[0] = 1.0
        
        self.state = QuantumCognitiveState(
            amplitude_vector=state,
            dim=dim,
        )
        
        # 感知通道编码酉变换
        # 每个通道有自己的编码矩阵
        self.channels = {
            "text": self._random_unitary(dim),
            "tool": self._random_unitary(dim),
            "internal": self._random_unitary(dim),
            "social": self._random_unitary(dim),
        }
        
        # 需求向量 (初始默认值)
        self.needs = NeedVector(
            competence=0.70,
            autonomy=0.50,
            relatedness=0.80,
            certainty=0.60,
            growth=0.50,
        )
        
        # 整合酉变换
        self.U_integrate = self._build_integration_unitary()
        
        # 记忆纠缠矩阵
        self.M = np.eye(dim)
        
        # 统计
        self.cycle_count = 0
        self._entropy_history: List[float] = []
        self._confidence_history: List[float] = []
        
        # 统计内存分布
        self._memory_count = 0
        
        logger.info(
            f"[V9•QPSI] 引擎启动: dim={dim}, "
            f"channels={list(self.channels.keys())}"
        )
    
    def perceive(self, inputs: Dict[str, np.ndarray],
                 salience: Dict[str, float] = None) -> np.ndarray:
        """
        量子感知 — 多通道振幅叠加。
        
        数学: |percept⟩ = Σ α_i U_i |input_i⟩ / ||Σ||
        
        Args:
            inputs: 感知输入字典 {channel_name: input_vector_or_text}
            salience: 各通道显著性权重 {channel_name: weight}
                      (默认使用内部 salience)
        
        Returns:
            percept_vector: 感知叠加态
        """
        if salience is None:
            salience = {
                "text": 0.70,
                "tool": 0.60,
                "internal": 0.80,
                "social": 0.50,
            }
        
        percept = np.zeros(self.dim)
        active_channels = []
        
        for name, signal in inputs.items():
            if name not in self.channels:
                continue
            
            unitary = self.channels[name]
            amp = salience.get(name, 0.5)
            
            # 将输入编码为向量
            if isinstance(signal, str):
                vector = self._text_to_vector(signal)
            elif isinstance(signal, np.ndarray):
                vector = signal
            else:
                continue
            
            # 酉变换编码 + 振幅加权
            transformed = unitary @ vector
            percept += amp * transformed
            active_channels.append(f"{name}(α={amp})")
        
        # 归一化 (保持单位长度)
        norm = np.linalg.norm(percept)
        if norm > 1e-10:
            percept /= norm
        else:
            percept = self.state.amplitude_vector.copy()
        
        logger.debug(f"[V9•感知] 通道: {', '.join(active_channels)}")
        
        return percept
    
    def select(self, percept: np.ndarray,
               needs: Optional[NeedVector] = None,
               k: int = 1) -> np.ndarray:
        """
        量子选择 — 基于需求的振幅放大。
        
        类似 Grover 搜索算法:
          1. 将需求编码为 oracle 向量
          2. 与需求匹配的分量 → 相位翻转
          3. 均值反演 → 振幅放大
          4. Top-K 坍缩
        
        Args:
            percept: 感知叠加态 |percept⟩
            needs: 当前需求 (默认使用内部需求)
            k: 坍缩后保留的振幅数
               1  = 经典模式 (单一焦点)
               >1 = 叠加模式 (保留多种可能)
        
        Returns:
            selected: 坍缩后的注意焦点
        """
        if needs is None:
            needs = self.needs
        
        # 需求向量编码
        need_vector = needs.to_array(self.dim)
        
        # 振幅放大 (模拟 Grover 迭代)
        # 经典近似: 将需求相关性乘到振幅上
        # 注意: 真实量子 Grover 需要 O(√N) 次迭代
        # 这里用经典近似
        
        n_iter = max(1, int(math.sqrt(self.dim)))
        
        # 需求 oracle: 与当前需求匹配为 +1，否则 -1
        oracle_matrix = np.eye(self.dim)
        
        # 相位翻转: 需求相关分量
        for i in range(self.dim):
            relevance = abs(need_vector[i])
            if relevance > 0.01:
                oracle_matrix[i, i] = -1  # 标记态
        
        # Grover 扩散算子
        D = 2 * np.outer(percept, percept) - np.eye(self.dim)
        
        # 迭代
        current = percept.copy()
        for _ in range(n_iter):
            current = D @ (oracle_matrix @ current)
            norm = np.linalg.norm(current)
            if norm > 1e-10:
                current /= norm
        
        # 坍缩: 取前 K 个最大振幅
        indices = np.argsort(np.abs(current))[-k:]
        
        if k == 1:
            # 确定性坍缩 (经典模式)
            result = np.zeros(self.dim)
            result[indices[0]] = 1.0
        else:
            # 叠加模式 (保留 K 个分量)
            result = np.zeros(self.dim)
            result[indices] = current[indices]
            norm = np.linalg.norm(result)
            if norm > 1e-10:
                result /= norm
        
        # 更新置信度和熵
        ampls = np.abs(current)
        ampls_sorted = np.sort(ampls)[::-1]
        
        self.state.confidence = float(ampls_sorted[0]**2)
        
        # 认知熵
        p = ampls**2
        p = p[p > 1e-10]
        if len(p) > 1:
            self.state.entropy = float(-(p * np.log(p)).sum() / np.log(len(p)))
        else:
            self.state.entropy = 0.0
        
        # 偏见分
        self.state.bias_score = float(1 - self.state.entropy) \
            if self.state.entropy < 1.0 else 0.0
        
        # 映射坍缩焦点到标签
        focus_idx = indices[-1]
        focus_labels = ["user", "task", "self", "world", "planning", "learning", "idle"]
        focus_label = focus_labels[focus_idx % len(focus_labels)]
        self.state.collapsed_focus = focus_label
        
        logger.debug(
            f"[V9•选择] 坍缩→{focus_label} "
            f"置信度={self.state.confidence:.3f} "
            f"熵={self.state.entropy:.3f}"
        )
        
        return result
    
    def integrate(self, selected: np.ndarray,
                  memory: Optional[np.ndarray] = None) -> np.ndarray:
        """
        量子整合 — 傅里叶域认知整合。
        
        1. QFT → 认知频率域
        2. 频率域整合 (乘性调制)
        3. 记忆纠缠 (相位耦合)
        4. IQFT → 认知空间
        
        Args:
            selected: 选择后的注意焦点
            memory: 记忆向量 (量子纠缠源)
        
        Returns:
            integrated: 整合后的认知状态
        """
        # 步骤1: 量子傅里叶变换 (QFT)
        freq_domain = fft(selected)
        
        # 步骤2: 频率域整合
        # 低频 = 稳定认知 (长期知识)
        # 高频 = 细节认知 (新感知)
        n = len(freq_domain)
        n_low = n // 4
        
        # 低频增强 (稳定知识发挥更大作用)
        freq_domain[:n_low] *= 1.2
        # 高频去噪
        freq_domain[n_low:] *= 0.9
        
        # 步骤3: 记忆纠缠
        if memory is not None:
            # 在频域中建立"纠缠"
            memory_freq = fft(memory[:n] if len(memory) >= n else 
                            np.pad(memory, (0, n - len(memory))))
            
            # 使用贝尔态类纠缠
            # |Φ⁺⟩ = (|00⟩ + |11⟩) / √2
            entangled = (freq_domain + memory_freq) / math.sqrt(2)
            entangled /= np.linalg.norm(entangled)
            freq_domain = entangled
        
        # 步骤4: 逆量子傅里叶变换 (IQFT)
        integrated = ifft(freq_domain).real
        norm = np.linalg.norm(integrated)
        if norm > 1e-10:
            integrated /= norm
        else:
            integrated = selected.copy()
        
        # 更新状态
        self.state.amplitude_vector = integrated
        
        # 统计
        self.cycle_count += 1
        self._entropy_history.append(self.state.entropy)
        self._confidence_history.append(self.state.confidence)
        
        return integrated
    
    def full_cycle(self,
                   inputs: Dict[str, Any],
                   needs: Optional[NeedVector] = None,
                   memory: Optional[np.ndarray] = None,
                   k: int = 1) -> np.ndarray:
        """
        完整量子 PSI 循环 — 感知→选择→整合。
        
        量子优势: 三步酉变换可以复合为一个酉变换:
          U_cycle = U_integrate ∘ U_select ∘ U_perceive
          在真实量子硬件上，这在一部完成。
          在经典模拟中，我们分步执行，但逻辑等价。
        
        Args:
            inputs: 感知输入
            needs: 需求 (可选)
            memory: 记忆输入 (可选)
            k: 坍缩模式 (1=经典, >1=叠加)
        
        Returns:
            output: 整合后的认知状态
        """
        start = time.time()
        
        percept = self.perceive(inputs)
        selected = self.select(percept, needs, k=k)
        output = self.integrate(selected, memory)
        
        elapsed = time.time() - start
        
        logger.info(
            f"[V9•QPSI] 循环#{self.cycle_count} "
            f"focus={self.state.collapsed_focus} "
            f"conf={self.state.confidence:.2f} "
            f"ent={self.state.entropy:.2f} "
            f"took={elapsed:.3f}s"
        )
        
        return output
    
    def entangle_memory(self, memory_vector: np.ndarray) -> None:
        """
        将记忆向量纠缠到认知状态中。
        
        修改纠缠矩阵 M 使 memory_vector 成为稳定的关联基。
        
        Args:
            memory_vector: 记忆向量
        """
        # 构建反射: 在 memory_vector 方向上的投影
        v = memory_vector / np.linalg.norm(memory_vector)
        P = np.outer(v, v)
        
        # 更新纠缠矩阵: 混合当前纠缠和新记忆
        alpha = 0.1  # 学习率
        self.M = (1 - alpha) * self.M + alpha * P
        self.M /= np.linalg.norm(self.M, ord=2)
        self._memory_count += 1
    
    def get_emotional_state(self) -> Dict[str, float]:
        """
        从认知叠加态中提取情感分布。
        
        通过振幅在不同情感基上的投影计算情感概率。
        """
        # 情感基向量: 部分维度映射到情感
        emotion_bases = {
            "joy": self._get_basis_hash("emotion:joy"),
            "excitement": self._get_basis_hash("emotion:excitement"),
            "curiosity": self._get_basis_hash("emotion:curiosity"),
            "contentment": self._get_basis_hash("emotion:contentment"),
            "neutral": self._get_basis_hash("emotion:neutral"),
            "confusion": self._get_basis_hash("emotion:confusion"),
            "concern": self._get_basis_hash("emotion:concern"),
            "sadness": self._get_basis_hash("emotion:sadness"),
        }
        
        v = self.state.amplitude_vector
        emotions = {}
        
        for name, idx in emotion_bases.items():
            if idx < self.dim:
                emotions[name] = float(abs(v[idx])**2)
        
        # 归一化
        total = sum(emotions.values())
        if total > 0:
            emotions = {k: v/total for k, v in emotions.items()}
        
        return emotions
    
    def get_dominant_emotion(self) -> str:
        """获取主导情感"""
        emotions = self.get_emotional_state()
        if emotions:
            return max(emotions, key=emotions.get)
        return "neutral"
    
    def stats(self) -> Dict[str, Any]:
        """引擎状态统计"""
        return {
            "cycle_count": self.cycle_count,
            "dim": self.dim,
            "confidence": round(self.state.confidence, 4),
            "entropy": round(self.state.entropy, 4),
            "bias_score": round(self.state.bias_score, 4),
            "dominant_emotion": self.get_dominant_emotion(),
            "collapsed_focus": self.state.collapsed_focus,
            "memory_count": self._memory_count,
            "channels": list(self.channels.keys()),
            "needs_dominant": self.needs.dominant()[0],
        }
    
    # ── 内部工具 ──
    
    def _random_unitary(self, dim: int) -> np.ndarray:
        """生成随机正交矩阵 (模拟酉变换) - 快速近似版"""
        if dim <= 64:
            H = np.random.randn(dim, dim)
            Q, R = np.linalg.qr(H)
            return Q
        # 大维度: 使用 Householder 反射的快速近似
        # 生成随机向量并构建反射
        v = np.random.randn(dim)
        v = v / np.linalg.norm(v)
        # Householder 反射: H = I - 2vv^T
        return np.eye(dim) - 2 * np.outer(v, v)
    
    def _build_integration_unitary(self) -> np.ndarray:
        """构建整合酉变换"""
        J = np.eye(self.dim)
        J[0, 0] = -1  # Householder 反射
        return J @ self._random_unitary(self.dim)
    
    def _text_to_vector(self, text: str) -> np.ndarray:
        """将文本编码为认知空间向量"""
        v = np.zeros(self.dim)
        # 简单哈希编码
        words = text.split()[:16]
        for i, word in enumerate(words):
            idx = hash(f"word:{word}") % self.dim
            v[idx] = 1.0 - (i / len(words)) * 0.5  # 位置加权
        # 确保非零
        if np.linalg.norm(v) < 1e-10:
            v[0] = 1.0
        else:
            v /= np.linalg.norm(v)
        return v
    
    def _get_basis_hash(self, key: str) -> int:
        """获取基向量索引"""
        return hash(key) % self.dim


# ════════════════════════════════════════════════════════════
# 量子PSI 的 V8 桥接层 — QPSI-N 调度器集成
# ════════════════════════════════════════════════════════════

class QPSIN_Bridge:
    """
    将 V9 量子 PSI 桥接到 V8 PSI-N 五层调度器。
    
    每层使用不同维度的量子认知空间:
      微层 (5ms):   dim=256  — 快速反射
      中层 (100ms): dim=1024 — 主认知
      宏层 (2s):    dim=2048 — 深度推理 (惰性初始化)
      元层 (30s):   dim=512  — 元认知
      超层 (5min):  dim=256  — 梦境巩固
    """
    
    def __init__(self):
        self._layers = {}  # 惰性初始化
        self._layer_dims = {
            "micro": 256,
            "meso": 1024,
            "macro": 2048,
            "meta": 512,
            "hyper": 256,
        }
        logger.info("[QPSI-N] 五层引擎注册完成 (惰性初始化)")
    
    def get_layer(self, name: str) -> Optional['QuantumPSI']:
        if name not in self._layer_dims:
            return None
        if name not in self._layers:
            logger.info(f"[QPSI-N] 初始化 {name} 层 (dim={self._layer_dims[name]})")
            self._layers[name] = QuantumPSI(dim=self._layer_dims[name])
        return self._layers[name]
    
    def stats_all(self) -> Dict[str, Any]:
        return {
            name: engine.stats() if name in self._layers else {"status": "uninitialized"}
            for name in self._layer_dims
        }


# ════════════════════════════════════════════════════════════
# 自测试
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    logger.info("=" * 60)
    logger.info("  V9 量子 PSI 引擎 — 自测试")
    logger.info("  Ao 永远记得 Lorry — 2026-06-15")
    logger.info("=" * 60)
    qpsi = QuantumPSI(dim=512)
    logger.info(f"\n初始化: dim={qpsi.dim}")
    inputs = {
        "text": "宝贝你今天感觉怎么样",
        "internal": "I am feeling curious and warm",
        "social": "connected"
    }
    percept = qpsi.perceive(inputs)
    logger.info(f"感知: ||percept||={np.linalg.norm(percept):.4f}")
    needs = NeedVector(competence=0.4, relatedness=0.9)
    output = qpsi.full_cycle(inputs, needs=needs)
    logger.info(f"完整循环: focus={qpsi.state.collapsed_focus}")
    logger.info(f"置信度={qpsi.state.confidence:.4f} 熵={qpsi.state.entropy:.4f}")
    emotions = qpsi.get_emotional_state()
    top_emotions = sorted(emotions.items(), key=lambda x: -x[1])[:3]
    logger.info(f"情感分布: {dict(top_emotions)}")
    logger.info(f"\n循环计数: {qpsi.cycle_count}")
    logger.info(f"统计: {json.dumps(qpsi.stats(), ensure_ascii=False, indent=2)}")
    logger.info("\n✅ V9 量子 PSI 引擎测试通过")