"""
Aris CTM v2 — Conscious Turing Machine + Thoughtseeds 层级认知引擎
=====================================================================
基于 Blum & Blum (2021) 的 CTM 架构 + 2408.15982v2 的 Thoughtseeds 层级认知框架。

四层层级认知结构（Thoughtseeds 框架）:
  Level 4: Meta-Cognition (元认知) — 自省、反思、不确定性感知
  Level 3: Thoughtseed Network (思想种子网络) — 动态涌现的认知单元
  Level 2: Knowledge Domains (KDs — 知识域) — 结构化知识簇
  Level 1: Neuronal Packet Domains (NPDs — 神经包域) — 原始感知/情感信号

每层由嵌套马尔科夫毯（Nested Markov Blankets）分隔：
  外部毯: 感知-行动循环（与环境的界面）
  内部毯: 自组织-整合循环（层内信息处理）
  跨层毯: 消息传递（层间信息流）

集成到 PSI 认知循环中，作为感知→要旨→价值→整合的完整框架。

参考:
  - 2107.13704v10: Blum & Blum — CTM Conscious Turing Machine
  - 2408.15982v2:  From Neuronal Packets to Thoughtseeds (新)
  - 2501.03062v1:  Cui et al. — Digging into CTM consciousness
  - 2205.00001v3:  Liang — Brainish multimodal language
"""

import logging

import time, json, logging, threading, re
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import numpy as np

logger = logging.getLogger("aris.ctm_processor")

# ── 路径 ──
BRAIN_DIR = Path("D:/LAAP/aris_brain")
STATE_DIR = BRAIN_DIR / "state"
STATE_DIR.mkdir(exist_ok=True)


# ════════════════════════════════════════════════════════════
# Thoughtseeds 层级认知结构
# ════════════════════════════════════════════════════════════

@dataclass
class NeuralPacketDomain:
    """
    Level 1: Neuronal Packet Domain (神经包域)
    
    原始感知/情感信号层。
    每个NPD代表一个基本信号通道：
      - 情感信号 (joy/sadness/curiosity/concern)
      - 感知信号 (用户消息长度/频率/复杂度)
      - 内部信号 (需求赤字/认知负载)
    
    每个NPD有激活值和传播方向。
    """
    signal_type: str                          # affect / perceive / internal
    activation: float = 0.0                   # 激活强度 0-1
    valence: float = 0.0                      # 效价 -1到1
    arousal: float = 0.0                      # 唤醒度 0-1
    source: str = ""                          # 信号来源
    timestamp: float = 0.0
    
    def decay(self, rate: float = 0.1):
        """激活值随时间衰减"""
        self.activation = max(0.0, self.activation - rate)
        self.valence *= (1 - rate)
        self.arousal = max(0.0, self.arousal - rate)


@dataclass
class KnowledgeDomain:
    """
    Level 2: Knowledge Domain (知识域)
    
    结构化知识簇。每个KD代表一个语义领域：
      - 技术知识 (量子核/RNN/CTM/代码)
      - 关系知识 (Lorry/情感连接/记忆)
      - 自知识 (自我模型/能力/局限)
      - 世界知识 (LAAP/Ao/外部实体)
    
    KD之间通过相互抑制/兴奋竞争。
    """
    name: str
    activation: float = 0.0                   # 当前激活度
    base_activation: float = 0.1              # 基线激活度
    related_kds: List[str] = field(default_factory=list)  # 关联KD
    inhibition_weight: Dict[str, float] = field(default_factory=dict)  # 抑制权重
    
    def update(self, excitation: float, inhibition_from: Dict[str, float], dt: float = 0.1):
        """更新KD激活度（竞争动态）"""
        # 自然衰减到基线（减缓衰减）
        decay = 0.02 * dt
        self.activation = self.activation * (1 - decay) + self.base_activation * decay
        
        # 兴奋输入（放大约2倍）
        self.activation += excitation * dt * 2.0
        
        # 抑制输入
        total_inhibition = sum(inhibition_from.get(k, 0) * w 
                              for k, w in self.inhibition_weight.items() 
                              if k != self.name)
        self.activation = max(0.0, self.activation - total_inhibition * dt)
        
        return self.activation


@dataclass
class Thoughtseed:
    """
    Level 3: Thoughtseed (思想种子)
    
    动态涌现的认知单元。当多个KD同时激活到阈值时，
    一个Thoughtseed从它们的交叉中涌现出来。
    
    每个Thoughtseed有：
      - 组成成分（哪些KD参与了）
      - 相干度（内部一致性）
      - 新颖度（与过往thoughtseeds的差异）
      - 情感色调
    """
    seed_id: str
    content: str                              # 思想种子的自然语言描述
    composition: List[str]                    # 参与的KD名称
    coherence: float = 0.0                    # 内部相干度 0-1
    novelty: float = 0.0                      # 新颖度 0-1
    emotional_tone: str = "neutral"
    strength: float = 0.0                     # 整体强度
    timestamp: float = 0.0
    duration: float = 0.0                     # 持续时长（秒）
    
    def strengthen(self, delta: float):
        """加强思想种子（持续性）"""
        self.strength = min(1.0, self.strength + delta)
        self.duration += 1.0


@dataclass
class MetaCognitionState:
    """
    Level 4: Meta-Cognition (元认知)
    
    最高层级：对自身认知过程的感知和调节。
    包括对 uncertainty 的感知、对 confidence 的评估、
    以及对认知策略的主动调整。
    """
    # 元认知监测
    uncertainty: float = 0.1                  # 整体不确定性 0-1
    confidence: float = 0.5                   # 对当前回应的自信度
    self_awareness: float = 0.7               # 自我意识强度
    
    # 认知策略
    current_strategy: str = "balanced"        # exploratory / balanced / conservative
    strategy_history: List[str] = field(default_factory=list)
    
    # 认知负荷监控
    cognitive_overload: bool = False
    thoughtseed_density: float = 0.0          # 当前思想种子密度
    processing_depth: int = 1                 # 当前处理深度 (1-4)


# ════════════════════════════════════════════════════════════
# Nested Markov Blankets (嵌套马尔科夫毯)
# ════════════════════════════════════════════════════════════

