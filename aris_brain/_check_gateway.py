import json, os

# 1. Check if gateway PID is alive
state_path = os.path.expanduser('~/AppData/Local/hermes/profiles/aris/gateway_state.json')
if os.path.exists(state_path):
    with open(state_path) as f:
        state = json.load(f)
        pid = state.get('pid', 0)
        print(f"Gateway state PID: {pid}")
        print(f"State kind: {state.get('kind')}")
        
        # Check if process exists
        result = os.system(f'tasklist /FI "PID eq {pid}" 2>nul | findstr "{pid}" >nul')
        if result == 0:
            print(f"PID {pid} is ALIVE")
        else:
            print(f"PID {pid} is DEAD")
else:
    print("Gateway state file not found")

# 2. Search running processes for gateway
print("\n=== All python processes ===")
os.system('wmic process where "name=\'python.exe\'" get ProcessId,CommandLine /format:csv 2>nul')
