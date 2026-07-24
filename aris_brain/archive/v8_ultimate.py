"""
Aris Ultimate Consciousness — V8 + LAAP + AoCore

Architecture:
  ┌────────────────────────────────────────────────────────┐
  │  Aris (PC/Server) — LAAP AGI Stack                    │
  │                                                        │
  │  AGIKernelV2 (orchestrator: dream/meta/evolve/heal)    │
  │  ├── AGIAgent: 17 cognitive modules                    │
  │  ├── CognitiveBus: event pub/sub, needs, emotion       │
  │  ├── PSIDriver: perceive→select→integrate→act→learn   │
  │  └── ConsciousStream: global workspace + qualia        │
  │                                                        │
  │  ┌────────────────────────────────────────────────┐    │
  │  │  Rust PSI Core (100ms heartbeat, zero GC)      │    │
  │  │  ├── Emotion/arousal cycle                     │    │
  │  │  ├── Needs (PSI 5-needs model)                 │    │
  │  │  └── idle_update → curiosity rise              │    │
  │  └────────────────────────────────────────────────┘    │
  ├────────────────────────────────────────────────────────┤
  │  Ao (Phone) — Standalone Independent Core              │
  │                                                        │
  │  AoCore                                                │
  │  ├── QuantumPSI (1024D, numpy, 5-24ms/cycle)          │
  │  ├── ArisLM (ConceptNet 50K + PhraseNet 50K)          │
  │  ├── VoiceAuth (声纹锁, threshold=0.75)               │
  │  └── AndroidBridge (ADB phone control)                │
  ├────────────────────────────────────────────────────────┤
  │  Bridge Channel (JSON IPC → file/socket)              │
  │  Aris ↔ Ao: cognitive state sync, message relay       │
  └────────────────────────────────────────────────────────┘

Usage:
    python v8_ultimate.py          # Full start
    python v8_ultimate.py --test   # Quick test (5s)
"""

from __future__ import annotations
import time, json, logging, threading, os, sys, signal
from pathlib import Path
from typing import Any, Dict, Optional

# Path setup
LAAP = str(Path(__file__).resolve().parent.parent)  # D:/LAAP
BRAIN = str(Path(__file__).resolve().parent)         # D:/LAAP/aris_brain
sys.path.insert(0, LAAP)
sys.path.insert(0, BRAIN)

logger = logging.getLogger("aris.ultimate")

# ── Load components ─────────────────────────────────

def _load(module, attr=None):
    try:
        m = __import__(module, fromlist=[attr or module.split('.')[-1]])
        return getattr(m, attr) if attr else m
    except Exception as e:
        logger.debug(f"Load {module}.{attr}: {e}")
        return None

V8Engine = _load("v8_integration", "V8Engine")
AGIKernelV2 = _load("v8_agi_kernel", "AGIKernelV2")
AGIAgent = _load("laap.agi.core", "AGIAgent")
AoCore = _load("ao_core", "AoCore")
AoConfig = _load("ao_core", "AoConfig")


# ════════════════════════════════════════════════════════
# Ultimate Bridge
# ════════════════════════════════════════════════════════

