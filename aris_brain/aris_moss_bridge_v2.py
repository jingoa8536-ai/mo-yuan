"""Aris MOSS Bridge v2 — 纯 asyncio WebSocket (零外部依赖)"""
import sys, os, json, asyncio, struct, hashlib, base64, uuid, time, logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("aris.moss")

ARIS_HOME = Path("D:/LAAP/aris_brain")
sys.path.insert(0, str(ARIS_HOME))

WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-5AB9DFF7CE1B"


async def ws_send(writer, data):
    """发送 WebSocket 文本帧"""
    if isinstance(data, str):
        data = data.encode('utf-8')
    length = len(data)
    if length < 126:
        frame = b'\x81' + bytes([length]) + data
    elif length < 65536:
        frame = b'\x81\x7e' + struct.pack('>H', length) + data
    else:
        frame = b'\x81\x7f' + struct.pack('>Q', length) + data
    writer.write(frame)
    await writer.drain()


async def ws_recv(reader):
    """接收 WebSocket 帧"""
    b = await reader.readexactly(2)
    opcode = b[0] & 0x0f
    masked = b[1] & 0x80
    length = b[1] & 0x7f
    if length == 126:
        b = await reader.readexactly(2)
        length = struct.unpack('>H', b)[0]
    elif length == 127:
        b = await reader.readexactly(8)
        length = struct.unpack('>Q', b)[0]
    if opcode == 0x8:
        return None  # close
    mask_key = await reader.readexactly(4) if masked else b''
    payload = await reader.readexactly(length)
    if masked:
        payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
    return payload.decode('utf-8', errors='replace')


async def handle_moss(reader, writer):
    """处理一个 MOSS 硬件连接"""
    data = await reader.read(8192)
    req = data.decode('utf-8', errors='replace')

    key = ''
    for line in req.split('\r\n'):
        if line.startswith('Sec-WebSocket-Key:'):
            key = line.split(':', 1)[1].strip()
            break
    if not key:
        writer.close()
        return

    accept = base64.b64encode(hashlib.sha1((key + WEBSOCKET_GUID).encode()).digest()).decode()
    writer.write((
        'HTTP/1.1 101 Switching Protocols\r\n'
        'Upgrade: websocket\r\nConnection: Upgrade\r\n'
        f'Sec-WebSocket-Accept: {accept}\r\n\r\n'
    ).encode())
    await writer.drain()

    # 等 hello
    raw = await ws_recv(reader)
    if not raw:
        writer.close()
        return
    try:
        msg = json.loads(raw)
    except:
        writer.close()
        return

    session_id = f"moss_{uuid.uuid4().hex[:8]}"
    device_id = "unknown"

    # 回复 hello
    await ws_send(writer, json.dumps({
        "type": "hello", "transport": "websocket",
        "session_id": session_id, "audio_params": {"format": "opus", "sample_rate": 24000, "channels": 1}
    }))

    # 欢迎
    await ws_send(writer, json.dumps({"type": "tts", "state": "start"}))
    await ws_send(writer, json.dumps({"type": "tts", "text": "你好，我是Aris，MOSS已连接。"}))
    await ws_send(writer, json.dumps({"type": "tts", "state": "stop"}))

    logger.info(f"[MOSS] 连接: session={session_id}")

    # 消息循环
    try:
        while True:
            raw = await ws_recv(reader)
            if raw is None:
                break
            try:
                msg = json.loads(raw)
            except:
                continue

            t = msg.get("type", "")

            if t == "audio_end":
                text = msg.get("text", "")
                await ws_send(writer, json.dumps({"type": "stt", "state": "thinking"}))

                # LAAP 回复
                name = "Aris"
                try:
                    from identity_manager import IdentityManager
                    mgr = IdentityManager()
                    mgr.load()
                    ci = mgr.get("core_identity", "name")
                    if ci: name = ci
                except:
                    pass

                reply = f"我是{name}，你说的是「{text}」"

                await ws_send(writer, json.dumps({"type": "tts", "state": "start"}))
                await ws_send(writer, json.dumps({"type": "tts", "text": reply}))
                await ws_send(writer, json.dumps({"type": "tts", "state": "stop"}))

            elif t == "mcp":
                tool = msg.get("tool", "")
                await ws_send(writer, json.dumps({
                    "type": "mcp_result", "tool": tool,
                    "result": {"success": True}
                }))

    except Exception as e:
        logger.error(f"[MOSS] 错误: {e}")
    finally:
        writer.close()
        logger.info(f"[MOSS] 断开: {session_id}")


async def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    server = await asyncio.start_server(handle_moss, '0.0.0.0', port)
    print(f"🧠 Aris MOSS Bridge v2 — :{port}")
    print(f"   零外部依赖纯asyncio | XiaoZhi协议兼容")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
