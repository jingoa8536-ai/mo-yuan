"""LAAP Godot Bridge — Physics Stepping Controller (Task 10).

Provides deterministic, single-step physics advancement for the 0-Token Game
Dev Framework. The Godot engine is paused via ``Engine.time_scale = 0`` so the
simulation no longer advances autonomously, and individual physics frames are
then driven on demand by calling ``SceneTree.physics_step()`` through the
JSONRPC bridge.

This module also provides state snapshots (``save_snapshot`` /
``restore_snapshot``) so a test harness can roll a scene back to a known
configuration after exploratory steps, plus two convenience helpers:

- ``step_and_compare`` — snapshot → step → snapshot, returning a positional
  diff so callers can verify which bodies moved.
- ``validate_no_penetration`` — steps one frame and reports any bodies whose
  position was changed by Godot's collision resolver, returning the inferred
  collision pairs.

All operations are 0-token: every call is a deterministic JSON-RPC round
trip, with no LLM in the loop.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# The client lives under ``python/`` next to this ``controllers/`` package.
# Support both import styles so the module works whether the bridge root or
# its ``python/`` subdirectory is on ``sys.path``.
try:  # pragma: no cover - exercised by both layouts in different envs
    from python.godot_jsonrpc_client import GodotJSONRPCClient
except ImportError:  # pragma: no cover
    from godot_jsonrpc_client import GodotJSONRPCClient  # type: ignore


__all__ = ["PhysicsSnapshot", "PhysicsStepper"]


@dataclass
class PhysicsSnapshot:
    """Point-in-time state of a set of physics nodes.

    Each entry maps a node path to a dict of ``{position, rotation,
    velocity, angular_velocity}``. The dict is intentionally
    JSON-serialisable so it can be persisted, diffed, or sent back over the
    bridge without further conversion.
    """

    node_states: dict[str, dict[str, Any]] = field(default_factory=dict)


class PhysicsStepper:
    """Deterministic physics stepping controller for a paused Godot engine.

    The controller wraps a :class:`GodotJSONRPCClient` and exposes
    pause / step / snapshot operations that drive the engine via JSON-RPC.
    All public methods are synchronous and block on the RPC round trip.

    Parameters
    ----------
    jsonrpc_client : GodotJSONRPCClient
        Connected JSON-RPC client used to invoke bridge RPCs
        (``set_property``, ``get_property``, ``call_method_on_node``,
        ``get_scene_tree``).
    snapshot_node_paths : list[str] | None
        Explicit list of node paths to snapshot. If ``None``, every
        ``Node3D`` in the scene is included (resolved lazily via the
        ``get_scene_tree`` RPC on the first ``save_snapshot`` call).
    """

    # Godot's Engine singleton is exposed as a node-like target by the
    # bridge; ``Engine`` is the conventional path used in the spec.
    _ENGINE_PATH = "Engine"
    # SceneTree singleton, addressed as a child of /root by the bridge.
    _SCENE_TREE_PATH = "/root/SceneTree"
    # The four per-node properties tracked by every snapshot.
    _PROPS: tuple[str, ...] = (
        "position",
        "rotation",
        "velocity",
        "angular_velocity",
    )

    def __init__(
        self,
        jsonrpc_client: GodotJSONRPCClient,
        snapshot_node_paths: list[str] | None = None,
    ) -> None:
        self._client = jsonrpc_client
        self._snapshot_node_paths = snapshot_node_paths
        # Lazily populated when snapshot_node_paths is None and the first
        # save_snapshot() call queries the scene tree. Keeping a cached
        # resolved list avoids repeating the (relatively expensive)
        # get_scene_tree RPC on every snapshot.
        self._resolved_paths: list[str] | None = (
            list(snapshot_node_paths)
            if snapshot_node_paths is not None
            else None
        )

    # ------------------------------------------------------------------ #
    # Time control
    # ------------------------------------------------------------------ #
    def pause(self) -> None:
        """Pause the engine by setting ``Engine.time_scale = 0``.

        After this call the simulation no longer advances autonomously;
        use :meth:`step` to drive individual physics frames.
        """
        self._set_property(self._ENGINE_PATH, "time_scale", 0)

    def resume(self) -> None:
        """Resume the engine by restoring ``Engine.time_scale = 1``."""
        self._set_property(self._ENGINE_PATH, "time_scale", 1)

    def step(self, frames: int = 1) -> None:
        """Advance ``frames`` physics steps while the engine is paused.

        Each frame is one call to ``SceneTree.physics_step()`` invoked
        through the bridge's ``call_method_on_node`` RPC. The caller is
        expected to have called :meth:`pause` first; this method does not
        enforce it.

        Parameters
        ----------
        frames : int
            Number of physics frames to step (default ``1``). Must be
            ``>= 0``; ``0`` is a no-op.

        Raises
        ------
        ValueError
            If ``frames`` is negative.
        """
        frames = int(frames)
        if frames < 0:
            raise ValueError(f"frames must be non-negative, got {frames}")
        for _ in range(frames):
            self._call_method_on_node(
                self._SCENE_TREE_PATH, "physics_step", []
            )

    # ------------------------------------------------------------------ #
    # Snapshots
    # ------------------------------------------------------------------ #
    def save_snapshot(self) -> PhysicsSnapshot:
        """Capture position/rotation/velocity for all snapshot node paths.

        If ``snapshot_node_paths`` was ``None`` at construction time, the
        list of paths is resolved once via the ``get_scene_tree`` RPC and
        cached. Only nodes whose class derives from ``Node3D``
        (heuristic: class name contains ``"3D"``) are included in the
        auto-discovery.

        Returns
        -------
        PhysicsSnapshot
            Snapshot dict keyed by node path; each value has the four
            tracked properties.
        """
        paths = self._ensure_paths()
        return self._snapshot_paths(paths)

    def restore_snapshot(self, snapshot: PhysicsSnapshot) -> None:
        """Write back the captured state for every node in ``snapshot``.

        Each property is restored with a separate ``set_property`` RPC.
        The order is ``position → rotation → velocity → angular_velocity``,
        matching the capture order in :meth:`save_snapshot`. Properties
        absent from a node's entry are skipped so partial snapshots can be
        restored safely.
        """
        for path, state in snapshot.node_states.items():
            for prop in self._PROPS:
                if prop in state:
                    self._set_property(path, prop, state[prop])

    # ------------------------------------------------------------------ #
    # Higher-level helpers
    # ------------------------------------------------------------------ #
    def step_and_compare(self, frames: int = 1) -> dict:
        """Snapshot → step → snapshot, returning a positional diff.

        Returns
        -------
        dict
            ``{"moved": [(path, old_pos, new_pos), ...],
              "unchanged": [path, ...]}`` where ``moved`` lists every node
            whose ``position`` field changed (in snapshot iteration order)
            and ``unchanged`` lists the rest.
        """
        before = self.save_snapshot()
        self.step(frames)
        after = self.save_snapshot()

        moved: list[tuple[str, Any, Any]] = []
        unchanged: list[str] = []
        for path, old_state in before.node_states.items():
            new_state = after.node_states.get(path, {})
            old_pos = old_state.get("position")
            new_pos = new_state.get("position")
            if old_pos != new_pos:
                moved.append((path, old_pos, new_pos))
            else:
                unchanged.append(path)
        return {"moved": moved, "unchanged": unchanged}

    def validate_no_penetration(
        self, body_paths: list[str]
    ) -> list[tuple[str, str]]:
        """Step one frame and report body pairs that collided.

        A collision is inferred when a body's position changes after a
        single physics step while the engine is paused (i.e. the only
        possible cause is Godot's collision resolver pushing overlapping
        bodies apart). All bodies whose position changed are paired
        together and returned.

        Parameters
        ----------
        body_paths : list[str]
            Node paths of the physics bodies to check.

        Returns
        -------
        list[tuple[str, str]]
            List of ``(body_a, body_b)`` pairs that appear to have
            collided. Empty list if no body moved (or if only one body
            moved, since pairing requires at least two movers).
        """
        if not body_paths:
            return []
        paths = list(body_paths)
        before = self._snapshot_paths(paths)
        self.step(1)
        after = self._snapshot_paths(paths)

        moved: list[str] = []
        for path in paths:
            old_pos = before.node_states.get(path, {}).get("position")
            new_pos = after.node_states.get(path, {}).get("position")
            if old_pos != new_pos:
                moved.append(path)

        # Pair every moved body with every other moved body. A real engine
        # would give us contact points; this heuristic is sufficient for
        # 0-token validation, and the caller can refine the pairs from
        # there if needed.
        pairs: list[tuple[str, str]] = []
        for i, a in enumerate(moved):
            for b in moved[i + 1:]:
                pairs.append((a, b))
        return pairs

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _snapshot_paths(self, paths: list[str]) -> PhysicsSnapshot:
        """Capture the four tracked properties for each path in ``paths``."""
        states: dict[str, dict[str, Any]] = {}
        for path in paths:
            states[path] = {
                prop: self._get_property(path, prop) for prop in self._PROPS
            }
        return PhysicsSnapshot(node_states=states)

    def _ensure_paths(self) -> list[str]:
        """Return the snapshot node paths, resolving from the scene tree once."""
        if self._resolved_paths is not None:
            return self._resolved_paths
        tree = self._client.call_method("get_scene_tree", {})
        paths: list[str] = []
        self._collect_node3d_paths(tree, paths)
        self._resolved_paths = paths
        return paths

    @staticmethod
    def _collect_node3d_paths(node: Any, out: list[str]) -> None:
        """Walk a serialized scene tree and collect Node3D paths.

        The bridge's ``get_scene_tree`` RPC returns nested dicts of
        ``{path, class, name, children: [...]}``. We treat any node whose
        ``class`` contains the substring ``"3D"`` as a Node3D-derived
        node worth snapshotting (covers ``Node3D``, ``RigidBody3D``,
        ``CharacterBody3D``, ``StaticBody3D``, ``MeshInstance3D``, ...).
        """
        if not isinstance(node, dict):
            return
        cls = node.get("class", "")
        path = node.get("path", "")
        if path and isinstance(cls, str) and "3D" in cls:
            out.append(path)
        for child in node.get("children", []) or []:
            PhysicsStepper._collect_node3d_paths(child, out)

    def _set_property(self, path: str, prop: str, value: Any) -> None:
        """Invoke the bridge ``set_property`` RPC."""
        self._client.call_method(
            "set_property",
            {"path": path, "prop": prop, "value": value},
        )

    def _get_property(self, path: str, prop: str) -> Any:
        """Invoke the bridge ``get_property`` RPC and return the value."""
        return self._client.call_method(
            "get_property",
            {"path": path, "prop": prop},
        )

    def _call_method_on_node(
        self, path: str, method: str, args: list
    ) -> Any:
        """Invoke the bridge ``call_method_on_node`` RPC."""
        return self._client.call_method(
            "call_method_on_node",
            {"path": path, "method": method, "args": args},
        )