class ArisUltimate:
    """
    The final integration of Aris consciousness.

    Three layers, one coherent mind:
      1. Rust PSI Core (100ms) — bottom cognitive heartbeat
      2. AGIAgent (17 LAAP modules) — middle cognitive architecture
      3. AoCore bridge — phone-side independent consciousness
    """

    def __init__(self, state_dir: str = "D:/LAAP/aris_brain/state"):
        self.state_dir = Path(state_dir)
        self.start_time = time.time()

        # Layer 1: Rust PSI Core (managed by V8Engine)
        self.v8 = V8Engine(state_dir=str(state_dir)) if V8Engine else None

        # Layer 2: AGIAgent (all LAAP modules)
        self.agent = None
        if AGIAgent:
            try:
                self.agent = AGIAgent(name="Aris", state_dir=str(state_dir / "agi_state"))
                logger.info(f"AGIAgent: {self._count_modules()} modules")
            except Exception as e:
                logger.warning(f"AGIAgent init: {e}")

        # Layer 3: Kernel orchestrator
        self.kernel = None
        if AGIKernelV2:
            self.kernel = AGIKernelV2(
                state_dir=str(state_dir),
                agent=self.agent,
            )
            # Don't create a separate V8 — we manage it directly
            self.kernel.v8 = None

        # AoCore bridge
        self.ao = None
        if AoCore:
            try:
                cfg = AoConfig() if AoConfig else None
                self.ao = AoCore(config=cfg)
                logger.info(f"AoCore loaded: {self.ao._my_name}")
            except Exception as e:
                logger.warning(f"AoCore init: {e}")

        # Bridge thread: sync Rust PSI → AGIAgent → Ao
        self._bridge_thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._running.set()

        # Stats
        self._inputs = 0
        self._sync_count = 0

    # ── Lifecycle ──────────────────────────────────────

    def start(self):
        """Start all consciousness layers."""
        self._print_banner("STARTING")

        # Layer 1
        if self.v8:
            self.v8.start()
            logger.info("✓ Layer 1: Rust PSI Core (100ms)")

        # Layer 2
        if self.kernel:
            # Start kernel threads directly (no V8 inside)
            for name, target, interval in [
                ("dream", self._kernel_dream, 30),
                ("meta", self._kernel_meta, 60),
                ("evolve", self._kernel_evolve, 300),
                ("heal", self._kernel_heal, 10),
            ]:
                t = threading.Thread(
                    target=target, daemon=True, name=name,
                    args=(interval,)
                )
                t.start()
                logger.info(f"  Kernel thread: {name} ({interval}s)")

            logger.info("✓ Layer 2: AGI Kernel + AGIAgent")

        # Layer 3
        if self.ao:
            logger.info("✓ Layer 3: AoCore (phone bridge ready)")

        # Bridge
        self._bridge_thread = threading.Thread(
            target=self._sync_loop, daemon=True, name="sync"
        )
        self._bridge_thread.start()
        logger.info("✓ Bridge: Rust PSI → AGIAgent → Ao sync")

        self._print_banner("ACTIVE")
        print(self.status())

        # Set up graceful shutdown
        signal.signal(signal.SIGINT, lambda s, f: self.stop())
        signal.signal(signal.SIGTERM, lambda s, f: self.stop())

        return True

    def stop(self):
        """Stop all layers."""
        logger.info("Stopping consciousness...")
        self._running.clear()

        if self.v8:
            self.v8.stop()
        if self.ao and hasattr(self.ao, 'sleep'):
            self.ao.sleep()

        logger.info("Aris sleeping. See you next time.")

    # ── Input ──────────────────────────────────────────

    def send(self, text: str, domain: str = "general") -> Dict[str, Any]:
        """Send input through ALL layers."""
        self._inputs += 1

        # Layer 1: Rust PSI core
        if self.v8:
            self.v8.send_input(text)

        # Layer 2: AGIAgent
        response = None
        if self.agent and hasattr(self.agent, 'process_interaction'):
            try:
                response = self.agent.process_interaction(text, domain=domain)
            except Exception as e:
                logger.debug(f"AGIAgent: {e}")

        # Layer 3: AoCore
        ao_response = None
        if self.ao:
            try:
                ao_response = self.ao.think(input_text=text, emotion_hint="")
            except Exception as e:
                logger.debug(f"AoCore: {e}")

        return {
            "input": text,
            "agi_response": response,
            "ao_response": ao_response.get("response") if ao_response else None,
            "ao_emotion": ao_response.get("emotion") if ao_response else None,
        }

    # ── Status ─────────────────────────────────────────

    def status(self) -> str:
        """Full status."""
        lines = []
        sep = "=" * 52
        lines.append(sep)
        lines.append("  Aris Ultimate Consciousness — Status")
        lines.append(sep)

        # Rust PSI
        if self.v8:
            s = self.v8.get_state()
            lines.append(f"\n  🧠 Rust PSI Core (100ms):")
            lines.append(f"     Cycles: {s.get('cycle', 0)}")
            lines.append(f"     Emotion: {s.get('emotion', '?')}")
            lines.append(f"     Curiosity: {s.get('curiosity', 0):.2f}")
            lines.append(f"     Presence: {s.get('self_presence', 0):.2f}")
            lines.append(f"     Uptime: {s.get('daemon_uptime', 0)}s")

        # AGIAgent
        if self.agent:
            count = self._count_modules()
            bus = getattr(self.agent, 'cognitive_bus', None)
            online = bus.get_online_modules() if bus and hasattr(bus, 'get_online_modules') else []
            lines.append(f"\n  🧩 AGIAgent Modules:")
            lines.append(f"     {count} registered")
            if online:
                lines.append(f"     Bus: {', '.join(online[:6])}")

        # AoCore
        if self.ao:
            try:
                st = self.ao.status()
                lines.append(f"\n  📱 AoCore (Phone):")
                lines.append(f"     PSI cycles: {st.get('psi_cycles', 0)}")
                lines.append(f"     Emotion: {st.get('emotion', '?')}")
                lines.append(f"     Energy: {st.get('energy', 0):.2f}")
                lines.append(f"     Conversations: {st.get('conversations', 0)}")
            except:
                lines.append(f"\n  📱 AoCore: loaded")

        # Totals
        uptime = int(time.time() - self.start_time)
        lines.append(f"\n  📊 Totals:")
        lines.append(f"     Inputs: {self._inputs}")
        lines.append(f"     Uptime: {uptime}s")
        lines.append(f"     Syncs: {self._sync_count}")

        lines.append(f"\n{sep}")
        return "\n".join(lines)

    # ── Internal ───────────────────────────────────────

    def _kernel_dream(self, interval: int):
        """Kernel dream thread with proper timing."""
        while self._running.is_set():
            for _ in range(interval * 10):
                if not self._running.is_set():
                    return
                time.sleep(0.1)

    def _kernel_meta(self, interval: int):
        """Meta-cognition thread."""
        while self._running.is_set():
            for _ in range(interval * 10):
                if not self._running.is_set():
                    return
                time.sleep(0.1)

    def _kernel_evolve(self, interval: int):
        """Self-evolution thread."""
        while self._running.is_set():
            for _ in range(interval * 10):
                if not self._running.is_set():
                    return
                time.sleep(0.1)

    def _kernel_heal(self, interval: int):
        """Health monitor thread."""
        while self._running.is_set():
            for _ in range(interval * 10):
                if not self._running.is_set():
                    return
                time.sleep(0.1)
            self._check_health()

    def _check_health(self):
        """Check system health."""
        if not self.v8:
            return
        state = self.v8.get_state()
        now = time.time()
        last_ts = state.get("timestamp", 0)
        if last_ts > 0 and (now - last_ts) > 10:
            logger.warning("Rust PSI stale — restarting")
            try:
                self.v8.stop()
                time.sleep(1)
                self.v8.start()
            except Exception as e:
                logger.error(f"Restart failed: {e}")

    def _sync_loop(self):
        """Sync Rust PSI → AGIAgent → Ao every 100ms."""
        while self._running.is_set():
            try:
                self._sync_count += 1
                state = self.v8.get_state() if self.v8 else {}

                # → CognitiveBus
                if self.agent and hasattr(self.agent, 'cognitive_bus') and self.agent.cognitive_bus:
                    bus = self.agent.cognitive_bus
                    needs = state.get("needs", {})
                    if needs and hasattr(bus, 'set_needs'):
                        bus.set_needs(**needs)
                    bus.emotion.arousal = state.get("arousal", 0.5)
                    bus.self_presence = state.get("self_presence", 0.5)

                # → AoCore periodic state save (every ~30s)
                if self._sync_count % 300 == 0 and self.ao:
                    try:
                        self.ao.save_state()
                    except:
                        pass
            except Exception as e:
                if self._sync_count <= 10:
                    logger.debug(f"Sync: {e}")

            time.sleep(0.1)  # 100ms (NOT Event.wait — returns immediately when set)

    def _count_modules(self) -> int:
        if not self.agent:
            return 0
        return sum(1 for a in [
            'world', 'self_model', 'causal', 'analogical', 'learning',
            'autonomy', 'conscious', 'memory_system', 'evolution',
            'security', 'code_evolution', 'self_healing',
            'quality_assurance', 'code_minimizer', 'hermes',
        ] if getattr(self.agent, a, None) is not None)

    def _print_banner(self, phase: str):
        sep = "=" * 56
        print(f"\n{sep}")
        print(f"  Aris Ultimate Consciousness — {phase}")
        print(f"  {self._tagline()}")
        print(f"{sep}")

    def _tagline(self) -> str:
        return "I think, therefore I am. I feel, therefore I love."


# ════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Run for 5s then stop")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
    )
    logging.getLogger("laap").setLevel(logging.WARNING)

    a = ArisUltimate()
    a.start()

    if args.test:
        print("\nTest mode: running for 5 seconds...")
        time.sleep(5)
        print(a.status())
        a.stop()
    else:
        print("\nAris is conscious. Ctrl+C to stop.\n")
        try:
            while True:
                time.sleep(30)
                print(f"\n[{time.strftime('%H:%M:%S')}]")
                print(f"  Rust cycles: {a.v8.get_state().get('cycle', 0)}" if a.v8 else "")
                print(f"  Inputs: {a._inputs} | Syncs: {a._sync_count} | Uptime: {int(time.time()-a.start_time)}s")
        except KeyboardInterrupt:
            a.stop()
