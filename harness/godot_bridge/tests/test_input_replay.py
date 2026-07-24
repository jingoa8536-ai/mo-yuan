"""Unit tests for :mod:`controllers.input_replay` (Task 9).

Covers:

- Recording produces correctly-timestamped frames.
- JSON save/load round-trips frames losslessly (tuple preserved).
- ``InputReplayer.play`` invokes ``set_input_vector`` once per frame with the
  recorded vectors.
- Replay speed multipliers (0.5x, 2x) scale wall-clock duration as expected.
- ``play_async`` returns a live ``threading.Thread`` that completes the replay.
- ``stop()`` interrupts an in-flight async replay within ~0.5s.

The ``CharacterController`` is mocked with ``MagicMock``; no real Godot or
character controller is required, keeping the suite 0-token.

Run::

    python -m pytest D:\\LAAP\\harness\\godot_bridge\\tests\\test_input_replay.py -v
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Make ``controllers`` importable when tests run from anywhere.
_BRIDGE_ROOT = Path(__file__).resolve().parent.parent
if str(_BRIDGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_ROOT))

from controllers.input_replay import (  # noqa: E402  (import after sys.path tweak)
    InputFrame,
    InputRecording,
    InputRecorder,
    InputReplayer,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _make_recording(frames: list[tuple[float, tuple[float, float, float]]],
                    name: str = "test-recording") -> InputRecording:
    """Build an :class:`InputRecording` from ``(timestamp, vector)`` pairs."""
    if not frames:
        return InputRecording(frames=[], duration_s=0.0, name=name,
                              recorded_at="2026-07-05T00:00:00")
    built = [
        InputFrame(timestamp_s=ts, node_path="/root/Player",
                   input_vector=tuple(vec), metadata={"idx": i})
        for i, (ts, vec) in enumerate(frames)
    ]
    return InputRecording(frames=built, duration_s=built[-1].timestamp_s,
                          name=name, recorded_at="2026-07-05T00:00:00")


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

def test_record_creates_frames():
    """recorder.start() → 3 records → stop() yields 3 monotonic frames."""
    rec = InputRecorder()
    rec.start()

    # Space records by a small, measurable amount.
    rec.record("/root/Player", (1.0, 0.0, 0.0), metadata={"i": 0})
    time.sleep(0.02)
    rec.record("/root/Player", (0.0, 1.0, 0.0), metadata={"i": 1})
    time.sleep(0.02)
    rec.record("/root/Player", (0.0, 0.0, 1.0), metadata={"i": 2})

    recording = rec.stop()

    assert len(recording.frames) == 3
    # Timestamps are monotonic non-decreasing.
    ts = [f.timestamp_s for f in recording.frames]
    assert ts[0] >= 0.0
    assert ts[1] >= ts[0]
    assert ts[2] >= ts[1]
    # The 40ms of sleeps should be reflected (allow generous slack for CI).
    assert ts[2] - ts[0] >= 0.03
    # Vectors and metadata preserved.
    assert recording.frames[0].input_vector == (1.0, 0.0, 0.0)
    assert recording.frames[1].input_vector == (0.0, 1.0, 0.0)
    assert recording.frames[2].input_vector == (0.0, 0.0, 1.0)
    assert recording.frames[0].metadata == {"i": 0}
    # duration_s should match the last frame's timestamp.
    assert recording.duration_s == pytest.approx(ts[2])
    # recorded_at should be a non-empty ISO string.
    assert isinstance(recording.recorded_at, str) and recording.recorded_at


def test_save_load_roundtrip(tmp_path):
    """save() → load() reproduces frames, vectors (as tuples), and metadata."""
    original = _make_recording([
        (0.0, (1.0, 2.0, 3.0)),
        (0.5, (-1.0, 0.0, 0.5)),
        (1.0, (0.0, 0.0, 0.0)),
    ], name="roundtrip")

    rec = InputRecorder()
    path = tmp_path / "rec.json"
    rec.save(original, str(path))
    assert path.exists()

    loaded = rec.load(str(path))

    assert loaded.name == "roundtrip"
    assert loaded.duration_s == pytest.approx(1.0)
    assert len(loaded.frames) == 3
    for orig, got in zip(original.frames, loaded.frames):
        assert got.timestamp_s == pytest.approx(orig.timestamp_s)
        assert got.node_path == orig.node_path
        # Crucially, input_vector must round-trip as a tuple, not a list.
        assert isinstance(got.input_vector, tuple)
        assert got.input_vector == orig.input_vector
        assert got.metadata == orig.metadata


def test_play_calls_set_input_vector():
    """play() invokes set_input_vector once per frame with the recorded vector."""
    recording = _make_recording([
        (0.0, (1.0, 0.0, 0.0)),
        (0.01, (0.0, 1.0, 0.0)),
        (0.02, (0.0, 0.0, 1.0)),
    ])

    mock_controller = MagicMock()
    replayer = InputReplayer(mock_controller)

    replayer.play(recording, speed=1.0)

    assert mock_controller.set_input_vector.call_count == 3
    actual_vectors = [
        call.args[0] for call in mock_controller.set_input_vector.call_args_list
    ]
    assert actual_vectors == [
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    ]


def test_play_speed_2x():
    """1s of recording at 2x speed replays in ~0.5s of wall-clock time."""
    recording = _make_recording([
        (0.0, (1.0, 0.0, 0.0)),
        (1.0, (0.0, 1.0, 0.0)),
    ])

    mock_controller = MagicMock()
    replayer = InputReplayer(mock_controller)

    start = time.perf_counter()
    replayer.play(recording, speed=2.0)
    elapsed = time.perf_counter() - start

    # Expect ~0.5s; allow slack for scheduler jitter on CI.
    assert 0.35 <= elapsed <= 0.85, f"elapsed={elapsed:.3f}s outside 0.5s ± 0.15s"
    assert mock_controller.set_input_vector.call_count == 2


def test_play_speed_0_5x():
    """1s of recording at 0.5x speed replays in ~2s of wall-clock time."""
    recording = _make_recording([
        (0.0, (1.0, 0.0, 0.0)),
        (1.0, (0.0, 1.0, 0.0)),
    ])

    mock_controller = MagicMock()
    replayer = InputReplayer(mock_controller)

    start = time.perf_counter()
    replayer.play(recording, speed=0.5)
    elapsed = time.perf_counter() - start

    # Expect ~2.0s; allow generous slack for CI.
    assert 1.75 <= elapsed <= 2.4, f"elapsed={elapsed:.3f}s outside 2.0s ± 0.25s"
    assert mock_controller.set_input_vector.call_count == 2


def test_play_async_returns_thread():
    """play_async() returns a Thread; joining yields a completed replay."""
    recording = _make_recording([
        (0.0, (1.0, 0.0, 0.0)),
        (0.02, (0.0, 1.0, 0.0)),
        (0.04, (0.0, 0.0, 1.0)),
    ])

    mock_controller = MagicMock()
    replayer = InputReplayer(mock_controller)

    completed = threading.Event()

    thread = replayer.play_async(recording, speed=1.0, on_complete=completed.set)

    assert isinstance(thread, threading.Thread)
    thread.join(timeout=2.0)
    assert not thread.is_alive(), "replay thread did not finish within 2s"
    assert completed.is_set(), "on_complete was not invoked"
    assert mock_controller.set_input_vector.call_count == 3


def test_stop_interrupts_replay():
    """stop() aborts an async replay well within 0.5s."""
    # A 10s recording: frame 2 fires at t=10s, so without stop() this would
    # block for ~10s. With stop() the worker must exit promptly.
    recording = _make_recording([
        (0.0, (1.0, 0.0, 0.0)),
        (10.0, (0.0, 1.0, 0.0)),
    ])

    mock_controller = MagicMock()
    replayer = InputReplayer(mock_controller)

    thread = replayer.play_async(recording, speed=1.0)
    # Give the worker a moment to enter the interruptible wait for frame 2.
    time.sleep(0.05)

    stop_start = time.perf_counter()
    replayer.stop()
    thread.join(timeout=0.5)
    stop_elapsed = time.perf_counter() - stop_start

    assert not thread.is_alive(), "replay thread did not exit within 0.5s of stop()"
    assert stop_elapsed < 0.5, f"stop+join took {stop_elapsed:.3f}s, expected < 0.5s"
    # Frame 1 fires immediately (t=0); frame 2 must NOT have fired.
    assert mock_controller.set_input_vector.call_count == 1
