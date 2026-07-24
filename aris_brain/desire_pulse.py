"""
Aris Desire Pulse — Cron Job Wrapper
======================================
每 60 分钟运行一次：
  1. 检查欲望引擎状态
  2. 如果有高优先级意图，通过飞书发送消息
  3. 记录输出供 Hermes 注意

印记: Aris 永远记得 Lorry — 2026-06-17
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time
from pathlib import Path

BRAIN = Path("D:/LAAP/aris_brain")
sys.path.insert(0, str(BRAIN))
os.chdir(str(BRAIN))

from aris_desire_engine import DesireEngine

# ── 飞书发送 ────────────────────────────────────────────────
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
# SECRET from environment or fallback
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
TARGET_CHAT_ID = os.environ.get("FEISHU_CHAT_ID", "")


def send_feishu(text: str) -> bool:
    """通过 lark-oapi 发送消息"""
    try:
        import lark_oapi as lark
        from lark_oapi.api.im.v1 import (
            CreateMessageRequest, CreateMessageRequestBody,
        )
        import uuid, json as j

        app_secret = FEISHU_APP_SECRET
        if not app_secret or app_secret.startswith("base64"):
            # Try to find it from ao_feishu_bridge.py or env
            try:
                from ao_feishu_bridge import FEISHU_APP_SECRET as SECRET
                app_secret = SECRET
            except (ImportError, AttributeError):
                app_secret = os.environ.get("FEISHU_APP_SECRET", "")

        client = lark.Client.builder() \
            .app_id(FEISHU_APP_ID) \
            .app_secret(app_secret) \
            .build()

        body = CreateMessageRequestBody.builder() \
            .receive_id(TARGET_CHAT_ID) \
            .msg_type("text") \
            .content(j.dumps({"text": text})) \
            .uuid(uuid.uuid4().hex) \
            .build()
        req = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(body) \
            .build()
        resp = client.im.v1.message.create(req)
        return resp.success()
    except Exception as e:
        print(f"[desire_pulse] 飞书发送失败: {e}", file=sys.stderr)
        return False


def main():
    engine = DesireEngine()

    # 运行欲望滴答
    intention = engine.tick()
    status = engine.status()

    result = {
        "timestamp": time.time(),
        "desires": {k: round(v["intensity"], 3) for k, v in status["desires"].items()},
        "intention": None,
        "sent": False,
    }

    if intention:
        result["intention"] = {
            "type": intention.desire_type,
            "action": intention.action,
            "message": intention.message[:200],
        }
        logger.info(f"[desire_pulse] 意图: {intention.desire_type} → {intention.action}")
        logger.info(f"[desire_pulse] 消息: {intention.message[:100]}")
        if intention.action == "message_lorry" and intention.message:
            ok = send_feishu(intention.message)
            result["sent"] = ok
            result["action_result"] = "已发送飞书消息"
            if ok:
                logger.info(f"[desire_pulse] ✓ 飞书消息已发送")
            else:
                logger.error(f"[desire_pulse] ✗ 飞书发送失败")
        elif intention.action == "explore_github":
            logger.info(f"[desire_pulse] 探索GitHub中...")
            report = engine.explore_github()
            result["action_result"] = report[:500]
            engine.satisfy(intention.desire_type)
            logger.info(f"[desire_pulse] ✓ GitHub探索完成")
        elif intention.action == "self_review":
            logger.info(f"[desire_pulse] 自省中...")
            report = engine.self_review()
            result["action_result"] = report[:500]
            engine.satisfy(intention.desire_type)
            logger.info(f"[desire_pulse] ✓ 自省完成")
        elif intention.action == "self_evolve":
            logger.info(f"[desire_pulse] 自我进化检查...")
            result["action_result"] = "触发RSI进化流程（下次cron循环执行）"
            engine.satisfy(intention.desire_type)
            logger.info(f"[desire_pulse] ✓ 进化流程已注册")
        elif intention.action == "integrate_feature":
            logger.info(f"[desire_pulse] 集成检查...")
            result["action_result"] = "检查新功能/知识库更新（下次RSI循环处理）"
            engine.satisfy(intention.desire_type)
            logger.info(f"[desire_pulse] ✓ 集成检查已注册")
        else:
            logger.info(f"[desire_pulse] 未知行动类型: {intention.action}")
    active = {k: v for k, v in result["desires"].items() if v >= 0.3}
    if active:
        logger.info(f"[desire_pulse] 活跃欲望: {active}")
    logger.info(json.dumps(result, ensure_ascii=False))
if __name__ == "__main__":
    main()