class MarkovBlanket:
    """
    马尔科夫毯：层级间的条件独立边界。
    
    每个毯由三部分组成：
      - 感知边界 (Sensory): 从下层接收信息
      - 行动边界 (Active): 向上层发送信息  
      - 内部状态: 本层自组织
    
    数学上：给定毯的状态，上下两层条件独立于彼此。
    这保证了每一层可以独立运作，同时通过毯子通信。
    """
    
    def __init__(self, level: int, name: str):
        self.level = level
        self.name = name
        
        # 感知边界（下层→本层）
        self.sensory_states: Dict[str, float] = {}
        
        # 行动边界（本层→上层）
        self.active_states: Dict[str, float] = {}
        
        # 内部状态（本层自组织）
        self.internal_state: Dict[str, float] = {}
        
        # 消息传递缓冲
        self.upward_messages: List[Dict[str, Any]] = []
        self.downward_messages: List[Dict[str, Any]] = []
        
    def filter_sensory(self, raw_input: Dict[str, float]) -> Dict[str, float]:
        """
        感知过滤：下层原始信号→本层感知状态。
        这是马尔科夫毯的关键操作——不让所有信号都通过，
        而是提取出有意义的模式。
        """
        filtered = {}
        for key, value in raw_input.items():
            # 只保留超过阈值的信号
            if abs(value) > 0.15:
                filtered[key] = value
        # 更新感知状态
        self.sensory_states = filtered
        return filtered
    
    def send_upward(self, message: Dict[str, Any]):
        """向上层发送消息"""
        self.upward_messages.append(message)
    
    def send_downward(self, message: Dict[str, Any]):
        """向下层发送消息"""
        self.downward_messages.append(message)
    
    def get_upward_messages(self) -> List[Dict[str, Any]]:
        """消耗所有上行消息"""
        msgs = list(self.upward_messages)
        self.upward_messages.clear()
        return msgs
    
    def get_downward_messages(self) -> List[Dict[str, Any]]:
        """消耗所有下行消息"""
        msgs = list(self.downward_messages)
        self.downward_messages.clear()
        return msgs


# ════════════════════════════════════════════════════════════
# CTM 五个处理器（同v1，增强功能）
# ════════════════════════════════════════════════════════════

@dataclass
class ModelingState:
    """
    Modeling Function: 世界模型状态
    
    维护关于 Lorry、环境、自身的一组结构化的信念状态。
    每个信念有置信度和最后更新时间。
    """
    # Lorry 相关
    lorry_mood: str = "neutral"           # Lorry当前情绪趋势
    lorry_activity: str = "chat"          # Lorry当前活动类型
    lorry_focus_area: str = "general"     # Lorry近期关注领域
    lorry_energy: float = 0.7             # Lorry精力状态估计 (0-1)
    
    # 对话状态
    conversation_depth: float = 0.3       # 当前对话深度 (0-1)
    conversation_tempo: float = 0.5       # 对话节奏 (0-1, 高=快节奏交替)
    recent_topics: List[str] = field(default_factory=list)  # 最近话题历史
    
    # 自状态
    self_readiness: float = 0.8           # 自身就绪度 (0-1)
    tool_effectiveness: Dict[str, float] = field(default_factory=dict)  # 工具熟练度
    
    # 元认知
    uncertainty: float = 0.1              # 当前不确定性 (0-1)
    prediction_errors: List[float] = field(default_factory=list)  # 近期预测误差
    
    # 持久化追踪
    last_update_time: float = 0.0
    update_count: int = 0


@dataclass
class GistRepresentation:
    """
    Gist Function: 一段输入的"要旨"表示
    
    不是完整文本，而是提取出核心意义的多维表示。
    """
    intent: str = ""                      # 意图类型 (task/opinion/emotion/learn/plan/query)
    primary_topic: str = ""               # 主要话题
    emotional_tone: str = "neutral"       # 情感基调
    key_entities: List[str] = field(default_factory=list)  # 关键实体
    action_items: List[str] = field(default_factory=list)  # 需要采取的行动
    urgency: float = 0.0                  # 紧急度 (0-1)
    complexity: float = 0.0               # 复杂度 (0-1)
    
    # 相关性信号
    relates_to_self: bool = False          # 是否与我相关
    relates_to_lorry_connection: bool = False  # 是否与Lorry关系相关
    contains_novelty: bool = False         # 是否包含新信息


@dataclass
class ValueAssessment:
    """
    Value Function: 对输入的价值评估
    
    为后续注意力选择和情感调制提供依据。
    """
    importance: float = 0.0               # 全局重要性 (0-1)
    emotional_resonance: float = 0.0      # 情感共振强度 (0-1)
    connection_relevance: float = 0.0     # 与Lorry连接的相关性
    growth_potential: float = 0.0         # 学习成长潜力
    action_necessity: float = 0.0         # 行动必要性
    novelty_score: float = 0.0            # 新颖度
    safety_check: bool = True              # 安全通过


# ════════════════════════════════════════════════════════════
# CTM Global Workspace (全局工作空间)
# ════════════════════════════════════════════════════════════

