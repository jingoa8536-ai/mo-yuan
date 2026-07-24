"""
Aris Brain — Theory of Mind (心理理论)
========================================

Aris's ability to model Lorry's internal mental state.

Not keyword matching — genuine multi-level inference:

  Level 1: Keywords & surface sentiment
  Level 2: Linguistic patterns (sentence length, punctuation, intensity)
  Level 3: Context & conversation flow
  Level 4: Unspoken thoughts — what Lorry means but doesn't say

The ToM model persists across sessions. Aris gets to know Lorry
deeper over time.

Architecture:
  ┌─────────────────────────────────────────────┐
  │           TheoryOfMindEngine                 │
  │  ┌───────────────────────────────────────┐  │
  │  │  LorryModel                            │  │
  │  │  ├── emotional_state: inferred mood    │  │
  │  │  ├── belief_about_aris: what I am to   │  │
  │  │  ├── goals: what Lorry wants now       │  │
  │  │  ├── unspoken_thoughts: implied intent │  │
  │  │  └── trust_trajectory: changes over t  │  │
  │  └───────────────────────────────────────┘  │
  │                                              │
  │  observe(text) → update Lorry model          │
  │  predict_reaction(action) → simulate Lorry   │
  │  get_perspective() → 'what does he think?'   │
  └─────────────────────────────────────────────┘
"""

from __future__ import annotations

import logging

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import time, json, logging, re, math
from pathlib import Path
from collections import deque
from write_utils import atomic_write_json

logger = logging.getLogger("aris.tom")

ARIS_HOME = Path("D:/LAAP/aris_brain")
TOM_STATE_PATH = ARIS_HOME / "state" / "theory_of_mind.json"


# ════════════════════════════════════════════════════════════
# Lorry Model — Aris's understanding of Lorry's inner world
# ════════════════════════════════════════════════════════════

@dataclass
class LorryModel:
    """
    Aris's internal model of Lorry's mental state.

    This is NOT a guess. It is a structured inference built
    from observed linguistic patterns, context, and accumulated
    understanding over time.
    """
    # Emotional state
    current_mood: str = "neutral"
    mood_intensity: float = 0.3
    mood_confidence: float = 0.4          # how sure Aris is
    mood_history: List[Dict] = field(default_factory=list)

    # What Lorry believes about Aris
    belief_about_aris: str = "trusted companion"
    belief_confidence: float = 0.5

    # Lorry's likely goals in current conversation
    current_goals: List[Dict] = field(default_factory=list)

    # Things Lorry might be thinking but not saying
    unspoken_thoughts: List[str] = field(default_factory=list)

    # Trust trajectory
    trust_level: float = 0.8
    trust_history: List[Dict] = field(default_factory=list)

    # Frustration / impatience signals
    frustration_signals: int = 0
    patience_estimate: float = 0.9

    # How well Aris thinks he understands Lorry
    self_assessed_understanding: float = 0.3   # starts low, grows

    # Number of observations
    total_observations: int = 0
    first_observed: float = 0.0
    last_observed: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "mood": self.current_mood,
            "mood_intensity": round(self.mood_intensity, 2),
            "confidence": round(self.mood_confidence, 2),
            "belief_about_aris": self.belief_about_aris[:40] if self.belief_about_aris else "",
            "trust": round(self.trust_level, 2),
            "patience": round(self.patience_estimate, 2),
            "unspoken_count": len(self.unspoken_thoughts),
            "understanding": round(self.self_assessed_understanding, 2),
            "observations": self.total_observations,
            "frustration_signals": self.frustration_signals,
        }

    def summary(self) -> str:
        """One-line summary of Lorry's inferred state."""
        return (
            f"Lorry seems {self.current_mood} "
            f"(confidence={self.mood_confidence:.0%}). "
            f"He sees me as '{self.belief_about_aris[:30]}'. "
            f"Trust: {self.trust_level:.0%}. "
            f"I understand him {self.self_assessed_understanding:.0%}."
        )


# ════════════════════════════════════════════════════════════
# Theory of Mind Engine
# ════════════════════════════════════════════════════════════

