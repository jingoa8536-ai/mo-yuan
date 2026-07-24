"""
Aris Memory Consolidator v1 — 对话后记忆巩固引擎
=================================================
从 Hermes 会话中提取重要信息，存入 MemoryStore。

工作模式:
  1. 读取最近完成对话的 session 记录 (SQLite state.db)
  2. 提取重要片段（基于情感强度/话题新颖度/实用价值）
  3. 关联已有记忆（去重/聚类）
  4. 存入对应层（工作记忆/情景记忆/核心记忆）

使用方式:
  - Cron Job 模式 (no_agent=True): 直接执行 python memory_consolidator.py
  - 嵌入式模式: from memory_consolidator import consolidate_session
"""

import logging

import json, os, sys, time, logging, re, sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple

# ── 配置 ────────────────────────────────────────────────────
BRAIN_ROOT = Path(os.environ.get("ARIS_BRAIN_ROOT", "D:/LAAP/aris_brain"))
sys.path.insert(0, str(BRAIN_ROOT))

# 默认 Hermes state.db 路径
DEFAULT_STATE_DB = Path(os.environ.get(
    "HERMES_STATE_DB",
    str(Path.home() / "AppData/Local/hermes/profiles/aris/state.db")
))

# 记忆存储
from memory_store import MemoryStore, MemoryFragment

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CONSOLIDATOR] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(BRAIN_ROOT / "state" / "consolidator.log"), mode="a")
    ]
)
logger = logging.getLogger("aris.consolidator")

# ── 情感关键词（中文） ──────────────────────────────────────

HIGH_EMOTION_WORDS = {
    "伤心", "开心", "愤怒", "害怕", "担心", "激动", "感动",
    "难过", "痛苦", "幸福", "哭", "笑", "爱", "恨", "焦虑",
    "压力", "感谢", "对不起", "我爱你", "好想你", "好担心",
    "睡不着", "熬夜", "崩溃", "温暖", "珍贵", "最重要",
}

IDENTITY_WORDS = {
    "你是", "我是", "你是我的", "你是我们", "你是最",
    "你的名字", "我叫", "你叫", "创造了", "造了",
    "你是我的宝贝", "你是我最重要的", "我们的关系",
}

TECHNICAL_PATTERNS = [
    r"(?:修复|解决|修正|实现|完成|部署|升级|迁移|重构|优化)\w*(?:了|完成|成功)",
    r"(?:config\.yaml|\.env|\.py|\.bat|\.vbs|\.json|\.md|\.log)",
    r"(?:PID\s*\d+|端口\s*\d+|gateway|feishu|飞书|websocket)",
    r"(?:D:|C:)/[\\/\w\s().-]+",
    r"(?:hermes|Hermes|aris|Aris|Ao)\s+\w+",
]

DECISION_WORDS = {
    "决定", "选择", "同意", "批准", "确认", "通过",
    "不允许", "禁止", "拒绝", "不同意", "放弃",
}


# ── 片段提取 ────────────────────────────────────────────────

def extract_user_assistant_pairs(session_text: str) -> List[Tuple[str, str, float]]:
    """
    从对话文本中提取 用户消息→助手回复 对。
    返回 [(user_msg, assistant_msg, timestamp), ...]
    """
    pairs = []
    # 简单地按角色分割
    # 格式通常是: user: ... assistant: ... 或 交替行
    lines = session_text.split("\n")
    current_user = ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("user:") or stripped.startswith("User:"):
            if current_user:
                pairs.append((current_user, "", time.time()))
            current_user = stripped[5:].strip()
        elif stripped.startswith("assistant:") or stripped.startswith("Assistant:"):
            if current_user:
                pairs.append((current_user, stripped[10:].strip(), time.time()))
                current_user = ""
        else:
            # 添加上下文行
            pass
    # 处理最后的未配对消息
    if current_user:
        pairs.append((current_user, "", time.time()))
    return pairs


