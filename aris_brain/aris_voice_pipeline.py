"""Aris Voice Pipeline — 纯本地语音流 (ASR + TTS)"""
import sys, os, json, asyncio, tempfile, logging
from pathlib import Path
import numpy as np

logger = logging.getLogger("aris.voice")

# ─── ASR ──────────────────────────────────────────

_ASR_MODEL = None

def get_asr():
    global _ASR_MODEL
    if _ASR_MODEL is None:
        from faster_whisper import WhisperModel
        logger.info("加载 Whisper tiny (CPU int8)...")
        _ASR_MODEL = WhisperModel('tiny', device='cpu', compute_type='int8')
    return _ASR_MODEL

async def transcribe(audio_bytes: bytes, sample_rate: int = 16000) -> str:
    """语音转文字 (异步包装)"""
    model = get_asr()
    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    
    loop = asyncio.get_event_loop()
    segments, info = await loop.run_in_executor(
        None, lambda: model.transcribe(audio, beam_size=1, language='zh')
    )
    result = ' '.join(s.text for s in segments)
    return result.strip()

async def transcribe_file(wav_path: str) -> str:
    """从WAV文件转文字"""
    model = get_asr()
    loop = asyncio.get_event_loop()
    segments, info = await loop.run_in_executor(
        None, lambda: model.transcribe(wav_path, beam_size=1, language='zh')
    )
    result = ' '.join(s.text for s in segments)
    return result.strip()

# ─── TTS ──────────────────────────────────────────

_TTS_AVAILABLE = False
try:
    import edge_tts
    _TTS_AVAILABLE = True
except:
    pass

async def synthesize(text: str) -> bytes:
    """文字转语音 (返回 WAV bytes)"""
    if not _TTS_AVAILABLE:
        return b''
    communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
    audio = b''
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
    return audio

async def synthesize_stream(text: str):
    """流式 TTS (逐块生成)"""
    if not _TTS_AVAILABLE:
        return
    communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            yield chunk["data"]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=" * 50)
    print("Aris Voice Pipeline v1")
    print("=" * 50)
    print(f"  ASR: faster-whisper tiny ✅")
    print(f"  TTS: {'edge-tts ✅' if _TTS_AVAILABLE else '❌'}")
    print()
    print("用法: from aris_voice_pipeline import transcribe, synthesize")
