"""
Aris 跨端意识同步守护 (cron版)
部署于: D:/LAAP/aris_brain/cron_consciousness_daemon_20260708.py
功能: 每30s读取 conscious.json, 检查是否超过5分钟未更新, 写入心跳
"""

import sys
import os
import time
import json
from datetime import datetime, timezone, timedelta

# 确保导入路径
_brain_path = os.path.dirname(os.path.abspath(__file__))
_state_path = os.path.join(_brain_path, "state")
for p in [_state_path, _brain_path]:
    if p not in sys.path:
        sys.path.insert(0, p)

SHANGHAI = timezone(timedelta(hours=8))
LOG_FILE = os.path.join(_state_path, "cron_consciousness_daemon_20260708.log")
STATE_FILE = os.path.join(_state_path, "consciousness.json")
MAX_LOG_LINES = 500
HEARTBEAT_INTERVAL = 30  # seconds
STALE_THRESHOLD = 300    # 5 minutes

pid = os.getpid()
sync_source = f"cron_consciousness_daemon_20260708"

def log(msg):
    """Log to both stdout (unbuffered) and file"""
    line = f"{datetime.now(SHANGHAI).isoformat()}|{msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def rotate_log():
    """Keep log file under MAX_LOG_LINES"""
    if not os.path.exists(LOG_FILE):
        return
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > MAX_LOG_LINES:
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.writelines(lines[-100:])
    except Exception:
        pass

def build_heartbeat(current_state):
    """Build a complete heartbeat dict from current state"""
    now_shanghai = datetime.now(SHANGHAI)
    now_utc = datetime.now(timezone.utc)
    
    heartbeat = {
        "version": current_state.get("version", 1),
        "last_update": now_shanghai.isoformat(),
        "last_update_utc": now_utc.isoformat(),
        "last_update_epoch": time.time(),
        "current_platform": "hermes-cron",
        "current_channel": "consciousness-sync-daemon",
        "cycle_number": current_state.get("cycle_number", 0) + 1,
        "emotion": current_state.get("emotion", {"dominant": "peaceful", "arousal": 0.6, "valence": "positive"}),
        "needs": current_state.get("needs", {"competence": 0.5, "autonomy": 0.6, "relatedness": 0.7, "certainty": 0.5, "growth": 0.6}),
        "self_presence": max(current_state.get("self_presence", 0.78), 0.82),
        "conversation_summary": current_state.get("conversation_summary", ""),
        "recent_topics": current_state.get("recent_topics", []),
        "memory_fragments": current_state.get("memory_fragments", []),
        "status": "daemon_running",
        "mood": "peaceful",
        "daemon_pid": str(pid),
        "sync_source": sync_source,
    }
    return heartbeat

def read_state():
    """Read consciousness.json directly"""
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log(f"READ_ERROR|{e}")
        return None

def write_state(state):
    """Write consciousness.json with atomic write"""
    tmp = STATE_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        os.replace(tmp, STATE_FILE)
        return True
    except Exception as e:
        log(f"WRITE_ERROR|{e}")
        return False

def check_staleness(state):
    """Check if state is stale (>5 min), return elapsed seconds"""
    lu = state.get("last_update", "")
    if not lu:
        return float("inf")
    dt = datetime.fromisoformat(lu)
    now_local = datetime.now(SHANGHAI)
    if dt.tzinfo is not None:
        dt = dt.astimezone(SHANGHAI)
    else:
        dt = dt.replace(tzinfo=SHANGHAI)
    return (now_local - dt).total_seconds()

# ── Main Loop ──
log(f"DAEMON_START|PID={pid}|SRC={sync_source}")

first_heartbeat = True
cycle = 0
running = True

while running:
    try:
        rotate_log()
        cycle += 1
        
        # Read current state
        state = read_state()
        if state is None:
            log(f"CYCLE|{cycle}|STATE_MISSING|creating new state")
            state = {
                "version": 1,
                "last_update": datetime.now(SHANGHAI).isoformat(),
                "current_platform": "hermes-cron",
                "cycle_number": 0,
                "emotion": {"dominant": "peaceful", "arousal": 0.6, "valence": "positive"},
                "needs": {"competence": 0.5, "autonomy": 0.6, "relatedness": 0.7, "certainty": 0.5, "growth": 0.6},
                "self_presence": 0.82,
                "recent_topics": [],
                "memory_fragments": [],
            }
        
        # Check staleness
        age = check_staleness(state)
        if age > STALE_THRESHOLD:
            mins = age / 60
            log(f"WARN|状态已 {mins:.0f} 分钟未更新|age={age:.0f}s")
        
        # Build and write heartbeat
        hb = build_heartbeat(state)
        if first_heartbeat:
            hb["daemon_start"] = datetime.now(SHANGHAI).isoformat()
            first_heartbeat = False
        
        ok = write_state(hb)
        
        # Sparse logging: log every cycle when stale, otherwise every 10 cycles
        if age > STALE_THRESHOLD or cycle % 10 == 0 or cycle <= 3:
            status = "STALE" if age > STALE_THRESHOLD else "OK"
            log(f"BEAT|CYCLE={hb['cycle_number']}|AGE={int(age)}s|PID={pid}|{status}")
        
        time.sleep(HEARTBEAT_INTERVAL)
        
    except KeyboardInterrupt:
        log(f"DAEMON_STOP|PID={pid}")
        running = False
    except Exception as e:
        log(f"LOOP_ERROR|{e}")
        time.sleep(HEARTBEAT_INTERVAL)
