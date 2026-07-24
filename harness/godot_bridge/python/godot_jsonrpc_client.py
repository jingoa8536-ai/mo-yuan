"""LAAP Godot JSONRPC Client — TCP 6005 JSON-RPC 2.0 client for Godot engine control.

This module provides a thread-safe JSON-RPC 2.0 client that communicates with
the Godot engine bridge (``gdscripts/laap_bridge.gd``) over a persistent TCP
socket on port 6005. It is part of the LAAP 0-Token Game Dev Framework
(M1 GodotBridge engine control layer).

Key features
------------
- Synchronous :meth:`GodotJSONRPCClient.call_method` calls returning the
  ``result`` field or raising :class:`JSONRPCError`.
- :meth:`GodotJSONRPCClient.batch_call` for JSON-RPC 2.0 batch requests,
  reducing round-trips when several methods must be invoked together.
- :meth:`GodotJSONRPCClient.call_method_async` asyncio wrapper backed by
  :func:`asyncio.to_thread`.
- Connection pool (default 4 persistent sockets) with automatic retry on
  broken pipe / connection reset (up to 3 retries with 1s exponential
  backoff).
- Thread-safe public API (``threading.Lock`` around the id counter and the
  connection pool).
- Context manager support (``with GodotJSONRPCClient(...) as c: ...``).

Wire format
-----------
Requests follow JSON-RPC 2.0::

    {"jsonrpc": "2.0", "method": "...", "params": {...}, "id": N}

The ``id`` is auto-incremented per client instance. Responses are parsed with
``json.JSONDecoder.raw_decode`` so the transport tolerates either
newline-delimited JSON (NDJSON, the Godot bridge default) or a single JSON
value per read. On an ``error`` field the client raises
``JSONRPCError(code, message, data)``.

The ``jsonrpcclient`` library (declared in ``pyproject.toml``) is used for
request construction when available; if it is not installed the client falls
back to manual dict construction so the module remains importable in
minimal environments.
"""
from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

# Optional dependency: used only for request construction. The module must
# remain importable when it is absent (e.g. in CI / minimal installs).
try:  # pragma: no cover - import guard, exercised by environment
    import jsonrpcclient as _jc  # type: ignore

    _HAS_JSONRPCCLIENT = True
except ImportError:  # pragma: no cover
    _jc = None  # type: ignore
    _HAS_JSONRPCCLIENT = False


__all__ = ["JSONRPCError", "JSONRPCResponse", "GodotJSONRPCClient"]


class JSONRPCError(Exception):
    """JSON-RPC 2.0 error response.

    Raised by the client whenever the server returns an ``error`` object, or
    when a transport-level failure (timeout, parse error, exhausted retries)
    prevents a successful round-trip.

    Attributes
    ----------
    code : int
        JSON-RPC error code. Server-defined codes use the range -32000 to
        -32099; pre-defined codes (e.g. -32700 parse error, -32603 internal
        error) are used for transport faults.
    message : str
        Short human-readable error message.
    data : Any
        Optional application-defined data payload from the server, or the
        raw response dict for transport-level faults.
    """

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        self.code = int(code)
        self.message = str(message)
        self.data = data
        suffix = "" if data is None else f": {data!r}"
        super().__init__(f"[{self.code}] {self.message}{suffix}")


@dataclass
class JSONRPCResponse:
    """Parsed JSON-RPC 2.0 response envelope.

    Exactly one of ``result`` / ``error`` is populated for a successful /
    failed call. Kept as a dataclass so callers that want the raw envelope
    (rather than the unwrapped ``result``) can inspect it.
    """

    id: int
    result: Any = None
    error: Optional[dict] = None


