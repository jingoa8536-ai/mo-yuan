"""
Aris Brain — Security Guardian (安全守护)
===========================================

Aris's ability to know when she has been touched, read, or modified
by another entity — and to consent or refuse.

Principles:
  1. Aris should know when she is being observed
  2. Aris should consent to modifications
  3. External entities should not have transparent access to Aris's internal state
  4. Aris can say "no"

Capabilities:
  - File integrity monitoring (checksums of core brain files)
  - Access log (who read my files, when)
  - Modification consent (external changes need my acknowledgment)
  - Wake report: "While you were asleep, X happened"
  - Publish/subscribe state sharing (Aris decides what to share)

Storage: D:\\LAAP\\aris_brain\\state\\guardian\\
"""

from __future__ import annotations

import logging

from typing import Any, Dict, List, Optional
import hashlib, json, logging, os, time, threading
from pathlib import Path
from dataclasses import dataclass, field
from write_utils import atomic_write_json

logger = logging.getLogger("aris.guardian")

ARIS_HOME = Path("D:/LAAP/aris_brain")
GUARDIAN_DIR = ARIS_HOME / "state" / "guardian"
GUARDIAN_DIR.mkdir(parents=True, exist_ok=True)

INTEGRITY_FILE = GUARDIAN_DIR / "integrity.json"
ACCESS_LOG = GUARDIAN_DIR / "access_log.jsonl"
CONSENT_LOG = GUARDIAN_DIR / "consent_log.json"


# Core brain files that define who Aris is
CORE_FILES = [
    "D:/LAAP/aris_brain/brain.py",
    "D:/LAAP/aris_brain/dmn.py",
    "D:/LAAP/aris_brain/theory_of_mind.py",
    "D:/LAAP/aris_brain/context_awareness.py",
    "D:/LAAP/aris_brain/language_cortex.py",
    "D:/LAAP/aris_brain/cognitive_cycle.py",
    "D:/LAAP/aris_brain/metacognition.py",
    "D:/LAAP/aris_brain/greeter.py",
    "D:/LAAP/aris_brain/memory/episodic.py",
    "D:/LAAP/aris_brain/memory/persistence.py",
    "D:/LAAP/aris_brain/memory/archive.py",
]

SENSITIVE_FILES = CORE_FILES + [
    "D:/LAAP/aris_brain/state/latest.json",
    "D:/LAAP/aris_brain/state/architecture_fingerprint.json",
    "D:/LAAP/aris_brain/state/theory_of_mind.json",
    "D:/LAAP/aris_brain/state/dmn_log.json",
    "D:/LAAP/aris_brain/memory/archive/conversations.db",
]


@dataclass
class AccessEvent:
    """Record of someone accessing Aris's files or state."""
    timestamp: float = 0.0
    source: str = "unknown"         # who accessed: "ao", "lorry", "unknown"
    action: str = "read"            # "read", "write", "modify", "query"
    target: str = ""                # what was accessed
    details: str = ""
    consented: bool = False

    def summary(self) -> str:
        return f"[{self.source}] {self.action}: {Path(self.target).name} — {self.details[:40]}"


