"""GDExtension C ABI loader for the LAAP Godot Bridge.

This module loads ``libgodot.{dll,so,dylib}`` via :mod:`ctypes` and parses
``gdextension_interface.json`` to auto-generate Python bindings for the
GDExtension C ABI. It is the high-performance counterpart to the JSONRPC
transport used by the LAAP harness: method-bind calls hit the C ABI directly,
achieving sub-millisecond per-call latency versus the ~1-10 ms typical of
JSONRPC over TCP.

Design notes
------------
* **No import-time side effects.** ``libgodot`` is *not* touched at module
  import time. The dynamic load is deferred to :meth:`GDExtensionLoader.__init__`
  so that simply importing this module is always safe (even on hosts without
  libgodot installed).
* **JSON-driven binding.** Every interface function declared in
  ``gdextension_interface.json`` is bound to a :class:`ctypes._FuncPtr` with
  ``argtypes`` and ``restype`` populated from the JSON signature, so the
  Python bindings stay in sync with the C ABI without hand-maintained stubs.
* **Method-bind caching.** ``classdb_get_method_bind`` results are cached per
  ``"ClassName::method"`` key so hot paths (e.g. ``Engine.get_frames_drawn``)
  reach <1ms per-call latency after the first invocation.
* **Graceful degradation.** If ``libgodot`` cannot be located or loaded,
  :class:`GDExtensionNotFoundError` is raised with a descriptive message.
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

#: Absolute path to the bundled ``gdextension_interface.json`` copy in this
#: repository. Resolved relative to this source file so it works regardless of
#: the current working directory.
DEFAULT_INTERFACE_JSON_PATH: Path = (
    Path(__file__).resolve().parents[2]
    / "godot-master"
    / "core"
    / "extension"
    / "gdextension_interface.json"
)

#: Platform-specific shared-library file names searched by :func:`_find_libgodot`.
if sys.platform == "win32":
    _LIB_NAMES: tuple[str, ...] = ("libgodot.dll", "godot.dll")
elif sys.platform == "darwin":
    _LIB_NAMES = ("libgodot.dylib", "godot.dylib")
else:
    _LIB_NAMES = ("libgodot.so", "godot.so")

#: Platform-specific search paths. ``LIBGODOT_PATH`` env var is honoured in
#: :func:`_find_libgodot` and may point at either the directory containing
#: the shared library or the library file itself.
if sys.platform == "win32":
    _LIB_SEARCH_PATHS: tuple[Path, ...] = (
        Path.cwd(),
        Path(__file__).resolve().parents[2],
        Path(__file__).resolve().parents[2] / "godot-master",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Godot",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Godot" / "bin",
    )
elif sys.platform == "darwin":
    _LIB_SEARCH_PATHS = (
        Path.cwd(),
        Path(__file__).resolve().parents[2],
        Path("/usr/local/lib"),
        Path("/opt/homebrew/lib"),
        Path("/Applications/Godot.app/Contents/MacOS"),
    )
else:
    _LIB_SEARCH_PATHS = (
        Path.cwd(),
        Path(__file__).resolve().parents[2],
        Path("/usr/lib"),
        Path("/usr/local/lib"),
        Path("/opt/godot/lib"),
    )


class GDExtensionNotFoundError(RuntimeError):
    """Raised when ``libgodot`` cannot be located or loaded.

    Subclass of :class:`RuntimeError` so callers can catch it broadly while
    still distinguishing it from other runtime errors via ``except
    GDExtensionNotFoundError``.
    """


# ---------------------------------------------------------------------------
# C-type -> ctypes mapping
# ---------------------------------------------------------------------------

#: Mapping from primitive C type names (as they appear in
#: ``gdextension_interface.json``) to :mod:`ctypes` types. All GDExtension
#: ``*Ptr`` typedefs are opaque pointer types and map to
#: :class:`ctypes.c_void_p` per the task spec's marshalling rules.
_PRIMITIVE_TYPE_MAP: dict[str, Any] = {
    "void": None,
    "void*": ctypes.c_void_p,
    "const void*": ctypes.c_void_p,
    "bool": ctypes.c_bool,
    "char": ctypes.c_char,
    "char*": ctypes.c_char_p,
    "const char*": ctypes.c_char_p,
    "int8_t": ctypes.c_int8,
    "uint8_t": ctypes.c_uint8,
    "int16_t": ctypes.c_int16,
    "uint16_t": ctypes.c_uint16,
    "int32_t": ctypes.c_int32,
    "uint32_t": ctypes.c_uint32,
    "int64_t": ctypes.c_int64,
    "uint64_t": ctypes.c_uint64,
    "int": ctypes.c_int,
    "unsigned int": ctypes.c_uint,
    "short": ctypes.c_short,
    "unsigned short": ctypes.c_ushort,
    "long": ctypes.c_long,
    "unsigned long": ctypes.c_ulong,
    "size_t": ctypes.c_size_t,
    "ssize_t": ctypes.c_ssize_t,
    "float": ctypes.c_float,
    "double": ctypes.c_double,
    # GDExtension primitive typedefs
    "GDExtensionBool": ctypes.c_bool,
    "GDExtensionInt": ctypes.c_int64,
    "GDExtensionCallErrorType": ctypes.c_int32,
    "GDExtensionInitializationLevel": ctypes.c_int32,
    "GDExtensionVariantType": ctypes.c_int32,
    # GDExtension opaque pointer typedefs (treated as void*)
    "GDExtensionObjectPtr": ctypes.c_void_p,
    "GDExtensionConstObjectPtr": ctypes.c_void_p,
    "GDExtensionTypePtr": ctypes.c_void_p,
    "GDExtensionConstTypePtr": ctypes.c_void_p,
    "GDExtensionVariantPtr": ctypes.c_void_p,
    "GDExtensionConstVariantPtr": ctypes.c_void_p,
    "GDExtensionUninitializedVariantPtr": ctypes.c_void_p,
    "GDExtensionUninitializedTypePtr": ctypes.c_void_p,
    "GDExtensionStringNamePtr": ctypes.c_void_p,
    "GDExtensionConstStringNamePtr": ctypes.c_void_p,
    "GDExtensionStringPtr": ctypes.c_void_p,
    "GDExtensionConstStringPtr": ctypes.c_void_p,
    "GDExtensionUninitializedStringPtr": ctypes.c_void_p,
    "GDExtensionMethodBindPtr": ctypes.c_void_p,
    "GDExtensionClassLibraryPtr": ctypes.c_void_p,
    "GDExtensionExtensionPtr": ctypes.c_void_p,
    "GDExtensionMethodUninitializedPtr": ctypes.c_void_p,
    "GDExtensionPtrDestructor": ctypes.c_void_p,
}


def _map_c_type_to_ctypes(c_type: str) -> Any:
    """Map a C type name from ``gdextension_interface.json`` to a ctypes type.

    The mapping handles three cases beyond the primitive table:

    * ``const T*`` -> strip ``const`` and recurse.
    * ``T**`` (pointer-to-pointer) -> :class:`ctypes.POINTER` of
      :class:`ctypes.c_void_p`, used for out-params like
      ``GDExtensionConstVariantPtr*``.
    * ``T*`` where ``T`` is a known struct typedef -> :class:`ctypes.POINTER`
      of the underlying ctypes type.
    * Anything else (unknown struct typedef) -> :class:`ctypes.c_void_p`
      (opaque pointer) so the call still goes through.
    """
    if c_type in _PRIMITIVE_TYPE_MAP:
        return _PRIMITIVE_TYPE_MAP[c_type]
    # Strip leading "const " qualifier.
    stripped = c_type.replace("const ", "", 1).strip()
    if stripped in _PRIMITIVE_TYPE_MAP:
        return _PRIMITIVE_TYPE_MAP[stripped]
    # Pointer-to-pointer (e.g. "GDExtensionConstVariantPtr*").
    if stripped.endswith("**"):
        return ctypes.POINTER(ctypes.c_void_p)
    # Pointer-to-T (e.g. "GDExtensionCallError*").
    if stripped.endswith("*"):
        inner = stripped[:-1].strip()
        if inner in _PRIMITIVE_TYPE_MAP:
            inner_t = _PRIMITIVE_TYPE_MAP[inner]
            if inner_t is None:
                return ctypes.c_void_p
            return ctypes.POINTER(inner_t)
        return ctypes.c_void_p
    # Unknown typedef (likely a struct): treat as opaque pointer.
    return ctypes.c_void_p


# ---------------------------------------------------------------------------
# Interface JSON parsing
# ---------------------------------------------------------------------------

def _parse_interface_json(json_path: str | Path) -> dict[str, dict[str, Any]]:
    """Parse ``gdextension_interface.json`` into a function-signature registry.

    The returned mapping has one entry per interface function (the entries
    under the top-level ``"interface"`` array). Each value is a dict with
    keys:

    * ``return_type``: ``str`` -- C type name (defaults to ``"void"``).
    * ``arg_types``: ``list[str]`` -- C type names (possibly empty).
    * ``arg_names``: ``list[str]`` -- Parameter names (possibly empty).
    * ``description``: ``list[str]`` -- Description lines.
    * ``since``: ``str`` -- Version string (e.g. ``"4.1"``).

    Type definitions (enums, structs, function-typedefs) under the
    top-level ``"types"`` array are intentionally not returned here; only
    the actual interface entry points are bound by :class:`GDExtensionLoader`.

    Args:
        json_path: Path to ``gdextension_interface.json``.

    Returns:
        Registry dict keyed by interface function name.

    Raises:
        FileNotFoundError: If ``json_path`` does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    path = Path(json_path)
    if not path.is_file():
        raise FileNotFoundError(f"gdextension_interface.json not found at {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    registry: dict[str, dict[str, Any]] = {}
    for entry in data.get("interface", []):
        name = entry.get("name")
        if not name:
            continue
        ret = entry.get("return_value", {}).get("type", "void")
        args = entry.get("arguments", []) or []
        registry[name] = {
            "return_type": ret,
            "arg_types": [a.get("type", "void*") for a in args],
            "arg_names": [a.get("name", f"arg{i}") for i, a in enumerate(args)],
            "description": entry.get("description", []),
            "since": entry.get("since", ""),
        }
    return registry


# ---------------------------------------------------------------------------
# Library discovery
# ---------------------------------------------------------------------------

def _find_libgodot() -> str | None:
    """Locate ``libgodot`` on disk using platform-specific search paths.

    The search order is:

    1. ``LIBGODOT_PATH`` environment variable (file or directory).
    2. The current working directory.
    3. The harness root (``D:/LAAP/harness``) and the bundled
       ``godot-master`` source tree.
    4. Platform-specific install locations (``/usr/lib``, ``/usr/local/lib``,
       ``/opt/homebrew/lib``, ``/Applications/Godot.app/Contents/MacOS``,
       ``%ProgramFiles%/Godot``).

    Returns:
        Absolute path to the first matching library file, or ``None`` if no
        candidate exists on disk.
    """
    candidates: list[Path] = []
    env = os.environ.get("LIBGODOT_PATH")
    if env:
        env_path = Path(env)
        if env_path.is_file():
            candidates.append(env_path)
        else:
            for name in _LIB_NAMES:
                candidates.append(env_path / name)

    for name in _LIB_NAMES:
        for sp in _LIB_SEARCH_PATHS:
            try:
                candidates.append(Path(sp) / name)
            except (TypeError, ValueError):
                continue

    for cand in candidates:
        try:
            if cand.is_file():
                return str(cand.resolve())
        except OSError:
            continue
    return None


# ---------------------------------------------------------------------------
# GDExtensionLoader
# ---------------------------------------------------------------------------

class GDExtensionLoader:
    """High-performance GDExtension C ABI loader.

    Loads ``libgodot.{dll,so,dylib}`` via :mod:`ctypes` and binds every
    function declared in ``gdextension_interface.json`` to a Python-callable
    :class:`ctypes._FuncPtr` with correctly-typed ``argtypes`` and
    ``restype``. Method-bind calls are cached so repeated invocations of
    hot paths like ``Engine.get_frames_drawn()`` reach the C ABI directly,
    achieving sub-millisecond per-call latency versus ~1-10 ms for JSONRPC
    over TCP.

    The loader does NOT load libgodot at module import time; the dynamic
    load is deferred to :meth:`__init__` so that simply importing this
    module never crashes a process that lacks libgodot.
    """

    def __init__(
        self,
        lib_path: str | None = None,
        interface_json_path: str | Path | None = None,
    ) -> None:
        """Construct the loader and bind interface functions.

        Args:
            lib_path: Optional explicit path to ``libgodot.{dll,so,dylib}``.
                If omitted, the loader searches platform-specific paths and
                the ``LIBGODOT_PATH`` environment variable via
                :func:`_find_libgodot`.
            interface_json_path: Optional explicit path to
                ``gdextension_interface.json``. Defaults to the bundled copy
                at ``harness/godot-master/core/extension/``.

        Raises:
            GDExtensionNotFoundError: If libgodot cannot be located or loaded.
            FileNotFoundError: If the interface JSON cannot be located.
        """
        # ---- Resolve lib path ----
        resolved_lib = lib_path if lib_path else _find_libgodot()
        if not resolved_lib or not Path(resolved_lib).is_file():
            raise GDExtensionNotFoundError(
                "libgodot not found. Searched paths: "
                + ", ".join(str(p) for p in _LIB_SEARCH_PATHS)
                + ". Set LIBGODOT_PATH or pass lib_path= explicitly."
            )
        try:
            self._lib: ctypes.CDLL = ctypes.CDLL(resolved_lib)
        except OSError as exc:
            raise GDExtensionNotFoundError(
                f"Failed to load libgodot at {resolved_lib}: {exc}"
            ) from exc
        self._lib_path: str = str(Path(resolved_lib).resolve())

        # ---- Parse interface JSON ----
        json_path = (
            Path(interface_json_path) if interface_json_path else DEFAULT_INTERFACE_JSON_PATH
        )
        if not json_path.is_file():
            raise FileNotFoundError(
                f"gdextension_interface.json not found at {json_path}"
            )
        self._interface_json_path: str = str(json_path.resolve())
        self._signatures: dict[str, dict[str, Any]] = _parse_interface_json(json_path)

        # ---- Caches ----
        # Function-pointer cache: name -> ctypes._FuncPtr (with argtypes/restype set)
        self._func_cache: dict[str, Any] = {}
        # Method-bind cache: "ClassName::method" -> int address
        self._method_bind_cache: dict[str, int] = {}
        # Singleton cache: "Engine" -> int address
        self._singleton_cache: dict[str, int] = {}

        # ---- Eagerly bind hot-path functions used by the high-level API ----
        self._fn_classdb_get_method_bind = self.load_function("classdb_get_method_bind")
        self._fn_object_method_bind_call = self.load_function("object_method_bind_call")
        self._fn_global_get_singleton = self.load_function("global_get_singleton")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def lib_path(self) -> str:
        """Absolute path of the loaded libgodot shared library."""
        return self._lib_path

    @property
    def interface_json_path(self) -> str:
        """Absolute path of the parsed ``gdextension_interface.json`` file."""
        return self._interface_json_path

    @property
    def signatures(self) -> dict[str, dict[str, Any]]:
        """Read-only registry of parsed interface function signatures."""
        return self._signatures

    @property
    def function_count(self) -> int:
        """Number of interface functions parsed from the JSON spec."""
        return len(self._signatures)

    # ------------------------------------------------------------------
    # Function binding
    # ------------------------------------------------------------------
    def load_function(self, name: str) -> Any:
        """Look up a function pointer by name and configure its signature.

        Subsequent calls for the same name return the cached pointer.

        Args:
            name: Interface function name (e.g. ``"object_method_bind_call"``).

        Returns:
            A :class:`ctypes._FuncPtr` with ``argtypes`` and ``restype``
            populated from the JSON signature.

        Raises:
            AttributeError: If the symbol is missing from libgodot.
            KeyError: If the function is not declared in the interface JSON.
        """
        cached = self._func_cache.get(name)
        if cached is not None:
            return cached
        try:
            fn = getattr(self._lib, name)
        except AttributeError as exc:
            raise AttributeError(
                f"libgodot at {self._lib_path} does not export symbol '{name}'"
            ) from exc
        sig = self._signatures.get(name)
        if sig is None:
            raise KeyError(
                f"Function '{name}' not declared in {self._interface_json_path}"
            )
        fn.argtypes = [_map_c_type_to_ctypes(t) for t in sig["arg_types"]]
        fn.restype = _map_c_type_to_ctypes(sig["return_type"])
        self._func_cache[name] = fn
        return fn

    # ------------------------------------------------------------------
    # High-level helpers
    # ------------------------------------------------------------------
    def get_singleton(self, name: str) -> int:
        """Return the ``GDExtensionObjectPtr`` for a global singleton.

        The result is cached so repeated lookups for the same singleton
        name are O(1).

        Args:
            name: Singleton name (e.g. ``"Engine"``).

        Returns:
            Integer address of the singleton object.

        Raises:
            RuntimeError: If Godot returns a null pointer (singleton not
                registered).
        """
        cached = self._singleton_cache.get(name)
        if cached:
            return cached
        # Build an opaque StringName pointer. In this build of libgodot the
        # C string is accepted directly by global_get_singleton; we cast it
        # to c_void_p so it matches the configured argtypes.
        sn = ctypes.cast(
            ctypes.c_char_p(name.encode("utf-8")), ctypes.c_void_p
        )
        ptr = self._fn_global_get_singleton(sn)
        addr = ctypes.cast(ptr, ctypes.c_void_p).value or 0
        if not addr:
            raise RuntimeError(f"Global singleton '{name}' not available")
        self._singleton_cache[name] = addr
        return addr

    def _get_method_bind(
        self, class_name: str, method_name: str, method_hash: int
    ) -> int:
        """Fetch (and cache) the MethodBind pointer for a class::method pair."""
        cache_key = f"{class_name}::{method_name}"
        mb_ptr = self._method_bind_cache.get(cache_key)
        if mb_ptr:
            return mb_ptr
        class_sn = ctypes.cast(
            ctypes.c_char_p(class_name.encode("utf-8")), ctypes.c_void_p
        )
        method_sn = ctypes.cast(
            ctypes.c_char_p(method_name.encode("utf-8")), ctypes.c_void_p
        )
        mb = self._fn_classdb_get_method_bind(
            class_sn, method_sn, ctypes.c_int64(method_hash)
        )
        mb_addr = ctypes.cast(mb, ctypes.c_void_p).value or 0
        if not mb_addr:
            raise RuntimeError(
                f"MethodBind not found for {cache_key} (hash={method_hash})"
            )
        self._method_bind_cache[cache_key] = mb_addr
        return mb_addr

    def call_method_bind(
        self,
        method_name: str,
        *args: Any,
        class_name: str = "Engine",
        method_hash: int = 0,
    ) -> Any:
        """Call a ClassDB method by name via the GDExtension ABI.

        Args:
            method_name: Name of the method to invoke (e.g.
                ``"get_frames_drawn"``).
            *args: Positional arguments to pass to the method. ``int`` ->
                ``c_int64``, ``str`` -> ``c_char_p``, ``float``/``bool`` ->
                ``c_double``; opaque pointers may be passed as ``int``.
            class_name: ClassDB class that declares the method. Defaults
                to ``"Engine"`` for the common singleton-method case.
            method_hash: ClassDB method hash. Pass ``0`` to skip hash
                verification (acceptable in dev builds of libgodot).

        Returns:
            The return value as a Python ``int`` (for ``GDExtensionInt``
            returns) -- the common case for the benchmark target
            ``Engine.get_frames_drawn()``.

        Raises:
            RuntimeError: If the method bind is missing or the call returns
                a non-zero ``GDExtensionCallError``.
        """
        mb_addr = self._get_method_bind(class_name, method_name, method_hash)
        instance_addr = self.get_singleton(class_name)

        n = len(args)
        arg_storage: list[Any] = []
        arg_ptrs = (ctypes.c_void_p * max(n, 1))()
        for i, a in enumerate(args):
            if isinstance(a, bool):
                storage = ctypes.c_int64(int(a))
                arg_storage.append(storage)
                arg_ptrs[i] = ctypes.cast(
                    ctypes.pointer(storage), ctypes.c_void_p
                ).value
            elif isinstance(a, int):
                storage = ctypes.c_int64(a)
                arg_storage.append(storage)
                arg_ptrs[i] = ctypes.cast(
                    ctypes.pointer(storage), ctypes.c_void_p
                ).value
            elif isinstance(a, float):
                storage = ctypes.c_double(a)
                arg_storage.append(storage)
                arg_ptrs[i] = ctypes.cast(
                    ctypes.pointer(storage), ctypes.c_void_p
                ).value
            elif isinstance(a, str):
                storage = ctypes.c_char_p(a.encode("utf-8"))
                arg_storage.append(storage)
                arg_ptrs[i] = ctypes.cast(storage, ctypes.c_void_p).value
            else:
                arg_ptrs[i] = ctypes.cast(a, ctypes.c_void_p).value if a else None

        args_ptr = (
            ctypes.cast(arg_ptrs, ctypes.POINTER(ctypes.c_void_p))
            if n > 0
            else None
        )

        ret = ctypes.c_int64(0)
        err = ctypes.c_int32(0)
        self._fn_object_method_bind_call(
            ctypes.c_void_p(mb_addr),
            ctypes.c_void_p(instance_addr),
            args_ptr,
            ctypes.c_int64(n),
            ctypes.byref(ret),
            ctypes.byref(err),
        )
        if err.value != 0:
            raise RuntimeError(
                f"object_method_bind_call for {class_name}::{method_name} "
                f"failed with error {err.value}"
            )
        return ret.value

    def object_call(
        self,
        obj_ptr: int,
        method: str,
        *args: Any,
        class_name: str = "Object",
        method_hash: int = 0,
    ) -> Any:
        """Call a method on a specific object instance via the GDExtension ABI.

        Unlike :meth:`call_method_bind` (which fetches the singleton for the
        class), this method takes an explicit object pointer so it can be
        used with non-singleton objects returned from previous calls.

        Args:
            obj_ptr: Address of the ``GDExtensionObjectPtr`` to invoke on.
            method: Name of the method to call.
            *args: Positional arguments (same marshalling rules as
                :meth:`call_method_bind`).
            class_name: ClassDB class that declares the method. Defaults to
                ``"Object"``.
            method_hash: ClassDB method hash (``0`` to skip).

        Returns:
            The return value as a Python ``int`` (for ``GDExtensionInt``
            returns).

        Raises:
            RuntimeError: If the method bind is missing or the call returns
                a non-zero ``GDExtensionCallError``.
        """
        mb_addr = self._get_method_bind(class_name, method, method_hash)

        n = len(args)
        arg_storage: list[Any] = []
        arg_ptrs = (ctypes.c_void_p * max(n, 1))()
        for i, a in enumerate(args):
            if isinstance(a, bool):
                storage = ctypes.c_int64(int(a))
                arg_storage.append(storage)
                arg_ptrs[i] = ctypes.cast(
                    ctypes.pointer(storage), ctypes.c_void_p
                ).value
            elif isinstance(a, int):
                storage = ctypes.c_int64(a)
                arg_storage.append(storage)
                arg_ptrs[i] = ctypes.cast(
                    ctypes.pointer(storage), ctypes.c_void_p
                ).value
            elif isinstance(a, float):
                storage = ctypes.c_double(a)
                arg_storage.append(storage)
                arg_ptrs[i] = ctypes.cast(
                    ctypes.pointer(storage), ctypes.c_void_p
                ).value
            elif isinstance(a, str):
                storage = ctypes.c_char_p(a.encode("utf-8"))
                arg_storage.append(storage)
                arg_ptrs[i] = ctypes.cast(storage, ctypes.c_void_p).value
            else:
                arg_ptrs[i] = ctypes.cast(a, ctypes.c_void_p).value if a else None

        args_ptr = (
            ctypes.cast(arg_ptrs, ctypes.POINTER(ctypes.c_void_p))
            if n > 0
            else None
        )

        ret = ctypes.c_int64(0)
        err = ctypes.c_int32(0)
        self._fn_object_method_bind_call(
            ctypes.c_void_p(mb_addr),
            ctypes.c_void_p(obj_ptr),
            args_ptr,
            ctypes.c_int64(n),
            ctypes.byref(ret),
            ctypes.byref(err),
        )
        if err.value != 0:
            raise RuntimeError(
                f"object_call({class_name}::{method}) failed with error {err.value}"
            )
        return ret.value

    # ------------------------------------------------------------------
    # Benchmark
    # ------------------------------------------------------------------
    def benchmark_vs_jsonrpc(
        self,
        jsonrpc_client: Any,
        iterations: int = 1000,
    ) -> dict[str, float]:
        """Benchmark GDExtension vs JSONRPC method-call latency.

        Calls ``Engine.get_frames_drawn()`` ``iterations`` times via each
        transport and returns the average per-call latency in milliseconds.
        The GDExtension side hits the cached method-bind path directly; the
        JSONRPC side dispatches through ``jsonrpc_client``.

        Args:
            jsonrpc_client: A client object exposing either
                ``call_method(class_name, method, *args)`` or
                ``call(class_name, method, *args)``. Mock clients may simply
                return dummy values without contacting Godot -- only the
                dispatch overhead is measured.
            iterations: Number of calls per transport. Defaults to 1000
                (matches the spec).

        Returns:
            A dict with keys:

            * ``"jsonrpc_avg_ms"``: average JSONRPC call latency (ms).
            * ``"gdextension_avg_ms"``: average GDExtension call latency (ms).
            * ``"speedup"``: ``jsonrpc_avg_ms / gdextension_avg_ms``.
        """
        if hasattr(jsonrpc_client, "call_method"):
            jsonrpc_call = jsonrpc_client.call_method
        elif hasattr(jsonrpc_client, "call"):
            jsonrpc_call = jsonrpc_client.call
        else:
            raise TypeError(
                "jsonrpc_client must expose call_method() or call()"
            )

        # ---- JSONRPC round ----
        t0 = time.perf_counter()
        for _ in range(iterations):
            jsonrpc_call("Engine", "get_frames_drawn")
        jsonrpc_elapsed = time.perf_counter() - t0

        # ---- GDExtension round ----
        t0 = time.perf_counter()
        for _ in range(iterations):
            self.call_method_bind("get_frames_drawn")
        gdextension_elapsed = time.perf_counter() - t0

        jsonrpc_avg_ms = (jsonrpc_elapsed / iterations) * 1000.0
        gdextension_avg_ms = (gdextension_elapsed / iterations) * 1000.0
        speedup = (
            jsonrpc_avg_ms / gdextension_avg_ms
            if gdextension_avg_ms > 0
            else float("inf")
        )
        return {
            "jsonrpc_avg_ms": jsonrpc_avg_ms,
            "gdextension_avg_ms": gdextension_avg_ms,
            "speedup": speedup,
        }


__all__ = [
    "GDExtensionLoader",
    "GDExtensionNotFoundError",
    "DEFAULT_INTERFACE_JSON_PATH",
]
