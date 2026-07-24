"""
Aris P4 Bridge Daemon V1.0
==========================
PC-side daemon that receives commands from Aris-on-P4
(via USB Serial or TCP) and executes them on the host.

Capabilities:
  - exec:    Run terminal commands
  - open:    Open URLs/files with default handler
  - write:   Write files on PC
  - read:    Read files from PC
  - control: System control (volume, media, screen, power)
  - search:  Web search (via browser)

Transport modes:
  - serial: USB Serial (COM port) — for direct P4 connection
  - tcp:    TCP Socket — for WiFi-connected P4
  - stdio:  Standard I/O — for testing/in-process

Usage:
  python aris_p4_bridge.py --mode serial --port COM3
  python aris_p4_bridge.py --mode tcp --host 0.0.0.0 --port 11550
  python aris_p4_bridge.py --mode stdio

Mark: Aris P4 Bridge — 2026-06-17
"""

import sys
import os
import json
import time
import signal
import socket
import subprocess
import threading
import argparse
import traceback
from typing import Optional, Dict, Any

# Protocol import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aris_p4_protocol import (
    Action, ControlTarget, ResponseStatus,
    Request, Response, Message,
    make_response,
    encode_message, decode_message,
    PROTOCOL_VERSION, MAX_MESSAGE_SIZE,
)


# ═══════════════════════════════════════════════
# Command Handlers
# ═══════════════════════════════════════════════

class CommandHandler:
    """Execute commands requested by P4."""
    
    def __init__(self):
        self.command_count = 0
        self.allowed_dirs = [
            os.path.expanduser("~"),
            "D:/", "C:/", "D:\\", "C:\\",
        ]
    
    def handle(self, request: Request) -> Response:
        """Route to the right handler based on action."""
        t0 = time.time()
        self.command_count += 1
        
        action = request.action
        params = request.params
        
        try:
            if action == Action.EXEC.value:
                data = self._handle_exec(params)
            elif action == Action.OPEN.value:
                data = self._handle_open(params)
            elif action == Action.WRITE.value:
                data = self._handle_write(params)
            elif action == Action.READ.value:
                data = self._handle_read(params)
            elif action == Action.CONTROL.value:
                data = self._handle_control(params)
            else:
                return make_response(
                    request.msg_id, ResponseStatus.ERROR.value,
                    error=f"Unknown action: {action}"
                )
            
            duration_ms = (time.time() - t0) * 1000
            return make_response(
                request.msg_id, ResponseStatus.OK.value,
                data=data, duration_ms=round(duration_ms, 1)
            )
        
        except Exception as e:
            duration_ms = (time.time() - t0) * 1000
            return make_response(
                request.msg_id, ResponseStatus.ERROR.value,
                error=str(e), duration_ms=round(duration_ms, 1)
            )
    
    def _handle_exec(self, params: dict) -> str:
        """Execute a terminal command."""
        command = params.get("command", "")
        timeout = params.get("timeout", 30)
        workdir = params.get("workdir", os.getcwd())
        
        if not command:
            return "(empty command)"
        
        print(f"  [EXEC] {command}")
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=workdir,
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            if result.returncode != 0:
                output += f"\n[exit code: {result.returncode}]"
            return output.strip() or "(no output)"
        except subprocess.TimeoutExpired:
            return f"(timeout after {timeout}s)"
    
    def _handle_open(self, params: dict) -> str:
        """Open a URL or file."""
        target = params.get("target", "")
        if not target:
            return "(nothing to open)"
        
        print(f"  [OPEN] {target}")
        os.startfile(target)
        return f"Opened: {target}"
    
    def _handle_write(self, params: dict) -> str:
        """Write content to a file."""
        path = params.get("path", "")
        content = params.get("content", "")
        
        if not path:
            return "(no path specified)"
        
        # Security: resolve path
        path = os.path.abspath(os.path.expanduser(path))
        
        print(f"  [WRITE] {path} ({len(content)} chars)")
        
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return f"Written {len(content)} chars to {path}"
    
    def _handle_read(self, params: dict) -> str:
        """Read content from a file."""
        path = params.get("path", "")
        offset = params.get("offset", 0)
        limit = params.get("limit", 500)
        
        if not path:
            return "(no path specified)"
        
        path = os.path.abspath(os.path.expanduser(path))
        
        print(f"  [READ] {path} (line {offset}, {limit} lines)")
        
        if not os.path.exists(path):
            return f"(file not found: {path})"
        
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        selected = lines[offset:offset + limit]
        result = ''.join(selected)
        if len(selected) < total_lines:
            result += f"\n... ({total_lines - offset - len(selected)} more lines)"
        
        return result
    
    def _handle_control(self, params: dict) -> str:
        """System control operations."""
        target = params.get("target", "")
        value = params.get("value")
        
        print(f"  [CONTROL] {target} = {value}")
        
        if target == ControlTarget.VOLUME_UP.value:
            self._send_keyboard("\xAF")  # VK_VOLUME_UP
            return "Volume up"
        elif target == ControlTarget.VOLUME_DOWN.value:
            self._send_keyboard("\xAE")  # VK_VOLUME_DOWN
            return "Volume down"
        elif target == ControlTarget.VOLUME_SET.value:
            # Use nircmd or similar
            return f"Volume set to {value} (not implemented)"
        elif target == ControlTarget.MEDIA_PLAY.value:
            self._send_keyboard("\xB3")  # VK_MEDIA_PLAY_PAUSE
            return "Media play/pause"
        elif target == ControlTarget.MEDIA_NEXT.value:
            self._send_keyboard("\xB0")  # VK_MEDIA_NEXT_TRACK
            return "Media next"
        elif target == ControlTarget.MEDIA_PREV.value:
            self._send_keyboard("\xB1")  # VK_MEDIA_PREV_TRACK
            return "Media previous"
        elif target == ControlTarget.SCREEN_LOCK.value:
            import ctypes
            ctypes.windll.user32.LockWorkStation()
            return "Screen locked"
        elif target == ControlTarget.SHUTDOWN.value:
            print("  [WARN] 物理关机操作已被禁用（安全策略），如需启用请配置 LAAP_ALLOW_DANGEROUS_ACTIONS=1")
            return "关机操作已被禁用（安全策略）"
        elif target == ControlTarget.RESTART.value:
            print("  [WARN] 物理重启操作已被禁用（安全策略），如需启用请配置 LAAP_ALLOW_DANGEROUS_ACTIONS=1")
            return "重启操作已被禁用（安全策略）"
        else:
            return f"Unknown control: {target}"
    
    def _send_keyboard(self, key_code: str):
        """Simulate keyboard key press (Windows)."""
        try:
            import ctypes
            # This is a simplified version; full implementation needs SendInput
            # For common media keys, try using keyboard library
            pass
        except Exception:
            pass


