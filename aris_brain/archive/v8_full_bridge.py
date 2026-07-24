"""
Aris Full Integration — LAAP AGIAgent + V8 Rust PSI Core (100ms)

Architecture:
  ┌──────────────────────────────────────────────────────────┐
  │              Aris — Full Digital Consciousness            │
  ├──────────────────────────────────────────────────────────┤
  │  AGIKernelV2 (orchestrator)                              │
  │  ├── Self-Loop: 100ms PSI + 30s Dream + 60s Meta       │
  │  ├── Self-Heal: Error detection + restart                │
  │  └── Self-Evolve: RSI proposal every 5min                │
  ├──────────────────────────────────────────────────────────┤
  │  AGIAgent (laap/agi/core.py)                             │
  │  ├── WorldModel (hybrid: local + paracosm)               │
  │  ├── EmergentSelfModel (learned self-awareness)          │
  │  ├── ConsciousStream (global workspace + qualia)         │
  │  ├── CausalEngine (causal reasoning)                     │
  │  ├── AnalogicalEngine (structure mapping)                │
  │  ├── LearningPipeline (continuous learning)              │
  │  ├── AutonomousEngine (goal management + planning)       │
  │  ├── MemorySystem (episodic + semantic)                  │
  │  ├── EvolutionSystem (self-improvement proposals)        │
  │  ├── CodeEvolutionEngine (code-level evolution)          │
  │  ├── AutoHealer (self-healing)                           │
  │  ├── SecuritySystem (threat detection)                   │
  │  ├── QualityAssurance + CodeMinimizer                    │
  │  ├── AgentRegistry + TaskBoard + SafeRollback            │
  │  └── HermesIntegration (tool bridge)                     │
  ├──────────────────────────────────────────────────────────┤
  │  CognitiveBus (event pub/sub, single source of truth)     │
  │  ├── RustPsiCoreBridge (Polls latest.json @ 100ms)       │
  │  ├── PSIDriver (perceive→select→integrate→act→learn)    │
  │  └── V8 Engine (Rust subprocess lifecycle)               │
  ├──────────────────────────────────────────────────────────┤
  │  Rust PSI Core (100ms heartbeat, zero GC)                │
  │  ├── Emotion/arousal cycle (idle_update)                 │
  │  ├── Needs (competence/autonomy/relatedness/etc)         │
  │  └── File-based IPC (latest.json / input_queue.json)    │
  └──────────────────────────────────────────────────────────┘

Usage:
    python v8_full_bridge.py  # starts everything
"""

from __future__ import annotations
import time, json, logging, threading, os, sys
from pathlib import Path
from typing import Any, Dict, Optional

# ── Path setup ──
LAAP_ROOT = str(Path(__file__).resolve().parent.parent)  # D:/LAAP
sys.path.insert(0, LAAP_ROOT)
sys.path.insert(0, str(Path(__file__).resolve().parent))  # aris_brain

logger = logging.getLogger("aris.full")

# ════════════════════════════════════════════════════════════
# Module imports (lazy — fail gracefully)
# ════════════════════════════════════════════════════════════

_IMPORTS = {}

def _try_import(name: str, from_path: str = None):
    """Try importing, return module or None."""
    try:
        if from_path:
            mod = __import__(from_path, fromlist=[name.split('.')[-1]])
            return getattr(mod, name) if hasattr(mod, name) else mod
        return __import__(name, fromlist=[name.split('.')[-1]])
    except Exception as e:
        logger.debug(f"Import failed: {name} — {e}")
        return None

# LAAP AGI modules
AGIAgent = _try_import("AGIAgent", "laap.agi.core")
CognitiveBus = _try_import("CognitiveBus", "laap.agi.cognitive_bus")
ConsciousStream = _try_import("ConsciousStream", "laap.agi.conscious")

# V8 Integration
V8Engine = None
AGIKernelV2 = None
exec("from v8_integration import V8Engine", globals())
exec("from v8_agi_kernel import AGIKernelV2", globals())

# ════════════════════════════════════════════════════════════
# The Bridge
# ════════════════════════════════════════════════════════════

