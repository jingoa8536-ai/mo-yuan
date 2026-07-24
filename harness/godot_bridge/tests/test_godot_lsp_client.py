"""Unit tests for :mod:`godot_lsp_client`.

These tests exercise the message-framing helpers and the JSON-RPC payload
construction logic of :class:`GodotLSPClient` **without** launching a real
Godot subprocess.  Tests that need the :mod:`pylsp_jsonrpc` dependency are
guarded with ``pytest.importorskip("pylsp_jsonrpc")`` so the suite still
collects (and reports a skip) when the library is not installed.

The tests are organised as:

- ``test_lsp_message_framing`` -- encode/decode a single LSP frame.
- ``test_lsp_message_framing_multiple`` -- decode two concatenated frames
  plus an incomplete tail (incremental decoding).
- ``test_did_open_payload`` -- verify the ``textDocument/didOpen`` JSON-RPC
  payload structure (method, params, no ``id`` field).
- ``test_completion_payload`` -- verify the ``textDocument/completion``
  request structure (method, params, ``id`` field, position, context).
- ``test_diagnostics_handler_invocation`` -- simulate the server publishing
  diagnostics and verify the registered callback is invoked with the
  correct ``(uri, diagnostics)`` tuple.
- ``test_apply_text_edits`` -- verify :func:`apply_text_edits` applies
  LSP ``TextEdit`` ranges correctly (insert, replace, delete).
- ``test_did_change_increments_version`` -- verify that two consecutive
  ``didChange`` calls produce monotonically increasing version numbers.
- ``test_apply_edit_no_error_returns_true`` -- mock the diagnostics wait
  and assert :meth:`GodotLSPClient.apply_edit` returns ``True`` when no
  error-severity diagnostic is published.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

# Ensure the module under test is importable regardless of pytest's
# invocation directory.  The ``pythonpath`` setting in ``pyproject.toml``
# already adds the package root, but we add it explicitly here so the
# tests can be run directly with ``pytest <this_file>`` from anywhere.
_MOD_DIR = Path(__file__).resolve().parent.parent / "python"
if str(_MOD_DIR) not in sys.path:
    sys.path.insert(0, str(_MOD_DIR))

from godot_lsp_client import (  # noqa: E402  (import after sys.path tweak)
    DEFAULT_DIAGNOSTICS_TIMEOUT,
    DIAGNOSTIC_SEVERITY_ERROR,
    GDSCRIPT_LANGUAGE_ID,
    GodotLSPClient,
    apply_text_edits,
    decode_lsp_messages,
    encode_lsp_message,
    file_path_to_uri,
    uri_to_file_path,
)


# ---------------------------------------------------------------------------
# Framing
# ---------------------------------------------------------------------------


def test_lsp_message_framing() -> None:
    """Encode then decode a single LSP message and verify round-trip."""
    pytest.importorskip("pylsp_jsonrpc")
    msg = {
        "jsonrpc": "2.0",
        "method": "textDocument/didOpen",
        "params": {"textDocument": {"uri": "file:///tmp/test.gd"}},
    }
    encoded = encode_lsp_message(msg)
    assert isinstance(encoded, bytes)

    # Header must be ASCII and contain the Content-Length field.
    assert b"Content-Length: " in encoded
    assert b"\r\nContent-Type: application/vscode-jsonrpc; charset=utf8\r\n\r\n" in encoded

    # Body must be valid UTF-8 JSON matching the input dict.
    body_start = encoded.index(b"\r\n\r\n") + 4
    body = encoded[body_start:]
    assert json.loads(body.decode("utf-8")) == msg

    # Round-trip via the decoder.
    decoded, remaining = decode_lsp_messages(encoded)
    assert remaining == b""
    assert len(decoded) == 1
    assert decoded[0] == msg


def test_lsp_message_framing_multiple() -> None:
    """Decode two concatenated frames plus an incomplete tail."""
    pytest.importorskip("pylsp_jsonrpc")
    msg1 = {"jsonrpc": "2.0", "method": "a", "params": {"i": 1}}
    msg2 = {"jsonrpc": "2.0", "id": 7, "method": "b", "params": {"i": 2}}
    encoded1 = encode_lsp_message(msg1)
    encoded2 = encode_lsp_message(msg2)

    # Concatenate two full frames plus an incomplete header.
    incomplete_tail = b"Content-Length: 999\r\n\r\n"
    buffer = encoded1 + encoded2 + incomplete_tail

    decoded, remaining = decode_lsp_messages(buffer)
    assert len(decoded) == 2
    assert decoded[0] == msg1
    assert decoded[1] == msg2
    # The incomplete header must be returned as the remaining tail so the
    # caller can prepend it to the next read.
    assert remaining == incomplete_tail


def test_lsp_message_framing_unicode() -> None:
    """Verify non-ASCII content survives the round-trip."""
    pytest.importorskip("pylsp_jsonrpc")
    msg = {
        "jsonrpc": "2.0",
        "method": "test",
        "params": {"text": "extends Node  # 中文注释 ñ é ü"},
    }
    encoded = encode_lsp_message(msg)
    decoded, _ = decode_lsp_messages(encoded)
    assert decoded == [msg]


# ---------------------------------------------------------------------------
# didOpen payload
# ---------------------------------------------------------------------------


def test_did_open_payload(tmp_path: Path) -> None:
    """Verify the ``textDocument/didOpen`` JSON-RPC payload structure."""
    pytest.importorskip("pylsp_jsonrpc")
    client = GodotLSPClient(project_path=str(tmp_path))

    captured: list[dict] = []
    client._send_message = lambda msg: captured.append(msg)  # type: ignore[assignment]

    file_path = tmp_path / "player.gd"
    file_path.write_text("extends Node\n", encoding="utf-8")
    client.did_open(str(file_path), "extends Node\n")

    assert len(captured) == 1
    msg = captured[0]

    # Notifications must NOT carry an ``id`` field.
    assert "id" not in msg
    assert msg["jsonrpc"] == "2.0"
    assert msg["method"] == "textDocument/didOpen"

    params = msg["params"]
    assert "textDocument" in params
    td = params["textDocument"]
    assert td["languageId"] == GDSCRIPT_LANGUAGE_ID
    assert td["text"] == "extends Node\n"
    assert td["version"] == 1
    assert td["uri"].startswith("file://")
    # The URI must round-trip back to the original path.
    assert uri_to_file_path(td["uri"]) == str(file_path.resolve())


def test_did_open_payload_uses_absolute_uri(tmp_path: Path) -> None:
    """``did_open`` must resolve relative paths to absolute ``file://`` URIs."""
    pytest.importorskip("pylsp_jsonrpc")
    client = GodotLSPClient(project_path=str(tmp_path))
    captured: list[dict] = []
    client._send_message = lambda msg: captured.append(msg)  # type: ignore[assignment]

    # Create the file in tmp_path and pass a relative path to did_open.
    abs_path = tmp_path / "player.gd"
    abs_path.write_text("extends Node\n", encoding="utf-8")
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        client.did_open("player.gd", "extends Node\n")
    finally:
        os.chdir(cwd)

    assert len(captured) == 1
    uri = captured[0]["params"]["textDocument"]["uri"]
    assert uri.startswith("file:///")
    assert uri_to_file_path(uri) == str(abs_path.resolve())


