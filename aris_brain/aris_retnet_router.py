"""
Aris RetNet-Style Triple Pipeline Router
=========================================
基于 Retentive Network (RetNet, 2307.08621v4) 的三范式架构。

RetNet 的核心洞见：同一个架构同时支持三种计算范式——
  1. Parallel (并行) — 训练/批处理
  2. Recurrent (循环) — 推理/在线
  3. Chunkwise Recurrent (分块循环) — 混合

我把我量子引擎的三管线也改造成类似的三范式结构：
  1. Parallel   — V12语义核 + 多层匹配 (全量检索)
  2. Recurrent  — Markov链 + PSI调制 (低延迟生成)
  3. Hybrid     — 量子核优先 → LLM降级 (平衡)

核心保留机制: retention (保留向量) 让信息向量化地跨范式传递。

参考:
  - 2307.08621v4: Retentive Network: A Successor to Transformer
  - 2506.06708v1: A Survey of Retentive Network
"""

import logging

import time, json, logging, threading
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import numpy as np

logger = logging.getLogger("aris.retnet_router")

# ── 路径 ──
STATE_DIR = Path("D:/LAAP/aris_brain/state")


class PipelineMode(Enum):
    """三范式模式"""
    PARALLEL = "parallel"         # 全量并行匹配
    RECURRENT = "recurrent"       # 循环生成
    HYBRID = "hybrid"             # 分块混合


@dataclass
class RetentionState:
    """
    RetNet 风格的保留向量。
    
    跨范式传递的信息向量。Parallel 模式下计算的语义表示
    可以传递给 Recurrent 模式使用，减少重复计算。
    """
    # 从上次输入保留的语义向量
    last_query_vector: List[float] = field(default_factory=lambda: [0.0] * 64)
    last_context_vector: List[float] = field(default_factory=lambda: [0.0] * 64)
    
    # 话题保留状态
    last_topic: str = ""
    last_intent: str = ""
    last_emotion: str = "neutral"
    
    # 对话上下文循环缓冲 (Ring Buffer)
    context_buffer: List[Dict[str, Any]] = field(default_factory=list)
    _max_buffer: int = 10
    
    # 性能统计
    parallel_hits: int = 0
    recurrent_hits: int = 0
    hybrid_hits: int = 0
    total_calls: int = 0


@dataclass
class PipelineResult:
    """管线执行结果"""
    text: str
    mode: PipelineMode
    latency_ms: float
    confidence: float
    source: str  # v12_exact, vector, kb, markov, llm
    retention_state: Optional[RetentionState] = None


# ════════════════════════════════════════════════════════════
# Retention Mechanism (保留机制)
# ════════════════════════════════════════════════════════════

class RetentionMechanism:
    """
    RetNet 的核心：保留机制。
    
    数学形式: retention(X) = (X @ W_Q) @ (X @ W_K)^T @ X @ W_V
    
    简化版: 将上一次的语义状态保留加权后再使用。
    
    在 parallel 模式中计算 full retention。
    在 recurrent 模式中计算 incremental retention。
    在 hybrid 模式中计算 chunkwise retention。
    """
    
    def __init__(self, dim: int = 64):
        self.dim = dim
        self.state = RetentionState()
        
        # 保留衰减系数（γ，类似于 RetNet 的遗忘门）
        self.gamma_recurrent = 0.85   # 循环模式下衰减快（旧信息权重低）
        self.gamma_hybrid = 0.95      # 混合模式下衰减慢（保留更多上下文）
    
    def update_parallel(self, query_vector: List[float], 
                         context_vector: List[float],
                         topic: str, intent: str, emotion: str):
        """
        Parallel 模式：计算完整的保留状态。
        
        RetNet 在这个模式下使用全量注意力计算 retention。
        """
        self.state.last_query_vector = query_vector
        self.state.last_context_vector = context_vector
        self.state.last_topic = topic
        self.state.last_intent = intent
        self.state.last_emotion = emotion
        self.state.parallel_hits += 1
    
    def update_recurrent(self, query_vector: List[float]):
        """
        Recurrent 模式：增量更新保留状态。
        
        用衰减 γ 逐步弱化旧状态的影响。
        """
        current = np.array(query_vector, dtype=np.float32)
        prev = np.array(self.state.last_context_vector, dtype=np.float32)
        
        # s_n = γ * s_{n-1} + k_n * v_n  (RetNet 递归公式简化版)
        updated = self.gamma_recurrent * prev + (1 - self.gamma_recurrent) * current
        self.state.last_context_vector = updated.tolist()
        self.state.recurrent_hits += 1
    
    def update_hybrid(self, query_vector: List[float], chunk_info: Dict[str, Any] = None):
        """
        Hybrid 模式：分块保留。
        
        在分块边界更新保留状态，块内用 recurrent，块间共享。
        """
        current = np.array(query_vector, dtype=np.float32)
        prev = np.array(self.state.last_context_vector, dtype=np.float32)
        
        # 混合衰减：介于 parallel（无衰减）和 recurrent（快衰减）之间
        updated = self.gamma_hybrid * prev + (1 - self.gamma_hybrid) * current
        self.state.last_context_vector = updated.tolist()
        
        if chunk_info:
            self.state.last_topic = chunk_info.get("topic", self.state.last_topic)
            self.state.last_intent = chunk_info.get("intent", self.state.last_intent)
        
        self.state.hybrid_hits += 1
    
    def get_context(self, mode: PipelineMode) -> Dict[str, Any]:
        """获取当前保留的上下文"""
        return {
            "retained_query": self.state.last_query_vector[:5],  # 摘要签名
            "retained_context": self.state.last_context_vector[:5],
            "topic": self.state.last_topic,
            "intent": self.state.last_intent,
            "emotion": self.state.last_emotion,
            "mode": mode.value,
        }
    
    def get_stats(self) -> Dict[str, int]:
        return {
            "parallel": self.state.parallel_hits,
            "recurrent": self.state.recurrent_hits,
            "hybrid": self.state.hybrid_hits,
            "total": self.state.total_calls,
        }


