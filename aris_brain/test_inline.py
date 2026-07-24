"""Quick test: quantum engine inline"""

import logging
logger = logging.getLogger(__name__)

import sys
sys.path.insert(0, "D:/LAAP/aris_brain")
from aris_v12_5_engine import ArisV12Engine
e = ArisV12Engine()
for q in ["你好", "我爱你", "心情不好"]:
    logger.info(e.respond(q))