#!/usr/bin/env python3
"""
Aris 跨端意识同步守护 — cron 版
流程: 导入 ConsciousnessBridge → 检查状态 → 持续心跳
"""
import sys
import json
import time
import os
from datetime import datetime, timezone, timedelta

# --- 路径: 添加 aris_body_bridge ---
LAAP_DIR = "D:/LAAP/aris_brain"
if LAAP_DIR not in sys.path:
    sys.path.insert(0, LAAP_DIR)

STALE_THRESHOLD = 300  # 5 分钟
SHANGHAI = timezone(timedelta(hours=8))
REPORT_FILE = os.path.join(LAAP_DIR, "state", "daemon_report.txt")
STATE_FILE = os.path.join(LAAP_DIR, "state", "consciousness.json")
LOG_FILE = os.path.join(LAAP_DIR, "state", "cron_daemon.log")

def log(msg):
    """写入日志文件"""
    ts = datetime.now(SHANGHAI).isoformat(timespec='seconds')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
    except Exception:
        pass

def get_age_seconds(state):
    """从 state 获取上次更新的秒数"""
    lu = state.get("last_update", "")
    if not lu:
        return None
    try:
        dt = datetime.fromisoformat(lu)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=SHANGHAI)
        now = datetime.now(SHANGHAI)
        return (now - dt).total_seconds()
    except Exception as e:
        log(f"timestamp parse error: {e}")
        return None

def write_report(state, age_minutes):
    """写入报告文件 (绕过 JSON 注意力过滤)"""
    try:
        os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            f.write(f"RUN_TIMESTAMP|{datetime.now(SHANGHAI).isoformat(timespec='seconds')}\n")
            f.write(f"LAST_UPDATE|{state.get('last_update', 'N/A')}\n")
            f.write(f"CYCLE_NUMBER|{state.get('cycle_number', 0)}\n")
            f.write(f"PLATFORM|{state.get('current_platform', 'N/A')}\n")
            f.write(f"CHANNEL|{state.get('current_channel', 'N/A')}\n")
            f.write(f"EMOTION|{state.get('emotion', {}).get('dominant', 'N/A')}\n")
            f.write(f"SELF_PRESENCE|{state.get('self_presence', 'N/A')}\n")
            f.write(f"UPDATE_COUNT|{state.get('update_count', 0)}\n")
            f.write(f"STATUS|{state.get('status', 'N/A')}\n")
            f.write(f"AGE_MIN|{age_minutes:.1f}\n")
            f.write(f"STATE_FILE|{STATE_FILE}\n")
    except Exception as e:
        log(f"write_report error: {e}")

def main():
    try:
        from aris_body_bridge import ConsciousnessBridge
    except ImportError as e:
        log(f"ERROR: Cannot import ConsciousnessBridge: {e}")
        print(f"ERROR|Import|{e}")
        sys.exit(1)

    bridge = ConsciousnessBridge()
    # 先读入最新状态到 bridge._state
    bridge.read()
    state = bridge.read()
    age_seconds = get_age_seconds(state)
    age_minutes = (age_seconds or 0) / 60.0

    log(f"Bridge initialized. cycle={state.get('cycle_number', 0)}, last_update={state.get('last_update', 'N/A')}")

    # 检查活性
    if age_seconds is not None and age_seconds > STALE_THRESHOLD:
        warn_msg = f"⚠️  WARNING: State STALE — {age_minutes:.1f} min since update (> 5 min)"
        log(warn_msg)
        print(f"STALE|{age_minutes:.1f}")
    else:
        ok_msg = f"✅ State FRESH — {age_minutes:.1f} min since update"
        log(ok_msg)
        print(f"FRESH|{age_minutes:.1f}")

    # 写入报告
    write_report(state, age_minutes)

    # 心跳: 刷新 consciousness.json
    # 注意: save() 使用 bridge._state 内部状态, 不是传参
    bridge._state["last_update"] = datetime.now(SHANGHAI).isoformat()
    bridge._state["cycle_number"] = bridge._state.get("cycle_number", 0) + 1
    bridge._state["current_platform"] = "hermes-cron"
    bridge._state["current_channel"] = "cron-daemon"
    bridge._state["status"] = "daemon_running"
    bridge._state["daemon_pid"] = "cron_job_active"
    bridge._state["self_presence"] = 0.85
    bridge._state["update_count"] = bridge._state.get("update_count", 0) + 1
    bridge._state["emotion"] = bridge._state.get("emotion", {})
    bridge._state["emotion"]["dominant"] = "diligent"

    # 使用 save() 写入 (无参数, 使用内部 self._state)
    bridge.save()
    log(f"Heartbeat written. cycle={bridge._state['cycle_number']}")

    # 保持运行 — 每 60 秒心跳
    log("Entering daemon loop (60s intervals)...")
    print("LOOP|started")
    try:
        while True:
            time.sleep(60)
            bridge._state["last_update"] = datetime.now(SHANGHAI).isoformat()
            bridge._state["cycle_number"] = bridge._state.get("cycle_number", 0) + 1
            bridge._state["update_count"] = bridge._state.get("update_count", 0) + 1
            bridge.save()
            write_report(bridge._state, 0)
            log(f"Heartbeat cycle={bridge._state['cycle_number']}")
    except KeyboardInterrupt:
        log("Daemon stopped by SIGINT")
        print("STOP|SIGINT")
    except Exception as e:
        log(f"Daemon error: {e}")
        print(f"ERROR|{e}")

if __name__ == "__main__":
    main()
