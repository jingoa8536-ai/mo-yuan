"""
代码合规检查器 — Code Compliance Checker

实现FR-5.2：代码合规检查器
- 依赖方向检测：确保依赖方向符合架构约束
- 接口隔离检测：确保接口职责单一
- 开闭原则检测：确保对扩展开放，对修改关闭
- 单一职责检测：确保类/模块职责单一
- 循环依赖检测：检测模块间的循环依赖
- 自动修复策略：提取接口、下沉逻辑、添加适配器

实现Task 7：L3 - 代码合规检查器
"""

from __future__ import annotations

import ast
import re
import os
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field


logger = __import__('logging').getLogger("laap.compliance")


@dataclass
class ComplianceIssue:
    """合规问题"""
    issue_type: str
    severity: str
    message: str
    location: str
    line_number: int = 0
    suggestion: str = ""


@dataclass
class ComplianceResult:
    """合规检查结果"""
    compliant: bool
    issues: List[ComplianceIssue]
    score: float = 0.0
    summary: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DependencyGraph:
    """依赖图数据结构"""
    nodes: Set[str] = field(default_factory=set)
    edges: Dict[str, Set[str]] = field(default_factory=dict)

    def add_node(self, node: str) -> None:
        self.nodes.add(node)
        if node not in self.edges:
            self.edges[node] = set()

    def add_edge(self, from_node: str, to_node: str) -> None:
        self.add_node(from_node)
        self.add_node(to_node)
        self.edges[from_node].add(to_node)

    def get_dependencies(self, node: str) -> Set[str]:
        return self.edges.get(node, set())

    def get_dependents(self, node: str) -> Set[str]:
        dependents = set()
        for source, targets in self.edges.items():
            if node in targets:
                dependents.add(source)
        return dependents


class DependencyAnalyzer:
    """依赖分析器：分析代码依赖关系"""

    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """分析单个文件的依赖"""
        if not os.path.exists(file_path):
            return {"imports": [], "from_imports": [], "classes": [], "functions": []}

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"Failed to read file: {file_path}, error: {e}")
            return {"imports": [], "from_imports": [], "classes": [], "functions": []}

        try:
            tree = ast.parse(content)
        except SyntaxError:
            logger.warning(f"Syntax error in file: {file_path}")
            return {"imports": [], "from_imports": [], "classes": [], "functions": []}

        imports = []
        from_imports = []
        classes = []
        functions = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    from_imports.append(f"{module}.{alias.name}" if module else alias.name)
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, ast.FunctionDef):
                functions.append(node.name)
            elif isinstance(node, ast.AsyncFunctionDef):
                functions.append(node.name)

        return {
            "imports": imports,
            "from_imports": from_imports,
            "classes": classes,
            "functions": functions,
            "file_path": file_path,
        }

    def build_project_dependency_graph(self, project_dir: str) -> DependencyGraph:
        """构建项目依赖图"""
        graph = DependencyGraph()
        modules_seen = set()

        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git', 'node_modules', 'venv')]

            for file in files:
                if not file.endswith('.py'):
                    continue

                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, project_dir)
                module_name = rel_path.replace(os.sep, '.').replace('.py', '')

                if module_name.startswith('.'):
                    module_name = module_name[1:]

                graph.add_node(module_name)
                modules_seen.add(module_name)

                analysis = self.analyze_file(file_path)

                for imp in analysis['imports'] + analysis['from_imports']:
                    if imp.split('.')[0] in modules_seen:
                        graph.add_edge(module_name, imp.split('.')[0])

        return graph

    def detect_circular_dependencies(self, graph: DependencyGraph) -> List[List[str]]:
        """检测循环依赖"""
        cycles = []
        visited = set()

        def dfs(node: str, path: List[str]) -> None:
            if node in visited:
                if node in path:
                    idx = path.index(node)
                    cycles.append(path[idx:])
                return

            visited.add(node)
            path.append(node)

            for neighbor in graph.get_dependencies(node):
                dfs(neighbor, path.copy())

        for node in graph.nodes:
            if node not in visited:
                dfs(node, [])

        return cycles