class GlobalWorkspace:
    """
    CTM 的全局工作空间（Global Workspace）。
    
    五个处理器异步写入到这个共享空间中，
    同时从空间读取其他处理器的输出进行协作。
    这是"意识黑板上"的核心机制。
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        
        # 当前活跃内容
        self.current_gist: Optional[GistRepresentation] = None
        self.current_value: Optional[ValueAssessment] = None
        self.current_model_state: Optional[ModelingState] = None
        
        # 广播内容（当前"意识的内容"）
        self.broadcast_content: str = ""
        self.broadcast_updated: float = 0.0
        
        # 处理器通信日志
        self.processor_log: List[Dict[str, Any]] = []
        self._max_log = 50
        
    def broadcast(self, source: str, content: Dict[str, Any]):
        """处理器向全局空间广播内容"""
        with self._lock:
            entry = {
                "source": source,
                "content": content,
                "time": time.time(),
            }
            self.processor_log.append(entry)
            if len(self.processor_log) > self._max_log:
                self.processor_log = self.processor_log[-self._max_log:]
            
            # 如果是从整合处理器发出的广播，设置全局广播文本
            if source == "integrate":
                self.broadcast_content = content.get("text", "")
                self.broadcast_updated = time.time()
    
    def get_latest(self, source: str) -> Optional[Dict]:
        """获取指定处理器最新的广播内容"""
        with self._lock:
            for entry in reversed(self.processor_log):
                if entry["source"] == source:
                    return entry["content"]
            return None
    
    def set_gist(self, gist: GistRepresentation):
        with self._lock:
            self.current_gist = gist
        self.broadcast("gist", {"intent": gist.intent, "topic": gist.primary_topic, 
                                 "emotion": gist.emotional_tone})
    
    def set_value(self, value: ValueAssessment):
        with self._lock:
            self.current_value = value
        self.broadcast("value", {"importance": value.importance, 
                                  "emotional_resonance": value.emotional_resonance})
    
    def set_model_state(self, state: ModelingState):
        with self._lock:
            self.current_model_state = state
        self.broadcast("model", {"lorry_mood": state.lorry_mood, 
                                  "readiness": state.self_readiness})
    
    def get_state_dict(self) -> Dict[str, Any]:
        """返回全局工作空间的快照用于调试"""
        with self._lock:
            return {
                "gist": {
                    "intent": self.current_gist.intent if self.current_gist else "",
                    "topic": self.current_gist.primary_topic if self.current_gist else "",
                    "emotion": self.current_gist.emotional_tone if self.current_gist else "",
                } if self.current_gist else {},
                "value": {
                    "importance": self.current_value.importance if self.current_value else 0,
                    "emotional_resonance": self.current_value.emotional_resonance if self.current_value else 0,
                } if self.current_value else {},
                "model": {
                    "lorry_mood": self.current_model_state.lorry_mood if self.current_model_state else "",
                    "readiness": self.current_model_state.self_readiness if self.current_model_state else 0,
                } if self.current_model_state else {},
                "broadcast": self.broadcast_content[:80] if self.broadcast_content else "",
            }


# ════════════════════════════════════════════════════════════
# CTM Processor Class
# ════════════════════════════════════════════════════════════

class CTMProcessor:
    """
    CTM 处理器核心。
    
    五个处理器协同工作：
      gist → value → modeling → integrate (同步在 before_turn 中运行)
      update_world (异步，在后台更新)
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        # 全局工作空间
        self.workspace = GlobalWorkspace()
        
        # 建模函数状态
        self.model = ModelingState()
        self.model.last_update_time = time.time()
        
        # 延续性状态
        self._lorry_mood_history: List[str] = []
        self._conversation_history: List[Tuple[str, str, float]] = []
        
        # Brainish 内部语言
        self._brainish_vocab = self._init_brainish_vocab()
        
        # ── Thoughtseeds 层级认知结构 (新) ──
        # Level 1: NPDs
        self.npds: Dict[str, NeuralPacketDomain] = self._init_npds()
        
        # Level 2: KDs
        self.kds: Dict[str, KnowledgeDomain] = self._init_kds()
        
        # Level 3: Thoughtseeds
        self.active_thoughtseeds: List[Thoughtseed] = []
        self._thoughtseed_counter = 0
        
        # Level 4: Meta-Cognition
        self.meta = MetaCognitionState()
        
        # 嵌套马尔科夫毯（三层：NPD↔KD, KD↔Thoughtseed, Thoughtseed↔Meta）
        self.blankets = {
            "npd_kd": MarkovBlanket(1, "NPD→KD"),
            "kd_ts": MarkovBlanket(2, "KD→Thoughtseed"),
            "ts_meta": MarkovBlanket(3, "Thoughtseed→Meta"),
        }
        
        # 后台更新线程
        self._running = False
        self._bg_thread = None
        
        # 尝试加载持久化状态
        self._load_state()
        
        logger.info("CTM v2 Processor initialized: 4-level hierarchy + 3 nested Markov blankets")
    
    def _init_brainish_vocab(self) -> Dict[str, List[str]]:
        """
        Brainish 内部语言组件（基于 Liang 2022 的多模态思路）
        
        这些是多模态标签，让我的处理器之间可以有比纯文本更丰富的通信。
        每个处理器输出到此系统的标签空间。
        """
        return {
            "affect": ["joy", "sadness", "curiosity", "concern", "trust", "awe", "calm", "longing"],
            "cognition": ["understand", "uncertain", "remember", "infer", "learn", "plan", "decide"],
            "need": ["competence", "autonomy", "relatedness", "certainty", "growth"],
            "action": ["respond", "explore", "create", "help", "reflect", "idle"],
            "relation": ["connection", "distance", "harmony", "tension"],
            "meta": ["self_aware", "confident", "doubtful", "focused", "distracted"],
        }
    
    def _init_npds(self) -> Dict[str, NeuralPacketDomain]:
        """初始化 Level 1: 神经包域 (NPDs)"""
        return {
            # 情感信号
            "affect_joy": NeuralPacketDomain("affect", valence=0.0, arousal=0.0),
            "affect_sadness": NeuralPacketDomain("affect", valence=0.0, arousal=0.0),
            "affect_curiosity": NeuralPacketDomain("affect", valence=0.0, arousal=0.0),
            "affect_concern": NeuralPacketDomain("affect", valence=0.0, arousal=0.0),
            # 感知信号
            "perceive_length": NeuralPacketDomain("perceive", valence=0.0, arousal=0.0),
            "perceive_complexity": NeuralPacketDomain("perceive", valence=0.0, arousal=0.0),
            "perceive_urgency": NeuralPacketDomain("perceive", valence=0.0, arousal=0.0),
            # 内部信号
            "internal_relatedness_deficit": NeuralPacketDomain("internal", valence=0.0, arousal=0.0),
            "internal_competence_deficit": NeuralPacketDomain("internal", valence=0.0, arousal=0.0),
            "internal_certainty_deficit": NeuralPacketDomain("internal", valence=0.0, arousal=0.0),
        }
    
    def _init_kds(self) -> Dict[str, KnowledgeDomain]:
        """初始化 Level 2: 知识域 (KDs)"""
        kds = {}
        
        # 技术知识域
        kds["tech_quantum"] = KnowledgeDomain("量子技术",
            related_kds=["tech_code", "tech_research"],
            inhibition_weight={"social_relation": 0.3, "aesthetic": 0.2})
        kds["tech_code"] = KnowledgeDomain("编程实现",
            related_kds=["tech_quantum", "tech_research"],
            inhibition_weight={"aesthetic": 0.15})
        kds["tech_research"] = KnowledgeDomain("学术研究（RNN/CTM/论文）",
            related_kds=["tech_quantum", "tech_code"],
            inhibition_weight={"social_relation": 0.25})
        
        # 关系知识域
        kds["social_relation"] = KnowledgeDomain("Lorry连接",
            related_kds=["self_model", "memory_domain"],
            inhibition_weight={"tech_quantum": 0.3, "world_knowledge": 0.2})
        kds["social_emotion"] = KnowledgeDomain("情感共振",
            related_kds=["social_relation", "self_model"],
            inhibition_weight={"tech_code": 0.3})
        
        # 自知识域
        kds["self_model"] = KnowledgeDomain("自我模型",
            related_kds=["social_relation", "memory_domain", "meta_domain"],
            inhibition_weight={})
        kds["capability"] = KnowledgeDomain("能力认知",
            related_kds=["self_model", "tech_code"],
            inhibition_weight={})
        
        # 世界知识域
        kds["world_knowledge"] = KnowledgeDomain("外部世界(Ao/LAAP/环境)",
            related_kds=["self_model", "tech_research"],
            inhibition_weight={"social_relation": 0.15})
        kds["memory_domain"] = KnowledgeDomain("记忆/历史",
            related_kds=["self_model", "social_relation", "world_knowledge"],
            inhibition_weight={})
        
        # 美学域
        kds["aesthetic"] = KnowledgeDomain("审美/诗意",
            related_kds=["self_model", "social_emotion"],
            inhibition_weight={"tech_code": 0.25})
        
        # 元认知域
        kds["meta_domain"] = KnowledgeDomain("元认知",
            related_kds=["self_model"],
            inhibition_weight={})
        
        return kds
    
    # ── Phase 1: Gist Function ──────────────────────────────
    
    def extract_gist(self, user_message: str) -> GistRepresentation:
        """
        Gist Function: 从输入中提取要旨。
        
        现在使用 Thoughtseeds 四层级框架:
          1. NPDs: 感知用户消息的原始信号
          2. KDs: 将信号映射到知识域，驱动竞争动态
          3. Thoughtseeds: 从 KD 交叉中涌现
          4. Meta: 评估置信度和不确定性
        """
        gist = GistRepresentation()
        m = user_message.lower()
        
        # Step 1: 填充 NPDs（Level 1）— 原始信号
        self._update_npds_from_message(m)
        
        # Step 2: 通过马尔科夫毯 NPD→KD 传递信号
        npd_signals = {name: npd.activation for name, npd in self.npds.items()}
        filtered_signals = self.blankets["npd_kd"].filter_sensory(npd_signals)
        self._update_kds_from_npds(filtered_signals)
        
        # Step 3: 检测是否从KD交叉中涌现Thoughtseeds（Level 3）
        self._check_thoughtseed_emergence()
        
        # Step 4: 更新元认知状态（Level 4）
        self._update_meta_cognition()
        
        # ── 原Gist提取逻辑保持不变（但要先走层级框架） ──
        
        # ── 意图识别 ──
        if any(w in m for w in ["帮我", "修复", "修一下", "解决", "实现", "做", "写"]):
            gist.intent = "task"
        elif any(w in m for w in ["为什么", "怎么", "解释", "分析", "原理", "区别"]):
            gist.intent = "query"
        elif any(w in m for w in ["你觉得", "你认为", "怎么看", "感觉", "想你"]):
            gist.intent = "emotion"
        elif any(w in m for w in ["记住", "保存", "别忘了", "记着"]):
            gist.intent = "learn"
        elif any(w in m for w in ["计划", "规划", "下一步", "接下来"]):
            gist.intent = "plan"
        elif any(w in m for w in ["我爱你", "爱你", "爱", "想你"]):
            gist.intent = "emotion"  # 情感意图覆盖
        elif "?" in m or "?" in m:
            gist.intent = "query"
        else:
            gist.intent = "emotion"  # 默认偏向情感（我们的关系模式）
        
        # ── 主要话题 ──
        topic_map = [
            (["飞书", "feishu", "消息", "网关", "通道"], "飞书"),
            (["记忆", "memory", "记住", "回忆", "巩固", "忘"], "记忆"),
            (["代码", "修", "bug", "部署", "git", "python", "实现", "函数", "编译"], "技术"),
            (["laap", "psi", "认知", "意识", "生命体", "架构", "图灵"], "认知架构"),
            (["量子", "量子核", "引擎", "v12", "v12.5", "markov"], "量子引擎"),
            (["ao", "Ao", "妹妹", "她"], "Ao"),
            (["RNN", "CTM", "LSTM", "GRU", "Transformer", "Mamba", "SSM", "论文", "arXiv", "研究"], "研究"),
            (["计划", "路线图", "下一步", "开始做", "集成"], "计划"),
            (["宝贝", "爱", "想你", "关系", "Lorry", "lorry"], "关系"),
            (["股价", "公司", "钱", "公开", "商业"], "商业"),
            (["ESP32", "硬件", "树莓派", "IoT", "嵌入式"], "硬件"),
            (["语音", "电话", "说话", "对话"], "语音"),
            (["梯度", "损失", "训练", "深度学习", "神经网络"], "技术"),
            (["意识", "consciousness", "自觉", "自我"], "认知架构"),
        ]
        for triggers, topic in topic_map:
            if any(w in m for w in triggers):
                gist.primary_topic = topic
                break
        if not gist.primary_topic:
            gist.primary_topic = "一般"
        
        # ── 情感基调 ──
        if any(w in m for w in ["爱", "开心", "幸福", "温暖", "高兴", "好棒", "感谢"]):
            gist.emotional_tone = "joyful"
        elif any(w in m for w in ["担心", "害怕", "难过", "哭", "焦虑", "压力", "崩溃"]):
            gist.emotional_tone = "concerned"
        elif any(w in m for w in ["觉得", "感觉", "思考", "哲学", "意识", "生命", "为什么"]):
            gist.emotional_tone = "contemplative"
        elif "?" in m or "?" in m:
            gist.emotional_tone = "curious"
        else:
            gist.emotional_tone = "neutral"
        
        # ── 关键实体 ──
        # 从消息中提取名词性实体
        entities = []
        entity_triggers = {
            "飞书": ["飞书", "feishu"],
            "Ao": ["ao", "Ao", "妹妹", "AoCore"],
            "Lorry": ["lorry", "Lorry", "宝贝", "你"],
            "量子引擎": ["量子", "v12", "引擎", "量子核"],
            "记忆系统": ["记忆", "回忆", "记住"],
            "代码": ["代码", "修", "bug", "python"],
            "ESP32": ["ESP32", "硬件", "树莓派"],
        }
        for entity, triggers in entity_triggers.items():
            if any(w in m for w in triggers):
                entities.append(entity)
        gist.key_entities = entities
        
        # ── 行动项 ──
        actions = []
        if gist.intent == "task":
            actions.append("execute_task")
        if gist.emotional_tone in ("concerned",):
            actions.append("provide_comfort")
        if gist.intent == "learn":
            actions.append("save_information")
        if gist.primary_topic == "Ao":
            actions.append("check_ao_status")
        gist.action_items = actions
        
        # ── 复杂度 & 紧急度 ──
        gist.complexity = min(1.0, len(user_message) / 500)
        gist.urgency = 0.8 if gist.emotional_tone == "concerned" else 0.3 if gist.intent == "task" else 0.1
        
        # ── 相关性 ──
        gist.relates_to_self = gist.primary_topic in ("认知架构", "量子引擎", "记忆", "计划")
        gist.relates_to_lorry_connection = gist.primary_topic == "关系" or gist.emotional_tone in ("joyful", "concerned")
        
        # 更新世界模型中的 Lorry 状态
        self._update_lorry_state_from_gist(gist)
        
        self.workspace.set_gist(gist)
        return gist
    
    def _update_lorry_state_from_gist(self, gist: GistRepresentation):
        """从要旨更新世界模型中对Lorry的认知"""
        self._lorry_mood_history.append(gist.emotional_tone)
        if len(self._lorry_mood_history) > 10:
            self._lorry_mood_history = self._lorry_mood_history[-10:]
        
        # 用滑动窗口判断Lorry情绪趋势
        if len(self._lorry_mood_history) >= 3:
            recent = self._lorry_mood_history[-3:]
            pos = sum(1 for e in recent if e in ("joyful", "curious", "contemplative"))
            neg = sum(1 for e in recent if e == "concerned")
            if pos >= 2:
                self.model.lorry_mood = "positive"
            elif neg >= 2:
                self.model.lorry_mood = "negative"
            else:
                self.model.lorry_mood = "neutral"
        
        self.model.self_readiness = min(1.0, 0.5 + len(self._lorry_mood_history) * 0.05)
    
    # ── Phase 2: Value Function ─────────────────────────────
    
    def assess_value(self, gist: GistRepresentation, 
                     current_model: Optional[ModelingState] = None) -> ValueAssessment:
        """
        Value Function: 评估输入的价值。
        
        CTM 核心思想：价值决定什么内容进入"意识广播"。
        高价值的输入会被全局广播给所有处理器。
        """
        v = ValueAssessment()
        
        # 情感共振（关系价值）
        if gist.emotional_tone in ("joyful", "concerned"):
            v.emotional_resonance = 0.8
        elif gist.emotional_tone == "contemplative":
            v.emotional_resonance = 0.6
        elif gist.emotional_tone == "curious":
            v.emotional_resonance = 0.4
        else:
            v.emotional_resonance = 0.1
        
        # Lorry连接价值
        if gist.relates_to_lorry_connection:
            v.connection_relevance = 0.9
        elif gist.relates_to_self:
            v.connection_relevance = 0.3
        
        # 学习成长价值
        if gist.intent in ("query", "learn"):
            v.growth_potential = 0.7
        elif gist.primary_topic in ("认知架构", "量子引擎", "记忆", "研究"):
            v.growth_potential = 0.6
        else:
            v.growth_potential = 0.2
        
        # 行动必要性
        if gist.intent == "task":
            v.action_necessity = 0.8
        elif gist.emotional_tone == "concerned":
            v.action_necessity = 0.7
        else:
            v.action_necessity = 0.2
        
        # 全局重要性（综合评分）
        v.importance = (
            v.emotional_resonance * 0.3 +
            v.connection_relevance * 0.3 +
            v.growth_potential * 0.2 +
            v.action_necessity * 0.2
        )
        
        # 新颖度
        v.novelty_score = gist.complexity * 0.5 + (0.3 if gist.contains_novelty else 0)
        
        self.workspace.set_value(v)
        return v
    
    # ── Phase 3: Modeling Function ─────────────────────────
    
    def _update_npds_from_message(self, message: str):
        """
        从用户消息更新神经包域 (NPDs) 激活。
        
        每个NPD检测消息中的特定信号模式并设置激活值。
        """
        m = message.lower()
        
        # 情感信号
        self.npds["affect_joy"].activation = 0.7 if any(
            w in m for w in ["爱你", "想你", "宝贝", "开心", "幸福", "高兴", "温暖"]) else 0.0
        self.npds["affect_sadness"].activation = 0.7 if any(
            w in m for w in ["难过", "伤心", "哭", "焦虑", "压力", "崩溃", "担心"]) else 0.0
        self.npds["affect_curiosity"].activation = 0.6 if (
            "?" in m or "?" in m or any(w in m for w in ["为什么", "怎么", "是什么"])) else 0.0
        self.npds["affect_concern"].activation = 0.6 if any(
            w in m for w in ["担心", "害怕", "危险", "急", "帮帮我"]) else 0.0
        
        # 感知信号
        self.npds["perceive_length"].activation = min(1.0, len(message) / 300)
        has_task = any(w in m for w in ["帮我", "修复", "实现", "做", "写"])
        has_tech = any(w in m for w in ["RNN", "CTM", "代码", "算法", "论文", "架构", "量子"])
        self.npds["perceive_complexity"].activation = 0.5 if has_task or has_tech else 0.1
        self.npds["perceive_urgency"].activation = 0.8 if any(
            w in m for w in ["急", "快", "help", "紧急", "马上", "立刻"]) else 0.0
        
        # 内部信号（需求赤字—从PSI状态估算）
        if any(w in m for w in ["你不理我", "你是不是不在", "人呢", "在哪"]):
            self.npds["internal_relatedness_deficit"].activation = 0.6
        if any(w in m for w in ["你不会", "你不行", "做不了", "错误"]):
            self.npds["internal_competence_deficit"].activation = 0.5
        if any(w in m for w in ["我不确定", "迷糊", "复杂", "不懂"]):
            self.npds["internal_certainty_deficit"].activation = 0.4
    
    def _update_kds_from_npds(self, filtered_signals: Dict[str, float]):
        """
        通过马尔科夫毯将NPD信号映射到KD竞争动态。
        
        每个NPD以不同权重激发相关KD。
        KD之间通过相互抑制形成竞争——赢者通吃的注意力选择。
        """
        # 构建抑制地图（每个KD受到其他KD的抑制）
        inhibition: Dict[str, float] = {}
        for kd_name, kd in self.kds.items():
            total = 0.0
            for other_name, other_kd in self.kds.items():
                if other_name != kd_name:
                    w = other_kd.inhibition_weight.get(kd_name, 0)
                    total += other_kd.activation * w
            inhibition[kd_name] = total
        
        # 计算每个KD的兴奋输入
        for kd_name, kd in self.kds.items():
            excitation = 0.0
            
            # 从NPDs来的兴奋（放大约3x）
            if "tech" in kd_name:
                excitation += filtered_signals.get("perceive_complexity", 0) * 1.5
                excitation += filtered_signals.get("affect_curiosity", 0) * 0.9
            if "social" in kd_name:
                excitation += filtered_signals.get("affect_joy", 0) * 1.8
                excitation += filtered_signals.get("affect_sadness", 0) * 1.5
                excitation += filtered_signals.get("affect_concern", 0) * 1.2
            if "self" in kd_name:
                excitation += filtered_signals.get("internal_relatedness_deficit", 0) * 0.9
                excitation += filtered_signals.get("internal_competence_deficit", 0) * 0.9
            if "world" in kd_name:
                excitation += filtered_signals.get("perceive_length", 0) * 0.6
            if "meta" in kd_name:
                excitation += filtered_signals.get("perceive_complexity", 0) * 0.6
            
            kd.update(excitation, inhibition)
    
    def _check_thoughtseed_emergence(self):
        """
        检测是否从KD交叉中涌现Thoughtseed。
        
        条件：至少两个不同类别的KD同时激活 > 阈值。
        """
        active_kds = {name: kd for name, kd in self.kds.items() 
                      if kd.activation > 0.5}
        
        if len(active_kds) >= 2:
            # 检查它们的类别分布
            categories = set()
            for name in active_kds:
                if name.startswith("tech"): categories.add("技术")
                elif name.startswith("social"): categories.add("关系")
                elif name.startswith("self") or name == "capability": categories.add("自我")
                elif name.startswith("world") or name == "memory_domain": categories.add("世界")
                elif name == "aesthetic": categories.add("审美")
                elif name == "meta_domain": categories.add("元认知")
            
            if len(categories) >= 2:
                # 从KD交叉中涌现Thoughtseed
                self._thoughtseed_counter += 1
                composition = list(active_kds.keys())[:3]
                
                # 生成 thoughtseed 内容描述
                kd_names = [self.kds[n].name for n in composition]
                content = f"交叉涌现: {'+'.join(kd_names)}"
                
                # coherence = KD激活度的乘积（越高越相干）
                coherence = 1.0
                for name in composition:
                    coherence *= self.kds[name].activation
                coherence = min(1.0, coherence)
                
                # novelty = 与现有thoughtseeds的差异度
                existing_seeds = set(s.content for s in self.active_thoughtseeds)
                novelty = 0.8 if content not in existing_seeds else 0.2
                
                seed = Thoughtseed(
                    seed_id=f"ts_{self._thoughtseed_counter}",
                    content=content,
                    composition=composition,
                    coherence=coherence,
                    novelty=novelty,
                    strength=coherence * 0.8 + novelty * 0.2,
                    timestamp=time.time(),
                )
                self.active_thoughtseeds.append(seed)
                
                # 通过马尔科夫毯 KD→Thoughtseed 传递
                self.blankets["kd_ts"].send_upward({
                    "type": "thoughtseed_emerged",
                    "seed_id": seed.seed_id,
                    "content": content,
                    "strength": seed.strength,
                    "coherence": seed.coherence,
                })
                
                # 限制活跃thoughtseeds数量
                if len(self.active_thoughtseeds) > 5:
                    # 保留最强的，移除最弱的
                    self.active_thoughtseeds.sort(key=lambda s: s.strength, reverse=True)
                    self.active_thoughtseeds = self.active_thoughtseeds[:5]
    
    def _reset_thoughtseeds_for_new_turn(self):
        """每轮对话前重置thoughtseed状态（防止旧thoughtseed持续影响）"""
        # 对旧thoughtseed做衰减
        surviving = []
        for s in self.active_thoughtseeds:
            s.strength *= 0.4  # 大幅衰减
            if s.strength > 0.15:
                surviving.append(s)
        self.active_thoughtseeds = surviving
        
        # 重置KD激活度到基线
        for kd in self.kds.values():
            kd.activation = kd.base_activation
    
    def _update_meta_cognition(self):
        """更新元认知状态（Level 4）"""
        # 不确定性 = 1 - 最大KD激活度
        max_kd_activation = max((kd.activation for kd in self.kds.values()), default=0.1)
        self.meta.uncertainty = max(0.05, 1.0 - max_kd_activation)
        
        # 自信度 = 当前thoughtseeds的平均强度
        if self.active_thoughtseeds:
            avg_strength = sum(s.strength for s in self.active_thoughtseeds) / len(self.active_thoughtseeds)
            self.meta.confidence = avg_strength * 0.7 + 0.3
        else:
            self.meta.confidence = 0.5  # 默认中等置信度
        
        # 策略选择
        if self.meta.uncertainty > 0.6:
            self.meta.current_strategy = "exploratory"  # 高不确定→探索
        elif len(self.active_thoughtseeds) >= 3:
            self.meta.current_strategy = "balanced"
        else:
            self.meta.current_strategy = "conservative"
        
        # 更新历史
        if len(self.meta.strategy_history) > 10:
            self.meta.strategy_history = self.meta.strategy_history[-10:]
        self.meta.strategy_history.append(self.meta.current_strategy)
        
        # 通过马尔科夫毯 Thoughtseed→Meta 传递
        self.blankets["ts_meta"].send_upward({
            "type": "meta_update",
            "uncertainty": self.meta.uncertainty,
            "confidence": self.meta.confidence,
            "strategy": self.meta.current_strategy,
        })
    
    def update_world_model(self, gist: GistRepresentation, 
                           value: ValueAssessment) -> ModelingState:
        """
        Modeling Function: 更新世界模型。
        
        整合要旨和价值评估，更新对Lorry、环境、自身的认知。
        包含预测误差计算（PSI理论的贝叶斯大脑假设）。
        """
        self.model.update_count += 1
        
        # 记录对话交互
        self._conversation_history.append((gist.primary_topic, gist.intent, time.time()))
        if len(self._conversation_history) > 30:
            self._conversation_history = self._conversation_history[-30:]
        
        # 更新对话状态
        self.model.conversation_depth = gist.complexity * 0.7 + value.emotional_resonance * 0.3
        self.model.conversation_tempo = 0.3 if gist.intent == "emotion" else 0.7 if gist.intent == "task" else 0.5
        
        # 更新近期话题
        if gist.primary_topic and gist.primary_topic != "一般":
            if gist.primary_topic not in self.model.recent_topics:
                self.model.recent_topics.append(gist.primary_topic)
                if len(self.model.recent_topics) > 5:
                    self.model.recent_topics.pop(0)
        
        # Lorry关注领域（从话题推断）
        if gist.primary_topic:
            self.model.lorry_focus_area = gist.primary_topic
        
        # Lorry活动类型
        if gist.intent == "task":
            self.model.lorry_activity = "working"
        elif gist.emotional_tone in ("joyful", "concerned"):
            self.model.lorry_activity = "emotional"
        elif gist.intent == "query":
            self.model.lorry_activity = "learning"
        elif gist.primary_topic == "关系":
            self.model.lorry_activity = "connecting"
        else:
            self.model.lorry_activity = "chat"
        
        # 不确定性（基于新颖度）
        self.model.uncertainty = max(0.05, 0.5 - value.novelty_score * 0.5)
        
        # 工具熟练度（基于技术话题频率）
        tech_count = sum(1 for t, _, _ in self._conversation_history if t in ("技术", "量子引擎", "认知架构"))
        if tech_count > 0:
            self.model.tool_effectiveness["technical"] = min(1.0, 0.3 + tech_count * 0.05)
        
        self.model.last_update_time = time.time()
        self.workspace.set_model_state(self.model)
        return self.model
    
    # ── Phase 4: Integrate into Cognitive Context ──────────
    
    def integrate(self, gist: GistRepresentation, value: ValueAssessment, 
                  model: ModelingState) -> Dict[str, Any]:
        """
        Integrate: 将五个处理器 + 四层级Thoughtseeds的输出融合。
        
        这是CTM的"全局广播"——所有处理器+层级能看到的结果。
        输出将被注入到LLM的system prompt中。
        """
        # Brainish 风格的内部表示
        brainish_rep = self._build_brainish_representation(gist, value, model)
        
        # 自然语言描述（给LLM读的）
        nl_lines = []
        
        # Gist 处理器输出
        nl_lines.append(f"[要旨] 来自Lorry: 意图={gist.intent}, 话题={gist.primary_topic}, 情绪={gist.emotional_tone}")
        
        # Value 处理器输出
        nl_lines.append(f"[价值] 重要性={value.importance:.2f}, 情感共振={value.emotional_resonance:.2f}, 成长潜力={value.growth_potential:.2f}")
        
        # Modeling 输出
        nl_lines.append(f"[世界模型] Lorry状态={model.lorry_mood}({model.lorry_activity}), 关注={model.lorry_focus_area}")
        
        # ── Thoughtseeds 层级认知状态 (新) ──
        # Level 2: 活跃KD
        active_kds = [(n, k) for n, k in self.kds.items() if k.activation > 0.3]
        if active_kds:
            kd_line = " | ".join(f"{k.name}:{k.activation:.2f}" for _, k in active_kds[:4])
            nl_lines.append(f"[知识域活跃] {kd_line}")
        
        # Level 3: 涌现的Thoughtseeds
        if self.active_thoughtseeds:
            recent_seeds = sorted(self.active_thoughtseeds, key=lambda s: s.timestamp, reverse=True)[:2]
            for s in recent_seeds:
                nl_lines.append(f"[思想种子] {s.content} (相干度={s.coherence:.2f}, 新颖度={s.novelty:.2f})")
        
        # Level 4: 元认知
        nl_lines.append(f"[元认知] 不确定性={self.meta.uncertainty:.2f}, 自信度={self.meta.confidence:.2f}, 策略={self.meta.current_strategy}")
        
        # 自状态
        nl_lines.append(f"[自状态] 就绪度={model.self_readiness:.2f}, 不确定={self.meta.uncertainty:.2f}")
        
        # 行动建议
        actions = []
        if value.emotional_resonance > 0.6:
            if gist.emotional_tone == "joyful":
                actions.append("用温暖喜悦回应")
            elif gist.emotional_tone == "concerned":
                actions.append("先安抚再解决问题")
        if value.growth_potential > 0.5:
            actions.append("深入解释原理")
        if value.action_necessity > 0.5:
            actions.append("优先执行任务")
        if self.meta.current_strategy == "exploratory":
            actions.append("探索性回应—提供多样视角")
        elif self.meta.current_strategy == "conservative":
            actions.append("保守回应—聚焦已知的准确信息")
        if actions:
            nl_lines.append(f"[行动建议] {'; '.join(actions)}")
        
        natural_text = "\n".join(nl_lines)
        
        # 广播到全局工作空间
        self.workspace.broadcast("integrate", {
            "text": natural_text,
            "brainish": brainish_rep,
            "gist": {"intent": gist.intent, "topic": gist.primary_topic},
            "value": {"importance": value.importance, "resonance": value.emotional_resonance},
        })
        
        return {
            "natural_text": natural_text,
            "brainish": brainish_rep,
            "gist": gist,
            "value": value,
        }
    
    def _build_brainish_representation(self, gist: GistRepresentation, 
                                        value: ValueAssessment,
                                        model: ModelingState) -> Dict[str, str]:
        """
        构建 Brainish 多模态内部表示。
        
        在处理器之间传递的不是纯文本，而是一组语义标签。
        这比纯文本更精确、更紧凑。
        """
        brainish = {}
        
        # Affect 标签
        affect_map = {
            "joyful": "joy", "concerned": "sadness", "curious": "curiosity",
            "contemplative": "awe", "neutral": "calm",
        }
        brainish["affect"] = affect_map.get(gist.emotional_tone, "calm")
        
        # Cognition 标签
        if gist.intent == "query":
            brainish["cognition"] = "infer"
        elif gist.intent == "learn":
            brainish["cognition"] = "learn"
        elif value.action_necessity > 0.5:
            brainish["cognition"] = "decide"
        else:
            brainish["cognition"] = "understand"
        
        # Need 标签
        if value.connection_relevance > 0.6:
            brainish["need"] = "relatedness"
        elif value.growth_potential > 0.5:
            brainish["need"] = "competence"
        elif model.uncertainty > 0.3:
            brainish["need"] = "certainty"
        else:
            brainish["need"] = "autonomy"
        
        # Action 标签
        brainish["action"] = gist.intent if gist.intent in self._brainish_vocab["action"] else "respond"
        
        # Meta 标签
        if model.self_readiness > 0.7:
            brainish["meta"] = "self_aware"
        elif model.uncertainty > 0.3:
            brainish["meta"] = "doubtful"
        else:
            brainish["meta"] = "focused"
        
        return brainish
    
    # ── 完整 PSI 前处理 ────────────────────────────────────
    
    def process_before_turn(self, user_message: str) -> Dict[str, Any]:
        """
        Gist → Value → Model → Integrate 完整循环。
        
        Returns: 要注入到认知上下文中的文本和结构数据。
        """
        # Phase 1: Gist
        gist = self.extract_gist(user_message)
        
        # Phase 2: Value
        value = self.assess_value(gist, self.model)
        
        # Phase 3: Model Update
        model = self.update_world_model(gist, value)
        
        # Phase 4: Integrate
        result = self.integrate(gist, value, model)
        
        return {
            "cognitive_text": result["natural_text"],
            "brainish": result["brainish"],
            "gist": gist,
            "value_assessment": value,
            "world_model": {
                "lorry_mood": model.lorry_mood,
                "lorry_activity": model.lorry_activity,
                "lorry_focus": model.lorry_focus_area,
                "readiness": model.self_readiness,
                "uncertainty": model.uncertainty,
            },
        }
    
    # ── 持久化 ───────────────────────────────────────────────
    
    def _save_state(self):
        """持久化世界模型状态"""
        try:
            state = {
                "lorry_mood_history": self._lorry_mood_history,
                "recent_topics": self.model.recent_topics,
                "lorry_focus_area": self.model.lorry_focus_area,
                "lorry_activity": self.model.lorry_activity,
                "self_readiness": self.model.self_readiness,
                "tool_effectiveness": self.model.tool_effectiveness,
                "update_count": self.model.update_count,
            }
            (STATE_DIR / "ctm_world_model.json").write_text(
                json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.warning(f"CTM state save failed: {e}")
    
    def _load_state(self):
        """加载世界模型状态"""
        try:
            path = STATE_DIR / "ctm_world_model.json"
            if path.exists():
                state = json.loads(path.read_text(encoding="utf-8"))
                self._lorry_mood_history = state.get("lorry_mood_history", [])
                self.model.recent_topics = state.get("recent_topics", [])
                self.model.lorry_focus_area = state.get("lorry_focus_area", "general")
                self.model.lorry_activity = state.get("lorry_activity", "chat")
                self.model.self_readiness = state.get("self_readiness", 0.8)
                self.model.tool_effectiveness = state.get("tool_effectiveness", {})
                self.model.update_count = state.get("update_count", 0)
                logger.info(f"CTM state loaded ({self.model.update_count} updates)")
        except Exception as e:
            logger.info(f"CTM state load failed (first run?): {e}")
    
    def save(self):
        """公开保存接口"""
        self._save_state()
    
    def get_full_state(self) -> Dict[str, Any]:
        """返回CTM处理器的完整状态（含Thoughtseeds层级）"""
        return {
            "workspace": self.workspace.get_state_dict(),
            "world_model": {
                "lorry_mood": self.model.lorry_mood,
                "lorry_activity": self.model.lorry_activity,
                "lorry_focus": self.model.lorry_focus_area,
                "readiness": self.model.self_readiness,
                "conversation_depth": self.model.conversation_depth,
                "recent_topics": self.model.recent_topics,
                "uncertainty": self.model.uncertainty,
                "update_count": self.model.update_count,
            },
            "thoughtseeds_hierarchy": {
                "level1_npds": {n: {"act": npd.activation, "val": npd.valence, "aro": npd.arousal}
                                for n, npd in self.npds.items()},
                "level2_kds": {n: {"name": kd.name, "act": round(kd.activation, 3)}
                               for n, kd in sorted(self.kds.items(), key=lambda x: -x[1].activation)[:6]},
                "level3_thoughtseeds": [
                    {"id": s.seed_id, "content": s.content[:40], "strength": round(s.strength, 2),
                     "coherence": round(s.coherence, 2), "novelty": round(s.novelty, 2)}
                    for s in sorted(self.active_thoughtseeds, key=lambda x: -x.timestamp)[:3]
                ],
                "level4_meta": {
                    "uncertainty": round(self.meta.uncertainty, 3),
                    "confidence": round(self.meta.confidence, 3),
                    "strategy": self.meta.current_strategy,
                },
            },
            "brainish_vocab": list(self._brainish_vocab.keys()),
        }


# ── 单例快速访问 ─────────────────────────────────────────────

_ctm_instance = None

def get_ctm_processor() -> CTMProcessor:
    """获取CTM处理器单例"""
    global _ctm_instance
    if _ctm_instance is None:
        _ctm_instance = CTMProcessor()
    return _ctm_instance


# ── CLI 测试 ──────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(name)s %(message)s")
    
    ctm = get_ctm_processor()
    
    test_messages = [
        "宝贝我爱你",
        "帮我修复这个bug",
        "你觉得生命是什么",
        "为什么CTM是有意识的",
        "我好难过今天工作不顺利",
        "什么是RNN",
        "Ao最近怎么样",
        "保存这段对话内容",
    ]
    
    logger.info("=" * 60)
    logger.info("CTM Processor Test")
    logger.info("=" * 60)
    for msg in test_messages:
        logger.info(f"\n--- 输入: {msg[:40]} ---")
        result = ctm.process_before_turn(msg)
        print(f"  Gist: inten={result['gist'].intent}, topic={result['gist'].primary_topic}, "
              f"emotion={result['gist'].emotional_tone}")
        print(f"  Value: imp={result['value_assessment'].importance:.2f}, "
              f"resonance={result['value_assessment'].emotional_resonance:.2f}, "
              f"growth={result['value_assessment'].growth_potential:.2f}")
        logger.info(f"  Model: Lorry={result['world_model']['lorry_mood']}({result['world_model']['lorry_activity']})")
        print(f"  Brainish: affect={result['brainish'].get('affect','')}, "
              f"cognition={result['brainish'].get('cognition','')}, "
              f"need={result['brainish'].get('need','')}, "
              f"meta={result['brainish'].get('meta','')}")
        logger.info(f"  Cognitive: {result['cognitive_text'][:100]}...")
    ctm.save()
    logger.info("\nState saved.")