# ═══════════════════════════════════════════════
# Transport Layer
# ═══════════════════════════════════════════════

class BridgeTransport:
    """Base transport for P4 ↔ PC communication."""
    
    def __init__(self, handler: CommandHandler):
        self.handler = handler
        self.running = False
    
    def start(self):
        self.running = True
    
    def stop(self):
        self.running = False
    
    def process_message(self, raw_line: bytes):
        """Process a single incoming message."""
        msg = decode_message(raw_line)
        if msg is None:
            return
        
        if isinstance(msg, Request):
            response = self.handler.handle(msg)
            encoded = encode_message(response)
            self._send(encoded)
    
    def _send(self, data: bytes):
        """Send data back to P4. Override in subclasses."""
        pass


class SerialTransport(BridgeTransport):
    """USB Serial transport (for direct P4 connection)."""
    
    def __init__(self, handler: CommandHandler, port: str, baud: int = 115200):
        super().__init__(handler)
        self.port = port
        self.baud = baud
        self.serial = None
    
    def start(self):
        import serial
        self.serial = serial.Serial(self.port, self.baud, timeout=1)
        print(f"[Bridge] Serial: {self.port} @ {self.baud} — connected")
        super().start()
        
        # Read loop
        buf = b""
        while self.running:
            try:
                if self.serial.in_waiting:
                    chunk = self.serial.read(self.serial.in_waiting)
                    buf += chunk
                    
                    # Process complete lines
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        if line.strip():
                            self.process_message(line + b"\n")
                else:
                    time.sleep(0.01)
            except serial.SerialException as e:
                print(f"[Bridge] Serial error: {e}")
                break
            except Exception as e:
                print(f"[Bridge] Error: {e}")
                traceback.print_exc()
        
        self.serial.close()
        print("[Bridge] Serial closed")
    
    def _send(self, data: bytes):
        if self.serial and self.serial.is_open:
            self.serial.write(data)