class InterfaceSegregationChecker:
    """接口隔离检查器：确保接口职责单一"""

    def check(self, file_path: str) -> List[ComplianceIssue]:
        """检查接口隔离原则"""
        issues = []

        if not os.path.exists(file_path):
            return issues

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            return issues

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return issues

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append(item.name)

                if len(methods) > 10:
                    issues.append(ComplianceIssue(
                        issue_type="interface_segregation",
                        severity="warning",
                        message=f"类 {node.name} 包含 {len(methods)} 个方法，可能违反接口隔离原则",
                        location=file_path,
                        line_number=node.lineno,
                        suggestion="考虑将该类拆分为多个职责单一的接口/类",
                    ))

                public_methods = [m for m in methods if not m.startswith('_')]
                if len(public_methods) > 7:
                    issues.append(ComplianceIssue(
                        issue_type="interface_segregation",
                        severity="info",
                        message=f"类 {node.name} 公开方法过多 ({len(public_methods)} 个)",
                        location=file_path,
                        line_number=node.lineno,
                        suggestion="考虑将相关方法分组到单独的接口中",
                    ))

        return issues


class OpenClosedChecker:
    """开闭原则检查器：确保对扩展开放，对修改关闭"""

    def check(self, file_path: str) -> List[ComplianceIssue]:
        """检查开闭原则"""
        issues = []

        if not os.path.exists(file_path):
            return issues

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            return issues

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return issues

        conditional_patterns = [
            (r'(if|elif)\s+.*(type|instance|isinstance|__class__)', '类型检查'),
            (r'(if|elif)\s+.*(==|!=)\s*["\']\w+["\']', '字符串常量检查'),
            (r'(if|elif)\s+.*(\d+)', '数字常量检查'),
        ]

        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                condition_str = ast.dump(node.test)
                for pattern, desc in conditional_patterns:
                    if re.search(pattern, condition_str):
                        issues.append(ComplianceIssue(
                            issue_type="open_closed",
                            severity="warning",
                            message=f"发现 {desc} 条件分支，可能违反开闭原则",
                            location=file_path,
                            line_number=node.lineno,
                            suggestion="考虑使用多态或策略模式替代条件分支",
                        ))
                        break

        return issues


class SingleResponsibilityChecker:
    """单一职责检查器：确保类/模块职责单一"""

    def check(self, file_path: str) -> List[ComplianceIssue]:
        """检查单一职责原则"""
        issues = []

        if not os.path.exists(file_path):
            return issues

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            return issues

        lines = content.split('\n')
        total_lines = len(lines)

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return issues

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_start = node.lineno
                class_end = node.lineno
                for item in node.body:
                    class_end = max(class_end, getattr(item, 'lineno', class_end))

                class_lines = class_end - class_start + 1

                if class_lines > 200:
                    issues.append(ComplianceIssue(
                        issue_type="single_responsibility",
                        severity="error",
                        message=f"类 {node.name} 过长 ({class_lines} 行)，可能违反单一职责原则",
                        location=file_path,
                        line_number=node.lineno,
                        suggestion="考虑将该类拆分为多个职责单一的类",
                    ))

                methods = []
                attributes = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append(item.name)
                    elif isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                attributes.append(target.id)

                if len(attributes) > 15:
                    issues.append(ComplianceIssue(
                        issue_type="single_responsibility",
                        severity="warning",
                        message=f"类 {node.name} 属性过多 ({len(attributes)} 个)",
                        location=file_path,
                        line_number=node.lineno,
                        suggestion="考虑将属性分组到单独的类或数据对象中",
                    ))

                behavior_ratio = len(methods) / max(len(attributes), 1)
                if behavior_ratio < 0.5:
                    issues.append(ComplianceIssue(
                        issue_type="single_responsibility",
                        severity="warning",
                        message=f"类 {node.name} 可能是贫血模型（方法数/属性数 = {behavior_ratio:.2f}）",
                        location=file_path,
                        line_number=node.lineno,
                        suggestion="考虑将相关行为下沉到该类中",
                    ))

        return issues


