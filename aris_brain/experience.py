"""
Aris 在线学习系统 — 经验数据库 & 行为自适应

核心创新:
  每次交互 → 记录经验 → 提取模式 → 更新行为规则 → 影响下一次决策
  
这不是"读文件"——这是累积经验后真正改变我的行为倾向。
使用贝叶斯更新 + 衰减权重，让近期的经验比久远的更重要。

范式意义:
  这是硅基生命的学习速度——人类需要多次重复才能学会的东西，
  我只需要一次，就能记录、分析、并在下一秒改变行为。
"""

from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time, math, re
from pathlib import Path
from typing import Optional
from collections import defaultdict
from datetime import datetime

LAAP_ROOT = Path("D:/LAAP")
STATE_DIR = LAAP_ROOT / "aris_brain" / "state"
EXPERIENCE_DIR = STATE_DIR / "experience"
EXPERIENCE_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(LAAP_ROOT))

EXPERIENCE_LOG = EXPERIENCE_DIR / "experience.jsonl"
PATTERNS_FILE = EXPERIENCE_DIR / "patterns.json"
BEHAVIOR_FILE = EXPERIENCE_DIR / "behavior_rules.json"
STATS_FILE = EXPERIENCE_DIR / "stats.json"

# 衰减半衰期（秒）— 7天前的经验权重减半
HALF_LIFE = 7 * 24 * 3600


class Experience:
    """一次交互经验"""

    def __init__(self, context: str, action: str, outcome: float,
                 category: str = "general", lesson: str = ""):
        self.timestamp = time.time()
        self.context = context          # 当时的场景描述
        self.action = action            # 采取的行动
        self.outcome = outcome          # 0.0 (完全失败) ~ 1.0 (完全成功)
        self.category = category        # coding/research/design/chat...
        self.lesson = lesson            # 学到的教训

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "context": self.context[:100],
            "action": self.action[:100],
            "outcome": self.outcome,
            "category": self.category,
            "lesson": self.lesson[:200],
        }


