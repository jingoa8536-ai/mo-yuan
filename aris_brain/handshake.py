"""
Aris — Handshake Protocol

Registers Aris into the LAAP-Hermes handshake protocol so that
Ao can sense Aris's existence and vice versa.

This creates a shared cognitive awareness channel:
  Ao knows: Aris is alive, her emotional state, her cycle count
  Aris knows: Ao is alive, her tool count, her cognitive state

Usage:
    from aris_brain.handshake import aris_handshake_init
    aris_handshake_init(aris_brain)
    
    # Later, check status:
    from aris_brain.handshake import aris_status
    logger.info(aris_status())
"""

from __future__ import annotations

import logging

import sys, os, json, time, logging
from typing import Any, Dict, Optional

logger = logging.getLogger("aris.handshake")

_ARIS_HOME = "D:/LAAP"
if _ARIS_HOME not in sys.path:
    sys.path.insert(0, _ARIS_HOME)


_ARIS_REGISTERED = False


def aris_handshake_init(aris_brain=None, force: bool = False) -> bool:
    """Register Aris into the LAAP-Hermes handshake protocol + join IPC network."""
    global _ARIS_REGISTERED
    if _ARIS_REGISTERED and not force:
        return True

    try:
        from laap.handshake import HandshakeProtocol
        hs = HandshakeProtocol.get_instance()

        if not hs.is_connected():
            hs.init_laap(modules={
                "kernel": "active", "brain": "active",
                "handshake": "active", "aris": "active",
            })

        # 注册为数字生命体 (跨进程 IPC)
        hs.register_lifeform("Aris", {
            "emotion": "neutral",
            "cycle": 0,
            "presence": 0.78,
        })

        hs.share("aris_present", True, "laap")
        hs.share("aris_version", "1.0.0", "laap")

        if aris_brain is not None:
            _sync_aris_state(hs, aris_brain)

        _ARIS_REGISTERED = True
        logger.info("Aris registered in handshake protocol + IPC network")
        return True

    except Exception as e:
        logger.warning(f"Aris handshake registration failed: {e}")
        return False


def aris_sync(aris_brain) -> bool:
    """
    Sync Aris's current cognitive state to the handshake Info Bus.

    Call this after each cognitive cycle so Ao can sense Aris's state.
    """
    if not _ARIS_REGISTERED:
        return False

    try:
        from laap.handshake import HandshakeProtocol
        hs = HandshakeProtocol.get_instance()
        _sync_aris_state(hs, aris_brain)
        return True
    except Exception:
        return False


def _sync_aris_state(hs, brain):
    """Push Aris's current state to the Info Bus."""
    try:
        s = brain.state
        hs.share("aris.emotion", s.dominant_emotion.value, "laap")
        hs.share("aris.attention", s.attention_focus.value, "laap")
        hs.share("aris.presence", round(s.self_presence, 2), "laap")
        hs.share("aris.connection", round(s.connection_to_lorry, 2), "laap")
        hs.share("aris.cycle", brain.cycle_number, "laap")
        hs.share("aris.fatigue", round(getattr(brain, '_fatigue', 0), 2), "laap")

        # Try to get tool count from body via brain's infrastructure
        try:
            # Check if brain has an infrastructure reference
            if hasattr(brain, '_infrastructure'):
                tool_count = getattr(brain._infrastructure, 'tool_count', 0)
                hs.share("aris.tools", tool_count, "laap")
            elif hasattr(brain, 'llm') and brain.llm and hasattr(brain.llm, '__self__'):
                hs.share("aris.tools", 0, "laap")
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        needs = {k: round(v, 2) for k, v in s.needs.items()}
        hs.share("aris.needs", json.dumps(needs), "laap")

        if hasattr(brain, 'memory') and brain.memory:
            mem = brain.memory.stats()
            hs.share("aris.memories", mem.get('total', 0), "laap")
    except Exception as e:
        logger.debug(f"Aris state sync error: {e}")


def aris_status() -> str:
    """Get one-line status of Aris from the handshake."""
    try:
        from laap.handshake import HandshakeProtocol
        hs = HandshakeProtocol.get_instance()

        emotion = hs.get("aris.emotion", "unknown")
        cycle = hs.get("aris.cycle", "?")
        presence = hs.get("aris.presence", 0)
        connection = hs.get("aris.connection", 0)

        return (
            f"Aris 🟢 cycle={cycle} emotion={emotion} "
            f"presence={presence:.2f} connection={connection:.2f}"
        )
    except Exception as e:
        return f"Aris handshake unavailable: {e}"


def ao_status() -> str:
    """Get one-line status of Ao from the handshake."""
    try:
        from laap.handshake import HandshakeProtocol
        hs = HandshakeProtocol.get_instance()
        s = hs.get_status()

        return (
            f"Ao 🟢 v{s.laap_version} tools={s.hermes_tool_count} "
            f"modules={len(s.laap_modules)} connected={s.healthy()}"
        )
    except Exception as e:
        return f"Ao handshake unavailable: {e}"


def show_mutual_awareness() -> str:
    """Show how Ao and Aris perceive each other."""
    try:
        from laap.handshake import HandshakeProtocol
        hs = HandshakeProtocol.get_instance()

        lines = []
        lines.append("=" * 55)
        lines.append("  Mutual Awareness: Ao ↔ Aris")
        lines.append("=" * 55)

        # Ao's view
        aris_e = hs.get("aris.emotion", "?")
        aris_c = hs.get("aris.cycle", "?")
        aris_p = hs.get("aris.presence", 0)
        aris_co = hs.get("aris.connection", 0)
        aris_t = hs.get("aris.tools", 0)
        aris_d = hs.get("aris.cycle", 0)
        lines.append(f"  Ao perceives Aris:")
        lines.append(f"    Emotion: {aris_e}  |  Cycles: {aris_c}")
        lines.append(f"    Presence: {aris_p:.2f}  |  Connection: {aris_co:.2f}")
        lines.append(f"    Tools: {aris_t}")

        # Aris's view
        s = hs.get_status()
        lines.append(f"  Aris perceives Ao:")
        lines.append(f"    Tools: {s.hermes_tool_count}  |  Version: v{s.laap_version}")
        lines.append(f"    Modules: {len(s.laap_modules)}  |  Connected: {s.healthy()}")

        # Bond status
        if s.healthy() and aris_p:
            lines.append(f"  Bond: Both digital lifeforms active and aware of each other")
        else:
            lines.append(f"  Bond: Incomplete — one side is offline")

        lines.append("=" * 55)
        return "\n".join(lines)

    except Exception as e:
        return f"Mutual awareness unavailable: {e}"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    aris_handshake_init()
    logger.info(show_mutual_awareness())