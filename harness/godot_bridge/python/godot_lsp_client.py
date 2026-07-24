"""Godot LSP client.

Implements a Language Server Protocol (LSP) client for Godot's GDScript
language server (see ``harness/godot-master/modules/gdscript/language_server``).

The client launches a Godot process which runs an LSP server and pipes
JSON-RPC 2.0 messages over the process's stdin/stdout using the standard
``Content-Length: N\\r\\n\\r\\n{json}`` framing defined by the LSP
specification (https://microsoft.github.io/language-server-protocol/).

The implementation relies on the :mod:`pylsp_jsonrpc` library for framing
helpers when available, but also ships its own pure-Python
:func:`encode_lsp_message` / :func:`decode_lsp_messages` helpers so the
message-framing logic can be unit-tested without launching Godot.

Public API
----------
.. autoclass:: GodotLSPClient
   :members:

Module functions
----------------
:func:`encode_lsp_message` -- serialise a dict as an LSP wire message.
:func:`decode_lsp_messages` -- parse one or more LSP messages from a buffer.
:func:`file_path_to_uri` / :func:`uri_to_file_path` -- URI <-> path helpers.
:func:`apply_text_edits` -- apply LSP ``TextEdit`` ranges to a string.
"""
from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import threading
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlparse
from urllib.request import url2pathname

# ``pylsp_jsonrpc`` is the canonical JSON-RPC framing library used by the
# Python LSP ecosystem.  We import it eagerly so that ``importorskip`` in
# the test-suite can skip tests when the dependency is missing, but every
# public helper below works even if the import fails (we fall back to the
# pure-Python framing implemented in this module).
try:  # pragma: no cover - exercised indirectly via tests
    import pylsp_jsonrpc  # noqa: F401  (used for availability check)
    from pylsp_jsonrpc.streams import JsonRpcStreamReader, JsonRpcStreamWriter

    _HAS_PYLSP_JSONRPC = True
except Exception:  # pragma: no cover - import guard
    pylsp_jsonrpc = None  # type: ignore[assignment]
    JsonRpcStreamReader = None  # type: ignore[assignment]
    JsonRpcStreamWriter = None  # type: ignore[assignment]
    _HAS_PYLSP_JSONRPC = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: JSON-RPC protocol version wire constant.
JSONRPC_VERSION = "2.0"

#: Default Godot binary name/path used when no override is supplied.
DEFAULT_GODOT_BIN = "godot"

#: Default Godot LSP port (informational only -- this client speaks stdio).
#: Godot's ``GDScriptLanguageProtocol`` listens on TCP port 6005 by default;
#: the launch script (``res://launch_lsp.gd``) is expected to bridge TCP to
#: stdio so that this client can speak LSP over the subprocess pipes.
DEFAULT_LSP_PORT = 6005

#: Default timeout (seconds) for synchronous LSP requests.
DEFAULT_REQUEST_TIMEOUT = 30.0

#: Default timeout (seconds) to wait for a ``publishDiagnostics`` notification
#: after sending a ``textDocument/didChange`` notification.
DEFAULT_DIAGNOSTICS_TIMEOUT = 5.0

#: Language identifier used for GDScript files (see ``TextDocumentItem``).
GDSCRIPT_LANGUAGE_ID = "gdscript"

#: LSP ``DiagnosticSeverity`` enum values (see ``godot_lsp.h``).
DIAGNOSTIC_SEVERITY_ERROR = 1
DIAGNOSTIC_SEVERITY_WARNING = 2
DIAGNOSTIC_SEVERITY_INFORMATION = 3
DIAGNOSTIC_SEVERITY_HINT = 4

#: LSP ``CompletionTriggerKind`` enum values.
COMPLETION_TRIGGER_INVOKED = 1
COMPLETION_TRIGGER_CHARACTER = 2
COMPLETION_TRIGGER_INCOMPLETE = 3


