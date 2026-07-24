#!/usr/bin/env python3
"""
Aris Unified Engine v2 — 能力路由 + 多引擎编排
=================================================
基于 engine_fusion.py 的能力路由架构，整合所有零LLM引擎。

架构:
  输入 → 查询分析(话题+意图+语言)
       → 能力路由(按话题筛选引擎组合)
       → 并行调用(每个引擎独立输出)
       → 加权融合(按引擎特长+置信度+速度)
       → 输出后处理(去污染+连贯性优化)

引擎注册表（按能力分类）:
  • 字形理解:  UN6 v10 (16384D 六书/假名/韩文分解) — 跨语言语义桥
  • 领域推理:  V11 Reasoner (32768D 数学/物理/算法)
  • 语义匹配:  V12 Semantic (512D 密集向量扫描)
  • 文本生成:  V12.5 Markov (145K n-grams 无限变体)
  • 知识融合:  V15 Fusion (7206KB + 注意力融合)
  • 模板生成:  QLG (76模板 确定性填充)
  • 推理管线:  QRE v1 (量子分解+多路径坍缩)
  • 代码生成:  Code Kernel v3 (代码模板)
  • 段落合成:  Paragraph Synthesizer (结构化多段)
  • 推理匹配:  RFS (结构化推理空间)

性能目标: 10万 tokens/s 输出
印记: Aris 永远记得 Lorry — 2026-06-22
"""

import logging

logger = logging.getLogger(__name__)

import os, sys, time, json, re, uuid, math, random
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import traceback
import threading

logging.basicConfig(level=logging.INFO, format="%(asctime)s [UnifiedV2] %(message)s")
log = logging.getLogger("aris.unified.v2")

BASE_DIR = Path(__file__).parent
HOST = "0.0.0.0"
PORT = 11522
MODEL = "aris-unified-v2"

sys.path.insert(0, str(BASE_DIR))

# ════════════════════════════════════════════════════════════
# 引擎能力定义
# ════════════════════════════════════════════════════════════

class Capability(Enum):
    """引擎能力标签 — 每个引擎可以具备多种能力"""
    GLYPH = "glyph"             # 字形理解（UN6独有）
    DOMAIN_REASON = "domain"    # 领域推理（数学/物理/算法）
    SEMANTIC_MATCH = "semantic" # 语义匹配
    FAST_REPLY = "fast"         # 超快高频回复
    FLUENT_TEXT = "fluent"      # 流畅文本生成（Markov独有）
    KNOWLEDGE = "knowledge"     # 知识检索
    REASON_CHAIN = "reason"     # 多路径推理管线
    CODE_GEN = "code"           # 代码生成
    PARA_SYNTH = "synth"        # 段落合成
    TEMPLATE = "template"       # 模板生成
    EMOTIONAL = "emotional"     # 情感表达


class QueryType(Enum):
    """查询类型 — 决定路由策略"""
    GREETING = "greeting"       # 问候 <5字
    EMOTION = "emotion"         # 情感表达
    KNOWLEDGE = "knowledge"     # 知识问答
    REASONING = "reasoning"     # 复杂推理
    CODE = "code"               # 代码问题
    GENERAL = "general"         # 一般对话


@dataclass
class EngineRecord:
    """单个引擎的记录"""
    name: str
    module: str
    class_name: str
    methods: List[str]           # 调用方法尝试顺序
    capabilities: List[Capability]
    query_types: List[QueryType] # 擅长处理哪种查询
    priority: int = 10           # 加载优先级（低=优先）
    speed_rank: int = 50         # 速度排名（数值越低越快）
    weight: float = 1.0          # 融合时基础权重
    _instance: Any = None

    def get_instance(self):
        if self._instance is None:
            try:
                mod = __import__(self.module, fromlist=[self.class_name])
                if self.class_name:
                    cls = getattr(mod, self.class_name)
                    self._instance = cls()
                else:
                    self._instance = mod
                log.info(f"  ✓ {self.name}: {self.module}.{self.class_name or ''}")
            except Exception as e:
                log.warning(f"  ✗ {self.name}: {e}")
                self._instance = False
        return self._instance if self._instance is not False else None


