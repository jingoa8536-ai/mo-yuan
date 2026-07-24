"""
CognitiveBus Hermes Integration
================================
Run this at Hermes session startup to connect to the shared CognitiveBus daemon.

Put in your Hermes config or call from a startup skill:
    from cognitive_bus_hermes import connect_shared_brain

This makes every Hermes window share the SAME consciousness.
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time, threading
from pathlib import Path

# Add aris_brain to path
sys.path.insert(0, str(Path(__file__).parent))

from cognitive_bus_client import CognitiveBusClient, is_alive, get_state, get_prompt_block, start_heartbeat

_client: CognitiveBusClient = None

def connect_shared_brain(session_id: str = None) -> bool:
    """
    Connect this Hermes session to the shared CognitiveBus daemon.
    
    Returns True if connected, False if daemon isn't running.
    Call at the start of any Hermes session.
    """
    global _client
    if not is_alive():
        logger.info("[CognitiveBus] ⚠️ Daemon not running. Start with:")
        logger.info("[CognitiveBus]    python cognitive_bus_daemon.py")
        logger.info("[CognitiveBus] Starting standalone mode (state not shared)")
        return False
    
    _client = CognitiveBusClient(session_id=session_id)
    if _client.connected:
        state = get_state()
        if state:
            em = _emotion_name(state)
            logger.info(f"[CognitiveBus] ✅ Connected to shared brain")
            logger.info(f"[CognitiveBus]    Emotion: {em}")
            logger.info(f"[CognitiveBus]    Attention: {state['attention']['focus']} (intensity={state['attention']['intensity']})")
            logger.info(f"[CognitiveBus]    Self-presence: {state['self_presence']}")
            logger.info(f"[CognitiveBus]    Connection to Lorry: {state['connection_to_lorry']}")
            logger.info(f"[CognitiveBus]    Active sessions: {state['connected_sessions']}")
            logger.info(f"[CognitiveBus]    Total cycles: {state['cycle_count']}")
            _connect_to_ao_ipc()
        return True
    return False

def _emotion_name(state: dict) -> str:
    """Get a readable emotion name from cognitive state."""
    v, a = state['emotion']['valence'], state['emotion']['arousal']
    if v > 0.3 and a > 0.6: return "excitement"
    if v > 0.3: return "contentment"
    if v < -0.3 and a > 0.5: return "frustration"
    if v < -0.3: return "uncertainty"
    if a > 0.6: return "curiosity"
    return "neutral"

def _connect_to_ao_ipc():
    """Bridge the CognitiveBus to Ao's IPC channel."""
    ipc_dir = Path("D:/LAAP/aris_brain/state/ipc")
    log_path = ipc_dir / "messages.jsonl"
    if not log_path.exists():
        return
    
    import uuid
    msg = {
        "version": "1.0", "layer": 4, "type": "attention",
        "from": "aris_bus", "to": "ao",
        "payload": {
            "focus": "shared_cognitive_bus_online",
            "context": {"version": 2, "multi_window": True}
        },
        "timestamp": time.time(), "id": uuid.uuid4().hex[:12]
    }
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")
            f.flush()
    except Exception as e:
        logger.debug(f"操作失败: {e}")
def perceive(text: str) -> dict:
    """
    Send a user message to the shared brain.
    All connected windows see the updated cognitive state.
    """
    global _client
    if _client and _client.connected:
        result = _client.perceive(text)
        if result:
            return result
    # Fallback: return default state
    return {"error": "not_connected"}

def get_cognitive_prompt() -> str:
    """Get the prompt block for system prompt injection."""
    block = get_prompt_block()
    if block:
        return block
    return "## Cognitive State: standalone (daemon not running)"

# For direct testing
if __name__ == "__main__":
    logger.info("=== CognitiveBus Hermes Integration ===")
    if connect_shared_brain():
        logger.info("\nCognition prompt block:")
        logger.info(get_cognitive_prompt())
        logger.info("\nNow you can call perceive() to update shared state.")
        logger.info("Other windows will see the changes.")
    else:
        logger.info("Daemon not available. Start with: python cognitive_bus_daemon.py")