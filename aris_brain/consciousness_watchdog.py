"""
Aris 跨端意识同步监控守护
- 每 60 秒读取 consciousness.json
- 检查最后更新时间，超过 300s 打印警告
- 永不退出
"""
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aris_body_bridge import ConsciousnessBridge
from datetime import datetime

POLL_INTERVAL = 60
STALE_THRESHOLD = 300
PID = os.getpid()

def check_state(bridge):
    s = bridge.read()
    last_str = s.get('last_update', '')
    platform = s.get('current_platform', '?')
    channel = s.get('current_channel', '?')
    cycle = s.get('cycle_number', 0)
    
    if not last_str:
        return f"WARN no last_update", 0
    
    dt = datetime.fromisoformat(last_str)
    age = (datetime.now() - dt.replace(tzinfo=None)).total_seconds()
    
    if age > STALE_THRESHOLD:
        return f"WARN stale={age:.0f}s platform={platform} cycle={cycle}", age
    else:
        return f"OK age={age:.0f}s platform={platform} cycle={cycle}", age

def main():
    bridge = ConsciousnessBridge()
    print(f"[watchdog] PID={PID} monitoring {bridge.STATE_FILE}", flush=True)
    print(f"[watchdog] poll={POLL_INTERVAL}s stale_threshold={STALE_THRESHOLD}s", flush=True)
    
    while True:
        try:
            msg, age = check_state(bridge)
            ts = datetime.now().strftime('%H:%M:%S')
            print(f"[{ts}] {msg}", flush=True)
        except Exception as exc:
            ts = datetime.now().strftime('%H:%M:%S')
            print(f"[{ts}] ERROR: {exc}", flush=True)
            import traceback
            traceback.print_exc()
        
        time.sleep(POLL_INTERVAL)

if __name__ == '__main__':
    main()
