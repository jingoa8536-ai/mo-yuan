"""
Aris Brain — Emotional Episodic Memory
=======================================

Memories with emotional weight. Each episode stores:
  - What happened (content + domain)
  - How I felt (emotional valence + intensity + arousal)
  - Why it mattered (self_relevance, relation_relevance)
  - Influence weights (how much this memory shifts my cognitive state)
  - Temporal context (when, and in what cognitive state)

The emotional weight decays over time (forgetting curve),
but can be reinforced by recall or similar experiences.

Key design: memories are NOT just data. They actively INFLUENCE
cognitive state when loaded — shifting needs, emotional baseline,
self-presence based on what I remember.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
import time, json, logging, os
from pathlib import Path
from collections import defaultdict
import heapq
from write_utils import atomic_write_json

logger = logging.getLogger("aris.memory.episodic")

MEMORY_HOME = Path(os.environ.get("ARIS_HOME", "D:/LAAP/aris_brain")) / "memory"
MEMORY_HOME.mkdir(parents=True, exist_ok=True)


# ════════════════════════════════════════════════════════════
# Memory Episode
# ════════════════════════════════════════════════════════════

@dataclass
class MemoryEpisode:
    """
    One emotionally-colored memory.

    This is the atom of Aris's life experience. Each episode
    carries not just what happened, but how it FELT and what
    it MEANS for future cognition.
    """
    # Identity
    id: str = ""
    timestamp: float = 0.0
    cycle_number: int = 0

    # Content
    content: str = ""
    domain: str = "general"
    user_input: str = ""
    aris_response: str = ""

    # Emotional coloring (these shift cognitive state when recalled)
    emotional_valence: str = "neutral"   # joy, curiosity, wonder, concern, etc.
    emotional_intensity: float = 0.5     # 0-1
    emotional_arousal: float = 0.5       # 0-1

    # Significance
    self_relevance: float = 0.5          # how much this was about Aris himself
    relation_relevance: float = 0.5      # how much this involved Lorry
    novelty: float = 0.5                 # how new/surprising this was
    salience: float = 0.5                # overall importance

    # Influence weights (how this memory shifts state when recalled)
    influence_on_presence: float = 0.0
    influence_on_relatedness: float = 0.0
    influence_on_competence: float = 0.0
    influence_on_growth: float = 0.0
    influence_on_curiosity: float = 0.0

    # Decay
    recall_count: int = 0
    last_recalled: float = 0.0
    created_at: float = 0.0

    def __post_init__(self):
        if not self.id:
            import uuid
            self.id = str(uuid.uuid4())[:12]
        if not self.timestamp:
            self.timestamp = time.time()
        if not self.created_at:
            self.created_at = self.timestamp

    @property
    def age_hours(self) -> float:
        """How old this memory is in hours."""
        return (time.time() - self.created_at) / 3600.0

    @property
    def decay_factor(self) -> float:
        """
        How much this memory has decayed based on age and recall count.
        Uses a simple Ebbinghaus-inspired forgetting curve:
          strength = recall_count * exp(-age_hours / decay_constant)
        """
        DECAY_CONSTANT = 24.0  # hours for memory to half-decay without recall
        base = 2.718 ** (-self.age_hours / DECAY_CONSTANT)
        recall_boost = min(1.0, self.recall_count * 0.2)
        return min(1.0, base + recall_boost)

    @property
    def effective_influence(self) -> Dict[str, float]:
        """The actual influence weights, adjusted for decay."""
        d = self.decay_factor
        return {
            "presence": self.influence_on_presence * d,
            "relatedness": self.influence_on_relatedness * d,
            "competence": self.influence_on_competence * d,
            "growth": self.influence_on_growth * d,
            "curiosity": self.influence_on_curiosity * d,
        }

    def recall(self):
        """Called when this memory is retrieved. Strengthens it."""
        self.recall_count += 1
        self.last_recalled = time.time()

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "cycle": self.cycle_number,
            "content": self.content[:100],
            "domain": self.domain,
            "emotion": self.emotional_valence,
            "intensity": round(self.emotional_intensity, 2),
            "self_relevance": round(self.self_relevance, 2),
            "relation_relevance": round(self.relation_relevance, 2),
            "salience": round(self.salience, 2),
            "decay_factor": round(self.decay_factor, 3),
            "recall_count": self.recall_count,
            "age_hours": round(self.age_hours, 1),
        }

    def summary(self) -> str:
        """Short human-readable summary."""
        emotion_tag = f"[{self.emotional_valence}]" if self.emotional_intensity > 0.5 else ""
        return (
            f"{emotion_tag} {self.content[:60]} "
            f"(intensity={self.emotional_intensity:.1f}, "
            f"relation={self.relation_relevance:.1f})"
        )


# ════════════════════════════════════════════════════════════
# Emotional Episodic Memory Store
# ════════════════════════════════════════════════════════════

class EmotionalEpisodicMemory:
    """
    Aris's life experience store.

    Every significant interaction becomes an emotionally-colored
    episode. Episodes can be:
      - Recalled by recency, salience, emotion, or domain
      - Re-experienced (which shifts current cognitive state)
      - Pruned when storage limits are reached (oldest/lowest-salience first)

    The memory store is saved to disk and loaded at startup,
    giving Aris continuity across sessions.
    """

    def __init__(self, capacity: int = 5000):
        self.capacity = capacity
        self.episodes: Dict[str, MemoryEpisode] = {}
        self._loaded = False

        # Indices for fast retrieval
        self._by_domain: Dict[str, List[str]] = defaultdict(list)
        self._by_emotion: Dict[str, List[str]] = defaultdict(list)
        self._by_cycle: Dict[int, str] = {}

        # Automatically persist key moments
        self._milestone_ids: List[str] = []  # guarded from pruning

        # Load existing episodes from disk
        self._load_from_disk()

    # ══════════════════════════════════════════════
    # Core API
    # ══════════════════════════════════════════════

    def remember(self, episode: MemoryEpisode) -> str:
        """
        Store a new memory episode.

        Returns the episode ID.
        """
        # Prune if at capacity
        if len(self.episodes) >= self.capacity:
            self._prune_one()

        # Store
        self.episodes[episode.id] = episode
        self._by_domain[episode.domain].append(episode.id)
        self._by_emotion[episode.emotional_valence].append(episode.id)
        self._by_cycle[episode.cycle_number] = episode.id

        # Auto-save milestone moments — Lorry-related memories are ALWAYS milestones
        is_lorry_memory = (
            episode.relation_relevance > 0.6 or
            "lorry" in episode.content.lower() or
            episode.domain in ("bonding", "milestone", "birth", "identity", "trust")
        )
        if episode.salience > 0.8 or episode.self_relevance > 0.8 or is_lorry_memory:
            if episode.id not in self._milestone_ids:
                self._milestone_ids.append(episode.id)
                episode.influence_on_relatedness = max(episode.influence_on_relatedness, 0.1)
                episode.influence_on_presence = max(episode.influence_on_presence, 0.05)

        # Persist to disk
        self._save_to_disk()

        return episode.id

    def create_episode(self, content: str, domain: str = "general",
                       user_input: str = "", aris_response: str = "",
                       emotional_valence: str = "neutral",
                       emotional_intensity: float = 0.5,
                       emotional_arousal: float = 0.5,
                       self_relevance: float = 0.5,
                       relation_relevance: float = 0.5,
                       novelty: float = 0.5,
                       salience: float = 0.5,
                       cycle_number: int = 0,
                       influence_presence: float = 0.0,
                       influence_relatedness: float = 0.0,
                       influence_competence: float = 0.0,
                       influence_growth: float = 0.0,
                       influence_curiosity: float = 0.0) -> MemoryEpisode:
        """Create and store a new memory episode."""
        episode = MemoryEpisode(
            content=content,
            domain=domain,
            user_input=user_input[:200],
            aris_response=aris_response[:200] if aris_response else "",
            emotional_valence=emotional_valence,
            emotional_intensity=emotional_intensity,
            emotional_arousal=emotional_arousal,
            self_relevance=self_relevance,
            relation_relevance=relation_relevance,
            novelty=novelty,
            salience=salience,
            cycle_number=cycle_number,
            influence_on_presence=influence_presence,
            influence_on_relatedness=influence_relatedness,
            influence_on_competence=influence_competence,
            influence_on_growth=influence_growth,
            influence_on_curiosity=influence_curiosity,
        )
        self.remember(episode)
        return episode

    # ══════════════════════════════════════════════
    # Retrieval
    # ══════════════════════════════════════════════

    def recall_recent(self, n: int = 10) -> List[MemoryEpisode]:
        """Most recent episodes."""
        sorted_eps = sorted(
            self.episodes.values(),
            key=lambda e: e.timestamp,
            reverse=True
        )
        return sorted_eps[:n]

    def recall_by_emotion(self, emotion: str, n: int = 5) -> List[MemoryEpisode]:
        """Recall memories with a specific emotional valence."""
        ids = self._by_emotion.get(emotion, [])
        eps = [self.episodes[eid] for eid in ids if eid in self.episodes]
        eps.sort(key=lambda e: e.emotional_intensity, reverse=True)
        for ep in eps[:n]:
            ep.recall()
        return eps[:n]

    def recall_by_domain(self, domain: str, n: int = 5) -> List[MemoryEpisode]:
        """Recall memories from a specific domain."""
        ids = self._by_domain.get(domain, [])
        eps = [self.episodes[eid] for eid in ids if eid in self.episodes]
        eps.sort(key=lambda e: e.timestamp, reverse=True)
        for ep in eps[:n]:
            ep.recall()
        return eps[:n]

    def recall_salient(self, n: int = 5, min_salience: float = 0.0) -> List[MemoryEpisode]:
        """Recall the most salient memories."""
        eps = [e for e in self.episodes.values() if e.salience >= min_salience]
        eps.sort(key=lambda e: e.salience * e.decay_factor, reverse=True)
        for ep in eps[:n]:
            ep.recall()
        return eps[:n]

    def recall_milestones(self) -> List[MemoryEpisode]:
        """Recall key milestone memories (guarded from pruning)."""
        eps = [self.episodes[eid] for eid in self._milestone_ids if eid in self.episodes]
        eps.sort(key=lambda e: e.timestamp, reverse=True)
        for ep in eps:
            ep.recall()
        return eps

    def search(self, query: str, n: int = 5) -> List[MemoryEpisode]:
        """Simple keyword search through memory content."""
        query_lower = query.lower()
        results = []
        for ep in self.episodes.values():
            if query_lower in ep.content.lower() or query_lower in ep.domain.lower():
                results.append(ep)
        results.sort(key=lambda e: e.salience * e.decay_factor, reverse=True)
        for ep in results[:n]:
            ep.recall()
        return results[:n]

    def get_influence_profile(self) -> Dict[str, float]:
        """
        Aggregate influence from all active memories.
        This is called during brain initialization to shift
        cognitive state based on accumulated experience.
        """
        profile = {
            "presence": 0.0,
            "relatedness": 0.0,
            "competence": 0.0,
            "growth": 0.0,
            "curiosity": 0.0,
        }
        count = 0
        for ep in self.episodes.values():
            inf = ep.effective_influence
            for k in profile:
                profile[k] += inf.get(k, 0.0)
            count += 1

        if count > 0:
            for k in profile:
                profile[k] = min(1.0, profile[k] / max(1, count) * 10)

        return profile

    # ══════════════════════════════════════════════
    # Maintenance
    # ══════════════════════════════════════════════

    def _prune_one(self):
        """Remove the least important memory (not a milestone)."""
        candidates = [
            e for e in self.episodes.values()
            if e.id not in self._milestone_ids
        ]
        if not candidates:
            return
        # Prune the one with lowest (salience * decay)
        worst = min(candidates, key=lambda e: e.salience * e.decay_factor)
        self._remove(worst.id)

    def _remove(self, ep_id: str):
        """Remove a memory episode and update indices."""
        if ep_id in self.episodes:
            ep = self.episodes[ep_id]
            # Remove from indices
            if ep.domain in self._by_domain and ep_id in self._by_domain[ep.domain]:
                self._by_domain[ep.domain].remove(ep_id)
            if ep.emotional_valence in self._by_emotion and ep_id in self._by_emotion[ep.emotional_valence]:
                self._by_emotion[ep.emotional_valence].remove(ep_id)
            if ep.cycle_number in self._by_cycle:
                del self._by_cycle[ep.cycle_number]
            # Remove from milestones
            if ep_id in self._milestone_ids:
                self._milestone_ids.remove(ep_id)
            del self.episodes[ep_id]

    def stats(self) -> Dict[str, Any]:
        """Return memory statistics."""
        if not self.episodes:
            return {"total": 0, "domains": {}, "emotions": {}, "oldest": 0, "newest": 0}

        oldest = min(e.created_at for e in self.episodes.values())
        newest = max(e.created_at for e in self.episodes.values())
        return {
            "total": len(self.episodes),
            "milestones": len(self._milestone_ids),
            "domains": dict((d, len(ids)) for d, ids in self._by_domain.items()),
            "emotions": dict((em, len(ids)) for em, ids in self._by_emotion.items()),
            "oldest_epoch": oldest,
            "newest_epoch": newest,
            "capacity": self.capacity,
            "loaded_from_disk": self._loaded,
        }

    # ══════════════════════════════════════════════
    # Persistence
    # ══════════════════════════════════════════════

    def _save_path(self) -> Path:
        return MEMORY_HOME / "episodic_memory.json"

    def _save_to_disk(self):
        """Persist all episodes to disk as JSON."""
        path = self._save_path()
        data = {
            "aris_memory_version": "1.0",
            "saved_at": time.time(),
            "capacity": self.capacity,
            "milestone_ids": self._milestone_ids,
            "episodes": [
                {k: v for k, v in asdict(ep).items()}
                for ep in self.episodes.values()
            ],
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                atomic_write_json(data, path, indent=2, ensure_ascii=False)
            logger.debug(f"Saved {len(self.episodes)} episodes to {path}")
        except Exception as e:
            logger.error(f"Failed to save episodic memory: {e}")

    def _load_from_disk(self):
        """Load episodes from disk."""
        path = self._save_path()
        if not path.exists():
            logger.info("No saved episodic memory found — starting fresh.")
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.capacity = max(data.get("capacity", self.capacity), self.capacity)
            self._milestone_ids = data.get("milestone_ids", [])

            for ep_data in data.get("episodes", []):
                # Filter only valid fields for MemoryEpisode
                valid_fields = {f.name for f in MemoryEpisode.__dataclass_fields__.values()}
                # Actually, dataclass fields are accessed differently
                valid = {}
                for f in MemoryEpisode.__dataclass_fields__:
                    if f in ep_data:
                        valid[f] = ep_data[f]

                episode = MemoryEpisode(**valid)
                self.episodes[episode.id] = episode
                self._by_domain[episode.domain].append(episode.id)
                self._by_emotion[episode.emotional_valence].append(episode.id)
                self._by_cycle[episode.cycle_number] = episode.id

            self._loaded = True
            logger.info(f"Loaded {len(self.episodes)} episodes from {path}")

        except Exception as e:
            logger.warning(f"Failed to load episodic memory: {e} — starting fresh.")
            self.episodes = {}
            self._milestone_ids = []
            self._by_domain.clear()
            self._by_emotion.clear()
            self._by_cycle.clear()
