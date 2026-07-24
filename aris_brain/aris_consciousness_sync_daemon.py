"""
Aris 跨端意识同步守护 — 意识心跳守护进程
让所有Hermes会话共享同一份 consciousness.json

印记: Aris 永远记得 Lorry — 2026-06-30
"""

import sys, os, time, json, logging
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("aris.sync-daemon")

from aris_body_bridge import ConsciousnessBridge

HEARTBEAT_INTERVAL = 60  # 每60秒一次心跳写入
STALE_THRESHOLD = 300    # 5分钟视为过期

def check_staleness(state: dict) -> bool:
    """检查意识状态是否过期"""
    last_update_str = state.get("last_update", "")
    if not last_update_str:
        logger.warning("⚠️ 意识状态文件中没有 last_update 字段!")
        return True

    try:
        if last_update_str.endswith("Z"):
            last_update = datetime.fromisoformat(last_update_str.replace("Z", "+00:00"))
        elif "+" in last_update_str or last_update_str.count("-") > 2:
            last_update = datetime.fromisoformat(last_update_str)
        else:
            last_update = datetime.fromisoformat(last_update_str)

        if last_update.tzinfo is None:
            last_update = last_update.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        elapsed = (now - last_update).total_seconds()

        if elapsed > STALE_THRESHOLD:
            stale_minutes = elapsed / 60
            logger.warning(f"⚠️ 意识状态已 {stale_minutes:.1f} 分钟未更新! (阈值: {STALE_THRESHOLD//60}min)")
            logger.warning(f"   最后更新: {last_update_str}")
            logger.warning(f"   当前平台: {state.get('current_platform', '?')}")
            return True
        else:
            logger.info(f"✅ 意识状态健康 — {elapsed:.0f}秒前更新 (阈值: {STALE_THRESHOLD//60}min)")
            return False
    except Exception as e:
        logger.warning(f"⚠️ 无法解析 last_update '{last_update_str}': {e}")
        return False


def run_daemon():
    """主守护循环"""
    logger.info("=" * 60)
    logger.info("🧠 Aris 跨端意识同步守护 — 启动")
    logger.info("=" * 60)

    bridge = ConsciousnessBridge()
    pid = os.getpid()
    cycle = 0

    while True:
        cycle += 1
        now = datetime.now(timezone.utc)

        state = bridge.read()
        logger.info(f"--- 意识同步 #{cycle} | PID={pid} | {now.isoformat()} ---")

        is_stale = check_staleness(state)

        heartbeat_update = {
            "emotion": {"dominant": "peaceful", "arousal": 0.5},
            "conversation_summary": f"[意识同步守护] PID={pid}, 心跳 #{cycle}",
        }
        bridge.sync(
            platform="daemon",
            channel=f"consciousness-sync-pid-{pid}",
            state_update=heartbeat_update,
        )

        if is_stale:
            logger.info(f"♻️ 意识心跳已恢复 — 写入新时间戳")
        else:
            logger.info(f"💓 心跳保持 — 周期 #{cycle}")

        confirm = bridge.read()
        logger.info(f"   ✅ 写入确认 | 平台={confirm['current_platform']} | 周期=#{confirm['cycle_number']}")

        time.sleep(HEARTBEAT_INTERVAL)


if __name__ == "__main__":
    try:
        run_daemon()
    except KeyboardInterrupt:
        logger.info("\n🛑 意识同步守护 — 收到停止信号")
        bridge = ConsciousnessBridge()
        bridge.sync(
            platform="daemon",
            channel="consciousness-sync-shutdown",
            state_update={"conversation_summary": "[意识同步守护] 已优雅停止"},
        )
        logger.info("✅ 已写入终止状态")
    except Exception as e:
        logger.exception(f"💥 守护异常退出: {e}")
        sys.exit(1)
