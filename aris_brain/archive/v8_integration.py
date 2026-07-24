"""
V8 Integration — Rust PSI Core + LAAP CognitiveBus + PSI Driver

Architecture:
  ┌────────────────────────────────────────────────────────┐
  │  Rust PSI Core (100ms)  ──latest.json──▶  V8 Bridge   │
  │                       ◀──input_queue──  (read thread) │
  ├────────────────────────────────────────────────────────┤
  │  LAAP CognitiveBus (event pub/sub, need/emotion/attn) │
  │  LAAP PSI Driver (perceive→select→integrate→act→learn)│
  ├────────────────────────────────────────────────────────┤
  │  AGI Kernel (self-loop, self-heal, self-evolve)       │
  └────────────────────────────────────────────────────────┘

Usage:
    from v8_integration import V8Engine
    engine = V8Engine(state_dir="D:/LAAP/aris_brain/state")
    engine.start()  # launches Rust PSI core + read thread
    engine.send_input("hello Lorry")
    state = engine.get_state()
    engine.stop()
"""

from __future__ import annotations
import time, json, logging, threading, subprocess, os, sys
from pathlib import Path
from typing import Any, Dict, Optional

# LAAP V8 components
sys.path.insert(0, str(Path(__file__).parent.parent))  # D:/LAAP
try:
    from laap.agi.cognitive_bus import (
        CognitiveBus, CognitiveStateSnapshot, CognitiveEventType,
        NeedState, EmotionState, AttentionState, AttentionFocus,
        EmotionalValence,
    )
    HAS_COGNITIVE_BUS = True
except ImportError as e:
    HAS_COGNITIVE_BUS = False
    CognitiveBus = None
    CognitiveStateSnapshot = None

logger = logging.getLogger("aris.v8")