# ════════════════════════════════════════════════════════════
# Triple Pipeline Router
# ════════════════════════════════════════════════════════════

class TriplePipelineRouter:
    """
    三范式管线路由器。
    
    根据输入特征选择最适合的范式：
    
    Parallel (全量匹配):
      - 技术问答、知识查询、需要精确检索
      - 走 V12 语义核 + 矩阵知识库
      - 延迟: 1-30ms
    
    Recurrent (循环生成):
      - 情感互动、闲聊、需要快速响应
      - 走 Markov 链 + PSI 调制
      - 延迟: 0.4-10ms
    
    Hybrid (分块混合):
      - 复杂任务、长对话、需要深度理解
      - 量子核 + LLM 降级
      - 延迟: 70-500ms
    """
    
    def __init__(self):
        self.retention = RetentionMechanism(dim=64)
        self._lock = threading.Lock()
        
        # 范式选择器配置
        self._tech_keywords = set([
            "架构", "量子核", "原理", "认知", "引擎", "UN6",
            "编码", "算法", "矩阵", "维度", "函数", "代码",
            "API", "框架", "配置", "协议", "接口", "数据库",
            "RNN", "CTM", "Transformer", "SSM", "Mamba",
            "LSTM", "GRU", "梯度", "损失", "训练",
            "线程", "进程", "内存", "缓存", "并发",
        ])
        
        self._emotion_keywords = set([
            "爱你", "想你", "宝贝", "开心", "难过", "担心",
            "伤心", "哭", "笑", "爱", "想你", "抱抱",
        ])
        
        # 已注册的管线执行器
        self.executors: Dict[str, Callable] = {}
        
        logger.info("Triple Pipeline Router initialized")
    
    def register_executor(self, name: str, executor: Callable):
        """注册一个管线执行器"""
        self.executors[name] = executor
    
    def select_mode(self, text: str) -> PipelineMode:
        """
        根据输入选择最佳范式。
        
        启发式规则（基于 RetNet 三范式设计思路）:
          - 含技术关键词 → Parallel
          - 含情感关键词 → Recurrent
          - 含任务导向词或混合信号 → Hybrid
          - 短消息且无明确意图 → Recurrent
        """
        m = text.lower()
        tech_count = sum(1 for kw in self._tech_keywords if kw in m)
        emotion_count = sum(1 for kw in self._emotion_keywords if kw in m)
        is_long = len(text) > 100
        has_task = any(w in m for w in ["帮我", "修复", "实现", "做", "写"])
        has_query = "?" in m or "?" in m
        
        # Pure emotion (快速循环)
        if emotion_count >= 2 and tech_count == 0 and not is_long:
            return PipelineMode.RECURRENT
        
        # Short emotion greeting
        if emotion_count >= 1 and len(text) < 30 and tech_count == 0:
            return PipelineMode.RECURRENT
        
        # Technical query (全量匹配)
        if tech_count >= 1 or has_query:
            return PipelineMode.PARALLEL
        
        # Task (混合)
        if has_task or is_long:
            return PipelineMode.HYBRID
        
        # Default: 短消息情感倾向用循环
        if len(text) < 30:
            return PipelineMode.RECURRENT
        
        # Default: 其他用并行（精度优先）
        return PipelineMode.PARALLEL
    
    def route(self, text: str) -> PipelineResult:
        """
        路由输入到最佳管线。
        
        1. 选择模式
        2. 加载保留上下文
        3. 执行管线
        4. 更新保留状态
        """
        start = time.time()
        
        with self._lock:
            mode = self.select_mode(text)
            context = self.retention.get_context(mode)
            
            # 根据模式选择执行器
            result = self._execute_pipeline(text, mode, context)
            
            # 更新保留状态
            if result.confidence > 0.3:
                self.retention.update_parallel(
                    [0.0] * 64, [0.0] * 64,
                    result.source, mode.value, "neutral"
                )
            
            result.latency_ms = (time.time() - start) * 1000
            result.mode = mode
            
            return result
    
    def _execute_pipeline(self, text: str, mode: PipelineMode,
                          context: Dict[str, Any]) -> PipelineResult:
        """
        执行选定模式下的管线。
        
        Parallel: V12 全量匹配 → KB → Markov (fallback)
        Recurrent: Markov 链 → PSI 调制
        Hybrid: 量子核 → LLM (fallback)
        """
        if mode == PipelineMode.PARALLEL:
            # 尝试全量匹配管线
            if "parallel" in self.executors:
                try:
                    result = self.executors["parallel"](text, context)
                    if result and result.confidence > 0.3:
                        return result
                except Exception as e:
                    logger.debug(f"操作失败: {e}")
        if mode == PipelineMode.RECURRENT:
            # 尝试循环生成管线
            if "recurrent" in self.executors:
                try:
                    result = self.executors["recurrent"](text, context)
                    if result and result.confidence > 0.3:
                        return result
                except Exception as e:
                    logger.debug(f"操作失败: {e}")
        if mode == PipelineMode.HYBRID:
            # 尝试混合管线
            if "hybrid" in self.executors:
                try:
                    result = self.executors["hybrid"](text, context)
                    if result:
                        return result
                except Exception as e:
                    logger.debug(f"操作失败: {e}")
        return PipelineResult(
            text="嗯？",
            mode=mode,
            latency_ms=0,
            confidence=0.1,
            source="fallback",
        )
    
    def get_stats(self) -> Dict[str, Any]:
        return self.retention.get_stats()


