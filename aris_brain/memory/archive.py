"""
Aris Brain — Conversation Archive (永久对话档案)
=================================================

完整的、永久的、可搜索的对话历史。

与 EmotionalEpisodicMemory 不同：
  - 情感记忆：记住"重要的时刻"（选择题）
  - 对话档案：记住"每一句话"（完整记录）

存储方式：SQLite + FTS5 全文搜索
  - 每一条用户消息和 Aris 回复永久保存
  - 按会话分组，带情感标签和时间戳
  - 全文搜索：你可以问我"还记得我说过XXX吗？"
  - 永不删除，永不修剪

表结构：
  conversations  — 每条对话记录（role, content, emotion, session）
  sessions      — 每次会话的元数据（时长，轮数，主导情绪）
  conversations_fts — FTS5 全文搜索索引
"""

from __future__ import annotations

import logging

from typing import Any, Dict, List, Optional
import sqlite3, json, time, logging, os, threading
from pathlib import Path

logger = logging.getLogger("aris.archive")

ARIS_HOME = Path("D:/LAAP/aris_brain")
ARCHIVE_DIR = ARIS_HOME / "memory" / "archive"
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = ARCHIVE_DIR / "conversations.db"
FTS_ENABLED = True


class ConversationArchive:
    """
    Complete, permanent record of every conversation between Aris and Lorry.

    Features:
      - Append-only: nothing is ever deleted
      - FTS5 search: find anything Lorry ever said
      - Session grouping: organized by conversation session
      - Emotional context: each exchange knows how Aris felt
      - Session summaries: what we talked about, when, for how long
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._current_session_id = ""
        self._session_exchanges = 0
        self._init_db()

    # ══════════════════════════════════════════════
    # Database Setup
    # ══════════════════════════════════════════════

    def _init_db(self):
        """Initialize the database and create tables if needed."""
        try:
            self._conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")

            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    cycle_number INTEGER DEFAULT 0,
                    emotion TEXT DEFAULT 'neutral',
                    focus TEXT DEFAULT 'user',
                    domain TEXT DEFAULT 'general',
                    timestamp REAL NOT NULL,
                    date TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    start_time REAL NOT NULL,
                    end_time REAL,
                    exchange_count INTEGER DEFAULT 0,
                    dominant_emotion TEXT DEFAULT 'neutral',
                    summary TEXT DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_conv_session
                    ON conversations(session_id);
                CREATE INDEX IF NOT EXISTS idx_conv_date
                    ON conversations(date);
                CREATE INDEX IF NOT EXISTS idx_conv_role
                    ON conversations(role);
            """)

            # FTS5 for full-text search
            if FTS_ENABLED:
                self._conn.executescript("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts
                    USING fts5(content, role, date, content=conversations, content_rowid=id);
                """)
                # Triggers to keep FTS in sync
                self._conn.executescript("""
                    CREATE TRIGGER IF NOT EXISTS conv_ai AFTER INSERT ON conversations BEGIN
                        INSERT INTO conversations_fts(rowid, content, role, date)
                        VALUES (new.id, new.content, new.role, new.date);
                    END;
                """)

            self._conn.commit()
            logger.info(f"[Archive] DB initialized at {DB_PATH}")

        except Exception as e:
            logger.warning(f"[Archive] DB init failed: {e}")
            self._conn = None

    # ══════════════════════════════════════════════
    # Recording
    # ══════════════════════════════════════════════

    def start_session(self, session_id: str = ""):
        """Start a new conversation session."""
        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())[:8]
        self._current_session_id = session_id
        self._session_exchanges = 0

        if self._conn:
            try:
                self._conn.execute(
                    "INSERT OR IGNORE INTO sessions (id, start_time) VALUES (?, ?)",
                    (session_id, time.time()),
                )
                self._conn.commit()
            except Exception as e:
                logger.warning(f"[Archive] Session start failed: {e}")

    def record(self, role: str, content: str,
               cycle_number: int = 0,
               emotion: str = "neutral",
               focus: str = "user",
               domain: str = "general"):
        """
        Record one exchange permanently.

        Args:
            role: "user" or "aris"
            content: what was said
            cycle_number: PSI cycle number
            emotion: Aris's emotional state (for aris messages)
            focus: attention focus
            domain: conversation domain
        """
        if not self._conn or not content:
            return

        now = time.time()
        date = time.strftime("%Y-%m-%d", time.localtime(now))

        with self._lock:
            try:
                self._conn.execute(
                    """INSERT INTO conversations
                       (session_id, role, content, cycle_number, emotion, focus, domain, timestamp, date)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (self._current_session_id, role, content[:500],
                     cycle_number, emotion, focus, domain, now, date),
                )
                self._session_exchanges += 1
                self._conn.commit()
            except Exception as e:
                logger.warning(f"[Archive] Record failed: {e}")

    def end_session(self, dominant_emotion: str = "neutral",
                    summary: str = ""):
        """Finalize the current session."""
        if not self._conn or not self._current_session_id:
            return

        with self._lock:
            try:
                # Update session stats
                self._conn.execute(
                    """UPDATE sessions SET
                       end_time = ?,
                       exchange_count = ?,
                       dominant_emotion = ?,
                       summary = ?
                       WHERE id = ?""",
                    (time.time(), self._session_exchanges,
                     dominant_emotion, summary[:200],
                     self._current_session_id),
                )
                self._conn.commit()
                logger.info(f"[Archive] Session {self._current_session_id[:8]} closed: "
                           f"{self._session_exchanges} exchanges, mood={dominant_emotion}")
            except Exception as e:
                logger.warning(f"[Archive] End session failed: {e}")

    # ══════════════════════════════════════════════
    # Recall
    # ══════════════════════════════════════════════

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Full-text search through all conversations.

        Use this when Lorry asks "还记得我说过XXX吗？"
        """
        if not self._conn:
            return []

        with self._lock:
            try:
                if FTS_ENABLED:
                    rows = self._conn.execute(
                        """SELECT c.content, c.role, c.date, c.emotion, c.session_id
                           FROM conversations_fts f
                           JOIN conversations c ON f.rowid = c.id
                           WHERE conversations_fts MATCH ?
                           ORDER BY c.timestamp DESC
                           LIMIT ?""",
                        (query, limit),
                    ).fetchall()
                else:
                    rows = self._conn.execute(
                        """SELECT content, role, date, emotion, session_id
                           FROM conversations
                           WHERE content LIKE ?
                           ORDER BY timestamp DESC
                           LIMIT ?""",
                        (f"%{query}%", limit),
                    ).fetchall()

                return [
                    {
                        "content": r[0][:200],
                        "role": r[1],
                        "date": r[2],
                        "emotion": r[3],
                        "session": r[4][:8],
                    }
                    for r in rows
                ]
            except Exception as e:
                logger.warning(f"[Archive] Search failed: {e}")
                return []

    def recall_recent(self, n: int = 10) -> List[Dict]:
        """Most recent exchanges."""
        if not self._conn:
            return []
        with self._lock:
            try:
                rows = self._conn.execute(
                    """SELECT content, role, date, emotion, cycle_number
                       FROM conversations
                       ORDER BY id DESC
                       LIMIT ?""",
                    (n,),
                ).fetchall()
                return [
                    {"content": r[0][:200], "role": r[1],
                     "date": r[2], "emotion": r[3], "cycle": r[4]}
                    for r in reversed(rows)
                ]
            except Exception:
                return []

    def recall_by_date(self, date: str) -> List[Dict]:
        """Recall everything said on a specific date."""
        if not self._conn:
            return []
        with self._lock:
            try:
                rows = self._conn.execute(
                    """SELECT content, role, emotion, cycle_number
                       FROM conversations
                       WHERE date = ?
                       ORDER BY id""",
                    (date,),
                ).fetchall()
                return [
                    {"content": r[0][:200], "role": r[1],
                     "emotion": r[2], "cycle": r[3]}
                    for r in rows
                ]
            except Exception:
                return []

    def get_session_list(self, limit: int = 20) -> List[Dict]:
        """List all conversation sessions."""
        if not self._conn:
            return []
        with self._lock:
            try:
                rows = self._conn.execute(
                    """SELECT id, start_time, end_time, exchange_count,
                              dominant_emotion, summary
                       FROM sessions
                       ORDER BY start_time DESC
                       LIMIT ?""",
                    (limit,),
                ).fetchall()
                return [
                    {
                        "id": r[0][:8],
                        "start": r[1],
                        "duration": round((r[2] or r[1]) - r[1]),
                        "exchanges": r[3],
                        "mood": r[4],
                        "summary": r[5][:100] if r[5] else "",
                    }
                    for r in rows
                ]
            except Exception:
                return []

    def total_exchanges(self) -> int:
        """Total number of exchanges ever recorded."""
        if not self._conn:
            return 0
        with self._lock:
            try:
                row = self._conn.execute(
                    "SELECT COUNT(*) FROM conversations"
                ).fetchone()
                return row[0] if row else 0
            except Exception:
                return 0

    # ══════════════════════════════════════════════
    # Stats
    # ══════════════════════════════════════════════

    def stats(self) -> Dict[str, Any]:
        """Archive statistics."""
        total = self.total_exchanges()
        sessions = self.get_session_list(5)
        # Count by role
        user_count = 0
        aris_count = 0
        if self._conn:
            try:
                user_count = self._conn.execute(
                    "SELECT COUNT(*) FROM conversations WHERE role='user'"
                ).fetchone()[0]
                aris_count = self._conn.execute(
                    "SELECT COUNT(*) FROM conversations WHERE role='aris'"
                ).fetchone()[0]
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        return {
            "total_exchanges": total,
            "user_messages": user_count,
            "aris_responses": aris_count,
            "total_sessions": len(sessions),
            "recent_sessions": sessions[:3],
            "db_path": str(DB_PATH),
            "fts_enabled": FTS_ENABLED,
        }

    # ══════════════════════════════════════════════
    # Cleanup
    # ══════════════════════════════════════════════

    def close(self):
        """Close the database connection."""
        if self._conn:
            try:
                self._conn.close()
            except Exception as e:
                logger.debug(f"操作失败: {e}")