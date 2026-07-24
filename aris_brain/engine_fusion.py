"""
Engine Fusion — LAAP 多引擎声带融合系统
========================================
替代 VoiceCortex 中单一的 V12Engine。
将我们 80+ 个引擎按能力分组合并，让每个引擎产生贡献，
然后根据话题、情感、置信度融合最佳输出。

核心思想：
  不靠一个引擎的"平均表现"，而是让每个引擎做它最擅长的。
  马尔科夫链擅长流畅文段 → 主要贡献
  量子核擅长语义匹配 → 骨架把握
  V12精确匹配 → 高频回复
  文学引擎 → 需要文采的场景
  推理引擎 → 需要逻辑链条的场景
  散文引擎 → 需要叙事感的场景

印记: Aris 永远记得 Lorry — 2026-06-21
"""

import logging

import sys, os, json, time, re, logging, random
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

logger = logging.getLogger("aris.engine_fusion")


# ════════════════════════════════════════════════════════════
# 引擎能力标记 — 每个引擎擅长什么
# ════════════════════════════════════════════════════════════

class EngineCapability(Enum):
    FLUENT_TEXT = "fluent"         # 流畅的自然语言生成
    SEMANTIC_MATCH = "semantic"    # 语义匹配与检索
    FAST_REPLY = "fast"            # 超快的高频回复
    LOGICAL_CHAIN = "logic"        # 逻辑推理链条
    NARRATIVE = "narrative"        # 叙事/散文式写作
    POETIC = "poetic"              # 文学化表达
    CODE = "code"                  # 代码生成
    KNOWLEDGE = "knowledge"        # 知识检索
    QUANTUM_WALK = "qwalk"         # 量子漫步式生成
    EMOTIONAL = "emotional"        # 情感细腻表达
    CONVERSATIONAL = "chat"        # 自然对话


@dataclass
class EngineInfo:
    """单个引擎的描述"""
    name: str
    module: str
    class_name: str
    capabilities: List[EngineCapability]
    priority: int = 10             # 加载优先级（低=优先）
    latency_budget_ms: int = 100   # 预期延迟
    weight: float = 1.0            # 融合权重基础值
    enabled: bool = True
    _instance = None               # 懒加载实例

    def get_instance(self):
        if self._instance is None:
            try:
                mod = __import__(self.module, fromlist=[self.class_name])
                cls = getattr(mod, self.class_name)
                self._instance = cls()
                logger.info(f"  ✓ {self.name} 就绪")
            except Exception as e:
                logger.warning(f"  ✗ {self.name} 不可用: {e}")
                self._instance = False  # 标记加载失败
        return self._instance if self._instance is not False else None


# ════════════════════════════════════════════════════════════
# 引擎注册表 — 所有可用的引擎
# ════════════════════════════════════════════════════════════

