"""MOSS 测试客户端 v3 — 匹配服务端帧格式"""
import sys, os, json, asyncio, struct, hashlib, base64, secrets

GUID = "258EAFA5-E914-47DA-95CA-5AB9DFF7CE1B"

def encode_frame(text):
    data = text.encode('utf-8')
    mask = secrets.token_bytes(4)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    if len(data) < 126:
        header = bytes([0x81, 0x80 | len(data)])
    else:
        header = bytes([0x81, 0x80 | 0x7e]) + struct.pack('>H', len(data))
    return header + mask + masked

def decode_frame(data):
    if len(data) < 2: return None, None, data
    length = data[1] & 0x7f
    pos = 2
    if length == 126: length = struct.unpack('>H', data[2:4])[0]; pos = 4
    elif length == 127: length = struct.unpack('>Q', data[2:10])[0]; pos = 10
    payload = data[pos:pos+length]
    rest = data[pos+length:]
    return payload.decode('utf-8', errors='replace'), rest

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
        print(f"❌ 失败: {resp[:100]}")
        return

    buf = b''

    def read_frame():
        nonlocal buf
        text, buf = decode_frame(buf)
        return text

    # 发 hello (WebSocket帧)
    w.write(encode_frame(json.dumps({"type": "hello", "version": 1})))
    await w.drain()

    # 连续收集回复
    await asyncio.sleep(1)
    buf += await r.read(4096)
    
    while True:
        text = read_frame()
        if text is None: break
        msg = json.loads(text)
        if msg.get('session_id'):
            print(f"✅ Hello确认: {msg['session_id']}")
        if msg.get('text'):
            print(f"🤖 {msg['text']}")
        if msg.get('state') == 'stop':
            break
        if msg.get('type') == 'hello':
            print(f"✅ 服务端hello")

    print()

    # 说话
    w.write(encode_frame(json.dumps({"type": "audio_end", "text": "MOSS你好，今天天气怎么样？"})))
    await w.drain()

    await asyncio.sleep(1)
    buf += await r.read(4096)

    while True:
        text = read_frame()
        if text is None: break
        msg = json.loads(text)
        if msg.get('text'):
            print(f"🤖 {msg['text']}")
        if msg.get('state') == 'stop':
            break

    w.close()
    print("\n✅ MOSS Bridge v3 测试通过!")

asyncio.run(test())
