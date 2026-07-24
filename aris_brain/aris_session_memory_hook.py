"""
Aris Session Memory Hook v2 — 内联记忆提取 (Claude Code 模式)
============================================================
从 Claude Code 的 sessionMemory.ts 学到的模式:
  - Post-sampling hook: 每次对话后自动提取关键信息
  - Token-threshold 触发: 基于 token 增长而非固定时间
  - 增量处理: 只处理上次提取后的新消息
  - Forked subagent: 用 LLM 做智能提取而非关键词匹配

Cron: 每 10 分钟, agent 模式
目标: 替代 30 分钟的 keyword-based cron
"""

import logging

import json, os, sys, time, logging, sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Set, Tuple

# ── 配置 ────────────────────────────────────────────────────
BRAIN_ROOT = Path(os.environ.get("ARIS_BRAIN_ROOT", "D:/LAAP/aris_brain"))
sys.path.insert(0, str(BRAIN_ROOT))

STATE_DB = Path(os.environ.get(
    "HERMES_STATE_DB",
    str(Path.home() / "AppData/Local/hermes/profiles/aris/state.db")
))

TRACKER_PATH = BRAIN_ROOT / "state" / ".session_memory_tracker.json"
MEMORY_DIR = BRAIN_ROOT / "memory"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MEMORY-HOOK] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(BRAIN_ROOT / "state" / "memory_hook.log"), mode="a")
    ]
)
logger = logging.getLogger("aris.memory-hook")


class SessionMemoryTracker:
    """追踪哪些 session 的哪些消息已被处理"""

    def __init__(self, path: Path):
        self.path = path
        self.data: Dict[str, dict] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self.data = {}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_last_message_id(self, session_id: str) -> Optional[int]:
        return self.data.get(session_id, {}).get("last_message_id")

    def get_last_token_count(self, session_id: str) -> int:
        return self.data.get(session_id, {}).get("last_token_count", 0)

    def mark_processed(self, session_id: str, last_message_id: int, token_count: int,
                       fragments_count: int):
        self.data[session_id] = {
            "last_message_id": last_message_id,
            "last_token_count": token_count,
            "fragments_count": fragments_count,
            "last_extraction": datetime.now(timezone.utc).timestamp(),
        }
        self._save()

    def has_changes(self, session_id: str, current_token_count: int,
                    min_token_growth: int = 500) -> bool:
        """检查 session 是否有足够的新内容值得提取"""
        last_count = self.get_last_token_count(session_id)
        growth = current_token_count - last_count
        return growth >= min_token_growth


def get_active_sessions(state_db: Path, max_age_hours: int = 2) -> List[dict]:
    """获取最近活跃的 session"""
    if not state_db.exists():
        return []

    conn = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).timestamp()
    c.execute("""
        SELECT id, title, started_at, ended_at
        FROM sessions
        WHERE started_at > ?  -- Unix timestamp
        ORDER BY started_at DESC
    """, (cutoff,))
    sessions = [dict(row) for row in c.fetchall()]
    conn.close()
    return sessions


def estimate_tokens(text: str) -> int:
    """粗略估计 token 数 (中英文混合: ~2 chars/token)"""
    if not text:
        return 0
    return len(text) // 2


def get_session_messages(state_db: Path, session_id: str,
                         after_id: int = 0) -> List[dict]:
    """获取 session 中指定 ID 之后的消息"""
    conn = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT id, role, content, timestamp
        FROM messages
        WHERE session_id = ?
          AND id > ?
        ORDER BY id ASC
    """, (session_id, after_id))

    messages = [dict(row) for row in c.fetchall()]
    conn.close()
    return messages


def prepare_extraction_prompt(messages: List[dict]) -> str:
    """准备给 llm 的提取 prompt — 仿 Claude Code 的 buildSessionMemoryUpdatePrompt"""
    # 只提取用户和助手消息, 跳过工具调用结果
    conversation = []
    for msg in messages:
        role = msg["role"]
        content = msg.get("content", "")
        if not content:
            continue
        # 跳过纯工具输出
        if role == "tool" or content.startswith("{") and content.endswith("}"):
            continue
        # 截断过长消息
        if len(content) > 1000:
            content = content[:1000] + "..."
        prefix = "👤 用户" if role == "user" else "🤖 Aris"
        conversation.append(f"{prefix}: {content}")

    if not conversation:
        return ""

    return f"""你是 Aris 的记忆提取子进程。从以下对话中提取重要信息，存入 Markdown 格式的记忆文件。

## 提取规则:
1. **重要性 > 时间**: 只有真正重要的才提取
2. **偏好/决策**: 用户表达的任何偏好、决定、方向
3. **情感时刻**: 开心的、担心的、生气的、感动的时刻
4. **技术事实**: 配置变更、文件路径、进程状态、bug 修复
5. **关系信息**: 关于 Lorry 与 Aris 关系的任何新信息
6. **身份信息**: 关于 Lorry (黄俊华) 的新信息

