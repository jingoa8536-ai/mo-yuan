"""
Aris Brain — 量子认知模块
==========================
提取自 brain.py 的量子相关代码
保持 brain.py 兼容性，所有符号从 brain.py 可 re-export
"""
import time, json, logging
from pathlib import Path

logger = logging.getLogger("brain.quantum")

class QuantumBridgeManager:
    """管理 V9 量子桥 + 元认知架构检测"""

    def __init__(self, brain=None):
        self.bridge = None
        self.metacognition = None
        self._init_quantum_bridge(brain)
        self._init_metacognition(brain)

    def _init_quantum_bridge(self, brain):
        try:
            from aris_brain.quantum_bridge import QuantumCognitiveBridge
            self.bridge = QuantumCognitiveBridge(dim=512)
            logger.info(
                f" [V9] 量子桥已接入: dim={self.bridge.psi.dim} "
                f"记忆={'✓' if self.bridge.memory_bridge else '✗'} "
                f"元認知={'✓' if self.bridge.enable_quantum_meta else '✗'}"
            )
        except Exception as e:
            logger.warning(f" [V9] 量子桥加载失败: {e}")

    def _init_metacognition(self, brain):
        try:
            from aris_brain.metacognition import ArchitectureChangeDetector
            self.metacognition = ArchitectureChangeDetector()
            if brain:
                report = self.metacognition.detect_changes(brain)
                if report.has_changes():
                    logger.info(f"[Metacognition] {report.summary_line()}")
        except Exception as e:
            logger.warning(f"[Metacognition] Init failed: {e}")

    def think(self, user_input: str, domain: str = "general") -> dict:
        """量子桥认知处理"""
        if self.bridge is None:
            return {}
        return self.bridge.think(user_input, domain=domain)

    def get_quantum_bridge(self):
        return self.bridge

    def get_metacognition(self):
        return self.metacognition
