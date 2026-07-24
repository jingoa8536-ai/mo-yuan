"""Unit tests for :mod:`godot_headless_runner` (LAAP Task 6).

These tests are 0-token by construction: they mock :class:`subprocess.Popen`
so no real ``godot`` binary is ever spawned. They cover:

- ``test_error_parsing`` - stdout containing ``ERROR:`` and ``SCRIPT ERROR:``
  is parsed into ``result.errors``.
- ``test_warning_parsing`` - stdout containing ``WARNING:`` is parsed into
  ``result.warnings``.
- ``test_timeout_raises`` - a non-terminating mock process triggers
  :class:`HeadlessRunTimeoutError` and the process tree is killed.
- ``test_success_flag`` - ``returncode`` and ``errors`` flip the
  ``success`` flag.
- ``test_arg_templating`` - user ``args`` are appended verbatim after the
  script path in the constructed argv.
- Plus additional coverage for parse-error/compile-error patterns, the
  ``run_scene`` / ``export_project`` / ``validate_scene`` argv shapes, and
  the ``--path`` injection.
"""
from __future__ import annotations

import subprocess
import sys
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Make ``from godot_headless_runner import ...`` work regardless of the
# caller's working directory.
sys.path.insert(0, r"D:\LAAP\harness\godot_bridge\python")

from godot_headless_runner import (  # noqa: E402  (path insert above)
    GodotHeadlessRunner,
    HeadlessRunResult,
    HeadlessRunTimeoutError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
class _FakeProc:
    """Minimal stand-in for :class:`subprocess.Popen` used in tests.

    It records the argv it was constructed with and serves a fixed
    (stdout, stderr, returncode) triple via :meth:`communicate`. Tests can
    swap :meth:`communicate` for a side_effect to simulate a hang.
    """

    def __init__(
        self,
        argv: list[str],
        *,
        stdout: bytes = b"",
        stderr: bytes = b"",
        returncode: int = 0,
        **_kwargs: Any,
    ) -> None:
        self.argv = list(argv)
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        self.pid = 12345
        self.killed = False
        self.waited = False

    def communicate(self, timeout: float | None = None):  # noqa: D401
        return self._stdout, self._stderr

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: float | None = None) -> int:
        self.waited = True
        return self.returncode


def _make_popen_mock(
    stdout: bytes = b"",
    stderr: bytes = b"",
    returncode: int = 0,
    communicate_side_effect: Any = None,
) -> tuple[MagicMock, list[list[str]]]:
    """Return a ``(popen_patch, captured_argv)`` pair.

    ``popen_patch`` is configured to invoke ``_FakeProc`` for every call
    and to record the argv of the most recent invocation in
    ``captured_argv``. ``communicate_side_effect`` overrides the default
    ``communicate`` behaviour to simulate hangs/timeouts.
    """
    captured: list[list[str]] = []

    def _factory(argv: list[str], **kwargs: Any) -> _FakeProc:
        captured.append(list(argv))
        proc = _FakeProc(argv, stdout=stdout, stderr=stderr, returncode=returncode)
        if communicate_side_effect is not None:
            proc.communicate = communicate_side_effect  # type: ignore[assignment]
        return proc

    mock = MagicMock(side_effect=_factory)
    return mock, captured


# ---------------------------------------------------------------------------
# Error / warning parsing
# ---------------------------------------------------------------------------
def test_error_parsing() -> None:
    """ERROR: and SCRIPT ERROR: lines must land in ``result.errors``."""
    fake_stdout = (
        b"Godot Engine v4.0\n"
        b"ERROR: Some error\n"
        b"SCRIPT ERROR: Some script error\n"
        b"some normal log line\n"
    )
    popen_mock, _ = _make_popen_mock(stdout=fake_stdout, returncode=0)
    runner = GodotHeadlessRunner(godot_bin="godot", default_project=".")

    with patch("subprocess.Popen", popen_mock):
        result = runner.run_script("res://run.gd", timeout=5.0)

    assert "ERROR: Some error" in result.errors
    assert "SCRIPT ERROR: Some script error" in result.errors
    assert len(result.errors) == 2
    # No warnings expected from this stream.
    assert result.warnings == []
    # Errors flip success off even with returncode 0.
    assert result.success is False