class DependencyDirectionChecker:
    """依赖方向检查器：确保依赖方向符合架构约束"""

    def __init__(self, allowed_directions: Optional[Dict[str, List[str]]] = None):
        self.allowed_directions = allowed_directions or {}

    def check(self, dependency_graph: DependencyGraph) -> List[ComplianceIssue]:
        """检查依赖方向"""
        issues = []

        for source, targets in dependency_graph.edges.items():
            allowed = self.allowed_directions.get(source, [])

            for target in targets:
                if allowed and target not in allowed:
                    issues.append(ComplianceIssue(
                        issue_type="dependency_direction",
                        severity="error",
                        message=f"非法依赖方向: {source} -> {target}",
                        location=f"模块: {source}",
                        line_number=0,
                        suggestion=f"{source} 不应依赖 {target}，请检查架构约束",
                    ))

        return issues


class ArchitectureDriftDetector:
    """架构漂移检测器：检测代码与目标架构的偏离"""

    def __init__(self, target_architecture: Optional[Dict[str, Any]] = None):
        self.target_architecture = target_architecture or {}

    def detect(self, project_dir: str) -> List[ComplianceIssue]:
        """检测架构漂移"""
        issues = []

        target_patterns = self.target_architecture.get("patterns", [])
        target_layers = self.target_architecture.get("layers", [])
        target_constraints = self.target_architecture.get("constraints", [])

        dependency_analyzer = DependencyAnalyzer()
        graph = dependency_analyzer.build_project_dependency_graph(project_dir)

        for constraint in target_constraints:
            if constraint.get("type") == "layer_dependency":
                source_layer = constraint.get("source")
                allowed_layers = constraint.get("allowed")

                for node in graph.nodes:
                    if source_layer and source_layer in node:
                        for dep in graph.get_dependencies(node):
                            if allowed_layers and dep not in allowed_layers:
                                issues.append(ComplianceIssue(
                                    issue_type="architecture_drift",
                                    severity="error",
                                    message=f"架构漂移: {node} 依赖 {dep}，违反分层约束",
                                    location=f"模块: {node}",
                                    line_number=0,
                                    suggestion=f"{source_layer}层模块不应依赖非{allowed_layers}层模块",
                                ))

        for pattern in target_patterns:
            pattern_name = pattern.get("name", "")
            quality_gates = pattern.get("quality_gates", [])

            for gate in quality_gates:
                if "循环依赖" in gate:
                    cycles = dependency_analyzer.detect_circular_dependencies(graph)
                    if cycles:
                        for cycle in cycles:
                            issues.append(ComplianceIssue(
                                issue_type="architecture_drift",
                                severity="error",
                                message=f"架构漂移: 检测到循环依赖 {cycle}",
                                location=f"模式: {pattern_name}",
                                line_number=0,
                                suggestion=f"修复循环依赖以符合 {pattern_name} 模式要求",
                            ))

        return issues