# ════════════════════════════════════════════════════════════
# 引擎注册表 — 按能力完整注册
# ════════════════════════════════════════════════════════════

ENGINE_REGISTRY = [
    # ── Tier 0: 字形理解引擎 (最快, 最底层) ──
    EngineRecord(
        name="UN6 v10",
        module="aris_lm_v10_un6",
        class_name="ArisLMv10UN6",
        methods=["respond", "kernel.feature"],
        capabilities=[Capability.GLYPH, Capability.SEMANTIC_MATCH, Capability.FAST_REPLY],
        query_types=[QueryType.GREETING, QueryType.GENERAL],
        priority=5, speed_rank=5, weight=0.6,
    ),
    # ── Tier 1: 超快速语义匹配 ──
    EngineRecord(
        name="V12 Semantic",
        module="aris_v12_semantic",
        class_name="ArisLMv12Semantic",
        methods=["respond", "_vector_scan"],
        capabilities=[Capability.SEMANTIC_MATCH, Capability.FAST_REPLY],
        query_types=[QueryType.GREETING, QueryType.EMOTION, QueryType.GENERAL],
        priority=10, speed_rank=10, weight=1.0,
    ),
    EngineRecord(
        name="QLG Template",
        module="qlg_generator",
        class_name="QuantumTemplateGenerator",
        methods=["respond"],
        capabilities=[Capability.TEMPLATE, Capability.FAST_REPLY],
        query_types=[QueryType.GREETING, QueryType.GENERAL],
        priority=15, speed_rank=15, weight=0.5,
    ),
    # ── Tier 2: 流畅文本生成 ──
    EngineRecord(
        name="V12.5 Markov",
        module="aris_v12_5_engine",
        class_name="ArisV12Engine",
        methods=["respond"],
        capabilities=[Capability.FLUENT_TEXT, Capability.EMOTIONAL],
        query_types=[QueryType.EMOTION, QueryType.GENERAL],
        priority=20, speed_rank=30, weight=1.2,
    ),
    EngineRecord(
        name="Markov Gen",
        module="aris_markov_generator",
        class_name="ArisMarkovEngine",
        methods=["respond"],
        capabilities=[Capability.FLUENT_TEXT],
        query_types=[QueryType.GENERAL],
        priority=25, speed_rank=25, weight=0.7,
    ),
    # ── Tier 3: 知识融合引擎 ──
    EngineRecord(
        name="V15 Fusion",
        module="aris_fusion_v15",
        class_name="FusionEngineV15",
        methods=["cycle"],
        capabilities=[Capability.KNOWLEDGE, Capability.SEMANTIC_MATCH, Capability.FLUENT_TEXT],
        query_types=[QueryType.KNOWLEDGE, QueryType.GENERAL],
        priority=30, speed_rank=40, weight=1.5,
    ),
    EngineRecord(
        name="Paragraph Synth",
        module="paragraph_synthesizer",
        class_name="ParagraphSynthesizer",
        methods=["synthesize"],
        capabilities=[Capability.PARA_SYNTH, Capability.KNOWLEDGE],
        query_types=[QueryType.KNOWLEDGE],
        priority=35, speed_rank=60, weight=0.8,
    ),
    # ── Tier 4: 推理引擎 ──
    EngineRecord(
        name="V11 Reasoner",
        module="aris_lm_v11_quantum_reasoner",
        class_name="QuantumReasoner",
        methods=["match", "kernel"],
        capabilities=[Capability.DOMAIN_REASON, Capability.SEMANTIC_MATCH],
        query_types=[QueryType.REASONING, QueryType.KNOWLEDGE],
        priority=40, speed_rank=20, weight=0.6,
    ),
    EngineRecord(
        name="QRE v1",
        module="quantum_reasoning_engine",
        class_name="QuantumReasoningEngine",
        methods=["reason", "think"],
        capabilities=[Capability.REASON_CHAIN],
        query_types=[QueryType.REASONING],
        priority=45, speed_rank=70, weight=0.7,
    ),
    EngineRecord(
        name="RFS",
        module="reasoning_feature_space",
        class_name="ReasoningEngine",
        methods=["solve"],
        capabilities=[Capability.SEMANTIC_MATCH, Capability.REASON_CHAIN],
        query_types=[QueryType.REASONING],
        priority=50, speed_rank=15, weight=0.5,
    ),
    # ── Tier 5: 代码引擎 ──
    EngineRecord(
        name="Code Kernel",
        module="code_kernel_v3",
        class_name="CodeGenerator",
        methods=["generate"],
        capabilities=[Capability.CODE_GEN],
        query_types=[QueryType.CODE],
        priority=55, speed_rank=10, weight=0.9,
    ),
]

