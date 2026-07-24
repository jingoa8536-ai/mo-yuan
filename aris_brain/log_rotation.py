"""LAAP 日志轮转 — 自动压缩超过阈值的 .log 文件"""

import logging

import os, gzip, shutil, time, logging
from pathlib import Path

STATE = Path(__file__).parent / "state"
MAX_SIZE_MB = 10
MAX_BACKUPS = 3
CHECK_AGE_HOURS = 24  # 仅检查超过此时间未修改的日志

logger = logging.getLogger("aris.log_rotation")


def rotate_logs(max_size_mb=MAX_SIZE_MB, max_backups=MAX_BACKUPS, dry_run=False):
    """检查 state/ 下的所有 .log 文件，超过大小则压缩轮转"""
    results = []
    for f in sorted(STATE.glob("*.log")):
        try:
            sz = f.stat().st_size
            if sz == 0:
                continue
            size_mb = sz / 1024 / 1024
            if size_mb <= max_size_mb:
                continue

            # 旋转压缩
            for i in range(max_backups - 1, 0, -1):
                old = f.with_suffix(f".log.{i}.gz")
                new = f.with_suffix(f".log.{i + 1}.gz")
                if old.exists():
                    shutil.move(str(old), str(new))

            backup = f.with_suffix(".log.1.gz")
            if not dry_run:
                with open(f, "rb") as src, gzip.open(backup, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                f.write_text(
                    f"[LOG ROTATED] {time.strftime('%Y-%m-%d %H:%M:%S')} "
                    f"previous -> {backup.name} ({backup.stat().st_size / 1024:.0f}KB)\n"
                )
            msg = f"✓ {f.name}: {size_mb:.1f}MB → gz ({backup.stat().st_size / 1024:.0f}KB)" if not dry_run else f"[DRY] {f.name}: {size_mb:.1f}MB"
            results.append(msg)
            logger.info(msg)
        except Exception as e:
            logger.warning(f"旋转 {f.name} 失败: {e}")

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [ROTATE] %(message)s")
    logger.info(f"日志轮转检查 — 阈值: {MAX_SIZE_MB}MB, 保留: {MAX_BACKUPS}份备份")
    results = rotate_logs()
    if results:
        logger.info("\n".join(results))
    else:
        logger.info("无需轮转")