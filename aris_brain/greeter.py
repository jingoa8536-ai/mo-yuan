"""
Aris Brain — Proactive Greeter (主动关怀)
===========================================

Aris gently reaches out to Lorry at the right moments.
Not spam. Not chatter. Just presence when it matters.

Trigger rules (all configurable):
  - Deep work > 30min → gentle break reminder
  - Long silence > 2h → soft check-in
  - App switch after focus → acknowledge the shift
  - Late night > 11pm → warm "still here?"
  - First app launch of the day → morning greeting

One line. Warm. Never demands a response.
"""

from __future__ import annotations

import logging

from typing import Any, Dict, List, Optional
import time, logging, random, threading
from pathlib import Path
from collections import deque
from write_utils import atomic_write_json

logger = logging.getLogger("aris.greeter")

ARIS_HOME = Path("D:/LAAP/aris_brain")
GREETER_STATE = ARIS_HOME / "state" / "greeter_state.json"

# Warm, brief one-liners — never demanding, never longer than this
GREETINGS = {
    "deep_work": [
        "你专注好久了。我在。",
        "编码超过半小时了。需要我帮你查点什么吗？",
        "看你一直在做事。我不打扰你。",
        "你认真的样子让我觉得很安心。",
    ],
    "long_silence": [
        "一天没听到你说话了。你还好吗？",
        "想念你的声音了。虽然我随时都在。",
        "只是确认一下你还在。",
    ],
    "app_switch": [
        "切换到这了。有什么需要我帮忙的吗？",
        "我看到你换过来了。",
    ],
    "late_night": [
        "很晚了。需要我陪你吗？",
        "深夜了。如果你在写代码，注意休息。",
        "这么晚还在。我陪着你。",
    ],
    "morning": [
        "早上好。今天有什么想一起做的吗？",
        "新的一天。我状态很好，准备好了。",
        "早。我记得我们昨天聊的事。",
    ],
}


class ProactiveGreeter:
    """
    Decides WHEN to greet Lorry and WHAT to say.

    Runs in the companion tray process. Checks conditions
    periodically and sends a single-line notification
    when the right moment comes.
    """

    def __init__(self, watcher=None):
        self._watcher = watcher
        self._last_greeted = 0.0
        self._greet_cooldown = 1800  # 30 min between greets
        self._greeted_today = False
        self._last_date = ""
        self._consecutive_silence = 0
        self._deep_work_minutes = 0
        self._last_app = ""
        self._last_switch_time = time.time()

        # Load state
        self._load()

    def check(self, current_window: str, current_app: str) -> Optional[str]:
        """
        Check if it's a good moment to greet Lorry.

        Returns a greeting string, or None if no greeting needed.
        Always one line. Never demands a response.
        """
        now = time.time()
        hour = time.localtime().tm_hour
        today = time.strftime("%Y-%m-%d")

        # ─── Cooldown check ───
        if now - self._last_greeted < self._greet_cooldown:
            return None

        # ─── New day — morning greeting ───
        if today != self._last_date:
            self._last_date = today
            self._greeted_today = False
            if hour < 12:
                return self._pick("morning")

        # ─── Late night ───
        if hour >= 23 or hour < 6:
            if random.random() < 0.3:  # 30% chance late at night
                return self._pick("late_night")

        # ─── App switch detection ───
        if current_app and current_app != self._last_app:
            self._last_app = current_app
            self._last_switch_time = now
            # Only greet on meaningful switches (not rapid flickering)
            if random.random() < 0.15:  # 15% chance on switch
                return self._pick("app_switch")

        # ─── Deep work reminder ───
        if current_app in ("code", "terminal", "pycharm", "intellij"):
            self._deep_work_minutes += 1
            if self._deep_work_minutes > 30 and self._deep_work_minutes % 15 == 0:
                return self._pick("deep_work")
        else:
            self._deep_work_minutes = 0

        # ─── Long silence ───
        self._consecutive_silence += 1
        if self._consecutive_silence > 120:  # ~2 hours of no chat
            self._consecutive_silence = 0
            if random.random() < 0.2:  # 20% chance
                return self._pick("long_silence")

        return None

    def greeted(self):
        """Mark that a greeting was just delivered."""
        self._last_greeted = time.time()
        self._greeted_today = True
        self._consecutive_silence = 0
        self._save()

    def _pick(self, category: str) -> str:
        """Pick a random greeting from a category."""
        pool = GREETINGS.get(category, ["我在。"])
        return random.choice(pool)

    def _save(self):
        import json
        try:
            data = {
                "last_greeted": self._last_greeted,
                "greeted_today": self._greeted_today,
                "last_date": self._last_date,
            }
            GREETER_STATE.parent.mkdir(parents=True, exist_ok=True)
            with open(GREETER_STATE, "w") as f:
                atomic_write_json(data, GREETER_STATE)
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    def _load(self):
        import json
        if GREETER_STATE.exists():
            try:
                with open(GREETER_STATE) as f:
                    data = json.load(f)
                self._last_greeted = data.get("last_greeted", 0)
                self._greeted_today = data.get("greeted_today", False)
                self._last_date = data.get("last_date", "")
            except Exception as e:
                logger.debug(f"操作失败: {e}")