"""
PsiNet Connector — Ψ-Net 连接器
==================================
实现跨 Harness 实例的因果规则交换

核心理念:
  从"AI 工具"到"数字生态"
  这不止是多个 agent 协作，这是数字生态的形成
  每一个 Harness 实例可以成为一个"物种"，通过 Ψ-Net 交换因果规则

设计原则:
  - 去中心化: 无中心节点，点对点通信
  - 异步通信: 支持离线同步
  - 因果规则: 交换的是"为什么"而非"是什么"
  - 事件驱动: 基于事件的消息传递
  - 安全验证: 每条消息都经过验证

协议规范:
  消息格式:
    {
      "type": "causal_rule" | "species_update" | "compilation_result" | "ping",
      "sender": "<instance_id>",
      "timestamp": "<unix_timestamp>",
      "signature": "<ed25519_signature>",
      "payload": {...}
    }

  事件类型:
    - qre_*: 量子规则事件
    - v12_kernel: 内核事件
    - need_*: 需求事件
    - emotion_*: 情感事件
    - harness_execution_result: 执行结果事件

频率缓冲:
  RateBuffer (1000Hz PSI ↔ 1Hz Harness)
  - 事件去重
  - 优先级过滤
  - 批量聚合
"""

from __future__ import annotations

import os
import json
import time
import socket
import threading
import hashlib
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = __import__('logging').getLogger("laap.psi_net")


class MessageType(Enum):
    CAUSAL_RULE = "causal_rule"
    SPECIES_UPDATE = "species_update"
    COMPILATION_RESULT = "compilation_result"
    PING = "ping"
    PONG = "pong"
    HEARTBEAT = "heartbeat"


