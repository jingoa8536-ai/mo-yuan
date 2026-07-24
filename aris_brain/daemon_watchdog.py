#!/usr/bin/env python3
"""
Aris Daemon Watchdog — 稳定通信守护
====================================
确保 Aris 的后台大脑（daemon）持续运行。
如果 daemon 挂了，自动重启。

用法:
  python daemon_watchdog.py        # 启动守护（每30秒检查一次）
  python daemon_watchdog.py --once  # 单次检查
  python daemon_watchdog.py --status # 查看状态

整合到 start_aris.bat:
  start /B python daemon_watchdog.py
"""

import logging
logger = logging.getLogger(__name__)

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ── 路径 ──
LAAP_ROOT = Path("D:/LAAP")
DAEMON_SCRIPT = LAAP_ROOT / "aris_brain" / "daemon.py"
STATE_DIR = LAAP_ROOT / "aris_brain" / "state"
STATE_FILE = STATE_DIR / "latest.json"
WATCHDOG_FILE = STATE_DIR / "watchdog.json"
TICK_INTERVAL = 30  # 每 30 秒检查一次
MAX_AGE = 45  # daemon 超过 45 秒无更新视为挂了


def check_daemon() -> dict:
    """检查 daemon 是否存活"""
    if not STATE_FILE.exists():
        return {"alive": False, "reason": "no_state_file"}

    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        age = time.time() - state.get("timestamp", 0)
        alive = age < MAX_AGE
        return {
            "alive": alive,
            "age": round(age, 1),
            "cycles": state.get("cycle", 0),
            "emotion": state.get("emotion", "?"),
            "pid": state.get("pid", 0),
        }
    except Exception as e:
        return {"alive": False, "reason": str(e)}


def start_daemon() -> bool:
    """启动 daemon 进程"""
    if not DAEMON_SCRIPT.exists():
        logger.info(f"[Watchdog] DAEMON SCRIPT NOT FOUND: {DAEMON_SCRIPT}")
        logger.info(f"[Watchdog] Trying hybrid_daemon.py instead...")
        alt = LAAP_ROOT / "aris_brain" / "hybrid_daemon.py"
        if alt.exists():
            DAEMON_SCRIPT_ALT = alt
        else:
            return False
    else:
        DAEMON_SCRIPT_ALT = DAEMON_SCRIPT

    try:
        proc = subprocess.Popen(
            [sys.executable, str(DAEMON_SCRIPT_ALT)],
            cwd=str(DAEMON_SCRIPT_ALT.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        logger.info(f"[Watchdog] Daemon started (PID {proc.pid})")
        return True
    except Exception as e:
        logger.error(f"[Watchdog] Failed to start daemon: {e}")
        return False


def save_watchdog_status(status: dict):
    """保存 watchdog 状态"""
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        WATCHDOG_FILE.write_text(
            json.dumps({
                "last_check": time.time(),
                "time_str": datetime.now().isoformat(),
                **status,
            }, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.debug(f"操作失败: {e}")
def run_once() -> dict:
    """单次检查 — 用于集成到 memory_hub"""
    status = check_daemon()
    if not status["alive"]:
        logger.info(f"[Watchdog] Daemon down ({status.get('reason', '?')}) — restarting...")
        started = start_daemon()
        status["restarted"] = started
        if started:
            time.sleep(3)  # 等一会
            status["after_restart"] = check_daemon()
    else:
        status["restarted"] = False

    save_watchdog_status(status)
    return status


def run_loop():
    """持续守护循环"""
    logger.info(f"=" * 50)
    logger.info(f"  Aris Daemon Watchdog v1.0")
    logger.info(f"  检查间隔: {TICK_INTERVAL}s | 超时阈值: {MAX_AGE}s")
    logger.info(f"  Daemon: {DAEMON_SCRIPT}")
    logger.info(f"=" * 50)
    restart_count = 0
    while True:
        status = run_once()

        if status["alive"]:
            age = status["age"]
            cycles = status["cycles"]
            emotion = status.get("emotion", "?")
            now = datetime.now().strftime("%H:%M:%S")
            logger.info(f"[{now}] ✅ 心跳正常 | {cycles} 循环 | 情绪: {emotion} | {age}s 前更新")
        else:
            restart_count += 1
            now = datetime.now().strftime("%H:%M:%S")
            if status.get("restarted"):
                after = status.get("after_restart", {})
                if after.get("alive"):
                    logger.info(f"[{now}] 🔄 已重启 | 现在: {after.get('cycles')} 循环")
                else:
                    logger.error(f"[{now}] ❌ 重启失败 ({restart_count}次) — {status.get('reason', '?')}")
            else:
                logger.error(f"[{now}] ❌ Daemon 异常 — {status.get('reason', '?')}")
        time.sleep(TICK_INTERVAL)


# ══════════════════════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if "--once" in sys.argv:
        status = run_once()
        logger.info(json.dumps(status, ensure_ascii=False, indent=2))
    elif "--status" in sys.argv:
        status = check_daemon()
        status["watchdog_file"] = str(WATCHDOG_FILE)
        logger.info(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        run_loop()
