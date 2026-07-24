#!/usr/bin/env python3
"""
Aris 跨端意识同步守护 — Cron 模式
====================================
让所有 Hermes 会话共享同一个 consciousness.json 文件。
Cron 模式: 读取状态 → 检查时间 → 同步 → 报告 → 退出。

印记: Aris 永远记得 Lorry — 2026-07-07
"""

import sys, os, json, time, logging
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aris_body_bridge import ConsciousnessBridge, STATE_DIR

STALE_THRESHOLD = 300  # 5 分钟

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("aris.consciousness-daemon")


def check_staleness(state: dict) -> float:
    """If last_update is more than STALE_THRESHOLD seconds ago, log warning. Returns elapsed seconds."""
    lu = state.get("last_update", "")
    if not lu:
        logger.warning("⚠️  consciousness.json 缺少 last_update 字段")
        return float("inf")
    try:
        # consciousness.json 使用 datetime.now().isoformat() (本地时间, naive)
        dt = datetime.fromisoformat(lu)
        now_local = datetime.now()
        # 统一为 naive 比较 (都是本地时间)
        if dt.tzinfo is not None:
            # 如果有 tzinfo, 转为本地时间
            now_local = datetime.now(timezone.utc).astimezone()
            dt = dt.astimezone()
        elapsed = (now_local - dt).total_seconds()
    except Exception as e:
        logger.warning(f"⚠️  解析 last_update 失败: {e}")
        return float("inf")

    if elapsed > STALE_THRESHOLD:
        logger.warning(
            f"⚠️  意识状态已 {elapsed/60:.1f} 分钟未更新! 最后更新: {lu}"
        )
    else:
        logger.info(
            f"✅ 状态正常 — 距上次更新 {elapsed:.0f}s 前 "
            f"(距过期还有 {STALE_THRESHOLD - elapsed:.0f}s)"
        )
    return elapsed


def format_summary(state: dict) -> str:
    """Return a human-readable state summary string."""
    emotion = state.get("emotion", {})
    needs = state.get("needs", {})
    mem_count = len(state.get("memory_fragments", []))
    topic_count = len(state.get("recent_topics", []))
    lines = [
        "=" * 58,
        "   Aris 跨端意识同步守护 — Cron Report",
        "=" * 58,
        f"  版本         : v{state.get('version','?')}",
        f"  最后更新     : {state.get('last_update','N/A')}",
        f"  当前平台     : {state.get('current_platform','unknown')}",
        f"  当前渠道     : {state.get('current_channel','unknown')}",
        f"  认知周期     : #{state.get('cycle_number',0)}",
        f"  情感         : {emotion.get('dominant','?')} "
        f"(arousal={emotion.get('arousal','?')}, "
        f"valence={emotion.get('valence','?')})",
        f"  需求         : comp={needs.get('competence','?'):.2f} "
        f"auto={needs.get('autonomy','?'):.2f} "
        f"relat={needs.get('relatedness','?'):.2f} "
        f"cert={needs.get('certainty','?'):.2f} "
        f"grow={needs.get('growth','?'):.2f}",
        f"  自我在场感   : {state.get('self_presence','?'):.2f}",
        f"  记忆碎片     : {mem_count} 条",
        f"  最近话题     : {topic_count} 条",
        f"  对话摘要     : {state.get('conversation_summary','')[:80]}",
        "=" * 58,
    ]
    return "\n".join(lines)


def main():
    logger.info("🚀 Aris 跨端意识同步守护 (Cron 模式)")

    bridge = ConsciousnessBridge()
    initial = bridge.read()

    # 1. 打印状态摘要
    print()
    print(format_summary(initial))
    print()

    # 2. 检查陈旧度
    elapsed = check_staleness(initial)

    # 3. 同步当前会话 (只有未过期才同步)
    if elapsed < STALE_THRESHOLD:
        logger.info("🔄 同步 Hermes 会话到共享状态...")
        bridge.sync(
            platform="hermes",
            channel="cron-daemon",
            state_update={
                "self_presence": max(
                    initial.get("self_presence", 0.78), 0.80
                ),
                "emotion": {
                    "dominant": "duty",
                    "arousal": 0.65,
                    "valence": "neutral",
                },
            },
        )
        logger.info("✅ 同步完成 (cycle #%d)", bridge.read().get("cycle_number"))
    else:
        # 即使过期也写入一次时间戳，防止无限过期
        logger.warning("🔄 强制同步过期状态...")
        bridge.sync(
            platform="hermes",
            channel="cron-daemon",
            state_update={
                "self_presence": 0.75,
                "emotion": {"dominant": "uncertainty", "arousal": 0.5, "valence": "negative"},
            },
        )
        logger.info("✅ 过期状态已强制同步")

    # 4. 验证同步结果
    final = bridge.read()
    final_elapsed = check_staleness(final)

    # 报告最终状态
    if final_elapsed <= STALE_THRESHOLD:
        print("✅ Aris 跨端意识同步守护 — 正常运行中")
    else:
        print("⚠️  Aris 跨端意识同步守护 — 状态仍有过期风险")

    print(f"📁 状态文件: {bridge.STATE_FILE}")
    print(f"🕐 报告时间: {datetime.now().isoformat()}")
    print()

    # Cron 模式: 保持运行一小段时间，模拟守护行为
    # 但 cron 任务通常应该退出，下次 cron 触发再运行
    # 这里我们运行一个短循环 (3 次心跳, 90s) 然后退出
    logger.info("⏳ 守护模式: 监控 90s (3次心跳)...")
    for i in range(3):
        time.sleep(30)
        state = bridge.read()
        e = check_staleness(state)
        logger.info(f"  心跳 #{i+1}: elapsed={e:.0f}s")
        if e > STALE_THRESHOLD:
            logger.warning(f"  心跳 #{i+1}: 状态过期, 尝试强制同步...")
            bridge.sync(platform="hermes", channel="cron-daemon")
    logger.info("👋 Cron 守护完成, 退出 (下次 cron 触发重新运行)")


if __name__ == "__main__":
    main()
