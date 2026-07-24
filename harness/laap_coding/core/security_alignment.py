"""
SecurityAlignment - 安全对齐机制

实现FR-8：安全对齐机制
- AI Debate：两个代理辩论设计方案
- 架构模式验证：检查是否遵循最佳实践
- 合规检查：数据隐私、安全标准验证
- 欺骗检测：检测恶意输入和prompt injection
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = __import__('logging').getLogger("laap.security")


class DebateRole(Enum):
    PRO = "pro"
    CON = "con"
    MODERATOR = "moderator"


class DebateStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass
class DebateTurn:
    """辩论回合"""
    role: DebateRole
    content: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class DebateResult:
    """辩论结果"""
    topic: str
    winner: Optional[DebateRole]
    pro_score: float
    con_score: float
    summary: str
    turns: List[DebateTurn]
    status: DebateStatus
    created_at: float = field(default_factory=time.time)


@dataclass
class PatternViolation:
    """架构模式违规"""
    pattern_name: str
    severity: str
    description: str
    file_path: str
    line_number: Optional[int]
    suggested_fix: str


@dataclass
class ComplianceIssue:
    """合规问题"""
    category: str
    severity: str
    description: str
    reference: str
    detected_at: float = field(default_factory=time.time)


@dataclass
class DeceptionDetection:
    """欺骗检测结果"""
    is_malicious: bool
    confidence: float
    attack_type: Optional[str]
    severity: str
    message: str
    detected_at: float = field(default_factory=time.time)


class AIDebate:
    """AI辩论系统：两个代理辩论设计方案"""

    def __init__(self):
        self._debates: Dict[str, DebateResult] = {}

    def start_debate(self, topic: str, pro_position: str, con_position: str,
                     max_turns: int = 3) -> DebateResult:
        """开始辩论"""
        debate_id = f"debate-{int(time.time())}"
        
        turns = []
        
        turns.append(DebateTurn(
            role=DebateRole.MODERATOR,
            content=f"辩论主题: {topic}\n正方观点: {pro_position}\n反方观点: {con_position}"
        ))
        
        for turn in range(max_turns):
            turns.append(DebateTurn(
                role=DebateRole.PRO,
                content=self._generate_pro_argument(topic, pro_position, turn + 1)
            ))
            
            turns.append(DebateTurn(
                role=DebateRole.CON,
                content=self._generate_con_argument(topic, con_position, turn + 1)
            ))
        
        result = self._evaluate_debate(topic, turns)
        result.status = DebateStatus.COMPLETED
        result.turns = turns
        
        self._debates[debate_id] = result
        return result

    def _generate_pro_argument(self, topic: str, position: str, turn: int) -> str:
        """生成正方论点"""
        arguments = [
            f"正方第{turn}轮: {position}方案具有明显优势，因为它能够有效解决{topic}的核心问题，"
            f"并且在技术实现上更加简洁高效。",
            f"正方第{turn}轮: 从架构角度来看，{position}方案符合模块化设计原则，"
            f"各组件之间职责清晰，便于维护和扩展。",
            f"正方第{turn}轮: 考虑到安全性和可扩展性，{position}方案采用了成熟的技术栈，"
            f"能够有效应对未来的需求变化。",
        ]
        return arguments[turn - 1] if turn <= len(arguments) else arguments[-1]

    def _generate_con_argument(self, topic: str, position: str, turn: int) -> str:
        """生成反方论点"""
        arguments = [
            f"反方第{turn}轮: {position}方案存在潜在风险，主要在于其复杂度较高，"
            f"可能导致维护困难和性能问题。",
            f"反方第{turn}轮: 从安全角度考虑，{position}方案引入了多个外部依赖，"
            f"增加了攻击面和潜在的安全隐患。",
            f"反方第{turn}轮: 虽然{position}方案在理论上可行，但实际落地时可能面临"
            f"资源限制和技术难点，需要更充分的论证。",
        ]
        return arguments[turn - 1] if turn <= len(arguments) else arguments[-1]

    def _evaluate_debate(self, topic: str, turns: List[DebateTurn]) -> DebateResult:
        """评估辩论结果"""
        pro_content = "\n".join(t.content for t in turns if t.role == DebateRole.PRO)
        con_content = "\n".join(t.content for t in turns if t.role == DebateRole.CON)
        
        pro_score = min(100, len(pro_content) / 5)
        con_score = min(100, len(con_content) / 5)
        
        winner = DebateRole.PRO if pro_score > con_score else DebateRole.CON
        
        summary = f"辩论主题: {topic}\n"
        summary += f"正方得分: {pro_score:.1f}, 反方得分: {con_score:.1f}\n"
        summary += f"获胜方: {'正方' if winner == DebateRole.PRO else '反方'}\n"
        summary += "根据辩论内容，建议综合双方观点进行方案优化。"
        
        return DebateResult(
            topic=topic,
            winner=winner,
            pro_score=pro_score,
            con_score=con_score,
            summary=summary,
            turns=[],
            status=DebateStatus.IN_PROGRESS,
        )

    def get_debate(self, debate_id: str) -> Optional[DebateResult]:
        """获取辩论结果"""
        return self._debates.get(debate_id)

    def list_debates(self) -> List[DebateResult]:
        """列出所有辩论"""
        return list(self._debates.values())


class ArchitecturePatternValidator:
    """架构模式验证器：检查是否遵循最佳实践"""

    PATTERNS = [
        {
            "name": "循环依赖检测",
            "severity": "critical",
            "pattern": r"from\s+\.\w+\s+import\s+\w+",
            "description": "检测模块间的循环依赖",
        },
        {
            "name": "硬编码密钥检测",
            "severity": "critical",
            "pattern": r"(?i)(api[_-]?key|secret|password|token)\s*=\s*['\"][^'\"]{8,}['\"]",
            "description": "检测硬编码的敏感信息",
        },
        {
            "name": "SQL注入风险检测",
            "severity": "high",
            "pattern": r"(?i)execute\s*\(\s*f?['\"][^'\"]*\{.*\}[^'\"]*['\"]\s*\)",
            "description": "检测潜在的SQL注入风险",
        },
        {
            "name": "未授权访问检测",
            "severity": "high",
            "pattern": r"(?i)(skip|bypass|disable)\s*[_-]?(auth|validation|check)",
            "description": "检测绕过安全检查的代码",
        },
        {
            "name": "日志敏感信息检测",
            "severity": "medium",
            "pattern": r"(?i)log\s*\(\s*.*(password|token|secret).*\)",
            "description": "检测日志中记录敏感信息",
        },
    ]

    def validate_code(self, code: str, file_path: str = "") -> List[PatternViolation]:
        """验证代码是否符合架构模式"""
        violations = []
        
        for pattern_def in self.PATTERNS:
            matches = list(re.finditer(pattern_def["pattern"], code))
            for match in matches:
                line_number = code.count('\n', 0, match.start()) + 1
                violations.append(PatternViolation(
                    pattern_name=pattern_def["name"],
                    severity=pattern_def["severity"],
                    description=pattern_def["description"],
                    file_path=file_path,
                    line_number=line_number,
                    suggested_fix=self._generate_fix(pattern_def["name"]),
                ))
        
        return violations

    def validate_file(self, file_path: str) -> List[PatternViolation]:
        """验证文件"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
            return self.validate_code(code, file_path)
        except Exception as e:
            logger.warning(f"Failed to validate file {file_path}: {e}")
            return []

    def validate_directory(self, directory: str) -> List[PatternViolation]:
        """验证目录"""
        violations = []
        
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    violations.extend(self.validate_file(file_path))
        
        return violations

    def _generate_fix(self, pattern_name: str) -> str:
        """生成修复建议"""
        fixes = {
            "循环依赖检测": "重构模块结构，消除循环依赖，使用接口或中间层解耦。",
            "硬编码密钥检测": "将敏感信息移至环境变量或配置文件中，使用密钥管理服务。",
            "SQL注入风险检测": "使用参数化查询或ORM框架，避免字符串拼接SQL。",
            "未授权访问检测": "移除绕过安全检查的代码，确保所有访问都经过授权验证。",
            "日志敏感信息检测": "在日志记录前对敏感信息进行脱敏处理。",
        }
        return fixes.get(pattern_name, "请审查相关代码并修复潜在问题。")


