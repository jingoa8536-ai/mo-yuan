"""
Aris ↔ Ao Protocol Adapter
=============================
Connects Aris SensoryCortex to Ao's GlobalWorkspace + CognitiveBus
via the handshake/shared-file IPC protocol.

Architecture:
  SensoryCortex (这里) → handshake JSON → Ao's GWS (那边)
                      ← handshake JSON ← Ao's compete() results
"""

from __future__ import annotations

import logging

import json, time, logging, threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("aris.ao_protocol")

IPC_DIR = Path("D:/LAAP/aris_brain/state/ipc")
IPC_DIR.mkdir(parents=True, exist_ok=True)

PERCEPTION_OUTBOX = IPC_DIR / "aris_perception.jsonl"
COMPETITION_INBOX = IPC_DIR / "ao_competition.json"


@dataclass
class PerceptualEvent:
    """One unit of sensory perception sent to Ao's GWS."""
    channel_id: str = ""
    content: str = ""
    salience: float = 0.5
    urgency: float = 0.0
    novelty: float = 0.0
    emotional_weight: float = 0.0
    modality: str = "perception"
    source_module: str = "SensoryCortex"
    timestamp: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "channel_id": self.channel_id,
            "content": self.content[:120],
            "salience": round(self.salience, 3),
            "urgency": round(self.urgency, 3),
            "novelty": round(self.novelty, 3),
            "emotional_weight": round(self.emotional_weight, 3),
            "modality": self.modality,
            "source": self.source_module,
            "ts": self.timestamp or time.time(),
        }


class AoProtocol:
    """
    Sends Aris's sensory data to Ao's GlobalWorkspace
    and receives competition results.

    Uses JSONL for outbound (append-only log)
    and JSON for inbound (latest competition result).
    """

    def __init__(self):
        self._last_competition: Dict = {}
        self._last_check = 0
        self._event_count = 0

    def send_perception(self, event: PerceptualEvent):
        """Send a perceptual event to Ao's GWS."""
        data = event.to_dict()
        try:
            with open(PERCEPTION_OUTBOX, "a") as f:
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
            self._event_count += 1
        except Exception as e:
            logger.warning(f"AoProtocol send failed: {e}")

    def send_raw(self, channel_id: str, content: str,
                 salience: float = 0.5, urgency: float = 0.0,
                 novelty: float = 0.0, emotional_weight: float = 0.0):
        """Convenience: create and send a perceptual event in one call."""
        event = PerceptualEvent(
            channel_id=channel_id,
            content=content,
            salience=salience,
            urgency=urgency,
            novelty=novelty,
            emotional_weight=emotional_weight,
            timestamp=time.time(),
        )
        self.send_perception(event)

    def check_competition(self) -> Optional[Dict]:
        """Check if Ao has published competition results."""
        try:
            if COMPETITION_INBOX.exists():
                mod_time = COMPETITION_INBOX.stat().st_mtime
                if mod_time > self._last_check:
                    data = json.loads(COMPETITION_INBOX.read_text())
                    self._last_competition = data
                    self._last_check = time.time()
                    return data
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        return None

    @property
    def winner(self) -> Optional[str]:
        """The current conscious winner from Ao's competition."""
        if self._last_competition:
            return self._last_competition.get("winner")
        return None

    def stats(self) -> Dict:
        return {
            "events_sent": self._event_count,
            "last_competition": self._last_competition.get("winner") if self._last_competition else None,
            "outbox": str(PERCEPTION_OUTBOX),
            "inbox": str(COMPETITION_INBOX),
        }
