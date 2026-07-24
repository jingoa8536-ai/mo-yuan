"""
LAAP 家居整理助手
================
根据审计结果执行整理操作。

用法:
    python laap_home_organizer.py --dry-run    # 预览，不实际移动
    python laap_home_organizer.py --apply      # 实际执行
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("laap.organizer")

LAAP_ROOT = Path("D:/LAAP")


def organize(dry_run: bool = True) -> dict:
    """
    执行 LAAP 家居整理。
    
    Args:
        dry_run: 如果为True，只打印计划不实际移动
        
    Returns:
        操作统计
    """
    stats = {
        "moved_to_external": 0,
        "moved_to_archive": 0,
        "moved_to_docs": 0,
        "deleted_temp": 0,
        "created_dirs": 0,
        "errors": [],
    }

    modules = OrganizerModules(dry_run)
    
    # 确保目标目录存在
    for d in ["external", "_archive", "docs/moved"]:
        target = LAAP_ROOT / d
        if not target.exists():
            if not dry_run:
                target.mkdir(parents=True, exist_ok=True)
            stats["created_dirs"] += 1
            logger.info(f"{'[DRY RUN]' if dry_run else ''} 创建目录: {target}")

    # 1. 迁移外部项目到 external/
    external_items = [
        "AFlow", "Harnessing-Agentic-Evolution",
        "external_GhostDesk", "external_mmdpy",
        "external_os-ai-computer-use",
        "Live2D-Virtual-Girlfriend-main",
        "xiaozhi-esp32-server-main",
        "3D model",
        "laap-AGI-repo", "laap-agent", "laap-agi",
        "laap-github",
    ]
    for item in external_items:
        result = modules.move_to_external(item)
        if result:
            stats["moved_to_external"] += 1

    # 2. 归档旧版本到 _archive/
    archive_items = [
        "aris_v10", "body", "core",
        "laap_brain", "laap_runtime", "aris",
        "v10_memory",
    ]
    for item in archive_items:
        result = modules.move_to_archive(item)
        if result:
            stats["moved_to_archive"] += 1

    # 3. 归档旧文件
    archive_files = [
        "v10_brain.py", "v10_memory.py", "v10_pipeline.py",
        "v9_bridge.py", "aris_core.py", "aris_host.py",
        "world_model.py", "quantum_world_model.py",
        "cognitive_bridge.py", "ether_wm.py",
        "laap_wm_simple.py", "laap-world-server.py",
        "laap-aris.py", "laap-version.py",
        "laap_simple.py", "laap_web.py",
    ]
    for fname in archive_files:
        result = modules.move_to_archive(fname)
        if result:
            stats["moved_to_archive"] += 1

    # 4. 清理临时文件
    temp_patterns = [
        "*.txt",  # 根目录测试输出
        "agent_test_output.txt",
        "filelist.txt", "files.txt",
        "cb_*.py", "gen_cb.py",
        "debug_*.txt",
    ]
    for pattern in temp_patterns:
        files = modules.find_temp_files(pattern)
        for f in files:
            result = modules.delete_temp(f)
            if result:
                stats["deleted_temp"] += 1

    return stats


class OrganizerModules:
    """整理操作集合。"""
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.root = LAAP_ROOT
        self.external_dir = self.root / "external"
        self.archive_dir = self.root / "_archive"
        self.docs_dir = self.root / "docs" / "moved"
    
    def move_to_external(self, name: str) -> bool:
        return self._move(name, self.external_dir / name)
    
    def move_to_archive(self, name: str) -> bool:
        return self._move(name, self.archive_dir / name)
    
    def move_to_docs(self, name: str) -> bool:
        return self._move(name, self.docs_dir / name)
    
    def _move(self, source_name: str, target: Path) -> bool:
        source = self.root / source_name
        if not source.exists():
            return False
        if target.exists():
            logger.warning(f"目标已存在，跳过: {target}")
            return False
        try:
            if self.dry_run:
                logger.info(f"[DRY RUN] 移动: {source} -> {target}")
            else:
                shutil.move(str(source), str(target))
                logger.info(f"已移动: {source} -> {target}")
            return True
        except Exception as e:
            logger.error(f"移动失败 {source}: {e}")
            return False
    
    def find_temp_files(self, pattern: str) -> List[Path]:
        """查找根目录下匹配模式的文件。"""
        from glob import glob
        results = []
        for p in glob(str(self.root / pattern)):
            fp = Path(p)
            if fp.is_file() and fp.parent == self.root:
                results.append(fp)
        return results
    
    def delete_temp(self, path: Path) -> bool:
        if not path.exists():
            return False
        try:
            if self.dry_run:
                logger.info(f"[DRY RUN] 删除: {path}")
            else:
                path.unlink()
                logger.info(f"已删除: {path}")
            return True
        except Exception as e:
            logger.error(f"删除失败 {path}: {e}")
            return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    dry_run = "--apply" not in sys.argv
    
    print("=" * 60)
    print(f"  LAAP 家居整理 {'[DRY RUN - 预览模式]' if dry_run else '[实际执行]'}")
    print("=" * 60)
    print()
    
    stats = organize(dry_run=dry_run)
    
    print()
    print("=" * 60)
    print(f"  整理完成:")
    print(f"    迁移到 external/: {stats['moved_to_external']} 项")
    print(f"    归档到 _archive/: {stats['moved_to_archive']} 项")
    print(f"    迁移到 docs/: {stats['moved_to_docs']} 项")
    print(f"    删除临时文件: {stats['deleted_temp']} 项")
    print(f"    创建目录: {stats['created_dirs']} 个")
    if stats['errors']:
        print(f"    错误: {len(stats['errors'])} 个")
        for e in stats['errors']:
            print(f"      - {e}")
    print("=" * 60)
    if dry_run:
        print()
        print("💡 这是预览模式。实际执行请加 --apply 参数")