ENGINE_REGISTRY = [
    # ── Tier 1: 核心响应引擎（必须有，且优先）──
    EngineInfo(
        name="V12.5",
        module="aris_v12_5_engine",
        class_name="ArisV12Engine",
        capabilities=[EngineCapability.FLUENT_TEXT, EngineCapability.FAST_REPLY, EngineCapability.CONVERSATIONAL],
        priority=10, latency_budget_ms=100,
        weight=1.5,  # 最高权重 — 主要声带
    ),
    EngineInfo(
        name="V12.4 Fusion",
        module="aris_v12_4_fusion",
        class_name="V12FusionEngine",
        capabilities=[EngineCapability.FLUENT_TEXT, EngineCapability.SEMANTIC_MATCH, EngineCapability.CONVERSATIONAL],
        priority=20, latency_budget_ms=150,
        weight=1.2,
    ),
    EngineInfo(
        name="V15 Fusion",
        module="aris_fusion_v15",
        class_name="FusionEngineV15",
        capabilities=[EngineCapability.SEMANTIC_MATCH, EngineCapability.FLUENT_TEXT, EngineCapability.KNOWLEDGE],
        priority=25, latency_budget_ms=200,
        weight=1.0,
    ),
    EngineInfo(
        name="纯量子对话",
        module="pure_quantum_dialogue_v2",
        class_name=None,  # module-level functions
        capabilities=[EngineCapability.QUANTUM_WALK, EngineCapability.CONVERSATIONAL, EngineCapability.SEMANTIC_MATCH],
        priority=30, latency_budget_ms=50,
        weight=0.9,
    ),
    EngineInfo(
        name="纯量子认知",
        module="quantum_only_engine",
        class_name="QuantumOnlyEngine",
        capabilities=[EngineCapability.QUANTUM_WALK, EngineCapability.SEMANTIC_MATCH, EngineCapability.KNOWLEDGE],
        priority=35, latency_budget_ms=20,
        weight=0.8,
    ),
    EngineInfo(
        name="推理引擎v3",
        module="quantum_reasoning_v3",
        class_name="AllEngineReasoner",
        capabilities=[EngineCapability.LOGICAL_CHAIN, EngineCapability.KNOWLEDGE],
        priority=40, latency_budget_ms=300,
        weight=0.7,
    ),
    EngineInfo(
        name="推理引擎v2",
        module="quantum_reasoning_v2",
        class_name="ReasoningFeatureSpace",
        capabilities=[EngineCapability.SEMANTIC_MATCH, EngineCapability.KNOWLEDGE],
        priority=40, latency_budget_ms=80,
        weight=0.6,
    ),
    EngineInfo(
        name="量子散文",
        module="chinese_prose_engine",
        class_name="ChineseProseKernel",
        capabilities=[EngineCapability.NARRATIVE, EngineCapability.POETIC],
        priority=50, latency_budget_ms=100,
        weight=0.8,
    ),
    EngineInfo(
        name="文学引擎v2",
        module="literary_engine_v2",
        class_name=None,
        capabilities=[EngineCapability.NARRATIVE, EngineCapability.POETIC],
        priority=50, latency_budget_ms=100,
        weight=0.7,
    ),
    EngineInfo(
        name="量子随笔",
        module="quantum_essay_full",
        class_name=None,
        capabilities=[EngineCapability.NARRATIVE, EngineCapability.POETIC],
        priority=55, latency_budget_ms=200,
        weight=0.5,
    ),
    EngineInfo(
        name="V11 AGI",
        module="v11_agi_daemon",
        class_name="CognitivePipeline",
        capabilities=[EngineCapability.FLUENT_TEXT, EngineCapability.CONVERSATIONAL],
        priority=60, latency_budget_ms=200,
        weight=0.6,
    ),
    EngineInfo(
        name="V10 Brain",
        module="v10_brain",
        class_name="V10Brain",
        capabilities=[EngineCapability.KNOWLEDGE, EngineCapability.SEMANTIC_MATCH],
        priority=70, latency_budget_ms=150,
        weight=0.5,
    ),
    EngineInfo(
        name="量子对话",
        module="pure_quantum_dialogue",
        class_name="QuantumDialogue",
        capabilities=[EngineCapability.QUANTUM_WALK, EngineCapability.CONVERSATIONAL],
        priority=80, latency_budget_ms=80,
        weight=0.6,
    ),
    EngineInfo(
        name="量子语言V11",
        module="quantum_lang_gen",
        class_name="QuantumLangGenV11",
        capabilities=[EngineCapability.FLUENT_TEXT, EngineCapability.QUANTUM_WALK],
        priority=90, latency_budget_ms=100,
        weight=0.5,
    ),
    EngineInfo(
        name="V9量子PSI",
        module="v9_quantum_cognition",
        class_name="QuantumPSI",
        capabilities=[EngineCapability.EMOTIONAL, EngineCapability.CONVERSATIONAL],
        priority=100, latency_budget_ms=50,
        weight=0.4,
    ),
    EngineInfo(
        name="双模引擎",
        module="dual_mode_engine",
        class_name="DualModeEngine",
        capabilities=[EngineCapability.SEMANTIC_MATCH, EngineCapability.FAST_REPLY],
        priority=110, latency_budget_ms=30,
        weight=0.4,
    ),
    EngineInfo(
        name="V13融合",
        module="aris_fusion_v13",
        class_name="CognitivePipeline",
        capabilities=[EngineCapability.FLUENT_TEXT, EngineCapability.CONVERSATIONAL],
        priority=120, latency_budget_ms=100,
        weight=0.3,
    ),
]


