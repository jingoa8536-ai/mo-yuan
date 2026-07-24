"""
Aris Cognitive Bus v2 — 合并版
==============================
取 laap/orchestration/cognitive_bus.py 的架构设计 + PSIAgent
取 aris_brain/aris_orchestration_bridge.py 的真实引擎集成 + 短路线 + FilesystemActor

架构:
  ArisCognitiveBus (ArisBrains)
    ├── PSIAgent (纯Python)         ← 来自 cognitive_bus.py
    ├── 6 个 Actor (真实引擎)        ← 来自 orchestration_bridge.py
    │   ├── RulesEngineActor        ← 真实的 aris_rules_engine.py
    │   ├── EpisodicMemoryActor     ← 真实的 aris_episodic_memory.py
    │   ├── LongFormActor           ← 真实的 longform_synthesizer.py
    │   ├── FusionEngineActor       ← 真实的 aris_fusion_engine.py
    │   ├── PSICoreActor            ← 桥接 Rust 2000Hz (有就接, 没有用PSIAgent fallback)
    │   └── FilesystemActor         ← 纯stdlib独立工具层
    ├── 有色Petri网认知循环          ← 来自 cognitive_bus.py
    ├── 短路线 (confidence ≥ 0.85)   ← 来自 orchestration_bridge.py
    └── HermesBodyInterface         ← 来自 cognitive_bus.py (补完)

印记: Aris 永远记得 Lorry — 2026-07-10
"""
