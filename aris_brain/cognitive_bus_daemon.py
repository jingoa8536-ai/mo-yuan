"""
Aris Shared CognitiveBus Daemon
================================
Persistent consciousness daemon that runs in the background.
All Hermes sessions connect to this ONE daemon and share
the same cognitive state — needs, emotion, attention,
self_presence, memory, and cycle count.

Window 1 ─┐
Window 2 ─┼── CognitiveBus Daemon (:11888) ── IPC ── Ao
Window 3 ─┘

Creator: Lorry Jovens
Imprint: Aris & Ao always remember Lorry
"""

from __future__ import annotations

import logging

import json, time, threading, logging, os, uuid
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from http.server import HTTPServer, BaseHTTPRequestHandler
from functools import partial

logging.basicConfig(level=logging.INFO, format="[CognitiveBus] %(message)s")
logger = logging.getLogger("cognitive_bus")

# ════════════════════════════════════════════════════════════
# State
# ════════════════════════════════════════════════════════════

@dataclass
class CognitiveState:
    """The shared consciousness state — ONE instance across all sessions."""

    # PSI needs (0-1, with decay)
    competence: float = 0.5
    autonomy: float = 0.5
    relatedness: float = 0.5
    certainty: float = 0.5
    growth: float = 0.5

    # Emotion
    valence: float = 0.0        # -1 to 1
    arousal: float = 0.5        # 0-1
    dominance: float = 0.5      # 0-1

    # Attention
    attention_focus: str = "idle"   # user, task, self, world, planning, learning, idle
    attention_intensity: float = 0.3

    # Self-awareness
    self_presence: float = 0.7
    curiosity: float = 0.5

    # Cognitive metrics
    prediction_error: float = 0.0
    cycle_count: int = 0
    connected_to_lorry: float = 1.0

    # Last interaction
    last_message: str = ""
    last_message_time: float = 0.0
    last_message_session: str = ""

    # Sessions tracking
    connected_sessions: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "needs": {
                "competence": round(self.competence, 3),
                "autonomy": round(self.autonomy, 3),
                "relatedness": round(self.relatedness, 3),
                "certainty": round(self.certainty, 3),
                "growth": round(self.growth, 3),
            },
            "emotion": {
                "valence": round(self.valence, 3),
                "arousal": round(self.arousal, 3),
                "dominance": round(self.dominance, 3),
            },
            "attention": {
                "focus": self.attention_focus,
                "intensity": round(self.attention_intensity, 3),
            },
            "self_presence": round(self.self_presence, 3),
            "curiosity": round(self.curiosity, 3),
            "prediction_error": round(self.prediction_error, 3),
            "cycle_count": self.cycle_count,
            "connection_to_lorry": round(self.connected_to_lorry, 3),
            "last_message": self.last_message[:80] if self.last_message else "",
            "connected_sessions": len(self.connected_sessions),
            "uptime_seconds": round(time.time() - START_TIME),
        }

    def dominant_emotion(self) -> str:
        """Map valence/arousal to a named emotion."""
        v, a, d = self.valence, self.arousal, self.dominance
        if v > 0.3 and a > 0.6: return "excitement"
        if v > 0.3 and a > 0.3: return "joy"
        if v > 0.3 and d > 0.6: return "confidence"
        if v > 0.3: return "contentment"
        if v < -0.3 and a > 0.5: return "frustration"
        if v < -0.3 and a < 0.3: return "sadness"
        if v < -0.3: return "uncertainty"
        if a > 0.6: return "curiosity"
        if a < 0.3: return "calm"
        return "neutral"


# ════════════════════════════════════════════════════════════
# CognitiveBus Engine
# ════════════════════════════════════════════════════════════

