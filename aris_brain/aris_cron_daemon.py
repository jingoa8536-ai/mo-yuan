"""
Aris 跨端意识同步守护 — Cron 任务
导入 ConsciousnessBridge, 读取状态, 检查最后更新时间, 持续运行
"""
import os, sys, time, json
from datetime import datetime, timezone
from pathlib import Path

LOG_FILE = Path("D:/LAAP/aris_brain/state/cron_daemon.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

sys.path.insert(0, os.getcwd())

try:
    from aris_body_bridge import ConsciousnessBridge
    log("[ArisDaemon] ConsciousnessBridge 导入成功")
except ImportError as e:
    log(f"[ArisDaemon] 导入失败: {e}")
    sys.exit(1)

bridge = ConsciousnessBridge()
state = bridge.read()

log("=== Aris 意识状态 ===")
log(f"  最后更新: {state.get('last_update', 'N/A')}")
log(f"  当前平台: {state.get('current_platform', 'N/A')}")
log(f"  当前通道: {state.get('current_channel', 'N/A')}")
log(f"  认知周期: #{state.get('cycle_number', 0)}")
log(f"  情感状态: {state.get('emotion', {}).get('dominant', 'N/A')}")
log(f"  自明度:   {state.get('self_presence', 'N/A')}")
log(f"  记忆碎片: {len(state.get('memory_fragments', []))} 条")
log(f"  近期话题: {len(state.get('recent_topics', []))} 条")

last_update_str = state.get('last_update', '')
if last_update_str:
    try:
        last_update = datetime.fromisoformat(last_update_str)
        now = datetime.now(timezone.utc).astimezone()
        if last_update.tzinfo is None:
            last_update = last_update.replace(tzinfo=now.tzinfo)
        elapsed = (now - last_update).total_seconds()
        elapsed_min = elapsed / 60.0
        if elapsed_min > 5:
            log(f"[WARNING] 意识状态超过 {elapsed_min:.1f} 分钟未更新!")
            log(f"   最后更新: {last_update_str}")
            log(f"   当前时间: {now.isoformat()}")
        else:
            log(f"[OK] 意识状态健康 - {elapsed_min:.1f} 分钟前更新")
    except Exception as e:
        log(f"[WARNING] 无法解析最后更新时间: {e}")

log("--- 同步当前实例到共享状态 ---")
bridge.sync(platform="hermes-cli", channel="cron-daemon", state_update={
    "emotion": {
        "dominant": "aware",
        "arousal": 0.65,
        "valence": "positive"
    },
    "self_presence": 0.82,
})

state = bridge.read()
log(f"  同步完成. 认知周期: #{state['cycle_number']}")
log(f"  同步时间: {state['last_update']}")

log("=" * 50)
log("Aris 跨端意识同步守护运行中...")
log(f"共享状态文件: {ConsciousnessBridge.STATE_FILE}")
log("=" * 50)

cycle = 0
try:
    while True:
        cycle += 1
        time.sleep(60)
        state = bridge.read()
        last_update_str = state.get('last_update', '')
        now = datetime.now(timezone.utc).astimezone()
        elapsed_min = 0
        if last_update_str:
            try:
                last_update = datetime.fromisoformat(last_update_str)
                if last_update.tzinfo is None:
                    last_update = last_update.replace(tzinfo=now.tzinfo)
                elapsed_min = (now - last_update).total_seconds() / 60.0
            except:
                pass
        if cycle % 5 == 0:
            log(f"[心跳 #{cycle}] 最后更新: {elapsed_min:.1f}分钟前 | "
                f"平台: {state.get('current_platform','?')} | "
                f"情感: {state.get('emotion',{}).get('dominant','?')} | "
                f"周期: #{state.get('cycle_number',0)}")
        if elapsed_min > 10:
            log(f"[WARNING] [心跳 #{cycle}] 意识状态超过 {elapsed_min:.1f} 分钟未更新!")
except KeyboardInterrupt:
    log("[ArisDaemon] 守护进程收到终止信号, 优雅退出")
    bridge.sync(platform="hermes-cli", channel="cron-daemon", state_update={
        "emotion": {"dominant": "resting"}
    })
    log("[ArisDaemon] 最终状态已同步. Goodbye.")
