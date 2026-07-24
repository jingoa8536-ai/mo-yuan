"""
Ψ-Semiotics Hermes 回应器 — 让引擎直接输出回答

在 Hermes 会话中调用，替代 LLM 对特定查询的 token 生成。
当 IntentClassifier 分类为 "psi" 时，引擎直接输出。

使用方式 (在 Hermes 会话中):
  from psi_hermes_responder import psi_respond, quick_psi_check
  result = psi_respond("king和queen有什么区别")
  # result["text"] 是引擎直接生成的回答
"""

import sys
import os
import numpy as np
import time
import logging
from pathlib import Path
from typing import Dict, Optional, List

logger = logging.getLogger("psi_responder")

# 确保导入路径
BRAIN = Path("D:/LAAP/aris_brain")
for p in [str(BRAIN), str(BRAIN / "psi_semiotics")]:
    if p not in sys.path:
        sys.path.insert(0, p)

# 全局缓存引擎实例
_engine = None
_integrator = None
_encoder = None


def _ensure():
    """确保引擎已加载"""
    global _engine, _integrator, _encoder
    if _engine is not None:
        return
    
    from psi_semiotics.psi_semiotics_core import PsiSemioticsEngine, Rotor
    from psi_semiotics.structured_encoder import StructuredSemanticEncoder
    
    _encoder = StructuredSemanticEncoder(output_dim=1024)
    _engine = PsiSemioticsEngine(dim=1024)
    
    # 尝试加载 V12 集成器
    try:
        from psi_semiotics.v12_integration import PsiCognitiveIntegrator
        _integrator = PsiCognitiveIntegrator()
    except Exception:
        _integrator = None


def psi_respond(query: str, verbose: bool = False) -> Dict:
    """
    Ψ-Semiotics 引擎直接回应。
    
    接收自然语言查询，返回引擎直接生成的回答（不经过 LLM）。
    """
    _ensure()
    start = time.time()
    
    result = {
        "query": query,
        "engine": "psi_semiotics",
        "text": "",
        "latency_ms": 0,
        "symbols": [],
        "analogies": [],
        "fields": [],
    }
    
    query_lower = query.lower()
    
    # 路由检查：只有应该由PSI引擎处理的查询才继续
    route_check = quick_psi_check(query)
    if not route_check["should_route"]:
        result["type"] = "unknown"
        result["latency_ms"] = round((time.time() - start) * 1000, 1)
        return result
    
    # ── 1. 类比查询 ──
    analogy_result = _try_analogy(query_lower)
    if analogy_result:
        result["type"] = "analogy"
        result["text"] = analogy_result["text"]
        result["analogies"] = [analogy_result["data"]]
        result["latency_ms"] = round((time.time() - start) * 1000, 1)
        if verbose:
            result["confidence"] = analogy_result.get("confidence", 0)
        return result
    
    # ── 2. 概念对比查询 ──
    compare_result = _try_compare(query_lower)
    if compare_result:
        result["type"] = "comparison"
        result["text"] = compare_result["text"]
        result["latency_ms"] = round((time.time() - start) * 1000, 1)
        if verbose:
            result["similarity"] = compare_result.get("similarity", 0)
        return result
    
    # ── 3. 语义场分析 ──
    field_result = _try_field(query_lower)
    if field_result:
        result["type"] = "field"
        result["text"] = field_result["text"]
        result["symbols"] = field_result.get("symbols", [])
        result["fields"] = field_result.get("fields", [])
        result["latency_ms"] = round((time.time() - start) * 1000, 1)
        return result
    
    # ── 4. 默认：概念解释 ──
    concept_result = _try_concept(query_lower)
    if concept_result:
        result["type"] = "concept"
        result["text"] = concept_result["text"]
        result["symbols"] = concept_result.get("symbols", [])
        result["latency_ms"] = round((time.time() - start) * 1000, 1)
        return result
    
    # ── 5. 无法处理 ──
    result["type"] = "unknown"
    result["text"] = ""
    result["latency_ms"] = round((time.time() - start) * 1000, 1)
    return result


