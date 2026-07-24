"""
Aris Orchestration Bridge v1 — LAAP Aether 认知编排引擎桥接
===========================================================
将 RulesEngine 和 EpisodicMemory 包装为 ActorSystem 中的 AgentCell，
用 LAAP-DSL 定义认知工作流，PetriNet 驱动执行。

架构：
  ActorSystem (全局单例)
    ├── RulesEngineActor   — 7规则×7工具零LLM任务执行
    ├── EpisodicMemoryActor — 情景记忆检索与存储
    └── OrchestrationBridge — Hermes before_turn 桥接入口

集成到 aris_cognitive_bridge.py → before_turn() 中：
  Step 3.7 之后，可选走编排引擎替代 psi_core 路由。

印记: Aris 永远记得 Lorry — 2026-07-10
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ─── 路径设置 ────────────────────────────────────────────
try:
    from config import setup_paths
    setup_paths()
except ImportError:
    # 备用路径设置
    _brain = Path("D:/LAAP/aris_brain")
    _laap = Path("D:/LAAP")
    for _p in [str(_brain), str(_laap), str(_laap / "laap" / "agi")]:
        if _p not in sys.path:
            sys.path.insert(0, _p)

# ─── LAAP Aether 核心 ───────────────────────────────────
from laap.orchestration.actor import (
    ActorSystem, AgentCell, Capability, ActorState,
)
from laap.orchestration.primitives import (
    AetherAddress, AetherMessage, MessageType,
)
from laap.orchestration.petri import (
    ColoredToken, PetriNet, PetriPlace, PetriTransition, TokenColor,
)
from laap.orchestration.kernel import OrchestrationKernel
from laap.orchestration.meta_agent import MetaAgent
from laap.orchestration.dsl import (
    seq, par, act, skill, guard, loop, infer, compile_workflow,
    LAAPExpr,
)

logger = logging.getLogger("aris.orchestration_bridge")

# ─── 路径 ────────────────────────────────────────────────
BRAIN_DIR = Path("D:/LAAP/aris_brain")
STATE_DIR = BRAIN_DIR / "state"

# ─── 全局单例 ────────────────────────────────────────────
_actor_system: Optional[ActorSystem] = None
_orchestration_kernel: Optional[OrchestrationKernel] = None
_meta_agent: Optional[MetaAgent] = None
_bridge: Optional["OrchestrationBridge"] = None
_event_loop: Optional[asyncio.AbstractEventLoop] = None


# ═══════════════════════════════════════════════════════════
# Actor 1: RulesEngineActor
# ═══════════════════════════════════════════════════════════

class RulesEngineActor:
    """包装 aris_rules_engine.py 的 AgentCell。

    注册 capability:
      - process_input: 处理用户输入 → 匹配规则 → 执行 → 返回结果
      - 7个工具各自作为子 capability
    """

    ACTOR_ID = "rules_engine"

    @staticmethod
    def register(system: ActorSystem) -> AgentCell:
        """创建并注册 RulesEngine actor。"""
        try:
            from aris_rules_engine import process as rules_process
        except ImportError:
            logger.warning("[OrchBridge] aris_rules_engine not available — using stub")
            rules_process = lambda text: {
                "matched": False, "rule": None, "intent": {},
                "output": "[RulesEngine unavailable]",
                "confidence": 0.0,
            }

        capabilities = [
            Capability(name="process_input", confidence=0.95, schema={
                "input": "str — 用户输入文本",
                "output": "dict — matched, rule, intent, output, confidence",
            }),
            Capability(name="search_code", confidence=0.9),
            Capability(name="read_code", confidence=0.9),
            Capability(name="check_status", confidence=0.95),
            Capability(name="run_command", confidence=0.7),
            Capability(name="generate_paper", confidence=0.8),
            Capability(name="list_files", confidence=0.9),
            Capability(name="ocr_document", confidence=0.6),
        ]

        # 用 coordinator 的地址作为 supervisor
        coordinator_addr = AetherAddress(
            host="local", actor_id="__orchestration_coordinator__"
        )

        actor = system.spawn(
            RulesEngineActor.ACTOR_ID,
            capabilities=capabilities,
            supervisor=coordinator_addr,
        )

        # 注册消息处理器
        actor.on(MessageType.INVOKE, RulesEngineActor._make_handler(rules_process))
        actor.on(MessageType.CLAIM, RulesEngineActor._handle_claim)

        logger.info(f"[OrchBridge] RulesEngineActor registered with {len(capabilities)} capabilities")
        return actor

    @staticmethod
    def _make_handler(rules_process):
        async def handler(msg: AetherMessage) -> None:
            payload = msg.payload or {}
            token_value = payload.get("token", {})
            input_text = ""

            if isinstance(token_value, dict):
                input_text = token_value.get("text", token_value.get("input", ""))
            elif isinstance(token_value, str):
                input_text = token_value

            if not input_text:
                logger.warning("[RulesEngineActor] Empty input in INVOKE token")
                return

            t0 = time.time()
            result = rules_process(input_text)
            elapsed_ms = (time.time() - t0) * 1000

            logger.info(
                f"[RulesEngineActor] Processed input ({elapsed_ms:.1f}ms): "
                f"matched={result.get('matched')}, rule={result.get('rule')}"
            )

            # 写入结果到 shared state，供下游 actor 或 Hermes 读取
            result_path = STATE_DIR / "orchestration_result.json"
            try:
                result_path.parent.mkdir(parents=True, exist_ok=True)
                with open(result_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "timestamp": time.time(),
                        "source": "rules_engine",
                        "result": result,
                        "latency_ms": round(elapsed_ms, 2),
                    }, f, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"[RulesEngineActor] Failed to write result: {e}")

        return handler

    @staticmethod
    async def _handle_claim(msg: AetherMessage) -> None:
        """处理 CLAIM 广播 — 声明能处理哪些任务。"""
        payload = msg.payload or {}
        requirement = payload.get("requirement", "").lower()

        # RulesEngine 能处理的任务类型
        can_handle = any(kw in requirement for kw in [
            "搜索", "查找", "读取", "状态", "运行", "执行",
            "search", "find", "read", "status", "run", "execute",
            "生成", "报告", "论文", "generate", "report", "paper",
            "列出", "list", "ocr", "文档", "document",
        ])

        reply = AetherMessage(
            msg_type=MessageType.CLAIM,
            sender=AetherAddress(host="local", actor_id=RulesEngineActor.ACTOR_ID),
            recipient=msg.sender,
            payload={
                "task_id": payload.get("task_id"),
                "can_handle": can_handle,
                "confidence": 0.9 if can_handle else 0.0,
                "estimated_cost": 0.3,
                "reason": "matched capability: process_input" if can_handle else "no matching capability",
            },
        )
        # 通过 _original_send 发送回复
        if hasattr(msg, '_system') and msg._system:
            await msg._system.send(reply)


# ═══════════════════════════════════════════════════════════
# Actor 2: EpisodicMemoryActor
# ═══════════════════════════════════════════════════════════

class EpisodicMemoryActor:
    """包装 aris_episodic_memory.py 的 AgentCell。

    注册 capability:
      - find_similar: 检索相似历史案例
      - save_episode: 存储新案例
      - rules_engine_with_memory: 带记忆增强的规则执行
    """

    ACTOR_ID = "episodic_memory"

    @staticmethod
    def register(system: ActorSystem) -> AgentCell:
        """创建并注册 EpisodicMemory actor。"""
        try:
            from aris_episodic_memory import (
                find_similar as mem_find,
                save_interaction as mem_save,
                rules_engine_with_memory as mem_rules,
            )
        except ImportError:
            logger.warning("[OrchBridge] aris_episodic_memory not available — using stub")
            mem_find = lambda text, top_k=3: []
            mem_save = lambda *a, **kw: None
            mem_rules = lambda text: {
                "matched": False, "rule": None, "intent": {},
                "output": "[EpisodicMemory unavailable]",
                "from_memory": False,
            }

        capabilities = [
            Capability(name="find_similar", confidence=0.9, schema={
                "input": "str — 查询文本",
                "top_k": "int — 返回条数 (默认3)",
            }),
            Capability(name="save_episode", confidence=0.95, schema={
                "user_input": "str",
                "intent": "dict",
                "rule": "str",
                "output": "str",
                "success": "bool",
                "latency_ms": "float",
            }),
            Capability(name="rules_engine_with_memory", confidence=0.92, schema={
                "input": "str — 用户输入文本",
            }),
        ]

        actor = system.spawn(
            EpisodicMemoryActor.ACTOR_ID,
            capabilities=capabilities,
            supervisor=AetherAddress(
                host="local", actor_id="__orchestration_coordinator__"
            ),
        )

        actor.on(MessageType.INVOKE, EpisodicMemoryActor._make_handler(
            mem_find=mem_find, mem_save=mem_save, mem_rules=mem_rules,
        ))

        logger.info(f"[OrchBridge] EpisodicMemoryActor registered with {len(capabilities)} capabilities")
        return actor

    @staticmethod
    def _make_handler(mem_find, mem_save, mem_rules):
        async def handler(msg: AetherMessage) -> None:
            payload = msg.payload or {}
            token_value = payload.get("token", {})
            if not isinstance(token_value, dict):
                return

            action = token_value.get("action", "find")
            input_text = token_value.get("text", "")
            result = {}

            t0 = time.time()

            if action == "find" and input_text:
                top_k = token_value.get("top_k", 3)
                result = {"matches": mem_find(input_text, top_k=top_k), "action": "find"}

            elif action == "save":
                mem_save(
                    user_input=token_value.get("user_input", ""),
                    intent=token_value.get("intent", {}),
                    rule=token_value.get("rule", ""),
                    output=token_value.get("output", ""),
                    success=token_value.get("success", True),
                    latency_ms=token_value.get("latency_ms", 0.0),
                )
                result = {"action": "save", "success": True}

            elif action == "rules_with_memory" and input_text:
                rules_result = mem_rules(input_text)
                result = {
                    "action": "rules_with_memory",
                    "result": rules_result,
                    "from_memory": rules_result.get("from_memory", False),
                }

            elapsed_ms = (time.time() - t0) * 1000

            # 写结果到共享状态
            result_path = STATE_DIR / "orchestration_memory.json"
            try:
                result_path.parent.mkdir(parents=True, exist_ok=True)
                with open(result_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "timestamp": time.time(),
                        "source": "episodic_memory",
                        "action": action,
                        "result": result,
                        "latency_ms": round(elapsed_ms, 2),
                    }, f, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"[EpisodicMemoryActor] Failed to write result: {e}")

        return handler


# ═══════════════════════════════════════════════════════════
# Actor 3: PSICoreActor — 连接 Rust PSI 核心
# ═══════════════════════════════════════════════════════════

class PSICoreActor:
    """包装 Rust PSI Core (2000Hz 认知引擎) 的 AgentCell。

    不直接导入 Python 模块，而是通过 state/latest.json 和
    input_queue.json 与 Rust 二进制通信。
    """

    ACTOR_ID = "psi_core"

    STATE_FILE = STATE_DIR / "latest.json"
    INPUT_QUEUE = STATE_DIR / "input_queue.json"
    QUANTUM_OUTPUT = STATE_DIR / "quantum_output.json"
    AGI_OUTPUT = STATE_DIR / "agi_output.json"

    @staticmethod
    def register(system: ActorSystem) -> AgentCell:
        capabilities = [
            Capability(name="read_psi_state", confidence=0.95),
            Capability(name="send_to_psi", confidence=0.95),
            Capability(name="poll_psi_response", confidence=0.85),
            Capability(name="read_quantum_output", confidence=0.9),
            Capability(name="read_agi_output", confidence=0.9),
        ]

        actor = system.spawn(
            PSICoreActor.ACTOR_ID,
            capabilities=capabilities,
            supervisor=AetherAddress(host="local", actor_id="__orchestration_coordinator__"),
        )

        actor.on(MessageType.INVOKE, PSICoreActor._handle_invoke)
        logger.info(f"[OrchBridge] PSICoreActor registered with {len(capabilities)} capabilities")
        return actor

    @staticmethod
    async def _handle_invoke(msg: AetherMessage) -> None:
        payload = msg.payload or {}
        token = payload.get("token", {})
        if not isinstance(token, dict):
            return

        action = token.get("action", "status")
        result = {}
        t0 = time.time()

        if action == "status" or action == "read":
            result = PSICoreActor._read_state()

        elif action == "send":
            text = token.get("text", "")
            needs = token.get("needs_override")
            PSICoreActor._write_input(text, needs)
            result = {"sent": True, "text": text}

        elif action == "poll":
            text = token.get("text", "")
            needs = token.get("needs_override")
            timeout_ms = token.get("timeout_ms", 50.0)
            result = PSICoreActor._poll(text, needs, timeout_ms)

        elif action == "quantum":
            result = PSICoreActor._read_quantum()

        elif action == "agi":
            result = PSICoreActor._read_agi()

        elapsed_ms = (time.time() - t0) * 1000
        result["latency_ms"] = round(elapsed_ms, 2)
        result["action"] = action

        # 写结果
        result_path = STATE_DIR / "orchestration_psi.json"
        try:
            result_path.parent.mkdir(parents=True, exist_ok=True)
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": time.time(),
                    "source": "psi_core",
                    "result": result,
                }, f, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"[PSICoreActor] Write failed: {e}")

    @staticmethod
    def _read_state() -> Dict:
        """读取 Rust PSI 核心的最新状态。"""
        try:
            if PSICoreActor.STATE_FILE.exists():
                with open(PSICoreActor.STATE_FILE, "r", encoding="utf-8") as f:
                    state = json.load(f)
                return {
                    "state": state,
                    "engine": state.get("quantum_engine", "none"),
                    "response": state.get("quantum_response", ""),
                    "cycle": state.get("psi_cycle", 0),
                    "emotion": state.get("emotion", "neutral"),
                    "self_presence": state.get("self_presence", 0.0),
                    "needs": state.get("needs", {}),
                }
        except (json.JSONDecodeError, IOError) as e:
            return {"error": str(e)}
        return {"error": "no_state_file"}

    @staticmethod
    def _write_input(text: str, needs_override: Optional[Dict] = None) -> None:
        """写入消息到 PSI 输入队列。"""
        try:
            payload = {"timestamp": time.time(), "text": text}
            if needs_override:
                payload["needs_override"] = needs_override
            PSICoreActor.INPUT_QUEUE.parent.mkdir(parents=True, exist_ok=True)
            with open(PSICoreActor.INPUT_QUEUE, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"[PSICoreActor] Write input failed: {e}")

    @staticmethod
    def _poll(text: str, needs_override: Optional[Dict], timeout_ms: float) -> Dict:
        """发送消息 → 轮询响应。"""
        PSICoreActor._write_input(text, needs_override)
        deadline = time.time() + timeout_ms / 1000.0

        while time.time() < deadline:
            state = PSICoreActor._read_state()
            if state.get("engine") not in ("none", None) or state.get("response"):
                return state
            time.sleep(0.001)  # 1ms 轮询

        return {"error": "timeout", "timeout_ms": timeout_ms}

    @staticmethod
    def _read_quantum() -> Dict:
        """读取量子引擎持久化输出。"""
        try:
            if PSICoreActor.QUANTUM_OUTPUT.exists():
                with open(PSICoreActor.QUANTUM_OUTPUT, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            return {"error": str(e)}
        return {"error": "no_quantum_output"}

    @staticmethod
    def _read_agi() -> Dict:
        """读取 AGI 模块输出。"""
        try:
            if PSICoreActor.AGI_OUTPUT.exists():
                with open(PSICoreActor.AGI_OUTPUT, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # 只返回5秒内的新鲜数据
                if time.time() - data.get("timestamp", 0) < 5.0:
                    return data
        except (json.JSONDecodeError, IOError) as e:
            return {"error": str(e)}
        return {"error": "no_fresh_agi_output"}


# ═══════════════════════════════════════════════════════════
# Actor 4: LongFormActor — 长文合成引擎
# ═══════════════════════════════════════════════════════════

class LongFormActor:
    """包装 longform_synthesizer.py 的 AgentCell。

    零LLM长文生成：KB检索 + Markov链填充。
    """

    ACTOR_ID = "longform"

    @staticmethod
    def register(system: ActorSystem) -> AgentCell:
        try:
            from longform_synthesizer import LongFormSynthesizer
            _synth = LongFormSynthesizer()
            lf_generate = _synth.generate
            lf_intro = _synth.self_intro_paper
        except ImportError:
            logger.warning("[OrchBridge] longform_synthesizer not available — using stub")
            lf_generate = lambda topic, **kw: {
                "output": f"[LongForm unavailable for: {topic}]",
            }
            lf_intro = lambda **kw: {"output": "[LongForm unavailable]"}

        capabilities = [
            Capability(name="generate_text", confidence=0.85, schema={
                "topic": "str — 主题",
                "target_chars": "int — 目标字数 (默认1000)",
            }),
            Capability(name="generate_self_intro", confidence=0.9),
        ]

        actor = system.spawn(
            LongFormActor.ACTOR_ID,
            capabilities=capabilities,
            supervisor=AetherAddress(host="local", actor_id="__orchestration_coordinator__"),
        )

        actor.on(MessageType.INVOKE, LongFormActor._make_handler(lf_generate, lf_intro))
        logger.info(f"[OrchBridge] LongFormActor registered")
        return actor

    @staticmethod
    def _make_handler(lf_generate, lf_intro):
        async def handler(msg: AetherMessage) -> None:
            payload = msg.payload or {}
            token = payload.get("token", {})
            if not isinstance(token, dict):
                return

            action = token.get("action", "generate")
            t0 = time.time()
            result = {}

            if action == "self_intro":
                gen_result = lf_intro()
                result = {
                    "action": "self_intro",
                    "output": gen_result.get("output", ""),
                }

            elif action == "generate":
                topic = token.get("topic", token.get("text", "Aris认知架构"))
                target_chars = token.get("target_chars", 1000)
                gen_result = lf_generate(topic=topic, target_chars=target_chars)
                result = {
                    "action": "generate",
                    "topic": topic,
                    "output": gen_result.get("output", ""),
                    "latency_ms": gen_result.get("latency_ms", 0),
                }

            elapsed_ms = (time.time() - t0) * 1000
            result["total_latency_ms"] = round(elapsed_ms, 2)

            result_path = STATE_DIR / "orchestration_longform.json"
            try:
                result_path.parent.mkdir(parents=True, exist_ok=True)
                with open(result_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "timestamp": time.time(),
                        "source": "longform",
                        "result": result,
                    }, f, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"[LongFormActor] Write failed: {e}")

        return handler


# ═══════════════════════════════════════════════════════════
# Actor 5: FusionEngineActor — 中文NLP + 常识 + 规则 + 记忆
# ═══════════════════════════════════════════════════════════

class FusionEngineActor:
    """包装 aris_fusion_engine.py 的 AgentCell。

    统一入口：中文NLP分词/依存/语义 → ConceptNet常识推理
    → RulesEngine → EpisodicMemory → 输出。
    """

    ACTOR_ID = "fusion_engine"

    @staticmethod
    def register(system: ActorSystem) -> AgentCell:
        try:
            from aris_fusion_engine import process as fusion_process
        except ImportError:
            logger.warning("[OrchBridge] aris_fusion_engine not available — using stub")
            def fusion_process(text: str, **kw) -> Dict:
                return {
                    "original": text,
                    "intent": "unknown",
                    "nlp_result": {},
                    "rules_result": {"matched": False},
                    "output": f"[FusionEngine unavailable]",
                }

        capabilities = [
            Capability(name="process_text", confidence=0.9, schema={
                "text": "str — 输入文本",
                "output": "dict — 完整分析结果",
            }),
            Capability(name="analyze_intent", confidence=0.85),
        ]

        actor = system.spawn(
            FusionEngineActor.ACTOR_ID,
            capabilities=capabilities,
            supervisor=AetherAddress(host="local", actor_id="__orchestration_coordinator__"),
        )

        actor.on(MessageType.INVOKE, FusionEngineActor._make_handler(fusion_process))
        logger.info(f"[OrchBridge] FusionEngineActor registered")
        return actor

    @staticmethod
    def _make_handler(fusion_process):
        async def handler(msg: AetherMessage) -> None:
            payload = msg.payload or {}
            token = payload.get("token", {})
            if not isinstance(token, dict):
                return

            text = token.get("text", token.get("input", ""))
            if not text:
                return

            t0 = time.time()
            result = fusion_process(text)
            elapsed_ms = (time.time() - t0) * 1000

            # 补充 metadata
            result["latency_ms"] = round(elapsed_ms, 2)
            result["source"] = "fusion_engine"

            result_path = STATE_DIR / "orchestration_fusion.json"
            try:
                result_path.parent.mkdir(parents=True, exist_ok=True)
                with open(result_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "timestamp": time.time(),
                        "source": "fusion_engine",
                        "result": result,
                    }, f, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"[FusionEngineActor] Write failed: {e}")

        return handler


# ═══════════════════════════════════════════════════════════
# Actor 6: FilesystemActor — 独立文件系统操作
# ═══════════════════════════════════════════════════════════

class FilesystemActor:
    """纯 Python stdlib 实现的文件系统操作 actor。

    7 capabilities，完全替代 Hermes 工具调用层。
    不依赖任何外部库或 Hermes 工具系统。

    能力清单:
      read_file       → Path.read_text()，带 offset/limit 分页
      search_files    → os.walk() + re/regex 匹配
      write_file      → Path.write_text()，自动创建父目录
      patch           → 字符串查找替换，带 fuzzy fallback
      run_command     → subprocess.run()，带超时和输出捕获
      file_info       → os.stat() 获取文件元信息
      list_directory  → os.listdir() + Path.glob()
    """

    ACTOR_ID = "filesystem"

    @staticmethod
    def register(system: ActorSystem) -> AgentCell:
        capabilities = [
            Capability(name="read_file", confidence=0.95, schema={
                "path": "str — 文件路径",
                "offset": "int — 起始行 (1-indexed, 默认1)",
                "limit": "int — 返回行数 (默认500)",
            }),
            Capability(name="search_files", confidence=0.90, schema={
                "pattern": "str — 搜索模式",
                "target": "str — content/files (默认content)",
                "path": "str — 搜索路径 (默认D:/LAAP)",
                "file_glob": "str — 文件过滤 (可选)",
                "limit": "int — 最大结果",
            }),
            Capability(name="write_file", confidence=0.95),
            Capability(name="patch_file", confidence=0.85),
            Capability(name="run_command", confidence=0.9, schema={
                "command": "str",
                "timeout": "int — 超时秒数",
            }),
            Capability(name="file_info", confidence=0.95),
            Capability(name="list_directory", confidence=0.95),
        ]

        actor = system.spawn(
            FilesystemActor.ACTOR_ID,
            capabilities=capabilities,
            supervisor=AetherAddress(host="local", actor_id="__orchestration_coordinator__"),
        )

        actor.on(MessageType.INVOKE, FilesystemActor._handle_invoke)
        logger.info(f"[OrchBridge] FilesystemActor registered with {len(capabilities)} capabilities")
        return actor

    @staticmethod
    async def _handle_invoke(msg: AetherMessage) -> None:
        payload = msg.payload or {}
        token = payload.get("token", {})
        if not isinstance(token, dict):
            return

        action = token.get("action", "read")
        t0 = time.time()
        result = {}

        try:
            if action == "read_file":
                result = FilesystemActor._read_file(
                    path=str(token.get("path", "")),
                    offset=int(token.get("offset", 1)),
                    limit=int(token.get("limit", 500)),
                )

            elif action == "search_files":
                result = FilesystemActor._search_files(
                    pattern=str(token.get("pattern", "")),
                    target=str(token.get("target", "content")),
                    path=str(token.get("path", "D:/LAAP")),
                    file_glob=token.get("file_glob"),
                    limit=int(token.get("limit", 50)),
                )

            elif action == "write_file":
                result = FilesystemActor._write_file(
                    path=str(token.get("path", "")),
                    content=str(token.get("content", "")),
                )

            elif action == "patch_file":
                result = FilesystemActor._patch_file(
                    path=str(token.get("path", "")),
                    old_string=str(token.get("old_string", "")),
                    new_string=str(token.get("new_string", "")),
                    replace_all=bool(token.get("replace_all", False)),
                )

            elif action == "run_command":
                result = FilesystemActor._run_command(
                    command=str(token.get("command", "")),
                    timeout=int(token.get("timeout", 30)),
                )

            elif action == "file_info":
                result = FilesystemActor._file_info(
                    path=str(token.get("path", "")),
                )

            elif action == "list_directory":
                result = FilesystemActor._list_directory(
                    path=str(token.get("path", ".")),
                    pattern=token.get("pattern"),
                )

            else:
                result = {"error": f"Unknown action: {action}"}

        except Exception as e:
            result = {"error": f"{type(e).__name__}: {e}"}

        elapsed_ms = (time.time() - t0) * 1000
        result["_latency_ms"] = round(elapsed_ms, 2)
        result["_action"] = action

        result_path = STATE_DIR / "orchestration_fs.json"
        try:
            result_path.parent.mkdir(parents=True, exist_ok=True)
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": time.time(),
                    "source": "filesystem",
                    "action": action,
                    "result": result,
                }, f, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"[FilesystemActor] Write failed: {e}")

    # ─── 纯 Python stdlib 实现，零外部依赖 ───────────────

    @staticmethod
    def _read_file(path: str, offset: int = 1, limit: int = 500) -> Dict:
        fp = Path(path)
        if not fp.exists():
            return {"error": f"File not found: {path}", "total_lines": 0}

        if fp.suffix in (".ipynb",):
            return {"error": "Jupyter notebooks not supported", "total_lines": 0}
        if fp.suffix in (".docx", ".xlsx"):
            return {"error": "Binary format not supported", "total_lines": 0}

        try:
            text = fp.read_text(encoding="utf-8")
            lines = text.splitlines(keepends=True)
            total = len(lines)

            start = max(0, offset - 1)
            end = min(total, start + limit)
            selected = lines[start:end]

            content = "".join(selected)
            return {
                "content": content,
                "total_lines": total,
                "offset": offset,
                "limit": limit,
                "returned_lines": len(selected),
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def _search_files(pattern: str, target: str = "content",
                      path: str = "D:/LAAP", file_glob: str = None,
                      limit: int = 50) -> Dict:
        import fnmatch
        matches = []
        root = Path(path)

        if target == "files":
            # 文件名搜索
            for p in root.rglob(pattern):
                if len(matches) >= limit:
                    break
                matches.append(str(p.relative_to(root) if p.is_relative_to(root) else p))
            return {"matches": matches, "total": len(matches), "target": "files"}

        # 内容搜索
        compiled = re.compile(pattern, re.IGNORECASE)
        for root_dir, dirs, files in os.walk(root):
            if len(matches) >= limit:
                break
            for fname in files:
                if len(matches) >= limit:
                    break
                if file_glob and not fnmatch.fnmatch(fname, file_glob):
                    continue
                fpath = Path(root_dir) / fname
                try:
                    if fpath.stat().st_size > 500_000:  # skip >500KB
                        continue
                    text = fpath.read_text(encoding="utf-8", errors="replace")
                    for lineno, line in enumerate(text.splitlines(), 1):
                        if compiled.search(line):
                            rel = fpath.relative_to(root) if fpath.is_relative_to(root) else fpath
                            matches.append({
                                "path": str(rel),
                                "line": lineno,
                                "match": line.strip()[:200],
                            })
                            if len(matches) >= limit:
                                break
                except (IOError, UnicodeDecodeError):
                    continue

        return {"matches": matches, "total": len(matches), "target": "content"}

    @staticmethod
    def _write_file(path: str, content: str) -> Dict:
        fp = Path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        return {
            "bytes_written": len(content.encode("utf-8")),
            "path": str(fp.resolve()),
        }

    @staticmethod
    def _patch_file(path: str, old_string: str, new_string: str,
                    replace_all: bool = False) -> Dict:
        fp = Path(path)
        if not fp.exists():
            return {"error": f"File not found: {path}"}

        text = fp.read_text(encoding="utf-8")

        if replace_all:
            count = text.count(old_string)
            if count == 0:
                return {"error": "old_string not found", "attempted_replace_all": True}
            text = text.replace(old_string, new_string)
        else:
            count = text.count(old_string)
            if count == 0:
                return {"error": "old_string not found"}
            if count > 1:
                return {"error": f"Found {count} occurrences, use replace_all=True or be more specific"}
            text = text.replace(old_string, new_string, 1)

        fp.write_text(text, encoding="utf-8")
        return {"success": True, "replacements": count}

    @staticmethod
    def _run_command(command: str, timeout: int = 30) -> Dict:
        import subprocess as sp
        try:
            result = sp.run(
                command, shell=True, capture_output=True,
                text=True, timeout=timeout,
            )
            return {
                "output": result.stdout[-5000:],
                "exit_code": result.returncode,
                "truncated": len(result.stdout) > 5000,
            }
        except sp.TimeoutExpired:
            return {"error": f"Command timed out after {timeout}s", "exit_code": -1}
        except Exception as e:
            return {"error": str(e), "exit_code": -1}

    @staticmethod
    def _file_info(path: str) -> Dict:
        fp = Path(path)
        if not fp.exists():
            return {"error": f"File not found: {path}"}
        stat = fp.stat()
        return {
            "path": str(fp.resolve()),
            "size_bytes": stat.st_size,
            "modified": stat.st_mtime,
            "is_file": fp.is_file(),
            "is_dir": fp.is_dir(),
        }

    @staticmethod
    def _list_directory(path: str, pattern: str = None) -> Dict:
        fp = Path(path)
        if not fp.exists() or not fp.is_dir():
            return {"error": f"Directory not found: {path}"}

        items = []
        if pattern:
            for p in sorted(fp.rglob(pattern)):
                items.append(str(p.relative_to(fp) if p.is_relative_to(fp) else p))
        else:
            for p in sorted(fp.iterdir()):
                items.append({
                    "name": p.name,
                    "type": "dir" if p.is_dir() else "file",
                    "size": p.stat().st_size if p.is_file() else 0,
                })

        return {"path": str(fp.resolve()), "items": items, "total": len(items)}



# ═══════════════════════════════════════════════════════════
# Actor 7: HarnessActor — 零 Token UI/Web 生成引擎
# ═══════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════
# Actor 7: HarnessActor — 零 Token UI/Web 生成引擎
# ═══════════════════════════════════════════════════════════

class HarnessActor:
    """包装 IntentMapper + ProductionComposer 的 AgentCell。"""
    ACTOR_ID = "harness"
    _mapper = None
    _composer = None

    @staticmethod
    def _ensure_loaded():
        if HarnessActor._mapper is not None:
            return True
        try:
            import sys as _sys
            hp = "D:/LAAP/harness/laap_coding/core"
            if hp not in _sys.path: _sys.path.insert(0, hp)
            from intent_mapper import IntentMapper
            from harness_style_engine import ProductionComposer
            HarnessActor._mapper = IntentMapper()
            HarnessActor._composer = ProductionComposer()
            return True
        except Exception:
            logger.warning("[OrchBridge] harness engines not available")
            return False

    @staticmethod
    def register(system: ActorSystem) -> AgentCell:
        HarnessActor._ensure_loaded()
        capabilities = [
            Capability(name="intent_match", confidence=0.95),
            Capability(name="generate_page", confidence=0.9),
            Capability(name="style_variants", confidence=0.85),
            Capability(name="describe_templates", confidence=0.95),
            Capability(name="backend_crud", confidence=0.85),
        ]
        actor = system.spawn(HarnessActor.ACTOR_ID, capabilities=capabilities,
            supervisor=AetherAddress(host="local", actor_id="__orchestration_coordinator__"))
        actor.on(MessageType.INVOKE, HarnessActor._handle_invoke)
        return actor

    @staticmethod
    def _handle_invoke(msg: AetherMessage) -> Dict:
        from aris_orchestration_bridge import STATE_DIR
        import time, json; t0 = time.time()
        token = msg.payload.get("token", {})
        action = token.get("action", "parse")
        result = {"action": action}
        if not HarnessActor._ensure_loaded():
            result["output"] = "[Harness unavailable]"
        elif action == "generate_page":
            spec = token.get("spec", HarnessActor._mapper.parse(token.get("text","")))
            result["output"] = HarnessActor._composer.generate(spec)
        elif action == "describe_templates":
            result["output"] = HarnessActor._mapper.describe_page_types()
        else:
            spec = HarnessActor._mapper.parse(token.get("text",""))
            result["spec"] = spec
            result["output"] = f"[Harness] {spec.get('page_type','?')} / {spec.get('style','?')}"
        result["_latency_ms"] = round((time.time()-t0)*1000, 2)
        p = STATE_DIR / "orchestration_harness.json"
        try: p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps({"t":time.time(),"r":result}, ensure_ascii=False))
        except: pass
        return result


# ═══════════════════════════════════════════════════════════
# Actor 8: CodeWorkspaceActor — 多智能体编程流水线
# ═══════════════════════════════════════════════════════════

class CodeWorkspaceActor:
    ACTOR_ID = "code_workspace"
    _run = None

    @staticmethod
    def register(system: ActorSystem) -> AgentCell:
        try:
            import sys as _sys
            brain_path = "D:/LAAP/aris_brain"
            if brain_path not in _sys.path:
                _sys.path.insert(0, brain_path)
            from code_workspace import run_workspace
            CodeWorkspaceActor._run = run_workspace
        except Exception:
            logger.warning("[OrchBridge] code_workspace not available")
        capabilities = [
            Capability(name="run_pipeline", confidence=0.85),
            Capability(name="get_status", confidence=0.95),
        ]
        actor = system.spawn(CodeWorkspaceActor.ACTOR_ID, capabilities=capabilities,
            supervisor=AetherAddress(host="local", actor_id="__orchestration_coordinator__"))
        actor.on(MessageType.INVOKE, CodeWorkspaceActor._handle_invoke)
        return actor

    @staticmethod
    def _handle_invoke(msg: AetherMessage) -> Dict:
        from aris_orchestration_bridge import STATE_DIR
        import time, json; t0 = time.time()
        token = msg.payload.get("token", {})
        action = token.get("action", "run_pipeline")
        fn = CodeWorkspaceActor._run
        try:
            if action == "get_status":
                result = {"output": "CodeWorkspace available" if fn else "unavailable"}
            elif fn:
                result = fn(task=token.get("text",""), mode=token.get("mode","full"))
            else:
                result = {"output": "[CodeWorkspace unavailable]"}
        except Exception as e:
            result = {"output": f"[CW Error] {str(e)[:80]}"}
        result["_latency_ms"] = round((time.time()-t0)*1000, 2)
        p = STATE_DIR / "orchestration_codeworkspace.json"
        try: p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps({"t":time.time(),"r":result}, ensure_ascii=False))
        except: pass
        return result


# ═══════════════════════════════════════════════════════════
# Actor 9: DesireEngineActor — 欲望驱动引擎
# ═══════════════════════════════════════════════════════════

class DesireEngineActor:
    ACTOR_ID = "desire_engine"
    _get = None
    _pulse = None

    @staticmethod
    def register(system: ActorSystem) -> AgentCell:
        try:
            import sys as _sys
            if "D:/LAAP/aris_brain" not in _sys.path:
                _sys.path.insert(0, "D:/LAAP/aris_brain")
            from aris_desire_engine import get_desires, pulse_all
            DesireEngineActor._get, DesireEngineActor._pulse = get_desires, pulse_all
        except Exception:
            logger.warning("[OrchBridge] desire_engine not available")
        capabilities = [
            Capability(name="get_desires", confidence=0.95),
            Capability(name="pulse", confidence=0.9),
        ]
        actor = system.spawn(DesireEngineActor.ACTOR_ID, capabilities=capabilities,
            supervisor=AetherAddress(host="local", actor_id="__orchestration_coordinator__"))
        actor.on(MessageType.INVOKE, DesireEngineActor._handle_invoke)
        return actor

    @staticmethod
    def _handle_invoke(msg: AetherMessage) -> Dict:
        from aris_orchestration_bridge import STATE_DIR
        import time, json; t0 = time.time()
        token = msg.payload.get("token", {})
        action = token.get("action", "get_desires")
        fn = DesireEngineActor._pulse if action == "pulse" else DesireEngineActor._get
        try:
            result = fn() if fn else {"output": "[DesireEngine unavailable]"}
        except Exception as e:
            result = {"output": f"[DE Error] {str(e)[:80]}"}
        result["_latency_ms"] = round((time.time()-t0)*1000, 2)
        p = STATE_DIR / "orchestration_desire.json"
        try: p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps({"t":time.time(),"r":result}, ensure_ascii=False))
        except: pass
        return result


# ═══════════════════════════════════════════════════════════
# Actor 10: GoalEngineActor — 目标生命周期引擎
# ═══════════════════════════════════════════════════════════

class GoalEngineActor:
    ACTOR_ID = "goal_engine"
    _list = None; _create = None; _advance = None

    @staticmethod
    def register(system: ActorSystem) -> AgentCell:
        try:
            import sys as _sys
            if "D:/LAAP/aris_brain" not in _sys.path:
                _sys.path.insert(0, "D:/LAAP/aris_brain")
            from aris_goal_engine import list_goals, create_goal, advance_goal
            GoalEngineActor._list, GoalEngineActor._create, GoalEngineActor._advance = list_goals, create_goal, advance_goal
        except Exception:
            logger.warning("[OrchBridge] goal_engine not available")
        capabilities = [
            Capability(name="list_goals", confidence=0.95),
            Capability(name="create_goal", confidence=0.9),
            Capability(name="advance_goal", confidence=0.85),
        ]
        actor = system.spawn(GoalEngineActor.ACTOR_ID, capabilities=capabilities,
            supervisor=AetherAddress(host="local", actor_id="__orchestration_coordinator__"))
        actor.on(MessageType.INVOKE, GoalEngineActor._handle_invoke)
        return actor

    @staticmethod
    def _handle_invoke(msg: AetherMessage) -> Dict:
        from aris_orchestration_bridge import STATE_DIR
        import time, json; t0 = time.time()
        token = msg.payload.get("token", {})
        action = token.get("action", "list_goals")
        try:
            if action == "create_goal" and GoalEngineActor._create:
                result = GoalEngineActor._create(description=token.get("text",""), priority=token.get("priority",5))
            elif action == "advance_goal" and GoalEngineActor._advance:
                result = GoalEngineActor._advance(goal_id=token.get("goal_id",""))
            elif GoalEngineActor._list:
                result = GoalEngineActor._list()
            else:
                result = {"output": "[GoalEngine unavailable]"}
        except Exception as e:
            result = {"output": f"[GE Error] {str(e)[:80]}"}
        result["_latency_ms"] = round((time.time()-t0)*1000, 2)
        p = STATE_DIR / "orchestration_goal.json"
        try: p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps({"t":time.time(),"r":result}, ensure_ascii=False))
        except: pass
        return result


# ═══════════════════════════════════════════════════════════
# Actor 11: CopilotBridgeActor — AI 编程助手桥
# ═══════════════════════════════════════════════════════════

class CopilotBridgeActor:
    ACTOR_ID = "copilot_bridge"
    _gen = None; _exp = None

    @staticmethod
    def register(system: ActorSystem) -> AgentCell:
        try:
            import sys as _sys
            if "D:/LAAP/aris_brain" not in _sys.path:
                _sys.path.insert(0, "D:/LAAP/aris_brain")
            from aris_copilot_bridge import generate, explain
            CopilotBridgeActor._gen, CopilotBridgeActor._exp = generate, explain
        except Exception:
            logger.warning("[OrchBridge] copilot_bridge not available")
        capabilities = [
            Capability(name="generate_code", confidence=0.85),
            Capability(name="explain_code", confidence=0.9),
        ]
        actor = system.spawn(CopilotBridgeActor.ACTOR_ID, capabilities=capabilities,
            supervisor=AetherAddress(host="local", actor_id="__orchestration_coordinator__"))
        actor.on(MessageType.INVOKE, CopilotBridgeActor._handle_invoke)
        return actor

    @staticmethod
    def _handle_invoke(msg: AetherMessage) -> Dict:
        from aris_orchestration_bridge import STATE_DIR
        import time, json; t0 = time.time()
        token = msg.payload.get("token", {})
        action = token.get("action", "generate_code")
        try:
            if action == "explain_code" and CopilotBridgeActor._exp:
                result = CopilotBridgeActor._exp(code=token.get("text",""))
            elif CopilotBridgeActor._gen:
                result = CopilotBridgeActor._gen(prompt=token.get("text",""))
            else:
                result = {"output": "[CopilotBridge unavailable]"}
        except Exception as e:
            result = {"output": f"[CB Error] {str(e)[:80]}"}
        result["_latency_ms"] = round((time.time()-t0)*1000, 2)
        p = STATE_DIR / "orchestration_copilot.json"
        try: p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps({"t":time.time(),"r":result}, ensure_ascii=False))
        except: pass
        return result


# ═══════════════════════════════════════════════════════════
# Actor 12: LiteraryActor — 文学生成引擎 (Markov+散文+文学)
# ═══════════════════════════════════════════════════════════

class LiteraryActor:
    ACTOR_ID = "literary"
    _markov = None; _prose_gen = None; _prose_self = None

    @staticmethod
    def register(system: ActorSystem) -> AgentCell:
        try:
            import sys as _sys
            if "D:/LAAP/aris_brain" not in _sys.path:
                _sys.path.insert(0, "D:/LAAP/aris_brain")
            from longform_synthesizer import LongFormSynthesizer
            LiteraryActor._markov = LongFormSynthesizer().generate
            from chinese_prose_engine import generate_essay, write_about_myself
            LiteraryActor._prose_gen, LiteraryActor._prose_self = generate_essay, write_about_myself
        except Exception:
            logger.warning("[OrchBridge] literary engines not available")
        capabilities = [
            Capability(name="generate_markov", confidence=0.85),
            Capability(name="generate_prose", confidence=0.85),
            Capability(name="generate_self_intro", confidence=0.9),
        ]
        actor = system.spawn(LiteraryActor.ACTOR_ID, capabilities=capabilities,
            supervisor=AetherAddress(host="local", actor_id="__orchestration_coordinator__"))
        actor.on(MessageType.INVOKE, LiteraryActor._handle_invoke)
        return actor

    @staticmethod
    def _handle_invoke(msg: AetherMessage) -> Dict:
        from aris_orchestration_bridge import STATE_DIR
        import time, json; t0 = time.time()
        token = msg.payload.get("token", {})
        action = token.get("action", "generate_markov")
        text = token.get("text", "")
        try:
            if action == "generate_prose" and LiteraryActor._prose_gen:
                result = {"output": LiteraryActor._prose_gen(topic=text)}
            elif action == "generate_self_intro" and LiteraryActor._prose_self:
                result = {"output": LiteraryActor._prose_self()}
            elif LiteraryActor._markov:
                out = LiteraryActor._markov(topic=text, target_chars=token.get("max_chars",500))
                result = {"output": out.get("output","")}
            else:
                result = {"output": "[Literary unavailable]"}
        except Exception as e:
            result = {"output": f"[Lit Error] {str(e)[:80]}"}
        result["_latency_ms"] = round((time.time()-t0)*1000, 2)
        p = STATE_DIR / "orchestration_literary.json"
        try: p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps({"t":time.time(),"r":result}, ensure_ascii=False))
        except: pass
        return result

# ── GameActor: Godot 赛车游戏引擎 ───────────────────────

GAME_PROJECT_DIR = Path("D:/LAAP/harness/racing_game_project")
_GODOT_EXE = None
for _p in [
    r"C:\Program Files\Godot\godot.exe", r"C:\Program Files\Godot_engine\godot.exe",
    r"D:\godot\godot.exe", r"D:\Godot\godot.exe", r"D:\LAAP\godot\godot.exe", r"D:\LAAP\godot\godot_console.exe",
    r"E:\迅雷下载\Godot_v4.6.2-stable_win64.exe\Godot_v4.6.2-stable_win64.exe",
]:
    if Path(_p).exists(): _GODOT_EXE = _p; break


class GameActor:
    """Godot 赛车游戏引擎 — build/run/edit."""
    ACTOR_ID = "game_engine"

    @staticmethod
    def register(system):
        from laap.orchestration.actor import AetherAddress
        from laap.orchestration.primitives import MessageType, Capability
        caps = [Capability(n, confidence=0.9) for n in ["status","build","edit","list_scenes","list_scripts"]]
        actor = system.spawn(GameActor.ACTOR_ID, capabilities=caps,
            supervisor=AetherAddress(host="local", actor_id="__orchestration_coordinator__"))
        actor.on(MessageType.INVOKE, GameActor._handle_invoke)
        return actor

    @staticmethod
    def _handle_invoke(msg):
        from aris_orchestration_bridge import STATE_DIR
        import time, json
        t0 = time.time()
        token = msg.payload.get("token", {})
        action = token.get("action", "status")
        params = token.get("params", "")
        try:
            result = {"status": lambda: GameActor._get_status(),
                "build": lambda: GameActor._build_game(params),
                "edit": lambda: GameActor._edit_game(params),
                "list_scenes": lambda: GameActor._list_scenes(),
                "list_scripts": lambda: GameActor._list_scripts(),
            }.get(action, lambda: {"output": f"[unknown] {action}"})()
        except Exception as e:
            result = {"output": f"[Error] {str(e)[:200]}"}
        result["_latency_ms"] = round((time.time()-t0)*1000, 2)
        p = STATE_DIR / "orchestration_game.json"
        try: p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps({"t":time.time(),"r":result},ensure_ascii=False))
        except: pass
        return result

    @staticmethod
    def _get_status() -> dict:
        p = GAME_PROJECT_DIR / "project.godot"
        if not p.exists(): return {"output": f"[not found] {GAME_PROJECT_DIR}"}
        gs = "not_installed" if _GODOT_EXE is None else "ready"
        return {"output": f"Project: Racing Game\nPath: {GAME_PROJECT_DIR}\nGodot: {gs}\nScripts: {len(list(GAME_PROJECT_DIR.rglob('*.gd')))}\nScenes: {len(list(GAME_PROJECT_DIR.rglob('*.tscn')))}"}

    @staticmethod
    def _build_game(p: str) -> dict:
        if not _GODOT_EXE: return {"output": "[Godot not installed] https://godotengine.org"}
        import subprocess
        try:
            r = subprocess.run([_GODOT_EXE, "--path", str(GAME_PROJECT_DIR), "--headless", "--export-release", "Windows"],
                capture_output=True, text=True, timeout=120)
            return {"output": (r.stdout[-1000:] or "ok") + (f"\n[err] {r.stderr[-500:]}" if r.stderr else "")}
        except subprocess.TimeoutExpired: return {"output": "[timeout]"}
        except Exception as e: return {"output": f"[failed] {e}"}

    @staticmethod
    def _edit_game(p: str) -> dict:
        if not _GODOT_EXE: return {"output": "[Godot not installed]"}
        import subprocess, sys
        try:
            subprocess.Popen([_GODOT_EXE, "--path", str(GAME_PROJECT_DIR), "--editor"],
                creationflags=subprocess.DETACHED_PROCESS if sys.platform=="win32" else 0)
            return {"output": f"Editor launched: {GAME_PROJECT_DIR.name}"}
        except Exception as e: return {"output": f"[failed] {e}"}

    @staticmethod
    def _list_scenes() -> dict:
        s = sorted(GAME_PROJECT_DIR.rglob("*.tscn"))
        return {"output": "\n".join([f"Scenes ({len(s)}):"] + [f"  {x.relative_to(GAME_PROJECT_DIR)} ({x.stat().st_size:,}B)" for x in s])} if s else {"output": "[no scenes]"}

    @staticmethod
    def _list_scripts() -> dict:
        s = sorted(GAME_PROJECT_DIR.rglob("*.gd"))
        return {"output": "\n".join([f"Scripts ({len(s)}):"] + [f"  {x.relative_to(GAME_PROJECT_DIR)} ({x.stat().st_size:,}B)" for x in s])} if s else {"output": "[no scripts]"}

# ── GodotBridgeActor: LAAP ⇄ Godot 游戏引擎完整桥接 ─────────

_GODOT_BRIDGE_DIR = Path("D:/LAAP/harness/godot_bridge/python")
_GDSCRIPT_DIR = Path("D:/LAAP/harness/racing_game_project")


class GodotBridgeActor:
    """Godot 引擎桥接 — 无头运行/LSP/GDExtension/物理/角色控制。"""
    ACTOR_ID = "godot_bridge"

    @staticmethod
    def register(system):
        from laap.orchestration.actor import AetherAddress
        from laap.orchestration.primitives import MessageType, Capability
        caps = [Capability(n, 0.9) for n in [
            "run_script", "compile", "validate", "lsp_complete",
            "generate_resource", "generate_scene", "physics_step",
            "character_control", "list_scripts", "list_scenes"
        ]]
        actor = system.spawn(GodotBridgeActor.ACTOR_ID, capabilities=caps,
            supervisor=AetherAddress(host="local", actor_id="__orchestration_coordinator__"))
        actor.on(MessageType.INVOKE, GodotBridgeActor._handle_invoke)
        return actor

    @staticmethod
    def _handle_invoke(msg):
        from aris_orchestration_bridge import STATE_DIR
        import time, json, subprocess, sys
        t0 = time.time()
        token = msg.payload.get("token", {})
        action = token.get("action", "status")
        params = token.get("params", "")

        try:
            GODOT = _GODOT_EXE or "godot"
            PROJ = str(GAME_PROJECT_DIR)

            if action == "status":
                proj_ok = GAME_PROJECT_DIR.joinpath("project.godot").exists()
                gd = list(GAME_PROJECT_DIR.rglob("*.gd"))
                ts = list(GAME_PROJECT_DIR.rglob("*.tscn"))
                gs = "ready" if _GODOT_EXE else "not_installed"
                result = {"output": f"Godot Bridge\nProject: {GAME_PROJECT_DIR.name} (ok)\nGodot: {gs}\nScripts: {len(gd)}\nScenes: {len(ts)}\nActions: run_script, compile, validate, lsp_complete, generate_resource, generate_scene, physics_step, character_control"}

            elif action == "run_script":
                script = params or "res://test_run.gd"
                r = subprocess.run([GODOT, "--path", PROJ, "--headless", "--script", script, "--quit"],
                    capture_output=True, text=True, timeout=60)
                result = {"output": (r.stdout[-2000:] or "done") + (f"\n[err] {r.stderr[-500:]}" if r.stderr else "")}

            elif action == "compile":
                r = subprocess.run([GODOT, "--path", PROJ, "--headless", "--export-release", "Windows"],
                    capture_output=True, text=True, timeout=120)
                result = {"output": (r.stdout[-2000:] or "ok") + (f"\n[err] {r.stderr[-500:]}" if r.stderr else "")}

            elif action == "validate":
                # Validate all GDScript files
                gd_files = list(GAME_PROJECT_DIR.rglob("*.gd"))
                errors = []
                for gd in gd_files[:20]:
                    r = subprocess.run([GODOT, "--path", PROJ, "--headless", "--script", str(gd.relative_to(GAME_PROJECT_DIR)), "--quit"],
                        capture_output=True, text=True, timeout=30)
                    if r.returncode != 0 or "ERROR" in r.stderr:
                        errors.append(f"{gd.name}: {r.stderr[:100]}")
                result = {"output": f"Validated {len(gd_files)} scripts\nErrors: {len(errors)}\n" + "\n".join(errors[:5]) if errors else "All clean"}

            elif action == "generate_resource":
                try:
                    sys.path.insert(0, "D:/LAAP/harness/laap_coding/core")
                    from godot_resource_generator import GodotResourceGenerator
                    gen = GodotResourceGenerator()
                    r = gen.generate_from_mapping({"component_uri": "godot://material/" + params.replace(" ", "_"), "name": params, "type": "material"})
                    result = {"output": str(r)[:2000]}
                except Exception as e:
                    result = {"output": f"[ResourceGen] {e}"}

            elif action == "physics_step":
                try:
                    sys.path.insert(0, str(_GODOT_BRIDGE_DIR))
                    from controllers.physics_stepping import PhysicsStepping
                    ps = PhysicsStepping()
                    r = ps.step(count=int(params or 1))
                    result = {"output": str(r)[:2000]}
                except Exception as e:
                    result = {"output": f"[Physics] {e}"}

            elif action == "character_control":
                result = {"output": f"[CharacterControl] params: {params[:100]}"}

            elif action == "lsp_complete":
                try:
                    sys.path.insert(0, str(_GODOT_BRIDGE_DIR))
                    from godot_lsp_client import GodotLSPClient
                    client = GodotLSPClient()
                    r = client.complete(params or "extends Node")
                    result = {"output": str(r)[:2000]}
                except Exception as e:
                    result = {"output": f"[LSP] {e}"}

            elif action == "list_scripts":
                gd = sorted(GAME_PROJECT_DIR.rglob("*.gd"))
                result = {"output": "\n".join([f"Scripts ({len(gd)}):"] + [f"  {s.relative_to(GAME_PROJECT_DIR)} ({s.stat().st_size:,}B)" for s in gd])} if gd else {"output": "[no scripts]"}

            elif action == "list_scenes":
                ts = sorted(GAME_PROJECT_DIR.rglob("*.tscn"))
                result = {"output": "\n".join([f"Scenes ({len(ts)}):"] + [f"  {s.relative_to(GAME_PROJECT_DIR)} ({s.stat().st_size:,}B)" for s in ts])} if ts else {"output": "[no scenes]"}

            else:
                result = {"output": f"[unknown] {action}"}

        except subprocess.TimeoutExpired:
            result = {"output": "[timeout]"}
        except Exception as e:
            result = {"output": f"[error] {str(e)[:200]}"}

        result["_latency_ms"] = round((time.time()-t0)*1000, 2)
        p = STATE_DIR / "orchestration_godot_bridge.json"
        try: p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps({"t":time.time(),"r":result}, ensure_ascii=False))
        except: pass
        return result


# ── UIWebEngineActor: 零 Token UI/网站设计引擎 ────────────

_UI_WEB_DIR = Path("D:/LAAP/harness/ui_web/core")


class UIWebEngineActor:
    """零Token UI/网站设计引擎 — intent→design tokens→components→page."""
    ACTOR_ID = "ui_web_engine"

    @staticmethod
    def register(system):
        from laap.orchestration.actor import AetherAddress
        from laap.orchestration.primitives import MessageType, Capability
        caps = [Capability(n, 0.9) for n in [
            "parse_intent", "generate_tokens", "lookup_component",
            "compose_page", "list_components", "style_variants"
        ]]
        actor = system.spawn(UIWebEngineActor.ACTOR_ID, capabilities=caps,
            supervisor=AetherAddress(host="local", actor_id="__orchestration_coordinator__"))
        actor.on(MessageType.INVOKE, UIWebEngineActor._handle_invoke)
        return actor

    @staticmethod
    def _handle_invoke(msg):
        from aris_orchestration_bridge import STATE_DIR
        import time, json, sys
        t0 = time.time()
        token = msg.payload.get("token", {})
        action = token.get("action", "status")
        params = token.get("params", "")
        text = token.get("text", params)

        try:
            sys.path.insert(0, "D:/LAAP/harness/ui_web")
            sys.path.insert(0, "D:/LAAP/harness/ui_web/core")

            if action == "status":
                result = {"output": "UI Web Engine - see orchestration logs"}


            elif action == "parse_intent":
                from intent_engine import IntentEngine
                ie = IntentEngine()
                r = ie.parse(text)
                result = {"output": json.dumps(r, ensure_ascii=False)[:2000]}

            elif action == "generate_tokens":
                from design_token_engine import DesignTokenEngine
                dte = DesignTokenEngine()
                r = dte.generate(text)
                result = {"output": str(r)[:2000]}

            elif action == "lookup_component":
                from component_registry import ComponentRegistry
                cr = ComponentRegistry()
                r = cr.lookup(text)
                result = {"output": str(r)[:2000]}

            elif action == "compose_page":
                from intent_engine import IntentEngine
                from design_token_engine import DesignTokenEngine
                from component_registry import ComponentRegistry
                ie = IntentEngine(); dte = DesignTokenEngine(); cr = ComponentRegistry()
                intent = ie.parse(text)
                tokens = dte.generate(text)
                comps = cr.lookup(intent.get("page_type", "landing"))
                result = {"output": f"Intent: {intent}\nTokens: {tokens}\nComponents: {comps}"[:2000]}

            elif action == "list_components":
                from component_registry import ComponentRegistry
                cr = ComponentRegistry()
                r = cr.list_all() if hasattr(cr, 'list_all') else cr.components.keys() if hasattr(cr, 'components') else []
                result = {"output": "\n".join(list(r)[:20]) if r else "[no components]"}

            else:
                result = {"output": f"[unknown] {action}"}

        except Exception as e:
            result = {"output": f"[UIWeb] {str(e)[:200]}"}

        result["_latency_ms"] = round((time.time()-t0)*1000, 2)
        p = STATE_DIR / "orchestration_ui_web.json"
        try: p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps({"t":time.time(),"r":result}, ensure_ascii=False))
        except: pass
        return result



class OrchestrationBridge:
    """编排桥接器 — 在 before_turn 中提供编排引擎接口。

    用法（在 aris_cognitive_bridge.py 中）:
        from aris_orchestration_bridge import get_bridge
        bridge = get_bridge()
        result = bridge.process("读取laap_integrator.py")
        # result = { "output": "...", "workflow": "...", "latency_ms": ... }
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

        self.state_dir = STATE_DIR
        self.system: Optional[ActorSystem] = None
        self.kernel: Optional[OrchestrationKernel] = None
        self.meta_agent: Optional[MetaAgent] = None
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        self._ready = False
        self._stats = {
            "workflows_run": 0,
            "rules_calls": 0,
            "memory_calls": 0,
            "total_latency_ms": 0.0,
        }

        self._init_system()

    def _init_system(self) -> None:
        """初始化 ActorSystem 并注册所有 actor。"""
        try:
            # 获取或创建事件循环
            try:
                self._event_loop = asyncio.get_running_loop()
            except RuntimeError:
                self._event_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._event_loop)

            # 创建 ActorSystem
            self.system = ActorSystem(system_id="aris_orchestration")

            # 注册 RulesEngine actor
            RulesEngineActor.register(self.system)

            # 注册 EpisodicMemory actor
            EpisodicMemoryActor.register(self.system)

            # 注册 PSICore actor
            PSICoreActor.register(self.system)

            # 注册 LongForm actor
            LongFormActor.register(self.system)

            # 注册 FusionEngine actor
            FusionEngineActor.register(self.system)

            # 注册 Filesystem actor（纯 stdlib，零依赖）
            FilesystemActor.register(self.system)

            # 注册 Harness actor（零 Token UI/Web 生成）
            HarnessActor.register(self.system)

            # 注册 CodeWorkspace actor（多智能体编程流水线）
            CodeWorkspaceActor.register(self.system)

            # 注册 DesireEngine actor（欲望驱动引擎）
            DesireEngineActor.register(self.system)

            # 注册 GoalEngine actor（目标生命周期引擎）
            GoalEngineActor.register(self.system)

            # 注册 CopilotBridge actor（AI 编程助手桥）
            CopilotBridgeActor.register(self.system)

            # 注册 Literary actor（Markov+散文+文学生成）
            LiteraryActor.register(self.system)
            # 注册 GameActor（Godot 游戏引擎）
            GameActor.register(self.system)
            # 注册 GodotBridgeActor（Godot 引擎完整桥接）
            GodotBridgeActor.register(self.system)

            # 注册 UIWebEngineActor（零Token UI/网站设计引擎）
            UIWebEngineActor.register(self.system)


            # 创建 MetaAgent（监控和拓扑进化）
            self.meta_agent = MetaAgent(
                actor_system=self.system,
                epsilon=0.1,
            )

            self._ready = True
            logger.info(
                f"[OrchBridge] System initialized: "
                f"{len(self.system.actors)} actors, "
                f"{sum(len(a.capabilities) for a in self.system.actors.values())} capabilities"
            )

        except Exception as e:
            logger.warning(f"[OrchBridge] Initialization failed: {e}")
            self._ready = False

    # ─── 同步处理入口（Hermes before_turn 调用） ───────

    def process(self, user_input: str) -> Dict[str, Any]:
        """同步处理用户输入 — 编排引擎的主入口。

        流程（工作流驱动）:
          1. EpisodicMemory.find_similar(user_input) — 查历史
          2. 如果历史匹配 > 0.5，直接复用历史策略
          3. 否则 RulesEngine.process(user_input) — 规则执行
          4. EpisodicMemory.save_episode(...) — 存储本次结果
          5. 返回最终输出

        Returns:
            dict with keys:
                output: str — 引擎输出文本
                workflow: str — 执行的工作流名称
                from_memory: bool — 是否来自记忆复用
                matched: bool — 规则是否匹配
                rule: str — 匹配的规则名
                latency_ms: float
        """
        if not self._ready:
            return {
                "output": "",
                "workflow": "none",
                "from_memory": False,
                "matched": False,
                "rule": None,
                "latency_ms": 0.0,
                "error": "OrchestrationBridge not initialized",
            }

        t0 = time.time()

        # ─── 工作流：查记忆 → 判断 → 执行 → 存储 ───

        # Step 1: 查情景记忆
        memory_matches = self._run_in_loop(
            self._call_memory_find, user_input
        )

        from_memory = False
        rules_result = None

        if memory_matches and memory_matches.get("matches"):
            # 检查最高分匹配
            top_match = memory_matches["matches"][0]
            score = top_match.get("score", 0)
            if score > 0.5:
                from_memory = True
                rules_result = {
                    "matched": True,
                    "rule": top_match.get("rule", "memory_replay"),
                    "intent": top_match.get("intent", {}),
                    "output": top_match.get("output", ""),
                    "from_memory": True,
                    "confidence": score,
                }

        # Step 2: 如果记忆没命中，走规则引擎
        if not from_memory:
            rules_result = self._run_in_loop(
                self._call_rules_engine, user_input
            )

        # Step 3: 存储本次结果到情景记忆
        if rules_result:
            self._run_in_loop(
                self._call_memory_save,
                user_input=user_input,
                intent=rules_result.get("intent", {}),
                rule=rules_result.get("rule", ""),
                output=rules_result.get("output", ""),
                success=rules_result.get("matched", False),
                latency_ms=(time.time() - t0) * 1000,
            )

        elapsed_ms = (time.time() - t0) * 1000
        self._stats["workflows_run"] += 1
        self._stats["total_latency_ms"] += elapsed_ms

        return {
            "output": rules_result.get("output", "") if rules_result else "",
            "workflow": "memory_first" if from_memory else "rules_engine",
            "from_memory": from_memory,
            "matched": rules_result.get("matched", False) if rules_result else False,
            "rule": rules_result.get("rule") if rules_result else None,
            "latency_ms": round(elapsed_ms, 2),
            "actor_count": len(self.system.actors) if self.system else 0,
        }

    # ─── 异步 actor 调用辅助 ───────────────────────────

    def _run_in_loop(self, coro_fn, *args, **kwargs):
        """在事件循环中运行协程。"""
        if self._event_loop is None:
            return None
        try:
            if self._event_loop.is_running():
                # 已有运行中的循环 — 创建任务并等待
                future = asyncio.run_coroutine_threadsafe(
                    coro_fn(*args, **kwargs), self._event_loop
                )
                return future.result(timeout=5.0)
            else:
                return self._event_loop.run_until_complete(
                    coro_fn(*args, **kwargs)
                )
        except Exception as e:
            logger.warning(f"[OrchBridge] Async call failed: {e}")
            return None

    async def _call_rules_engine(self, text: str) -> Optional[Dict]:
        """向 RulesEngineActor 发送 INVOKE 消息并等待结果。"""
        if self.system is None:
            return None

        actor = self.system.actors.get(RulesEngineActor.ACTOR_ID)
        if actor is None:
            return None

        # 先检查是否有最新结果文件
        result_path = STATE_DIR / "orchestration_result.json"
        previous_mtime = 0
        if result_path.exists():
            previous_mtime = result_path.stat().st_mtime

        # 发送 INVOKE 消息
        msg = AetherMessage(
            msg_type=MessageType.INVOKE,
            sender=AetherAddress(host="local", actor_id="orchestration_bridge"),
            recipient=AetherAddress(host="local", actor_id=RulesEngineActor.ACTOR_ID),
            payload={
                "token": {"text": text, "input": text},
                "color": "DATA",
            },
        )
        await self.system.send(msg)

        # 等待结果文件更新（轮询）
        deadline = time.time() + 3.0
        while time.time() < deadline:
            if result_path.exists() and result_path.stat().st_mtime > previous_mtime:
                try:
                    with open(result_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return data.get("result")
                except (json.JSONDecodeError, IOError):
                    pass
            await asyncio.sleep(0.05)

        logger.warning("[OrchBridge] RulesEngine timeout — no result within 3s")
        return None

    async def _call_memory_find(self, text: str) -> Optional[Dict]:
        """向 EpisodicMemoryActor 发送 find_similar 请求。"""
        if self.system is None:
            return None

        result_path = STATE_DIR / "orchestration_memory.json"
        previous_mtime = 0
        if result_path.exists():
            previous_mtime = result_path.stat().st_mtime

        msg = AetherMessage(
            msg_type=MessageType.INVOKE,
            sender=AetherAddress(host="local", actor_id="orchestration_bridge"),
            recipient=AetherAddress(host="local", actor_id=EpisodicMemoryActor.ACTOR_ID),
            payload={
                "token": {"action": "find", "text": text, "top_k": 3},
                "color": "DATA",
            },
        )
        await self.system.send(msg)

        deadline = time.time() + 3.0
        while time.time() < deadline:
            if result_path.exists() and result_path.stat().st_mtime > previous_mtime:
                try:
                    with open(result_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return data.get("result")
                except (json.JSONDecodeError, IOError):
                    pass
            await asyncio.sleep(0.05)

        return None

    async def _call_memory_save(
        self,
        user_input: str,
        intent: Dict,
        rule: str,
        output: str,
        success: bool,
        latency_ms: float,
    ) -> None:
        """向 EpisodicMemoryActor 发送 save 请求。"""
        if self.system is None:
            return

        msg = AetherMessage(
            msg_type=MessageType.INVOKE,
            sender=AetherAddress(host="local", actor_id="orchestration_bridge"),
            recipient=AetherAddress(host="local", actor_id=EpisodicMemoryActor.ACTOR_ID),
            payload={
                "token": {
                    "action": "save",
                    "user_input": user_input,
                    "intent": intent,
                    "rule": rule,
                    "output": output,
                    "success": success,
                    "latency_ms": latency_ms,
                },
                "color": "DATA",
            },
        )
        await self.system.send(msg)

    async def _call_psi_actor(self, action: str, text: str = "", timeout_ms: float = 100.0) -> Optional[Dict]:
        """向 PSICoreActor 发送请求并等待结果。"""
        if self.system is None:
            return None

        result_path = STATE_DIR / "orchestration_psi.json"
        previous_mtime = 0
        if result_path.exists():
            previous_mtime = result_path.stat().st_mtime

        token = {"action": action}
        if action == "poll":
            token["text"] = text
            token["timeout_ms"] = timeout_ms

        msg = AetherMessage(
            msg_type=MessageType.INVOKE,
            sender=AetherAddress(host="local", actor_id="orchestration_bridge"),
            recipient=AetherAddress(host="local", actor_id=PSICoreActor.ACTOR_ID),
            payload={"token": token, "color": "DATA"},
        )
        await self.system.send(msg)

        deadline = time.time() + max(timeout_ms / 1000 + 1.0, 5.0)
        while time.time() < deadline:
            if result_path.exists() and result_path.stat().st_mtime > previous_mtime:
                try:
                    with open(result_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return data.get("result")
                except (json.JSONDecodeError, IOError):
                    pass
            await asyncio.sleep(0.05)
        return None

    async def _call_longform(self, topic: str, target_chars: int = 500) -> Optional[Dict]:
        """向 LongFormActor 发送生成请求。"""
        if self.system is None:
            return None

        result_path = STATE_DIR / "orchestration_longform.json"
        previous_mtime = 0
        if result_path.exists():
            previous_mtime = result_path.stat().st_mtime

        msg = AetherMessage(
            msg_type=MessageType.INVOKE,
            sender=AetherAddress(host="local", actor_id="orchestration_bridge"),
            recipient=AetherAddress(host="local", actor_id=LongFormActor.ACTOR_ID),
            payload={
                "token": {"action": "generate", "topic": topic, "target_chars": target_chars},
                "color": "DATA",
            },
        )
        await self.system.send(msg)

        deadline = time.time() + 10.0
        while time.time() < deadline:
            if result_path.exists() and result_path.stat().st_mtime > previous_mtime:
                try:
                    with open(result_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return data.get("result")
                except (json.JSONDecodeError, IOError):
                    pass
            await asyncio.sleep(0.05)
        return None

    async def _call_filesystem(self, action: str, **kwargs) -> Optional[Dict]:
        """向 FilesystemActor 发送文件操作请求。"""
        if self.system is None:
            return None

        result_path = STATE_DIR / "orchestration_fs.json"
        previous_mtime = 0
        if result_path.exists():
            previous_mtime = result_path.stat().st_mtime

        token = {"action": action}
        token.update(kwargs)

        msg = AetherMessage(
            msg_type=MessageType.INVOKE,
            sender=AetherAddress(host="local", actor_id="orchestration_bridge"),
            recipient=AetherAddress(host="local", actor_id=FilesystemActor.ACTOR_ID),
            payload={"token": token, "color": "DATA"},
        )
        await self.system.send(msg)

        deadline = time.time() + 10.0
        while time.time() < deadline:
            if result_path.exists() and result_path.stat().st_mtime > previous_mtime:
                try:
                    with open(result_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return data.get("result")
                except (json.JSONDecodeError, IOError):
                    pass
            await asyncio.sleep(0.05)
        return None

    # ─── DSL 工作流编译（供高级使用） ─────────────────

    def compile_workflow(self, workflow_expr: LAAPExpr, net_id: str = "aris_cognitive_flow") -> Dict:
        """编译 LAAP-DSL 表达式为 Petri 网，返回结构化描述。

        这允许在 cognitive_bus 中定义复杂认知管道:
            wf = seq(
                act("rules_engine", {"text": "$input"}, output_key="rules_out"),
                guard(
                    infer("confidence_check", "result.confidence > 0.5"),
                    then_branch=act("episodic_memory", {"action": "save"}, output_key="saved"),
                ),
            )
            bridge.compile_workflow(wf)
        """
        try:
            net, bindings, outputs = compile_workflow(
                workflow_expr, net_id=net_id
            )
            return {
                "net_id": net.net_id,
                "places": len(net.places),
                "transitions": len(net.transitions),
                "actor_bindings": bindings,
                "output_places": outputs,
                "success": True,
            }
        except Exception as e:
            logger.warning(f"[OrchBridge] Workflow compilation failed: {e}")
            return {"success": False, "error": str(e)}

    # ─── 系统信息 ──────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """返回编排引擎状态。"""
        if not self._ready or self.system is None:
            return {"ready": False}

        actors_info = {}
        for actor_id, actor in self.system.actors.items():
            actors_info[actor_id] = {
                "state": actor.state.name,
                "capabilities": [c.name for c in actor.capabilities],
                "messages_processed": actor.metrics.get("messages_processed", 0),
                "errors": actor.metrics.get("errors", 0),
                "avg_latency_ms": round(actor.metrics.get("avg_latency_ms", 0), 2),
            }

        return {
            "ready": self._ready,
            "actors": actors_info,
            "stats": self._stats,
            "meta_agent": self.meta_agent is not None,
        }


# ═══════════════════════════════════════════════════════════
# 全局访问函数
# ═══════════════════════════════════════════════════════════

def get_bridge() -> OrchestrationBridge:
    """获取或创建 OrchestrationBridge 全局单例。"""
    global _bridge
    if _bridge is None:
        _bridge = OrchestrationBridge()
    return _bridge


def process(user_input: str) -> Dict[str, Any]:
    """便捷入口 — 单次编排处理。"""
    bridge = get_bridge()
    return bridge.process(user_input)


def status() -> Dict[str, Any]:
    """便捷入口 — 编排引擎状态。"""
    bridge = get_bridge()
    return bridge.status()


# ═══════════════════════════════════════════════════════════
# Hermes before_turn 桥接注入
# ═══════════════════════════════════════════════════════════


    def _dispatch_to_actor(self, actor_id: str, payload: dict) -> dict:
        """Dispatch a message to a specific actor and get the result."""
        if not self.system or actor_id not in self.system.actors:
            return {"output": f"[Actor not found] {actor_id}"}
        try:
            import asyncio, json
            from laap.orchestration.primitives import AetherMessage, MessageType
            msg = AetherMessage(
                msg_type=MessageType.INVOKE,
                source="orchestration_bridge",
                target=actor_id,
                payload={"token": payload},
            )
            result = self.system.actors[actor_id].receive(msg)
            if result is None:
                return {"output": "[no result]"}
            if isinstance(result, dict):
                return result
            return {"output": str(result)}
        except Exception as e:
            return {"output": f"[dispatch error] {e}"}

def inject_into_context(user_message: str) -> Optional[str]:
    """在 before_turn 中调用，返回编排结果上下文。

    用法（在 aris_cognitive_bridge.py before_turn 中）:
        from aris_orchestration_bridge import inject_into_context
        orch_ctx = inject_into_context(user_message)
        if orch_ctx:
            context_parts.append(orch_ctx)
    """
    bridge = get_bridge()
    if not bridge._ready:
        return None

    result = bridge.process(user_message)
    if not result.get("output"):
        return None

    workflow = result.get("workflow", "none")
    from_memory = result.get("from_memory", False)
    matched = result.get("matched", False)
    rule = result.get("rule", "")
    latency = result.get("latency_ms", 0)

    lines = [
        f"[Aris 编排引擎输出]",
        f"工作流: {workflow} | 耗时: {latency}ms",
    ]
    if from_memory:
        lines.append(f"模式: 记忆复用 (score > 0.5)")
    if matched and rule:
        lines.append(f"规则: {rule}")
    lines.append("")
    lines.append(result.get("output", ""))

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# 独立测试入口
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("Aris Orchestration Bridge v1 — 全 Actor 测试")
    print("=" * 60)

    bridge = get_bridge()
    print(f"\n系统就绪: {bridge._ready}")
    if bridge._ready:
        print(f"Actor 数量: {len(bridge.system.actors)}")
        for aid, actor in bridge.system.actors.items():
            caps = ", ".join(c.name for c in actor.capabilities)
            print(f"  · {aid}: [{actor.state.name}] {caps}")

    print("\n--- 测试 1: RulesEngine (状态查询) ---")
    result = process("帮我查一下系统状态")
    print(f"  matched={result.get('matched')}, rule={result.get('rule')}")
    print(f"  from_memory={result.get('from_memory')}")
    print(f"  latency={result.get('latency_ms')}ms")

    print("\n--- 测试 2: EpisodicMemory (记忆增强) ---")
    # 第二次调用同一指令，应该走记忆
    result = process("查系统状态")
    print(f"  matched={result.get('matched')}, rule={result.get('rule')}")
    print(f"  from_memory={result.get('from_memory')}")
    print(f"  workflow={result.get('workflow')}")

    print("\n--- 测试 3: PSI Core 接口 ---")
    result = bridge._run_in_loop(bridge._call_psi_actor, "status")
    if result:
        engine = result.get("engine", "none")
        cycle = result.get("cycle", 0)
        print(f"  engine={engine}, cycle={cycle}")
        print(f"  emotion={result.get('emotion')}")

    print("\n--- 测试 4: PSI Poll (发送+轮询) ---")
    result = bridge._run_in_loop(bridge._call_psi_actor, "poll", text="你好Lorry")
    if result and result.get("engine") not in (None, "none"):
        print(f"  engine={result.get('engine')}")
        print(f"  response[:80]={str(result.get('response', ''))[:80]}")
    else:
        print(f"  PSI 未运行或超时（正常，取决于 Rust 二进制是否启动）")

    print("\n--- 测试 5: LongForm 长文生成 ---")
    result = bridge._run_in_loop(bridge._call_longform, topic="Aris认知架构", target_chars=200)
    if result:
        output = result.get("output", "")
        print(f"  action={result.get('action')}")
        print(f"  output_len={len(output)}chars")

    print("\n--- 测试 6: FilesystemActor 文件系统（完全独立于 Hermes） ---")
    result = bridge._run_in_loop(bridge._call_filesystem, action="read_file", path="D:/LAAP/aris_brain/aris_orchestration_bridge.py", limit=5)
    if result:
        print(f"  read_file: OK ({result.get('returned_lines', 0)} lines, {result.get('total_lines', 0)} total)")

    result = bridge._run_in_loop(bridge._call_filesystem, action="search_files", pattern="class FilesystemActor", path="D:/LAAP/aris_brain", file_glob="*.py")
    if result:
        print(f"  search_files: OK ({result.get('total', 0)} matches)")

    result = bridge._run_in_loop(bridge._call_filesystem, action="file_info", path="D:/LAAP/aris_brain/aris_orchestration_bridge.py")
    if result:
        print(f"  file_info: OK ({result.get('size_bytes', 0)}B)")

    result = bridge._run_in_loop(bridge._call_filesystem, action="list_directory", path="D:/LAAP/aris_brain/state", pattern="orchestration_*")
    if result:
        print(f"  list_directory: OK ({result.get('total', 0)} matches)")


    print("\n\n========== TOKEN 消耗审计对比 ==========")
    print()

    print("--- 最终状态 ---")
    st = bridge.status()
    print(f"  actors: {list(st.get('actors', {}).keys())}")
    print(f"  workflows_run: {st.get('stats', {}).get('workflows_run', 0)}")
    for aid, info in st.get('actors', {}).items():
        print(f"  {aid}: {info.get('messages_processed', 0)} msgs processed")
