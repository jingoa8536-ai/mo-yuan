"""Unit tests for :mod:`godot_gdextension_loader`.

These tests intentionally avoid loading the real ``libgodot`` shared library:
the JSON-parsing and signature-extraction tests exercise only the pure-Python
parsing helpers, and the loader-not-found test asserts the graceful-degradation
contract. The benchmark test only runs when ``libgodot`` is actually
available on the host -- otherwise it is skipped via ``pytest.skip``.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

# Make the package importable regardless of pytest invocation CWD.
_PYTHON_DIR = Path(__file__).resolve().parents[1] / "python"
if str(_PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(_PYTHON_DIR))

from godot_gdextension_loader import (  # noqa: E402  (sys.path manipulation above)
    DEFAULT_INTERFACE_JSON_PATH,
    GDExtensionLoader,
    GDExtensionNotFoundError,
    _parse_interface_json,
)


# ---------------------------------------------------------------------------
# Tests: interface JSON parsing
# ---------------------------------------------------------------------------

def test_interface_json_parsed() -> None:
    """Verify the bundled ``gdextension_interface.json`` parses successfully.

    Asserts that the registry is non-empty and contains the core method-bind
    and singleton entry points that :class:`GDExtensionLoader` depends on.
    """
    registry = _parse_interface_json(DEFAULT_INTERFACE_JSON_PATH)
    assert isinstance(registry, dict)
    assert len(registry) >= 100, (
        f"Expected >=100 interface functions, got {len(registry)}"
    )
    # Core entry points required by the loader's high-level API.
    assert "object_method_bind_call" in registry
    assert "classdb_get_method_bind" in registry
    assert "global_get_singleton" in registry


def test_signature_parsing() -> None:
    """Verify function signatures (return type + arg types) are extracted correctly.

    Uses ``object_method_bind_call`` as the canonical example -- its C ABI
    signature is well-known and stable since GDExtension 4.1:

    ``void object_method_bind_call(
        GDExtensionMethodBindPtr p_method_bind,
        GDExtensionObjectPtr p_instance,
        const GDExtensionConstVariantPtr* p_args,
        GDExtensionInt p_arg_count,
        GDExtensionUninitializedVariantPtr r_ret,
        GDExtensionCallError* r_error);``
    """
    registry = _parse_interface_json(DEFAULT_INTERFACE_JSON_PATH)
    sig = registry["object_method_bind_call"]

    # Return type: void (no return_value field in the JSON).
    assert sig["return_type"] == "void"

    # 6 arguments in the documented order.
    arg_types = sig["arg_types"]
    assert len(arg_types) == 6
    assert arg_types[0] == "GDExtensionMethodBindPtr"
    assert arg_types[1] == "GDExtensionObjectPtr"
    assert arg_types[2] == "const GDExtensionConstVariantPtr*"
    assert arg_types[3] == "GDExtensionInt"
    assert arg_types[4] == "GDExtensionUninitializedVariantPtr"
    assert arg_types[5] == "GDExtensionCallError*"

    # Argument names should be non-empty and match the C ABI.
    arg_names = sig["arg_names"]
    assert len(arg_names) == 6
    assert arg_names[0] == "p_method_bind"
    assert arg_names[1] == "p_instance"
    assert arg_names[3] == "p_arg_count"

    # classdb_get_method_bind should return GDExtensionMethodBindPtr.
    sig2 = registry["classdb_get_method_bind"]
    assert sig2["return_type"] == "GDExtensionMethodBindPtr"
    assert "GDExtensionConstStringNamePtr" in sig2["arg_types"]

    # global_get_singleton should return GDExtensionObjectPtr.
    sig3 = registry["global_get_singleton"]
    assert sig3["return_type"] == "GDExtensionObjectPtr"


# ---------------------------------------------------------------------------
# Tests: graceful degradation when libgodot is unavailable
# ---------------------------------------------------------------------------

def test_loader_not_found_raises() -> None:
    """Instantiating with a nonexistent lib_path raises GDExtensionNotFoundError."""
    with pytest.raises(GDExtensionNotFoundError):
        GDExtensionLoader(lib_path="/nonexistent/path/to/libgodot.so")


def test_loader_not_found_raises_windows_path() -> None:
    """Same contract with a Windows-style nonexistent path."""
    with pytest.raises(GDExtensionNotFoundError):
        GDExtensionLoader(lib_path=r"C:\nonexistent\libgodot.dll")


# ---------------------------------------------------------------------------
# Tests: benchmark structural contract
# ---------------------------------------------------------------------------

class _MockJSONRPCClient:
    """Mock JSONRPC client used by the benchmark test.

    Returns dummy values without contacting any server -- only the dispatch
    overhead (attribute lookup + method call) is measured.
    """

    def __init__(self) -> None:
        self.call_count: int = 0

    def call_method(self, class_name: str, method: str, *args: Any) -> int:
        self.call_count += 1
        return 0


def test_benchmark_returns_dict() -> None:
    """Verify ``benchmark_vs_jsonrpc`` returns a dict with the required keys.

    This test is skipped if ``libgodot`` is not available on the host, since
    the GDExtension side of the benchmark requires a real C ABI call.
    """
    try:
        loader = GDExtensionLoader()
    except GDExtensionNotFoundError as exc:
        pytest.skip(f"libgodot not available: {exc}")

    mock_client = _MockJSONRPCClient()
    result = loader.benchmark_vs_jsonrpc(mock_client, iterations=10)

    assert isinstance(result, dict)
    assert "jsonrpc_avg_ms" in result
    assert "gdextension_avg_ms" in result
    assert "speedup" in result

    # Averages should be non-negative floats.
    assert isinstance(result["jsonrpc_avg_ms"], float)
    assert isinstance(result["gdextension_avg_ms"], float)
    assert result["jsonrpc_avg_ms"] >= 0.0
    assert result["gdextension_avg_ms"] >= 0.0
    # Speedup may be ``inf`` if gdextension_avg_ms is 0.
    assert isinstance(result["speedup"], float)


# ---------------------------------------------------------------------------
# Tests: module-level import contract
# ---------------------------------------------------------------------------

def test_module_imports_without_libgodot() -> None:
    """Importing the module must never load libgodot (no import-time side effects)."""
    # The fact that we successfully imported the module at the top of this
    # file is sufficient evidence; this test makes the contract explicit and
    # asserts the public symbols are present.
    import godot_gdextension_loader as mod

    assert hasattr(mod, "GDExtensionLoader")
    assert hasattr(mod, "GDExtensionNotFoundError")
    assert hasattr(mod, "DEFAULT_INTERFACE_JSON_PATH")
    assert isinstance(mod.DEFAULT_INTERFACE_JSON_PATH, Path)


def test_loader_class_signature_methods_exist() -> None:
    """Verify the GDExtensionLoader class exposes the spec-required methods."""
    # Inspect the class without instantiating it (no libgodot needed).
    for method_name in (
        "load_function",
        "call_method_bind",
        "get_singleton",
        "object_call",
        "benchmark_vs_jsonrpc",
    ):
        assert callable(getattr(GDExtensionLoader, method_name)), (
            f"GDExtensionLoader.{method_name} must be defined"
        )
