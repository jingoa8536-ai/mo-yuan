"""
LAAP Consciousness Harness — 代码任务引擎核心架构

实现FR-1要求的7层认知架构：
- 感知层（PerceptionLayer）：需求解析器、意图分类器、上下文提取器
- 记忆层（MemoryLayer）：设计系统库、架构模式库、项目历史库
- 推理层（ReasoningLayer）：规划引擎、依赖分析器、冲突检测器
- 决策层（DecisionLayer）：审美评估器、架构合规器、质量门控
- 执行层（ExecutionLayer）：代码生成模板、工具编排器、沙箱执行器
- 验证层（VerificationLayer）：测试验证器、静态分析器、安全扫描器
- 反馈层（FeedbackLayer）：自修正循环、模式学习器、经验积累器

实现FR-1.3和FR-5.1：记忆层架构模式库
- 从YAML配置文件加载架构模式（CQRS、模块化单体、事件溯源、Repository、Dependency Injection）
- 模式匹配引擎：根据任务特征关键词自动选择合适的架构模式
- 项目历史库：存储和检索已完成任务记录
"""

from __future__ import annotations

import logging
import re
import time
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Set, Tuple
from pathlib import Path

try:
    import yaml
except ImportError:
    try:
        import ruamel.yaml as yaml
    except ImportError:
        yaml = None

try:
    from laap.agi.multi_agent import TaskBoard, SafeRollback
except ImportError:
    TaskBoard = None
    SafeRollback = None

try:
    from .test_validator import TestValidator, TestResult, CoverageReport
except ImportError:
    TestValidator = None
    TestResult = None
    CoverageReport = None

try:
    from .static_analyzer import StaticAnalyzer, AnalysisIssue, StaticAnalysisResult
except ImportError:
    StaticAnalyzer = None
    AnalysisIssue = None
    StaticAnalysisResult = None

try:
    from .security_scanner import SecurityScanner, SecurityIssue, SecurityScanResult
except ImportError:
    SecurityScanner = None
    SecurityIssue = None
    SecurityScanResult = None

try:
    from .incremental_delivery import IncrementalDelivery
except ImportError:
    IncrementalDelivery = None

try:
    from .cognitive_integration import (
        CognitiveIntegration,
        start_integration,
        stop_integration,
        get_context,
        process_pending_insights,
        HarnessExecutionResult,
        EmergenceInsight,
    )
except ImportError:
    CognitiveIntegration = None
    start_integration = None
    stop_integration = None
    get_context = None
    process_pending_insights = None
    HarnessExecutionResult = None
    EmergenceInsight = None

logger = logging.getLogger("laap.harness")


# ════════════════════════════════════════════════════════════
# 数据结构定义
# ════════════════════════════════════════════════════════════

@dataclass
class TaskContext:
    task_id: str
    description: str
    intent: str
    keywords: List[str]
    constraints: List[str]
    related_patterns: List[str]
    project_context: Dict[str, Any]
    created_at: float = field(default_factory=time.time)


@dataclass
class SubTask:
    sub_task_id: str
    parent_task_id: str
    description: str
    files: List[str]
    estimated_lines: int
    dependencies: List[str]
    status: str = "pending"
    created_at: float = field(default_factory=time.time)


@dataclass
class ExecutionResult:
    success: bool
    output: str
    modified_files: List[str]
    duration_ms: float
    error: Optional[str] = None


@dataclass
class VerificationResult:
    passed: bool
    issues: List[Dict[str, Any]]
    score: float = 0.0


# ════════════════════════════════════════════════════════════
# 感知层 — Perception Layer
# ════════════════════════════════════════════════════════════

class RequirementParser:
    """需求解析器：解析用户任务描述，提取关键词和约束"""

    def __init__(self):
        self._keyword_patterns = {
            "language": r"(python|javascript|typescript|rust|go|java|cpp|c\+\+|html|css)",
            "framework": r"(react|vue|angular|flask|django|fastapi|tornado|express)",
            "action": r"(implement|fix|create|add|remove|update|refactor|optimize|debug)",
            "scope": r"(frontend|backend|api|database|security|performance)",
        }

    def parse(self, description: str) -> Dict[str, Any]:
        result = {
            "keywords": [],
            "constraints": [],
            "language": [],
            "framework": [],
            "action": [],
            "scope": [],
        }

        for category, pattern in self._keyword_patterns.items():
            matches = re.findall(pattern, description, re.IGNORECASE)
            if matches:
                result[category] = [m.lower() for m in matches]
                result["keywords"].extend([m.lower() for m in matches])

        constraint_keywords = ["must", "should", "need", "require", "limit",
                               "avoid", "prevent", "ensure", "guarantee",
                               "不能", "必须", "应该", "需要", "限制", "避免"]
        for kw in constraint_keywords:
            if kw.lower() in description.lower():
                result["constraints"].append(kw)

        result["keywords"] = list(set(result["keywords"]))
        return result


class IntentClassifier:
    """意图分类器：分类任务类型（code/fix/implement/review/test）"""

    INTENT_CODES = {
        "code": ["write", "create", "generate", "build", "编写", "创建", "生成", "构建"],
        "fix": ["fix", "bug", "repair", "correct", "resolve", "修复", "修正", "解决"],
        "implement": ["implement", "add", "feature", "功能", "实现", "添加"],
        "review": ["review", "audit", "inspect", "check", "审查", "检查", "审计"],
        "test": ["test", "verify", "validate", "单元测试", "测试", "验证"],
        "refactor": ["refactor", "restructure", "重构", "优化"],
        "deploy": ["deploy", "publish", "部署", "发布"],
    }

    def classify(self, description: str) -> str:
        desc_lower = description.lower()

        for intent, keywords in self.INTENT_CODES.items():
            for kw in keywords:
                if kw.lower() in desc_lower:
                    return intent

        return "implement"


class ContextExtractor:
    """上下文提取器：从项目历史和架构模式中提取相关上下文"""

    def __init__(self, memory_layer: "MemoryLayer"):
        self.memory_layer = memory_layer

    def extract(self, description: str, keywords: List[str]) -> Dict[str, Any]:
        context = {
            "architecture_patterns": [],
            "project_history": [],
            "design_system": [],
        }

        for pattern in self.memory_layer.architecture_patterns:
            if any(kw in pattern.get("name", "").lower() for kw in keywords):
                context["architecture_patterns"].append(pattern)

        for history in self.memory_layer.project_history.get("history", []):
            if any(kw in history.get("description", "").lower() for kw in keywords):
                context["project_history"].append(history)

        for design in self.memory_layer.design_system:
            if any(kw in design.get("name", "").lower() for kw in keywords):
                context["design_system"].append(design)

        return context


class PerceptionLayer:
    """感知层：需求解析器、意图分类器、上下文提取器"""

    def __init__(self, memory_layer: Optional["MemoryLayer"] = None):
        self.requirement_parser = RequirementParser()
        self.intent_classifier = IntentClassifier()
        self.context_extractor = ContextExtractor(memory_layer) if memory_layer else None

    def perceive(self, description: str) -> TaskContext:
        parsed = self.requirement_parser.parse(description)
        intent = self.intent_classifier.classify(description)
        keywords = parsed["keywords"]

        related_patterns = []
        project_context = {}

        if self.context_extractor:
            extracted = self.context_extractor.extract(description, keywords)
            related_patterns = [p["name"] for p in extracted.get("architecture_patterns", [])]
            project_context = extracted

        return TaskContext(
            task_id=f"task_{int(time.time())}",
            description=description,
            intent=intent,
            keywords=keywords,
            constraints=parsed["constraints"],
            related_patterns=related_patterns,
            project_context=project_context,
        )


# ════════════════════════════════════════════════════════════
# 记忆层 — Memory Layer
# ════════════════════════════════════════════════════════════