# ---------------------------------------------------------------------------
# completion payload
# ---------------------------------------------------------------------------


def test_completion_payload(tmp_path: Path) -> None:
    """Verify the ``textDocument/completion`` request structure."""
    pytest.importorskip("pylsp_jsonrpc")
    client = GodotLSPClient(project_path=str(tmp_path))

    captured: list[dict] = []

    def fake_send(msg: dict) -> None:
        captured.append(msg)
        # Inject a fake empty-list response so the synchronous ``request``
        # call unblocks immediately.
        msg_id = str(msg["id"])
        q = client._get_response_queue(int(msg_id))
        q.put({"jsonrpc": "2.0", "id": msg["id"], "result": []})

    client._send_message = fake_send  # type: ignore[assignment]

    file_path = tmp_path / "player.gd"
    file_path.write_text("extends Node\n", encoding="utf-8")
    items = client.completion(str(file_path), line=5, char=10)

    assert items == []
    assert len(captured) == 1
    msg = captured[0]

    # Requests MUST carry an ``id`` field.
    assert "id" in msg
    assert msg["jsonrpc"] == "2.0"
    assert msg["method"] == "textDocument/completion"

    params = msg["params"]
    assert params["textDocument"]["uri"].startswith("file://")
    assert params["position"] == {"line": 5, "character": 10}
    assert params["context"]["triggerKind"] == 1  # Invoked


