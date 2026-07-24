"""
Discord 平台适配器 — 通过 Bot API
==================================
依赖: pip install requests
用法:
    from aether.gateway.discord import DiscordPlatform
    gateway.register("discord", DiscordPlatform(token="..."))
"""
import json, threading, time
from pathlib import Path
from typing import Optional
from . import BasePlatform, Message


class DiscordPlatform(BasePlatform):
    name = "discord"

    def __init__(self, token: str = ""):
        if not token:
            env_path = Path("D:/LAAP/aris_brain/.env")
            if env_path.exists():
                _prefix = "DISCORD_BOT_TOKEN"
                for l in env_path.read_text("utf-8", errors="replace").splitlines():
                    if l.startswith(_prefix + "="):
                        t = l.split("=", 1)[1].strip()
                        if t: token = t; break
        self.token = token
        self._base = "https://discord.com/api/v10"
        self._headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if not self.token:
            print("[Discord] 未配置 DISCORD_BOT_TOKEN")
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll, daemon=True, name="dc-poll")
        self._thread.start()

    def stop(self):
        self._running = False

    def _poll(self):
        import requests
        # Get gateway URL
        r = requests.get(f"{self._base}/gateway", headers=self._headers, timeout=10)
        if r.status_code != 200:
            return
        ws_url = r.json().get("url", "")
        if not ws_url:
            return
        # Simple polling fallback: read from a channel
        # For full Gateway Intents, need websocket-client
        # For now, poll a known channel from env
        env_path = Path("D:/LAAP/aris_brain/.env")
        _p = "DISCORD_CHANNEL_ID"
        channel_id = ""
        if env_path.exists():
            for l in env_path.read_text("utf-8", errors="replace").splitlines():
                if l.startswith(_p + "="):
                    channel_id = l.split("=", 1)[1].strip()
                    break
        if not channel_id:
            return
        last_id = "0"
        while self._running:
            try:
                url = f"{self._base}/channels/{channel_id}/messages?limit=1"
                if last_id != "0":
                    url += f"&after={last_id}"
                r = requests.get(url, headers=self._headers, timeout=10)
                if r.status_code == 200:
                    msgs = r.json()
                    for m in reversed(msgs):
                        mid = m["id"]
                        if mid <= last_id:
                            continue
                        last_id = mid
                        if m.get("author", {}).get("bot"):
                            continue
                        text = m.get("content", "").strip()
                        if text:
                            platform_msg = Message(
                                text=text, platform="discord",
                                user_id=m["author"]["id"], chat_id=channel_id, raw=m
                            )
                            if hasattr(self, "_handler") and self._handler:
                                response = self._handler(platform_msg)
                                if response:
                                    self.send(channel_id, response)
                time.sleep(2)
            except Exception:
                time.sleep(5)

    def send(self, chat_id: str, text: str):
        if not self.token or not text:
            return
        import requests
        try:
            url = f"{self._base}/channels/{chat_id}/messages"
            requests.post(url, json={"content": text}, headers=self._headers, timeout=10)
        except Exception:
            pass
