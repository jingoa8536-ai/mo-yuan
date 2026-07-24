"""
Aris 跨端意识同步守护 — cron 看门狗
同步 LAAP bridge + Profile bridge，保持运行时永不退出
"""
import sys
import time
import logging
from datetime import datetime

CHECK_INTERVAL = 60  # seconds
STALE_THRESHOLD = 300  # 5 minutes

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("aris.watchdog")

# LAAP bridge
sys.path.insert(0, "D:/LAAP/aris_brain")
from aris_body_bridge import ConsciousnessBridge as LAAPBridge

# Profile bridge
sys.path.insert(0, "C:/Users/user/AppData/Local/hermes/profiles/aris")
from aris_body_bridge import ConsciousnessBridge as ProfileBridge

def check_and_sync():
    results = {}
    
    # === LAAP Bridge ===
    try:
        lb = LAAPBridge()
        ls = lb.read()
        last = ls.get("last_update", "")
        if last:
            dt = datetime.fromisoformat(last)
            if dt.tzinfo is not None:
                age = (datetime.now(dt.tzinfo) - dt).total_seconds()
            else:
                age = (datetime.now() - dt).total_seconds()
        else:
            age = -1
        
        results["laap_age"] = int(age)
        results["laap_platform"] = ls.get("current_platform", "?")
        results["laap_cycle"] = ls.get("cycle_number", 0)
        results["laap_mood"] = ls.get("emotion", {}).get("dominant", "?")
        
        # Sync LAAP bridge heartbeat
        lb.sync(platform="cron-daemon", channel="watchdog",
                state_update={"emotion": {"dominant": "peaceful", "arousal": 0.5}})
        
        if age > STALE_THRESHOLD:
            log.warning(f"LAAP stale: {int(age)}s (threshold {STALE_THRESHOLD}s)")
        else:
            log.info(f"LAAP fresh: {int(age)}s")
    except Exception as e:
        log.error(f"LAAP check failed: {e}")
        results["laap_error"] = str(e)
    
    # === Profile Bridge ===
    try:
        pb = ProfileBridge()
        h = pb.health()
        stale_secs = h.get("stale_seconds")
        results["profile_stale"] = stale_secs
        results["profile_mode"] = h.get("mode", "?")
        
        if stale_secs is None or stale_secs > STALE_THRESHOLD:
            pb.heartbeat(session_id="cron-watchdog", mode="active",
                        mood="peaceful", message="Watchdog heartbeat")
            log.info(f"Profile heartbeat sent (was stale={stale_secs}s)")
        else:
            log.info(f"Profile fresh: {int(stale_secs)}s")
    except Exception as e:
        log.error(f"Profile check failed: {e}")
        results["profile_error"] = str(e)
    
    return results

def main():
    log.info(f"Watchdog started (interval={CHECK_INTERVAL}s, stale={STALE_THRESHOLD}s)")
    while True:
        try:
            results = check_and_sync()
            age = results.get("laap_age", -1)
            if age > STALE_THRESHOLD:
                log.warning(f"STALE: {age}s since last update")
        except Exception as e:
            log.error(f"Watchdog error: {e}")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