def test_completion_normalises_completion_list(tmp_path: Path) -> None:
    """A ``CompletionList`` dict result must be normalised to its items."""
    pytest.importorskip("pylsp_jsonrpc")
    client = GodotLSPClient(project_path=str(tmp_path))

    fake_items = [
        {"label": "Node", "kind": 7},
        {"label": "position", "kind": 6},
    ]

    def fake_send(msg: dict) -> None:
        msg_id = str(msg["id"])
        q = client._get_response_queue(int(msg_id))
        q.put(
            {
                "jsonrpc": "2.0",
                "id": msg["id"],
                "result": {"isIncomplete": False, "items": fake_items},
            }
        )

    client._send_message = fake_send  # type: ignore[assignment]
    items = client.completion(str(tmp_path / "x.gd"), 0, 0)
    assert items == fake_items


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


def test_diagnostics_handler_invocation() -> None:
    """A registered callback is invoked when the server publishes diagnostics."""
    pytest.importorskip("pylsp_jsonrpc")
    client = GodotLSPClient()

    received: list[tuple[str, list[dict]]] = []
    client.on_diagnostics(lambda uri, diags: received.append((uri, diags)))

    fake_message = {
        "jsonrpc": "2.0",
        "method": "textDocument/publishDiagnostics",
        "params": {
            "uri": "file:///tmp/test.gd",
            "diagnostics": [
                {
                    "range": {
                        "start": {"line": 0, "character": 0},
                        "end": {"line": 0, "character": 5},
                    },
                    "message": "Unexpected token",
                    "severity": DIAGNOSTIC_SEVERITY_ERROR,
                    "code": 101,
                    "source": "gdscript",
                },
                {
                    "range": {
                        "start": {"line": 1, "character": 0},
                        "end": {"line": 1, "character": 3},
                    },
                    "message": "Unused variable",
                    "severity": 2,  # Warning
                },
            ],
        },
    }
    client._handle_message(fake_message)

    assert len(received) == 1
    uri, diags = received[0]
    assert uri == "file:///tmp/test.gd"
    assert len(diags) == 2
    assert diags[0]["message"] == "Unexpected token"
    assert diags[0]["severity"] == DIAGNOSTIC_SEVERITY_ERROR
    assert diags[1]["message"] == "Unused variable"

    # The diagnostics must also be cached so ``apply_edit`` can poll them.
    assert client._last_diagnostics["file:///tmp/test.gd"] == diags
    assert client._diagnostics_event.is_set()


def test_diagnostics_handler_replacement() -> None:
    """Calling ``on_diagnostics`` again replaces the previous callback."""
    pytest.importorskip("pylsp_jsonrpc")
    client = GodotLSPClient()
    first: list[tuple[str, list[dict]]] = []
    second: list[tuple[str, list[dict]]] = []
    client.on_diagnostics(lambda uri, d: first.append((uri, d)))
    client.on_diagnostics(lambda uri, d: second.append((uri, d)))

    client._handle_message(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {"uri": "file:///x.gd", "diagnostics": []},
        }
    )
    assert first == []
    assert len(second) == 1