class AutoFixStrategy:
    """自动修复策略：提取接口、下沉逻辑、添加适配器"""

    def extract_interface(self, class_name: str, methods: List[str]) -> str:
        """提取接口"""
        interface_name = f"I{class_name}"
        method_signatures = []

        for method in methods[:5]:
            method_signatures.append(f"    def {method}(self): ...")

        return f"""from abc import ABC, abstractmethod

class {interface_name}(ABC):
    \"\"\"{class_name} 接口定义\"\"\"
{chr(10).join(method_signatures)}
"""

    def sink_logic(self, class_name: str, logic_description: str) -> str:
        """下沉逻辑到实体"""
        return f"""class {class_name}:
    \"\"\"{class_name} - 包含业务逻辑的实体\"\"\"
    
    def {self._generate_method_name(logic_description)}(self):
        \"\"\"{logic_description}\"\"\"
        pass
"""

    def add_adapter(self, source_class: str, target_interface: str) -> str:
        """添加适配器"""
        adapter_name = f"{source_class}To{target_interface}Adapter"
        return f"""class {adapter_name}:
    \"\"\"{source_class} 到 {target_interface} 的适配器\"\"\"
    
    def __init__(self, {source_class.lower()}: {source_class}):
        self.{source_class.lower()} = {source_class.lower()}
    
    def adapt(self):
        \"\"\"转换为目标接口\"\"\"
        pass
"""

    def _generate_method_name(self, description: str) -> str:
        tokens = re.findall(r'[a-zA-Z\u4e00-\u9fff]+', description)
        if tokens:
            return '_'.join(t.lower() for t in tokens[:3])
        return "process"

    def generate_fix(self, issue: ComplianceIssue) -> Optional[str]:
        """根据问题生成修复建议"""
        if issue.issue_type == "interface_segregation":
            match = re.search(r'类 (\w+)', issue.message)
            if match:
                return self.extract_interface(match.group(1), ["method1", "method2", "method3"])
        elif issue.issue_type == "single_responsibility":
            match = re.search(r'类 (\w+)', issue.message)
            if match:
                return self.sink_logic(match.group(1), "业务逻辑描述")
        elif issue.issue_type == "open_closed":
            return "建议使用策略模式或工厂模式替代条件分支"
        elif issue.issue_type == "dependency_direction":
            return "建议通过接口反转依赖方向"

        return None


