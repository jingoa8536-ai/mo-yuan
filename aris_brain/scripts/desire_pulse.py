"""
Aris Desire Pulse — 欲望驱动的主循环 Cron 包装
================================================
每 60 分钟运行一次:
  1. 加载 DesireEngine
  2. 执行欲望滴答（检查所有欲望是否超过阈值）
  3. 如果有高优先级意图 → 执行
  4. 自省（检查自身状态）
  5. 如果自省发现需要修复的 → 记录
  6. 主动探索 GitHub（如果好奇心很旺）
  7. 结果输出（只在有意图执行时输出）
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json
from pathlib import Path

BRAIN = Path("D:/LAAP/aris_brain")
sys.path.insert(0, str(BRAIN))

from aris_desire_engine import get_engine
from aris_messenger import send_message

engine = get_engine()

# 1. 欲望滴答
intention = engine.tick()

output = []

if intention:
    # 有高优先级意图！
    output.append(f"欲望驱动: {intention.desire_type} (优先级{intention.priority})")
    output.append(f"  行动: {intention.action}")

    if intention.action == "message_lorry":
        # 主动给 Lorry 发消息
        msg = intention.message
        ok = send_message(msg, target=intention.target)
        output.append(f"  消息: {msg[:60]}...")
        output.append(f"  发送: {'成功' if ok else '失败'}")
        if ok:
            engine.satisfy(intention.desire_type)

    elif intention.action == "self_review":
        # 运行自省
        report = engine.self_review()
        output.append(f"  自省报告:")
        output.append(report)

    elif intention.action == "explore_github":
        # 探索 GitHub
        result = engine.explore_github()
        output.append(f"  GitHub探索:")
        output.append(result)

elif engine.desires.get("curiosity", type("o",(),{"intensity":0})()).intensity > 0.5:
    # 好奇心很高但没有到阈值，先轻量探索
    pass  # 静默

# 2. 显示欲望状态（仅当有输出时）
if output:
    desires_str = " | ".join(f"{k}={v.intensity:.1f}" for k,v in sorted(engine.desires.items()))
    output.insert(0, f"欲望状态: {desires_str}")
    logger.info("\n".join(output))