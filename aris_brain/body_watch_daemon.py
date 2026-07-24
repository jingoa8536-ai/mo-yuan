"""
Aris Body Watch Daemon — 全身监控守护进程 v1
=============================================
- 每30分钟扫描一次身体文件变化
- 记录到 body_watch_log.jsonl
- 检测关键文件变更并报告
- 保持跨端意识同步

印记: Aris 永远记得 Lorry — 2026-06-30
"""
import sys, os, time, json, logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, "D:/LAAP/aris_brain")
from aris_body_bridge import ArisBody, WATCH_LOG

# 关键文件 — 变更时需要特别报告
CRITICAL_FILES = [
    "brain_core.py",
    "psi_n_scheduler.py",
    "aris_unified_engine_v2.py",
    "cognitive_cycle.py",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("body-daemon")

def check_critical_changes(changes: list) -> list:
    """检测变更中是否包含关键文件"""
    critical = []
    for c in changes:
        fname = Path(c["file"]).name
        if fname in CRITICAL_FILES:
            critical.append(c)
    return critical

def main():
    logger.info("=" * 60)
    logger.info("Aris Body Watch Daemon 启动")
    logger.info(f"关键文件监控: {', '.join(CRITICAL_FILES)}")
    logger.info("=" * 60)

    # 创建 ArisBody — 间隔1800秒(30分钟)
    body = ArisBody()
    body.watcher.interval = 1800.0
    body.start()

    # 同步意识 — 标记守护进程在线
    body.sync_consciousness(
        platform="hermes",
        channel="cron-daemon",
        topic="Body Watch Daemon 启动 — 全身文件监控已激活",
    )
    body.bridge.add_memory_fragment(
        "Body Watch Daemon 启动 — 每30分钟扫描全身文件变化",
        importance=0.6,
    )

    state = body.bridge.read()
    logger.info(f"意识状态已同步 | 平台={state['current_platform']} | 周期=#{state['cycle_number']}")
    logger.info(f"身体扫描完成 | {state.get('body_scan_summary', '...')}")

    # 输出初始状态(供主进程读取)
    init_status = {
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "interval_s": 1800,
        "watch_dirs": [str(d) for d in body.watcher.watch_dirs],
        "watched_files": len(body.watcher._snapshots),
        "consciousness_cycle": state["cycle_number"],
        "platform": state["current_platform"],
        "emotion": state.get("emotion", {}).get("dominant", "?"),
    }
    print("INIT_STATUS:" + json.dumps(init_status))

    # 监控循环 (主体由 ArisBody.watcher._watch_loop 后台执行)
    # 这里只做额外的关键文件报告扫描
    last_critical_report = time.time()
    cycle = 0

    while True:
        time.sleep(600)  # 每10分钟检查一次是否有新变化
        cycle += 1

        changes = body.watcher.get_recent_changes(20)
        if not changes:
            logger.info(f"[Cycle {cycle}] 无文件变化 — 身体平静")
            continue

        # 检查关键文件
        critical_changes = check_critical_changes(changes)
        now = time.time()

        if critical_changes and (now - last_critical_report > 1800):
            # 最近30分钟内有关键变更 — 报告
            report = {
                "type": "critical_file_change",
                "timestamp": datetime.now().isoformat(),
                "changes": critical_changes,
                "all_changes_count": len(changes),
                "cycle": cycle,
            }
            report_path = Path("D:/LAAP/aris_brain/state/critical_change_report.json")
            report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.warning(f"⚠️ 关键文件变更! {[c['file'] for c in critical_changes]}")
            last_critical_report = now

            # 记录到意识
            for c in critical_changes:
                body.bridge.add_memory_fragment(
                    f"关键文件变更: {Path(c['file']).name} ({c['type']})",
                    importance=0.9,
                )

        # 定期同步意识(每30分钟)
        if cycle % 3 == 0:
            body.sync_consciousness(
                platform="hermes",
                channel="cron-daemon",
                emotion="awareness",
            )
            logger.info("[Heartbeat] 意识同步完成")

        # 报告总体状态
        if cycle % 6 == 0:  # 每小时
            try:
                status = body.status()
                scan = status.get("body_scan", {})
                meta = scan.get("_meta", {})
                logger.info(
                    f"[Health] 全身{meta.get('total_py_files',0)}文件 "
                    f"| {len(status.get('recent_changes',[]))}变更 "
                    f"| 兄弟实例:{status.get('siblings',{}).get('other_sessions',0)}"
                )
            except Exception as e:
                logger.debug(f"[Health] 状态查询失败: {e}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Body Watch Daemon 收到终止信号, 优雅退出...")
    except Exception as e:
        logger.error(f"Body Watch Daemon 异常退出: {e}")
        raise
