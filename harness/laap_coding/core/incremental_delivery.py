"""
IncrementalDelivery - 增量交付约束

实现FR-4.3：增量交付约束
支持强制Git commit、语义化提交信息和变更验证

核心功能：
- 语义化提交信息验证（Conventional Commits）
- Git commit 强制执行
- 变更行数限制（每子任务≤200行）
- 测试门控验证
"""

from __future__ import annotations

import subprocess
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class CommitResult:
    success: bool
    commit_hash: Optional[str] = None
    message: str = ""
    error: Optional[str] = None


@dataclass
class ChangeStats:
    total_lines: int
    added_lines: int
    removed_lines: int
    modified_files: int
    exceeds_limit: bool


@dataclass
class DeliveryConstraint:
    max_lines_per_subtask: int = 200
    required_commit_prefixes: List[str] = field(default_factory=lambda: ["feat", "fix", "refactor", "test", "docs", "chore"])
    enforce_conventional_commits: bool = True


class IncrementalDelivery:
    """增量交付约束管理器"""

    def __init__(self, project_root: str = ""):
        self.project_root = project_root or os.environ.get("LAAP_ROOT", os.getcwd())
        self._constraints = DeliveryConstraint()
        self._commit_count = 0

    def check_line_count(self, file_path: str = "") -> ChangeStats:
        """检查变更行数

        Args:
            file_path: 文件路径（可选，不指定则检查所有变更文件）

        Returns:
            ChangeStats: 变更统计信息
        """
        try:
            if file_path:
                abs_path = file_path if os.path.isabs(file_path) else os.path.join(self.project_root, file_path)
                result = subprocess.run(
                    ["git", "diff", "--numstat", "--", abs_path],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            else:
                result = subprocess.run(
                    ["git", "diff", "--numstat"],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

            total_added = 0
            total_removed = 0
            modified_files = 0

            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split('\t')
                        if len(parts) >= 3:
                            added = int(parts[0]) if parts[0] != '-' else 0
                            removed = int(parts[1]) if parts[1] != '-' else 0
                            total_added += added
                            total_removed += removed
                            modified_files += 1

            total_lines = total_added + total_removed

            return ChangeStats(
                total_lines=total_lines,
                added_lines=total_added,
                removed_lines=total_removed,
                modified_files=modified_files,
                exceeds_limit=total_lines > self._constraints.max_lines_per_subtask
            )

        except Exception as e:
            return ChangeStats(
                total_lines=0,
                added_lines=0,
                removed_lines=0,
                modified_files=0,
                exceeds_limit=False
            )

    def validate_commit_message(self, message: str) -> Tuple[bool, str]:
        """验证提交信息是否符合语义化规范

        Args:
            message: 提交信息

        Returns:
            Tuple[bool, str]: (是否通过, 错误消息)
        """
        if not message or not message.strip():
            return False, "提交信息不能为空"

        lines = message.strip().split('\n')
        first_line = lines[0].strip()

        if len(first_line) > 72:
            return False, f"提交信息标题过长（{len(first_line)} > 72字符）"

        if self._constraints.enforce_conventional_commits:
            pattern = r"^(feat|fix|refactor|test|docs|chore|style|perf|ci|build|revert)\([a-zA-Z0-9_-]+\):\s+.+"
            if not re.match(pattern, first_line):
                return False, f"提交信息不符合语义化规范: {first_line}"

        return True, ""

    def commit(self, message: str, files: List[str] = None) -> CommitResult:
        """执行Git commit

        Args:
            message: 提交信息
            files: 需要提交的文件列表

        Returns:
            CommitResult: 提交结果
        """
        valid, error_msg = self.validate_commit_message(message)
        if not valid:
            return CommitResult(
                success=False,
                message="提交信息验证失败",
                error=error_msg
            )

        try:
            if files:
                for f in files:
                    abs_path = f if os.path.isabs(f) else os.path.join(self.project_root, f)
                    subprocess.run(
                        ["git", "add", abs_path],
                        cwd=self.project_root,
                        capture_output=True,
                        timeout=30
                    )
            else:
                subprocess.run(
                    ["git", "add", "-A"],
                    cwd=self.project_root,
                    capture_output=True,
                    timeout=30
                )

            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return CommitResult(
                    success=False,
                    message="Git commit失败",
                    error=result.stderr.strip()
                )

            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10
            )

            self._commit_count += 1

            return CommitResult(
                success=True,
                commit_hash=hash_result.stdout.strip()[:8],
                message="提交成功"
            )

        except Exception as e:
            return CommitResult(
                success=False,
                message="Git操作失败",
                error=str(e)
            )

    def create_conventional_commit(self, type_: str, scope: str, description: str,
                                   body: str = "", footer: str = "") -> str:
        """创建符合语义化规范的提交信息

        Args:
            type_: 提交类型（feat/fix/refactor/test/docs/chore等）
            scope: 范围（模块名）
            description: 简短描述
            body: 详细描述（可选）
            footer: 页脚（可选）

        Returns:
            str: 格式化的提交信息
        """
        lines = [f"{type_}({scope}): {description}"]
        
        if body:
            lines.append("")
            lines.append(body)
        
        if footer:
            lines.append("")
            lines.append(footer)
        
        return "\n".join(lines)

    def validate_subtask_delivery(self, subtask_description: str, modified_files: List[str] = None) -> Dict[str, Any]:
        """验证子任务交付是否符合约束

        Args:
            subtask_description: 子任务描述
            modified_files: 修改的文件列表

        Returns:
            Dict[str, Any]: 验证结果
        """
        stats = self.check_line_count()
        
        result = {
            "valid": True,
            "checks": [],
            "stats": {
                "total_lines": stats.total_lines,
                "added_lines": stats.added_lines,
                "removed_lines": stats.removed_lines,
                "modified_files": stats.modified_files,
            },
            "message": "交付验证通过"
        }

        if stats.exceeds_limit:
            result["valid"] = False
            result["checks"].append({
                "type": "line_limit",
                "passed": False,
                "message": f"变更行数超过限制: {stats.total_lines} > {self._constraints.max_lines_per_subtask}",
                "suggestion": "请将子任务拆分为更小的单元"
            })

        if stats.modified_files == 0:
            result["valid"] = False
            result["checks"].append({
                "type": "no_changes",
                "passed": False,
                "message": "没有检测到任何变更",
                "suggestion": "请确保有实际的代码变更"
            })

        return result

    def enforce_delivery(self, subtask_description: str, modified_files: List[str] = None,
                         commit_scope: str = "harness") -> Dict[str, Any]:
        """强制执行增量交付约束

        Args:
            subtask_description: 子任务描述
            modified_files: 修改的文件列表
            commit_scope: 提交范围

        Returns:
            Dict[str, Any]: 交付结果
        """
        validation = self.validate_subtask_delivery(subtask_description, modified_files)
        
        if not validation["valid"]:
            return {
                "success": False,
                "stage": "validation",
                "message": "交付验证未通过",
                "details": validation
            }

        commit_message = self.create_conventional_commit(
            type_="feat",
            scope=commit_scope,
            description=subtask_description[:50] + "..." if len(subtask_description) > 50 else subtask_description
        )

        commit_result = self.commit(commit_message, modified_files)
        
        if not commit_result.success:
            return {
                "success": False,
                "stage": "commit",
                "message": "提交失败",
                "details": commit_result.error
            }

        return {
            "success": True,
            "stage": "completed",
            "message": "增量交付完成",
            "commit_hash": commit_result.commit_hash,
            "commit_message": commit_message,
            "stats": validation["stats"]
        }

    def get_commit_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的提交历史"""
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", f"-{limit}"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30
            )

            commits = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(' ', 1)
                    if len(parts) >= 2:
                        commits.append({
                            "hash": parts[0][:8],
                            "message": parts[1]
                        })

            return commits
        except Exception:
            return []

    def get_current_branch(self) -> str:
        """获取当前分支名"""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def has_uncommitted_changes(self) -> bool:
        """检查是否有未提交的变更"""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            return len(result.stdout.strip()) > 0
        except Exception:
            return False