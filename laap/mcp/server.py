"""LAAP MCP — Server

FastMCP-based MCP server that exposes LAAP's tools, memory, and
cognitive capabilities as MCP tools for use by any MCP client.
"""

from __future__ import annotations
import asyncio
import json
import logging
import os
import sys
import threading
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from laap.mcp.session_registry import get_registry
from laap.mcp.base import MCPMessage, MCPResponse
from laap.tools.base import ToolResult
from laap.tools.tool_registry import get_tool, list_tools

if TYPE_CHECKING:
    from laap_brain import LaapBrain

logger = logging.getLogger("laap.mcp.server")


try:
    from mcp.server.fastmcp import FastMCP
    HAS_FASTMCP = True
except ImportError:
    HAS_FASTMCP = False
    FastMCP = None  # type: ignore



class LAAPMCPServer:
    """MCP server exposing LAAP capabilities via FastMCP.

    Exposes as MCP tools:
    - LAAP agent tools (read/write/search/execute)
    - Memory tools (remember/recall/forget)
    - Cognitive tools (needs/emotion/status)
    - MCP server management tools
    """

    def __init__(self, name: str = "LAAP-Agent", agent=None):
        self.name = name
        self.agent = agent
        self._server: Optional[FastMCP] = None
        self._running = False
        self._event_bridge = None
        # MCP hook tool brain cache: session_id -> LaapBrain
        self._brains: Dict[str, "LaapBrain"] = {}
        self._brains_lock = threading.Lock()

    def _get_or_create_brain(self, session_id: str) -> "LaapBrain":
        """Get the cached LaapBrain for a session, creating it if needed.

        Maintains a 1:1 mapping between MCP session_id and LaapBrain instance
        so that cognitive state (mode, cortex, skills) accumulates across the
        three hooks (``laap_before_turn`` / ``laap_after_tool`` /
        ``laap_after_turn``) within the same session.

        Args:
            session_id: MCP client session identifier.

        Returns:
            The :class:`~laap_brain.LaapBrain` instance bound to this session.
        """
        with self._brains_lock:
            cached = self._brains.get(session_id)
            if cached is not None:
                return cached
            lifeform_id = get_registry().register_session(session_id)
            from laap_brain import LaapBrain

            brain = LaapBrain(agent=None, agent_id=lifeform_id)
            self._brains[session_id] = brain
            return brain

    def build_server(self) -> FastMCP:
        """Build and configure the FastMCP server."""
        if not HAS_FASTMCP:
            raise ImportError("pip install mcp")

        mcp = FastMCP(self.name, log_level="WARNING")

        # ── Agent Tools ──────────────────────────────────────
        @mcp.tool()
        async def agent_chat(message: str) -> str:
            """Send a message to the LAAP agent and get a response."""
            if not self.agent:
                return "Agent not connected"
            import asyncio
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self.agent.chat, message)

        @mcp.tool()
        async def agent_status() -> str:
            """Get the current agent status."""
            if not self.agent:
                return json.dumps({"status": "disconnected"})
            return json.dumps(self.agent.status())

        @mcp.tool()
        async def agent_memory_prefetch(query: str) -> str:
            """Retrieve relevant memories for a query."""
            if not self.agent or not hasattr(self.agent, 'memory_manager'):
                return "[]"
            ctx = self.agent.memory_manager.prefetch_all(query)
            return ctx or "[]"

        # ── File Tools ────────────────────────────────────────
        @mcp.tool()
        async def read_file(path: str) -> str:
            """Read a file from the filesystem."""
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                return json.dumps({"error": str(e)})

        @mcp.tool()
        async def write_file(path: str, content: str) -> str:
            """Write content to a file."""
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return json.dumps({"status": "written", "path": path})
            except Exception as e:
                return json.dumps({"error": str(e)})

        @mcp.tool()
        async def search_files(pattern: str, path: str = ".") -> str:
            """Search for files matching a pattern."""
            import glob as glob_mod
            matches = glob_mod.glob(os.path.join(path, pattern), recursive=True)
            return json.dumps(matches[:100])

        # ── Shell Tools ───────────────────────────────────────
        @mcp.tool()
        async def run_command(command: str, timeout: int = 30) -> str:
            """Run a shell command and return output."""
            import subprocess
            try:
                result = subprocess.run(
                    command, shell=True, capture_output=True,
                    text=True, timeout=timeout,
                )
                output = result.stdout[-5000:] if result.stdout else ""
                if result.stderr:
                    output += "\nSTDERR:\n" + result.stderr[-1000:]
                return output or "(no output)"
            except subprocess.TimeoutExpired:
                return "(timeout)"
            except Exception as e:
                return json.dumps({"error": str(e)})

        # ── Web Tools ─────────────────────────────────────────
        @mcp.tool()
        async def web_search(query: str) -> str:
            """Search the web for information."""
            try:
                import httpx
                url = f"https://api.duckduckgo.com/?q={query}&format=json"
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, timeout=10)
                    return resp.text[:5000]
            except Exception as e:
                return json.dumps({"error": str(e)})

        # ── Memory Tools ──────────────────────────────────────
        @mcp.tool()
        async def memory_store(content: str, memory_type: str = "fact",
                               importance: float = 0.5) -> str:
            """Store a memory in the persistent memory system."""
            if not self.agent or not hasattr(self.agent, 'memory_manager'):
                return json.dumps({"error": "memory not available"})
            from laap.memory.persistent import MemoryEntry
            provider = self.agent.memory_manager.get_provider("builtin")
            if provider:
                eid = provider._engine.store(
                    MemoryEntry(content=content, memory_type=memory_type,
                                importance=importance)
                )
                return json.dumps({"status": "stored", "id": eid[:8]})
            return json.dumps({"error": "no provider"})

        @mcp.tool()
        async def memory_recall(query: str = "", limit: int = 5) -> str:
            """Recall memories from the persistent memory system."""
            if not self.agent or not hasattr(self.agent, 'memory_manager'):
                return "[]"
            provider = self.agent.memory_manager.get_provider("builtin")
            if provider:
                result = provider.handle_tool_call("recall",
                    {"query": query, "limit": limit})
                return result
            return "[]"

        # ── Cognitive Status ──────────────────────────────────
        @mcp.tool()
        async def cognitive_status() -> str:
            """Get the cognitive state (needs, emotions, goals)."""
            if not self.agent:
                return json.dumps({"status": "no_agent"})
            state = {}
            if hasattr(self.agent, 'needs'):
                state["needs"] = {k: v.to_dict() for k, v in self.agent.needs.needs.items()}
            if hasattr(self.agent, 'emotion_gradient'):
                state["emotion"] = self.agent.emotion_gradient.state.to_dict()
            if hasattr(self.agent, 'goals'):
                state["goals"] = self.agent.goals.to_dict()
            return json.dumps(state, ensure_ascii=False)

        # ── LAAP Cognitive Hooks ─────────────────────────────
        # External MCP clients (Claude Code / Cursor / Trae) call these to
        # mount the LAAP cognitive brain: before_turn injects cognitive
        # context, after_tool records learning, after_turn records reflection,
        # and laap_cognitive_status returns a full snapshot.

        @mcp.tool()
        async def laap_before_turn(session_id: str, user_message: str = "") -> str:
            """LAAP cognitive hook: inject cognitive context before a turn.

            Call this at the start of each user turn to obtain a formatted
            cognitive context block (mode, biases, parliament, skills, cortex
            state) that should be appended to the system prompt.

            Args:
                session_id: Stable MCP client session identifier.
                user_message: The incoming user message text (optional).

            Returns:
                A formatted cognitive context string starting with
                ``[LAAP Cognitive Context]``. On error returns
                ``[LAAP Error] <message>``.
            """
            try:
                brain = self._get_or_create_brain(session_id)
                lifeform_id = get_registry().get_lifeform_id(session_id) or ""

                messages = (
                    [{"role": "user", "content": user_message}]
                    if user_message
                    else []
                )
                brain_block = brain.before_turn(messages=messages, system_prompt="")

                status = brain.status() if hasattr(brain, "status") else {}
                cortex = status.get("cortex", {}) if isinstance(status, dict) else {}

                needs_summary = (
                    f"mode={status.get('mode', '?')} "
                    f"cognitive_load={cortex.get('cognitive_load', 0):.2f}"
                )
                emotion_summary = (
                    f"limbic={cortex.get('limbic_activation', 0):.2f} "
                    f"salience={cortex.get('salience_signal', 0):.2f}"
                )
                goals_summary = (
                    f"skills={status.get('skills', 0)} "
                    f"gap={status.get('avg_gap', 0):.2f}"
                )
                recent_memory = (
                    f"turns={status.get('turns', 0)} "
                    f"tools={status.get('tools', 0)} "
                    f"biases={status.get('biases_corrected', 0)}"
                )

                parts = [
                    "[LAAP Cognitive Context]",
                    f"Session: {session_id} | Lifeform: {lifeform_id}",
                    f"Needs: {needs_summary}",
                    f"Emotion: {emotion_summary}",
                    f"Goals: {goals_summary}",
                    f"Recent Memory: {recent_memory}",
                ]
                if brain_block:
                    parts.append(brain_block)
                return "\n".join(parts)
            except Exception as e:
                return f"[LAAP Error] {e}"

        @mcp.tool()
        async def laap_after_tool(
            session_id: str, tool_name: str, result: str
        ) -> Dict[str, Any]:
            """LAAP cognitive hook: learn from a tool call result.

            Call this after each tool invocation so the LAAP brain can update
            skill proficiency, EWC parameters, and the tool history.

            Args:
                session_id: Stable MCP client session identifier.
                tool_name: Name of the tool that was executed.
                result: The tool's return value (stringified).

            Returns:
                ``{"learned": True, "memory_id": <id_or_empty>,
                "session_id": <session_id>}`` on success, or
                ``{"learned": False, "error": <message>}`` on failure.
            """
            try:
                brain = self._get_or_create_brain(session_id)
                brain.after_tool(tool_name, result)
                return {
                    "learned": True,
                    "memory_id": "",
                    "session_id": session_id,
                }
            except Exception as e:
                return {"learned": False, "error": str(e)}

        @mcp.tool()
        async def laap_after_turn(
            session_id: str, response: str
        ) -> Dict[str, Any]:
            """LAAP cognitive hook: reflect after a turn completes.

            Call this after the assistant response is generated so the LAAP
            brain can decay cortical activation and run meta-cognitive
            reflection.

            Args:
                session_id: Stable MCP client session identifier.
                response: The assistant's response text.

            Returns:
                ``{"reflection": <text_or_empty>,
                "emotion_delta": <cortex_diff_dict>,
                "session_id": <session_id>}`` on success, or
                ``{"reflection": "", "error": <message>}`` on failure.
            """
            try:
                brain = self._get_or_create_brain(session_id)
                before = (
                    brain.status().get("cortex", {})
                    if hasattr(brain, "status")
                    else {}
                )
                brain.after_turn(response)
                after = (
                    brain.status().get("cortex", {})
                    if hasattr(brain, "status")
                    else {}
                )
                emotion_delta = {
                    k: round(
                        float(after.get(k, 0)) - float(before.get(k, 0)), 3
                    )
                    for k in set(before) | set(after)
                }
                return {
                    "reflection": "",
                    "emotion_delta": emotion_delta,
                    "session_id": session_id,
                }
            except Exception as e:
                return {"reflection": "", "error": str(e)}

        @mcp.tool()
        async def laap_cognitive_status(session_id: str) -> Dict[str, Any]:
            """LAAP cognitive hook: return the full cognitive snapshot.

            Returns the brain's current cognitive state (mode, cortex, skills,
            activity counters, uptime) along with the bound lifeform_id.

            Args:
                session_id: Stable MCP client session identifier.

            Returns:
                Dict with keys: ``session_id``, ``lifeform_id``, ``needs``,
                ``emotion``, ``goals``, ``recent_memory``, ``uptime``.
            """
            try:
                brain = self._get_or_create_brain(session_id)
                lifeform_id = get_registry().get_lifeform_id(session_id) or ""
                status = (
                    brain.status()
                    if hasattr(brain, "status")
                    else (brain.to_dict() if hasattr(brain, "to_dict") else {})
                )
                cortex = status.get("cortex", {}) if isinstance(status, dict) else {}
                return {
                    "session_id": session_id,
                    "lifeform_id": lifeform_id,
                    "needs": {
                        "mode": status.get("mode", "unknown"),
                        "cognitive_load": cortex.get("cognitive_load", 0),
                        "salience_signal": cortex.get("salience_signal", 0),
                        "certainty": cortex.get("integration_level", 0),
                    },
                    "emotion": {
                        "limbic_activation": cortex.get("limbic_activation", 0),
                        "dmn_activation": cortex.get("dmn_activation", 0),
                        "pfc_activation": cortex.get("pfc_activation", 0),
                    },
                    "goals": {
                        "skills": status.get("skills", 0),
                        "avg_gap": status.get("avg_gap", 0),
                        "deliberations": status.get("deliberations", 0),
                    },
                    "recent_memory": {
                        "turns": status.get("turns", 0),
                        "tools": status.get("tools", 0),
                        "biases_corrected": status.get("biases_corrected", 0),
                    },
                    "uptime": status.get("uptime_s", 0),
                }
            except Exception as e:
                return {
                    "session_id": session_id,
                    "lifeform_id": "",
                    "error": str(e),
                }

        self._server = mcp
        return mcp

    def run_stdio(self):
        """Run the MCP server over stdio transport."""
        if not self._server:
            self.build_server()
        self._running = True
        logger.info(f"MCP server '{self.name}' running on stdio")
        self._server.run(transport="stdio")

    def run_sse(self, host: str = "127.0.0.1", port: int = 8766):
        """Run the MCP server over SSE transport."""
        if not self._server:
            self.build_server()
        self._running = True
        logger.info(f"MCP server '{self.name}' running on http://{host}:{port}/sse")
        self._server.run(transport="sse", host=host, port=port)

    def stop(self):
        """Stop the MCP server."""
        self._running = False
        logger.info("MCP server stopped")

