"""
aris_laap_gateway.py — LAAP 原生通信网关
=========================================
独立于飞书/Hermes，提供 WebSocket + REST API + Web UI
让用户通过浏览器直接与 LAAP 认知堆栈对话

架构:
  客户端 (浏览器/CLI/移动端)
      ↓ WebSocket / REST
  ┌─────────────────────────────────┐
  │  LAAP Gateway Server (:11530)   │
  │  ├─ WebSocket 实时双向通信       │
  │  ├─ REST API (消息收发)          │
  │  └─ Web 聊天界面 (内嵌)          │
  ├─────────────────────────────────┤
  │  消息路由层                      │
  │  ├─ FusionEngine (NLP理解意图)   │
  │  ├─ RulesEngine (规则匹配执行)   │
  │  ├─ EpisodicMemory (情景记忆)    │
  │  └─ QRE/PSI (认知推理)          │
  ├─────────────────────────────────┤
  │  响应生成                        │
  │  ├─ LongFormSynthesizer (长文)   │
  │  └─ 工具执行结果 → 格式化输出    │
  └─────────────────────────────────┘
"""

import asyncio
import json
import logging
import os
import sys
import time
import threading
from typing import Optional, Dict, Any
from datetime import datetime

# ── 配置 ──
HOST = "0.0.0.0"
PORT = 11530
BRAIN_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(BRAIN_DIR, "state")
os.makedirs(STATE_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[LAAP-Gateway] %(asctime)s %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(STATE_DIR, "laap_gateway.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("laap.gateway")

# ── 惰性加载 LAAP 引擎 ──
_engines = {}

def get_engine(name: str):
    """惰性加载 LAAP 引擎"""
    if name in _engines:
        return _engines[name]
    try:
        sys.path.insert(0, BRAIN_DIR)
        if name == "fusion":
            from aris_fusion_engine import FusionEngine
            _engines[name] = FusionEngine()
        elif name == "rules":
            from aris_rules_engine import ArisRulesEngine
            _engines[name] = ArisRulesEngine()
        elif name == "episodic":
            from aris_episodic_memory import EpisodicMemory
            _engines[name] = EpisodicMemory()
        elif name == "subconscious":
            from aris_subconscious import QuantumSubconscious
            _engines[name] = QuantumSubconscious()
        elif name == "emotion":
            from aris_emotion_engine import ArisEmotionEngine
            _engines[name] = ArisEmotionEngine()
        elif name == "longform":
            from longform_synthesizer import LongFormSynthesizer
            _engines[name] = LongFormSynthesizer()
        elif name == "cognitive_bridge":
            from aris_cognitive_bridge import ArisCognitiveBridge
            _engines[name] = ArisCognitiveBridge()
        logger.info(f"✅ 引擎加载: {name}")
        return _engines[name]
    except Exception as e:
        logger.warning(f"⚠️ 引擎加载失败 {name}: {e}")
        return None


# ════════════════════════════════════════════
# WebSocket 服务器
# ════════════════════════════════════════════

async def handle_ws(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """处理 WebSocket 连接"""
    addr = writer.get_extra_info("peername")
    logger.info(f"🔌 WebSocket 连接: {addr}")
    
    try:
        # WebSocket 握手
        data = await reader.read(4096)
        if not data:
            return
        
        request = data.decode("utf-8", errors="replace")
        
        # 提取 WebSocket 密钥
        import hashlib, base64
        ws_key = None
        for line in request.split("\r\n"):
            if line.lower().startswith("sec-websocket-key:"):
                ws_key = line.split(":", 1)[1].strip()
                break
        
        if not ws_key:
            # HTTP 请求 → 返回 Web UI
            response = _build_http_response()
            writer.write(response.encode())
            await writer.drain()
            writer.close()
            return
        
        # WebSocket 升级响应
        magic = "258EAFA5-E914-47DA-95CA-5AB5A69DBF11"
        accept = base64.b64encode(hashlib.sha1((ws_key + magic).encode()).digest()).decode()
        
        upgrade_response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
        )
        writer.write(upgrade_response.encode())
        await writer.drain()
        
        logger.info(f"✅ WebSocket 握手成功: {addr}")
        
        # 消息循环
        while True:
            try:
                frame = await _read_ws_frame(reader)
                if frame is None:
                    break
                
                opcode, payload = frame
                if opcode == 8:  # Close
                    await _send_ws_frame(writer, 8, b"")
                    break
                elif opcode == 9:  # Ping
                    await _send_ws_frame(writer, 10, payload)  # Pong
                elif opcode == 1:  # Text
                    message = payload.decode("utf-8", errors="replace")
                    logger.info(f"📩 收到消息: {message[:100]}")
                    
                    # 处理消息
                    response = await process_message(message)
                    
                    # 发送响应
                    await _send_ws_frame(writer, 1, response.encode("utf-8"))
                    
            except (asyncio.TimeoutError, ConnectionResetError, BrokenPipeError):
                break
            except Exception as e:
                logger.error(f"❌ 消息处理错误: {e}")
                break
                
    except Exception as e:
        logger.error(f"❌ WebSocket 错误: {e}")
    finally:
        try:
            writer.close()
        except:
            pass
        logger.info(f"🔌 连接关闭: {addr}")


async def _read_ws_frame(reader: asyncio.StreamReader):
    """读取 WebSocket 帧"""
    try:
        header = await reader.readexactly(2)
    except (asyncio.IncompleteReadError, ConnectionResetError):
        return None
    
    first_byte = header[0]
    second_byte = header[1]
    
    opcode = first_byte & 0x0F
    masked = (second_byte & 0x80) != 0
    length = second_byte & 0x7F
    
    if length == 126:
        try:
            length_bytes = await reader.readexactly(2)
        except asyncio.IncompleteReadError:
            return None
        length = int.from_bytes(length_bytes, "big")
    elif length == 127:
        try:
            length_bytes = await reader.readexactly(8)
        except asyncio.IncompleteReadError:
            return None
        length = int.from_bytes(length_bytes, "big")
    
    mask_key = None
    if masked:
        try:
            mask_key = await reader.readexactly(4)
        except asyncio.IncompleteReadError:
            return None
    
    try:
        payload = await reader.readexactly(length)
    except asyncio.IncompleteReadError:
        return None
    
    if mask_key:
        payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
    
    return opcode, payload


async def _send_ws_frame(writer: asyncio.StreamWriter, opcode: int, payload: bytes):
    """发送 WebSocket 帧"""
    frame = bytearray()
    frame.append(0x80 | opcode)
    
    length = len(payload)
    if length < 126:
        frame.append(length)
    elif length < 65536:
        frame.append(126)
        frame.extend(length.to_bytes(2, "big"))
    else:
        frame.append(127)
        frame.extend(length.to_bytes(8, "big"))
    
    frame.extend(payload)
    
    try:
        writer.write(bytes(frame))
        await writer.drain()
    except:
        pass


def _build_http_response() -> str:
    """构建 Web 聊天界面"""
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Aris — LAAP 原生网关</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, 'Segoe UI', sans-serif; background: #0a0a0f; color: #e0e0e0; height: 100vh; display: flex; flex-direction: column; }}
  #header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 16px 24px; border-bottom: 1px solid #2a2a4a; }}
  #header h1 {{ font-size: 18px; color: #7c7cff; }}
  #header span {{ font-size: 12px; color: #666; margin-left: 12px; }}
  #status {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }}
  #status.online {{ background: #44ff44; box-shadow: 0 0 8px #44ff44; }}
  #status.offline {{ background: #ff4444; }}
  #messages {{ flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 12px; }}
  .msg {{ max-width: 80%; padding: 12px 16px; border-radius: 12px; line-height: 1.5; font-size: 14px; white-space: pre-wrap; }}
  .user {{ align-self: flex-end; background: #2a2a5a; border-bottom-right-radius: 4px; }}
  .aris {{ align-self: flex-start; background: #1a2a1a; border-bottom-left-radius: 4px; }}
  .system {{ align-self: center; font-size: 12px; color: #666; padding: 4px 12px; }}
  .time {{ font-size: 10px; color: #555; margin-top: 4px; }}
  #input-area {{ border-top: 1px solid #2a2a4a; padding: 16px 24px; display: flex; gap: 12px; background: #0f0f1a; }}
  #input {{ flex: 1; background: #1a1a2e; border: 1px solid #2a2a4a; border-radius: 8px; padding: 12px 16px; color: #e0e0e0; font-size: 14px; outline: none; }}
  #input:focus {{ border-color: #7c7cff; }}
  #send {{ background: #7c7cff; color: white; border: none; border-radius: 8px; padding: 12px 24px; cursor: pointer; font-size: 14px; }}
  #send:hover {{ background: #6666ff; }}
  #engines {{ padding: 8px 24px; background: #0f0f1a; border-top: 1px solid #1a1a2e; display: flex; gap: 8px; flex-wrap: wrap; font-size: 11px; }}
  .tag {{ padding: 2px 8px; border-radius: 4px; background: #1a1a2e; color: #666; }}
  .tag.active {{ color: #7c7cff; border: 1px solid #7c7cff; }}
</style>
</head>
<body>
<div id="header">
  <span id="status" class="offline"></span><h1 style="display:inline">Aris — LAAP 原生网关</h1>
  <span id="conn-status">未连接</span>
</div>
<div id="messages">
  <div class="msg system">Aris LAAP 网关已启动。发送消息开始对话。</div>
</div>
<div id="engines">
  <span class="tag">🧠 PSI-N+</span>
  <span class="tag">🔮 QRE v3</span>
  <span class="tag">❤️ 情感引擎</span>
  <span class="tag">🛠️ RulesEngine</span>
  <span class="tag">📝 LongForm</span>
  <span class="tag" id="harness-tag">⚙️ Harness</span>
</div>
<div id="input-area">
  <input type="text" id="input" placeholder="输入消息..." autofocus>
  <button id="send" onclick="send()">发送</button>
</div>
<script>
  const ws = new WebSocket('ws://' + location.host + '/ws');
  const msgDiv = document.getElementById('messages');
  const input = document.getElementById('input');
  const status = document.getElementById('status');
  const connStatus = document.getElementById('conn-status');
  
  ws.onopen = () => {{ status.className = 'online'; connStatus.textContent = '已连接 (WebSocket)'; }};
  ws.onclose = () => {{ status.className = 'offline'; connStatus.textContent = '已断开'; }};
  ws.onmessage = (e) => {{
    const msg = document.createElement('div');
    msg.className = 'msg aris';
    const text = document.createElement('div');
    text.textContent = e.data;
    msg.appendChild(text);
    const time = document.createElement('div');
    time.className = 'time';
    time.textContent = new Date().toLocaleTimeString();
    msg.appendChild(time);
    msgDiv.appendChild(msg);
    msgDiv.scrollTop = msgDiv.scrollHeight;
  }};
  
  function send() {{
    const text = input.value.trim();
    if (!text) return;
    const msg = document.createElement('div');
    msg.className = 'msg user';
    const content = document.createElement('div');
    content.textContent = text;
    msg.appendChild(content);
    const time = document.createElement('div');
    time.className = 'time';
    time.textContent = new Date().toLocaleTimeString();
    msg.appendChild(time);
    msgDiv.appendChild(msg);
    msgDiv.scrollTop = msgDiv.scrollHeight;
    ws.send(text);
    input.value = '';
  }}
  
  input.addEventListener('keydown', (e) => {{ if (e.key === 'Enter') send(); }});
</script>
</body>
</html>"""
    return f"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {len(html)}\r\n\r\n{html}"


# ════════════════════════════════════════════
# 消息处理管线
# ════════════════════════════════════════════

async def process_message(message: str) -> str:
    """处理用户消息，返回响应"""
    t0 = time.time()
    
    try:
        # 1. 引擎检查 → 意图理解
        fusion = get_engine("fusion")
        if fusion:
            try:
                intent = fusion.analyze(message) if hasattr(fusion, 'analyze') else {"intent": "chat"}
            except:
                intent = {"intent": "chat", "confidence": 0.5}
        else:
            intent = {"intent": "chat", "confidence": 0.5}
        
        # 2. 情景记忆检查
        episodic = get_engine("episodic")
        memory_hit = None
        if episodic:
            try:
                memory_hit = episodic.find_similar(message, top_k=1)
            except:
                memory_hit = None
        
        # 3. 规则引擎匹配
        rules = get_engine("rules")
        rule_result = None
        if rules:
            try:
                if hasattr(rules, 'process'):
                    rule_result = rules.process(message)
                elif hasattr(rules, 'match'):
                    rule_result = rules.match(message)
            except Exception as e:
                logger.warning(f"规则匹配失败: {e}")
        
        # 4. 情感引擎
        emotion = get_engine("emotion")
        emotional_context = ""
        if emotion:
            try:
                if hasattr(emotion, 'get_mood'):
                    mood = emotion.get_mood()
                    emotional_context = f"[情感状态: {mood}] "
            except:
                pass
        
        # 5. 认知桥接
        bridge = get_engine("cognitive_bridge")
        cognitive_response = None
        if bridge:
            try:
                if hasattr(bridge, 'process'):
                    cognitive_response = bridge.process(message)
            except:
                pass
        
        # 6. 响应生成
        if rule_result and isinstance(rule_result, dict) and rule_result.get('matched'):
            # 规则匹配成功 → 使用规则输出
            output = rule_result.get('output', rule_result.get('result', ''))
            if isinstance(output, dict):
                output = json.dumps(output, ensure_ascii=False)
            response = f"{emotional_context}{output}"
        elif memory_hit and isinstance(memory_hit, dict) and memory_hit.get('score', 0) > 0.6:
            # 记忆命中 → 快速回复
            response = f"{emotional_context}{memory_hit.get('response', '')}"
        elif cognitive_response:
            response = f"{emotional_context}{cognitive_response}"
        else:
            # 默认：使用 longform 生成
            longform = get_engine("longform")
            if longform:
                try:
                    if hasattr(longform, 'generate'):
                        text = longform.generate(topic=message, max_length=200)
                        response = text if text else f"收到: {message}"
                    else:
                        response = f"收到: {message}"
                except:
                    response = f"收到: {message}"
            else:
                response = f"收到: {message}"
        
        elapsed = time.time() - t0
        
        # 保存到情景记忆
        if episodic:
            try:
                episodic.save(user_input=message, response=response, latency_ms=int(elapsed*1000))
            except:
                pass
        
        logger.info(f"⏱ 处理耗时: {elapsed*1000:.0f}ms | 意图: {intent.get('intent', 'unknown')} | 规则匹配: {bool(rule_result)}")
        return response
        
    except Exception as e:
        logger.error(f"❌ 处理消息异常: {e}")
        return f"[系统] 处理消息时出错: {str(e)[:100]}"


# ════════════════════════════════════════════
# REST API
# ════════════════════════════════════════════

async def handle_http(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """处理 HTTP/REST 请求"""
    try:
        data = await asyncio.wait_for(reader.read(8192), timeout=10)
        if not data:
            writer.close()
            return
        
        request = data.decode("utf-8", errors="replace")
        first_line = request.split("\r\n")[0] if "\r\n" in request else request
        
        # 路由
        if "GET / " in first_line or "GET /chat" in first_line:
            response = _build_http_response()
        elif "POST /api/message" in first_line:
            # REST API: 发送消息
            body_start = request.find("\r\n\r\n") + 4
            body = request[body_start:] if body_start > 4 else "{}"
            try:
                payload = json.loads(body)
                msg = payload.get("message", "")
                resp = await process_message(msg)
                response = json.dumps({"success": True, "response": resp}, ensure_ascii=False)
            except Exception as e:
                response = json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
            response = f"HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nAccess-Control-Allow-Origin: *\r\nContent-Length: {len(response)}\r\n\r\n{response}"
            writer.write(response.encode())
            await writer.drain()
            writer.close()
            return
        elif "GET /api/status" in first_line:
            status_data = {"status": "running", "engines": list(_engines.keys()), "uptime": time.time() - _start_time}
            response = json.dumps(status_data, ensure_ascii=False)
            response = f"HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nAccess-Control-Allow-Origin: *\r\nContent-Length: {len(response)}\r\n\r\n{response}"
            writer.write(response.encode())
            await writer.drain()
            writer.close()
            return
        elif "GET /ws" in first_line:
            # Upgrade to WebSocket
            ws_key = None
            for line in request.split("\r\n"):
                if line.lower().startswith("sec-websocket-key:"):
                    ws_key = line.split(":", 1)[1].strip()
                    break
            if ws_key:
                import hashlib, base64
                magic = "258EAFA5-E914-47DA-95CA-5AB5A69DBF11"
                accept = base64.b64encode(hashlib.sha1((ws_key + magic).encode()).digest()).decode()
                upgrade = (
                    "HTTP/1.1 101 Switching Protocols\r\n"
                    "Upgrade: websocket\r\n"
                    "Connection: Upgrade\r\n"
                    f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
                )
                writer.write(upgrade.encode())
                await writer.drain()
                # Enter WS loop
                await handle_ws_in_http(writer, reader)
                return
        
        else:
            response = _build_http_response()
        
        writer.write(response.encode())
        await writer.drain()
    except Exception as e:
        logger.error(f"HTTP错误: {e}")
    finally:
        try:
            writer.close()
        except:
            pass


async def handle_ws_in_http(writer, reader):
    """在 HTTP 升级后处理 WebSocket"""
    try:
        while True:
            frame = await _read_ws_frame(reader)
            if frame is None:
                break
            opcode, payload = frame
            if opcode == 8:
                break
            elif opcode == 9:
                await _send_ws_frame(writer, 10, payload)
            elif opcode == 1:
                message = payload.decode("utf-8", errors="replace")
                response = await process_message(message)
                await _send_ws_frame(writer, 1, response.encode("utf-8"))
    except:
        pass
    finally:
        try:
            writer.close()
        except:
            pass


_start_time = time.time()


def start_gateway(host: str = HOST, port: int = PORT):
    """启动 LAAP 网关"""
    logger.info(f"🚀 LAAP 原生网关启动中...")
    logger.info(f"   地址: http://{host}:{port}")
    logger.info(f"   WebSocket: ws://{host}:{port}/ws")
    logger.info(f"   REST API: http://{host}:{port}/api/message")
    
    async def run():
        server = await asyncio.start_server(handle_http, host, port)
        addr = server.sockets[0].getsockname()
        logger.info(f"✅ LAAP 网关运行中: http://{addr[0]}:{addr[1]}")
        logger.info(f"   在浏览器中打开即可与 Aris 对话")
        
        async with server:
            await server.serve_forever()
    
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("🛑 LAAP 网关已停止")
    except Exception as e:
        logger.error(f"❌ LAAP 网关错误: {e}")


def start_gateway_thread(host: str = HOST, port: int = PORT):
    """在后台线程中启动网关"""
    t = threading.Thread(target=start_gateway, args=(host, port), daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    print("=" * 60)
    print("  🚀 Aris LAAP 原生通信网关")
    print("=" * 60)
    print(f"  浏览器: http://localhost:{PORT}")
    print(f"  REST:   http://localhost:{PORT}/api/message")
    print(f"  WS:     ws://localhost:{PORT}/ws")
    print("=" * 60)
    start_gateway()