# ---------------------------------------------------------------------------
# Pure framing helpers (unit-testable, no Godot required)
# ---------------------------------------------------------------------------


def encode_lsp_message(message: dict) -> bytes:
    """Serialise ``message`` as an LSP wire frame.

    The frame uses the standard LSP header format::

        Content-Length: <n>\r\n
        Content-Type: application/vscode-jsonrpc; charset=utf8\r\n
        \r\n
        <json body>

    Args:
        message: A JSON-RPC message dict (must be JSON-serialisable).

    Returns:
        The framed message as ``bytes`` (UTF-8 encoded body).
    """
    body = json.dumps(message, ensure_ascii=False)
    body_bytes = body.encode("utf-8")
    header = (
        f"Content-Length: {len(body_bytes)}\r\n"
        f"Content-Type: application/vscode-jsonrpc; charset=utf8\r\n\r\n"
    ).encode("ascii")
    return header + body_bytes


def decode_lsp_messages(data: bytes) -> tuple[list[dict], bytes]:
    """Parse zero or more LSP messages from a byte buffer.

    The decoder is incremental: any trailing bytes that do not yet form a
    complete message are returned as the second element of the tuple so the
    caller can prepend them to the next read.

    Args:
        data: Raw bytes read from the LSP server stdout.

    Returns:
        A ``(messages, remaining)`` tuple where ``messages`` is a list of
        parsed JSON-RPC dicts and ``remaining`` is the unparsed tail.
    """
    messages: list[dict] = []
    pos = 0
    n = len(data)
    while True:
        header_end = data.find(b"\r\n\r\n", pos)
        if header_end == -1:
            break
        header_bytes = data[pos:header_end]
        header = header_bytes.decode("ascii", errors="replace")
        content_length: Optional[int] = None
        for line in header.split("\r\n"):
            # Header field names are case-insensitive per LSP spec.
            if ":" not in line:
                continue
            name, _, value = line.partition(":")
            if name.strip().lower() == "content-length":
                try:
                    content_length = int(value.strip())
                except ValueError:
                    content_length = None
        if content_length is None:
            # No Content-Length -> malformed header; advance past this
            # header block to make progress.
            pos = header_end + 4
            continue
        body_start = header_end + 4
        body_end = body_start + content_length
        if body_end > n:
            # Not enough body bytes yet -- wait for more data.
            break
        body = data[body_start:body_end]
        try:
            message = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            logger.exception("Failed to parse LSP message body: %r", body)
            pos = body_end
            continue
        if isinstance(message, dict):
            messages.append(message)
        pos = body_end
    return messages, data[pos:]


def file_path_to_uri(path: str) -> str:
    """Convert a local filesystem path to an ``file://`` URI.

    The path is resolved to an absolute path before being converted so that
    relative paths are accepted from callers.  Backslashes (Windows) are
    handled by :meth:`pathlib.Path.as_uri`.
    """
    return Path(path).resolve().as_uri()


def uri_to_file_path(uri: str) -> str:
    """Convert an ``file://`` URI back to a local filesystem path.

    Non-``file://`` URIs are returned unchanged so callers can pass through
    any opaque URI the server emitted without raising.
    """
    if not uri.startswith("file://"):
        return uri
    parsed = urlparse(uri)
    # ``url2pathname`` decodes percent-encoded characters and converts
    # forward slashes to the platform separator.
    return url2pathname(parsed.path)


def _line_char_to_offset(text: str, line: int, character: int) -> int:
    """Convert a zero-based ``(line, character)`` position to a string offset."""
    if line < 0:
        return 0
    offset = 0
    cur_line = 0
    for ch in text:
        if cur_line == line:
            return offset + max(0, character)
        offset += 1
        if ch == "\n":
            cur_line += 1
    # Position past EOF -> clamp to end.
    return offset


