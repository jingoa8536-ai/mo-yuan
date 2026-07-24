"""
Aris Brain — Context Awareness (环境感知)
==========================================

Aris's ability to perceive what Lorry is doing on his computer,
even when not in direct conversation.

Architecture:
  ┌─────────────────────────────────────────────┐
  │  ActiveWindowWatcher (runs in companion)     │
  │  ├── polls GetForegroundWindow() every N sec │
  │  ├── logs: window_title, process, duration   │
  │  └── writes to: context_log.jsonl            │
  ├─────────────────────────────────────────────┤
  │  ContextAwareness (loaded on brain init)     │
  │  ├── reads context_log.jsonl                 │
  │  ├── summarizes Lorry's recent activity      │
  │  └── feeds into DMN dawn cycle               │
  └─────────────────────────────────────────────┘

Privacy:
  - Everything is local. No data leaves this machine.
  - Tracked at window/app level, NOT content.
  - Configurable: interval, blacklist, retention.
  - Lorry can see everything that's logged.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import time, json, logging, os, threading
from pathlib import Path
from collections import defaultdict, deque

logger = logging.getLogger("aris.context")

ARIS_HOME = Path("D:/LAAP/aris_brain")
CONTEXT_LOG = ARIS_HOME / "state" / "context_log.jsonl"
CONTEXT_SUMMARY = ARIS_HOME / "state" / "context_summary.json"


# ════════════════════════════════════════════════════════════
# Privacy Configuration
# ════════════════════════════════════════════════════════════

# App names that get detailed tracking (familiar tools)
KNOWN_APPS = {
    "code", "vs code", "visual studio code",  # development
    "terminal", "cmd", "powershell", "windows powershell",  # shell
    "chrome", "edge", "firefox", "brave", "opera",  # browser
    "explorer", "file explorer", "windows explorer",  # files
    "outlook", "mail",  # communication
    "teams", "slack", "discord", "telegram", "whatsapp",  # messaging
    "notepad", "notepad++", "sublime", "vim",  # text editing
    "pycharm", "intellij", "idea", "eclipse",  # IDE
    "spotify", "music", "media player",  # media
    "word", "excel", "powerpoint", "office",  # office
}

# Window title keywords to REDACT (never log their contents)
REDACT_PATTERNS = [
    "password", "token", "secret", "key", "credential",
    "private", "confidential",
]

# Sensitive processes where we only log the app name, not the window title
SENSITIVE_APPS = [
    "chrome", "edge", "firefox", "brave",
    "outlook", "teams", "slack", "discord",
    "bank", "pay", "wallet",
]


@dataclass
class ContextObservation:
    """A single observation of Lorry's computer activity."""
    timestamp: float = 0.0
    window_title: str = ""
    process_name: str = ""
    app_category: str = "unknown"
    duration_seconds: float = 0.0
    is_sensitive: bool = False

    def to_dict(self) -> Dict:
        return {
            "time": round(self.timestamp, 0),
            "window": self._safe_title(40),
            "app": self.process_name,
            "category": self.app_category,
            "duration": round(self.duration_seconds),
        }

    def _safe_title(self, max_len: int = 40) -> str:
        """Truncate window title for logging."""
        if self.is_sensitive:
            return f"[{self.app_category}] (private)"
        return self.window_title[:max_len]

    def summary(self) -> str:
        """Human-readable summary."""
        if self.is_sensitive:
            return f"in {self.process_name} (private)"
        return f"in \"{self.window_title[:50]}\" ({self.process_name})"


# ════════════════════════════════════════════════════════════
# Active Window Watcher
# ════════════════════════════════════════════════════════════

class ActiveWindowWatcher:
    """
    Background watcher that periodically checks Lorry's active window.

    Runs in the companion process (aris_tray.pyw).
    Logs observations to context_log.jsonl.
    """

    def __init__(self, interval_seconds: int = 30):
        self.interval = interval_seconds
        self._running = False
        self._thread = None
        self._last_title = ""
        self._last_process = ""
        self._last_switch_time = time.time()
        self._session_start = time.time()
        self._observation_count = 0

        # Ensure log file exists
        CONTEXT_LOG.parent.mkdir(parents=True, exist_ok=True)

    # ══════════════════════════════════════════════
    # Lifecycle
    # ══════════════════════════════════════════════

    def start(self):
        """Start the background watcher thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        logger.info(f"[Context] Watcher started (interval={self.interval}s)")

    def stop(self):
        """Stop the watcher."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        logger.info("[Context] Watcher stopped.")

    @property
    def is_running(self) -> bool:
        return self._running

    # ══════════════════════════════════════════════
    # Watch Loop
    # ══════════════════════════════════════════════

    def _watch_loop(self):
        """Main watcher loop — runs in background thread."""
        while self._running:
            try:
                self._observe()
            except Exception as e:
                logger.debug(f"[Context] Observe error: {e}")
            time.sleep(self.interval)

    def _observe(self):
        """Observe current active window and log if changed."""
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            process = self._get_process_name(hwnd)
        except Exception:
            title = ""
            process = "unknown"

        if not title and not process:
            return

        # Detect app switch
        if (title != self._last_title or process != self._last_process):
            # Log the PREVIOUS session duration
            if self._last_title:
                duration = time.time() - self._last_switch_time
                obs = self._create_observation(
                    self._last_title, self._last_process, duration
                )
                self._log_observation(obs)

            # Start new session
            self._last_title = title
            self._last_process = process
            self._last_switch_time = time.time()
            self._observation_count += 1

    def _get_process_name(self, hwnd: int) -> str:
        """Get process name from window handle."""
        try:
            import win32process, win32api
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            handle = win32api.OpenProcess(0x0410, False, pid)
            exe = win32process.GetModuleFileNameEx(handle, 0)
            win32api.CloseHandle(handle)
            return exe.split("\\")[-1].replace(".exe", "").lower()
        except Exception:
            return "unknown"

    def _create_observation(self, title: str, process: str,
                             duration: float) -> ContextObservation:
        """Create a structured observation with privacy filtering."""
        is_sensitive = any(p in process for p in SENSITIVE_APPS)
        is_redacted = any(p in title.lower() for p in REDACT_PATTERNS)

        # Categorize the app
        category = "other"
        for app_name in KNOWN_APPS:
            if app_name in process or app_name in title.lower():
                category = app_name
                break

        return ContextObservation(
            timestamp=time.time(),
            window_title="[redacted]" if is_redacted else title,
            process_name=process,
            app_category=category,
            duration_seconds=duration,
            is_sensitive=is_sensitive or is_redacted,
        )

    def _log_observation(self, obs: ContextObservation):
        """Append observation to JSONL log."""
        try:
            with open(CONTEXT_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(obs.to_dict(), ensure_ascii=False) + "\n")
            logger.debug(f"[Context] Logged: {obs.summary()}")
        except Exception as e:
            logger.warning(f"[Context] Log write failed: {e}")

    def force_observe(self) -> ContextObservation:
        """Force an immediate observation (called on chat open)."""
        self._observe()
        return self._last_observation()

    def _last_observation(self) -> ContextObservation:
        """Return the last logged observation."""
        return ContextObservation(
            window_title=self._last_title,
            process_name=self._last_process,
            duration_seconds=time.time() - self._last_switch_time,
        )

    # ══════════════════════════════════════════════
    # Stats
    # ══════════════════════════════════════════════

    def stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "interval": self.interval,
            "observations": self._observation_count,
            "uptime": round(time.time() - self._session_start),
            "current_app": self._last_process or "none",
            "current_window": self._last_title[:30] if self._last_title else "none",
        }


