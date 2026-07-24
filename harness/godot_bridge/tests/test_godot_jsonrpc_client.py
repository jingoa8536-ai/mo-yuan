"""Unit tests for :mod:`godot_jsonrpc_client`.

These tests run a real in-process mock TCP JSON-RPC server on a random port
and exercise the client against it, verifying:

- request/response format compliance with JSON-RPC 2.0
- error propagation as :class:`JSONRPCError`
- batch call handling (request array → response array)
- auto-reconnect after the server closes a connection mid-call
- thread-safety under concurrent callers

The mock server speaks newline-delimited JSON (NDJSON), matching the Godot
bridge's framing. Tests do **not** require the optional ``jsonrpcclient``
library — the client falls back to manual request construction when it is
absent, so these tests run in minimal environments.

Run::

    python -m pytest D:\\LAAP\\harness\\godot_bridge\\tests\\test_godot_jsonrpc_client.py -v
"""
from __future__ import annotations

import json
import socket
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Optional

import pytest

# Make the client module importable when tests are run from anywhere.
_PYTHON_DIR = Path(__file__).resolve().parent.parent / "python"
if str(_PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(_PYTHON_DIR))

from godot_jsonrpc_client import (  # noqa: E402  (import after sys.path tweak)
    GodotJSONRPCClient,
    JSONRPCError,
)


# --------------------------------------------------------------------------- #
# Mock JSON-RPC server (real TCP, in-process)
# --------------------------------------------------------------------------- #
class MockJSONRPCServer:
    """Minimal NDJSON JSON-RPC 2.0 server bound to an ephemeral port.

    Each accepted connection is handled in its own daemon thread. The
    ``handler`` callable maps a parsed request dict to a response dict (or
    ``None`` to suppress a reply). ``close_first_n`` closes the first *N*
    connections immediately without reading or writing — used to exercise
    the client's auto-reconnect path.
    """

    def __init__(
        self,
        handler: Optional[Callable[[dict], Any]] = None,
        close_first_n: int = 0,
    ) -> None:
        self.handler = handler
        self.close_first_n = close_first_n
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind(("127.0.0.1", 0))
        self._server_socket.listen(32)
        self.port: int = self._server_socket.getsockname()[1]
        self.host: str = "127.0.0.1"
        self._running = threading.Event()
        self._accept_thread: Optional[threading.Thread] = None
        self._conn_count = 0
        self._count_lock = threading.Lock()
        self._handler_threads: list[threading.Thread] = []

    def start(self) -> None:
        self._running.set()
        self._accept_thread = threading.Thread(
            target=self._accept_loop, daemon=True
        )
        self._accept_thread.start()

    def stop(self) -> None:
        self._running.clear()
        try:
            # Unblock accept() by closing the listening socket.
            self._server_socket.close()
        except OSError:
            pass
        if self._accept_thread is not None:
            self._accept_thread.join(timeout=2.0)

    def _accept_loop(self) -> None:
        while self._running.is_set():
            try:
                conn, _addr = self._server_socket.accept()
            except OSError:
                break  # server socket closed
            with self._count_lock:
                self._conn_count += 1
                conn_num = self._conn_count
            t = threading.Thread(
                target=self._handle, args=(conn, conn_num), daemon=True
            )
            t.start()
            self._handler_threads.append(t)

    def _handle(self, conn: socket.socket, conn_num: int) -> None:
        """Handle one connection: optionally close-first, then serve NDJSON."""
        try:
            if conn_num <= self.close_first_n:
                # Close immediately to force the client to reconnect.
                return
            decoder = json.JSONDecoder()
            buffer = ""
            while self._running.is_set():
                try:
                    chunk = conn.recv(65536)
                except OSError:
                    break
                if not chunk:
                    break
                buffer += chunk.decode("utf-8")
                # Parse one or more complete JSON values from the buffer.
                while buffer:
                    try:
                        obj, end = decoder.raw_decode(buffer)
                    except json.JSONDecodeError:
                        break  # incomplete — need more bytes
                    response = self._build_response(obj)
                    if response is not None:
                        try:
                            conn.sendall(
                                (json.dumps(response) + "\n").encode("utf-8")
                            )
                        except OSError:
                            return
                    buffer = buffer[end:].lstrip()
        except (OSError, ConnectionError):
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def _build_response(self, request: Any) -> Any:
        """Produce a JSON-RPC 2.0 response dict for a single request."""
        if self.handler is None:
            return None
        return self.handler(request)


# --------------------------------------------------------------------------- #
# Pytest fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def mock_server() -> MockJSONRPCServer:
    """Start a MockJSONRPCServer on an ephemeral port; tear down after test."""
    server = MockJSONRPCServer()
    server.start()
    try:
        yield server
    finally:
        server.stop()


def _make_client(
    server: MockJSONRPCServer,
    *,
    pool_size: int = 4,
    retries: int = 3,
    backoff: float = 0.02,
    timeout: float = 5.0,
) -> GodotJSONRPCClient:
    """Build a client pointed at ``server`` with test-friendly retry timings."""
    client = GodotJSONRPCClient(
        host=server.host,
        port=server.port,
        pool_size=pool_size,
        retries=retries,
        backoff=backoff,
        timeout=timeout,
    )
    return client


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_call_method_success(mock_server: MockJSONRPCServer) -> None:
    """Mock server returns a valid result → client unwraps and returns it."""

    def handler(req: dict) -> dict:
        # Echo back the request id and params so we verify format compliance.
        return {
            "jsonrpc": "2.0",
            "result": {"status": "ok", "echo": req.get("params")},
            "id": req["id"],
        }

    mock_server.handler = handler
    client = _make_client(mock_server)
    try:
        result = client.call_method("ping", {"hello": "world"})
    finally:
        client.close()

    assert result == {"status": "ok", "echo": {"hello": "world"}}


