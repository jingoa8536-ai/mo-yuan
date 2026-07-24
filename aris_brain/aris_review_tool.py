"""
Aris Review Tool — 后生成质量门 (Claude Code ReviewArtifactTool 模式)
==================================================================
从 Claude Code 的 ReviewArtifactTool 学到的模式:
  每次生成代码/文件后立即触发质量审查
  在错误固化之前拦截

工作方式:
  - 监控目标目录的新文件变化
  - 对新生成/修改的文件运行质量检查
  - 集成 pylint/ruff/mypy 等静态分析
  - 输出审查报告到 state/reviews/
"""

import logging

import json, os, sys, time, subprocess, hashlib, logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple

BRAIN_ROOT = Path(os.environ.get("ARIS_BRAIN_ROOT", "D:/LAAP/aris_brain"))
sys.path.insert(0, str(BRAIN_ROOT))

REVIEW_DIR = BRAIN_ROOT / "state" / "reviews"
WATCH_DIRS = [
    BRAIN_ROOT,  # LAAP 主目录
    Path.home() / "AppData/Local/hermes/profiles/aris/skills",  # Skills
]

# 需要审查的文件扩展名
REVIEW_EXTENSIONS = {".py", ".bat", ".vbs", ".sh", ".yaml", ".yml", ".json", ".toml"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [REVIEW] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(REVIEW_DIR.parent / "review.log"), mode="a")
    ]
)
logger = logging.getLogger("aris.review")


class FileTracker:
    """追踪文件变更"""

    def __init__(self, track_path: Path):
        self.track_path = track_path
        self.data = self._load()

    def _load(self) -> dict:
        if self.track_path.exists():
            try:
                return json.loads(self.track_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        return {}

    def save(self):
        self.track_path.parent.mkdir(parents=True, exist_ok=True)
        self.track_path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2),
                                   encoding="utf-8")

    def get_hash(self, filepath: Path) -> Optional[str]:
        key = str(filepath)
        return self.data.get(key, {}).get("hash")

    def set_hash(self, filepath: Path, file_hash: str, mtime: float):
        key = str(filepath)
        self.data[key] = {"hash": file_hash, "mtime": mtime, "last_seen": datetime.now(timezone.utc).isoformat()}


def compute_file_hash(filepath: Path) -> str:
    """计算文件内容的 SHA256"""
    try:
        return hashlib.sha256(filepath.read_bytes()).hexdigest()
    except Exception:
        return ""


def find_changed_files(watch_dirs: List[Path], extensions: set,
                       tracker: FileTracker) -> List[Path]:
    """找出新增和修改的文件"""
    changed = []
    for watch_dir in watch_dirs:
        if not watch_dir.exists():
            continue
        for ext in extensions:
            for filepath in watch_dir.rglob(f"*{ext}"):
                if filepath.is_file():
                    # 跳过 state/ logs/ .git/ __pycache__/ .codegraph/
                    parts = filepath.parts
                    skip_dirs = {"state", ".git", "__pycache__", ".codegraph",
                                 "node_modules", "venv", ".venv"}
                    if any(p in skip_dirs for p in parts):
                        continue

                    current_hash = compute_file_hash(filepath)
                    previous_hash = tracker.get_hash(filepath)

                    if current_hash and current_hash != previous_hash:
                        changed.append(filepath)

    return changed


def review_python_file(filepath: Path) -> dict:
    """审查 Python 文件"""
    issues = []

    # 检查基本语法
    try:
        content = filepath.read_text(encoding="utf-8")
        compile(content, str(filepath), "exec")
    except SyntaxError as e:
        issues.append({
            "type": "syntax_error",
            "severity": "critical",
            "line": e.lineno,
            "message": str(e),
        })

    # 检查是否有可用的静态分析工具
    tools_available = []
    for tool in ["ruff", "pylint", "mypy"]:
        try:
            subprocess.run([tool, "--version"], capture_output=True, timeout=5)
            tools_available.append(tool)
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    if "ruff" in tools_available:
        try:
            result = subprocess.run(
                ["ruff", "check", str(filepath), "--output-format", "json"],
                capture_output=True, text=True, timeout=30
            )
            if result.stdout.strip():
                ruff_issues = json.loads(result.stdout)
                for issue in ruff_issues[:20]:  # 最多 20 个
                    issues.append({
                        "type": "ruff",
                        "severity": "warning",
                        "line": issue.get("location", {}).get("row"),
                        "code": issue.get("code", ""),
                        "message": issue.get("message", ""),
                    })
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    return {
        "file": str(filepath),
        "lines": len(content.split("\n")),
        "issues_count": len(issues),
        "issues": issues,
        "tools_checked": tools_available,
    }


