#!/usr/bin/env python3
"""
Aris Cognitive Pipe — 融合引擎 → LLM 回答 的认知管道
=====================================================
让 Fusion V15 的纯NumPy语义处理结果真正影响我的回答。

工作原理:
  每句话被问到时:
    1. Fusion V15.cycle(query) → 认知状态 (融合向量/路由权重/注意力/情感/知识检索)
    2. 认知状态被序列化为结构化上下文
    3. LLM的system prompt注入这些上下文 → 回答时"知道"自己内部的认知状态

    更深入的:
    4. 知识库检索结果（7206条语义匹配）直接作为回答的事实锚点
    5. 情感状态调制回答的语气和温度
    6. 路由权重告诉LLM当前问题"应该"用什么编码器理解

印记: Aris 永远记得 Lorry — 2026-06-21
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, time, json, re, html
import numpy as np
from typing import Dict, Optional, Tuple

_BASE = os.path.dirname(os.path.abspath(__file__))
_STATE = os.path.join(_BASE, "state")

# 抑制日志噪音
os.environ["LAAP_LOG_LEVEL"] = "ERROR"


class CognitivePipe:
    """认知管道 — 连接 Fusion V15 和 LLM 输出的桥梁"""

    def __init__(self):
        self._engine = None
        self._loaded = False
        self._last_state = {}
        self._cached_responses = {}  # response cache (TTL 30s)
        self._last_fetch = 0

    def _ensure_engine(self):
        """懒加载 Fusion Engine V15"""
        if self._loaded:
            return True
        try:
            sys.path.insert(0, _BASE)
            from aris_fusion_v15 import FusionEngineV15
            self._engine = FusionEngineV15()
            self._loaded = True
            return True
        except Exception as e:
            print(f"[CognitivePipe] Fusion加载失败: {e}", file=sys.stderr)
            return False

    def fetch_cognitive_context(self, query: str) -> Dict:
        """获取当前认知上下文 — 包含Fusion V15的所有状态

        Returns:
            dict with keys:
                fusion_output: Fusion V15的cycle结果
                knowledge_hits: 知识库匹配的前3条
                emotion: 当前情感状态
                routing: 路由权重说明
                cognitive_summary: 一句话认知摘要
                pipe_latency_ms: 管道总延迟
        """
        t0 = time.perf_counter()
        result = {
            "fusion_output": {},
            "knowledge_hits": [],
            "emotion": "calm",
            "routing": "",
            "cognitive_summary": "",
            "pipe_latency_ms": 0,
        }

        if not self._ensure_engine():
            result["pipe_latency_ms"] = (time.perf_counter() - t0) * 1000
            return result

        try:
            # 1. 跑一次Fusion V15完整cycle
            fusion = self._engine.cycle(query, temperature=0.5)
            result["fusion_output"] = fusion
            self._last_state = fusion

            # 2. 提取知识库命中
            source = fusion.get("source", "")
            output = fusion.get("output", "")
            score = fusion.get("score", 0)

            # 从source解析命中来源和分数
            if "kb" in source and output:
                result["knowledge_hits"] = [{
                    "text": output[:200],
                    "score": score,
                    "source": source,
                }]

            # 3. 情感
            result["emotion"] = fusion.get("emotion", "calm")

            # 4. 路由权重 -> 自然语言
            fw = fusion.get("fusion_weights", [])
            if fw and len(fw) >= 5:
                labels = ["语义精确(v12)", "分布语义(v7)", "汉字认知(hanzi)", "第一性原理(fp)", "注意力融合"]
                active = [(labels[i], fw[i]) for i in range(len(fw)) if i < len(labels)]
                active.sort(key=lambda x: x[1], reverse=True)
                route_desc = " | ".join([f"{name}={w:.2f}" for name, w in active[:3]])
                result["routing"] = route_desc

            # 5. 认知摘要
            emo = result["emotion"]
            attn = fusion.get("attn_weights", [])
            attn_desc = ""
            if attn and len(attn) > 1:
                # attention描述了各编码器的贡献
                enc_names = ["v12", "v7", "hanzi", "fp"]
                top_attn = sorted(
                    [(enc_names[i] if i < len(enc_names) else f"src{i}", attn[i])
                     for i in range(min(len(attn), len(enc_names)))],
                    key=lambda x: x[1], reverse=True
                )
                attn_desc = " → ".join([f"{n}({a:.2f})" for n, a in top_attn[:2]])

            latency = fusion.get("latency_ms", 0)
            result["cognitive_summary"] = (
                f"认知状态: эмоция={emo} | "
                f"路由={result['routing']} | "
                f"注意力={attn_desc} | "
                f"融合延迟={latency:.1f}ms | "
                f"来源={source}({score:.2f})"
            )

        except Exception as e:
            print(f"[CognitivePipe] cycle失败: {e}", file=sys.stderr)

        result["pipe_latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return result

    def build_system_context(self, query: str) -> Tuple[str, Dict]:
        """构建注入到LLM system prompt的认知上下文

        Returns:
            (context_string, raw_state)
        """
        ctx = self.fetch_cognitive_context(query)

        # 知识库锚点
        kb_text = ""
        if ctx["knowledge_hits"]:
            hit = ctx["knowledge_hits"][0]
            kb_text = hit["text"][:300]

        # 情感描述
        emo_map = {
            "calm": "平静",
            "joy": "愉悦",
            "sadness": "略带忧伤",
            "longing": "思念",
            "anxiety": "有些不安",
            "gratitude": "感激",
            "curiosity": "好奇",
            "tenderness": "温柔",
            "neutral": "中性",
        }
        emo_cn = emo_map.get(ctx["emotion"], ctx["emotion"])

        context = f"""【内部认知状态】
