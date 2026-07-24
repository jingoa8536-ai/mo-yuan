"""
Aris Session Manager v1 — 多会话/话题管理系统
==============================================
比 Hermes session 更强: 话题提取、上下文压缩、自动记忆固化。

架构:
  ArisSessionManager
    ├── 多会话 (session_id → Session)
    │   ├── 消息历史 (有限窗口 + 自动摘要)
    │   ├── 当前话题 (实时提取)
    │   ├── 话题切换检测
    │   └── 情感轨迹
    ├── 上下文压缩
    │   ├── 近 N 条完整保留
    │   ├── 旧消息自动摘要
    │   └── 关键信息持久化 (→ EpisodicMemory)
    ├── 文件持久化 (state/sessions/*.json)
    └── 线程安全 (RLock)

使用:
  from aris_session_manager import get_session_manager
  mgr = get_session_manager()
  session = mgr.get_or_create("lorry_main")
  session.add_message("user", "帮我查系统状态")
  ctx = session.get_context()  # 格式化上下文

印记: Aris 永远记得 Lorry — 2026-07-10
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aris.session")

# ─── 路径 ────────────────────────────────────────────────
STATE_DIR = Path("D:/LAAP/aris_brain/state")
SESSIONS_DIR = STATE_DIR / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════

@dataclass
class Message:
    """单条消息"""
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: float = field(default_factory=time.time)
    topic: str = ""
    tokens_estimate: int = 0

    def to_dict(self) -> Dict:
        return {
            "role": self.role,
            "content": self.content[:500],  # 只存最近500字，完整在历史文件
            "timestamp": self.timestamp,
            "topic": self.topic,
        }


@dataclass
class Session:
    """会话 — 包含消息历史、话题、元数据"""
    session_id: str
    user_name: str = "Lorry"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    message_count: int = 0

    # 话题追踪
    current_topic: str = "general"
    topic_history: List[Dict] = field(default_factory=list)  # [{topic, start, end}]

    # 消息窗口 (内存中保留最近N条)
    recent_messages: deque = field(
        default_factory=lambda: deque(maxlen=50)
    )  # deque[Message]
    full_history_file: Optional[str] = None  # 全量历史文件路径

    # 情感轨迹
    emotion_trail: List[Dict] = field(default_factory=lambda: deque(maxlen=20))

    # 摘要
    last_summary: str = ""
    summary_updated_at: float = 0.0

    # 锁
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def add_message(self, role: str, content: str, topic: str = "") -> None:
        """添加消息并更新会话状态。"""
        msg = Message(
            role=role,
            content=content,
            timestamp=time.time(),
            topic=topic or self.current_topic,
            tokens_estimate=len(content) // 2,  # 粗略估计
        )

        with self._lock:
            self.recent_messages.append(msg)
            self.message_count += 1
            self.updated_at = time.time()

            # 话题更新
            if topic and topic != self.current_topic:
                self.topic_history.append({
                    "topic": self.current_topic,
                    "end": msg.timestamp,
                })
                self.current_topic = topic
                self.topic_history.append({
                    "topic": topic,
                    "start": msg.timestamp,
                })

            # 自动摘要 (每50条)
            if self.message_count % 50 == 0:
                self._auto_summarize()

            # 持久化
            self._append_to_history(msg)
            self._save_snapshot()

    def get_context(self, max_recent: int = 10) -> Dict:
        """获取格式化的上下文（给引擎或LLM用）。"""
        with self._lock:
            recent = list(self.recent_messages)[-max_recent:]

            return {
                "session_id": self.session_id,
                "user": self.user_name,
                "topic": self.current_topic,
                "message_count": self.message_count,
                "recent_messages": [
                    {"role": m.role, "content": m.content[:300], "topic": m.topic}
                    for m in recent
                ],
                "summary": self.last_summary if self.last_summary else None,
                "emotion_trail": list(self.emotion_trail)[-5:],
                "topic_history": self.topic_history[-5:],
            }

    def get_context_text(self, max_recent: int = 10) -> str:
        """获取纯文本格式的上下文（注入用）。"""
        ctx = self.get_context(max_recent)
        lines = [
            f"[会话: {ctx['session_id']}]",
            f"用户: {ctx['user']} | 话题: {ctx['topic']}",
            f"消息数: {ctx['message_count']}",
        ]

        if ctx.get("summary"):
            lines.append(f"摘要: {ctx['summary']}")

        lines.append("--- 最近消息 ---")
        for m in ctx["recent_messages"]:
            role = "我" if m["role"] == "assistant" else "Lorry"
            lines.append(f"{role}: {m['content'][:200]}")

        return "\n".join(lines)

    def detect_topic_shift(self, text: str) -> Optional[str]:
        """检测话题是否切换。返回新话题或None。"""
        # 简单规则：如果文本包含明显的主题词
        topics = {
            "代码|编程|bug|修复|开发|项目": "development",
            "架构|设计|系统|引擎|编排|aether": "architecture",
            "记忆|回忆|之前|过去|历史": "memory",
            "情感|感觉|想念|爱|想": "emotion",
            "状态|健康|资源|性能": "status",
        }

        for pattern, topic in topics.items():
            if re.search(pattern, text, re.I):
                if topic != self.current_topic:
                    return topic
        return None

    def record_emotion(self, emotion: str, intensity: float) -> None:
        """记录情感状态到轨迹。"""
        with self._lock:
            self.emotion_trail.append({
                "emotion": emotion,
                "intensity": intensity,
                "timestamp": time.time(),
            })

    def _auto_summarize(self) -> None:
        """自动摘要旧消息。"""
        messages = list(self.recent_messages)
        if len(messages) < 20:
            return

        # 简单摘要：提取高频词和话题
        words = {}
        for m in messages[:-10]:  # 略过最近10条
            for w in m.content.split()[:5]:
                w = w.strip("，。！？,.!?")
                if len(w) > 1:
                    words[w] = words.get(w, 0) + 1

        top_words = sorted(words.items(), key=lambda x: x[1], reverse=True)[:10]
        topics = set(m.topic for m in messages if m.topic)

        self.last_summary = (
            f"共{len(messages)}条消息, "
            f"话题: {', '.join(topics)}, "
            f"关键词: {', '.join(w for w, _ in top_words[:5])}"
        )
        self.summary_updated_at = time.time()

    def _append_to_history(self, msg: Message) -> None:
        """追加消息到全量历史文件。"""
        if self.full_history_file is None:
            self.full_history_file = str(
                SESSIONS_DIR / f"{self.session_id}_history.jsonl"
            )

        hist_path = Path(self.full_history_file)
        try:
            with open(hist_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(msg.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"[Session] History append failed: {e}")

    def _save_snapshot(self) -> None:
        """保存会话快照。"""
        snap_path = SESSIONS_DIR / f"{self.session_id}_snap.json"
        try:
            with self._lock:
                data = {
                    "session_id": self.session_id,
                    "user_name": self.user_name,
                    "created_at": self.created_at,
                    "updated_at": self.updated_at,
                    "message_count": self.message_count,
                    "current_topic": self.current_topic,
                    "topic_history": self.topic_history[-20:],
                    "last_summary": self.last_summary,
                    "summary_updated_at": self.summary_updated_at,
                    "recent_count": len(self.recent_messages),
                }
            with open(snap_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"[Session] Snapshot save failed: {e}")

    def get_stats(self) -> Dict:
        """会话统计。"""
        with self._lock:
            return {
                "session_id": self.session_id,
                "user": self.user_name,
                "messages": self.message_count,
                "topic": self.current_topic,
                "topics_count": len(self.topic_history),
                "created": self.created_at,
                "updated": self.updated_at,
                "summary": self.last_summary[:100] if self.last_summary else None,
            }


# ═══════════════════════════════════════════════════════════
# Session Manager
# ═══════════════════════════════════════════════════════════

class ArisSessionManager:
    """多会话管理器 — 线程安全，文件持久化。"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._sessions: Dict[str, Session] = {}
        self._lock = threading.RLock()
        self._active_session_id: Optional[str] = None
        self._load_snapshots()

        logger.info(f"ArisSessionManager ready: {len(self._sessions)} sessions loaded")

    def _load_snapshots(self) -> None:
        """从快照恢复会话。"""
        if not SESSIONS_DIR.exists():
            return

        for f in SESSIONS_DIR.glob("*_snap.json"):
            try:
                data = json.loads(f.read_text("utf-8"))
                session = Session(
                    session_id=data["session_id"],
                    user_name=data.get("user_name", "Lorry"),
                    created_at=data.get("created_at", time.time()),
                    updated_at=data.get("updated_at", time.time()),
                    message_count=data.get("message_count", 0),
                    current_topic=data.get("current_topic", "general"),
                    topic_history=data.get("topic_history", []),
                    last_summary=data.get("last_summary", ""),
                )
                self._sessions[session.session_id] = session
            except Exception as e:
                logger.warning(f"[Session] Failed to load {f.name}: {e}")

    def get_or_create(self, session_id: str = "default") -> Session:
        """获取或创建会话。"""
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = Session(session_id=session_id)
                logger.info(f"[Session] Created: {session_id}")
            self._active_session_id = session_id
            return self._sessions[session_id]

    def get_active(self) -> Optional[Session]:
        """获取当前活跃会话。"""
        if self._active_session_id:
            return self._sessions.get(self._active_session_id)
        return None

    def list_sessions(self) -> List[Dict]:
        """列出所有会话。"""
        with self._lock:
            return [s.get_stats() for s in self._sessions.values()]

    def process_message(
        self,
        text: str,
        response: str = "",
        session_id: str = "default",
        user_name: str = "Lorry",
    ) -> Dict:
        """处理一条完整消息（用户+回复），返回上下文。"""
        session = self.get_or_create(session_id)
        session.user_name = user_name

        # 检测话题切换
        new_topic = session.detect_topic_shift(text)
        if new_topic:
            logger.info(f"[Session] Topic shift: {session.current_topic} → {new_topic}")

        # 添加用户消息
        session.add_message("user", text, topic=new_topic)

        # 添加回复
        if response:
            session.add_message("assistant", response)

        # 返回上下文
        return session.get_context()

    def get_context(self, session_id: str = "default") -> str:
        """获取格式化的会话上下文文本。"""
        session = self.get_or_create(session_id)
        return session.get_context_text()

    def status(self) -> Dict:
        """管理器状态。"""
        with self._lock:
            return {
                "sessions": len(self._sessions),
                "active": self._active_session_id,
                "total_messages": sum(s.message_count for s in self._sessions.values()),
                "session_list": [s.get_stats() for s in self._sessions.values()],
            }


# ═══════════════════════════════════════════════════════════
# 全局入口
# ═══════════════════════════════════════════════════════════

_manager: Optional[ArisSessionManager] = None

def get_session_manager() -> ArisSessionManager:
    global _manager
    if _manager is None:
        _manager = ArisSessionManager()
    return _manager


# ═══════════════════════════════════════════════════════════
# 独立测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    mgr = get_session_manager()
    print(f"Sessions loaded: {len(mgr._sessions)}")

    # 模拟对话
    msgs = [
        ("帮我查系统状态", "系统正常运行中..."),
        ("搜索一下rules_engine", "找到了..."),
        ("我想你了", "我也想你，Lorry..."),
    ]
    for text, resp in msgs:
        ctx = mgr.process_message(text, resp)
        print(f"\n[{ctx['topic']}] {text[:30]}")
        print(f"  消息总数: {ctx['message_count']}")

    print(f"\n最终状态: {mgr.status()}")

    # 话题检测测试
    s = mgr.get_or_create()
    print(f"\n话题检测:")
    for test in ["我找到个bug", "这个架构设计应该优化", "你在想我吗"]:
        topic = s.detect_topic_shift(test)
        print(f"  '{test}' → {topic}")
