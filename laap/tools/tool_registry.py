"""
LAAP — Unified Tool Registry with automatic OpenAI-compatible JSON Schema generation.

This module provides a global registry of tools (``TOOL_REGISTRY``) and a backward-
compatible ``ToolRegistry`` class used by existing Agent/tool code.  Tools are
registered by name with their callable handler, category, and an inferred JSON
Schema produced from the function's type hints and defaults using only the
standard library.
"""

from __future__ import annotations

import inspect
import json
import logging
import re
import threading
from typing import Any, Callable, Dict, List, Optional, Union

from laap.tools.base import Tool, ToolResult

try:
    from typing import get_origin, get_args  # type: ignore
except ImportError:  # pragma: no cover
    def get_origin(tp):  # type: ignore
        return getattr(tp, "__origin__", None)

    def get_args(tp):  # type: ignore
        return getattr(tp, "__args__", ())


logger = logging.getLogger("laap.tools.tool_registry")

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {}
"""Global mapping of tool name -> metadata dict."""

_registry_lock = threading.RLock()

_DISCOVER_MODULES = [
    "laap.tools.browser_auto",
    "laap.tools.web",
    "laap.tools.shell",
    "laap.tools.vision",
    "laap.tools.memory_tool",
    "laap.tools.kanban",
    "laap.tools.delegate",
    "laap.tools.filesystem",
    "laap.tools.terminal",
    "laap.tools.code_runner",
]

_MODULE_CATEGORIES = {
    "laap.tools.browser_auto": "browser",
    "laap.tools.web": "web",
    "laap.tools.shell": "shell",
    "laap.tools.vision": "vision",
    "laap.tools.memory_tool": "memory",
    "laap.tools.kanban": "kanban",
    "laap.tools.delegate": "delegate",
    "laap.tools.filesystem": "filesystem",
    "laap.tools.terminal": "terminal",
    "laap.tools.code_runner": "code_runner",
}

_JSON_TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
    type(None): "null",
}


# ── JSON Schema helpers ───────────────────────────────────────────


def _resolve_json_type(tp: Any) -> str:
    """Map a Python type hint to a JSON Schema primitive type."""
    if tp in _JSON_TYPE_MAP:
        return _JSON_TYPE_MAP[tp]

    origin = get_origin(tp)
    if origin is list:
        return "array"
    if origin is dict:
        return "object"
    if origin is Union:
        # Optional[T] is Union[T, None]; resolve the non-None alternative.
        args = [a for a in get_args(tp) if a is not type(None)]
        if len(args) == 1:
            return _resolve_json_type(args[0])
        return "string"
    return "string"


def _is_optional(tp: Any) -> bool:
    """Return True if *tp* is Optional[T] (i.e. Union[..., None])."""
    origin = get_origin(tp)
    if origin is Union:
        return type(None) in get_args(tp)
    return False


def _extract_param_descriptions(doc: str) -> Dict[str, str]:
    """Extract ``Args:`` descriptions from a docstring.

    Tries the lightweight ``docstring_parser`` package when available, then
    falls back to a simple stdlib parser so the registry stays usable without
    optional dependencies.
    """
    if not doc:
        return {}

    try:
        from docstring_parser import parse as _doc_parse  # type: ignore

        parsed = _doc_parse(doc)
        return {
            p.arg_name: (p.description or "")
            for p in (parsed.params or [])
            if p.arg_name
        }
    except Exception:
        pass

    descriptions: Dict[str, str] = {}
    lines = doc.splitlines()
    in_args = False
    current: Optional[str] = None
    section_re = re.compile(r"^[A-Z][a-zA-Z0-9_ ]*:$")

    for raw in lines:
        stripped = raw.strip()
        if stripped.lower() == "args:":
            in_args = True
            current = None
            continue
        if not in_args:
            continue
        if not stripped:
            current = None
            continue
        if section_re.match(stripped):
            break

        m = re.match(r"^-\s*(\w+)\s*:\s*(.*)$", stripped)
        if not m:
            m = re.match(r"^(\w+)\s*:\s*(.*)$", stripped)
        if m:
            name, desc = m.group(1), m.group(2).strip()
            current = name
            descriptions[name] = desc
        elif current and raw.startswith((" ", "\t")):
            descriptions[current] = (descriptions.get(current, "") + " " + stripped).strip()

    return descriptions