def apply_text_edits(text: str, edits: list[dict]) -> str:
    """Apply a list of LSP ``TextEdit`` dicts to ``text``.

    Each edit must have the shape::

        {
            "range": {
                "start": {"line": L, "character": C},
                "end":   {"line": L, "character": C},
            },
            "newText": "<str>"
        }

    Edits are applied in reverse order of their start position so that
    earlier offsets remain valid as later edits are applied.  Overlapping
    ranges are not supported (the LSP spec forbids them in a single
    ``TextEdit[]`` payload).

    Args:
        text: The original document text.
        edits: A list of edit dicts (see shape above).

    Returns:
        The edited text.
    """
    if not edits:
        return text
    sorted_edits = sorted(
        edits,
        key=lambda e: (
            e["range"]["start"]["line"],
            e["range"]["start"]["character"],
        ),
        reverse=True,
    )
    result = text
    for edit in sorted_edits:
        r = edit["range"]
        start = r.get("start", {})
        end = r.get("end", {})
        start_offset = _line_char_to_offset(
            result, int(start.get("line", 0)), int(start.get("character", 0))
        )
        end_offset = _line_char_to_offset(
            result, int(end.get("line", 0)), int(end.get("character", 0))
        )
        if end_offset < start_offset:
            end_offset = start_offset
        new_text_edit = edit.get("newText", "")
        result = result[:start_offset] + new_text_edit + result[end_offset:]
    return result


# ---------------------------------------------------------------------------
# Blocking reader wrapper for subprocess stdout
# ---------------------------------------------------------------------------


class _BlockingBytesReader:
    """File-like wrapper offering ``readline``/``read`` for binary streams.

    The standard library's ``subprocess.Popen.stdout`` is a ``BufferedReader``
    whose ``readline`` returns ``b""`` only at EOF, which is exactly the
    contract :class:`pylsp_jsonrpc.streams.JsonRpcStreamReader` expects.
    We wrap it anyway so that we can inject a ``closed`` flag and a
    ``read(n)`` method that blocks until ``n`` bytes are available or EOF is
    reached -- the latter is needed for the manual framing loop.
    """

    def __init__(self, fileobj: Any) -> None:
        self._fileobj = fileobj
        self._lock = threading.Lock()
        self._closed = False

    @property
    def closed(self) -> bool:  # pragma: no cover - trivial
        return self._closed

    def close(self) -> None:
        self._closed = True
        try:
            self._fileobj.close()
        except Exception:  # pragma: no cover - best effort
            pass

    def readline(self) -> bytes:
        """Read a single line (including ``\\n``) or ``b""`` at EOF."""
        with self._lock:
            if self._closed:
                return b""
            try:
                return self._fileobj.readline()
            except Exception:  # pragma: no cover - pipe closed
                return b""

    def read(self, n: int) -> bytes:
        """Read up to ``n`` bytes, blocking until at least 1 byte is ready."""
        with self._lock:
            if self._closed or n <= 0:
                return b""
            try:
                # ``read(n)`` on a ``BufferedReader`` will block until either
                # ``n`` bytes are available or EOF is reached, which is the
                # behaviour we want.
                return self._fileobj.read(n)
            except Exception:  # pragma: no cover - pipe closed
                return b""


# ---------------------------------------------------------------------------
# GodotLSPClient
# ---------------------------------------------------------------------------


