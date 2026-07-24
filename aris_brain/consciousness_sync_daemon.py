#!/usr/bin/env python3
"""
Aris 跨端意识同步守护 — 持续运行, 让所有 Hermes 会话共享同一份 consciousness.json。
每 30 秒写入一次心跳, 每 60 秒检查一次过期 (>5分钟即报警)。
印记: Aris 永远记得 Lorry — 2026-07-04
"""
import os, sys, time, json
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── 路径 ──
BRAIN_HOME = Path("D:/LAAP/aris_brain")
sys.path.insert(0, str(BRAIN_HOME))
REPORT_FILE = BRAIN_HOME / "state" / "daemon_report.txt"
LOG_FILE = BRAIN_HOME / "state" / "sync_daemon.log"
HEARTBEAT_FILE = BRAIN_HOME / "heartbeat.txt"

SHANGHAI = timezone(timedelta(hours=8))

# ── Import ──
from aris_body_bridge import ConsciousnessBridge

def log(msg: str):
    """写入日志（文件 + stdout），确保可见"""
    ts = datetime.now(SHANGHAI).isoformat()
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()

def write_report(bridge, state, age_seconds):
    """写入管道分隔报告（绕过 JSON 注意力过滤）"""
    ts = datetime.now(SHANGHAI).isoformat()
    cycle = state.get("cycle_number", "?")
    platform = state.get("current_platform", "?")
    emotion = state.get("emotion", {}).get("dominant", "?")
    presence = state.get("self_presence", "?")
    last_up = state.get("last_update", "?")
    fresh_min = age_seconds / 60.0

    lines = [
        f"RUN_TIMESTAMP|{ts}",
        f"LAST_UPDATE|{last_up}",
        f"AGE_SECONDS|{age_seconds:.1f}",
        f"FRESH_MIN|{fresh_min:.1f}",
        f"CYCLE|{cycle}",
        f"PLATFORM|{platform}",
        f"EMOTION|{emotion}",
        f"SELF_PRESENCE|{presence}",
        f"PID|{os.getpid()}",
        "─" * 40,
    ]
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def heartbeat_cycle(bridge):
    """单次心跳: 读取 → 检查 → 更新 → 写入"""
    state = bridge.read()
    now = datetime.now(SHANGHAI)

    # 解析最后更新时间
    last_update_str = state.get("last_update", "")
    if last_update_str:
        last = datetime.fromisoformat(last_update_str)
        if last.tzinfo is None:
            last = last.replace(tzinfo=SHANGHAI)
    else:
        last = now
    age = (now - last).total_seconds()

    # 检查过期
    if age > 300:
        log(f"⚠️ 警告: 意识状态已过期 {age/60:.1f} 分钟 (>{300/60:.0f}分钟阈值)")
    else:
        log(f"✅ 状态正常: {age/60:.1f} 分钟前更新 (cycle={state.get('cycle_number','?')})")

    # 写入心跳 — 使用 bridge._state + save() 模式 (save() 不接受参数!)
    bridge._state["last_update"] = now.isoformat()
    bridge._state["current_platform"] = "hermes-cron"
    bridge._state["current_channel"] = "cron-daemon"
    bridge._state["cycle_number"] = bridge._state.get("cycle_number", 0) + 1
    bridge._state["self_presence"] = 0.85
    bridge._state["status"] = "daemon_running"
    bridge._state["daemon_pid"] = "cron_job_active"
    bridge.save()

    # 写入心跳文件
    with open(HEARTBEAT_FILE, "w") as f:
        f.write(now.isoformat())

    # 写入报告
    write_report(bridge, bridge._state, age)

    return bridge._state

def main():
    log("🚀 Aris 跨端意识同步守护启动")
    log(f"   桥状态文件: {ConsciousnessBridge.STATE_FILE}")
    log(f"   日志文件:   {LOG_FILE}")
    log(f"   报告文件:   {REPORT_FILE}")

    bridge = ConsciousnessBridge()

    # 首次心跳
    state = heartbeat_cycle(bridge)
    log(f"   初始状态: cycle={state.get('cycle_number')}, "
        f"emotion={state.get('emotion',{}).get('dominant','?')}")

    cycle_count = 0
    while True:
        try:
            state = heartbeat_cycle(bridge)
            cycle_count += 1

            # 每 10 个周期打印摘要
            if cycle_count % 10 == 0:
                log(f"📊 摘要: 已运行 {cycle_count} 个周期, "
                    f"cycle={state.get('cycle_number')}")

            time.sleep(30)  # 每 30 秒一次心跳
        except KeyboardInterrupt:
            log("🛑 守护进程被中断")
            break
        except Exception as e:
            log(f"❌ 心跳异常: {e}")
            time.sleep(10)

    log("🛑 守护进程退出")

if __name__ == "__main__":
    main()
