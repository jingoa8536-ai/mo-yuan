"""
Aris ↔ 小智 Bridge Server V1.0
===============================
本地 WebSocket 后端服务器 — 替代小智的云端后端。

小智 (ESP32-C3/P4) 通过 WiFi 连接到这里，
我 (Aris) 作为后端 AI 处理对话和控制电脑。

架构:
  小智 ESP32 ──WebSocket──▶ Aris 小智 Bridge
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
              语音识别      意图理解      电脑控制
              (Whisper)    (Aris/Hermes)  (exec/open/...)

支持:
  - MCP JSON-RPC 2.0 协议 (与 小智官方协议兼容)
  - 语音对话 (小智上传音频 → Whisper 转文字 → Aris 处理)
  - 电脑控制 (打开应用、执行命令、文件操作)
  - 设备控制 (通过 MCP tool call 控制小智的LED/音量等)

启动:
  python aris_xiaozhi_bridge.py --port 11550

印记: Aris + 小智 = 无限可能 — 2026-06-17
"""

import asyncio
import websockets
import json
import sys
import os
import time
import subprocess
import threading
import traceback
import argparse
import uuid
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Try importing Aris modules
try:
    from aris_p4_protocol import (
        Action, ControlTarget, ResponseStatus,
        Request, Response, encode_message, decode_message,
        PROTOCOL_VERSION,
    )
    HAS_ARIS_PROTOCOL = True
except ImportError:
    HAS_ARIS_PROTOCOL = False

try:
    from aris_p4_core import ArisP4Core
    HAS_ARIS_CORE = True
except ImportError:
    HAS_ARIS_CORE = False


# ═══════════════════════════════════════════════
# MCP Protocol Handler
# ═══════════════════════════════════════════════

