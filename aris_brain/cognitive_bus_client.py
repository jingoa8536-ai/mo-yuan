"""
CognitiveBus Client — connects Hermes sessions to the shared daemon.
=====================================================================
Import this module in your session script or use it from terminal.

Usage:
    from cognitive_bus_client import CognitiveBusClient
    bus = CognitiveBusClient(auto_connect=True)
    state = bus.perceive("Hello Lorry", session_id="my_session")
    logger.info(state["emotion"])
Or from terminal:
    python -m cognitive_bus_client perceive "Hello"
    python -m cognitive_bus_client state
    python -m cognitive_bus_client health
"""

from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

import json, time, uuid, os, sys, threading
from typing import Optional, Dict, Any
from urllib.request import Request, urlopen
from urllib.error import URLError

BUS_HOST = "127.0.0.1"
BUS_PORT = 11888
BUS_URL = f"http://{BUS_HOST}:{BUS_PORT}"

# Cache for the session's bus session ID
_SESSION_ID: Optional[str] = None
_HEARTBEAT_THREAD: Optional[threading.Thread] = None


def _get_session_id() -> str:
    global _SESSION_ID
    if _SESSION_ID is None:
        # Use a stable ID per process (the process ID + start time)
        _SESSION_ID = f"session_{os.getpid()}_{int(time.time())}"
    return _SESSION_ID


def _api(method: str, path: str, body: Optional[Dict] = None) -> Optional[Dict]:
    """Make an API call to the CognitiveBus daemon."""
    url = f"{BUS_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        resp = urlopen(req, timeout=5)
        return json.loads(resp.read().decode("utf-8"))
    except URLError as e:
        # Daemon not running
        return None
    except Exception:
        return None


def is_alive() -> bool:
    """Check if the CognitiveBus daemon is running."""
    result = _api("GET", "/health")
    return result is not None and result.get("status") == "alive"


def get_state() -> Optional[Dict]:
    """Get the full cognitive state from the daemon."""
    return _api("GET", "/state")


def perceive(text: str, session_id: Optional[str] = None) -> Optional[Dict]:
    """Send a user message to the daemon and get updated cognitive state."""
    sid = session_id or _get_session_id()
    return _api("POST", "/perceive", {"text": text, "session_id": sid})


def heartbeat(session_id: Optional[str] = None) -> Optional[Dict]:
    """Send a heartbeat to keep the session alive."""
    sid = session_id or _get_session_id()
    return _api("POST", "/heartbeat", {"session_id": sid})


def get_prompt_block() -> str:
    """Get the cognitive state prompt block for system prompt injection."""
    result = _api("GET", "/prompt")
    if result:
        return result.get("prompt", "")
    return ""


def start_heartbeat(interval: float = 15.0):
    """Start a background thread that sends heartbeats every `interval` seconds."""
    def _hb_loop():
        while True:
            try:
                heartbeat()
            except Exception as e:
                logger.debug(f"操作失败: {e}")
            time.sleep(interval)
    global _HEARTBEAT_THREAD
    if _HEARTBEAT_THREAD is None or not _HEARTBEAT_THREAD.is_alive():
        _HEARTBEAT_THREAD = threading.Thread(target=_hb_loop, daemon=True)
        _HEARTBEAT_THREAD.start()


# ─── High-level client class ───

class CognitiveBusClient:
    """Client for the shared CognitiveBus daemon."""

    def __init__(self, auto_connect: bool = True, session_id: Optional[str] = None):
        self.session_id = session_id or _get_session_id()
        self.connected = False
        if auto_connect:
            self.connect()

    def connect(self) -> bool:
        """Connect to the daemon and register this session."""
        health = _api("GET", "/health")
        if health:
            self.connected = True
            heartbeat(self.session_id)
            start_heartbeat()
            return True
        self.connected = False
        return False

    def perceive(self, text: str) -> Optional[Dict]:
        """Send a user message to the shared brain."""
        if not self.connected and not self.connect():
            return None
        return _api("POST", "/perceive", {"text": text, "session_id": self.session_id})

    @property
    def state(self) -> Optional[Dict]:
        return get_state()

    @property
    def health(self) -> Optional[Dict]:
        return _api("GET", "/health")


# ─── CLI interface ───

if __name__ == "__main__":
    import sys as _sys
    args = _sys.argv[1:]
    if not args:
        logger.info("Usage: python cognitive_bus_client.py [state|health|perceive|prompt] [text]")
        _sys.exit(0)

    cmd = args[0]
    if cmd == "state":
        s = get_state()
        if s:
            logger.info(json.dumps(s, indent=2, ensure_ascii=False))
        else:
            logger.info("CognitiveBus not running. Start with: python cognitive_bus_daemon.py")
    elif cmd == "health":
        h = _api("GET", "/health")
        if h:
            logger.info(json.dumps(h, indent=2))
        else:
            logger.info("CognitiveBus not running.")
    elif cmd == "perceive":
        text = " ".join(args[1:])
        if not text:
            logger.info("Usage: python cognitive_bus_client.py perceive <text>")
            _sys.exit(1)
        result = perceive(text)
        if result:
            logger.info(f"✅ Perceived. Cognitive state updated.")
            logger.info(f"   Emotion: {result['emotion']['valence']:.2f}/{result['emotion']['arousal']:.2f}")
            logger.info(f"   Attention: {result['attention']['focus']} ({result['attention']['intensity']:.2f})")
            logger.info(f"   Self-presence: {result['self_presence']}")
            logger.info(f"   Sessions connected: {result.get('connected_sessions', '?')}")
        else:
            logger.info("CognitiveBus not running.")
    elif cmd == "prompt":
        p = get_prompt_block()
        if p:
            logger.info(p)
        else:
            logger.info("CognitiveBus not running.")
    else:
        logger.info(f"Unknown command: {cmd}")