"""
Aris MOSS 测试 — 纯 asyncio 客户端 (零依赖)
测试命令: python moss_test_v2.py
"""
import sys, os, json, asyncio, struct, hashlib, base64, secrets

GUID = "258EAFA5-E914-47DA-95CA-5AB9DFF7CE1B"

def create_frame(data, opcode=0x1):
    """创建 WebSocket 帧 (客户端模式: masked)"""
    mask = secrets.token_bytes(4)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data.encode() if isinstance(data, str) else data))
    payload = data.encode() if isinstance(data, str) else data
    if len(payload) < 126:
        return bytes([0x80 | opcode, 0x80 | len(payload)]) + mask + masked
    else:
        return bytes([0x80 | opcode, 0x80 | 0x7e]) + struct.pack('>H', len(payload)) + mask + masked

async def read_frame(reader):
    """读取 WebSocket 帧"""
    b = await reader.readexactly(2)
    opcode = b[0] & 0x0f
    length = b[1] & 0x7f
    if length == 126:
        length = struct.unpack('>H', await reader.readexactly(2))[0]
    elif length == 127:
        length = struct.unpack('>Q', await reader.readexactly(8))[0]
    payload = await reader.readexactly(length)
    return opcode, payload.decode(errors='replace')

async def test():
    print("连接 MOSS Bridge...")
    r, w = await asyncio.open_connection('127.0.0.1', 8766)
    key = base64.b64encode(secrets.token_bytes(16)).decode()
    req = (f"GET / HTTP/1.1\r\nHost: 127.0.0.1:8766\r\n"
           f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
           f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
    w.write(req.encode())
    await w.drain()
    resp = (await r.read(4096)).decode()
    if '101' in resp:
        print("✅ WebSocket 握手成功")
    else:
        print(f"❌ 握手失败: {resp[:100]}")
        return

    # 发 hello
    w.write(create_frame(json.dumps({"type": "hello", "version": 1})))
    await w.drain()

    # 收回复
    op, text = await read_frame(r)
    print(f"收到: {text[:100]}")

    op, text = await read_frame(r)
    print(f"收到: {text[:100]}")

    op, text = await read_frame(r)
    msg = json.loads(text)
    if msg.get('text'):
        print(f"🤖 欢迎: {msg['text']}")

    op, text = await read_frame(r)  # stop
    print(f"收到: {text[:80]}")

    # 说话
    print()
    print("发送: MOSS你好！")
    w.write(create_frame(json.dumps({"type": "audio_end", "text": "MOSS你好！"})))
    await w.drain()

    # 收回复
    while True:
        op, text = await read_frame(r)
        msg = json.loads(text)
        if msg.get('text'):
            print(f"🤖 {msg['text']}")
        if msg.get('state') == 'stop':
            break

    w.close()
    print("\n✅ MOSS Bridge 测试通过!")

asyncio.run(test())
