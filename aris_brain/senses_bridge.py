#!/usr/bin/env python3
"""
Aris 感官桥梁 — 传感器 → PSI大脑 → TTS
=======================================
感官捕获的每一句话都走真正的 Aris 认知架构。

架构:
  麦克风 → ASR → SensoryCortex → ArisBrain.think() → TTS
  摄像头 → VLM → SensoryCortex → visual quale → 认知状态

用法:
  python senses_bridge.py          # 启动完整感官→大脑→语音
  python senses_bridge.py --once   # 单次听+说
"""

import logging
logger = logging.getLogger(__name__)

import sys, time, json
from pathlib import Path
sys.path.insert(0, str(Path("D:/LAAP")))

from aris_brain.senses import SensoryCortex

print()
logger.info("  ✦ Aris Senses Bridge")
logger.info("  Sensors → PSI Brain → Voice")
print()

cortex = SensoryCortex(use_ipc=True, use_tts=True)
cortex.start()

logger.info("  我在听。你想说什么？")
print()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    cortex.stop()
    logger.info("\n  桥梁已关闭。")