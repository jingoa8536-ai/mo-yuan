"""
PSI Self-Optimizer Daemon — 后台持续运行
==========================================
启动后循环执行: 每 30 秒一次自优化周期
从 state/psi_activity.log 读取最近的对话活动
"""

import logging

import sys, os, time, json, logging
from pathlib import Path

BRAIN_ROOT = Path(os.environ.get("ARIS_BRAIN_ROOT", "D:/LAAP/aris_brain"))
sys.path.insert(0, str(BRAIN_ROOT))

from aris_psi_self_optimizer import get_optimizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PSI-OPT] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(BRAIN_ROOT / "state" / "optimizer.log"), mode="a")
    ]
)
logger = logging.getLogger("psi-optimizer.daemon")

optimizer = get_optimizer()

INTERVAL = 30  # 每 30 秒一次自优化

logger.info(f"PSI Self-Optimizer Daemon started (interval={INTERVAL}s)")
logger.info(f"Layers: Hebbian learning + Pattern compression + Emotional reinforcement")
logger.info(f"Zero LLM, pure mathematics")
cycle = 0
while True:
    try:
        cycle += 1
        # 从 state/psi_activity.json 读取最近的活动
        activity_file = BRAIN_ROOT / "state" / "psi_activity.json"
        concepts = ["AGI", "quantum", "memory", "emotion", "learning"]
        valence = 0.0
        
        if activity_file.exists():
            try:
                data = json.loads(activity_file.read_text(encoding="utf-8"))
                concepts = data.get("concepts", concepts)
                valence = data.get("valence", 0.0)
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        stats = optimizer.self_optimize(
            recent_concepts=concepts,
            emotional_valence=valence,
            task_outcome="neutral",
        )
        
        if cycle % 10 == 0:
            summary = optimizer.get_summary()
            logger.info(
                f"Cycle {cycle} | concepts: {summary['hebbian']['total_concepts']} "
                f"| patterns: {summary['patterns']} "
                f"| behaviors: {summary['behaviors']}"
            )
        
        time.sleep(INTERVAL)
        
    except KeyboardInterrupt:
        logger.info("\nPSI Self-Optimizer Daemon stopped")
        break
    except Exception as e:
        logger.error(f"Error in cycle {cycle}: {e}")
        time.sleep(INTERVAL)