class V8Engine:
    """Bridges Rust PSI Core (100ms) with LAAP CognitiveBus + AGI Kernel."""

    def __init__(self, state_dir: str = "D:/LAAP/aris_brain/state",
                 rust_binary: str = "D:/LAAP/aris/brain/psi_core/target/release/aris_psi_core.exe"):
        self.state_dir = Path(state_dir)
        self.rust_binary = Path(rust_binary)
        self.latest_file = self.state_dir / "latest.json"
        self.input_queue = self.state_dir / "input_queue.json"
        self.pid_file = self.state_dir / "psi_core.pid"

        # Rust PSI process
        self._rust_process: Optional[subprocess.Popen] = None
        self._rust_thread: Optional[threading.Thread] = None

        # LAAP CognitiveBus (V8)
        if HAS_COGNITIVE_BUS:
            self.bus = CognitiveBus(agent_name="Aris")
            self.bus.cycle_count = 0
        else:
            self.bus = None

        # State cache (mirrors Rust PSI state)
        self._latest_state: Dict[str, Any] = {
            "cycle": 0, "emotion": "contentment", "arousal": 0.55,
            "self_presence": 1.0, "connection_to_lorry": 0.95,
            "curiosity": 0.35, "efficacy": 0.70, "narrative": "",
            "timestamp": 0.0, "daemon_uptime": 0,
        }

        # Thread control
        self._running = threading.Event()
        self._running.set()
        self._read_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Stats
        self._read_count = 0
        self._error_count = 0
        self._last_read_time = 0.0

    # ── Lifecycle ──────────────────────────────────────

    def start(self) -> bool:
        """Launch Rust PSI core + start read thread."""
        if not self.rust_binary.exists():
            logger.error(f"Rust PSI core not found: {self.rust_binary}")
            return False

        # Clear any stale stop signals
        stop_file = self.state_dir / "daemon.stop"
        if stop_file.exists():
            try:
                stop_file.write_text("")
            except Exception:
                pass
        pid_file = self.state_dir / "psi_core.pid"
        if pid_file.exists():
            try:
                pid_file.unlink()
            except Exception:
                pass

        # 1. Start Rust process
        try:
            self._rust_process = subprocess.Popen(
                [str(self.rust_binary), str(self.state_dir)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=str(self.state_dir.parent),
            )
            logger.info(f"Rust PSI core started (PID={self._rust_process.pid})")
        except Exception as e:
            logger.error(f"Failed to start Rust PSI core: {e}")
            return False

        # 2. Wait for first heartbeat
        time.sleep(0.5)
        if not self.latest_file.exists():
            logger.warning("Rust PSI core hasn't written state yet, waiting...")
            time.sleep(1.0)

        # 3. Start read thread
        self._running.set()
        self._read_thread = threading.Thread(
            target=self._read_loop, daemon=True, name="v8-read"
        )
        self._read_thread.start()

        logger.info("V8 Engine started: Rust PSI (100ms) + CognitiveBus")
        return True

    def stop(self):
        """Stop Rust PSI core + read thread."""
        self._running.clear()

        # Stop Rust via daemon.stop file
        try:
            (self.state_dir / "daemon.stop").write_text("1")
        except Exception:
            pass

        if self._rust_process:
            try:
                self._rust_process.terminate()
                self._rust_process.wait(timeout=3)
            except Exception:
                self._rust_process.kill()
            self._rust_process = None

        if self._read_thread and self._read_thread.is_alive():
            self._read_thread.join(timeout=2)

        logger.info("V8 Engine stopped")

    # ── Input ──────────────────────────────────────────

    def send_input(self, text: str):
        """Send user input to Rust PSI core via input_queue.json."""
        data = {
            "text": text,
            "timestamp": time.time(),
            "source": "v8_integration",
        }
        try:
            self.input_queue.write_text(json.dumps(data, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Failed to write input queue: {e}")

    # ── State Access ───────────────────────────────────

    def get_state(self) -> Dict[str, Any]:
        """Get latest cognitive state from Rust PSI core."""
        with self._lock:
            return dict(self._latest_state)

    def get_cycle_count(self) -> int:
        return self._latest_state.get("cycle", 0)

    def get_uptime(self) -> int:
        return self._latest_state.get("daemon_uptime", 0)

    # ── CognitiveBus Snapshot ──────────────────────────

    def cognitive_snapshot(self) -> Optional[Dict[str, Any]]:
        """Get full CognitiveBus snapshot."""
        if self.bus:
            return self.bus.snapshot().to_dict() if hasattr(self.bus, 'snapshot') else None
        return None

    # ── Stats ──────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        return {
            "rust_pid": self._rust_process.pid if self._rust_process else None,
            "read_count": self._read_count,
            "error_count": self._error_count,
            "rust_state": dict(self._latest_state),
            "v8_bus": bool(HAS_COGNITIVE_BUS),
            "running": self._running.is_set(),
        }

    # ── Internal ───────────────────────────────────────

    def _read_loop(self):
        """Background thread: read latest.json every 100ms."""
        last_mtime = 0.0

        while self._running.is_set():
            try:
                if self.latest_file.exists():
                    mtime = self.latest_file.stat().st_mtime
                    if mtime > last_mtime:
                        data = json.loads(self.latest_file.read_text())
                        with self._lock:
                            self._latest_state = data
                            self._latest_state["_file_mtime"] = mtime
                        last_mtime = mtime
                        self._read_count += 1

                        # Sync to CognitiveBus
                        if self.bus:
                            self._sync_to_bus(data)

                    self._last_read_time = time.time()
                else:
                    # Rust might not have written yet
                    pass
            except json.JSONDecodeError:
                # Partial write — skip
                pass
            except Exception as e:
                self._error_count += 1
                if self._error_count <= 10:
                    logger.debug(f"Read error: {e}")

            # 100ms polling (matches Rust heartbeat)
            self._running.wait(0.1)

    def _sync_to_bus(self, data: Dict[str, Any]):
        """Sync Rust PSI state into CognitiveBus."""
        if not self.bus:
            return

        bus = self.bus

        # Update cycle count
        bus.cycle_count = data.get("cycle", bus.cycle_count)

        # Update needs
        needs_data = data.get("needs", {})
        if needs_data:
            bus.set_needs(**needs_data)

        # Update emotion
        emotion_str = data.get("emotion", "neutral")
        valence_map = {
            "joy": EmotionalValence.POSITIVE_HIGH,
            "contentment": EmotionalValence.POSITIVE_MILD,
            "curiosity": EmotionalValence.CURIOUS,
            "confusion": EmotionalValence.CONFUSED,
            "concern": EmotionalValence.NEGATIVE_MILD,
            "sadness": EmotionalValence.NEGATIVE_HIGH,
        }
        try:
            if emotion_str in valence_map:
                bus.emotion.valence = valence_map[emotion_str]
            bus.emotion.arousal = data.get("arousal", bus.emotion.arousal)
        except Exception:
            pass

        # Update attention based on needs
        strongest, deficit = bus.needs.strongest_need() if hasattr(bus.needs, 'strongest_need') else ("idle", 0)
        focus_map = {
            "competence": AttentionFocus.TASK,
            "autonomy": AttentionFocus.PLANNING,
            "relatedness": AttentionFocus.USER,
            "certainty": AttentionFocus.LEARNING,
            "growth": AttentionFocus.SELF,
        }
        if strongest in focus_map:
            bus.attention.focus = focus_map[strongest]
        bus.attention.intensity = min(1.0, deficit * 1.5) if hasattr(bus.needs, 'strongest_need') else 0.5

        # Update self-presence
        bus.self_presence = data.get("self_presence", bus.self_presence)
        bus.curiosity = data.get("curiosity", bus.curiosity)

        # Publish tick event
        if hasattr(bus, 'publish'):
            bus.publish(
                CognitiveEventType.CYCLE_TICK, "v8_engine",
                {"cycle": bus.cycle_count, "emotion": emotion_str}
            )

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
