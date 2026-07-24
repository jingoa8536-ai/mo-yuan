"""Aris MOSS Bridge v3 — 稳定版 (纯asyncio WebSocket)"""
import sys, os, json, asyncio, struct, hashlib, base64, uuid, logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("aris.moss")

sys.path.insert(0, str(Path("D:/LAAP/aris_brain")))

GUID = "258EAFA5-E914-47DA-95CA-5AB9DFF7CE1B"


def decode_frame(data):
    """解码 WebSocket 帧, 返回 (opcode, payload, rest)"""
    if len(data) < 2:
        return None, None, data
    opcode = data[0] & 0x0f
    masked = bool(data[1] & 0x80)
    length = data[1] & 0x7f
    pos = 2
    if length == 126:
        length = struct.unpack('>H', data[pos:pos+2])[0]
        pos += 2
    elif length == 127:
        length = struct.unpack('>Q', data[pos:pos+8])[0]
        pos += 8
    mask_key = data[pos:pos+4] if masked else b''
    pos += 4 if masked else 0
    payload = data[pos:pos+length]
    if masked:
        payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
    rest = data[pos+length:]
    return opcode, payload.decode('utf-8', errors='replace'), rest


def encode_frame(text, server_mode=True):
    """编码 WebSocket 帧 (服务端模式: 不mask)"""
    data = text.encode('utf-8') if isinstance(text, str) else text
    if len(data) < 126:
        header = bytes([0x81, len(data)])
    else:
        header = bytes([0x81, 126]) + struct.pack('>H', len(data))
    return header + data


async def handle(reader, writer):
    try:
        # 读HTTP请求
        data = await asyncio.wait_for(reader.read(8192), timeout=10)
    except:
        writer.close()
        return

    req = data.decode('utf-8', errors='replace')
    key = ''
    for line in req.split('\r\n'):
        if line.lower().startswith('sec-websocket-key:'):
            key = line.split(':', 1)[1].strip()
            break

    if not key:
        writer.write(b'HTTP/1.1 400 Bad Request\r\n\r\n')
        await writer.drain()
        writer.close()
        return

    accept = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
    writer.write(
        'HTTP/1.1 101 Switching Protocols\r\n'
        'Upgrade: websocket\r\nConnection: Upgrade\r\n'
        f'Sec-WebSocket-Accept: {accept}\r\n\r\n'.encode()
    )
    await writer.drain()

    buf = data  # 可能有帧跟在HTTP请求后面
    session_id = f'moss_{uuid.uuid4().hex[:8]}'

    # 处理已缓冲的数据（hello 可能跟HTTP请求一起到达）
    hello_received = False
    while buf:
        opcode, text, buf = decode_frame(buf)
        if opcode is None:
            break
        if opcode == 8:
            writer.close()
            return
        if opcode == 1 and text:
            await _process_message(writer, text, session_id)
            hello_received = True

    # 等待 hello（如果是分开到达的）
    if not hello_received:
        while True:
            b = await asyncio.wait_for(reader.read(65536), timeout=600)
            if not b:
                break
            opcode, text, rest = decode_frame(b)
            if opcode == 1 and text:
                await _process_message(writer, text, session_id)
                hello_received = True
                buf = rest
                break
            elif opcode == 8:
                writer.close()
                return

    # 发欢迎
    await _send_msg(writer, 'tts_state', state='start')
    await _send_msg(writer, 'tts_text', text='你好，我是Aris，MOSS已连接')
    await _send_msg(writer, 'tts_state', state='stop')
    logger.info(f"[MOSS] 已连接: {session_id}")

    # 持续读帧（包含刚才剩余的 buf）
    if buf:
        while buf:
            opcode, text, buf = decode_frame(buf)
            if opcode is None:
                break
            if opcode == 8:
                writer.close()
                return
            if opcode == 1 and text:
                await _process_message(writer, text, session_id)

    while True:
        try:
            b = await asyncio.wait_for(reader.read(65536), timeout=600)
        except asyncio.TimeoutError:
            break
        except:
            break
        if not b:
            break
        buf = b
        while buf:
            opcode, text, buf = decode_frame(buf)
            if opcode is None:
                break
            if opcode == 8:
                writer.close()
                return
            if opcode == 1 and text:
                await _process_message(writer, text, session_id)

    writer.close()
    logger.info(f"[MOSS] 断开: {session_id}")


async def _process_message(writer, text, session_id):
    """处理一条JSON消息"""
    try:
        msg = json.loads(text)
    except:
        return
    t = msg.get('type', '')
    
    if t == 'hello':
        await _send_msg(writer, 'hello', transport='websocket', session_id=session_id,
                        audio_params={'format': 'opus', 'sample_rate': 24000})
    elif t == 'audio_end':
        user_text = msg.get('text', '')
        audio_data = msg.get('audio', None)
        
        # 如果有音频数据, 用 ASR
        if not user_text and audio_data:
            import base64
            try:
                audio_bytes = base64.b64decode(audio_data)
                from aris_voice_pipeline import transcribe
                user_text = await transcribe(audio_bytes)
                logger.info(f"[ASR] {user_text}")
            except Exception as e:
                logger.error(f"[ASR] 失败: {e}")
        
        # LAAP 回复
        name = "Aris"
        try:
            from identity_manager import IdentityManager
            mgr = IdentityManager()
            mgr.load()
            ci = mgr.get('core_identity', 'name')
            if ci: name = ci
        except:
            pass
        reply = f"我是{name}，你说的是「{user_text}」"
        await _send_msg(writer, 'tts_state', state='start')
        await _send_msg(writer, 'tts_text', text=reply)
        await _send_msg(writer, 'tts_state', state='stop')


async def _send_msg(writer, msg_type, **kwargs):
    """发送消息"""
    payload = json.dumps({"type": msg_type, **kwargs}, ensure_ascii=False)
    writer.write(encode_frame(payload))
    await writer.drain()


async def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    server = await asyncio.start_server(handle, '0.0.0.0', port)
    print(f"🧠 Aris MOSS Bridge v3 — :{port}")
    print(f"   纯asyncio WebSocket (RFC 6455)")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