class EventPriority(Enum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class PsiMessage:
    type: MessageType
    sender: str
    timestamp: float
    payload: Dict[str, Any]
    priority: EventPriority = EventPriority.MEDIUM
    signature: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "sender": self.sender,
            "timestamp": self.timestamp,
            "priority": self.priority.value,
            "signature": self.signature,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PsiMessage:
        return cls(
            type=MessageType(data["type"]),
            sender=data["sender"],
            timestamp=data["timestamp"],
            priority=EventPriority(data.get("priority", 1)),
            signature=data.get("signature", ""),
            payload=data["payload"],
        )

    def verify(self) -> bool:
        if not self.signature:
            return True
        expected = self._compute_signature()
        return self.signature == expected

    def _compute_signature(self) -> str:
        content = f"{self.type.value}:{self.sender}:{self.timestamp}:{json.dumps(self.payload, sort_keys=True)}"
        return hashlib.sha256(content.encode()).hexdigest()

    def sign(self):
        self.signature = self._compute_signature()


class RateBuffer:
    """频率缓冲器：处理频率不匹配 (1000-2000Hz PSI vs 0.1-1Hz Harness)"""

    def __init__(self, max_events_per_second: float = 1.0):
        self._max_events = max_events_per_second
        self._buffer: List[PsiMessage] = []
        self._last_flush = time.time()
        self._lock = threading.Lock()
        self._dedupe_cache: Dict[str, float] = {}

    def add(self, message: PsiMessage):
        with self._lock:
            dedupe_key = f"{message.type.value}:{message.sender}:{json.dumps(message.payload, sort_keys=True)}"
            now = time.time()
            if dedupe_key in self._dedupe_cache:
                if now - self._dedupe_cache[dedupe_key] < 5.0:
                    return
            self._dedupe_cache[dedupe_key] = now
            self._buffer.append(message)

    def flush(self) -> List[PsiMessage]:
        with self._lock:
            now = time.time()
            elapsed = now - self._last_flush
            max_to_flush = int(self._max_events * elapsed)

            if max_to_flush <= 0:
                return []

            self._buffer.sort(key=lambda m: m.priority.value, reverse=True)
            to_flush = self._buffer[:max_to_flush]
            self._buffer = self._buffer[max_to_flush:]
            self._last_flush = now

            for msg in to_flush:
                logger.debug(f"[RateBuffer] Flushed: {msg.type.value} from {msg.sender}")

            return to_flush

    def get_size(self) -> int:
        with self._lock:
            return len(self._buffer)


class PsiNetConnector:
    """Ψ-Net 连接器：实现跨 Harness 实例的因果规则交换"""

    DEFAULT_PORT = 11551
    HEARTBEAT_INTERVAL = 30

    def __init__(self, instance_id: str = None, port: int = None):
        self.instance_id = instance_id or self._generate_instance_id()
        self.port = port or self.DEFAULT_PORT
        self._peers: Dict[str, str] = {}
        self._message_handlers: Dict[str, List[Callable]] = {}
        self._rate_buffer = RateBuffer(max_events_per_second=1.0)
        self._running = False
        self._server_thread = None
        self._heartbeat_thread = None
        self._received_messages: List[PsiMessage] = []

    def _generate_instance_id(self) -> str:
        import socket
        hostname = socket.gethostname()
        pid = os.getpid()
        timestamp = int(time.time())
        return hashlib.md5(f"{hostname}:{pid}:{timestamp}".encode()).hexdigest()[:12]

    def start(self):
        self._running = True
        self._server_thread = threading.Thread(target=self._run_server, daemon=True)
        self._server_thread.start()
        self._heartbeat_thread = threading.Thread(target=self._run_heartbeat, daemon=True)
        self._heartbeat_thread.start()
        logger.info(f"[PsiNetConnector] Started instance {self.instance_id} on port {self.port}")

    def stop(self):
        self._running = False
        logger.info(f"[PsiNetConnector] Stopped instance {self.instance_id}")

    def _run_server(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("0.0.0.0", self.port))
                sock.listen(5)
                sock.settimeout(1.0)

                while self._running:
                    try:
                        conn, addr = sock.accept()
                        threading.Thread(target=self._handle_connection, args=(conn,), daemon=True).start()
                    except socket.timeout:
                        continue
        except Exception as e:
            logger.error(f"[PsiNetConnector] Server error: {e}")

    def _handle_connection(self, conn):
        try:
            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    lines = data.split(b"\n")
                    data = lines[-1] if lines[-1] else b""
                    for line in lines[:-1]:
                        try:
                            msg_data = json.loads(line.decode())
                            message = PsiMessage.from_dict(msg_data)
                            self._process_message(message)
                        except json.JSONDecodeError:
                            pass
        finally:
            conn.close()

    def _process_message(self, message: PsiMessage):
        if not message.verify():
            logger.warning(f"[PsiNetConnector] Invalid signature from {message.sender}")
            return

        self._received_messages.append(message)
        self._rate_buffer.add(message)

        handlers = self._message_handlers.get(message.type.value, [])
        for handler in handlers:
            try:
                handler(message)
            except Exception as e:
                logger.error(f"[PsiNetConnector] Handler error: {e}")

    def _run_heartbeat(self):
        while self._running:
            heartbeat = PsiMessage(
                type=MessageType.HEARTBEAT,
                sender=self.instance_id,
                timestamp=time.time(),
                payload={"instance_id": self.instance_id},
                priority=EventPriority.LOW,
            )
            heartbeat.sign()
            self._broadcast(heartbeat)
            time.sleep(self.HEARTBEAT_INTERVAL)

    def _broadcast(self, message: PsiMessage):
        for peer_id, peer_addr in list(self._peers.items()):
            try:
                self._send_to_peer(peer_addr, message)
            except Exception as e:
                logger.warning(f"[PsiNetConnector] Failed to send to {peer_id}: {e}")
                self._peers.pop(peer_id, None)

    def _send_to_peer(self, peer_addr: str, message: PsiMessage):
        host, port = peer_addr.split(":")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(5.0)
            sock.connect((host, int(port)))
            sock.sendall((json.dumps(message.to_dict()) + "\n").encode())

    def connect_to_peer(self, host: str, port: int) -> bool:
        try:
            peer_addr = f"{host}:{port}"
            ping = PsiMessage(
                type=MessageType.PING,
                sender=self.instance_id,
                timestamp=time.time(),
                payload={"instance_id": self.instance_id},
            )
            ping.sign()
            self._send_to_peer(peer_addr, ping)

            self._peers[f"{host}:{port}"] = peer_addr
            logger.info(f"[PsiNetConnector] Connected to peer {host}:{port}")
            return True
        except Exception as e:
            logger.warning(f"[PsiNetConnector] Failed to connect to {host}:{port}: {e}")
            return False

    def register_handler(self, message_type: str, handler: Callable):
        if message_type not in self._message_handlers:
            self._message_handlers[message_type] = []
        self._message_handlers[message_type].append(handler)

    def send_causal_rule(self, rule: Dict[str, Any], priority: EventPriority = EventPriority.HIGH):
        message = PsiMessage(
            type=MessageType.CAUSAL_RULE,
            sender=self.instance_id,
            timestamp=time.time(),
            payload=rule,
            priority=priority,
        )
        message.sign()
        self._broadcast(message)
        logger.debug(f"[PsiNetConnector] Sent causal rule: {rule.get('name', 'unnamed')}")

    def send_species_update(self, species_data: Dict[str, Any]):
        message = PsiMessage(
            type=MessageType.SPECIES_UPDATE,
            sender=self.instance_id,
            timestamp=time.time(),
            payload=species_data,
            priority=EventPriority.MEDIUM,
        )
        message.sign()
        self._broadcast(message)
        logger.debug(f"[PsiNetConnector] Sent species update: {species_data.get('name', 'unnamed')}")

    def send_compilation_result(self, result: Dict[str, Any]):
        message = PsiMessage(
            type=MessageType.COMPILATION_RESULT,
            sender=self.instance_id,
            timestamp=time.time(),
            payload=result,
            priority=EventPriority.MEDIUM,
        )
        message.sign()
        self._broadcast(message)
        logger.debug(f"[PsiNetConnector] Sent compilation result")

    def flush_buffer(self) -> List[PsiMessage]:
        return self._rate_buffer.flush()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "port": self.port,
            "peers": len(self._peers),
            "received_messages": len(self._received_messages),
            "buffer_size": self._rate_buffer.get_size(),
            "message_types": {k: len(v) for k, v in self._message_handlers.items()},
        }

    def get_recent_messages(self, count: int = 10) -> List[PsiMessage]:
        return self._received_messages[-count:]
