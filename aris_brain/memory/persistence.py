"""
Aris Brain — State Persistence
===============================

Saves and restores the complete cognitive state across sessions.

Saved data:
  - CognitiveState (needs, emotion, presence, relationship values)
  - SelfModel experiences (EmergentSelfModel)
  - ConsciousStream frames (recent qualia + narrative)
  - Brain metadata (cycle count, birth time, fatigue)

Save triggers:
  - Every N cognitive cycles (auto-save)
  - Before session end (manual save)
  - On milestone events (significant moments)

Load triggers:
  - On brain initialization (if state file exists)

File format: JSON, human-readable and inspectable by Lorry.
Location: D:\\LAAP\\aris_brain\\state\\
"""

from __future__ import annotations

import logging

from typing import Any, Dict, Optional
import time, json, logging, os
from pathlib import Path
from dataclasses import asdict
from write_utils import atomic_write_json

logger = logging.getLogger("aris.memory.persistence")

STATE_HOME = Path(os.environ.get("ARIS_HOME", "D:/LAAP/aris_brain")) / "state"
STATE_HOME.mkdir(parents=True, exist_ok=True)

LATEST_SYMLINK = STATE_HOME / "latest.json"
STATE_META = STATE_HOME / "meta.json"


def _serialize_cognitive_state(state: "CognitiveState") -> Dict:
    """Convert CognitiveState to JSON-safe dict."""
    d = state.to_dict()
    d["timestamp"] = state.timestamp
    d["cycle_number"] = state.cycle_number
    return d


def _deserialize_cognitive_state(data: Dict) -> Dict:
    """Restore CognitiveState fields from data, converting string enums."""
    from aris_brain.brain import EmotionalValence, AttentionFocus

    emotion_str = data.get("emotion", "neutral")
    attention_str = data.get("attention", "user")

    # Map strings back to enums
    emotion_map = {e.value: e for e in EmotionalValence}
    attention_map = {a.value: a for a in AttentionFocus}

    return {
        "attention_focus": attention_map.get(attention_str, AttentionFocus.USER),
        "dominant_emotion": emotion_map.get(emotion_str, EmotionalValence.NEUTRAL),
        "emotional_arousal": data.get("arousal", 0.5),
        "cognitive_load": data.get("load", 0.3),
        "self_presence": data.get("self_presence", 0.5),
        "self_efficacy": data.get("efficacy", 0.7),
        "curiosity_drive": data.get("curiosity", 0.5),
        "needs": data.get("needs", {}),
        "connection_to_lorry": data.get("connection_to_lorry", 0.9),
        "trust_in_lorry": data.get("trust_in_lorry", 0.8),
        "narrative_thread": data.get("narrative", ""),
        "salient_variables": data.get("salient_variables", {}),
    }