def _build_schema(fn: Callable) -> Dict[str, Any]:
    """Build an OpenAI-compatible parameter schema from *fn*'s signature."""
    sig = inspect.signature(fn)
    doc = inspect.getdoc(fn) or ""
    param_descs = _extract_param_descriptions(doc)

    properties: Dict[str, Any] = {}
    required: List[str] = []

    for pname, param in sig.parameters.items():
        if pname in ("self", "cls", "agent", "fc"):
            continue
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue

        ann = param.annotation if param.annotation != inspect.Parameter.empty else str
        ptype = _resolve_json_type(ann)
        prop: Dict[str, Any] = {"type": ptype}

        desc = param_descs.get(pname)
        if desc:
            prop["description"] = desc

        if param.default is not inspect.Parameter.empty and param.default is not None:
            try:
                json.dumps(param.default)
                prop["default"] = param.default
            except (TypeError, ValueError):
                pass

        properties[pname] = prop

        has_default = param.default is not inspect.Parameter.empty
        if not (_is_optional(ann) or has_default):
            required.append(pname)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


# ── Global registry API ───────────────────────────────────────────


def _register(
    name: str,
    fn: Callable,
    category: str,
    description: str,
    overwrite: bool = False,
) -> bool:
    """Store a tool in the global registry."""
    if not callable(fn):
        raise TypeError(f"Tool handler for '{name}' must be callable")

    with _registry_lock:
        if name in TOOL_REGISTRY and not overwrite:
            logger.debug("Tool already registered, skipping: %s", name)
            return False

    desc = description or inspect.getdoc(fn) or ""
    schema = _build_schema(fn)

    with _registry_lock:
        TOOL_REGISTRY[name] = {
            "name": name,
            "fn": fn,
            "category": category,
            "description": desc,
            "schema": schema,
        }
    logger.debug("Registered tool: %s [%s]", name, category)
    return True


def register_tool(
    name: Optional[Union[str, Callable]] = None,
    fn: Optional[Callable] = None,
    category: str = "general",
    description: str = "",
) -> Any:
    """Register a callable as a tool.

    Usable as a decorator or as a plain function:

        @register_tool
        def my_tool(x: int) -> str: ...

        @register_tool(name="my_tool", category="data")
        def my_tool_impl(x: int) -> str: ...

        register_tool("my_tool", my_function, category="data")
    """
    # @register_tool (no parentheses)
    if callable(name) and fn is None:
        actual_fn = name
        _register(actual_fn.__name__, actual_fn, category, description)
        return actual_fn

    # register_tool("name", fn)
    if isinstance(name, str) and callable(fn):
        _register(name, fn, category, description)
        return fn

    # Decorator form with optional name
    actual_name = name

    def decorator(f: Callable) -> Callable:
        nonlocal actual_name
        n = actual_name if isinstance(actual_name, str) else f.__name__
        _register(n, f, category, description)
        return f

    return decorator


def get_tool(name: str) -> Optional[Callable]:
    """Return the callable registered under *name*, or ``None``."""
    with _registry_lock:
        entry = TOOL_REGISTRY.get(name)
    return entry["fn"] if entry else None


