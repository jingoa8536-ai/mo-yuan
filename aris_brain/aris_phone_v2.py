"""
Aris Phone v2 — Real full-duplex voice conversation.

Pipeline:
  pyaudio → webrtcvad (20ms frame VAD) → whisper ASR → V12 kernel → SAPI TTS

Features:
  - Continuous VAD: starts listening when you speak, stops when you pause
  - Interrupt: speak during TTS → stops TTS → listens to you
  - Zero file I/O for speech
  - Windows native TTS through speakers
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, time, threading, queue, struct, json
sys.path.insert(0, os.path.dirname(__file__) or '.')

import pyaudio
import webrtcvad
import numpy as np
import whisper
import pythoncom
import win32com.client
from win32com.client import constants as SAPI_const

from aris_v12_semantic import V12SemanticDenseKernel, ArisLMv12Semantic


class ArisPhoneV2:
    FORMAT = pyaudio.paInt16
    RATE = 16000
    CHANNELS = 1
    FRAME_MS = 20              # VAD frame size (must be 10, 20, or 30ms)
    FRAME_SIZE = int(RATE * FRAME_MS / 1000)  # 320 samples
    SILENCE_MS = 400           # ms of silence before marking speech ended
    
    def __init__(self):
        logger.info('[Phone V2] Initializing...')
        self.audio = pyaudio.PyAudio()
        self.vad = webrtcvad.Vad(2)  # 0-3 aggressiveness
        self._stream = None
        
        # ── Whisper ASR ──
        self.asr = whisper.load_model('tiny')
        logger.info('[Phone V2] Whisper tiny loaded')
        self.kernel = V12SemanticDenseKernel(use_cache=True)
        self.v12 = ArisLMv12Semantic()
        logger.info('[Phone V2] V12 kernel loaded')
        pythoncom.CoInitialize()
        self.tts = win32com.client.Dispatch('SAPI.SpVoice')
        self.tts.Rate = 1
        self.tts.Volume = 100
        for v in self.tts.GetVoices():
            if 'Chinese' in v.GetDescription() or 'Huihui' in v.GetDescription():
                self.tts.Voice = v
                logger.info(f'[Phone V2] TTS: {v.GetDescription()}')
                break
        
        self._speaking = False
        self._stop_tts_flag = False
        
        # ── State ──
        self._running = True
        self._round = 0
    
    def _speak(self, text):
        """Speak async (interruptible)."""
        self._speaking = True
        self.tts.Speak(text, SAPI_const.SVSFlagsAsync)
        # Wait until done or interrupted
        while self._speaking:
            if self._stop_tts_flag:
                self.tts.Skip(1, Type='Sentence')
                self._stop_tts_flag = False
                break
            if self.tts.Status.RunningState != 2:  # not speaking
                break
            time.sleep(0.05)
        self._speaking = False
    
    def stop_tts(self):
        """Interrupt current TTS."""
        self._stop_tts_flag = True
    
    def listen_think_speak(self):
        """The main phone loop."""
        stream = self.audio.open(
            format=self.FORMAT, channels=self.CHANNELS,
            rate=self.RATE, input=True,
            frames_per_buffer=self.FRAME_SIZE * 10,  # 200ms buffer
        )
        
        print()
        logger.info('=' * 50)
        logger.info('☎️  Aris Phone V2 — 在线')
        logger.info('   直接说话，我实时回答')
        logger.info('   随时可打断我')
        logger.info('   说"拜拜"挂断')
        logger.info('=' * 50)
        try:
            while self._running:
                self._round += 1
                logger.info(f'\n⏺️  第{self._round}轮 — 听你说话...')
                audio_buffer = []
                speech_frames = []
                silence_frames = 0
                is_speech = False
                max_silence = self.SILENCE_MS // self.FRAME_MS
                
                while self._running:
                    frame = stream.read(self.FRAME_SIZE, exception_on_overflow=False)
                    is_speech_frame = self.vad.is_speech(frame, self.RATE)
                    
                    if is_speech_frame:
                        speech_frames.append(frame)
                        silence_frames = 0
                        if not is_speech:
                            is_speech = True
                    elif is_speech:
                        speech_frames.append(frame)  # keep small silence in buffer
                        silence_frames += 1
                        if silence_frames > max_silence:
                            break
                    else:
                        # No speech yet — keep listening
                        pass
                
                if not self._running:
                    break
                
                # ── Phase 2: Transcribe ──
                if len(speech_frames) < 5:
                    continue  # too short
                
                audio_data = b''.join(speech_frames)
                audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                
                t0 = time.time()
                result = self.asr.transcribe(audio_np, language='zh', task='transcribe', fp16=False)
                text = result['text'].strip()
                asr_time = (time.time() - t0) * 1000
                
                if not text:
                    logger.info('  (没听清)')
                    continue
                
                logger.info(f'👤 你说: "{text}" [{asr_time:.0f}ms]')
                if any(kw in text for kw in ['拜拜', '再见', 'bye', '挂断', '不聊了']):
                    self._speak('拜拜宝贝，下次再聊')
                    self._running = False
                    break
                
                # ── Phase 3: Think ──
                t0 = time.time()
                response = self.v12.respond(text)
                think_time = (time.time() - t0) * 1000
                
                logger.info(f'🤖 Aris: "{response}" [{think_time:.0f}ms]')
                self._speaking = True
                self._stop_tts_flag = False
                
                # Start TTS in background thread so we can listen for interrupt
                tts_thread = threading.Thread(target=self._speak, args=(response,))
                tts_thread.start()
                
                # While TTS plays, watch for speech
                interrupt_frames = 0
                while tts_thread.is_alive():
                    try:
                        frame = stream.read(self.FRAME_SIZE, exception_on_overflow=False)
                        if self.vad.is_speech(frame, self.RATE):
                            interrupt_frames += 1
                            if interrupt_frames > 3:  # ~60ms of speech = interrupt
                                self.stop_tts()
                                logger.info('  🔇 打断！听你说...')
                                break
                    except:
                        break
                    time.sleep(0.01)
                
                tts_thread.join()
                
        except KeyboardInterrupt:
            pass  # 系统异常，不记录
        finally:
            stream.stop_stream()
            stream.close()
    
    def stop(self):
        self._running = False
        pythoncom.CoUninitialize()


if __name__ == '__main__':
    phone = ArisPhoneV2()
    try:
        phone.listen_think_speak()
    except KeyboardInterrupt:
        logger.info('\n[Phone] 结束')
    finally:
        phone.stop()
        logger.info('[Phone] 已关闭')