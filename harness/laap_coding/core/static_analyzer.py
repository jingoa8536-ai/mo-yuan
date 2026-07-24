"""
StaticAnalyzer - 静态分析器

实现FR-4.1：静态分析环节
支持Python语法检查、代码风格检查和类型检查

核心功能：
- Python语法检查（ast模块）
- flake8代码风格检查
- pylint代码质量检查
- mypy类型检查
- 综合分析报告生成
"""

from __future__ import annotations

import subprocess
import os
import re
import ast
import sys
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class AnalysisIssue:
    category: str
    severity: str
    code: str
    message: str
    line: Optional[int] = None
    column: Optional[int] = None
    file_path: Optional[str] = None


@dataclass
class StaticAnalysisResult:
    passed: bool
    issues: List[AnalysisIssue]
    syntax_valid: bool
    flake8_passed: bool
    pylint_score: Optional[float] = None
    mypy_passed: Optional[bool] = None


class StaticAnalyzer:
    """静态分析器：代码质量静态分析"""

    def __init__(self, project_root: str = ""):
        self.project_root = project_root or os.environ.get("LAAP_ROOT", os.getcwd())
        self._max_issues = 50

    def analyze(self, code: str) -> List[Dict[str, Any]]:
        return []

    def check_syntax(self, code: str, file_path: str = "") -> List[AnalysisIssue]:
        """检查Python语法

        Args:
            code: Python代码字符串
            file_path: 文件名（用于报告）

        Returns:
            List[AnalysisIssue]: 语法错误列表
        """
        issues = []
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(AnalysisIssue(
                category="syntax",
                severity="error",
                code="SYNTAX_ERROR",
                message=str(e),
                line=e.lineno,
                column=e.offset,
                file_path=file_path
            ))
        return issues

    def check_syntax_file(self, file_path: str) -> List[AnalysisIssue]:
        """检查文件的Python语法"""
        abs_path = file_path if os.path.isabs(file_path) else os.path.join(self.project_root, file_path)
        
        if not os.path.exists(abs_path):
            return [AnalysisIssue(
                category="syntax",
                severity="error",
                code="FILE_NOT_FOUND",
                message=f"文件不存在: {file_path}",
                file_path=file_path
            )]

        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                code = f.read()
            return self.check_syntax(code, file_path)
        except Exception as e:
            return [AnalysisIssue(
                category="syntax",
                severity="error",
                code="READ_ERROR",
                message=f"读取文件失败: {str(e)}",
                file_path=file_path
            )]

    def run_flake8(self, file_path: str = "") -> List[AnalysisIssue]:
        """运行flake8代码风格检查

        Args:
            file_path: 文件或目录路径

        Returns:
            List[AnalysisIssue]: flake8问题列表
        """
        issues = []
        
        if not file_path:
            return issues

        abs_path = file_path if os.path.isabs(file_path) else os.path.join(self.project_root, file_path)

        if not os.path.exists(abs_path):
            return [AnalysisIssue(
                category="flake8",
                severity="error",
                code="FILE_NOT_FOUND",
                message=f"文件不存在: {file_path}",
                file_path=file_path
            )]

        try:
            result = subprocess.run(
                [sys.executable, "-m", "flake8", abs_path, "--max-line-length=120"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0 and result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split(':')
                        if len(parts) >= 4:
                            fp = parts[0]
                            line_num = int(parts[1]) if parts[1].isdigit() else None
                            col = int(parts[2]) if parts[2].isdigit() else None
                            code_msg = ':'.join(parts[3:])
                            
                            code_match = re.match(r'^([A-Za-z]\d+)', code_msg.strip())
                            code = code_match.group(1) if code_match else "FLAKE8_ERROR"
                            message = code_msg.strip()[len(code):].strip() if code_match else code_msg.strip()

                            severity = "warning"
                            if code.startswith('E'):
                                severity = "error"
                            elif code.startswith('F'):
                                severity = "error"
                            elif code.startswith('W'):
                                severity = "warning"
                            elif code.startswith('C'):
                                severity = "convention"
                            elif code.startswith('N'):
                                severity = "note"

                            issues.append(AnalysisIssue(
                                category="flake8",
                                severity=severity,
                                code=code,
                                message=message,
                                line=line_num,
                                column=col,
                                file_path=fp
                            ))

            return issues[:self._max_issues]
        except Exception as e:
            return [AnalysisIssue(
                category="flake8",
                severity="error",
                code="RUN_ERROR",
                message=f"flake8运行失败: {str(e)}",
                file_path=file_path
            )]

    def run_pylint(self, file_path: str = "") -> Tuple[List[AnalysisIssue], Optional[float]]:
        """运行pylint代码质量检查

        Args:
            file_path: 文件或目录路径

        Returns:
            Tuple[List[AnalysisIssue], Optional[float]]: 问题列表和pylint分数
        """
        issues = []
        score = None

        if not file_path:
            return issues, score

        abs_path = file_path if os.path.isabs(file_path) else os.path.join(self.project_root, file_path)

        if not os.path.exists(abs_path):
            return [AnalysisIssue(
                category="pylint",
                severity="error",
                code="FILE_NOT_FOUND",
                message=f"文件不存在: {file_path}",
                file_path=file_path
            )], score

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pylint", abs_path, "--disable=R,C", "--reports=n"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line and ':' in line and not line.startswith('---'):
                        parts = line.split(':', 3)
                        if len(parts) >= 4:
                            fp = parts[0].strip()
                            line_num = int(parts[1].strip()) if parts[1].strip().isdigit() else None
                            code = parts[2].strip()
                            message = parts[3].strip()

                            severity = "warning"
                            if code.startswith('E'):
                                severity = "error"
                            elif code.startswith('W'):
                                severity = "warning"
                            elif code.startswith('F'):
                                severity = "fatal"

                            issues.append(AnalysisIssue(
                                category="pylint",
                                severity=severity,
                                code=code,
                                message=message,
                                line=line_num,
                                file_path=fp
                            ))

            score_match = re.search(r"Your code has been rated at (\d+\.\d+)/10", result.stderr)
            if score_match:
                score = float(score_match.group(1))

            return issues[:self._max_issues], score
        except Exception as e:
            return [AnalysisIssue(
                category="pylint",
                severity="error",
                code="RUN_ERROR",
                message=f"pylint运行失败: {str(e)}",
                file_path=file_path
            )], score

    def run_mypy(self, file_path: str = "") -> Tuple[List[AnalysisIssue], bool]:
        """运行mypy类型检查

        Args:
            file_path: 文件或目录路径

        Returns:
            Tuple[List[AnalysisIssue], bool]: 问题列表和是否通过
        """
        issues = []

        if not file_path:
            return issues, True

        abs_path = file_path if os.path.isabs(file_path) else os.path.join(self.project_root, file_path)

        if not os.path.exists(abs_path):
            return [AnalysisIssue(
                category="mypy",
                severity="error",
                code="FILE_NOT_FOUND",
                message=f"文件不存在: {file_path}",
                file_path=file_path
            )], False

        try:
            result = subprocess.run(
                [sys.executable, "-m", "mypy", abs_path, "--ignore-missing-imports"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=120
            )

            passed = result.returncode == 0

            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line and ':' in line:
                        parts = line.split(':', 3)
                        if len(parts) >= 4:
                            fp = parts[0].strip()
                            line_num = int(parts[1].strip()) if parts[1].strip().isdigit() else None
                            col = int(parts[2].strip()) if parts[2].strip().isdigit() else None
                            message = parts[3].strip()

                            code_match = re.search(r'\[(\w+)\]', message)
                            code = code_match.group(1) if code_match else "MYPY_ERROR"

                            severity = "error" if "error" in message.lower() else "warning"

                            issues.append(AnalysisIssue(
                                category="mypy",
                                severity=severity,
                                code=code,
                                message=message,
                                line=line_num,
                                column=col,
                                file_path=fp
                            ))

            return issues[:self._max_issues], passed
        except Exception as e:
            return [AnalysisIssue(
                category="mypy",
                severity="error",
                code="RUN_ERROR",
                message=f"mypy运行失败: {str(e)}",
                file_path=file_path
            )], False

    def analyze_file(self, file_path: str) -> StaticAnalysisResult:
        """综合分析单个文件"""
        all_issues = []

        syntax_issues = self.check_syntax_file(file_path)
        all_issues.extend(syntax_issues)

        if not syntax_issues:
            flake8_issues = self.run_flake8(file_path)
            all_issues.extend(flake8_issues)

            pylint_issues, pylint_score = self.run_pylint(file_path)
            all_issues.extend(pylint_issues)

            mypy_issues, mypy_passed = self.run_mypy(file_path)
            all_issues.extend(mypy_issues)
        else:
            pylint_score = None
            mypy_passed = False

        has_errors = any(issue.severity == "error" or issue.severity == "fatal" for issue in all_issues)

        return StaticAnalysisResult(
            passed=not has_errors,
            issues=all_issues,
            syntax_valid=len(syntax_issues) == 0,
            flake8_passed=len(flake8_issues) == 0,
            pylint_score=pylint_score,
            mypy_passed=mypy_passed
        )

    def analyze_project(self, paths: List[str] = None) -> StaticAnalysisResult:
        """综合分析项目

        Args:
            paths: 文件或目录路径列表

        Returns:
            StaticAnalysisResult: 综合分析结果
        """
        if not paths:
            paths = [self.project_root]

        all_issues = []
        syntax_valid = True
        flake8_passed = True
        pylint_score = None
        mypy_passed = True

        for path in paths:
            abs_path = path if os.path.isabs(path) else os.path.join(self.project_root, path)

            if os.path.isfile(abs_path):
                if abs_path.endswith('.py'):
                    result = self.analyze_file(abs_path)
                    all_issues.extend(result.issues)
                    syntax_valid = syntax_valid and result.syntax_valid
                    flake8_passed = flake8_passed and result.flake8_passed
                    if result.pylint_score is not None:
                        pylint_score = result.pylint_score
                    mypy_passed = mypy_passed and (result.mypy_passed is not False)

            elif os.path.isdir(abs_path):
                for root, _, files in os.walk(abs_path):
                    for f in files:
                        if f.endswith('.py'):
                            file_path = os.path.join(root, f)
                            result = self.analyze_file(file_path)
                            all_issues.extend(result.issues)
                            syntax_valid = syntax_valid and result.syntax_valid
                            flake8_passed = flake8_passed and result.flake8_passed
                            if result.pylint_score is not None:
                                pylint_score = result.pylint_score
                            mypy_passed = mypy_passed and (result.mypy_passed is not False)

        has_errors = any(issue.severity == "error" or issue.severity == "fatal" for issue in all_issues)

        return StaticAnalysisResult(
            passed=not has_errors,
            issues=all_issues[:self._max_issues],
            syntax_valid=syntax_valid,
            flake8_passed=flake8_passed,
            pylint_score=pylint_score,
            mypy_passed=mypy_passed
        )

    def generate_report(self, result: StaticAnalysisResult) -> str:
        """生成静态分析报告"""
        report = [
            "=" * 60,
            "静态分析报告",
            "=" * 60,
            f"分析结果: {'✅ 通过' if result.passed else '❌ 失败'}",
            f"语法检查: {'✅ 通过' if result.syntax_valid else '❌ 失败'}",
            f"flake8检查: {'✅ 通过' if result.flake8_passed else '❌ 失败'}",
            f"pylint分数: {result.pylint_score:.2f}/10" if result.pylint_score else "pylint: 未运行",
            f"mypy检查: {'✅ 通过' if result.mypy_passed else '❌ 失败'}",
            f"问题总数: {len(result.issues)}",
        ]

        if result.issues:
            report.extend(["", "-" * 60, "问题详情", "-" * 60])

            error_count = sum(1 for i in result.issues if i.severity == "error")
            warning_count = sum(1 for i in result.issues if i.severity == "warning")
            other_count = len(result.issues) - error_count - warning_count

            report.extend([
                f"  错误: {error_count}",
                f"  警告: {warning_count}",
                f"  其他: {other_count}",
            ])

            for issue in sorted(result.issues, key=lambda x: x.severity == "error", reverse=True)[:20]:
                line_info = f":{issue.line}" if issue.line else ""
                col_info = f":{issue.column}" if issue.column else ""
                report.append(f"  [{issue.severity.upper()}] {issue.code} {issue.file_path or ''}{line_info}{col_info}: {issue.message}")

        return "\n".join(report)