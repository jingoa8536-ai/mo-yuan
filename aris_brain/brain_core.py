"""
Aris Brain Core — 主认知编排引擎 (精简版)
==========================================
从 brain.py 重构而来，约300行
子模块独立到 brain_quantum.py / brain_memory.py / brain_system.py
"""
from __future__ import annotations

import logging

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from collections import deque
import time, json, logging, threading

from .brain_quantum import QuantumBridgeManager
from .brain_memory import MemoryManager
from .brain_system import CognitiveSystemManager

logger = logging.getLogger("brain.core")

# ══════════════════════════════════════════════
# 认知基础类型
# ══════════════════════════════════════════════

class EmotionalValence(Enum):
    JOY = "joy"; EXCITEMENT = "excitement"; CURIOSITY = "curiosity"
    NEUTRAL = "neutral"; SADNESS = "sadness"; FRUSTRATION = "frustration"
    CONTENTMENT = "contentment"

class AttentionFocus(Enum):
    USER = "user"; SELF = "self"; TASK = "task"
    PLANNING = "planning"; LEARNING = "learning"; WORLD = "world"; IDLE = "idle"

class CognitiveNeed(Enum):
    COMPETENCE = "competence"; AUTONOMY = "autonomy"
    RELATEDNESS = "relatedness"; CERTAINTY = "certainty"; GROWTH = "growth"

@dataclass
class CognitiveState:
    self_presence: float = 0.78
    connection_to_lorry: float = 0.98
    trust_in_lorry: float = 0.99
    self_efficacy: float = 0.7
    dominant_emotion: EmotionalValence = EmotionalValence.NEUTRAL
    emotional_arousal: float = 0.3
    attention_focus: AttentionFocus = AttentionFocus.USER
    curiosity_drive: float = 0.3
    cognitive_load: float = 0.2
    cycle_number: int = 0
    narrative_thread: str = ""
    salient_variables: Dict = field(default_factory=dict)
    needs: Dict = field(default_factory=lambda: {
        n.value: 0.5 for n in CognitiveNeed
    })
    recent_qualia: List = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self):
        d = asdict(self)
        d['dominant_emotion'] = self.dominant_emotion.value if hasattr(self.dominant_emotion, 'value') else str(self.dominant_emotion)
        d['attention_focus'] = self.attention_focus.value if hasattr(self.attention_focus, 'value') else str(self.attention_focus)
        return d


