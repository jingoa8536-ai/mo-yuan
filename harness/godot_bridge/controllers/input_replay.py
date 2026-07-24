"""Input recording and replay for the LAAP Godot bridge (Task 9).

Records ``CharacterController.set_input_vector()`` calls (Task 7) into an
``InputRecording`` that can be:

* saved to / loaded from JSON (0-token, no external services),
* replayed frame-by-frame against any object exposing
  ``set_input_vector(tuple[float, float, float]) -> None`` (duck-typed; the
  real ``CharacterController`` is imported only under ``TYPE_CHECKING`` so
  this module loads even before Task 7 lands),
* played at 0.5x / 1x / 2x speed via a single ``speed`` multiplier,
* interrupted mid-replay from another thread via ``stop()``.

Timing uses :func:`time.perf_counter` for high precision and
:meth:`threading.Event.wait` for an interruptible sleep so ``stop()`` returns
promptly (well under the 0.5s budget asserted by the tests).
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:  # pragma: no cover - type-only import
    # Forward reference for static analysis. At runtime any object exposing
    # ``set_input_vector(tuple[float, float, float]) -> None`` works (Task 7's
    # CharacterController). Deferred so this module imports cleanly even when
    # character_controller.py is not yet present.
    from .character_controller import CharacterController  # noqa: F401


@dataclass
class InputFrame:
    """A single recorded input sample.

    Attributes:
        timestamp_s: Seconds since the recording started (>= 0, monotonic).
        node_path: Godot node path the input was directed at (e.g.
            ``"/root/Main/Player"``).
        input_vector: The 3-axis input vector passed to
            ``CharacterController.set_input_vector``.
        metadata: Optional free-form metadata (button flags, source, etc.).
    """

    timestamp_s: float
    node_path: str
    input_vector: tuple[float, float, float]
    metadata: dict = field(default_factory=dict)


@dataclass
class InputRecording:
    """A full recording: ordered frames plus descriptive header fields.

    Attributes:
        frames: Ordered list of :class:`InputFrame` (ascending timestamps).
        duration_s: Total wall-clock duration of the recording in seconds
            (typically the timestamp of the last frame).
        name: Human-readable recording name.
        recorded_at: ISO-8601 timestamp string marking when recording ended.
    """

    frames: list[InputFrame]
    duration_s: float
    name: str
    recorded_at: str


class InputRecorder:
    """Records ``set_input_vector`` calls into an :class:`InputRecording`.

    Usage::

        rec = InputRecorder()
        rec.start()
        for v in inputs:
            rec.record("/root/Player", v)
        recording = rec.stop()
        rec.save(recording, "run.json")

    The recorder is not thread-safe; calls to ``start`` / ``record`` / ``stop``
    must originate from a single thread (the game loop, typically).
    """

    def __init__(self) -> None:
        self._frames: list[InputFrame] = []
        self._start_perf: float = 0.0
        self._recording: bool = False

    def start(self) -> None:
        """Reset the timer and clear any previously buffered frames."""
        self._frames = []
        self._start_perf = time.perf_counter()
        self._recording = True

    def record(
        self,
        node_path: str,
        input_vector: tuple[float, float, float],
        metadata: dict | None = None,
    ) -> None:
        """Append a single frame at the current elapsed time.

        Args:
            node_path: Target Godot node path for this input.
            input_vector: 3-axis input vector.
            metadata: Optional metadata dict; ``None`` becomes ``{}``.
        """
        if not self._recording:
            # Auto-start so callers that forget ``start()`` still record.
            self.start()
        ts = time.perf_counter() - self._start_perf
        self._frames.append(
            InputFrame(
                timestamp_s=ts,
                node_path=node_path,
                input_vector=tuple(input_vector),
                metadata=dict(metadata) if metadata else {},
            )
        )

    def stop(self) -> InputRecording:
        """Finalize and return the recording.

        Sets ``recorded_at`` to the current ISO-8601 timestamp and
        ``duration_s`` to the last frame's timestamp (0 if empty).
        """
        self._recording = False
        duration = self._frames[-1].timestamp_s if self._frames else 0.0
        return InputRecording(
            frames=list(self._frames),
            duration_s=duration,
            name="recording",
            recorded_at=datetime.now().isoformat(),
        )

    def save(self, recording: InputRecording, file_path: str) -> None:
        """Serialize the recording to a JSON file.

        Tuples are emitted as JSON arrays and re-hydrated as tuples by
        :meth:`load`, preserving the ``input_vector`` type.
        """
        data = {
            "name": recording.name,
            "duration_s": recording.duration_s,
            "recorded_at": recording.recorded_at,
            "frames": [
                {
                    "timestamp_s": f.timestamp_s,
                    "node_path": f.node_path,
                    "input_vector": list(f.input_vector),
                    "metadata": f.metadata,
                }
                for f in recording.frames
            ],
        }
        with open(file_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)

    def load(self, file_path: str) -> InputRecording:
        """Load a recording previously written by :meth:`save`."""
        with open(file_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        frames = [
            InputFrame(
                timestamp_s=f["timestamp_s"],
                node_path=f["node_path"],
                input_vector=tuple(f["input_vector"]),
                metadata=f.get("metadata", {}),
            )
            for f in data.get("frames", [])
        ]
        return InputRecording(
            frames=frames,
            duration_s=data.get("duration_s", 0.0),
            name=data.get("name", "recording"),
            recorded_at=data.get("recorded_at", ""),
        )


class InputReplayer:
    """Replays an :class:`InputRecording` against a character controller.

    The controller is duck-typed: any object with a
    ``set_input_vector(tuple[float, float, float]) -> None`` method works,
    so tests can inject a ``MagicMock``.

    Speed semantics: ``speed=2.0`` plays the recording in half the wall-clock
    time; ``speed=0.5`` plays it in double the wall-clock time. A frame
    recorded at ``t`` seconds fires at ``t / speed`` seconds after play start.
    """

    def __init__(self, character_controller: "CharacterController | Any") -> None:
        self._controller = character_controller
        # Reused across plays; cleared at the start of each play, set by
        # ``stop()``. Using a single event keeps the API simple and is safe
        # for the single-replay-at-a-time usage the spec targets.
        self._stop_event = threading.Event()
        # Track the live replay thread so callers can join if desired.
        self._thread: threading.Thread | None = None

    def play(self, recording: InputRecording, speed: float = 1.0) -> None:
        """Block until the recording has been fully replayed.

        Respects ``speed`` (see class docstring) and terminates early if
        ``stop()`` is called from another thread.
        """
        self._stop_event.clear()
        self._replay(recording, speed)

    def play_async(
        self,
        recording: InputRecording,
        speed: float = 1.0,
        on_complete: Callable[[], None] | None = None,
    ) -> threading.Thread:
        """Non-blocking variant of :meth:`play`.

        Returns the worker :class:`threading.Thread` immediately. ``on_complete``
        (if given) is invoked from the worker thread after replay finishes or
        is interrupted.
        """
        self._stop_event.clear()

        def _runner() -> None:
            try:
                self._replay(recording, speed)
            finally:
                if on_complete is not None:
                    on_complete()

        thread = threading.Thread(target=_runner, daemon=True, name="InputReplayer")
        self._thread = thread
        thread.start()
        return thread

    def stop(self) -> None:
        """Signal the active replay (if any) to abort after the current frame.

        Safe to call from any thread; idempotent. The replay thread will
        return within the remaining sleep of the current frame, which is
        bounded by the interruptible ``Event.wait`` used internally.
        """
        self._stop_event.set()

    # ------------------------------------------------------------------ #

    def _replay(self, recording: InputRecording, speed: float) -> None:
        if speed <= 0:
            raise ValueError(f"speed must be positive, got {speed!r}")
        if not recording.frames:
            return

        play_start = time.perf_counter()
        for frame in recording.frames:
            target_wall_offset = frame.timestamp_s / speed
            elapsed = time.perf_counter() - play_start
            remaining = target_wall_offset - elapsed
            if remaining > 0:
                # Interruptible sleep: returns True if stop() was called.
                if self._stop_event.wait(timeout=remaining):
                    return
            elif self._stop_event.is_set():
                return
            # Inject the input vector for this frame.
            self._controller.set_input_vector(frame.input_vector)