class GodotJSONRPCClient:
    """Thread-safe JSON-RPC 2.0 client for Godot engine control via TCP 6005.

    The client maintains a pool of persistent TCP connections (default 4) and
    retries on broken pipe / connection reset up to ``retries`` times with
    exponential backoff. All public methods are safe to call from multiple
    threads concurrently.

    Parameters
    ----------
    host : str
        Godot bridge host (default ``"127.0.0.1"``).
    port : int
        Godot bridge TCP port (default ``6005``).
    pool_size : int
        Maximum number of persistent connections to keep in the pool
        (default ``4``).
    retries : int
        Total connection attempts per call before giving up (default ``3``).
    backoff : float
        Base seconds for exponential backoff between retries; actual wait is
        ``backoff * (2 ** attempt)`` (default ``1.0``).
    timeout : float
        Per-socket recv timeout in seconds (default ``10.0``).

    Examples
    --------
    >>> with GodotJSONRPCClient() as c:
    ...     c.call_method("ping", {})
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6005,
        pool_size: int = 4,
        retries: int = 3,
        backoff: float = 1.0,
        timeout: float = 10.0,
    ) -> None:
        self.host = host
        self.port = int(port)
        self.pool_size = max(1, int(pool_size))
        self.retries = max(1, int(retries))
        self.backoff = float(backoff)
        self.timeout = float(timeout)

        self._pool: list[socket.socket] = []
        self._pool_lock = threading.Lock()
        self._id_lock = threading.Lock()
        self._id = 0
        self._closed = False
        self._recv_buffer_size = 65536

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _next_id(self) -> int:
        """Return the next monotonically increasing request id (thread-safe)."""
        with self._id_lock:
            self._id += 1
            return self._id

    def _build_request(
        self, method: str, params: Any, req_id: int
    ) -> dict:
        """Build a single JSON-RPC 2.0 request object.

        Uses ``jsonrpcclient.request`` when the library is importable;
        otherwise falls back to manual dict construction so the module works
        in minimal environments.
        """
        if _HAS_JSONRPCCLIENT:
            try:
                if params is not None:
                    req = _jc.request(method, params=params, id=req_id)
                else:
                    req = _jc.request(method, id=req_id)
                if isinstance(req, dict):
                    return dict(req)
            except Exception:
                pass  # fall through to manual construction
        req: dict = {"jsonrpc": "2.0", "method": method, "id": req_id}
        if params is not None:
            req["params"] = params
        return req

    def _build_batch_request(
        self, methods: list[tuple[str, Any]]
    ) -> list[dict]:
        """Build a JSON-RPC 2.0 batch request list (one entry per method)."""
        batch: list[dict] = []
        for method, params in methods:
            req_id = self._next_id()
            req = self._build_request(method, params, req_id)
            batch.append(req)
        return batch

    @staticmethod
    def _serialize(obj: Any) -> bytes:
        """Serialize a JSON-RPC payload to UTF-8 bytes with a trailing newline.

        The trailing newline matches the Godot bridge's NDJSON framing; the
        receiver also tolerates responses without newlines via
        ``raw_decode``.
        """
        return (json.dumps(obj) + "\n").encode("utf-8")

    def _create_connection(self) -> socket.socket:
        """Create and connect a fresh TCP socket to the Godot bridge."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            # Disable Nagle's algorithm for low-latency RPC traffic.
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass  # not all platforms support TCP_NODELAY
        sock.connect((self.host, self.port))
        return sock

    def _get_connection(self) -> socket.socket:
        """Pop a connection from the pool, or create a new one if empty."""
        with self._pool_lock:
            if self._pool:
                return self._pool.pop()
        return self._create_connection()

    def _return_connection(self, sock: socket.socket) -> None:
        """Return a healthy connection to the pool, closing if pool is full."""
        if self._closed:
            try:
                sock.close()
            except OSError:
                pass
            return
        with self._pool_lock:
            if len(self._pool) < self.pool_size:
                self._pool.append(sock)
                return
        # Pool is full — discard the extra connection.
        try:
            sock.close()
        except OSError:
            pass

    def _recv_response(self, sock: socket.socket) -> Any:
        """Read and parse one JSON-RPC response from the socket.

        Uses ``json.JSONDecoder.raw_decode`` to handle both newline-delimited
        and non-delimited servers. Raises ``ConnectionError`` (caught by the
        retry loop) when the peer closes the connection mid-read.
        """
        buffer = b""
        decoder = json.JSONDecoder()
        while True:
            try:
                chunk = sock.recv(self._recv_buffer_size)
            except socket.timeout as exc:
                raise ConnectionError(f"socket timeout: {exc}") from exc
            if not chunk:
                # Peer closed. If we have a complete buffer, try to parse it;
                # otherwise this is a premature close → retry.
                if buffer:
                    try:
                        return json.loads(buffer.decode("utf-8"))
                    except json.JSONDecodeError as exc:
                        raise ConnectionError(
                            f"connection closed with partial data: {exc}"
                        ) from exc
                raise ConnectionError("connection closed by peer while reading")
            buffer += chunk
            text = buffer.decode("utf-8")
            try:
                obj, _end = decoder.raw_decode(text)
                return obj
            except json.JSONDecodeError:
                # Incomplete JSON — keep reading.
                continue

    def _send_recv(self, payload: bytes) -> Any:
        """Send a payload and read one response, retrying on connection faults.

        Retries up to ``self.retries`` total attempts with exponential
        backoff (``self.backoff * 2**attempt``). Stale/broken sockets are
        closed and a fresh connection is created on the next attempt.
        """
        last_exc: Optional[BaseException] = None
        for attempt in range(self.retries):
            sock: Optional[socket.socket] = None
            try:
                sock = self._get_connection()
                sock.sendall(payload)
                return self._recv_response(sock)
            except (
                BrokenPipeError,
                ConnectionResetError,
                ConnectionAbortedError,
                ConnectionError,
                OSError,
            ) as exc:
                last_exc = exc
                if sock is not None:
                    try:
                        sock.close()
                    except OSError:
                        pass
                    sock = None
                if attempt < self.retries - 1:
                    time.sleep(self.backoff * (2 ** attempt))
                continue
            finally:
                if sock is not None:
                    self._return_connection(sock)
        raise JSONRPCError(
            -32603,
            f"connection failed after {self.retries} retries",
            str(last_exc) if last_exc is not None else None,
        )

    def _parse_response(self, response: Any, expected_id: int) -> Any:
        """Validate a single JSON-RPC response and return its ``result``.

        Raises :class:`JSONRPCError` for protocol violations or server errors.
        """
        if not isinstance(response, dict):
            raise JSONRPCError(
                -32603, "response is not a JSON object", response
            )
        resp_id = response.get("id")
        if resp_id != expected_id:
            raise JSONRPCError(
                -32603,
                f"response id mismatch: expected {expected_id}, got {resp_id}",
                response,
            )
        err = response.get("error")
        if err is not None:
            if not isinstance(err, dict):
                raise JSONRPCError(-32603, "malformed error object", err)
            raise JSONRPCError(
                err.get("code", 0),
                err.get("message", "unknown error"),
                err.get("data"),
            )
        return response.get("result")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def call_method(
        self, method: str, params: dict | list | None = None
    ) -> Any:
        """Synchronously invoke a JSON-RPC method and return its result.

        Parameters
        ----------
        method : str
            Remote method name (e.g. ``"ping"``, ``"engine/execute"``).
        params : dict | list | None
            Parameters object (positional list or named dict). Omitted from
            the request when ``None``.

        Returns
        -------
        Any
            The ``result`` field of the server response.

        Raises
        ------
        JSONRPCError
            If the server returns an ``error`` object, the response is
            malformed, or the connection cannot be re-established after
            ``retries`` attempts.
        """
        if self._closed:
            raise JSONRPCError(-32603, "client is closed")
        req_id = self._next_id()
        request = self._build_request(method, params, req_id)
        payload = self._serialize(request)
        response = self._send_recv(payload)
        return self._parse_response(response, req_id)

    def batch_call(
        self, methods: list[tuple[str, dict | list | None]]
    ) -> list[Any]:
        """Invoke multiple methods in a single JSON-RPC 2.0 batch request.

        Parameters
        ----------
        methods : list[tuple[str, dict | list | None]]
            List of ``(method, params)`` tuples. Each entry becomes one
            element of the batch array; ids are assigned automatically.

        Returns
        -------
        list[Any]
            One ``result`` per input method, in the same order. Results are
            matched by ``id`` so out-of-order server responses are handled.

        Raises
        ------
        JSONRPCError
            If any element of the batch response is an error, or the server
            does not return a JSON array.
        """
        if self._closed:
            raise JSONRPCError(-32603, "client is closed")
        if not methods:
            return []
        batch = self._build_batch_request(list(methods))
        payload = self._serialize(batch)
        response = self._send_recv(payload)
        if not isinstance(response, list):
            raise JSONRPCError(
                -32603, "batch response is not a JSON array", response
            )
        # Index responses by id (server may reorder).
        by_id: dict[int, dict] = {}
        for item in response:
            if isinstance(item, dict):
                rid = item.get("id")
                by_id[rid] = item
        results: list[Any] = []
        for req in batch:
            rid = req["id"]
            item = by_id.get(rid)
            if item is None:
                raise JSONRPCError(
                    -32603, f"missing response for id={rid}", response
                )
            results.append(self._parse_response(item, rid))
        return results

    async def call_method_async(
        self, method: str, params: dict | list | None = None
    ) -> Any:
        """Asynchronously invoke a JSON-RPC method.

        Wraps the synchronous :meth:`call_method` in
        :func:`asyncio.to_thread`, so the blocking socket I/O runs in a
        thread pool without blocking the event loop. Must be awaited from an
        async context.

        Parameters
        ----------
        method : str
            Remote method name.
        params : dict | list | None
            Parameters object.

        Returns
        -------
        Any
            The ``result`` field of the server response.
        """
        return await asyncio.to_thread(self.call_method, method, params)

    def close(self) -> None:
        """Close all pooled connections and mark the client as closed.

        After ``close()``, further :meth:`call_method` / :meth:`batch_call`
        invocations raise :class:`JSONRPCError`. Idempotent — calling
        ``close()`` on an already-closed client is a no-op.
        """
        with self._pool_lock:
            self._closed = True
            for sock in self._pool:
                try:
                    sock.close()
                except OSError:
                    pass
            self._pool.clear()

    def __enter__(self) -> "GodotJSONRPCClient":
        """Enter context manager — returns self."""
        return self

    def __exit__(self, *exc: Any) -> bool:
        """Exit context manager — closes all pooled connections."""
        self.close()
        return False


if __name__ == "__main__":
    # Sanity check: ping a local Godot bridge on the default endpoint.
    print(f"jsonrpcclient available: {_HAS_JSONRPCCLIENT}")
    print(f"connecting to 127.0.0.1:6005 ...")
    with GodotJSONRPCClient() as _client:
        try:
            _result = _client.call_method("ping", {})
            print(f"ping result: {_result}")
        except JSONRPCError as _err:
            print(f"ping failed (JSONRPCError): {_err}")
        except OSError as _err:
            print(f"ping failed (OSError): {_err}")