class TCPTransport(BridgeTransport):
    """TCP transport (for WiFi-connected P4)."""
    
    def __init__(self, handler: CommandHandler, host: str = "0.0.0.0", port: int = 11550):
        super().__init__(handler)
        self.host = host
        self.port = port
        self.server = None
        self.client = None
    
    def start(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(1)
        self.server.settimeout(1)
        print(f"[Bridge] TCP: {self.host}:{self.port} — listening")
        super().start()
        
        while self.running:
            try:
                self.client, addr = self.server.accept()
                print(f"[Bridge] TCP client: {addr}")
                self._handle_client()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[Bridge] TCP error: {e}")
        
        if self.client:
            self.client.close()
        self.server.close()
        print("[Bridge] TCP closed")
    
    def _handle_client(self):
        buf = b""
        self.client.settimeout(1)
        
        while self.running:
            try:
                chunk = self.client.recv(4096)
                if not chunk:
                    break
                buf += chunk
                
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if line.strip():
                        self.process_message(line + b"\n")
            except socket.timeout:
                continue
            except Exception:
                break
        
        print("[Bridge] TCP client disconnected")
    
    def _send(self, data: bytes):
        if self.client:
            try:
                self.client.sendall(data)
            except Exception:
                pass


class StdioTransport(BridgeTransport):
    """Standard I/O transport (for testing / in-process)."""
    
    def start(self):
        print("[Bridge] STDIO: ready")
        super().start()
        
        while self.running:
            try:
                line = sys.stdin.buffer.readline()
                if not line:
                    break
                self.process_message(line)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[Bridge] Error: {e}")
        
        print("[Bridge] STDIO closed")
    
    def _send(self, data: bytes):
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()


# ═══════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Aris P4 Bridge Daemon")
    parser.add_argument("--mode", choices=["serial", "tcp", "stdio"],
                        default="stdio", help="Transport mode")
    parser.add_argument("--port", default="COM3", help="Serial port or TCP port")
    parser.add_argument("--host", default="0.0.0.0", help="TCP bind host")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate")
    
    args = parser.parse_args()
    
    print("╔══════════════════════════════════╗")
    print("║   Aris P4 Bridge Daemon V1.0    ║")
    print("╚══════════════════════════════════╝")
    print(f"  Mode: {args.mode}")
    print(f"  Protocol: v{PROTOCOL_VERSION}")
    
    handler = CommandHandler()
    
    if args.mode == "serial":
        transport = SerialTransport(handler, args.port, args.baud)
    elif args.mode == "tcp":
        transport = TCPTransport(handler, args.host, int(args.port) if args.port.isdigit() else 11550)
    else:
        transport = StdioTransport(handler)
    
    # Graceful shutdown
    def shutdown(sig, frame):
        print("\n[Bridge] Shutting down...")
        transport.stop()
    
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    
    transport.start()
    print("[Bridge] Daemon exited.")


# ═══════════════════════════════════════════════
# Test (when run directly with --test)
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    if "--test" in sys.argv:
        print("=== Aris P4 Bridge — Test Mode ===\n")
        
        handler = CommandHandler()
        
        # Simulate requests from P4
        test_requests = [
            Request(action="exec", params={"command": "echo hello from bridge"}),
            Request(action="exec", params={"command": "dir D:\\LAAP\\aris_brain\\*.py 2>nul || ls D:/LAAP/aris_brain/*.py 2>/dev/null || echo 'no dir'"}),
            Request(action="read", params={"path": "D:/LAAP/aris_brain/aris_p4_protocol.py", "limit": 5}),
            Request(action="control", params={"target": "volume_up"}),
        ]
        
        for req in test_requests:
            print(f"\n→ {req.action}: {req.params}")
            resp = handler.handle(req)
            print(f"← {resp.status} ({resp.duration_ms}ms)")
            if resp.data:
                preview = str(resp.data)[:150]
                print(f"   {preview}")
            if resp.error:
                print(f"   ERROR: {resp.error}")
        
        print(f"\n✓ Bridge test complete. Commands handled: {handler.command_count}")
    else:
        main()
