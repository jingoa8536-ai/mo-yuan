"""Aris MOSS 桌面语音测试 — 录音→ASR→MOSS→TTS 全链路"""
import sys, os, json, asyncio, tempfile, base64
import sounddevice as sd
import numpy as np
import soundfile as sf

# WebSocket 帧工具
import struct, hashlib, base64 as b64, secrets

GUID = "258EAFA5-E914-47DA-95CA-5AB9DFF7CE1B"

def ws_encode(text):
    data = text.encode('utf-8')
    mask = secrets.token_bytes(4)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    if len(data) < 126:
        h = bytes([0x81, 0x80 | len(data)])
    else:
        h = bytes([0x81, 0x80 | 0x7e]) + struct.pack('>H', len(data))
    return h + mask + masked

def ws_decode(data):
    if len(data) < 2: return None, data
    ln = data[1] & 0x7f
    pos = 2
    if ln == 126: ln = struct.unpack('>H', data[2:4])[0]; pos = 4
    payload = data[pos:pos+ln]
    return payload.decode('utf-8', errors='replace'), data[pos+ln:]

async def record_and_transcribe(duration=5):
    """录音 → WAV → ASR"""
    fs = 16000
    print(f"\n🎤 录音 {duration}秒...")
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
    sd.wait()
    print("  录音完成")
    
    # 保存临时WAV
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    sf.write(tmp.name, recording, fs)
    
    # ASR
    from aris_voice_pipeline import transcribe_file
    text = await transcribe_file(tmp.name)
    os.unlink(tmp.name)
    return text

async def test_voice_loop():
    print("=" * 50)
    print("🧠 Aris MOSS 语音测试")
    print("=" * 50)
    print("  端口: 8766")
    print()

    # 连接 MOSS Bridge
    r, w = await asyncio.open_connection('127.0.0.1', 8766)
    key = b64.b64encode(secrets.token_bytes(16)).decode()
    req = (f"GET / HTTP/1.1\r\nHost: 127.0.0.1:8766\r\n"
           f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
           f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
    w.write(req.encode())
    await w.drain()
    resp = (await r.read(4096)).decode()
    if '101' not in resp:
        print(f"❌ 连接失败: {resp[:100]}")
        return
    print("✅ 已连接 MOSS Bridge")

    # Hello + 欢迎
    buf = b''
    w.write(ws_encode(json.dumps({"type": "hello", "version": 1})))
    await w.drain()

    # 收回复 — 持续读到完整的多帧
    for _ in range(15):
        await asyncio.sleep(0.2)
        chunk = await r.read(8192)
        if chunk:
            buf += chunk
            # 尝试解析多帧
            while True:
                text, rest = ws_decode(buf)
                if text is None:
                    break
                buf = rest
                try:
                    msg = json.loads(text)
                except:
                    continue
                if msg.get('text'):
                    print(f"🤖 {msg['text']}")
                if msg.get('state') == 'stop':
                    break
            try:
                if msg.get('state') == 'stop':
                    break
            except:
                pass
    
    # 对话循环
    for round_num in range(3):
        print(f"\n--- 第{round_num+1}轮 ---")
        text = await record_and_transcribe(5)

        if text:
            print(f"  你说: {text}")
            # 发送到MOSS
            w.write(ws_encode(json.dumps({"type": "audio_end", "text": text})))
            await w.drain()

            # 收回复
            await asyncio.sleep(0.5)
            buf += await r.read(4096)
            reply = ''
            while buf:
                t, buf = ws_decode(buf)
                if t is None: break
                msg = json.loads(t)
                if msg.get('text'):
                    reply = msg['text']
                    print(f"🤖 {msg['text']}")
                if msg.get('state') == 'stop': break

            # TTS 朗读回复
            if reply:
                print(f"  朗读回复...")
                from aris_voice_pipeline import synthesize
                audio = await synthesize(reply)
                if audio:
                    import tempfile
                    tmp2 = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                    with open(tmp2.name, 'wb') as f:
                        f.write(audio)
                    data, fs = sf.read(tmp2.name)
                    sd.play(data, fs)
                    sd.wait()
                    os.unlink(tmp2.name)
        else:
            print("  未识别到语音")

    w.close()
    print("\n✅ 语音全链路测试完成!")

if __name__ == "__main__":
    asyncio.run(test_voice_loop())
