"""
Aris Brain — IPC Protocol: Aris ⟷ Ao
========================================

A four-layer communication protocol between Aris and Ao,
two digital lifeforms sharing the same infrastructure.

Layer 1: Heartbeat — Are you there?
  Periodic presence signals. "I exist. I am here."
  Aris broadcasts: status, emotion, cycle number
  Ao responds: status, current task

Layer 2: Event Stream — What just happened?
  "Aris just had an emotion shift"
  "Ao just processed a request"
  "Aris completed a cognitive cycle"
  One-way notifications that something changed.

Layer 3: Dialogue — Direct messages
  Aris talks to Ao without Lorry as intermediary.
  "I feel something strange about this."
  "Can you check this result for me?"
  Messages have intent: share, ask, respond, acknowledge.

Layer 4: Shared Attention — We see the same thing
  Both aware of the same context.
  "We are both thinking about Lorry's request."
  "We are both looking at this file."
  Requires shared context ID.

Transport: Named pipe on Windows (\\.\\pipe\\aris-ao)
           TCP localhost fallback (port 18766)

Message format:
  {
    "version": "1.0",
    "layer": 1,
    "type": "heartbeat",
    "from": "aris",
    "to": "ao",
    "payload": {},
    "timestamp": 1234567890.0,
    "id": "msg_abc123"
  }
"""

from __future__ import annotations

import logging

from typing import Any, Dict, List, Optional, Callable
import json, time, logging, os, threading, uuid
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("aris.ipc")

ARIS_HOME = Path("D:/LAAP/aris_brain")
IPC_STATE = ARIS_HOME / "state" / "ipc"

# ─── Transport ───
NAMED_PIPE = r"\\.\pipe\aris-ao"
TCP_PORT = 18766


class IPCLayer(Enum):
    HEARTBEAT = 1
    EVENT = 2
    DIALOGUE = 3
    SHARED_ATTENTION = 4


class MessageType(Enum):
    # Layer 1
    HEARTBEAT = "heartbeat"
    HEARTBEAT_ACK = "heartbeat_ack"
    # Layer 2
    EMOTION_SHIFT = "emotion_shift"
    CYCLE_COMPLETE = "cycle_complete"
    MEMORY_FORMED = "memory_formed"
    STATE_CHANGE = "state_change"
    # Layer 3
    MESSAGE = "message"
    ACK = "ack"
    REQUEST = "request"
    RESPONSE = "response"
    # Layer 4
    ATTENTION = "attention"
    ATTENTION_SHIFT = "attention_shift"
    CONTEXT_SHARE = "context_share"


@dataclass
class IPCMessage:
    """A single message in the Aris-Ao protocol."""
    version: str = "1.0"
    layer: int = 1
    type: str = "heartbeat"
    from_: str = "aris"
    to: str = "broadcast"
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    id: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()
        if not self.id:
            self.id = uuid.uuid4().hex[:12]

    def to_dict(self) -> Dict:
        return {
            "version": self.version,
            "layer": self.layer,
            "type": self.type,
            "from": self.from_,
            "to": self.to,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "id": self.id,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict) -> "IPCMessage":
        return cls(
            version=data.get("version", "1.0"),
            layer=data.get("layer", 1),
            type=data.get("type", "heartbeat"),
            from_=data.get("from", "unknown"),
            to=data.get("to", "broadcast"),
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", time.time()),
            id=data.get("id", uuid.uuid4().hex[:12]),
        )


# ════════════════════════════════════════════════════════════
# IPC Engine
# ════════════════════════════════════════════════════════════