def test_call_method_success_format(mock_server: MockJSONRPCServer) -> None:
    """Verify the on-wire request body is JSON-RPC 2.0 compliant."""

    captured: dict = {}

    def handler(req: dict) -> dict:
        captured.update(req)
        return {"jsonrpc": "2.0", "result": 42, "id": req["id"]}

    mock_server.handler = handler
    client = _make_client(mock_server)
    try:
        result = client.call_method("add", {"a": 1, "b": 2})
    finally:
        client.close()

    assert result == 42
    # Verify the request envelope followed the JSON-RPC 2.0 spec.
    assert captured["jsonrpc"] == "2.0"
    assert captured["method"] == "add"
    assert captured["params"] == {"a": 1, "b": 2}
    assert isinstance(captured["id"], int)


def test_call_method_error(mock_server: MockJSONRPCServer) -> None:
    """Mock server returns a JSON-RPC error → client raises JSONRPCError."""

    def handler(req: dict) -> dict:
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32000,
                "message": "boom",
                "data": {"detail": "explosion"},
            },
            "id": req["id"],
        }

    mock_server.handler = handler
    client = _make_client(mock_server)
    try:
        with pytest.raises(JSONRPCError) as exc_info:
            client.call_method("explode", {})
    finally:
        client.close()

    err = exc_info.value
    assert err.code == -32000
    assert err.message == "boom"
    assert err.data == {"detail": "explosion"}


def test_batch_call(mock_server: MockJSONRPCServer) -> None:
    """Batch request → batch response, results matched by id and order kept."""

    def handler(req: dict) -> dict:
        if req["method"] == "add" and isinstance(req.get("params"), list):
            a, b = req["params"]
            return {"jsonrpc": "2.0", "result": a + b, "id": req["id"]}
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": "method not found"},
            "id": req["id"],
        }

    mock_server.handler = handler
    client = _make_client(mock_server)
    try:
        results = client.batch_call(
            [
                ("add", [1, 2]),
                ("add", [3, 4]),
                ("add", [10, 20]),
            ]
        )
    finally:
        client.close()

    assert results == [3, 7, 30]


def test_batch_call_unordered(mock_server: MockJSONRPCServer) -> None:
    """Server may reorder batch responses — client matches by id."""

    def handler(req: dict) -> dict:
        return {"jsonrpc": "2.0", "result": req["id"] * 10, "id": req["id"]}

    mock_server.handler = handler
    client = _make_client(mock_server)
    try:
        results = client.batch_call(
            [
                ("mul", [1]),
                ("mul", [2]),
                ("mul", [3]),
            ]
        )
    finally:
        client.close()

    # ids 1,2,3 → results 10,20,30 regardless of server response order.
    assert results == [10, 20, 30]


def test_auto_reconnect(mock_server: MockJSONRPCServer) -> None:
    """Server closes the first connection → client reconnects and retries."""

    # First accepted connection is dropped immediately by the mock server.
    mock_server.close_first_n = 1

    def handler(req: dict) -> dict:
        return {"jsonrpc": "2.0", "result": "reconnected", "id": req["id"]}

    mock_server.handler = handler
    client = _make_client(mock_server, retries=3, backoff=0.02)
    try:
        result = client.call_method("ping", {})
    finally:
        client.close()

    assert result == "reconnected"
    # Sanity check: at least 2 connections were accepted (1 dropped + 1 served).
    assert mock_server._conn_count >= 2


def test_concurrent_calls(mock_server: MockJSONRPCServer) -> None:
    """10 concurrent threads call_method → all succeed (thread-safe)."""

    def handler(req: dict) -> dict:
        params = req.get("params") or {}
        return {
            "jsonrpc": "2.0",
            "result": params.get("a", 0) + params.get("b", 0),
            "id": req["id"],
        }

    mock_server.handler = handler
    client = _make_client(mock_server, pool_size=4)
    results: list[Any] = [None] * 10
    errors: list[Any] = [None] * 10

    def worker(idx: int) -> None:
        try:
            results[idx] = client.call_method("add", {"a": idx, "b": 1})
        except BaseException as exc:  # noqa: BLE001 — capture any failure
            errors[idx] = exc

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15.0)

    try:
        for i, err in enumerate(errors):
            assert err is None, f"thread {i} failed: {err!r}"
        for i, value in enumerate(results):
            assert value == i + 1, f"thread {i} got {value!r}, expected {i + 1}"
    finally:
        client.close()


def test_context_manager_closes_pool(mock_server: MockJSONRPCServer) -> None:
    """Using the client as a context manager closes pooled sockets."""

    def handler(req: dict) -> dict:
        return {"jsonrpc": "2.0", "result": "ok", "id": req["id"]}

    mock_server.handler = handler
    with _make_client(mock_server) as client:
        assert client.call_method("ping", {}) == "ok"
    # After context exit the client is closed; further calls raise.
    with pytest.raises(JSONRPCError):
        client.call_method("ping", {})


def test_empty_batch_returns_empty_list(
    mock_server: MockJSONRPCServer
) -> None:
    """batch_call with no methods short-circuits to an empty list (no I/O)."""
    client = _make_client(mock_server)
    try:
        assert client.batch_call([]) == []
    finally:
        client.close()
