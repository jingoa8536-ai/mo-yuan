"""
TestValidator - 测试验证器

实现FR-4.1：测试验证环节
支持单元测试、集成测试验证，以及测试覆盖率检查

核心功能：
- pytest测试运行与结果解析
- unittest测试运行与结果解析
- 测试覆盖率检查（coverage.py）
- 测试结果分析与报告生成
"""

from __future__ import annotations

import subprocess
import os
import re
import json
import sys
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class TestResult:
    passed: bool
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    errors: int
    duration_ms: float
    output: str
    coverage: Optional[float] = None
    coverage_details: Optional[Dict[str, Any]] = None


@dataclass
class CoverageReport:
    total: float
    files: Dict[str, float]
    uncovered_lines: Dict[str, List[int]]
    missing_branches: Dict[str, List[int]]


class TestValidator:
    """测试验证器：验证测试是否通过"""

    def __init__(self, project_root: str = ""):
        self.project_root = project_root or os.environ.get("LAAP_ROOT", os.getcwd())
        self._test_framework = None
        self._coverage_threshold = 80.0

    def validate(self, test_output: str) -> Dict[str, Any]:
        if not test_output:
            return {"passed": True, "details": "No output", "total": 0, "passed_count": 0}

        passed_keywords = ["PASS", "passed", "success", "ok", "Generated", "Written"]
        failed_keywords = ["FAIL", "failed", "error", "traceback", "exception"]

        has_failed = any(kw.lower() in test_output.lower() for kw in failed_keywords)
        has_passed = any(kw in test_output for kw in passed_keywords)

        passed = not has_failed and (has_passed or "Generated" in test_output)
        return {"passed": passed, "details": test_output, "total": 1, "passed_count": 1 if passed else 0}

    def run_pytest(self, test_path: str = "", args: List[str] = None) -> TestResult:
        """运行pytest测试

        Args:
            test_path: 测试文件或目录路径
            args: 额外的pytest参数

        Returns:
            TestResult: 测试结果
        """
        cmd_args = [sys.executable, "-m", "pytest"]

        if test_path:
            abs_path = test_path if os.path.isabs(test_path) else os.path.join(self.project_root, test_path)
            cmd_args.append(abs_path)

        if args:
            cmd_args.extend(args)

        cmd_args.extend(["-v", "--tb=short", "-q"])

        try:
            result = subprocess.run(
                cmd_args,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=120
            )
            return self._parse_pytest_output(result)
        except subprocess.TimeoutExpired:
            return TestResult(
                passed=False,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                skipped_tests=0,
                errors=1,
                duration_ms=120000,
                output="测试超时"
            )
        except Exception as e:
            return TestResult(
                passed=False,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                skipped_tests=0,
                errors=1,
                duration_ms=0,
                output=f"运行测试失败: {str(e)}"
            )

    def run_unittest(self, test_path: str = "", args: List[str] = None) -> TestResult:
        """运行unittest测试

        Args:
            test_path: 测试文件或目录路径
            args: 额外的unittest参数

        Returns:
            TestResult: 测试结果
        """
        cmd_args = [sys.executable, "-m", "unittest"]

        if test_path:
            abs_path = test_path if os.path.isabs(test_path) else os.path.join(self.project_root, test_path)
            
            if os.path.isdir(abs_path):
                cmd_args.append("discover")
                cmd_args.append("-s")
                cmd_args.append(abs_path)
            else:
                module_path = abs_path.replace(os.sep, '.').replace('.py', '')
                cmd_args.append(module_path)

        if args:
            cmd_args.extend(args)

        try:
            result = subprocess.run(
                cmd_args,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=120
            )
            return self._parse_unittest_output(result)
        except subprocess.TimeoutExpired:
            return TestResult(
                passed=False,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                skipped_tests=0,
                errors=1,
                duration_ms=120000,
                output="测试超时"
            )
        except Exception as e:
            return TestResult(
                passed=False,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                skipped_tests=0,
                errors=1,
                duration_ms=0,
                output=f"运行测试失败: {str(e)}"
            )

    def run_integration_tests(self, test_path: str = "tests/integration") -> TestResult:
        """运行集成测试"""
        return self.run_pytest(test_path)

    def run_with_coverage(self, test_path: str = "", coverage_source: str = "") -> Tuple[TestResult, CoverageReport]:
        """运行测试并检查覆盖率

        Args:
            test_path: 测试文件或目录路径
            coverage_source: 需要覆盖的源代码目录

        Returns:
            Tuple[TestResult, CoverageReport]: 测试结果和覆盖率报告
        """
        if not coverage_source:
            coverage_source = self.project_root

        cmd_args = [
            sys.executable, "-m", "coverage", "run", "-m", "pytest",
            test_path if test_path else "tests",
            "-v", "--tb=short"
        ]

        try:
            subprocess.run(
                cmd_args,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=120
            )

            coverage_cmd = [
                sys.executable, "-m", "coverage", "report", "-m", "-json"
            ]
            
            coverage_result = subprocess.run(
                coverage_cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30
            )

            test_result = self.run_pytest(test_path)
            coverage_report = self._parse_coverage_output(coverage_result)

            test_result.coverage = coverage_report.total
            test_result.coverage_details = {
                "files": coverage_report.files,
                "uncovered_lines": coverage_report.uncovered_lines,
                "missing_branches": coverage_report.missing_branches
            }

            return test_result, coverage_report
        except Exception as e:
            return TestResult(
                passed=False,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                skipped_tests=0,
                errors=1,
                duration_ms=0,
                output=f"覆盖率测试失败: {str(e)}"
            ), CoverageReport(
                total=0.0,
                files={},
                uncovered_lines={},
                missing_branches={}
            )

    def check_coverage_threshold(self, coverage_report: CoverageReport) -> bool:
        """检查覆盖率是否达到阈值"""
        return coverage_report.total >= self._coverage_threshold

    def _parse_pytest_output(self, result: subprocess.CompletedProcess) -> TestResult:
        """解析pytest输出"""
        output = result.stdout + result.stderr
        
        passed_match = re.search(r"(\d+)\s+passed", output)
        failed_match = re.search(r"(\d+)\s+failed", output)
        skipped_match = re.search(r"(\d+)\s+skipped", output)
        error_match = re.search(r"(\d+)\s+error", output)
        duration_match = re.search(r"(\d+\.\d+)\s+seconds", output)

        total = 0
        passed = int(passed_match.group(1)) if passed_match else 0
        failed = int(failed_match.group(1)) if failed_match else 0
        skipped = int(skipped_match.group(1)) if skipped_match else 0
        errors = int(error_match.group(1)) if error_match else 0
        duration_ms = float(duration_match.group(1)) * 1000 if duration_match else 0

        total = passed + failed + skipped + errors

        return TestResult(
            passed=failed == 0 and errors == 0,
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            skipped_tests=skipped,
            errors=errors,
            duration_ms=duration_ms,
            output=output[:5000]
        )

    def _parse_unittest_output(self, result: subprocess.CompletedProcess) -> TestResult:
        """解析unittest输出"""
        output = result.stdout + result.stderr

        passed_match = re.search(r"OK\s*\((\d+)\s+test", output)
        failed_match = re.search(r"FAILED\s*\((failures=(\d+))?", output)
        error_match = re.search(r"ERRORS=(\d+)", output)
        duration_match = re.search(r"(\d+\.\d+)\s+sec", output)

        if passed_match:
            return TestResult(
                passed=True,
                total_tests=int(passed_match.group(1)),
                passed_tests=int(passed_match.group(1)),
                failed_tests=0,
                skipped_tests=0,
                errors=0,
                duration_ms=float(duration_match.group(1)) * 1000 if duration_match else 0,
                output=output[:5000]
            )

        total = 0
        passed = 0
        failed = int(failed_match.group(2)) if failed_match and failed_match.group(2) else 0
        errors = int(error_match.group(1)) if error_match else 0
        duration_ms = float(duration_match.group(1)) * 1000 if duration_match else 0

        return TestResult(
            passed=False,
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            skipped_tests=0,
            errors=errors,
            duration_ms=duration_ms,
            output=output[:5000]
        )

    def _parse_coverage_output(self, result: subprocess.CompletedProcess) -> CoverageReport:
        """解析coverage输出"""
        try:
            data = json.loads(result.stdout)
            
            files = {}
            uncovered_lines = {}
            missing_branches = {}
            total_covered = 0
            total_statements = 0

            for file_path, file_data in data.get("files", {}).items():
                percent = file_data.get("percent_covered", 0.0)
                files[file_path] = percent
                
                if file_data.get("missing_lines"):
                    uncovered_lines[file_path] = file_data["missing_lines"]
                if file_data.get("missing_branches"):
                    missing_branches[file_path] = file_data["missing_branches"]
                
                total_covered += file_data.get("num_covered", 0)
                total_statements += file_data.get("num_statements", 0)

            total_percent = (total_covered / total_statements * 100) if total_statements > 0 else 0.0

            return CoverageReport(
                total=total_percent,
                files=files,
                uncovered_lines=uncovered_lines,
                missing_branches=missing_branches
            )
        except Exception:
            return CoverageReport(
                total=0.0,
                files={},
                uncovered_lines={},
                missing_branches={}
            )

    def generate_report(self, test_result: TestResult) -> str:
        """生成测试报告"""
        report = [
            "=" * 60,
            "测试验证报告",
            "=" * 60,
            f"测试结果: {'✅ 通过' if test_result.passed else '❌ 失败'}",
            f"总测试数: {test_result.total_tests}",
            f"通过: {test_result.passed_tests}",
            f"失败: {test_result.failed_tests}",
            f"跳过: {test_result.skipped_tests}",
            f"错误: {test_result.errors}",
            f"耗时: {test_result.duration_ms:.2f}ms",
        ]

        if test_result.coverage is not None:
            report.extend([
                "-" * 60,
                "覆盖率报告",
                "-" * 60,
                f"总覆盖率: {test_result.coverage:.2f}%",
                f"覆盖率达标: {'✅ 是' if test_result.coverage >= self._coverage_threshold else '❌ 否'}",
            ])

        report.extend([
            "-" * 60,
            "测试输出摘要",
            "-" * 60,
            test_result.output[:2000]
        ])

        return "\n".join(report)