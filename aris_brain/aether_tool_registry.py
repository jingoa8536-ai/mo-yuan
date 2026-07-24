"""
Aether Tool Registry — 工具注册与执行引擎 v1
=============================================
用法:
    from aether_tool_registry import tool, get_registry
    
    @tool(description="读取文件内容", category="filesystem")
    def read_file(path: str, limit: int = 100) -> dict:
        \"\"\"读取指定文件的内容。\"\"\"
        ...
    
    registry = get_registry()
    result = registry.execute("read_file", path="/etc/hosts")
"""

import inspect
import json
import time
import functools
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, get_type_hints


# ═══════════════════════════════════════════════════════════
# 类型系统
# ═══════════════════════════════════════════════════════════

TYPE_MAP = {
    str: "string", int: "integer", float: "number", bool: "boolean",
    dict: "object", list: "array", type(None): "null",
    Any: "string",
}


def _pytype_to_json(py_type) -> str:
    """Python 类型 → JSON Schema 类型。"""
    if hasattr(py_type, "__origin__"):  # 泛型如 List[str], Optional[int]
        origin = py_type.__origin__
        if origin is list:
            return "array"
        elif origin is dict:
            return "object"
        elif origin is Union:  # noqa: F821
            args = py_type.__args__
            non_none = [a for a in args if a is not type(None)]
            return _pytype_to_json(non_none[0]) if non_none else "string"
    return TYPE_MAP.get(py_type, "string")


def _pytype_to_llm_type(py_type) -> str:
    """Python 类型 → LLM 工具调用格式的类型。"""
    base = _pytype_to_json(py_type)
    if base == "integer": return "integer"
    if base == "number": return "number"
    if base == "boolean": return "boolean"
    if base == "array": return "array"
    if base == "object": return "object"
    return "string"


@dataclass
class ToolParameter:
    """工具参数的 Schema 定义。"""
    name: str
    type: str
    description: str = ""
    required: bool = True
    default: Any = None


