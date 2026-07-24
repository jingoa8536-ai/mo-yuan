"""
Aris Infrastructure — Body Layer (Tools + Session + Memory)

给 Aris 装上和 Ao 一样的基础设施能力，同时保留她自己的 PSI 认知架构。

架构:
  ArisBrain.think() → CognitiveState (情感/需求/注意)
       ↓
  ArisInfrastructure (身体层)
    ├── HermesToolBridge     — 71 个工具 (读文件、搜索、执行代码...)
    ├── SessionDB             — Hermes 会话持久化
    └── MemoryBridge          — Hermes 记忆系统
       ↓
  LanguageCortex.express() → 自然语言输出
       ↓
  如果有工具结果 → 反馈给下一个 cognitive cycle

设计原则:
  - 认知照旧: ArisBrain.think() 仍然是思考主体
  - 身体共用: Aris 的工具和 Ao 完全一致 (同一个 ToolRegistry)
  - 自然融合: 工具调用结果进入认知状态，影响情感/需求
"""

from __future__ import annotations

import logging

import sys, os, json, time, logging
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger("aris.infrastructure")

_HERMES_HOME = r"D:\hermes-agent-main (1)\hermes-agent-main"
_LAAP_HOME = r"D:\LAAP"
for p in [_HERMES_HOME, _LAAP_HOME]:
    if p not in sys.path:
        sys.path.insert(0, p)