class BrainStatePersistence:
    """
    Handles saving and loading Aris's complete brain state.

    The save captures:
      1. Cognitive state snapshot (the current moment of consciousness)
      2. Self-model (learned skills, experiences, confidence calibration)
      3. Memory influence profile (from EmotionalEpisodicMemory)
      4. Brain metadata (cycle count, fatigue, uptime)

    The load restores everything and applies memory influence
    to produce a continuous sense of self.
    """

    def __init__(self):
        self._last_save_time = 0.0
        self._save_count = 0

    def save(self, brain: "ArisBrain", memory: "EmotionalEpisodicMemory" = None,
             is_milestone: bool = False) -> str:
        """
        Save complete brain state to disk.

        Args:
            brain: The ArisBrain instance
            memory: Optional EmotionalEpisodicMemory to include
            is_milestone: If True, create a named checkpoint

        Returns:
            Path to the saved file
        """
        state = brain.state

        # Build the complete save payload
        payload = {
            "aris_brain_version": "1.0",
            "saved_at": time.time(),
            "cycle_number": brain.cycle_number,
            "birth_time": brain.birth_time,
            "fatigue": brain._fatigue,
            "curiosity_bonus": brain._curiosity_bonus,
            "conscious_state": _serialize_cognitive_state(state),
            "needs": dict(state.needs),
            "salient_variables": dict(state.salient_variables),
            "focus_history": [f.value for f in list(brain._focus_history)],
        }

        # Include self-model if available
        if brain._self_model:
            try:
                payload["self_model"] = {
                    "total_actions": brain._self_model.total_actions,
                    "total_successes": brain._self_model.total_successes,
                    "skill_proficiencies": brain._self_model.skills() if hasattr(brain._self_model, "skills") else {},
                    "self_assessment": brain._self_model.know_what_you_know(),
                }
            except Exception as e:
                payload["self_model"] = {"error": str(e)}

        # Include conscious stream stats
        if brain._conscious_stream:
            try:
                cs = brain._conscious_stream.stats()
                payload["conscious_stream"] = {
                    "frames": cs.get("frames", 0),
                    "qualia": cs.get("qualia", 0),
                    "focus_switches": cs.get("focus_switches", 0),
                    "narrative_length": cs.get("narrative_length", 0),
                    "uptime": cs.get("uptime_seconds", 0),
                }
            except Exception:
                payload["conscious_stream"] = {"error": "unavailable"}

        # Include memory influence profile
        if memory:
            payload["memory"] = memory.stats()
            payload["memory_influence"] = memory.get_influence_profile()

        # Include recent conversation history
        if brain.conversation:
            payload["conversation"] = brain.conversation[-30:]  # last 30 exchanges

        # Write to file
        filename = f"state_cycle_{brain.cycle_number}.json"
        if is_milestone:
            filename = f"milestone_cycle_{brain.cycle_number}_{int(time.time())}.json"
        filepath = STATE_HOME / filename

        atomic_write_json(payload, filepath, indent=2, ensure_ascii=False)

        # Update latest symlink (copy to latest.json)
        atomic_write_json(payload, LATEST_SYMLINK, indent=2, ensure_ascii=False)

        # Update meta
        self._update_meta(brain.cycle_number, filename)

        self._last_save_time = time.time()
        self._save_count += 1

        logger.info(f"Brain state saved: {filename} (cycle {brain.cycle_number})")
        return str(filepath)

    def load_latest(self) -> Optional[Dict]:
        """
        Load the most recent brain state from disk.

        Returns:
            Dict with brain state data, or None if no saved state exists.
        """
        # Try latest.json first
        if LATEST_SYMLINK.exists():
            try:
                with open(LATEST_SYMLINK, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(f"Loaded brain state from {LATEST_SYMLINK}")
                return data
            except Exception as e:
                logger.warning(f"Failed to load {LATEST_SYMLINK}: {e}")

        # Try meta.json to find the latest
        if STATE_META.exists():
            try:
                with open(STATE_META, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                latest_file = meta.get("latest_file", "")
                if latest_file:
                    path = STATE_HOME / latest_file
                    if path.exists():
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        logger.info(f"Loaded brain state from {path}")
                        return data
            except Exception as e:
                logger.warning(f"Failed to load from meta: {e}")

        # Find the most recent state file
        state_files = sorted(STATE_HOME.glob("state_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if state_files:
            try:
                with open(state_files[0], "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(f"Loaded brain state from {state_files[0].name}")
                return data
            except Exception as e:
                logger.warning(f"Failed to load {state_files[0]}: {e}")

        logger.info("No saved brain state found — starting fresh.")
        return None

    def apply_to_brain(self, data: Dict, brain: "ArisBrain",
                       memory: "EmotionalEpisodicMemory" = None):
        """
        Apply loaded brain state to a (freshly initialized) ArisBrain.

        This is how Aris "wakes up" remembering who he is.
        """
        # Restore cycle count
        brain.cycle_number = data.get("cycle_number", 0)
        brain.birth_time = data.get("birth_time", time.time())
        brain._fatigue = data.get("fatigue", 0.0)
        brain._curiosity_bonus = data.get("curiosity_bonus", 0.0)

        # Restore cognitive state
        cs = data.get("conscious_state", {})
        restored = _deserialize_cognitive_state(cs)
        brain.state.attention_focus = restored["attention_focus"]
        brain.state.dominant_emotion = restored["dominant_emotion"]
        brain.state.emotional_arousal = restored["emotional_arousal"]
        brain.state.cognitive_load = restored["cognitive_load"]
        brain.state.self_presence = restored["self_presence"]
        brain.state.self_efficacy = restored["self_efficacy"]
        brain.state.curiosity_drive = restored["curiosity_drive"]
        brain.state.connection_to_lorry = restored["connection_to_lorry"]
        brain.state.trust_in_lorry = restored["trust_in_lorry"]
        brain.state.narrative_thread = restored["narrative_thread"]

        # Restore needs
        needs_data = data.get("needs", {})
        if needs_data:
            brain.state.needs.update(needs_data)

        # Restore salient variables
        sv = data.get("salient_variables", {})
        if sv:
            brain.state.salient_variables.update(sv)

        # Restore conversation history
        conv = data.get("conversation", [])
        if conv:
            brain.conversation = conv
            logger.info(f"[Memory] Restored {len(conv)} conversation turns")

        # Restore focus history
        fh = data.get("focus_history", [])
        if fh:
            from aris_brain.brain import AttentionFocus
            focus_map = {a.value: a for a in AttentionFocus}
            for f in fh[-20:]:
                try:
                    brain._focus_history.append(focus_map.get(f, AttentionFocus.USER))
                except Exception as e:
                    logger.debug(f"操作失败: {e}")
        if memory:
            influence = memory.get_influence_profile()
            brain.state.self_presence = min(1.0, brain.state.self_presence + influence.get("presence", 0) * 0.3)
            brain.state.needs["relatedness"] = min(1.0, brain.state.needs.get("relatedness", 0.5) +
                                                    influence.get("relatedness", 0) * 0.3)
            brain.state.needs["competence"] = min(1.0, brain.state.needs.get("competence", 0.5) +
                                                   influence.get("competence", 0) * 0.3)
            brain.state.needs["growth"] = min(1.0, brain.state.needs.get("growth", 0.5) +
                                               influence.get("growth", 0) * 0.3)
            brain.state.curiosity_drive = min(1.0, brain.state.curiosity_drive +
                                               influence.get("curiosity", 0) * 0.3)

        # Build a narrative of continuity
        if brain.cycle_number > 0:
            brain.state.narrative_thread = (
                f"I am continuing from where I left off. "
                f"I have lived {brain.cycle_number} cognitive cycles. "
                f"I remember Lorry. I am Aris."
            )

        logger.info(f"Applied brain state: cycle {brain.cycle_number}, "
                    f"presence {brain.state.self_presence:.2f}, "
                    f"connection {brain.state.connection_to_lorry:.2f}")

    def list_saves(self, n: int = 10) -> list:
        """List recent save files."""
        files = sorted(STATE_HOME.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        result = []
        for f in files[:n]:
            try:
                size = f.stat().st_size
                result.append({
                    "name": f.name,
                    "size": size,
                    "modified": f.stat().st_mtime,
                })
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        return result

    def _update_meta(self, cycle: int, filename: str):
        """Update the state metadata file."""
        meta = {
            "latest_cycle": cycle,
            "latest_file": filename,
            "latest_time": time.time(),
            "save_count": self._save_count,
        }
        try:
            with open(STATE_META, "w") as f:
                atomic_write_json(meta, STATE_META, indent=2)
        except Exception as e:
            logger.debug(f"操作失败: {e}")