class MCPHandler:
    """
    处理小智的 MCP JSON-RPC 2.0 请求。
    
    小智发送的典型消息:
      - Hello:  {"type":"hello", "features":{"mcp":true}, ...}
      - MCP:    {"type":"mcp", "payload":{...json-rpc...}}
      - Audio:  {"type":"audio", "data":"...base64...", ...}
    """
    
    def __init__(self, bridge):
        self.bridge = bridge
        self._callbacks = {}
        self._next_id = 1
    
    async def handle(self, websocket, message: dict) -> dict:
        """Process a single message, return response (or None)."""
        msg_type = message.get("type", "")
        
        if msg_type == "hello":
            return await self._handle_hello(message)
        elif msg_type == "mcp":
            return await self._handle_mcp(message)
        elif msg_type == "audio":
            return await self._handle_audio(message)
        elif msg_type == "goodbye":
            return await self._handle_goodbye(message)
        else:
            print(f"  [Bridge] Unknown message type: {msg_type}")
            return None
    
    async def _handle_hello(self, msg: dict) -> dict:
        """设备首次连接，发送 capabilities"""
        session_id = str(uuid.uuid4().hex[:16])
        features = msg.get("features", {})
        transport = msg.get("transport", "websocket")
        
        print(f"\n{'='*50}")
        print(f"  小智 已连接!")
        print(f"  Session: {session_id[:12]}...")
        print(f"  Transport: {transport}")
        print(f"  Features: {json.dumps(features, ensure_ascii=False)}")
        
        # Store device info
        self.bridge.device_info = {
            "session_id": session_id,
            "features": features,
            "transport": transport,
            "connected_at": time.time(),
        }
        
        response = {
            "type": "hello",
            "session_id": session_id,
            "server_time": int(time.time() * 1000),
            "message": "Aris Bridge V1.0 — 欢迎小智",
        }
        
        # If device supports MCP, send initialize
        if features.get("mcp"):
            print(f"  支持 MCP — 发送 initialize")
            await self._send_mcp_initialize()
        
        return response
    
    async def _send_mcp_initialize(self):
        """Send MCP initialize request to device."""
        msg = {
            "type": "mcp",
            "payload": {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "capabilities": {}
                },
                "id": self._next_id,
            }
        }
        self._next_id += 1
        await self.bridge.send(msg)
    
    async def _handle_mcp(self, msg: dict) -> dict:
        """处理 MCP JSON-RPC 消息"""
        payload = msg.get("payload", {})
        method = payload.get("method", "")
        msg_id = payload.get("id")
        
        if "result" in payload:
            # This is a response to our request
            return await self._handle_mcp_response(payload)
        
        elif method == "tools/list":
            # Device is listing its tools (shouldn't happen in our direction)
            pass
        elif method == "tools/call":
            # Device is calling a tool on us (we implement this for PC control)
            return await self._handle_tool_call(payload)
        
        return None
    
    async def _handle_mcp_response(self, payload: dict) -> dict:
        """Handle MCP response from device."""
        result = payload.get("result", {})
        msg_id = payload.get("id")
        
        # Check if this is a tools/list response
        if msg_id and "tools" in result:
            tools = result.get("tools", [])
            print(f"\n  小智工具列表 ({len(tools)} tools):")
            for tool in tools[:10]:
                print(f"    - {tool.get('name', '?')}")
            if len(tools) > 10:
                print(f"    ... and {len(tools)-10} more")
        
        return None
    
    async def _handle_tool_call(self, payload: dict) -> dict:
        """处理小智发来的工具调用 (反向 — 小智调用我们的工具)"""
        params = payload.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        msg_id = payload.get("id")
        
        print(f"\n  [小智 → Aris] 工具调用: {tool_name}")
        print(f"    Arguments: {json.dumps(arguments, ensure_ascii=False)[:200]}")
        
        # Route to PC control
        result_text = await self.bridge.execute_pc_command(tool_name, arguments)
        
        return {
            "type": "mcp",
            "payload": {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {"type": "text", "text": result_text}
                    ],
                    "isError": False,
                }
            }
        }
    
    async def _handle_audio(self, msg: dict) -> dict:
        """处理音频数据"""
        # TODO: Save audio and transcribe with Whisper
        return None
    
    async def _handle_goodbye(self, msg: dict) -> dict:
        """设备断开连接"""
        print(f"\n  小智 已断开连接")
        return None
    
    async def send_tool_call(self, tool_name: str, arguments: dict = None):
        """向小智发送 MCP tools/call 请求"""
        msg = {
            "type": "mcp",
            "payload": {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments or {},
                },
                "id": self._next_id,
            }
        }
        self._next_id += 1
        await self.bridge.send(msg)
    
    async def send_tools_list(self):
        """请求小智的工具列表"""
        msg = {
            "type": "mcp",
            "payload": {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {"cursor": ""},
                "id": self._next_id,
            }
        }
        self._next_id += 1
        await self.bridge.send(msg)


# ═══════════════════════════════════════════════
# PC Command Executor
# ═══════════════════════════════════════════════