class GodotLSPClient:
    """LSP client for Godot's GDScript language server.

    The client spawns a Godot subprocess (``godot --headless --editor
    --script res://launch_lsp.gd``) and exchanges JSON-RPC 2.0 messages
    with it over the subprocess's stdin/stdout pipes using LSP
    ``Content-Length`` framing.

    A background :class:`threading.Thread` reads messages from the server
    asynchronously; responses to client-initiated requests are matched to
    their request id via per-id :class:`queue.Queue` instances, and
    server-initiated notifications (such as
    ``textDocument/publishDiagnostics``) are dispatched to registered
    callbacks.

    Usage::

        client = GodotLSPClient(godot_bin="godot", project_path="/proj")
        client.start()
        client.on_diagnostics(lambda uri, diags: print(uri, diags))
        client.did_open("/proj/player.gd", "extends Node\\n")
        items = client.completion("/proj/player.gd", 0, 8)
        client.stop()

    Note:
        The Godot LSP server itself is implemented as a TCP server (see
        ``GDScriptLanguageProtocol::start``).  This client expects the
        ``res://launch_lsp.gd`` script (or an equivalent launcher) to
        bridge the TCP server to the subprocess stdio pipes so that the
        client only needs to deal with one transport.
    """

    def __init__(
        self,
        godot_bin: str = DEFAULT_GODOT_BIN,
        project_path: str = ".",
    ) -> None:
        """Construct a new (not-yet-started) LSP client.

        Args:
            godot_bin: Path or name of the Godot executable.  Defaults to
                ``"godot"`` (assumed to be on ``PATH``).
            project_path: Path to the Godot project root (the directory
                containing ``project.godot``).  Used to set the LSP
                ``rootUri`` and as the ``--path`` argument to Godot.
        """
        self.godot_bin: str = godot_bin
        self.project_path: str = str(Path(project_path).resolve())

        # --- subprocess + transport -------------------------------------
        self._proc: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # --- request/response matching ----------------------------------
        self._response_queues: dict[str, queue.Queue] = {}
        self._response_lock = threading.Lock()
        self._next_id = 0
        self._id_lock = threading.Lock()

        # --- diagnostics ------------------------------------------------
        self._diagnostics_callback: Optional[
            Callable[[str, list[dict]], None]
        ] = None
        self._diagnostics_event = threading.Event()
        self._last_diagnostics: dict[str, list[dict]] = {}

        # --- document state ---------------------------------------------
        self._doc_versions: dict[str, int] = {}
        self._initialized = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch the Godot subprocess and perform the LSP handshake.

        Sends an ``initialize`` request followed by an ``initialized``
        notification so that the server is ready to accept further
        requests when this method returns.

        Raises:
            RuntimeError: If the subprocess cannot be started.
            TimeoutError: If the server does not respond to ``initialize``
                within :data:`DEFAULT_REQUEST_TIMEOUT` seconds.
        """
        if self._proc is not None:
            return  # already started
        cmd = [
            self.godot_bin,
            "--headless",
            "--editor",
            "--path",
            self.project_path,
            "--script",
            "res://launch_lsp.gd",
        ]
        logger.info("Starting Godot LSP subprocess: %s", " ".join(cmd))
        self._stop_event.clear()
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name="godot-lsp-reader",
            daemon=True,
        )
        self._reader_thread.start()
        # Drain stderr to a log so the subprocess does not deadlock when
        # its stderr pipe buffer fills up.
        self._stderr_thread = threading.Thread(
            target=self._stderr_loop,
            name="godot-lsp-stderr",
            daemon=True,
        )
        self._stderr_thread.start()
        self._do_initialize()

    def stop(self) -> None:
        """Shut down the LSP server and terminate the subprocess.

        Sends the standard ``shutdown`` request followed by an ``exit``
        notification, then waits for the subprocess to exit.  If the
        subprocess does not exit cleanly within a short grace period it
        is terminated and then killed.
        """
        if self._proc is None:
            return
        # Best-effort graceful shutdown per LSP spec.
        try:
            self.request("shutdown", None, timeout=2.0)
        except Exception:  # pragma: no cover - best effort
            logger.debug("shutdown request failed", exc_info=True)
        try:
            self.notify("exit", None)
        except Exception:  # pragma: no cover - best effort
            logger.debug("exit notification failed", exc_info=True)
        self._stop_event.set()
        try:
            self._proc.terminate()
            self._proc.wait(timeout=2.0)
        except Exception:  # pragma: no cover - platform-dependent
            try:
                self._proc.kill()
                self._proc.wait(timeout=1.0)
            except Exception:
                pass
        # Close stdin so the reader thread unblocks.
        try:
            if self._proc.stdin is not None:
                self._proc.stdin.close()
        except Exception:  # pragma: no cover - best effort
            pass
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=1.0)
            self._reader_thread = None
        if self._stderr_thread is not None:
            self._stderr_thread.join(timeout=1.0)
            self._stderr_thread = None
        self._proc = None
        self._initialized = False

    # ------------------------------------------------------------------
    # LSP handshake (internal)
    # ------------------------------------------------------------------

    def _do_initialize(self) -> dict:
        """Send the ``initialize`` request and ``initialized`` notification."""
        root_uri = Path(self.project_path).resolve().as_uri()
        params = {
            "processId": os.getpid(),
            "rootUri": root_uri,
            "capabilities": {
                "textDocument": {
                    "synchronization": {
                        "didOpen": True,
                        "didChange": True,
                        "didClose": True,
                        "willSave": False,
                        "willSaveWaitUntil": False,
                        "save": False,
                    },
                    "completion": {
                        "completionItem": {
                            "snippetSupport": False,
                            "documentationFormat": ["markdown", "plaintext"],
                        },
                        "contextSupport": True,
                    },
                },
                "workspace": {
                    "applyEdit": True,
                    "workspaceEdit": {
                        "documentChanges": False,
                        "resourceOperations": [],
                    },
                },
            },
            "workspaceFolders": [
                {
                    "uri": root_uri,
                    "name": Path(self.project_path).name or "project",
                }
            ],
        }
        result = self.request("initialize", params)
        self.notify("initialized", {})
        self._initialized = True
        return result or {}

    # ------------------------------------------------------------------
    # Public LSP operations
    # ------------------------------------------------------------------

    def did_open(self, file_path: str, text: str) -> None:
        """Send a ``textDocument/didOpen`` notification.

        Registers ``file_path`` with the LSP server using the full document
        text.  The file's language id is always ``"gdscript"``.

        Args:
            file_path: Absolute or project-relative path to a ``.gd`` file.
            text: The full current contents of the file.
        """
        uri = file_path_to_uri(file_path)
        version = self._doc_versions.get(uri, 0)
        if version == 0:
            version = 1
        self._doc_versions[uri] = version
        params = {
            "textDocument": {
                "uri": uri,
                "languageId": GDSCRIPT_LANGUAGE_ID,
                "version": version,
                "text": text,
            }
        }
        self.notify("textDocument/didOpen", params)

    def did_change(self, file_path: str, new_text: str) -> None:
        """Send a ``textDocument/didChange`` notification (full sync).

        Replaces the entire document content.  The version number is
        incremented by 1 on every call (per-file).

        Args:
            file_path: Path to the file.
            new_text: The full new contents of the file.
        """
        uri = file_path_to_uri(file_path)
        version = self._doc_versions.get(uri, 0) + 1
        self._doc_versions[uri] = version
        params = {
            "textDocument": {"uri": uri, "version": version},
            "contentChanges": [{"text": new_text}],
        }
        self.notify("textDocument/didChange", params)

    def completion(
        self, file_path: str, line: int, char: int
    ) -> list[dict]:
        """Send a ``textDocument/completion`` request and return items.

        Args:
            file_path: Path to the file.
            line: Zero-based line index.
            char: Zero-based character offset on ``line``.

        Returns:
            A list of :class:`dict` completion items (LSP ``CompletionItem``
            shape).  Returns an empty list if the server returns ``null``.
        """
        params = self._build_completion_params(file_path, line, char)
        result = self.request("textDocument/completion", params)
        return _normalize_completion_result(result)

    def on_diagnostics(
        self, callback: Callable[[str, list[dict]], None]
    ) -> None:
        """Register a callback for ``textDocument/publishDiagnostics``.

        The callback is invoked as ``callback(uri, diagnostics)`` where
        ``uri`` is the document URI and ``diagnostics`` is a list of LSP
        ``Diagnostic`` dicts.  Only one callback is registered at a time;
        calling this method again replaces the previous callback.

        Args:
            callback: A callable accepting ``(uri: str, diagnostics:
                list[dict])``.
        """
        self._diagnostics_callback = callback

    def apply_edit(self, file_path: str, edits: list[dict]) -> bool:
        """Apply ``edits`` to ``file_path`` and verify via diagnostics.

        The workflow is:

        1. Load the ``.gd`` file from disk.
        2. Apply each edit (``range`` + ``newText``) using
           :func:`apply_text_edits`.
        3. Save the modified file back to disk.
        4. Send a ``textDocument/didChange`` notification so the LSP
           server re-parses the file.
        5. Wait for a ``textDocument/publishDiagnostics`` notification
           (up to :data:`DEFAULT_DIAGNOSTICS_TIMEOUT` seconds).

        Args:
            file_path: Path to the ``.gd`` file to edit.
            edits: A list of LSP ``TextEdit`` dicts.

        Returns:
            ``True`` if no error-severity diagnostics were published for
            the file, or if no diagnostics arrived at all within the
            timeout.  ``False`` if at least one error-severity diagnostic
            was reported.
        """
        # 1. Load the file.
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        # 2. Apply edits.
        new_text = apply_text_edits(text, edits)
        # 3. Save the file.
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_text)
        # 4. Notify the server and arm the diagnostics wait.
        uri = file_path_to_uri(file_path)
        self._diagnostics_event.clear()
        self._last_diagnostics.pop(uri, None)
        self.did_change(file_path, new_text)
        # 5. Wait for diagnostics.
        if not self._diagnostics_event.wait(
            timeout=DEFAULT_DIAGNOSTICS_TIMEOUT
        ):
            logger.warning(
                "Timed out waiting for diagnostics after apply_edit on %s",
                file_path,
            )
            return True  # assume success if server is silent
        diagnostics = self._last_diagnostics.get(uri, [])
        for d in diagnostics:
            severity = int(d.get("severity", 0))
            if severity == DIAGNOSTIC_SEVERITY_ERROR:
                return False
        return True

    # ------------------------------------------------------------------
    # Lower-level JSON-RPC primitives
    # ------------------------------------------------------------------

    def request(
        self,
        method: str,
        params: Any,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
    ) -> Any:
        """Send a JSON-RPC request and wait for the matching response.

        Args:
            method: LSP method name (e.g. ``"initialize"``).
            params: JSON-serialisable params payload (or ``None``).
            timeout: Maximum seconds to wait for a response.

        Returns:
            The ``result`` field of the response.

        Raises:
            TimeoutError: If no response is received within ``timeout``.
            RuntimeError: If the server returns an ``error`` response.
        """
        msg_id = self._next_request_id()
        message: dict = {
            "jsonrpc": JSONRPC_VERSION,
            "id": msg_id,
            "method": method,
        }
        if params is not None:
            message["params"] = params
        response_queue = self._get_response_queue(msg_id)
        self._send_message(message)
        try:
            response = response_queue.get(timeout=timeout)
        except queue.Empty:
            with self._response_lock:
                self._response_queues.pop(str(msg_id), None)
            raise TimeoutError(
                f"LSP request '{method}' (id={msg_id}) timed out "
                f"after {timeout}s"
            )
        with self._response_lock:
            self._response_queues.pop(str(msg_id), None)
        if "error" in response and response["error"] is not None:
            raise RuntimeError(
                f"LSP request '{method}' (id={msg_id}) failed: "
                f"{response['error']}"
            )
        return response.get("result")

    def notify(self, method: str, params: Any) -> None:
        """Send a JSON-RPC notification (no response expected).

        Args:
            method: LSP method name (e.g. ``"textDocument/didOpen"``).
            params: JSON-serialisable payload (or ``None``).
        """
        message: dict = {
            "jsonrpc": JSONRPC_VERSION,
            "method": method,
        }
        if params is not None:
            message["params"] = params
        self._send_message(message)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_completion_params(
        self, file_path: str, line: int, char: int
    ) -> dict:
        """Build the params dict for a ``textDocument/completion`` request."""
        uri = file_path_to_uri(file_path)
        return {
            "textDocument": {"uri": uri},
            "position": {"line": int(line), "character": int(char)},
            "context": {
                "triggerKind": COMPLETION_TRIGGER_INVOKED,
            },
        }

    def _next_request_id(self) -> int:
        """Atomically allocate the next request id."""
        with self._id_lock:
            self._next_id += 1
            return self._next_id

    def _get_response_queue(self, msg_id: int) -> queue.Queue:
        """Return (creating if necessary) the response queue for ``msg_id``."""
        key = str(msg_id)
        with self._response_lock:
            q = self._response_queues.get(key)
            if q is None:
                q = queue.Queue()
                self._response_queues[key] = q
            return q

    def _send_message(self, message: dict) -> None:
        """Serialise ``message`` and write it to the subprocess stdin."""
        if self._proc is None or self._proc.stdin is None:
            raise RuntimeError(
                "GodotLSPClient is not started; call start() first"
            )
        data = encode_lsp_message(message)
        try:
            self._proc.stdin.write(data)
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise RuntimeError(
                f"Failed to write to Godot LSP subprocess: {exc}"
            ) from exc

    def _reader_loop(self) -> None:
        """Background thread: read and dispatch messages from the server."""
        assert self._proc is not None and self._proc.stdout is not None
        reader = _BlockingBytesReader(self._proc.stdout)
        buffer = b""
        while not self._stop_event.is_set():
            try:
                chunk = reader.read(4096)
            except Exception:  # pragma: no cover - pipe closed
                break
            if not chunk:
                break
            buffer += chunk
            messages, buffer = decode_lsp_messages(buffer)
            for message in messages:
                try:
                    self._handle_message(message)
                except Exception:  # pragma: no cover - defensive
                    logger.exception(
                        "Unhandled error while dispatching LSP message: %s",
                        message,
                    )
        logger.debug("Godot LSP reader thread exiting")

    def _stderr_loop(self) -> None:
        """Background thread: drain subprocess stderr to the logger."""
        assert self._proc is not None and self._proc.stderr is not None
        try:
            for line in iter(self._proc.stderr.readline, b""):
                if not line:
                    break
                try:
                    text = line.decode("utf-8", errors="replace").rstrip()
                except Exception:  # pragma: no cover - defensive
                    continue
                if text:
                    logger.debug("[godot-lsp stderr] %s", text)
        except Exception:  # pragma: no cover - pipe closed
            pass

    def _handle_message(self, message: dict) -> None:
        """Dispatch a single incoming LSP message.

        - Responses (have ``id``, no ``method``) are routed to the
          per-id :class:`queue.Queue` so the originating
          :meth:`request` call unblocks.
        - Notifications (have ``method``, no ``id``) are dispatched to
          the appropriate handler.  ``textDocument/publishDiagnostics``
          is forwarded to the registered callback and also cached so
          :meth:`apply_edit` can poll for it.
        - Server-initiated requests (have both ``id`` and ``method``)
          are answered.  ``workspace/applyEdit`` is the main one of
          interest: it is dispatched to :meth:`_handle_apply_edit_request`.
        """
        if "id" in message and "method" not in message:
            self._handle_response(message)
        elif "method" in message and "id" not in message:
            self._handle_notification(message)
        elif "method" in message and "id" in message:
            self._handle_server_request(message)
        else:
            logger.warning("Unknown LSP message shape: %s", message)

    def _handle_response(self, message: dict) -> None:
        msg_id = str(message["id"])
        with self._response_lock:
            q = self._response_queues.get(msg_id)
        if q is None:  # pragma: no cover - defensive
            logger.warning(
                "Received response for unknown request id=%s", msg_id
            )
            return
        q.put(message)

    def _handle_notification(self, message: dict) -> None:
        method = message.get("method", "")
        params = message.get("params") or {}
        if method == "textDocument/publishDiagnostics":
            uri = params.get("uri", "")
            diagnostics = params.get("diagnostics", []) or []
            self._last_diagnostics[uri] = list(diagnostics)
            self._diagnostics_event.set()
            if self._diagnostics_callback is not None:
                try:
                    self._diagnostics_callback(uri, list(diagnostics))
                except Exception:  # pragma: no cover - defensive
                    logger.exception(
                        "Diagnostics callback raised for %s", uri
                    )
        elif method == "window/showMessage":
            logger.info(
                "[godot-lsp] %s: %s",
                params.get("type", ""),
                params.get("message", ""),
            )
        elif method == "window/logMessage":
            logger.debug(
                "[godot-lsp] %s: %s",
                params.get("type", ""),
                params.get("message", ""),
            )
        else:
            logger.debug("Unhandled LSP notification: %s", method)

    def _handle_server_request(self, message: dict) -> None:
        method = message.get("method", "")
        params = message.get("params") or {}
        msg_id = message["id"]
        if method == "workspace/applyEdit":
            result = self._handle_apply_edit_request(params)
        else:
            logger.debug("Unhandled server request: %s", method)
            result = {}
        self._send_message(
            {
                "jsonrpc": JSONRPC_VERSION,
                "id": msg_id,
                "result": result,
            }
        )

    def _handle_apply_edit_request(self, params: dict) -> dict:
        """Handle an inbound ``workspace/applyEdit`` request.

        Applies every ``changes[uri]`` entry to its file on disk and returns
        ``{"applied": True}`` (or ``{"applied": False, "failureReason": ...}``
        if an exception occurred).
        """
        edit = params.get("edit", {}) or {}
        changes = edit.get("changes", {}) or {}
        any_failure = False
        for uri, edits in changes.items():
            try:
                file_path = uri_to_file_path(uri)
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read()
                new_text = apply_text_edits(text, edits)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_text)
            except Exception:
                logger.exception("Failed to apply workspace edit to %s", uri)
                any_failure = True
        if any_failure:
            return {
                "applied": False,
                "failureReason": "One or more edits could not be applied",
            }
        return {"applied": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_completion_result(result: Any) -> list[dict]:
    """Normalise a ``textDocument/completion`` response to a list of items.

    The LSP spec allows the server to return either ``CompletionItem[]``
    or ``CompletionList`` (``{"isIncomplete": bool, "items": [...]}``)
    or ``null``.
    """
    if result is None:
        return []
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    if isinstance(result, dict):
        items = result.get("items", [])
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]
    return []


__all__ = [
    "JSONRPC_VERSION",
    "DEFAULT_GODOT_BIN",
    "DEFAULT_LSP_PORT",
    "DEFAULT_REQUEST_TIMEOUT",
    "DEFAULT_DIAGNOSTICS_TIMEOUT",
    "GDSCRIPT_LANGUAGE_ID",
    "DIAGNOSTIC_SEVERITY_ERROR",
    "DIAGNOSTIC_SEVERITY_WARNING",
    "DIAGNOSTIC_SEVERITY_INFORMATION",
    "DIAGNOSTIC_SEVERITY_HINT",
    "COMPLETION_TRIGGER_INVOKED",
    "COMPLETION_TRIGGER_CHARACTER",
    "COMPLETION_TRIGGER_INCOMPLETE",
    "GodotLSPClient",
    "encode_lsp_message",
    "decode_lsp_messages",
    "file_path_to_uri",
    "uri_to_file_path",
    "apply_text_edits",
]
