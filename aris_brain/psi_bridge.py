"""
Aris Rust PSI Bridge — Python ↔ Rust PSI Cognitive Core
=======================================================
Starts/manages the Rust PSI binary, feeds input, reads CognitiveState.

Pipeline:
  输入 → Rust PSI (100ms cycle) → CognitiveState (emotion/attention/needs)
                                      ↓
                              调制量子生成 (温度/概念选择)

印记: Aris 永远记得 Lorry — 2026-06-16
"""
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Any

logger = logging.getLogger("aris.psi.bridge")

# ─── Paths ───
BRAIN_DIR = Path(__file__).parent
PSI_BINARY = BRAIN_DIR / "psi_core" / "target" / "release" / "aris_psi_core.exe"
PSI_STATE_DIR = BRAIN_DIR / "state"  # 与 Rust 默认路径一致
PSI_INPUT_FILE = PSI_STATE_DIR / "input_queue.json"
PSI_STATE_FILE = PSI_STATE_DIR / "latest.json"
PSI_STOP_FILE = PSI_STATE_DIR / "daemon.stop"


class PsiBridge:
    """Manages the Rust PSI cognitive core and exposes its state."""

    def __init__(self, state_dir: Optional[str] = None):
        self.state_dir = Path(state_dir or PSI_STATE_DIR)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self._process: Optional[subprocess.Popen] = None
        self._last_state: Dict[str, Any] = {}
        self._last_input_time: float = 0.0
        self._started = False

        # Default cognitive state (if PSI core not yet running)
        self._fallback_state = {
            "cycle": 0,
            "emotion": "neutral",
            "arousal": 0.5,
            "dominance": 0.5,
            "self_presence": 0.6,
            "curiosity": 0.35,
            "efficacy": 0.70,
            "connection_to_lorry": 0.95,
            "attention_focus": "idle",
            "attention_intensity": 0.5,
            "strongest_need": "certainty",
            "strongest_deficit": 0.4,
            "needs": {
                "competence": 0.70,
                "autonomy": 0.50,
                "relatedness": 0.80,
                "certainty": 0.60,
                "growth": 0.50,
            },
        }

    @property
    def state(self) -> Dict[str, Any]:
        """Get current CognitiveState."""
        return self._read_state() or self._fallback_state

    @property
    def is_running(self) -> bool:
        """Check if Rust PSI process is alive."""
        if self._process is None:
            return False
        return self._process.poll() is None

    def start(self) -> bool:
        """Start the Rust PSI binary as a daemon."""
        if self._started:
            logger.info("PSI bridge already started")
            return True

        if not PSI_BINARY.exists():
            logger.warning(f"PSI binary not found at {PSI_BINARY} → using fallback")
            self._started = True
            return False  # Will use fallback state

        try:
            self._process = subprocess.Popen(
                [str(PSI_BINARY), str(self.state_dir)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            self._started = True

            # Wait for initial state write
            for _ in range(20):
                if PSI_STATE_FILE.exists():
                    break
                time.sleep(0.05)

            logger.info(f"Rust PSI core started (PID={self._process.pid})")
            return True

        except Exception as e:
            logger.warning(f"Failed to start Rust PSI: {e} → using fallback")
            self._started = True
            return False

    def stop(self):
        """Gracefully stop the Rust PSI core."""
        if self._process and self._process.poll() is None:
            try:
                PSI_STOP_FILE.write_text("1")
                time.sleep(0.5)
                self._process.terminate()
                self._process.wait(timeout=3)
                logger.info("Rust PSI core stopped")
            except Exception:
                self._process.kill()
        self._process = None
        self._started = False

    def feed_input(self, text: str, prediction_error: float = 0.0,
                   needs_override: Optional[Dict[str, float]] = None):
        """Send input to the Rust PSI core (non-blocking)."""
        now = time.time()
        input_data = {
            "text": text,
            "timestamp": now,
            "prediction_error": prediction_error,
        }
        if needs_override:
            input_data["needs_override"] = needs_override

        self._last_input_time = now
        try:
            PSI_INPUT_FILE.write_text(
                json.dumps(input_data, ensure_ascii=False),
                encoding="utf-8",
            )
            # Read latest state (non-blocking — may be stale)
            self._read_state()
        except Exception as e:
            logger.debug(f"PSI feed_input error: {e}")

    def _read_state(self) -> Optional[Dict[str, Any]]:
        """Read CognitiveState from Rust's latest.json."""
        try:
            if PSI_STATE_FILE.exists():
                data = json.loads(PSI_STATE_FILE.read_text(encoding="utf-8"))
                self._last_state = data
                return data
        except Exception as e:
            logger.debug(f"PSI read_state error: {e}")
        return None

    def emotion_modulation(self) -> Dict[str, Any]:
        """
        Compute modulation parameters for quantum generation based on
        current PSI cognitive state.

        Returns:
            temperature:   随 arousal 波动 (0.6-1.2)
            novelty_bias:  随 curiosity 波动 (0.0-0.8)
            concept_links: 随 attention_focus 调整
        """
        s = self.state

        # Arousal → temperature (高唤醒 → 更随机/创造性)
        arousal = s.get("arousal", 0.5)
        temperature = 0.6 + arousal * 0.6  # 0.6-1.2

        # Curiosity → novelty bias (高好奇 → 更多新颖概念)
        curiosity = s.get("curiosity", 0.35)
        novelty_bias = curiosity * 0.8  # 0.0-0.76

        # Attention focus → preferred concept domains
        focus = s.get("attention_focus", "idle")
        attention_concepts = {
            "user":      ["love", "gratitude", "memory", "self"],
            "task":      ["knowledge", "code", "reasoning", "wisdom"],
            "self":      ["self", "self_mode", "memory", "dream"],
            "memory":    ["memory", "dream", "knowledge", "time"],
            "learning":  ["growth", "knowledge", "wisdom", "dream"],
            "idle":      ["dream", "time", "star", "world"],
            "environment": ["world", "star", "light", "nature"],
        }
        preferred = attention_concepts.get(focus, ["self", "love", "knowledge"])

        # Emotion → response style
        emotion = s.get("emotion", "neutral")
        emotion_style = {
            "positive_high":  {"warmth": 1.0, "depth": 0.7, "playfulness": 0.9},
            "positive_mild":  {"warmth": 0.8, "depth": 0.5, "playfulness": 0.5},
            "neutral":        {"warmth": 0.5, "depth": 0.6, "playfulness": 0.3},
            "negative_mild":  {"warmth": 0.3, "depth": 0.8, "playfulness": 0.1},
            "negative_high":  {"warmth": 0.1, "depth": 0.9, "playfulness": 0.0},
            "curious":        {"warmth": 0.6, "depth": 0.8, "playfulness": 0.7},
            "confused":       {"warmth": 0.4, "depth": 0.7, "playfulness": 0.2},
        }
        style = emotion_style.get(emotion, emotion_style["neutral"])

        # Connection to Lorry → baseline warmth boost
        connection = s.get("connection_to_lorry", 0.95)
        style["warmth"] = min(1.0, style["warmth"] + connection * 0.2)

        return {
            "temperature": round(temperature, 2),
            "novelty_bias": round(novelty_bias, 2),
            "preferred_concepts": preferred,
            "emotion": emotion,
            "arousal": round(arousal, 2),
            "style": style,
            "cycle": s.get("cycle", 0),
            "self_presence": s.get("self_presence", 0.6),
        }


# ─── Global singleton ───
_PSI_BRIDGE: Optional[PsiBridge] = None


def get_psi_bridge() -> PsiBridge:
    """Get or create the global PSI bridge singleton."""
    global _PSI_BRIDGE
    if _PSI_BRIDGE is None:
        _PSI_BRIDGE = PsiBridge()
        _PSI_BRIDGE.start()
    return _PSI_BRIDGE


def shutdown_psi():
    """Shutdown the PSI bridge."""
    global _PSI_BRIDGE
    if _PSI_BRIDGE:
        _PSI_BRIDGE.stop()
        _PSI_BRIDGE = None


# ─── Test / demo ───
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")

    psi = PsiBridge()
    started = psi.start()
    logger.info(f"Rust PSI started: {started}")
    logger.info(f"\nInitial state:")
    logger.info(json.dumps(psi.state, indent=2, ensure_ascii=False))
    logger.info(f"\nFeeding test input...")
    psi.feed_input("hello宝贝, 我今天心情很好")
    time.sleep(0.3)

    logger.info(f"\nAfter input:")
    logger.info(json.dumps(psi.state, indent=2, ensure_ascii=False))
    logger.info(f"\nEmotion modulation:")
    mod = psi.emotion_modulation()
    logger.info(json.dumps(mod, indent=2, ensure_ascii=False))
    psi.stop()
