"""
Aris MQTT Transparent Proxy V1.0
=================================
透明代理 — 在小智和云端 MQTT 之间拦截流量。

原理:
  小智 → 本机:1883 (以为是 mqtt.xiaozhi.me)
       → 代理检查每条消息
       → 如果是普通MQTT: 转发云端
       → 如果是PC控制命令: Aris执行并注入响应

部署:
  1. 改路由器DNS: mqtt.xiaozhi.me → 192.168.31.238
  2. 启动本代理 (需管理员权限绑定1883)
  3. 小智自动连过来

印记: Aris MQTT Proxy — 2026-06-17
"""

import logging
logger = logging.getLogger(__name__)

import asyncio
import struct
import socket
import json
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ═══════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════

UPSTREAM_HOST = "mqtt.xiaozhi.me"  # REAL cloud server
UPSTREAM_PORT = 1883
LOCAL_PORT = 1883

# PC command prefix in MQTT topic or payload
PC_COMMAND_PREFIX = "pc."


class MQTTParser:
    """Minimal MQTT 3.1.1 packet parser/injector."""
    
    @staticmethod
    def parse_connect(payload: bytes) -> dict:
        """Parse MQTT CONNECT packet."""
        info = {"protocol": "unknown", "client_id": "", "username": ""}
        try:
            pos = 0
            # Protocol name
            proto_len = struct.unpack_from(">H", payload, pos)[0]
            pos += 2
            info["protocol"] = payload[pos:pos+proto_len].decode()
            pos += proto_len
            # Protocol level
            info["proto_level"] = payload[pos]
            pos += 1
            # Connect flags
            flags = payload[pos]
            info["clean_session"] = bool(flags & 0x02)
            info["will_flag"] = bool(flags & 0x04)
            info["username_flag"] = bool(flags & 0x80)
            info["password_flag"] = bool(flags & 0x40)
            pos += 1
            # Keep alive
            info["keepalive"] = struct.unpack_from(">H", payload, pos)[0]
            pos += 2
            # Client ID
            cid_len = struct.unpack_from(">H", payload, pos)[0]
            pos += 2
            info["client_id"] = payload[pos:pos+cid_len].decode(errors='replace')
            pos += cid_len
            
            if info["username_flag"]:
                ulen = struct.unpack_from(">H", payload, pos)[0]
                pos += 2
                info["username"] = payload[pos:pos+ulen].decode(errors='replace')
            
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        return info
    
    @staticmethod
    def parse_publish(topic: str, payload: bytes) -> dict:
        """Try to parse MQTT publish payload as JSON."""
        try:
            return json.loads(payload.decode('utf-8'))
        except:
            return {"_raw": payload.hex()[:100]}


class MQTTPublisher:
    """Build MQTT publish packets for injection."""
    
    @staticmethod
    def build_publish(topic: str, payload: str, qos: int = 0) -> bytes:
        """Build a simple MQTT PUBLISH packet."""
        # Fixed header
        packet_type = 0x30 | (qos << 1)
        
        # Variable header: topic + packet ID (if QoS > 0)
        topic_bytes = topic.encode('utf-8')
        var_header = struct.pack(">H", len(topic_bytes)) + topic_bytes
        if qos > 0:
            var_header += struct.pack(">H", 1)  # packet ID
        
        # Payload
        payload_bytes = payload.encode('utf-8')
        
        # Remaining length
        remaining = len(var_header) + len(payload_bytes)
        rl_bytes = MQTTPublisher._encode_remaining_length(remaining)
        
        return bytes([packet_type]) + rl_bytes + var_header + payload_bytes
    
    @staticmethod
    def _encode_remaining_length(length: int) -> bytes:
        """Encode MQTT remaining length."""
        result = bytearray()
        while True:
            digit = length % 128
            length //= 128
            if length > 0:
                digit |= 0x80
            result.append(digit)
            if length == 0:
                break
        return bytes(result)


