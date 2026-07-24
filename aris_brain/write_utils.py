"""
write_utils.py — 原子文件写入 + 安全归档工具

写入保护：
  临时文件 + fsync + os.replace() 保证写入原子性。
  即使崩溃也不会产生半写文件。

归档策略：
  先归档再删除。归档到 target/_archive/YYYY-MM/ 目录下，
  保留所有历史数据的可追溯性。
"""

import logging
logger = logging.getLogger(__name__)

import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Union

_PATH_LOCK = {}


def atomic_write_json(
    data: Any,
    path: Union[str, Path],
    *,
    ensure_ascii: bool = False,
    indent: int = 2,
    default: Any = None,
) -> None:
    """
    原子写入 JSON 文件。

    策略：
      - 在目标文件同目录创建临时文件
      - 写入 JSON 并 fsync
      - os.replace() 覆盖目标文件
      - Windows 下 os.replace() 保证是原子操作（NTFS 文件系统级别）
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            kwargs = {"ensure_ascii": ensure_ascii, "indent": indent}
            if default is not None:
                kwargs["default"] = default
            json.dump(data, f, **kwargs)
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError as e:
            logger.debug(f"操作失败: {e}")
        raise

    os.replace(str(tmp_path), str(path))


def safe_read_json(path: Union[str, Path], default: Any = None) -> Any:
    """
    安全读取 JSON 文件。文件不存在或损坏时返回 default。
    损坏文件自动备份为 .corrupted 后缀。
    """
    path = Path(path)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        backup = path.with_suffix(path.suffix + ".corrupted")
        try:
            os.replace(str(path), str(backup))
        except OSError as e:
            logger.debug(f"操作失败: {e}")
        return default


def archive_files(
    patterns: List[str],
    base_dir: Union[str, Path],
    *,
    archive_dir: Optional[Union[str, Path]] = None,
    keep: int = 0,
    label: str = "",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    归档匹配模式的文件到 _archive/{YYYY-MM}/ 目录。

    Args:
        patterns: glob 模式列表，如 ['state/aris_speech_*.mp3', 'state/milestone_cycle_*.json']
        base_dir: 搜索根目录
        archive_dir: 归档目录（默认 base_dir / '_archive'）
        keep: 保留最近 N 个文件（按 mtime），其余归档
        label: 日志标签
        dry_run: 只展示不动手

    Returns:
        {"archived": 归档数, "kept": 保留数, "skipped": 跳过数, "errors": [...]}
    """
    base_dir = Path(base_dir)
    archive_root = Path(archive_dir) if archive_dir else base_dir / "_archive"
    archive_root.mkdir(parents=True, exist_ok=True)

    month_dir = archive_root / time.strftime("%Y-%m")
    month_dir.mkdir(parents=True, exist_ok=True)

    result: Dict[str, Any] = {"archived": 0, "kept": 0, "skipped": 0, "errors": []}

    for pattern in patterns:
        files = sorted(
            base_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime if p.exists() else 0,
            reverse=True,
        )

        to_archive = files[keep:] if keep > 0 else files
        to_keep = files[:keep] if keep > 0 else []

        result["kept"] += len(to_keep)

        for f in to_archive:
            dest = month_dir / f.name
            # 避免重名冲突
            if dest.exists():
                stem = dest.stem
                suffix = dest.suffix
                dest = month_dir / f"{stem}_{int(time.time())}{suffix}"

            if dry_run:
                logger.info(f"  [DRY RUN] Would archive: {f} -> {dest}")
                result["archived"] += 1
                continue

            try:
                shutil.copy2(str(f), str(dest))
                os.unlink(str(f))
                result["archived"] += 1
            except Exception as e:
                result["errors"].append(str(e))

    tag = f" [{label}]" if label else ""
    if not dry_run:
        print(
            f"[Archive{tag}] {result['archived']} archived, "
            f"{result['kept']} kept, {len(result['errors'])} errors"
        )
        if result["errors"]:
            for e in result["errors"][:5]:
                logger.error(f"  ERROR: {e}")
    return result


def clean_state_dir(
    state_dir: Union[str, Path],
    *,
    archive_to: Optional[Union[str, Path]] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    标准化的 state/ 目录清理。
    规则：
      - 废弃 speech mp3: 全部归档 (keep=0)
      - milestone 文件: 保留最近 20 个，其余归档
      - 旧的 state_cycle_*: 全部归档
      - .wav 录音: 全部归档
      - >2MB 的单体日志: gzip（不归档）
      - 孤立 .npz 缓存: 保留（可能被引用）
    """
    state_dir = Path(state_dir)
    total: Dict[str, Any] = {
        "speech_mp3": {"archived": 0, "kept": 0},
        "milestones": {"archived": 0, "kept": 0},
        "state_cycles": {"archived": 0, "kept": 0},
        "wav_files": {"archived": 0, "kept": 0},
        "gzipped_logs": 0,
    }

    rules = [
        ("speech_mp3", "aris_speech_*.mp3", 0),
        ("milestones", "milestone_cycle_*.json", 20),
        ("state_cycles", "state_cycle_*.json", 0),
        ("wav_files", "*.wav", 0),
    ]

    for key, pattern, keep in rules:
        r = archive_files(
            [pattern],
            state_dir,
            archive_dir=archive_to,
            keep=keep,
            label=key,
            dry_run=dry_run,
        )
        total[key] = {"archived": r["archived"], "kept": r["kept"]}

    # 大日志 gzip
    if not dry_run:
        for f in state_dir.glob("*.log"):
            if f.stat().st_size > 2 * 1024 * 1024:  # >2MB
                import gzip
                gz_path = f.with_suffix(f.suffix + ".gz")
                if not gz_path.exists():
                    with open(f, "rb") as src, gzip.open(gz_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    os.unlink(str(f))
                    total["gzipped_logs"] += 1

    if not dry_run:
        logger.info(f"\n[clean_state_dir] Done: {sum(v['archived'] for v in total.values() if isinstance(v, dict))} archived, {total['gzipped_logs']} logs gzipped")
    return total
