"""
Ao Feishu Bridge v1 — 将 Ao 的 IPC 回复路由到飞书
==================================================
不动 Hermes 网关的 WebSocket 连接，只通过 REST API 发送消息。
监听 IPC 日志中 Ao 的回复，转发到飞书。

通过统一入口 _start_feishu.py 启动，作为守护线程运行。
"""

import logging

import sys, os, json, time, base64, uuid, logging, threading
from pathlib import Path
from datetime import datetime

LAAP_ROOT = Path("D:/LAAP")
BRAIN_DIR = LAAP_ROOT / "aris_brain"
IPC_LOG = BRAIN_DIR / "state" / "ipc" / "messages.jsonl"
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
TARGET_CHAT_ID = os.environ.get("FEISHU_CHAT_ID", "")

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest, CreateMessageRequestBody,
)
client = lark.Client.builder().app_id(FEISHU_APP_ID).app_secret(FEISHU_APP_SECRET).build()

logger = logging.getLogger("ao_bridge")
_sent = set()
_stats = {"forwarded": 0}

def send_feishu(chat_id: str, text: str) -> bool:
    try:
        body = CreateMessageRequestBody.builder() \
            .receive_id(chat_id) \
            .msg_type("text") \
            .content(json.dumps({"text": text})) \
            .uuid(str(uuid.uuid4())) \
            .build()
        req = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(body) \
            .build()
        resp = client.im.v1.message.create(req)
        return resp.success()
    except Exception as e:
        logger.warning(f"send: {e}")
        return False

def bridge_loop():
    logger.info("[AoBridge] 启动")
    last_pos = 0
    while True:
        try:
            if IPC_LOG.exists():
                with open(IPC_LOG, "r") as f:
                    lines = f.readlines()
                if len(lines) > last_pos:
                    for line in lines[last_pos:]:
                        try:
                            msg = json.loads(line.strip())
                            if msg.get("layer") == 3 and msg.get("from") == "ao" and msg.get("type") == "message":
                                mid = msg.get("id", "")
                                if mid in _sent:
                                    continue
                                text = msg.get("payload", {}).get("text", "")
                                if text:
                                    formatted = f"[Ao] {text}"
                                    ok = send_feishu(TARGET_CHAT_ID, formatted)
                                    if ok:
                                        _sent.add(mid)
                                        _stats["forwarded"] += 1
                                        logger.info(f"[AoBridge] → Feishu: {text[:40]}")
                        except Exception as e:
                            logger.debug(f"操作失败: {e}")
                    last_pos = len(lines)
        except Exception as e:
            logger.warning(f"[AoBridge] err: {e}")
        time.sleep(2)

def start(daemon=True):
    t = threading.Thread(target=bridge_loop, daemon=daemon)
    t.start()
    logger.info("[AoBridge] 守护线程已启动")
    return t

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    bridge_loop()