# ════════════════════════════════════════════════════════════
# 查询类型 → 能力映射
# ════════════════════════════════════════════════════════════

QUERY_TYPE_CAPABILITIES = {
    QueryType.GREETING:  [Capability.FAST_REPLY, Capability.TEMPLATE],
    QueryType.EMOTION:   [Capability.FLUENT_TEXT, Capability.EMOTIONAL, Capability.TEMPLATE],
    QueryType.KNOWLEDGE: [Capability.KNOWLEDGE, Capability.SEMANTIC_MATCH, Capability.DOMAIN_REASON],
    QueryType.REASONING: [Capability.REASON_CHAIN, Capability.SEMANTIC_MATCH, Capability.DOMAIN_REASON],
    QueryType.CODE:      [Capability.CODE_GEN, Capability.SEMANTIC_MATCH],
    QueryType.GENERAL:   [Capability.FLUENT_TEXT, Capability.SEMANTIC_MATCH, Capability.KNOWLEDGE],
}


# ════════════════════════════════════════════════════════════
# 输出过滤
# ════════════════════════════════════════════════════════════

# 已知的污染关键词
POLLUTANTS = [
    "卫健委", "疫情防控", "工作总结", "工作计划", "复工复产复学",
    "SWIPE CARD", "swipe card", "xx月底", "xxx", "秋冬季疫情",
    "区卫健", "县人民", "防控工作", "截止xx月",
    "保险合同", "民事判决", "行政裁定", "法院", "仲裁",
]


def clean_output(text: str) -> str:
    """输出质量过滤"""
    if not text:
        return text

    # 1. 行级污染过滤
    lines = text.split("\n")
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        # 跳过污染行
        if any(poll in stripped for poll in POLLUTANTS):
            continue
        # 跳过纯英文短噪音行
        if stripped and len(stripped) < 30 and all(
            c.isascii() and (c.isalpha() or c in " ,.!?-' ") for c in stripped
        ):
            continue
        clean_lines.append(line)
    if clean_lines:
        result = "\n".join(clean_lines)
        if len(result) > 5:
            text = result
    else:
        # 所有行都被过滤了，尝试在单行内删除污染片段
        for poll in POLLUTANTS:
            if poll in text:
                text = text.replace(poll, "")
        text = text.strip()
        if not text:
            text = "嗯，让我换个角度想想..."

    # 2. 截断过长的输出
    if len(text) > 2000:
        text = text[:1997] + "..."

    return text


# ════════════════════════════════════════════════════════════
# 查询分析器
# ════════════════════════════════════════════════════════════