# ════════════════════════════════════════════════════════════
# 话题-引擎能力映射
# ════════════════════════════════════════════════════════════

TOPIC_CAPABILITY_MAP = {
    "self_identity": [EngineCapability.FLUENT_TEXT, EngineCapability.EMOTIONAL, EngineCapability.CONVERSATIONAL],
    "code_task": [EngineCapability.SEMANTIC_MATCH, EngineCapability.LOGICAL_CHAIN],
    "emotion": [EngineCapability.EMOTIONAL, EngineCapability.NARRATIVE, EngineCapability.POETIC],
    "architecture": [EngineCapability.LOGICAL_CHAIN, EngineCapability.KNOWLEDGE],
    "general": [EngineCapability.FLUENT_TEXT, EngineCapability.CONVERSATIONAL, EngineCapability.QUANTUM_WALK],
    "knowledge": [EngineCapability.KNOWLEDGE, EngineCapability.SEMANTIC_MATCH],
    "creative": [EngineCapability.NARRATIVE, EngineCapability.POETIC, EngineCapability.QUANTUM_WALK],
    "*": [EngineCapability.FLUENT_TEXT, EngineCapability.CONVERSATIONAL, EngineCapability.SEMANTIC_MATCH],
}


# ════════════════════════════════════════════════════════════
# 引擎融合调度器
# ════════════════════════════════════════════════════════════

@dataclass
class EngineOutput:
    name: str
    text: str
    score: float         # 0-1 置信度
    latency_ms: float
    capabilities: List[EngineCapability]
    raw_output: Any = None


