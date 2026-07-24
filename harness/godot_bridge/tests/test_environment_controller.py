"""Unit tests for :mod:`environment_controller` (Task 8).

Mocks ``GodotJSONRPCClient`` with ``MagicMock`` and verifies:

- ``add_child`` / ``remove`` / ``set_property`` RPC payloads
- transaction begin/commit/rollback semantics
- undo log replay order (reverse)
- rollback restores removed nodes and changed properties
- no memory leaks after rollback/commit (reference count correctness via
  ``weakref`` — :class:`SceneSnapshot` objects are garbage-collected once
  the undo log is cleared)

These tests do not require a running Godot instance; all RPC calls are
intercepted by the mock. They are 0-token (no LLM involvement).

Run::

    python -m pytest D:\\LAAP\\harness\\godot_bridge\\tests\\test_environment_controller.py -v
"""
from __future__ import annotations

import gc
import sys
import weakref
from pathlib import Path
from typing import Any, Callable
from unittest.mock import MagicMock

import pytest

# Make the controller and client modules importable from anywhere.
_HERE = Path(__file__).resolve().parent
_BRIDGE_DIR = _HERE.parent
_CONTROLLERS_DIR = _BRIDGE_DIR / "controllers"
_PYTHON_DIR = _BRIDGE_DIR / "python"
for _p in (_CONTROLLERS_DIR, _PYTHON_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from environment_controller import (  # noqa: E402  (import after sys.path tweak)
    EnvironmentController,
    SceneSnapshot,
)
from godot_jsonrpc_client import GodotJSONRPCClient  # noqa: E402


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _make_scene_tree() -> dict:
    """Return a minimal scene tree dict matching the bridge's get_scene_tree."""
    return {
        "path": "/root",
        "class": "Window",
        "name": "root",
        "children": [
            {
                "path": "/root/SomeNode",
                "class": "Node3D",
                "name": "SomeNode",
                "children": [],
            }
        ],
    }


def _make_mock_client() -> MagicMock:
    """Return a ``MagicMock`` configured as a ``GodotJSONRPCClient``."""
    client = MagicMock(spec=GodotJSONRPCClient)
    client.call_method = MagicMock()
    return client


# --------------------------------------------------------------------------- #
# Tests: node operations
# --------------------------------------------------------------------------- #
def test_add_child_returns_path() -> None:
    """add_child returns the new node's path and issues the correct RPC."""
    client = _make_mock_client()
    client.call_method.return_value = "/root/Parent/NewNode"
    ctrl = EnvironmentController(client)

    result = ctrl.add_child("/root/Parent", "Node3D", "NewNode")

    assert result == "/root/Parent/NewNode"
    client.call_method.assert_called_once_with(
        "add_child",
        {
            "parent_path": "/root/Parent",
            "child_type": "Node3D",
            "child_name": "NewNode",
        },
    )


def test_remove_calls_rpc() -> None:
    """remove issues the remove_node RPC with the correct payload."""
    client = _make_mock_client()
    client.call_method.return_value = None
    ctrl = EnvironmentController(client)

    ctrl.remove("/root/SomeNode")

    # Not in a transaction → only remove_node RPC is issued.
    client.call_method.assert_called_once_with(
        "remove_node", {"path": "/root/SomeNode"}
    )


def test_set_property_calls_rpc() -> None:
    """set_property issues the set_property RPC with the correct payload."""
    client = _make_mock_client()
    client.call_method.return_value = None
    ctrl = EnvironmentController(client)

    ctrl.set_property("/root/SomeNode", "position", [1, 2, 3])

    # Not in a transaction → only set_property RPC is issued (no get_property).
    client.call_method.assert_called_once_with(
        "set_property",
        {
            "path": "/root/SomeNode",
            "prop": "position",
            "value": [1, 2, 3],
        },
    )


# --------------------------------------------------------------------------- #
# Tests: transactions
# --------------------------------------------------------------------------- #
def test_begin_commit_clears_undo_log() -> None:
    """After commit, rollback is a no-op (undo log was cleared)."""
    client = _make_mock_client()
    client.call_method.return_value = "/root/TestNode"
    ctrl = EnvironmentController(client)

    ctrl.begin_transaction()
    ctrl.add_child("/root", "Node3D", "TestNode")
    ctrl.commit()

    # Snapshot the call count after commit; rollback should not add calls.
    calls_after_commit = client.call_method.call_count
    ctrl.rollback()
    assert client.call_method.call_count == calls_after_commit
    # Undo log must be empty after commit.
    assert ctrl._undo_log == []


def test_rollback_replays_undo_log() -> None:
    """rollback undoes an add_child by calling remove_node on the new path."""
    client = _make_mock_client()
    client.call_method.return_value = "/root/TestNode"
    ctrl = EnvironmentController(client)

    ctrl.begin_transaction()
    ctrl.add_child("/root", "Node3D", "TestNode")
    ctrl.rollback()

    # Verify remove_node RPC was called with the new node's path.
    remove_calls = [
        c
        for c in client.call_method.call_args_list
        if c.args[0] == "remove_node"
    ]
    assert len(remove_calls) == 1
    assert remove_calls[0].args[1] == {"path": "/root/TestNode"}


def test_rollback_restores_removed_node() -> None:
    """rollback undoes a remove by calling add_child to re-add the node."""
    client = _make_mock_client()

    def side_effect(method: str, params: Any) -> Any:
        if method == "get_scene_tree":
            return _make_scene_tree()
        if method == "remove_node":
            return None
        if method == "add_child":
            return params["parent_path"] + "/" + params["child_name"]
        return None

    client.call_method.side_effect = side_effect
    ctrl = EnvironmentController(client)

    ctrl.begin_transaction()
    ctrl.remove("/root/SomeNode")
    ctrl.rollback()

    # Verify add_child RPC was called to re-add SomeNode under /root.
    add_calls = [
        c
        for c in client.call_method.call_args_list
        if c.args[0] == "add_child"
    ]
    assert len(add_calls) == 1
    assert add_calls[0].args[1] == {
        "parent_path": "/root",
        "child_type": "Node3D",
        "child_name": "SomeNode",
    }


def test_rollback_restores_property() -> None:
    """rollback undoes a set_property by restoring the old value."""
    client = _make_mock_client()

    def side_effect(method: str, params: Any) -> Any:
        if method == "get_property":
            return [0, 0, 0]
        return None

    client.call_method.side_effect = side_effect
    ctrl = EnvironmentController(client)

    ctrl.begin_transaction()
    ctrl.set_property("/root/SomeNode", "position", [1, 2, 3])
    ctrl.rollback()

    # Two set_property RPC calls: the original set, then the undo restore.
    set_prop_calls = [
        c
        for c in client.call_method.call_args_list
        if c.args[0] == "set_property"
    ]
    assert len(set_prop_calls) == 2
    # The undo call must restore the old value captured before the change.
    assert set_prop_calls[1].args[1] == {
        "path": "/root/SomeNode",
        "prop": "position",
        "value": [0, 0, 0],
    }


def test_undo_log_order_is_reverse() -> None:
    """Undo ops are replayed in reverse order.

    Sequence: add_child → set_property
    Undo order: set_property undo (restore old value), then add_child undo
    (remove_node on the new path).
    """
    client = _make_mock_client()
    call_log: list[str] = []

    def side_effect(method: str, params: Any) -> Any:
        call_log.append(method)
        if method == "add_child":
            return "/root/TestNode"
        if method == "get_property":
            return "old_value"
        return None

    client.call_method.side_effect = side_effect
    ctrl = EnvironmentController(client)

    ctrl.begin_transaction()
    ctrl.add_child("/root", "Node3D", "TestNode")
    ctrl.set_property("/root/TestNode", "name", "new_value")
    ctrl.rollback()

    # Initial ops issue: add_child, get_property, set_property (3 calls).
    # Rollback replays undo log in reverse:
    #   1. undo set_property → set_property(path, prop, old_value)
    #   2. undo add_child   → remove_node(new_path)
    rollback_calls = call_log[3:]
    assert rollback_calls == ["set_property", "remove_node"]


# --------------------------------------------------------------------------- #
# Tests: memory leak verification (SubTask 5)
# --------------------------------------------------------------------------- #
def test_rollback_no_memory_leak() -> None:
    """After rollback, undo log entries are released (no ref leaks).

    Uses ``weakref`` to verify that :class:`SceneSnapshot` objects captured
    during the transaction are garbage-collected once rollback clears the
    undo log. This validates reference-count correctness: no live references
    to the snapshots remain after rollback.
    """
    client = _make_mock_client()

    def side_effect(method: str, params: Any) -> Any:
        if method == "get_scene_tree":
            return _make_scene_tree()
        if method == "add_child":
            return "/root/AddedNode"
        return None

    client.call_method.side_effect = side_effect
    ctrl = EnvironmentController(client)

    ctrl.begin_transaction()
    ctrl.remove("/root/SomeNode")  # captures a SceneSnapshot

    # Hold weak references to the snapshots currently in the undo log.
    snapshot_refs: list[weakref.ref] = [
        weakref.ref(op.snapshot)
        for op in ctrl._undo_log
        if op.snapshot is not None
    ]
    assert len(snapshot_refs) == 1

    ctrl.rollback()
    assert ctrl._undo_log == []
    gc.collect()
    for ref in snapshot_refs:
        assert ref() is None, (
            "SceneSnapshot was not garbage-collected after rollback — "
            "the controller is leaking references"
        )


def test_commit_no_memory_leak() -> None:
    """After commit, undo log entries are released (no ref leaks)."""
    client = _make_mock_client()

    def side_effect(method: str, params: Any) -> Any:
        if method == "get_scene_tree":
            return _make_scene_tree()
        if method == "add_child":
            return "/root/AddedNode"
        return None

    client.call_method.side_effect = side_effect
    ctrl = EnvironmentController(client)

    ctrl.begin_transaction()
    ctrl.remove("/root/SomeNode")  # captures a SceneSnapshot

    snapshot_refs: list[weakref.ref] = [
        weakref.ref(op.snapshot)
        for op in ctrl._undo_log
        if op.snapshot is not None
    ]
    assert len(snapshot_refs) == 1

    ctrl.commit()
    assert ctrl._undo_log == []
    gc.collect()
    for ref in snapshot_refs:
        assert ref() is None, (
            "SceneSnapshot was not garbage-collected after commit — "
            "the controller is leaking references"
        )


# --------------------------------------------------------------------------- #
# Tests: scene tree introspection helpers
# --------------------------------------------------------------------------- #
def test_get_children_returns_child_paths() -> None:
    """get_children returns the paths of direct children of a node."""
    client = _make_mock_client()
    client.call_method.return_value = _make_scene_tree()
    ctrl = EnvironmentController(client)

    children = ctrl.get_children("/root")

    assert children == ["/root/SomeNode"]


def test_find_nodes_no_filter_returns_all() -> None:
    """find_nodes with no filter returns all node paths in the tree."""
    client = _make_mock_client()
    client.call_method.return_value = _make_scene_tree()
    ctrl = EnvironmentController(client)

    nodes = ctrl.find_nodes()

    assert nodes == ["/root", "/root/SomeNode"]


def test_find_nodes_with_filter() -> None:
    """find_nodes with a type filter returns only matching node paths."""
    client = _make_mock_client()
    client.call_method.return_value = _make_scene_tree()
    ctrl = EnvironmentController(client)

    nodes = ctrl.find_nodes(type_filter="Node3D")

    assert nodes == ["/root/SomeNode"]


def test_get_property_returns_value() -> None:
    """get_property returns the value from the get_property RPC."""
    client = _make_mock_client()
    client.call_method.return_value = [1.0, 2.0, 3.0]
    ctrl = EnvironmentController(client)

    value = ctrl.get_property("/root/SomeNode", "position")

    assert value == [1.0, 2.0, 3.0]
    client.call_method.assert_called_once_with(
        "get_property",
        {"path": "/root/SomeNode", "prop": "position"},
    )


def test_scene_snapshot_dataclass_fields() -> None:
    """SceneSnapshot is a dataclass with the expected fields."""
    snap = SceneSnapshot(
        path="/root/Node",
        node_type="Node3D",
        node_name="Node",
        parent_path="/root",
        properties={"position": [0, 0, 0]},
    )
    assert snap.path == "/root/Node"
    assert snap.node_type == "Node3D"
    assert snap.node_name == "Node"
    assert snap.parent_path == "/root"
    assert snap.properties == {"position": [0, 0, 0]}

    # Default properties is an empty dict (not shared between instances).
    snap2 = SceneSnapshot(
        path="/root/Other",
        node_type="Sprite2D",
        node_name="Other",
        parent_path="/root",
    )
    assert snap2.properties == {}
    assert snap2.properties is not snap.properties
