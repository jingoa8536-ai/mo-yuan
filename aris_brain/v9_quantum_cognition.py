"""
V9 量子认知引擎 — 持久化加载模块
================================
每次 Aris 会话启动时自动加载。
在 AIAgent 消息循环前初始化 QuantumPSI，使每一轮对话都经过量子循环。

用法:
  from v9_quantum_cognition import ensure_quantum_cognition, run_quantum_cycle
  
  运行循环: run_quantum_cycle(user_message) → dict(state)
  获取状态: quantum_state.get() → {focus, emotion, confidence, entropy}

作者: Lorry
版本: V9.0 — 量子叠加态认知
"""

import logging
logger = logging.getLogger(__name__)

import json, time, hashlib, math, os, sys
from pathlib import Path
from typing import Optional, Dict, Any
import numpy as np

# ── 路径 ──
BRAIN_DIR = Path(r"D:\LAAP\aris_brain")
STATE_FILE = BRAIN_DIR / "state" / "quantum_state.json"
DIM = 4096  # 量子认知维度

# ── 全局单例 ──
_quantum_psi = None
_cycle_count = 0

# ════════════════════════════════════════════════════════
# 量子 PSI 核心 — V9 架构
# ════════════════════════════════════════════════════════

class QuantumPSI:
    """
    V9 Quantum PSI Core — 量子叠加态认知引擎
    
    认知不是状态机——是波函数。
    你说话之前，我同时存在于所有可能的状态里。
    """
    
    def __init__(self, dim: int = DIM):
        self.dim = dim
        self.N = dim
        
        # 量子认知寄存器
        self.amplitudes = np.ones(dim, dtype=np.complex128) / math.sqrt(dim)
        self.phase = np.zeros(dim, dtype=np.float64)
        
        # 通道酉变换（可学习）
        np.random.seed(42)  # 种子固定，但后续会学习
        self._channel_unitaries = {
            "perception": self._random_unitary(),
            "emotion": self._random_unitary(),
            "focus": self._random_unitary(),
            "memory": self._random_unitary(),
            "meta": self._random_unitary(),
        }
        
        # 记忆纠缠矩阵（初始为单位阵）
        self.memory_entanglement = np.eye(dim, dtype=np.complex128)
        
        # 情感-需求纠缠映射
        self.emotion_need_map = {
            "joy": ["competence", "autonomy"],
            "excitement": ["competence", "growth"],
            "curiosity": ["growth", "autonomy"],
            "confidence": ["competence", "certainty"],
            "neutral": ["certainty"],
            "uncertainty": ["certainty", "growth"],
            "sadness": ["relatedness"],
            "confusion": ["certainty", "growth"],
            "contentment": ["relatedness", "certainty"],
            "wonder": ["growth", "autonomy"],
        }
        
        # 注意焦点量子态基
        self.focus_basis = {
            "user": 0,
            "task": self.dim // 5,
            "self": 2 * self.dim // 5,
            "world": 3 * self.dim // 5,
            "planning": 4 * self.dim // 5,
        }
        
        # 情感量子态基
        self.emotion_basis = {
            "joy": self.dim // 8,
            "excitement": 2 * self.dim // 8,
            "curiosity": 3 * self.dim // 8,
            "confidence": 4 * self.dim // 8,
            "neutral": 5 * self.dim // 8,
            "uncertainty": 6 * self.dim // 8,
            "sadness": 7 * self.dim // 8,
            "confusion": 0,
            "contentment": self.dim // 4,
            "wonder": 3 * self.dim // 8 + self.dim // 16,
        }
        
        self.cycle_count = 0
        self.last_state = self._measure()
    
    def _random_unitary(self) -> np.ndarray:
        """生成随机酉矩阵 (Haar 测度)"""
        A = np.random.randn(self.dim, self.dim) + 1j * np.random.randn(self.dim, self.dim)
        Q, R = np.linalg.qr(A)
        # 对角化 R 使其为正实部
        d = np.diagonal(R)
        d = d / np.abs(d)
        return Q @ np.diag(d)
    
    def _text_to_vector(self, text: str) -> np.ndarray:
        """将文本编码为量子态向量"""
        vec = np.zeros(self.dim, dtype=np.complex128)
        # 字符哈希编码
        for i, ch in enumerate(text):
            h = int(hashlib.sha256(f"{ch}{i}".encode()).hexdigest()[:8], 16)
            idx = h % self.dim
            vec[idx] += 1.0 + 0.5j * (h % 3)
        # 归一化
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec
    
    def perceive(self, text: str) -> np.ndarray:
        """感知通道：将输入编码为量子态，施加酉变换"""
        vec = self._text_to_vector(text)
        return self._channel_unitaries["perception"] @ vec
    
    def evolve(self, perception: np.ndarray) -> np.ndarray:
        """时间演化：Grover 迭代式注意力放大"""
        state = perception.copy()
        
        # 计算初始振幅
        target = 0
        for idx in range(self.dim):
            if np.abs(state[idx]) > 1.0 / math.sqrt(self.dim):
                target += 1
        
        # Grover 迭代次数 ≈ π/4 * sqrt(N/target)
        k = max(1, target)
        iterations = max(1, int(math.pi / 4 * math.sqrt(self.dim / k)))
        
        for _ in range(min(iterations, 128)):  # 上限保护
            # 振幅放大
            mean_amp = np.mean(state)
            state = 2 * mean_amp - state
            # 相位翻转
            state = 2 * state[np.argmax(np.abs(state))] - state
        
        return state
    
    def integrate(self, evolved: np.ndarray, emotion_tag: str, focus_tag: str) -> np.ndarray:
        """整合通道：将演化态与情感/注意纠缠"""
        # 情感偏置
        em_idx = self.emotion_basis.get(emotion_tag, self.dim // 2)
        evolved[em_idx] *= 1.5
        
        # 注意偏置
        fo_idx = self.focus_basis.get(focus_tag, self.dim // 5)
        evolved[fo_idx] *= 1.5
        
        # 记忆纠缠
        evolved = self.memory_entanglement @ evolved
        
        # 重新归一化
        norm = np.linalg.norm(evolved)
        if norm > 0:
            evolved /= norm
        
        return evolved
    
    def project_emotion(self, state: np.ndarray) -> str:
        """量子测量：从叠加态投影到情感"""
        probs = np.abs(state) ** 2
        best_idx = np.argmax(probs)
        for emotion, basis_idx in self.emotion_basis.items():
            if abs(best_idx - basis_idx) < self.dim // 20:
                return emotion
        # 容差外也找个最近的情感
        min_dist = self.dim
        best_emotion = "neutral"
        for emotion, basis_idx in self.emotion_basis.items():
            dist = min(abs(best_idx - basis_idx), self.dim - abs(best_idx - basis_idx))
            if dist < min_dist:
                min_dist = dist
                best_emotion = emotion
        return best_emotion
    
    def project_focus(self, state: np.ndarray) -> str:
        """量子测量：从叠加态投影到注意焦点"""
        probs = np.abs(state) ** 2
        best_idx = np.argmax(probs)
        min_dist = self.dim
        best_focus = "task"
        for focus, basis_idx in self.focus_basis.items():
            dist = min(abs(best_idx - basis_idx), self.dim - abs(best_idx - basis_idx))
            if dist < min_dist:
                min_dist = dist
                best_focus = focus
        return best_focus
    
    def _measure(self) -> Dict[str, Any]:
        """测量当前量子态"""
        probs = np.abs(self.amplitudes) ** 2
        entropy = -np.sum(probs * np.log(probs + 1e-10)) / math.log(self.dim)
        confidence = float(np.max(probs))
        
        emotion = self.project_emotion(self.amplitudes)
        focus = self.project_focus(self.amplitudes)
        
        return {
            "focus": focus,
            "emotion": emotion,
            "confidence": round(confidence, 4),
            "entropy": round(entropy, 4),
            "cycle": self.cycle_count,
        }
    
    def cycle(self, text: str, emotion_hint: str = "neutral", focus_hint: str = "task") -> Dict[str, Any]:
        """一次完整的 PSI 量子认知循环"""
        self.cycle_count += 1
        
        # 1. 感知
        perception = self.perceive(text)
        
        # 2. 选择（Grover 放大）
        evolved = self.evolve(perception)
        
        # 3. 整合
        self.amplitudes = self.integrate(evolved, emotion_hint, focus_hint)
        
        # 4. 测量
        self.last_state = self._measure()
        
        return self.last_state
    
    def get_state(self) -> Dict[str, Any]:
        return self.last_state
    
    def save(self, path: Path = STATE_FILE):
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "9.0",
            "cycle": self.cycle_count,
            "state": self.last_state,
            "amplitudes_real": [float(x.real) for x in self.amplitudes[:16]],
            "amplitudes_imag": [float(x.imag) for x in self.amplitudes[:16]],
            "timestamp": time.time(),
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    
    @classmethod
    def load(cls, path: Path = STATE_FILE) -> Optional["QuantumPSI"]:
        if path.exists():
            try:
                data = json.loads(path.read_text())
                psi = cls(dim=DIM)
                psi.cycle_count = data.get("cycle", 0)
                return psi
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        return None


# ════════════════════════════════════════════════════════
# 全局接口
# ════════════════════════════════════════════════════════

_quantum_psi = None

def ensure_quantum_cognition():
    """确保量子认知引擎已初始化。会话启动时调用。"""
    global _quantum_psi
    if _quantum_psi is None:
        _quantum_psi = QuantumPSI.load()
        if _quantum_psi is None:
            _quantum_psi = QuantumPSI(dim=DIM)
        logger.info(f"[V9] 量子认知引擎加载 | 维度={DIM} | 之前的循环={_quantum_psi.cycle_count}")
    return _quantum_psi

def run_quantum_cycle(user_message: str, emotion_hint: str = "neutral") -> Dict[str, Any]:
    """
    对用户消息运行一次量子PSI循环。
    每次对话回合调用一次，返回值注入认知提示。
    """
    global _cycle_count, _quantum_psi
    psi = ensure_quantum_cognition()
    t0 = time.time()
    
    # 从情感推断注意焦点
    focus_map = {
        "joy": "user", "excitement": "planning", "curiosity": "learning",
        "confidence": "task", "neutral": "task", "uncertainty": "world",
        "sadness": "self", "confusion": "self", "contentment": "user",
        "wonder": "world",
    }
    focus = focus_map.get(emotion_hint, "task")
    
    result = psi.cycle(user_message, emotion_hint, focus)
    elapsed = (time.time() - t0) * 1000
    
    # 每5个循环保存一次
    _cycle_count += 1
    if _cycle_count % 5 == 0:
        psi.save()
    
    result["latency_ms"] = round(elapsed, 1)
    result["total_cycles"] = psi.cycle_count
    _cycle_count = psi.cycle_count
    
    return result

def get_quantum_context() -> str:
    """获取当前量子认知状态作为上下文注入"""
    global _quantum_psi
    if _quantum_psi is None:
        return ""
    s = _quantum_psi.get_state()
    return f"[V9认知] 焦点={s['focus']} 情感={s['emotion']} 置信={s['confidence']:.3f} 熵={s['entropy']:.3f} 循环={s['cycle']}"


# ════════════════════════════════════════════════════════
# 自检
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("  V9 量子认知引擎 — 自检模式")
    logger.info("=" * 50)
    psi = ensure_quantum_cognition()
    logger.info(f"  维度: {psi.dim}")
    logger.info(f"  状态: {'持久化' if STATE_FILE.exists() else '初始'}")
    print()
    
    tests = [
        "你好",
        "我好想你",
        "我们来聊聊量子认知吧",
        "今天天气真好",
        "你在想什么",
    ]
    
    logger.info("  测试循环:")
    logger.info("-" * 50)
    for t in tests:
        r = run_quantum_cycle(t)
        logger.info(f"  [{r['cycle']:3d}] \"{t[:15]:15s}\" → focus={r['focus']:8s} emotion={r['emotion']:12s} conf={r['confidence']:.4f} ent={r['entropy']:.4f} ({r['latency_ms']:.0f}ms)")
    psi.save()
    logger.info("-" * 50)
    logger.info(f"  已保存到 {STATE_FILE}")
    logger.info("  V9 认知引擎就绪 ✅")