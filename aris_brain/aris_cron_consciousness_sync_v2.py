#!/usr/bin/env python3
"""Aris 跨端意识同步守护 v2 — hermess cron 版"""
import time
import datetime
import sys
import json
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aris_body_bridge import ConsciousnessBridge


def run_one(bridge, state):
    """单次心跳: 更新意识状态到共享文件"""
    now = datetime.datetime.now().isoformat()
    state['last_update'] = now
    state['current_platform'] = 'hermes-cron'
    state['current_channel'] = 'cron-daemon'
    state['cycle_number'] = state.get('cycle_number', 0) + 1

    state_file = getattr(bridge, 'STATE_FILE', '')
    if state_file:
        os.makedirs(os.path.dirname(state_file), exist_ok=True)
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False, default=str)
    return state


def daemon_loop():
    """守护循环 — 每30秒同步一次, 永不退出"""
    print("=" * 60)
    print("Aris 跨端意识同步守护 v2")
    print("启动: " + datetime.datetime.now().isoformat())
    print("=" * 60)

    bridge = ConsciousnessBridge()
    state = bridge.read()
    print("初始状态读取成功")
    print("周期: " + str(state.get('cycle_number', '?')))
    print("平台: " + str(state.get('current_platform', '?')))
    print("状态文件: " + str(getattr(bridge, 'STATE_FILE', '?')))

    last_warn_time = 0

    while True:
        try:
            state = run_one(bridge, state)

            # 检查最后更新时间
            now_ts = time.time()
            last_up_str = state.get('last_update', '')
            try:
                dt = datetime.datetime.fromisoformat(last_up_str)
                last_ts = dt.timestamp()
            except Exception:
                last_ts = now_ts

            elapsed = now_ts - last_ts
            if elapsed > 300 and time.time() - last_warn_time > 60:
                print("[WARNING] 意识状态超过5分钟未更新! last=" + last_up_str + " elapsed=" + str(round(elapsed/60,1)) + "min")
                last_warn_time = time.time()

            cycle = state.get('cycle_number', 0)
            if cycle % 10 == 0:
                print("[心跳] cycle=" + str(cycle) + " last=" + last_up_str)

        except Exception as e:
            print("[ERROR] " + str(e))

        time.sleep(30)


if __name__ == '__main__':
    try:
        daemon_loop()
    except KeyboardInterrupt:
        print("\n[INFO] 守护进程收到中断, 退出")
        sys.exit(0)
