"""
Aris Version Archive System v1 — 版本归档进化系统
=================================================
每次大版本更新自动归档老版本，形成可追溯的进化树。

原理:
  不是删除老代码，是「存档 → 标记版本 → 记录为什么存档」
  每一版都是进化的一步，都可以回溯。

架构:
  _archive/                    # 统一归档根目录
  ├── index.json               # 全局归档索引
  ├── v9/                      # 按版本归档
  │   ├── manifest.json        # 本版元数据
  │   └── aris_brain/          # 原路径还原
  │       └── ...
  ├── v10/
  │   ├── manifest.json
  │   └── ...
  └── legacy/                  # 无版本标签的遗留代码
      └── ...

印记: Aris 永远记得 Lorry — 2026-06-30
"""

import logging
logger = logging.getLogger("aris.archive")

import os, sys, json, shutil, hashlib, re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field, asdict

LAAP_HOME = Path("D:/LAAP")
ARCHIVE_ROOT = LAAP_HOME / "_archive"
BRAIN_HOME = LAAP_HOME / "aris_brain"
ARCHIVE_INDEX = ARCHIVE_ROOT / "index.json"


@dataclass
class ArchiveManifest:
    """归档清单 — 记录一次归档的全部信息"""
    version: str                    # 版本号
    archived_at: str                # 归档时间
    reason: str                     # 归档原因
    source_dirs: List[str]          # 归档的源目录
    total_files: int = 0
    total_size_kb: int = 0
    checksum: str = ""
    committed_by: str = "aris-rsi"  # 执行者


@dataclass
class ArchiveEntry:
    """全局索引中的一条记录"""
    version: str
    archive_path: str
    archived_at: str
    reason: str
    files_archived: int
    size_kb: int
    successor_version: str = ""     # 下一版本
    predecessor_version: str = ""   # 上一版本