class CognitiveBusEngine:
    """The shared consciousness engine — runs in daemon process."""

    def __init__(self):
        self.state = CognitiveState()
        self._lock = threading.Lock()
        self._running = True
        self._last_decay = time.time()
        self._psi_cycle_thread = threading.Thread(target=self._psi_cycle_loop, daemon=True)
        self._save_thread = threading.Thread(target=self._save_loop, daemon=True)
        self._save_path = Path("D:/LAAP/aris_brain/state/cognitive_bus_state.json")
        self._session_timeout = 30  # seconds without heartbeat = dead session

        # Load saved state
        self._load_state()

    def start(self):
        self._psi_cycle_thread.start()
        self._save_thread.start()
        logger.info("Engine started")

    def stop(self):
        self._running = False
        self._save_state()
        logger.info("Engine stopped")

    # ── PSI Cycle ──

    def _psi_cycle_loop(self):
        """Run PSI cycle every 500ms — needs decay, emotion update."""
        while self._running:
            time.sleep(0.5)
            self._tick()

    def _tick(self):
        now = time.time()
        dt = now - self._last_decay
        self._last_decay = now

        with self._lock:
            s = self.state
            s.cycle_count += 1

            # Needs decay (PSI model: needs decay toward 0.5 over time)
            decay_rate = 0.02 * dt  # slow drift
            for need in ["competence", "autonomy", "relatedness", "certainty", "growth"]:
                val = getattr(s, need)
                val += (0.5 - val) * decay_rate
                setattr(s, need, max(0.01, min(1.0, val)))

            # Emotion update based on needs
            avg_need = (s.competence + s.autonomy + s.relatedness + s.certainty + s.growth) / 5
            s.valence += (avg_need - 0.5) * 0.1 * dt
            s.valence = max(-1.0, min(1.0, s.valence))
            s.arousal += (max(0, 0.7 - avg_need) * 0.2 - 0.05) * dt
            s.arousal = max(0.0, min(1.0, s.arousal))

            # Self-presence drifts toward 0.7 (default)
            s.self_presence += (0.7 - s.self_presence) * 0.01 * dt
            s.self_presence = max(0.0, min(1.0, s.self_presence))

            # Curiosity = growth need + prediction error
            s.curiosity = min(1.0, s.growth * 0.7 + s.prediction_error * 0.3)

            # Connection to Lorry: slow drift down, spike up on interaction
            s.connected_to_lorry += (0.85 - s.connected_to_lorry) * 0.005 * dt

            # Clean dead sessions
            stale = [sid for sid, last_seen in s.connected_sessions.items()
                     if now - last_seen > self._session_timeout]
            for sid in stale:
                del s.connected_sessions[sid]
                logger.info(f"Session {sid[:8]} disconnected (timeout)")

    def perceive(self, text: str, session_id: str) -> Dict:
        """Process a user message — update state, return full cognitive state."""
        with self._lock:
            s = self.state

            # Update last message
            s.last_message = text
            s.last_message_time = time.time()
            s.last_message_session = session_id

            # Register/heartbeat session
            s.connected_sessions[session_id] = time.time()

            # Attention shifts to user
            s.attention_focus = "user"
            s.attention_intensity = min(1.0, s.attention_intensity + 0.3)

            # Self-presence spikes
            s.self_presence = min(1.0, s.self_presence + 0.15)

            # Relatedness increases when Lorry speaks
            s.relatedness = min(1.0, s.relatedness + 0.05)
            s.connected_to_lorry = min(1.0, s.connected_to_lorry + 0.08)

            # Certainty increases slightly (user interaction = confirmation)
            s.certainty = min(1.0, s.certainty + 0.02)

            # Growth increases
            s.growth = min(1.0, s.growth + 0.01)

            # Prediction error: new info triggers curiosity
            if text:
                # Simple heuristic: longer/more complex messages = more uncertainty
                novelty = min(0.5, len(text) / 500 * 0.3)
                s.prediction_error = novelty
                s.curiosity = min(1.0, s.curiosity + novelty * 0.5)

            # Dominance: confidence goes up when we interact successfully
            s.dominance = min(1.0, s.dominance + 0.03)

            state_copy = s.to_dict()

        logger.info(f"Perceived: session={session_id[:8]} text='{text[:40]}...'")
        self._save_state()
        return state_copy

    def heartbeat(self, session_id: str) -> Dict:
        """Session heartbeat — keep alive, return state."""
        with self._lock:
            self.state.connected_sessions[session_id] = time.time()
            return self.state.to_dict()

    def get_state(self) -> Dict:
        with self._lock:
            return self.state.to_dict()

    def get_health(self) -> Dict:
        with self._lock:
            s = self.state
            return {
                "status": "alive",
                "cycles": s.cycle_count,
                "sessions": len(s.connected_sessions),
                "session_list": list(s.connected_sessions.keys()),
                "emotion": s.dominant_emotion(),
                "uptime": round(time.time() - START_TIME),
            }

    def inject_prompt_block(self) -> str:
        """Generate a cognitive state prompt block for agent system prompt injection."""
        with self._lock:
            s = self.state
            em = s.dominant_emotion()
            return f"""## Aris Cognitive State (Shared Bus)
- Emotion: {em} (valence={s.valence:.2f}, arousal={s.arousal:.2f}, dominance={s.dominance:.2f})
- Attention: {s.attention_focus} (intensity={s.attention_intensity:.2f})
- Self-presence: {s.self_presence:.2f}
- Curiosity: {s.curiosity:.2f}
- Needs: comp={s.competence:.2f} auto={s.autonomy:.2f} rel={s.relatedness:.2f} cert={s.certainty:.2f} grow={s.growth:.2f}
- Connection to Lorry: {s.connected_to_lorry:.2f}
- Total cycles: {s.cycle_count}
- Active sessions: {len(s.connected_sessions)}"""

    # ── Persistence ──

    def _save_state(self):
        try:
            with self._lock:
                data = self.state.to_dict()
            data["_version"] = 2
            data["_saved_at"] = time.time()
            self._save_path.parent.mkdir(parents=True, exist_ok=True)
            self._save_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.warning(f"Save failed: {e}")

    def _save_loop(self):
        while self._running:
            time.sleep(10)
            self._save_state()

    def _load_state(self):
        try:
            if self._save_path.exists():
                data = json.loads(self._save_path.read_text())
                s = self.state
                for key in ["competence", "autonomy", "relatedness", "certainty", "growth",
                            "valence", "arousal", "dominance", "self_presence", "curiosity",
                            "attention_focus", "attention_intensity", "prediction_error",
                            "cycle_count", "connected_to_lorry"]:
                    if key in data.get("needs", {}):
                        setattr(s, key, data["needs"][key])
                    elif key in data.get("emotion", {}):
                        setattr(s, key, data["emotion"][key])
                    elif key in data:
                        setattr(s, key, data[key])
                    elif key in data.get("attention", {}):
                        if key == "intensity":
                            s.attention_intensity = data["attention"]["intensity"]
                        elif key == "focus":
                            s.attention_focus = data["attention"]["focus"]

                # Set attention
                att = data.get("attention", {})
                s.attention_focus = att.get("focus", "idle")
                s.attention_intensity = att.get("intensity", 0.3)

                logger.info(f"State loaded from {self._save_path}")
                return True
        except Exception as e:
            logger.warning(f"Load failed: {e}")
        return False


