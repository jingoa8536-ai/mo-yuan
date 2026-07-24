"""
反馈引擎 — Feedback Engine

实现FR-6：自修正循环和反馈层
- 自修正循环：整合验证层和合规检查器的反馈，自动检测和修复错误
- 模式学习器：记录成功和失败的模式，支持模式检索和应用
- 经验积累器：将经验存入长期记忆，支持经验查询和应用
- 质量回溯：分析历史任务的质量趋势

实现Task 8：L3 - 自修正循环和反馈层
"""

from __future__ import annotations

import os
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


logger = __import__('logging').getLogger("laap.feedback")


@dataclass
class PatternRecord:
    """模式记录"""
    pattern_id: str
    pattern_type: str
    context: Dict[str, Any]
    result: str
    score: float
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperienceRecord:
    """经验记录"""
    experience_id: str
    task_id: str
    intent: str
    description: str
    success: bool
    score: float
    duration_ms: float
    issues: List[Dict[str, Any]] = field(default_factory=list)
    corrections: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityMetric:
    """质量指标"""
    period: str
    total_tasks: int
    success_rate: float
    avg_score: float
    avg_duration_ms: float
    common_issues: List[str] = field(default_factory=list)


class PatternLearner:
    """模式学习器：从经验中学习成功和失败的模式"""

    def __init__(self, project_root: str = ""):
        self.project_root = project_root or os.getcwd()
        self._patterns: List[PatternRecord] = []
        self._pattern_index: Dict[str, List[int]] = {}
        self._load_patterns()

    def learn(self, context: Dict[str, Any], result: str, score: float,
              metadata: Optional[Dict[str, Any]] = None) -> None:
        """学习模式"""
        pattern_id = self._generate_pattern_id(context)
        pattern_type = context.get("intent", "unknown")

        record = PatternRecord(
            pattern_id=pattern_id,
            pattern_type=pattern_type,
            context=context,
            result=result,
            score=score,
            metadata=metadata or {},
        )

        self._patterns.append(record)
        self._update_index(record)
        self._save_patterns()

        logger.info(f"[PatternLearner] Learned pattern: {pattern_id}")

    def _generate_pattern_id(self, context: Dict[str, Any]) -> str:
        """生成模式ID"""
        intent = context.get("intent", "unknown")
        keywords = context.get("keywords", [])[:3]
        keyword_str = "_".join(keywords) if keywords else "generic"
        return f"{intent}_{keyword_str}_{int(time.time())}"

    def _update_index(self, record: PatternRecord) -> None:
        """更新模式索引"""
        for keyword in record.context.get("keywords", []):
            if keyword not in self._pattern_index:
                self._pattern_index[keyword] = []
            self._pattern_index[keyword].append(len(self._patterns) - 1)

        if record.pattern_type not in self._pattern_index:
            self._pattern_index[record.pattern_type] = []
        self._pattern_index[record.pattern_type].append(len(self._patterns) - 1)

    def retrieve_patterns(self, query: Dict[str, Any], top_n: int = 5) -> List[PatternRecord]:
        """检索匹配的模式"""
        keywords = query.get("keywords", [])
        intent = query.get("intent", "")

        candidate_indices = set()
        for keyword in keywords:
            if keyword in self._pattern_index:
                candidate_indices.update(self._pattern_index[keyword])
        if intent and intent in self._pattern_index:
            candidate_indices.update(self._pattern_index[intent])

        if not candidate_indices:
            return []

        candidates = []
        for idx in candidate_indices:
            if idx < len(self._patterns):
                candidates.append(self._patterns[idx])

        candidates.sort(key=lambda x: x.score, reverse=True)
        return candidates[:top_n]

    def get_success_patterns(self, intent: str = "", top_n: int = 5) -> List[PatternRecord]:
        """获取成功的模式"""
        filtered = [p for p in self._patterns if p.result == "success"]
        if intent:
            filtered = [p for p in filtered if p.pattern_type == intent]
        filtered.sort(key=lambda x: x.score, reverse=True)
        return filtered[:top_n]

    def get_failure_patterns(self, intent: str = "", top_n: int = 5) -> List[PatternRecord]:
        """获取失败的模式"""
        filtered = [p for p in self._patterns if p.result == "failure"]
        if intent:
            filtered = [p for p in filtered if p.pattern_type == intent]
        filtered.sort(key=lambda x: x.score)
        return filtered[:top_n]

    def get_pattern_statistics(self) -> Dict[str, Any]:
        """获取模式统计信息"""
        success_count = sum(1 for p in self._patterns if p.result == "success")
        failure_count = sum(1 for p in self._patterns if p.result == "failure")
        total_patterns = len(self._patterns)

        return {
            "total_patterns": total_patterns,
            "success_patterns": success_count,
            "failure_patterns": failure_count,
            "success_rate": success_count / max(total_patterns, 1),
            "avg_score": sum(p.score for p in self._patterns) / max(total_patterns, 1),
            "index_size": len(self._pattern_index),
        }

    def _load_patterns(self) -> None:
        """加载模式"""
        patterns_path = os.path.join(self.project_root, ".laap", "patterns.json")
        if os.path.exists(patterns_path):
            try:
                with open(patterns_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._patterns = [PatternRecord(**p) for p in data.get("patterns", [])]
                self._build_index()
                logger.info(f"[PatternLearner] Loaded {len(self._patterns)} patterns")
            except Exception as e:
                logger.warning(f"Failed to load patterns: {e}")

    def _save_patterns(self) -> None:
        """保存模式"""
        patterns_path = os.path.join(self.project_root, ".laap", "patterns.json")
        os.makedirs(os.path.dirname(patterns_path), exist_ok=True)
        with open(patterns_path, 'w', encoding='utf-8') as f:
            json.dump({
                "patterns": [p.__dict__ for p in self._patterns],
                "saved_at": time.time(),
            }, f, indent=2, ensure_ascii=False)

    def _build_index(self) -> None:
        """构建索引"""
        self._pattern_index = {}
        for idx, record in enumerate(self._patterns):
            for keyword in record.context.get("keywords", []):
                if keyword not in self._pattern_index:
                    self._pattern_index[keyword] = []
                self._pattern_index[keyword].append(idx)
            if record.pattern_type not in self._pattern_index:
                self._pattern_index[record.pattern_type] = []
            self._pattern_index[record.pattern_type].append(idx)


class ExperienceAccumulator:
    """经验积累器：积累和管理经验"""

    def __init__(self, project_root: str = ""):
        self.project_root = project_root or os.getcwd()
        self._experiences: List[ExperienceRecord] = []
        self._load_experiences()

    def accumulate(self, experience: Dict[str, Any]) -> None:
        """积累经验"""
        experience_id = experience.get("experience_id") or f"exp_{int(time.time())}"

        record = ExperienceRecord(
            experience_id=experience_id,
            task_id=experience.get("task_id", ""),
            intent=experience.get("intent", ""),
            description=experience.get("description", ""),
            success=experience.get("success", False),
            score=experience.get("score", 0.0),
            duration_ms=experience.get("duration_ms", 0),
            issues=experience.get("issues", []),
            corrections=experience.get("corrections", []),
            metadata=experience.get("metadata", {}),
        )

        self._experiences.append(record)
        self._save_experiences()

        logger.info(f"[ExperienceAccumulator] Accumulated experience: {experience_id}")

    def query_experiences(self, filters: Optional[Dict[str, Any]] = None) -> List[ExperienceRecord]:
        """查询经验"""
        filtered = self._experiences.copy()

        if filters:
            if "intent" in filters:
                filtered = [e for e in filtered if e.intent == filters["intent"]]
            if "success" in filters:
                filtered = [e for e in filtered if e.success == filters["success"]]
            if "min_score" in filters:
                filtered = [e for e in filtered if e.score >= filters["min_score"]]
            if "keyword" in filters:
                keyword = filters["keyword"].lower()
                filtered = [e for e in filtered if keyword in e.description.lower()]

        filtered.sort(key=lambda x: x.timestamp, reverse=True)
        return filtered

    def get_recent_experiences(self, limit: int = 10) -> List[ExperienceRecord]:
        """获取最近的经验"""
        sorted_experiences = sorted(self._experiences, key=lambda x: x.timestamp, reverse=True)
        return sorted_experiences[:limit]

    def get_experience_statistics(self) -> Dict[str, Any]:
        """获取经验统计信息"""
        total_experiences = len(self._experiences)
        success_count = sum(1 for e in self._experiences if e.success)
        avg_score = sum(e.score for e in self._experiences) / max(total_experiences, 1)
        avg_duration = sum(e.duration_ms for e in self._experiences) / max(total_experiences, 1)

        intent_stats = {}
        for e in self._experiences:
            if e.intent not in intent_stats:
                intent_stats[e.intent] = {"total": 0, "success": 0, "avg_score": 0}
            intent_stats[e.intent]["total"] += 1
            intent_stats[e.intent]["success"] += 1 if e.success else 0
            intent_stats[e.intent]["avg_score"] += e.score

        for intent, stats in intent_stats.items():
            stats["success_rate"] = stats["success"] / stats["total"]
            stats["avg_score"] = stats["avg_score"] / stats["total"]

        return {
            "total_experiences": total_experiences,
            "success_count": success_count,
            "failure_count": total_experiences - success_count,
            "success_rate": success_count / max(total_experiences, 1),
            "avg_score": avg_score,
            "avg_duration_ms": avg_duration,
            "intent_stats": intent_stats,
        }

    def get_common_issues(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取常见问题"""
        issue_counts: Dict[str, int] = {}

        for experience in self._experiences:
            for issue in experience.issues:
                issue_key = issue.get("message", "") or issue.get("description", "")
                if issue_key:
                    issue_counts[issue_key] = issue_counts.get(issue_key, 0) + 1

        sorted_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)
        return [
            {"issue": issue, "count": count}
            for issue, count in sorted_issues[:limit]
        ]

    def apply_experience(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """应用经验到当前上下文"""
        similar_experiences = self.query_experiences({
            "intent": context.get("intent", ""),
            "success": True,
            "min_score": 0.7,
        })[:5]

        if not similar_experiences:
            return {"applied": False, "message": "没有找到适用的经验"}

        recommendations = []
        for exp in similar_experiences:
            if exp.corrections:
                recommendations.extend(exp.corrections)

        return {
            "applied": True,
            "message": f"应用了 {len(similar_experiences)} 条经验",
            "recommendations": list(set(recommendations))[:10],
            "experience_ids": [e.experience_id for e in similar_experiences],
        }

    def _load_experiences(self) -> None:
        """加载经验"""
        experiences_path = os.path.join(self.project_root, ".laap", "experiences.json")
        if os.path.exists(experiences_path):
            try:
                with open(experiences_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._experiences = [ExperienceRecord(**e) for e in data.get("experiences", [])]
                logger.info(f"[ExperienceAccumulator] Loaded {len(self._experiences)} experiences")
            except Exception as e:
                logger.warning(f"Failed to load experiences: {e}")

    def _save_experiences(self) -> None:
        """保存经验"""
        experiences_path = os.path.join(self.project_root, ".laap", "experiences.json")
        os.makedirs(os.path.dirname(experiences_path), exist_ok=True)
        with open(experiences_path, 'w', encoding='utf-8') as f:
            json.dump({
                "experiences": [e.__dict__ for e in self._experiences],
                "saved_at": time.time(),
            }, f, indent=2, ensure_ascii=False)


class QualityTrendAnalyzer:
    """质量趋势分析器：分析历史任务的质量趋势"""

    def __init__(self, experience_accumulator: ExperienceAccumulator):
        self.experience_accumulator = experience_accumulator

    def analyze_trend(self, period: str = "all") -> QualityMetric:
        """分析质量趋势"""
        experiences = self.experience_accumulator._experiences

        if period == "day":
            cutoff = time.time() - 24 * 3600
            experiences = [e for e in experiences if e.timestamp >= cutoff]
        elif period == "week":
            cutoff = time.time() - 7 * 24 * 3600
            experiences = [e for e in experiences if e.timestamp >= cutoff]
        elif period == "month":
            cutoff = time.time() - 30 * 24 * 3600
            experiences = [e for e in experiences if e.timestamp >= cutoff]

        if not experiences:
            return QualityMetric(
                period=period,
                total_tasks=0,
                success_rate=0.0,
                avg_score=0.0,
                avg_duration_ms=0.0,
            )

        total_tasks = len(experiences)
        success_count = sum(1 for e in experiences if e.success)
        avg_score = sum(e.score for e in experiences) / total_tasks
        avg_duration = sum(e.duration_ms for e in experiences) / total_tasks

        common_issues = self.experience_accumulator.get_common_issues(5)
        common_issue_strings = [str(issue["issue"]) for issue in common_issues]

        return QualityMetric(
            period=period,
            total_tasks=total_tasks,
            success_rate=success_count / total_tasks,
            avg_score=avg_score,
            avg_duration_ms=avg_duration,
            common_issues=common_issue_strings,
        )

    def generate_trend_report(self) -> str:
        """生成趋势报告"""
        periods = ["day", "week", "month", "all"]
        metrics = {}

        for period in periods:
            metrics[period] = self.analyze_trend(period)

        lines = [
            "=" * 60,
            "质量趋势报告",
            "=" * 60,
            "",
        ]

        period_names = {
            "day": "今日",
            "week": "本周",
            "month": "本月",
            "all": "全部",
        }

        for period, metric in metrics.items():
            lines.append(f"{period_names[period]}:")
            lines.append(f"  任务总数: {metric.total_tasks}")
            lines.append(f"  成功率: {metric.success_rate:.1%}")
            lines.append(f"  平均分数: {metric.avg_score:.2f}")
            lines.append(f"  平均耗时: {metric.avg_duration_ms:.0f}ms")
            if metric.common_issues:
                lines.append(f"  常见问题: {', '.join(metric.common_issues[:3])}")
            lines.append("")

        return "\n".join(lines)

    def get_improvement_suggestions(self) -> List[str]:
        """获取改进建议"""
        suggestions = []

        metric = self.analyze_trend("all")
        if metric.success_rate < 0.7:
            suggestions.append("提高任务成功率，当前成功率较低")

        if metric.avg_score < 0.6:
            suggestions.append("提高代码质量分数，当前质量分数较低")

        if metric.avg_duration_ms > 60000:
            suggestions.append("优化任务执行时间，当前平均耗时较长")

        common_issues = self.experience_accumulator.get_common_issues(3)
        for issue in common_issues:
            suggestions.append(f"解决常见问题: {issue['issue']}")

        return suggestions


class SelfCorrectionLoop:
    """自修正循环：自动检测和修复错误"""

    def __init__(self):
        self._correction_rules = {
            "syntax_error": self._fix_syntax_error,
            "test_failure": self._fix_test_failure,
            "import_error": self._fix_import_error,
            "type_error": self._fix_type_error,
            "circular_dependency": self._fix_circular_dependency,
            "anemic_model": self._fix_anemic_model,
            "interface_segregation": self._fix_interface_segregation,
            "open_closed": self._fix_open_closed,
            "single_responsibility": self._fix_single_responsibility,
        }

    def correct(self, issue: Dict[str, Any]) -> str:
        """根据问题类型生成修复方案"""
        issue_type = issue.get("issue_type", "") or issue.get("type", "")
        message = issue.get("message", "")

        for rule_type, fix_func in self._correction_rules.items():
            if rule_type in issue_type.lower() or rule_type in message.lower():
                return fix_func(issue)

        return self._fix_generic(issue)

    def _fix_syntax_error(self, issue: Dict[str, Any]) -> str:
        """修复语法错误"""
        return "检查代码语法，确保括号匹配、缩进正确、语句完整。建议使用IDE语法检查功能。"

    def _fix_test_failure(self, issue: Dict[str, Any]) -> str:
        """修复测试失败"""
        return "分析测试失败原因，检查被测试代码的返回值和行为是否符合预期。建议先编写失败测试，再实现功能。"

    def _fix_import_error(self, issue: Dict[str, Any]) -> str:
        """修复导入错误"""
        return "检查导入语句，确保模块路径正确、依赖已安装。建议使用绝对导入而非相对导入。"

    def _fix_type_error(self, issue: Dict[str, Any]) -> str:
        """修复类型错误"""
        return "检查变量类型，确保函数参数类型匹配。建议使用类型注解和mypy进行静态类型检查。"

    def _fix_circular_dependency(self, issue: Dict[str, Any]) -> str:
        """修复循环依赖"""
        return "重构模块依赖，提取公共接口或使用依赖注入。建议创建中间接口层解耦依赖。"

    def _fix_anemic_model(self, issue: Dict[str, Any]) -> str:
        """修复贫血模型"""
        return "将业务逻辑下沉到实体类中，使实体拥有行为而非仅仅是数据容器。"

    def _fix_interface_segregation(self, issue: Dict[str, Any]) -> str:
        """修复接口隔离问题"""
        return "将大接口拆分为多个小接口，每个接口只包含相关方法。建议遵循接口隔离原则。"

    def _fix_open_closed(self, issue: Dict[str, Any]) -> str:
        """修复开闭原则问题"""
        return "使用多态或策略模式替代条件分支，使系统对扩展开放、对修改关闭。"

    def _fix_single_responsibility(self, issue: Dict[str, Any]) -> str:
        """修复单一职责问题"""
        return "将类拆分为多个职责单一的类，每个类只负责一个功能领域。"

    def _fix_generic(self, issue: Dict[str, Any]) -> str:
        """通用修复方案"""
        message = issue.get("message", "")
        return f"分析问题: {message}。建议参考相关最佳实践进行修复。"

    def analyze_and_fix(self, issues: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析多个问题并生成修复方案"""
        corrections = []
        grouped_issues = {}

        for issue in issues:
            issue_type = issue.get("issue_type", "unknown")
            if issue_type not in grouped_issues:
                grouped_issues[issue_type] = []
            grouped_issues[issue_type].append(issue)

        for issue_type, issue_list in grouped_issues.items():
            correction = {
                "issue_type": issue_type,
                "count": len(issue_list),
                "examples": [i.get("message", "") for i in issue_list[:3]],
                "fix": self.correct(issue_list[0]),
            }
            corrections.append(correction)

        return {
            "total_issues": len(issues),
            "issue_types": len(grouped_issues),
            "corrections": corrections,
        }


class FeedbackEngine:
    """反馈引擎：综合管理自修正、模式学习和经验积累"""

    def __init__(self, project_root: str = ""):
        self.project_root = project_root or os.getcwd()
        self.self_correction = SelfCorrectionLoop()
        self.pattern_learner = PatternLearner(project_root)
        self.experience_accumulator = ExperienceAccumulator(project_root)
        self.quality_trend = QualityTrendAnalyzer(self.experience_accumulator)

    def process_feedback(self, context: Dict[str, Any], execution_result: Dict[str, Any],
                         verification_result: Dict[str, Any]) -> Dict[str, Any]:
        """处理反馈"""
        result = {
            "corrected": False,
            "corrections": [],
            "learned": False,
            "accumulated": False,
        }

        issues = verification_result.get("issues", []) or []

        if not verification_result.get("passed", True) and issues:
            correction_result = self.self_correction.analyze_and_fix(issues)
            result["corrected"] = True
            result["corrections"] = correction_result["corrections"]

        pattern_result = "success" if verification_result.get("passed", False) else "failure"
        pattern_score = verification_result.get("score", 0.0)

        self.pattern_learner.learn(context, pattern_result, pattern_score)
        result["learned"] = True

        experience_data = {
            "task_id": context.get("task_id", ""),
            "intent": context.get("intent", ""),
            "description": context.get("description", ""),
            "success": verification_result.get("passed", False),
            "score": pattern_score,
            "duration_ms": execution_result.get("duration_ms", 0),
            "issues": issues,
            "corrections": [c.get("fix", "") for c in result.get("corrections", [])],
        }
        self.experience_accumulator.accumulate(experience_data)
        result["accumulated"] = True

        return result

    def get_quality_report(self) -> str:
        """获取质量报告"""
        return self.quality_trend.generate_trend_report()

    def get_improvement_suggestions(self) -> List[str]:
        """获取改进建议"""
        return self.quality_trend.get_improvement_suggestions()

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "pattern_stats": self.pattern_learner.get_pattern_statistics(),
            "experience_stats": self.experience_accumulator.get_experience_statistics(),
        }

    def apply_learning(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """应用学到的模式和经验"""
        pattern_result = self.pattern_learner.retrieve_patterns(context, top_n=3)
        experience_result = self.experience_accumulator.apply_experience(context)

        recommendations = []
        for pattern in pattern_result:
            recommendations.append(f"参考模式 {pattern.pattern_id}: {pattern.context.get('description', '')[:50]}")

        if experience_result.get("recommendations"):
            recommendations.extend(experience_result["recommendations"])

        return {
            "patterns_found": len(pattern_result),
            "experience_applied": experience_result.get("applied", False),
            "recommendations": recommendations[:10],
        }