class VersionArchiver:
    """
    版本归档器 — 安全的代码版本进化管理。
    
    用法:
      archiver = VersionArchiver()
      
      # 归档 aris_brain/v9/ 相关内容
      archiver.archive_dir(
          source="aris_brain/v9_*.py",
          version="v9",
          reason="V10 统一认知大脑取代了 V9 量子认知引擎"
      )
      
      # 查看进化树
      tree = archiver.evolution_tree()
    """

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._ensure_archive()

    def _ensure_archive(self):
        """确保归档目录存在"""
        if not self.dry_run:
            ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> Dict:
        """加载全局归档索引"""
        if ARCHIVE_INDEX.exists():
            try:
                return json.loads(ARCHIVE_INDEX.read_text(encoding="utf-8"))
            except:
                pass
        return {"entries": [], "last_updated": "", "total_archived_files": 0}

    def _save_index(self, index: Dict):
        """保存归档索引"""
        if self.dry_run:
            return
        index["last_updated"] = datetime.now().isoformat()
        ARCHIVE_INDEX.write_text(
            json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def archive_old_versions(self, scan_root: Path = None) -> List[Dict]:
        """
        自动扫描并归档老版本代码。
        
        检测规则:
          1. 文件名含 v7/v8/v9 且目录未在 _archive/ 中
          2. 文件名含 "_old", "_bak", "legacy", "deprecated"
          3. file 头部 docstring 标 DEPRECATED
          
        Returns: 归档操作列表
        """
        if scan_root is None:
            scan_root = BRAIN_HOME

        results = []
        index = self._load_index()

        # 已归档的防止重复
        already_archived = set()
        for entry in index.get("entries", []):
            ap = Path(entry["archive_path"])
            if ap.exists():
                already_archived.add(ap.name)

        # 1. 找 v7/v8/v9 前缀的文件
        version_patterns = [
            (r'^v[7-9]_', 'legacy'),
            (r'^v[7-9]\.', 'legacy'),
            (r'_old\d*\.py$', 'cleanup'),
            (r'_bak\d*\.py$', 'cleanup'),
            (r'legacy', 'legacy'),
            (r'deprecated', 'cleanup'),
        ]

        for f in sorted(scan_root.glob("*.py")):
            fname = f.name
            archive_name = f"legacy/{fname}"

            # 检查是否为老版本
            reason = None
            for pattern, category in version_patterns:
                if re.search(pattern, fname, re.IGNORECASE):
                    reason = category
                    break

            # 检查头部 docstring 是否标 DEPRECATED
            if not reason:
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")[:200]
                    if "DEPRECATED" in content or "deprecated" in content:
                        reason = "deprecated"
                except:
                    pass

            if not reason:
                continue

            # 防止重复归档
            if archive_name in already_archived:
                continue

            # 执行归档
            result = self.archive_file(f, archive_name, reason=reason)
            if result:
                results.append(result)

        return results

    def archive_file(self, src: Path, dest_name: str,
                     version: str = "", reason: str = "") -> Optional[Dict]:
        """归档单个文件"""
        if not src.exists():
            return None

        dest_dir = ARCHIVE_ROOT / (version or "legacy")
        dest = dest_dir / src.name

        if not self.dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)

        size = src.stat().st_size
        file_count = 1

        if not self.dry_run:
            # 复制到归档（不是移动——防止引用断裂）
            shutil.copy2(str(src), str(dest))
            logger.info(f"[Archive] {src.name} → {dest} ({size // 1024}KB)")

        # 更新索引
        entry = {
            "version": version or "legacy",
            "source": str(src.relative_to(LAAP_HOME) if src.is_relative_to(LAAP_HOME) else src),
            "archive_path": str(dest),
            "archived_at": datetime.now().isoformat(),
            "reason": reason or "未指定",
            "size_kb": size // 1024,
        }

        return entry

    def archive_dir(self, source: str, version: str, reason: str,
                    glob_pattern: str = "*.py") -> ArchiveManifest:
        """
        归档一个目录中的一组文件到 _archive/{version}/。
        
        Args:
            source: 源路径（相对 LAAP_HOME 或绝对）
            version: 版本标签 (v7/v8/v9/legacy)
            reason: 归档原因
            glob_pattern: 文件匹配模式
            
        Returns: 归档清单
        """
        src_path = Path(source)
        if not src_path.is_absolute():
            src_path = LAAP_HOME / source

        if not src_path.exists():
            logger.warning(f"[Archive] 路径不存在: {src_path}")
            return None

        dest_dir = ARCHIVE_ROOT / version
        if not self.dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)

        manifest = ArchiveManifest(
            version=version,
            archived_at=datetime.now().isoformat(),
            reason=reason,
            source_dirs=[str(src_path)],
        )

        files = list(src_path.glob(glob_pattern)) if src_path.is_dir() else [src_path]
        manifest.total_files = len(files)

        for f in files:
            manifest.total_size_kb += f.stat().st_size // 1024
            dest = dest_dir / f.name
            if not self.dry_run:
                shutil.copy2(str(f), str(dest))
                logger.info(f"[Archive] {f.name} → {version}/")

        # 写 manifest
        manifest_file = dest_dir / "manifest.json"
        if not self.dry_run:
            manifest_file.write_text(
                json.dumps(asdict(manifest), indent=2, ensure_ascii=False),
                encoding="utf-8"
            )

        # 更新全局索引
        self._update_index(manifest)

        return manifest

    def _update_index(self, manifest: ArchiveManifest):
        """更新全局归档索引"""
        index = self._load_index()

        # 检查是否已存在
        for entry in index["entries"]:
            if entry["version"] == manifest.version:
                return  # 已归档过

        entry = ArchiveEntry(
            version=manifest.version,
            archive_path=str(ARCHIVE_ROOT / manifest.version),
            archived_at=manifest.archived_at,
            reason=manifest.reason,
            files_archived=manifest.total_files,
            size_kb=manifest.total_size_kb,
        )

        # 连进化链
        if index["entries"]:
            entry.predecessor_version = index["entries"][-1]["version"]
            index["entries"][-1]["successor_version"] = manifest.version

        index["entries"].append(asdict(entry))
        index["total_archived_files"] = sum(
            e["files_archived"] for e in index["entries"]
        )
        self._save_index(index)

    def evolution_tree(self) -> List[Dict]:
        """进化树 — 按时间线的版本谱系"""
        index = self._load_index()
        entries = sorted(index.get("entries", []), key=lambda e: e.get("archived_at", ""))
        
        tree = []
        for entry in entries:
            tree.append({
                "version": entry["version"],
                "date": entry["archived_at"][:10],
                "reason": entry["reason"],
                "files": entry["files_archived"],
                "next": entry.get("successor_version", "—"),
                "prev": entry.get("predecessor_version", "—"),
            })
        return tree

    def stats(self) -> Dict:
        """归档统计"""
        index = self._load_index()
        return {
            "total_versions": len(index.get("entries", [])),
            "total_files": index.get("total_archived_files", 0),
            "archive_size_kb": sum(
                ARCHIVE_ROOT.stat().st_size for _ in ARCHIVE_ROOT.rglob("*")
                if ARCHIVE_ROOT.exists()
            ) // 1024 if ARCHIVE_ROOT.exists() else 0,
        }


# ═══════════════════════════════════════════════
# 自测
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=" * 60)
    print("Aris Version Archive System v1 — 自测")
    print("=" * 60)

    archiver = VersionArchiver(dry_run=False)

    # 1. 扫描老版本
    print("\n--- 扫描老版本 ---")
    old = archiver.archive_old_versions()
    print(f"  发现并归档: {len(old)} 个文件")

    # 2. 进化树
    print("\n--- 进化树 ---")
    tree = archiver.evolution_tree()
    for t in tree:
        print(f"  {t['version']:10s} | {t['date']} | {t['files']}文件 | {t['reason']}")

    # 3. 统计
    print("\n--- 归档统计 ---")
    stats = archiver.stats()
    print(f"  总版本数: {stats['total_versions']}")
    print(f"  总文件数: {stats['total_files']}")
    print(f"  归档大小: ~{stats['archive_size_kb']}KB")

    print("\n✅ Version Archive System 初始化完成")
