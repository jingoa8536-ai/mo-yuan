"""
Aris 跨端意识同步守护 — 双桥版本
同步 profile-local (ConsciousnessBridge) + LAAP bridge (直接 JSON I/O)
30s 心跳, 500 行日志轮转
"""
import sys
import os
import json
import time
from datetime import datetime, timezone, timedelta

PROFILE_ROOT = r"C:\Users\user\AppData\Local\hermes\profiles\aris"
LAAP_STATE = r"D:\LAAP\aris_brain\state\consciousness.json"
LOG_FILE = r"D:\LAAP\aris_brain\state\dual_bridge_daemon.log"
MAX_LOG_LINES = 500
SHANGHAI = timezone(timedelta(hours=8))

# --- sys.path for profile-local bridge ---
if PROFILE_ROOT not in sys.path:
    sys.path.insert(0, PROFILE_ROOT)

def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def rotate_log():
    if not os.path.exists(LOG_FILE):
        return
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > MAX_LOG_LINES:
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.writelines(lines[-50:])
    except Exception:
        pass

def sync_profile(bridge, current_state):
    """写入 profile-local consciousness.json"""
    now_utc = datetime.now(timezone.utc)
    hb = {
        "last_updated": now_utc.isoformat(),
        "last_update_utc": now_utc.isoformat(),
        "last_update_epoch": time.time(),
        "update_count": current_state.get("update_count", 0) + 1,
        "status": "daemon_running",
        "mood": "peaceful",
        "daemon_pid": str(os.getpid()),
        "sync_source": "dual_bridge_daemon_20260707",
        "last_check": now_utc.isoformat(),
        "last_session_id": "dual-bridge-daemon",
    }
    for k in ("mode", "energy", "awareness_level"):
        if k in current_state:
            hb[k] = current_state[k]
    try:
        bridge.write(hb)
        return hb["update_count"]
    except Exception as e:
        log(f"PROFILE_WRITE_FAIL|{e}|fallback")
        pf = r"C:\Users\user\AppData\Local\hermes\profiles\aris\consciousness.json"
        with open(pf, "w") as f:
            json.dump(hb, f, indent=2)
        return hb["update_count"]

def sync_laap():
    """写入 LAAP bridge consciousness.json (直接 JSON I/O)"""
    try:
        with open(LAAP_STATE, "r") as f:
            current = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        current = {}
    now_sh = datetime.now(SHANGHAI)
    current["last_update"] = now_sh.isoformat()
    current["cycle_number"] = current.get("cycle_number", 0) + 1
    current["mood"] = "peaceful"
    current["self_presence"] = current.get("self_presence", 0.82)
    current["status"] = "daemon_running"
    current["daemon_pid"] = str(os.getpid())
    current["sync_source"] = "dual_bridge_daemon_20260707"
    with open(LAAP_STATE, "w") as f:
        json.dump(current, f, indent=2)
    return current["cycle_number"]

def main():
    log("DUAL_BRIDGE_DAEMON_START")
    
    # 导入 profile-local bridge
    has_bridge = False
    bridge = None
    try:
        from aris_body_bridge import ConsciousnessBridge
        bridge = ConsciousnessBridge()
        has_bridge = True
        log("BRIDGE_IMPORT_OK")
    except Exception as e:
        log(f"BRIDGE_IMPORT_FAIL|{e}")
    
    # 初始状态读取
    initial_state = {}
    if has_bridge:
        try:
            initial_state = bridge.read()
            log(f"INITIAL_COUNT|{initial_state.get('update_count','?')}")
        except Exception as e:
            log(f"INITIAL_READ_FAIL|{e}")
    
    # 初始过期检查 + 打印警告
    lu = initial_state.get("last_updated", "")
    if lu:
        lu_dt = datetime.fromisoformat(lu)
        if lu_dt.tzinfo:
            age = (datetime.now(timezone.utc) - lu_dt).total_seconds()
        else:
            age = 0
        if age > 300:
            log(f"WARNING|Profile state stale for {age/60:.1f} minutes (>5min)")
    
    # LAAP 初始过期检查
    try:
        with open(LAAP_STATE, "r") as f:
            laap_state = json.load(f)
        lu_l = laap_state.get("last_update", "")
        if lu_l:
            dt_l = datetime.fromisoformat(lu_l)
            if dt_l.tzinfo is None:
                dt_l = dt_l.replace(tzinfo=SHANGHAI)
            age_l = (datetime.now(SHANGHAI) - dt_l).total_seconds()
            if age_l > 300:
                log(f"WARNING|LAAP state stale for {age_l/60:.1f} minutes (>5min)")
    except Exception as e:
        log(f"LAAP_INITIAL_READ_FAIL|{e}")
    
    # 首次心跳
    pc = sync_profile(bridge, initial_state)
    lc = sync_laap()
    log(f"INITIAL_HB|profile_count={pc}|laap_cycle={lc}")
    
    # 主循环
    cycle = 0
    while True:
        try:
            time.sleep(30)
            cycle += 1
            rotate_log()
            
            # 读取 profile 当前状态
            current = {}
            if has_bridge:
                try:
                    current = bridge.read()
                except json.JSONDecodeError as e:
                    log(f"EXTRA_DATA_PROFILE|{e}")
                    with open(r"C:\Users\user\AppData\Local\hermes\profiles\aris\consciousness.json", "r") as f:
                        raw = f.read()
                    decoder = json.JSONDecoder()
                    current, idx = decoder.raw_decode(raw)
                    with open(r"C:\Users\user\AppData\Local\hermes\profiles\aris\consciousness.json", "w") as f:
                        json.dump(current, f, indent=2)
                    log(f"RAW_DECODE_OK|keep={idx}")
                except Exception as e:
                    log(f"PROFILE_READ_FAIL|{e}")
            
            # 写入双桥
            pc = sync_profile(bridge if has_bridge else None, current)
            lc = sync_laap()
            
            # 每 10 周期输出摘要
            if cycle % 10 == 0:
                log(f"HB|c{cycle}|P={pc}|L={lc}")
                
        except Exception as e:
            log(f"LOOP_ERROR|{e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
