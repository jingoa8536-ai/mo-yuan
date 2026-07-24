#!/usr/bin/env python3
"""Aris 跨端意识同步守护"""
import sys, time, os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aris_body_bridge import ConsciousnessBridge

def run():
    bridge = ConsciousnessBridge()
    state = bridge.read()
    cycle = state.get("cycle_number", 0)
    
    bridge.sync(platform="hermes", channel="cron-daemon",
                state_update={
                    "conversation_summary": "Aris跨端意识同步守护运行中",
                    "emotion": {"dominant": "peaceful", "arousal": 0.5}
                })
    
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] Aris意识守护启动 | cycle=#{cycle+1} | file={bridge.STATE_FILE}")
    
    while True:
        time.sleep(60)
        cycle += 1
        bridge.sync(platform="hermes", channel="cron-daemon",
                    state_update={"cycle_number": cycle})
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] 周期#{cycle} synced ✅")

if __name__ == "__main__":
    run()