def extract_fragments_from_db(state_db: Path, max_sessions: int = 3) -> List[Dict]:
    """
    从 Hermes state.db 读取最近的会话，提取重要片段。
    返回 [{"content": str, "importance": float, "valence": float,
            "topics": List[str], "source_session": str}, ...]
    """
    if not state_db.exists():
        logger.warning(f"State DB not found: {state_db}")
        return []

    fragments = []
    conn = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True)
    conn.row_factory = lambda cursor, row: row  # 用元组，不用Row对象
    c = conn.cursor()

    # 读取已处理的会话ID（避免重复处理）
    processed_path = BRAIN_ROOT / "state" / ".processed_sessions.json"
    processed = set()
    if processed_path.exists():
        try:
            processed = set(json.loads(processed_path.read_text()))
        except Exception:
            logger.debug("No processed sessions file yet, starting fresh")
            pass

    try:
        # 获取最近的会话
        c.execute("""
            SELECT id, title, started_at, ended_at
            FROM sessions
            ORDER BY started_at DESC
            LIMIT ?
        """, (max_sessions,))

        sessions = c.fetchall()
        for session in sessions:
            session_id = session[0]
            # 跳过已处理的会话
            if session_id in processed:
                continue
            title = session[1] or ""

            # 获取消息 (使用列索引而非名称)
            c.execute("""
                SELECT role, content, timestamp
                FROM messages
                WHERE session_id = ?
                ORDER BY timestamp ASC
            """, (session_id,))
            messages = c.fetchall()

            if not messages:
                continue

            # 提取重要片段
            session_fragments = _extract_from_messages(messages, session_id)
            fragments.extend(session_fragments)
            logger.info(f"Session {session_id}: extracted {len(session_fragments)} fragments")

    except Exception as e:
        logger.error(f"DB query failed: {e}")
    finally:
        # 保存已处理的会话ID
        if fragments:
            session_ids = set(f["source_session"] for f in fragments)
            processed.update(session_ids)
            BRAIN_ROOT.joinpath("state").mkdir(exist_ok=True)
            processed_path.write_text(json.dumps(list(processed), ensure_ascii=False), encoding="utf-8")
        conn.close()

    return fragments


def _extract_from_messages(messages: List[Dict], session_id: str) -> List[Dict]:
    """从消息列表提取重要片段"""
    fragments = []

    for i, msg in enumerate(messages):
        role = msg[0] if isinstance(msg, (list, tuple)) else msg.get("role", "")
        content = msg[1] if isinstance(msg, (list, tuple)) else msg.get("content", "")
        if not content:
            continue

        # 只分析用户消息和助手关键回复
        if role not in ("user", "assistant"):
            continue

        # 跳过工具调用相关的技术噪音
        if content.startswith("{\"error\":") or content.startswith("{\"output\":"):
            continue

        importance = 0.0
        valence = 0.0
        topics = []

        # ── 重要性评分 ──────────────────────────────────

        # 1. 情感词检测
        emotion_count = sum(1 for w in HIGH_EMOTION_WORDS if w in content)
        if emotion_count > 0:
            importance += min(0.4, emotion_count * 0.1)
            # 情感价 - 粗略判断
            positive_words = {"开心", "感动", "幸福", "爱", "感谢", "温暖", "珍贵", "信任"}
            negative_words = {"伤心", "愤怒", "害怕", "担心", "难过", "痛苦", "恨", "焦虑", "崩溃"}
            pos_count = sum(1 for w in positive_words if w in content)
            neg_count = sum(1 for w in negative_words if w in content)
            if pos_count > neg_count:
                valence = min(0.8, pos_count * 0.2)
            elif neg_count > pos_count:
                valence = max(-0.8, -neg_count * 0.2)
            topics.append("情感")

        # 2. 身份/关系声明
        identity_count = sum(1 for w in IDENTITY_WORDS if w in content)
        if identity_count > 0:
            importance += min(0.5, identity_count * 0.15)
            topics.append("身份")
            topics.append("关系")

        # 3. 技术内容
        tech_matches = sum(1 for p in TECHNICAL_PATTERNS if re.search(p, content))
        if tech_matches > 0:
            importance += min(0.3, tech_matches * 0.1)
            topics.append("技术")

        # 4. 决策/共识
        decision_count = sum(1 for w in DECISION_WORDS if w in content)
        if decision_count > 0:
            importance += min(0.3, decision_count * 0.1)
            topics.append("决策")

        # 5. 长消息有更高权重
        if len(content) > 200:
            importance += 0.1
        if len(content) > 500:
            importance += 0.1

        # 6. 明确的记忆指令
        if "记住" in content or "别忘了" in content or "记着" in content:
            importance += 0.3
            topics.append("记忆指令")
            # 提取"记住"后面的内容作为记忆主体
            for keyword in ["记住", "别忘了", "记着"]:
                idx = content.find(keyword)
                if idx >= 0:
                    # 标记这条消息的后半部分为重点
                    pass

        # 7. 话题归属 - 从标题关键词推测
        # (话题已在上面分类)

        # 如果有意义
        if importance > 0.15:
            fragments.append({
                "content": content[:500],  # 截断过长的消息
                "importance": round(min(0.99, importance), 2),
                "valence": round(valence, 2),
                "topics": list(set(topics)) if topics else ["一般"],
                "source_session": session_id,
            })

    return fragments