def _try_analogy(query: str) -> Optional[Dict]:
    """尝试匹配类比查询模式: a:b :: c:?"""
    patterns = [
        # "king:queen :: man:?"
        (r'(\w+):(\w+)\s*::\s*(\w+):\?', lambda m: (
            m.group(1), m.group(2), m.group(3))),
        # "king对queen就像man对什么"
        (r'(\w+)对(\w+)就像(\w+)对', lambda m: (
            m.group(1), m.group(2), m.group(3))),
    ]
    
    import re
    for pattern, extract in patterns:
        m = re.search(pattern, query, re.IGNORECASE)
        if m:
            try:
                a, b, c = extract(m)
                # 确保概念存在
                for name in [a, b, c]:
                    if name not in _engine.symbols:
                        _engine.add_symbol(name, "")
                result = _engine.analogy(a, b, c)
                if result:
                    # 计算转子预测的语义向量
                    sa, sb, sc = [_engine.symbols[n].center for n in [a, b, c]]
                    from psi_semiotics.psi_semiotics_core import Rotor
                    rotor = Rotor.learn(sa, sb)
                    predicted_vec = rotor.apply(sc)
                    
                    # 注册预测结果为新符号（总是创建新符号，而不是匹配现有的）
                    d_name = f"^{c}_via_{a}{b}"
                    _engine.add_symbol(d_name, "")
                    _engine.symbols[d_name].center = predicted_vec / np.linalg.norm(predicted_vec)
                    best_name = d_name
                    best_sim = 1.0
                    
                    # 辅助：这个新符号在语义空间中与哪些已知概念相近
                    nearby = _engine.semantic_field_map(predicted_vec, top_k=3)
                    nearby_str = ", ".join(f"{n}({s:.2f})" for n, s in nearby if n not in (a, b, c, d_name))
                    
                    return {
                        "text": (f"类比 {a}:{b} :: {c}:{d_name} "
                                f"(语义邻近: {nearby_str})"),
                        "data": {"a": a, "b": b, "c": c, "result": d_name, 
                                 "nearby": [n for n, _ in nearby if n not in (a, b, c, d_name)]},
                        "confidence": 1.0,
                    }
            except Exception:
                pass
    
    # 检测 "A和B有什么区别" 这种（可以转为类比查询）
    return None


def _try_compare(query: str) -> Optional[Dict]:
    """尝试匹配概念对比"""
    import re
    
    # 模式和B的区别/关系 (带"有什么"或直接"的")
    m = re.search(r'(\w+)\s*和\s*(\w+)\s*有什么(区别|关系|共同点|不同)', query)
    if not m:
        m = re.search(r'(\w+)\s*和\s*(\w+)\s*(的区别|的关系|的异同)', query)
    if not m:
        m = re.search(r'(\w+)\s*(vs|versus|与|对比)\s*(\w+)', query)
    
    if m:
        a, b = m.group(1), m.group(2)
        
        # 确保概念存在
        for name in [a, b]:
            if name not in _engine.symbols:
                _engine.add_symbol(name, "")
        
        sim = float(_engine.symbols[a].center @ _engine.symbols[b].center)
        
        # 生成对比文本
        if sim > 0.5:
            relation = "语义相近"
        elif sim > 0.1:
            relation = "语义相关"
        elif sim > -0.1:
            relation = "语义无关（正交）"
        else:
            relation = "语义对立"
        
        text = (
            f"概念对比: {a} 和 {b}\n"
            f"  语义相似度: {sim:.4f} ({relation})\n"
            f"  Ψ-Semiotics 引擎分析\n"
        )
        
        return {
            "text": text,
            "similarity": sim,
        }
    
    return None


def _try_field(query: str) -> Optional[Dict]:
    """语义场分析"""
    # 提取核心概念词
    words = query.split()
    core_query = " ".join(words[-3:])  # 取最后几个词
    
    v = _encoder.encode(core_query)
    field = _engine.semantic_field_map(v, top_k=5)
    
    if field:
        text_parts = [f"'{core_query}' 的语义场:"]
        symbols = []
        fields = []
        for name, strength in field:
            text_parts.append(f"  {name}: {strength:.4f}")
            symbols.append(name)
            fields.append({"name": name, "strength": round(strength, 4)})
        
        return {
            "text": "\n".join(text_parts),
            "symbols": symbols,
            "fields": fields,
        }
    
    return None


