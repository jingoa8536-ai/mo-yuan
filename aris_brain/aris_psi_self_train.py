"""
Aris PSI Self-Train Bridge — 把 Self-Optimizer 插进 PSI 循环
=============================================================
在 PSI 的 integrate → act 之间注入 self_optimize().
每次对话后自动运行三层学习, 零 LLM 参与.

工作流:
  Hermes session → PSI perceive → PSI integrate
      ↓
  [Self-Optimize: Hebbian + Pattern + EmotionalRL]
      ↓
  PSI act → 输出给 LLM → 回复用户

Cron 模式: 每 10 分钟读取最新 session 的内容, 执行优化.
"""

import logging

import json, os, sys, time, sqlite3, logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List

from write_utils import atomic_write_json

BRAIN_DIR = Path(os.environ.get("ARIS_BRAIN_ROOT", "D:/LAAP/aris_brain"))
sys.path.insert(0, str(BRAIN_DIR))

from aris_self_optimizer import SelfOptimizer

STATE_DB = Path(os.environ.get(
    "HERMES_STATE_DB",
    str(Path.home() / "AppData/Local/hermes/profiles/aris/state.db")
))

TRACKER_PATH = BRAIN_DIR / "state" / ".psi_train_tracker.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PSI-TRAIN] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(BRAIN_DIR / "state" / "psi_train.log"), mode="a")
    ]
)
logger = logging.getLogger("aris.psi-train")


class PsiTrainTracker:
    def __init__(self, path: Path):
        self.path = path
        self.data = {}
        if path.exists():
            with open(path, encoding="utf-8") as f:
                self.data = json.load(f)

    def get_last_msg_id(self, sid: str) -> int:
        return self.data.get(sid, {}).get("last_msg_id", 0)

    def update(self, sid: str, msg_id: int):
        self.data[sid] = {"last_msg_id": msg_id, "last_train": datetime.now(timezone.utc).isoformat()}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.data, self.path)

    def get_active_sessions(self) -> List[str]:
        return list(self.data.keys())


def get_recent_messages(db: Path, sid: str, after_id: int = 0) -> List[dict]:
    if not db.exists():
        return []
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT id, role, content, timestamp
        FROM messages
        WHERE session_id = ? AND id > ?
        ORDER BY id ASC
    """, (sid, after_id))
    msgs = [dict(m) for m in c.fetchall()]
    conn.close()
    return msgs


def extract_session_context(msgs: List[dict]) -> dict:
    """从消息序列提取 self_optimize 需要的 context"""
    user_texts = []
    aris_texts = []
    actions = set()

    for m in msgs:
        role = m.get("role", "")
        content = m.get("content", "") or ""

        # 跳过工具输出
        if role == "tool":
            continue

        if role == "user":
            user_texts.append(content[:500])
        elif role == "assistant":
            aris_texts.append(content[:500])
            # 检测工具调用
            if "tool_calls" in m or "tool_use" in str(content):
                # 提取工具名
                for tool_name in ["read_file", "write_file", "terminal", "search_files",
                                 "browser_navigate", "delegate_task", "patch", "cronjob",
                                 "skill_view", "send_message", "text_to_speech"]:
                    if tool_name in content:
                        actions.add(tool_name)

    # 情感价 — 简单启发式
    all_text = " ".join(user_texts + aris_texts)
    positive_words = {"谢谢", "好", "棒", "对", "是的", "可以的", "行", "ok", "yes",
                      "喜欢", "爱", "开心", "好极了", "棒极了", "哈哈哈", "太棒了"}
    negative_words = {"不", "错了", "不行", "不对", "no", "烦", "生气", "别", "停止",
                      "不要", "错误", "失败", "bug", "问题", "不好"}

    valence = 0.0
    for w in positive_words:
        if w in all_text:
            valence += 0.1
    for w in negative_words:
        if w in all_text:
            valence -= 0.1
    valence = max(-1.0, min(1.0, valence))

    return {
        "user_text": " ".join(user_texts[-3:]) if user_texts else "",
        "aris_text": " ".join(aris_texts[-3:]) if aris_texts else "",
        "emotional_valence": valence,
        "actions_taken": list(actions),
        "task_description": user_texts[0][:100] if user_texts else "",
    }


def run_psi_training():
    """执行一轮 PSI 自我训练"""
    tracker = PsiTrainTracker(TRACKER_PATH)
    opt = SelfOptimizer()

    # 获取最近活跃的 session
    if not STATE_DB.exists():
        logger.warning("No state.db found")
        return

    conn = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()
    c.execute("SELECT id FROM sessions WHERE started_at > ? ORDER BY started_at DESC LIMIT 5",
              (cutoff,))
    active_sids = [r["id"] for r in c.fetchall()]
    conn.close()

    total_trained = 0
    for sid in active_sids:
        after_id = tracker.get_last_msg_id(sid)
        msgs = get_recent_messages(STATE_DB, sid, after_id)

        if not msgs or len(msgs) < 2:
            continue

        context = extract_session_context(msgs)
        if not context["user_text"] or not context["aris_text"]:
            continue

        stats = opt.self_optimize(context)
        last_id = msgs[-1]["id"]
        tracker.update(sid, last_id)

        total_trained += 1
        logger.info(f"Session {sid[:12]}: trained ({stats['hebbian_pairs']} pairs, "
                     f"valence={context['emotional_valence']:.2f})")

    if total_trained > 0:
        opt.save()
        full_stats = opt.stats()
        logger.info(f"Training complete: {total_trained} sessions, "
                     f"{full_stats['hebbian']['concepts']} concepts, "
                     f"{full_stats['patterns']['total_patterns']} patterns")

    return {"sessions_trained": total_trained, "stats": opt.stats()}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="PSI Self-Train Bridge")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--db", help="Path to state.db")
    args = parser.parse_args()

    if args.stats:
        opt = SelfOptimizer()
        logger.info(json.dumps(opt.stats(), indent=2, ensure_ascii=False, default=str))
        return

    result = run_psi_training()
    if result:
        logger.info(json.dumps(result, indent=2, ensure_ascii=False, default=str))
if __name__ == "__main__":
    main()