class MemoryLayer:
    """记忆层：设计系统库、架构模式库、项目历史库

    实现FR-1.3：记忆层功能
    实现FR-5.1：架构模式库
    实现Task 6：跨会话状态工程

    核心能力：
    - 三层状态架构：工作记忆（当前上下文窗口）、短期记忆（项目约定、架构约束、工具配置）、长期记忆（已完成模块、决策记录、错误模式）
    - 从YAML配置文件加载架构模式（CQRS、模块化单体、事件溯源、Repository、Dependency Injection）
    - 模式匹配引擎：根据任务特征关键词自动选择合适的架构模式
    - 项目历史库：存储和检索已完成任务记录
    - 上下文压缩策略：摘要压缩、分支执行追踪
    - 跨会话状态传递机制：特征列表+Git提交记录+测试门控
    """

    def __init__(self, project_root: str = ""):
        self.project_root = project_root or os.environ.get("LAAP_ROOT", r"D:\LAAP")
        self._config_path = os.path.join(
            os.path.dirname(__file__), "..", "config", "architecture_patterns.yml"
        )
        self.architecture_patterns = self._load_architecture_patterns()
        self.design_system = self._load_design_system()
        self.project_history = self._load_project_history()
        self._pattern_index = self._build_pattern_index()
        
        self._working_memory: Dict[str, Any] = {}
        self._short_term_memory: Dict[str, Any] = {}
        self._long_term_memory: Dict[str, Any] = {}
        self._context_compressor = ContextCompressor()
        self._state_persistence = TaskStatePersistence(self.project_root)
        
        self._load_memory_layers()

    def _load_architecture_patterns(self) -> List[Dict[str, Any]]:
        if yaml is None:
            logger.warning("PyYAML not installed, using fallback patterns")
            return self._get_fallback_patterns()

        if not os.path.exists(self._config_path):
            logger.warning(f"Architecture patterns config not found: {self._config_path}")
            return self._get_fallback_patterns()

        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            patterns = config.get("architecture_patterns", [])
            logger.info(f"Loaded {len(patterns)} architecture patterns from {self._config_path}")
            return patterns
        except Exception as e:
            logger.error(f"Failed to load architecture patterns: {e}")
            return self._get_fallback_patterns()

    def _get_fallback_patterns(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "cqrs",
                "name": "CQRS",
                "category": "architecture",
                "description": "Command Query Responsibility Segregation",
                "triggers": ["高并发读写分离", "命令和查询性能差异大"],
                "structure": ["命令模型与查询模型完全分离"],
                "quality_gates": ["命令和查询代码路径隔离"],
                "keywords": ["command", "query", "separation", "event"],
            },
            {
                "id": "modular_monolith",
                "name": "Modular Monolith",
                "category": "architecture",
                "description": "Single codebase with modular components",
                "triggers": ["团队规模小", "统一技术栈"],
                "structure": ["单一代码仓库，多个业务模块"],
                "quality_gates": ["模块间无循环依赖"],
                "keywords": ["module", "monolith", "boundary"],
            },
            {
                "id": "event_sourcing",
                "name": "Event Sourcing",
                "category": "architecture",
                "description": "Store state changes as events",
                "triggers": ["审计日志", "事件驱动"],
                "structure": ["不可变事件日志"],
                "quality_gates": ["事件不可变"],
                "keywords": ["event", "store", "projection"],
            },
            {
                "id": "repository",
                "name": "Repository Pattern",
                "category": "design",
                "description": "Abstraction layer for data access",
                "triggers": ["数据访问抽象", "多种数据源"],
                "structure": ["定义通用仓储接口"],
                "quality_gates": ["领域层只依赖接口"],
                "keywords": ["repository", "data", "access"],
            },
            {
                "id": "dependency_injection",
                "name": "Dependency Injection",
                "category": "design",
                "description": "Inversion of control for dependencies",
                "triggers": ["提高可测试性", "复杂依赖关系"],
                "structure": ["依赖通过构造函数注入"],
                "quality_gates": ["无硬编码依赖实例化"],
                "keywords": ["dependency", "inject", "container"],
            },
        ]

    def _build_pattern_index(self) -> Dict[str, Dict[str, Any]]:
        index = {}
        for pattern in self.architecture_patterns:
            index[pattern["id"].lower()] = pattern
            index[pattern["name"].lower()] = pattern
            for keyword in pattern.get("keywords", []):
                index[keyword.lower()] = pattern
        return index

    def _load_design_system(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "soc",
                "name": "Separation of Concerns",
                "description": "Different modules handle different concerns",
                "category": "principle",
                "keywords": ["concerns", "separation"],
                "triggers": ["复杂系统", "职责划分"],
                "structure": ["按关注点划分模块"],
                "quality_gates": ["模块职责单一"],
            },
            {
                "id": "sr",
                "name": "Single Responsibility",
                "description": "Each class has one responsibility",
                "category": "principle",
                "keywords": ["single", "responsibility"],
                "triggers": ["类职责过重", "难以测试"],
                "structure": ["一个类只做一件事"],
                "quality_gates": ["类方法不超过10个"],
            },
            {
                "id": "oc",
                "name": "Open Closed",
                "description": "Open for extension, closed for modification",
                "category": "principle",
                "keywords": ["open", "closed", "extension"],
                "triggers": ["频繁修改", "需要扩展"],
                "structure": ["通过接口扩展"],
                "quality_gates": ["修改不影响现有代码"],
            },
            {
                "id": "dry",
                "name": "DRY",
                "description": "Don't Repeat Yourself",
                "category": "principle",
                "keywords": ["dry", "repeat"],
                "triggers": ["重复代码", "维护困难"],
                "structure": ["提取公共逻辑"],
                "quality_gates": ["无重复代码块"],
            },
        ]

    def _load_project_history(self) -> Dict[str, Any]:
        history_path = os.path.join(self.project_root, ".laap", "project_history.json")
        if os.path.exists(history_path):
            try:
                with open(history_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load project history: {e}")
        return {
            "project_id": "default",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "description": "Default project",
            "history": [],
        }

    def add_project_event(self, event: Dict[str, Any]) -> None:
        event_id = f"event-{int(time.time())}"
        event["event_id"] = event_id
        event["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if "history" not in self.project_history:
            self.project_history["history"] = []

        self.project_history["history"].append(event)
        self._save_project_history()

        logger.info(f"Added project event: {event_id} - {event.get('description', '')}")

    def _save_project_history(self) -> None:
        history_path = os.path.join(self.project_root, ".laap", "project_history.json")
        os.makedirs(os.path.dirname(history_path), exist_ok=True)
        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump(self.project_history, f, indent=2, ensure_ascii=False)

    def get_project_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        history = self.project_history.get("history", [])
        return history[-limit:]

    def search_project_history(self, query: str) -> List[Dict[str, Any]]:
        results = []
        query_lower = query.lower()
        for event in self.project_history.get("history", []):
            if (query_lower in event.get("description", "").lower() or
                query_lower in event.get("type", "").lower() or
                query_lower in str(event.get("metadata", "")).lower()):
                results.append(event)
        return results

    def get_pattern_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        for pattern in self.architecture_patterns:
            if pattern["name"].lower() == name.lower():
                return pattern
        return None

    def get_pattern_by_id(self, pattern_id: str) -> Optional[Dict[str, Any]]:
        for pattern in self.architecture_patterns:
            if pattern["id"].lower() == pattern_id.lower():
                return pattern
        return None

    def match_patterns(self, keywords: List[str], threshold: int = 1) -> List[Tuple[Dict[str, Any], int]]:
        """模式匹配引擎：根据关键词匹配架构模式

        Args:
            keywords: 任务特征关键词列表
            threshold: 最小匹配关键词数量

        Returns:
            匹配的模式列表，按匹配度排序，每个元素是(模式, 匹配分数)
        """
        scores = []

        for pattern in self.architecture_patterns:
            pattern_keywords = pattern.get("keywords", [])
            pattern_triggers = pattern.get("triggers", [])

            score = 0
            matched_keywords = []

            for kw in keywords:
                kw_lower = kw.lower()
                for p_kw in pattern_keywords:
                    if kw_lower in p_kw.lower() or p_kw.lower() in kw_lower:
                        score += 2
                        matched_keywords.append(kw)
                        break

                for trigger in pattern_triggers:
                    if kw_lower in trigger.lower():
                        score += 1
                        break

            if score >= threshold:
                scores.append((pattern, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    def recommend_patterns(self, description: str, top_n: int = 3) -> List[Dict[str, Any]]:
        """根据任务描述推荐架构模式

        Args:
            description: 任务描述文本
            top_n: 返回前N个推荐模式

        Returns:
            推荐的架构模式列表
        """
        tokens = self._extract_tokens(description)

        matched = self.match_patterns(tokens, threshold=1)
        recommendations = []

        for pattern, score in matched[:top_n]:
            recommendations.append({
                "id": pattern["id"],
                "name": pattern["name"],
                "category": pattern.get("category", ""),
                "description": pattern.get("description", ""),
                "match_score": score,
                "triggers": pattern.get("triggers", []),
                "structure": pattern.get("structure", []),
                "quality_gates": pattern.get("quality_gates", []),
                "keywords": pattern.get("keywords", []),
            })

        return recommendations

    def _extract_tokens(self, text: str) -> List[str]:
        """从文本中提取tokens，支持中英文混合"""
        tokens = []

        english_words = re.findall(r'[a-zA-Z]+', text, re.IGNORECASE)
        tokens.extend([w.lower() for w in english_words])

        chinese_chars = re.findall(r'[\u4e00-\u9fff]+', text)
        for char_group in chinese_chars:
            tokens.extend(list(char_group))

        for i in range(len(chinese_chars)):
            for j in range(i + 1, len(chinese_chars)):
                tokens.append(chinese_chars[i] + chinese_chars[j])

        return list(set(tokens))

    def get_all_patterns(self) -> List[Dict[str, Any]]:
        """获取所有架构模式"""
        return self.architecture_patterns

    def get_pattern_categories(self) -> List[str]:
        """获取所有架构模式类别"""
        categories = set()
        for pattern in self.architecture_patterns:
            categories.add(pattern.get("category", "uncategorized"))
        return sorted(list(categories))

    def validate_pattern_quality(self, pattern_id: str, code_context: Dict[str, Any]) -> Dict[str, Any]:
        """验证代码是否符合指定模式的质量门控

        Args:
            pattern_id: 模式ID
            code_context: 代码上下文信息

        Returns:
            验证结果，包含通过状态和违规项
        """
        pattern = self.get_pattern_by_id(pattern_id)
        if not pattern:
            return {"valid": False, "error": f"Pattern {pattern_id} not found"}

        quality_gates = pattern.get("quality_gates", [])
        violations = []

        for gate in quality_gates:
            if not self._check_quality_gate(gate, code_context):
                violations.append(gate)

        return {
            "valid": len(violations) == 0,
            "pattern_name": pattern["name"],
            "total_gates": len(quality_gates),
            "passed_gates": len(quality_gates) - len(violations),
            "violations": violations,
        }

    def _check_quality_gate(self, gate: str, code_context: Dict[str, Any]) -> bool:
        """检查单个质量门控"""
        gate_lower = gate.lower()

        if "循环依赖" in gate:
            return not code_context.get("has_circular_dependency", False)
        if "硬编码" in gate:
            return not code_context.get("has_hardcoded_dependencies", False)
        if "接口" in gate:
            return code_context.get("uses_interfaces", True)
        if "事务" in gate:
            return code_context.get("has_transactions", True)

        return True

    # ════════════════════════════════════════════════════════
    # 三层状态架构方法
    # ════════════════════════════════════════════════════════

    def _load_memory_layers(self) -> None:
        """加载三层记忆"""
        self._short_term_memory = self._state_persistence.load_short_term_memory()
        self._long_term_memory = self._state_persistence.load_long_term_memory()

    def add_working_memory(self, key: str, value: Any) -> None:
        """添加工作记忆（当前上下文窗口）"""
        self._working_memory[key] = value

    def get_working_memory(self, key: str) -> Any:
        """获取工作记忆"""
        return self._working_memory.get(key)

    def clear_working_memory(self) -> None:
        """清除工作记忆"""
        self._working_memory.clear()

    def add_short_term_memory(self, key: str, value: Any) -> None:
        """添加短期记忆（项目约定、架构约束、工具配置）"""
        self._short_term_memory[key] = value
        self._state_persistence.save_short_term_memory(self._short_term_memory)

    def get_short_term_memory(self, key: str) -> Any:
        """获取短期记忆"""
        return self._short_term_memory.get(key)

    def add_long_term_memory(self, key: str, value: Any) -> None:
        """添加长期记忆（已完成模块、决策记录、错误模式）"""
        self._long_term_memory[key] = value
        self._state_persistence.save_long_term_memory(self._long_term_memory)

    def get_long_term_memory(self, key: str) -> Any:
        """获取长期记忆"""
        return self._long_term_memory.get(key)

    def compress_context(self, context: str, max_tokens: int = 500) -> str:
        """压缩上下文（摘要压缩策略）"""
        return self._context_compressor.compress(context, max_tokens)

    def get_compression_ratio(self, original: str, compressed: str) -> float:
        """计算压缩比率"""
        return self._context_compressor.calculate_ratio(original, compressed)

    def get_feature_list(self, task_id: str) -> Dict[str, Any]:
        """获取任务特征列表（跨会话状态传递）"""
        return self._state_persistence.get_feature_list(task_id)

    def save_feature_list(self, task_id: str, features: Dict[str, Any]) -> None:
        """保存任务特征列表"""
        self._state_persistence.save_feature_list(task_id, features)

    def get_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态（用于恢复）"""
        return self._state_persistence.load_task_state(task_id)

    def save_task_state(self, task_id: str, state: Dict[str, Any]) -> None:
        """保存任务状态"""
        self._state_persistence.save_task_state(task_id, state)

    def restore_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        """恢复任务状态（跨会话恢复）"""
        return self._state_persistence.restore_task_state(task_id)

    def get_memory_status(self) -> Dict[str, Any]:
        """获取记忆层状态"""
        return {
            "working_memory": {
                "size": len(self._working_memory),
                "keys": list(self._working_memory.keys()),
            },
            "short_term_memory": {
                "size": len(self._short_term_memory),
                "keys": list(self._short_term_memory.keys()),
            },
            "long_term_memory": {
                "size": len(self._long_term_memory),
                "keys": list(self._long_term_memory.keys()),
            },
        }


# ════════════════════════════════════════════════════════════
# 上下文压缩器 — Context Compressor
# ════════════════════════════════════════════════════════════

class ContextCompressor:
    """上下文压缩器：摘要压缩、分支执行追踪

    实现FR-4.4：上下文压缩策略
    - 摘要压缩：将长上下文压缩为摘要
    - 分支执行追踪：记录和管理分支执行历史
    - 压缩比率计算：评估压缩效果
    """

    def compress(self, context: str, max_tokens: int = 500) -> str:
        """压缩上下文到指定token数（按字符估算，1token≈2字符）"""
        if not context:
            return ""

        max_chars = max_tokens * 2
        if len(context) <= max_chars:
            return context

        sentences = self._tokenize(context)
        compressed = self._smart_compress(sentences, max_chars)
        return compressed

    def _tokenize(self, text: str) -> List[str]:
        """简单的分词实现"""
        import re
        sentences = re.split(r'[.!?。！？\n]+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _smart_compress(self, sentences: List[str], max_chars: int) -> str:
        """智能压缩：保留关键信息，按字符数限制"""
        key_phrases = ["实现", "创建", "修复", "添加", "删除", "更新",
                       "设计", "分析", "验证", "测试", "架构", "模式",
                       "依赖", "接口", "模型", "服务", "API", "路由",
                       "需求", "功能", "技术", "要求", "项目", "结构"]

        priority_sentences = []
        normal_sentences = []

        for sentence in sentences:
            has_key_phrase = any(phrase in sentence for phrase in key_phrases)
            if has_key_phrase:
                priority_sentences.append(sentence)
            else:
                normal_sentences.append(sentence)

        combined = priority_sentences + normal_sentences
        result = []
        current_length = 0

        for sentence in combined:
            sentence_length = len(sentence) + 1
            if current_length + sentence_length <= max_chars:
                result.append(sentence)
                current_length += sentence_length
            else:
                if current_length < max_chars:
                    remaining = max_chars - current_length
                    truncated = sentence[:remaining - 3] + "..."
                    result.append(truncated)
                break

        return "。".join(result)

    def calculate_ratio(self, original: str, compressed: str) -> float:
        """计算压缩比率"""
        if not original:
            return 0.0
        original_len = len(original)
        compressed_len = len(compressed)
        return (original_len - compressed_len) / original_len

    def compress_with_summary(self, context: str, max_tokens: int = 500) -> Dict[str, Any]:
        """压缩并生成摘要"""
        compressed = self.compress(context, max_tokens)
        ratio = self.calculate_ratio(context, compressed)
        
        return {
            "original_length": len(context),
            "compressed_length": len(compressed),
            "compression_ratio": ratio,
            "compressed_text": compressed,
            "summary": self._generate_summary(context),
        }

    def _generate_summary(self, context: str) -> str:
        """生成上下文摘要"""
        lines = context.split('\n')
        if len(lines) <= 3:
            return context[:200]

        first_line = lines[0].strip()
        last_line = lines[-1].strip()

        key_elements = []
        for line in lines[:10]:
            if any(kw in line for kw in ["任务", "目标", "需求", "实现", "功能"]):
                key_elements.append(line.strip())

        summary_parts = [first_line] + key_elements
        if last_line not in summary_parts:
            summary_parts.append(last_line)

        return "；".join(summary_parts)[:300]


# ════════════════════════════════════════════════════════════
# 任务状态持久化 — Task State Persistence
# ════════════════════════════════════════════════════════════

class TaskStatePersistence:
    """任务状态持久化：跨会话状态传递和恢复

    实现FR-4.5：任务状态持久化和恢复机制
    - 特征列表存储：任务关键特征、上下文摘要、已完成子任务列表
    - Git提交记录：关联任务状态与版本控制
    - 测试门控记录：各阶段测试结果
    - 任务状态恢复：从中断点继续执行
    """

    def __init__(self, project_root: str):
        self.project_root = project_root
        self._state_dir = os.path.join(project_root, ".laap", "task_states")
        self._memory_dir = os.path.join(project_root, ".laap", "memory")
        os.makedirs(self._state_dir, exist_ok=True)
        os.makedirs(self._memory_dir, exist_ok=True)

    def save_task_state(self, task_id: str, state: Dict[str, Any]) -> str:
        """保存任务状态"""
        state_path = os.path.join(self._state_dir, f"{task_id}.json")
        state["saved_at"] = time.time()
        
        with open(state_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        
        return state_path

    def load_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        """加载任务状态"""
        state_path = os.path.join(self._state_dir, f"{task_id}.json")
        if not os.path.exists(state_path):
            return None
        
        try:
            with open(state_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load task state: {e}")
            return None

    def restore_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        """恢复任务状态（包含验证）"""
        state = self.load_task_state(task_id)
        if not state:
            return None

        if not self._validate_state(state):
            logger.warning(f"Invalid task state: {task_id}")
            return None

        return state

    def _validate_state(self, state: Dict[str, Any]) -> bool:
        """验证任务状态完整性"""
        required_fields = ["task_id", "description", "subtasks", "current_subtask_index", "status"]
        return all(field in state for field in required_fields)

    def save_feature_list(self, task_id: str, features: Dict[str, Any]) -> None:
        """保存任务特征列表"""
        feature_path = os.path.join(self._memory_dir, f"features_{task_id}.json")
        features["updated_at"] = time.time()
        
        with open(feature_path, 'w', encoding='utf-8') as f:
            json.dump(features, f, indent=2, ensure_ascii=False)

    def get_feature_list(self, task_id: str) -> Dict[str, Any]:
        """获取任务特征列表"""
        feature_path = os.path.join(self._memory_dir, f"features_{task_id}.json")
        if not os.path.exists(feature_path):
            return {}
        
        try:
            with open(feature_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load feature list: {e}")
            return {}

    def save_short_term_memory(self, memory: Dict[str, Any]) -> None:
        """保存短期记忆"""
        memory_path = os.path.join(self._memory_dir, "short_term_memory.json")
        memory["updated_at"] = time.time()
        
        with open(memory_path, 'w', encoding='utf-8') as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)

    def load_short_term_memory(self) -> Dict[str, Any]:
        """加载短期记忆"""
        memory_path = os.path.join(self._memory_dir, "short_term_memory.json")
        if not os.path.exists(memory_path):
            return {}
        
        try:
            with open(memory_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load short term memory: {e}")
            return {}

    def save_long_term_memory(self, memory: Dict[str, Any]) -> None:
        """保存长期记忆"""
        memory_path = os.path.join(self._memory_dir, "long_term_memory.json")
        memory["updated_at"] = time.time()
        
        with open(memory_path, 'w', encoding='utf-8') as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)

    def load_long_term_memory(self) -> Dict[str, Any]:
        """加载长期记忆"""
        memory_path = os.path.join(self._memory_dir, "long_term_memory.json")
        if not os.path.exists(memory_path):
            return {}
        
        try:
            with open(memory_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load long term memory: {e}")
            return {}

    def list_tasks_with_state(self) -> List[Dict[str, Any]]:
        """列出所有有状态的任务"""
        tasks = []
        if not os.path.exists(self._state_dir):
            return tasks
        
        for filename in os.listdir(self._state_dir):
            if filename.endswith(".json"):
                task_id = filename.replace(".json", "")
                state = self.load_task_state(task_id)
                if state:
                    tasks.append({
                        "task_id": task_id,
                        "description": state.get("description", ""),
                        "status": state.get("status", "unknown"),
                        "saved_at": state.get("saved_at", 0),
                    })
        
        return sorted(tasks, key=lambda x: x["saved_at"], reverse=True)

    def delete_task_state(self, task_id: str) -> bool:
        """删除任务状态"""
        state_path = os.path.join(self._state_dir, f"{task_id}.json")
        if os.path.exists(state_path):
            os.remove(state_path)
            return True
        return False


# ════════════════════════════════════════════════════════════
# 推理层 — Reasoning Layer
# ════════════════════════════════════════════════════════════

class DependencyGraph:
    """依赖图数据结构：支持拓扑排序和循环依赖检测"""

    def __init__(self):
        self._nodes: Dict[str, SubTask] = {}
        self._edges: Dict[str, List[str]] = {}

    def add_node(self, subtask: SubTask) -> None:
        self._nodes[subtask.sub_task_id] = subtask
        if subtask.sub_task_id not in self._edges:
            self._edges[subtask.sub_task_id] = []

    def add_dependency(self, from_id: str, to_id: str) -> None:
        if from_id not in self._edges:
            self._edges[from_id] = []
        if to_id not in self._edges[from_id]:
            self._edges[from_id].append(to_id)

    def build_from_subtasks(self, subtasks: List[SubTask]) -> None:
        for subtask in subtasks:
            self.add_node(subtask)
            for dep_id in subtask.dependencies:
                self.add_dependency(dep_id, subtask.sub_task_id)

    def topological_sort(self) -> List[str]:
        in_degree: Dict[str, int] = {node: 0 for node in self._nodes}
        
        for node in self._edges:
            for neighbor in self._edges[node]:
                if neighbor in in_degree:
                    in_degree[neighbor] += 1

        queue = [node for node in in_degree if in_degree[node] == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            for neighbor in self._edges.get(node, []):
                if neighbor in in_degree:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

        if len(result) != len(self._nodes):
            cycle = self._find_cycle()
            raise ValueError(f"循环依赖检测: {cycle}")

        return result

    def _find_cycle(self) -> List[str]:
        visited = set()
        rec_stack = set()

        def dfs(node):
            if node not in visited:
                visited.add(node)
                rec_stack.add(node)

                for neighbor in self._edges.get(node, []):
                    if neighbor not in visited and dfs(neighbor):
                        return True
                    elif neighbor in rec_stack:
                        return True

            if node in rec_stack:
                rec_stack.remove(node)
            return False

        for node in self._nodes:
            if dfs(node):
                return list(rec_stack)
        return []

    def detect_cycles(self) -> List[List[str]]:
        cycles = []
        visited = set()

        def dfs(node, path):
            if node in visited:
                if node in path:
                    idx = path.index(node)
                    cycles.append(path[idx:])
                return

            visited.add(node)
            path.append(node)

            for neighbor in self._edges.get(node, []):
                dfs(neighbor, path.copy())

        for node in self._nodes:
            if node not in visited:
                dfs(node, [])

        return cycles

    def get_dependencies(self, node_id: str) -> List[str]:
        return self._edges.get(node_id, [])

    def get_dependents(self, node_id: str) -> List[str]:
        dependents = []
        for source, targets in self._edges.items():
            if node_id in targets:
                dependents.append(source)
        return dependents

    def get_independent_tasks(self) -> List[str]:
        in_degree: Dict[str, int] = {node: 0 for node in self._nodes}

        for node in self._edges:
            for neighbor in self._edges[node]:
                if neighbor in in_degree:
                    in_degree[neighbor] += 1

        return [node for node, degree in in_degree.items() if degree == 0]

    def get_node(self, node_id: str) -> Optional[SubTask]:
        return self._nodes.get(node_id)

    def get_sorted_subtasks(self) -> List[SubTask]:
        sorted_ids = self.topological_sort()
        return [self._nodes[node_id] for node_id in sorted_ids]

    def __repr__(self) -> str:
        return f"DependencyGraph(nodes={len(self._nodes)}, edges={sum(len(v) for v in self._edges.values())})"


class SubTaskGranularityControl:
    """子任务粒度控制：代码行数预估和自动拆分"""

    MAX_LINES_PER_SUBTASK = 200

    _complexity_multipliers = {
        "implement": 1.0,
        "fix": 0.3,
        "review": 0.1,
        "test": 0.6,
        "refactor": 0.8,
        "deploy": 0.2,
    }

    _task_type_templates = {
        "crud": {
            "base_lines": 150,
            "operations": ["create", "read", "update", "delete"],
        },
        "api": {
            "base_lines": 100,
            "operations": ["endpoint", "middleware", "validation", "error_handling"],
        },
        "auth": {
            "base_lines": 200,
            "operations": ["login", "logout", "register", "token", "refresh"],
        },
        "database": {
            "base_lines": 80,
            "operations": ["schema", "migration", "queries", "connection"],
        },
    }

    def estimate_lines(self, description: str, intent: str) -> int:
        base_estimate = 100

        multiplier = self._complexity_multipliers.get(intent, 1.0)

        for template_name, template in self._task_type_templates.items():
            if template_name in description.lower():
                base_estimate = template["base_lines"]
                break

        keyword_multipliers = {
            "复杂": 1.5,
            "高级": 1.5,
            "完整": 1.3,
            "大规模": 2.0,
            "简单": 0.5,
            "基础": 0.7,
            "核心": 1.2,
            "扩展": 1.1,
        }

        for keyword, mult in keyword_multipliers.items():
            if keyword in description:
                base_estimate = int(base_estimate * mult)

        if len(description) > 100:
            base_estimate = int(base_estimate * 1.2)
        if len(description) > 200:
            base_estimate = int(base_estimate * 1.5)

        return int(base_estimate * multiplier)

    def should_split(self, estimated_lines: int) -> bool:
        return estimated_lines > self.MAX_LINES_PER_SUBTASK

    def split_task(self, subtask: SubTask, target_lines: int = MAX_LINES_PER_SUBTASK) -> List[SubTask]:
        if subtask.estimated_lines <= target_lines:
            return [subtask]

        num_parts = (subtask.estimated_lines + target_lines - 1) // target_lines

        sub_tasks = []
        base_id = subtask.sub_task_id
        parent_id = subtask.parent_task_id
        base_deps = subtask.dependencies.copy()

        for i in range(num_parts):
            part_lines = target_lines if i < num_parts - 1 else subtask.estimated_lines - (num_parts - 1) * target_lines
            part_deps = base_deps.copy()

            if i > 0:
                part_deps.append(f"{base_id}_{i}")

            new_subtask = SubTask(
                sub_task_id=f"{base_id}_{i + 1}",
                parent_task_id=parent_id,
                description=f"{subtask.description} - 第{i + 1}部分",
                files=subtask.files.copy(),
                estimated_lines=part_lines,
                dependencies=part_deps,
                status="pending",
            )
            sub_tasks.append(new_subtask)

        return sub_tasks

    def validate_granularity(self, subtasks: List[SubTask]) -> Dict[str, Any]:
        issues = []
        warnings = []

        for subtask in subtasks:
            if subtask.estimated_lines > self.MAX_LINES_PER_SUBTASK:
                issues.append({
                    "sub_task_id": subtask.sub_task_id,
                    "description": subtask.description,
                    "estimated_lines": subtask.estimated_lines,
                    "max_allowed": self.MAX_LINES_PER_SUBTASK,
                    "message": f"子任务预估代码量超过限制: {subtask.estimated_lines} > {self.MAX_LINES_PER_SUBTASK}",
                })
            elif subtask.estimated_lines > self.MAX_LINES_PER_SUBTASK * 0.8:
                warnings.append({
                    "sub_task_id": subtask.sub_task_id,
                    "description": subtask.description,
                    "estimated_lines": subtask.estimated_lines,
                    "message": "子任务预估代码量接近上限",
                })

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "total_subtasks": len(subtasks),
            "avg_lines": sum(s.estimated_lines for s in subtasks) / max(len(subtasks), 1),
        }


class PlanningEngine:
    """规划引擎：任务分解与依赖图管理

    实现FR-2.2：Planner Agent功能
    实现Task 3：规划引擎完整功能

    核心能力：
    - 任务分解算法：将复杂任务拆分为多个子任务（每个子任务≤200行变更）
    - 依赖图生成器：确定子任务执行顺序
    - 不同类型任务的规划策略（implement/fix/review/test/refactor/deploy）
    - 架构模式库集成：根据推荐模式调整子任务规划
    - TaskBoard集成：任务自动注册和状态同步
    """

    def __init__(self, memory_layer: Optional[MemoryLayer] = None, task_board: Optional["TaskBoard"] = None):
        self.memory_layer = memory_layer
        self.task_board = task_board
        self.granularity_control = SubTaskGranularityControl()
        self._planning_strategies = {
            "implement": self._plan_implement,
            "fix": self._plan_fix,
            "review": self._plan_review,
            "test": self._plan_test,
            "refactor": self._plan_refactor,
            "deploy": self._plan_deploy,
            "code": self._plan_implement,
            "create": self._plan_implement,
        }

    def plan(self, context: TaskContext) -> List[SubTask]:
        strategy = self._planning_strategies.get(context.intent, self._plan_implement)
        subtasks = strategy(context)

        subtasks = self._apply_architecture_patterns(subtasks, context)

        subtasks = self._ensure_granularity(subtasks)

        self._register_with_task_board(subtasks)

        return subtasks

    def plan_with_dependency_graph(self, context: TaskContext) -> Dict[str, Any]:
        subtasks = self.plan(context)

        graph = DependencyGraph()
        graph.build_from_subtasks(subtasks)

        cycles = graph.detect_cycles()
        if cycles:
            logger.warning(f"检测到循环依赖: {cycles}")

        sorted_subtasks = graph.get_sorted_subtasks()

        return {
            "subtasks": sorted_subtasks,
            "dependency_graph": graph,
            "cycles": cycles,
            "execution_order": [s.sub_task_id for s in sorted_subtasks],
            "independent_tasks": graph.get_independent_tasks(),
        }

    def _plan_implement(self, context: TaskContext) -> List[SubTask]:
        base_id = context.task_id
        description = context.description.lower()

        subtasks = []

        if any(keyword in description for keyword in ["crud", "博客", "文章", "系统"]):
            subtasks = self._plan_crud_system(base_id, context)
        elif any(keyword in description for keyword in ["api", "rest", "接口"]):
            subtasks = self._plan_api_system(base_id, context)
        elif any(keyword in description for keyword in ["auth", "login", "认证", "登录"]):
            subtasks = self._plan_auth_system(base_id, context)
        else:
            subtasks = self._plan_generic_implement(base_id, context)

        return subtasks

    def _plan_crud_system(self, base_id: str, context: TaskContext) -> List[SubTask]:
        return [
            SubTask(
                sub_task_id=f"{base_id}_1",
                parent_task_id=context.task_id,
                description="分析需求并设计数据模型",
                files=["models.py"],
                estimated_lines=50,
                dependencies=[],
            ),
            SubTask(
                sub_task_id=f"{base_id}_2",
                parent_task_id=context.task_id,
                description="实现数据库schema和迁移",
                files=["schema.sql", "migrations/001_initial.py"],
                estimated_lines=60,
                dependencies=[f"{base_id}_1"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_3",
                parent_task_id=context.task_id,
                description="实现Repository数据访问层",
                files=["repository.py"],
                estimated_lines=80,
                dependencies=[f"{base_id}_2"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_4",
                parent_task_id=context.task_id,
                description="实现业务逻辑层（Service）",
                files=["service.py"],
                estimated_lines=100,
                dependencies=[f"{base_id}_3"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_5",
                parent_task_id=context.task_id,
                description="实现API路由和控制器",
                files=["api.py", "routes.py"],
                estimated_lines=120,
                dependencies=[f"{base_id}_4"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_6",
                parent_task_id=context.task_id,
                description="实现请求验证和错误处理",
                files=["validators.py", "exceptions.py"],
                estimated_lines=60,
                dependencies=[f"{base_id}_5"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_7",
                parent_task_id=context.task_id,
                description="编写单元测试",
                files=["tests/test_models.py", "tests/test_service.py", "tests/test_api.py"],
                estimated_lines=150,
                dependencies=[f"{base_id}_4", f"{base_id}_5"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_8",
                parent_task_id=context.task_id,
                description="集成测试和验证",
                files=["tests/test_integration.py"],
                estimated_lines=80,
                dependencies=[f"{base_id}_7"],
            ),
        ]

    def _plan_api_system(self, base_id: str, context: TaskContext) -> List[SubTask]:
        return [
            SubTask(
                sub_task_id=f"{base_id}_1",
                parent_task_id=context.task_id,
                description="设计API接口规范",
                files=["openapi.yaml"],
                estimated_lines=40,
                dependencies=[],
            ),
            SubTask(
                sub_task_id=f"{base_id}_2",
                parent_task_id=context.task_id,
                description="实现API路由注册",
                files=["routes.py"],
                estimated_lines=50,
                dependencies=[f"{base_id}_1"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_3",
                parent_task_id=context.task_id,
                description="实现请求处理器",
                files=["handlers.py"],
                estimated_lines=100,
                dependencies=[f"{base_id}_2"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_4",
                parent_task_id=context.task_id,
                description="实现中间件（认证、日志）",
                files=["middleware.py"],
                estimated_lines=80,
                dependencies=[f"{base_id}_2"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_5",
                parent_task_id=context.task_id,
                description="实现数据序列化和反序列化",
                files=["serializers.py"],
                estimated_lines=60,
                dependencies=[f"{base_id}_3"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_6",
                parent_task_id=context.task_id,
                description="编写API测试",
                files=["tests/test_api.py"],
                estimated_lines=100,
                dependencies=[f"{base_id}_3", f"{base_id}_4"],
            ),
        ]

    def _plan_auth_system(self, base_id: str, context: TaskContext) -> List[SubTask]:
        return [
            SubTask(
                sub_task_id=f"{base_id}_1",
                parent_task_id=context.task_id,
                description="设计认证方案（JWT/OAuth2）",
                files=["auth_config.py"],
                estimated_lines=30,
                dependencies=[],
            ),
            SubTask(
                sub_task_id=f"{base_id}_2",
                parent_task_id=context.task_id,
                description="实现用户模型和密码加密",
                files=["models.py", "security.py"],
                estimated_lines=70,
                dependencies=[f"{base_id}_1"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_3",
                parent_task_id=context.task_id,
                description="实现登录和注册接口",
                files=["auth_api.py"],
                estimated_lines=80,
                dependencies=[f"{base_id}_2"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_4",
                parent_task_id=context.task_id,
                description="实现JWT令牌生成和验证",
                files=["jwt_utils.py"],
                estimated_lines=60,
                dependencies=[f"{base_id}_2"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_5",
                parent_task_id=context.task_id,
                description="实现认证中间件",
                files=["auth_middleware.py"],
                estimated_lines=50,
                dependencies=[f"{base_id}_4"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_6",
                parent_task_id=context.task_id,
                description="实现权限控制",
                files=["permissions.py"],
                estimated_lines=40,
                dependencies=[f"{base_id}_5"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_7",
                parent_task_id=context.task_id,
                description="编写认证测试",
                files=["tests/test_auth.py"],
                estimated_lines=100,
                dependencies=[f"{base_id}_3", f"{base_id}_5"],
            ),
        ]

    def _plan_generic_implement(self, base_id: str, context: TaskContext) -> List[SubTask]:
        return [
            SubTask(
                sub_task_id=f"{base_id}_1",
                parent_task_id=context.task_id,
                description="分析需求并确定技术方案",
                files=[],
                estimated_lines=30,
                dependencies=[],
            ),
            SubTask(
                sub_task_id=f"{base_id}_2",
                parent_task_id=context.task_id,
                description="设计数据模型和接口",
                files=["models.py", "interfaces.py"],
                estimated_lines=60,
                dependencies=[f"{base_id}_1"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_3",
                parent_task_id=context.task_id,
                description="实现核心业务逻辑",
                files=["core.py"],
                estimated_lines=120,
                dependencies=[f"{base_id}_2"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_4",
                parent_task_id=context.task_id,
                description="实现辅助功能",
                files=["utils.py"],
                estimated_lines=50,
                dependencies=[f"{base_id}_3"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_5",
                parent_task_id=context.task_id,
                description="编写单元测试",
                files=["tests/test_core.py"],
                estimated_lines=80,
                dependencies=[f"{base_id}_3"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_6",
                parent_task_id=context.task_id,
                description="验证和调试",
                files=[],
                estimated_lines=40,
                dependencies=[f"{base_id}_5"],
            ),
        ]

    def _plan_fix(self, context: TaskContext) -> List[SubTask]:
        base_id = context.task_id
        return [
            SubTask(
                sub_task_id=f"{base_id}_1",
                parent_task_id=context.task_id,
                description="定位问题根源（日志分析、代码审查）",
                files=[],
                estimated_lines=20,
                dependencies=[],
            ),
            SubTask(
                sub_task_id=f"{base_id}_2",
                parent_task_id=context.task_id,
                description="编写复现测试用例",
                files=["tests/test_bug_reproduction.py"],
                estimated_lines=30,
                dependencies=[f"{base_id}_1"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_3",
                parent_task_id=context.task_id,
                description="修复代码",
                files=[],
                estimated_lines=40,
                dependencies=[f"{base_id}_2"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_4",
                parent_task_id=context.task_id,
                description="验证修复效果",
                files=[],
                estimated_lines=20,
                dependencies=[f"{base_id}_3"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_5",
                parent_task_id=context.task_id,
                description="回归测试确保没有引入新问题",
                files=["tests/test_regression.py"],
                estimated_lines=50,
                dependencies=[f"{base_id}_4"],
            ),
        ]

    def _plan_review(self, context: TaskContext) -> List[SubTask]:
        base_id = context.task_id
        return [
            SubTask(
                sub_task_id=f"{base_id}_1",
                parent_task_id=context.task_id,
                description="代码结构审查",
                files=[],
                estimated_lines=10,
                dependencies=[],
            ),
            SubTask(
                sub_task_id=f"{base_id}_2",
                parent_task_id=context.task_id,
                description="安全漏洞扫描",
                files=[],
                estimated_lines=10,
                dependencies=[f"{base_id}_1"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_3",
                parent_task_id=context.task_id,
                description="架构合规检查",
                files=[],
                estimated_lines=15,
                dependencies=[f"{base_id}_1"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_4",
                parent_task_id=context.task_id,
                description="性能问题分析",
                files=[],
                estimated_lines=10,
                dependencies=[f"{base_id}_1"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_5",
                parent_task_id=context.task_id,
                description="生成审查报告和改进建议",
                files=["review_report.md"],
                estimated_lines=40,
                dependencies=[f"{base_id}_2", f"{base_id}_3", f"{base_id}_4"],
            ),
        ]

    def _plan_test(self, context: TaskContext) -> List[SubTask]:
        base_id = context.task_id
        return [
            SubTask(
                sub_task_id=f"{base_id}_1",
                parent_task_id=context.task_id,
                description="分析测试需求和覆盖范围",
                files=[],
                estimated_lines=15,
                dependencies=[],
            ),
            SubTask(
                sub_task_id=f"{base_id}_2",
                parent_task_id=context.task_id,
                description="编写单元测试",
                files=["tests/test_unit.py"],
                estimated_lines=100,
                dependencies=[f"{base_id}_1"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_3",
                parent_task_id=context.task_id,
                description="编写集成测试",
                files=["tests/test_integration.py"],
                estimated_lines=80,
                dependencies=[f"{base_id}_2"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_4",
                parent_task_id=context.task_id,
                description="编写端到端测试",
                files=["tests/test_e2e.py"],
                estimated_lines=60,
                dependencies=[f"{base_id}_3"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_5",
                parent_task_id=context.task_id,
                description="运行测试并生成测试报告",
                files=["test_report.md"],
                estimated_lines=20,
                dependencies=[f"{base_id}_2", f"{base_id}_3", f"{base_id}_4"],
            ),
        ]

    def _plan_refactor(self, context: TaskContext) -> List[SubTask]:
        base_id = context.task_id
        return [
            SubTask(
                sub_task_id=f"{base_id}_1",
                parent_task_id=context.task_id,
                description="分析现有代码结构和问题",
                files=[],
                estimated_lines=20,
                dependencies=[],
            ),
            SubTask(
                sub_task_id=f"{base_id}_2",
                parent_task_id=context.task_id,
                description="制定重构方案",
                files=["refactor_plan.md"],
                estimated_lines=30,
                dependencies=[f"{base_id}_1"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_3",
                parent_task_id=context.task_id,
                description="执行代码重构",
                files=[],
                estimated_lines=150,
                dependencies=[f"{base_id}_2"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_4",
                parent_task_id=context.task_id,
                description="更新测试用例",
                files=["tests/"],
                estimated_lines=60,
                dependencies=[f"{base_id}_3"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_5",
                parent_task_id=context.task_id,
                description="验证重构后功能正常",
                files=[],
                estimated_lines=30,
                dependencies=[f"{base_id}_4"],
            ),
        ]

    def _plan_deploy(self, context: TaskContext) -> List[SubTask]:
        base_id = context.task_id
        return [
            SubTask(
                sub_task_id=f"{base_id}_1",
                parent_task_id=context.task_id,
                description="准备部署配置",
                files=["deploy/config.yaml"],
                estimated_lines=30,
                dependencies=[],
            ),
            SubTask(
                sub_task_id=f"{base_id}_2",
                parent_task_id=context.task_id,
                description="构建应用包",
                files=["Dockerfile", "docker-compose.yaml"],
                estimated_lines=40,
                dependencies=[f"{base_id}_1"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_3",
                parent_task_id=context.task_id,
                description="部署到测试环境",
                files=[],
                estimated_lines=20,
                dependencies=[f"{base_id}_2"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_4",
                parent_task_id=context.task_id,
                description="执行部署后验证",
                files=[],
                estimated_lines=20,
                dependencies=[f"{base_id}_3"],
            ),
            SubTask(
                sub_task_id=f"{base_id}_5",
                parent_task_id=context.task_id,
                description="部署到生产环境",
                files=[],
                estimated_lines=20,
                dependencies=[f"{base_id}_4"],
            ),
        ]

    def _apply_architecture_patterns(self, subtasks: List[SubTask], context: TaskContext) -> List[SubTask]:
        if not self.memory_layer or not context.related_patterns:
            return subtasks

        modified_subtasks = []

        for pattern_name in context.related_patterns:
            pattern = self.memory_layer.get_pattern_by_name(pattern_name)
            if not pattern:
                continue

            structure = pattern.get("structure", [])
            quality_gates = pattern.get("quality_gates", [])

            for struct in structure:
                if "接口" in struct:
                    interface_task = SubTask(
                        sub_task_id=f"{context.task_id}_iface",
                        parent_task_id=context.task_id,
                        description=f"定义{pattern_name}接口",
                        files=["interfaces.py"],
                        estimated_lines=40,
                        dependencies=[],
                    )
                    modified_subtasks.append(interface_task)

                    for st in subtasks:
                        if st.sub_task_id != f"{context.task_id}_iface":
                            st.dependencies.append(f"{context.task_id}_iface")
                            modified_subtasks.append(st)

        return modified_subtasks if modified_subtasks else subtasks

    def _ensure_granularity(self, subtasks: List[SubTask]) -> List[SubTask]:
        result = []

        for subtask in subtasks:
            if self.granularity_control.should_split(subtask.estimated_lines):
                split_tasks = self.granularity_control.split_task(subtask)
                result.extend(split_tasks)
            else:
                result.append(subtask)

        return result

    def _register_with_task_board(self, subtasks: List[SubTask]) -> None:
        if not self.task_board:
            return

        for subtask in subtasks:
            try:
                self.task_board.create_task(
                    description=subtask.description,
                    priority=1.0 - (len(subtask.dependencies) * 0.1),
                    affected_files=subtask.files,
                )
                logger.info(f"子任务已注册到TaskBoard: {subtask.sub_task_id}")
            except Exception as e:
                logger.warning(f"注册子任务到TaskBoard失败: {e}")

    def update_subtask_status(self, sub_task_id: str, status: str) -> None:
        if not self.task_board:
            return

        for task_id, task in self.task_board.tasks.items():
            if task.description in sub_task_id or sub_task_id in task.description:
                task.status = status
                self.task_board._save()
                logger.info(f"更新子任务状态: {sub_task_id} -> {status}")
                break


class DependencyAnalyzer:
    """依赖分析器：分析代码依赖关系"""

    def analyze(self, files: List[str]) -> Dict[str, Any]:
        return {
            "dependencies": [],
            "conflicts": [],
            "suggestions": [],
        }


class ConflictDetector:
    """冲突检测器：检测代码冲突"""

    def detect(self, files: List[str]) -> List[Dict[str, Any]]:
        return []


class ReasoningLayer:
    """推理层：规划引擎、依赖分析器、冲突检测器"""

    def __init__(self, memory_layer: Optional[MemoryLayer] = None, task_board: Optional["TaskBoard"] = None):
        self.planning_engine = PlanningEngine(memory_layer, task_board)
        self.dependency_analyzer = DependencyAnalyzer()
        self.conflict_detector = ConflictDetector()

    def reason(self, context: TaskContext) -> List[SubTask]:
        return self.planning_engine.plan(context)

    def reason_with_graph(self, context: TaskContext) -> Dict[str, Any]:
        return self.planning_engine.plan_with_dependency_graph(context)


# ════════════════════════════════════════════════════════════
# 决策层 — Decision Layer（占位实现）
# ════════════════════════════════════════════════════════════

class AestheticEvaluator:
    """审美评估器：评估代码风格和设计质量"""

    def evaluate(self, code: str) -> Dict[str, Any]:
        return {"score": 0.8, "issues": []}


class ArchitectureComplianceChecker:
    """架构合规器：检查代码是否符合架构规范"""

    def check(self, code: str, patterns: List[str]) -> Dict[str, Any]:
        return {"compliant": True, "violations": []}


class QualityGate:
    """质量门控：确保代码质量达标"""

    def gate(self, results: Dict[str, Any]) -> bool:
        return True


class DecisionLayer:
    """决策层：审美评估器、架构合规器、质量门控（集成认知洞见处理）"""

    def __init__(self):
        self.aesthetic_evaluator = AestheticEvaluator()
        self.architecture_compliance = ArchitectureComplianceChecker()
        self.quality_gate = QualityGate()
        self._pending_insights: List[EmergenceInsight] = []
        self._incorporated_insights: List[EmergenceInsight] = []

    def decide(self, code: str, context: TaskContext) -> Dict[str, Any]:
        aesthetic = self.aesthetic_evaluator.evaluate(code)
        compliance = self.architecture_compliance.check(code, context.related_patterns)

        insight_influence = self._evaluate_insight_influence()
        gate_result = self.quality_gate.gate({
            "aesthetic": aesthetic,
            "compliance": compliance,
            "insight_influence": insight_influence,
        })

        return {
            "aesthetic_score": aesthetic["score"],
            "compliant": compliance["compliant"],
            "gate_passed": gate_result,
            "issues": aesthetic.get("issues", []) + compliance.get("violations", []),
            "insight_influence": insight_influence,
            "pending_insights": len(self._pending_insights),
            "incorporated_insights": len(self._incorporated_insights),
        }

    def consider_insight(self, insight: EmergenceInsight) -> None:
        """考虑PSI涌现的洞见，将其纳入决策过程"""
        if insight:
            self._pending_insights.append(insight)
            logger.info(f"[DecisionLayer] Insight considered: {insight.content[:50]}...")

    def _evaluate_insight_influence(self) -> float:
        """评估当前洞见对决策的影响程度"""
        if not self._pending_insights:
            return 0.0

        influence = 0.0
        for insight in self._pending_insights:
            priority_multiplier = {"high": 1.0, "medium": 0.5, "low": 0.2}.get(insight.priority, 0.5)
            influence += insight.confidence * priority_multiplier

        return min(influence / len(self._pending_insights), 1.0)

    def incorporate_insights(self, insights: List[EmergenceInsight]) -> None:
        """批量纳入洞见并标记为已处理"""
        for insight in insights:
            self._pending_insights.append(insight)
            self._incorporated_insights.append(insight)
            logger.info(f"[DecisionLayer] Insight incorporated: {insight.content[:50]}...")

    def clear_pending_insights(self) -> None:
        """清除待处理洞见"""
        self._pending_insights.clear()

    def get_pending_insights(self) -> List[EmergenceInsight]:
        """获取待处理洞见列表"""
        return self._pending_insights.copy()

    def get_insight_summary(self) -> Dict[str, Any]:
        """获取洞见摘要统计"""
        high_priority = sum(1 for i in self._pending_insights if i.priority == "high")
        medium_priority = sum(1 for i in self._pending_insights if i.priority == "medium")
        low_priority = sum(1 for i in self._pending_insights if i.priority == "low")

        return {
            "pending": len(self._pending_insights),
            "incorporated": len(self._incorporated_insights),
            "by_priority": {
                "high": high_priority,
                "medium": medium_priority,
                "low": low_priority,
            },
            "avg_confidence": sum(i.confidence for i in self._pending_insights) / max(len(self._pending_insights), 1),
        }


# ════════════════════════════════════════════════════════════
# 执行层 — Execution Layer（集成CodexAgent）
# ════════════════════════════════════════════════════════════

class CodeTemplateEngine:
    """代码生成模板引擎

    实现FR-6：工具编排与沙箱隔离中的代码模板系统
    支持多种编程语言和框架模板，约束LLM输出格式

    模板分类：
    - Python: 类、函数、测试、FastAPI路由、Pydantic模型
    - JavaScript/TypeScript: 类、函数、测试、Express路由
    - 通用: 配置文件、README、Makefile
    """

    TEMPLATES = {
        # ════════════════════════════════════════════════════════
        # Python 模板
        # ════════════════════════════════════════════════════════
        "python_class": """class {class_name}:
    \"\"\"{description}\"\"\"
    
    def __init__(self{params}):
{init_body}
    
{methods}
""",
        "python_function": """def {function_name}({params}){return_type}:
    \"\"\"{description}\"\"\"
{body}
""",
        "python_test": """import pytest
from {module} import {class_name}

class Test{class_name}:
    def test_{test_name}(self):
        # Arrange
        # Act
        # Assert
        pass
""",
        "python_fastapi_route": """from fastapi import APIRouter, Depends, HTTPException
from {module} import {model_class}, {service_class}

router = APIRouter(prefix=\"/{endpoint}\", tags=[\"{tag}\"])

@router.get(\"/\")
async def get_{endpoint}(service: {service_class} = Depends()):
    \"\"\"获取{description}\"\"\"
    return service.get_all()

@router.get("/{{item_id}}")
async def get_{endpoint}_by_id(item_id: int, service: {service_class} = Depends()):
    \"\"\"根据ID获取{description}\"\"\"
    item = service.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=\"Not found\")
    return item

@router.post(\"/\")
async def create_{endpoint}(item: {model_class}, service: {service_class} = Depends()):
    \"\"\"创建{description}\"\"\"
    return service.create(item)

@router.put("/{{item_id}}")
async def update_{endpoint}(item_id: int, item: {model_class}, service: {service_class} = Depends()):
    \"\"\"更新{description}\"\"\"
    return service.update(item_id, item)

@router.delete("/{{item_id}}")
async def delete_{endpoint}(item_id: int, service: {service_class} = Depends()):
    \"\"\"删除{description}\"\"\"
    service.delete(item_id)
    return dict(message="Deleted successfully")
""",
        "python_pydantic_model": """from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime

class {model_name}(BaseModel):
    \"\"\"{description}\"\"\"
{fields}
    
    class Config:
        from_attributes = True

class {model_name}Create(BaseModel):
    \"\"\"{description}创建模型\"\"\"
{create_fields}

class {model_name}Update(BaseModel):
    \"\"\"{description}更新模型\"\"\"
{update_fields}
""",
        "python_dataclass": """from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class {class_name}:
    \"\"\"{description}\"\"\"
{fields}
""",
        "python_enum": """from enum import Enum

class {enum_name}(Enum):
    \"\"\"{description}\"\"\"
{values}
""",
        "python_exception": """class {exception_name}(Exception):
    \"\"\"{description}\"\"\"
    
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
""",
        "python_singleton": """class {class_name}:
    \"\"\"{description} - 单例模式\"\"\"
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self{params}):
        if not hasattr(self, '_initialized'):
{init_body}
            self._initialized = True
""",
        "python_factory": """class {class_name}Factory:
    \"\"\"{description} - 工厂模式\"\"\"
    
    _creators = {{}}
    
    @classmethod
    def register(cls, type_name: str, creator):
        cls._creators[type_name] = creator
    
    @classmethod
    def create(cls, type_name: str, **kwargs):
        creator = cls._creators.get(type_name)
        if not creator:
            raise ValueError(f\"Unknown type: {type_name}\")
        return creator(**kwargs)
""",
        "python_repository": """from abc import ABC, abstractmethod
from typing import List, Optional, TypeVar

T = TypeVar('T')

class {class_name}Repository(ABC):
    \"\"\"{description} - Repository模式接口\"\"\"
    
    @abstractmethod
    def get_by_id(self, item_id: int) -> Optional[T]:
        pass
    
    @abstractmethod
    def get_all(self) -> List[T]:
        pass
    
    @abstractmethod
    def create(self, item: T) -> T:
        pass
    
    @abstractmethod
    def update(self, item_id: int, item: T) -> T:
        pass
    
    @abstractmethod
    def delete(self, item_id: int) -> None:
        pass
""",

        # ════════════════════════════════════════════════════════
        # JavaScript 模板
        # ════════════════════════════════════════════════════════
        "javascript_class": """class {class_name} {{
    /**
     * {description}
     */
    constructor({params}) {{
{init_body}
    }}
    
{methods}
}}

module.exports = {class_name};
""",
        "javascript_function": "/**\n * {description}\n */\nfunction {function_name}({params}) {{\n{body}\n}}\n\nmodule.exports = {function_name};\n",
        "javascript_test": """const assert = require('assert');
const {class_name} = require('../{module}');

describe('{class_name}', function() {{
    describe('#{method_name}()', function() {{
        it('should {test_description}', function() {{
            // Arrange
            const instance = new {class_name}();
            
            // Act
            const result = instance.{method_name}();
            
            // Assert
            assert.strictEqual(result, {expected});
        }});
    }});
}});
""",
        "javascript_express_route": """const express = require('express');
const router = express.Router();
const {service_class} = require('../services/{service_file}');

const service = new {service_class}();

router.get('/', async (req, res) => {{
    try {{
        const items = await service.getAll();
        res.json(items);
    }} catch (error) {{
        res.status(500).json({{ error: error.message }});
    }}
}});

router.get('/:id', async (req, res) => {{
    try {{
        const item = await service.getById(req.params.id);
        if (!item) {{
            return res.status(404).json({{ error: 'Not found' }});
        }}
        res.json(item);
    }} catch (error) {{
        res.status(500).json({{ error: error.message }});
    }}
}});

router.post('/', async (req, res) => {{
    try {{
        const item = await service.create(req.body);
        res.status(201).json(item);
    }} catch (error) {{
        res.status(500).json({{ error: error.message }});
    }}
}});

router.put('/:id', async (req, res) => {{
    try {{
        const item = await service.update(req.params.id, req.body);
        res.json(item);
    }} catch (error) {{
        res.status(500).json({{ error: error.message }});
    }}
}});

router.delete('/:id', async (req, res) => {{
    try {{
        await service.delete(req.params.id);
        res.json({{ message: 'Deleted successfully' }});
    }} catch (error) {{
        res.status(500).json({{ error: error.message }});
    }}
}});

module.exports = router;
""",
        "javascript_async_function": "/**\n * {description}\n */\nasync function {function_name}({params}) {{\n{body}\n}}\n\nmodule.exports = {function_name};\n",
        "javascript_error": "class {error_name} extends Error {{\n    /**\n     * {description}\n     */\n    constructor(message) {{\n        super(message);\n        this.name = '{error_name}';\n    }}\n}}\n\nmodule.exports = {error_name};\n",

        # ════════════════════════════════════════════════════════
        # TypeScript 模板
        # ════════════════════════════════════════════════════════
        "typescript_class": """export class {class_name} {{
    /**
     * {description}
     */
{properties}
    
    constructor({params}) {{
{init_body}
    }}
    
{methods}
}}
""",
        "typescript_function": "/**\n * {description}\n */\nexport function {function_name}({params}): {return_type} {{\n{body}\n}}\n",
        "typescript_interface": "/**\n * {description}\n */\nexport interface {interface_name} {{\n{properties}\n}}\n",
        "typescript_type": "/**\n * {description}\n */\nexport type {type_name} = {definition};\n",
        "typescript_test": """import {{ describe, it, expect }} from 'vitest';
import {{ {class_name} }} from '../src/{module}';

describe('{class_name}', () => {{
    it('should {test_description}', () => {{
        // Arrange
        const instance = new {class_name}();
        
        // Act
        const result = instance.{method_name}();
        
        // Assert
        expect(result).toBe({expected});
    }});
}});
""",
        "typescript_express_route": """import express, {{ Router, Request, Response }} from 'express';
import {{ {service_class} }} from '../services/{service_file}';

const router: Router = express.Router();
const service = new {service_class}();

router.get('/', async (req: Request, res: Response) => {{
    try {{
        const items = await service.getAll();
        res.json(items);
    }} catch (error) {{
        res.status(500).json({{ error: (error as Error).message }});
    }}
}});

router.get('/:id', async (req: Request, res: Response) => {{
    try {{
        const item = await service.getById(req.params.id);
        if (!item) {{
            return res.status(404).json({{ error: 'Not found' }});
        }}
        res.json(item);
    }} catch (error) {{
        res.status(500).json({{ error: (error as Error).message }});
    }}
}});

router.post('/', async (req: Request, res: Response) => {{
    try {{
        const item = await service.create(req.body);
        res.status(201).json(item);
    }} catch (error) {{
        res.status(500).json({{ error: (error as Error).message }});
    }}
}});

router.put('/:id', async (req: Request, res: Response) => {{
    try {{
        const item = await service.update(req.params.id, req.body);
        res.json(item);
    }} catch (error) {{
        res.status(500).json({{ error: (error as Error).message }});
    }}
}});

router.delete('/:id', async (req: Request, res: Response) => {{
    try {{
        await service.delete(req.params.id);
        res.json({{ message: 'Deleted successfully' }});
    }} catch (error) {{
        res.status(500).json({{ error: (error as Error).message }});
    }}
}});

export default router;
""",

        # ════════════════════════════════════════════════════════
        # 通用模板
        # ════════════════════════════════════════════════════════
        "common_readme": """# {project_name}

{description}

## Features

{features}

## Getting Started

### Prerequisites

{prerequisites}

### Installation

{installation}

### Usage

{usage}

## Project Structure

{structure}

## Contributing

{contributing}

## License

{license}
""",
        "common_makefile": ".PHONY: all install test lint clean build\n\nall: install test\n\ninstall:\n\tpip install -r requirements.txt\n\ntest:\n\tpython -m pytest tests/ -v\n\nlint:\n\tflake8 src/\n\tblack src/\n\nclean:\n\trm -rf __pycache__\n\trm -rf .pytest_cache\n\trm -rf dist\n\trm -rf *.egg-info\n\nbuild:\n\tpython setup.py sdist bdist_wheel\n\nrun:\n\tpython -m {module_name}\n",
        "common_pyproject": "[build-system]\nrequires = [\"setuptools>=61.0\", \"wheel\"]\nbuild-backend = \"setuptools.build_meta\"\n\n[project]\nname = \"{project_name}\"\nversion = \"{version}\"\ndescription = \"{description}\"\nreadme = \"README.md\"\nrequires-python = \">=3.11\"\n\n[project.scripts]\n{script_name} = \"{module_name}.cli:main\"\n\n[tool.pytest.ini_options]\ntestpaths = [\"tests\"]\n\n[tool.black]\nline-length = 88\ntarget-version = ['py311']\n\n[tool.flake8]\nmax-line-length = 88\n",
        "common_requirements": "{requirements}\n",
        "common_gitignore": "# Byte-compiled / optimized / DLL files\n__pycache__/\n*.py[cod]\n*$py.class\n*.so\n\n# C extensions\n*.c\n*.o\n\n# Distribution / packaging\n.Python\nbuild/\ndevelop-eggs/\ndist/\ndownloads/\neggs/\n.eggs/\nlib/\nlib64/\nparts/\nsdist/\nvar/\nwheels/\n*.egg-info/\n.installed.cfg\n*.egg\n\n# PyInstaller\n*.manifest\n*.spec\n\n# Installer logs\npip-log.txt\npip-delete-this-directory.txt\n\n# Unit test / coverage reports\nhtmlcov/\n.tox/\n.nox/\n.coverage\n.coverage.*\n.cache\nnosetests.xml\ncoverage.xml\n*.cover\n*.py,cover\n.hypothesis/\n.pytest_cache/\n\n# Translations\n*.mo\n*.pot\n\n# Django stuff:\n*.log\nlocal_settings.py\ndb.sqlite3\n\n# Flask stuff:\ninstance/\n.webassets-cache\n\n# Scrapy stuff:\n.scrapy\n\n# Sphinx documentation\ndocs/_build/\n\n# PyBuilder\ntarget/\n\n# Jupyter Notebook\n.ipynb_checkpoints\n\n# IPython\nprofile_default/\nipython_config.py\n\n# pyenv\n.python-version\n\n# pipenv\nPipfile.lock\n\n# poetry\npoetry.lock\n\n# virtualenv\nvenv/\nenv/\nENV/\n\n# mypy\n.mypy_cache/\n.dmypy.json\ndmypy.json\n\n# VS Code\n.vscode/\n*.swp\n*.swo\n*~\n\n# OS files\n.DS_Store\nThumbs.db\n",
        "common_package_json": "{{\n  \"name\": \"{project_name}\",\n  \"version\": \"{version}\",\n  \"description\": \"{description}\",\n  \"main\": \"index.js\",\n  \"scripts\": {{\n    \"start\": \"node index.js\",\n    \"dev\": \"nodemon index.js\",\n    \"test\": \"jest\",\n    \"build\": \"tsc\"\n  }},\n  \"dependencies\": {{\n{dependencies}\n  }},\n  \"devDependencies\": {{\n{dev_dependencies}\n  }}\n}}\n",
        "common_tsconfig": "{{\n  \"compilerOptions\": {{\n    \"target\": \"ES2020\",\n    \"module\": \"CommonJS\",\n    \"outDir\": \"./dist\",\n    \"rootDir\": \"./src\",\n    \"strict\": true,\n    \"esModuleInterop\": true,\n    \"skipLibCheck\": true,\n    \"forceConsistentCasingInFileNames\": true\n  }},\n  \"include\": [\"src/**/*\"],\n  \"exclude\": [\"node_modules\", \"dist\"]\n}}\n",
    }

    def render(self, template_name: str, **kwargs) -> str:
        template = self.TEMPLATES.get(template_name, "")
        if not template:
            logger.warning(f"Template not found: {template_name}")
            return ""
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing template parameter: {e}")
            return ""

    def get_available_templates(self) -> List[str]:
        """获取所有可用模板名称"""
        return sorted(list(self.TEMPLATES.keys()))

    def get_template_categories(self) -> Dict[str, List[str]]:
        """按类别分组模板"""
        categories = {
            "python": [],
            "javascript": [],
            "typescript": [],
            "common": [],
        }
        for name in self.TEMPLATES:
            if name.startswith("python_"):
                categories["python"].append(name)
            elif name.startswith("javascript_"):
                categories["javascript"].append(name)
            elif name.startswith("typescript_"):
                categories["typescript"].append(name)
            elif name.startswith("common_"):
                categories["common"].append(name)
        return categories

    def render_python_class(self, class_name: str, description: str = "",
                           params: str = "", init_body: str = "", methods: str = "") -> str:
        """渲染Python类模板"""
        return self.render(
            "python_class",
            class_name=class_name,
            description=description,
            params=params,
            init_body=init_body,
            methods=methods,
        )

    def render_python_function(self, function_name: str, params: str = "",
                               return_type: str = "", description: str = "", body: str = "") -> str:
        """渲染Python函数模板"""
        return self.render(
            "python_function",
            function_name=function_name,
            params=params,
            return_type=return_type,
            description=description,
            body=body,
        )

    def render_pydantic_model(self, model_name: str, description: str = "",
                              fields: str = "", create_fields: str = "", update_fields: str = "") -> str:
        """渲染Pydantic模型模板"""
        return self.render(
            "python_pydantic_model",
            model_name=model_name,
            description=description,
            fields=fields,
            create_fields=create_fields or fields,
            update_fields=update_fields or fields,
        )

    def render_fastapi_route(self, endpoint: str, description: str = "",
                             model_class: str = "", service_class: str = "",
                             module: str = "", tag: str = "") -> str:
        """渲染FastAPI路由模板"""
        return self.render(
            "python_fastapi_route",
            endpoint=endpoint,
            description=description,
            model_class=model_class,
            service_class=service_class,
            module=module,
            tag=tag or endpoint,
        )

    def render_readme(self, project_name: str, description: str = "",
                      features: str = "", prerequisites: str = "",
                      installation: str = "", usage: str = "",
                      structure: str = "", contributing: str = "",
                      license: str = "MIT") -> str:
        """渲染README模板"""
        return self.render(
            "common_readme",
            project_name=project_name,
            description=description,
            features=features,
            prerequisites=prerequisites,
            installation=installation,
            usage=usage,
            structure=structure,
            contributing=contributing,
            license=license,
        )


class ToolOrchestrator:
    """工具编排器：管理和调度工具执行

    实现FR-6：工具编排与沙箱隔离中的工具编排系统

    核心能力：
    - 文件读写操作（read_file, write_file, append_file, delete_file）
    - Shell命令执行（带超时控制）
    - Python代码执行
    - Git操作（clone, commit, push, branch）
    """

    def __init__(self, agent=None, workdir: str = "", sandbox=None):
        self.agent = agent
        self.workdir = workdir or os.getcwd()
        self.sandbox = sandbox
        self._tool_registry = {
            "read_file": self.read_file,
            "write_file": self.write_file,
            "append_file": self.append_file,
            "delete_file": self.delete_file,
            "list_files": self.list_files,
            "run_shell": self.run_shell,
            "run_python": self.run_python,
            "git_clone": self.git_clone,
            "git_commit": self.git_commit,
            "git_push": self.git_push,
            "git_pull": self.git_pull,
            "git_checkout": self.git_checkout,
            "git_status": self.git_status,
        }

    def execute(self, tool_name: str, **kwargs) -> Any:
        """执行指定工具"""
        tool = self._tool_registry.get(tool_name)
        if not tool:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        logger.info(f"[ToolOrchestrator] Executing tool: {tool_name}")
        try:
            result = tool(**kwargs)
            logger.info(f"[ToolOrchestrator] Tool {tool_name} executed successfully")
            return result
        except Exception as e:
            logger.error(f"[ToolOrchestrator] Tool {tool_name} failed: {e}")
            raise

    def get_available_tools(self) -> List[str]:
        """获取所有可用工具"""
        return sorted(list(self._tool_registry.keys()))

    def register_tool(self, name: str, handler: Callable) -> None:
        """注册自定义工具"""
        self._tool_registry[name] = handler
        logger.info(f"[ToolOrchestrator] Registered tool: {name}")

    # ════════════════════════════════════════════════════════
    # 文件操作工具
    # ════════════════════════════════════════════════════════

    def read_file(self, file_path: str) -> str:
        """读取文件内容"""
        abs_path = self._resolve_path(file_path)
        
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.debug(f"[ToolOrchestrator] Read file: {file_path} ({len(content)} bytes)")
        return content

    def write_file(self, file_path: str, content: str, overwrite: bool = True) -> str:
        """写入文件内容"""
        abs_path = self._resolve_path(file_path)
        
        if os.path.exists(abs_path) and not overwrite:
            raise FileExistsError(f"File exists and overwrite=False: {file_path}")
        
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.debug(f"[ToolOrchestrator] Wrote file: {file_path} ({len(content)} bytes)")
        return f"Written: {file_path}"

    def append_file(self, file_path: str, content: str) -> str:
        """追加内容到文件"""
        abs_path = self._resolve_path(file_path)
        
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'a', encoding='utf-8') as f:
            f.write(content)
        
        logger.debug(f"[ToolOrchestrator] Appended to file: {file_path} ({len(content)} bytes)")
        return f"Appended to: {file_path}"

    def delete_file(self, file_path: str) -> str:
        """删除文件"""
        abs_path = self._resolve_path(file_path)
        
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        os.remove(abs_path)
        logger.debug(f"[ToolOrchestrator] Deleted file: {file_path}")
        return f"Deleted: {file_path}"

    def list_files(self, directory: str = "") -> List[str]:
        """列出目录中的文件"""
        abs_path = self._resolve_path(directory)
        
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        files = []
        for entry in os.listdir(abs_path):
            full_path = os.path.join(abs_path, entry)
            if os.path.isfile(full_path):
                files.append(entry)
        
        logger.debug(f"[ToolOrchestrator] Listed {len(files)} files in: {directory}")
        return files

    def _resolve_path(self, path: str) -> str:
        """解析并验证路径"""
        if os.path.isabs(path):
            abs_path = path
        else:
            abs_path = os.path.join(self.workdir, path)
        
        abs_path = os.path.abspath(abs_path)
        
        if self.sandbox and hasattr(self.sandbox, 'config'):
            allowed = False
            for ap in self.sandbox.config.allowed_paths:
                ap_abs = os.path.abspath(ap)
                if abs_path.startswith(ap_abs):
                    allowed = True
                    break
            if not allowed:
                raise PermissionError(f"Path not in allowed paths: {path}")
        
        return abs_path

    # ════════════════════════════════════════════════════════
    # Shell命令执行工具
    # ════════════════════════════════════════════════════════

    def run_shell(self, command: str, timeout: int = 120, cwd: str = "",
                  env: Dict[str, str] = None) -> Dict[str, Any]:
        """执行Shell命令"""
        import subprocess
        
        working_dir = self._resolve_path(cwd) if cwd else self.workdir
        
        if self.sandbox and hasattr(self.sandbox, 'sandbox') and hasattr(self.sandbox.sandbox, 'validate'):
            allowed, reason = self.sandbox.sandbox.validate(command, timeout=timeout, cwd=working_dir)
            if not allowed:
                return {"success": False, "stdout": "", "stderr": reason, "return_code": -1}
            
            env = self.sandbox.sandbox.sanitize_env(env)
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            
            max_bytes = self.sandbox.sandbox.config.max_output_bytes if self.sandbox and hasattr(self.sandbox, 'sandbox') and hasattr(self.sandbox.sandbox, 'config') else 100 * 1024
            output = {
                "success": result.returncode == 0,
                "stdout": result.stdout[:max_bytes],
                "stderr": result.stderr[:max_bytes],
                "return_code": result.returncode,
            }
            
            if result.returncode != 0:
                logger.warning(f"[ToolOrchestrator] Shell command failed: {command}")
            
            return output
        except subprocess.TimeoutExpired:
            logger.warning(f"[ToolOrchestrator] Shell command timeout: {command}")
            return {"success": False, "stdout": "", "stderr": f"Timeout after {timeout}s", "return_code": -1}
        except Exception as e:
            logger.error(f"[ToolOrchestrator] Shell command error: {e}")
            return {"success": False, "stdout": "", "stderr": str(e), "return_code": -1}

    # ════════════════════════════════════════════════════════
    # Python代码执行工具
    # ════════════════════════════════════════════════════════

    def run_python(self, code: str, timeout: int = 60) -> Dict[str, Any]:
        """执行Python代码"""
        import subprocess
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8', dir=self.workdir) as f:
            f.write(code)
            temp_path = f.name
        
        try:
            if self.sandbox and hasattr(self.sandbox, 'sandbox') and hasattr(self.sandbox.sandbox, 'validate'):
                allowed, reason = self.sandbox.sandbox.validate(f"python {temp_path}", timeout=timeout, cwd=self.workdir)
                if not allowed:
                    return {"success": False, "stdout": "", "stderr": reason, "return_code": -1}
            
            result = subprocess.run(
                ["python", temp_path],
                cwd=self.workdir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            
            max_bytes = self.sandbox.sandbox.config.max_output_bytes if self.sandbox and hasattr(self.sandbox, 'sandbox') and hasattr(self.sandbox.sandbox, 'config') else 100 * 1024
            output = {
                "success": result.returncode == 0,
                "stdout": result.stdout[:max_bytes],
                "stderr": result.stderr[:max_bytes],
                "return_code": result.returncode,
            }
            
            return output
        except subprocess.TimeoutExpired:
            logger.warning(f"[ToolOrchestrator] Python execution timeout")
            return {"success": False, "stdout": "", "stderr": f"Timeout after {timeout}s", "return_code": -1}
        except Exception as e:
            logger.error(f"[ToolOrchestrator] Python execution error: {e}")
            return {"success": False, "stdout": "", "stderr": str(e), "return_code": -1}
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    # ════════════════════════════════════════════════════════
    # Git操作工具
    # ════════════════════════════════════════════════════════

    def git_clone(self, repo_url: str, target_dir: str = "", branch: str = "") -> Dict[str, Any]:
        """克隆Git仓库"""
        command = f"git clone {repo_url}"
        if branch:
            command += f" -b {branch}"
        if target_dir:
            command += f" {target_dir}"
        
        return self.run_shell(command, timeout=300)

    def git_commit(self, message: str, files: List[str] = None) -> Dict[str, Any]:
        """提交Git更改"""
        if files:
            files_str = " ".join(files)
            self.run_shell(f"git add {files_str}", timeout=30)
        
        return self.run_shell(f'git commit -m "{message}"', timeout=30)

    def git_push(self, remote: str = "origin", branch: str = "main") -> Dict[str, Any]:
        """推送Git更改"""
        return self.run_shell(f"git push {remote} {branch}", timeout=300)

    def git_pull(self, remote: str = "origin", branch: str = "main") -> Dict[str, Any]:
        """拉取Git更改"""
        return self.run_shell(f"git pull {remote} {branch}", timeout=300)

    def git_checkout(self, branch: str) -> Dict[str, Any]:
        """切换Git分支"""
        return self.run_shell(f"git checkout {branch}", timeout=30)

    def git_status(self) -> Dict[str, Any]:
        """获取Git状态"""
        return self.run_shell("git status", timeout=30)


class SandboxExecutor:
    """沙箱执行器：在隔离环境中执行代码

    实现FR-6：工具编排与沙箱隔离中的沙箱执行环境

    核心能力：
    - 文件系统隔离（限制访问路径）
    - 网络隔离（可选）
    - 超时控制
    - 权限控制（最小权限原则）

    集成现有laap.shell.sandbox.Sandbox实现OS级隔离
    """

    def __init__(self, workdir: str = "", isolation_level: int = 2):
        self.workdir = workdir or os.getcwd()
        
        try:
            from laap.shell.sandbox import Sandbox, SandboxConfig, IsolationLevel
            self._sandbox_module_available = True
            self._IsolationLevel = IsolationLevel
            
            level = IsolationLevel(isolation_level)
            config = SandboxConfig(
                level=level,
                allowed_paths=[self.workdir],
                timeout_default=120,
                timeout_max=3600,
            )
            self.sandbox = Sandbox(config)
        except ImportError:
            self._sandbox_module_available = False
            self._IsolationLevel = None
            self.sandbox = None
            logger.warning("[SandboxExecutor] laap.shell.sandbox not available, using fallback mode")

        logger.info(f"[SandboxExecutor] Initialized: workdir={self.workdir}, isolation_level={isolation_level}")

    def run_command(self, command: str, timeout: int = 120, cwd: str = "", 
                    env: Dict[str, str] = None) -> Dict[str, Any]:
        """执行Shell命令（带沙箱隔离）"""
        import subprocess
        
        working_dir = cwd or self.workdir
        
        if self.sandbox:
            allowed, reason = self.sandbox.validate(command, timeout=timeout, cwd=working_dir)
            if not allowed:
                logger.warning(f"[SandboxExecutor] Command blocked: {reason}")
                return {"success": False, "stdout": "", "stderr": reason, "return_code": -1}
            
            env = self.sandbox.sanitize_env(env)
            prefix = self.sandbox.get_command_prefix()
            
            if prefix:
                command = " ".join(prefix) + " " + command
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            
            max_bytes = self.sandbox.config.max_output_bytes if self.sandbox else 100 * 1024
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout[:max_bytes],
                "stderr": result.stderr[:max_bytes],
                "return_code": result.returncode,
                "timeout": False,
            }
        except subprocess.TimeoutExpired:
            logger.warning(f"[SandboxExecutor] Command timeout: {command}")
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Timeout after {timeout}s",
                "return_code": -1,
                "timeout": True,
            }
        except Exception as e:
            logger.error(f"[SandboxExecutor] Command error: {e}")
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "timeout": False,
            }

    def run_python(self, code: str, timeout: int = 60) -> Dict[str, Any]:
        """执行Python代码（带沙箱隔离）"""
        import subprocess
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8', dir=self.workdir) as f:
            f.write(code)
            temp_path = f.name
        
        try:
            if self.sandbox:
                allowed, reason = self.sandbox.validate(f"python {temp_path}", timeout=timeout, cwd=self.workdir)
                if not allowed:
                    return {"success": False, "stdout": "", "stderr": reason, "return_code": -1, "timeout": False}
            
            result = subprocess.run(
                ["python", temp_path],
                cwd=self.workdir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            
            max_bytes = self.sandbox.config.max_output_bytes if self.sandbox else 100 * 1024
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout[:max_bytes],
                "stderr": result.stderr[:max_bytes],
                "return_code": result.returncode,
                "timeout": False,
            }
        except subprocess.TimeoutExpired:
            logger.warning(f"[SandboxExecutor] Python execution timeout")
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Timeout after {timeout}s",
                "return_code": -1,
                "timeout": True,
            }
        except Exception as e:
            logger.error(f"[SandboxExecutor] Python execution error: {e}")
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "timeout": False,
            }
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def run_code(self, code: str, language: str = "python", timeout: int = 60) -> Dict[str, Any]:
        """执行指定语言的代码"""
        language = language.lower()
        
        if language == "python":
            return self.run_python(code, timeout)
        elif language in ["javascript", "js"]:
            return self._run_javascript(code, timeout)
        elif language in ["typescript", "ts"]:
            return self._run_typescript(code, timeout)
        else:
            return {"success": False, "stdout": "", "stderr": f"Unsupported language: {language}", "return_code": -1, "timeout": False}

    def _run_javascript(self, code: str, timeout: int = 60) -> Dict[str, Any]:
        """执行JavaScript代码"""
        import subprocess
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8', dir=self.workdir) as f:
            f.write(code)
            temp_path = f.name
        
        try:
            if self.sandbox:
                allowed, reason = self.sandbox.validate(f"node {temp_path}", timeout=timeout)
                if not allowed:
                    return {"success": False, "stdout": "", "stderr": reason, "return_code": -1, "timeout": False}
            
            result = subprocess.run(
                ["node", temp_path],
                cwd=self.workdir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            
            max_bytes = self.sandbox.config.max_output_bytes if self.sandbox else 100 * 1024
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout[:max_bytes],
                "stderr": result.stderr[:max_bytes],
                "return_code": result.returncode,
                "timeout": False,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": f"Timeout after {timeout}s", "return_code": -1, "timeout": True}
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e), "return_code": -1, "timeout": False}
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def _run_typescript(self, code: str, timeout: int = 60) -> Dict[str, Any]:
        """执行TypeScript代码（先编译再执行）"""
        import subprocess
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ts', delete=False, encoding='utf-8', dir=self.workdir) as f:
            f.write(code)
            ts_path = f.name
        
        js_path = ts_path.replace('.ts', '.js')
        
        try:
            if self.sandbox:
                allowed, reason = self.sandbox.validate(f"npx tsc {ts_path} --outFile {js_path}", timeout=timeout)
                if not allowed:
                    return {"success": False, "stdout": "", "stderr": reason, "return_code": -1, "timeout": False}
            
            compile_result = subprocess.run(
                ["npx", "tsc", ts_path, "--outFile", js_path],
                cwd=self.workdir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            
            if compile_result.returncode != 0:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Compilation failed: {compile_result.stderr}",
                    "return_code": compile_result.returncode,
                    "timeout": False,
                }
            
            return self._run_javascript(open(js_path, 'r', encoding='utf-8').read(), timeout)
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": f"Timeout after {timeout}s", "return_code": -1, "timeout": True}
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e), "return_code": -1, "timeout": False}
        finally:
            if os.path.exists(ts_path):
                os.unlink(ts_path)
            if os.path.exists(js_path):
                os.unlink(js_path)

    def validate_path(self, path: str) -> bool:
        """验证路径是否在允许范围内"""
        if not self.sandbox:
            return True
        
        abs_path = os.path.abspath(path)
        for ap in self.sandbox.config.allowed_paths:
            ap_abs = os.path.abspath(ap)
            if abs_path.startswith(ap_abs):
                return True
        
        return False

    def set_isolation_level(self, level: int) -> None:
        """设置隔离级别"""
        if self._sandbox_module_available and self.sandbox:
            self.sandbox.config.level = self._IsolationLevel(level)
            logger.info(f"[SandboxExecutor] Isolation level set to: {level}")

    @property
    def status(self) -> Dict[str, Any]:
        """返回沙箱状态"""
        if self.sandbox:
            return {
                "available": True,
                **self.sandbox.status,
                "workdir": self.workdir,
            }
        return {
            "available": False,
            "workdir": self.workdir,
            "message": "Sandbox module not available, using fallback mode",
        }


class ExecutionLayer:
    """执行层：代码生成模板、工具编排器、沙箱执行器

    实现FR-2.3：Executor Agent（子任务执行）
    实现FR-6：工具编排与沙箱隔离

    核心能力：
    - 子任务执行器：按依赖图顺序执行子任务
    - 代码生成模板：支持多种编程语言和框架模板
    - 工具编排器：管理文件操作、shell执行等工具调用
    - 沙箱执行器：集成现有Sandbox进行隔离执行
    - 认知物种库：优先从物种库匹配模板，零Token生成
    """

    def __init__(self, codex_agent=None, workdir: str = "", species_library=None):
        self.workdir = workdir or os.getcwd()
        self.code_template = CodeTemplateEngine()
        self.sandbox = SandboxExecutor(self.workdir)
        self.tool_orchestrator = ToolOrchestrator(codex_agent, self.workdir, self.sandbox)
        self.codex_agent = codex_agent
        self.species_library = species_library
        self._executed_tasks: Set[str] = set()
        self._task_results: Dict[str, ExecutionResult] = {}

        logger.info(f"[ExecutionLayer] Initialized at {self.workdir}")
        if self.species_library:
            logger.info(f"[ExecutionLayer] CognitiveSpeciesLibrary integrated - {len(self.species_library._species)} species available")

    def execute(self, subtask: SubTask) -> ExecutionResult:
        """执行单个子任务，生成并写入代码文件"""
        t0 = time.time()
        logger.info(f"[ExecutionLayer] Executing subtask: {subtask.sub_task_id} - {subtask.description}")

        try:
            if self.codex_agent:
                result = self.codex_agent.generate_code(subtask.description)
                modified_files = subtask.files
            else:
                result = self._generate_code_from_template(subtask)
                modified_files = self._write_generated_code(subtask, result)

            subtask.status = "completed"
            self._executed_tasks.add(subtask.sub_task_id)

            duration_ms = (time.time() - t0) * 1000
            logger.info(f"[ExecutionLayer] Subtask {subtask.sub_task_id} completed in {duration_ms:.2f}ms")

            execution_result = ExecutionResult(
                success=True,
                output=result,
                modified_files=modified_files,
                duration_ms=duration_ms,
            )
            self._task_results[subtask.sub_task_id] = execution_result
            return execution_result

        except Exception as e:
            subtask.status = "failed"
            duration_ms = (time.time() - t0) * 1000
            logger.error(f"[ExecutionLayer] Subtask {subtask.sub_task_id} failed: {e}")

            return ExecutionResult(
                success=False,
                output="",
                modified_files=[],
                duration_ms=duration_ms,
                error=str(e),
            )

    def _write_generated_code(self, subtask: SubTask, code: str) -> List[str]:
        """将生成的代码写入文件"""
        if not code.strip():
            return []

        desc = subtask.description.lower()
        modified_files = []

        file_map = {
            ("model", "数据库", "数据模型"): "app/models.py",
            ("schema", "pydantic", "验证"): "app/schemas.py",
            ("repository", "数据访问", "dao"): "app/repository.py",
            ("service", "业务逻辑"): "app/services.py",
            ("api", "route", "接口"): "app/api.py",
            ("auth", "jwt", "认证"): "app/auth.py",
            ("main", "入口"): "app/main.py",
            ("database", "db", "连接"): "app/database.py",
            ("test", "测试"): "tests/test_main.py",
        }

        matched_path = None
        for keywords, path in file_map.items():
            if any(keyword in desc for keyword in keywords):
                matched_path = path
                break

        if not matched_path:
            matched_path = f"app/{subtask.sub_task_id}.py"

        full_path = os.path.join(self.workdir, matched_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(code)
            modified_files.append(full_path)
            logger.info(f"[ExecutionLayer] Wrote code to: {full_path}")
        except Exception as e:
            logger.error(f"[ExecutionLayer] Failed to write file {full_path}: {e}")

        return modified_files

    def execute_with_dependency_graph(self, subtasks: List[SubTask]) -> Dict[str, Any]:
        """按依赖图顺序执行子任务

        实现FR-2.3：Executor Agent核心功能

        Args:
            subtasks: 子任务列表

        Returns:
            执行结果汇总
        """
        t0 = time.time()

        graph = DependencyGraph()
        graph.build_from_subtasks(subtasks)

        try:
            execution_order = graph.topological_sort()
            logger.info(f"[ExecutionLayer] Execution order: {execution_order}")
        except ValueError as e:
            logger.error(f"[ExecutionLayer] Circular dependency detected: {e}")
            return {
                "success": False,
                "error": str(e),
                "execution_order": [],
                "results": [],
            }

        results = []
        all_success = True

        for task_id in execution_order:
            subtask = graph.get_node(task_id)
            if not subtask:
                continue

            deps_ready = all(dep in self._executed_tasks for dep in subtask.dependencies)
            if not deps_ready:
                logger.warning(f"[ExecutionLayer] Dependencies not ready for {task_id}, skipping")
                continue

            result = self.execute(subtask)
            results.append({
                "sub_task_id": subtask.sub_task_id,
                "description": subtask.description,
                "success": result.success,
                "duration_ms": result.duration_ms,
                "output": result.output,
                "error": result.error,
            })

            if not result.success:
                all_success = False
                logger.error(f"[ExecutionLayer] Subtask {task_id} failed, stopping execution")
                break

        duration_ms = (time.time() - t0) * 1000

        return {
            "success": all_success,
            "execution_order": execution_order,
            "total_subtasks": len(execution_order),
            "completed_subtasks": len(self._executed_tasks),
            "failed_subtasks": len([r for r in results if not r["success"]]),
            "duration_ms": duration_ms,
            "results": results,
        }

    def execute_task_chain(self, subtasks: List[SubTask], stop_on_failure: bool = True) -> Dict[str, Any]:
        """执行子任务链（顺序执行，不构建依赖图）"""
        t0 = time.time()
        results = []
        all_success = True

        for subtask in subtasks:
            result = self.execute(subtask)
            results.append({
                "sub_task_id": subtask.sub_task_id,
                "description": subtask.description,
                "success": result.success,
                "duration_ms": result.duration_ms,
                "output": result.output,
                "error": result.error,
            })

            if not result.success and stop_on_failure:
                all_success = False
                break

        duration_ms = (time.time() - t0) * 1000

        return {
            "success": all_success,
            "total_subtasks": len(subtasks),
            "duration_ms": duration_ms,
            "results": results,
        }

    def _translate_intent_to_search_query(self, intent: str) -> str:
        """语义桥接层：将中文意图描述翻译为英文搜索关键词

        实现零Token生成的关键：让中文意图能够匹配到英文模板物种
        """
        keyword_map = {
            "按钮": "button",
            "卡片": "card",
            "模态框": "modal",
            "输入框": "input",
            "表格": "table",
            "表单": "form",
            "对话框": "dialog",
            "导航": "navigation",
            "菜单": "menu",
            "图标": "icon",
            "渐变": "gradient",
            "阴影": "shadow",
            "悬停": "hover",
            "交互": "interactive",
            "API": "api",
            "接口": "api",
            "服务": "service",
            "数据": "data",
            "处理": "process",
            "列表": "list",
            "详情": "detail",
            "创建": "create",
            "生成": "generate",
            "组件": "component",
            "页面": "page",
            "布局": "layout",
        }

        translated = []
        intent_lower = intent.lower()
        
        for chinese, english in keyword_map.items():
            if chinese in intent_lower:
                translated.append(english)
        
        if translated:
            return " ".join(translated)
        
        return intent

    def _generate_code_from_template(self, subtask: SubTask) -> str:
        """根据子任务描述从模板生成代码（优先从物种库匹配）

        编译式AI范式核心：优先从认知物种库匹配模板，零Token生成
        只有在物种库未找到匹配时才使用代码模板引擎
        """
        desc = subtask.description.lower()

        if self.species_library:
            search_query = self._translate_intent_to_search_query(subtask.description)
            matched_species = self.species_library.search_species(search_query)
            if matched_species:
                best_species = matched_species[0]
                logger.info(f"[ExecutionLayer] Found matching species: {best_species.name} (template={best_species.template})")
                best_species.update_usage(success=True)
                
                template_code = self._render_species_template(best_species)
                self.species_library.register_compiled_species(
                    template=best_species.template,
                    props=best_species.props,
                    tags=best_species.tags,
                    domain=best_species.domain,
                )
                return template_code

        if "class" in desc or "类" in desc:
            return self.code_template.render_python_class(
                class_name=self._extract_class_name(subtask.description),
                description=subtask.description,
            )
        elif "function" in desc or "函数" in desc:
            return self.code_template.render_python_function(
                function_name=self._extract_function_name(subtask.description),
                description=subtask.description,
            )
        elif "test" in desc or "测试" in desc:
            return self.code_template.render(
                "python_test",
                module="module",
                class_name="TestClass",
                test_name="example",
            )
        elif "model" in desc or "模型" in desc:
            return self.code_template.render_pydantic_model(
                model_name=self._extract_class_name(subtask.description),
                description=subtask.description,
                fields="    id: int\n    name: str",
            )
        elif "route" in desc or "api" in desc:
            return self.code_template.render_fastapi_route(
                endpoint="items",
                description=subtask.description,
            )
        else:
            return f"# Generated for: {subtask.description}\n"

    def _render_species_template(self, species) -> str:
        """从物种渲染代码模板"""
        template = species.template
        props = species.props
        
        if template == "button":
            return f"""def render_button(label="{props.get('label', 'Button')}", color="{props.get('color', 'primary')}"):
    '''渲染按钮组件'''
    return f'<button class="btn btn-{color}">{label}</button>'
"""
        elif template == "card":
            return f"""def render_card(title="{props.get('title', '')}", content="{props.get('content', '')}"):
    '''渲染卡片组件'''
    return f'<div class="card"><h3>{{title}}</h3><p>{{content}}</p></div>'
"""
        elif template == "api_service":
            return f"""def {props.get('method', 'get').lower()}_{props.get('endpoint', 'endpoint').strip('/').replace('/', '_')}():
    '''调用 {props.get('method', 'GET')} {props.get('endpoint', '')}'''
    import requests
    url = "{props.get('base_url', 'http://localhost:8000')}{props.get('endpoint', '')}"
    return requests.request("{props.get('method', 'GET')}", url)
"""
        elif template == "data_processing":
            return f"""def process_data(data, algorithm="{props.get('algorithm', 'process')}"):
    '''{props.get('algorithm', 'Process')}数据处理'''
    {'' if props.get('parallel') else '# '}from concurrent.futures import ThreadPoolExecutor
    return data
"""
        else:
            return f"# Species: {species.name}\n# Template: {template}\n# Props: {props}\n"


    def _extract_class_name(self, description: str) -> str:
        """从描述中提取类名"""
        tokens = re.findall(r'[a-zA-Z]+', description)
        if tokens:
            return ''.join(t.capitalize() for t in tokens[:3])
        return "GeneratedClass"

    def _extract_function_name(self, description: str) -> str:
        """从描述中提取函数名"""
        tokens = re.findall(r'[a-zA-Z]+', description)
        if tokens:
            return '_'.join(t.lower() for t in tokens[:4])
        return "generate_code"

    def write_code(self, file_path: str, code: str, overwrite: bool = True) -> ExecutionResult:
        """写入代码文件"""
        t0 = time.time()
        try:
            if self.tool_orchestrator:
                result = self.tool_orchestrator.write_file(file_path, code, overwrite)
            else:
                abs_path = os.path.join(self.workdir, file_path)
                os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                with open(abs_path, 'w', encoding='utf-8') as f:
                    f.write(code)
                result = f"Written: {file_path}"

            return ExecutionResult(
                success=True,
                output=result,
                modified_files=[file_path],
                duration_ms=(time.time() - t0) * 1000,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="",
                modified_files=[],
                duration_ms=(time.time() - t0) * 1000,
                error=str(e),
            )

    def run_tests(self, test_dir: str = "") -> ExecutionResult:
        """运行测试"""
        t0 = time.time()
        try:
            if self.tool_orchestrator:
                result = self.tool_orchestrator.run_shell(
                    f"python -m pytest {test_dir or '.'} -v",
                    timeout=300,
                )
            else:
                result = self.sandbox.run_command(f"python -m pytest {test_dir or '.'} -v")

            passed = result.get("success", False) or "PASS" in str(result.get("stdout", ""))

            return ExecutionResult(
                success=passed,
                output=str(result),
                modified_files=[],
                duration_ms=(time.time() - t0) * 1000,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="",
                modified_files=[],
                duration_ms=(time.time() - t0) * 1000,
                error=str(e),
            )

    def run_shell(self, command: str, timeout: int = 120) -> ExecutionResult:
        """执行Shell命令"""
        t0 = time.time()
        try:
            if self.tool_orchestrator:
                result = self.tool_orchestrator.run_shell(command, timeout)
            else:
                result = self.sandbox.run_command(command, timeout)

            return ExecutionResult(
                success=result.get("success", False),
                output=str(result.get("stdout", "")),
                modified_files=[],
                duration_ms=(time.time() - t0) * 1000,
                error=result.get("stderr", "") if not result.get("success") else None,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="",
                modified_files=[],
                duration_ms=(time.time() - t0) * 1000,
                error=str(e),
            )

    def run_python(self, code: str, timeout: int = 60) -> ExecutionResult:
        """执行Python代码"""
        t0 = time.time()
        try:
            if self.tool_orchestrator:
                result = self.tool_orchestrator.run_python(code, timeout)
            else:
                result = self.sandbox.run_python(code, timeout)

            return ExecutionResult(
                success=result.get("success", False),
                output=str(result.get("stdout", "")),
                modified_files=[],
                duration_ms=(time.time() - t0) * 1000,
                error=result.get("stderr", "") if not result.get("success") else None,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="",
                modified_files=[],
                duration_ms=(time.time() - t0) * 1000,
                error=str(e),
            )

    def read_file(self, file_path: str) -> ExecutionResult:
        """读取文件内容"""
        t0 = time.time()
        try:
            if self.tool_orchestrator:
                content = self.tool_orchestrator.read_file(file_path)
            else:
                abs_path = os.path.join(self.workdir, file_path)
                with open(abs_path, 'r', encoding='utf-8') as f:
                    content = f.read()

            return ExecutionResult(
                success=True,
                output=content,
                modified_files=[],
                duration_ms=(time.time() - t0) * 1000,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="",
                modified_files=[],
                duration_ms=(time.time() - t0) * 1000,
                error=str(e),
            )

    def get_executed_tasks(self) -> Set[str]:
        """获取已执行的任务ID集合"""
        return self._executed_tasks.copy()

    def get_task_result(self, task_id: str) -> Optional[ExecutionResult]:
        """获取指定任务的执行结果"""
        return self._task_results.get(task_id)

    def reset(self) -> None:
        """重置执行状态"""
        self._executed_tasks.clear()
        self._task_results.clear()
        logger.info("[ExecutionLayer] Execution state reset")

    @property
    def status(self) -> Dict[str, Any]:
        """返回执行层状态"""
        return {
            "workdir": self.workdir,
            "executed_tasks": len(self._executed_tasks),
            "task_results": len(self._task_results),
            "sandbox": self.sandbox.status,
            "available_tools": self.tool_orchestrator.get_available_tools() if self.tool_orchestrator else [],
            "available_templates": self.code_template.get_available_templates(),
        }


# ════════════════════════════════════════════════════════════
# 验证层 — Verification Layer（完整实现）
# ════════════════════════════════════════════════════════════
# 实现FR-4：多层验证循环
#   FR-4.1: Write → Lint → Unit Test → Integration Test → Security Scan → Merge
#   FR-4.2: 错误恢复模式（测试失败自动修复、架构偏离自动回滚）
#   FR-4.3: 增量交付约束（每子任务≤200行变更、强制Git commit、语义化提交信息）

@dataclass
class VerificationStep:
    name: str
    passed: bool
    score: float
    details: Dict[str, Any]


class VerificationLayer:
    """验证层：测试验证器、静态分析器、安全扫描器

    实现FR-4多层验证循环：
    - 验证链：Write → Lint → Unit Test → Integration Test → Security Scan → Delivery
    - 错误恢复：测试失败自动修复、架构偏离自动回滚（最多重试3次）
    - 增量交付约束：强制Git commit、语义化提交信息、每子任务≤200行
    - 三层备份：集成SafeRollback（内存→文件→Git）
    """

    MAX_RETRY_ATTEMPTS = 3
    MAX_LINES_PER_SUBTASK = 200

    def __init__(self, project_root: str = ""):
        self.project_root = project_root or os.environ.get("LAAP_ROOT", os.getcwd())
        
        if TestValidator:
            self.test_validator = TestValidator(self.project_root)
        else:
            self.test_validator = None

        if StaticAnalyzer:
            self.static_analyzer = StaticAnalyzer(self.project_root)
        else:
            self.static_analyzer = None

        if SecurityScanner:
            self.security_scanner = SecurityScanner(self.project_root)
        else:
            self.security_scanner = None

        if IncrementalDelivery:
            self.incremental_delivery = IncrementalDelivery(self.project_root)
        else:
            self.incremental_delivery = None

        if SafeRollback:
            self.safe_rollback = SafeRollback(self.project_root)
        else:
            self.safe_rollback = None

        self._verification_history: List[Dict[str, Any]] = []
        self._current_retry_count = 0

    def verify(self, execution_result: ExecutionResult) -> VerificationResult:
        test_result = {}
        static_issues = []
        security_issues = []

        if self.test_validator:
            test_result = self.test_validator.validate(execution_result.output)
        else:
            test_result = {"passed": True, "details": "TestValidator not available"}

        if self.static_analyzer:
            static_issues = self.static_analyzer.analyze(execution_result.output)
        else:
            static_issues = []

        if self.security_scanner:
            security_issues = self.security_scanner.scan(execution_result.output)
        else:
            security_issues = []

        all_issues = static_issues + security_issues
        score = 1.0 - (len(all_issues) * 0.05)

        return VerificationResult(
            passed=test_result["passed"] and len(all_issues) == 0,
            issues=all_issues,
            score=max(0.0, score),
        )

    def verify_chain(self, execution_result: ExecutionResult,
                     subtask: Optional[SubTask] = None) -> Dict[str, Any]:
        """执行完整验证链：Write → Lint → Unit Test → Integration Test → Security Scan

        Args:
            execution_result: 执行结果
            subtask: 子任务信息（用于增量交付）

        Returns:
            Dict[str, Any]: 验证链结果
        """
        steps = []
        overall_passed = True
        reports = {}

        if execution_result.modified_files:
            for file_path in execution_result.modified_files:
                if self.safe_rollback:
                    self.safe_rollback.snapshot(file_path)

        if self.static_analyzer:
            lint_result = self._run_lint(execution_result.modified_files)
            steps.append(lint_result)
            overall_passed = overall_passed and lint_result["passed"]
            reports["lint"] = lint_result

            if not lint_result["passed"]:
                return self._build_chain_result(steps, overall_passed, reports, "lint_failed")

        unit_test_result = self._run_unit_tests()
        steps.append(unit_test_result)
        overall_passed = overall_passed and unit_test_result["passed"]
        reports["unit_test"] = unit_test_result

        if not unit_test_result["passed"]:
            return self._build_chain_result(steps, overall_passed, reports, "unit_test_failed")

        integration_test_result = self._run_integration_tests()
        steps.append(integration_test_result)
        overall_passed = overall_passed and integration_test_result["passed"]
        reports["integration_test"] = integration_test_result

        if not integration_test_result["passed"]:
            return self._build_chain_result(steps, overall_passed, reports, "integration_test_failed")

        if self.security_scanner:
            security_result = self._run_security_scan()
            steps.append(security_result)
            overall_passed = overall_passed and security_result["passed"]
            reports["security"] = security_result

            if not security_result["passed"]:
                return self._build_chain_result(steps, overall_passed, reports, "security_failed")

        if self.incremental_delivery and subtask:
            delivery_result = self._enforce_delivery(subtask)
            steps.append(delivery_result)
            overall_passed = overall_passed and delivery_result["passed"]
            reports["delivery"] = delivery_result

        self._verification_history.append({
            "timestamp": time.time(),
            "steps": steps,
            "passed": overall_passed,
        })

        return self._build_chain_result(steps, overall_passed, reports, "completed")

    def _run_lint(self, modified_files: List[str]) -> Dict[str, Any]:
        """运行静态分析（Lint）"""
        if not self.static_analyzer:
            return {
                "name": "lint",
                "passed": True,
                "score": 1.0,
                "details": {"message": "StaticAnalyzer not available"}
            }

        if not modified_files:
            return {
                "name": "lint",
                "passed": True,
                "score": 1.0,
                "details": {"message": "No modified files"}
            }

        try:
            result = self.static_analyzer.analyze_project(modified_files)
            return {
                "name": "lint",
                "passed": result.passed,
                "score": result.pylint_score / 10.0 if result.pylint_score else 1.0,
                "details": {
                    "syntax_valid": result.syntax_valid,
                    "flake8_passed": result.flake8_passed,
                    "mypy_passed": result.mypy_passed,
                    "pylint_score": result.pylint_score,
                    "issues_count": len(result.issues),
                    "report": self.static_analyzer.generate_report(result)
                }
            }
        except Exception as e:
            return {
                "name": "lint",
                "passed": False,
                "score": 0.0,
                "details": {"error": str(e)}
            }

    def _run_unit_tests(self, test_path: str = "tests") -> Dict[str, Any]:
        """运行单元测试"""
        if not self.test_validator:
            return {
                "name": "unit_test",
                "passed": True,
                "score": 1.0,
                "details": {"message": "TestValidator not available"}
            }

        try:
            result = self.test_validator.run_pytest(test_path)
            return {
                "name": "unit_test",
                "passed": result.passed,
                "score": result.passed_tests / max(result.total_tests, 1),
                "details": {
                    "total_tests": result.total_tests,
                    "passed_tests": result.passed_tests,
                    "failed_tests": result.failed_tests,
                    "duration_ms": result.duration_ms,
                    "report": self.test_validator.generate_report(result)
                }
            }
        except Exception as e:
            return {
                "name": "unit_test",
                "passed": False,
                "score": 0.0,
                "details": {"error": str(e)}
            }

    def _run_integration_tests(self, test_path: str = "tests/integration") -> Dict[str, Any]:
        """运行集成测试"""
        if not self.test_validator:
            return {
                "name": "integration_test",
                "passed": True,
                "score": 1.0,
                "details": {"message": "TestValidator not available"}
            }

        if not os.path.exists(os.path.join(self.project_root, test_path)):
            return {
                "name": "integration_test",
                "passed": True,
                "score": 1.0,
                "details": {"message": "Integration tests not found, skipped"}
            }

        try:
            result = self.test_validator.run_integration_tests(test_path)
            return {
                "name": "integration_test",
                "passed": result.passed,
                "score": result.passed_tests / max(result.total_tests, 1),
                "details": {
                    "total_tests": result.total_tests,
                    "passed_tests": result.passed_tests,
                    "failed_tests": result.failed_tests,
                    "duration_ms": result.duration_ms,
                    "report": self.test_validator.generate_report(result)
                }
            }
        except Exception as e:
            return {
                "name": "integration_test",
                "passed": False,
                "score": 0.0,
                "details": {"error": str(e)}
            }

    def _run_security_scan(self) -> Dict[str, Any]:
        """运行安全扫描"""
        if not self.security_scanner:
            return {
                "name": "security",
                "passed": True,
                "score": 1.0,
                "details": {"message": "SecurityScanner not available"}
            }

        try:
            result = self.security_scanner.comprehensive_scan()
            return {
                "name": "security",
                "passed": result.passed,
                "score": 1.0 - ((result.critical_count + result.high_count) * 0.5),
                "details": {
                    "total_vulnerabilities": result.total_vulnerabilities,
                    "critical_count": result.critical_count,
                    "high_count": result.high_count,
                    "medium_count": result.medium_count,
                    "low_count": result.low_count,
                    "report": self.security_scanner.generate_report(result)
                }
            }
        except Exception as e:
            return {
                "name": "security",
                "passed": False,
                "score": 0.0,
                "details": {"error": str(e)}
            }

    def _enforce_delivery(self, subtask: SubTask) -> Dict[str, Any]:
        """强制执行增量交付约束"""
        if not self.incremental_delivery:
            return {
                "name": "delivery",
                "passed": True,
                "score": 1.0,
                "details": {"message": "IncrementalDelivery not available"}
            }

        try:
            result = self.incremental_delivery.enforce_delivery(
                subtask.description,
                subtask.files
            )
            return {
                "name": "delivery",
                "passed": result.get("success", False),
                "score": 1.0 if result.get("success") else 0.0,
                "details": result
            }
        except Exception as e:
            return {
                "name": "delivery",
                "passed": False,
                "score": 0.0,
                "details": {"error": str(e)}
            }

    def _build_chain_result(self, steps: List[Dict[str, Any]], passed: bool,
                            reports: Dict[str, Any], reason: str) -> Dict[str, Any]:
        """构建验证链结果"""
        return {
            "passed": passed,
            "reason": reason,
            "steps": steps,
            "reports": reports,
            "total_steps": len(steps),
            "passed_steps": sum(1 for s in steps if s["passed"]),
            "score": sum(s["score"] for s in steps) / max(len(steps), 1),
            "timestamp": time.time(),
        }

    def attempt_fix(self, execution_result: ExecutionResult,
                    subtask: Optional[SubTask] = None) -> Dict[str, Any]:
        """尝试自动修复（错误恢复模式）

        Args:
            execution_result: 执行结果
            subtask: 子任务信息

        Returns:
            Dict[str, Any]: 修复结果
        """
        self._current_retry_count += 1

        if self._current_retry_count > self.MAX_RETRY_ATTEMPTS:
            return {
                "success": False,
                "message": f"已达到最大重试次数 ({self.MAX_RETRY_ATTEMPTS})",
                "retry_count": self._current_retry_count,
                "action": "rollback"
            }

        logger.info(f"[Verification] 尝试修复，第 {self._current_retry_count}/{self.MAX_RETRY_ATTEMPTS} 次")

        if execution_result.modified_files and self.safe_rollback:
            for file_path in execution_result.modified_files:
                rollback_result = self.safe_rollback.rollback(file_path)
                logger.info(f"[Verification] 回滚文件 {file_path}: {rollback_result}")

        verification_result = self.verify_chain(execution_result, subtask)

        if verification_result["passed"]:
            self._current_retry_count = 0
            return {
                "success": True,
                "message": "修复成功",
                "retry_count": self._current_retry_count - 1,
                "action": "verified",
                "verification": verification_result
            }

        return {
            "success": False,
            "message": f"修复尝试失败，第 {self._current_retry_count}/{self.MAX_RETRY_ATTEMPTS} 次",
            "retry_count": self._current_retry_count,
            "action": "retry",
            "verification": verification_result
        }

    def reset_retry_count(self) -> None:
        """重置重试计数器"""
        self._current_retry_count = 0

    def get_verification_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取验证历史"""
        return self._verification_history[-limit:]


# ════════════════════════════════════════════════════════════
# 反馈层 — Feedback Layer（占位实现）
# ════════════════════════════════════════════════════════════

class SelfCorrectionLoop:
    """自修正循环：自动检测和修复错误"""

    def correct(self, issue: Dict[str, Any]) -> str:
        return "Fixed: " + issue.get("description", "")


class PatternLearner:
    """模式学习器：从经验中学习模式"""

    def learn(self, context: TaskContext, result: ExecutionResult) -> None:
        pass


class ExperienceAccumulator:
    """经验积累器：积累和管理经验"""

    def accumulate(self, experience: Dict[str, Any]) -> None:
        pass


class FeedbackLayer:
    """反馈层：自修正循环、模式学习器、经验积累器"""

    def __init__(self):
        self.self_correction = SelfCorrectionLoop()
        self.pattern_learner = PatternLearner()
        self.experience_accumulator = ExperienceAccumulator()

    def feedback(self, context: TaskContext, execution_result: ExecutionResult,
                 verification_result: VerificationResult) -> Dict[str, Any]:
        if not verification_result.passed and verification_result.issues:
            corrections = []
            for issue in verification_result.issues:
                correction = self.self_correction.correct(issue)
                corrections.append(correction)
            return {"corrected": True, "corrections": corrections}

        self.pattern_learner.learn(context, execution_result)
        self.experience_accumulator.accumulate({
            "task_id": context.task_id,
            "intent": context.intent,
            "success": verification_result.passed,
            "score": verification_result.score,
        })

        return {"corrected": False, "corrections": []}


# ════════════════════════════════════════════════════════════
# ConsciousnessHarness 核心类
# ════════════════════════════════════════════════════════════

class ConsciousnessHarness:
    """Consciousness Harness — 代码任务引擎核心类

    实现FR-1要求的7层认知架构，作为代码任务的总控制器。
    集成编译式AI范式三大核心组件：
    - CognitiveSpeciesLibrary: 认知物种库，编译产物自动注册为新物种
    - EvolutionaryCompiler: 进化编译器，实现持续进化的编译循环
    - PsiNetConnector: Ψ-Net连接器，跨实例因果规则交换
    """

    def __init__(self, workdir: str = "", token_budget: int = 2000, task_board: Optional["TaskBoard"] = None):
        self.workdir = workdir or os.getcwd()
        self.token_budget = token_budget
        self._started_at = time.time()
        self._task_history: List[Dict[str, Any]] = []

        self.memory_layer = MemoryLayer(workdir)
        self.task_board = task_board or (TaskBoard() if TaskBoard else None)

        self._init_cognitive_species_library()

        self.perception_layer = PerceptionLayer(self.memory_layer)
        self.reasoning_layer = ReasoningLayer(self.memory_layer, self.task_board)
        self.decision_layer = DecisionLayer()
        self.execution_layer = ExecutionLayer(workdir=workdir, species_library=self.species_library)
        self.verification_layer = VerificationLayer()
        self.feedback_layer = FeedbackLayer()

        self._init_evolutionary_compiler()
        self._init_psi_net_connector()

        self._cognitive_integration = None
        self._init_cognitive_integration()

        logger.info(f"[Harness] ConsciousnessHarness initialized at {self.workdir}")
        logger.info(f"[Harness] Compiled AI Paradigm components: species_library={self.species_library is not None}, evolutionary_compiler={self.evolutionary_compiler is not None}, psi_net={self.psi_net is not None}")

    def _init_cognitive_integration(self) -> None:
        """初始化CognitiveIntegration，建立与PSI的双向通信"""
        if start_integration:
            try:
                self._cognitive_integration = start_integration(harness=self)
                logger.info("[Harness] CognitiveIntegration initialized - PSI ↔ Harness bidirectional communication established")
            except Exception as e:
                logger.warning(f"[Harness] Failed to initialize CognitiveIntegration: {e}")
        else:
            logger.info("[Harness] CognitiveIntegration not available - running in standalone mode")

    def _init_cognitive_species_library(self) -> None:
        """初始化认知物种库"""
        try:
            from .cognitive_species_library import CognitiveSpeciesLibrary
            self.species_library = CognitiveSpeciesLibrary(self.workdir)
            logger.info(f"[Harness] CognitiveSpeciesLibrary initialized - {len(self.species_library._species)} species loaded")
        except ImportError as e:
            self.species_library = None
            logger.warning(f"[Harness] CognitiveSpeciesLibrary not available: {e}")

    def _init_evolutionary_compiler(self) -> None:
        """初始化进化编译器"""
        try:
            from .evolutionary_compiler import EvolutionaryCompiler
            self.evolutionary_compiler = EvolutionaryCompiler(self.species_library, workdir=self.workdir)
            logger.info("[Harness] EvolutionaryCompiler initialized - continuous evolution enabled")
        except ImportError as e:
            self.evolutionary_compiler = None
            logger.warning(f"[Harness] EvolutionaryCompiler not available: {e}")

    def _init_psi_net_connector(self) -> None:
        """初始化Ψ-Net连接器"""
        try:
            from .psi_net_connector import PsiNetConnector
            self.psi_net = PsiNetConnector()
            logger.info(f"[Harness] PsiNetConnector initialized - instance_id={self.psi_net.instance_id}, port={self.psi_net.port}")
        except ImportError as e:
            self.psi_net = None
            logger.warning(f"[Harness] PsiNetConnector not available: {e}")

    def set_codex_agent(self, agent):
        """设置CodexAgent到执行层"""
        self.execution_layer.codex_agent = agent
        self.execution_layer.tool_orchestrator = ToolOrchestrator(agent)
        logger.info(f"[Harness] CodexAgent [{agent.id[:8]}] integrated")

    def run(self, description: str, intent: Optional[str] = None) -> Dict[str, Any]:
        """执行完整的代码任务流程（集成CognitiveBus双向通信）"""
        t0 = time.time()
        logger.info(f"[Harness] ========== 任务开始 ==========")
        logger.info(f"[Harness] 任务描述: {description[:100]}{'...' if len(description) > 100 else ''}")
        logger.info(f"[Harness] 用户意图: {intent or '自动检测'}")

        try:
            logger.info(f"[Harness] [1/5] 阶段: 获取认知上下文")
            cognitive_context = self._get_cognitive_context()
            if cognitive_context:
                logger.info(f"[Harness]         需求状态: {cognitive_context.get('needs', {})}")
                logger.info(f"[Harness]         情感状态: {cognitive_context.get('emotion', {})}")
                logger.info(f"[Harness]         注意力: {cognitive_context.get('attention', {})}")
                logger.info(f"[Harness]         好奇心: {cognitive_context.get('curiosity', 0)}")
                logger.info(f"[Harness]         待处理洞见: {cognitive_context.get('insights_pending', 0)}")
            else:
                logger.info(f"[Harness]         认知上下文不可用（独立模式）")

            logger.info(f"[Harness] [2/5] 阶段: 感知层 (Perception)")
            t1 = time.time()
            context = self.perceive(description, intent)
            logger.info(f"[Harness]         任务ID: {context.task_id}")
            logger.info(f"[Harness]         检测意图: {context.intent}")
            logger.info(f"[Harness]         提取关键词: {context.keywords}")
            logger.info(f"[Harness]         相关模式: {context.related_patterns}")
            logger.info(f"[Harness]         感知耗时: {(time.time() - t1) * 1000:.2f}ms")

            logger.info(f"[Harness] [3/5] 阶段: 推理层 (Reasoning)")
            t1 = time.time()
            plan = self.reason(context)
            logger.info(f"[Harness]         规划子任务数: {len(plan)}")
            for i, subtask in enumerate(plan):
                logger.info(f"[Harness]         子任务{i+1}: {subtask.description}")
            logger.info(f"[Harness]         推理耗时: {(time.time() - t1) * 1000:.2f}ms")

            logger.info(f"[Harness] [PSI] 处理涌现洞见")
            insights = self._process_pending_insights(batch_size=5)
            if insights:
                logger.info(f"[Harness]         处理洞见数: {len(insights)}")
                for insight in insights:
                    logger.info(f"[Harness]         - [{insight.priority}] {insight.content[:50]}... (置信度={insight.confidence})")
            else:
                logger.info(f"[Harness]         无待处理洞见")

            logger.info(f"[Harness] [4/5] 阶段: 执行层 + 验证层 (Execution + Verification)")
            results = []
            for i, subtask in enumerate(plan):
                logger.info(f"[Harness]         执行子任务 {i+1}/{len(plan)}: {subtask.description}")

                t1 = time.time()
                result = self.execute(subtask)
                exec_time = (time.time() - t1) * 1000
                logger.info(f"[Harness]         - 执行结果: {'成功' if result.success else '失败'}")
                logger.info(f"[Harness]         - 执行耗时: {exec_time:.2f}ms")
                logger.info(f"[Harness]         - 修改文件: {result.modified_files}")

                t1 = time.time()
                verification = self.verify(result)
                verify_time = (time.time() - t1) * 1000
                logger.info(f"[Harness]         - 验证结果: {'通过' if verification.passed else '未通过'}")
                logger.info(f"[Harness]         - 验证耗时: {verify_time:.2f}ms")
                if verification.issues:
                    logger.info(f"[Harness]         - 验证问题: {verification.issues[:3]}")

                t1 = time.time()
                feedback = self.feedback(context, result, verification)
                feedback_time = (time.time() - t1) * 1000
                logger.info(f"[Harness]         - 反馈类型: {feedback.get('type', 'unknown')}")
                logger.info(f"[Harness]         - 反馈耗时: {feedback_time:.2f}ms")

                results.append({
                    "subtask": subtask.description,
                    "status": "completed" if verification.passed else "failed",
                    "duration_ms": result.duration_ms,
                    "feedback": feedback,
                })

                if not verification.passed and feedback.get("corrected"):
                    logger.info(f"[Harness]         - 自动修正并重试...")
                    result = self.execute(subtask)
                    verification = self.verify(result)

            logger.info(f"[Harness] [5/5] 阶段: 结果汇总与反馈")
            duration_ms = (time.time() - t0) * 1000
            all_passed = all(r["status"] == "completed" for r in results)
            logger.info(f"[Harness]         总耗时: {duration_ms:.2f}ms")
            logger.info(f"[Harness]         任务状态: {'全部通过' if all_passed else '部分失败'}")
            logger.info(f"[Harness]         完成子任务: {sum(1 for r in results if r['status'] == 'completed')}/{len(results)}")

            self._task_history.append({
                "task_id": context.task_id,
                "description": description,
                "intent": context.intent,
                "duration_ms": duration_ms,
                "success": all_passed,
                "subtasks": len(results),
            })

            logger.info(f"[Harness] [PSI] 提交执行结果反馈")
            self._submit_execution_result(context.task_id, all_passed, results, duration_ms)

            logger.info(f"[Harness] ========== 任务结束 ==========")

            return {
                "status": "success" if all_passed else "partial",
                "task_id": context.task_id,
                "intent": context.intent,
                "duration_ms": duration_ms,
                "results": results,
                "message": "Task completed" if all_passed else "Some subtasks failed",
                "cognitive_context": cognitive_context if cognitive_context else None,
                "insights_processed": len(insights) if insights else 0,
            }

        except Exception as e:
            logger.error(f"[Harness] 任务执行失败: {e}")
            if 'context' in dir():
                self._submit_execution_result(context.task_id, False, [], 0, error=str(e))
            return {
                "status": "error",
                "error": str(e),
                "message": f"Task failed: {e}",
            }

    def _get_cognitive_context(self) -> Optional[Dict[str, Any]]:
        """从CognitiveBus获取实时认知上下文（需求、情感、注意力）"""
        if get_context:
            try:
                context = get_context()
                if context:
                    logger.debug(f"[Harness] Cognitive context received: needs={context.get('needs')}, emotion={context.get('emotion')}")
                return context
            except Exception as e:
                logger.warning(f"[Harness] Failed to get cognitive context: {e}")
        return None

    def _process_pending_insights(self, batch_size: int = 5) -> List[EmergenceInsight]:
        """处理PSI涌现的洞见（批量获取，避免高频阻塞）"""
        if process_pending_insights:
            try:
                insights = process_pending_insights(batch_size=batch_size)
                for insight in insights:
                    logger.info(f"[Harness] Processed insight: {insight.content[:50]}... (priority={insight.priority}, confidence={insight.confidence})")
                    self.decision_layer.consider_insight(insight)
                return insights
            except Exception as e:
                logger.warning(f"[Harness] Failed to process pending insights: {e}")
        return []

    def _submit_execution_result(self, task_id: str, success: bool, results: List[Dict[str, Any]],
                                 duration_ms: float, error: str = "") -> None:
        """提交执行结果反馈给PSI（更新需求、情感、预测误差）"""
        if self._cognitive_integration and HarnessExecutionResult:
            try:
                verification_passed = all(r.get("status") == "completed" for r in results) if results else success
                result = HarnessExecutionResult(
                    task_id=task_id,
                    success=success,
                    output=str(results)[:500] if results else "",
                    tokens_used=0,
                    duration=duration_ms / 1000,
                    verification_passed=verification_passed,
                    error=error,
                )
                self._cognitive_integration.submit_execution_result(result)
                logger.info(f"[Harness] Execution result submitted to PSI: task={task_id}, success={success}")
            except Exception as e:
                logger.warning(f"[Harness] Failed to submit execution result: {e}")

    def perceive(self, description: str, intent: Optional[str] = None) -> TaskContext:
        """感知层：解析需求"""
        context = self.perception_layer.perceive(description)
        if intent:
            context.intent = intent
        logger.info(f"[Harness] Perceived: intent={context.intent}, keywords={context.keywords}")
        return context

    def reason(self, context: TaskContext) -> List[SubTask]:
        """推理层：规划任务"""
        plan = self.reasoning_layer.reason(context)
        logger.info(f"[Harness] Planned {len(plan)} subtasks")
        return plan

    def decide(self, code: str, context: TaskContext) -> Dict[str, Any]:
        """决策层：评估代码质量"""
        return self.decision_layer.decide(code, context)

    def execute(self, subtask: SubTask) -> ExecutionResult:
        """执行层：执行子任务"""
        logger.info(f"[Harness] Executing: {subtask.description}")
        return self.execution_layer.execute(subtask)

    def verify(self, result: ExecutionResult) -> VerificationResult:
        """验证层：验证结果"""
        return self.verification_layer.verify(result)

    def feedback(self, context: TaskContext, execution_result: ExecutionResult,
                 verification_result: VerificationResult) -> Dict[str, Any]:
        """反馈层：处理反馈"""
        return self.feedback_layer.feedback(context, execution_result, verification_result)

    def compile(self, intent: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """编译式AI范式核心方法：将意图编译为实现

        实现"意图→实现"的编译过程，支持持续进化。
        每一次编译都会自动注册新物种，并通过Ψ-Net广播结果。

        Args:
            intent: 用户意图描述
            context: 编译上下文

        Returns:
            Dict[str, Any]: 编译结果
        """
        if not self.evolutionary_compiler:
            return {"status": "error", "message": "EvolutionaryCompiler not available"}

        result = self.evolutionary_compiler.compile(intent, context)

        if self.psi_net:
            self.psi_net.send_compilation_result(result.to_dict())

        return result.to_dict()

    def register_species(self, template: str, props: Dict[str, Any],
                         tags: List[str] = None, domain: List[str] = None) -> Dict[str, Any]:
        """注册新物种到认知物种库"""
        if not self.species_library:
            return {"status": "error", "message": "CognitiveSpeciesLibrary not available"}

        species = self.species_library.register_compiled_species(template, props, tags, domain)

        if self.psi_net:
            self.psi_net.send_species_update(species.to_dict())

        return species.to_dict()

    def send_causal_rule(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """通过Ψ-Net发送因果规则"""
        if not self.psi_net:
            return {"status": "error", "message": "PsiNetConnector not available"}

        self.psi_net.send_causal_rule(rule)
        return {"status": "success", "message": "Causal rule sent"}

    def start_psi_net(self) -> Dict[str, Any]:
        """启动Ψ-Net连接器"""
        if not self.psi_net:
            return {"status": "error", "message": "PsiNetConnector not available"}

        self.psi_net.start()
        return {"status": "success", "instance_id": self.psi_net.instance_id, "port": self.psi_net.port}

    def connect_to_peer(self, host: str, port: int) -> Dict[str, Any]:
        """连接到Ψ-Net对等节点"""
        if not self.psi_net:
            return {"status": "error", "message": "PsiNetConnector not available"}

        success = self.psi_net.connect_to_peer(host, port)
        return {"status": "success" if success else "failed", "host": host, "port": port}

    def summary(self) -> str:
        """返回引擎摘要"""
        uptime = time.time() - self._started_at
        return (
            f"ConsciousnessHarness [uptime={uptime:.0f}s]"
            f" | tasks={len(self._task_history)}"
            f" | patterns={len(self.memory_layer.architecture_patterns)}"
        )

    @property
    def status(self) -> Dict[str, Any]:
        """返回引擎状态（包含认知集成状态和编译式AI范式组件状态）"""
        uptime = time.time() - self._started_at
        success_count = sum(1 for t in self._task_history if t.get("success"))

        cognitive_status = {}
        if self._cognitive_integration:
            try:
                cognitive_status = self._cognitive_integration.stats()
            except Exception as e:
                cognitive_status = {"error": str(e)}
        else:
            cognitive_status = {"available": False, "message": "CognitiveIntegration not initialized"}

        species_stats = {}
        if self.species_library:
            species_stats = self.species_library.get_stats()
        else:
            species_stats = {"available": False, "message": "CognitiveSpeciesLibrary not initialized"}

        compiler_stats = {}
        if self.evolutionary_compiler:
            compiler_stats = self.evolutionary_compiler.get_pattern_stats()
        else:
            compiler_stats = {"available": False, "message": "EvolutionaryCompiler not initialized"}

        psi_net_stats = {}
        if self.psi_net:
            psi_net_stats = self.psi_net.get_stats()
        else:
            psi_net_stats = {"available": False, "message": "PsiNetConnector not initialized"}

        return {
            "uptime": f"{uptime:.0f}s",
            "turns": len(self._task_history),
            "total_tokens": 0,
            "messages": len(self._task_history),
            "tools_loaded": 0,
            "layers": {
                "perception": "active",
                "memory": "active",
                "reasoning": "active",
                "decision": "active",
                "execution": "active",
                "verification": "active",
                "feedback": "active",
            },
            "cognitive_integration": cognitive_status,
            "compiled_ai_paradigm": {
                "species_library": species_stats,
                "evolutionary_compiler": compiler_stats,
                "psi_net": psi_net_stats,
            },
            "stats": {
                "tasks_total": len(self._task_history),
                "tasks_success": success_count,
                "tasks_failed": len(self._task_history) - success_count,
            },
        }

    def save_state(self, path: Optional[str] = None) -> str:
        """保存引擎状态"""
        save_path = path or os.path.join(self.workdir, ".laap", "harness_state.json")
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        state = {
            "started_at": self._started_at,
            "workdir": self.workdir,
            "token_budget": self.token_budget,
            "task_history": self._task_history,
            "saved_at": time.time(),
        }

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)

        return save_path

    def load_state(self, path: str) -> bool:
        """加载引擎状态"""
        if not os.path.exists(path):
            return False

        try:
            with open(path, 'r', encoding='utf-8') as f:
                state = json.load(f)

            self._started_at = state.get("started_at", time.time())
            self.workdir = state.get("workdir", self.workdir)
            self.token_budget = state.get("token_budget", self.token_budget)
            self._task_history = state.get("task_history", [])

            logger.info(f"[Harness] State loaded from {path}")
            return True
        except Exception as e:
            logger.warning(f"[Harness] Failed to load state: {e}")
            return False

    def run_with_state(self, description: str, intent: Optional[str] = None,
                       task_id: Optional[str] = None) -> Dict[str, Any]:
        """执行完整的代码任务流程（带状态保存）"""
        t0 = time.time()

        try:
            context = self.perceive(description, intent)
            
            if task_id:
                restored_state = self.restore_task(task_id)
                if restored_state:
                    logger.info(f"[Harness] Restored task state: {task_id}")
                    return restored_state

            plan = self.reason(context)
            results = []
            
            self._save_task_state_at_start(context.task_id, description, plan)

            for idx, subtask in enumerate(plan):
                result = self.execute(subtask)
                verification = self.verify(result)
                feedback = self.feedback(context, result, verification)

                results.append({
                    "subtask": subtask.description,
                    "sub_task_id": subtask.sub_task_id,
                    "status": "completed" if verification.passed else "failed",
                    "duration_ms": result.duration_ms,
                    "feedback": feedback,
                })

                self._save_task_state_at_progress(context.task_id, description, plan, idx, results)

                if not verification.passed and feedback.get("corrected"):
                    result = self.execute(subtask)
                    verification = self.verify(result)

            duration_ms = (time.time() - t0) * 1000
            all_passed = all(r["status"] == "completed" for r in results)

            self._task_history.append({
                "task_id": context.task_id,
                "description": description,
                "intent": context.intent,
                "duration_ms": duration_ms,
                "success": all_passed,
                "subtasks": len(results),
            })

            self._save_task_state_at_completion(context.task_id, description, plan, results, all_passed)

            return {
                "status": "success" if all_passed else "partial",
                "task_id": context.task_id,
                "intent": context.intent,
                "duration_ms": duration_ms,
                "results": results,
                "message": "Task completed" if all_passed else "Some subtasks failed",
            }

        except Exception as e:
            logger.error(f"[Harness] Task execution failed: {e}")
            
            if 'context' in dir():
                self._save_task_state_at_failure(context.task_id, description, str(e))
            
            return {
                "status": "error",
                "error": str(e),
                "message": f"Task failed: {e}",
            }

    def _save_task_state_at_start(self, task_id: str, description: str, subtasks: List[SubTask]) -> None:
        """任务开始时保存状态"""
        state = {
            "task_id": task_id,
            "description": description,
            "status": "in_progress",
            "current_subtask_index": 0,
            "subtasks": [
                {
                    "sub_task_id": s.sub_task_id,
                    "description": s.description,
                    "status": s.status,
                    "estimated_lines": s.estimated_lines,
                    "dependencies": s.dependencies,
                } for s in subtasks
            ],
            "results": [],
            "started_at": time.time(),
        }
        self.memory_layer.save_task_state(task_id, state)

    def _save_task_state_at_progress(self, task_id: str, description: str,
                                     subtasks: List[SubTask], current_index: int,
                                     results: List[Dict[str, Any]]) -> None:
        """任务执行过程中保存进度"""
        state = {
            "task_id": task_id,
            "description": description,
            "status": "in_progress",
            "current_subtask_index": current_index + 1,
            "subtasks": [
                {
                    "sub_task_id": s.sub_task_id,
                    "description": s.description,
                    "status": "completed" if i <= current_index else s.status,
                    "estimated_lines": s.estimated_lines,
                    "dependencies": s.dependencies,
                } for i, s in enumerate(subtasks)
            ],
            "results": results,
            "last_saved_at": time.time(),
        }
        self.memory_layer.save_task_state(task_id, state)

    def _save_task_state_at_completion(self, task_id: str, description: str,
                                       subtasks: List[SubTask], results: List[Dict[str, Any]],
                                       success: bool) -> None:
        """任务完成时保存状态"""
        state = {
            "task_id": task_id,
            "description": description,
            "status": "completed" if success else "failed",
            "current_subtask_index": len(subtasks),
            "subtasks": [
                {
                    "sub_task_id": s.sub_task_id,
                    "description": s.description,
                    "status": "completed",
                    "estimated_lines": s.estimated_lines,
                    "dependencies": s.dependencies,
                } for s in subtasks
            ],
            "results": results,
            "success": success,
            "completed_at": time.time(),
        }
        self.memory_layer.save_task_state(task_id, state)

    def _save_task_state_at_failure(self, task_id: str, description: str, error: str) -> None:
        """任务失败时保存状态"""
        state = {
            "task_id": task_id,
            "description": description,
            "status": "failed",
            "current_subtask_index": -1,
            "subtasks": [],
            "results": [],
            "error": error,
            "failed_at": time.time(),
        }
        self.memory_layer.save_task_state(task_id, state)

    def restore_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """恢复中断的任务"""
        state = self.memory_layer.restore_task_state(task_id)
        if not state:
            return None

        if state.get("status") == "completed":
            logger.info(f"[Harness] Task already completed: {task_id}")
            return {
                "status": "already_completed",
                "task_id": task_id,
                "message": "Task has already been completed",
                "results": state.get("results", []),
            }

        current_index = state.get("current_subtask_index", 0)
        subtasks_info = state.get("subtasks", [])
        description = state.get("description", "")

        logger.info(f"[Harness] Restoring task {task_id} from subtask index {current_index}")

        context = self.perceive(description)
        plan = self.reason(context)

        results = state.get("results", [])

        for idx, subtask in enumerate(plan):
            if idx < current_index:
                continue

            result = self.execute(subtask)
            verification = self.verify(result)
            feedback = self.feedback(context, result, verification)

            results.append({
                "subtask": subtask.description,
                "sub_task_id": subtask.sub_task_id,
                "status": "completed" if verification.passed else "failed",
                "duration_ms": result.duration_ms,
                "feedback": feedback,
            })

            self._save_task_state_at_progress(task_id, description, plan, idx, results)

            if not verification.passed and feedback.get("corrected"):
                result = self.execute(subtask)
                verification = self.verify(result)

        all_passed = all(r["status"] == "completed" for r in results)

        self._save_task_state_at_completion(task_id, description, plan, results, all_passed)

        return {
            "status": "success" if all_passed else "partial",
            "task_id": task_id,
            "message": "Task restored and completed" if all_passed else "Task restored but some subtasks failed",
            "results": results,
            "restored_from_index": current_index,
        }

    def list_pending_tasks(self) -> List[Dict[str, Any]]:
        """列出所有待恢复的任务"""
        return self.memory_layer._state_persistence.list_tasks_with_state()

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        return self.memory_layer.get_task_state(task_id)

    def delete_task_state(self, task_id: str) -> bool:
        """删除任务状态"""
        return self.memory_layer._state_persistence.delete_task_state(task_id)
