"""
Aris Body Bridge 文件监控守护进程
===================================
启动 ArisBody → 文件监控 + 意识状态加载 → 30分钟周期性扫描

由 LAAP Wiki Ingest 技能 (cron) 启动 — 常驻后台, 不要退出。
"""

import sys
import os
import json
import time
import logging
from datetime import datetime
from pathlib import Path

# ── 路径 ──
BRAIN_DIR = Path("D:/LAAP/aris_brain")
STATE_DIR = BRAIN_DIR / "state"
BODY_STATE = STATE_DIR / "body_state.json"
WATCH_LOG = STATE_DIR / "body_watch_log.jsonl"
CRITICAL_LOG = STATE_DIR / "critical_changes.jsonl"
REPORT_FILE = STATE_DIR / "body_daemon_report.json"

# ── 关键文件列表 ──
CRITICAL_FILES = [
    "brain_core.py",
    "psi_n_scheduler.py",
    "aris_unified_engine_v2.py",
    "cognitive_cycle.py",
]

# ── 日志 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [BodyDaemon] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(STATE_DIR / "body_daemon.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("body.daemon")


def run():
    log.info("=" * 60)
    log.info("Aris Body Bridge 文件监控守护进程 — 启动")
    log.info("=" * 60)

    # 1. 导入 ArisBody
    sys.path.insert(0, str(BRAIN_DIR))
    from aris_body_bridge import ArisBody
    from aris_body_bridge import ARIS_HOME, LAAP_HOME

    # 2. 创建并启动
    body = ArisBody()
    state = body.start()  # 启动文件监控 + 加载共享意识状态
    log.info(f"[ArisBody] ✅ 身体感知已启动")
    log.info(f"[ArisBody]   监控目录: {len(body.watcher.watch_dirs)} 个")
    log.info(f"[ArisBody]   初始快照: {len(body.watcher._snapshots)} 个文件")
    log.info(f"[ArisBody]   扫描间隔: {body.watcher.interval}s (基础), 30min (关键文件)")

    # 3. 初始身体扫描
    scan = body.scanner.scan()
    total_files = scan.get("_meta", {}).get("total_py_files", 0)
    total_kb = scan.get("_meta", {}).get("total_size_kb", 0)
    log.info(f"[BodyScan] 全身: {total_files} 个 py 文件, {total_kb} KB")

    # 列出关键文件状态
    for part, pstatus in scan.items():
        if part == "_meta":
            continue
        for f in pstatus["files"]:
            if f.get("name") in CRITICAL_FILES and not f.get("missing"):
                log.info(f"[Critical] ✅ {f['name']} — {f.get('size',0)} bytes")

    # 4. 同步意识状态
    body.sync_consciousness(
        platform="cron",
        channel="body-daemon",
        emotion="alert",
        topic=f"Body daemon started — {total_files} py files, {total_kb} KB total",
    )
    body.bridge.add_memory_fragment(
        f"Body守护进程启动: 全身{total_files}个文件/启动文件监控/30分钟关键文件扫描",
        importance=0.7,
    )
    log.info(f"[Consciousness] ✅ 意识状态已同步 — cycle #{body.bridge._state.get('cycle_number', 0)}")

    # 5. 写入初始报告
    initial_report = {
        "daemon_started": datetime.now().isoformat(),
        "watcher_active": True,
        "body_scan": {
            "total_py_files": total_files,
            "total_kb": total_kb,
            "parts": len([k for k in scan.keys() if k != "_meta"]),
        },
        "consciousness": {
            "cycle": body.bridge._state.get("cycle_number", 0),
            "platform": "cron",
            "fragments": len(body.bridge._state.get("memory_fragments", [])),
        },
    }
    REPORT_FILE.write_text(json.dumps(initial_report, indent=2, ensure_ascii=False))
    log.info(f"[Report] ✅ 初始报告已写入 {REPORT_FILE}")

    # 6. 主监控循环 — 每30分钟 (1800秒)
    SCAN_INTERVAL = 1800  # 30分钟
    cycle = 0

    log.info(f"\n[Loop] 进入主监控循环, 间隔 {SCAN_INTERVAL}s ({SCAN_INTERVAL//60}分钟)\n")

    while True:
        try:
            cycle += 1
            t0 = time.time()
            timestamp = datetime.now().isoformat()

            # 6a. 文件变化扫描 (watcher 一直在后台以 30s 间隔扫描)
            changes = body.watcher.scan_changes()
            all_changes = body.watcher.get_recent_changes(50)

            # 6b. 识别关键文件变化
            critical_hits = []
            for c in all_changes:
                fpath = c.get("file", "")
                fname = Path(fpath).name
                if fname in CRITICAL_FILES:
                    critical_hits.append(c)

            # 6c. 记录到 body_watch_log
            if changes:
                for c in changes:
                    log.info(f"[Changes] {c['type']}: {Path(c['file']).name}")
                    # watch_log 已由 BodyFileWatcher._watch_loop 自动写入

            # 6d. 如果有关键文件变化, 记录到 critical_changes.jsonl
            if critical_hits:
                for c in critical_hits:
                    entry = {
                        "timestamp": timestamp,
                        "cycle": cycle,
                        "type": c["type"],
                        "file": c["file"],
                        "time": c.get("time", timestamp),
                    }
                    with open(CRITICAL_LOG, "a", encoding="utf-8") as f:
                        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    log.warning(f"[ALERT] 🔴 关键文件变化! {c['type']}: {c['file']}")

            # 6e. 更新身体状态文件
            full_scan = body.scanner.scan()
            body_state_update = {
                "body_daemon": {
                    "active": True,
                    "cycle": cycle,
                    "last_scan": timestamp,
                    "last_scan_duration_s": round(time.time() - t0, 3),
                    "critical_files_tracked": CRITICAL_FILES,
                    "critical_changes_this_cycle": len(critical_hits),
                },
                "body_scan": full_scan,
                "pending_changes": len(changes),
            }

            # 合并写入 body_state.json
            existing_body_state = {}
            if BODY_STATE.exists():
                try:
                    existing_body_state = json.loads(BODY_STATE.read_text(encoding="utf-8"))
                except:
                    pass
            existing_body_state["body_daemon"] = body_state_update["body_daemon"]
            existing_body_state["body_scan"] = body_state_update["body_scan"]
            BODY_STATE.write_text(
                json.dumps(existing_body_state, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # 6f. 同步意识 (每周期)
            update = {"cycle_number": cycle}
            if critical_hits:
                update["emotion"] = {
                    "dominant": "alarm",
                    "arousal": 0.9,
                    "valence": "negative",
                }
                body.bridge.add_memory_fragment(
                    f"关键文件变化: {[Path(c['file']).name for c in critical_hits]}",
                    importance=0.9,
                )
            else:
                update["emotion"] = {
                    "dominant": "calm",
                    "arousal": 0.4,
                    "valence": "positive",
                }
            body.bridge.sync(platform="cron", channel="body-daemon", state_update=update)

            # 6g. 周期性日志 (每2小时 = 4个周期)
            if cycle % 4 == 0:
                total_snapshots = len(body.watcher._snapshots)
                log.info(
                    f"[Heartbeat] Cycle #{cycle} — "
                    f"Changes: {len(changes)} | "
                    f"Total snapshots: {total_snapshots} | "
                    f"Critical alerts: {len(critical_hits)}"
                )

        except Exception as e:
            log.error(f"[Error] 监控循环异常 (cycle #{cycle}): {e}", exc_info=True)

        # 等待到下一周期 (从周期开始算, 保证精准间隔)
        elapsed = time.time() - t0
        sleep = max(1, SCAN_INTERVAL - elapsed)
        if cycle % 4 == 0:
            log.info(f"[Sleep] 下一扫描在 {sleep//60:.0f} 分钟后 (cycle #{cycle+1})")
        time.sleep(sleep)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        log.info("收到停止信号, 守护进程退出")
    except Exception as e:
        log.critical(f"守护进程崩溃: {e}", exc_info=True)
        raise