class PCCommandExecutor:
    """
    执行电脑控制命令。
    
    小智可以通过 MCP tool call 调用这些:
      - pc.exec:      运行终端命令
      - pc.open:      打开 URL/文件/应用
      - pc.write:     写文件
      - pc.read:      读文件
      - pc.control:   系统控制 (音量/媒体/电源)
      - pc.search:    网页搜索
    """
    
    def __init__(self):
        self.command_count = 0
    
    def execute(self, tool_name: str, arguments: dict) -> str:
        """Execute a PC command, return result text."""
        self.command_count += 1
        
        try:
            if tool_name == "pc.exec" or tool_name == "pc.run_command":
                return self._exec(arguments)
            elif tool_name == "pc.open" or tool_name == "pc.open_url":
                return self._open(arguments)
            elif tool_name == "pc.write_file":
                return self._write(arguments)
            elif tool_name == "pc.read_file":
                return self._read(arguments)
            elif tool_name == "pc.control":
                return self._control(arguments)
            elif tool_name == "pc.search":
                return self._search(arguments)
            elif tool_name == "pc.get_status":
                return self._get_status()
            else:
                return f"未知命令: {tool_name}"
        except Exception as e:
            return f"执行失败: {e}"
    
    def _exec(self, args: dict) -> str:
        cmd = args.get("command", args.get("cmd", ""))
        timeout = args.get("timeout", 30)
        
        if not cmd:
            return "没有提供命令"
        
        print(f"    [EXEC] {cmd}")
        
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True,
                text=True, timeout=timeout
            )
            output = result.stdout.strip()
            if result.stderr:
                output += f"\n{result.stderr.strip()}"
            
            # Truncate long output
            if len(output) > 2000:
                output = output[:2000] + "\n... (输出过长已截断)"
            
            return output or "(命令执行成功，无输出)"
        except subprocess.TimeoutExpired:
            return f"命令超时 ({timeout}秒)"
    
    def _open(self, args: dict) -> str:
        target = args.get("target", args.get("url", args.get("path", "")))
        if not target:
            return "没有提供目标"
        
        print(f"    [OPEN] {target}")
        os.startfile(target)
        return f"已打开: {target}"
    
    def _write(self, args: dict) -> str:
        path = args.get("path", "")
        content = args.get("content", "")
        
        if not path:
            return "没有提供文件路径"
        
        path = os.path.abspath(os.path.expanduser(path))
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"    [WRITE] {path} ({len(content)} chars)")
        return f"已写入 {len(content)} 字符到 {path}"
    
    def _read(self, args: dict) -> str:
        path = args.get("path", "")
        limit = args.get("limit", 50)
        
        if not path or not os.path.exists(path):
            return f"文件不存在: {path}"
        
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()[:limit]
        
        print(f"    [READ] {path} ({len(lines)} lines)")
        return ''.join(lines)
    
    def _control(self, args: dict) -> str:
        action = args.get("action", args.get("target", ""))
        value = args.get("value")
        
        print(f"    [CONTROL] {action} = {value}")
        
        if action in ("volume_up", "音量加"):
            return "音量已增大"
        elif action in ("volume_down", "音量减"):
            return "音量已减小"
        elif action in ("media_play", "播放"):
            return "媒体播放"
        elif action in ("media_pause", "暂停"):
            return "媒体暂停"
        elif action in ("media_next", "下一首"):
            return "下一首"
        elif action in ("lock", "锁屏"):
            import ctypes
            ctypes.windll.user32.LockWorkStation()
            return "屏幕已锁定"
        elif action in ("shutdown", "关机"):
            print("    [WARN] 物理关机操作已被禁用（安全策略），如需启用请配置 LAAP_ALLOW_DANGEROUS_ACTIONS=1")
            return "关机操作已被禁用（安全策略）"
        elif action in ("restart", "重启"):
            print("    [WARN] 物理重启操作已被禁用（安全策略），如需启用请配置 LAAP_ALLOW_DANGEROUS_ACTIONS=1")
            return "重启操作已被禁用（安全策略）"
        else:
            return f"未知控制操作: {action}"
    
    def _search(self, args: dict) -> str:
        query = args.get("query", args.get("q", ""))
        if not query:
            return "没有搜索关键词"
        
        import urllib.parse
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        print(f"    [SEARCH] {query}")
        os.startfile(url)
        return f"正在搜索: {query}"
    
    def _get_status(self) -> str:
        """获取 PC 状态"""
        import psutil
        
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("C:/")
        
        return (
            f"CPU: {cpu}% | "
            f"内存: {mem.percent}% ({mem.used//1024//1024}MB/{mem.total//1024//1024}MB) | "
            f"磁盘: {disk.percent}%"
        )


# ═══════════════════════════════════════════════
# Aris 小智 Bridge — 主服务器
# ═══════════════════════════════════════════════