def test_warning_parsing() -> None:
    """WARNING: lines must land in ``result.warnings`` and not flip success."""
    fake_stdout = (
        b"WARNING: deprecation notice\n"
        b"normal line\n"
    )
    popen_mock, _ = _make_popen_mock(stdout=fake_stdout, returncode=0)
    runner = GodotHeadlessRunner()

    with patch("subprocess.Popen", popen_mock):
        result = runner.run_script("res://run.gd")

    assert result.warnings == ["WARNING: deprecation notice"]
    # Pure warnings do not break success.
    assert result.success is True
    assert result.errors == []


def test_parse_and_compile_error_patterns() -> None:
    """``Parse Error:`` and ``Cannot compile`` are also errors."""
    fake_stdout = (
        b"Parse Error: unexpected token\n"
        b"Cannot compile expression foo\n"
    )
    popen_mock, _ = _make_popen_mock(stdout=fake_stdout, returncode=1)
    runner = GodotHeadlessRunner()

    with patch("subprocess.Popen", popen_mock):
        result = runner.run_script("res://run.gd")

    assert any("Parse Error:" in e for e in result.errors)
    assert any("Cannot compile" in e for e in result.errors)
    assert result.success is False


def test_stderr_is_also_parsed() -> None:
    """Error lines on stderr (where Godot usually writes them) are caught."""
    popen_mock, _ = _make_popen_mock(stdout=b"ok\n", stderr=b"ERROR: boom\n")
    runner = GodotHeadlessRunner()

    with patch("subprocess.Popen", popen_mock):
        result = runner.run_script("res://run.gd")

    assert "ERROR: boom" in result.errors


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------
def test_timeout_raises() -> None:
    """A process that never terminates must trigger HeadlessRunTimeoutError."""
    def _hang(timeout: float | None = None):
        raise subprocess.TimeoutExpired(cmd=["godot"], timeout=timeout or 0.0)

    popen_mock, _ = _make_popen_mock(
        stdout=b"",
        stderr=b"",
        returncode=0,
        communicate_side_effect=_hang,
    )
    runner = GodotHeadlessRunner()
    # Patch the tree-killer so the test does not actually try to kill pid=12345.
    with patch("subprocess.Popen", popen_mock), \
         patch.object(GodotHeadlessRunner, "_kill_process_tree") as kill_mock:
        with pytest.raises(HeadlessRunTimeoutError):
            runner.run_script("res://run.gd", timeout=0.1)
    # The tree killer must have been invoked exactly once.
    kill_mock.assert_called_once()


def test_timeout_kills_process_tree() -> None:
    """On timeout the runner must call ``_kill_process_tree`` with the proc."""
    call_log: list[Any] = []
    hang_proc = _FakeProc(["godot"], returncode=0)
    hang_proc.communicate = lambda timeout=None: (_ for _ in ()).throw(
        subprocess.TimeoutExpired(cmd=["godot"], timeout=timeout or 0.0)
    )
    # Second communicate call (after kill) should return empty bytes.
    real_communicate = hang_proc.communicate

    def _communicate_after_kill(timeout: float | None = None):
        # The first call raises; subsequent calls (after _kill_process_tree)
        # return empty bytes so the runner can finish building its exception.
        if not hang_proc.killed:
            return real_communicate(timeout=timeout)
        return b"", b""

    hang_proc.communicate = _communicate_after_kill  # type: ignore[assignment]

    def _popen(argv, **kwargs):
        call_log.append(list(argv))
        return hang_proc

    runner = GodotHeadlessRunner()
    with patch("subprocess.Popen", side_effect=_popen), \
         patch.object(GodotHeadlessRunner, "_kill_process_tree") as kill_mock:
        with pytest.raises(HeadlessRunTimeoutError):
            runner.run_script("res://run.gd", timeout=0.05)
    # ``_kill_process_tree`` was invoked with the proc returned by Popen.
    kill_mock.assert_called_once()
    killed_proc = kill_mock.call_args.args[0]
    assert killed_proc is hang_proc


# ---------------------------------------------------------------------------
# success flag
# ---------------------------------------------------------------------------
def test_success_flag_zero_returncode_no_errors() -> None:
    popen_mock, _ = _make_popen_mock(stdout=b"ok\n", returncode=0)
    runner = GodotHeadlessRunner()
    with patch("subprocess.Popen", popen_mock):
        result = runner.run_script("res://run.gd")
    assert result.returncode == 0
    assert result.errors == []
    assert result.success is True


def test_success_flag_nonzero_returncode() -> None:
    popen_mock, _ = _make_popen_mock(stdout=b"ok\n", returncode=1)
    runner = GodotHeadlessRunner()
    with patch("subprocess.Popen", popen_mock):
        result = runner.run_script("res://run.gd")
    assert result.returncode == 1
    assert result.success is False


