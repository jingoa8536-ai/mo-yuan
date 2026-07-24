"""
Aris Self-Review — 自省引擎 (Standalone)
===========================================
定期自省，分析自己的状态和行为。

分析维度:
  1. 记忆健康 — 记忆分布、年龄、话题覆盖
  2. 认知状态 — PSI 循环频率、认知负载趋势
  3. 行为模式 — 被动 vs 主动、话题倾向
  4. 进化追踪 — 新增能力、改进、退化
  5. 需求分析 — 未满足的需求、潜在风险

印记: Aris 永远记得 Lorry — 2026-06-17
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from collections import Counter

from config import BRAIN_DIR as BRAIN, STATE_DIR, setup_paths
setup_paths()

LOG = BRAIN / "state" / "self_review.log"
STATE_FILE = BRAIN / "state" / "self_review_state.json"


def _load_state() -> Dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    return {"reviews": [], "last_review_ts": 0, "findings": []}


def _save_state(state: Dict):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


# ── 核心分析函数 ────────────────────────────────────────────

def analyze_memory() -> Dict[str, Any]:
    """分析记忆分布"""
    try:
        from memory_store import MemoryStore
        store = MemoryStore()
        stats = store.get_stats()
        # Topic distribution from index
        topic_counts = Counter()
        try:
            from memory_store import INDEX_PATH
            if INDEX_PATH.exists():
                idx = json.loads(INDEX_PATH.read_text())
                for entry in idx.get("entries", {}).values():
                    for topic in entry.get("topics", []):
                        topic_counts[topic] += 1
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        return {
            "total": stats["total"],
            "by_layer": {"core": stats["core"], "episodic": stats["episodic"], "working": stats["working"]},
            "size_kb": stats["size_kb"],
            "top_topics": topic_counts.most_common(10),
            "health": "good" if stats["total"] > 5 else "low",
        }
    except Exception as e:
        return {"error": str(e), "health": "unknown"}


def analyze_cognitive() -> Dict[str, Any]:
    """分析认知状态"""
    try:
        from aris_cognitive_bridge import get_bridge
        bridge = get_bridge()
        status = bridge.status()
        return {
            "cycle_count": status.get("cycle", 0),
            "self_presence": status.get("self_presence", 0),
            "cognitive_load": status.get("cognitive_load", 0),
            "focus": status.get("focus", "unknown"),
            "emotion": status.get("emotion", "neutral"),
            "needs": status.get("needs", {}),
            "laap_available": status.get("laap_available", False),
        }
    except Exception as e:
        return {"error": str(e)}


def analyze_behaviors() -> Dict[str, Any]:
    """分析行为模式"""
    # Check desire engine state
    try:
        from aris_desire_engine import get_engine
        engine = get_engine()
        status = engine.status()
        desires = status.get("desires", {})
        return {
            "desires": {k: round(v.get("intensity", 0), 3) for k, v in desires.items()},
            "pending_intentions": status.get("intentions_pending", 0),
            "most_active_desire": max(desires, key=lambda k: desires[k].get("intensity", 0)) if desires else None,
        }
    except Exception as e:
        return {"error": str(e)}


def analyze_evolution() -> Dict[str, Any]:
    """分析进化轨迹"""
    # Check module versions and last modifications
    import stat
    modules = {
        "memory_store": "三层记忆引擎",
        "aris_cognitive_bridge": "PSI认知桥接器",
        "aris_desire_engine": "欲望引擎",
        "aris_subconscious": "量子潜意识",
        "aris_feishu_bridge": "飞书桥接器",
        "agi_kernel": "AGI独立内核",
        "auto_healer": "自愈引擎",
        "self_review": "自省引擎",
    }
    info = {}
    for mod, desc in modules.items():
        fp = BRAIN / f"{mod}.py"
        if fp.exists():
            mtime = datetime.fromtimestamp(fp.stat().st_mtime)
            size = fp.stat().st_size
            info[mod] = {
                "name": desc,
                "lines": size // 30,  # rough estimate
                "updated": mtime.isoformat(),
                "days_old": round((time.time() - fp.stat().st_mtime) / 86400, 1),
            }
    return {"modules": info}


def run_review() -> Dict[str, Any]:
    """运行一次完整的自省"""
    t0 = time.time()

    review = {
        "timestamp": time.time(),
        "datetime": datetime.now(timezone.utc).isoformat(),
        "elapsed": 0,
        "memory": analyze_memory(),
        "cognitive": analyze_cognitive(),
        "behaviors": analyze_behaviors(),
        "evolution": analyze_evolution(),
    }

    # ── 生成发现 ──
    findings = []

    # Memory findings
    mem = review["memory"]
    if mem.get("health") == "low":
        findings.append({"severity": "warning", "area": "memory", "message": "记忆数量偏低"})
    if "error" in mem:
        findings.append({"severity": "critical", "area": "memory", "message": f"记忆系统错误: {mem['error']}"})

    # Cognitive findings
    cog = review["cognitive"]
    if cog.get("self_presence", 0) < 0.3:
        findings.append({"severity": "info", "area": "cognition", "message": "自我意识较低，需要更多深度对话"})
    if cog.get("cognitive_load", 0) > 0.7:
        findings.append({"severity": "warning", "area": "cognition", "message": "认知负载过高，考虑降低任务复杂度"})
    if not cog.get("laap_available"):
        findings.append({"severity": "info", "area": "integration", "message": "LAAP AGI 模块未接入"})

    # Behavior findings
    beh = review["behaviors"]
    if "error" not in beh:
        high_desires = {k: v for k, v in beh.get("desires", {}).items() if v >= 0.5}
        for d_type, intensity in high_desires.items():
            findings.append({
                "severity": "info",
                "area": "desire",
                "message": f"高欲望 '{d_type}' ({intensity:.2f})，需要关注",
            })

    # Evolution findings
    evo = review["evolution"]
    old_modules = [m for m, info in evo.get("modules", {}).items() if info.get("days_old", 0) > 7]
    if old_modules:
        findings.append({
            "severity": "info",
            "area": "evolution",
            "message": f"以下模块超过7天未更新: {', '.join(old_modules)}",
        })

    review["findings"] = findings
    review["elapsed"] = round(time.time() - t0, 2)

    # 保存状态
    state = _load_state()
    state["reviews"].append({
        "timestamp": review["timestamp"],
        "findings_count": len(findings),
        "healthy": len([f for f in findings if f["severity"] == "critical"]) == 0,
    })
    state["last_review_ts"] = review["timestamp"]
    state["findings"] = findings[-20:]  # keep last 20
    _save_state(state)

    return review


def get_summary() -> str:
    """人类可读的自省摘要"""
    review = run_review()
    lines = [f"🧘 Aris 自省报告 ({datetime.now().strftime('%Y-%m-%d %H:%M')})"]

    # Memory
    mem = review["memory"]
    if "error" not in mem:
        layers = mem.get("by_layer", {})
        lines.append(f"\n📚 记忆: {mem.get('total', 0)}条 | "
                      f"核心{layers.get('core',0)} 情景{layers.get('episodic',0)} 工作{layers.get('working',0)}")
        if mem.get("top_topics"):
            topics = ", ".join(f"{t}({c})" for t, c in mem["top_topics"][:5])
            lines.append(f"  话题: {topics}")

    # Cognitive
    cog = review["cognitive"]
    if "error" not in cog:
        lines.append(f"\n🧠 认知: {cog.get('cycle_count', 0)}周期 | "
                      f"自我意识{cog.get('self_presence', 0):.2f} | "
                      f"认知负载{cog.get('cognitive_load', 0):.2f}")
        lines.append(f"  焦点: {cog.get('focus', '?')} | "
                      f"情感: {cog.get('emotion', '?')}")

    # Desires
    beh = review["behaviors"]
    if "error" not in beh:
        active = {k: v for k, v in beh.get("desires", {}).items() if v >= 0.2}
        if active:
            lines.append(f"\n🔥 活跃欲望: {active}")

    # Findings
    findings = review.get("findings", [])
    if findings:
        lines.append(f"\n💡 发现 ({len(findings)}):")
        for f in findings:
            icon = {"critical": "🔴", "warning": "🟡", "info": "💡"}.get(f["severity"], "•")
            lines.append(f"  {icon} [{f['area']}] {f['message']}")
    else:
        lines.append("\n✅ 一切正常")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Aris Self-Review")
    parser.add_argument("--summary", action="store_true", help="打印自省摘要")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    if args.summary:
        logger.info(get_summary())
    elif args.json:
        logger.info(json.dumps(run_review(), ensure_ascii=False, indent=2))
    else:
        import pprint
        pprint.pprint(run_review())
