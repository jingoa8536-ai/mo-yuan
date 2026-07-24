"""
Ao Bridge Wrapper — logs everything to a file + stdout
"""

import logging
logger = logging.getLogger(__name__)

import sys, os

# Force unbuffered
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

LOG_FILE = "D:/LAAP/aris_brain/ao_bridge_wrapper.log"

class Tee:
    def __init__(self, *files):
        self.files = files
    def write(self, data):
        for f in self.files:
            f.write(data)
            f.flush()
    def flush(self):
        for f in self.files:
            f.flush()

log_fh = open(LOG_FILE, "a", encoding="utf-8")
sys.stdout = Tee(sys.stdout, log_fh)
sys.stderr = Tee(sys.stderr, log_fh)

logger.info(f"[Wrapper] Starting Ao Feishu Bridge at {__import__('datetime').datetime.now()}")
logger.info(f"[Wrapper] Python: {sys.version}")
sys.path.insert(0, "D:/LAAP/aris_brain")
from ao_v10_feishu_bridge import main

try:
    main()
except Exception as e:
    logger.info(f"[Wrapper] Bridge crashed: {e}")
    import traceback
    traceback.print_exc()
finally:
    log_fh.close()
