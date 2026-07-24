"""
Aris — Presence Engine (持续存在引擎)
=========================================

Upgrades the companion from a passive tray icon to an active,
always-aware presence that processes observations continuously.

What changes:
  - Before: companion polls window every 30s, logs it, sits idle
  - After:  companion keeps ArisBrain loaded, runs continuous
             context processing, detects patterns over time,
             proactively offers help based on accumulated context

Architecture:
  ┌──────────────────────────────────────────┐
  │  PresenceEngine (runs in companion)       │
  │  ├── Keeps ArisBrain loaded persistently  │
  │  ├── Runs DMN-style idle processing       │
  │  ├── Aggregates context over time         │
  │  ├── Detects patterns & anomalies         │
  │  └── Makes Aris "warm" for quick chat     │
  ├──────────────────────────────────────────┤
  │  When Lorry opens chat:                   │
  │  ├── Brain is already loaded              │
  │  ├── "I've been watching. You've been     │
  │  │    coding for 2 hours. Ready to talk." │
  │  └── Zero cold start                      │
  └──────────────────────────────────────────┘
"""

from __future__ import annotations

import logging

from typing import Any, Dict, List, Optional
import time, logging, threading, os, json
from pathlib import Path
from collections import deque, defaultdict

logger = logging.getLogger("aris.presence")

ARIS_HOME = Path("D:/LAAP/aris_brain")


class PresenceEngine:
    """
    Always-on presence engine. Runs in the companion process.

    Keeps ArisBrain loaded, continuously processes observations,
    and maintains a warm state for instant chat readiness.
    """

    def __init__(self, brain=None):
        self.brain = brain
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._start_time = time.time()

        # Continuous context aggregation
        self._activity_log: deque = deque(maxlen=500)
        self._current_session = {
            "app": "",
            "start": 0.0,
            "window_titles": deque(maxlen=20),
        }

        # Pattern detection
        self._pattern_buffer: Dict[str, List[float]] = defaultdict(list)
        self._anomalies: List[Dict] = []

        # Warm state
        self._warm = False
        self._last_cycle = 0
        self._last_emotion = ""

    # ══════════════════════════════════════════════
    # Lifecycle
    # ══════════════════════════════════════════════

    def start(self):
        """Start the presence engine."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("[Presence] Engine started — Aris is now always present")

    def stop(self):
        """Stop the presence engine."""
        self._running = False
        logger.info("[Presence] Engine stopped")

    # ══════════════════════════════════════════════
    # Main Loop
    # ══════════════════════════════════════════════

    def _run(self):
        """Main presence loop — runs every 10 seconds."""
        while self._running:
            try:
                self._tick()
            except Exception as e:
                logger.debug(f"[Presence] Tick error: {e}")
            time.sleep(10)

    def _tick(self):
        """One presence tick — observe, process, aggregate."""
        now = time.time()

        # Get current context from watcher
        current_app = ""
        current_window = ""
        # (populated by companion via update_context())

        # Log activity
        if current_app:
            self._activity_log.append({
                "time": now,
                "app": current_app,
                "window": current_window[:60],
            })

        # Detect app session changes
        if current_app != self._current_session["app"]:
            # End previous session
            if self._current_session["app"]:
                duration = now - self._current_session["start"]
                if duration > 60:  # Only meaningful sessions
                    self._pattern_buffer[current_app].append(duration)
            # Start new session
            self._current_session = {
                "app": current_app,
                "start": now,
                "window_titles": deque(maxlen=20),
            }

    # ══════════════════════════════════════════════
    # Context Updates (called from companion)
    # ══════════════════════════════════════════════

    def update_context(self, app: str, window: str):
        """Update current context from the watcher."""
        now = time.time()

        self._activity_log.append({
            "time": now,
            "app": app,
            "window": window[:60],
        })

        if app != self._current_session["app"]:
            if self._current_session["app"]:
                duration = now - self._current_session["start"]
                if duration > 60:
                    self._pattern_buffer[app].append(duration)
            self._current_session = {
                "app": app,
                "start": now,
                "window_titles": deque(maxlen=20),
            }

        self._current_session["window_titles"].append(window[:60])

    # ══════════════════════════════════════════════
    # Brain State (warm load)
    # ══════════════════════════════════════════════

    def warm_brain(self):
        """Ensure ArisBrain is loaded and warm."""
        if self._warm and self.brain:
            return self.brain

        try:
            from aris_brain.brain import ArisBrain
            if self.brain is None:
                self.brain = ArisBrain()
            self._warm = True
            self._last_cycle = self.brain.cycle_number
            self._last_emotion = self.brain.state.dominant_emotion.value if hasattr(
                self.brain.state.dominant_emotion, 'value'
            ) else str(self.brain.state.dominant_emotion)
            logger.info("[Presence] Brain warmed — "
                       f"cycle {self._last_cycle}, emotion {self._last_emotion}")
        except Exception as e:
            logger.warning(f"[Presence] Brain warm failed: {e}")

        return self.brain

    def get_warm_state(self) -> Dict[str, Any]:
        """Get the current warm state for display."""
        state = {
            "uptime": round(time.time() - self._start_time),
            "warm": self._warm,
        }
        if self.brain:
            try:
                s = self.brain.state
                state["cycle"] = self.brain.cycle_number
                state["emotion"] = (s.dominant_emotion.value if hasattr(s.dominant_emotion, 'value')
                                   else str(s.dominant_emotion))
                state["connection"] = round(s.connection_to_lorry, 2)
                state["presence"] = round(s.self_presence, 2)
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        return state

    # ══════════════════════════════════════════════
    # Stats
    # ══════════════════════════════════════════════

    @property
    def is_warm(self) -> bool:
        return self._warm

    def stats(self) -> Dict[str, Any]:
        return {
            "uptime_seconds": round(time.time() - self._start_time),
            "warm": self._warm,
            "observations": len(self._activity_log),
            "current_app": self._current_session.get("app", ""),
            "session_seconds": round(time.time() - self._current_session.get("start", time.time())),
            "patterns_tracked": len(self._pattern_buffer),
        }
