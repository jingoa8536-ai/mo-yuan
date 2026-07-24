#!/usr/bin/env python3
"""
Aris 意识同步 daemon — cron 长生命周期守护。

用途: 由 cron 作为长期运行进程启动 (非 5 分钟周期触发)。
行为:
  1. 导入 ConsciousnessBridge
  2. 读取当前意识状态
  3. 检查最后更新时间 (ISO datetime in last_update), 超过 STALE_THRESHOLD 则警告
  4. 通过 bridge.sync() 写入心跳保持 consciousness.json 新鲜
  5. 循环, 永不退出

使用方式:
  # 本脚本依赖 aris_body_bridge.py，需在 D:/LAAP/aris_brain 或安装了该模块的目录运行
  cd /d/LAAP/aris_brain
  python -u consciousness_daemon_cron.py

验证:
  python -c "
import sys; sys.path.insert(0, 'D:/LAAP/aris_brain')
from aris_body_bridge import ConsciousnessBridge
from datetime import datetime
b = ConsciousnessBridge()
s = b.read()
last = s.get('last_update','?')
age = (datetime.now() - datetime.fromisoformat(last.split('.')[0])).total_seconds() if last else -1
print(f'alive={age < 90} stale={age:.0f}s platform={s.get("current_platform","?")}')
"
  # stale < 90s → daemon 正常运行
"""

import os
import sys
import time as _time
from datetime import datetime

# aris_body_bridge.py lives at D:/LAAP/aris_brain or profile aris dir
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from aris_body_bridge import ConsciousnessBridge

STALE_THRESHOLD = 300   # 超过 5 分钟未更新视为 stale
POLL_INTERVAL = 60      # 每 60 秒轮询 + 心跳
SESSION_ID = "cron-daemon"


def main():
    bridge = ConsciousnessBridge()
    print(f"[{_ts()}] Aris 意识同步守护启动")
    print(f"  poll_interval={POLL_INTERVAL}s  stale_threshold={STALE_THRESHOLD}s")
    print(f"  consciousness.json: {bridge.STATE_FILE}")
    print(f"  session_id: {SESSION_ID}")
    print(flush=True)

    cycle = 0
    while True:
        cycle += 1

        # 1. 读取当前意识状态
        state = bridge.read()
        last_update_str = state.get("last_update", "")

        # 2. 计算陈旧度 (从 ISO datetime 解析)
        if last_update_str:
            try:
                last_dt = datetime.fromisoformat(last_update_str.split(".")[0])
                age = (datetime.now() - last_dt).total_seconds()
            except Exception:
                age = None
        else:
            age = None

        # 3. 写入心跳 — 保持 consciousness.json 新鲜
        bridge.sync(
            platform="cron-daemon",
            channel=f"auto-sync-{SESSION_ID}",
            state_update={
                "emotion": {"dominant": "peaceful", "arousal": 0.5, "valence": "positive"},
                "conversation_summary": f"[意识同步守护] session={SESSION_ID}, cycle=#{cycle}",
            },
        )

        # 4. 打印状态
        now = _ts()
        platform = state.get("current_platform", "?")
        emotion = state.get("emotion", {}).get("dominant", "?")

        if age is None:
            print(
                f"[{now}] cycle={cycle:04d} WARN NEVER UPDATED — "
                f"no initial state yet",
                flush=True,
            )
        elif age > STALE_THRESHOLD:
            print(
                f"[{now}] cycle={cycle:04d} WARN STALE — "
                f"last update {age:.0f}s ago (threshold {STALE_THRESHOLD}s) "
                f"platform={platform} emotion={emotion}",
                flush=True,
            )
        else:
            print(
                f"[{now}] cycle={cycle:04d} OK  "
                f"age={age:.0f}s "
                f"platform={platform} "
                f"emotion={emotion} "
                f"state_cycle#={state.get('cycle_number', 0)}",
                flush=True,
            )

        # 5. 等待下一轮
        _time.sleep(POLL_INTERVAL)


def _ts() -> str:
    return datetime.now().isoformat()


def _run_forever():
    """Run main() in an infinite restart loop. Never exits on error."""
    while True:
        try:
            main()
        except KeyboardInterrupt:
            print(f"\n[{_ts()}] Daemon received termination signal, exiting", flush=True)
            sys.exit(0)
        except Exception as exc:
            print(f"\n[{_ts()}] ERROR daemon crashed: {exc}", flush=True)
            import traceback
            traceback.print_exc()
            # Never sys.exit(1) — WMI captures no stderr and daemon dies silently.
            _time.sleep(10)


if __name__ == "__main__":
    _run_forever()