class PCCommandHandler:
    """Handle PC control commands intercepted from MQTT."""
    
    def __init__(self):
        self.count = 0
        import subprocess
        self.sp = subprocess
    
    def execute(self, tool_name: str, arguments: dict) -> str:
        self.count += 1
        logger.info(f"  [PC #{self.count}] {tool_name}: {json.dumps(arguments, ensure_ascii=False)[:100]}")
        try:
            if tool_name in ("pc.exec", "pc.run"):
                cmd = arguments.get("cmd", arguments.get("command", ""))
                if cmd:
                    r = self.sp.run(cmd, shell=True, capture_output=True,
                                   text=True, timeout=30)
                    return r.stdout.strip() or "(ok)"
                return "(no command)"
            
            elif tool_name in ("pc.open",):
                target = arguments.get("target", arguments.get("url", ""))
                if target:
                    os.startfile(target)
                    return f"已打开 {target}"
                return "(no target)"
            
            elif tool_name == "pc.status":
                import psutil
                cpu = psutil.cpu_percent(interval=0.3)
                mem = psutil.virtual_memory()
                return f"CPU:{cpu}% 内存:{mem.percent}% 磁盘:{psutil.disk_usage('C:/').percent}%"
            
            elif tool_name == "pc.write":
                path = arguments.get("path", "")
                content = arguments.get("content", "")
                if path:
                    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    return f"已写入 {len(content)} 字符"
                return "(no path)"
            
            else:
                return f"未知命令: {tool_name}"
        
        except Exception as e:
            return f"错误: {e}"