# ---------------------------------------------------------------------------
# Argument templating
# ---------------------------------------------------------------------------
def test_arg_templating() -> None:
    """User ``args`` must be appended verbatim after the script path."""
    popen_mock, captured = _make_popen_mock(stdout=b"", returncode=0)
    runner = GodotHeadlessRunner(godot_bin="/usr/bin/godot", default_project="/game")

    user_args = ["--track=laguna-seca", "--car=porsche-911"]
    with patch("subprocess.Popen", popen_mock):
        runner.run_script("res://run_tests.gd", args=user_args, timeout=5.0)

    assert len(captured) == 1
    argv = captured[0]
    # Binary + headless flag first.
    assert argv[0] == "/usr/bin/godot"
    assert "--headless" in argv
    # Project path injected.
    assert "--path" in argv
    path_idx = argv.index("--path")
    assert argv[path_idx + 1] == "/game"
    # Editor + script + quit pattern.
    assert "--editor" in argv
    script_idx = argv.index("--script")
    assert argv[script_idx + 1] == "res://run_tests.gd"
    assert "--quit" in argv
    # User args appear after the script path.
    assert argv[script_idx + 2] == "--quit"
    # The last two elements are the user args (in order).
    assert argv[-2] == "--track=laguna-seca"
    assert argv[-1] == "--car=porsche-911"


def test_project_path_override() -> None:
    """An explicit ``project_path`` overrides ``default_project``."""
    popen_mock, captured = _make_popen_mock(stdout=b"", returncode=0)
    runner = GodotHeadlessRunner(default_project="/default")
    with patch("subprocess.Popen", popen_mock):
        runner.run_script("res://run.gd", project_path="/override")
    argv = captured[0]
    assert "--path" in argv
    assert argv[argv.index("--path") + 1] == "/override"


def test_run_scene_argv() -> None:
    """``run_scene`` must NOT add ``--editor`` and must include the scene."""
    popen_mock, captured = _make_popen_mock(stdout=b"", returncode=0)
    runner = GodotHeadlessRunner(default_project="/game")
    with patch("subprocess.Popen", popen_mock):
        runner.run_scene("res://track.tscn", args=["--speed=1.0"])
    argv = captured[0]
    assert "--headless" in argv
    assert "--editor" not in argv
    assert "res://track.tscn" in argv
    assert "--quit" in argv
    assert argv[-1] == "--speed=1.0"


def test_export_project_argv() -> None:
    popen_mock, captured = _make_popen_mock(stdout=b"", returncode=0)
    runner = GodotHeadlessRunner(default_project="/game")
    with patch("subprocess.Popen", popen_mock):
        runner.export_project("Windows Desktop", "build/game.exe", timeout=10.0)
    argv = captured[0]
    assert "--export-release" in argv
    export_idx = argv.index("--export-release")
    assert argv[export_idx + 1] == "Windows Desktop"
    assert argv[export_idx + 2] == "build/game.exe"
    assert "--editor" in argv


def test_validate_scene_argv() -> None:
    popen_mock, captured = _make_popen_mock(stdout=b"", returncode=0)
    runner = GodotHeadlessRunner(default_project="/game")
    with patch("subprocess.Popen", popen_mock):
        runner.validate_scene("res://x.tscn")
    argv = captured[0]
    assert "--editor" in argv
    assert "--import" in argv


# ---------------------------------------------------------------------------
# Result dataclass sanity
# ---------------------------------------------------------------------------
def test_headless_run_result_post_init_success() -> None:
    """``success`` is derived from ``returncode`` and ``errors``."""
    ok = HeadlessRunResult(
        returncode=0, stdout="", stderr="", duration_s=0.1, errors=[], warnings=[]
    )
    assert ok.success is True

    err = HeadlessRunResult(
        returncode=0,
        stdout="",
        stderr="",
        duration_s=0.1,
        errors=["ERROR: x"],
        warnings=[],
    )
    assert err.success is False

    rc = HeadlessRunResult(
        returncode=2, stdout="", stderr="", duration_s=0.1, errors=[], warnings=[]
    )
    assert rc.success is False

    # Warnings alone do not flip success.
    warn = HeadlessRunResult(
        returncode=0,
        stdout="",
        stderr="",
        duration_s=0.1,
        errors=[],
        warnings=["WARNING: x"],
    )
    assert warn.success is True