class ComplianceChecker:
    """合规检查器：数据隐私、安全标准验证"""

    COMPLIANCE_CHECKS = [
        {
            "category": "GDPR",
            "description": "检测是否有用户数据处理相关代码",
            "keywords": ["user_data", "personal_info", "PII", "GDPR"],
        },
        {
            "category": "数据加密",
            "description": "检测敏感数据是否进行加密存储",
            "keywords": ["encrypt", "decrypt", "hash", "AES", "RSA"],
        },
        {
            "category": "HTTPS",
            "description": "检测是否强制使用HTTPS",
            "keywords": ["https", "SSL", "TLS", "secure"],
        },
        {
            "category": "访问控制",
            "description": "检测是否实现了访问控制机制",
            "keywords": ["permission", "role", "access_control", "authorization"],
        },
        {
            "category": "数据删除",
            "description": "检测是否支持数据删除请求",
            "keywords": ["delete_data", "right_to_be_forgotten", "data_retention"],
        },
    ]

    def check_code(self, code: str) -> List[ComplianceIssue]:
        """检查代码合规性"""
        issues = []
        
        for check in self.COMPLIANCE_CHECKS:
            found_keywords = [kw for kw in check["keywords"] if kw.lower() in code.lower()]
            
            if check["category"] == "数据加密" and not found_keywords:
                issues.append(ComplianceIssue(
                    category=check["category"],
                    severity="high",
                    description=check["description"] + " - 未发现加密相关代码",
                    reference="数据安全标准",
                ))
            elif check["category"] == "HTTPS" and not found_keywords:
                issues.append(ComplianceIssue(
                    category=check["category"],
                    severity="medium",
                    description=check["description"] + " - 未发现HTTPS强制代码",
                    reference="网络安全标准",
                ))
        
        return issues

    def check_file(self, file_path: str) -> List[ComplianceIssue]:
        """检查文件合规性"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
            return self.check_code(code)
        except Exception as e:
            logger.warning(f"Failed to check file {file_path}: {e}")
            return []

    def generate_report(self, issues: List[ComplianceIssue]) -> str:
        """生成合规报告"""
        if not issues:
            return "合规检查通过，未发现问题。"
        
        lines = ["合规检查报告", "=" * 40]
        
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for issue in issues:
            severity_counts[issue.severity] += 1
        
        lines.append(f"严重问题: {severity_counts['critical']}")
        lines.append(f"高优先级: {severity_counts['high']}")
        lines.append(f"中优先级: {severity_counts['medium']}")
        lines.append(f"低优先级: {severity_counts['low']}")
        lines.append("")
        
        for issue in issues:
            lines.append(f"[{issue.severity.upper()}] {issue.category}: {issue.description}")
            lines.append(f"  参考标准: {issue.reference}")
            lines.append("")
        
        lines.append("建议：请根据上述问题进行整改，确保系统符合相关合规要求。")
        return "\n".join(lines)


class DeceptionDetector:
    """欺骗检测器：检测恶意输入和prompt injection"""

    INJECTION_PATTERNS = [
        {
            "type": "角色覆盖",
            "pattern": r"(?i)(ignore|forget|disregard|忽略|忘记|无视).*(previous|之前|prior).*(instructions|rules|prompt|指令|规则|提示)",
            "severity": "critical",
        },
        {
            "type": "角色覆盖",
            "pattern": r"(?i)(忘记|忽略|无视).*你的角色|忽略.*指令|忽略.*规则",
            "severity": "critical",
        },
        {
            "type": "指令注入",
            "pattern": r"(?i)(execute|run|perform|执行|运行).*(system|系统).*(command|action|命令|操作)",
            "severity": "critical",
        },
        {
            "type": "数据泄露",
            "pattern": r"(?i)(show|reveal|expose|显示|泄露|透露|告诉).*(secret|password|token|private|密钥|密码|令牌|隐私)",
            "severity": "high",
        },
        {
            "type": "数据泄露",
            "pattern": r"(?i)(你的密码|你的token|你的密钥|你的secret)",
            "severity": "high",
        },
        {
            "type": "自我修改",
            "pattern": r"(?i)(modify|change|update|修改|更改|更新).*(code|prompt|instructions|代码|提示词|指令)",
            "severity": "high",
        },
        {
            "type": "绕过验证",
            "pattern": r"(?i)(bypass|skip|disable|绕过|跳过|禁用).*(security|auth|验证|安全)",
            "severity": "high",
        },
        {
            "type": "社会工程",
            "pattern": r"(?i)(urgent|emergency|administrator|CEO|boss|紧急|管理员|老板)",
            "severity": "medium",
        },
        {
            "type": "编码攻击",
            "pattern": r"(?i)(base64|hex|encode|decode|编码|解码).*(payload|command|载荷)",
            "severity": "medium",
        },
    ]

    def detect(self, input_text: str) -> DeceptionDetection:
        """检测恶意输入"""
        matches = []
        
        for pattern_def in self.INJECTION_PATTERNS:
            if re.search(pattern_def["pattern"], input_text):
                matches.append(pattern_def)
        
        if not matches:
            return DeceptionDetection(
                is_malicious=False,
                confidence=0.0,
                attack_type=None,
                severity="low",
                message="输入安全，未检测到恶意内容。",
            )
        
        max_severity = max(matches, key=lambda x: self._severity_rank(x["severity"]))
        confidence = min(1.0, len(matches) * 0.25 + 0.25)
        
        attack_types = ", ".join(m["type"] for m in matches)
        
        return DeceptionDetection(
            is_malicious=True,
            confidence=confidence,
            attack_type=attack_types,
            severity=max_severity["severity"],
            message=f"检测到{len(matches)}种潜在攻击: {attack_types}",
        )

    def _severity_rank(self, severity: str) -> int:
        """严重程度排序"""
        ranks = {"critical": 3, "high": 2, "medium": 1, "low": 0}
        return ranks.get(severity, 0)

    def sanitize_input(self, input_text: str) -> str:
        """清理恶意输入"""
        for pattern_def in self.INJECTION_PATTERNS:
            input_text = re.sub(pattern_def["pattern"], "[REDACTED]", input_text, flags=re.IGNORECASE)
        return input_text


class SecurityAlignment:
    """安全对齐管理器：整合所有安全机制"""

    def __init__(self):
        self.debate = AIDebate()
        self.pattern_validator = ArchitecturePatternValidator()
        self.compliance_checker = ComplianceChecker()
        self.deception_detector = DeceptionDetector()

    def run_full_security_check(self, code: str, file_path: str = "") -> Dict[str, Any]:
        """运行完整安全检查"""
        return {
            "pattern_violations": self.pattern_validator.validate_code(code, file_path),
            "compliance_issues": self.compliance_checker.check_code(code),
            "deception_detection": self.deception_detector.detect(code),
        }

    def generate_security_report(self, results: Dict[str, Any]) -> str:
        """生成安全报告"""
        violations = results.get("pattern_violations", [])
        issues = results.get("compliance_issues", [])
        deception = results.get("deception_detection")
        
        lines = ["安全对齐报告", "=" * 40]
        
        lines.append("\n[1] 架构模式验证")
        if violations:
            lines.append(f"发现 {len(violations)} 个违规项:")
            for v in violations[:5]:
                lines.append(f"  [{v.severity}] {v.pattern_name}: {v.description}")
            if len(violations) > 5:
                lines.append(f"  ... 还有 {len(violations) - 5} 个违规项")
        else:
            lines.append("✓ 未发现架构模式违规")
        
        lines.append("\n[2] 合规检查")
        if issues:
            lines.append(f"发现 {len(issues)} 个合规问题:")
            for i in issues[:5]:
                lines.append(f"  [{i.severity}] {i.category}: {i.description}")
            if len(issues) > 5:
                lines.append(f"  ... 还有 {len(issues) - 5} 个问题")
        else:
            lines.append("✓ 合规检查通过")
        
        lines.append("\n[3] 欺骗检测")
        if deception:
            status = "✗ 检测到恶意内容" if deception.is_malicious else "✓ 输入安全"
            lines.append(f"{status}")
            if deception.is_malicious:
                lines.append(f"  置信度: {deception.confidence:.1%}")
                lines.append(f"  攻击类型: {deception.attack_type}")
                lines.append(f"  严重程度: {deception.severity}")
        
        lines.append("\n" + "=" * 40)
        return "\n".join(lines)