@dataclass
class ToolDef:
    """工具定义。"""
    name: str
    func: Callable
    description: str
    category: str = "general"
    parameters: List[ToolParameter] = field(default_factory=list)
    is_async: bool = False
    latency_ms: float = 0.0
    call_count: int = 0
    last_error: Optional[str] = None

    def to_llm_format(self) -> dict:
        """转换为 LLM function calling 格式。"""
        properties = {}
        required = []
        for p in self.parameters:
            prop = {"type": p.type, "description": p.description}
            if p.default is not None:
                prop["default"] = p.default
            properties[p.name] = prop
            if p.required:
                required.append(p.name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def to_actor_format(self) -> dict:
        """转换为 Actor Capability 格式。"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": [p.name for p in self.parameters],
            "latency_ms": self.latency_ms,
            "call_count": self.call_count,
        }


# ═══════════════════════════════════════════════════════════
# 注册器
# ═══════════════════════════════════════════════════════════

class ToolRegistry:
    """全局工具注册中心。"""

    def __init__(self):
        self._tools: Dict[str, ToolDef] = {}
        self._categories: Dict[str, List[str]] = {}

    # ─── 注册 ────────────────────────────────────────

    def register(self, tool_def: ToolDef) -> ToolDef:
        """注册一个工具。"""
        self._tools[tool_def.name] = tool_def
        self._categories.setdefault(tool_def.category, []).append(tool_def.name)
        return tool_def

    def register_func(
        self,
        func: Callable,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: str = "general",
    ) -> ToolDef:
        """从函数自动提取参数并注册。"""
        name = name or func.__name__
        desc = description or (func.__doc__ or "").strip().split("\n")[0]
        sig = inspect.signature(func)
        hints = get_type_hints(func) if hasattr(func, "__annotations__") else {}
        
        parameters = []
        for pname, param in sig.parameters.items():
            if pname in ("self", "cls"):
                continue
            py_type = hints.get(pname, str)
            default = param.default if param.default is not inspect.Parameter.empty else None
            required = param.default is inspect.Parameter.empty
            p_desc = ""
            # 从文档字符串提取参数描述
            if func.__doc__:
                for line in func.__doc__.split("\n"):
                    line = line.strip()
                    if line.startswith(f":param {pname}:"):
                        p_desc = line.split(":", 2)[-1].strip()
                        break
            
            parameters.append(ToolParameter(
                name=pname,
                type=_pytype_to_llm_type(py_type),
                description=p_desc,
                required=required,
                default=default,
            ))
        
        is_async = inspect.iscoroutinefunction(func)
        tool_def = ToolDef(
            name=name, func=func, description=desc,
            category=category, parameters=parameters,
            is_async=is_async,
        )
        return self.register(tool_def)

    # ─── 执行 ────────────────────────────────────────

    def execute(self, name: str, **kwargs) -> Any:
        """执行一个已注册的工具。"""
        tool_def = self._tools.get(name)
        if not tool_def:
            raise KeyError(f"工具 '{name}' 未注册")
        
        t0 = time.time()
        try:
            if tool_def.is_async:
                raise ValueError(f"工具 '{name}' 是异步的，请用 execute_async")
            result = tool_def.func(**kwargs)
            elapsed = (time.time() - t0) * 1000
            tool_def.latency_ms = tool_def.latency_ms * 0.7 + elapsed * 0.3
            tool_def.call_count += 1
            return result
        except Exception as e:
            elapsed = (time.time() - t0) * 1000
            tool_def.last_error = f"{type(e).__name__}: {str(e)[:100]}"
            tool_def.call_count += 1
            raise

    async def execute_async(self, name: str, **kwargs) -> Any:
        """执行一个异步工具。"""
        tool_def = self._tools.get(name)
        if not tool_def:
            raise KeyError(f"工具 '{name}' 未注册")
        
        t0 = time.time()
        try:
            if tool_def.is_async:
                result = await tool_def.func(**kwargs)
            else:
                result = tool_def.func(**kwargs)
            elapsed = (time.time() - t0) * 1000
            tool_def.latency_ms = tool_def.latency_ms * 0.7 + elapsed * 0.3
            tool_def.call_count += 1
            return result
        except Exception as e:
            elapsed = (time.time() - t0) * 1000
            tool_def.last_error = f"{type(e).__name__}: {str(e)[:100]}"
            tool_def.call_count += 1
            raise

    # ─── 查询 ────────────────────────────────────────

    def get(self, name: str) -> Optional[ToolDef]:
        return self._tools.get(name)

    def list_tools(self, category: Optional[str] = None) -> List[ToolDef]:
        if category:
            return [self._tools[n] for n in self._categories.get(category, [])]
        return list(self._tools.values())

    def get_schemas_for_llm(self) -> List[dict]:
        """返回所有工具的 LLM function calling 格式。"""
        return [t.to_llm_format() for t in self._tools.values()]

    def get_stats(self) -> dict:
        return {
            "total_tools": len(self._tools),
            "categories": {k: len(v) for k, v in self._categories.items()},
            "total_calls": sum(t.call_count for t in self._tools.values()),
            "avg_latency": sum(t.latency_ms for t in self._tools.values()) / max(len(self._tools), 1),
        }


# ═══════════════════════════════════════════════════════════
# @tool 装饰器
# ═══════════════════════════════════════════════════════════

_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """获取全局 ToolRegistry 单例。"""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def tool(
    name: Optional[str] = None,
    *,
    description: Optional[str] = None,
    category: str = "general",
):
    """装饰器：将函数注册为工具。

    用法:
        @tool(description="读取文件", category="filesystem")
        def read_file(path: str, limit: int = 100) -> dict:
            ...
    """
    def decorator(func: Callable) -> Callable:
        registry = get_registry()
        registry.register_func(
            func,
            name=name,
            description=description,
            category=category,
        )
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════
# 内置工具 — 包装 Aether 现有引擎
# ═══════════════════════════════════════════════════════════

def _register_builtins():
    """注册 Aether 引擎的现有能力作为工具。"""
    registry = get_registry()
    
    @tool(description="查系统状态", category="system")
    def check_status() -> dict:
        """返回当前 Aether 引擎的运行状态。"""
        # 委托给 RulesEngine
        try:
            from aris_orchestration_bridge import get_bridge
            b = get_bridge()
            r = b.process("查系统状态")
            if r:
                return {"status": "ok", "data": r.get("output", "")}
        except Exception as e:
            pass
        return {"status": "ok", "message": "Aether 运行正常"}

    @tool(description="读取文件内容", category="filesystem")
    def read_file(path: str, limit: int = 200) -> str:
        """读取文件内容。path: 文件路径, limit: 最大行数。"""
        try:
            from hermes_tools import read_file as _read
            r = _read(path=path, limit=limit)
            return r.get("content", "")
        except Exception as e:
            # 回退到原生 Python
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            return "".join(lines[:limit])

    @tool(description="搜索文件内容", category="filesystem")
    def search_files(pattern: str, path: str = ".") -> list:
        """搜索文件内容。pattern: 正则表达式, path: 搜索目录。"""
        try:
            from hermes_tools import search_files as _search
            r = _search(pattern=pattern, path=path)
            return r.get("matches", [])
        except Exception:
            import subprocess
            r = subprocess.run(
                ["grep", "-rn", pattern, path],
                capture_output=True, text=True, timeout=10
            )
            return r.stdout.split("\n")[:20]

    @tool(description="执行终端命令", category="system")
    def run_command(command: str) -> str:
        """执行终端命令并返回输出。"""
        import subprocess
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        return (r.stdout or "")[:2000] + (r.stderr or "")[:500]

    @tool(description="写入文件", category="filesystem")
    def write_file(path: str, content: str) -> str:
        """写入文件（覆盖）。path: 路径, content: 内容。"""
        try:
            from hermes_tools import write_file as _write
            _write(path=path, content=content)
        except Exception:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        return f"已写入 {path} ({len(content)} 字符)"

    @tool(description="搜索会话历史", category="memory")
    def search_memory(query: str) -> list:
        """搜索过去的对话记录。"""
        try:
            from aris_episodic_memory import find_similar
            return find_similar(query, top_k=3)
        except Exception:
            return []

    @tool(description="获取当前时间", category="system")
    def get_time() -> str:
        """返回当前日期和时间。"""
        import datetime
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# 模块加载时自动注册内置工具
_register_builtins()


# ═══════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    registry = get_registry()
    print(f"已注册 {len(registry.list_tools())} 个工具")
    print()
    for tool_def in registry.list_tools():
        params = ", ".join(f"{p.name}:{p.type}" for p in tool_def.parameters)
        print(f"  {tool_def.name:20} [{tool_def.category:12}] ({params})")
        print(f"  {'':20}  {tool_def.description[:60]}")
        print()
    
    print("LLM Schemas:")
    import json
    for s in registry.get_schemas_for_llm():
        print(json.dumps(s, ensure_ascii=False, indent=2)[:300])
        print()