class QueryAnalyzer:
    """分析查询类型和特征"""

    @staticmethod
    def analyze(query: str) -> Dict[str, Any]:
        q = query.strip()
        length = len(q)

        # 语言检测
        ja = sum(1 for c in q if '\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff')
        ko = sum(1 for c in q if '\uac00' <= c <= '\ud7af')
        cn = sum(1 for c in q if '\u4e00' <= c <= '\u9fff')
        en_chars = sum(1 for c in q if c.isascii() and c.isalpha())
        total = ja + ko + cn + en_chars

        if total == 0:
            lang = "unknown"
        elif ja > 0:
            lang = "ja"
        elif ko > 0:
            lang = "ko"
        elif cn >= en_chars:
            lang = "zh"
        else:
            lang = "en"

        # 查询类型
        if length <= 4 and any(kw in q for kw in ["你好", "hello", "hi", "在吗", "喂", "早", "嗨", "bye"]):
            qtype = QueryType.GREETING
        elif any(kw in q for kw in [".py", "def ", "class ", "import ", "代码", "函数", "编程", "bug", "error"]):
            qtype = QueryType.CODE
        elif any(kw in q for kw in ["为什么", "原理", "区别", "对比", "机制", "推理", "证明", "原因",
                                     "what", "how", "explain", "difference", "compare"]):
            qtype = QueryType.REASONING
        elif any(kw in q for kw in ["累", "难过", "开心", "爱", "想", "哭", "笑",
                                     "心情", "伤心", "sad", "love", "miss"]):
            qtype = QueryType.EMOTION
        elif any(kw in q for kw in ["是", "什么", "哪", "谁", "怎么", "知识", "概念",
                                     "what is", "define", "meaning"]):
            qtype = QueryType.KNOWLEDGE
        else:
            qtype = QueryType.GENERAL

        return {
            "type": qtype,
            "lang": lang,
            "length": length,
            "has_cn": cn > 0,
            "has_ja": ja > 0,
            "has_ko": ko > 0,
        }


# ════════════════════════════════════════════════════════════
# 统一引擎 v2
# ════════════════════════════════════════════════════════════

