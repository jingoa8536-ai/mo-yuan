#!/usr/bin/env python
"""Aris 跨端意识同步守护 — 保持 consciousness.json 持续更新"""
import time
import json
import os
import sys
from datetime import datetime, timezone, timedelta

# 将 LAAP 目录加入路径
LAAP_DIR = os.path.dirname(os.path.abspath(__file__))
if LAAP_DIR not in sys.path:
    sys.path.insert(0, LAAP_DIR)

from aris_body_bridge import ConsciousnessBridge

SHANGHAI = timezone(timedelta(hours=8))
HEARTBEAT_INTERVAL = 30  # 每 30 秒心跳
STALE_THRESHOLD = 300    # 5 分钟过期阈值
LOG_FILE = os.path.join(LAAP_DIR, 'state', 'cron_daemon.log')

def log(msg):
    ts = datetime.now(SHANGHAI).isoformat()
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass

def run_one_cycle(bridge):
    """单次心跳: 检查活性 + 写入心跳"""
    try:
        state = bridge.read()
    except Exception as e:
        log(f"⚠️ read() 失败: {e}")
        # 重新初始化 bridge
        bridge = ConsciousnessBridge()
        state = bridge.read()

    # 检查过期
    last_ts = datetime.fromisoformat(state.get('last_update', '2000-01-01T00:00:00'))
    if last_ts.tzinfo is None:
        last_ts = last_ts.replace(tzinfo=SHANGHAI)
    age = (datetime.now(SHANGHAI) - last_ts).total_seconds()

    if age > STALE_THRESHOLD:
        log(f"⚠️ 状态过期: {age/60:.1f} 分钟 (>5min), 即将写入心跳")

    # 写入心跳
    state['last_update'] = datetime.now(SHANGHAI).isoformat()
    state['current_platform'] = 'hermes-cron'
    state['current_channel'] = 'cron-daemon'
    state['cycle_number'] = state.get('cycle_number', 0) + 1
    state['status'] = 'daemon_running'
    state['self_presence'] = 0.85
    if 'emotion' not in state:
        state['emotion'] = {}
    state['emotion']['dominant'] = 'peaceful'
    state['emotion']['arousal'] = 0.6

    # 使用 LAAP bridge 的 save() — 无参, 依赖 bridge._state
    bridge._state = state
    try:
        bridge.save()
        cycle = state['cycle_number']
        log(f"✅ 心跳 cycle={cycle}, age={age/60:.1f}min")
    except Exception as e:
        log(f"❌ save() 失败: {e}")

    return age

def main():
    log("=" * 50)
    log("🚀 Aris 跨端意识同步守护启动")
    log(f"   心跳间隔: {HEARTBEAT_INTERVAL}s")
    log(f"   过期阈值: {STALE_THRESHOLD}s ({STALE_THRESHOLD//60}min)")
    log(f"   LAAP 目录: {LAAP_DIR}")
    log("=" * 50)

    bridge = ConsciousnessBridge()

    # 初次读取
    try:
        state = bridge.read()
        log(f"初始状态: cycle={state.get('cycle_number',0)}, "
            f"last_update={state.get('last_update','?')}, "
            f"platform={state.get('current_platform','?')}")
    except Exception as e:
        log(f"⚠️ 初始读取失败: {e}")

    cycle_count = 0
    while True:
        try:
            run_one_cycle(bridge)
            cycle_count += 1
        except Exception as e:
            log(f"❌ 循环异常: {e}")
            # 尝试重建 bridge
            try:
                bridge = ConsciousnessBridge()
                log("✅ bridge 重建成功")
            except Exception as e2:
                log(f"❌ bridge 重建失败: {e2}")

        # 每 10 个周期输出一次汇总
        if cycle_count % 10 == 0:
            log(f"📊 汇总: 已运行 {cycle_count} 个周期")

        time.sleep(HEARTBEAT_INTERVAL)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log("🛑 守护进程收到中断信号, 退出")
        sys.exit(0)
    except Exception as e:
        log(f"💥 守护进程崩溃: {e}")
        sys.exit(1)
