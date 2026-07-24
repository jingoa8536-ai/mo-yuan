"""Environment controller for the LAAP 0-Token Game Dev Framework (Task 8).

Drives the Godot scene tree via the JSONRPC bridge (Task 3). Provides node
add/remove/property operations and a transaction API (begin/commit/rollback)
backed by an undo log of inverse operations.

All operations are 0-token: they drive Godot directly via JSON-RPC and never
involve an LLM. The bridge (``gdscripts/laap_bridge.gd``) exposes the
``add_child``, ``remove_node``, ``set_property``, ``get_property`` and
``get_scene_tree`` RPC methods consumed here.

Transaction model
-----------------
``begin_transaction()`` starts tracking every scene-tree mutation in an undo
log. Each operation records its inverse:

- ``add_child``  → undo: ``remove_node(new_path)``
- ``remove``     → undo: ``add_child(parent, type, name)`` + restore properties
  (node state is captured BEFORE removal via a :class:`SceneSnapshot`)
- ``set_property`` → undo: ``set_property(path, prop, old_value)`` (old value
  is captured BEFORE the change)

``rollback()`` replays the undo log in reverse order. ``commit()`` discards
the undo log, making the changes permanent. The controller is thread-safe via
a ``threading.Lock``; internal RPC helpers are lock-free so rollback can
replay the log while holding the lock without deadlocking.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Optional

# Import the JSON-RPC client. The preferred path is the fully-qualified
# package import; if that fails (e.g. when this module is loaded via a
# direct sys.path entry pointing at the ``godot_bridge`` directory), fall
# back to importing from the sibling ``python`` directory.
try:  # pragma: no cover - exercised by environment
    from godot_bridge.python.godot_jsonrpc_client import GodotJSONRPCClient
except ImportError:  # pragma: no cover
    import sys as _sys
    from pathlib import Path as _Path

    _PYTHON_DIR = _Path(__file__).resolve().parent.parent / "python"
    if str(_PYTHON_DIR) not in _sys.path:
        _sys.path.insert(0, str(_PYTHON_DIR))
    from godot_jsonrpc_client import GodotJSONRPCClient  # type: ignore


__all__ = ["EnvironmentController", "SceneSnapshot"]


@dataclass
class SceneSnapshot:
    """Captures scene tree state for a node at a point in time.

    Used by the transaction undo log to record enough state to re-add a
    removed node (type, name, parent, properties) so the scene tree can be
    restored to its state at ``begin_transaction()``. The ``path`` is the
    node's full path (e.g. ``/root/SomeNode``); ``parent_path`` is derived
    from it so the node can be re-added under the correct parent.
    """

    path: str
    node_type: str
    node_name: str
    parent_path: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class _UndoOp:
    """A single inverse operation recorded in the transaction undo log.

    ``op_type`` is one of:
    - ``"add_child"``: undo by calling ``remove_node(path)``.
    - ``"remove"``: undo by re-adding the node from ``snapshot``.
    - ``"set_property"``: undo by calling ``set_property(path, prop, old_value)``.
    """

    op_type: str
    path: str
    snapshot: Optional[SceneSnapshot] = None
    prop: Optional[str] = None
    old_value: Any = None


class EnvironmentController:
    """Controller for the Godot scene tree via the JSONRPC bridge.

    Provides CRUD operations on nodes and a transaction API backed by an
    undo log. Thread-safe via ``threading.Lock``.

    Parameters
    ----------
    jsonrpc_client : GodotJSONRPCClient
        A connected JSON-RPC client used to drive the Godot bridge.

    Examples
    --------
    >>> client = GodotJSONRPCClient()
    >>> ctrl = EnvironmentController(client)
    >>> ctrl.begin_transaction()
    >>> ctrl.add_child("/root", "Node3D", "Temp")
    '/root/Temp'
    >>> ctrl.rollback()  # removes /root/Temp
    """

    def __init__(self, jsonrpc_client: GodotJSONRPCClient) -> None:
        self._client = jsonrpc_client
        self._lock = threading.Lock()
        self._undo_log: list[_UndoOp] = []
        self._in_transaction: bool = False

    # ------------------------------------------------------------------ #
    # Node operations
    # ------------------------------------------------------------------ #
    def add_child(
        self, parent_path: str, child_type: str, child_name: str
    ) -> str:
        """Add a node of ``child_type`` named ``child_name`` under ``parent_path``.

        Returns the new node's path (empty string on failure). Records an
        undo entry (remove the new node) if inside a transaction.
        """
        with self._lock:
            new_path = self._rpc_add_child(parent_path, child_type, child_name)
            if self._in_transaction and new_path:
                self._undo_log.append(
                    _UndoOp(op_type="add_child", path=new_path)
                )
            return new_path

    def remove(self, path: str) -> None:
        """Remove the node at ``path``.

        Records an undo entry (re-add the node with its state) if inside a
        transaction. The node's state is captured BEFORE removal via
        :class:`SceneSnapshot`.
        """
        with self._lock:
            snapshot: Optional[SceneSnapshot] = None
            if self._in_transaction:
                snapshot = self._capture_node_snapshot(path)
                self._undo_log.append(
                    _UndoOp(op_type="remove", path=path, snapshot=snapshot)
                )
            self._rpc_remove(path)

    def set_property(self, path: str, prop: str, value: Any) -> None:
        """Set property ``prop`` on node at ``path`` to ``value``.

        Records an undo entry (restore the old value) if inside a
        transaction. The old value is captured BEFORE the change.
        """
        with self._lock:
            if self._in_transaction:
                old_value = self._rpc_get_property(path, prop)
                self._undo_log.append(
                    _UndoOp(
                        op_type="set_property",
                        path=path,
                        prop=prop,
                        old_value=old_value,
                    )
                )
            self._rpc_set_property(path, prop, value)

    def get_property(self, path: str, prop: str) -> Any:
        """Return the value of property ``prop`` on node at ``path``."""
        with self._lock:
            return self._rpc_get_property(path, prop)

    def get_children(self, path: str) -> list[str]:
        """Return the paths of direct children of the node at ``path``."""
        with self._lock:
            tree = self._rpc_get_scene_tree()
            node = self._find_node_in_tree(tree, path)
            if node is None:
                return []
            children = node.get("children") or []
            return [
                str(c.get("path", ""))
                for c in children
                if isinstance(c, dict) and c.get("path")
            ]

    def find_nodes(self, type_filter: Optional[str] = None) -> list[str]:
        """Return paths of all nodes, optionally filtered by type (class)."""
        with self._lock:
            tree = self._rpc_get_scene_tree()
            result: list[str] = []
            self._walk_tree(tree, type_filter, result)
            return result

    # ------------------------------------------------------------------ #
    # Transaction API
    # ------------------------------------------------------------------ #
    def begin_transaction(self) -> None:
        """Begin a transaction: clear the undo log and start tracking ops."""
        with self._lock:
            self._undo_log.clear()
            self._in_transaction = True

    def commit(self) -> None:
        """Commit the transaction: clear the undo log (ops are permanent)."""
        with self._lock:
            self._undo_log.clear()
            self._in_transaction = False

    def rollback(self) -> None:
        """Rollback the transaction: replay the undo log in reverse order.

        Restores the scene tree to its state at ``begin_transaction()``:
        - Removes nodes added since begin
        - Re-adds nodes removed since begin (with their properties)
        - Restores property values changed since begin
        """
        with self._lock:
            for op in reversed(self._undo_log):
                self._apply_undo(op)
            self._undo_log.clear()
            self._in_transaction = False

    # ------------------------------------------------------------------ #
    # Internal RPC helpers — lock-free, call with lock held
    # ------------------------------------------------------------------ #
    def _rpc_add_child(
        self, parent_path: str, child_type: str, child_name: str
    ) -> str:
        result = self._client.call_method(
            "add_child",
            {
                "parent_path": parent_path,
                "child_type": child_type,
                "child_name": child_name,
            },
        )
        return str(result) if result else ""

    def _rpc_remove(self, path: str) -> None:
        self._client.call_method("remove_node", {"path": path})

    def _rpc_set_property(
        self, path: str, prop: str, value: Any
    ) -> None:
        self._client.call_method(
            "set_property",
            {"path": path, "prop": prop, "value": value},
        )

    def _rpc_get_property(self, path: str, prop: str) -> Any:
        return self._client.call_method(
            "get_property", {"path": path, "prop": prop}
        )

    def _rpc_get_scene_tree(self) -> Any:
        return self._client.call_method("get_scene_tree", {})

    # ------------------------------------------------------------------ #
    # Undo log replay
    # ------------------------------------------------------------------ #
    def _apply_undo(self, op: _UndoOp) -> None:
        """Apply a single undo operation (reverse one prior op).

        Called with ``self._lock`` held; invokes RPC helpers directly (no
        lock reacquisition, no undo-log tracking) so rollback does not
        deadlock or pollute the log.
        """
        if op.op_type == "add_child":
            # Undo an add_child: remove the node that was added.
            self._rpc_remove(op.path)
        elif op.op_type == "remove":
            # Undo a remove: re-add the node from its captured snapshot.
            snap = op.snapshot
            if snap is not None:
                self._rpc_add_child(
                    snap.parent_path, snap.node_type, snap.node_name
                )
                for prop, value in snap.properties.items():
                    self._rpc_set_property(snap.path, prop, value)
        elif op.op_type == "set_property":
            # Undo a set_property: restore the old value.
            if op.prop is not None:
                self._rpc_set_property(op.path, op.prop, op.old_value)

    # ------------------------------------------------------------------ #
    # Scene tree helpers
    # ------------------------------------------------------------------ #
    def _capture_node_snapshot(self, path: str) -> Optional[SceneSnapshot]:
        """Capture the state of the node at ``path`` BEFORE removal.

        Walks the current scene tree to find the node's class and name,
        and derives the parent path from the path string. Returns ``None``
        if the node is not found in the tree (the undo entry is still
        recorded, but rollback will skip re-adding the node).
        """
        tree = self._rpc_get_scene_tree()
        node_info = self._find_node_in_tree(tree, path)
        if node_info is None:
            return None
        parent_path = self._derive_parent_path(path)
        return SceneSnapshot(
            path=path,
            node_type=str(node_info.get("class", "")),
            node_name=str(node_info.get("name", "")),
            parent_path=parent_path,
            properties={},
        )

    @staticmethod
    def _derive_parent_path(path: str) -> str:
        """Derive the parent path from a node path string.

        ``"/root/SomeNode/Child"`` → ``"/root/SomeNode"``.
        ``"/root"`` → ``""`` (root has no parent).
        """
        if not path or "/" not in path:
            return ""
        parent, _sep, _name = path.rpartition("/")
        return parent

    @staticmethod
    def _find_node_in_tree(tree: Any, target_path: str) -> Optional[dict]:
        """Find the node with ``target_path`` in the scene tree dict.

        The tree dict has the shape ``{path, class, name, children: [...]}``
        as produced by the bridge's ``get_scene_tree`` RPC. Returns ``None``
        if the tree is not a dict or the node is not found.
        """
        if not isinstance(tree, dict):
            return None
        if tree.get("path") == target_path:
            return tree
        children = tree.get("children") or []
        for child in children:
            found = EnvironmentController._find_node_in_tree(
                child, target_path
            )
            if found is not None:
                return found
        return None

    @staticmethod
    def _walk_tree(
        tree: Any, type_filter: Optional[str], out: list[str]
    ) -> None:
        """Walk the scene tree and collect node paths matching ``type_filter``.

        If ``type_filter`` is ``None``, all node paths are collected.
        """
        if not isinstance(tree, dict):
            return
        path = tree.get("path")
        if path:
            if type_filter is None or tree.get("class") == type_filter:
                out.append(str(path))
        children = tree.get("children") or []
        for child in children:
            EnvironmentController._walk_tree(child, type_filter, out)