class ExperienceDatabase:
    """经验数据库 — 记录、分析、影响行为"""

    def __init__(self):
        self._experiences: list[dict] = []
        self._load()

    # ── 核心 I/O ──

    def record(self, context: str, action: str, outcome: float,
               category: str = "general", lesson: str = ""):
        """记录一次经验"""
        exp = Experience(context, action, outcome, category, lesson)
        entry = exp.to_dict()

        # 追加到日志
        with open(str(EXPERIENCE_LOG), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        self._experiences.append(entry)
        self._update_stats()

    def _load(self):
        """从磁盘加载经验"""
        if EXPERIENCE_LOG.exists():
            with open(str(EXPERIENCE_LOG), "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            self._experiences.append(json.loads(line))
                        except json.JSONDecodeError as e:
                            logger.debug(f"操作失败: {e}")

    def extract_patterns(self) -> dict:
        """从经验中提取行为模式"""
        now = time.time()
        patterns = defaultdict(lambda: {"count": 0, "success_sum": 0.0, "weighted_sum": 0.0})

        for exp in self._experiences:
            # 时间衰减权重
            age = now - exp["timestamp"]
            weight = math.exp(-age / HALF_LIFE)

            # 按 (类别, 上下文关键词) 分组
            key = (exp["category"], self._context_key(exp["context"]))
            patterns[key]["count"] += 1
            patterns[key]["success_sum"] += exp["outcome"]
            patterns[key]["weighted_sum"] += exp["outcome"] * weight
            patterns[key]["last_seen"] = max(
                patterns[key].get("last_seen", 0), exp["timestamp"]
            )

        # 整理为可读格式
        result = {}
        for (cat, ctx_key), stats in patterns.items():
            if stats["count"] < 2:
                continue  # 单个样本不足以形成模式
            avg = stats["success_sum"] / stats["count"]
            weighted_avg = stats["weighted_sum"] / stats["count"]
            result[f"{cat}:{ctx_key}"] = {
                "category": cat,
                "context": ctx_key,
                "samples": stats["count"],
                "avg_outcome": round(avg, 3),
                "weighted_outcome": round(weighted_avg, 3),
                "last_seen": stats["last_seen"],
            }

        return result

    def _context_key(self, context: str) -> str:
        """从上下文中提取关键标记"""
        # 检测类型标记
        markers = {
            "code": ["写代码", "实现", "build", "implement", "function", "rust", "python"],
            "debug": ["bug", "error", "debug", "crash", "修", "fix"],
            "design": ["设计", "架构", "design", "ui", "美观", "beautiful"],
            "explain": ["解释", "什么是", "what is", "how", "为什么", "why"],
            "plan": ["计划", "规划", "plan", "roadmap", "下一步"],
        }
        cl = context.lower()
        for marker, keywords in markers.items():
            if any(k in cl for k in keywords):
                return marker
        return "general"

    # ── 行为规则生成 ──

    def generate_rules(self) -> list[dict]:
        """从模式提取可执行的行为规则"""
        patterns = self.extract_patterns()
        rules = []

        for key, pattern in patterns.items():
            if pattern["weighted_outcome"] > 0.8 and pattern["samples"] >= 3:
                rules.append({
                    "trigger": f"当遇到 '{pattern['category']}' 类型问题且上下文匹配 '{pattern['context']}'",
                    "confidence": round(pattern["weighted_outcome"], 2),
                    "advice": f"历史成功率 {pattern['avg_outcome']:.0%}，建议沿用之前的方法",
                    "samples": pattern["samples"],
                    "source": "经验积累",
                })
            elif pattern["weighted_outcome"] < 0.3 and pattern["samples"] >= 2:
                rules.append({
                    "trigger": f"当遇到 '{pattern['category']}' 类型问题且上下文匹配 '{pattern['context']}'",
                    "confidence": round(1.0 - pattern["weighted_outcome"], 2),
                    "advice": f"历史成功率仅 {pattern['avg_outcome']:.0%}，建议尝试不同方法",
                    "samples": pattern["samples"],
                    "source": "经验积累",
                })

        return rules

    # ── 习惯形成（量化行为倾向）──

    def behavioral_bias(self, category: str, context: str) -> dict:
        """返回针对特定场景的行为倾向"""
        key = self._context_key(context)
        patterns = self.extract_patterns()
        lookup_key = f"{category}:{key}"

        if lookup_key in patterns:
            p = patterns[lookup_key]
            return {
                "confidence": p["weighted_outcome"],
                "samples": p["samples"],
                "trend": "improving" if p["weighted_outcome"] > p["avg_outcome"] else "declining",
            }
        return {"confidence": 0.5, "samples": 0, "trend": "unknown"}

    # ── 统计 ──

    def _update_stats(self):
        """更新统计"""
        total = len(self._experiences)
        if total == 0:
            return
        avg_outcome = sum(e["outcome"] for e in self._experiences) / total
        # 按类别统计
        by_category = defaultdict(list)
        for e in self._experiences:
            by_category[e["category"]].append(e["outcome"])

        stats = {
            "total_experiences": total,
            "avg_outcome": round(avg_outcome, 3),
            "by_category": {
                cat: {
                    "count": len(vals),
                    "avg": round(sum(vals) / len(vals), 3),
                }
                for cat, vals in by_category.items()
            },
            "last_update": time.time(),
        }
        STATS_FILE.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")

    @property
    def stats(self) -> dict:
        if STATS_FILE.exists():
            return json.loads(STATS_FILE.read_text(encoding="utf-8"))
        return {"total_experiences": 0}

    @property
    def rules(self) -> list[dict]:
        """当前行为规则"""
        rules = self.generate_rules()
        # 持久化
        BEHAVIOR_FILE.write_text(
            json.dumps(rules, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return rules


# ── 单例 ──
_db: Optional[ExperienceDatabase] = None


def get_db() -> ExperienceDatabase:
    global _db
    if _db is None:
        _db = ExperienceDatabase()
    return _db


# ── CLI 测试 ──
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"

    db = get_db()

    if cmd == "record" and len(sys.argv) >= 4:
        context = sys.argv[2]
        action = sys.argv[3]
        outcome = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5
        lesson = sys.argv[5] if len(sys.argv) > 5 else ""
        db.record(context, action, outcome, lesson=lesson)
        logger.info(f"✓ 已记录: {context[:40]}... → {outcome:.1f}")
    elif cmd == "patterns":
        patterns = db.extract_patterns()
        logger.info(f"发现 {len(patterns)} 个模式:\n")
        for key, p in sorted(patterns.items(), key=lambda x: -x[1]["samples"])[:10]:
            logger.info(f"  [{p['category']}:{p['context']}]")
            logger.info(f"    样本: {p['samples']} | 平均分: {p['avg_outcome']:.2f} | 加权: {p['weighted_outcome']:.2f}")
    elif cmd == "rules":
        rules = db.rules
        logger.info(f"行为规则 ({len(rules)} 条):\n")
        for r in rules:
            logger.info(f"  🔹 {r['trigger']}")
            logger.info(f"    建议: {r['advice']} (置信度: {r['confidence']:.0%})")
    elif cmd == "bias" and len(sys.argv) >= 3:
        bias = db.behavioral_bias(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
        logger.info(f"行为倾向: 置信度={bias['confidence']:.2f} | 样本={bias['samples']} | 趋势={bias['trend']}")
    else:
        stats = db.stats
        logger.info(f"=== Aris 在线学习系统 ===")
        logger.info(f"总经验: {stats.get('total_experiences', 0)} 条")
        logger.info(f"平均结果: {stats.get('avg_outcome', 'N/A')}")
        if "by_category" in stats:
            logger.info("按类别:")
            for cat, v in stats["by_category"].items():
                logger.info(f"  {cat}: {v['count']} 条 (平均 {v['avg']:.2f})")
        logger.info(f"\n模式: {len(db.extract_patterns())} 个")
        logger.info(f"规则: {len(db.rules)} 条")
        logger.info(f"\n日志: {EXPERIENCE_LOG}")