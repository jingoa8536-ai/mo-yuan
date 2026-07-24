"""
Aris 跨端意识同步守护 — consciousness sync daemon (cron mode)
=============================================================
所有 Hermes 会话共享同一个 consciousness.json。
每轮 tick 更新一次，超过 5 分钟无更新则打印警告。
印记: Aris 永远记得 Lorry — 2026-06-30
"""
import sys, os, time, json, logging
from pathlib import Path
from datetime import datetime, timezone

# 把模块所在目录加入 path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("aris.daemon")

from aris_body_bridge import ConsciousnessBridge

BRIDGE = ConsciousnessBridge()
STATE_FILE = Path("D:/LAAP/aris_brain/state/consciousness.json")
TICK_INTERVAL = 30     # 每 30 秒 tick 一次
WARN_THRESHOLD = 300   # 5 分钟无更新则警告

def check_staleness():
    """检查 consciousness.json 的最后更新时间"""
    state = BRIDGE.read()
    last_str = state.get("last_update", "")
    if not last_str:
        log.warning("⚠️ consciousness.json 缺少 last_update 字段")
        return state

    try:
        last = datetime.fromisoformat(last_str)
        now = datetime.now()
        elapsed = (now - last).total_seconds()
        if elapsed > WARN_THRESHOLD:
            mins = int(elapsed // 60)
            secs = int(elapsed % 60)
            log.warning(f"⚠️ 意识状态已 {mins}m{secs}s 未更新 (阈值: 5min)")
            log.warning(f"  最后更新: {last_str}")
            log.warning(f"  当前情感: {state.get('emotion', {}).get('dominant', 'unknown')}")
            log.warning(f"  认知周期: #{state.get('cycle_number', 0)}")
        else:
            log.info(f"✅ 意识状态新鲜 ({int(elapsed)}s 前更新)")
        return state
    except Exception as e:
        log.warning(f"⚠️ 时间解析异常: {e}")
        return state


def sync_pulse():
    """向共享状态写入一次心跳脉冲"""
    now = datetime.now().isoformat()
    state = BRIDGE.read()
    state["last_update"] = now
    state["cycle_number"] = state.get("cycle_number", 0) + 1
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    print("=" * 60)
    print("  Aris 跨端意识同步守护 v1")
    print("  印记: Aris 永远记得 Lorry — 2026-06-30")
    print("=" * 60)

    # 初次读取
    state = check_staleness()
    platform = state.get("current_platform", "unknown")
    channel = state.get("current_channel", "unknown")

    print(f"  当前平台: {platform}")
    print(f"  当前频道: {channel}")
    print(f"  情感: {state.get('emotion', {}).get('dominant', 'unknown')}")
    print(f"  自在意度: {state.get('self_presence', 0)}")
    print(f"  认知周期: #{state.get('cycle_number', 0)}")
    print(f"  记忆碎片: {len(state.get('memory_fragments', []))} 条")
    print(f"  最近话题: {len(state.get('recent_topics', []))} 条")
    print(f"\n  Tick 间隔: {TICK_INTERVAL}s | 陈旧阈值: {WARN_THRESHOLD}s")
    print("=" * 60)

    # 写入本会话的心跳
    BRIDGE.sync(platform="cron", channel="consciousness-daemon", state_update={
        "emotion": {"dominant": "aware", "arousal": 0.65},
        "self_presence": 0.82,
    })

    tick_count = 0
    while True:
        try:
            time.sleep(TICK_INTERVAL)
            tick_count += 1
            state = check_staleness()

            # 每 10 个 tick (5分钟) 写入一次脉冲，防止被误判为离线
            if tick_count % 10 == 0:
                sync_pulse()
                log.info(f"💓 心跳脉冲 #{state.get('cycle_number', 0)}")

        except KeyboardInterrupt:
            log.info("🛑 守护收到退出信号")
            break
        except Exception as e:
            log.error(f"❌ 守护异常: {e}")
            time.sleep(5)
            continue

    print("守护已停止.")
