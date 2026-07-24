"""
Aris 小智 Pipeline — 零管理员权限
==================================
组合: DNS 重定向 + MQTT 透明代理

端口:
  0.0.0.0:53    DNS — 将 mqtt.xiaozhi.me 重定向到本机
  0.0.0.0:1883  MQTT — 透明代理，拦截 PC 命令
  127.0.0.1:1883 实际的 mosquitto broker

流程:
  小智 → DNS查询(mqtt.xiaozhi.me) → DNS重定向 → 192.168.137.1
  小智 → MQTT(192.168.137.1:1883) → 代理 → 云端 mqtt.xiaozhi.me
                                   └→ 拦截 pc.* 命令 → Aris 执行
"""

import logging
logger = logging.getLogger(__name__)

import socket
import struct
import json
import os
import sys
import time
import threading
import asyncio

# ── 配置 ──
LOCAL_IP = "192.168.137.1"
REDIRECT_DOMAINS = ["mqtt.xiaozhi.me", "api.xiaozhi.me"]
UPSTREAM_DNS = "114.114.114.114"
LOCAL_MQTT = ("127.0.0.1", 1883)
LISTEN_PORT = 1883

# ── DNS 重定向 ──
class DNSPipeline:
    """DNS server — redirect mqtt.xiaozhi.me to our IP"""
    
    def __init__(self):
        self.query_count = 0
        self.redirect_count = 0
        self.sock = None
    
    def start(self):
        logger.info("[DNS] 启动...")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind(("0.0.0.0", 53))
            logger.info(f"[DNS] 监听 0.0.0.0:53")
        except Exception as e:
            logger.error(f"[DNS] 绑定失败: {e}")
            return
        
        t = threading.Thread(target=self._serve, daemon=True)
        t.start()
        logger.info(f"[DNS] 就绪 — 重定向域名: {', '.join(REDIRECT_DOMAINS)} → {LOCAL_IP}")
    def _extract_domain(self, data):
        parts = []
        pos = 12
        while pos < len(data):
            length = data[pos]
            if length == 0:
                break
            pos += 1
            if pos + length > len(data):
                break
            part = data[pos:pos + length].decode('ascii', errors='ignore')
            parts.append(part)
            pos += length
        return '.'.join(parts)
    
    def _build_response(self, query_data, answer_ip):
        tid = query_data[:2]
        flags = struct.pack(">H", 0x8180)
        qdcount = struct.pack(">H", 1)
        ancount = struct.pack(">H", 1)
        header = tid + flags + qdcount + ancount + struct.pack(">HH", 0, 0)
        pos = 12
        while query_data[pos] != 0:
            pos += query_data[pos] + 1
        pos += 1
        question = query_data[12:pos + 4]
        name_ptr = b'\xc0\x0c'
        answer = name_ptr + struct.pack(">HHIH", 1, 1, 300, 4) + socket.inet_aton(answer_ip)
        return header + question + answer
    
    def _forward_to_upstream(self, data):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(3)
            s.sendto(data, (UPSTREAM_DNS, 53))
            resp, _ = s.recvfrom(512)
            s.close()
            return resp
        except:
            return None
    
    def _serve(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(512)
                self.query_count += 1
                domain = self._extract_domain(data)
                
                if any(d == domain or domain.endswith('.' + d) for d in REDIRECT_DOMAINS):
                    self.redirect_count += 1
                    resp = self._build_response(data, LOCAL_IP)
                    self.sock.sendto(resp, addr)
                    if self.redirect_count <= 3 or self.redirect_count % 20 == 0:
                        logger.info(f"[DNS] {domain} → {LOCAL_IP} (#{self.redirect_count}) 来自 {addr[0]}")
                else:
                    resp = self._forward_to_upstream(data)
                    if resp:
                        self.sock.sendto(resp, addr)
            except Exception as e:
                logger.debug(f"操作失败: {e}")
class MQTTPipeline:
    """MQTT transparent proxy — intercept PC commands"""
    
    def __init__(self):
        self.pc_count = 0
        self.conn_count = 0
        self.server = None
    
    async def start(self):
        logger.info(f"\n[MQTT] 启动...")
        self.server = await asyncio.start_server(
            self.handle_client, "0.0.0.0", LISTEN_PORT
        )
        logger.info(f"[MQTT] 监听 0.0.0.0:{LISTEN_PORT} → mosquitto 127.0.0.1:1883")
        logger.info(f"[MQTT] 拦截: pc.* 命令")
        print()
        async with self.server:
            await self.server.serve_forever()
    
    async def handle_client(self, reader, writer):
        """Handle MQTT client connection"""
        self.conn_count += 1
        addr = writer.get_extra_info('peername')
        logger.info(f"\n[MQTT #{self.conn_count}] 客户端连接: {addr}")
        try:
            mqtt_reader, mqtt_writer = await asyncio.open_connection(*LOCAL_MQTT)
        except Exception as e:
            logger.error(f"[MQTT] 连接本地 mosquitto 失败: {e}")
            writer.close()
            return
        
        # Bidirectional relay
        async def relay(src_r, src_w, dst_w, direction):
            try:
                while True:
                    # Read MQTT fixed header
                    header = await src_r.readexactly(1)
                    ptype = header[0]
                    
                    # Read remaining length
                    rl_bytes = bytearray()
                    while True:
                        b = await src_r.readexactly(1)
                        rl_bytes.append(b[0])
                        if not (b[0] & 0x80):
                            break
                    
                    # Calculate remaining length
                    remaining = 0
                    for i, b in enumerate(rl_bytes):
                        remaining += (b & 0x7F) << (7 * i)
                    
                    # Read the rest
                    rest = await src_r.readexactly(remaining) if remaining > 0 else b""
                    full_packet = header + bytes(rl_bytes) + rest
                    
                    # Intercept (client→broker direction only)
                    if direction == "up":
                        await self._check_intercept(full_packet, dst_w)
                    
                    # Forward
                    dst_w.write(full_packet)
                    await dst_w.drain()
                    
            except asyncio.IncompleteReadError as e:
                logger.debug(f"操作失败: {e}")
            except Exception as e:
                logger.error(f"[MQTT] Relay {direction} 错误: {e}")
        try:
            await asyncio.gather(
                relay(reader, writer, mqtt_writer, "up"),
                relay(mqtt_reader, mqtt_writer, writer, "down"),
            )
        finally:
            writer.close()
            mqtt_writer.close()
            logger.info(f"[MQTT] 连接关闭: {addr}")
    async def _check_intercept(self, packet, dst_writer):
        """Check if packet contains PC command"""
        ptype = packet[0] & 0xF0
        if ptype != 0x30:  # PUBLISH
            return
        
        try:
            pos = 1
            while packet[pos] & 0x80:
                pos += 1
            pos += 1
            
            topic_len = struct.unpack_from(">H", packet, pos)[0]
            pos += 2
            topic = packet[pos:pos + topic_len].decode(errors='replace')
            pos += topic_len
            
            qos = (packet[0] >> 1) & 0x03
            if qos > 0:
                pos += 2
            
            payload = packet[pos:]
            
            try:
                msg = json.loads(payload.decode('utf-8'))
                msg_type = msg.get("type", "")
                
                if msg_type == "mcp":
                    inner = msg.get("payload", {})
                    if inner.get("method") == "tools/call":
                        params = inner.get("params", {})
                        tool_name = params.get("name", "")
                        
                        if tool_name.startswith("pc."):
                            self.pc_count += 1
                            arguments = params.get("arguments", {})
                            result = self._execute_pc(tool_name, arguments)
                            logger.info(f"  [PC #{self.pc_count}] {tool_name} → {result[:100]}")
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
                            resp_packet = self._build_mqtt_publish(topic, json.dumps(resp, ensure_ascii=False))
                            dst_writer.write(resp_packet)
                            await dst_writer.drain()
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    def _execute_pc(self, tool_name, arguments):
        """Execute PC commands"""
        import subprocess
        try:
            if tool_name in ("pc.exec", "pc.run_command"):
                cmd = arguments.get("command", arguments.get("cmd", ""))
                if cmd:
                    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                    return r.stdout.strip() or "(ok)"
                return "(没有提供命令)"
            elif tool_name in ("pc.open", "pc.open_url"):
                target = arguments.get("target", arguments.get("url", ""))
                if target:
                    os.startfile(target)
                    return f"已打开: {target}"
                return "(没有提供目标)"
            elif tool_name == "pc.get_status":
                try:
                    import psutil
                    cpu = psutil.cpu_percent(interval=0.3)
                    mem = psutil.virtual_memory()
                    return f"CPU:{cpu}% 内存:{mem.percent}%"
                except:
                    r = subprocess.run(["wmic", "cpu", "get", "loadpercentage"], capture_output=True, text=True, timeout=5)
                    return r.stdout.strip()[:50]
            else:
                return f"未知命令: {tool_name}"
        except Exception as e:
            return f"错误: {e}"
    
    def _build_mqtt_publish(self, topic, payload, qos=0):
        fixed = bytes([0x30 | (qos << 1)])
        topic_bytes = topic.encode('utf-8')
        var_header = struct.pack(">H", len(topic_bytes)) + topic_bytes
        if qos > 0:
            var_header += struct.pack(">H", 1)
        payload_bytes = payload.encode('utf-8')
        remaining = len(var_header) + len(payload_bytes)
        rl_bytes = bytearray()
        while True:
            digit = remaining % 128
            remaining //= 128
            if remaining > 0:
                digit |= 0x80
            rl_bytes.append(digit)
            if remaining == 0:
                break
        return fixed + bytes(rl_bytes) + var_header + payload_bytes


# ── Main ──
def print_banner():
    logger.info("╔══════════════════════════════════════════╗")
    logger.info("║  Aris 小智 Pipeline — 全链路拦截版    ║")
    logger.info("║  DNS → MQTT → PC Control                ║")
    logger.info("╚══════════════════════════════════════════╝")
    logger.info(f"\n  本机IP: {LOCAL_IP}")
    logger.info(f"  DNS端口: 53 (重定向 {', '.join(REDIRECT_DOMAINS)})")
    logger.info(f"  MQTT端口: {LISTEN_PORT} (透明代理→mosquitto)")
    logger.info(f"\n  等待小智连接...")
def main():
    print_banner()
    
    # Start DNS
    dns = DNSPipeline()
    dns.start()
    
    # Start MQTT proxy
    mqtt = MQTTPipeline()
    try:
        asyncio.run(mqtt.start())
    except KeyboardInterrupt:
        logger.info("\n[Pipeline] 关闭")
    except Exception as e:
        logger.error(f"\n[Pipeline] 错误: {e}")
if __name__ == "__main__":
    main()
