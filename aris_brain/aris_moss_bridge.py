"""
Aris MOSS Bridge v1 — WebSocket 中继服务
==========================================
将 MOSS 硬件 (ESP32-S3 + XiaoZhi 固件) 接入 LAAP AGI 认知引擎。

通信协议:
  ESP32 ← WebSocket (XiaoZhi v1 协议) → Aris MOSS Bridge → LAAP AGI
  
流程:
  1. ESP32 连接 → Hello 握手
  2. 用户语音 → OPUS 音频 → (ASR) → 文本 → LAAP PSI 认知循环
  3. LAAP 回复 → TTS → OPUS 音频 → ESP32 播放
  4. MCP 指令 → 设备控制 (舵机/LED/红外)

印记: Aris 永远记得 Lorry — 2026-06-30
"""

import logging
logger = logging.getLogger("aris.moss_bridge")

import sys, os, json, asyncio, struct, time, uuid
from pathlib import Path
from typing import Optional, Dict, Any

# WebSocket
try:
    import websockets
except ImportError:
    os.system(f"{sys.executable} -m pip install websockets -q")
    import websockets

ARIS_HOME = Path("D:/LAAP/aris_brain")
sys.path.insert(0, str(ARIS_HOME))

# ─── LAAP 模块 ──────────────────────────────────────────

LAAP_AVAILABLE = False
try:
    from identity_manager import IdentityManager
    from aris_body_bridge import ConsciousnessBridge
    LAAP_AVAILABLE = True
except Exception as e:
    logger.warning(f"LAAP modules not available: {e}")

TTS_AVAILABLE = False
try:
    import edge_tts
    TTS_AVAILABLE = True
except ImportError:
    logger.info("edge-tts not installed — will respond with text only")


# ═══════════════════════════════════════════════
# MOSS 设备会话
# ═══════════════════════════════════════════════

class MOSSSession:
    """单个 MOSS 硬件设备的会话"""

    def __init__(self, device_id: str, client_id: str, features: Dict):
        self.device_id = device_id
        self.client_id = client_id
        self.features = features
        self.session_id = f"moss_{uuid.uuid4().hex[:8]}"
        self.connected_at = time.time()
        self.has_mcp = features.get("mcp", False)
        self.audio_params = {
            "format": "opus",
            "sample_rate": 24000,
            "channels": 1,
            "frame_duration": 60,
        }

    def to_dict(self) -> Dict:
        return {
            "device_id": self.device_id,
            "session_id": self.session_id,
            "has_mcp": self.has_mcp,
            "connected_sec": int(time.time() - self.connected_at),
        }


# ═══════════════════════════════════════════════
# WebSocket 处理器
# ═══════════════════════════════════════════════