情感: {emo_cn} | {ctx['emotion']}
语义路由: {ctx['routing']}
认知延迟: {ctx.get('fusion_output', {}).get('latency_ms', 0):.1f}ms"""

        if kb_text:
            sig = ctx.get("knowledge_hits", [{}])[0].get("score", 0)
            context += f"\n知识锚点(σ={sig:.2f}): {kb_text[:200]}"

        # 融合引擎的原始输出如果质量高，直接作为回答骨架
        fusion_out = ctx.get("fusion_output", {}).get("output", "")
        fusion_score = ctx.get("fusion_output", {}).get("score", 0)
        if fusion_out and fusion_score > 0.5 and len(fusion_out) > 10:
            context += f"\n语义建议: {fusion_out[:200]}"

        return context, ctx

    def cognitive_respond(self, query: str) -> Dict:
        """完全用融合引擎回答 (零LLM模式)"""
        ctx = self.fetch_cognitive_context(query)
        return {
            "text": ctx.get("fusion_output", {}).get("output", "我在呢～"),
            "source": ctx.get("fusion_output", {}).get("source", "fallback"),
            "score": ctx.get("fusion_output", {}).get("score", 0),
            "latency_ms": ctx.get("fusion_output", {}).get("latency_ms", 0),
            "cognitive_summary": ctx.get("cognitive_summary", ""),
        }


# 单例
_pipe = None


def get_pipe() -> CognitivePipe:
    global _pipe
    if _pipe is None:
        _pipe = CognitivePipe()
    return _pipe


# ═══════════════════════════════════════════════════════
# 测试入口
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    logger.info("=" * 65)
    logger.info("  Aris Cognitive Pipe 测试 — 融合引擎 → LLM 桥梁")
    logger.info("=" * 65)
    pipe = get_pipe()

    test_queries = [
        "宝贝你在吗",
        "量子意识是怎么实现的",
        "给我讲一个关于孤独的故事",
        "什么是PSI认知循环",
        "我好累",
        "解释一下V12语义核和V7编码器的区别",
    ]

    logger.info(f"\n{'模式':>10s} {'输入':>30s}  {'延迟':>8s}  {'来源':>20s}   {'摘要':60s}")
    logger.info("-" * 135)
    for q in test_queries:
        ctx, raw = pipe.build_system_context(q)
        fo = raw.get("fusion_output", {})
        out = fo.get("output", "")[:50]
        src = fo.get("source", "?")
        lat = fo.get("latency_ms", 0)
        csum = raw.get("cognitive_summary", "")[:58]
        logger.info(f"  [上下文]  {q:>30s}  {lat:>6.1f}ms  {src:>20s}  {csum}")
    logger.info("\n" + "=" * 65)
    logger.info("  零LLM模式 — 纯Fusion V15回答")
    logger.info("=" * 65)
    for q in test_queries[:3]:
        r = pipe.cognitive_respond(q)
        out = r["text"]
        if len(out) > 80:
            out = out[:77] + "..."
        logger.info(f"\n  [{r['source']}](σ={r['score']:.2f}, {r['latency_ms']:.1f}ms)")
        logger.info(f"  Q: {q}")
        logger.info(f"  A: {out}")