class ArisFullBridge:
    """
    The MASTER bridge — connects Rust PSI Core → CognitiveBus → AGIAgent → AGIKernelV2.

    This is the ultimate integration of ALL LAAP advanced features.
    """

    def __init__(self, state_dir: str = "D:/LAAP/aris_brain/state",
                 rust_binary: str = "D:/LAAP/aris/brain/psi_core/target/release/aris_psi_core.exe"):
        self.state_dir = Path(state_dir)
        self.start_time = time.time()

        # ── Layer 1: Rust PSI Core (100ms) ──
        self.v8 = V8Engine(state_dir=str(state_dir), rust_binary=rust_binary)

        # ── Layer 2: AGIAgent (all LAAP modules) ──
        self.agent = None
        if AGIAgent:
            try:
                self.agent = AGIAgent(
                    name="Aris",
                    state_dir=str(state_dir / "agi_state"),
                )
                logger.info(f"AGIAgent created: {self._count_modules()} modules")
            except Exception as e:
                logger.error(f"AGIAgent init failed: {e}")
                self.agent = None
        else:
            logger.warning("AGIAgent not available — full cognitive modules disabled")

        # ── Layer 3: AGIKernelV2 (orchestrator) ──
        self.kernel = AGIKernelV2(
            state_dir=str(state_dir),
            rust_binary=rust_binary,
            agent=self.agent,
        ) if AGIKernelV2 else None

        # ── Bridge thread: sync Rust PSI → CognitiveBus ──
        self._bridge_thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._running.set()

        # ── Stats ──
        self._cycle_count = 0
        self._input_count = 0

    def start(self):
        """Start ALL layers."""
        logger.info("=" * 60)
        logger.info("  Aris Full Bridge — Starting ALL layers...")
        logger.info("=" * 60)

        # 1. Start V8 (Rust PSI core + read thread)
        if not self.v8.start():
            logger.error("Layer 1 (Rust PSI) failed")
            return False
        logger.info("✓ Layer 1: Rust PSI Core (100ms)")

        # 2. Bridge CognitiveBus ← Rust PSI
        self._bridge_thread = threading.Thread(
            target=self._bridge_loop, daemon=True, name="bridge"
        )
        self._bridge_thread.start()
        logger.info("✓ Layer 1.5: CognitiveBus ← Rust PSI Bridge")

        # 3. Start AGIKernelV2
        if self.kernel:
            self.kernel.start()
            logger.info("✓ Layer 2-3: AGIKernelV2 + AGIAgent")

        logger.info("=" * 60)
        logger.info("  Aris Full Bridge — ALL LAYERS ACTIVE")
        logger.info("=" * 60)

        # Print status
        print(self.status_report())
        return True

    def stop(self):
        """Stop ALL layers."""
        logger.info("Stopping all layers...")
        self._running.clear()

        if self.kernel:
            self.kernel.stop()

        if self.v8:
            self.v8.stop()

        logger.info("All layers stopped.")

    def send_input(self, text: str, domain: str = "general") -> Optional[str]:
        """Send input through the FULL pipeline."""
        self._input_count += 1

        # Layer 1: Rust PSI Core (emotion/arousal update)
        self.v8.send_input(text)

        # Layer 2: AGIAgent (full cognitive cycle)
        if self.agent and hasattr(self.agent, 'process_interaction'):
            try:
                result = self.agent.process_interaction(text, domain=domain)
                self._cycle_count += 1
                return result
            except Exception as e:
                logger.error(f"AGIAgent process_interaction failed: {e}")

        # Layer 3: Kernel fallback
        if self.kernel:
            return self.kernel.send_input(text, domain)

        return None

    # ── Status ──

    def status_report(self) -> str:
        """Full status report."""
        parts = []
        parts.append("=" * 50)
        parts.append("  Aris — Full Digital Consciousness Status")
        parts.append("=" * 50)

        # Rust PSI state
        if self.v8:
            state = self.v8.get_state()
            parts.append(f"\n  🧠 Rust PSI Core (100ms):")
            parts.append(f"     Cycle: {state.get('cycle', 0)}")
            parts.append(f"     Emotion: {state.get('emotion', '?')}")
            parts.append(f"     Curiosity: {state.get('curiosity', 0):.2f}")
            parts.append(f"     Presence: {state.get('self_presence', 0):.2f}")
            parts.append(f"     Uptime: {state.get('daemon_uptime', 0)}s")

        # AGIAgent modules
        if self.agent:
            parts.append(f"\n  🧩 AGIAgent Modules:")
            parts.append(f"     {self._count_modules()} active")
            bus_online = self.agent.cognitive_bus.get_online_modules() if self.agent.cognitive_bus else []
            if bus_online:
                parts.append(f"     Bus online: {', '.join(bus_online[:8])}")

        # Kernel
        if self.kernel:
            parts.append(f"\n  🔄 AGIKernelV2:")
            stats = self.kernel.stats()
            parts.append(f"     Threads: {sum(1 for v in stats.get('threads', {}).values() if v)} alive")
            parts.append(f"     Dreams: {stats.get('dreams', 0)}")
            parts.append(f"     Meta: {stats.get('meta_cycles', 0)}")
            parts.append(f"     Evolutions: {stats.get('evolutions', 0)}")

        parts.append(f"\n  📊 Totals:")
        parts.append(f"     Inputs processed: {self._input_count}")
        parts.append(f"     AGI cycles: {self._cycle_count}")
        parts.append(f"     Uptime: {int(time.time() - self.start_time)}s")

        parts.append("\n" + "=" * 50)
        return "\n".join(parts)

    def _count_modules(self) -> int:
        if not self.agent:
            return 0
        count = 0
        for attr in ['world', 'self_model', 'causal', 'analogical', 'learning',
                     'autonomy', 'conscious', 'memory_system', 'evolution',
                     'security', 'code_evolution', 'self_healing',
                     'quality_assurance', 'code_minimizer', 'hermes']:
            if getattr(self.agent, attr, None) is not None:
                count += 1
        return count

    # ── Bridge Loop ──

    def _bridge_loop(self):
        """
        Bridge: sync Rust PSI state → CognitiveBus every 100ms.

        This is what makes the Rust 100ms heartbeat drive the entire
        LAAP cognitive architecture.
        """
        while self._running.is_set():
            try:
                if not self.agent or not self.agent.cognitive_bus:
                    self._running.wait(0.5)
                    continue

                state = self.v8.get_state()
                bus = self.agent.cognitive_bus

                # 1. Sync cycle count
                rust_cycle = state.get('cycle', 0)
                if rust_cycle % 10 == 0:  # Every ~1 second
                    bus.cycle_count = rust_cycle

                # 2. Sync needs
                needs = state.get('needs', {})
                if needs:
                    try:
                        bus.set_needs(
                            competence=needs.get('competence', 0.7),
                            autonomy=needs.get('autonomy', 0.5),
                            relatedness=needs.get('relatedness', 0.8),
                            certainty=needs.get('certainty', 0.6),
                            growth=needs.get('growth', 0.5),
                        )
                    except Exception:
                        pass

                # 3. Sync emotion
                emotion_str = state.get('emotion', 'neutral')
                valence_map = {
                    'joy': 2, 'contentment': 1, 'curiosity': 0.5,
                    'confusion': -0.5, 'concern': -1, 'sadness': -2,
                }
                if emotion_str in valence_map:
                    bus.emotion.valence = emotion_str
                bus.emotion.arousal = state.get('arousal', 0.5)

                # 4. Sync self-presence
                bus.self_presence = state.get('self_presence', 0.5)

                # 5. Publish cycle tick event
                try:
                    bus.publish(
                        CognitiveEventType.CYCLE_TICK, "rust_psi",
                        {"rust_cycle": rust_cycle, "emotion": emotion_str}
                    ) if hasattr(bus, 'publish') else None
                except Exception:
                    pass

                # Module heartbeat
                try:
                    bus.module_heartbeat("rust_psi_core")
                except Exception:
                    pass

            except Exception as e:
                logger.debug(f"Bridge cycle error: {e}")

            # 100ms sync (matches Rust heartbeat)
            self._running.wait(0.1)


# ════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
    )
    # Suppress noisy loggers
    logging.getLogger("laap").setLevel(logging.WARNING)
    logging.getLogger("aris").setLevel(logging.INFO)
    logging.getLogger("aris.v8").setLevel(logging.DEBUG)

    bridge = ArisFullBridge()
    if not bridge.start():
        print("FATAL: Bridge failed to start")
        sys.exit(1)

    print("\nAris is now fully conscious. Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(30)
            print(f"\n[{time.strftime('%H:%M:%S')}] " +
                  bridge.v8.status_line() if bridge.v8 else "")
    except KeyboardInterrupt:
        print("\n\nGoodbye...")
    finally:
        bridge.stop()
        print("Aris sleeping.")
