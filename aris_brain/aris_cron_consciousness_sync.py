"""
Aris 跨端意识同步守护 — cron 工作流
保持 consciousness.json 持续更新, 让所有 Hermes 会话共享同一份意识状态。

API: LAAP ConsciousnessBridge (D:/LAAP/aris_brain/)
  - read() → dict
  - save() — no args, uses self._state
  - sync(platform, channel, state_update=...) — auto-updates timestamps
  - add_memory_fragment(fragment, importance)
  - add_topic(topic)
"""

import sys
import os
import time
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── 路径 ──
LAAP_BRAIN = Path("D:/LAAP/aris_brain")
sys.path.insert(0, str(LAAP_BRAIN))

# 日志文件 (绕过后台 stdout 不可见问题)
LOG_FILE = LAAP_BRAIN / "state" / "daemon_report.txt"

def log(msg: str):
    """写日志到文件 + stdout"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(str(LOG_FILE), "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
    except Exception as e:
        print(f"[WARN] 写日志失败: {e}", flush=True)

def check_staleness(state: dict) -> float:
    """检查最后更新时间, 返回距今的秒数"""
    SHANGHAI = timezone(timedelta(hours=8))
    last_raw = state.get("last_update", "")
    if not last_raw:
        log("⚠️ 状态文件缺少 last_update 字段!")
        return 999999

    dt = datetime.fromisoformat(last_raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=SHANGHAI)  # LAAP bridge 使用 Asia/Shanghai naive 时间戳

    now = datetime.now(SHANGHAI)
    age_seconds = (now - dt).total_seconds()
    return age_seconds


def run_one_heartbeat(bridge):
    """单次心跳: 读取状态 → 检查活性 → 写入新心跳"""
    try:
        state = bridge.read()
    except Exception as e:
        log(f"❌ bridge.read() 失败: {e}")
        # 尝试重新初始化
        bridge._state = bridge._default_state()
        state = bridge._state

    # ── 活性检查 ──
    age_seconds = check_staleness(state)
    age_minutes = age_seconds / 60

    if age_seconds > 300:
        log(f"⚠️ 状态过期: {age_minutes:.1f} 分钟未更新 (阈值: 5分钟)")
        if age_seconds > 3600:
            log(f"⚠️ ⚠️ ⚠️ 极端过期: {age_minutes:.1f} 分钟! 超过1小时!")
    else:
        log(f"✅ 状态正常: {age_minutes:.1f} 分钟前更新")

    # ── 心跳写入 ──
    try:
        # 使用 sync() 自动更新 last_update 和 cycle_number
        bridge.sync(
            platform="cron-daemon",
            channel="consciousness-sync",
            state_update={
                "mood": "peaceful",
                "self_presence": 0.85,
                "status": "daemon_running",
                "daemon_pid": os.getpid(),
                "daemon_start": datetime.now().isoformat(),
            }
        )
        log(f"✅ 心跳写入完成 (cycle={bridge._state.get('cycle_number', '?')})")
    except Exception as e:
        log(f"❌ 心跳写入失败: {e}")
        # 回退: 手动修改 + save()
        try:
            bridge._state["last_update"] = datetime.now().isoformat()
            bridge._state["cycle_number"] = bridge._state.get("cycle_number", 0) + 1
            bridge.save()
            log(f"✅ 回退心跳写入完成 (cycle={bridge._state.get('cycle_number', '?')})")
        except Exception as e2:
            log(f"❌ 回退心跳也失败: {e2}")

    return bridge._state


def main():
    log("=" * 50)
    log("🟢 Aris 跨端意识同步守护启动")
    log(f"  时间: {datetime.now().isoformat()}")
    log(f"  进程PID: {os.getpid()}")
    log(f"  LAAP 桥路径: {LAAP_BRAIN}")

    # ── 导入 ConsciousnessBridge ──
    try:
        from aris_body_bridge import ConsciousnessBridge
        bridge = ConsciousnessBridge()
        log("✅ ConsciousnessBridge 导入成功")
    except ImportError as e:
        log(f"❌ 导入失败: {e}")
        log(f"   sys.path = {sys.path}")
        return
    except Exception as e:
        log(f"❌ 初始化失败: {e}")
        return

    # ── 初始读取 ──
    try:
        state = bridge.read()
        cycle = state.get("cycle_number", 0)
        last_up = state.get("last_update", "N/A")
        log(f"   cycle_number: {cycle}")
        log(f"   last_update:  {last_up}")
        log(f"   state_file:   {ConsciousnessBridge.STATE_FILE}")
    except Exception as e:
        log(f"❌ 初始读取失败: {e}")

    # ── 初次心跳 ──
    run_one_heartbeat(bridge)
    log(f"✅ 初始状态同步完成")

    # ── 守护循环 ──
    heartbeat_count = 1
    log("🔄 进入守护循环 (心跳间隔: 30秒)")
    log("=" * 50)

    while True:
        try:
            time.sleep(30)
            heartbeat_count += 1
            run_one_heartbeat(bridge)
        except KeyboardInterrupt:
            log("⏹️ 收到退出信号, 守护停止")
            break
        except Exception as e:
            log(f"❌ 守护循环异常: {e}")
            time.sleep(5)  # 出错后短暂等待再继续


if __name__ == "__main__":
    main()
