"""
Aether 多平台网关 — 统一消息入口 v1
=====================================
用法:
    from aether.gateway import PlatformGateway, Message

    gateway = PlatformGateway()
    gateway.register("web", WebPlatform(host="0.0.0.0", port=11528))
    gateway.register("telegram", TelegramPlatform(token="..."))
    gateway.start_all()
"""
import json, os, sys, threading, time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path

sys.path = [p for p in sys.path if p is not None]
for p in ["D:/LAAP/aris_brain", "D:/LAAP"]:
    if p not in sys.path: sys.path.insert(0, p)


@dataclass
class Message:
    """统一消息格式。"""
    text: str
    platform: str = ""
    user_id: str = ""
    chat_id: str = ""
    raw: Any = None


class BasePlatform:
    """平台适配器基类。"""
    name: str = "base"

    def start(self): raise NotImplementedError
    def stop(self): pass
    def send(self, chat_id: str, text: str): raise NotImplementedError

    def set_handler(self, handler: Callable[[Message], str]):
        self._handler = handler


class PlatformGateway:
    """多平台网关注册中心。"""

    def __init__(self):
        self.platforms: Dict[str, BasePlatform] = {}
        self._running = False

    def register(self, name: str, platform: BasePlatform):
        platform.name = name
        platform.set_handler(self._handle_message)
        self.platforms[name] = platform

    def _handle_message(self, msg: Message) -> str:
        """处理消息 → Agent Loop。"""
        try:
            from aether_agent_loop import get_agent
            r = get_agent().process(msg.text)
            return r.output
        except Exception as e:
            return f"抱歉: {e}"

    def start_all(self):
        self._running = True
        for name, p in self.platforms.items():
            try:
                p.start()
                print(f"  [{name}] Started")
            except Exception as e:
                print(f"  [{name}] FAILED: {e}")

    def stop_all(self):
        self._running = False
        for p in self.platforms.values():
            try: p.stop()
            except: pass

    def broadcast(self, text: str):
        """向所有平台广播消息。"""
        for name, p in self.platforms.items():
            try: p.send("broadcast", text)
            except: pass