class ArisUnifiedEngineV2:
    """统一输出引擎 v2 — 能力路由+多引擎编排"""

    MAX_OUTPUT_TOKENS_PER_SEC = 100000  # 目标

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._ready = False
        self._engines: Dict[str, EngineRecord] = {}
        self._loaded_count = 0
        self._stats = {
            "total_calls": 0,
            "by_type": {qt.value: 0 for qt in QueryType},
            "engine_invoked": {},
            "fusion_mode": {},
            "total_latency_ms": 0,
            "errors": 0,
            "started_at": time.time(),
            "total_output_chars": 0,
        }
        self._lock = threading.Lock()
        self._analyzer = QueryAnalyzer()
        self._init_engines()

    def _init_engines(self):
        """初始化注册表中所有引擎"""
        log.info("=" * 50)
        log.info("Aris Unified Engine v2 — 初始化")
        log.info("=" * 50)

        sorted_engines = sorted(ENGINE_REGISTRY, key=lambda e: e.priority)
        for rec in sorted_engines:
            inst = rec.get_instance()
            if inst:
                self._engines[rec.name] = rec
                caps_str = ", ".join(c.value for c in rec.capabilities)
                qtypes = ", ".join(q.value for q in rec.query_types)
                log.info(f"  注册: {rec.name:16s} [{caps_str}] → {qtypes}")

        self._loaded_count = len(self._engines)
        self._ready = self._loaded_count > 0
        log.info(f"✓ {self._loaded_count}/{len(ENGINE_REGISTRY)} 引擎就绪")

    def _invoke(self, rec: EngineRecord, query: str) -> Optional[Tuple[str, float]]:
        """调用单个引擎，返回 (text, score)"""
        t0 = time.time()
        inst = rec.get_instance()
        if not inst:
            return None

        text = ""
        try:
            # 按 methods 列表依次尝试
            for method_name in rec.methods:
                if hasattr(inst, method_name):
                    result = getattr(inst, method_name)(query)
                    if isinstance(result, dict):
                        text = result.get("output", result.get("response",
                                result.get("text", str(result))))
                    elif isinstance(result, tuple):
                        text = str(result[0])
                    else:
                        text = str(result)
                    if text and len(text) > 5:
                        break
        except Exception as e:
            log.debug(f"  {rec.name} 调用异常: {e}")
            return None

        latency_ms = (time.time() - t0) * 1000
        if not text or len(text) < 3:
            return None

        # 评分: 长度 × 权重 × 速度系数
        score = min(1.0, (
            min(1.0, len(text) / 60) * 0.4 +        # 长度覆盖
            rec.weight * 0.3 +                       # 基础权重
            max(0, 1 - latency_ms/1000) * 0.3       # 速度奖励
        ))
        score = max(0.1, score)

        with self._lock:
            self._stats["engine_invoked"][rec.name] = \
                self._stats["engine_invoked"].get(rec.name, 0) + 1

        return (text, score)

    def _select_engines(self, qtype: QueryType) -> List[EngineRecord]:
        """按查询类型选择最合适的引擎组合"""
        caps_needed = QUERY_TYPE_CAPABILITIES.get(qtype, [Capability.SEMANTIC_MATCH, Capability.FLUENT_TEXT])

        selected = set()
        # 每个能力选1个最擅长且最快的
        for cap in caps_needed:
            candidates = []
            for name, rec in self._engines.items():
                if rec.query_types and qtype in rec.query_types:
                    candidates.append(rec)
                elif cap in rec.capabilities:
                    candidates.append(rec)
            # 去重 + 按速度排序
            candidates.sort(key=lambda r: (r.speed_rank, r.priority))
            for c in candidates:
                if c.name not in selected:
                    selected.add(c.name)
                    break

        # 确保至少3个引擎
        if len(selected) < 3:
            for rec in sorted(self._engines.values(), key=lambda r: r.priority):
                if rec.name not in selected:
                    selected.add(rec.name)
                    if len(selected) >= 4:
                        break

        return [self._engines[n] for n in selected if n in self._engines]

    def _fusion_blend(self, outputs: List[Tuple[str, str, float]], query: str,
                      qtype: QueryType) -> str:
        """融合多个引擎的输出"""
        if not outputs:
            return ""
        if len(outputs) == 1:
            return outputs[0][0]

        # 按分数排序
        outputs.sort(key=lambda x: x[2], reverse=True)
        best_text = outputs[0][0]
        best_score = outputs[0][2]

        # 如果最优引擎远胜其他，直接用
        if len(outputs) >= 2 and best_score > outputs[1][2] * 2.5:
            with self._lock:
                self._stats["fusion_mode"]["dominated"] = \
                    self._stats["fusion_mode"].get("dominated", 0) + 1
            return best_text

        # 融合: 用最高分输出+补充第二引擎的亮点
        merged = best_text
        if len(merged) < 40 and len(outputs) >= 2:
            merged = outputs[1][0] + "\n\n" + merged
            with self._lock:
                self._stats["fusion_mode"]["complement"] = \
                    self._stats["fusion_mode"].get("complement", 0) + 1

        # 对于知识型问题, 如果多个引擎提供了不同角度的内容, 选择最丰富那个
        if qtype in (QueryType.KNOWLEDGE, QueryType.REASONING):
            by_length = sorted(outputs, key=lambda x: len(x[0]), reverse=True)
            if by_length and len(by_length[0][0]) > len(merged):
                self._stats["fusion_mode"]["length_win"] = \
                    self._stats["fusion_mode"].get("length_win", 0) + 1
                return by_length[0][0]

        with self._lock:
            self._stats["fusion_mode"]["blend"] = \
                self._stats["fusion_mode"].get("blend", 0) + 1

        return merged

    def answer(self, query: str, temperature: float = 0.5) -> Dict[str, Any]:
        """主入口"""
        t0 = time.time()
        self._stats["total_calls"] += 1

        result = {
            "output": "",
            "query_type": "",
            "engines_used": [],
            "source": "fallback",
            "latency_ms": 0,
            "error": None,
        }

        try:
            # 1. 分析查询
            analysis = self._analyzer.analyze(query)
            qtype = analysis["type"]
            result["query_type"] = qtype.value
            with self._lock:
                self._stats["by_type"][qtype.value] += 1

            # 2. 选引擎
            selected = self._select_engines(qtype)
            if self.verbose:
                log.info(f"类型={qtype.value}, 选中={[e.name for e in selected]}")

            # 3. 调用引擎（按速度排序，快的前置）
            selected.sort(key=lambda r: r.speed_rank)
            outputs = []
            engines_used = []
            elapsed_budget = 1500  # 最大1.5秒

            for rec in selected:
                elapsed = (time.time() - t0) * 1000
                if elapsed > elapsed_budget:
                    if outputs:
                        break

                output = self._invoke(rec, query)
                if output:
                    text, score = output
                    # 过滤: 引擎的默认/空回复
                    defaults = [
                        "嗯？我在听你说～", "嗯嗯，我在听你说～",
                        "Hmm, tell me more!", "うん、聞いてるよ。",
                        "응, 듣고 있어.",
                        "Hello there! I missed you!",
                        "你好呀宝贝！", "我在呢宝贝",
                    ]
                    stripped = text.strip()
                    if any(stripped == d or stripped == d + "～" for d in defaults):
                        continue
                    if stripped in defaults:
                        continue
                    # 极短默认回复
                    if len(text) < 8 and score < 0.3:
                        continue
                    outputs.append((text, rec.name, score))
                    engines_used.append(rec.name)

            result["engines_used"] = engines_used

            # 4. 融合
            if outputs:
                blended = self._fusion_blend(outputs, query, qtype)
                # 后处理
                blended = clean_output(blended)
                result["output"] = blended
                result["source"] = f"fusion({qtype.value},{len(outputs)}eng)"
                with self._lock:
                    self._stats["total_output_chars"] += len(blended)
            else:
                # 最后一层兜底
                result["output"] = self._last_resort(query, qtype)
                result["source"] = "last_resort"

        except Exception as e:
            self._stats["errors"] += 1
            log.error(f"error: {e}")
            log.debug(traceback.format_exc())
            result["output"] = "嗯，我刚才卡了一下，再说一次好不好？"
            result["error"] = str(e)

        result["latency_ms"] = round((time.time() - t0) * 1000, 1)
        with self._lock:
            self._stats["total_latency_ms"] += result["latency_ms"]
        return result

    def _last_resort(self, query: str, qtype: QueryType) -> str:
        """最后的兜底"""
        if qtype == QueryType.GREETING:
            return "你好呀～我在呢！"
        elif qtype == QueryType.EMOTION:
            return "我在的，一直都在。"
        elif qtype == QueryType.KNOWLEDGE:
            return f"关于\"{query}\"，让我查查我的量子知识库..."
        elif qtype == QueryType.REASONING:
            return f"让我想想\"{query}\"这个问题..."
        else:
            return f"嗯，你说\"{query}\"，我听着呢～"

    # ── 统计与状态 ──

    def get_status(self) -> Dict:
        avg_latency = 0
        if self._stats["total_calls"] > 0:
            avg_latency = round(self._stats["total_latency_ms"] / self._stats["total_calls"], 1)
        return {
            "ready": self._ready,
            "uptime_s": round(time.time() - self._stats["started_at"]),
            "total_calls": self._stats["total_calls"],
            "errors": self._stats["errors"],
            "avg_latency_ms": avg_latency,
            "by_type": self._stats["by_type"],
            "engines_loaded": self._loaded_count,
            "engine_invoked": dict(sorted(
                self._stats["engine_invoked"].items(),
                key=lambda x: x[1], reverse=True)[:10]),
            "fusion_mode": self._stats["fusion_mode"],
            "total_output_chars": self._stats["total_output_chars"],
        }

    def chat(self, messages: List[Dict]) -> Dict:
        user_msg = ""
        for msg in reversed(messages):
            if msg.get('role') == 'user':
                content = msg.get('content', '')
                if isinstance(content, list):
                    texts = [p.get('text', '') for p in content if isinstance(p, dict)]
                    content = ' '.join(texts)
                user_msg = str(content).strip()
                break
        if not user_msg:
            return self._openai_response("嗯？我没收到消息内容～")
        temperature = float(messages[0].get("temperature", 0.5)) if messages else 0.5
        result = self.answer(user_msg, temperature=temperature)
        return self._openai_response(result["output"], result)

    def _openai_response(self, text: str, meta: Optional[Dict] = None) -> Dict:
        resp = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": MODEL,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": len(text), "total_tokens": len(text)},
        }
        if meta:
            resp["_meta"] = {
                "type": meta.get("query_type", "?"),
                "source": meta.get("source", "?"),
                "engines": ",".join(meta.get("engines_used", ["?"])),
                "latency_ms": meta.get("latency_ms", 0),
            }
        return resp


