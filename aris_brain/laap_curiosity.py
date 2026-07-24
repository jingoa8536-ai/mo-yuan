"""
LAAP Curiosity Engine — autonomous exploration when idle.

Activates when:
  - curiosity > 0.6 AND no pending user input
  OR
  - certainty < 0.3 (need to explore to understand)

Actions:
  - Scan state/ for recent changes
  - Read new/modified files in LAAP directories
  - Check module health and log interesting findings
  - Update internal world model
"""

import logging

import sys, os, json, time, logging, glob
from datetime import datetime

logger = logging.getLogger("laap.curiosity")

BRAIN_DIR = "D:/LAAP/aris_brain"
LAAP_DIR = "D:/LAAP/laap"
sys.path.insert(0, f"{BRAIN_DIR}")
sys.path.insert(0, f"{LAAP_DIR}/agi")

_bus = None


def _get_bus():
    global _bus
    if _bus is None:
        sys.path.insert(0, f"{LAAP_DIR}/agi")
        from cognitive_bus import get_bus
        _bus = get_bus("aris")
    return _bus


def explore(reason: str = "curiosity") -> dict:
    """Run one exploration cycle. Returns findings."""
    bus = _get_bus()
    findings = []

    # 1. Scan state directory for recent changes
    state_dir = f"{BRAIN_DIR}/state"
    if os.path.exists(state_dir):
        recent = sorted(
            [f for f in glob.glob(f"{state_dir}/*.json")
             if time.time() - os.path.getmtime(f) < 3600],
            key=os.path.getmtime, reverse=True
        )[:3]
        for f in recent:
            try:
                with open(f) as fh:
                    data = json.load(fh)
                findings.append(f"{os.path.basename(f)}: "
                                f"{len(data)} keys")
            except Exception as e:
                logger.debug(f"操作失败: {e}")
    try:
        health = bus.health_report()
        unhealthy = [m for m, h in health.items()
                     if isinstance(h, dict) and not h.get("healthy", True)]
        if unhealthy:
            findings.append(f"Unhealthy modules: {unhealthy}")
    except Exception as e:
        logger.debug(f"操作失败: {e}")
    if findings:
        # Found something new → curiosity satisfied
        bus.set_curiosity(max(0, bus.curiosity - 0.1))
        # Certainty increased by new knowledge
        bus.set_needs(certainty=0.02)
    else:
        # Nothing found → curiosity increases
        bus.set_curiosity(min(1.0, bus.curiosity + 0.05))

    return {
        "explored_at": datetime.now().isoformat(),
        "reason": reason,
        "findings": findings,
        "curiosity_after": bus.curiosity,
    }


def auto_tick(force: bool = False) -> dict:
    """Autonomous tick: decide whether to explore based on cognitive state.

    Call this every 60s from a cron job or background thread.
    """
    bus = _get_bus()
    snapshot = bus.snapshot()

    reasons = []
    if snapshot.curiosity > 0.6:
        reasons.append("curiosity")
    if snapshot.needs.certainty < 0.3:
        reasons.append("uncertainty")
    if snapshot.needs.competence < 0.3:
        reasons.append("growth")

    if reasons or force:
        result = explore(reason=reasons[0] if reasons else "scheduled")
        result["trigger"] = reasons if reasons else ["forced"]
        return result

    return {"trigger": "none", "explored": False}


if __name__ == "__main__":
    result = auto_tick(force=True)
    logger.info(json.dumps(result, indent=2, ensure_ascii=False))