class MCPServer:
    """Minimal JSON-RPC MCP server exposing LAAP tools.

    The server reads requests from *transport*, dispatches them, and writes
    responses back.  It supports ``initialize``, ``tools/list`` and
    ``tools/call``.  Tool handlers are resolved from the global LAAP tool
    registry when *tool_registry* is ``None``.
    """

    def __init__(
        self,
        transport: Any,
        tool_registry: Optional[Any] = None,
    ) -> None:
        self.transport = transport
        self.tool_registry = tool_registry
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def _tool_schema(self, name: str) -> Optional[Dict[str, Any]]:
        if self.tool_registry is not None:
            schema_fn = getattr(self.tool_registry, "get_tool_schema", None)
            if schema_fn:
                try:
                    return schema_fn(name)
                except Exception:
                    pass
        try:
            return get_tool_schema(name)
        except Exception:
            return None

    def _list_tools(self) -> List[Dict[str, Any]]:
        if self.tool_registry is not None:
            list_fn = getattr(self.tool_registry, "list_tools", None)
            if list_fn:
                return list_fn()
        return list_tools()

    def _get_tool(self, name: str) -> Optional[Any]:
        if self.tool_registry is not None:
            get_fn = getattr(self.tool_registry, "get_tool", None)
            if get_fn:
                return get_fn(name)
        return get_tool(name)

    def _handle_request(self, message: MCPMessage) -> Optional[MCPResponse]:
        method = message.method
        params = message.params or {}
        req_id = message.id

        if method == "initialize":
            return MCPResponse(
                id=req_id,
                result={
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "laap-mcp", "version": "0.1.0"},
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "resources": {"subscribe": False, "listChanged": False},
                        "prompts": {"listChanged": False},
                        "logging": {},
                    },
                },
            )

        if method == "notifications/initialized":
            # Lifecycle notification: no response required.
            logger.debug("MCP client initialized notification received")
            return None

        if method == "ping":
            return MCPResponse(id=req_id, result={})

        if method == "tools/list":
            tools = self._list_tools()
            return MCPResponse(
                id=req_id,
                result={
                    "tools": [
                        {
                            "name": t["name"],
                            "description": t.get("description", ""),
                            "inputSchema": t.get("schema", {}),
                        }
                        for t in tools
                    ]
                },
            )

        if method == "tools/call":
            name = params.get("name", "")
            arguments = params.get("arguments", {})
            handler = self._get_tool(name)
            if handler is None:
                return MCPResponse(
                    id=req_id,
                    error={"code": -32602, "message": f"Tool '{name}' not found"},
                )
            try:
                result = handler(**arguments)
            except Exception as exc:
                return MCPResponse(
                    id=req_id,
                    error={"code": -32603, "message": f"{type(exc).__name__}: {exc}"},
                )
            content = self._result_to_content(result)
            return MCPResponse(id=req_id, result={"content": content, "isError": False})

        # Resources — LAAP exposes no resources by default, but replying with
        # empty lists keeps the protocol complete for generic MCP clients.
        if method == "resources/list":
            return MCPResponse(id=req_id, result={"resources": [], "nextCursor": None})

        if method == "resources/read":
            uri = params.get("uri", "")
            return MCPResponse(
                id=req_id,
                error={"code": -32602, "message": f"Resource '{uri}' not found"},
            )

        if method == "resources/templates/list":
            return MCPResponse(id=req_id, result={"resourceTemplates": []})

        # Prompts — no prompts exposed by default.
        if method == "prompts/list":
            return MCPResponse(id=req_id, result={"prompts": [], "nextCursor": None})

        if method == "prompts/get":
            name = params.get("name", "")
            return MCPResponse(
                id=req_id,
                error={"code": -32602, "message": f"Prompt '{name}' not found"},
            )

        if method == "logging/setLevel":
            level = params.get("level", "info")
            logger.debug("MCP client requested log level: %s", level)
            return MCPResponse(id=req_id, result={})

        return MCPResponse(
            id=req_id,
            error={"code": -32601, "message": f"Method '{method}' not found"},
        )

    @staticmethod
    def _result_to_content(result: Any) -> List[Dict[str, Any]]:
        if isinstance(result, ToolResult):
            return [
                {
                    "type": "text",
                    "text": json.dumps(result.to_dict(), ensure_ascii=False),
                }
            ]
        if isinstance(result, dict):
            return [
                {
                    "type": "text",
                    "text": json.dumps(result, ensure_ascii=False),
                }
            ]
        return [{"type": "text", "text": str(result)}]

    async def _serve_loop(self) -> None:
        while self._running:
            try:
                message = await asyncio.wait_for(self.transport.receive(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            if message is None:
                break
            if not message.is_request():
                continue
            response = self._handle_request(message)
            if response is None:
                continue
            try:
                await self.transport.send(response)
            except Exception as exc:
                logger.warning("Failed to send MCP response: %s", exc)
                break

    async def start(self) -> None:
        """Start serving requests asynchronously."""
        self._running = True
        self._task = asyncio.create_task(self._serve_loop())

    async def stop(self) -> None:
        """Stop the server and close the transport."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.transport.close()

    def run_stdio(self):
        """Run over stdio (transport must already be attached)."""
        import asyncio

        async def _main():
            await self.start()
            try:
                while self._running:
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                pass
            finally:
                await self.stop()

        try:
            asyncio.run(_main())
        except KeyboardInterrupt:
            pass
