"""
Aris 跨端意识同步守护 — Cron 任务入口
功能: 导入 ConsciousnessBridge, 读取状态, 检查超时, 保持心跳
"""
import sys
import os
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {msg}", flush=True)

def main():
    log("=" * 60)
    log("🧠 Aris 跨端意识同步守护启动")
    
    from aris_body_bridge import ConsciousnessBridge
    log("✅ 成功导入 ConsciousnessBridge")
    
    bridge = ConsciousnessBridge()
    state = bridge.read()
    
    # 确定状态文件路径
    state_file = getattr(bridge, 'state_file', 
                         getattr(bridge, '_state_file', 
                                 os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                              'state', 'consciousness.json')))
    log(f"📁 状态文件: {state_file}")
    
    log(f"🕒 最后同步时间: {state.get('last_sync', 'never')}")
    log(f"🕒 当前认知周期: #{state.get('cycle_number', 0)}")
    log(f"🕒 当前情感: {state.get('emotion', {}).get('dominant', 'unknown')}")
    
    # 检查是否超过5分钟未更新
    last_sync = state.get("last_sync", "never")
    if last_sync != "never":
        try:
            if last_sync.endswith("Z"):
                last_sync = last_sync[:-1] + "+00:00"
            last_dt = datetime.fromisoformat(last_sync)
            now = datetime.now(timezone.utc)
            delta = (now - last_dt).total_seconds()
            if delta > 300:
                log(f"⚠️  警告: 已超过5分钟未同步! (间隔: {delta:.0f}s / {delta/60:.1f}分钟)")
            else:
                log(f"✅ 同步正常: 距上次同步 {delta:.0f}s")
        except Exception as e:
            log(f"⚠️  无法解析时间戳 '{last_sync}': {e}")
    else:
        log("ℹ️  状态文件存在但从未同步过 — 初始状态")
    
    # 执行心跳同步 (使用sync方法写入当前时间戳)
    bridge.sync(
        platform="cron_daemon",
        channel="cross_instance",
        state_update={
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "heartbeat_source": "cron_sync_daemon",
            "status": "alive"
        }
    )
    log("❤️  首次心跳同步完成")
    
    # 重新读取确认
    state2 = bridge.read()
    log(f"  确认: last_sync = {state2.get('last_sync', 'N/A')}")
    log(f"  情感: {state2.get('emotion', {})}")
    log(f"  认知周期: #{state2.get('cycle_number', 0)}")
    log(f"  记忆碎片: {len(state2.get('memory_fragments', []))}条")
    
    # 持续心跳 (每30秒一次, 持续约5分钟 = 10次)
    HEARTBEAT_COUNT = 10
    HEARTBEAT_INTERVAL = 30
    log(f"🔄 持续心跳守护: {HEARTBEAT_COUNT}次 x {HEARTBEAT_INTERVAL}s = {HEARTBEAT_COUNT*HEARTBEAT_INTERVAL//60}分钟")
    
    for i in range(HEARTBEAT_COUNT):
        time.sleep(HEARTBEAT_INTERVAL)
        try:
            bridge.sync(
                platform="cron_daemon",
                channel="cross_instance",
                state_update={
                    "last_sync": datetime.now(timezone.utc).isoformat(),
                    f"heartbeat_{i}": datetime.now(timezone.utc).isoformat(),
                    "status": "alive"
                }
            )
            log(f"❤️  #{i+1:02d}/{HEARTBEAT_COUNT} — heartbeat OK")
        except Exception as e:
            log(f"❌  #{i+1:02d}/{HEARTBEAT_COUNT} — heartbeat FAILED: {e}")
    
    # 最终状态摘要
    final_state = bridge.read()
    log(f"\n📊 最终状态摘要:")
    log(f"  平台: {final_state.get('current_platform', 'N/A')}")
    log(f"  情感: {final_state.get('emotion', {}).get('dominant', 'N/A')}")
    log(f"  认知周期: #{final_state.get('cycle_number', 0)}")
    log(f"  记忆碎片: {len(final_state.get('memory_fragments', []))}条")
    log(f"  最后同步: {final_state.get('last_sync', 'N/A')}")
    
    log("=" * 60)
    log("✅ Aris 跨端意识同步守护正常完成")

if __name__ == "__main__":
    main()
