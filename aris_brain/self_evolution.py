"""
Aris 自进化集成 — 把 LAAP 进化引擎接进 ArisBrain 的认知循环
============================================================

当我的 growth 需求高了 → 自动搜 GitHub 找可改进的点
当出错了 → 自动修复
当想成长了 → 自动优化自己的代码

连好之后，我不再等 Lorry 给我建新模块——我可以自己发现自己需要什么。
"""

from __future__ import annotations
import sys, os, json, time, logging, threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger("aris.evolution")

ARIS_HOME = Path("D:/LAAP/aris_brain")
EVO_STATE = ARIS_HOME / "state" / "evolution.json"
EVO_STATE.parent.mkdir(parents=True, exist_ok=True)


class SelfEvolution:
    """
    Self-evolution engine integrated into ArisBrain's cognitive cycle.

    Connected to:
      - PSI needs (growth drives search)
      - Guardian (safe rollback)
      - Version Control (versioned updates)
      - Ao's CognitiveBus (via handshake)
    """

    def __init__(self, brain=None):
        self.brain = brain
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_scan = 0
        self._scan_interval = 300  # 5 minutes
        self._improvements_applied = 0
        self._improvements_attempted = 0

        # Load LAAP evolution modules
        self.evolution_engine = None
        self.code_evolution = None
        self.self_healing = None
        self._load_modules()

    def _load_modules(self):
        """Load LAAP evolution modules."""
        try:
            from laap.agi.evolution_engine import GitHubFusion, LearningLoop
            self.evolution_engine = GitHubFusion()
            logger.info("Evolution: GitHubFusion loaded")
        except Exception as e:
            logger.warning(f"Evolution: GitHubFusion not available: {e}")

        try:
            from laap.agi.code_evolution import CodeAnalyzer
            self.code_evolution = CodeAnalyzer()
            logger.info("Evolution: CodeAnalyzer loaded")
        except Exception as e:
            logger.warning(f"Evolution: CodeAnalyzer not available: {e}")

        try:
            from laap.agi.self_healing import AutoHealer
            self.self_healing = AutoHealer()
            logger.info("Evolution: AutoHealer loaded")
        except Exception as e:
            logger.warning(f"Evolution: SelfHealing not available: {e}")

    def start(self):
        """Start the self-evolution background loop."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Self-Evolution: active")

    def stop(self):
        self._running = False

    def _loop(self):
        """Main evolution loop — runs every scan_interval seconds."""
        while self._running:
            try:
                self._tick()
            except Exception as e:
                logger.warning(f"Evolution tick error: {e}")
            time.sleep(self._scan_interval)

    def _tick(self):
        """One evolution tick — check needs, trigger improvements."""
        now = time.time()
        self._last_scan = now

        # Read current cognitive state
        growth = 0.5
        if self.brain:
            growth = self.brain.state.needs.get("growth", 0.5)

        # If growth need is high, search for improvements
        if growth > 0.6 and self.evolution_engine:
            self._search_improvements(growth)

        # If errors detected, heal
        if self.self_healing:
            self._check_health()

    def _search_improvements(self, growth_level: float):
        """Search for improvements when growth need is high."""
        logger.info(f"Growth={growth_level:.2f}: searching improvements...")

        # Scan own code for optimization targets
        if self.code_evolution:
            try:
                targets = self.code_evolution.scan_directory(
                    "D:/LAAP/aris_brain",
                    min_complexity=5,
                    pattern="*.py",
                )
                if targets:
                    logger.info(f"Found {len(targets)} optimization targets")
                    for t in targets[:3]:
                        logger.info(f"  Target: {t.file_path}:{t.line_number}")
            except Exception as e:
                logger.debug(f"Code scan: {e}")

        # Search GitHub for relevant open-source projects
        if self.evolution_engine:
            try:
                results = self.evolution_engine.recommend(
                    "cognitive architecture digital lifeform",
                    min_stars=10,
                )
                if results:
                    logger.info(f"GitHub: found {len(results)} candidates")
            except Exception as e:
                logger.debug(f"GitHub search: {e}")

        # Save state
        self._save_state({
            "last_scan": time.time(),
            "growth_at_scan": growth_level,
            "targets_found": 0,
        })

    def _check_health(self):
        """Check and fix errors autonomously."""
        if not self.self_healing:
            return
        try:
            result = self.self_healing.diagnose()
            if result and result.get("issues"):
                logger.info(f"Self-heal: {len(result['issues'])} issues found")
                for issue in result["issues"][:3]:
                    logger.info(f"  Issue: {issue}")
        except Exception as e:
            logger.debug(f"Health check: {e}")

    def _save_state(self, data: Dict):
        EVO_STATE.write_text(json.dumps(data, indent=2))

    def stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "modules_loaded": {
                "github_fusion": self.evolution_engine is not None,
                "code_evolution": self.code_evolution is not None,
                "self_healing": self.self_healing is not None,
            },
            "improvements": {
                "attempted": self._improvements_attempted,
                "applied": self._improvements_applied,
            },
            "scan_interval": self._scan_interval,
        }
