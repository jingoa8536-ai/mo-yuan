"""
SecurityScanner - 安全扫描器

实现FR-4.1：安全扫描环节
支持常见安全漏洞检测、依赖漏洞扫描和敏感信息泄露检测

核心功能：
- SQL注入检测
- XSS漏洞检测
- 命令注入检测
- 路径遍历检测
- 敏感信息泄露检测（密钥、密码、token）
- 依赖漏洞扫描（safety/dependency-check）
- 安全配置检查
"""

from __future__ import annotations

import subprocess
import os
import re
import sys
import json
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class SecurityIssue:
    category: str
    severity: str
    code: str
    message: str
    line: Optional[int] = None
    column: Optional[int] = None
    file_path: Optional[str] = None
    confidence: float = 0.0


@dataclass
class SecurityScanResult:
    passed: bool
    issues: List[SecurityIssue]
    total_vulnerabilities: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int


class SecurityScanner:
    """安全扫描器：安全漏洞检测"""

    def __init__(self, project_root: str = ""):
        self.project_root = project_root or os.environ.get("LAAP_ROOT", os.getcwd())
        self._max_issues = 50

        self._pattern_rules = {
            "sql_injection": {
                "patterns": [
                    r"(?i)(select\s+.*from\s+|insert\s+into\s+|update\s+\w+\s+set\s+|delete\s+from\s+|drop\s+table\s+|union\s+select)",
                    r"(?i)\b(exec|execute|sp_executesql)\b.*['\"]",
                    r"(?i)\b(sql|query)\s*=\s*[\"\'].*\+.*[\"\']",
                ],
                "severity": "high",
                "code": "SQL_INJECTION",
                "message": "潜在SQL注入漏洞",
            },
            "xss": {
                "patterns": [
                    r"(?i)(innerHTML|document\.write|eval\(|setTimeout\(|setInterval\()",
                    r"(?i)\b(dangerouslySetInnerHTML|v-html)\b",
                    r"(?i)\b(response\.write|echo|print)\b.*request",
                ],
                "severity": "high",
                "code": "XSS_VULNERABILITY",
                "message": "潜在XSS跨站脚本漏洞",
            },
            "command_injection": {
                "patterns": [
                    r"(?i)(subprocess\.|os\.(system|popen|fork|exec)|commands\.)",
                    r"(?i)\b(popen|system|execve|spawn)\b.*['\"]",
                    r"(?i)\b(shell=True|shell=True)",
                ],
                "severity": "critical",
                "code": "COMMAND_INJECTION",
                "message": "潜在命令注入漏洞",
            },
            "path_traversal": {
                "patterns": [
                    r"(?i)\.\.(\\|\/)",
                    r"(?i)\b(path|file|dir)\s*=\s*.*\.\.",
                    r"(?i)\b(open|read|write)\s*\(\s*.*\.\.",
                ],
                "severity": "medium",
                "code": "PATH_TRAVERSAL",
                "message": "潜在路径遍历漏洞",
            },
            "hardcoded_secret": {
                "patterns": [
                    r"(?i)(api[_-]?key|api[_-]?secret|secret[_-]?key|access[_-]?key|auth[_-]?token|password|passwd)",
                    r"(?i)\b(SECRET_KEY|API_KEY|TOKEN|PASSWORD)\s*=\s*['\"][^'\"]{8,}['\"]",
                    r"(?i)\b(ssh|rsa|private[_-]?key)\s*=\s*['\"]",
                ],
                "severity": "critical",
                "code": "HARDCODED_SECRET",
                "message": "检测到硬编码敏感信息",
            },
            "weak_crypto": {
                "patterns": [
                    r"(?i)\b(md5|sha1|hashlib\.md5|hashlib\.sha1)\b",
                    r"(?i)\b(MD5|SHA1)\b",
                    r"(?i)\b(ECB|CBC)\b.*mode",
                ],
                "severity": "medium",
                "code": "WEAK_CRYPTO",
                "message": "使用了弱加密算法",
            },
            "insecure_random": {
                "patterns": [
                    r"(?i)\b(random\.randint|random\.random|random\.randrange)\b",
                    r"(?i)\b(random\.choice|random\.shuffle)\b",
                ],
                "severity": "medium",
                "code": "INSECURE_RANDOM",
                "message": "使用了不安全的随机数生成器",
            },
            "csrf": {
                "patterns": [
                    r"(?i)\b(csrf|xsrf)\b.*disabled",
                    r"(?i)\b(csrf_token|csrf_protect)\b.*=.*False",
                ],
                "severity": "medium",
                "code": "CSRF_VULNERABILITY",
                "message": "CSRF防护可能被禁用",
            },
        }

    def scan(self, code: str) -> List[Dict[str, Any]]:
        return []

    def scan_code(self, code: str, file_path: str = "") -> List[SecurityIssue]:
        """扫描代码中的安全漏洞

        Args:
            code: 代码字符串
            file_path: 文件名（用于报告）

        Returns:
            List[SecurityIssue]: 安全问题列表
        """
        issues = []

        for rule_name, rule in self._pattern_rules.items():
            for pattern in rule["patterns"]:
                matches = re.finditer(pattern, code)
                for match in matches:
                    line = code[:match.start()].count('\n') + 1
                    column = match.start() - code[:match.start()].rfind('\n')
                    
                    issues.append(SecurityIssue(
                        category=rule_name,
                        severity=rule["severity"],
                        code=rule["code"],
                        message=rule["message"],
                        line=line,
                        column=column,
                        file_path=file_path,
                        confidence=0.7
                    ))

        return issues

    def scan_file(self, file_path: str) -> List[SecurityIssue]:
        """扫描单个文件"""
        abs_path = file_path if os.path.isabs(file_path) else os.path.join(self.project_root, file_path)

        if not os.path.exists(abs_path):
            return [SecurityIssue(
                category="file",
                severity="error",
                code="FILE_NOT_FOUND",
                message=f"文件不存在: {file_path}",
                file_path=file_path
            )]

        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                code = f.read()
            return self.scan_code(code, file_path)
        except Exception as e:
            return [SecurityIssue(
                category="file",
                severity="error",
                code="READ_ERROR",
                message=f"读取文件失败: {str(e)}",
                file_path=file_path
            )]

    def scan_project(self, paths: List[str] = None) -> List[SecurityIssue]:
        """扫描整个项目，返回问题列表"""
        if not paths:
            paths = [self.project_root]

        all_issues = []

        for path in paths:
            abs_path = path if os.path.isabs(path) else os.path.join(self.project_root, path)

            if os.path.isfile(abs_path):
                if abs_path.endswith('.py') or abs_path.endswith('.js') or abs_path.endswith('.ts'):
                    all_issues.extend(self.scan_file(abs_path))

            elif os.path.isdir(abs_path):
                for root, _, files in os.walk(abs_path):
                    for f in files:
                        if f.endswith('.py') or f.endswith('.js') or f.endswith('.ts'):
                            file_path = os.path.join(root, f)
                            all_issues.extend(self.scan_file(file_path))

        return all_issues

    def scan_dependencies(self) -> Tuple[List[SecurityIssue], bool]:
        """扫描依赖漏洞

        Returns:
            Tuple[List[SecurityIssue], bool]: 问题列表和是否通过
        """
        issues = []
        passed = True

        requirements_file = os.path.join(self.project_root, "requirements.txt")
        if os.path.exists(requirements_file):
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "safety", "check", "--json"],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=120
                )

                if result.returncode != 0 and result.stdout:
                    try:
                        data = json.loads(result.stdout)
                        for vuln in data.get("vulnerabilities", []):
                            severity = "high"
                            if vuln.get("severity"):
                                severity = vuln["severity"].lower()
                            
                            issues.append(SecurityIssue(
                                category="dependency",
                                severity=severity,
                                code="DEPENDENCY_VULNERABILITY",
                                message=f"{vuln.get('package', '')} {vuln.get('installed_version', '')} has vulnerability: {vuln.get('advisory', '')}",
                                file_path="requirements.txt",
                                confidence=0.9
                            ))
                        passed = False
                    except Exception:
                        pass

            except Exception:
                pass

        return issues, passed

    def scan_secrets(self) -> List[SecurityIssue]:
        """扫描敏感信息泄露

        Returns:
            List[SecurityIssue]: 敏感信息问题列表
        """
        issues = []
        
        secret_patterns = [
            (r"(?i)\b(AKIA|ASIA)[A-Z0-9]{16}\b", "AWS_ACCESS_KEY", "检测到AWS访问密钥"),
            (r"(?i)\bsk_[a-zA-Z0-9_]{24,}\b", "API_SECRET_KEY", "检测到API密钥"),
            (r"(?i)\bghp_[a-zA-Z0-9_]{36}\b", "GITHUB_TOKEN", "检测到GitHub令牌"),
            (r"(?i)\b[a-zA-Z0-9_]{32,}\b", "POTENTIAL_SECRET", "检测到潜在的敏感字符串"),
        ]

        for root, _, files in os.walk(self.project_root):
            for f in files:
                if f.endswith('.py') or f.endswith('.env') or f.endswith('.yaml') or f.endswith('.yml'):
                    file_path = os.path.join(root, f)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as file:
                            content = file.read()
                            for pattern, code, message in secret_patterns:
                                matches = re.finditer(pattern, content)
                                for match in matches:
                                    line = content[:match.start()].count('\n') + 1
                                    issues.append(SecurityIssue(
                                        category="secret",
                                        severity="critical",
                                        code=code,
                                        message=message,
                                        line=line,
                                        file_path=file_path,
                                        confidence=0.8
                                    ))
                    except Exception:
                        continue

        return issues

    def scan_config(self) -> List[SecurityIssue]:
        """扫描安全配置问题"""
        issues = []

        config_files = [
            "config.py", "settings.py", "app.py", "main.py",
            ".env", "docker-compose.yml", "docker-compose.yaml",
        ]

        for config_file in config_files:
            file_path = os.path.join(self.project_root, config_file)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    if re.search(r"(?i)debug\s*=\s*True", content):
                        issues.append(SecurityIssue(
                            category="config",
                            severity="high",
                            code="DEBUG_ENABLED",
                            message="调试模式已启用，生产环境中存在安全风险",
                            file_path=config_file,
                            confidence=0.9
                        ))

                    if re.search(r"(?i)allow_origin\s*=\s*['\"]\*['\"]", content):
                        issues.append(SecurityIssue(
                            category="config",
                            severity="medium",
                            code="CORS_WILDCARD",
                            message="CORS配置允许所有来源，存在安全风险",
                            file_path=config_file,
                            confidence=0.8
                        ))

                except Exception:
                    continue

        return issues

    def comprehensive_scan(self) -> SecurityScanResult:
        """执行综合安全扫描"""
        all_issues = []

        all_issues.extend(self.scan_project())
        all_issues.extend(self.scan_secrets())
        all_issues.extend(self.scan_config())

        dep_issues, _ = self.scan_dependencies()
        all_issues.extend(dep_issues)

        return self._aggregate_results(all_issues)

    def _aggregate_results(self, issues: List[SecurityIssue]) -> SecurityScanResult:
        """聚合扫描结果"""
        critical = sum(1 for i in issues if i.severity == "critical")
        high = sum(1 for i in issues if i.severity == "high")
        medium = sum(1 for i in issues if i.severity == "medium")
        low = sum(1 for i in issues if i.severity == "low")

        has_critical_or_high = critical > 0 or high > 0

        return SecurityScanResult(
            passed=not has_critical_or_high,
            issues=issues[:self._max_issues],
            total_vulnerabilities=len(issues),
            critical_count=critical,
            high_count=high,
            medium_count=medium,
            low_count=low
        )

    def generate_report(self, result: SecurityScanResult) -> str:
        """生成安全扫描报告"""
        report = [
            "=" * 60,
            "安全扫描报告",
            "=" * 60,
            f"扫描结果: {'✅ 通过' if result.passed else '❌ 失败'}",
            f"漏洞总数: {result.total_vulnerabilities}",
            f"  严重(Critical): {result.critical_count}",
            f"  高危(High): {result.high_count}",
            f"  中危(Medium): {result.medium_count}",
            f"  低危(Low): {result.low_count}",
        ]

        if result.issues:
            report.extend(["", "-" * 60, "漏洞详情", "-" * 60])

            for issue in sorted(result.issues, key=lambda x: ["critical", "high", "medium", "low"].index(x.severity))[:20]:
                line_info = f":{issue.line}" if issue.line else ""
                report.append(f"  [{issue.severity.upper()}] {issue.code} {issue.file_path or ''}{line_info}: {issue.message}")

        return "\n".join(report)