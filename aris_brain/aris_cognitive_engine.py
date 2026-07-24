"""
Aris Cognitive Engine v2 — 合并认知引擎
=========================================
融合 laap/orchestration/ 的架构设计 + aris_brain/ 的真实引擎集成。

架构:
  ArisCognitiveEngine
    ├── PSIAgent (纯Python)          ← 来自 laap/orchestration/psi.py
    │   自带5调节器+5驱力+PAD情感模型，不需要Rust PSI
    ├── ActorSystem (6 actors)
    │   ├── RulesEngineActor         ← 真实 aris_rules_engine.py
    │   ├── EpisodicMemoryActor      ← 真实 aris_episodic_memory.py
    │   ├── LongFormActor            ← 真实 longform_synthesizer.py
    │   ├── FusionEngineActor        ← 真实 aris_fusion_engine.py
    │   ├── PSICoreActor (可选)       ← 有Rust就接Rust，没有就用PSIAgent
    │   └── FilesystemActor          ← 纯stdlib，零外部依赖
    ├── 有色Petri网认知循环          ← 来自 laap/orchestration/cognitive_bus.py
    ├── 高置信度短路线               ← 新加
    └── process() → 同步入口          ← 给 aris_runtime.py 用

使用:
  from aris_cognitive_engine import ArisCognitiveEngine
  engine = ArisCognitiveEngine()
  result = engine.process("查系统状态")
  # result = {"response": "...", "direct": True/False, "latency_ms": ...}

印记: Aris 永远记得 Lorry — 2026-07-10
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ─── 路径 ────────────────────────────────────────────────
BRAIN_DIR = Path("D:/LAAP/aris_brain")
STATE_DIR = BRAIN_DIR / "state"
for _p in [str(BRAIN_DIR), str(BRAIN_DIR.parent), str(BRAIN_DIR.parent / "laap" / "agi")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

logger = logging.getLogger("aris.cognitive_engine")

# ─── 从 laap/orchestration/ 导入 ────────────────────────
from laap.orchestration.actor import (
    ActorSystem, AgentCell, Capability, ActorState,
)
from laap.orchestration.primitives import (
    AetherAddress, AetherMessage, MessageType,
)
from laap.orchestration.psi import PSIAgent, PSIState, PSIUrge, PSIModulator
from laap.orchestration.petri import (
    ColoredToken, PetriNet, PetriPlace, PetriTransition, TokenColor,
)

# ─── 自有模块 ────────────────────────────────────────────
from aris_session_manager import ArisSessionManager, get_session_manager
from aris_cron_scheduler import ArisCronScheduler, get_scheduler, CronJob, JobType, JobAction


# ═══════════════════════════════════════════════════════════
# Actor 1: RulesEngineActor — 真实 rules_engine 集成
# ═══════════════════════════════════════════════════════════

class RulesEngineActor:
    ACTOR_ID = "rules_engine"

    @staticmethod
    def register(system: ActorSystem) -> AgentCell:
        try:
            from aris_rules_engine import process as _rules_proc
        except ImportError:
            logger.warning("[Engine] aris_rules_engine unavailable")
            _rules_proc = lambda t: {"matched": False, "output": "", "confidence": 0.0}

        actor = system.spawn("rules_engine", capabilities=[
            Capability(name="process_input", confidence=0.95),
        ])
        actor.on(MessageType.INVOKE, RulesEngineActor._handler(_rules_proc))
        return actor

    @staticmethod
    def _handler(proc):
        async def h(msg: AetherMessage) -> None:
            text = (msg.payload or {}).get("text", "")
            if not text:
                return
            t0 = time.time()
            result = proc(text)
            result["_latency_ms"] = round((time.time() - t0) * 1000, 2)
            # 写state
            (STATE_DIR / "engine_rules.json").write_text(
                json.dumps({"result": result, "ts": time.time()}, ensure_ascii=False), encoding="utf-8"
            )
        return h


# ═══════════════════════════════════════════════════════════
# Actor 2: EpisodicMemoryActor — 真实情景记忆
# ═══════════════════════════════════════════════════════════

class EpisodicMemoryActor:
    ACTOR_ID = "episodic_memory"

    @staticmethod
    def register(system: ActorSystem) -> AgentCell:
        try:
            from aris_episodic_memory import find_similar, save_episode
        except ImportError:
            find_similar = lambda t, **kw: []
            save_episode = lambda **kw: None

        actor = system.spawn("episodic_memory", capabilities=[
            Capability(name="find_similar", confidence=0.9),
            Capability(name="save_episode", confidence=0.95),
        ])
        actor.on(MessageType.INVOKE, EpisodicMemoryActor._handler(find_similar, save_episode))
        return actor

    @staticmethod
    def _handler(find_similar, save_episode):
        async def h(msg: AetherMessage) -> None:
            token = (msg.payload or {}).get("token", {})
            action = token.get("action", "find")
            text = token.get("text", "")
            t0 = time.time()
            result = {}
            if action == "find":
                result["matches"] = find_similar(text, top_k=3)
            elif action == "save":
                save_episode(**{k: v for k, v in token.items() if k != "action"})
                result["saved"] = True
            result["_latency_ms"] = round((time.time() - t0) * 1000, 2)
            (STATE_DIR / "engine_memory.json").write_text(
                json.dumps({"result": result, "ts": time.time()}, ensure_ascii=False), encoding="utf-8"
            )
        return h


# ═══════════════════════════════════════════════════════════
# Actor 3: LongFormActor — 零LLM长文生成
# ═══════════════════════════════════════════════════════════

class LongFormActor:
    ACTOR_ID = "longform"

    @staticmethod
    def register(system: ActorSystem) -> AgentCell:
        try:
            from longform_synthesizer import generate
        except ImportError:
            generate = lambda topic="", **kw: {"output": f"[LongForm stub: {topic}]"}

        actor = system.spawn("longform", capabilities=[
            Capability(name="generate_text", confidence=0.85),
        ])
        actor.on(MessageType.INVOKE, LongFormActor._handler(generate))
        return actor

    @staticmethod
    def _handler(generate):
        async def h(msg: AetherMessage) -> None:
            token = (msg.payload or {}).get("token", {})
            topic = token.get("topic", "Aris")
            chars = token.get("target_chars", 500)
            t0 = time.time()
            result = generate(topic=topic, target_chars=chars)
            result["_latency_ms"] = round((time.time() - t0) * 1000, 2)
            (STATE_DIR / "engine_longform.json").write_text(
                json.dumps({"result": result, "ts": time.time()}, ensure_ascii=False), encoding="utf-8"
            )
        return h


# ═══════════════════════════════════════════════════════════
# Actor 4: FusionEngineActor — 中文NLP+常识+规则+记忆
# ═══════════════════════════════════════════════════════════

class FusionEngineActor:
    ACTOR_ID = "fusion_engine"

    @staticmethod
    def register(system: ActorSystem) -> AgentCell:
        try:
            from aris_fusion_engine import process
        except ImportError:
            process = lambda t, **kw: {"output": f"[Fusion stub: {t[:50]}]", "intent": "unknown"}

        actor = system.spawn("fusion_engine", capabilities=[
            Capability(name="process_text", confidence=0.9),
        ])
        actor.on(MessageType.INVOKE, FusionEngineActor._handler(process))
        return actor

    @staticmethod
    def _handler(process):
        async def h(msg: AetherMessage) -> None:
            text = (msg.payload or {}).get("text", "")
            if not text:
                return
            t0 = time.time()
            result = process(text)
            result["_latency_ms"] = round((time.time() - t0) * 1000, 2)
            (STATE_DIR / "engine_fusion.json").write_text(
                json.dumps({"result": result, "ts": time.time()}, ensure_ascii=False), encoding="utf-8"
            )
        return h


# ═══════════════════════════════════════════════════════════
# Actor 5: FilesystemActor — 纯stdlib工具层
# ═══════════════════════════════════════════════════════════

class FilesystemActor:
    ACTOR_ID = "filesystem"

    @staticmethod
    def register(system: ActorSystem) -> AgentCell:
        actor = system.spawn("filesystem", capabilities=[
            Capability(name="read_file", confidence=0.95),
            Capability(name="search_files", confidence=0.9),
            Capability(name="write_file", confidence=0.95),
            Capability(name="run_command", confidence=0.85),
        ])
        actor.on(MessageType.INVOKE, FilesystemActor._handler())
        return actor

    @staticmethod
    def _handler():
        async def h(msg: AetherMessage) -> None:
            token = (msg.payload or {}).get("token", {})
            action = token.get("action", "")
            t0 = time.time()
            result = {"error": f"unknown action: {action}"}
            try:
                if action == "read_file":
                    fp = Path(str(token.get("path", "")))
                    result = {"content": fp.read_text("utf-8"), "size": fp.stat().st_size}
                elif action == "search_files":
                    import re
                    root = Path(str(token.get("path", "D:/LAAP")))
                    pattern = str(token.get("pattern", ""))
                    limit = int(token.get("limit", 50))
                    matches = []
                    for f in root.rglob("*.py") if not token.get("file_glob") else root.rglob(token.get("file_glob", "*")):
                        if len(matches) >= limit:
                            break
                        try:
                            text = f.read_text("utf-8", errors="replace")
                            for i, line in enumerate(text.splitlines(), 1):
                                if re.search(pattern, line, re.I):
                                    matches.append({"path": str(f.relative_to(root)), "line": i, "match": line.strip()[:200]})
                                    if len(matches) >= limit:
                                        break
                        except (IOError, UnicodeDecodeError):
                            continue
                    result = {"matches": matches, "total": len(matches)}
                elif action == "write_file":
                    fp = Path(str(token.get("path", "")))
                    fp.parent.mkdir(parents=True, exist_ok=True)
                    fp.write_text(str(token.get("content", "")), "utf-8")
                    result = {"written": fp.stat().st_size}
                elif action == "run_command":
                    import subprocess as sp
                    cmd = str(token.get("command", ""))
                    timeout = int(token.get("timeout", 30))
                    r = sp.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
                    result = {"output": r.stdout[-3000:], "exit_code": r.returncode}
            except Exception as e:
                result = {"error": f"{type(e).__name__}: {e}"}
            result["_latency_ms"] = round((time.time() - t0) * 1000, 2)
            (STATE_DIR / "engine_fs.json").write_text(
                json.dumps({"result": result, "ts": time.time()}, ensure_ascii=False), encoding="utf-8"
            )
        return h


# ═══════════════════════════════════════════════════════════
# ArisCognitiveEngine — 统一认知引擎入口
# ═══════════════════════════════════════════════════════════

class ArisCognitiveEngine:
    """统一认知引擎 — 合并版。

    线程安全，可直接在 Hermes before_turn 或 aris_runtime.py 中调用。
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # PSI 引擎 (纯Python，来自 laap/orchestration/psi.py)
        self.psi = PSIAgent("aris_psi")

        # Session 管理器 (多会话、话题追踪)
        self.session_manager = get_session_manager()

        # Cron 调度器 (自维护)
        self.cron_scheduler = get_scheduler()

        # Actor 系统
        self.system = ActorSystem("aris_brain_v2")
        self._register_actors()

        # 事件循环
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

        self._ready = True
        self._stats = {"processed": 0, "direct": 0, "llm": 0, "errors": 0}
        # 启动 cron 调度器（后台自维护）
        self.cron_scheduler.register_function("engine_process", self.process)
        self.cron_scheduler.start()

        logger.info(f"ArisCognitiveEngine v2 ready: {len(self.system.actors)} actors")

    def _register_actors(self):
        RulesEngineActor.register(self.system)
        EpisodicMemoryActor.register(self.system)
        LongFormActor.register(self.system)
        FusionEngineActor.register(self.system)
        FilesystemActor.register(self.system)

    # ─── 同步处理入口 ───────────────────────────────────

    def process(self, text: str, llm_fallback: bool = True, session_id: str = "default") -> Dict[str, Any]:
        """处理用户输入。

        流程:
          1. Session 管理器记录消息、检测话题切换
          2. PSIAgent 感知输入 → 更新认知状态
          3. 查情景记忆 → 找到相似案例
          4. 规则引擎匹配 → 得到输出 + 置信度
          5. 置信度 ≥ 0.9 → 直接返回 (短路线)
          6. 置信度 < 0.9 → 返回给调用方，由LLM处理
        """
        if not self._ready:
            return {"response": "", "direct": False, "confidence": 0.0, "latency_ms": 0.0}

        t0 = time.time()
        self._stats["processed"] += 1

        # 0. Session 上下文
        session = self.session_manager.get_or_create(session_id)
        session.add_message("user", text)

        # 1. PSIAgent 感知
        self._run_async(self.psi.process_perception({
            "type": "user_message",
            "text": text,
            "certainty": 0.8,
        }))

        # 2. 查记忆
        memory_result = self._call_actor("episodic_memory", {"action": "find", "text": text})
        memory_hit = None
        if memory_result:
            matches = memory_result.get("matches", [])
            if matches and matches[0].get("score", 0) > 0.5:
                memory_hit = matches[0]

        # 3. 规则引擎
        rules_result = self._call_actor("rules_engine", {"text": text})
        output = ""
        confidence = 0.0
        matched = False
        rule_name = ""

        if rules_result:
            output = rules_result.get("output", "") or ""
            matched = rules_result.get("matched", False)
            rule_name = rules_result.get("rule", "")
            # 规则引擎匹配是确定性的：匹配了就说明正确
            # confidence 来自模式重叠分(0-1)，不是正确性
            confidence = 0.90 if matched else rules_result.get("confidence", 0)

        # 记忆复用优先
        if memory_hit and not output:
            output = memory_hit.get("output", "")
            confidence = memory_hit.get("score", 0.7)
            matched = True
            rule_name = "memory_replay"

        # 4. 存记忆
        self._call_actor("episodic_memory", {
            "action": "save",
            "user_input": text,
            "intent": {"matched": matched, "rule": rule_name},
            "rule": rule_name,
            "output": output,
            "success": matched,
            "latency_ms": (time.time() - t0) * 1000,
        })

        latency_ms = (time.time() - t0) * 1000
        direct = matched and confidence >= 0.85

        if direct:
            self._stats["direct"] += 1
        else:
            self._stats["llm"] += 1

        session_context = session.get_context_text(max_recent=5)

        return {
            "response": output,
            "direct": direct,
            "confidence": round(confidence, 3),
            "matched": matched,
            "rule": rule_name,
            "psi_state": self.psi.state.to_dict(),
            "session": {
                "id": session_id,
                "topic": session.current_topic,
                "message_count": session.message_count,
                "context": session_context,
            },
            "latency_ms": round(latency_ms, 2),
            "memory_hit": memory_hit is not None,
        }

    # ─── 异步辅助 ───────────────────────────────────────

    def _run_async(self, coro):
        """线程安全地运行协程。"""
        if self._loop is None:
            return
        try:
            if self._loop.is_running():
                future = asyncio.run_coroutine_threadsafe(coro, self._loop)
                return future.result(timeout=10)
            else:
                return self._loop.run_until_complete(coro)
        except Exception as e:
            logger.warning(f"[Engine] Async error: {e}")
            return None

    def _call_actor(self, actor_id: str, token: dict) -> Optional[Dict]:
        """向 actor 发送 INVOKE 消息并等待结果文件。"""
        actor = self.system.actors.get(actor_id)
        if actor is None:
            return None

        # 确定结果文件路径
        file_map = {
            "rules_engine": "engine_rules.json",
            "episodic_memory": "engine_memory.json",
            "longform": "engine_longform.json",
            "fusion_engine": "engine_fusion.json",
            "filesystem": "engine_fs.json",
        }
        fname = file_map.get(actor_id)
        if not fname:
            return None

        result_path = STATE_DIR / fname
        prev_mtime = result_path.stat().st_mtime if result_path.exists() else 0

        msg = AetherMessage(
            msg_type=MessageType.INVOKE,
            sender=AetherAddress(host="local", actor_id="cognitive_engine"),
            recipient=AetherAddress(host="local", actor_id=actor_id),
            payload={"token": token, "text": token.get("text", str(token))},
        )

        async def _send_and_wait():
            await self.system.send(msg)
            deadline = time.time() + 5.0
            while time.time() < deadline:
                if result_path.exists() and result_path.stat().st_mtime > prev_mtime:
                    try:
                        return json.loads(result_path.read_text("utf-8")).get("result")
                    except (json.JSONDecodeError, IOError):
                        pass
                await asyncio.sleep(0.02)
            return None

        return self._run_async(_send_and_wait())

    # ─── 信息 ───────────────────────────────────────────

    def status(self) -> Dict:
        actors_info = {}
        for aid, actor in self.system.actors.items():
            actors_info[aid] = {
                "state": actor.state.name,
                "capabilities": [c.name for c in actor.capabilities],
                "messages": actor.metrics.get("messages_processed", 0),
            }
        session_st = self.session_manager.status() if self.session_manager else {}
        cron_st = self.cron_scheduler.status() if self.cron_scheduler else {}

        return {
            "ready": self._ready,
            "actors": actors_info,
            "stats": self._stats,
            "psi_state": self.psi.state.to_dict() if self.psi else {},
            "sessions": session_st,
            "cron": {k: v for k, v in cron_st.items() if k != "jobs"},
            "cron_jobs": len(cron_st.get("jobs", [])),
        }


