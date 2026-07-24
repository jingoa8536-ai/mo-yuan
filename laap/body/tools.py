"""LAAP Body layer — public unified tool registry API."""

from __future__ import annotations

from typing import List

from laap.tools.tool_registry import (
    TOOL_REGISTRY,
    get_tool,
    get_tool_schema,
    list_tools,
    register_tool,
)

__all__ = [
    "get_tool",
    "list_tools",
    "get_tool_schema",
    "register_tool",
    "discover_actors",
]


def discover_actors() -> List[str]:
    """Return the list of registered tool actor capability names."""
    return sorted(TOOL_REGISTRY.keys())