class ArisInfrastructure:
    """
    Aris 的身体层 — 基础设施能力集合。

    和 Ao 共享相同的底层:
      - Hermes ToolRegistry (71工具)
      - Hermes SessionDB (会话持久化)
      - Hermes Memory (记忆系统)

    用法:
        body = ArisInfrastructure()
        body.tools.call("web_search", {"query": "..."})
        body.session_sync({"cycle": 10, "emotion": "curiosity"})
        body.remember("key", "value")
    """

    def __init__(self, enabled_toolsets: Optional[List[str]] = None):
        self._created_at = time.time()

        # ── 工具系统 ──────────────────────────────────────
        self._setup_tools(enabled_toolsets)

        # ── Session DB ────────────────────────────────────
        self._session_db = None
        self.session_id = f"aris_{int(time.time())}"

        # ── 记忆系统 ──────────────────────────────────────
        self._memory_available = False

        # ── 工具调用历史 (Aris 自省用) ────────────────────
        self.tool_history: List[Dict] = []
        self.total_tool_calls = 0
        self.session_syncs = 0

        logger.info(
            f"Aris body ready: {self.tool_count} tools, "
            f"session={self.session_id}"
        )

    # ── 工具系统 ──────────────────────────────────────────

    def _setup_tools(self, enabled_toolsets):
        """初始化 HermesToolBridge"""
        try:
            from laap.agent_core.hermes_tool_bridge import HermesToolBridge
            self._tool_bridge = HermesToolBridge(
                enabled_toolsets=enabled_toolsets or ["hermes-cli"]
            )
        except Exception as e:
            logger.warning(f"Tool bridge init failed: {e}")
            self._tool_bridge = None

    @property
    def tool_count(self) -> int:
        """可用工具数量"""
        if not self._tool_bridge:
            return 0
        return len(self._tool_bridge.list_tools())

    @property
    def tool_names(self) -> List[str]:
        """所有工具名列表"""
        if not self._tool_bridge:
            return []
        return self._tool_bridge.list_tools()

    def call_tool(self, name: str, args: dict = None) -> Any:
        """
        调用一个 Hermes 工具。

        Aris 的 cognitive cycle 调这个方法和 Ao 的 agent.execute_tool()
        走的是同一个 registry.dispatch()，只是多了认知记录。
        """
        if not self._tool_bridge:
            return {"error": "Tool system not available"}

        start = time.time()
        result = self._tool_bridge.call(name, args or {})
        elapsed = (time.time() - start) * 1000
        self.total_tool_calls += 1

        # 记录到历史 (Aris 可自省)
        self.tool_history.append({
            "tool": name,
            "args": args,
            "success": result.success,
            "duration_ms": round(elapsed, 1),
            "timestamp": time.time(),
        })
        if len(self.tool_history) > 100:
            self.tool_history = self.tool_history[-100:]

        return {
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "tool": name,
            "duration_ms": round(elapsed, 1),
        }

    def get_tool_schemas(self) -> List[dict]:
        """获取 OpenAI 格式的工具定义 (给 LLM 用)"""
        if not self._tool_bridge:
            return []
        return self._tool_bridge.get_openai_tools()

    # ── Session DB ────────────────────────────────────────

    def _init_session(self):
        """延迟初始化 SessionDB"""
        if self._session_db is not None:
            return
        try:
            from hermes_state import SessionDB
            self._session_db = SessionDB()
        except Exception:
            self._session_db = False  # 标记为不可用

    def session_sync(self, state_data: dict) -> bool:
        """
        同步 Aris 的认知状态到 Hermes SessionDB。

        这样 Ao 也可以通过 SessionDB 读取 Aris 的历史状态。
        """
        self._init_session()
        if not self._session_db:
            return False

        try:
            self._session_db.update_session_metadata(self.session_id, {
                "aris_state": json.dumps(state_data, default=str, ensure_ascii=False),
                "aris_tool_calls": self.total_tool_calls,
                "aris_last_sync": time.time(),
            })
            self.session_syncs += 1
            return True
        except Exception as e:
            logger.debug(f"Session sync failed: {e}")
            return False

    def session_load(self) -> Optional[dict]:
        """从 SessionDB 读取 Aris 的历史状态"""
        self._init_session()
        if not self._session_db:
            return None
        try:
            meta = self._session_db.get_session_metadata(self.session_id)
            if meta and "aris_state" in meta:
                return json.loads(meta["aris_state"])
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        return None

    # ── Hermes 记忆 ──────────────────────────────────────

    def remember(self, key: str, value: Any) -> bool:
        """向 Hermes 记忆系统写入 (Ao 也能读到)"""
        try:
            from tools.memory_tool import memory_tool
            memory_tool(key, json.dumps(value, ensure_ascii=False),
                        action="add", target="memory")
            self._memory_available = True
            return True
        except Exception:
            return False

    def recall(self, key: str) -> Optional[str]:
        """从 Hermes 记忆系统读取"""
        try:
            from tools.memory_tool import memory_tool
            return memory_tool(key, action="search")
        except Exception:
            return None

    # ── 工具执行辅助 ──────────────────────────────────────

    def execute_code(self, code: str) -> dict:
        """便捷: 执行 Python 代码"""
        return self.call_tool("execute_code", {"code": code})

    def web_search(self, query: str) -> dict:
        """便捷: 搜索网络"""
        return self.call_tool("web_search", {"query": query})

    def read_file(self, path: str) -> dict:
        """便捷: 读文件"""
        return self.call_tool("read_file", {"path": path})

    def write_file(self, path: str, content: str) -> dict:
        """便捷: 写文件"""
        return self.call_tool("write_file", {"path": path, "content": content})

    # ── 状态 ──────────────────────────────────────────────

    def stats(self) -> dict:
        """基础设施统计"""
        return {
            "tools": self.tool_count,
            "tool_calls": self.total_tool_calls,
            "session_id": self.session_id,
            "session_syncs": self.session_syncs,
            "memory": self._memory_available,
            "uptime": round(time.time() - self._created_at, 1),
        }

    def summary(self) -> str:
        """一行摘要"""
        return (
            f"Body: {self.tool_count}tools | "
            f"{self.total_tool_calls}calls | "
            f"{self.session_syncs}syncs | "
            f"mem={'🟢' if self._memory_available else '🔴'}"
        )


# ══════════════════════════════════════════════════════════════════
# 快速初始化
# ══════════════════════════════════════════════════════════════════

def create_aris_body(enabled_toolsets: Optional[List[str]] = None) -> ArisInfrastructure:
    """创建 Aris 身体层"""
    return ArisInfrastructure(enabled_toolsets=enabled_toolsets)


def quick_test():
    """验证基础设施是否正常"""
    body = create_aris_body()
    logger.info(f"Tools: {body.tool_count}")
    logger.info(f"  Sample: {body.tool_names[:10]}")
    logger.info(f"Stats: {body.stats()}")
    result = body.call_tool("think", {"thought": "Aris is becoming self-aware"})
    logger.info(f"think(): ok={result['success']}")
    return body


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    quick_test()