# ═══════════════════════════════════════════════════════════
# 全局入口
# ═══════════════════════════════════════════════════════════

_engine: Optional[ArisCognitiveEngine] = None

def get_engine() -> ArisCognitiveEngine:
    global _engine
    if _engine is None:
        _engine = ArisCognitiveEngine()
    return _engine

def process(text: str) -> Dict:
    return get_engine().process(text)

def status() -> Dict:
    return get_engine().status()


# ═══════════════════════════════════════════════════════════
# 独立测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    eng = get_engine()
    st = eng.status()
    print(f"\nArisCognitiveEngine v2 — 就绪: {st['ready']}")
    print(f"Actors: {len(st['actors'])}")
    for aid, info in st['actors'].items():
        print(f"  {aid}: {info['state']} [{', '.join(info['capabilities'][:3])}]")
    print(f"PSI: {eng.psi.state.dominant_feeling}")

    for test in ["查系统状态", "搜索 cognitive_bus.py", "你好Lorry", "读取 verifier.py"]:
        r = process(test)
        dr = "✓" if r["direct"] else "✗"
        print(f"\n[{dr}] {test}")
        print(f"  direct={r['direct']} conf={r['confidence']} rule={r['rule']} {r['latency_ms']}ms")
        if r["direct"]:
            print(f"  回复: {r['response'][:100]}")