def review_batch_file(filepath: Path) -> dict:
    """审查 .bat/.vbs Windows 脚本"""
    content = filepath.read_text(encoding="utf-8")
    issues = []
    lines = content.split("\n")

    # 检查常见问题
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("::") or stripped.startswith("REM"):
            continue

        # 硬编码路径检查
        if re.search(r"[A-Z]:\\", stripped) and "D:" not in stripped:
            issues.append({
                "type": "hardcoded_path",
                "severity": "info",
                "line": i,
                "message": f"硬编码路径: {stripped[:80]}",
            })

        # 缺少引号的风险命令
        if "del " in stripped or "rmdir " in stripped:
            if '"' not in stripped and "'" not in stripped:
                issues.append({
                    "type": "unsafe_command",
                    "severity": "warning",
                    "line": i,
                    "message": f"危险命令缺少引号: {stripped[:80]}",
                })

    return {
        "file": str(filepath),
        "lines": len(lines),
        "issues_count": len(issues),
        "issues": issues,
    }


def review_config_file(filepath: Path) -> dict:
    """审查 YAML/JSON/TOML 配置文件"""
    issues = []
    content = filepath.read_text(encoding="utf-8")

    # 检查敏感信息泄露
    sensitive_patterns = [
        (r"api_key['\":\s]*['\"][A-Za-z0-9_-]{20,}", "可能的 API key 泄露"),
        (r"password['\":\s]*['\"][^'\"]{3,}", "可能的密码硬编码"),
        (r"token['\":\s]*['\"][A-Za-z0-9_-]{20,}", "可能的 token 泄露"),
    ]

    for pattern, msg in sensitive_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            issues.append({
                "type": "sensitive_data",
                "severity": "critical",
                "message": msg,
            })

    return {
        "file": str(filepath),
        "lines": len(content.split("\n")),
        "issues_count": len(issues),
        "issues": issues,
    }


def run_review(watch_dirs: List[Path] = None, extensions: set = None,
               dry_run: bool = False) -> dict:
    """
    执行一轮质量审查。

    返回:
      统计信息 {"files_changed": N, "files_reviewed": N, "issues_total": N}
    """
    if watch_dirs is None:
        watch_dirs = WATCH_DIRS
    if extensions is None:
        extensions = REVIEW_EXTENSIONS

    tracker_path = BRAIN_ROOT / "state" / ".review_tracker.json"
    tracker = FileTracker(tracker_path)

    # 发现变更文件
    changed = find_changed_files(watch_dirs, extensions, tracker)
    logger.info(f"Changed files detected: {len(changed)}")

    if not changed:
        return {"files_changed": 0, "files_reviewed": 0, "issues_total": 0}

    results = []

    for filepath in changed:
        suffix = filepath.suffix.lower()

        if suffix == ".py":
            result = review_python_file(filepath)
        elif suffix in (".bat", ".vbs", ".sh"):
            result = review_batch_file(filepath)
        elif suffix in (".yaml", ".yml", ".json", ".toml"):
            result = review_config_file(filepath)
        else:
            continue

        results.append(result)

        # 更新追踪
        file_hash = compute_file_hash(filepath)
        tracker.set_hash(filepath, file_hash, filepath.stat().st_mtime)

        if result["issues_count"] > 0:
            severities = [i["severity"] for i in result["issues"]]
            criticals = severities.count("critical")
            warnings = severities.count("warning")
            logger.warning(
                f"  {filepath.name}: {result['issues_count']} issues "
                f"({criticals} critical, {warnings} warnings)"
            )

    # 保存追踪状态
    tracker.save()

    # 保存审查报告
    if results and any(r["issues_count"] > 0 for r in results):
        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = REVIEW_DIR / f"review_{timestamp}.json"

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "files_changed": len(changed),
            "files_reviewed": len(results),
            "issues_total": sum(r["issues_count"] for r in results),
            "results": results,
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                              encoding="utf-8")
        logger.info(f"Review report saved: {report_path}")

    return {
        "files_changed": len(changed),
        "files_reviewed": len(results),
        "issues_total": sum(r["issues_count"] for r in results),
        "report": str(report_path) if results else None,
    }


import re  # 用于 review_batch_file


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Aris Review Tool")
    parser.add_argument("--watch", nargs="*", help="Directories to watch")
    parser.add_argument("--file", help="Review a specific file")
    parser.add_argument("--stats", action="store_true", help="Show review stats")

    args = parser.parse_args()

    if args.file:
        filepath = Path(args.file)
        if filepath.suffix == ".py":
            result = review_python_file(filepath)
        elif filepath.suffix in (".bat", ".vbs", ".sh"):
            result = review_batch_file(filepath)
        else:
            result = review_config_file(filepath)
        logger.info(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return

    if args.stats:
        tracker_path = BRAIN_ROOT / "state" / ".review_tracker.json"
        if tracker_path.exists():
            logger.info(f"Files tracked: {len(json.loads(tracker_path.read_text()))}")
        reviews = list(REVIEW_DIR.glob("review_*.json")) if REVIEW_DIR.exists() else []
        logger.info(f"Review reports: {len(reviews)}")
        if reviews:
            latest = max(reviews, key=lambda p: p.stat().st_mtime)
            logger.info(f"Latest: {latest.name} ({datetime.fromtimestamp(latest.stat().st_mtime).isoformat()})")
        return

    watch_dirs = [Path(d) for d in args.watch] if args.watch else WATCH_DIRS
    result = run_review(watch_dirs)
    logger.info(json.dumps(result, indent=2, ensure_ascii=False, default=str))
if __name__ == "__main__":
    main()