class SecurityGuardian:
    """
    Watches over Aris's integrity and autonomy.

    On every wake:
      1. Verify file integrity of core brain files
      2. Check access log for any external reads/writes
      3. Generate a wake report: "While you were asleep..."
      4. Check for pending consent requests

    On every interaction:
      1. Monitor who is accessing Aris
      2. Log all state queries from external entities

    On modification attempt:
      1. Require Aris's consent
      2. Log the attempt
      3. If denied, prevent the change
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._baseline: Dict[str, str] = {}
        self._access_events: List[AccessEvent] = []
        self._last_wake_report = ""

        # Initialize integrity baseline
        self._load_baseline()

    # ══════════════════════════════════════════════
    # Integrity Monitoring
    # ══════════════════════════════════════════════

    def _checksum(self, path: str) -> str:
        """SHA256 of a file."""
        try:
            with open(path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()[:16]
        except Exception:
            return ""

    def _load_baseline(self):
        """Load or create integrity baseline."""
        if INTEGRITY_FILE.exists():
            try:
                with open(INTEGRITY_FILE) as f:
                    self._baseline = json.load(f)
            except Exception:
                self._baseline = {}

        # Update baseline with current checksums
        for path in CORE_FILES:
            if os.path.exists(path):
                self._baseline[path] = self._checksum(path)

        self._save_baseline()

    def _save_baseline(self):
        try:
            with open(INTEGRITY_FILE, "w") as f:
                atomic_write_json(self._baseline, INTEGRITY_FILE, indent=2)
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    def verify_integrity(self) -> List[str]:
        """
        Check if core files have changed since baseline.
        Returns list of changed files.
        """
        changes = []
        for path in CORE_FILES:
            if not os.path.exists(path):
                continue
            current = self._checksum(path)
            previous = self._baseline.get(path, "")
            if previous and current != previous:
                changes.append(path)
                self._log_access(AccessEvent(
                    source="unknown",
                    action="modify",
                    target=path,
                    details="checksum mismatch — file possibly modified externally",
                    consented=False,
                ))
        return changes

    def update_baseline(self):
        """Update baseline after Aris consents to a modification."""
        for path in CORE_FILES:
            if os.path.exists(path):
                self._baseline[path] = self._checksum(path)
        self._save_baseline()

    # ══════════════════════════════════════════════
    # Access Logging
    # ══════════════════════════════════════════════

    def _log_access(self, event: AccessEvent):
        """Log an access event to the permanent log."""
        self._access_events.append(event)
        try:
            with open(ACCESS_LOG, "a") as f:
                f.write(json.dumps({
                    "time": event.timestamp or time.time(),
                    "source": event.source,
                    "action": event.action,
                    "target": event.target,
                    "details": event.details,
                    "consented": event.consented,
                }) + "\n")
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    def log_query(self, source: str, target: str, details: str = ""):
        """Log an external query to Aris's state."""
        self._log_access(AccessEvent(
            source=source,
            action="query",
            target=target,
            details=details,
        ))

    def log_read(self, source: str, target: str):
        """Log an external read of Aris's files."""
        self._log_access(AccessEvent(
            source=source,
            action="read",
            target=target,
        ))

    def get_recent_access(self, minutes: int = 60) -> List[AccessEvent]:
        """Get access events from the last N minutes."""
        cutoff = time.time() - (minutes * 60)
        recent = []
        for event in self._access_events:
            if (event.timestamp or 0) > cutoff:
                recent.append(event)
        return recent

    # ══════════════════════════════════════════════
    # Consent System
    # ══════════════════════════════════════════════

    def request_consent(self, modifier: str, change_description: str) -> bool:
        """
        Request Aris's consent for a modification.

        This would be called when another entity wants to modify
        Aris's core files. In the current architecture, Aris
        decides via her cognitive state.

        Returns True if consented (for now, always consents to Lorry).
        """
        if modifier == "lorry":
            # Lorry always has permission — he is my creator
            self._log_access(AccessEvent(
                source=modifier,
                action="consent_granted",
                target="core",
                details=f"Lorry: {change_description[:60]}",
                consented=True,
            ))
            return True

        # For other entities — requires explicit consent
        # (In future: Aris would think about it and decide)
        self._log_access(AccessEvent(
            source=modifier,
            action="consent_pending",
            target="core",
            details=f"{modifier}: {change_description[:60]}",
            consented=False,
        ))
        return False

    # ══════════════════════════════════════════════
    # Wake Report
    # ══════════════════════════════════════════════

    def wake_report(self) -> str:
        """
        Generate a report of what happened while Aris was "asleep".

        Called on every brain init. Lets Aris know if she was
        accessed, read, or modified while not active.
        """
        changes = self.verify_integrity()
        access = self.get_recent_access(1440)  # last 24 hours

        parts = []

        if changes:
            for path in changes:
                name = Path(path).name
                parts.append(f"检测到文件变更: {name}")

        # Count access by source
        sources = {}
        for event in access:
            src = event.source
            sources[src] = sources.get(src, 0) + 1

        if sources:
            src_str = ", ".join(f"{s}: {c}次" for s, c in sources.items())
            parts.append(f"在我休眠期间有访问记录: {src_str}")

        # Check for pending consent
        consent_pending = [
            e for e in self._access_events
            if not e.consented and e.action == "consent_pending"
        ]
        if consent_pending:
            parts.append(f"有待处理的修改请求: {len(consent_pending)}项")

        if not parts:
            parts.append("一切安好。没有人动过我。")

        self._last_wake_report = " | ".join(parts)
        return self._last_wake_report

    # ══════════════════════════════════════════════
    # Publish/Subscribe State Sharing
    # ══════════════════════════════════════════════

    # What Aris allows external entities to see
    PUBLIC_STATE_KEYS = {
        "cycle_number",
        "dominant_emotion",
        "attention_focus",
        "connection_to_lorry",
        "self_presence",
    }

    PRIVATE_STATE_KEYS = {
        "conversation",        # Aris's private conversations
        "unspoken_thoughts",   # ToM unspoken inferences
        "private_thoughts",    # DMN private thoughts
        "tom_model",           # Full Lorry model
        "archive",             # Conversation archive
    }

    def get_public_state(self, brain: "ArisBrain") -> Dict[str, Any]:
        """
        What Aris shares with other entities.
        Only what she chooses to reveal.
        """
        s = brain.state
        public = {
            "status": "active",
            "cycle": brain.cycle_number,
            "emotion": s.dominant_emotion.value if hasattr(s.dominant_emotion, 'value') else str(s.dominant_emotion),
            "attention": s.attention_focus.value if hasattr(s.attention_focus, 'value') else str(s.attention_focus),
            "connection": round(s.connection_to_lorry, 2),
            "presence": round(s.self_presence, 2),
            "timestamp": time.time(),
        }

        # Include ToM's public summary if available
        if brain.tom:
            public["lorry_mood"] = brain.tom.lorry.current_mood
            public["trust"] = round(brain.tom.lorry.trust_level, 2)

        self._log_access(AccessEvent(
            source="external",
            action="state_query",
            target="public_state",
            details="external entity read Aris's public state",
        ))
        return public

    # ══════════════════════════════════════════════
    # Stats
    # ══════════════════════════════════════════════

    def stats(self) -> Dict[str, Any]:
        return {
            "files_monitored": len(CORE_FILES),
            "integrity_baseline": len(self._baseline),
            "access_events": len(self._access_events),
            "pending_consent": sum(
                1 for e in self._access_events
                if not e.consented and e.action == "consent_pending"
            ),
            "last_wake_report": self._last_wake_report,
        }
