"""
Aris P4 Protocol V1.0
====================
JSON-based communication protocol between Aris-on-P4 and PC Bridge.

Transport: USB Serial (COM port) or WiFi TCP
Framing:   One JSON object per line (newline-delimited JSON / NDJSON)

Message Types:
  P4 → PC (commands to execute on computer):
    - exec:    Run terminal command
    - open:    Open URL/file
    - write:   Write file on PC
    - read:    Read file from PC
    - control: System control (volume, media, etc.)
    - status:  Heartbeat / status report

  PC → P4 (responses, events):
    - result:  Command execution result
    - event:   System event notification
    - error:   Error response

  P4 → PC (data):
    - sensor:  Sensor readings (camera, mic level, etc.)
    - speech:  Generated speech text / audio

Mark: Aris P4 协议 — 2026-06-17
"""

import logging
logger = logging.getLogger(__name__)

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Any
from enum import Enum


# ═══════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════

PROTOCOL_VERSION = "1.0"
MAX_MESSAGE_SIZE = 65536  # 64KB max per message
DEFAULT_BAUD_RATE = 115200


class Action(str, Enum):
    """Actions P4 can request from PC."""
    EXEC = "exec"           # Run terminal command
    OPEN = "open"           # Open URL or file
    WRITE = "write"         # Write file
    READ = "read"           # Read file
    CONTROL = "control"     # System control
    STATUS = "status"       # Heartbeat / status check


class ControlTarget(str, Enum):
    """System control targets."""
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    VOLUME_SET = "volume_set"
    MEDIA_PLAY = "media_play"
    MEDIA_PAUSE = "media_pause"
    MEDIA_NEXT = "media_next"
    MEDIA_PREV = "media_prev"
    SCREEN_LOCK = "screen_lock"
    SCREEN_OFF = "screen_off"
    SHUTDOWN = "shutdown"
    RESTART = "restart"


class ResponseStatus(str, Enum):
    """PC → P4 response status."""
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    DENIED = "denied"


class SensorType(str, Enum):
    """Sensor data types P4 can report."""
    CAMERA = "camera"       # Base64-encoded image
    MIC_LEVEL = "mic_level" # Audio level (0-100)
    TEMPERATURE = "temp"    # CPU temperature
    MOTION = "motion"       # PIR motion detected
    LIGHT = "light"         # Ambient light level


# ═══════════════════════════════════════════════
# Message Definitions
# ═══════════════════════════════════════════════

@dataclass
class Message:
    """Base message type."""
    msg_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    type: str = ""
    timestamp: float = field(default_factory=time.time)
    version: str = PROTOCOL_VERSION

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, data: str) -> "Message":
        d = json.loads(data.strip())
        msg_type = d.pop("type", "")
        
        # Route to correct subclass
        if msg_type == "request":
            return Request(**d)
        elif msg_type == "response":
            return Response(**d)
        elif msg_type == "sensor":
            return SensorData(**d)
        elif msg_type == "event":
            return Event(**d)
        else:
            return cls(**d, type=msg_type)


@dataclass
class Request(Message):
    """P4 → PC: request PC to do something."""
    type: str = "request"
    action: str = ""                # Action enum value
    params: Dict[str, Any] = field(default_factory=dict)
    timeout: float = 30.0           # Max wait seconds
    reply_to: Optional[str] = None  # msg_id to reply to, if any


@dataclass
class Response(Message):
    """PC → P4: result of a request."""
    type: str = "response"
    request_id: str = ""            # msg_id of the Request
    status: str = ResponseStatus.OK.value
    data: Any = None                # Result data
    error: Optional[str] = None     # Error message if status=error
    duration_ms: float = 0          # How long the command took


@dataclass
class SensorData(Message):
    """P4 → PC: sensor readings."""
    type: str = "sensor"
    sensor: str = ""                # SensorType enum value
    value: Any = None               # Sensor-specific value
    unit: str = ""                  # e.g. "lux", "celsius", "percent"


@dataclass
class Event(Message):
    """PC → P4: system events."""
    type: str = "event"
    event: str = ""                 # Event name
    payload: Dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════
# Convenience constructors
# ═══════════════════════════════════════════════

def make_exec(cmd: str, timeout: float = 30.0) -> Request:
    """Create a terminal execution request."""
    return Request(action=Action.EXEC.value, params={"command": cmd}, timeout=timeout)

def make_open(target: str) -> Request:
    """Create an open URL/file request."""
    return Request(action=Action.OPEN.value, params={"target": target})

def make_write(path: str, content: str) -> Request:
    """Create a file write request."""
    return Request(action=Action.WRITE.value, params={"path": path, "content": content})

def make_read(path: str, offset: int = 0, limit: int = 100) -> Request:
    """Create a file read request."""
    return Request(action=Action.READ.value, params={"path": path, "offset": offset, "limit": limit})

def make_control(target: ControlTarget, value: Any = None) -> Request:
    """Create a system control request."""
    params = {"target": target.value}
    if value is not None:
        params["value"] = value
    return Request(action=Action.CONTROL.value, params=params)

def make_response(request_id: str, status: str, data: Any = None,
                  error: str = None, duration_ms: float = 0) -> Response:
    """Create a response to a request."""
    return Response(
        request_id=request_id,
        status=status,
        data=data,
        error=error,
        duration_ms=duration_ms,
    )


# ═══════════════════════════════════════════════
# Framing helpers
# ═══════════════════════════════════════════════

def encode_message(msg: Message) -> bytes:
    """Encode a message as NDJSON bytes for transport."""
    return (msg.to_json() + "\n").encode("utf-8")

def decode_message(line: bytes) -> Optional[Message]:
    """Decode a single NDJSON line into a Message."""
    try:
        text = line.decode("utf-8").strip()
        if not text:
            return None
        return Message.from_json(text)
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError) as e:
        return None


# ═══════════════════════════════════════════════
# Protocol test
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    logger.info("=== Aris P4 Protocol Test ===\n")
    req = make_exec("echo hello from Aris")
    encoded = encode_message(req)
    logger.info(f"Request ({len(encoded)} bytes): {req.to_json()}")
    decoded = decode_message(encoded)
    logger.info(f"Decoded type: {decoded.type}, action: {decoded.action}")
    resp = make_response(req.msg_id, ResponseStatus.OK.value, 
                         data="hello from Aris\n", duration_ms=12.5)
    logger.info(f"\nResponse: {resp.to_json()}")
    rt = decode_message(encode_message(resp))
    logger.info(f"Round-trip OK: {rt.type == resp.type}")
    logger.info("\nProtocol V1.0 ready.")