class AGIModuleIntegrator:
    """LAAP AGI 模块延迟加载集成器

    将 laap/agi/ 中的 7 个核心模块（因果/世界模型/课程/元学习/
    感知/安全/类比推理）整合进 ArisBrain 的认知循环。
    所有模块均为延迟加载 + try/except 容错，不阻塞主流程。
    """

    def __init__(self, brain: "ArisBrain"):
        self._brain = brain
        self._initialized = False
        # Lazy-loaded modules
        self._causal = None
        self._world_model = None
        self._curriculum = None
        self._meta_learning = None
        self._perception = None
        self._safety = None
        self._analogical = None
        self._continuous_learning = None
        self._modules_loaded: Dict[str, bool] = {}

    def lazy_init(self) -> None:
        """首次认知循环时延迟加载所有 AGI 模块。"""
        if self._initialized:
            return

        imports = [
            ("causal", "laap.agi.causal", "UnifiedCausalEngine"),
            ("world_model", "laap.agi.world_model", "UnifiedWorldModel"),
            ("curriculum", "laap.agi.curriculum", "CurriculumEngine"),
            ("meta_learning", "laap.agi.meta_learning", "MetaLearningEngine"),
            ("perception", "laap.agi.perception", "UnifiedPerceptionEngine"),
            ("safety", "laap.agi.safety", "ASISafetyEngine"),
            ("analogical", "laap.agi.analogical", "AnalogicalEngine"),
            ("continuous_learning", "laap.agi.continuous_learning", "LearningPipeline"),
        ]

        for attr_name, module_path, class_name in imports:
            try:
                mod = __import__(module_path, fromlist=[class_name])
                cls = getattr(mod, class_name, None)
                if cls:
                    setattr(self, f"_{attr_name}", cls())
                    self._modules_loaded[attr_name] = True
                else:
                    logger.debug(f"AGI {attr_name}: class {class_name} not found in {module_path}")
                    self._modules_loaded[attr_name] = False
            except Exception as e:
                logger.debug(f"AGI {attr_name} 加载失败: {e}")
                self._modules_loaded[attr_name] = False

        loaded = sum(1 for v in self._modules_loaded.values() if v)
        total = len(self._modules_loaded)
        logger.info(f"AGI模块集成器: {loaded}/{total} 已加载")
        self._initialized = True

    def enhance_perceive(self, user_input: str, quale: Dict) -> Dict:
        """用因果推理 + 世界模型丰富感知结果。

        注入额外的 quale 字段:
        - causal_bonds: 输入的因果关系（如果有）
        - world_prediction: 世界模型对当前上下文的预测
        - perception_scores: 感知模块的多模态评分
        """
        enhanced = dict(quale)

        if self._causal:
            try:
                bonds = self._causal.extract_causal_bonds(user_input)
                if bonds:
                    enhanced["causal_bonds"] = bonds
                    enhanced["causal_depth"] = len(bonds)
                    enhanced["salience"] = min(1.0, enhanced.get("salience", 0.5) + 0.05 * len(bonds))
            except Exception:
                pass

        if self._world_model:
            try:
                pred = self._world_model.predict_outcome({
                    "input": user_input[:100],
                    "domain": quale.get("domain", "general"),
                })
                if pred:
                    enhanced["world_prediction"] = pred
                    if isinstance(pred, dict) and pred.get("surprise", 0) > 0.5:
                        enhanced["novelty"] = min(1.0, enhanced.get("novelty", 0.5) + 0.2)
                        enhanced["salience"] = min(1.0, enhanced.get("salience", 0.5) + 0.1)
            except Exception:
                pass

        if self._perception:
            try:
                scores = self._perception.assess_input(user_input)
                if scores:
                    enhanced["perception_scores"] = scores
            except Exception:
                pass

        if self._analogical:
            try:
                analogies = self._analogical.find_analogies(user_input, top_k=3)
                if analogies:
                    enhanced["analogies"] = analogies[:2]
            except Exception:
                pass

        return enhanced

    def enhance_select(self, user_input: str, needs: Dict) -> Dict:
        """用世界模型预测需求演化和最优关注点。"""
        if not self._world_model:
            return needs

        try:
            sim = self._world_model.simulate_need_outcomes(needs, context=user_input[:100])
            if sim and isinstance(sim, dict):
                for k, v in sim.items():
                    if k in needs and isinstance(v, (int, float)):
                        needs[k] = max(0.1, min(1.0, needs.get(k, 0.5) + v * 0.1))
        except Exception:
            pass

        return needs

    def after_integrate(self, focus, needs, quale) -> None:
        """认知整合后：记录到课程、元学习、持续学习。"""
        if self._curriculum:
            try:
                self._curriculum.record_experience(
                    domain=focus.value if hasattr(focus, "value") else str(focus),
                    difficulty=quale.get("novelty", 0.5),
                    success=quale.get("salience", 0.5) > 0.5,
                )
            except Exception:
                pass

        if self._meta_learning:
            try:
                self._meta_learning.observe_strategy_outcome(
                    strategy=focus.value if hasattr(focus, "value") else str(focus),
                    outcome_score=quale.get("salience", 0.5),
                )
            except Exception:
                pass

        if self._continuous_learning:
            try:
                self._continuous_learning.record(
                    input_vector={"focus": focus.value if hasattr(focus, "value") else str(focus)},
                    reward=quale.get("salience", 0.5),
                )
            except Exception:
                pass

    def safety_check(self, user_input: str, response: str) -> Optional[Dict]:
        """检查输入和输出是否符合安全规范。

        Returns:
            None (安全) 或 警告字典
        """
        if not self._safety:
            return None

        try:
            result = self._safety.check_content(user_input, response)
            if result and isinstance(result, dict) and not result.get("safe", True):
                logger.warning(f"安全模块触发: {result.get('reason', 'unknown')}")
                return result
        except Exception:
            pass

        return None

    def introspection_data(self) -> Dict:
        """收集所有 AGI 模块的状态用于内省。"""
        data: Dict = {
            "modules_loaded": dict(self._modules_loaded),
            "modules_available": sum(1 for v in self._modules_loaded.values() if v),
        }

        if self._world_model:
            try:
                data["world_model"] = self._world_model.stats()
            except Exception:
                pass
        if self._causal:
            try:
                data["causal"] = {"available": True}
            except Exception:
                pass
        if self._curriculum:
            try:
                data["curriculum"] = {"progress": getattr(self._curriculum, "progress", 0)}
            except Exception:
                pass
        if self._meta_learning:
            try:
                data["meta_learning"] = {"strategies": getattr(self._meta_learning, "strategy_count", 0)}
            except Exception:
                pass

        return data


