"""
Aris MOSS 桌面测试客户端 — 模拟 MOSS 硬件的语音对话
====================================================
用电脑麦克风录音 → 连 MOSS Bridge → 播放 TTS 回复

用法:
  python moss_test_client.py              # 录音 + 对话
  python moss_test_client.py --text "你好" # 文字模式
"""

import sys, os, json, asyncio, tempfile, time

MOSS_WS = "ws://127.0.0.1:8765"

try:
    import sounddevice as sd
    import soundfile as sf
    import numpy as np
    MIC_AVAILABLE = True
except:
    MIC_AVAILABLE = False
    print("⚠️ sounddevice 未安装, 使用文本模式")

try:
    import speech_recognition as sr
    ASR_AVAILABLE = True
except:
    ASR_AVAILABLE = False


async def record_and_transcribe(duration: float = 5.0) -> str:
    """录音 → ASR 转文字"""
    if not MIC_AVAILABLE:
        return input("请输入文字: ")

    print(f"\n🎤 录音中 ({duration}秒)...")
    
    # 录音
    fs = 16000
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
    sd.wait()
    
    print("📝 识别中...")
    
    # 保存为 WAV
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name
    import soundfile
    soundfile.write(wav_path, recording, fs)
    
    # ASR
    if ASR_AVAILABLE:
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as src:
            audio = recognizer.record(src)
        try:
            text = recognizer.recognize_google(audio, language="zh-CN")
            print(f"  → 识别: {text}")
            return text
        except Exception as e:
            print(f"  → 识别失败: {e}")
            return ""
    else:
        return f"[音频文件: {wav_path}]"


async def moss_test():
    """测试 MOSS 全链路"""
    print("=" * 50)
    print("🧠 Aris MOSS 桌面测试")
    print("=" * 50)
    print(f"  连接: {MOSS_WS}")
    print(f"  麦克风: {'✅' if MIC_AVAILABLE else '❌'}")
    print(f"  ASR:   {'✅' if ASR_AVAILABLE else '❌'}")
    print()

    try:
        import websockets
    except ImportError:
        print("❌ 需要安装 websockets")
        return

    async with websockets.connect(MOSS_WS) as ws:
        # Hello 握手
        await ws.send(json.dumps({
            "type": "hello", "version": 1,
            "features": {"mcp": True},
            "transport": "websocket",
            "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60}
        }))
        resp = json.loads(await asyncio.wait_for(ws.recv(), 10))
        print(f"✅ 连接成功: session={resp.get('session_id','?')}")

        # 收欢迎消息
        welcome = json.loads(await asyncio.wait_for(ws.recv(), 10))
        print(f"🤖 Aris: {welcome.get('text','')}")
        print()

        # 对话循环
        round_num = 0
        while True:
            round_num += 1
            print(f"\n--- 第{round_num}轮 ---")

            # 录音
            text = await record_and_transcribe(5.0)
            if not text:
                print("未识别到语音")
                continue
            if text.lower() in ["退出", "exit", "quit", "q"]:
                break

            # 发送给 MOSS Bridge
            await ws.send(json.dumps({"type": "audio_end", "text": text}))
            print("⏳ 等待回复...")

            # 接收回复 (可能有多条消息)
            reply_text = ""
            while True:
                raw = await asyncio.wait_for(ws.recv(), 30)
                if isinstance(raw, bytes):
                    # TTS 音频数据
                    pass
                else:
                    msg = json.loads(raw)
                    t = msg.get("type", "")
                    if t == "tts" and msg.get("state") == "start":
                        pass  # TTS 开始
                    elif t == "tts" and msg.get("state") == "stop":
                        break  # TTS 结束
                    elif t == "stt":
                        print(f"  [{msg.get('state','')}]")
                    elif "text" in msg:
                        reply_text = msg["text"]
                        print(f"🤖 Aris: {reply_text}")

            if not reply_text:
                break

    print("\n👋 对话结束")


if __name__ == "__main__":
    asyncio.run(moss_test())