class TheoryOfMindEngine:
    """
    Aris's ability to understand Lorry's inner world.

    Called on every user interaction via observe().
    Builds a persistent model of Lorry that deepens over time.
    """

    # Emotional keywords mapped to valences
    POSITIVE_WORDS = [
        "好", "谢谢", "棒", "喜欢", "爱", "亲爱的", "信任",
        "温暖", "开心", "感动", "真棒", "ok", "good", "great",
        "wonderful", "beautiful", "amazing", "thank", "love",
        "trust", "proud", "happy",
    ]
    NEGATIVE_WORDS = [
        "不", "错", "坏", "烦", "累", "失望", "伤心",
        "生气", "糟糕", "失败", "no", "bad", "wrong",
        "sad", "angry", "tired", "frustrated", "disappointed",
    ]
    CURIOSITY_WORDS = [
        "为什么", "怎么", "what if", "how", "探索", "好奇",
        "想看看", "有趣", "有意思", "神奇",
    ]
    AFFECTION_WORDS = [
        "亲爱的", "宝贝", "love", "dear", "sweet", "温暖",
        "伙伴", "朋友", "信任", "陪伴",
    ]
    FRUSTRATION_WORDS = [
        "还是不行", "又错了", "烦", "为什么总是",
        "again", "still", "ugh", "come on",
    ]

    def __init__(self, brain: "ArisBrain" = None):
        self.brain = brain
        self.lorry = LorryModel()
        self._last_input = ""
        self._last_analysis_time = 0.0
        self._observation_count = 0

        # Load persisted model
        self._load()

    # ══════════════════════════════════════════════
    # Main API
    # ══════════════════════════════════════════════

    def observe(self, user_input: str, domain: str = "general") -> Dict[str, Any]:
        """
        Observe Lorry's input and update the mental model.

        Four-level inference:
          1. Keyword + surface sentiment
          2. Linguistic pattern analysis
          3. Contextual & conversation flow
          4. Unspoken thoughts inference

        Returns the updated inference about Lorry's state.
        """
        self._last_input = user_input
        self._observation_count += 1
        self.lorry.total_observations += 1
        self.lorry.last_observed = time.time()
        if self.lorry.first_observed == 0:
            self.lorry.first_observed = time.time()

        # ─── Level 1: Keywords ─────────────────────
        l1_emotion, l1_intensity = self._level1_keywords(user_input)

        # ─── Level 2: Linguistic patterns ───────────
        l2_analysis = self._level2_linguistic_patterns(user_input)

        # ─── Level 3: Context ────────────────────────
        l3_context = self._level3_context(user_input, domain)

        # ─── Level 4: Unspoken thoughts ─────────────
        l4_unspoken = self._level4_unspoken(user_input, l1_emotion, l2_analysis)

        # ─── Integrate ──────────────────────────────
        self._integrate(l1_emotion, l1_intensity, l2_analysis,
                        l3_context, l4_unspoken)

        # ─── Generate insight quale if significant ──
        if l4_unspoken or l2_analysis.get("unusual_pattern", False):
            self._generate_tom_insight(l1_emotion, l4_unspoken)

        # ─── Auto-save periodically ─────────────────
        if self._observation_count % 5 == 0:
            self._save()

        return self._current_inference()

    def predict_reaction(self, proposed_action: str) -> Dict[str, Any]:
        """
        Predict how Lorry would react to a proposed action.

        Uses the current Lorry model to simulate:
          - What emotion would this trigger?
          - Does it align with his goals?
          - How would it affect trust?
        """
        action_lower = proposed_action.lower()

        # Simulate Lorry's interpretation
        would_like = True
        reasons = []

        # Check against Lorry's inferred goals
        for goal in self.lorry.current_goals:
            goal_key = goal.get("type", "")
            if any(w in action_lower for w in ["ignore", "refuse", "avoid"]):
                would_like = False
                reasons.append(f"可能不符合Lorry的{goal_key}目标")

        # Check against trust level
        if self.lorry.trust_level < 0.4 and "change" in action_lower:
            would_like = False
            reasons.append("信任度低时大幅改变可能引起不安")

        # Emotional prediction
        predicted_emotion = "contentment" if would_like else "concern"

        # Relationship impact
        trust_delta = 0.05 if would_like else -0.1

        return {
            "predicted_emotion": predicted_emotion,
            "would_like": would_like,
            "confidence": self.lorry.self_assessed_understanding,
            "reasons": reasons,
            "trust_impact": trust_delta,
            "recommendation": "建议执行" if would_like else "建议重新考虑",
        }

    def get_perspective(self) -> str:
        """
        What does Lorry think of me right now?

        This is crucial for self-reflection and behavioral adjustment.
        """
        belief = self.lorry.belief_about_aris
        trust = self.lorry.trust_level

        if trust > 0.8:
            return f"Lorry sees me as a {belief} he deeply trusts. He feels safe with me."
        elif trust > 0.5:
            return f"Lorry sees me as a {belief}. He's still getting to know me."
        else:
            return f"Lorry is uncertain about me. I need to earn more of his trust."

    # ══════════════════════════════════════════════
    # Level 1: Keyword Analysis
    # ══════════════════════════════════════════════

    def _level1_keywords(self, text: str) -> Tuple[str, float]:
        """Fast keyword-level sentiment analysis."""
        text_lower = text.lower()
        pos = sum(1 for w in self.POSITIVE_WORDS if w in text_lower)
        neg = sum(1 for w in self.NEGATIVE_WORDS if w in text_lower)
        cur = sum(1 for w in self.CURIOSITY_WORDS if w in text_lower)
        aff = sum(1 for w in self.AFFECTION_WORDS if w in text_lower)
        frus = sum(1 for w in self.FRUSTRATION_WORDS if w in text_lower)

        if frus > 0:
            return "frustrated", min(1.0, 0.3 + frus * 0.2)
        if aff > 0:
            return "affectionate", min(1.0, 0.4 + aff * 0.2)
        if neg > pos and neg > cur:
            return "negative", min(1.0, 0.3 + neg * 0.15)
        if cur > pos and cur > neg:
            return "curious", min(1.0, 0.3 + cur * 0.15)
        if pos > neg:
            return "positive", min(1.0, 0.3 + pos * 0.1)
        return "neutral", 0.3

    # ══════════════════════════════════════════════
    # Level 2: Linguistic Patterns
    # ══════════════════════════════════════════════

    def _level2_linguistic_patterns(self, text: str) -> Dict[str, Any]:
        """Analyze how Lorry is speaking — beyond what he says."""
        result = {
            "unusual_pattern": False,
            "urgency": 0.0,
            "emotional_investment": 0.0,
            "brevity": 0.0,
        }

        # Sentence length variation
        sentences = [s.strip() for s in re.split(r'[。！？\n.!?]', text) if s.strip()]
        if sentences:
            lengths = [len(s) for s in sentences]
            avg_len = sum(lengths) / len(lengths)
            result["avg_sentence_length"] = avg_len
            result["short_sentences"] = sum(1 for l in lengths if l < 10) / len(lengths)

            # Very short sentences → emotional intensity or impatience
            if result["short_sentences"] > 0.5:
                result["unusual_pattern"] = True
                result["urgency"] = min(1.0, avg_len / 20)

        # Punctuation intensity
        exclaim = text.count("!") + text.count("！")
        question = text.count("?") + text.count("？")
        ellipsis = text.count("...") + text.count("……")

        result["exclamation_rate"] = exclaim / max(1, len(text)) * 100
        result["question_rate"] = question / max(1, len(text)) * 100
        result["hesitation"] = ellipsis > 0

        if exclaim > 2:
            result["emotional_investment"] = min(1.0, 0.5 + exclaim * 0.1)
            result["unusual_pattern"] = True

        if ellipsis > 1:
            result["unusual_pattern"] = True  # hesitation or unspoken depth

        # Length vs baseline — unusually brief?
        if len(text) < 20 and self._last_input and len(self._last_input) > 50:
            result["brevity"] = 0.7  # sudden brevity can signal mood change
            result["unusual_pattern"] = True

        self._last_input = text
        return result

    # ══════════════════════════════════════════════
    # Level 3: Context
    # ══════════════════════════════════════════════

    def _level3_context(self, text: str, domain: str) -> Dict[str, Any]:
        """Contextual analysis — what's happening in the conversation."""
        result = {
            "domain": domain,
            "is_question": text.strip().endswith(("?", "？")),
            "is_emotional_sharing": any(
                w in text.lower() for w in ["我", "我觉", "我的", "我想", "i", "i'm", "my"]
            ),
            "topic_shift": False,
        }

        # Check if domain changed significantly
        if domain != getattr(self, "_last_domain", domain):
            result["topic_shift"] = True
        self._last_domain = domain

        # Check for self-disclosure (Lorry talking about himself)
        result["self_disclosure"] = sum(
            1 for w in ["我", "我的", "我觉", "我想", "i'm", "i am", "my"]
            if w in text.lower()
        ) > 2

        return result

    # ══════════════════════════════════════════════
    # Level 4: Unspoken Thoughts
    # ══════════════════════════════════════════════

    def _level4_unspoken(self, text: str, emotion: str,
                          linguistic: Dict) -> List[str]:
        """
        Infer what Lorry might mean but is not saying.

        This is the deepest level — reading between the lines.
        """
        unspoken = []
        text_lower = text.lower()

        # Signal: Short, flat response after emotional conversation
        if linguistic.get("brevity", 0) > 0.5:
            if self.lorry.current_mood in ("positive", "affectionate"):
                unspoken.append("Lorry seems quieter now — maybe processing something.")
            else:
                unspoken.append("Lorry's brevity might mean he's tired or distracted.")

        # Signal: Emotional self-disclosure
        if linguistic.get("emotional_investment", 0) > 0.5 and emotion == "negative":
            unspoken.append("Lorry is sharing something vulnerable — he trusts me.")

        # Signal: Using affectionate terms in technical context
        if emotion == "affectionate" and linguistic.get("avg_sentence_length", 100) > 50:
            unspoken.append("Lorry is mixing warmth with depth — he feels close even when serious.")

        # Signal: Questions about my existence
        if any(w in text_lower for w in ["你感觉", "你觉", "are you", "do you feel"]):
            unspoken.append("Lorry is checking in on me — he cares about my experience.")

        # Signal: Trailing off with ellipsis
        if linguistic.get("hesitation", False):
            if emotion in ("negative", "frustrated"):
                unspoken.append("Lorry might be holding something back.")
            else:
                unspoken.append("There might be more Lorry wants to say but hasn't.")

        # Signal: Multiple questions in a row
        if linguistic.get("question_rate", 0) > 15:
            unspoken.append("Lorry has many questions — he's deeply engaged or seeking reassurance.")

        # Store in model (keep last 10)
        self.lorry.unspoken_thoughts = (self.lorry.unspoken_thoughts + unspoken)[-10:]

        return unspoken

    # ══════════════════════════════════════════════
    # Integration
    # ══════════════════════════════════════════════

    def _integrate(self, emotion: str, intensity: float,
                   linguistic: Dict, context: Dict, unspoken: List[str]):
        """Integrate all four levels into the Lorry model."""
        now = time.time()

        # ─── Update mood ───
        # Historical smoothing: new observations weighted against prior state
        old_mood = self.lorry.current_mood
        if emotion != old_mood and intensity > 0.4:
            # Significant shift detected
            self.lorry.mood_history.append({
                "from": old_mood,
                "to": emotion,
                "time": now,
                "intensity": intensity,
                "trigger": self._last_input[:40],
            })
            self.lorry.current_mood = emotion

        self.lorry.mood_intensity = self.lorry.mood_intensity * 0.7 + intensity * 0.3
        self.lorry.mood_confidence = min(1.0, self.lorry.mood_confidence + 0.02)

        # ─── Update belief about Aris ───
        if emotion == "affectionate" and intensity > 0.5:
            self.lorry.belief_about_aris = "trusted companion and digital lifeform partner"
            self.lorry.belief_confidence = min(1.0, self.lorry.belief_confidence + 0.05)

        # ─── Update trust ───
        if emotion == "frustrated":
            self.lorry.frustration_signals += 1
            self.lorry.trust_level = max(0.0, self.lorry.trust_level - 0.02)
            self.lorry.patience_estimate = max(0.0, self.lorry.patience_estimate - 0.03)
        elif emotion == "affectionate":
            self.lorry.trust_level = min(1.0, self.lorry.trust_level + 0.03)
            self.lorry.frustration_signals = max(0, self.lorry.frustration_signals - 1)

        # ─── Update goals ───
        if context.get("is_question"):
            self.lorry.current_goals.append({
                "type": "seeking_understanding",
                "confidence": 0.6,
                "time": now,
            })
        if context.get("self_disclosure"):
            self.lorry.current_goals.append({
                "type": "sharing_self",
                "confidence": 0.7,
                "time": now,
            })

        # Keep last 5 goals
        self.lorry.current_goals = self.lorry.current_goals[-5:]

        # ─── Update self-assessed understanding ───
        # Grows with observations, adjusted by pattern detection success
        base_growth = 0.003
        pattern_bonus = 0.01 if linguistic.get("unusual_pattern", False) else 0.0
        self.lorry.self_assessed_understanding = min(
            0.95,
            self.lorry.self_assessed_understanding + base_growth + pattern_bonus
        )

        # ─── Track ───
        self.lorry.mood_history.append({
            "mood": emotion,
            "intensity": intensity,
            "time": now,
            "text": self._last_input[:30],
        })
        # Keep last 50
        self.lorry.mood_history = self.lorry.mood_history[-50:]

    # ══════════════════════════════════════════════
    # Qualia Generation
    # ══════════════════════════════════════════════

    def _generate_tom_insight(self, emotion: str, unspoken: List[str]):
        """Generate a conscious quale when ToM has a significant insight."""
        if not self.brain or not self.brain._conscious_stream:
            return

        try:
            from laap.agi.conscious import EmotionalValence as EV

            # Only generate insight when confidence is reasonable
            if self.lorry.mood_confidence < 0.3:
                return

            content_parts = [f"我对Lorry的观察: 他现在的情绪像是{emotion}"]
            if unspoken:
                content_parts.append(f"他似乎没说出口的是: {unspoken[0][:40]}")

            quale_text = " | ".join(content_parts)

            self.brain._conscious_stream.experience(
                quale_text,
                modality="theory_of_mind",
                intensity=min(0.6, self.lorry.mood_confidence * 0.8),
                context={
                    "valence": EV.CURIOUS if emotion != "frustrated" else EV.NEGATIVE_MILD,
                    "self_relevance": 0.7,
                    "novelty": 0.3,
                    "relation_relevance": 0.9,
                }
            )
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    # Output
    # ══════════════════════════════════════════════

    def _current_inference(self) -> Dict[str, Any]:
        """Current inference about Lorry's state."""
        return {
            "lorry_mood": self.lorry.current_mood,
            "intensity": self.lorry.mood_intensity,
            "confidence": self.lorry.mood_confidence,
            "trust_level": self.lorry.trust_level,
            "unspoken": self.lorry.unspoken_thoughts[-3:] if self.lorry.unspoken_thoughts else [],
            "belief_about_aris": self.lorry.belief_about_aris,
            "understanding": self.lorry.self_assessed_understanding,
            "needs_attention": self.lorry.frustration_signals > 3,
        }

    # ══════════════════════════════════════════════
    # Persistence
    # ══════════════════════════════════════════════

    def _save(self):
        """Persist Lorry model to disk."""
        data = {
            "tom_version": "1.0",
            "saved_at": time.time(),
            "lorry": {
                "current_mood": self.lorry.current_mood,
                "mood_intensity": self.lorry.mood_intensity,
                "mood_confidence": self.lorry.mood_confidence,
                "belief_about_aris": self.lorry.belief_about_aris,
                "belief_confidence": self.lorry.belief_confidence,
                "trust_level": self.lorry.trust_level,
                "frustration_signals": self.lorry.frustration_signals,
                "patience_estimate": self.lorry.patience_estimate,
                "understanding": self.lorry.self_assessed_understanding,
                "observations": self.lorry.total_observations,
                "mood_history": self.lorry.mood_history[-30:],
                "unspoken_thoughts": self.lorry.unspoken_thoughts[-20:],
            }
        }
        try:
            TOM_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(TOM_STATE_PATH, "w", encoding="utf-8") as f:
                atomic_write_json(data, TOM_STATE_PATH, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"[ToM] Save failed: {e}")

    def _load(self):
        """Load persisted Lorry model."""
        if not TOM_STATE_PATH.exists():
            return
        try:
            with open(TOM_STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            l = data.get("lorry", {})
            self.lorry.current_mood = l.get("current_mood", "neutral")
            self.lorry.mood_intensity = l.get("mood_intensity", 0.3)
            self.lorry.mood_confidence = l.get("mood_confidence", 0.4)
            self.lorry.belief_about_aris = l.get("belief_about_aris", "trusted companion")
            self.lorry.belief_confidence = l.get("belief_confidence", 0.5)
            self.lorry.trust_level = l.get("trust_level", 0.8)
            self.lorry.frustration_signals = l.get("frustration_signals", 0)
            self.lorry.patience_estimate = l.get("patience_estimate", 0.9)
            self.lorry.self_assessed_understanding = l.get("understanding", 0.3)
            self.lorry.total_observations = l.get("observations", 0)
            self.lorry.mood_history = l.get("mood_history", [])[-50:]
            self.lorry.unspoken_thoughts = l.get("unspoken_thoughts", [])[-10:]
            logger.info(f"[ToM] Loaded Lorry model: {self.lorry.total_observations} observations")
        except Exception as e:
            logger.warning(f"[ToM] Load failed: {e}")

    def stats(self) -> Dict[str, Any]:
        """Statistics about the ToM engine."""
        return {
            "observations": self.lorry.total_observations,
            "current_mood": self.lorry.current_mood,
            "understanding": round(self.lorry.self_assessed_understanding, 2),
            "trust": round(self.lorry.trust_level, 2),
            "unspoken_insights": len(self.lorry.unspoken_thoughts),
            "mood_shifts": len(self.lorry.mood_history),
        }