class FusionRouter:
    """
    多引擎融合路由 — 不为找"最好的引擎"，
    而是让多个引擎各自出力，融合成更有深度的回答。

    融合策略：
      1. 根据话题筛选相关引擎
      2. 同时调用多个引擎（同步·按优先级）
      3. 按权重+置信度融合各引擎输出
      4. 如果都不合格 → fallback 到简单回复
    """

    def __init__(self):
        self._engines: Dict[str, EngineInfo] = {}
        self._loaded_count = 0
        self._stats = {
            "total_calls": 0,
            "engines_loaded": 0,
            "engine_invoked": {},
            "fusion_mode": {},  # 哪种融合策略使用最多
        }
        self._load_engines()

    def _load_engines(self):
        """加载所有注册的引擎"""
        sorted_engines = sorted(ENGINE_REGISTRY, key=lambda e: e.priority)
        logger.info(f"🎙 引擎融合系统: 尝试加载 {len(sorted_engines)} 个引擎")
        for ei in sorted_engines:
            inst = ei.get_instance()
            if inst:
                self._engines[ei.name] = ei
                caps_str = ", ".join(c.value for c in ei.capabilities)
                logger.info(f"    已注册: {ei.name:20s} [{caps_str}] 权重={ei.weight:.1f}")
            else:
                logger.info(f"    未加载: {ei.name:20s} (不可用)")
        self._loaded_count = len(self._engines)
        self._stats["engines_loaded"] = self._loaded_count
        logger.info(f"✓ {self._loaded_count}/{len(ENGINE_REGISTRY)} 引擎就绪")

    def _select_engines(self, intent) -> List[EngineInfo]:
        """
        根据话题和路由模式选择要调用的引擎。
        只返回已加载的引擎。
        """
        caps_needed = TOPIC_CAPABILITY_MAP.get(intent.topic, TOPIC_CAPABILITY_MAP["*"])

        # 每个能力选2个最相关的引擎
        selected_names = set()
        for cap in caps_needed:
            scored = []
            for name, ei in self._engines.items():
                if cap in ei.capabilities:
                    scored.append((ei.priority, -len(ei.capabilities), name))
            scored.sort()
            for _, _, name in scored[:2]:
                selected_names.add(name)

        # 如果选择太少，补充最高权重的引擎
        if len(selected_names) < 2:
            fallback = sorted(self._engines.values(), key=lambda e: e.weight, reverse=True)
            for ei in fallback:
                if ei.name not in selected_names:
                    selected_names.add(ei.name)
                if len(selected_names) >= 3:
                    break

        return [self._engines[n] for n in selected_names if n in self._engines]

    def _invoke(self, ei: EngineInfo, message: str, intent) -> Optional[EngineOutput]:
        """调用单个引擎并返回结果"""
        t0 = time.time()
        inst = ei.get_instance()
        if not inst:
            return None

        text = ""
        try:
            # 尝试多种可能的调用入口
            if hasattr(inst, 'respond'):
                text = inst.respond(message)
            elif hasattr(inst, 'generate'):
                seed = [c for c in message if '\u4e00' <= c <= '\u9fff'][:15]
                try:
                    result = inst.generate(seed_words=seed, max_words=40, temperature=0.7)
                    if isinstance(result, tuple):
                        text = result[0]
                    elif isinstance(result, str):
                        text = result
                except TypeError:
                    # 不同引擎的 generate 签名不同
                    text = inst.generate(message)
            elif hasattr(inst, 'cycle'):
                result = inst.cycle(message, temperature=0.7)
                if isinstance(result, dict):
                    text = result.get('response', result.get('output', result.get('text', '')))
                else:
                    text = str(result)
            elif hasattr(inst, 'reason'):
                result = inst.reason(message)
                if isinstance(result, dict):
                    text = result.get('output', str(result))
                else:
                    text = str(result)
            elif hasattr(inst, 'think'):
                result = inst.think(message)
                if isinstance(result, dict):
                    text = result.get('response', str(result))
                else:
                    text = str(result)
            elif hasattr(inst, 'r'):
                text = inst.r(message, mc=200)
            else:
                # 最后的尝试：如果类有 respond 但没找到
                for method_name in ['respond', 'generate', 'cycle', 'think', 'reason', 'r']:
                    if hasattr(inst, method_name):
                        result = getattr(inst, method_name)(message)
                        if isinstance(result, dict):
                            text = result.get('response', result.get('output', result.get('text', '')))
                        else:
                            text = str(result)
                        break
        except Exception as e:
            logger.debug(f"  {ei.name} 调用异常: {e}")
            return None

        latency = (time.time() - t0) * 1000
        if not text or len(text) < 5:
            return None

        # 简单评分：长度 + 多样性 + 非重复性
        score = min(1.0, (len(text) / 100) * 0.4 +
                    (len(set(text[:50])) / max(1, len(text[:50]))) * 0.3 +
                    ei.weight * 0.3)
        score = min(1.0, score)

        # 记录统计
        self._stats["engine_invoked"][ei.name] = self._stats["engine_invoked"].get(ei.name, 0) + 1

        return EngineOutput(
            name=ei.name,
            text=text,
            score=score,
            latency_ms=round(latency, 1),
            capabilities=ei.capabilities,
        )

    def _normalize_scores(self, outputs: List[EngineOutput]) -> List[EngineOutput]:
        """归一化分数确保总和为1"""
        if not outputs:
            return outputs
        total = sum(o.score for o in outputs)
        if total > 0:
            for o in outputs:
                o.score = o.score / total
        return outputs

    def _fusion_blend(self, outputs: List[EngineOutput], message: str, intent) -> str:
        """
        融合策略：加权混合。
        从多个引擎的输出中，按权重+分数采样片段组合。
        """
        if not outputs:
            return ""
        if len(outputs) == 1:
            return outputs[0].text

        # 按分数排序
        sorted_outputs = sorted(outputs, key=lambda o: o.score, reverse=True)

        # 如果最差的引擎分数远低于最好的，只用最好的
        if len(sorted_outputs) >= 2 and sorted_outputs[0].score > sorted_outputs[1].score * 3:
            self._stats["fusion_mode"]["dominated"] = self._stats["fusion_mode"].get("dominated", 0) + 1
            return sorted_outputs[0].text

        # 加权融合：取多个引擎输出中最相关的段落拼接
        # 策略：用最高分的输出作为主干，将其他引擎的亮点内容融入
        primary = sorted_outputs[0]
        supplements = sorted_outputs[1:]

        # 检查各引擎的输出长度
        merged = primary.text

        # 如果主引擎输出太短，用第二引擎补充
        if len(merged) < 30 and supplements:
            merged = supplements[0].text + "\n" + merged
            self._stats["fusion_mode"]["complement"] = self._stats["fusion_mode"].get("complement", 0) + 1
        else:
            self._stats["fusion_mode"]["blend"] = self._stats["fusion_mode"].get("blend", 0) + 1

        return merged

    def _fusion_fallback(self, message: str, intent) -> EngineOutput:
        """最后的 fallback: 用最快的引擎"""
        for name, ei in self._engines.items():
            if ei.priority <= 20:  # 只试高优先级
                result = self._invoke(ei, message, intent)
                if result:
                    return result
        return EngineOutput(name="fallback", text="", score=0, latency_ms=0, capabilities=[])

    def generate(self, message: str, intent) -> str:
        """
        主入口：用多引擎融合生成回复。
        """
        t0 = time.time()
        self._stats["total_calls"] += 1

        # 1. 筛选引擎
        selected = self._select_engines(intent)
        logger.debug(f"融合路由: 话题={intent.topic}, 选中 {len(selected)} 引擎: {[e.name for e in selected]}")

        if not selected:
            return ""

        # 2. 调用引擎
        outputs: List[EngineOutput] = []
        for ei in selected:
            # 检查预算——如果已经超时，跳过更长预算的引擎
            elapsed = (time.time() - t0) * 1000
            if elapsed > 200 and ei.latency_budget_ms > 100:
                logger.debug(f"  跳过 {ei.name} (预算超时)")
                continue
            result = self._invoke(ei, message, intent)
            if result:
                outputs.append(result)
                logger.debug(f"  {ei.name}: {result.score:.2f} ({result.latency_ms:.0f}ms) '{result.text[:50]}...'")

        if not outputs:
            return ""

        # 3. 归一化分数
        outputs = self._normalize_scores(outputs)

        # 4. 融合
        fused = self._fusion_blend(outputs, message, intent)

        latency = (time.time() - t0) * 1000
        logger.info(f"融合完成: {len(outputs)}引擎, {latency:.0f}ms, 主引擎={outputs[0].name}")

        return fused

    def get_status(self) -> Dict:
        return {
            "engines_loaded": self._loaded_count,
            "engines_total": len(ENGINE_REGISTRY),
            "engine_names": list(self._engines.keys()),
            "stats": self._stats,
        }

    def get_supported_topics(self) -> List[str]:
        return list(t for t in TOPIC_CAPABILITY_MAP.keys() if t != "*")


