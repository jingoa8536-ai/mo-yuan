"""Headless Godot runner for the LAAP 0-Token Game Dev Framework (Task 6).

This module wraps the ``godot --headless --editor --script`` CLI invocation
used by the LAAP harness to drive Godot in a fully automated, GUI-less way.
It is intentionally token-free: every code path runs locally against the
Godot binary and consumes no LLM tokens.

Responsibilities (mapped to Task 6 sub-tasks):

1. **Wrap CLI invocation** - :meth:`GodotHeadlessRunner._build_argv` and
   :meth:`GodotHeadlessRunner._spawn` assemble the ``godot`` argument list
   (``--headless``, ``--editor``, ``--script res://path.gd``, ``--quit``)
   and launch the process via :class:`subprocess.Popen`.

2. **Parameter templating** - :meth:`GodotHeadlessRunner.run_script` accepts
   ``args`` such as ``["--track=laguna-seca", "--car=porsche-911"]`` which
   are appended after the script path so the GDScript can read them via
   ``OS.get_cmdline_args()``.

3. **Capture stdout/stderr and parse error logs** -
   :class:`HeadlessRunResult` carries the raw streams plus ``errors`` and
   ``warnings`` lists populated by :meth:`_parse_logs`, which recognises the
   ``ERROR:``, ``WARNING:``, ``SCRIPT ERROR:``, ``Parse Error:`` and
   ``Cannot compile`` prefixes emitted by the Godot logger.

4. **Timeout control and process cleanup** - :meth:`run_script` and friends
   use :meth:`subprocess.Popen.communicate` with a ``timeout`` argument. On
   :class:`subprocess.TimeoutExpired` the runner kills the whole process
   tree (children first via :mod:`psutil` when available, falling back to
   :func:`os.kill` on POSIX / ``taskkill`` on Windows) and raises
   :class:`HeadlessRunTimeoutError`.

The module never imports a Godot binary at import time and is safe to unit
test by mocking :class:`subprocess.Popen`.
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

# ``psutil`` is an optional dependency - it is used to robustly kill child
# processes on timeout. When it is not available we fall back to a best
# effort ``os.kill`` / ``taskkill`` based cleanup so the module remains
# importable in minimal environments (e.g. CI images without psutil).
try:  # pragma: no cover - exercised only when psutil is installed
    import psutil  # type: ignore[import-untyped]
    _HAS_PSUTIL = True
except Exception:  # pragma: no cover - exercised when psutil is missing
    psutil = None  # type: ignore[assignment]
    _HAS_PSUTIL = False


# ---------------------------------------------------------------------------
# Regex patterns for log parsing.
#
# Godot's logger emits lines that begin with a severity tag followed by a
# colon. The patterns below are anchored at the start of a line and tolerate
# leading whitespace. They are compiled once at import time for speed.
# ---------------------------------------------------------------------------
_ERROR_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*ERROR:", re.IGNORECASE),
    re.compile(r"^\s*SCRIPT ERROR:", re.IGNORECASE),
    re.compile(r"^\s*Parse Error:", re.IGNORECASE),
    re.compile(r"^\s*Cannot compile", re.IGNORECASE),
)

_WARNING_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*WARNING:", re.IGNORECASE),
)


# ---------------------------------------------------------------------------
# Public exceptions
# ---------------------------------------------------------------------------
class HeadlessRunError(RuntimeError):
    """Base class for :class:`GodotHeadlessRunner` errors."""


class HeadlessRunTimeoutError(HeadlessRunError):
    """Raised when a headless Godot run exceeds its timeout budget.

    The wrapped :class:`subprocess.Popen` instance has already been killed
    (process tree terminated) before this exception is raised, so callers
    can simply catch the exception and move on without leaking processes.
    """


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class HeadlessRunResult:
    """Structured outcome of a single headless Godot invocation.

    Attributes
    ----------
    returncode:
        Exit code of the Godot process. ``-1`` indicates the process was
        killed before producing an exit code (e.g. timeout).
    stdout:
        Decoded stdout stream (may be empty).
    stderr:
        Decoded stderr stream (may be empty).
    duration_s:
        Wall-clock duration of the run in seconds (from spawn to
        ``communicate`` returning).
    errors:
        List of Godot error lines parsed from stdout+stderr. Includes
        ``ERROR:``, ``SCRIPT ERROR:``, ``Parse Error:`` and ``Cannot
        compile`` matches.
    warnings:
        List of Godot warning lines parsed from stdout+stderr (``WARNING:``
        matches).
    success:
        Convenience flag: ``True`` only when ``returncode == 0`` and no
        errors were parsed.
    """

    returncode: int
    stdout: str
    stderr: str
    duration_s: float
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    success: bool = False

    def __post_init__(self) -> None:
        # Derive ``success`` from the other fields so callers cannot forget
        # to set it. ``returncode == 0`` and an empty ``errors`` list are
        # required; warnings do not affect success.
        self.success = bool(self.returncode == 0 and not self.errors)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
class GodotHeadlessRunner:
    """Drive the Godot engine in headless mode via its CLI.

    The runner is configured with the path to the Godot binary and an
    optional default project directory. Each :meth:`run_script`,
    :meth:`run_scene`, :meth:`export_project` or :meth:`validate_scene`
    call spawns a fresh Godot process, captures its output, parses Godot's
    log lines into structured errors/warnings and returns a
    :class:`HeadlessRunResult`.

    Parameters
    ----------
    godot_bin:
        Path or name of the Godot executable. Defaults to ``"godot"`` which
        relies on ``PATH`` resolution. Pass an absolute path for hermetic
        setups (e.g. CI).
    default_project:
        Path to the project directory used when no ``project_path`` is
        passed to a run method. The directory should contain a
        ``project.godot`` file at runtime, but the constructor does not
        verify this so tests can point at non-existent paths.

    Examples
    --------
    >>> runner = GodotHeadlessRunner(godot_bin="godot",
    ...                              default_project="D:/game")
    >>> # The following would launch godot in a real environment:
    >>> # result = runner.run_script("res://run_tests.gd", timeout=30.0)
    """

    def __init__(self, godot_bin: str = "godot", default_project: str = ".") -> None:
        self.godot_bin = godot_bin
        self.default_project = default_project

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run_script(
        self,
        script_path: str,
        args: list[str] | None = None,
        timeout: float = 60.0,
        project_path: str | None = None,
    ) -> HeadlessRunResult:
        """Run a GDScript file under ``godot --headless --editor --script``.

        The constructed command line is::

            godot --headless --editor --path <project> --script <script> \
                [--quit] [user args...]

        ``--quit`` is appended so the engine exits as soon as the script
        returns. The ``args`` list is appended verbatim after the script
        path and is intended for parameter templating
        (``--track=laguna-seca``, ``--car=porsche-911`` ...). The GDScript
        can read them via ``OS.get_cmdline_args()``.

        Parameters
        ----------
        script_path:
            ``res://`` path or filesystem path to the ``.gd`` file.
        args:
            Optional list of extra CLI arguments forwarded to Godot. Used
            for parameter templating.
        timeout:
            Maximum wall-clock seconds before the process is killed and
            :class:`HeadlessRunTimeoutError` is raised.
        project_path:
            Override for the project directory. Falls back to
            :attr:`default_project`.

        Returns
        -------
        HeadlessRunResult
            Parsed result of the run.

        Raises
        ------
        HeadlessRunTimeoutError
            If the run exceeds ``timeout``.
        """
        argv = self._build_argv(
            script_path=script_path,
            args=args,
            project_path=project_path,
            mode="script",
        )
        return self._run(argv, timeout=timeout)

    def run_scene(
        self,
        scene_path: str,
        args: list[str] | None = None,
        timeout: float = 60.0,
    ) -> HeadlessRunResult:
        """Run a scene headlessly (``godot --headless <scene>``).

        Unlike :meth:`run_script` this does not enter editor mode; it just
        launches the project with the given scene as the main scene. Useful
        for smoke-testing assembled scenes.

        Parameters
        ----------
        scene_path:
            ``res://`` path or filesystem path to the ``.tscn``/``.scn``
            file.
        args:
            Optional extra CLI arguments forwarded to Godot.
        timeout:
            Maximum wall-clock seconds before the process is killed.

        Returns
        -------
        HeadlessRunResult
            Parsed result of the run.
        """
        argv = self._build_argv(
            scene_path=scene_path,
            args=args,
            mode="scene",
        )
        return self._run(argv, timeout=timeout)

    def export_project(
        self,
        export_preset: str,
        output_path: str,
        timeout: float = 300.0,
    ) -> HeadlessRunResult:
        """Export the project using ``godot --headless --export-release``.

        Parameters
        ----------
        export_preset:
            Name of the preset defined in ``export_presets.cfg``.
        output_path:
            Filesystem path where the exported artifact will be written.
        timeout:
            Maximum wall-clock seconds. Defaults to 300s because exports
            can take much longer than script runs.

        Returns
        -------
        HeadlessRunResult
            Parsed result of the export run.
        """
        argv = self._build_argv(
            mode="export",
            export_preset=export_preset,
            output_path=output_path,
        )
        return self._run(argv, timeout=timeout)

    def validate_scene(
        self,
        scene_path: str,
        timeout: float = 30.0,
    ) -> HeadlessRunResult:
        """Validate a scene by importing it headlessly (``--import``).

        Uses ``godot --headless --editor --import`` which loads the project,
        imports resources and quits. Any error during import will surface
        in :attr:`HeadlessRunResult.errors`.

        Parameters
        ----------
        scene_path:
            Path of the scene to validate (currently informational - Godot
            imports the whole project). Kept for API symmetry with
            :meth:`run_scene`.
        timeout:
            Maximum wall-clock seconds.

        Returns
        -------
        HeadlessRunResult
            Parsed result of the validation run.
        """
        argv = self._build_argv(
            mode="validate",
            scene_path=scene_path,
        )
        return self._run(argv, timeout=timeout)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _build_argv(
        self,
        *,
        script_path: str | None = None,
        scene_path: str | None = None,
        args: list[str] | None = None,
        project_path: str | None = None,
        mode: str = "script",
        export_preset: str | None = None,
        output_path: str | None = None,
    ) -> list[str]:
        """Assemble the ``godot`` CLI argument vector.

        The order is intentionally compatible with Godot 4.x argument
        parsing: global flags first (``--headless``), then ``--path``,
        then the mode-specific flags (``--editor --script`` /
        ``--export-release`` / ``--import``), then ``--quit`` and finally
        user-supplied ``args``.

        Parameters
        ----------
        script_path:
            ``res://`` path for ``mode="script"``.
        scene_path:
            Scene path for ``mode="scene"`` or ``mode="validate"``.
        args:
            Extra user arguments appended verbatim.
        project_path:
            Project directory; falls back to :attr:`default_project`.
        mode:
            One of ``"script"``, ``"scene"``, ``"export"``, ``"validate"``.
        export_preset:
            Preset name for ``mode="export"``.
        output_path:
            Output artifact path for ``mode="export"``.

        Returns
        -------
        list[str]
            Argument vector ready for :class:`subprocess.Popen`.
        """
        argv: list[str] = [self.godot_bin, "--headless"]

        # Project path: prefer explicit override, then default. We always
        # pass ``--path`` so the runner works regardless of the current
        # working directory.
        effective_project = project_path or self.default_project
        if effective_project:
            argv += ["--path", str(effective_project)]

        if mode == "script":
            if not script_path:
                raise ValueError("script_path is required for mode='script'")
            # ``--editor`` is required for ``--script`` to be honoured.
            argv += ["--editor", "--script", script_path, "--quit"]
        elif mode == "scene":
            if not scene_path:
                raise ValueError("scene_path is required for mode='scene'")
            # Just run the scene as the main scene. ``--quit`` ensures we
            # exit after the first iteration instead of looping forever.
            argv += [scene_path, "--quit"]
        elif mode == "export":
            if not export_preset or not output_path:
                raise ValueError(
                    "export_preset and output_path are required for mode='export'"
                )
            argv += ["--editor", "--export-release", export_preset, output_path]
        elif mode == "validate":
            # ``--import`` opens the editor in import-only mode and exits.
            argv += ["--editor", "--import"]
        else:
            raise ValueError(f"Unknown mode: {mode!r}")

        if args:
            argv += list(args)

        return argv

    def _run(self, argv: list[str], *, timeout: float) -> HeadlessRunResult:
        """Spawn ``argv`` and wait up to ``timeout`` seconds for completion.

        On timeout the entire process tree is killed (see
        :meth:`_kill_process_tree`) and :class:`HeadlessRunTimeoutError` is
        raised. Otherwise the captured stdout/stderr are decoded and parsed
        into a :class:`HeadlessRunResult`.
        """
        start = time.monotonic()
        proc = self._spawn(argv)
        try:
            stdout_b, stderr_b = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            # Kill the whole tree before raising so we do not leak godot
            # child processes (e.g. the actual engine spawned by a wrapper).
            self._kill_process_tree(proc)
            # Drain any partial output so callers can inspect it via the
            # exception if they wish.
            try:
                stdout_b, stderr_b = proc.communicate(timeout=5.0)
            except Exception:
                stdout_b, stderr_b = b"", b""
            elapsed = time.monotonic() - start
            raise HeadlessRunTimeoutError(
                f"godot headless run timed out after {timeout:.1f}s "
                f"(argv={argv!r}, elapsed={elapsed:.2f}s)"
            ) from None

        elapsed = time.monotonic() - start
        stdout = self._decode(stdout_b)
        stderr = self._decode(stderr_b)
        errors, warnings = self._parse_logs(stdout, stderr)
        return HeadlessRunResult(
            returncode=proc.returncode if proc.returncode is not None else -1,
            stdout=stdout,
            stderr=stderr,
            duration_s=elapsed,
            errors=errors,
            warnings=warnings,
        )

    def _spawn(self, argv: list[str]) -> subprocess.Popen[bytes]:
        """Spawn a :class:`subprocess.Popen` for ``argv``.

        Factored into its own method so tests can patch
        ``subprocess.Popen`` once and exercise every public method without
        duplicating the Popen kwargs.
        """
        # ``creationflags=CREATE_NEW_PROCESS_GROUP`` on Windows lets us
        # kill the whole tree deterministically; on POSIX we rely on the
        # process group set via ``start_new_session=True``.
        popen_kwargs: dict[str, Any] = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "stdin": subprocess.DEVNULL,
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True

        return subprocess.Popen(argv, **popen_kwargs)

    @staticmethod
    def _decode(stream: bytes | str | None) -> str:
        """Best-effort decode of a subprocess output stream to ``str``."""
        if stream is None:
            return ""
        if isinstance(stream, str):
            return stream
        # Godot prints UTF-8 on all platforms; fall back to the locale
        # preferred encoding (``os.device_encoding(1)`` may be ``None`` so
        # ``errors="replace"`` keeps the output printable).
        try:
            return stream.decode("utf-8")
        except UnicodeDecodeError:
            return stream.decode(errors="replace")

    @staticmethod
    def _parse_logs(stdout: str, stderr: str) -> tuple[list[str], list[str]]:
        """Split ``stdout``+``stderr`` into ``errors`` and ``warnings``.

        Each line is classified independently; lines that match no pattern
        are dropped (they remain available on the raw ``stdout``/``stderr``
        of the :class:`HeadlessRunResult`).
        """
        errors: list[str] = []
        warnings: list[str] = []
        # Combine both streams in order: stderr first (Godot writes most
        # diagnostics there) then stdout. Tests that feed only stdout are
        # also handled correctly because the loops are independent.
        for line in stderr.splitlines():
            cls = _classify_line(line)
            if cls == "error":
                errors.append(line.strip())
            elif cls == "warning":
                warnings.append(line.strip())
        for line in stdout.splitlines():
            cls = _classify_line(line)
            if cls == "error":
                errors.append(line.strip())
            elif cls == "warning":
                warnings.append(line.strip())
        return errors, warnings

    @staticmethod
    def _kill_process_tree(proc: subprocess.Popen[bytes]) -> None:
        """Kill ``proc`` and all its descendants.

        Uses :mod:`psutil` when available for a robust cross-platform
        tree kill. Falls back to ``os.killpg`` on POSIX and
        ``taskkill /T /F`` on Windows when ``psutil`` is missing.

        Swallows all exceptions: this is best-effort cleanup invoked from
        the timeout path, and we never want to mask the original
        :class:`HeadlessRunTimeoutError` with a secondary failure.
        """
        if _HAS_PSUTIL and psutil is not None:
            try:
                parent = psutil.Process(proc.pid)
                children = parent.children(recursive=True)
                for child in children:
                    try:
                        child.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                parent.kill()
                # Reap zombies so we do not accumulate defunct processes.
                proc.wait(timeout=5.0)
                return
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return
            except Exception:
                # Fall through to the psutil-less path as a last resort.
                pass

        # POSIX path: kill the whole process group we started.
        if os.name != "nt":
            try:
                os.killpg(os.getpgid(proc.pid), 9)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                proc.wait(timeout=5.0)
            except Exception:
                pass
            return

        # Windows path without psutil: shell out to ``taskkill`` which
        # supports recursive tree kill via the ``/T`` flag.
        try:
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                capture_output=True,
                check=False,
            )
        except Exception:
            pass
        try:
            proc.wait(timeout=5.0)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _classify_line(line: str) -> str | None:
    """Return ``"error"``, ``"warning"`` or ``None`` for a single log line."""
    for pat in _ERROR_PATTERNS:
        if pat.match(line):
            return "error"
    for pat in _WARNING_PATTERNS:
        if pat.match(line):
            return "warning"
    return None


__all__ = [
    "GodotHeadlessRunner",
    "HeadlessRunResult",
    "HeadlessRunError",
    "HeadlessRunTimeoutError",
]
