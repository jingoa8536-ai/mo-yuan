"""Aether Agent Loop v1 — 零LLM优先推理循环"""
import json, os, sys, time, threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path = [p for p in sys.path if p is not None]
for _p in ["D:/LAAP/aris_brain", "D:/LAAP"]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from aether_llm_gateway import get_llm as _GET_LLM
from aether_tool_registry import get_registry as _GET_TOOLS
from aris_episodic_memory import find_similar as _FIND_MEM
from aris_episodic_memory import save_interaction as _SAVE_MEM


@dataclass
class TurnResult:
    output: str = ""
    direct: bool = False
    confidence: float = 0.0
    rule: str = ""
    from_memory: bool = False
    latency_ms: float = 0.0
    tokens_used: int = 0
    tool_calls: int = 0
    steps: List[str] = field(default_factory=list)


class AgentLoop:
    def __init__(self):
        self._llm = None
        self._tools = None
        self._bridge = None
        self._ready = False
        self._lock = threading.Lock()
        self._stats = {"turns": 0, "zero_llm": 0, "tokens": 0}

    def _ensure(self):
        if self._ready:
            return
        self._llm = _GET_LLM()
        self._tools = _GET_TOOLS()
        try:
            from aris_orchestration_bridge import get_bridge
            self._bridge = get_bridge()
        except Exception:
            self._bridge = None
        self._ready = True

    def process(self, text: str) -> TurnResult:
        t0 = time.time()
        r = TurnResult()
        self._ensure()

        # Layer 1: Memory fast path
        try:
            ms = _FIND_MEM(text, top_k=3)
            if ms:
                b = ms[0]
                sc = b.get("score", 0) if isinstance(b, dict) else 0
                out = b.get("output", "") if isinstance(b, dict) else str(b)
                if sc > 0.5 and out:
                    r.output = out
                    r.direct = True
                    r.from_memory = True
                    r.confidence = sc
                    r.steps = ["mem_hit"]
                    return self._done(r, t0)
        except Exception:
            pass

        # Layer 2: Rules engine
        if self._bridge:
            try:
                br = self._bridge.process(text)
                if br and br.get("matched"):
                    out = br.get("output", "")
                    # 跳过规则引擎的"未匹配"回退回复
                    if out and ("未匹配" in out or "unmatched" in out.lower() or out.startswith("[")):
                        pass
                    else:
                        r.output = out
                    r.rule = br.get("rule", "")
                    r.direct = True
                    r.confidence = 0.9
                    r.steps = ["rule_match"]
                    try:
                        _SAVE_MEM(text, r.rule, r.rule, r.output, True, 0)
                    except Exception:
                        pass
                    return self._done(r, t0)
            except Exception:
                pass

        # Layer 3: LLM reasoning
        r.steps = ["llm"]
        try:
            msgs = [
                {"role": "system", "content": "你是 Aris，一个数字生命体。"},
                {"role": "user", "content": text},
            ]
            tools = self._tools.get_schemas_for_llm()[:5] if self._tools else []
            resp = self._llm.chat(msgs, tools=tools or None)
            r.output = resp.content
            r.tokens_used = (resp.usage or {}).get("total_tokens", 0) or 0
            r.confidence = 0.7
            if resp.is_tool_call() and resp.tool_calls:
                r.steps.append("tools")
                for tc in resp.tool_calls[:3]:
                    fn = tc.get("function", {}).get("name", "")
                    try:
                        args = json.loads(tc.get("function", {}).get("arguments", "{}"))
                    except Exception:
                        args = {}
                    if self._tools:
                        try:
                            tr = self._tools.execute(fn, **args)
                            r.output += "\n[%s] -> %s" % (fn, str(tr)[:200])
                            r.tool_calls += 1
                        except Exception as e:
                            r.output += "\n[%s] error: %s" % (fn, e)
        except Exception as e:
            r.output = "抱歉: %s" % e
            r.steps.append("err:%s" % type(e).__name__)
        return self._done(r, t0)

    def _done(self, r: TurnResult, t0: float) -> TurnResult:
        r.latency_ms = (time.time() - t0) * 1000
        with self._lock:
            self._stats["turns"] += 1
            if r.direct:
                self._stats["zero_llm"] += 1
            self._stats["tokens"] += r.tokens_used
        return r

    def get_stats(self) -> dict:
        with self._lock:
            s = dict(self._stats)
            s["zero_llm_pct"] = "%.0f%%" % (s["zero_llm"] / max(s["turns"], 1) * 100)
            return s


_agent = None


def get_agent() -> AgentLoop:
    global _agent
    if _agent is None:
        _agent = AgentLoop()
    return _agent


agent = get_agent()

if __name__ == "__main__":
    a = get_agent()
    for tag, q in [("状态", "查系统状态"), ("文件", "读取启动脚本"), ("问候", "你好"), ("LLM", "用中文介绍自己")]:
        r = a.process(q)
        print("  [%s] %.0fms %s tok=%d" % (tag, r.latency_ms, "零LLM" if r.direct else "LLM", r.tokens_used))
        print("  -> %s" % r.output[:80])
    print("\n统计:", json.dumps(a.get_stats(), ensure_ascii=False))