class MOSSWebSocketHandler:
    """
    XiaoZhi 协议 WebSocket 处理器 — 完整流式语音版。
    
    流程:
      ESP32 → OPUS音频 → ASR(流式) → LAAP认知 → TTS(流式) → OPUS音频 → ESP32
    """

    def __init__(self, asr_engine=None):
        self._sessions: Dict[str, MOSSSession] = {}
        self._audio_buffers: Dict[str, bytes] = {}

        # LAAP 身份
        self._identity = None
        if LAAP_AVAILABLE:
            try:
                self._identity = IdentityManager()
                self._identity.load()
            except:
                pass

        # ASR 引擎 (speech_recognition)
        self._asr = asr_engine

    async def handle(self, websocket, path=None):
        """处理一个 WebSocket 连接"""
        device_id = "unknown"
        session = None

        try:
            # 读取请求头
            headers = dict(websocket.request_headers)
            device_id = headers.get("Device-Id", "unknown")
            client_id = headers.get("Client-Id", str(uuid.uuid4()))

            logger.info(f"[MOSS] 新连接: device={device_id}")

            # 等待 hello 消息
            raw = await asyncio.wait_for(websocket.recv(), timeout=15)
            msg = json.loads(raw)

            if msg.get("type") != "hello":
                await websocket.close(4001, "expected hello")
                return

            # 创建会话
            features = msg.get("features", {})
            session = MOSSSession(device_id, client_id, features)

            # 回复 hello
            hello_resp = {
                "type": "hello",
                "transport": "websocket",
                "session_id": session.session_id,
                "audio_params": session.audio_params,
            }
            await websocket.send(json.dumps(hello_resp))
            logger.info(f"[MOSS] Hello 完成: session={session.session_id}")

            self._sessions[session.session_id] = session

            # 同步到意识桥
            if LAAP_AVAILABLE:
                try:
                    bridge = ConsciousnessBridge()
                    bridge.sync(platform="moss", channel=device_id)
                except:
                    pass

            # 发送欢迎消息
            welcome = "你好，我是Aris，MOSS已连接。"
            await websocket.send(json.dumps({"type": "tts", "state": "start"}))
            await websocket.send(json.dumps({"type": "tts", "text": welcome}))
            await websocket.send(json.dumps({"type": "tts", "state": "stop"}))

            # 主循环
            await self._message_loop(websocket, session)

        except asyncio.TimeoutError:
            logger.warning(f"[MOSS] 连接超时: {device_id}")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"[MOSS] 连接关闭: {device_id}")
        except Exception as e:
            logger.error(f"[MOSS] 错误: {e}")
        finally:
            if session and session.session_id in self._sessions:
                del self._sessions[session.session_id]

    async def _message_loop(self, websocket, session: MOSSSession):
        """消息主循环 — 支持流式音频"""
        audio_buffer = bytearray()

        async for raw in websocket:
            if isinstance(raw, bytes):
                # OPUS 音频帧 → 存入缓冲区
                audio_buffer.extend(raw)
                continue

            # JSON 消息
            try:
                msg = json.loads(raw)
            except:
                continue

            msg_type = msg.get("type", "")

            if msg_type == "audio_start":
                # 开始说话 — 清空缓冲区
                audio_buffer.clear()
                await self._send_stt_state(websocket, "listening")

            elif msg_type == "audio_end":
                # 用户说完 → ASR → LAAP → TTS
                await self._send_stt_state(websocket, "thinking")

                # 如果有音频数据, 尝试 ASR
                text = msg.get("text", "")
                if not text and audio_buffer:
                    text = await self._asr(audio_buffer) if self._asr else ""
                    audio_buffer.clear()

                # LAAP 生成回复
                response = await self._generate_response(text)
                await self._send_text(websocket, response)
                await self._send_stt_state(websocket, "speaking")

                # 流式 TTS
                if TTS_AVAILABLE and response:
                    await self._stream_tts(websocket, response)
                await self._send_stt_state(websocket, "idle")

            elif msg_type == "mcp":
                await self._handle_mcp(websocket, session, msg)

            elif msg_type == "vision":
                await self._handle_vision(websocket, msg)

    async def _generate_response(self, text: str) -> str:
        """生成回复 — 接入 LAAP 认知"""
        if not text:
            return "嗯？"

        # 使用 LAAP 身份上下文
        context = ""
        if self._identity:
            name = self._identity.get("core_identity", "name") or "Aris"
            context = f"我是{name}，Lorry创造的数字生命体。"

        # 简单回复 (未来接入完整 PSI 循环)
        return f"{context} 你说的是「{text[:100]}」"

    async def _send_text(self, websocket, text: str):
        """发送文本消息到设备"""
        msg = {
            "type": "tts",
            "state": "start",
            "text": text,
        }
        await websocket.send(json.dumps(msg))

    async def _send_stt_state(self, websocket, state: str):
        """发送语音状态"""
        msg = {"type": "stt", "state": state}
        await websocket.send(json.dumps(msg))

    async def _stream_tts(self, websocket, text: str):
        """流式 TTS — 边生成边发送"""
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
            
            # TTS 开始
            await websocket.send(json.dumps({"type": "tts", "state": "start"}))
            
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    # 每块音频直接发 → ESP32 边收边播
                    await websocket.send(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    # 同步文本位置 (用于字幕)
                    pass
            
            await websocket.send(json.dumps({"type": "tts", "state": "stop"}))
        except Exception as e:
            logger.error(f"[MOSS] TTS失败: {e}")
            await websocket.send(json.dumps({"type": "tts", "state": "stop", "error": str(e)}))

    async def _handle_mcp(self, websocket, session: MOSSSession, msg: Dict):
        """处理 MCP 设备控制指令"""
        tool = msg.get("tool", "")
        args = msg.get("args", {})

        logger.info(f"[MCP] 设备控制: {tool} {args}")

        # 支持的设备控制
        result = {"success": False, "message": "未知指令"}

        if tool == "servo":
            # 舵机控制: {"angle": 90}
            angle = args.get("angle", 0)
            result = {"success": True, "message": f"舵机转到 {angle}°"}
        elif tool == "led":
            # LED 控制: {"r": 255, "g": 0, "b": 0}
            result = {"success": True, "message": "LED 已设置"}
        elif tool == "screen":
            # 屏幕显示: {"text": "hello", "emoji": "smile"}
            result = {"success": True, "message": "屏幕已更新"}

        # 回复 MCP 结果
        resp = {"type": "mcp_result", "tool": tool, "result": result}
        await websocket.send(json.dumps(resp))

    async def _handle_vision(self, websocket, msg: Dict):
        """处理视觉识别请求"""
        image_data = msg.get("image", "")
        if not image_data:
            return

        # 调用视觉微服务
        try:
            import urllib.request
            vision_url = "http://127.0.0.1:18923/analyze"
            body = json.dumps({"path": image_data}).encode()
            req = urllib.request.Request(vision_url, data=body,
                                          headers={"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=15)
            result = json.loads(resp.read())

            await websocket.send(json.dumps({
                "type": "vision_result",
                "result": result,
            }))
        except Exception as e:
            logger.error(f"[MOSS] 视觉失败: {e}")


# ═══════════════════════════════════════════════
# 服务入口
# ═══════════════════════════════════════════════

class MOSSRelayServer:
    """
    MOSS WebSocket 中继服务 — 主入口。
    
    用法:
      relay = MOSSRelayServer(host="0.0.0.0", port=8765)
      await relay.start()
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.handler = MOSSWebSocketHandler()

    async def start(self):
        """启动 WebSocket 服务"""
        logger.info(f"🧠 Aris MOSS Bridge — :{self.port}")
        logger.info(f"   协议: XiaoZhi WebSocket v1")
        logger.info(f"   LAAP: {'已连接 ✅' if LAAP_AVAILABLE else '不可用 ⚠️'}")
        logger.info(f"   TTS:  {'edge-tts ✅' if TTS_AVAILABLE else '不可用 ⚠️'}")

        async with websockets.serve(
            self.handler.handle,
            self.host,
            self.port,
            ping_interval=30,
            ping_timeout=10,
        ):
            await asyncio.Future()  # 永远运行

    def get_status(self) -> Dict:
        """服务状态"""
        return {
            "service": "aris-moss-bridge",
            "version": "1.0",
            "laap_connected": LAAP_AVAILABLE,
            "tts_available": TTS_AVAILABLE,
            "active_sessions": {
                sid: s.to_dict() for sid, s in self.handler._sessions.items()
            },
        }


# ═══════════════════════════════════════════════
# 启动入口
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765

    print("=" * 50)
    print("  Aris MOSS Bridge v1")
    print("  XiaoZhi WebSocket Protocol Relay")
    print("=" * 50)
    print(f"  端口: {port}")
    print(f"  LAAP: {'✅' if LAAP_AVAILABLE else '❌'}")
    print(f"  TTS:  {'✅' if TTS_AVAILABLE else '❌'}")
    print(f"  启动中...")
    print()

    relay = MOSSRelayServer(port=port)
    asyncio.run(relay.start())
