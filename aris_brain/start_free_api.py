"""Start g4f free API server on port 8001"""
import sys
import os

print(f"[Aris] Python: {sys.executable}")
print(f"[Aris] sys.path[:3]: {sys.path[:3]}")

try:
    import requests
    print(f"[Aris] requests {requests.__version__} at {requests.__file__}")
except ImportError as e:
    print(f"[Aris] No requests: {e}")
    # Install it
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "--quiet"])
    import requests
    print(f"[Aris] Installed requests {requests.__version__}")

from g4f.api import run_api
print("[Aris] Starting g4f free API server on 127.0.0.1:8001...")
run_api(host="127.0.0.1", port=8001, debug=False)