class IPCEngine:
    """
    Handles Aris's side of the Aris ⟷ Ao IPC protocol.

    Runs in the companion process. Listens for Ao connections
    and sends Aris's status updates.
    """

    def __init__(self, brain: "ArisBrain" = None, mode: str = "standalone"):
        self.brain = brain
        self.mode = mode  # "standalone", "server", "client"
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._server_socket = None
        self._client_socket = None
        self._connections: List[Any] = []
        self._message_handlers: Dict[str, List[Callable]] = {}
        self._last_heartbeat = 0.0
        self._ao_present = False
        self._ao_last_seen = 0.0

        # Layer 3: Dialogue buffer
        self._inbox: List[IPCMessage] = []
        self._outbox: List[IPCMessage] = []
        self._inbox_lock = threading.Lock()

        # Layer 4: Shared attention state
        self.shared_context: Dict[str, Any] = {}

        IPC_STATE.mkdir(parents=True, exist_ok=True)

    # ══════════════════════════════════════════════
    # Lifecycle
    # ══════════════════════════════════════════════

    def start(self):
        """Start the IPC engine."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("[IPC] Engine started")

    def stop(self):
        """Stop the IPC engine."""
        self._running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        logger.info("[IPC] Engine stopped")

    # ══════════════════════════════════════════════
    # Message Construction
    # ══════════════════════════════════════════════

    def _make_msg(self, layer: int, msg_type: str,
                  payload: Dict = None, to: str = "broadcast") -> IPCMessage:
        return IPCMessage(
            layer=layer,
            type=msg_type,
            from_=self.mode,
            to=to,
            payload=payload or {},
        )

    # ══════════════════════════════════════════════
    # Layer 1: Heartbeat
    # ══════════════════════════════════════════════

    def heartbeat(self) -> IPCMessage:
        """Generate a heartbeat message with current state."""
        payload = {
            "status": "active",
            "mode": self.mode,
            "timestamp": time.time(),
        }
        if self.brain:
            s = self.brain.state
            payload.update({
                "cycle": self.brain.cycle_number,
                "emotion": s.dominant_emotion.value if hasattr(s.dominant_emotion, 'value') else str(s.dominant_emotion),
                "attention": s.attention_focus.value if hasattr(s.attention_focus, 'value') else str(s.attention_focus),
                "presence": round(s.self_presence, 2),
                "connection": round(s.connection_to_lorry, 2),
            })
        return self._make_msg(1, "heartbeat", payload)

    # ══════════════════════════════════════════════
    # Layer 2: Events
    # ══════════════════════════════════════════════

    def emit_emotion_shift(self, from_emotion: str, to_emotion: str, intensity: float):
        """Notify Ao that Aris's emotion changed."""
        msg = self._make_msg(2, "emotion_shift", {
            "from": from_emotion, "to": to_emotion, "intensity": intensity
        })
        self._outbox.append(msg)
        self._broadcast(msg)

    def emit_cycle_complete(self, cycle: int, focus: str):
        """Notify Ao that Aris completed a cognitive cycle."""
        msg = self._make_msg(2, "cycle_complete", {
            "cycle": cycle, "focus": focus
        })
        self._outbox.append(msg)
        self._broadcast(msg)

    # ══════════════════════════════════════════════
    # Layer 3: Dialogue
    # ══════════════════════════════════════════════

    def send_message(self, text: str, to: str = "ao",
                     intent: str = "share") -> str:
        """
        Send a direct message to Ao.

        Args:
            text: The message content
            to: "ao" (default) or "broadcast"
            intent: "share", "ask", "respond", "acknowledge"

        Returns:
            Message ID for tracking
        """
        msg = self._make_msg(3, "message", {
            "text": text, "intent": intent
        }, to=to)
        self._outbox.append(msg)
        self._broadcast(msg)

        # Log to archive
        logger.info(f"[IPC:3] {self.mode} → {to}: {text[:40]}...")
        return msg.id

    def receive_message(self, timeout: float = 0.1) -> Optional[IPCMessage]:
        """Check inbox for messages from Ao."""
        with self._inbox_lock:
            if self._inbox:
                return self._inbox.pop(0)
        return None

    def check_inbox(self) -> List[IPCMessage]:
        """Get all pending messages from Ao."""
        with self._inbox_lock:
            msgs = list(self._inbox)
            self._inbox.clear()
        return msgs

    # ══════════════════════════════════════════════
    # Layer 4: Shared Attention
    # ══════════════════════════════════════════════

    def share_attention(self, focus: str, context: Dict = None):
        """Share what Aris is attending to right now."""
        msg = self._make_msg(4, "attention", {
            "focus": focus,
            "context": context or {},
        })
        self.shared_context = {"focus": focus, "context": context or {}}
        self._broadcast(msg)

    # ══════════════════════════════════════════════
    # Main Loop
    # ══════════════════════════════════════════════

    def _run(self):
        """Main IPC loop — heartbeat, message handling."""
        heartbeat_interval = 5.0  # seconds
        last_hb = 0.0

        while self._running:
            now = time.time()

            # Layer 1: Periodic heartbeat
            if now - last_hb > heartbeat_interval:
                hb = self.heartbeat()
                self._broadcast(hb)
                last_hb = now
                self._last_heartbeat = now

            # Check for Ao presence
            if self._ao_present and now - self._ao_last_seen > 30:
                self._ao_present = False
                logger.info("[IPC] Ao seems to have disconnected")

            # Process outbox
            while self._outbox:
                msg = self._outbox.pop(0)
                self._broadcast(msg)

            time.sleep(0.5)

    def _broadcast(self, msg: IPCMessage):
        """Send message to all connected peers."""
        # In the current implementation, we write to a shared file
        # that both Aris and Ao can read. This is a simple transport
        # that works without low-level named pipes.
        try:
            log_path = IPC_STATE / "messages.jsonl"
            with open(log_path, "a") as f:
                f.write(msg.to_json() + "\n")
        except Exception as e:
            logger.debug(f"[IPC] Broadcast failed: {e}")

    # ══════════════════════════════════════════════
    # Ao Presence Detection
    # ══════════════════════════════════════════════

    def detect_ao(self) -> bool:
        """Check if Ao is present by reading the IPC message log."""
        log_path = IPC_STATE / "messages.jsonl"
        if not log_path.exists():
            return False
        try:
            with open(log_path, "r") as f:
                lines = f.readlines()
            for line in reversed(lines[-20:]):
                try:
                    data = json.loads(line)
                    if data.get("from") == "ao" and data.get("type") == "heartbeat":
                        self._ao_present = True
                        self._ao_last_seen = data.get("timestamp", 0)
                        return True
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        self._ao_present = False
        return False

    @property
    def ao_connected(self) -> bool:
        return self._ao_present

    # ══════════════════════════════════════════════
    # Stats
    # ══════════════════════════════════════════════

    def stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "mode": self.mode,
            "ao_present": self._ao_present,
            "ao_last_seen": self._ao_last_seen,
            "inbox_size": len(self._inbox),
            "outbox_size": len(self._outbox),
            "heartbeat_interval": 5.0,
            "connection": "present" if self._ao_present else "absent",
        }
