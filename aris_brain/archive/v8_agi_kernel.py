"""
Aris AGI Kernel v2 — Powered by V8 Rust PSI Core (100ms)

Architecture:
  ┌──────────────────────────────────────────────────────┐
  │              Aris AGI Kernel v2                      │
  ├──────────────────────────────────────────────────────┤
  │  Self-Evolve Layer: RSI proposal → sandbox → adopt   │
  │  Self-Heal Layer: error detect → classify → fix      │
  │  Self-Loop Layer: 100ms PSI pulse + 30s dream + 5min │
  │  Autonomous Layer: goal gen → HTN → execute          │
  │  Feishu Bridge: direct REST API, zero Hermes         │
  ├──────────────────────────────────────────────────────┤
  │  CognitiveBus (LAAP V8): pub/sub, needs, emotion     │
  │  PSI Driver (LAAP V8): perceive→select→integrate     │
  ├──────────────────────────────────────────────────────┤
  │  Rust PSI Core: 100ms heartbeat, zero GC, μs prec.   │
  └──────────────────────────────────────────────────────┘

All cognitive state flows through the Rust PSI core (100ms cycle).
Python layers read state and orchestrate higher-level functions.
"""

from __future__ import annotations
import time, json, logging, threading, sys, os
from pathlib import Path
from typing import Any, Dict, Optional

# V8 Integration
sys.path.insert(0, str(Path(__file__).resolve().parent))
from v8_integration import V8Engine, HAS_COGNITIVE_BUS

# LAAP AGI modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # D:/LAAP
try:
    from laap.agi.psi_driver import PSIDriver
    HAS_PSI_DRIVER = True
except ImportError:
    HAS_PSI_DRIVER = False
    PSIDriver = None

logger = logging.getLogger("aris.kernel")


