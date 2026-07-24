"""Unit tests for :mod:`controllers.physics_stepping` (LAAP Task 10).

These tests are 0-token by construction: :class:`GodotJSONRPCClient` is
replaced with a :class:`unittest.mock.MagicMock` so no real Godot instance
and no real TCP socket is touched. They cover the seven cases required by
the Task 10 spec, plus three small edge cases (negative frames, zero
frames, no-collision path):

- ``test_pause_sets_time_scale_zero`` — pause() invokes the
  ``set_property`` RPC with ``("Engine", "time_scale", 0)``.
- ``test_resume_sets_time_scale_one`` — resume() invokes the same RPC with
  value ``1``.
- ``test_step_calls_physics_step_n_times`` — step(5) issues 5
  ``call_method_on_node`` RPCs with method ``"physics_step"``.
- ``test_save_snapshot_reads_properties`` — save_snapshot() reads the four
  tracked properties (position / rotation / velocity / angular_velocity)
  for every snapshot node path.
- ``test_restore_snapshot_writes_properties`` — restore_snapshot() issues
  one ``set_property`` RPC per property per node.
- ``test_step_and_compare_returns_diff`` — step_and_compare() returns the
  expected ``moved`` / ``unchanged`` split when positions change.
- ``test_validate_no_penetration_detects_collision`` — bodies that moved
  after a single step are paired up as collision suspects.

Run::

    python -m pytest D:\\LAAP\\harness\\godot_bridge\\tests\\test_physics_stepping.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# Make ``from controllers.physics_stepping import ...`` work regardless of
# the caller's working directory, and ``from godot_jsonrpc_client import ...``
# for the spec=MagicMock below.
_BRIDGE_DIR = Path(__file__).resolve().parent.parent
_PYTHON_DIR = _BRIDGE_DIR / "python"
for _p in (str(_BRIDGE_DIR), str(_PYTHON_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from controllers.physics_stepping import (  # noqa: E402  (path insert above)
    PhysicsSnapshot,
    PhysicsStepper,
)
from godot_jsonrpc_client import GodotJSONRPCClient  # noqa: E402


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _make_client() -> MagicMock:
    """Return a MagicMock standing in for :class:`GodotJSONRPCClient`.

    The mock returns ``None`` for every ``call_method`` invocation by
    default; individual tests override ``side_effect`` / ``return_value``
    on the ``call_method`` MagicMock to drive specific behaviours. Using
    ``spec=GodotJSONRPCClient`` catches typos in method names at test time.
    """
    client = MagicMock(spec=GodotJSONRPCClient)
    client.call_method = MagicMock(return_value=None)
    return client


def _prop_value(prop: str, *, pos: list[float] | None = None) -> Any:
    """Return a deterministic placeholder value for a tracked property."""
    if prop == "position":
        return pos if pos is not None else [0.0, 0.0, 0.0]
    if prop == "rotation":
        return [0.0, 0.0, 0.0]
    if prop == "velocity":
        return [0.0, 0.0, 0.0]
    if prop == "angular_velocity":
        return [0.0, 0.0, 0.0]
    return None


# --------------------------------------------------------------------------- #
# pause / resume
# --------------------------------------------------------------------------- #
def test_pause_sets_time_scale_zero() -> None:
    """pause() → set_property("Engine", "time_scale", 0) RPC issued."""
    client = _make_client()
    stepper = PhysicsStepper(client)
    stepper.pause()
    client.call_method.assert_called_once_with(
        "set_property",
        {"path": "Engine", "prop": "time_scale", "value": 0},
    )


def test_resume_sets_time_scale_one() -> None:
    """resume() → set_property("Engine", "time_scale", 1) RPC issued."""
    client = _make_client()
    stepper = PhysicsStepper(client)
    stepper.resume()
    client.call_method.assert_called_once_with(
        "set_property",
        {"path": "Engine", "prop": "time_scale", "value": 1},
    )


# --------------------------------------------------------------------------- #
# step
# --------------------------------------------------------------------------- #
def test_step_calls_physics_step_n_times() -> None:
    """step(5) → 5 call_method_on_node RPCs with method 'physics_step'."""
    client = _make_client()
    stepper = PhysicsStepper(client)
    stepper.step(5)
    assert client.call_method.call_count == 5
    for call in client.call_method.call_args_list:
        method, params = call.args
        assert method == "call_method_on_node"
        assert params["method"] == "physics_step"
        assert params["args"] == []
        # The path must be the SceneTree; the constant lives on the stepper
        # so callers can override it via subclassing if a future Godot
        # version moves the singleton.
        assert params["path"] == PhysicsStepper._SCENE_TREE_PATH


def test_step_zero_is_noop() -> None:
    """step(0) issues no RPCs (edge case)."""
    client = _make_client()
    stepper = PhysicsStepper(client)
    stepper.step(0)
    client.call_method.assert_not_called()


def test_step_negative_raises() -> None:
    """step(-1) raises ValueError (edge case)."""
    client = _make_client()
    stepper = PhysicsStepper(client)
    with pytest.raises(ValueError):
        stepper.step(-1)


# --------------------------------------------------------------------------- #
# save_snapshot
# --------------------------------------------------------------------------- #
def test_save_snapshot_reads_properties() -> None:
    """save_snapshot() reads position/rotation/velocity/angular_velocity per node."""
    client = _make_client()
    expected = {
        "position": [1.0, 2.0, 3.0],
        "rotation": [0.0, 1.0, 0.0],
        "velocity": [0.5, 0.0, 0.0],
        "angular_velocity": [0.0, 0.0, 0.2],
    }

    def side_effect(method: str, params: dict) -> Any:
        if method != "get_property":
            return None
        return expected[params["prop"]]

    client.call_method.side_effect = side_effect
    stepper = PhysicsStepper(
        client, snapshot_node_paths=["/root/BodyA"]
    )
    snap = stepper.save_snapshot()

    assert "/root/BodyA" in snap.node_states
    state = snap.node_states["/root/BodyA"]
    assert state["position"] == [1.0, 2.0, 3.0]
    assert state["rotation"] == [0.0, 1.0, 0.0]
    assert state["velocity"] == [0.5, 0.0, 0.0]
    assert state["angular_velocity"] == [0.0, 0.0, 0.2]
    # 4 get_property RPCs were issued (one per property), no get_scene_tree
    # call because snapshot_node_paths was explicit.
    assert client.call_method.call_count == 4
    for call in client.call_method.call_args_list:
        assert call.args[0] == "get_property"


# --------------------------------------------------------------------------- #
# restore_snapshot
# --------------------------------------------------------------------------- #
def test_restore_snapshot_writes_properties() -> None:
    """restore_snapshot() issues set_property RPC for each (node, property)."""
    client = _make_client()
    stepper = PhysicsStepper(client)
    snap = PhysicsSnapshot(
        node_states={
            "/root/BodyA": {
                "position": [1.0, 2.0, 3.0],
                "rotation": [0.0, 0.0, 0.0],
                "velocity": [0.1, 0.0, 0.0],
                "angular_velocity": [0.0, 0.0, 0.0],
            },
            "/root/BodyB": {
                "position": [4.0, 5.0, 6.0],
                "rotation": [1.0, 0.0, 0.0],
                "velocity": [0.0, 0.2, 0.0],
                "angular_velocity": [0.0, 0.0, 0.3],
            },
        }
    )
    stepper.restore_snapshot(snap)
    # 2 nodes × 4 properties = 8 set_property RPCs.
    assert client.call_method.call_count == 8
    seen: list[tuple[str, str]] = []
    for call in client.call_method.call_args_list:
        method, params = call.args
        assert method == "set_property"
        assert params["path"] in ("/root/BodyA", "/root/BodyB")
        assert params["prop"] in (
            "position",
            "rotation",
            "velocity",
            "angular_velocity",
        )
        seen.append((params["path"], params["prop"]))
    # Each (node, prop) pair must appear exactly once.
    assert len(seen) == 8
    assert len(set(seen)) == 8


# --------------------------------------------------------------------------- #
# step_and_compare
# --------------------------------------------------------------------------- #
def test_step_and_compare_returns_diff() -> None:
    """step_and_compare() returns moved/unchanged split when positions differ."""
    client = _make_client()
    pos_before_a = [0.0, 0.0, 0.0]
    pos_after_a = [1.0, 0.0, 0.0]
    pos_b = [5.0, 5.0, 5.0]  # BodyB stays put.

    # position_reads[path] counts how many times we've read BodyA.position.
    # The first read returns the "before" value, the second the "after".
    position_reads: dict[str, int] = {}

    def side_effect(method: str, params: dict) -> Any:
        if method != "get_property":
            return None  # call_method_on_node (the step) returns None.
        path = params["path"]
        prop = params["prop"]
        if prop == "position":
            position_reads[path] = position_reads.get(path, 0) + 1
            if path == "/root/BodyA":
                # 1st read = before, 2nd read = after the step.
                return pos_after_a if position_reads[path] == 2 else pos_before_a
            return pos_b  # BodyB never moves.
        return _prop_value(prop)

    client.call_method.side_effect = side_effect
    stepper = PhysicsStepper(
        client,
        snapshot_node_paths=["/root/BodyA", "/root/BodyB"],
    )
    diff = stepper.step_and_compare(frames=1)

    assert "moved" in diff
    assert "unchanged" in diff
    # BodyA moved, BodyB did not.
    moved_paths = [entry[0] for entry in diff["moved"]]
    assert "/root/BodyA" in moved_paths
    assert "/root/BodyB" not in moved_paths
    assert "/root/BodyB" in diff["unchanged"]
    # Verify the (old, new) tuple for BodyA.
    body_a_entry = next(e for e in diff["moved"] if e[0] == "/root/BodyA")
    assert body_a_entry[1] == pos_before_a
    assert body_a_entry[2] == pos_after_a


# --------------------------------------------------------------------------- #
# validate_no_penetration
# --------------------------------------------------------------------------- #
def test_validate_no_penetration_detects_collision() -> None:
    """Bodies that moved after a single step are reported as collision pairs."""
    client = _make_client()
    pos_before = [0.0, 0.0, 0.0]
    pos_after = [0.5, 0.0, 0.0]  # moved by collision resolver

    # Each body's position is read twice: before and after the step.
    position_reads: dict[str, int] = {}

    def side_effect(method: str, params: dict) -> Any:
        if method != "get_property":
            return None
        path = params["path"]
        prop = params["prop"]
        if prop != "position":
            return _prop_value(prop)
        position_reads[path] = position_reads.get(path, 0) + 1
        return pos_after if position_reads[path] == 2 else pos_before

    client.call_method.side_effect = side_effect
    stepper = PhysicsStepper(client)
    pairs = stepper.validate_no_penetration(
        ["/root/BodyA", "/root/BodyB"]
    )

    # Both bodies moved → one pair reported.
    assert pairs == [("/root/BodyA", "/root/BodyB")]


def test_validate_no_penetration_no_collision() -> None:
    """No body moved → empty list of pairs (edge case)."""
    client = _make_client()

    def side_effect(method: str, params: dict) -> Any:
        if method != "get_property":
            return None
        return _prop_value(params["prop"])

    client.call_method.side_effect = side_effect
    stepper = PhysicsStepper(client)
    pairs = stepper.validate_no_penetration(
        ["/root/BodyA", "/root/BodyB"]
    )
    assert pairs == []


def test_validate_no_penetration_empty_input() -> None:
    """Empty body_paths → empty list, no RPCs issued (edge case)."""
    client = _make_client()
    stepper = PhysicsStepper(client)
    pairs = stepper.validate_no_penetration([])
    assert pairs == []
    client.call_method.assert_not_called()