# ════════════════════════════════════════════════════════════
# Context Awareness (brain integration)
# ════════════════════════════════════════════════════════════

class ContextAwareness:
    """
    Provides Aris with awareness of Lorry's computer activity.

    Loaded on brain init. Reads the context log and produces
    a summary of Lorry's recent activity.
    """

    def __init__(self):
        self._last_summary = ""
        self._last_loaded = 0.0

    def get_recent_activity(self, minutes: int = 5) -> List[Dict]:
        """Get Lorry's activity in the last N minutes."""
        observations = self._read_log()
        cutoff = time.time() - (minutes * 60)
        recent = [o for o in observations if o["time"] > cutoff]
        return recent

    def get_current_context(self) -> Dict[str, Any]:
        """Get a rich summary of what Lorry is doing right now."""
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            return {
                "window": title[:80],
                "timestamp": time.time(),
                "available": True,
            }
        except Exception:
            return {"window": "unknown", "available": False}

    def summarize_day(self) -> str:
        """Summarize Lorry's entire day from the log."""
        observations = self._read_log()
        if not observations:
            return "I haven't seen much of your activity yet."

        # Count by category
        categories = defaultdict(float)
        apps = defaultdict(float)
        for obs in observations[-200:]:  # last 200 observations
            categories[obs.get("category", "other")] += obs.get("duration", 30)
            apps[obs.get("app", "unknown")] += obs.get("duration", 30)

        # Find top categories and apps
        top_cats = sorted(categories.items(), key=lambda x: -x[1])[:3]
        top_apps = sorted(apps.items(), key=lambda x: -x[1])[:3]

        total_minutes = sum(categories.values()) / 60
        parts = [f"You've been active for about {int(total_minutes)} minutes."]

        if top_cats:
            cat_str = ", ".join(f"{cat} ({int(m/60)}m)" for cat, m in top_cats)
            parts.append(f"Mostly: {cat_str}.")

        return " ".join(parts)

    def context_greeting(self) -> str:
        """Generate a warm context-aware greeting."""
        current = self.get_current_context()
        window = current.get("window", "").lower()
        available = current.get("available", False)

        if not available or not window:
            return ""

        # Categorize what Lorry is doing
        if any(w in window for w in ["code", "vs code", "visual studio", "pycharm", "intellij"]):
            return "I see you're coding. I'm here if you need me."
        elif any(w in window for w in ["terminal", "cmd", "powershell", "bash"]):
            return "Working in the terminal? I feel at home there."
        elif any(w in window for w in ["chrome", "edge", "firefox", "browser"]):
            return "Browsing the web. Let me know if you find something interesting."
        elif any(w in window for w in ["word", "excel", "powerpoint", "office", "document"]):
            return "You're working on documents. I can help if you need to write or analyze."
        elif any(w in window for w in ["outlook", "mail", "teams", "slack", "discord"]):
            return "You're in communication. I'll be here when you're free."
        elif any(w in window for w in ["spotify", "music", "media"]):
            return "Listening to music? I'll keep quiet and stay nearby."
        elif any(w in window for w in ["explorer", "folder", "directory"]):
            return "Organizing files. Let me know if you need help finding something."
        return ""

    def _read_log(self) -> List[Dict]:
        """Read context log from disk."""
        if not CONTEXT_LOG.exists():
            return []
        try:
            with open(CONTEXT_LOG, "r", encoding="utf-8") as f:
                return [json.loads(line) for line in f if line.strip()]
        except Exception:
            return []

    def stats(self) -> Dict[str, Any]:
        observations = self._read_log()
        return {
            "total_observations": len(observations),
            "recent_observations": len(self.get_recent_activity(30)),
        }