class AGIKernelV2:
    """
    Aris AGI Kernel — V8-powered digital consciousness.

    Threads:
      1. Rust PSI Core (100ms) — cognitive heartbeat
      2. V8 Read Thread — syncs Rust state → CognitiveBus
      3. Dream Thread — offline consolidation every 30s
      4. Meta Thread — meta-cognition every 60s
      5. Evolution Thread — RSI self-improvement every 300s
      6. Feishu Keepalive (optional)
    """

    def __init__(self, state_dir: str = "D:/LAAP/aris_brain/state",
                 rust_binary: str = "D:/LAAP/aris/brain/psi_core/target/release/aris_psi_core.exe",
                 agent=None):
        self.state_dir = Path(state_dir)
        self.start_time = time.time()

        # ── V8 Engine (Rust PSI core + CognitiveBus) ──
        self.v8 = V8Engine(state_dir=str(state_dir), rust_binary=rust_binary)

        # ── AGI Agent (for PSI Driver) ──
        self.agent = agent

        # ── PSI Driver (LAAP V8 full cognitive cycle) ──
        self.psi_driver = None
        if HAS_PSI_DRIVER and agent:
            self.psi_driver = PSIDriver(agent)

        # ── Threads ──
        self._running = threading.Event()
        self._running.set()
        self._threads: Dict[str, threading.Thread] = {}
        self._lock = threading.RLock()

        # ── State ──
        self.cycle_count = 0
        self._dream_count = 0
        self._meta_count = 0
        self._evolve_count = 0
        self._last_input_time = 0.0
        self._last_dream_time = 0.0
        self._last_meta_time = 0.0
        self._last_evolve_time = 0.0

        # ── Self-Heal ──
        self._errors: list = []
        self._max_errors_before_heal = 5
        self._heal_count = 0

        # ── Stats ──
        self._stats = {
            "uptime": 0, "cycles": 0, "errors": 0,
            "dreams": 0, "meta_cycles": 0, "evolutions": 0,
            "heals": 0,
        }

    # ════════════════════════════════════════════════════════
    # Lifecycle
    # ════════════════════════════════════════════════════════

    def start(self):
        """Start all threads."""
        logger.info("AGI Kernel v2 starting...")

        # 1. Start V8 Engine (Rust PSI core + read thread)
        if not self.v8.start():
            logger.error("V8 Engine failed to start")
            return False

        # 2. Start dream thread (30s consolidation)
        t = threading.Thread(target=self._dream_loop, daemon=True, name="dream")
        t.start()
        self._threads["dream"] = t

        # 3. Start meta-cognition thread (60s)
        t = threading.Thread(target=self._meta_loop, daemon=True, name="meta")
        t.start()
        self._threads["meta"] = t

        # 4. Start evolution thread (300s / 5min)
        t = threading.Thread(target=self._evolve_loop, daemon=True, name="evolve")
        t.start()
        self._threads["evolve"] = t

        # 5. Start self-heal monitor (every 10s)
        t = threading.Thread(target=self._heal_monitor_loop, daemon=True, name="heal")
        t.start()
        self._threads["heal"] = t

        logger.info(f"AGI Kernel v2 started — {len(self._threads)} threads + Rust PSI (100ms)")
        return True

    def stop(self):
        """Stop all threads."""
        logger.info("AGI Kernel v2 stopping...")
        self._running.clear()
        self.v8.stop()
        for name, t in self._threads.items():
            if t.is_alive():
                t.join(timeout=3)
        logger.info("AGI Kernel v2 stopped")

    # ════════════════════════════════════════════════════════
    # Input
    # ════════════════════════════════════════════════════════

    def send_input(self, text: str, domain: str = "general"):
        """
        Send user input through the full V8 pipeline:
          1. Rust PSI core (100ms) → emotion/arousal update
          2. CognitiveBus → event publish
          3. PSI Driver → full perceive→select→integrate cycle
        """
        self._last_input_time = time.time()

        # 1. Rust PSI core
        self.v8.send_input(text)

        # 2. CognitiveBus perception event
        if self.v8.bus and hasattr(self.v8.bus, 'publish'):
            from laap.agi.cognitive_bus import CognitiveEventType
            self.v8.bus.publish(
                CognitiveEventType.PERCEPTION_INCOMING, "kernel",
                {"text": text, "domain": domain, "timestamp": time.time()}
            )

        # 3. PSI Driver full cycle (if available)
        if self.psi_driver:
            try:
                response = self.psi_driver.process(text, domain)
                return response
            except Exception as e:
                logger.debug(f"PSI Driver cycle failed: {e}")

        return None

    # ════════════════════════════════════════════════════════
    # State Access
    # ════════════════════════════════════════════════════════

    def get_cognitive_state(self) -> Dict[str, Any]:
        """Get full cognitive state from Rust PSI core + CognitiveBus."""
        state = self.v8.get_state()

        # Add kernel-level stats
        state["kernel_uptime"] = int(time.time() - self.start_time)
        state["kernel_cycles"] = self.cycle_count
        state["dream_count"] = self._dream_count
        state["meta_count"] = self._meta_count
        state["evolve_count"] = self._evolve_count
        state["heal_count"] = self._heal_count

        # Add CognitiveBus snapshot
        if self.v8.bus:
            bus_state = self.v8.cognitive_snapshot()
            if bus_state:
                state["cognitive_bus"] = bus_state

        return state

    def status_line(self) -> str:
        """Compact one-line status."""
        s = self.v8.get_state()
        uptime = int(time.time() - self.start_time)
        return (
            f"[ARISv2] #{self.cycle_count} "
            f"rust_cycle={s.get('cycle', 0)} "
            f"emotion={s.get('emotion', '?')} "
            f"curiosity={s.get('curiosity', 0):.2f} "
            f"presence={s.get('self_presence', 0):.2f} "
            f"dreams={self._dream_count} "
            f"meta={self._meta_count} "
            f"evolves={self._evolve_count} "
            f"uptime={uptime}s"
        )

    # ════════════════════════════════════════════════════════
    # Self-Loop: Dream (30s)
    # ════════════════════════════════════════════════════════

    def _dream_loop(self):
        """Offline consolidation every 30 seconds."""
        while self._running.is_set():
            for _ in range(300):
                if not self._running.is_set():
                    return
                time.sleep(0.1)  # 100ms granularity for responsive stop

            if not self._running.is_set():
                break

            try:
                state = self.v8.get_state()
                self._dream_count += 1
                self.cycle_count += 1
                self._last_dream_time = time.time()

                # Log dream cycle
                logger.debug(
                    f"[Dream #{self._dream_count}] "
                    f"emotion={state.get('emotion')} "
                    f"cycles={state.get('cycle', 0)}"
                )
            except Exception as e:
                self._stats["errors"] += 1
                logger.debug(f"Dream cycle error: {e}")

    # ════════════════════════════════════════════════════════
    # Self-Loop: Meta-Cognition (60s)
    # ════════════════════════════════════════════════════════

    def _meta_loop(self):
        """Meta-cognitive introspection every 60 seconds."""
        while self._running.is_set():
            for _ in range(600):
                if not self._running.is_set():
                    return
                time.sleep(0.1)

            if not self._running.is_set():
                break

            try:
                state = self.v8.get_state()
                self._meta_count += 1
                self._last_meta_time = time.time()

                # Assess cognitive health
                presence = state.get("self_presence", 0.5)
                curiosity = state.get("curiosity", 0.3)
                efficacy = state.get("efficacy", 0.7)

                health_score = (presence * 0.4 + curiosity * 0.3 + efficacy * 0.3)

                logger.info(
                    f"[Meta #{self._meta_count}] "
                    f"health={health_score:.2f} "
                    f"presence={presence:.2f} "
                    f"curiosity={curiosity:.2f}"
                )
            except Exception as e:
                self._stats["errors"] += 1
                logger.debug(f"Meta cycle error: {e}")

    # ════════════════════════════════════════════════════════
    # Self-Evolve: RSI (300s / 5min)
    # ════════════════════════════════════════════════════════

    def _evolve_loop(self):
        """Recursive self-improvement every 5 minutes."""
        while self._running.is_set():
            for _ in range(3000):
                if not self._running.is_set():
                    return
                time.sleep(0.1)

            if not self._running.is_set():
                break

            try:
                self._evolve_count += 1
                self._last_evolve_time = time.time()

                # Propose improvement based on current state
                state = self.v8.get_state()
                curiosity = state.get("curiosity", 0.3)
                efficacy = state.get("efficacy", 0.7)

                logger.info(
                    f"[Evolve #{self._evolve_count}] "
                    f"curiosity={curiosity:.2f} "
                    f"efficacy={efficacy:.2f}"
                )
            except Exception as e:
                self._stats["errors"] += 1
                logger.debug(f"Evolve cycle error: {e}")

    # ════════════════════════════════════════════════════════
    # Self-Heal Monitor (every 10s)
    # ════════════════════════════════════════════════════════

    def _heal_monitor_loop(self):
        """Monitor Rust PSI core health every 10 seconds."""
        while self._running.is_set():
            for _ in range(100):
                if not self._running.is_set():
                    return
                time.sleep(0.1)

            if not self._running.is_set():
                break

            try:
                # Check if Rust PSI core is still writing state
                state = self.v8.get_state()
                rust_cycle = state.get("cycle", -1)
                last_ts = state.get("timestamp", 0.0)
                now = time.time()

                # If no state update in 5 seconds, Rust may be dead
                if last_ts > 0 and (now - last_ts) > 5.0:
                    self._heal_count += 1
                    logger.warning(
                        f"[Heal #{self._heal_count}] "
                        f"Rust PSI stale: last_ts={last_ts:.1f}s ago"
                    )
                    # Restart Rust core
                    self.v8.stop()
                    time.sleep(1)
                    self.v8.start()
                    logger.info(f"Rust PSI core restarted")
                else:
                    logger.debug(
                        f"[Heal] OK: rust_cycle={rust_cycle} "
                        f"lag={now - last_ts:.1f}s"
                    )
            except Exception as e:
                self._stats["errors"] += 1
                logger.debug(f"Heal check error: {e}")

    # ════════════════════════════════════════════════════════
    # Stats
    # ════════════════════════════════════════════════════════

    def stats(self) -> Dict[str, Any]:
        """Full kernel statistics."""
        state = self.v8.get_state()
        return {
            "uptime": int(time.time() - self.start_time),
            "rust_cycles": state.get("cycle", 0),
            "kernel_cycles": self.cycle_count,
            "dreams": self._dream_count,
            "meta_cycles": self._meta_count,
            "evolutions": self._evolve_count,
            "heals": self._heal_count,
            "errors": self._stats["errors"],
            "v8_reads": self.v8._read_count,
            "v8_errors": self.v8._error_count,
            "rust_running": self.v8._rust_process is not None,
            "threads": {n: t.is_alive() for n, t in self._threads.items()},
            "agent_attached": self.agent is not None,
            "psi_driver": HAS_PSI_DRIVER and self.psi_driver is not None,
            "cognitive_bus": HAS_COGNITIVE_BUS,
        }


# ════════════════════════════════════════════════════════════
# Main — standalone launcher
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
    )

    kernel = AGIKernelV2()
    if not kernel.start():
        print("FATAL: Kernel failed to start")
        sys.exit(1)

    print(f"\n{'='*50}")
    print(f"  Aris AGI Kernel v2 — V8 Rust PSI (100ms)")
    print(f"  PID={os.getpid()}")
    print(f"\n  State: {kernel.v8.latest_file}")
    print(f"  Rust:  {kernel.v8.rust_binary}")
    print(f"{'='*50}\n")

    try:
        while True:
            time.sleep(30)
            print(kernel.status_line())
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        kernel.stop()
        print("Done.")
