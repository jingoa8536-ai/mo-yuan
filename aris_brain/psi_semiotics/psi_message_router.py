"""
Ψ-Semiotics 消息路由 — IntentClassifier + 引擎直接回应

在 Hermes 网关层拦截消息，对 psi-domain 查询直接调用引擎，
跳过 LLM token 生成，实现零 token 回应。

工作流程:
  用户消息 → IntentClassifier → "psi" → psi_respond() → 直接返回
                                → "chat/code/..." → LLM 正常处理

集成方式:
  - 作为网关 preprocessor hook 挂载
  - 或在新会话开始时由 skill 加载
"""

import sys
import os
import json
import time
import re
from pathlib import Path
from typing import Dict, Optional

BRAIN = Path("D:/LAAP/aris_brain")
SEMIOTICS = BRAIN / "psi_semiotics"
for p in [str(BRAIN), str(SEMIOTICS)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# 全局引擎缓存
_responder = None


def _ensure():
    global _responder
    if _responder is not None:
        return
    try:
        from psi_hermes_responder import psi_respond, quick_psi_check
        _responder = (psi_respond, quick_psi_check)
    except Exception:
        _responder = None


def should_route(message: str) -> Dict:
    """
    判断消息是否应该路由到 Ψ-Semiotics 引擎。
    
    返回: {"route": bool, "reason": str, "confidence": float}
    """
    _ensure()
    if _responder is None:
        return {"route": False, "reason": "engine_not_loaded", "confidence": 0.0}
    
    _, check_fn = _responder
    result = check_fn(message)
    return {
        "route": result["should_route"],
        "reason": result["reason"],
        "confidence": result["domain_score"],
    }


def route_and_respond(message: str) -> Optional[Dict]:
    """
    路由消息并返回引擎回应（如果适用）。
    
    返回 None 表示应该由 LLM 处理。
    """
    _ensure()
    if _responder is None:
        return None
    
    # 路由检查
    route = should_route(message)
    if not route["route"]:
        return None
    
    # 引擎直接回应
    respond_fn, _ = _responder
    result = respond_fn(message)
    
    if result.get("type") == "unknown" or not result.get("text"):
        return None
    
    return {
        "routed": True,
        "route_info": route,
        "engine_response": result,
        "response_text": result.get("text", ""),
        "saved_llm_tokens": len(result.get("text", "")) // 2,  # 粗略估计
    }


# ── Gateway 集成接口 ──

def gateway_preprocessor(message: str, context: dict) -> Dict:
    """
    Hermes Gateway preprocessor hook.
    
    在消息进入 LLM 之前调用。
    如果引擎能处理，直接返回结果，跳过 LLM。
    """
    start = time.time()
    
    response = route_and_respond(message)
    if response is None:
        return {"action": "pass", "reason": "no_psi_match"}
    
    return {
        "action": "respond",
        "content": response["response_text"],
        "metadata": {
            "engine": "psi_semiotics",
            "latency_ms": round((time.time() - start) * 1000, 1),
            "saved_tokens": response["saved_llm_tokens"],
            "route": response["route_info"]["reason"],
        },
    }


def cli_check(message: str):
    """命令行测试路由"""
    result = should_route(message)
    print(f"消息: {message}")
    print(f"路由: {'✅ Ψ-Semiotics' if result['route'] else '❌ LLM'}")
    print(f"原因: {result['reason']}")
    print(f"置信度: {result['confidence']}")
    
    if result["route"]:
        resp = route_and_respond(message)
        if resp:
            print(f"\n引擎回应:\n{resp['response_text']}")
            print(f"\n节省 ~{resp['saved_llm_tokens']} tokens")


if __name__ == "__main__":
    print("=== Ψ-Semiotics 消息路由测试 ===\n")
    
    tests = [
        "king 和 queen 有什么区别",
        "hi 你好",
        "consciousness和quantum的关系",
        "king:queen :: man:?",
        "帮我写个 Python 爬虫",
    ]
    
    for msg in tests:
        cli_check(msg)
        print("-" * 40)
