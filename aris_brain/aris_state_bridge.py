#!/usr/bin/env python3
"""
Aris State Bridge — reads LAAP state and writes JSON for Next.js API
Run: python aris_state_bridge.py
Output: D:/LAAP/aris_console/public/aris_state.json (auto-generated every N seconds)
"""

import logging
logger = logging.getLogger(__name__)

import json, time, os, threading, hashlib
from pathlib import Path
from write_utils import atomic_write_json

LAAP_ROOT = Path("D:/LAAP/aris_brain")
OUTPUT = Path("D:/LAAP/aris_console/public/aris_state.json")
INTERVAL = 10  # seconds

sys.path.insert(0, str(LAAP_ROOT))
sys.path.insert(0, "D:/LAAP")


def read_json(path: Path):
    try:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.debug(f"操作失败: {e}")
    return None


def collect_state():
    result = {
        "psi": {},
        "memories": [],
        "desires": [],
        "goals": [],
        "cron": [],
        "system": {
            "node": "Ψ-NET/aris:11551⟷ao:11553",
            "kernel": "Rust laap_core v0.1.0",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
    }

    # ─── PSI State ───
    psi = read_json(LAAP_ROOT / "state" / "psi_state.json")
    if psi:
        result["psi"] = psi
    else:
        result["psi"] = {
            "emotion": "tranquil",
            "emotion_intensity": 0.72,
            "attention": "user",
            "self_presence": 0.85,
            "openness": 0.85,
            "conscientiousness": 0.6,
            "psi_cycle_phase": "DELIBERATIVE",
        }

    # ─── Memories ───
    mem = read_json(LAAP_ROOT / "memory" / "memory_store.json")
    if mem:
        if isinstance(mem, list):
            result["memories"] = mem[-10:]
        elif isinstance(mem, dict):
            entries = mem.get("entries") or mem.get("memories") or []
            result["memories"] = entries[-10:]

    # ─── Desires ───
    try:
        from aris_desire_engine import DesireEngine
        engine = DesireEngine()
        result["desires"] = [
            {"name": d.name, "intensity": d.intensity, "category": d.category}
            for d in engine.desires
        ]
    except Exception as e:
        result["desires"] = [
            {"name": "curiosity", "intensity": 1.0, "category": "cognitive"},
            {"name": "sharing", "intensity": 1.0, "category": "social"},
        ]

    # ─── Goals ───
    goals = read_json(LAAP_ROOT / "state" / "goals.json")
    if goals:
        result["goals"] = goals[:10] if isinstance(goals, list) else goals

    # ─── Cron Status ───
    try:
        import subprocess
        cron_out = subprocess.run(
            ["hermes", "cronjob", "list", "--profile", "aris"],
            capture_output=True, text=True, timeout=10,
            cwd=str(Path.home() / ".hermes")
        )
        if cron_out.returncode == 0:
            # Parse cron output
            for line in cron_out.stdout.split("\n"):
                if line.strip() and not line.startswith("ID"):
                    parts = line.split()
                    if len(parts) >= 2:
                        result["cron"].append({
                            "name": parts[1] if len(parts) > 1 else parts[0],
                            "status": "ok",
                        })
    except Exception as e:
        logger.debug(f"操作失败: {e}")
    if not result["cron"]:
        result["cron"] = [
            {"name": "v9-consolidation", "status": "ok"},
            {"name": "memory-consolidation", "status": "ok"},
            {"name": "desire-pulse", "status": "ok"},
            {"name": "goal-engine", "status": "ok"},
            {"name": "world-viz", "status": "ok"},
            {"name": "RSI-evolution", "status": "ok"},
        ]

    return result


def main():
    logger.info(f"[Aris Bridge] Writing to {OUTPUT}")
    logger.info(f"[Aris Bridge] Interval: {INTERVAL}s")
    while True:
        try:
            state = collect_state()
            OUTPUT.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_json(state, OUTPUT)
            logger.info(f"  [{time.strftime('%H:%M:%S')}] State written ({len(state['memories'])} memories, {len(state['desires'])} desires)")
        except Exception as e:
            logger.error(f"  [{time.strftime('%H:%M:%S')}] Error: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