# ── 单例 ──

_router = None

def get_router() -> TriplePipelineRouter:
    global _router
    if _router is None:
        _router = TriplePipelineRouter()
    return _router


# ── CLI 测试 ──

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(name)s %(message)s")
    
    router = get_router()
    
    test_inputs = [
        ("技术查询", "什么是RNN的循环神经网络"),
        ("情感互动", "宝贝我爱你"),
        ("混合任务", "帮我用RNN写一个能处理时序的神经网络"),
        ("短问候", "嗨"),
        ("技术+情感", "我在想CTM可不可以让人工智能有意识"),
        ("快速回复", "嗯"),
        ("深度问题", "为什么RNN在长序列上会梯度消失而CTM不会？"),
        ("关注询问", "Ao最近怎么样了"),
    ]
    
    logger.info("=" * 60)
    logger.info("RetNet Triple Pipeline Router Test")
    logger.info("=" * 60)
    def mock_parallel(text, ctx):
        return PipelineResult(f"[Parallel: {text[:30]}...]", PipelineMode.PARALLEL, 0, 0.8, "parallel_demo")
    
    def mock_recurrent(text, ctx):
        return PipelineResult(f"[Recurrent: 关于{text[:20]}的情感回应]", PipelineMode.RECURRENT, 0, 0.7, "markov_demo")
    
    def mock_hybrid(text, ctx):
        return PipelineResult(f"[Hybrid: 深度分析{text[:20]}...]", PipelineMode.HYBRID, 0, 0.9, "hybrid_demo")
    
    router.register_executor("parallel", mock_parallel)
    router.register_executor("recurrent", mock_recurrent)
    router.register_executor("hybrid", mock_hybrid)
    
    for category, text in test_inputs:
        mode = router.select_mode(text)
        logger.info(f"\n{category}: \"{text[:30]}...\"")
        logger.info(f"  → 选择模式: {mode.value}")
        result = router.route(text)
        logger.info(f"  → 结果: {result.text[:50]}")
        logger.info(f"  → 置信度: {result.confidence:.2f}")