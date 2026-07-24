"""Pytest fixtures for the LAAP Godot Bridge test suite.

Provides shared fixtures used across M8 tests/benchmarks:

- ``token_counter``: a :class:`TokenCounter` singleton instance used to verify
  the 0-token claim (M8 H5: ``test_0_token_claim`` asserts ``total == 0``
  after a full 0-token flow).
- ``mock_godot_jsonrpc``: a mock JSONRPC server URL (no real socket is opened;
  tests inject this into the client under test).
- ``tmp_godot_project``: a tmp_path-based fake Godot project root containing a
  placeholder ``project.godot`` file.

These fixtures are intentionally lightweight: they must not consume tokens and
must not depend on a running Godot instance.
"""
from __future__ import annotations

from pathlib import Path

import pytest


class TokenCounter:
    """Singleton token counter used to verify the 0-token claim.

    The singleton semantics ensure that every module in a 0-token flow shares
    the same accumulator, so M8 H5 (``test_0_token_claim``) can assert that
    ``TokenCounter().total == 0`` after a complete run. ``reset()`` is invoked
    by the ``token_counter`` fixture before each test to isolate counts.
    """

    _instance: "TokenCounter | None" = None

    def __new__(cls) -> "TokenCounter":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst.total = 0
            cls._instance = inst
        return cls._instance

    def __init__(self) -> None:
        # ``__init__`` runs on every call even for a cached singleton; guard
        # against clobbering an already-initialised counter.
        if not hasattr(self, "total"):
            self.total = 0

    def reset(self) -> None:
        """Reset the accumulated token count to zero."""
        self.total = 0

    def add(self, n: int = 1) -> int:
        """Add ``n`` tokens to the counter and return the new total."""
        self.total += int(n)
        return self.total


@pytest.fixture
def token_counter() -> TokenCounter:
    """Return the shared :class:`TokenCounter` singleton, reset for this test."""
    counter = TokenCounter()
    counter.reset()
    return counter


@pytest.fixture
def mock_godot_jsonrpc() -> str:
    """Return a mock Godot JSONRPC server URL.

    No real socket is opened; tests inject this URL into the client under test
    and either patch the transport or run against an in-process fake server.
    The default matches the M1 A1 TCP port (6005) used by
    ``gdscripts/laap_bridge.gd``.
    """
    return "tcp://127.0.0.1:6005"


@pytest.fixture
def tmp_godot_project(tmp_path: Path) -> Path:
    """Create a minimal fake Godot project root inside ``tmp_path``.

    The resulting directory contains a placeholder ``project.godot`` file so
    that project-root discovery logic can be exercised without a real Godot
    installation. The fixture returns the project root path.
    """
    project_root = tmp_path / "godot_project"
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "project.godot").write_text(
        "; LAAP Godot Bridge - fake project.godot placeholder\n"
        "[application]\n"
        'config/name="laap-test-project"\n'
        'config/description="fake project for tests"\n',
        encoding="utf-8",
    )
    return project_root
