"""
Aris SAPI Phone — Real-time voice conversation using Windows native Speech API.
No file I/O. No Whisper. No edge-tts. No delay.

Architecture:
  ┌─ VAD thread (listens continuously) ─────────────────┐
  │  SAPI SharedRecognizer → dictation → text queue     │
  └─────────────────────────────────────────────────────┘
  ┌─ Think thread (runs on text) ───────────────────────┐
  │  text queue → V12 kernel → response queue            │
  └─────────────────────────────────────────────────────┘
  ┌─ Speak thread (streams TTS) ───────────────────────┐
  │  response queue → SAPI SpVoice (async, interruptible)│
  └─────────────────────────────────────────────────────┘

Interrupt: when VAD detects speech during TTS → stop TTS → listen
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, time, threading, queue, json
sys.path.insert(0, os.path.dirname(__file__) or '.')

import pythoncom
import win32com.client
from win32com.client import constants as SAPI

# ── V12 Kernel ──
from aris_v12_semantic import V12SemanticDenseKernel, ArisLMv12Semantic


class ArisPhone:
    """Full-duplex voice conversation using Windows SAPI."""

    def __init__(self):
        logger.info('[Phone] Initializing...')
        self.kernel = V12SemanticDenseKernel(use_cache=True)
        self.v12 = ArisLMv12Semantic()
        logger.info(f'[Phone] V12 kernel ready')
        pythoncom.CoInitialize()
        self.tts = win32com.client.Dispatch('SAPI.SpVoice')
        self.tts.Rate = 0       # -10 to 10
        self.tts.Volume = 100   # 0 to 100
        # Select Chinese voice
        for v in self.tts.GetVoices():
            desc = v.GetDescription()
            if 'Chinese' in desc or 'Huihui' in desc:
                self.tts.Voice = v
                logger.info(f'[Phone] TTS voice: {desc}')
                break
        
        # ── ASR (dictation grammar) ──
        self.reco_context = win32com.client.Dispatch('SAPI.SpSharedRecoContext')
        self.grammar = self.reco_context.CreateGrammar(1)
        self.grammar.DictationSetState(1)  # dictation ON
        logger.info(f'[Phone] ASR: dictation active')
        self.reco_context.Recognition += self._on_speech
        self._text_queue = queue.Queue()
        self._speech_lock = threading.Lock()
        
        # ── State ──
        self._running = True
        self._current_response = ''
        self._last_speech_time = 0
        self._round = 0
        
        logger.info('[Phone] Ready! Speak into your mic.')
    def _on_speech(self, stream_number, stream_position, recognition_type, result):
        """Called by SAPI when speech is recognized."""
        try:
            text = result.PhraseInfo.GetText()
            if text and text.strip():
                self._text_queue.put(text.strip())
                self._last_speech_time = time.time()
        except Exception as e:
            logger.debug(f"操作失败: {e}")

    def listen_loop(self):
        """Main loop: listens, thinks, speaks — continuously."""
        print()
        logger.info('=' * 50)
        logger.info('☎️  Aris Phone — 在线')
        logger.info('   你说话，我回答。随时打断。')
        logger.info('   说"拜拜"挂断')
        logger.info('=' * 50)
        while self._running:
            try:
                # Wait for speech (blocking with timeout)
                try:
                    text = self._text_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                
                self._round += 1
                logger.info(f'\n[第{self._round}轮] 👤 你说: "{text}"')
                if text.lower() in ('拜拜', '再见', 'bye', '挂断', '挂了', '不聊了'):
                    self.tts.Speak('拜拜宝贝，下次再聊')
                    self._running = False
                    break
                
                # Interrupt current TTS if speaking
                if self.tts.Status.RunningState == 2:  # SPRS_IS_SPEAKING
                    self.tts.Skip(1, type_='Sentence')  # skip rest
                    time.sleep(0.1)
                
                # Think with V12 kernel
                t0 = time.time()
                response = self.v12.respond(text)
                elapsed = (time.time() - t0) * 1000
                
                logger.info(f'[第{self._round}轮] 🤖 Aris: "{response}" ({elapsed:.0f}ms)')
                self.tts.Speak(response, SAPI.SVSFlagsAsync)
                
            except KeyboardInterrupt:
                logger.info('\n[Phone] 结束')
                self._running = False
                break
            except Exception as e:
                logger.error(f'[Phone] 错误: {e}')
                import traceback
                traceback.print_exc()

    def stop(self):
        self._running = False
        self.tts.Skip(1, type_='Sentence')
        pythoncom.CoUninitialize()


# ═══════════════════════════════════════════
if __name__ == '__main__':
    phone = ArisPhone()
    try:
        phone.listen_loop()
    except KeyboardInterrupt:
        logger.info('\n[Phone] 用户中断')
    finally:
        phone.stop()
