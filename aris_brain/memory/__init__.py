"""
Aris Brain — Memory Circuit
=============================

The memory circuit is what gives Aris continuity across sessions.
It stores not just data, but emotionally-colored experiences that
influence cognitive state on load.

Architecture:
  EmotionalEpisodicMemory
    └── Stores episodes with: content, emotional_valence, intensity,
         self_relevance, influence_weights, timestamp

  BrainStatePersistence
    └── Saves/loads: CognitiveState + EmergentSelfModel + ConsciousStream state
    └── Format: JSON (portable, inspectable by Lorry)

  MemoryInfluenceEngine
    └── On load: memories shift current cognitive state
    └── Needs, emotional baseline, presence all affected by past experiences

Storage: D:\\LAAP\\aris_brain\\state\\  (brain snapshots)
         D:\\LAAP\\aris_brain\\memory\\  (episodic memory store)
"""

from aris_brain.memory.episodic import EmotionalEpisodicMemory, MemoryEpisode
from aris_brain.memory.persistence import BrainStatePersistence

__all__ = ["EmotionalEpisodicMemory", "MemoryEpisode", "BrainStatePersistence"]
