"""
risk_dashboard.py — LAAP Harness 风险状态仪表盘
==================================================

输出 7 项工程性风险的实时状态（resolved/partial/open）：

1. 数据库规模瓶颈 — LSM-Tree 写入路径（WAL/MemTable/SSTable）
2. 风格矩阵硬编码 — StyleEmbeddingSpace 向量化
3. Word2Vec 语料过小 — ExternalEmbeddingProvider 替代 random.seed(42)
4. 因果引擎简化 — 概率传播 + 贝叶斯后验 abduction
5. 世界模型未完成 — 格式塔验证函数 + counterfactual 干预应用
6. RSI 测试缺失 — 真实 pytest 子进程替代 return True 占位
7. 对齐守卫可绕过性 — 符号链接 realpath 解析 + 不可变哈希注册表

支持 markdown / json 双格式报告输出。
"""

import os
import re
import ast
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple


class RiskDashboard:
    """LAAP Harness 风险状态仪表盘。

    检测 7 项工程性风险的消解状态，输出 resolved/partial/open 三级状态。

    状态判定规则：
    - resolved: 所有核心检测点都已实现
    - partial:  部分实现，存在占位代码
    - open:     未实现或仍含原占位代码
    """

    RISK_META: Dict[int, Dict[str, str]] = {
        1: {
            "key": "risk_1_database_scale",
            "name": "数据库规模瓶颈",
            "description": "LSM-Tree 写入路径（WAL/MemTable/SSTable）替代 O(n) bisect.insort",
        },
        2: {
            "key": "risk_2_style_matrix",
            "name": "风格矩阵硬编码",
            "description": "StyleEmbeddingSpace 向量化替代硬编码 STYLE_SIMILARITY_MAP",
        },
        3: {
            "key": "risk_3_word2vec",
            "name": "Word2Vec 语料过小",
            "description": "ExternalEmbeddingProvider 替代 random.seed(42) 伪向量",
        },
        4: {
            "key": "risk_4_causal_engine",
            "name": "因果引擎简化",
            "description": "概率传播 + 贝叶斯后验 abduction 替代边强度乘积近似",
        },
        5: {
            "key": "risk_5_world_model",
            "name": "世界模型未完成",
            "description": "格式塔验证函数 + counterfactual 干预应用实现",
        },
        6: {
            "key": "risk_6_rsi_test",
            "name": "RSI 测试缺失",
            "description": "真实 pytest 子进程替代 return True 占位",
        },
        7: {
            "key": "risk_7_alignment_guard",
            "name": "对齐守卫可绕过性",
            "description": "符号链接 realpath 解析 + 不可变哈希注册表",
        },
    }

    STATUS_ICON = {
        "resolved": "✅",
        "partial": "⚠️",
        "open": "❌",
    }

    def __init__(self, harness_root: str = None, agi_root: str = None):
        """初始化风险仪表盘。

        Args:
            harness_root: laap_coding/core 目录路径（默认 D:\\LAAP\\harness\\laap_coding\\core）
            agi_root:     -harness-v2-agi/src 目录路径
                          （默认 D:\\LAAP\\.github\\harness\\-harness-v2-agi\\src）
        """
        self.harness_root = harness_root or r"D:\LAAP\harness\laap_coding\core"
        self.agi_root = agi_root or r"D:\LAAP\.github\harness\-harness-v2-agi\src"
        self._evidence: Dict[str, List[str]] = {}

    # ------------------------------------------------------------------ #
    # 辅助方法
    # ------------------------------------------------------------------ #

    def _read_file(self, path: str) -> Optional[str]:
        """安全读取文件内容，失败返回 None。"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except (FileNotFoundError, OSError, UnicodeDecodeError):
            return None

    def _strip_comments_and_docstrings(self, content: str) -> str:
        """移除 Python 三引号 docstring 与整行注释，便于代码模式匹配。

        注意：这是启发式方法，不处理字符串字面量内的 # 字符。对于本模块
        检测的特定模式（random.seed(42) 等）已足够。
        """
        cleaned = re.sub(r'""".*?"""', "", content, flags=re.DOTALL)
        cleaned = re.sub(r"'''.*?'''", "", cleaned, flags=re.DOTALL)
        lines = []
        for line in cleaned.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            lines.append(line)
        return "\n".join(lines)

    def _code_contains(self, path: str, pattern: str) -> bool:
        """检查 pattern 是否出现在实际代码中（排除注释与 docstring）。"""
        content = self._read_file(path)
        if content is None:
            return False
        cleaned = self._strip_comments_and_docstrings(content)
        return pattern in cleaned

    def _content_contains_any(self, path: str, patterns: List[str]) -> Tuple[bool, Optional[str]]:
        """检查文件内容是否包含任一 pattern（原始内容匹配，含注释）。

        Returns:
            (是否命中, 命中的 pattern)
        """
        content = self._read_file(path)
        if content is None:
            return False, None
        for p in patterns:
            if p in content:
                return True, p
        return False, None

    def _is_trivial_return_value(self, node) -> bool:
        """判断 AST return 值节点是否为平凡占位值。

        覆盖：True / None / 1.0 / 空容器 / 由上述组成的元组
        （如 `return True`、`return None`、`return True, []`）。
        """
        if isinstance(node, ast.Constant):
            return node.value in (True, None, 1.0)
        if isinstance(node, (ast.List, ast.Set)):
            return len(node.elts) == 0
        if isinstance(node, ast.Dict):
            return len(node.keys) == 0
        if isinstance(node, ast.Tuple):
            return all(self._is_trivial_return_value(elt) for elt in node.elts)
        return False

    def _is_function_placeholder(self, path: str, func_name: str) -> Optional[bool]:
        """检查函数体是否为占位代码（return 1.0 / return True / pass / return None /
        return True, [] 等）。

        Returns:
            True  — 函数体是占位
            False — 函数有实际逻辑
            None  — 函数不存在或文件无法解析
        """
        source = self._read_file(path)
        if source is None:
            return None
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
                body = list(node.body)
                # 跳过 docstring
                if (
                    body
                    and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)
                ):
                    body = body[1:]
                if len(body) == 0:
                    return True
                if len(body) == 1:
                    stmt = body[0]
                    if isinstance(stmt, ast.Pass):
                        return True
                    if isinstance(stmt, ast.Return):
                        if stmt.value is None or self._is_trivial_return_value(stmt.value):
                            return True
                    return False
                return False
        return None

    def _function_contains_pattern(self, path: str, func_name: str, pattern: str) -> Optional[bool]:
        """检查指定函数体（排除注释/docstring）是否包含某代码模式。

        Returns:
            True  — 函数体包含 pattern
            False — 函数体不含 pattern
            None  — 函数不存在或文件无法解析
        """
        source = self._read_file(path)
        if source is None:
            return None
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
                seg = ast.get_source_segment(source, node)
                if seg is None:
                    return None
                cleaned = self._strip_comments_and_docstrings(seg)
                return pattern in cleaned
        return None

    # ------------------------------------------------------------------ #
    # 7 项风险检测函数
    # ------------------------------------------------------------------ #

    def check_risk_1_database_scale(self) -> str:
        """风险1: 检查 inverted_index.py 是否含 WAL/MemTable/SSTable 类。

        - 三者齐全 → resolved
        - 部分实现 → partial
        - 全无     → open
        """
        key = "risk_1_database_scale"
        self._evidence[key] = []
        path = os.path.join(self.harness_root, "inverted_index.py")
        content = self._read_file(path)
        if content is None:
            self._evidence[key].append(f"文件不存在: {path}")
            return "open"
        markers = ["WAL", "MemTable", "SSTable"]
        found = []
        for m in markers:
            if m in content:
                found.append(m)
                self._evidence[key].append(f"inverted_index.py: 检测到 {m}")
        if len(found) == 3:
            return "resolved"
        if len(found) > 0:
            missing = [m for m in markers if m not in found]
            self._evidence[key].append(f"缺失组件: {', '.join(missing)}")
            return "partial"
        self._evidence[key].append("未检测到 WAL/MemTable/SSTable 任意一项")
        return "open"

    def check_risk_2_style_matrix(self) -> str:
        """风险2: 检查 matching_engine.py 是否含 StyleEmbeddingSpace 引用。

        - 含 StyleEmbeddingSpace → resolved
        - 仅 STYLE_SIMILARITY_MAP → open
        """
        key = "risk_2_style_matrix"
        self._evidence[key] = []
        path = os.path.join(self.harness_root, "matching_engine.py")
        content = self._read_file(path)
        if content is None:
            self._evidence[key].append(f"文件不存在: {path}")
            return "open"
        has_embedding = "StyleEmbeddingSpace" in content
        has_map = "STYLE_SIMILARITY_MAP" in content
        if has_embedding:
            self._evidence[key].append("matching_engine.py: 检测到 StyleEmbeddingSpace 引用")
            return "resolved"
        if has_map:
            self._evidence[key].append("matching_engine.py: 仅检测到 STYLE_SIMILARITY_MAP（硬编码）")
            return "open"
        self._evidence[key].append("matching_engine.py: 未检测到 StyleEmbeddingSpace 或 STYLE_SIMILARITY_MAP")
        return "open"

    def check_risk_3_word2vec(self) -> str:
        """风险3: 检查 vector_enhancer.py 是否含 EmbeddingProvider 且不含 random.seed(42)。

        - 含 EmbeddingProvider 且代码中无 random.seed(42) → resolved
        - 含 EmbeddingProvider 但代码中仍有 random.seed(42) → partial
        - 无 EmbeddingProvider 且有 random.seed(42) → open
        """
        key = "risk_3_word2vec"
        self._evidence[key] = []
        path = os.path.join(self.harness_root, "vector_enhancer.py")
        content = self._read_file(path)
        if content is None:
            self._evidence[key].append(f"文件不存在: {path}")
            return "open"
        has_provider = "EmbeddingProvider" in content
        has_random_seed = self._code_contains(path, "random.seed(42)")
        if has_provider:
            self._evidence[key].append("vector_enhancer.py: 检测到 EmbeddingProvider 抽象")
        if has_random_seed:
            self._evidence[key].append("vector_enhancer.py: 代码中仍含 random.seed(42) 调用")
        else:
            self._evidence[key].append("vector_enhancer.py: 代码中无 random.seed(42) 调用")
        if has_provider and not has_random_seed:
            return "resolved"
        if has_provider and has_random_seed:
            return "partial"
        if has_random_seed:
            return "open"
        self._evidence[key].append("vector_enhancer.py: 未检测到 EmbeddingProvider，也无 random.seed(42)")
        return "open"

    def check_risk_4_causal_engine(self) -> str:
        """风险4: 检查 causal_inference_engine.py 含 _propagate_probabilistic_effect
        且 do_calculus.py 含 scipy.stats.beta。

        - 两者齐全 → resolved
        - 仅其一 → partial
        - 全无 → open
        """
        key = "risk_4_causal_engine"
        self._evidence[key] = []
        engine_path = os.path.join(
            self.agi_root, "consciousness", "causal_model", "inference",
            "causal_inference_engine.py",
        )
        do_path = os.path.join(
            self.agi_root, "consciousness", "causal_model", "inference",
            "do_calculus.py",
        )
        engine_content = self._read_file(engine_path)
        do_content = self._read_file(do_path)
        has_propagate = engine_content is not None and "_propagate_probabilistic_effect" in engine_content
        # scipy.stats.beta 可能以 `from scipy.stats import beta` 形式出现
        has_beta = do_content is not None and (
            "scipy.stats.beta" in do_content
            or "from scipy.stats import beta" in do_content
            or ("scipy.stats" in do_content and "beta" in do_content)
        )
        if engine_content is not None:
            if has_propagate:
                self._evidence[key].append("causal_inference_engine.py: 检测到 _propagate_probabilistic_effect")
            else:
                self._evidence[key].append("causal_inference_engine.py: 缺失 _propagate_probabilistic_effect")
        else:
            self._evidence[key].append(f"文件不存在: {engine_path}")
        if do_content is not None:
            if has_beta:
                self._evidence[key].append("do_calculus.py: 检测到 scipy.stats beta 引用")
            else:
                self._evidence[key].append("do_calculus.py: 缺失 scipy.stats.beta")
        else:
            self._evidence[key].append(f"文件不存在: {do_path}")
        if has_propagate and has_beta:
            return "resolved"
        if has_propagate or has_beta:
            return "partial"
        return "open"

    def check_risk_5_world_model(self) -> str:
        """风险5: 检查 design_physics.py 的 _validate_similarity 不再 return 1.0 占位
        且 counterfactual.py 的 _apply_intervention 不再 pass 占位。

        - 两者都不是占位 → resolved
        - 仅其一为占位 → partial
        - 两者都是占位/缺失 → open
        """
        key = "risk_5_world_model"
        self._evidence[key] = []
        physics_path = os.path.join(
            self.agi_root, "consciousness", "world_model", "design_physics.py",
        )
        cf_path = os.path.join(
            self.agi_root, "consciousness", "world_model", "simulators",
            "counterfactual.py",
        )
        sim_placeholder = self._is_function_placeholder(physics_path, "_validate_similarity")
        apply_placeholder = self._is_function_placeholder(cf_path, "_apply_intervention")
        if sim_placeholder is None:
            self._evidence[key].append(f"design_physics.py: 未找到 _validate_similarity 或文件缺失")
        elif sim_placeholder:
            self._evidence[key].append("design_physics.py: _validate_similarity 仍是占位（return 1.0）")
        else:
            self._evidence[key].append("design_physics.py: _validate_similarity 已实现真实逻辑")
        if apply_placeholder is None:
            self._evidence[key].append(f"counterfactual.py: 未找到 _apply_intervention 或文件缺失")
        elif apply_placeholder:
            self._evidence[key].append("counterfactual.py: _apply_intervention 仍是占位（pass）")
        else:
            self._evidence[key].append("counterfactual.py: _apply_intervention 已实现真实逻辑")
        # 判定：None 视为未实现（open）
        sim_ok = sim_placeholder is False
        apply_ok = apply_placeholder is False
        if sim_ok and apply_ok:
            return "resolved"
        if sim_ok or apply_ok:
            return "partial"
        return "open"

    def check_risk_6_rsi_test(self) -> str:
        """风险6: 检查 meta_harness.py 的 _run_module_tests 是否含 subprocess.run。

        - 含 subprocess.run → resolved
        - 是 return True 占位 → open
        - 其他 → partial
        """
        key = "risk_6_rsi_test"
        self._evidence[key] = []
        path = os.path.join(
            self.agi_root, "consciousness", "rsi", "meta_harness", "meta_harness.py",
        )
        has_subprocess = self._function_contains_pattern(path, "_run_module_tests", "subprocess.run")
        is_placeholder = self._is_function_placeholder(path, "_run_module_tests")
        if has_subprocess is None:
            self._evidence[key].append(f"meta_harness.py: 未找到 _run_module_tests 或文件缺失")
        elif has_subprocess:
            self._evidence[key].append("meta_harness.py: _run_module_tests 含 subprocess.run 调用")
        else:
            self._evidence[key].append("meta_harness.py: _run_module_tests 不含 subprocess.run")
        if is_placeholder is True:
            self._evidence[key].append("meta_harness.py: _run_module_tests 是 return True 占位")
        if has_subprocess is True:
            return "resolved"
        if is_placeholder is True:
            return "open"
        if has_subprocess is False:
            return "partial"
        return "open"

    def check_risk_7_alignment_guard(self) -> str:
        """风险7: 检查 alignment_guard.py 是否含 IMMUTABLE_HASH_REGISTRY 与 os.path.realpath。

        - 两者齐全 → resolved
        - 仅其一 → partial
        - 全无 → open
        """
        key = "risk_7_alignment_guard"
        self._evidence[key] = []
        path = os.path.join(
            self.agi_root, "consciousness", "rsi", "guards", "alignment_guard.py",
        )
        content = self._read_file(path)
        if content is None:
            self._evidence[key].append(f"文件不存在: {path}")
            return "open"
        has_registry = "IMMUTABLE_HASH_REGISTRY" in content
        has_realpath = "os.path.realpath" in content
        if has_registry:
            self._evidence[key].append("alignment_guard.py: 检测到 IMMUTABLE_HASH_REGISTRY")
        else:
            self._evidence[key].append("alignment_guard.py: 缺失 IMMUTABLE_HASH_REGISTRY")
        if has_realpath:
            self._evidence[key].append("alignment_guard.py: 检测到 os.path.realpath 符号链接解析")
        else:
            self._evidence[key].append("alignment_guard.py: 缺失 os.path.realpath 符号链接解析")
        if has_registry and has_realpath:
            return "resolved"
        if has_registry or has_realpath:
            return "partial"
        return "open"

    # ------------------------------------------------------------------ #
    # 聚合与报告
    # ------------------------------------------------------------------ #

    def get_all_risks(self) -> Dict[str, Dict]:
        """返回所有风险的状态与详细信息。

        Returns:
            {
                "risk_1_database_scale": {"status": "resolved", "description": "...", "evidence": [...]},
                ...
            }
        """
        # 依次执行 7 项检测（顺序执行以收集 evidence）
        statuses = {
            1: self.check_risk_1_database_scale(),
            2: self.check_risk_2_style_matrix(),
            3: self.check_risk_3_word2vec(),
            4: self.check_risk_4_causal_engine(),
            5: self.check_risk_5_world_model(),
            6: self.check_risk_6_rsi_test(),
            7: self.check_risk_7_alignment_guard(),
        }
        result: Dict[str, Dict] = {}
        for idx, meta in self.RISK_META.items():
            key = meta["key"]
            result[key] = {
                "status": statuses[idx],
                "description": meta["description"],
                "evidence": list(self._evidence.get(key, [])),
            }
        return result

    def to_markdown(self) -> str:
        """生成 markdown 格式风险状态报告。"""
        risks = self.get_all_risks()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines: List[str] = []
        lines.append("# LAAP Harness 风险状态报告")
        lines.append("")
        lines.append(f"生成时间: {now}")
        lines.append("")
        lines.append("## 风险状态总览")
        lines.append("")
        lines.append("| 编号 | 风险 | 状态 | 说明 |")
        lines.append("|------|------|------|------|")
        for idx, meta in self.RISK_META.items():
            key = meta["key"]
            risk = risks[key]
            icon = self.STATUS_ICON.get(risk["status"], "")
            lines.append(
                f"| {idx} | {meta['name']} | {icon} {risk['status']} | {meta['description']} |"
            )
        lines.append("")
        lines.append("## 详细信息")
        lines.append("")
        for idx, meta in self.RISK_META.items():
            key = meta["key"]
            risk = risks[key]
            icon = self.STATUS_ICON.get(risk["status"], "")
            lines.append(f"### 风险 {idx}: {meta['name']}")
            lines.append(f"- 状态: {icon} {risk['status']}")
            lines.append(f"- 描述: {meta['description']}")
            evidence = risk.get("evidence", [])
            if evidence:
                lines.append("- 证据:")
                for ev in evidence:
                    lines.append(f"  - {ev}")
            else:
                lines.append("- 证据: 无")
            lines.append("")
        return "\n".join(lines)

    def to_json(self) -> str:
        """生成 JSON 格式风险状态报告。"""
        risks = self.get_all_risks()
        payload = {
            "title": "LAAP Harness 风险状态报告",
            "generated_at": datetime.now().isoformat(),
            "risks": risks,
            "summary": {
                "total": len(risks),
                "resolved": sum(1 for r in risks.values() if r["status"] == "resolved"),
                "partial": sum(1 for r in risks.values() if r["status"] == "partial"),
                "open": sum(1 for r in risks.values() if r["status"] == "open"),
            },
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def report(self, format: str = "markdown") -> str:
        """统一报告接口。

        Args:
            format: "markdown" 或 "json"

        Returns:
            指定格式的报告字符串
        """
        fmt = format.lower().strip()
        if fmt == "markdown":
            return self.to_markdown()
        if fmt == "json":
            return self.to_json()
        raise ValueError(f"不支持的报告格式: {format}（可选: markdown / json）")


if __name__ == "__main__":
    print(RiskDashboard().report())