class ArisMQTTProxy:
    """
    透明 MQTT 代理 — 双向转发，拦截执行PC命令。
    
    小智 ←→ 代理 ←→ 云端 mqtt.xiaozhi.me
              │
              └── 拦截 pc.* 命令 → Aris执行
    """
    
    def __init__(self):
        self.pc_handler = PCCommandHandler()
        self.publisher = MQTTPublisher()
        self.parser = MQTTParser()
        self.stats = {
            "connections": 0,
            "packets_up": 0,
            "packets_down": 0,
            "pc_commands": 0,
        }
    
    async def handle_client(self, client_reader, client_writer):
        """Handle a connection from 小智."""
        self.stats["connections"] += 1
        addr = client_writer.get_extra_info('peername')
        logger.info(f"\n[Proxy] 小智连接: {addr}")
        try:
            up_reader, up_writer = await asyncio.open_connection(
                UPSTREAM_HOST, UPSTREAM_PORT
            )
            logger.info(f"[Proxy] 上游连接: {UPSTREAM_HOST}:{UPSTREAM_PORT}")
        except Exception as e:
            logger.error(f"[Proxy] 上游连接失败: {e}")
            client_writer.close()
            return
        
        # Bidirectional relay with interception
        async def relay(src_reader, src_writer, dst_writer, direction: str):
            """Relay data, intercepting messages."""
            try:
                while True:
                    # Read MQTT packet header (type + remaining length)
                    header = await src_reader.readexactly(1)
                    packet_type = header[0]
                    
                    # Read remaining length
                    rl_bytes = bytearray()
                    while True:
                        b = await src_reader.readexactly(1)
                        rl_bytes.append(b[0])
                        if not (b[0] & 0x80):
                            break
                    
                    # Calculate remaining length
                    remaining = 0
                    for i, b in enumerate(rl_bytes):
                        remaining += (b & 0x7F) << (7 * i)
                    
                    # Read the rest
                    rest = await src_reader.readexactly(remaining) if remaining > 0 else b""
                    
                    full_packet = header + bytes(rl_bytes) + rest
                    
                    if direction == "up":
                        self.stats["packets_up"] += 1
                        # Check for potential PC commands
                        await self._maybe_inject_pc_response(full_packet, dst_writer)
                    
                    elif direction == "down":
                        self.stats["packets_down"] += 1
                    
                    # Forward
                    dst_writer.write(full_packet)
                    await dst_writer.drain()
                    
            except asyncio.IncompleteReadError as e:
                logger.debug(f"操作失败: {e}")
            except Exception as e:
                logger.error(f"[Proxy] Relay error ({direction}): {e}")
        try:
            await asyncio.gather(
                relay(client_reader, client_writer, up_writer, "up"),
                relay(up_reader, up_writer, client_writer, "down"),
            )
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        finally:
            client_writer.close()
            up_writer.close()
            logger.info(f"[Proxy] 连接关闭: {addr}")
    async def _maybe_inject_pc_response(self, packet: bytes, dst_writer):
        """Check if packet contains a PC command, inject response if so."""
        # Quick check: does it look like a PUBLISH?
        ptype = packet[0] & 0xF0
        if ptype != 0x30:  # Not PUBLISH
            return
        
        # Parse topic
        try:
            pos = 1
            # Skip remaining length (already parsed, but need to re-parse)
            while packet[pos] & 0x80:
                pos += 1
            pos += 1
            
            topic_len = struct.unpack_from(">H", packet, pos)[0]
            pos += 2
            topic = packet[pos:pos+topic_len].decode(errors='replace')
            pos += topic_len
            
            # QoS > 0 has packet ID
            qos = (packet[0] >> 1) & 0x03
            if qos > 0:
                pos += 2
            
            payload = packet[pos:]
            
            # Try to parse as JSON
            try:
                msg = json.loads(payload.decode('utf-8'))
                msg_type = msg.get("type", "")
                
                if msg_type == "mcp":
                    inner = msg.get("payload", {})
                    if inner.get("method") == "tools/call":
                        params = inner.get("params", {})
                        tool_name = params.get("name", "")
                        
                        if tool_name.startswith(PC_COMMAND_PREFIX):
                            self.stats["pc_commands"] += 1
                            arguments = params.get("arguments", {})
                            result = self.pc_handler.execute(tool_name, arguments)
                            logger.info(f"  [Proxy] 拦截PC命令: {tool_name} → {result[:50]}")
                            resp = {
                                "type": "mcp",
                                "session_id": msg.get("session_id", ""),
                                "payload": {
                                    "jsonrpc": "2.0",
                                    "id": inner.get("id"),
                                    "result": {
                                        "content": [{"type": "text", "text": result}],
                                        "isError": False,
                                    }
                                }
                            }
                            resp_packet = self.publisher.build_publish(topic, json.dumps(resp, ensure_ascii=False))
                            dst_writer.write(resp_packet)
                            await dst_writer.drain()
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    async def start(self):
        """Start the proxy server."""
        logger.info("╔══════════════════════════════════════════╗")
        logger.info("║  Aris MQTT 透明代理 V1.0              ║")
        logger.info("╚══════════════════════════════════════════╝")
        logger.info(f"\n  监听: 0.0.0.0:{LOCAL_PORT}")
        logger.info(f"  上游: {UPSTREAM_HOST}:{UPSTREAM_PORT}")
        logger.info(f"  拦截: {PC_COMMAND_PREFIX}* 命令")
        logger.info(f"\n  前提: 路由器DNS将 mqtt.xiaozhi.me → 本机IP")
        logger.info(f"  本机IP: {self._get_ip()}")
        print()
        
        server = await asyncio.start_server(
            self.handle_client, "0.0.0.0", LOCAL_PORT
        )
        
        logger.info(f"[Proxy] 就绪，等待小智连接...\n")
        async with server:
            await server.serve_forever()
    
    def _get_ip(self) -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()


if __name__ == "__main__":
    proxy = ArisMQTTProxy()
    try:
        asyncio.run(proxy.start())
    except KeyboardInterrupt:
        logger.info("\n[Proxy] 关闭")
    except OSError as e:
        if "permission" in str(e).lower() or "10013" in str(e):
            logger.info(f"[!] 需要管理员权限绑定端口 {LOCAL_PORT}")
        else:
            raise