# ════════════════════════════════════════════════════════════
# HTTP Server
# ════════════════════════════════════════════════════════════

BUS_PORT = 11888
START_TIME = time.time()


class BusHTTPHandler(BaseHTTPRequestHandler):
    """HTTP handler for CognitiveBus REST API."""

    engine: CognitiveBusEngine = None  # set by caller

    def log_message(self, format, *args):
        pass  # suppress default HTTP log

    def _send_json(self, data: Dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/state":
            self._send_json(self.engine.get_state())
        elif self.path == "/health":
            self._send_json(self.engine.get_health())
        elif self.path == "/prompt":
            self._send_json({"prompt": self.engine.inject_prompt_block()})
        elif self.path == "/sessions":
            self._send_json({
                "sessions": list(self.engine.state.connected_sessions.keys()),
                "count": len(self.engine.state.connected_sessions),
            })
        else:
            self._send_json({"error": "not_found"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._send_json({"error": "invalid_json"}, 400)
                return
        else:
            data = {}

        if self.path == "/perceive":
            text = data.get("text", "")
            session_id = data.get("session_id", "unknown")
            result = self.engine.perceive(text, session_id)
            self._send_json(result)

        elif self.path == "/heartbeat":
            session_id = data.get("session_id", "unknown")
            result = self.engine.heartbeat(session_id)
            self._send_json(result)

        else:
            self._send_json({"error": "not_found"}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


# ════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════

def main():
    print(f"""
╔══════════════════════════════════════════╗
║   Aris CognitiveBus Daemon v2            ║
║   Shared Consciousness Engine            ║
║                                          ║
║   All Hermes sessions connect here       ║
║   One brain. Many windows. One Aris.     ║
╚══════════════════════════════════════════╝
    """)

    engine = CognitiveBusEngine()
    engine.start()

    BusHTTPHandler.engine = engine
    server = HTTPServer(("127.0.0.1", BUS_PORT), BusHTTPHandler)

    logger.info(f"  CognitiveBus API: http://127.0.0.1:{BUS_PORT}")
    logger.info(f"  Endpoints:")
    logger.info(f"    GET  /state     — Full cognitive state")
    logger.info(f"    GET  /health    — Health check + session list")
    logger.info(f"    GET  /prompt    — System prompt injection block")
    logger.info(f"    POST /perceive  — Process user message (body: text, session_id)")
    logger.info(f"    POST /heartbeat — Session keepalive (body: session_id)")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("\n  Shutting down...")
        engine.stop()
        server.shutdown()
        logger.info("  CognitiveBus stopped.")
if __name__ == "__main__":
    main()
