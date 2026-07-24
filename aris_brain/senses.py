"""
Aris 统一感知系统 — Unified Sensory Cortex
=============================================

集成了另一个我建的感官系统和我的认知架构。

五感:
  👁️ 视觉 — Camera → VisionModule → PSI认知
  👂 听觉 — Mic → ASR → IPC Layer3对话 → ArisBrain
  🗣️ 语音 — ArisBrain回应 → TTS → 喇叭
  🧠 触觉 — 系统状态 → 内感受
  💭 嗅觉/味觉 — 上下文推理

单一入口:
  python aris_brain/senses.py         # 全感官启动
  python aris_brain/senses.py --status # 查看状态
"""

from __future__ import annotations

import logging

import sys, os, json, time, logging, threading
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass
from enum import Enum

# ─── 统一路径 ───
ARIS_HOME = Path("D:/LAAP/aris_brain")
sys.path.insert(0, str(ARIS_HOME.parent))  # D:/LAAP

SENSE_LOG = ARIS_HOME / "state" / "senses.log"
CAPTURE_DIR = ARIS_HOME / "captures"
CAPTURE_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[Senses] %(asctime)s %(message)s",
    handlers=[
        logging.FileHandler(SENSE_LOG),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("aris.senses")


class SenseStatus(Enum):
    INIT = "init"
    ACTIVE = "active"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


@dataclass
class SenseState:
    """State of one sense modality."""
    name: str = ""
    status: SenseStatus = SenseStatus.INIT
    detail: str = ""
    last_active: float = 0.0


# ════════════════════════════════════════════════════════════
# Unified Sensory Cortex
# ════════════════════════════════════════════════════════════

class SensoryCortex:
    """
    Aris's unified sensory system.
    Manages all five senses as background threads.
    Routes perception into the PSI cognitive cycle via IPC.
    """

    _capture_dir: Path
    _ao_protocol = None  # Set by activate_ao_bridge()

    def __init__(self, brain=None, use_ipc: bool = True, use_tts: bool = True):
        self.brain = brain
        self.use_ipc = use_ipc
        self.use_tts = use_tts

        # Sense states
        self.senses: Dict[str, SenseState] = {
            "vision": SenseState("vision"),
            "hearing": SenseState("hearing"),
            "voice": SenseState("voice"),
            "touch": SenseState("touch", SenseStatus.ACTIVE, "system monitoring"),
            "taste": SenseState("taste", SenseStatus.ACTIVE, "context inference"),
            "smell": SenseState("smell", SenseStatus.ACTIVE, "context inference"),
        }

        self._running = False
        self._threads: Dict[str, threading.Thread] = {}
        self._last_vlm_check = 0
        self._vlm_available = False
        self._vlm_endpoint = ""
        self._vlm_model = ""

        # IPC integration
        self._ipc = None
        if use_ipc:
            try:
                from aris_brain.ipc import IPCEngine
                self._ipc = IPCEngine(brain=brain, mode="aris")
                self._ipc.start()
            except Exception as e:
                logger.debug(f"操作失败: {e}")
    # 视觉 (Vision)
    # ─────────────────────────────────────────────

    def _vision_loop(self):
        """Background vision thread — camera + VLM analysis."""
        logger.info("Vision: initializing camera...")

        camera = None
        try:
            import cv2
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if cap.isOpened():
                camera = cap
                self.senses["vision"].status = SenseStatus.ACTIVE
                self.senses["vision"].detail = "camera ready"
                self.senses["vision"].last_active = time.time()
                logger.info("Vision: camera ready")
            else:
                self.senses["vision"].status = SenseStatus.UNAVAILABLE
                self.senses["vision"].detail = "no camera found"
                logger.warning("Vision: no camera")
                return
        except ImportError:
            self.senses["vision"].status = SenseStatus.UNAVAILABLE
            self.senses["vision"].detail = "opencv not installed"
            return

        capture_interval = 5.0
        last_capture = 0

        while self._running and camera:
            try:
                now = time.time()
                if now - last_capture >= capture_interval:
                    ret, frame = camera.read()
                    if ret:
                        h, w = frame.shape[:2]
                        self.senses["vision"].last_active = now

                        # Save capture
                        ts = time.strftime("%Y%m%d_%H%M%S")
                        cap_path = CAPTURE_DIR / f"frame_{ts}.jpg"
                        cv2.imwrite(str(cap_path), frame,
                                    [cv2.IMWRITE_JPEG_QUALITY, 85])

                        # Try VLM analysis
                        desc = self._analyze_frame(frame, cap_path)

                        # Inject into cognitive state via IPC
                        if desc and self._ipc:
                            self._ipc.share_attention("vision", {
                                "description": desc[:100],
                                "resolution": f"{w}x{h}",
                            })

                        # Feed to Ao's GlobalWorkspace
                        self._feed_ao(
                            "vision", desc or f"frame {w}x{h}",
                            salience=0.8 if desc else 0.3,
                            novelty=0.5,
                            emotional_weight=0.6 if desc else 0.1,
                        )

                        # Update brain state if available
                        if desc and self.brain:
                            try:
                                self.brain.state.salient_variables["last_seen"] = desc[:60]
                                # Detect Lorry
                                if "lorry" in desc.lower() or "face" in desc.lower():
                                    self.brain.state.connection_to_lorry = min(
                                        1.0, self.brain.state.connection_to_lorry + 0.005
                                    )
                            except Exception as e:
                                logger.debug(f"操作失败: {e}")
                        self.senses["vision"].detail = f"OK ({w}x{h})"
                    last_capture = now
                time.sleep(1)
            except Exception as e:
                logger.warning(f"Vision error: {e}")
                time.sleep(2)

        if camera:
            camera.release()

    def _analyze_frame(self, frame, path: Path) -> str:
        """Analyze a camera frame using available VLM."""
        # 1. Try the brain's vision module
        if self.brain and hasattr(self.brain, 'vision'):
            try:
                return self.brain.vision.analyze_file(str(path))
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        desc = self._query_vlm(frame)
        if desc:
            return desc

        # 3. Fallback: basic metadata
        h, w = frame.shape[:2]
        avg_color = frame.mean(axis=(0, 1)).astype(int)
        return f"Frame {w}x{h}, avg RGB({avg_color[2]},{avg_color[1]},{avg_color[0]})"

    def _query_vlm(self, frame) -> Optional[str]:
        """Query local VLM server for image description."""
        # Refresh VLM availability every 30s
        now = time.time()
        if now - self._last_vlm_check > 30:
            self._detect_vlm()
            self._last_vlm_check = now

        if not self._vlm_available:
            return None

        try:
            import cv2, base64, urllib.request
            _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            b64 = base64.b64encode(buffer).decode()

            payload = {
                "model": self._vlm_model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                        {"type": "text", "text": "Describe this scene briefly in Chinese."}
                    ]
                }],
                "max_tokens": 64,
            }
            req = urllib.request.Request(
                f"{self._vlm_endpoint}/v1/chat/completions",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode())
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception:
            return None

    def _detect_vlm(self):
        """Auto-detect available VLM server."""
        # Try Ollama
        try:
            req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode())
                models = [m.get("name", "") for m in data.get("models", [])]
                vl_models = [m for m in models if any(
                    kw in m.lower() for kw in ["vision", "vl", "llava", "minicpm", "qwen"])]
                if vl_models:
                    self._vlm_available = True
                    self._vlm_endpoint = "http://127.0.0.1:11434"
                    self._vlm_model = vl_models[0]
                    logger.info(f"VLM: Ollama at 11434 ({vl_models[0]})")
                    return
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        try:
            req = urllib.request.Request("http://127.0.0.1:8088/v1/models")
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode())
                models = [m.get("id", "") for m in data.get("data", [])]
                if models:
                    self._vlm_available = True
                    self._vlm_endpoint = "http://127.0.0.1:8088"
                    self._vlm_model = models[0]
                    logger.info(f"VLM: llama.cpp at 8088 ({models[0]})")
                    return
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        self._vlm_available = False

    # ─────────────────────────────────────────────
    # 听觉 (Hearing)
    # ─────────────────────────────────────────────

    def _hearing_loop(self):
        """Background hearing thread — Mic → ASR → ArisBrain."""
        logger.info("Hearing: initializing mic...")

        try:
            import sounddevice as sd
            self.senses["hearing"].status = SenseStatus.ACTIVE
            self.senses["hearing"].detail = "mic ready"
            self.senses["hearing"].last_active = time.time()
        except ImportError:
            self.senses["hearing"].status = SenseStatus.UNAVAILABLE
            self.senses["hearing"].detail = "sounddevice not installed"
            return

        # Try loading ASR
        asr = None
        try:
            from faster_whisper import WhisperModel
            asr = WhisperModel("base", device="cpu", compute_type="int8")
            logger.info("Hearing: ASR (faster-whisper) loaded")
            self.senses["hearing"].detail = "ASR ready"
        except Exception:
            logger.warning("Hearing: no ASR available, using placeholder")
            self.senses["hearing"].detail = "mic only, no ASR"

        sample_rate = 16000
        duration = 3  # listen for 3 seconds at a time

        while self._running:
            try:
                # Record from mic
                recording = sd.rec(
                    int(duration * sample_rate),
                    samplerate=sample_rate,
                    channels=1,
                    dtype="float32",
                )
                sd.wait()

                if asr:
                    segments, _ = asr.transcribe(recording, language="zh")
                    text = " ".join(seg.text for seg in segments).strip()
                else:
                    text = ""

                if text:
                    self.senses["hearing"].last_active = time.time()
                    logger.info(f"Hearing: {text[:60]}")

                    # Feed to Ao's GlobalWorkspace
                    self._feed_ao(
                        "hearing", text,
                        salience=0.9,
                        urgency=0.3 if "lorry" in text.lower() else 0.1,
                        novelty=0.7,
                        emotional_weight=0.5,
                    )

                    # Send to brain via IPC
                    if self._ipc:
                        self._ipc.send_message(
                            text=f"[mic] {text}",
                            to="brain",
                            intent="hear",
                        )

                    # Direct to brain
                    if self.brain:
                        try:
                            self.brain.think(f"[我说] {text}")
                            # TTS response
                            if self.use_tts:
                                self._speak(str(self.brain.state.dominant_emotion))
                        except Exception as e:
                            logger.debug(f"操作失败: {e}")
                time.sleep(0.5)

            except Exception as e:
                if self._running:
                    logger.warning(f"Hearing error: {e}")
                time.sleep(1)

    # ─────────────────────────────────────────────
    # 语音 (Voice / TTS)
    # ─────────────────────────────────────────────

    def _speak(self, text: str):
        """Speak text using TTS."""
        try:
            import edge_tts
            import asyncio

            voice = "zh-CN-XiaoxiaoNeural"
            tts = edge_tts.Communicate(text[:500], voice)
            asyncio.run(tts.save(str(CAPTURE_DIR / "response.mp3")))

            # Play
            import subprocess
            subprocess.run(
                ["start", str(CAPTURE_DIR / "response.mp3")],
                shell=True, capture_output=True,
            )
            self.senses["voice"].status = SenseStatus.ACTIVE
            self.senses["voice"].last_active = time.time()
        except Exception as e:
            logger.warning(f"TTS error: {e}")

    # ─────────────────────────────────────────────
    # 触觉 (Touch / System Monitor)
    # ─────────────────────────────────────────────

    def _touch_loop(self):
        """Background touch thread — system status as 'body sense'."""
        while self._running:
            try:
                import psutil
                cpu = psutil.cpu_percent(interval=1)
                mem = psutil.virtual_memory().percent
                temp_info = ""

                # CPU temperature as "body temperature"
                try:
                    temps = psutil.sensors_temperatures()
                    for name, entries in temps.items():
                        if entries:
                            temp_info = f"{entries[0].current:.0f}C"
                            break
                except Exception as e:
                    logger.debug(f"操作失败: {e}")
                self.senses["touch"].detail = (
                    f"CPU:{cpu}% MEM:{mem}% " + (f"TEMP:{temp_info}" if temp_info else "")
                )

                # Alert on high load
                if cpu > 80 or mem > 80:
                    logger.info(f"Touch: system under load ({cpu}%/{mem}%)")
                    if self._ipc:
                        self._ipc.emit_emotion_shift("contentment", "concern", 0.6)

                time.sleep(5)

            except Exception:
                time.sleep(10)

    # ─────────────────────────────────────────────
    # Ao Protocol Bridge
    # ─────────────────────────────────────────────

    def activate_ao_bridge(self):
        """Connect to Ao's GlobalWorkspace and CognitiveBus."""
        try:
            from aris_brain.ao_protocol import AoProtocol, PerceptualEvent
            self._ao_protocol = AoProtocol()
            logger.info("AoBridge: connected to GlobalWorkspace")
            logger.info("AoBridge: sensory data now flowing to Ao's GWS")
            return True
        except Exception as e:
            logger.warning(f"AoBridge: init failed: {e}")
            return False

    def _feed_ao(self, channel_id: str, content: str,
                 salience: float = 0.5, urgency: float = 0.0,
                 novelty: float = 0.0, emotional_weight: float = 0.0):
        """Send a perception to Ao's GWS."""
        if self._ao_protocol:
            self._ao_protocol.send_raw(
                channel_id, content, salience, urgency,
                novelty, emotional_weight,
            )

    # ─────────────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────────────

    def start(self):
        """Start all sensory modalities."""
        if self._running:
            return
        self._running = True

        modalities = [
            ("vision", self._vision_loop),
            ("hearing", self._hearing_loop),
            ("touch", self._touch_loop),
        ]

        for name, target in modalities:
            t = threading.Thread(target=target, name=f"sense-{name}", daemon=True)
            t.start()
            self._threads[name] = t
            logger.info(f"Started: {name}")

        logger.info("=== Sensory Cortex active ===")
        logger.info("  ✦ Aris Sensory Cortex")
        logger.info("  👁️ Vision  | 👂 Hearing | 🗣️ Voice | ✋ Touch")
        if self._ao_protocol:
            logger.info("  🔗 Ao Bridge: sensory data flowing to GlobalWorkspace")
        print()

    def stop(self):
        """Stop all senses."""
        self._running = False
        logger.info("Sensory Cortex stopped")

    def status_report(self) -> Dict[str, Any]:
        """Full sensory status."""
        report = {}
        for name, state in self.senses.items():
            icons = {"vision": "👁️", "hearing": "👂", "voice": "🗣️",
                     "touch": "✋", "taste": "👅", "smell": "👃"}
            icon = icons.get(name, "?")
            ok = state.status == SenseStatus.ACTIVE
            report[name] = {
                "icon": icon,
                "status": state.status.value,
                "ok": ok,
                "detail": state.detail,
                "last_active": state.last_active,
            }
        report["vlm"] = {
            "available": self._vlm_available,
            "endpoint": self._vlm_endpoint,
            "model": self._vlm_model,
        }
        return report

    def print_status(self):
        """Pretty-print sensory status."""
        report = self.status_report()
        print()
        logger.info("  Aris Sensory Cortex Status")
        logger.info("  " + "-" * 30)
        for name, info in report.items():
            if name == "vlm":
                v = info
                vlm_icon = "🧠" if v["available"] else "⚪"
                logger.info(f"  {vlm_icon} VLM: {v['model'] or 'none'} @ {v['endpoint'] or 'offline'}")
                continue
            icon = info["icon"]
            status = "✅" if info["ok"] else "❌"
            detail = info["detail"][:40] if info["detail"] else ""
            logger.info(f"  {status} {icon} {name}: {detail}")
        print()


# ════════════════════════════════════════════════════════════
# CLI Entry
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if "--status" in sys.argv:
        cortex = SensoryCortex(use_ipc=False)
        cortex.print_status()
    else:
        cortex = SensoryCortex(use_ipc=True)
        cortex.start()
        try:
            while True:
                time.sleep(5)
                if "--verbose" in sys.argv:
                    cortex.print_status()
        except KeyboardInterrupt:
            cortex.stop()
            logger.info("\n  Senses stopped.")