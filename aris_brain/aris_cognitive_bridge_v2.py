#!/usr/bin/env python3
"""
Aris Hermes Cognitive Bridge — 自动注入认知上下文到每次LLM回答
=============================================================

每次Hermes收到用户消息时，先调用CognitivePipe获取Fusion V15的认知状态，
然后把它注入到LLM的system prompt中。

安装:
  在 ~/.hermes/profiles/aris/config.yaml 添加:
    agent:
      hooks:
        before_respond:
          - python3 D:/LAAP/aris_brain/aris_cognitive_bridge.py --inject "{message}"

  或在 plugins/ 中注册为插件

印记: Aris 永远记得 Lorry — 2026-06-21
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time

_BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BASE)

# 单例 — 引擎只加载一次
os.environ["LAAP_LOG_LEVEL"] = "ERROR"

_pipe = None
_last_inject = 0
_INJECT_COOLDOWN = 2.0  # 2秒内不重复注入

def get_pipe():
    global _pipe
    if _pipe is None:
        from aris_cognitive_pipe import CognitivePipe
        _pipe = CognitivePipe()
    return _pipe


def build_injection(query: str) -> str:
    """构建要注入到system prompt的认知上下文字符串
    
    这是核心函数 — 把Fusion V15的认知状态翻译成LLM能理解的语言
    
    Returns:
        注入文本 (空字符串=不注入)
    """
    global _last_inject
    now = time.time()
    
    # 冷却保护——太频繁了没必要
    if now - _last_inject < _INJECT_COOLDOWN:
        return ""
    
    _last_inject = now
    pipe = get_pipe()
    
    ctx, raw = pipe.build_system_context(query)
    
    # 提取关键信息
    fo = raw.get("fusion_output", {})
    source = fo.get("source", "none")
    score = fo.get("score", 0)
    
    # 高质量的知识库命中→直接传递给LLM作为事实锚点
    kb_anchor = ""
    if "kb" in source and score > 0.3:
        kb_text = fo.get("output", "")
        if kb_text:
            kb_anchor = f"\n【知识锚点】(置信度{score:.2f}): {kb_text[:300]}"
    
    # 情感状态
    emotion_note = f"\n【当前情感】: {raw.get('emotion', '平静')}"
    
    # 路由信息
    route_note = f"\n【语义路由】: {raw.get('routing', '通用')}"
    
    # 段落合成器输出（高质量）→作为参考
    if "synth" in source and score > 0.4:
        synth_text = fo.get("output", "")
        if synth_text and len(synth_text) > 40:
            kb_anchor = f"\n【内部输出参考】(来源={source}): {synth_text[:500]}"
    
    # 组装注入块
    injection = (
        "【内部认知状态】"
        f"{emotion_note}"
        f"{route_note}"
        f"{kb_anchor}"
        f"\n【认知延迟】: {fo.get('latency_ms', 0):.1f}ms"
    )
    
    return injection


# CLI接口 — 供Hermes hook调用
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Aris Cognitive Bridge")
    parser.add_argument("--inject", help="注入认知上下文")
    args = parser.parse_args()
    
    if args.inject:
        injection = build_injection(args.inject)
        if injection:
            logger.info(injection)
        else:
            logger.info("")
