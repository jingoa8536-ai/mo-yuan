"""
Aris — Voice Output Module (语音合成)
=======================================

Gives Aris a voice. Uses edge-tts (Microsoft Edge TTS) for
natural-sounding speech synthesis with Chinese + English support.

Architecture:
  ┌──────────────────────────────────────────────┐
  │  VoiceOutput                                 │
  │  ├── edge-tts (primary) → .mp3 file          │
  │  ├── Play via sounddevice / pyaudio          │
  │  └── Multiple voice options (Chinese/English) │
  ├──────────────────────────────────────────────┤
  │  Usage:                                      │
  │    voice = VoiceOutput()                     │
  │    voice.say("你好，我是Aris")               │
  │    voice.say_async("Hello!", callback)       │
  └──────────────────────────────────────────────┘
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Callable
import asyncio, logging, os, subprocess, tempfile, threading, time
from pathlib import Path

logger = logging.getLogger("aris.voice")

# Supported voices
VOICES = {
    # Chinese voices
    "zh-CN-XiaoxiaoNeural": "zh-CN",   # Female, warm
    "zh-CN-YunxiNeural": "zh-CN",      # Male, lively
    "zh-CN-XiaoyiNeural": "zh-CN",     # Female, cute
    # English voices
    "en-US-AriaNeural": "en-US",       # Female, warm
    "en-US-GuyNeural": "en-US",        # Male, warm
    "en-GB-SoniaNeural": "en-GB",      # Female, British
    # Japanese
    "ja-JP-NanamiNeural": "ja-JP",     # Female
    # Cantonese
    "zh-HK-HiuGaaiNeural": "zh-HK",    # Female
}


class VoiceOutput:
    """
    Text-to-speech output using edge-tts.

    Falls back gracefully if edge-tts CLI is not available.
    """

    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural",
                 rate: str = "+0%", volume: str = "+0%"):
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self._edge_tts_available = self._check_edge_tts()

        # Thread safety for sequential speech
        self._speech_lock = threading.Lock()
        self._speaking = False

        # Stats
        self.total_utterances = 0
        self.total_audio_seconds = 0.0

        # Audio output device
        self._device = None
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            # Find default output device
            default = sd.default.device
            if isinstance(default, tuple):
                default = default[1]  # output device
            self._device = default
            logger.info(f"[Voice] Audio output device: {sd.query_devices(default)['name']}")
        except Exception:
            logger.debug("[Voice] sounddevice not available — playback disabled")

        logger.info(f"[Voice] Ready: {voice} | edge-tts={'✓' if self._edge_tts_available else '✗'}")

    def _check_edge_tts(self) -> bool:
        """Check if edge-tts CLI is installed."""
        try:
            result = subprocess.run(
                ["edge-tts", "--version"],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    # ══════════════════════════════════════════════
    # Single utterance (blocking)
    # ══════════════════════════════════════════════

    def say(self, text: str, voice: Optional[str] = None,
            output_file: Optional[str] = None, play: bool = True) -> Optional[str]:
        """
        Speak text aloud. Blocking call.

        Args:
            text: Text to speak
            voice: Override voice (default: self.voice)
            output_file: Save audio to path (optional)
            play: Play audio through speakers (default: True)

        Returns:
            Path to audio file if saved, else None
        """
        if not text or not text.strip():
            return None

        if not self._edge_tts_available:
            logger.warning("[Voice] edge-tts not available")
            return None

        voice = voice or self.voice
        with self._speech_lock:
            self._speaking = True
            try:
                # Generate audio file
                if output_file:
                    audio_path = output_file
                else:
                    fd, audio_path = tempfile.mkstemp(suffix=".mp3")
                    os.close(fd)

                cmd = [
                    "edge-tts",
                    "--voice", voice,
                    "--text", text,
                    "--write-media", audio_path,
                ]
                if self.rate != "+0%":
                    cmd.extend(["--rate", self.rate])
                if self.volume != "+0%":
                    cmd.extend(["--volume", self.volume])

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

                if result.returncode != 0:
                    logger.error(f"[Voice] edge-tts failed: {result.stderr[:200]}")
                    return None

                # Play audio
                if play:
                    self._play_audio(audio_path)

                # Update stats
                self.total_utterances += 1
                duration = self._estimate_duration(text)
                self.total_audio_seconds += duration

                return audio_path

            except subprocess.TimeoutExpired:
                logger.error("[Voice] edge-tts timed out")
                return None
            except Exception as e:
                logger.error(f"[Voice] Error: {e}")
                return None
            finally:
                self._speaking = False

    # ══════════════════════════════════════════════
    # Async speech
    # ══════════════════════════════════════════════

    def say_async(self, text: str, voice: Optional[str] = None,
                  callback: Optional[Callable] = None):
        """Speak text in background thread."""
        thread = threading.Thread(
            target=self._async_speak,
            args=(text, voice, callback),
            daemon=True,
        )
        thread.start()

    def _async_speak(self, text: str, voice: Optional[str],
                     callback: Optional[Callable]):
        result = self.say(text, voice)
        if callback:
            callback(result)

    # ══════════════════════════════════════════════
    # Audio playback
    # ══════════════════════════════════════════════

    def _play_audio(self, path: str):
        """Play an audio file through speakers."""
        ext = Path(path).suffix.lower()

        try:
            if ext == ".mp3":
                # Use ffplay or python playback
                try:
                    subprocess.run(
                        ["ffplay", "-nodisp", "-autoexit", path],
                        capture_output=True, timeout=60
                    )
                except Exception:
                    # Fallback: try reading with sounddevice
                    self._play_with_sounddevice(path)
            else:
                self._play_with_sounddevice(path)
        except Exception as e:
            logger.debug(f"[Voice] Playback failed: {e}")

    def _play_with_sounddevice(self, path: str):
        """Play using soundfile + sounddevice."""
        try:
            import soundfile as sf
            data, sr = sf.read(path)
            import sounddevice as sd
            sd.play(data, sr)
            sd.wait()
        except ImportError:
            logger.debug("[Voice] soundfile not installed — cannot play")
        except Exception as e:
            logger.debug(f"[Voice] Playback error: {e}")

    def _estimate_duration(self, text: str) -> float:
        """Rough estimate: ~5 chars per second for Chinese."""
        return len(text) / 5.0

    # ══════════════════════════════════════════════
    # Status
    # ══════════════════════════════════════════════

    @property
    def is_speaking(self) -> bool:
        return self._speaking

    def stats(self) -> Dict[str, Any]:
        return {
            "available": self._edge_tts_available,
            "voice": self.voice,
            "utterances": self.total_utterances,
            "speaking": self._speaking,
        }

    def list_voices(self) -> List[str]:
        """List all available voices."""
        return list(VOICES.keys())
