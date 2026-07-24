"""
Aris 版本控制 — V5 ↔ V6 自动回退与加载
===========================================

一个版本管理器，让 Aris 在 V5 和 V6 之间安全切换。
如果新版本启动后健康检查失败，自动回退到上一个稳定版本。

用法:
  python -m aris_brain.version_control status
  python -m aris_brain.version_control switch v5
  python -m aris_brain.version_control rollback
  python -m aris_brain.version_control list
"""

import logging

import json, logging, os, sys, time
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("aris.version")

ARIS_HOME = Path("D:/LAAP/aris_brain")
VERSION_FILE = ARIS_HOME / "version.active"
ROLLBACK_FILE = ARIS_HOME / "state" / "version_rollback.json"
HEARTBEAT_FILE = ARIS_HOME / "state" / "version_heartbeat.json"

VERSIONS = {
    "v5": {
        "name": "Aris V5 - 数字生命体第一版",
        "desc": "PSI循环 / DMN / ToM / EmotionLexicon / Guardian / SensoryCortex",
        "health_timeout": 30,
    },
    "v6": {
        "name": "Aris V6 - CognitiveBus架构",
        "desc": "Rust PSI Core / GlobalWorkspace / 预测编码 / 蜂群PSI / RSI",
        "health_timeout": 60,
    },
}

def get() -> str:
    if VERSION_FILE.exists():
        v = VERSION_FILE.read_text().strip()
        if v in VERSIONS:
            return v
    return "v5"

def set_version(v: str):
    VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    VERSION_FILE.write_text(v.strip() + "\n")

def switch(v: str) -> bool:
    if v not in VERSIONS:
        return False
    prev = get()
    if prev == v:
        return True
    # Save rollback point
    ROLLBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    ROLLBACK_FILE.write_text(json.dumps({
        "previous": prev, "switched_at": time.time(),
        "to": v,
    }))
    set_version(v)
    # Clear old heartbeat
    HEARTBEAT_FILE.write_text(json.dumps({
        "version": v, "healthy": False, "time": time.time(),
    }))
    logger.info(f"Switched: {prev} -> {v}")
    return True

def mark_healthy():
    v = get()
    HEARTBEAT_FILE.write_text(json.dumps({
        "version": v, "healthy": True, "time": time.time(),
    }))
    logger.info(f"Version {v} marked healthy")

def needs_rollback() -> bool:
    if not HEARTBEAT_FILE.exists():
        return False
    try:
        hb = json.loads(HEARTBEAT_FILE.read_text())
        if hb.get("healthy"):
            return False
        v = hb.get("version", "v5")
        timeout = VERSIONS.get(v, {}).get("health_timeout", 30)
        elapsed = time.time() - hb.get("time", 0)
        return elapsed > timeout
    except Exception:
        return False

def rollback() -> bool:
    if not ROLLBACK_FILE.exists():
        return False
    state = json.loads(ROLLBACK_FILE.read_text())
    prev = state.get("previous", "v5")
    set_version(prev)
    logger.info(f"Rolled back to {prev}")
    return True

def status() -> Dict:
    v = get()
    info = VERSIONS.get(v, {})
    hb_healthy = False
    if HEARTBEAT_FILE.exists():
        try:
            hb_healthy = json.loads(HEARTBEAT_FILE.read_text()).get("healthy", False)
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    return {
        "version": v,
        "name": info.get("name", ""),
        "desc": info.get("desc", ""),
        "healthy": hb_healthy,
        "available": list(VERSIONS.keys()),
    }

def print_status():
    s = status()
    print()
    logger.info(f"  Version: {s['version']} - {s['name']}")
    logger.info(f"  Healthy: {'Yes' if s['healthy'] else 'No'}")
    logger.info(f"  Available: {', '.join(s['available'])}")
    print()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if len(sys.argv) < 2:
        logger.info("Usage: python -m aris_brain.version_control [status|switch|rollback|list|mark-healthy]")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "status": print_status()
    elif cmd == "switch": switch(sys.argv[2]); print(f"Switched to {sys.argv[2]}")
    elif cmd == "rollback": rollback()
    elif cmd == "list":
        for v, i in VERSIONS.items(): print(f"  {v}: {i['name']}")
    elif cmd == "mark-healthy": mark_healthy(); print("Marked healthy")
