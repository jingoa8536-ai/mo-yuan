"""Unit tests for :mod:`controllers.character_controller` (Task 7).

These tests exercise the :class:`CharacterController` against a mocked
:class:`GodotJSONRPCClient` (``unittest.mock.MagicMock``). No real TCP
socket or Godot instance is required — the tests assert that the
controller emits the correct JSON-RPC payloads and parses mock responses
into the right Python value objects.

Covered behaviour
-----------------
- ``set_input_vector`` → ``call_method_on_node`` payload with ``set_velocity``.
- ``apply_impulse`` → ``call_method_on_node`` payload with ``apply_impulse``.
- ``teleport`` → ``call_method_on_node`` payload with ``set_position``.
- ``get_state`` → parses Transform3D + velocity + ``is_on_floor`` into a
  :class:`CharacterState`, including heading extraction from ``-basis.z``.
- ``Vector3`` round-trip serialisation (``to_dict`` / ``from_dict``).
- Convenience accessors (``set_velocity`` / ``get_velocity`` / ``look_at`` /
  ``rotate_y``) emit the expected payloads.

Run::

    python -m pytest D:\\LAAP\\harness\\godot_bridge\\tests\\test_character_controller.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Make the godot_bridge root importable so ``controllers.*`` resolves.
_BRIDGE_ROOT = Path(__file__).resolve().parent.parent
if str(_BRIDGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_ROOT))

from controllers.character_controller import (  # noqa: E402  (import after sys.path tweak)
    CharacterController,
    CharacterState,
    Vector3,
)


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
_NODE_PATH = "/root/Main/Player"


def _make_controller(
    node_path: str = _NODE_PATH,
) -> tuple[CharacterController, MagicMock]:
    """Build a controller backed by a MagicMock JSON-RPC client.

    Returns the controller and the mock so each test can assert on the
    calls made to ``call_method``.
    """
    mock_client = MagicMock(name="GodotJSONRPCClient")
    controller = CharacterController(mock_client, node_path)
    return controller, mock_client


def _identity_transform(origin: dict | None = None) -> dict:
    """Build a Godot Transform3D dict with identity basis + given origin."""
    return {
        "basis": {
            "x": {"x": 1.0, "y": 0.0, "z": 0.0},
            "y": {"x": 0.0, "y": 1.0, "z": 0.0},
            "z": {"x": 0.0, "y": 0.0, "z": 1.0},
        },
        "origin": origin if origin is not None else {"x": 0.0, "y": 0.0, "z": 0.0},
    }


# --------------------------------------------------------------------------- #
# Vector3 serialisation
# --------------------------------------------------------------------------- #
def test_vector3_serialization() -> None:
    """``to_dict`` emits the exact ``{"x","y","z"}`` shape; ``from_dict`` round-trips."""
    v = Vector3(1.5, 2.0, 3.5)
    assert v.to_dict() == {"x": 1.5, "y": 2.0, "z": 3.5}
    # Round-trip.
    assert Vector3.from_dict(v.to_dict()) == v
    # Tolerant of None / missing keys.
    assert Vector3.from_dict(None) == Vector3(0.0, 0.0, 0.0)
    assert Vector3.from_dict({"x": 1.0}) == Vector3(1.0, 0.0, 0.0)


def test_vector3_equality() -> None:
    """Dataclass value equality lets assertions stay concise."""
    assert Vector3(1.0, 2.0, 3.0) == Vector3(1.0, 2.0, 3.0)
    assert Vector3(1.0, 2.0, 3.0) != Vector3(1.0, 2.0, 4.0)


# --------------------------------------------------------------------------- #
# SubTask 1 — set_input_vector
# --------------------------------------------------------------------------- #
def test_set_input_vector_calls_rpc() -> None:
    """``set_input_vector`` emits one ``call_method_on_node`` RPC with set_velocity."""
    controller, mock_client = _make_controller()
    controller.set_input_vector(Vector3(1.0, 0.0, 0.0))
    mock_client.call_method.assert_called_once_with(
        "call_method_on_node",
        [_NODE_PATH, "set_velocity", [{"x": 1.0, "y": 0.0, "z": 0.0}]],
    )


# --------------------------------------------------------------------------- #
# SubTask 2 — apply_impulse
# --------------------------------------------------------------------------- #
def test_apply_impulse() -> None:
    """``apply_impulse`` forwards the impulse dict to ``apply_impulse`` on the node."""
    controller, mock_client = _make_controller()
    controller.apply_impulse(Vector3(0.0, 5.0, 0.0))
    mock_client.call_method.assert_called_once_with(
        "call_method_on_node",
        [_NODE_PATH, "apply_impulse", [{"x": 0.0, "y": 5.0, "z": 0.0}]],
    )


# --------------------------------------------------------------------------- #
# SubTask 3 — teleport
# --------------------------------------------------------------------------- #
def test_teleport_sets_transform() -> None:
    """``teleport`` calls ``set_position`` (which writes ``transform.origin``)."""
    controller, mock_client = _make_controller()
    controller.teleport(Vector3(10.0, 0.0, 5.0))
    mock_client.call_method.assert_called_once_with(
        "call_method_on_node",
        [_NODE_PATH, "set_position", [{"x": 10.0, "y": 0.0, "z": 5.0}]],
    )


# --------------------------------------------------------------------------- #
# SubTask 4 — get_state
# --------------------------------------------------------------------------- #
def test_get_state_parses_response() -> None:
    """``get_state`` parses Transform3D + velocity + is_on_floor into CharacterState."""
    controller, mock_client = _make_controller()
    transform = _identity_transform(origin={"x": 1.0, "y": 2.0, "z": 3.0})
    velocity = {"x": 0.5, "y": 0.0, "z": -0.5}
    # The controller issues three call_method calls in order: transform,
    # velocity, then is_on_floor.
    mock_client.call_method.side_effect = [transform, velocity, True]

    state = controller.get_state()

    assert isinstance(state, CharacterState)
    assert state.position == Vector3(1.0, 2.0, 3.0)
    assert state.velocity == Vector3(0.5, 0.0, -0.5)
    assert state.on_floor is True
    # Identity basis → forward = -Z = (0, 0, -1).
    assert state.heading == Vector3(0.0, 0.0, -1.0)
    # Verify the three RPC calls were the expected ones.
    assert mock_client.call_method.call_count == 3
    expected_calls = [
        (("get_property", [_NODE_PATH, "global_transform"]),),
        (("get_property", [_NODE_PATH, "velocity"]),),
        (("call_method_on_node", [_NODE_PATH, "is_on_floor", []]),),
    ]
    actual_calls = [
        (c.args,) for c in mock_client.call_method.call_args_list
    ]
    assert actual_calls == expected_calls


def test_get_state_rotated_heading() -> None:
    """A 90° Y-rotation maps the forward axis from -Z to +X."""
    controller, mock_client = _make_controller()
    # Basis after rotating 90° around Y: forward (-Z) → +X.
    # Rotation matrix (Y, 90°): x' = z, z' = -x → columns:
    #   x-axis: (0, 0, -1), y-axis: (0, 1, 0), z-axis: (1, 0, 0)
    transform = {
        "basis": {
            "x": {"x": 0.0, "y": 0.0, "z": -1.0},
            "y": {"x": 0.0, "y": 1.0, "z": 0.0},
            "z": {"x": 1.0, "y": 0.0, "z": 0.0},
        },
        "origin": {"x": 0.0, "y": 0.0, "z": 0.0},
    }
    mock_client.call_method.side_effect = [transform, {"x": 0.0, "y": 0.0, "z": 0.0}, False]

    state = controller.get_state()

    # heading = -basis.z = -(1, 0, 0) = (-1, 0, 0)... wait: forward is -Z,
    # and after 90° Y-rotation the local -Z points to world +X. The basis z
    # column is (1, 0, 0), so heading = -z = (-1, 0, 0). But Godot's
    # look_at points -Z at the target, so a 90° rotation about Y turns
    # -Z toward +X. Let's verify the controller's arithmetic: heading =
    # -basis.z_col = -(1,0,0) = (-1, 0, 0).
    assert state.heading == Vector3(-1.0, 0.0, 0.0)


def test_get_state_tolerates_malformed_transform() -> None:
    """A non-dict transform payload yields zero position/heading without raising."""
    controller, mock_client = _make_controller()
    mock_client.call_method.side_effect = [None, None, None]

    state = controller.get_state()

    assert state.position == Vector3(0.0, 0.0, 0.0)
    assert state.velocity == Vector3(0.0, 0.0, 0.0)
    assert state.heading == Vector3(0.0, 0.0, 0.0)
    assert state.on_floor is False


# --------------------------------------------------------------------------- #
# Convenience accessors
# --------------------------------------------------------------------------- #
def test_set_velocity_calls_rpc() -> None:
    """``set_velocity`` emits the same payload as ``set_input_vector``."""
    controller, mock_client = _make_controller()
    controller.set_velocity(Vector3(2.0, 3.0, 4.0))
    mock_client.call_method.assert_called_once_with(
        "call_method_on_node",
        [_NODE_PATH, "set_velocity", [{"x": 2.0, "y": 3.0, "z": 4.0}]],
    )


def test_get_velocity() -> None:
    """``get_velocity`` reads the ``velocity`` property and parses it."""
    controller, mock_client = _make_controller()
    mock_client.call_method.return_value = {"x": 2.0, "y": 3.0, "z": 4.0}

    vel = controller.get_velocity()

    assert vel == Vector3(2.0, 3.0, 4.0)
    mock_client.call_method.assert_called_once_with(
        "get_property",
        [_NODE_PATH, "velocity"],
    )


def test_look_at() -> None:
    """``look_at`` forwards the target dict to ``look_at`` on the node."""
    controller, mock_client = _make_controller()
    controller.look_at(Vector3(0.0, 0.0, 10.0))
    mock_client.call_method.assert_called_once_with(
        "call_method_on_node",
        [_NODE_PATH, "look_at", [{"x": 0.0, "y": 0.0, "z": 10.0}]],
    )


def test_rotate_y() -> None:
    """``rotate_y`` forwards a single float angle (no Vector3 wrapping)."""
    controller, mock_client = _make_controller()
    controller.rotate_y(1.5708)
    mock_client.call_method.assert_called_once_with(
        "call_method_on_node",
        [_NODE_PATH, "rotate_y", [1.5708]],
    )


def test_node_path_passed_through() -> None:
    """A custom node_path is threaded into every RPC payload."""
    custom_path = "/root/Scene/NPC_01"
    controller, mock_client = _make_controller(node_path=custom_path)
    controller.set_input_vector(Vector3(1.0, 0.0, 0.0))
    mock_client.call_method.assert_called_once_with(
        "call_method_on_node",
        [custom_path, "set_velocity", [{"x": 1.0, "y": 0.0, "z": 0.0}]],
    )