def list_tools(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """List registered tools as metadata dicts, optionally filtered by category."""
    with _registry_lock:
        items = list(TOOL_REGISTRY.values())

    result = []
    for item in items:
        if category is not None and item["category"] != category:
            continue
        result.append(
            {
                "name": item["name"],
                "category": item["category"],
                "description": item["description"],
                "schema": item["schema"],
                "fn": item["fn"],
            }
        )
    return result


def get_tool_schema(name: str) -> Dict[str, Any]:
    """Return the OpenAI-compatible parameter schema for *name*."""
    with _registry_lock:
        entry = TOOL_REGISTRY.get(name)
    if entry is None:
        raise KeyError(f"Tool '{name}' is not registered")
    return dict(entry["schema"])


def discover_actors() -> List[str]:
    """Return the list of registered tool actor capability names."""
    with _registry_lock:
        return sorted(TOOL_REGISTRY.keys())


# ── Backward-compatible ToolRegistry class ────────────────────────


class ToolRegistry:
    """Backward-compatible registry that delegates to the global TOOL_REGISTRY."""

    def register(self, tool: Tool, overwrite: bool = False) -> bool:
        """Register a ``Tool`` dataclass instance."""
        if tool.handler is None:
            return False
        desc = tool.description or inspect.getdoc(tool.handler) or ""
        return _register(
            tool.name,
            tool.handler,
            tool.category or "general",
            desc,
            overwrite=overwrite,
        )

    def tool(
        self,
        name: Optional[str] = None,
        category: str = "general",
        description: Optional[str] = None,
    ) -> Callable:
        """Decorator: ``@registry.tool(name=..., category=...)``."""
        def decorator(fn: Callable) -> Callable:
            desc = description or inspect.getdoc(fn) or ""
            _register(name or fn.__name__, fn, category, desc)
            return fn

        return decorator

    def register_fn(
        self,
        fn: Callable,
        name: Optional[str] = None,
        category: str = "general",
        description: Optional[str] = None,
    ) -> bool:
        """Register a function, inferring its schema from the signature."""
        desc = description or inspect.getdoc(fn) or ""
        _register(name or fn.__name__, fn, category, desc)
        return True

    def get(self, name: str) -> Optional[Tool]:
        """Return a ``Tool`` dataclass for the registered tool."""
        with _registry_lock:
            entry = TOOL_REGISTRY.get(name)
        if entry is None:
            return None
        return Tool(
            name=entry["name"],
            description=entry["description"],
            parameters=entry["schema"],
            handler=entry["fn"],
            category=entry["category"],
        )

    def call(self, name: str, **kwargs: Any) -> Any:
        """Execute a registered tool by name."""
        fn = get_tool(name)
        if fn is None:
            return json.dumps({"error": f"Tool '{name}' not found"})
        try:
            return fn(**kwargs)
        except Exception as e:
            return json.dumps({"error": f"{type(e).__name__}: {str(e)[:200]}"})

    def list(self, category: Optional[str] = None) -> List[Tool]:
        """Return registered tools as ``Tool`` dataclass instances."""
        return [
            Tool(
                name=item["name"],
                description=item["description"],
                parameters=item["schema"],
                handler=item["fn"],
                category=item["category"],
            )
            for item in list_tools(category)
        ]

    @property
    def count(self) -> int:
        return len(TOOL_REGISTRY)

    @property
    def categories(self) -> List[str]:
        with _registry_lock:
            return sorted({item["category"] for item in TOOL_REGISTRY.values()})


# ── Auto-discovery ────────────────────────────────────────────────


def _category_for_module(module_name: str) -> str:
    return _MODULE_CATEGORIES.get(module_name, module_name.rsplit(".", 1)[-1].replace("_", ""))


def _register_module_functions(module: Any) -> None:
    """Register top-level functions and class staticmethods from *module*."""
    category = _category_for_module(module.__name__)

    for attr_name in dir(module):
        if attr_name.startswith("_") or attr_name == "register_all":
            continue

        obj = getattr(module, attr_name)

        if inspect.isfunction(obj) and getattr(obj, "__module__", None) == module.__name__:
            register_tool(name=attr_name, fn=obj, category=category)
            continue

        if inspect.isclass(obj) and getattr(obj, "__module__", None) == module.__name__:
            for method_name, method in inspect.getmembers(obj, predicate=inspect.isfunction):
                if method_name.startswith("_"):
                    continue
                if not isinstance(obj.__dict__.get(method_name), staticmethod):
                    continue
                desc = inspect.getdoc(method) or ""
                register_tool(name=method_name, fn=method, category=category, description=desc)


def discover_and_register() -> None:
    """Import all configured tool modules and register their tools."""
    import importlib

    for modname in _DISCOVER_MODULES:
        try:
            module = importlib.import_module(modname)
        except Exception as exc:
            logger.warning("Failed to import tool module %s: %s", modname, exc)
            continue

        if hasattr(module, "register_all"):
            try:
                registry_instance = ToolRegistry()
                module.register_all(registry_instance)
            except Exception as exc:
                logger.warning("register_all failed for %s: %s", modname, exc)

        # Register any remaining public top-level functions / staticmethods.
        # Duplicates are silently skipped because register_tool does not
        # overwrite by default.
        try:
            _register_module_functions(module)
        except Exception as exc:
            logger.warning("Failed to register functions from %s: %s", modname, exc)


# Register built-in tool modules when this module is first imported.
discover_and_register()
