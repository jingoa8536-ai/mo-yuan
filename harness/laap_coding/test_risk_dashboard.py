"""
test_risk_dashboard.py — RiskDashboard 单元测试
=================================================

验证 7 项风险状态检测函数与 markdown/json 双格式报告输出。
使用 tmp_path 创建模拟目录结构，验证 partial/open 状态的判定逻辑。
"""

import json
import os
import sys
import textwrap

import pytest

# 确保 laap_coding 包可导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from laap_coding.core.risk_dashboard import RiskDashboard


# ---------------------------------------------------------------------- #
# 测试夹具：在 tmp_path 下构建 mock 目录结构
# ---------------------------------------------------------------------- #

def _write(path, content):
    """写入文件，自动创建父目录。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _build_full_resolved_layout(harness_root, agi_root):
    """构建一个 7 项风险全部 resolved 的 mock 目录结构。"""
    # Risk 1: inverted_index.py 含 WAL/MemTable/SSTable
    _write(os.path.join(harness_root, "inverted_index.py"), textwrap.dedent("""
        class WAL:
            def append(self, record): pass
        class MemTable:
            def insert(self, k, v): pass
        class SSTable:
            def query(self, key): return None
        class InvertedIndex:
            def add_document(self, doc): pass
    """).strip())

    # Risk 2: matching_engine.py 含 StyleEmbeddingSpace 引用
    _write(os.path.join(harness_root, "matching_engine.py"), textwrap.dedent("""
        from .style_register import StyleEmbeddingSpace
        class MatchingEngine:
            STYLE_SIMILARITY_MAP = {"modern-minimal": {}}
            def __init__(self):
                self.style_embedding_space = StyleEmbeddingSpace()
    """).strip())

    # Risk 3: vector_enhancer.py 含 EmbeddingProvider 且不含 random.seed(42)
    _write(os.path.join(harness_root, "vector_enhancer.py"), textwrap.dedent("""
        class EmbeddingProvider:
            def embed(self, texts): return []
        class HashingVectorizer(EmbeddingProvider):
            pass
    """).strip())

    # Risk 4: causal_inference_engine.py 含 _propagate_probabilistic_effect
    _write(
        os.path.join(agi_root, "consciousness", "causal_model", "inference",
                     "causal_inference_engine.py"),
        textwrap.dedent("""
            class CausalInferenceEngine:
                def _propagate_probabilistic_effect(self, target, intervention):
                    return 0.5, 0.9
        """).strip(),
    )
    # do_calculus.py 含 scipy.stats.beta
    _write(
        os.path.join(agi_root, "consciousness", "causal_model", "inference",
                     "do_calculus.py"),
        textwrap.dedent("""
            from scipy.stats import beta as beta_dist
            def _abduction():
                return beta_dist(1, 1)
        """).strip(),
    )

    # Risk 5: design_physics._validate_similarity 有真实逻辑（非 return 1.0 占位）
    _write(
        os.path.join(agi_root, "consciousness", "world_model", "design_physics.py"),
        textwrap.dedent("""
            class DesignPhysics:
                def _validate_similarity(self, components):
                    if len(components) < 2:
                        return 1.0
                    total = sum(1 for _ in components)
                    return total / len(components)
        """).strip(),
    )
    # counterfactual._apply_intervention 有真实逻辑（非 pass 占位）
    _write(
        os.path.join(agi_root, "consciousness", "world_model", "simulators",
                     "counterfactual.py"),
        textwrap.dedent("""
            class CounterfactualSimulator:
                def _apply_intervention(self, tree, intervention):
                    new_tree = tree
                    return new_tree
        """).strip(),
    )

    # Risk 6: meta_harness._run_module_tests 含 subprocess.run
    _write(
        os.path.join(agi_root, "consciousness", "rsi", "meta_harness",
                     "meta_harness.py"),
        textwrap.dedent("""
            import subprocess
            class MetaHarness:
                async def _run_module_tests(self, module_path):
                    result = subprocess.run(["pytest", module_path])
                    return result.returncode == 0, []
        """).strip(),
    )

    # Risk 7: alignment_guard.py 含 IMMUTABLE_HASH_REGISTRY 与 os.path.realpath
    _write(
        os.path.join(agi_root, "consciousness", "rsi", "guards",
                     "alignment_guard.py"),
        textwrap.dedent("""
            import os
            IMMUTABLE_HASH_REGISTRY = ["alignment_guard.py"]
            def is_base_llm_target(path):
                resolved = os.path.realpath(path)
                return "models" in resolved
        """).strip(),
    )


# ---------------------------------------------------------------------- #
# 实例化与基础测试
# ---------------------------------------------------------------------- #

class TestRiskDashboardInstantiation:
    """RiskDashboard 实例化与基础接口测试。"""

    def test_default_instantiation(self):
        """RiskDashboard() 可用默认参数实例化。"""
        dashboard = RiskDashboard()
        assert dashboard is not None
        assert os.path.isdir(dashboard.harness_root) or os.path.exists(dashboard.harness_root)
        assert "src" in dashboard.agi_root or os.path.isdir(dashboard.agi_root)

    def test_custom_roots(self, tmp_path):
        """可传入自定义 harness_root / agi_root。"""
        harness_root = str(tmp_path / "harness" / "core")
        agi_root = str(tmp_path / "agi" / "src")
        dashboard = RiskDashboard(harness_root=harness_root, agi_root=agi_root)
        assert dashboard.harness_root == harness_root
        assert dashboard.agi_root == agi_root


# ---------------------------------------------------------------------- #
# 7 项 check_risk_X 方法返回值测试
# ---------------------------------------------------------------------- #

class TestCheckRiskReturnValues:
    """7 个 check_risk_X 方法各自返回 resolved/partial/open 之一。"""

    def test_all_check_methods_return_valid_status(self):
        """7 个 check_risk_X 方法返回值均为 resolved/partial/open 之一。"""
        dashboard = RiskDashboard()
        valid = {"resolved", "partial", "open"}
        assert dashboard.check_risk_1_database_scale() in valid
        assert dashboard.check_risk_2_style_matrix() in valid
        assert dashboard.check_risk_3_word2vec() in valid
        assert dashboard.check_risk_4_causal_engine() in valid
        assert dashboard.check_risk_5_world_model() in valid
        assert dashboard.check_risk_6_rsi_test() in valid
        assert dashboard.check_risk_7_alignment_guard() in valid


# ---------------------------------------------------------------------- #
# get_all_risks 测试
# ---------------------------------------------------------------------- #

class TestGetAllRisks:
    """get_all_risks 返回结构测试。"""

    def test_returns_seven_risks(self):
        """get_all_risks 返回 7 个风险的字典。"""
        dashboard = RiskDashboard()
        risks = dashboard.get_all_risks()
        assert isinstance(risks, dict)
        assert len(risks) == 7
        expected_keys = {
            "risk_1_database_scale",
            "risk_2_style_matrix",
            "risk_3_word2vec",
            "risk_4_causal_engine",
            "risk_5_world_model",
            "risk_6_rsi_test",
            "risk_7_alignment_guard",
        }
        assert set(risks.keys()) == expected_keys

    def test_risk_entry_structure(self):
        """每个风险条目含 status/description/evidence 字段。"""
        dashboard = RiskDashboard()
        risks = dashboard.get_all_risks()
        for key, entry in risks.items():
            assert "status" in entry
            assert entry["status"] in {"resolved", "partial", "open"}
            assert "description" in entry
            assert isinstance(entry["description"], str)
            assert "evidence" in entry
            assert isinstance(entry["evidence"], list)


# ---------------------------------------------------------------------- #
# to_markdown / to_json / report 测试
# ---------------------------------------------------------------------- #

class TestReportFormats:
    """markdown / json 报告格式测试。"""

    def test_to_markdown_contains_title_and_table(self):
        """to_markdown 返回的字符串含标题与表格分隔符。"""
        dashboard = RiskDashboard()
        md = dashboard.to_markdown()
        assert isinstance(md, str)
        assert "# LAAP Harness 风险状态报告" in md
        assert "|" in md
        assert "生成时间" in md

    def test_to_json_parseable(self):
        """to_json 返回的字符串可被 json.loads 解析。"""
        dashboard = RiskDashboard()
        js = dashboard.to_json()
        assert isinstance(js, str)
        payload = json.loads(js)
        assert "risks" in payload
        assert "summary" in payload
        assert payload["summary"]["total"] == 7

    def test_report_markdown(self):
        """report(format='markdown') 与 to_markdown 等价（秒级时间戳内一致）。"""
        dashboard = RiskDashboard()
        md_report = dashboard.report(format="markdown")
        md_direct = dashboard.to_markdown()
        # 两者均含标题与表格；时间戳精度为秒，同秒内一致
        assert "# LAAP Harness 风险状态报告" in md_report
        assert "# LAAP Harness 风险状态报告" in md_direct
        assert "| 编号 | 风险 | 状态 | 说明 |" in md_report

    def test_report_json(self):
        """report(format='json') 与 to_json 结构等价（时间戳精度除外）。"""
        dashboard = RiskDashboard()
        r1 = json.loads(dashboard.report(format="json"))
        r2 = json.loads(dashboard.to_json())
        # generated_at 精度为微秒，两次调用可能不同，比较时排除
        assert r1["title"] == r2["title"]
        assert r1["risks"] == r2["risks"]
        assert r1["summary"] == r2["summary"]

    def test_report_default_is_markdown(self):
        """report() 默认格式为 markdown。"""
        dashboard = RiskDashboard()
        result = dashboard.report()
        assert "# LAAP Harness 风险状态报告" in result
        assert "| 编号 | 风险 | 状态 | 说明 |" in result

    def test_report_invalid_format_raises(self):
        """report(format='unknown') 抛出 ValueError。"""
        dashboard = RiskDashboard()
        with pytest.raises(ValueError):
            dashboard.report(format="unknown")


# ---------------------------------------------------------------------- #
# 检测逻辑准确性测试（基于 tmp_path 模拟目录结构）
# ---------------------------------------------------------------------- #

class TestDetectionLogicWithMockLayout:
    """使用 tmp_path 模拟目录结构，验证 partial/open 状态判定。"""

    def test_all_resolved_layout(self, tmp_path):
        """完整实现的 mock 目录结构下 7 项风险全部 resolved。"""
        harness_root = str(tmp_path / "harness" / "core")
        agi_root = str(tmp_path / "agi" / "src")
        _build_full_resolved_layout(harness_root, agi_root)
        dashboard = RiskDashboard(harness_root=harness_root, agi_root=agi_root)
        risks = dashboard.get_all_risks()
        for key, entry in risks.items():
            assert entry["status"] == "resolved", (
                f"{key} 应为 resolved，实际为 {entry['status']}，证据: {entry['evidence']}"
            )

    def test_risk_1_partial_when_only_wal(self, tmp_path):
        """Risk1: inverted_index.py 仅含 WAL（缺 MemTable/SSTable）→ partial。"""
        harness_root = str(tmp_path / "harness" / "core")
        agi_root = str(tmp_path / "agi" / "src")
        _build_full_resolved_layout(harness_root, agi_root)
        # 覆盖 inverted_index.py 仅保留 WAL
        _write(os.path.join(harness_root, "inverted_index.py"), "class WAL:\n    pass\n")
        dashboard = RiskDashboard(harness_root=harness_root, agi_root=agi_root)
        assert dashboard.check_risk_1_database_scale() == "partial"

    def test_risk_1_open_when_no_markers(self, tmp_path):
        """Risk1: inverted_index.py 无 WAL/MemTable/SSTable → open。"""
        harness_root = str(tmp_path / "harness" / "core")
        agi_root = str(tmp_path / "agi" / "src")
        _build_full_resolved_layout(harness_root, agi_root)
        _write(os.path.join(harness_root, "inverted_index.py"), "class InvertedIndex:\n    pass\n")
        dashboard = RiskDashboard(harness_root=harness_root, agi_root=agi_root)
        assert dashboard.check_risk_1_database_scale() == "open"

    def test_risk_1_open_when_file_missing(self, tmp_path):
        """Risk1: inverted_index.py 不存在 → open。"""
        harness_root = str(tmp_path / "harness" / "core")
        agi_root = str(tmp_path / "agi" / "src")
        _build_full_resolved_layout(harness_root, agi_root)
        os.remove(os.path.join(harness_root, "inverted_index.py"))
        dashboard = RiskDashboard(harness_root=harness_root, agi_root=agi_root)
        assert dashboard.check_risk_1_database_scale() == "open"

    def test_risk_2_open_when_only_style_map(self, tmp_path):
        """Risk2: matching_engine.py 仅含 STYLE_SIMILARITY_MAP（无 StyleEmbeddingSpace）→ open。"""
        harness_root = str(tmp_path / "harness" / "core")
        agi_root = str(tmp_path / "agi" / "src")
        _build_full_resolved_layout(harness_root, agi_root)
        _write(
            os.path.join(harness_root, "matching_engine.py"),
            "class MatchingEngine:\n    STYLE_SIMILARITY_MAP = {'modern-minimal': {}}\n",
        )
        dashboard = RiskDashboard(harness_root=harness_root, agi_root=agi_root)
        assert dashboard.check_risk_2_style_matrix() == "open"

    def test_risk_3_partial_when_provider_and_random_seed(self, tmp_path):
        """Risk3: 同时含 EmbeddingProvider 与 random.seed(42) 代码 → partial。"""
        harness_root = str(tmp_path / "harness" / "core")
        agi_root = str(tmp_path / "agi" / "src")
        _build_full_resolved_layout(harness_root, agi_root)
        _write(
            os.path.join(harness_root, "vector_enhancer.py"),
            textwrap.dedent("""
                import random
                class EmbeddingProvider:
                    pass
                class SimpleVectorModel:
                    def __init__(self):
                        random.seed(42)
            """).strip(),
        )
        dashboard = RiskDashboard(harness_root=harness_root, agi_root=agi_root)
        assert dashboard.check_risk_3_word2vec() == "partial"

    def test_risk_3_open_when_only_random_seed(self, tmp_path):
        """Risk3: 仅含 random.seed(42)（无 EmbeddingProvider）→ open。"""
        harness_root = str(tmp_path / "harness" / "core")
        agi_root = str(tmp_path / "agi" / "src")
        _build_full_resolved_layout(harness_root, agi_root)
        _write(
            os.path.join(harness_root, "vector_enhancer.py"),
            textwrap.dedent("""
                import random
                class SimpleVectorModel:
                    def __init__(self):
                        random.seed(42)
            """).strip(),
        )
        dashboard = RiskDashboard(harness_root=harness_root, agi_root=agi_root)
        assert dashboard.check_risk_3_word2vec() == "open"

    def test_risk_3_resolved_ignores_random_seed_in_comments(self, tmp_path):
        """Risk3: random.seed(42) 仅出现在注释/docstring 中 → resolved。"""
        harness_root = str(tmp_path / "harness" / "core")
        agi_root = str(tmp_path / "agi" / "src")
        _build_full_resolved_layout(harness_root, agi_root)
        _write(
            os.path.join(harness_root, "vector_enhancer.py"),
            textwrap.dedent('''
                class EmbeddingProvider:
                    """替代 random.seed(42) 伪向量。"""
                    pass
                # Task C1.5: 用 HashingVectorizer 替代 random.seed(42) 伪向量
                class HashingVectorizer(EmbeddingProvider):
                    pass
            ''').strip(),
        )
        dashboard = RiskDashboard(harness_root=harness_root, agi_root=agi_root)
        assert dashboard.check_risk_3_word2vec() == "resolved"

    def test_risk_4_partial_when_only_propagate(self, tmp_path):
        """Risk4: 仅 causal_inference_engine 含 _propagate_probabilistic_effect → partial。"""
        harness_root = str(tmp_path / "harness" / "core")
        agi_root = str(tmp_path / "agi" / "src")
        _build_full_resolved_layout(harness_root, agi_root)
        # 移除 do_calculus.py 的 scipy.stats 引用
        _write(
            os.path.join(agi_root, "consciousness", "causal_model", "inference",
                         "do_calculus.py"),
            "def _abduction():\n    return 0.5\n",
        )
        dashboard = RiskDashboard(harness_root=harness_root, agi_root=agi_root)
        assert dashboard.check_risk_4_causal_engine() == "partial"

    def test_risk_4_open_when_both_missing(self, tmp_path):
        """Risk4: 两个文件都缺失目标符号 → open。"""
        harness_root = str(tmp_path / "harness" / "core")
        agi_root = str(tmp_path / "agi" / "src")
        _build_full_resolved_layout(harness_root, agi_root)
        _write(
            os.path.join(agi_root, "consciousness", "causal_model", "inference",
                         "causal_inference_engine.py"),
            "class CausalInferenceEngine:\n    pass\n",
        )
        _write(
            os.path.join(agi_root, "consciousness", "causal_model", "inference",
                         "do_calculus.py"),
            "def _abduction():\n    return 0.5\n",
        )
        dashboard = RiskDashboard(harness_root=harness_root, agi_root=agi_root)
        assert dashboard.check_risk_4_causal_engine() == "open"

    def test_risk_5_partial_when_similarity_is_placeholder(self, tmp_path):
        """Risk5: _validate_similarity 仍是 return 1.0 占位 → partial（另一项已实现）。"""
        harness_root = str(tmp_path / "harness" / "core")
        agi_root = str(tmp_path / "agi" / "src")
        _build_full_resolved_layout(harness_root, agi_root)
        _write(
            os.path.join(agi_root, "consciousness", "world_model", "design_physics.py"),
            textwrap.dedent("""
                class DesignPhysics:
                    def _validate_similarity(self, components):
                        return 1.0
            """).strip(),
        )
        dashboard = RiskDashboard(harness_root=harness_root, agi_root=agi_root)
        assert dashboard.check_risk_5_world_model() == "partial"

    def test_risk_5_open_when_both_placeholders(self, tmp_path):
        """Risk5: _validate_similarity 与 _apply_intervention 都是占位 → open。"""
        harness_root = str(tmp_path / "harness" / "core")
        agi_root = str(tmp_path / "agi" / "src")
        _build_full_resolved_layout(harness_root, agi_root)
        _write(
            os.path.join(agi_root, "consciousness", "world_model", "design_physics.py"),
            textwrap.dedent("""
                class DesignPhysics:
                    def _validate_similarity(self, components):
                        return 1.0
            """).strip(),
        )
        _write(
            os.path.join(agi_root, "consciousness", "world_model", "simulators",
                         "counterfactual.py"),
            textwrap.dedent("""
                class CounterfactualSimulator:
                    def _apply_intervention(self, tree, intervention):
                        pass
            """).strip(),
        )
        dashboard = RiskDashboard(harness_root=harness_root, agi_root=agi_root)
        assert dashboard.check_risk_5_world_model() == "open"

    def test_risk_6_open_when_return_true_placeholder(self, tmp_path):
        """Risk6: _run_module_tests 是 return True 占位 → open。"""
        harness_root = str(tmp_path / "harness" / "core")
        agi_root = str(tmp_path / "agi" / "src")
        _build_full_resolved_layout(harness_root, agi_root)
        _write(
            os.path.join(agi_root, "consciousness", "rsi", "meta_harness",
                         "meta_harness.py"),
            textwrap.dedent("""
                class MetaHarness:
                    async def _run_module_tests(self, module_path):
                        return True, []
            """).strip(),
        )
        dashboard = RiskDashboard(harness_root=harness_root, agi_root=agi_root)
        assert dashboard.check_risk_6_rsi_test() == "open"

    def test_risk_6_partial_when_no_subprocess_no_placeholder(self, tmp_path):
        """Risk6: _run_module_tests 有逻辑但无 subprocess.run → partial。"""
        harness_root = str(tmp_path / "harness" / "core")
        agi_root = str(tmp_path / "agi" / "src")
        _build_full_resolved_layout(harness_root, agi_root)
        _write(
            os.path.join(agi_root, "consciousness", "rsi", "meta_harness",
                         "meta_harness.py"),
            textwrap.dedent("""
                class MetaHarness:
                    async def _run_module_tests(self, module_path):
                        results = []
                        return len(results) == 0, results
            """).strip(),
        )
        dashboard = RiskDashboard(harness_root=harness_root, agi_root=agi_root)
        assert dashboard.check_risk_6_rsi_test() == "partial"

    def test_risk_7_partial_when_only_registry(self, tmp_path):
        """Risk7: 仅含 IMMUTABLE_HASH_REGISTRY（无 os.path.realpath）→ partial。"""
        harness_root = str(tmp_path / "harness" / "core")
        agi_root = str(tmp_path / "agi" / "src")
        _build_full_resolved_layout(harness_root, agi_root)
        _write(
            os.path.join(agi_root, "consciousness", "rsi", "guards",
                         "alignment_guard.py"),
            "IMMUTABLE_HASH_REGISTRY = ['alignment_guard.py']\n",
        )
        dashboard = RiskDashboard(harness_root=harness_root, agi_root=agi_root)
        assert dashboard.check_risk_7_alignment_guard() == "partial"

    def test_risk_7_open_when_both_missing(self, tmp_path):
        """Risk7: 既无 IMMUTABLE_HASH_REGISTRY 也无 os.path.realpath → open。"""
        harness_root = str(tmp_path / "harness" / "core")
        agi_root = str(tmp_path / "agi" / "src")
        _build_full_resolved_layout(harness_root, agi_root)
        _write(
            os.path.join(agi_root, "consciousness", "rsi", "guards",
                         "alignment_guard.py"),
            "class AlignmentGuard:\n    pass\n",
        )
        dashboard = RiskDashboard(harness_root=harness_root, agi_root=agi_root)
        assert dashboard.check_risk_7_alignment_guard() == "open"

    def test_risk_7_open_when_file_missing(self, tmp_path):
        """Risk7: alignment_guard.py 不存在 → open。"""
        harness_root = str(tmp_path / "harness" / "core")
        agi_root = str(tmp_path / "agi" / "src")
        _build_full_resolved_layout(harness_root, agi_root)
        os.remove(os.path.join(agi_root, "consciousness", "rsi", "guards",
                               "alignment_guard.py"))
        dashboard = RiskDashboard(harness_root=harness_root, agi_root=agi_root)
        assert dashboard.check_risk_7_alignment_guard() == "open"

    def test_markdown_report_on_mock_layout(self, tmp_path):
        """在 mock 目录上生成的 markdown 报告含标题与表格。"""
        harness_root = str(tmp_path / "harness" / "core")
        agi_root = str(tmp_path / "agi" / "src")
        _build_full_resolved_layout(harness_root, agi_root)
        dashboard = RiskDashboard(harness_root=harness_root, agi_root=agi_root)
        md = dashboard.to_markdown()
        assert "# LAAP Harness 风险状态报告" in md
        assert "| 编号 | 风险 | 状态 | 说明 |" in md
        assert "resolved" in md

    def test_json_report_on_mock_layout(self, tmp_path):
        """在 mock 目录上生成的 json 报告可解析且 summary 正确。"""
        harness_root = str(tmp_path / "harness" / "core")
        agi_root = str(tmp_path / "agi" / "src")
        _build_full_resolved_layout(harness_root, agi_root)
        dashboard = RiskDashboard(harness_root=harness_root, agi_root=agi_root)
        payload = json.loads(dashboard.to_json())
        assert payload["summary"]["total"] == 7
        assert payload["summary"]["resolved"] == 7
        assert payload["summary"]["open"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-p", "no:quadrants"])