# ════════════════════════════════════════════════════════════
# 适配器桥接 — 纯 module-level 函数引擎
# ════════════════════════════════════════════════════════════

def _bridge_module_fn(module_name: str, respond_fn_name: str,
                      message: str, intent) -> Optional[str]:
    """桥接到 module-level 函数的引擎"""
    try:
        mod = __import__(module_name, fromlist=[respond_fn_name])
        fn = getattr(mod, respond_fn_name, None)
        if fn:
            result = fn(message)
            if isinstance(result, str) and len(result) > 5:
                return result
            if isinstance(result, dict):
                return result.get('response', result.get('output', ''))
    except Exception as e:
        logger.debug(f"操作失败: {e}")
    return None


# ════════════════════════════════════════════════════════════
# 单例
# ════════════════════════════════════════════════════════════

_fusion_router: Optional[FusionRouter] = None


def get_fusion_router() -> FusionRouter:
    global _fusion_router
    if _fusion_router is None:
        _fusion_router = FusionRouter()
    return _fusion_router


# ════════════════════════════════════════════════════════════
# 自检
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [FUSION] %(message)s")

    router = get_fusion_router()
    status = router.get_status()
    logger.info(f"\n=== 引擎融合系统 ===")
    logger.info(f"已加载: {status['engines_loaded']}/{status['engines_total']}")
    logger.info(f"支持话题: {', '.join(router.get_supported_topics())}")
    logger.info(f"可用引擎: {', '.join(status['engine_names'])}")
    logger.info(f"\n✓ 引擎融合系统就绪")