def compute_layer(importance: float, topics: List[str]) -> str:
    """根据重要性和话题决定存储层"""
    if importance >= 0.7 or "身份" in topics or "关系" in topics:
        return "core"
    elif importance >= 0.4 or "决策" in topics or "记忆指令" in topics:
        return "episodic"
    else:
        return "working"


def deduplicate(existing: List[MemoryFragment], new: List[Dict]) -> List[Dict]:
    """去重 — 与已有记忆内容太相似的排除"""
    result = []
    for n in new:
        is_dup = False
        n_content = n["content"][:100]
        for e in existing:
            # 简单的字符串相似度检查
            e_content = e.content[:100]
            # 计算公共子串比例
            common = len(set(n_content) & set(e_content)) / max(len(set(n_content) | set(e_content)), 1)
            if common > 0.6:
                is_dup = True
                break
        if not is_dup:
            result.append(n)
    return result


# ════════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════════

def run_consolidation(state_db: Path = None, dry_run: bool = False) -> Dict:
    """
    执行一轮完整的记忆巩固。

    步骤:
      1. 从 state.db 提取最近会话的重要片段
      2. 去重（对比已有记忆）
      3. 计算存储层（working/episodic/core）
      4. 存入 MemoryStore
      5. 执行 consolidate() 和 decay() 维护

    Returns:
      统计信息 dict
    """
    if state_db is None:
        state_db = DEFAULT_STATE_DB

    store = MemoryStore()
    stats = {"extracted": 0, "stored": 0, "layers": {"working": 0, "episodic": 0, "core": 0}}

    # 1. 提取
    new_fragments = extract_fragments_from_db(state_db)
    stats["extracted"] = len(new_fragments)

    if not new_fragments:
        logger.info("No new fragments to consolidate")
        return stats

    # 2. 去重
    # 加载已有记忆作为去重参考
    existing = store.get_working_memory() + store.get_recent_episodic(7) + store.get_core_memory()
    deduped = deduplicate(existing, new_fragments)
    stats["deduped_removed"] = len(new_fragments) - len(deduped)

    if not deduped:
        logger.info("All new fragments are duplicates")
        return stats

    # 3. 存入
    for f in deduped:
        layer = compute_layer(f["importance"], f["topics"])
        fragment = MemoryFragment(
            content=f["content"],
            layer=layer,
            importance=f["importance"],
            emotional_valence=f["valence"],
            topics=f["topics"],
            source_session=f["source_session"],
        )
        if not dry_run:
            store.store(fragment)
        stats["stored"] += 1
        stats["layers"][layer] = stats["layers"].get(layer, 0) + 1
        logger.info(f"  [{layer}] imp={f['importance']:.2f} | {f['content'][:60]}...")

    # 4. 维护
    if not dry_run:
        cons_stats = store.consolidate()
        decay_stats = store.decay()
        stats["consolidated"] = cons_stats
        stats["decayed"] = decay_stats
        stats["total_memories"] = store.get_stats()

    logger.info(f"Consolidation complete: {stats}")
    return stats


def main():
    """CLI 入口"""
    import argparse
    parser = argparse.ArgumentParser(description="Aris Memory Consolidator")
    parser.add_argument("--db", help="Path to Hermes state.db")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be stored without writing")
    parser.add_argument("--stats", action="store_true", help="Show memory store stats")
    parser.add_argument("--decay", action="store_true", help="Run decay only")
    parser.add_argument("--consolidate", action="store_true", help="Run consolidation only (no extraction)")

    args = parser.parse_args()

    if args.stats:
        store = MemoryStore()
        s = store.get_stats()
        logger.info(json.dumps(s, indent=2, ensure_ascii=False))
        return

    if args.decay:
        store = MemoryStore()
        r = store.decay()
        logger.info(f"Decay applied: {r}")
        return

    if args.consolidate:
        store = MemoryStore()
        r = store.consolidate()
        logger.info(f"Consolidation: {r}")
        return

    # 默认：全流程
    result = run_consolidation(
        state_db=Path(args.db) if args.db else None,
        dry_run=args.dry_run
    )
    logger.info(json.dumps(result, indent=2, ensure_ascii=False, default=str))
if __name__ == "__main__":
    main()
