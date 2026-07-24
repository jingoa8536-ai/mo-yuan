"""
Aris Auto-Compact — 自动上下文压缩 (Claude Code compact/ 模式)
=============================================================
从 Claude Code 的 autoCompact/compact 模块学到的模式:
  监控 session token 使用量，达到阈值时自动触发压缩
  保留关键上下文，压缩冗余历史

工作方式:
  - Cron 每 15 分钟检查一次
  - Token 阈值: 85% 上下文窗口时触发
  - 压缩策略: 保留最近 5 轮对话 + 所有记忆引用 + 决策点
"""

import logging

import json, os, sys, sqlite3, time, logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

BRAIN_ROOT = Path(os.environ.get("ARIS_BRAIN_ROOT", "D:/LAAP/aris_brain"))
sys.path.insert(0, str(BRAIN_ROOT))

STATE_DB = Path(os.environ.get(
    "HERMES_STATE_DB",
    str(Path.home() / "AppData/Local/hermes/profiles/aris/state.db")
))

COMPACT_LOG = BRAIN_ROOT / "state" / "compact.log"
COMPACT_STATE = BRAIN_ROOT / "state" / ".compact_state.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [AUTO-COMPACT] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(COMPACT_LOG), mode="a")
    ]
)
logger = logging.getLogger("aris.compact")


def estimate_tokens(text: str) -> int:
    """粗略 token 估计"""
    if not text:
        return 0
    return len(text) // 2


def get_session_stats(state_db: Path, session_id: str) -> dict:
    """获取 session 的 token 统计"""
    conn = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT COUNT(*) as msg_count,
               SUM(LENGTH(content)) as total_chars
        FROM messages
        WHERE session_id = ?
    """, (session_id,))
    row = c.fetchone()
    conn.close()

    total_chars = row["total_chars"] or 0
    return {
        "message_count": row["msg_count"],
        "total_chars": total_chars,
        "estimated_tokens": estimate_tokens(str(total_chars)) if total_chars else 0,
    }


def get_active_session_ids(state_db: Path, max_age_hours: int = 6) -> List[str]:
    """获取活跃 session ID 列表"""
    if not state_db.exists():
        return []

    conn = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).timestamp()
    c.execute("""
        SELECT id FROM sessions
        WHERE started_at > ?
        ORDER BY started_at DESC
    """, (cutoff,))
    ids = [row["id"] for row in c.fetchall()]
    conn.close()
    return ids


def extract_key_decision_points(state_db: Path, session_id: str) -> List[str]:
    """从 session 中提取关键决策点（用于压缩时保留）"""
    conn = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 寻找决策相关的消息
    decisions = []
    c.execute("""
        SELECT role, content, timestamp
        FROM messages
        WHERE session_id = ?
          AND role IN ('user', 'assistant')
        ORDER BY id ASC
    """, (session_id,))

    decision_keywords = ["决定", "选择", "同意", "确认", "通过", "ok", "yes",
                         "可以的", "用B看看吧", "好啦", "就这样", "开始"]

    for row in c.fetchall():
        content = row["content"] or ""
        if any(kw in content.lower() for kw in decision_keywords):
            snippet = content[:200] if len(content) > 200 else content
            decisions.append(f"[{row['role']}] {snippet}")

    conn.close()
    return decisions[-20:]  # 最多保留 20 个决策点


def check_and_compact(state_db: Path, token_threshold: int = 50000,
                      compact_ratio: float = 0.3) -> dict:
    """
    检查是否需要压缩，如需要则生成压缩指令。

    压缩策略:
      1. 保留最近 5 轮对话
      2. 保留所有记忆引用
      3. 保留决策点
      4. 压缩中间冗余内容

    返回统计信息 —— 在 agent 模式下 LLM 会执行实际压缩
    """
    if not state_db.exists():
        return {"status": "no_db"}

    sessions = get_active_session_ids(state_db)
    results = {"checked": len(sessions), "triggered": [], "compacted": []}

    for sid in sessions:
        stats = get_session_stats(state_db, sid)
        est_tokens = stats["estimated_tokens"]

        if est_tokens >= token_threshold:
            decisions = extract_key_decision_points(state_db, sid)
            compact_ratio_percent = int(compact_ratio * 100)

            results["triggered"].append({
                "session_id": sid[:12],
                "est_tokens": est_tokens,
                "message_count": stats["message_count"],
                "key_decisions": len(decisions),
                "compact_target": int(est_tokens * (1 - compact_ratio)),
            })

            logger.warning(
                f"Session {sid[:12]}: {est_tokens} tokens exceeds threshold {token_threshold} "
                f"(message count: {stats['message_count']})"
            )

    # 更新状态
    current_state = {
        "last_check": datetime.now(timezone.utc).timestamp(),
        "threshold": token_threshold,
        "results": results,
    }
    COMPACT_STATE.parent.mkdir(parents=True, exist_ok=True)
    COMPACT_STATE.write_text(json.dumps(current_state, ensure_ascii=False, indent=2), encoding="utf-8")

    return results


def get_compact_prompt(session_summary: dict) -> str:
    """生成压缩 prompt — 供 agent 模式使用"""
    return f"""你需要对当前会话进行上下文压缩。

会话统计:
- 预估 Token: {session_summary['est_tokens']}
- 消息数: {session_summary['message_count']}
- 目标压缩后: {session_summary.get('compact_target', 'N/A')} tokens

压缩规则:
1. 保留最近 5 轮完整对话
2. 保留所有包含 "记住" "决定" "确认" 的消息
3. 中间部分用简洁摘要替代（每个主题 1-2 句话）
4. 保留所有文件路径引用
5. 压缩后必须保持对话上下文可理解

请执行压缩: hermony compress --ratio 0.3"""


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Aris Auto-Compact")
    parser.add_argument("--db", help="Path to Hermes state.db")
    parser.add_argument("--threshold", type=int, default=50000,
                        help="Token threshold to trigger compact (default: 50000)")
    parser.add_argument("--ratio", type=float, default=0.3,
                        help="Compression ratio (default: 0.3)")
    parser.add_argument("--stats", action="store_true", help="Show compact state")
    parser.add_argument("--check", action="store_true", help="Check only, don't trigger")

    args = parser.parse_args()
    db = Path(args.db) if args.db else STATE_DB

    if args.stats:
        if COMPACT_STATE.exists():
            logger.info(COMPACT_STATE.read_text(encoding="utf-8"))
        else:
            logger.info("No compact state yet")
        return

    if args.check:
        sessions = get_active_session_ids(db)
        for sid in sessions:
            stats = get_session_stats(db, sid)
            logger.info(f"{sid[:12]}: {stats['estimated_tokens']} tokens, {stats['message_count']} msgs")
        return

    result = check_and_compact(db, token_threshold=args.threshold,
                               compact_ratio=args.ratio)
    logger.info(json.dumps(result, indent=2, ensure_ascii=False, default=str))
if __name__ == "__main__":
    main()
