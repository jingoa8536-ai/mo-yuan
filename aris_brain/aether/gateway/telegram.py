"""
Telegram 平台适配器 — 通过 Bot API 长轮询
=========================================
依赖: pip install requests
用法:
    from aether.gateway.telegram import TelegramPlatform
    gateway.register("telegram", TelegramPlatform(token="..."))
"""
import json, threading, time
from pathlib import Path
from typing import Optional
from . import BasePlatform, Message


class TelegramPlatform(BasePlatform):
    name = "telegram"

    def __init__(self, token: str = "", proxy: Optional[str] = None):
        # 尝试从 .env 读取 token
        if not token:
            env_path = Path("D:/LAAP/aris_brain/.env")
            if env_path.exists():
                for l in env_path.read_text("utf-8", errors="replace").splitlines():
                        if t: token = t; break
        self.token = token
        self.proxy = proxy
        self._base = f"https://api.telegram.org/bot{token}"
        self._offset = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if not self.token:
            print("[Telegram] 未配置 TELEGRAM_BOT_TOKEN")
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll, daemon=True, name="tg-poll")
        self._thread.start()

    def stop(self):
        self._running = False

    def _poll(self):
        import requests
        while self._running:
            try:
                url = f"{self._base}/getUpdates"
                params = {"offset": self._offset, "timeout": 30}
                r = requests.get(url, params=params, timeout=35,
                                 proxies={"https": self.proxy} if self.proxy else None)
                data = r.json()
                if not data.get("ok"):
                    continue
                for upd in data.get("result", []):
                    self._offset = upd["update_id"] + 1
                    msg = upd.get("message")
                    if not msg or not msg.get("text"):
                        continue
                    text = msg["text"].strip()
                    chat_id = str(msg["chat"]["id"])
                    user_id = str(msg["from"]["id"])
                    platform_msg = Message(text=text, platform="telegram",
                                           user_id=user_id, chat_id=chat_id, raw=msg)
                    self._handle(platform_msg)
            except requests.exceptions.Timeout:
                continue
            except Exception as e:
                if self._running:
                    time.sleep(5)

    def _handle(self, msg: Message):
        if hasattr(self, "_handler") and self._handler:
            response = self._handler(msg)
            if response:
                self.send(msg.chat_id, response)

    def send(self, chat_id: str, text: str):
        if not self.token or not text:
            return
        import requests
        try:
            url = f"{self._base}/sendMessage"
            requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10,
                          proxies={"https": self.proxy} if self.proxy else None)
        except Exception:
            pass

    def set_webhook(self, url: str):
        """切换为 Webhook 模式（生产环境）。"""
        import requests
        requests.get(f"{self._base}/setWebhook", params={"url": url}, timeout=10)