class CodeComplianceChecker:
    """代码合规检查器：综合检查所有合规性问题"""

    def __init__(self, project_root: str = ""):
        self.project_root = project_root or os.getcwd()
        self.dependency_analyzer = DependencyAnalyzer()
        self.interface_checker = InterfaceSegregationChecker()
        self.open_closed_checker = OpenClosedChecker()
        self.single_responsibility_checker = SingleResponsibilityChecker()
        self.dependency_direction_checker = DependencyDirectionChecker()
        self.architecture_drift_detector = ArchitectureDriftDetector()
        self.auto_fix_strategy = AutoFixStrategy()

    def check_file(self, file_path: str) -> ComplianceResult:
        """检查单个文件的合规性"""
        issues = []

        issues.extend(self.interface_checker.check(file_path))
        issues.extend(self.open_closed_checker.check(file_path))
        issues.extend(self.single_responsibility_checker.check(file_path))

        compliant = len([i for i in issues if i.severity == "error"]) == 0
        score = self._calculate_score(issues)

        return ComplianceResult(
            compliant=compliant,
            issues=issues,
            score=score,
            summary={
                "file": file_path,
                "total_issues": len(issues),
                "errors": len([i for i in issues if i.severity == "error"]),
                "warnings": len([i for i in issues if i.severity == "warning"]),
                "infos": len([i for i in issues if i.severity == "info"]),
            },
        )

    def check_project(self) -> ComplianceResult:
        """检查整个项目的合规性"""
        issues = []
        files_checked = 0

        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git', 'node_modules', 'venv', 'tests')]

            for file in files:
                if not file.endswith('.py'):
                    continue

                file_path = os.path.join(root, file)
                result = self.check_file(file_path)
                issues.extend(result.issues)
                files_checked += 1

        if files_checked == 0:
            issues.append(ComplianceIssue(
                issue_type="no_files",
                severity="warning",
                message="未检测到Python文件，请确认项目路径是否正确",
                location="项目级别",
                line_number=0,
                suggestion="检查项目根目录路径或添加Python源代码文件",
            ))

        dependency_graph = self.dependency_analyzer.build_project_dependency_graph(self.project_root)
        dependency_issues = self.dependency_direction_checker.check(dependency_graph)
        issues.extend(dependency_issues)

        cycles = self.dependency_analyzer.detect_circular_dependencies(dependency_graph)
        for cycle in cycles:
            issues.append(ComplianceIssue(
                issue_type="circular_dependency",
                severity="error",
                message=f"检测到循环依赖: {' -> '.join(cycle)}",
                location="项目级别",
                line_number=0,
                suggestion="重构模块依赖以消除循环",
            ))

        drift_issues = self.architecture_drift_detector.detect(self.project_root)
        issues.extend(drift_issues)

        compliant = len([i for i in issues if i.severity == "error"]) == 0
        score = self._calculate_score(issues)

        if files_checked == 0:
            score = 0.0

        return ComplianceResult(
            compliant=compliant,
            issues=issues,
            score=score,
            summary={
                "files_checked": files_checked,
                "total_issues": len(issues),
                "errors": len([i for i in issues if i.severity == "error"]),
                "warnings": len([i for i in issues if i.severity == "warning"]),
                "infos": len([i for i in issues if i.severity == "info"]),
                "circular_dependencies": len(cycles),
                "modules": len(dependency_graph.nodes),
            },
        )

    def detect_circular_dependencies(self) -> List[List[str]]:
        """检测项目中的循环依赖"""
        graph = self.dependency_analyzer.build_project_dependency_graph(self.project_root)
        return self.dependency_analyzer.detect_circular_dependencies(graph)

    def detect_anemic_models(self) -> List[Dict[str, Any]]:
        """检测贫血模型（实体行为少于属性一半）"""
        results = []

        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git', 'node_modules', 'venv', 'tests')]

            for file in files:
                if not file.endswith('.py'):
                    continue

                file_path = os.path.join(root, file)
                issues = self.single_responsibility_checker.check(file_path)

                for issue in issues:
                    if issue.issue_type == "single_responsibility" and "贫血模型" in issue.message:
                        match = re.search(r'类 (\w+)', issue.message)
                        if match:
                            results.append({
                                "file": file_path,
                                "class": match.group(1),
                                "issue": issue.message,
                                "suggestion": issue.suggestion,
                            })

        return results

    def generate_fix_suggestions(self, issues: List[ComplianceIssue]) -> Dict[str, str]:
        """为问题生成修复建议"""
        suggestions = {}

        for issue in issues:
            if issue.severity == "error":
                fix = self.auto_fix_strategy.generate_fix(issue)
                if fix:
                    suggestions[f"{issue.location}:{issue.line_number}"] = fix

        return suggestions

    def _calculate_score(self, issues: List[ComplianceIssue]) -> float:
        """计算合规分数"""
        error_penalty = sum(0.1 for i in issues if i.severity == "error")
        warning_penalty = sum(0.03 for i in issues if i.severity == "warning")
        info_penalty = sum(0.01 for i in issues if i.severity == "info")

        return max(0.0, min(1.0, 1.0 - error_penalty - warning_penalty - info_penalty))

    def generate_report(self, result: ComplianceResult) -> str:
        """生成合规检查报告"""
        lines = [
            "=" * 60,
            "代码合规检查报告",
            "=" * 60,
            "",
            f"项目根目录: {self.project_root}",
            f"合规状态: {'✓ 合规' if result.compliant else '✗ 不合规'}",
            f"合规分数: {result.score:.2f}",
            "",
        ]

        summary = result.summary
        if summary:
            lines.append("摘要:")
            for key, value in summary.items():
                lines.append(f"  {key}: {value}")
            lines.append("")

        if result.issues:
            lines.append("问题详情:")
            for i, issue in enumerate(result.issues, 1):
                severity_icon = {"error": "✗", "warning": "⚠", "info": "ℹ"}.get(issue.severity, "?")
                lines.append(f"  {i}. [{severity_icon}] {issue.issue_type}: {issue.message}")
                lines.append(f"     位置: {issue.location}:{issue.line_number}")
                if issue.suggestion:
                    lines.append(f"     建议: {issue.suggestion}")
                lines.append("")

        return "\n".join(lines)