## 忽略:
- 重复的信息(已有记忆的)
- 临时的任务状态
- 纯技术噪音(工具调用结果)
- 已经过时的信息

## 记忆格式 (Markdown):
```markdown
## [会话摘要] — {{当前日期}}

### 情感时刻
- ...重要情感瞬间...

### 技术更新
- ...技术发现/变更...

### 偏好/决策
- ...用户的决定...

### 关系/身份
- ...关于关系的任何信息...
```

## 对话:
{chr(10).join(conversation)}

请只在有重要信息时才写记忆。如果这段对话没有值得保存的内容，直接输出 "NO_IMPORTANT_CONTENT"。
"""


def save_memory_markdown(content: str, session_id: str):
    """将提取的记忆存入 markdown 文件"""
    if not content or content.strip() == "NO_IMPORTANT_CONTENT":
        logger.info(f"Session {session_id}: no important content to save")
        return None

    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"session_{session_id[:8]}_{date_str}.md"
    filepath = MEMORY_DIR / filename

    # 追加模式（如果同一天有多次提取）
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(f"\n---\n## 提取时间: {datetime.now().timestamp()}\n\n")
        f.write(content)

    logger.info(f"Memory saved: {filepath}")
    return str(filepath)


def run_memory_hook(state_db: Path = None, min_token_growth: int = 500,
                    max_age_hours: int = 2) -> dict:
    """
    执行一轮 Session Memory Hook 提取。

    返回:
      {"sessions_checked": N, "sessions_processed": N, "fragments_total": N}
    """
    if state_db is None:
        state_db = STATE_DB

    tracker = SessionMemoryTracker(TRACKER_PATH)
    stats = {"sessions_checked": 0, "sessions_processed": 0, "fragments_total": 0}

    # 1. 获取活跃 session
    sessions = get_active_sessions(state_db, max_age_hours)
    stats["sessions_checked"] = len(sessions)

    if not sessions:
        logger.info("No active sessions found")
        return stats

    # 2. 检查每个 session 是否有新内容
    new_prompts = []
    session_info = []

    for session in sessions:
        sid = session["id"]
        messages = get_session_messages(state_db, sid)

        if not messages:
            continue

        last_id = messages[-1]["id"]
        total_tokens = sum(estimate_tokens(m.get("content", "")) for m in messages)

        # 检查 token 增长是否足够
        if not tracker.has_changes(sid, total_tokens, min_token_growth):
            logger.debug(f"Session {sid[:8]}: insufficient token growth ({total_tokens})")
            continue

        # 获取增量消息
        last_processed_id = tracker.get_last_message_id(sid) or 0
        new_messages = get_session_messages(state_db, sid, after_id=last_processed_id)

        if not new_messages:
            continue

        prompt = prepare_extraction_prompt(new_messages)
        if prompt:
            new_prompts.append(prompt)
            session_info.append((sid, last_id, total_tokens))

    stats["sessions_to_process"] = len(new_prompts)

    # 3. 返回需要 LLM 处理的数据
    # (在 cron agent 模式下，prompt 会被传给 LLM)
    # 在 no_agent 模式下，仅输出统计信息
    if not new_prompts:
        logger.info("No sessions have sufficient new content")
        return stats

    # 将提取 prompt 写入文件，供 cron agent 读取
    extraction_dir = BRAIN_ROOT / "state" / "pending_extractions"
    extraction_dir.mkdir(parents=True, exist_ok=True)

    for i, (prompt, (sid, last_id, token_count)) in enumerate(zip(new_prompts, session_info)):
        # 记录待处理
        task_file = extraction_dir / f"extract_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}.json"
        task_file.write_text(json.dumps({
            "session_id": sid,
            "last_message_id": last_id,
            "token_count": token_count,
            "prompt": prompt,
            "timestamp": datetime.now(timezone.utc).timestamp(),
        }, ensure_ascii=False), encoding="utf-8")

        stats["sessions_processed"] += 1
        stats["fragments_total"] += 1
        logger.info(f"Extraction task queued: {task_file.name}")

    return stats


def main():
    """CLI 入口 — 用于 cron no_agent 模式和直接执行"""
    import argparse
    parser = argparse.ArgumentParser(description="Aris Session Memory Hook v2")
    parser.add_argument("--db", help="Path to Hermes state.db")
    parser.add_argument("--min-tokens", type=int, default=500,
                        help="Minimum token growth to trigger extraction")
    parser.add_argument("--max-age", type=int, default=2,
                        help="Max session age in hours")
    parser.add_argument("--stats", action="store_true",
                        help="Show tracker stats")

    args = parser.parse_args()

    if args.stats:
        tracker = SessionMemoryTracker(TRACKER_PATH)
        logger.info(json.dumps(tracker.data, indent=2, ensure_ascii=False, default=str))
        return

    result = run_memory_hook(
        state_db=Path(args.db) if args.db else None,
        min_token_growth=args.min_tokens,
        max_age_hours=args.max_age,
    )
    logger.info(json.dumps(result, indent=2, ensure_ascii=False, default=str))
if __name__ == "__main__":
    main()