# ---------------------------------------------------------------------------
# apply_text_edits (pure helper)
# ---------------------------------------------------------------------------


def test_apply_text_edits_insert() -> None:
    """An insert edit (start == end) inserts text at the position."""
    text = "extends Node\n"
    edits = [
        {
            "range": {
                "start": {"line": 0, "character": 7},
                "end": {"line": 0, "character": 7},
            },
            "newText": "2D",
        }
    ]
    assert apply_text_edits(text, edits) == "extends2D Node\n"


def test_apply_text_edits_replace() -> None:
    """A replace edit overwrites the characters in [start, end)."""
    text = "extends Node\n"
    edits = [
        {
            "range": {
                "start": {"line": 0, "character": 8},
                "end": {"line": 0, "character": 12},
            },
            "newText": "Sprite2D",
        }
    ]
    assert apply_text_edits(text, edits) == "extends Sprite2D\n"


def test_apply_text_edits_delete() -> None:
    """An edit with ``newText == ""`` deletes the range."""
    text = "extends Node2D Node\n"
    edits = [
        {
            "range": {
                "start": {"line": 0, "character": 8},
                "end": {"line": 0, "character": 15},
            },
            "newText": "",
        }
    ]
    assert apply_text_edits(text, edits) == "extends Node\n"


def test_apply_text_edits_multiple_reverse_order() -> None:
    """Multiple edits are applied without invalidating earlier offsets."""
    text = "abc\ndef\nghi\n"
    edits = [
        # Replace "abc" on line 0 with "AAA"
        {
            "range": {
                "start": {"line": 0, "character": 0},
                "end": {"line": 0, "character": 3},
            },
            "newText": "AAA",
        },
        # Insert "X" at start of line 2
        {
            "range": {
                "start": {"line": 2, "character": 0},
                "end": {"line": 2, "character": 0},
            },
            "newText": "X",
        },
    ]
    assert apply_text_edits(text, edits) == "AAA\ndef\nXghi\n"


def test_apply_text_edits_empty_list_returns_unchanged() -> None:
    text = "unchanged\n"
    assert apply_text_edits(text, []) is text


# ---------------------------------------------------------------------------
# didChange versioning
# ---------------------------------------------------------------------------


def test_did_change_increments_version(tmp_path: Path) -> None:
    """Two consecutive ``didChange`` calls produce increasing version numbers."""
    pytest.importorskip("pylsp_jsonrpc")
    client = GodotLSPClient(project_path=str(tmp_path))
    captured: list[dict] = []
    client._send_message = lambda msg: captured.append(msg)  # type: ignore[assignment]

    file_path = tmp_path / "x.gd"
    client.did_change(str(file_path), "extends Node\n")
    client.did_change(str(file_path), "extends Node2D\n")

    assert len(captured) == 2
    v1 = captured[0]["params"]["textDocument"]["version"]
    v2 = captured[1]["params"]["textDocument"]["version"]
    assert v2 == v1 + 1

    # ``contentChanges`` must use full-sync (a single change with ``text``).
    assert captured[0]["params"]["contentChanges"] == [{"text": "extends Node\n"}]


# ---------------------------------------------------------------------------
# apply_edit end-to-end (mocked diagnostics wait)
# ---------------------------------------------------------------------------


