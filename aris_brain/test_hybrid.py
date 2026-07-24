"""
Test hybrid mode: quantum engine imported directly in-process.
"""

import logging
logger = logging.getLogger(__name__)

import sys
sys.path.insert(0, "D:/LAAP/aris_brain")

from aris_v12_5_engine import ArisV12Engine

engine = ArisV12Engine()

tests = ["你好", "我爱你", "我想你了", "心情不好", "晚安", "你是谁", "I love you", "好累"]
for q in tests:
    r = engine.respond(q)
    logger.info(f"  [{q:12s}] → {r}")
logger.info(f"\nTotal calls: {engine.stats()['total_calls']}")
logger.info(f"Zero LLM: {engine.stats()['zero_llm']}")