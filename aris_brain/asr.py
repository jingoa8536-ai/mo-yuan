"""
Aris — Speech Recognition Module (语音识别)
=============================================

Gives Aris ears. Uses faster-whisper for local speech recognition
running on the RTX 4070 SUPER via CUDA.

Architecture:
  ┌──────────────────────────────────────────────┐
  │  SpeechRecognition                            │
  │  ├── faster-whisper (local, CUDA)            │
  │  │   └── medium model (good accuracy/speed)  │
  │  ├── Microphone capture via sounddevice      │
  │  └── Wake word detection (optional)          │
  ├──────────────────────────────────────────────┤
  │  Usage:                                      │
  │    asr = SpeechRecognition()                 │
  │    asr.start()       # background listening  │
  │    text = asr.listen(timeout=5)  # one shot │
  │    asr.stop()                                │
  └──────────────────────────────────────────────┘
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Callable
import logging, os, queue, tempfile, threading, time, wave
from pathlib import Path

logger = logging.getLogger("aris.asr")

SAMPLE_RATE = 16000
CHANNELS = 1
SILENCE_THRESHOLD = 0.001  # RMS threshold for silence detection (lowered for quiet mics)
SILENCE_DURATION = 1.5     # seconds of silence = end of utterance


class SpeechRecognition:
    """
    Local speech recognition via faster-whisper.

    Captures microphone audio, transcribes with whisper,
    returns text to the cognitive cycle.
    """

    def __init__(self, model_size: str = "medium",
                 language: str = "zh",
                 device: str = "auto"):
        self.model_size = model_size
        self.language = language
        self.device = device  # "auto" → CUDA if available

        self._model = None
        self._running = False
        self._listening = False
        self._thread: Optional[threading.Thread] = None
        self._audio_queue: queue.Queue = queue.Queue()
        self._result_queue: queue.Queue = queue.Queue()

        # Wake word callback
        self._wake_callbacks: List[Callable] = []

        # Stats
        self.total_transcriptions = 0

        # Check availability
        self._whisper_available = self._check_whisper()
        self._audio_available = self._check_audio()

        logger.info(f"[ASR] faster-whisper={'✓' if self._whisper_available else '✗'} "
                    f"audio={'✓' if self._audio_available else '✗'}")

    def _check_whisper(self) -> bool:
        """Check if faster-whisper is installed."""
        try:
            import faster_whisper
            return True
        except ImportError:
            return False

    def _check_audio(self) -> bool:
        """Check if audio input is available."""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            # Check for any input device
            for i, d in enumerate(devices):
                if d.get('max_input_channels', 0) > 0:
                    return True
            return False
        except Exception:
            return False

    # ══════════════════════════════════════════════
    # Lifecycle
    # ══════════════════════════════════════════════

    @property
    def is_available(self) -> bool:
        """Full availability: whisper + audio input."""
        return self._whisper_available and self._audio_available

    def load_model(self):
        """Load the whisper model (lazy-loaded on first use)."""
        if self._model is not None:
            return

        if not self._whisper_available:
            logger.error("[ASR] faster-whisper not installed")
            return

        try:
            import faster_whisper
            # Auto-detect device
            device = "cuda"
            try:
                import torch
                if not torch.cuda.is_available():
                    device = "cpu"
            except Exception:
                device = "cpu"

            compute_type = "float16" if device == "cuda" else "int8"
            logger.info(f"[ASR] Loading {self.model_size} model on {device} ({compute_type})...")

            self._model = faster_whisper.WhisperModel(
                model_size_or_path=self.model_size,
                device=device,
                compute_type=compute_type,
            )
            logger.info(f"[ASR] Model loaded: {self.model_size} on {device}")
        except Exception as e:
            logger.error(f"[ASR] Model load failed: {e}")
            self._whisper_available = False

    # ══════════════════════════════════════════════
    # One-shot listen
    # ══════════════════════════════════════════════

    def listen(self, timeout: float = 10.0) -> Optional[str]:
        """
        Listen for one utterance and transcribe.

        Args:
            timeout: Max seconds to wait for speech

        Returns:
            Transcribed text, or None if nothing heard
        """
        if not self.is_available:
            logger.warning("[ASR] Not available")
            return None

        self.load_model()
        if not self._model:
            return None

        import sounddevice as sd

        logger.info("[ASR] Listening...")

        # Record audio until silence detected
        audio_buffer = []
        silence_start = None
        started = False

        def callback(indata, frames, time_info, status):
            nonlocal silence_start, started
            if status:
                logger.debug(f"[ASR] Audio status: {status}")

            # Check RMS for speech detection
            import numpy as np
            rms = np.sqrt(np.mean(indata ** 2))

            if rms > SILENCE_THRESHOLD:
                if not started:
                    logger.debug("[ASR] Speech detected")
                started = True
                silence_start = None
                audio_buffer.append(indata.copy())

            elif started:
                if silence_start is None:
                    silence_start = time.time()
                elif time.time() - silence_start > SILENCE_DURATION:
                    raise sd.CallbackStop()

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                callback=callback,
                dtype='float32',
            ):
                sd.sleep(int(timeout * 1000))

        except sd.CallbackStop as e:
            logger.debug(f"操作失败: {e}")
        except Exception as e:
            logger.error(f"[ASR] Record error: {e}")
            return None

        if not audio_buffer:
            logger.debug("[ASR] No speech detected")
            return None

        # Convert buffer to array
        import numpy as np
        audio_data = np.concatenate(audio_buffer, axis=0).flatten()

        # Transcribe
        try:
            segments, info = self._model.transcribe(
                audio_data,
                language=self.language,
                beam_size=5,
                vad_filter=True,
            )

            text = " ".join(seg.text for seg in segments)
            self.total_transcriptions += 1

            if text.strip():
                logger.info(f"[ASR] Transcribed: '{text[:60]}'")
                return text.strip()
            else:
                logger.debug("[ASR] Empty transcription")
                return None

        except Exception as e:
            logger.error(f"[ASR] Transcription error: {e}")
            return None

    # ══════════════════════════════════════════════
    # Continuous listening (background)
    # ══════════════════════════════════════════════

    def start_listening(self):
        """Start background listening. Results go to result_queue."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("[ASR] Background listening started")

    def stop_listening(self):
        """Stop background listening."""
        self._running = False
        logger.info("[ASR] Background listening stopped")

    def _listen_loop(self):
        """Continuous listen → transcribe loop."""
        while self._running:
            try:
                text = self.listen(timeout=3.0)
                if text:
                    self._result_queue.put(text)
                    # Also notify wake callbacks
                    for cb in self._wake_callbacks:
                        try:
                            cb(text)
                        except Exception as e:
                            logger.debug(f"操作失败: {e}")
            except Exception as e:
                logger.debug(f"[ASR] Loop error: {e}")
                time.sleep(0.5)

    def get_transcription(self, timeout: float = 0.1) -> Optional[str]:
        """Get next transcription from background listening."""
        try:
            return self._result_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def on_wake_word(self, callback: Callable):
        """Register callback for wake word detection."""
        self._wake_callbacks.append(callback)

    # ══════════════════════════════════════════════
    # Status
    # ══════════════════════════════════════════════

    def stats(self) -> Dict[str, Any]:
        return {
            "available": self.is_available,
            "model": self.model_size,
            "language": self.language,
            "transcriptions": self.total_transcriptions,
            "listening": self._running,
            "whisper_loaded": self._model is not None,
        }