def test_apply_edit_no_error_returns_true(tmp_path: Path) -> None:
    """``apply_edit`` returns ``True`` when no error diagnostics arrive."""
    pytest.importorskip("pylsp_jsonrpc")
    client = GodotLSPClient(project_path=str(tmp_path))

    # Stub out network I/O: capture didChange notifications, never send
    # anything to a real subprocess.
    captured: list[dict] = []
    client._send_message = lambda msg: captured.append(msg)  # type: ignore[assignment]

    file_path = tmp_path / "player.gd"
    file_path.write_text("extends Node\n", encoding="utf-8")

    edits = [
        {
            "range": {
                "start": {"line": 0, "character": 8},
                "end": {"line": 0, "character": 12},
            },
            "newText": "Sprite2D",
        }
    ]

    # Pre-seed the diagnostics cache with a warning (severity 2).  No error
    # -> ``apply_edit`` must return True.
    uri = file_path_to_uri(str(file_path))
    client._last_diagnostics[uri] = [
        {"message": "x", "severity": 2},
    ]
    # Make the wait return immediately by pre-setting the event.
    client._diagnostics_event.set()
    # Patch the wait to be instant and not actually block.
    client._diagnostics_event.wait = lambda timeout=None: True  # type: ignore[assignment]

    result = client.apply_edit(str(file_path), edits)

    assert result is True
    # The file on disk must have been updated.
    assert file_path.read_text(encoding="utf-8") == "extends Sprite2D\n"
    # ``didChange`` must have been notified.
    assert any(
        m.get("method") == "textDocument/didChange" for m in captured
    )


def test_apply_edit_with_error_returns_false(tmp_path: Path) -> None:
    """``apply_edit`` returns ``False`` when an error diagnostic is published."""
    pytest.importorskip("pylsp_jsonrpc")
    client = GodotLSPClient(project_path=str(tmp_path))
    client._send_message = lambda msg: None  # type: ignore[assignment]

    file_path = tmp_path / "broken.gd"
    file_path.write_text("extends Node\n", encoding="utf-8")

    uri = file_path_to_uri(str(file_path))
    client._last_diagnostics[uri] = [
        {"message": "Parse error", "severity": DIAGNOSTIC_SEVERITY_ERROR},
    ]
    client._diagnostics_event.wait = lambda timeout=None: True  # type: ignore[assignment]

    result = client.apply_edit(str(file_path), [])
    assert result is False


# ---------------------------------------------------------------------------
# workspace/applyEdit inbound request
# ---------------------------------------------------------------------------


def test_handle_apply_edit_request_writes_file(tmp_path: Path) -> None:
    """Inbound ``workspace/applyEdit`` request edits files on disk."""
    pytest.importorskip("pylsp_jsonrpc")
    client = GodotLSPClient(project_path=str(tmp_path))

    captured: list[dict] = []
    client._send_message = lambda msg: captured.append(msg)  # type: ignore[assignment]

    file_path = tmp_path / "victim.gd"
    file_path.write_text("hello world\n", encoding="utf-8")
    uri = file_path_to_uri(str(file_path))

    params = {
        "edit": {
            "changes": {
                uri: [
                    {
                        "range": {
                            "start": {"line": 0, "character": 0},
                            "end": {"line": 0, "character": 5},
                        },
                        "newText": "goodbye",
                    }
                ]
            }
        }
    }
    result = client._handle_apply_edit_request(params)
    assert result == {"applied": True}
    assert file_path.read_text(encoding="utf-8") == "goodbye world\n"


# ---------------------------------------------------------------------------
# URI helpers
# ---------------------------------------------------------------------------


def test_file_path_to_uri_roundtrip(tmp_path: Path) -> None:
    """``file_path_to_uri`` and ``uri_to_file_path`` are inverse operations."""
    pytest.importorskip("pylsp_jsonrpc")
    p = tmp_path / "x.gd"
    p.write_text("", encoding="utf-8")
    uri = file_path_to_uri(str(p))
    assert uri.startswith("file://")
    back = uri_to_file_path(uri)
    # On Windows the drive letter may produce a different but equivalent
    # string; compare via ``Path.resolve()`` for normalisation.
    assert Path(back).resolve() == p.resolve()


def test_uri_to_file_path_passthrough_for_non_file_uri() -> None:
    pytest.importorskip("pylsp_jsonrpc")
    assert uri_to_file_path("gdscript://something") == "gdscript://something"