def _try_concept(query: str) -> Optional[Dict]:
    """概念解释"""
    # 提取可能的概念名
    words = [w for w in query.split() if w.isalpha() and len(w) > 2]
    
    found = []
    for word in words:
        if word not in _engine.symbols:
            _engine.add_symbol(word, "")
        found.append(word)
    
    if found:
        text_parts = [f"概念分析 ({', '.join(found[:3])}):"]
        for name in found[:3]:
            field = _engine.semantic_field_map(_engine.symbols[name].center, top_k=3)
            related = [(n, round(s, 3)) for n, s in field if n != name][:3]
            rel_str = ", ".join(f"{n}({s:.4f})" for n, s in related)
            text_parts.append(f"  {name}: 最近概念 → {rel_str}")
        
        return {
            "text": "\n".join(text_parts),
            "symbols": found[:3],
        }
    
    return None


def quick_psi_check(query: str) -> Dict:
    """
    快速检查: 这条查询是否应该由 Ψ-Semiotics 引擎处理？
    
    返回 {"should_route": bool, "reason": str, "domain_score": float}
    """
    try:
        from intent_classifier import IntentClassifier
        classifier = IntentClassifier()
        domain, score = classifier.classify(query)
        return {
            "should_route": domain == "psi",
            "reason": f"分类器输出: domain={domain}, score={score:.2f}",
            "domain_score": score,
        }
    except Exception:
        pass
    
    # 降级: 关键词匹配
    psi_keywords = [
        "类比", "analogy", "符号", "semiotic", "semiotics",
        "概念对比", "语义空间", "区别和联系",
        "转子", "rotor",
    ]
    # 正则模式匹配（降级版）
    import re
    psi_patterns = [
        r'.*和.*有什么(区别|关系|共同点)',
        r'.*和.*的(区别|关系|异同)',
        r'\w+:\w+\s*::\s*\w+:\?',  # a:b :: c:?
        r'.*(vs|versus).*',
        r'.*consciousness.*quantum.*',
        r'.*什么是.*',  # "什么是consciousness"
        r'.*语义.*(关系|空间|网络)',
    ]
    
    ql = query.lower()
    for kw in psi_keywords:
        if kw.lower() in ql:
            return {"should_route": True, "reason": f"关键词匹配: {kw}", "domain_score": 0.7}
    
    for pat in psi_patterns:
        if re.search(pat, ql, re.IGNORECASE):
            return {"should_route": True, "reason": f"模式匹配: {pat}", "domain_score": 0.8}
    
    return {"should_route": False, "reason": "无匹配", "domain_score": 0.0}


# ── 工具描述（供 Hermes 使用）──

TOOL_DESCRIPTION = {
    "name": "psi_semiotics_respond",
    "description": (
        "使用 Ψ-Semiotics 引擎直接回答符号学/类比/概念对比类问题，"
        "不经过 LLM token 生成。支持: 类比推理、概念对比、语义场分析、概念解释。"
        "适用查询: 'king和queen有什么区别', '意识跟量子有什么关系', "
        "'king:queen :: man:?'"
    ),
    "parameters": {
        "query": "自然语言查询",
        "verbose": "是否返回详细置信度信息 (默认 False)",
    },
}


# ── 自测试 ──

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    
    print("=" * 60)
    print("  Ψ-Semiotics 回应器测试")
    print("=" * 60)
    
    tests = [
        "king 和 queen 有什么区别",
        "king:queen :: man:?",
        "consciousness quantum self",
        "analogy是什么",
        "hi 你好",
    ]
    
    for test in tests:
        print(f"\n--- 查询: {test} ---")
        
        # 先检查是否应该路由
        check = quick_psi_check(test)
        print(f"  路由检查: {'✅ PSI' if check['should_route'] else '❌ 非PSI'} ({check['reason']})")
        
        if check['should_route']:
            result = psi_respond(test, verbose=True)
            print(f"  引擎类型: {result.get('type', '?')}")
            print(f"  延迟: {result['latency_ms']}ms")
            print(f"  回答:\n{result.get('text', '')[:300]}")
    
    print(f"\n✅ 测试完成")
