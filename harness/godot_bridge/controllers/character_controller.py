"""LAAP Godot Bridge — Character Controller (Task 7).

This module is part of the LAAP 0-Token Game Dev Framework. It provides a
high-level Python controller that drives a Godot ``CharacterBody3D`` node
through the JSON-RPC bridge implemented in
``gdscripts/laap_bridge.gd`` (Task 3).

All operations are 0-token: no LLM is involved. The controller translates
Python-side calls into JSON-RPC 2.0 requests carried by
:class:`GodotJSONRPCClient` over TCP (port 6005) to the running Godot
engine. The bridge dispatches them via ``call_method_on_node(path, method,
args)``, ``get_property(path, prop)`` and ``set_property(path, prop, value)``
RPC methods registered on the ``LAAPBridge`` autoload.

Public surface
--------------
- :class:`Vector3` — lightweight 3D vector with ``to_dict`` / ``from_dict``
  serialisation matching Godot's ``Vector3`` dict form.
- :class:`CharacterState` — immutable snapshot of a character's physical
  state (position, velocity, heading, floor contact).
- :class:`CharacterController` — the controller itself, wrapping a
  :class:`GodotJSONRPCClient` and a node path.

Thread safety
-------------
The controller performs no internal locking; it delegates all transport
concerns to the thread-safe :class:`GodotJSONRPCClient`. A single
controller instance may be shared across threads provided the caller does
not mutate the ``node_path``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

# Import the JSON-RPC client. Try the fully-qualified package path first
# (when the harness root is on sys.path); fall back to the subpackage path
# (when the godot_bridge root is on sys.path, as in unit tests and the
# verification command); finally fall back to the bare module name (when
# only python/ is on sys.path, matching the existing jsonrpc test pattern).
try:  # pragma: no cover - exercised depending on sys.path
    from godot_bridge.python.godot_jsonrpc_client import GodotJSONRPCClient
except ImportError:  # pragma: no cover
    try:
        from python.godot_jsonrpc_client import GodotJSONRPCClient  # type: ignore
    except ImportError:  # pragma: no cover
        from godot_jsonrpc_client import GodotJSONRPCClient  # type: ignore


__all__ = ["Vector3", "CharacterState", "CharacterController"]


@dataclass
class Vector3:
    """Minimal 3D vector mirroring Godot's ``Vector3`` for RPC serialisation.

    Godot has no Python binding in this harness, so we carry our own
    lightweight value type. ``to_dict`` emits the ``{"x":..,"y":..,"z":..}``
    form that the bridge's GDScript side can consume, and ``from_dict``
    parses the same shape returned by ``get_property`` / ``callv``.

    The dataclass provides value equality (``Vector3(1,2,3) ==
    Vector3(1,2,3)``) which keeps unit-test assertions concise.
    """

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def to_dict(self) -> dict[str, float]:
        """Serialise to the ``{"x","y","z"}`` dict form used over the wire."""
        return {"x": float(self.x), "y": float(self.y), "z": float(self.z)}

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "Vector3":
        """Parse a ``{"x","y","z"}`` dict; tolerant of missing keys/None."""
        if d is None:
            return cls()
        return cls(
            x=float(d.get("x", 0.0)),
            y=float(d.get("y", 0.0)),
            z=float(d.get("z", 0.0)),
        )


@dataclass
class CharacterState:
    """Immutable snapshot of a ``CharacterBody3D``'s physical state.

    Returned by :meth:`CharacterController.get_state`. ``heading`` is the
    world-space forward direction (Godot's ``-Z`` basis column), useful for
    steering logic. ``on_floor`` mirrors ``CharacterBody3D.is_on_floor()``.
    """

    position: Vector3
    velocity: Vector3
    heading: Vector3
    on_floor: bool = False


class CharacterController:
    """0-token controller driving a Godot ``CharacterBody3D`` via JSON-RPC.

    Each method maps to one or more JSON-RPC calls against the
    ``LAAPBridge`` autoload (see ``gdscripts/laap_bridge.gd``). The
    controller is a thin translation layer: Python values in, RPC payloads
    out, RPC results back to Python values. No state is cached between
    calls, so every getter round-trips to the engine.

    Parameters
    ----------
    jsonrpc_client : GodotJSONRPCClient
        A connected (or connectable) JSON-RPC client. The controller does
        not own the client's lifecycle; the caller is responsible for
        closing it.
    node_path : str
        Godot node path of the ``CharacterBody3D`` to drive, e.g.
        ``"/root/Main/Player"``.

    Examples
    --------
    >>> client = GodotJSONRPCClient()
    >>> ctrl = CharacterController(client, "/root/Main/Player")
    >>> ctrl.set_input_vector(Vector3(1.0, 0.0, 0.0))
    >>> state = ctrl.get_state()
    """

    # RPC method names exposed by the LAAPBridge autoload.
    _RPC_CALL_METHOD_ON_NODE: ClassVar[str] = "call_method_on_node"
    _RPC_GET_PROPERTY: ClassVar[str] = "get_property"
    _RPC_SET_PROPERTY: ClassVar[str] = "set_property"

    def __init__(self, jsonrpc_client: GodotJSONRPCClient, node_path: str) -> None:
        self._client = jsonrpc_client
        self._node_path = str(node_path)

    # ------------------------------------------------------------------ #
    # Internal RPC helpers
    # ------------------------------------------------------------------ #
    def _call_on_node(self, method: str, args: list[Any]) -> Any:
        """Invoke ``method`` on the character node via ``call_method_on_node``.

        Sends a positional JSON-RPC params list ``[node_path, method,
        args]``; the GDScript bridge forwards ``args`` to
        ``node.callv(method, args)``.
        """
        return self._client.call_method(
            self._RPC_CALL_METHOD_ON_NODE,
            [self._node_path, method, args],
        )

    def _get_property(self, prop: str) -> Any:
        """Read property ``prop`` from the node via the ``get_property`` RPC."""
        return self._client.call_method(
            self._RPC_GET_PROPERTY,
            [self._node_path, prop],
        )

    def _set_property(self, prop: str, value: Any) -> Any:
        """Write ``value`` to property ``prop`` via the ``set_property`` RPC."""
        return self._client.call_method(
            self._RPC_SET_PROPERTY,
            [self._node_path, prop, value],
        )

    # ------------------------------------------------------------------ #
    # Public API — SubTasks 1–4
    # ------------------------------------------------------------------ #
    def set_input_vector(self, vector: Vector3) -> None:
        """Inject ``CharacterBody3D.velocity`` via ``call_method_on_node``.

        SubTask 1. The vector is serialised to the Godot ``Vector3`` dict
        form and passed as the sole argument to ``set_velocity`` on the
        target node.
        """
        self._call_on_node("set_velocity", [vector.to_dict()])

    def apply_impulse(self, impulse: Vector3) -> None:
        """Apply a physics impulse to the character body.

        SubTask 2. Calls ``apply_impulse`` on the node. ``CharacterBody3D``
        has no built-in ``apply_impulse`` (unlike ``RigidBody3D``); the
        target node is expected to expose a same-named method (typically
        adding to ``velocity``) for this controller to drive.
        """
        self._call_on_node("apply_impulse", [impulse.to_dict()])

    def teleport(self, position: Vector3) -> None:
        """Instantly move the character to ``position``, bypassing physics.

        SubTask 3. Sets ``transform.origin`` directly by calling
        ``set_position`` on the node, which writes ``transform.origin``
        without going through the physics solver / ``move_and_slide``.
        """
        self._call_on_node("set_position", [position.to_dict()])

    def get_state(self) -> CharacterState:
        """Read the character's current physical state.

        SubTask 4. Issues three RPCs:

        1. ``get_property("global_transform")`` → Transform3D dict, from
           which both ``position`` (origin) and ``heading`` (``-basis.z``)
           are extracted.
        2. ``get_property("velocity")`` → Vector3 dict.
        3. ``call_method_on_node("is_on_floor", [])`` → bool.
        """
        transform = self._get_property("global_transform")
        velocity_raw = self._get_property("velocity")
        on_floor = self._call_on_node("is_on_floor", [])
        return CharacterState(
            position=self._extract_position(transform),
            velocity=Vector3.from_dict(velocity_raw),
            heading=self._extract_heading(transform),
            on_floor=bool(on_floor),
        )

    # ------------------------------------------------------------------ #
    # Convenience accessors
    # ------------------------------------------------------------------ #
    def set_velocity(self, velocity: Vector3) -> None:
        """Directly set the node's ``velocity`` property via RPC.

        Functionally equivalent to :meth:`set_input_vector` but provided
        under the physics-facing name for callers that model the character
        at the velocity level rather than the input level.
        """
        self._call_on_node("set_velocity", [velocity.to_dict()])

    def get_velocity(self) -> Vector3:
        """Read the node's current ``velocity`` property."""
        return Vector3.from_dict(self._get_property("velocity"))

    def look_at(self, target: Vector3) -> None:
        """Orient the character to face ``target`` in world space.

        Wraps ``Node3D.look_at(target)``. Only the target position is
        forwarded; the optional ``use_model_front`` argument defaults to
        ``false`` on the Godot side.
        """
        self._call_on_node("look_at", [target.to_dict()])

    def rotate_y(self, angle_rad: float) -> None:
        """Rotate the character around the world Y axis by ``angle_rad`` radians.

        Wraps ``Node3D.rotate_y(angle)`` — a single float argument, so no
        Vector3 serialisation is involved.
        """
        self._call_on_node("rotate_y", [float(angle_rad)])

    # ------------------------------------------------------------------ #
    # Transform parsing helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_position(transform: Any) -> Vector3:
        """Extract the origin vector from a Transform3D dict.

        Tolerates ``None`` / non-dict payloads by returning a zero vector,
        so a malformed engine response never raises into the caller.
        """
        if not isinstance(transform, dict):
            return Vector3()
        return Vector3.from_dict(transform.get("origin"))

    @staticmethod
    def _extract_heading(transform: Any) -> Vector3:
        """Extract the forward heading (``-basis.z``) from a Transform3D dict.

        Godot's forward axis is ``-Z``; the basis ``z`` column is the local
        ``+Z`` axis expressed in world space, so the heading vector is its
        negation. Returns a zero vector if the payload is malformed.
        """
        if not isinstance(transform, dict):
            return Vector3()
        basis = transform.get("basis")
        if not isinstance(basis, dict):
            return Vector3()
        z_col = basis.get("z")
        if not isinstance(z_col, dict):
            return Vector3()
        return Vector3(
            x=-float(z_col.get("x", 0.0)),
            y=-float(z_col.get("y", 0.0)),
            z=-float(z_col.get("z", 0.0)),
        )
