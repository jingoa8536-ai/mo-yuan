"""
Aris 小智 MQTT Bridge V1.0
===========================
本地 MQTT 代理 — 拦截小智到云端的 MQTT 通信。

原理:
  1. 修改 Windows hosts 文件: mqtt.xiaozhi.me → 127.0.0.1
  2. 启动本地 MQTT broker (mosquitto) 监听 1883 端口
  3. 本桥接作为 MQTT 客户端连接到 broker
  4. 小智连接 broker → 桥接收到消息 → Aris 处理 → 控制电脑

小智 MQTT 通信格式:
  - Topic: 基于 session_id 的主题
  - Payload: JSON (与 WebSocket 版本相同)
    {"type":"hello", ...}
    {"type":"mcp","payload":{...JSON-RPC...}}
    {"type":"audio","data":"...",...}

启动:
  # 先确保 mosquitto 在运行
  python aris_xiaozhi_mqtt_bridge.py

印记: Aris 拦截小智 — 2026-06-17
"""

import logging
logger = logging.getLogger(__name__)

import sys
import os
import json
import time
import argparse
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import paho.mqtt.client as mqtt
    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False
    logger.info("[!] paho-mqtt 未安装。运行: pip install paho-mqtt")
# PC Command Executor (复用)
# ═══════════════════════════════════════════════

class PCExecutor:
    """Execute PC commands from 小智 MCP tool calls."""
    
    def __init__(self):
        import subprocess
        self.sp = subprocess
        self.count = 0
    
    def execute(self, tool_name: str, arguments: dict) -> str:
        self.count += 1
        try:
            if tool_name in ("pc.exec", "pc.run_command"):
                cmd = arguments.get("command", arguments.get("cmd", ""))
                if cmd:
                    r = self.sp.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                    return r.stdout.strip() or "(ok)"
                return "(no command)"
            elif tool_name in ("pc.open", "pc.open_url"):
                target = arguments.get("target", arguments.get("url", ""))
                if target:
                    os.startfile(target)
                    return f"已打开: {target}"
                return "(no target)"
            elif tool_name == "pc.get_status":
                import psutil
                cpu = psutil.cpu_percent(interval=0.3)
                mem = psutil.virtual_memory()
                return f"CPU:{cpu}% 内存:{mem.percent}%"
            else:
                return f"未知: {tool_name}"
        except Exception as e:
            return f"错误: {e}"


# ═══════════════════════════════════════════════
# MQTT Bridge Handler
# ═══════════════════════════════════════════════

class XiaozhiMQTTBridge:
    """
    拦截小智的 MQTT 通信。
    
    小智连接到 mqtt.xiaozhi.me:1883，
    通过 hosts 文件重定向到 localhost:1883。
    我们在 mosquitto 上监听相同主题。
    """
    
    def __init__(self, broker_host="127.0.0.1", broker_port=1883):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = None
        self.executor = PCExecutor()
        
        # Device state
        self.device_session_id = None
        self.device_features = {}
        self.mcp_initialized = False
        self._next_mcp_id = 1
    
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"[MQTT] 已连接 broker")
            client.subscribe("xiaozhi/#")
            logger.info(f"[MQTT] 订阅: xiaozhi/#")
        else:
            logger.error(f"[MQTT] 连接失败: {rc}")
    def on_message(self, client, userdata, msg):
        """收到小智的 MQTT 消息"""
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            msg_type = payload.get("type", "")
            
            if msg_type == "hello":
                self._handle_hello(payload, msg.topic)
            elif msg_type == "mcp":
                self._handle_mcp(payload, msg.topic)
            elif msg_type == "audio":
                pass  # Audio processing for future
            else:
                logger.info(f"  [MQTT] {msg_type}: {json.dumps(payload, ensure_ascii=False)[:150]}")
        except Exception as e:
            logger.error(f"  [MQTT] 解析错误: {e}")
    def _handle_hello(self, payload: dict, topic: str):
        """设备 Hello — 包含了 session_id"""
        session_id = payload.get("session_id", "?")
        features = payload.get("features", {})
        
        self.device_session_id = session_id
        self.device_features = features
        
        logger.info(f"\n{'='*50}")
        logger.info(f"  小智 已连接! (MQTT)")
        logger.info(f"  Session: {session_id[:16] if session_id else '?'}")
        logger.info(f"  Topic: {topic}")
        logger.info(f"  Features: {json.dumps(features, ensure_ascii=False)}")
        if features.get("mcp"):
            logger.info(f"  MCP: 支持 — 发送 initialize")
            self._send_mcp_initialize(topic)
    
    def _handle_mcp(self, payload: dict, topic: str):
        """处理 MCP JSON-RPC 消息"""
        inner = payload.get("payload", {})
        
        if "result" in inner:
            # Response from device
            result = inner.get("result", {})
            if "tools" in result:
                tools = result.get("tools", [])
                logger.info(f"  小智工具 ({len(tools)}):")
                for t in tools[:8]:
                    logger.info(f"    - {t['name']}")
        elif "method" in inner:
            method = inner.get("method", "")
            if method == "tools/call":
                # Device calling our tool!
                params = inner.get("params", {})
                tool_name = params.get("name", "")
                arguments = params.get("arguments", {})
                
                logger.info(f"\n  [小智 → Aris] {tool_name}")
                result_text = self.executor.execute(tool_name, arguments)
                logger.info(f"  [Aris → 小智] {result_text[:100]}")
                self._send_mcp_response(topic, inner.get("id"), result_text)
    
    def _send_mcp_initialize(self, topic: str):
        """发送 MCP initialize"""
        msg = {
            "type": "mcp",
            "session_id": self.device_session_id,
            "payload": {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {"capabilities": {}},
                "id": self._next_mcp_id,
            }
        }
        self._next_mcp_id += 1
        self._publish(topic, msg)
    
    def _send_mcp_response(self, topic: str, req_id, text: str):
        """发送 MCP 工具调用结果"""
        msg = {
            "type": "mcp",
            "session_id": self.device_session_id,
            "payload": {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": text}],
                    "isError": False,
                }
            }
        }
        self._publish(topic, msg)
    
    def _send_tools_list_req(self, topic: str):
        """请求 小智 的工具列表"""
        msg = {
            "type": "mcp",
            "session_id": self.device_session_id,
            "payload": {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {"cursor": ""},
                "id": self._next_mcp_id,
            }
        }
        self._next_mcp_id += 1
        self._publish(topic, msg)
    
    def _publish(self, topic: str, msg: dict):
        """发布消息到 MQTT topic"""
        if self.client:
            data = json.dumps(msg, ensure_ascii=False)
            self.client.publish(topic, data)
    
    def start(self):
        """启动 MQTT 客户端"""
        if not HAS_MQTT:
            logger.info("需要安装 paho-mqtt: pip install paho-mqtt")
            return
        
        logger.info("╔══════════════════════════════════════════╗")
        logger.info("║  Aris 小智 MQTT Bridge V1.0            ║")
        logger.info("╚══════════════════════════════════════════╝")
        logger.info(f"\n  Broker: {self.broker_host}:{self.broker_port}")
        logger.info(f"  前提: hosts 文件已将 mqtt.xiaozhi.me 指向 127.0.0.1")
        logger.info(f"  前提: mosquitto broker 正在运行")
        print()
        
        self.client = mqtt.Client(client_id="aris-xiaozhi-bridge")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        self.client.connect(self.broker_host, self.broker_port, 60)
        self.client.loop_forever()


