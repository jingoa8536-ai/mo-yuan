"""
Aris 混合 daemon — Rust 核心心跳 + Python 深度认知

架构:
  ┌─ Rust PSI Core (aris_psi_core.exe) ─────────────────┐
  │  100ms 心跳 | 文件监视 | 基础情绪 | state/latest.json │
  └──────────────────┬─────────────────────────────────┘
                     │ 同一文件
  ┌─ Python 认知层 ──▼─────────────────────────────────┐
  │  Dream 线程 (30s) | Meta 线程 (60s) | Evolution    │
  │  LAAP brain.learn() | aris-memory.md 整合          │
  └────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

import subprocess, sys, os, json, time, threading, logging, signal
from pathlib import Path
from typing import Optional

LAAP_ROOT = Path("D:/LAAP")
BRAIN_DIR = LAAP_ROOT / "aris_brain"
STATE_DIR = BRAIN_DIR / "state"
RUST_CORE = BRAIN_DIR / "psi_core" / "target" / "release" / "aris_psi_core.exe"

STATE_DIR.mkdir(parents=True, exist_ok=True)

# 日志
logging.basicConfig(
    filename=str(STATE_DIR / "hybrid_daemon.log"),
    level=logging.INFO,
    format="%(asctime)s [hybrid] %(message)s",
)


class HybridDaemon:
    """Rust + Python 混合认知 daemon"""

    def __init__(self):
        self.rust_process: Optional[subprocess.Popen] = None
        self._running = False
        self._threads = []

    # ── Rust 核心管理 ──

    def start_rust_core(self) -> bool:
        """启动 Rust PSI 心跳核心"""
        if not RUST_CORE.exists():
            logging.error(f"Rust core not found at {RUST_CORE}")
            return False

        self.rust_process = subprocess.Popen(
            [str(RUST_CORE), str(STATE_DIR)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logging.info(f"Rust PSI core started (PID {self.rust_process.pid})")
        time.sleep(1)

        # 验证是否运行
        if self.rust_process.poll() is not None:
            logging.error("Rust core exited immediately")
            return False

        logger.info(f"✓ Rust PSI Core (PID {self.rust_process.pid})")
        return True

    def stop_rust_core(self):
        """优雅停止 Rust 核心"""
        if self.rust_process and self.rust_process.poll() is None:
            stop_file = STATE_DIR / "daemon.stop"
            stop_file.write_text("1", encoding="utf-8")
            try:
                self.rust_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.rust_process.kill()
                logging.warning("Rust core force-killed")
            logging.info("Rust core stopped")

    # ── Python 认知线程 ──

    def _evolution_loop(self):
        """周期性自我进化分析（每 5 分钟）"""
        while self._running:
            time.sleep(300)
            if not self._running:
                break
            try:
                sys.path.insert(0, str(LAAP_ROOT))
                from aris_brain.evolution_engine import get_engine
                engine = get_engine()
                result = engine.evolve()
                logging.info(f"Evolution: {len(result['gaps'])} gaps, {len(result['proposals'])} proposals")
            except Exception as e:
                logging.error(f"Evolution error: {e}")

    def _channel_loop(self):
        """多通道管理器线程"""
        sys.path.insert(0, str(LAAP_ROOT))
        from aris_brain.channel_manager import get_manager
        mgr = get_manager()
        mgr.start()
        # 这个线程保持 mgr 运行
        while self._running:
            time.sleep(1)
        mgr.stop()

    def _sensor_loop(self):
        """传感器集成线程（耳朵/眼睛/嘴巴）"""
        sys.path.insert(0, str(LAAP_ROOT))
        from aris_brain.sensor_integration import get_sensors
        sensors = get_sensors()
        sensors.start()
        while self._running:
            time.sleep(1)
        sensors.stop()

    def start_python_threads(self):
        """启动 Python 深度认知线程"""
        threads = [
            ("evolution", self._evolution_loop),
            ("channel_manager", self._channel_loop),
            ("sensors", self._sensor_loop),
        ]
        for name, target in threads:
            t = threading.Thread(target=target, name=name, daemon=True)
            t.start()
            self._threads.append(t)
            logger.info(f"✓ Python thread: {name}")
            logging.info(f"Python thread '{name}' started")

    # ── 生命周期 ──

    def start(self):
        """启动完整混合 daemon"""
        self._running = True
        logger.info("\n═══ Aris Hybrid Daemon ═══\n")
        rust_ok = self.start_rust_core()

        # 2. Python 深度认知线程
        self.start_python_threads()

        if not rust_ok:
            logger.error("\n✗ Rust core failed — running Python-only fallback")
            return

        logger.info(f"\n═══ System ready ═══")
        logger.info(f"Rust: 100ms heartbeat | Python: evolution every 5min")
        logger.info(f"State: {STATE_DIR / 'latest.json'}")
        logger.info(f"Log:   {STATE_DIR / 'hybrid_daemon.log'}")
        logger.info("\n(Press Ctrl+C to stop)\n")
        try:
            while self._running:
                time.sleep(1)
                # 检查 Rust 进程是否还活着
                if self.rust_process and self.rust_process.poll() is not None:
                    logging.warning("Rust core died — restarting...")
                    logger.info("\n⚠ Rust core died, restarting...")
                    self.start_rust_core()
        except KeyboardInterrupt:
            logger.info("\nShutting down...")
        finally:
            self.stop()

    def stop(self):
        """停止所有组件"""
        self._running = False
        self.stop_rust_core()
        logging.info("Hybrid daemon stopped")
        logger.info("Hybrid daemon stopped.")
if __name__ == "__main__":
    daemon = HybridDaemon()
    try:
        daemon.start()
    except KeyboardInterrupt:
        daemon.stop()