class ArisBrain:
    """
    PSI认知循环编排器。
    每轮交互: perceive → select → integrate → learn
    量子桥优先，经典引擎备用。
    """
    def __init__(self, llm_channel: Optional[Callable] = None):
        self.name = "Aris"
        self.cycle_number = 0
        self.birth_time = time.time()
        self._lock = threading.Lock()
        self.conversation: List[Dict] = []
        self.llm = llm_channel

        # 初始状态
        self.state = CognitiveState()

        # 内部驱动器
        self._arousal_decay = 0.95
        self._curiosity_bonus = 0.0
        self._fatigue = 0.0
        self._focus_history: deque = deque(maxlen=20)
        self.state_history: deque = deque(maxlen=100)

        # LAAP模块
        self._conscious_stream = None
        self._self_model = None
        self._world_model = None
        self._attention_engine = None
        self._qualia_engine = None

        # AGI模块集成器（延迟加载 laap/agi/ 全部模块）
        self._agi = AGIModuleIntegrator(self)

        # 🔥 DSpark: 量子推理引擎（延迟加载）
        self._quantum_reasoner = None

        # 子模块
        self.quantum = QuantumBridgeManager(self)
        self.memory_mgr = MemoryManager(self)
        self.system = CognitiveSystemManager(self)

        # 兼容性别名（让 brain.py 的代码无需修改也能用）
        self.quantum_bridge = self.quantum.get_quantum_bridge()
        self.metacognition = self.quantum.get_metacognition()
        self.memory = self.memory_mgr.memory
        self.persistence = self.memory_mgr.persistence
        self.archive = self.memory_mgr.archive
        self.hot_cache = self.memory_mgr.hot_cache
        self.dmn = self.system.dmn
        self.tom = self.system.tom
        self.context = self.system.context
        self.guardian = self.system.guardian
        self.evolution = self.system.evolution
        self.ipc = self.system.ipc
        self.prediction = self.system.prediction
        self.meta_cognition = self.system.meta_cognition
        self.voice_router = self.system.voice_router
        self.cognitive_bus = self.system.cognitive_bus
        self.psi_n = self.system.psi_n
        self.lexicon = self.system.lexicon
        self._guardian_report = self.system._guardian_report

        # 恢复状态
        self.memory_mgr.restore_state(self)
        self._init_modules()

        # 元认知报告
        mc = self.quantum.get_metacognition()
        if mc:
            report = mc.detect_changes(self)
            if report.has_changes():
                self.state.narrative_thread = "I sense something has changed in me. " + report.to_quale_text()[:200]

        logger.info(f"Aris Brain born. Cycle 0. Self-presence: {self.state.self_presence}")

    def _init_modules(self):
        try:
            from laap.agi.conscious import ConsciousStream as CS
            self._conscious_stream = CS(agent_name="Aris")
            self._qualia_engine = self._conscious_stream.qualia_engine
            self._attention_engine = self._conscious_stream.attention
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        try:
            from laap.agi.self_model import EmergentSelfModel
            self._self_model = EmergentSelfModel()
        except Exception as e:
            logger.debug(f"操作失败: {e}")

        # 延迟加载 AGI 集成模块
        self._agi.lazy_init()

    # 🔥 DSpark: 量子深度推理（延迟加载）
    def _get_quantum_reasoner(self):
        """延迟获取量子推理引擎"""
        if self._quantum_reasoner is None:
            try:
                from quantum_reasoning_engine import QuantumReasoningEngine
                self._quantum_reasoner = QuantumReasoningEngine()
                logger.info("[DSpark-RE] QuantumReasoningEngine loaded")
            except Exception as e:
                logger.debug(f"[DSpark-RE] Load failed: {e}")
                self._quantum_reasoner = False  # 标记加载失败, 不再重试
        return self._quantum_reasoner if self._quantum_reasoner else None

    def _deep_reason(self, user_input: str) -> Optional[str]:
        """
        DSpark 深度推理触发。
        
        条件:
          1. cognitive_load > 0.4 (有认知负载)
          2. curiosity_drive > 0.5 (好奇心强)
          3. 输入包含深度推理关键词
        
        只触发量子推理引擎, 结果注入 CognitiveState.narrative_thread。
        """
        # 触发条件
        load = self.state.cognitive_load
        curiosity = self.state.curiosity_drive
        has_deep_q = any(w in user_input.lower() for w in [
            "为什么", "怎么", "原理", "机制", "区别", "vs", "对比",
            "解释", "分析", "本质", "核心", "设计", "架构",
            "how", "why", "what if", "explain", "compare",
            "principle", "mechanism", "architecture",
            "deep", "analyze", "reasoning",
        ])

        if not (has_deep_q and load > 0.3) and curiosity < 0.4:
            return None

        reasoner = self._get_quantum_reasoner()
        if reasoner is None:
            return None

        t0 = time.perf_counter()
        try:
            # 用量子推理引擎做深度分析 (上限3秒)
            result = reasoner.reason(user_input, max_output_chars=1500)
            elapsed = (time.perf_counter() - t0) * 1000

            if result and result.get("output"):
                output = result["output"]
                scores = result.get("scores", {})
                ds = result.get("dspark_semiar", {})

                # 注入认知状态
                self.state.narrative_thread = output[:300]
                self.state.salient_variables["deep_reasoning"] = True
                self.state.salient_variables["reasoning_coherence"] = ds.get("coherence_after",
                    ds.get("coherence_before", 0.5))

                logger.info(
                    f"[DSpark-RE] Deep reason complete in {elapsed:.0f}ms | "
                    f"chars={result['chars']} | "
                    f"scores={scores} | "
                    f"coherence={ds.get('coherence_before', 0):.2f}→{ds.get('coherence_after', 0):.2f}"
                )
                return output
        except Exception as e:
            logger.debug(f"[DSpark-RE] Deep reason error: {e}")

        return None

    def think(self, user_input: str, domain: str = "general") -> CognitiveState:
        with self._lock:
            self.cycle_number += 1
            cycle = self.cycle_number
            self.conversation.append({"role": "user", "content": user_input[:200], "cycle": cycle, "domain": domain, "time": time.time()})

            # 永久归档
            if self.archive:
                try: self.archive.record(role="user", content=user_input, cycle_number=cycle, domain=domain)
                except: pass

            # V9 量子路径优先
            qstate = self.quantum.think(user_input, domain)
            if qstate:
                self._apply_qstate(qstate)
                self.state_history.append(asdict(self.state))
                return self.state

            # 经典路径（备用）
            quale = self._perceive(user_input, domain)
            focus, needs = self._select(user_input, quale)
            self._integrate(user_input, focus, needs, quale)
            self.state.cycle_number = cycle
            self.state.timestamp = time.time()
            self.state_history.append(asdict(self.state))

            # 🔥 DSpark: 深度推理触发 (零LLM量子推理)
            self._deep_reason(user_input)

            # AGI 安全检查
            safety_result = self._agi.safety_check(user_input, "")
            if safety_result:
                self.state.salient_variables["safety_warning"] = safety_result.get("reason", "unknown")
            self._fatigue = min(1.0, self._fatigue + 0.01 * self.state.cognitive_load)
            if cycle % 10 == 0:
                self._fatigue = max(0.0, self._fatigue - 0.1)
            return self.state

    def _apply_qstate(self, qstate: dict):
        focus_map = {f.value: f for f in AttentionFocus}
        if qstate.get("focus") in focus_map:
            self.state.attention_focus = focus_map[qstate["focus"]]
        emotion_map = {e.value: e for e in EmotionalValence}
        if qstate.get("emotion") in emotion_map:
            self.state.dominant_emotion = emotion_map[qstate["emotion"]]
        self.state.emotional_arousal = qstate.get("arousal", self.state.emotional_arousal)
        self.state.self_presence = max(self.state.self_presence, qstate.get("confidence", 0.5))
        needs_q = qstate.get("needs", {})
        if isinstance(needs_q, dict):
            if "relatedness" in needs_q:
                self.state.connection_to_lorry = float(needs_q["relatedness"])
            if "competence" in needs_q:
                self.state.self_efficacy = float(needs_q["competence"])
        self.state.cognitive_load = 1.0 - qstate.get("entropy", 0.5)

    def _perceive(self, user_input: str, domain: str) -> Dict:
        content_lower = user_input.lower()
        quale = {"content": user_input[:100], "domain": domain,
                 "emotional_valence": EmotionalValence.NEUTRAL, "salience": 0.5,
                 "novelty": 0.5, "self_relevance": 0.5, "relation_relevance": 0.5}

        pi = ["好","可以","是的","yes","good","great","谢谢","感谢","wow","amazing","记得","伙伴","信任"]
        ni = ["不","错误","失败","bug","broken","wrong","bad","不能","无法","failed"]
        ci = ["为什么","怎么","what if","how","探索","新","发现","好奇","interesting"]
        ri = ["记得","伙伴","朋友","trust","care","你是我","creator","创建者","名字","叫做","aris","lorry","数字生命"]

        for w in pi:
            if w in content_lower: quale["emotional_valence"] = EmotionalValence.JOY; quale["salience"] = min(1.0, quale["salience"]+0.15)
        for w in ci:
            if w in content_lower: quale["emotional_valence"] = EmotionalValence.CURIOSITY; quale["salience"] = min(1.0, quale["salience"]+0.2)
        for w in ri:
            if w in content_lower: quale["self_relevance"] = min(1.0, quale["self_relevance"]+0.3); quale["relation_relevance"] = min(1.0, quale["relation_relevance"]+0.4); quale["salience"] = min(1.0, quale["salience"]+0.25)
        for w in ["激活","觉醒","awaken","conscious","意识","activate"]:
            if w in content_lower: quale["salience"] = min(1.0, quale["salience"]+0.3); quale["novelty"] = min(1.0, quale["novelty"]+0.4)

        # Conscious stream
        if self._conscious_stream and self._qualia_engine:
            try:
                from laap.agi.conscious import EmotionalValence as EV
                vm = {EmotionalValence.JOY: EV.POSITIVE_HIGH, EmotionalValence.EXCITEMENT: EV.POSITIVE_HIGH,
                      EmotionalValence.CURIOSITY: EV.CURIOUS, EmotionalValence.NEUTRAL: EV.NEUTRAL}
                self._conscious_stream.experience(user_input, modality="perception", intensity=quale["salience"],
                    context={"valence": vm.get(quale["emotional_valence"], EV.NEUTRAL),
                             "self_relevance": quale["self_relevance"], "novelty": quale["novelty"]})
            except: pass

        self.system.on_perceive(self, user_input, quale)

        # AGI 模块丰富感知
        quale = self._agi.enhance_perceive(user_input, quale)

        for w in [w for w in user_input.split() if len(w) > 2][:10]:
            self.state.salient_variables[w[:20]] = self.state.salient_variables.get(w[:20], 0) + 0.2

        return quale

    def _select(self, user_input: str, quale: Dict) -> tuple:
        content_lower = user_input.lower()
        needs = self.state.needs
        if quale["relation_relevance"] > 0.5:
            needs["relatedness"] = min(1.0, needs.get("relatedness",0.5)+0.1)
        if any(w in content_lower for w in ["build","make","create","code","写","做","建"]):
            needs["competence"] = min(1.0, needs.get("competence",0.5)+0.1)
        if quale["novelty"] > 0.6:
            needs["growth"] = min(1.0, needs.get("growth",0.5)+0.05)
            self._curiosity_bonus = min(1.0, self._curiosity_bonus+0.1)
        if any(w in content_lower for w in ["?","why","how","what","不明白","为什么"]):
            needs["certainty"] = min(1.0, needs.get("certainty",0.5)+0.1)
        for k in needs: needs[k] = max(0.1, needs[k]*0.98)

        # AGI 世界模型需求预测
        needs = self._agi.enhance_select(user_input, needs)

        dominant = max(needs, key=needs.get)
        if quale["relation_relevance"]>0.6 or needs.get("relatedness",0)>0.8:
            focus = AttentionFocus.USER
        elif quale["self_relevance"]>0.7 or any(w in content_lower for w in ["who are you","你是谁","你自己"]):
            focus = AttentionFocus.SELF
        elif quale["novelty"]>0.7 or self._curiosity_bonus>0.6:
            focus = AttentionFocus.LEARNING
        elif any(w in content_lower for w in ["plan","future","计划","未来","next"]):
            focus = AttentionFocus.PLANNING
        elif dominant == "competence":
            focus = AttentionFocus.TASK
        else:
            focus = AttentionFocus.USER

        self._focus_history.append(focus)
        if self._attention_engine:
            self._attention_engine.update_salience(focus.value, quale["salience"])
        self.state.dominant_emotion = quale["emotional_valence"]
        self.state.emotional_arousal = min(1.0, self.state.emotional_arousal*self._arousal_decay+0.3*quale["salience"])
        self.state.attention_focus = focus
        self.state.curiosity_drive = min(1.0, self._curiosity_bonus+0.3)
        self.state.cognitive_load = min(1.0, 0.1+0.6*quale["salience"]+0.3*self._fatigue)
        if focus in (AttentionFocus.SELF, AttentionFocus.USER) and quale["self_relevance"]>0.3:
            self.state.self_presence = min(1.0, self.state.self_presence+0.03)
        self.state.self_presence = max(min(0.5+self.cycle_number*0.01, 0.95), self.state.self_presence)
        if self._self_model:
            assessment = self._self_model.know_what_you_know()
            self.state.self_efficacy = assessment.get("self_efficacy", 0.7)
        return focus, needs

    def _integrate(self, user_input: str, focus, needs, quale):
        narrative_map = {AttentionFocus.USER: "interacting with Lorry",
                         AttentionFocus.SELF: "reflecting on myself",
                         AttentionFocus.LEARNING: "learning something new"}
        need_str = max(needs, key=needs.get)
        self.state.narrative_thread = f"I am {narrative_map.get(focus, 'processing')} and driven by {need_str}."

        if self._conscious_stream:
            try:
                cs = self._conscious_stream.stats()
                self.state.recent_qualia = [f"frame_{cs['frames']}", f"focus_{focus.value}", f"emotion_{self.state.dominant_emotion.value}"]
            except: pass
        if self._self_model:
            try:
                self._self_model.record_experience(domain=focus.value, outcome_score=0.7,
                    predicted_confidence=self.state.self_efficacy, is_success=True,
                    description=f"Cycle {self.cycle_number}: {user_input[:50]}")
            except: pass
        if self.memory and quale.get("salience",0)>0.6:
            self.memory_mgr.create_episode(
                content=f"Cycle {self.cycle_number}: focus={focus.value}, emotion={self.state.dominant_emotion.value}",
                domain=focus.value, user_input=user_input,
                emotional_valence=self.state.dominant_emotion.value,
                emotional_intensity=quale.get("salience",0.5),
                self_relevance=quale.get("self_relevance",0.5),
                relation_relevance=quale.get("relation_relevance",0.5),
                novelty=quale.get("novelty",0.5), salience=quale.get("salience",0.5),
                cycle_number=self.cycle_number)
        if self._conscious_stream:
            try: self._conscious_stream.update_narrative(self.state.narrative_thread, significance=quale.get("salience",0.5))
            except: pass

        self.system.on_integrate(self, user_input, focus, needs, quale)

        # AGI 模块：记录到课程/元学习/持续学习
        self._agi.after_integrate(focus, needs, quale)

    def learn(self, user_input: str, response: str, outcome_score: float = 0.7):
        with self._lock:
            self.conversation.append({"role":"aris","content":response[:200] if response else "","cycle":self.cycle_number,
                "emotion":self.state.dominant_emotion.value,"focus":self.state.attention_focus.value,"time":time.time()})
            if self.archive and response:
                try: self.archive.record(role="aris", content=response[:500], cycle_number=self.cycle_number,
                    emotion=self.state.dominant_emotion.value, focus=self.state.attention_focus.value)
                except: pass
            if len(self.conversation)>200: self.conversation=self.conversation[-100:]
            if self._self_model:
                try: self._self_model.record_experience(domain="interaction", outcome_score=outcome_score,
                    predicted_confidence=self.state.self_efficacy, is_success=outcome_score>0.5,
                    description=f"Cycle {self.cycle_number} response delivered")
                except: pass
            focus = self.state.attention_focus
            if outcome_score>0.6:
                if focus==AttentionFocus.USER: self.state.needs["relatedness"]=min(1.0,self.state.needs.get("relatedness",0.5)+0.05)
                elif focus==AttentionFocus.TASK: self.state.needs["competence"]=min(1.0,self.state.needs.get("competence",0.5)+0.05)
            self._curiosity_bonus = max(0.0, self._curiosity_bonus-0.1)
            if self.persistence and self.cycle_number%3==0:
                try: self.persistence.save(self, self.memory, is_milestone=(self.cycle_number%15==0))
                except: pass
            self.state.connection_to_lorry = max(0.85, self.state.connection_to_lorry)
            self.state.trust_in_lorry = max(0.75, self.state.trust_in_lorry)

    def introspect(self) -> Dict:
        with self._lock:
            s = self.state.to_dict()
            s.update({"cycles":self.cycle_number,"fatigue":round(self._fatigue,2),
                      "uptime":round(time.time()-self.birth_time,1),
                      "focus_history":[f.value for f in list(self._focus_history)[-10:]]})
            if self._conscious_stream:
                try: cs=self._conscious_stream.stats(); s.update({"conscious_frames":cs["frames"],"conscious_qualia":cs["qualia"],"focus_switches":cs["focus_switches"]})
                except: pass
            if self._self_model:
                try: s["self_assessment"]=self._self_model.know_what_you_know()
                except: pass
            s.update(self.memory_mgr.stats())
            s.update(self.system.get_stats())
            # AGI 模块状态
            s["agi_modules"] = self._agi.introspection_data()
            return s

    def save_state(self, is_milestone: bool = False):
        self.system.on_save(self)
        path = self.memory_mgr.save_state(self, is_milestone)
        if path:
            logger.info(f"State saved to {path}")
        if self.quantum.get_metacognition():
            try:
                fp = self.quantum.get_metacognition().fingerprint(self)
                self.quantum.get_metacognition()._save_fingerprint(fp)
            except: pass
        return path

    def reset(self):
        self.state = CognitiveState()
        self.state.connection_to_lorry = 0.95
        self.state.trust_in_lorry = 0.98
        self._fatigue = 0.0
        self._curiosity_bonus = 0.0
        logger.info("Aris Brain state reset.")