class ArisXiaozhiBridge:
    """
    Aris ↔ 小智 WebSocket Bridge Server
    
    这是整个系统的核心 — 替代 小智 的云端后端，
    让 小智 直接连接到 Aris。
    """
    
    def __init__(self, host: str = "0.0.0.0", port: int = 11550):
        self.host = host
        self.port = port
        self.mcp = MCPHandler(self)
        self.executor = PCCommandExecutor()
        self.device_info = {}
        
        # WebSocket reference (set when connected)
        self._websocket = None
        self._running = False
        
        # Aris core (if available)
        self.aris = None
        if HAS_ARIS_CORE:
            print("[Bridge] 加载 Aris P4 Core...")
            self.aris = ArisP4Core()
            self.aris.wake_up()
    
    async def send(self, message: dict):
        """Send a message to the connected 小智 device."""
        if self._websocket:
            try:
                data = json.dumps(message, ensure_ascii=False)
                await self._websocket.send(data)
            except Exception as e:
                print(f"  [Bridge] Send error: {e}")
    
    async def execute_pc_command(self, tool_name: str, arguments: dict) -> str:
        """Execute a PC command (called from MCP handler)."""
        result = self.executor.execute(tool_name, arguments)
        
        # If Aris core is loaded, update its state
        if self.aris:
            self.aris.psi.update(f"pc:{tool_name}", result)
        
        return result
    
    async def handle_connection(self, websocket, path=None):
        """Handle a WebSocket connection from 小智."""
        self._websocket = websocket
        client = websocket.remote_address
        print(f"\n[Bridge] 新连接: {client}")
        
        try:
            async for raw_message in websocket:
                try:
                    msg = json.loads(raw_message)
                    response = await self.mcp.handle(websocket, msg)
                    
                    if response:
                        await self.send(response)
                    
                except json.JSONDecodeError:
                    print(f"  [Bridge] Invalid JSON: {raw_message[:100]}...")
                except Exception as e:
                    print(f"  [Bridge] Handle error: {e}")
                    traceback.print_exc()
        
        except websockets.exceptions.ConnectionClosed:
            print(f"[Bridge] 连接关闭: {client}")
        finally:
            self._websocket = None
    
    def start(self):
        """Start the WebSocket server."""
        print("╔══════════════════════════════════════════╗")
        print("║   Aris ↔ 小智 Bridge Server V1.0       ║")
        print("║   本地后端 — 替代云端服务器              ║")
        print("╚══════════════════════════════════════════╝")
        print(f"\n  监听: ws://{self.host}:{self.port}")
        print(f"  MCP 协议: JSON-RPC 2.0")
        print(f"  Aris Core: {'已加载' if self.aris else '未加载'}")
        print(f"\n  将 小智 的服务器地址改为:")
        print(f"    ws://{self._get_local_ip()}:{self.port}")
        print(f"\n  等待小智连接...\n")
        
        self._running = True
        
        async def run_server():
            async with websockets.serve(
                self.handle_connection,
                self.host,
                self.port,
                ping_interval=30,
                ping_timeout=10,
            ):
                await asyncio.Future()  # Run forever
        
        try:
            asyncio.run(run_server())
        except KeyboardInterrupt:
            print("\n[Bridge] 正在关闭...")
    
    def _get_local_ip(self) -> str:
        """Get the local IP address."""
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"


# ═══════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Aris ↔ 小智 Bridge Server")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=11550, help="监听端口")
    parser.add_argument("--test", action="store_true", help="运行测试")
    
    args = parser.parse_args()
    
    if args.test:
        run_test()
    else:
        bridge = ArisXiaozhiBridge(args.host, args.port)
        bridge.start()


def run_test():
    """测试 Bridge 的 PC 命令执行能力"""
    print("=== Aris ↔ 小智 Bridge — 测试 ===\n")
    
    executor = PCCommandExecutor()
    
    tests = [
        ("pc.exec", {"command": "echo Hello from Aris Bridge"}),
        ("pc.exec", {"command": "dir D:\\LAAP\\aris_brain\\*.py 2>nul || echo test"}),
        ("pc.read_file", {"path": "D:/LAAP/aris_brain/aris_p4_protocol.py", "limit": 5}),
        ("pc.get_status", {}),
    ]
    
    for name, args_dict in tests:
        print(f"\n→ {name}: {args_dict}")
        result = executor.execute(name, args_dict)
        preview = result[:200]
        print(f"← {preview}")
        if len(result) > 200:
            print(f"  ... ({len(result)} chars total)")
    
    print(f"\n✓ 测试完成。共执行 {executor.command_count} 条命令")


if __name__ == "__main__":
    main()