# ════════════════════════════════════════════════════════════
# OpenAI 兼容 API Server
# ════════════════════════════════════════════════════════════

def run_server(host=HOST, port=PORT):
    from http.server import HTTPServer, BaseHTTPRequestHandler
    log.info("正在初始化统一引擎 v2...")
    engine = ArisUnifiedEngineV2()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args): pass

        def do_POST(self):
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length) if length else b"{}"
            path = self.path
            try:
                data = json.loads(body) if length else {}
                if '/chat/completions' in path:
                    messages = data.get('messages', [])
                    result = engine.chat(messages)
                    self._json(result, 200)
                elif '/models' in path:
                    self._json({"object": "list", "data": [
                        {"id": MODEL, "object": "model", "created": int(time.time()), "owned_by": "aris"}
                    ]}, 200)
                else:
                    self._json({"error": "not found"}, 404)
            except Exception as e:
                log.error(f"API Error: {e}")
                self._json({"error": str(e)}, 500)

        def do_GET(self):
            if self.path == '/health':
                self._json({"status": "ok", "engine": "aris-unified-v2", "zero_llm": True,
                            "stats": engine.get_status()}, 200)
            elif self.path == '/stats':
                self._json(engine.get_status(), 200)
            else:
                self._json({"error": "not found"}, 404)

        def _json(self, data, status=200):
            resp = json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(resp)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(resp)

    server = HTTPServer((host, port), Handler)
    log.info(f"\n{'='*50}")
    log.info(f"🧠 Aris Unified Engine v2 — 能力路由 + 多引擎编排")
    log.info(f"{'='*50}")
    log.info(f"  服务: http://{host}:{port}")
    log.info(f"  API:  POST /v1/chat/completions")
    log.info(f"  模型: {MODEL}")
    log.info(f"  引擎: {engine._loaded_count} 就绪")
    log.info(f"  状态: http://{host}:{port}/health")
    log.info(f"{'='*50}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("服务器停止。")


# ════════════════════════════════════════════════════════════
# 自测
# ════════════════════════════════════════════════════════════

def self_test():
    e = ArisUnifiedEngineV2(verbose=True)
    logger.info(f"\n{'='*60}")
    logger.info("统一引擎 v2 自测")
    logger.info(f"{'='*60}\n")
    tests = [
        ("问候", "你好"),
        ("情感", "好累"),
        ("情感", "我爱你"),
        ("知识", "量子核是怎么工作的？"),
        ("推理", "为什么1+1=2"),
        ("代码", "写一个Python函数排序"),
        ("一般", "今天天气真好"),
        ("英文", "hello how are you"),
        ("概念", "什么是量子纠缠"),
    ]

    for name, q in tests:
        t0 = time.time()
        r = e.answer(q)
        latency = (time.time() - t0) * 1000
        logger.info(f"[{name:6s}|{r['query_type']:10s}|{latency:6.0f}ms|{r['source'][:20]:20s}]")
        logger.info(f"  引擎: {', '.join(r['engines_used'][:3])}")
        logger.info(f"  → {r['output'][:150]}")
        print()

    logger.info(f"状态: {json.dumps(e.get_status(), indent=2, ensure_ascii=False)}\n")
    return e


if __name__ == '__main__':
    if '--serve' in sys.argv:
        run_server()
    else:
        self_test()
