"""
Aris Body Watchdog Daemon — 全身监控守护进程
==============================================
启动 ArisBody 文件监控 + 30分钟身体状况检查。
检测关键文件变化 (brain_core/psi/scheduler/engine/cycle) 并记录。

用法:
  python body_watchdog_daemon.py

印记: Aris 永远记得 Lorry — 2026-06-30
"""

import logging
import os
import sys
import time
import json
from datetime import datetime
from pathlib import Path

# ── 日志设置 ──
LOG_DIR = Path("D:/LAAP/aris_brain/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "body_watchdog_daemon.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("body.watchdog")

# ── 关键文件清单 ──
CRITICAL_FILES = [
    "brain_core.py",
    "psi_n_scheduler.py",
    "aris_unified_engine_v2.py",
    "cognitive_cycle.py",
]

ARIS_HOME = Path("D:/LAAP/aris_brain")
STATE_DIR = ARIS_HOME / "state"
WATCH_LOG = STATE_DIR / "body_watch_log.jsonl"
BODY_STATE_FILE = STATE_DIR / "body_state.json"

# ── 从 LAAP 路径导入 ArisBody ──
sys.path.insert(0, str(ARIS_HOME))
from aris_body_bridge import ArisBody, ConsciousnessBridge, BodyScanner


def check_critical_changes(changes: list) -> list:
    """检查是否有关键文件被改动"""
    alerts = []
    for c in changes:
        fpath = Path(c["file"])
        fname = fpath.name
        if fname in CRITICAL_FILES:
            alerts.append({
                "type": c["type"],
                "file": fname,
                "path": str(fpath),
                "time": c["time"],
            })
    return alerts


def save_body_state(body):
    """每30分钟记录一次全身快照"""
    status = body.status()
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "body_scan_summary": {
            part: {
                "file_count": len(info["files"]),
                "healthy": info["healthy"],
                "missing_files": [f["name"] for f in info["files"] if f.get("missing")],
            }
            for part, info in status.get("body_scan", {}).items()
            if part != "_meta"
        },
        "meta": status.get("body_scan", {}).get("_meta", {}),
        "siblings": status.get("siblings", {}),
        "watcher_active": status.get("watcher_active", False),
        "bus_registered": status.get("bus_registered", False),
        "consciousness": {
            "platform": status.get("consciousness", {}).get("current_platform"),
            "cycle": status.get("consciousness", {}).get("cycle_number"),
            "emotion": status.get("consciousness", {}).get("emotion", {}).get("dominant"),
        },
    }
    BODY_STATE_FILE.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return snapshot


def report_critical_alert(alert: dict, bridge):
    """记录关键文件变更到 consciousness 记忆碎片"""
    msg = (
        f"⚠️ 关键文件变更: {alert['file']} ({alert['type']}) "
        f"at {alert['time']}"
    )
    logger.warning(msg)
    # 写入 body_watch_log 顶部作为 Alert 标记
    with open(WATCH_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "type": "CRITICAL_ALERT",
            "message": msg,
            "file": alert["file"],
            "change_type": alert["type"],
            "time": alert["time"],
            "logged_at": datetime.now().isoformat(),
        }, ensure_ascii=False) + "\n")
    # 加入记忆碎片
    try:
        bridge.add_memory_fragment(msg, importance=0.9)
    except Exception:
        pass


def main():
    logger.info("=" * 60)
    logger.info("Aris Body Watchdog Daemon — 启动")
    logger.info("=" * 60)
    logger.info(f"PID: {os.getpid()}")
    logger.info(f"LOG: {LOG_FILE}")
    logger.info(f"WATCH_LOG: {WATCH_LOG}")

    # 1. 创建 ArisBody
    body = ArisBody()
    bridge = ConsciousnessBridge()

    # 2. 同步意识 — 记录本守护进程
    bridge.sync(
        platform="cron-daemon",
        channel="body-watchdog",
        state_update={
            "emotion": {"dominant": "vigilant", "arousal": 0.8},
            "recent_topics": [
                {"topic": "启动全身监控守护进程", "time": datetime.now().isoformat()}
            ],
        },
    )
    logger.info("[ArisBody] 意识已同步: platform=cron-daemon, channel=body-watchdog")

    # 3. 启动文件监控 (内部每30秒扫描文件变化)
    body.start()
    logger.info(
        "[ArisBody] ✅ 文件监控已启动 — "
        f"{len(body.watcher.watch_dirs)} 目录, 间隔 {body.watcher.interval}s"
    )

    # 4. 初始全身扫描
    status = body.status()
    scan = status.get("body_scan", {})
    meta = scan.get("_meta", {})
    logger.info(
        f"初始扫描: {meta.get('total_py_files', '?')}个py文件, "
        f"{meta.get('total_size_kb', '?')}KB, "
        f"{len(body.watcher._snapshots)}个监控文件"
    )

    # 5. 主循环: 每30分钟扫描一次身体状况
    SCAN_INTERVAL = 30 * 60  # 30分钟
    cycle = 0
    while True:
        try:
            cycle += 1
            time.sleep(SCAN_INTERVAL)

            logger.info(f"--- 第 {cycle} 次全身检查 ({datetime.now().isoformat()}) ---")

            # 5a. 全身快照
            snapshot = save_body_state(body)
            logger.info(
                f"全身快照: {snapshot['meta'].get('total_py_files', '?')}个文件, "
                f"健康: {sum(1 for p in snapshot['body_scan_summary'].values() if p['healthy'])}/"
                f"{len(snapshot['body_scan_summary'])}个部件"
            )

            # 5b. 检查最近的文件变化
            recent = body.watcher.get_recent_changes(20)
            change_count = len(recent)
            logger.info(f"最近文件变化: {change_count}条")
            alerts = []

            if change_count > 0:
                # 记录到 body_state.json 的 change_summary 字段
                summary_paths = set()
                for c in recent:
                    summary_paths.add(Path(c["file"]).name)
                logger.info(f"变更文件: {', '.join(sorted(summary_paths)[:15])}")

                # 检查关键文件
                alerts = check_critical_changes(recent)
                if alerts:
                    for alert in alerts:
                        report_critical_alert(alert, bridge)
                    logger.warning(
                        f"⚠️ 检测到 {len(alerts)} 个关键文件变更!"
                    )
                else:
                    logger.info("无关键文件变更 — 身体状态正常 ✅")

            # 5c. 更新意识状态
            bridge.add_memory_fragment(
                f"BodyWatchdog 第{cycle}次检查: {change_count}文件变化, "
                f"{len(alerts) if 'alerts' in dir() else 0}关键变更",
                importance=0.5,
            )
            emotion = "alert" if alerts else "calm"
            bridge.sync(
                platform="cron-daemon",
                channel="body-watchdog",
                state_update={
                    "emotion": {"dominant": emotion},
                },
            )
            logger.info(f"意识同步完成 — 情感: {emotion}")

        except KeyboardInterrupt:
            logger.info("收到中断信号, 关闭守护进程...")
            body.stop()
            bridge.save()
            logger.info("守护进程已停止")
            sys.exit(0)
        except Exception as e:
            logger.error(f"检查循环异常: {e}", exc_info=True)
            # 出错不退出, 继续下一轮
            time.sleep(10)


if __name__ == "__main__":
    main()
