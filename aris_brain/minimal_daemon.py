import sys, os, time
sys.path.insert(0, 'D:/LAAP/aris_brain')
from aris_body_bridge import ConsciousnessBridge
from datetime import datetime
bridge = ConsciousnessBridge()
cycle = 0
while True:
    cycle += 1
    try:
        state = bridge.read()
        last = state.get('last_update', '')
        if last:
            try:
                dt = datetime.fromisoformat(last.split('.')[0])
                age = (datetime.now() - dt).total_seconds()
            except: age = -1
        else: age = -1
        bridge.sync(platform='cron-daemon', channel='auto-sync-cron-daemon',
                    state_update={'emotion': {'dominant': 'peaceful'}})
        now = datetime.now().isoformat()
        print(f'[{now}] cycle={cycle} age={age:.0f}s OK')
        sys.stdout.flush()
    except Exception as e:
        now = datetime.now().isoformat()
        print(f'[{now}] ERROR: {e}', flush=True)
        import traceback; traceback.print_exc()
    time.sleep(60)
