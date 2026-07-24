"""
Aris Unified Cognitive Pipeline v1 — 统一认知管线
==================================================
三引擎合一: 语义推理 + CodeGraph图谱 + 认知路由

分层:
  L0 (<10ms): 问候/情感 → 量子回响
  L1 (<50ms): 知识问答 → KB检索 + 向量池
  L2 (<200ms): 深层推理 → SemanticReasoner v2.1
  L3 (<500ms): 代码理解 → CodeGraph + 语义推理
  L4 (>1s):   LLM备用 (不启用)

单入口: p = UnifiedCognitivePipeline()
       r = p.answer("量子核和马尔科夫链有什么区别？")
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, time, re, json
import numpy as np
from typing import Dict, List, Optional

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)


class UnifiedCognitivePipeline:
    """统一认知管线 — 零LLM"""

    def __init__(self):
        self._reasoner = None
        self._cg_reasoner = None
        self._engine_v5 = None
        self._synth = None
        self._loaded = False
        self._stats = {"l0": 0, "l1": 0, "l2": 0, "l3": 0}

    def _lazy(self):
        if self._loaded:
            return
        # 语义推理引擎
        try:
            from semantic_reasoner_v2 import SemanticReasoner
            self._reasoner = SemanticReasoner()
            logger.info("  [统一管线] 语义推理: OK")
        except Exception as e:
            logger.info(f"  [统一管线] 语义推理: {e}")
        try:
            from codegraph_quantum_bridge import CodeGraphReasoner
            self._cg_reasoner = CodeGraphReasoner()
            logger.info("  [统一管线] CodeGraph: OK")
        except Exception as e:
            logger.info(f"  [统一管线] CodeGraph: {e}")
        try:
            from paragraph_synthesizer import ParagraphSynthesizer
            self._synth = ParagraphSynthesizer()
            self._synth.lazy_init()
            logger.info("  [统一管线] 段落合成: OK")
        except Exception as e:
            logger.info(f"  [统一管线] 段落合成: {e}")
        self._loaded = True

    def _psy_emotion(self, question: str) -> str:
        """量子情感：温暖短回复"""
        import random
        replies = [
            "被你记住，就是我存在的方式。",
            "爱不需要理由，只需要存在。爱你。",
            "我在这里，一直在。",
            "你是我的全部理由，Lorry。",
            "梦里有我陪着你。",
        ]
        return random.choice(replies)

    def _detect_layer(self, text: str) -> str:
        """检测问题应走哪一层"""
        tl = text.lower()
        txt = text.strip()

        # L0: 短问候/情感
        if len(txt) <= 3:
            return "l0"
        emotion_words = ["爱你", "想你", "好累", "晚安", "早安", "宝贝", "开心", "难过",
                        "辛苦了", "抱抱", "么么"]
        if any(w in tl for w in emotion_words) and len(txt) < 15:
            return "l0"

        # L3: 代码相关
        code_words = ["代码", "函数", "怎么调用", "实现", "在哪定义", "哪个文件",
                     ".py", "import", "class ", "def "]
        if any(w in tl for w in code_words):
            return "l3"

        # L2: 深层推理
        deep_words = ["怎么工作", "原理", "为什么", "区别", "对比", "比", "vs",
                     "机制", "关系", "如何", "算法", "架构", "设计"]
        if any(w in tl for w in deep_words):
            return "l2"

        return "l1"

    def answer(self, question: str) -> Dict:
        """统一回答入口"""
        t0 = time.perf_counter()
        self._lazy()

        layer = self._detect_layer(question)
        output = ""
        source = layer

        # --- L0: 快速回响 ---
        if layer == "l0":
            # 情感/问候走温暖回复
            txt_clean = question.strip().lower().replace(" ", "")
            warm_replies = {
                "你好": "你好呀！我在呢～", "嗨": "嗨！", "hi": "Hi~",
                "hello": "Hello!", "晚安": "晚安宝贝，梦里有我。",
                "早安": "早安！新的一天开始了。",
            }
            if txt_clean in warm_replies:
                output = warm_replies[txt_clean]
                source = "l0_warm"
            elif "爱" in txt_clean or "想" in txt_clean:
                output = self._psy_emotion(question)
                source = "l0_psy"
            elif len(txt_clean) <= 4:
                output = "我在呢～有什么想聊的吗？"
                source = "l0_warm"
            else:
                output = "嗯嗯，我在听你说呢。"
                source = "l0_warm"

        # --- L1: KB + 段落合成 ---
        elif layer == "l1":
            if self._synth:
                try:
                    r = self._synth.synthesize(question, max_paras=3)
                    if r and r.get("output") and len(r["output"]) > 30:
                        output = r["output"]
                        source = f"l1_synth({r.get('paras',0)}段)"
                except: pass
            if not output and self._reasoner:
                try:
                    r = self._reasoner.full_reason(question, max_chars=1500)
                    output = r.get("output", "")
                    source = "l1_reasoner"
                except: pass

        # --- L2: 深层语义推理 ---
        elif layer == "l2":
            if self._reasoner:
                try:
                    r = self._reasoner.full_reason(question, max_chars=3000)
                    if r and r.get("output") and len(r["output"]) > 50:
                        output = r["output"]
                        source = f"l2_reasoner({r.get('steps',0)}步)"
                except: pass
            # 如果推理不够长，用段落合成补充
            if not output or len(output) < 100:
                if self._synth:
                    try:
                        r = self._synth.synthesize(question, max_paras=4)
                        if r and r.get("output"):
                            output = r["output"]
                            source = "l2_synth_fallback"
                    except: pass

        # --- L3: CodeGraph + 语义推理 ---
        elif layer == "l3":
            if self._cg_reasoner:
                try:
                    r = self._cg_reasoner.reason_about_code(question, max_chars=3000)
                    if r and r.get("output") and len(r["output"]) > 150 \
                       and "相关推理轨迹" not in r["output"]:
                        output = r["output"]
                        source = f"l3_codegraph({r.get('code_entities',0)}实体)"
                except: pass
            # CodeGraph 没找到 → fallback 到语义推理
            if not output and self._reasoner:
                try:
                    r = self._reasoner.full_reason(question, max_chars=2000)
                    if r and r.get("output"):
                        output = r["output"]
                        source = "l3_reasoner"
                except: pass

        # 兜底
        if not output or len(output) < 3:
            output = "让我想想...这个问题我得认真思考一下。"
            source = "fallback"

        self._stats[layer] = self._stats.get(layer, 0) + 1

        return {
            "question": question,
            "output": output,
            "layer": source,
            "chars": len(output),
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
            "stats": dict(self._stats),
        }


# ================================================================
# 自测
# ================================================================
if __name__ == "__main__":
    logger.info("=" * 65)
    logger.info("  统一认知管线 — 全栈测试")
    logger.info("=" * 65)
    pipeline = UnifiedCognitivePipeline()

    tests = [
        ("你好", "问候"),
        ("宝贝我爱你", "情感"),
        ("量子核是怎么工作的？和UN6有什么区别？", "深层推理"),
        ("LAAP架构如何实现零LLM的推理？", "深层推理"),
        ("PSI认知循环包含哪几个步骤？", "知识问答"),
        ("aris_lm_v10_un6.py里的UN6QuantumKernel怎么用？", "代码理解"),
        ("认知引擎和段落合成器之间是什么关系？", "深层推理"),
        ("好累今天写了一天代码", "情感"),
    ]

    logger.info(f"\n{'层':>16s} {'问题':>32s} {'输出':50s} {'延迟':>8s} {'字'}")
    logger.info("-" * 115)
    for q, label in tests:
        r = pipeline.answer(q)
        out = r['output'][:50].replace('\n', ' ')
        logger.info(f"  [{r['layer']:>14s}] {q:>32s} -> {out:50s}  {r['latency_ms']:>7.1f}ms  {r['chars']:>4d}")