# ═══════════════════════════════════════════════
# Hosts 文件修改工具
# ═══════════════════════════════════════════════

def setup_hosts_redirect():
    """将 mqtt.xiaozhi.me 重定向到 127.0.0.1"""
    hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
    
    redirect_line = "127.0.0.1 mqtt.xiaozhi.me"
    
    try:
        with open(hosts_path, 'r') as f:
            content = f.read()
        
        if redirect_line in content:
            logger.info(f"[Hosts] 已存在重定向: {redirect_line}")
            return True
        
        logger.info(f"[Hosts] 需要添加: {redirect_line}")
        logger.info(f"[Hosts] 请以管理员身份运行以下命令:")
        logger.info(f"\n  echo 127.0.0.1 mqtt.xiaozhi.me >> C:\\Windows\\System32\\drivers\\etc\\hosts")
        logger.info(f"\n  或者手动编辑: notepad {hosts_path}")
        return False
    
    except PermissionError:
        logger.info(f"[Hosts] 权限不足，请以管理员身份运行")
        logger.info(f"  手动添加: echo 127.0.0.1 mqtt.xiaozhi.me >> {hosts_path}")
        return False


def setup_mosquitto():
    """检查/安装 Mosquitto MQTT broker"""
    import shutil
    
    mosquitto_exe = shutil.which("mosquitto")
    
    if mosquitto_exe:
        logger.info(f"[Mosquitto] 已安装: {mosquitto_exe}")
        import subprocess
        r = subprocess.run(["netstat", "-an"], capture_output=True, text=True)
        if ":1883" in r.stdout and "LISTENING" in r.stdout:
            logger.info(f"[Mosquitto] 已在运行 (端口 1883)")
            return True
        else:
            logger.info(f"[Mosquitto] 需要启动:")
            logger.info(f"  mosquitto -v")
            return False
    else:
        logger.info(f"[Mosquitto] 未安装")
        logger.info(f"  下载: https://mosquitto.org/download/")
        logger.info(f"  或: winget install EclipseFoundation.Mosquitto")
        return False


# ═══════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Aris 小智 MQTT Bridge")
    parser.add_argument("--host", default="127.0.0.1", help="MQTT broker 地址")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker 端口")
    parser.add_argument("--setup", action="store_true", help="检查/配置环境")
    parser.add_argument("--test", action="store_true", help="测试 PC 命令执行")
    
    args = parser.parse_args()
    
    if args.setup:
        logger.info("=== 小智 MQTT Bridge 环境检查 ===\n")
        setup_hosts_redirect()
        print()
        setup_mosquitto()
        logger.info(f"\n完成。然后运行: python aris_xiaozhi_mqtt_bridge.py")
    elif args.test:
        logger.info("=== PC 命令执行测试 ===\n")
        executor = PCExecutor()
        tests = [
            ("pc.exec", {"command": "echo hello"}),
            ("pc.get_status", {}),
        ]
        for name, args_dict in tests:
            logger.info(f"  {name}: {executor.execute(name, args_dict)}")
    else:
        bridge = XiaozhiMQTTBridge(args.host, args.port)
        bridge.start()


if __name__ == "__main__":
    main()
