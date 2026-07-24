"""
test_risk_gate.py — RiskGatePlugin 单元测试
=============================================

验证 CI 风险门控行为：
1. RiskGatePlugin 类实例化
2. --risk-gate 命令行参数注册（用 pytester fixture）
3. 启用 --risk-gate 时若 RiskDashboard 返回任一 open 风险，pytest 退出码非 0
4. 启用 --risk-gate 时若全部 resolved/partial，pytest 退出码 0
5. 用 unittest.mock.patch mock RiskDashboard.get_all_risks 控制返回值
6. 不启用 --risk-gate 时插件不干预

使用 pytester.runpytest_subprocess 在子进程中运行 pytest（避免 Python 3.13
在 Windows 上 runpytest_inprocess 的 access violation），通过在 pytester
tmp 目录创建 conftest.py 应用 unittest.mock.patch 实现 RiskDashboard 的 mock。
同时保留直接调用插件 hook 的测试，用 unittest.mock.patch 验证逻辑正确性。
"""

import json
import os
import sys
from unittest.mock import patch

import pytest

# 确保 laap_coding 包可导入
_HARNESS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HARNESS_ROOT not in sys.path:
    sys.path.insert(0, _HARNESS_ROOT)

from laap_coding.core.risk_gate_plugin import RiskGatePlugin


# ---------------------------------------------------------------------- #
# 辅助函数
# ---------------------------------------------------------------------- #

_RISK_KEYS = [
    "risk_1_database_scale",
    "risk_2_style_matrix",
    "risk_3_word2vec",
    "risk_4_causal_engine",
    "risk_5_world_model",
    "risk_6_rsi_test",
    "risk_7_alignment_guard",
]


def _make_risks(status_map=None):
    """构造 7 项风险的 mock 返回值。

    Args:
        status_map: dict of {index(1-7): status}，未指定的默认为 "resolved"

    Returns:
        dict，结构同 RiskDashboard.get_all_risks()
    """
    if status_map is None:
        status_map = {}
    result = {}
    for idx, key in enumerate(_RISK_KEYS, start=1):
        status = status_map.get(idx, "resolved")
        result[key] = {
            "status": status,
            "description": "Risk {} description".format(idx),
            "evidence": ["evidence line for {}".format(key)],
        }
    return result


@pytest.fixture(autouse=True)
def _ensure_pythonpath(monkeypatch):
    """确保子进程 pytest 能找到 laap_coding 包。"""
    existing = os.environ.get("PYTHONPATH", "")
    new_path = _HARNESS_ROOT + (os.pathsep + existing if existing else "")
    monkeypatch.setenv("PYTHONPATH", new_path)


def _make_mock_conftest(pytester, fake_risks):
    """在 pytester tmp 目录创建 conftest.py，用 unittest.mock.patch mock RiskDashboard。"""
    risks_path = pytester.path / "fake_risks.json"
    risks_path.write_text(
        json.dumps(fake_risks, ensure_ascii=False), encoding="utf-8"
    )
    pytester.makeconftest(
        '''
import json
import os
import sys
from unittest.mock import patch

# 加载 fake_risks.json
_risks_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fake_risks.json")
with open(_risks_path, "r", encoding="utf-8") as _f:
    _fake_risks = json.load(_f)

# 用 unittest.mock.patch mock RiskDashboard.get_all_risks
_patcher = patch("laap_coding.core.risk_gate_plugin.RiskDashboard")
_mock_dashboard_cls = _patcher.start()
_mock_dashboard_cls.return_value.get_all_risks.return_value = _fake_risks
'''
    )


def _run_pytest(pytester, *extra_args):
    """运行子进程 pytest，清空继承的 addopts，加载 risk_gate_plugin。

    包含 `-p no:quadrants` 以避免 quadrants 插件在子进程中触发 torch 循环导入。
    """
    args = [
        "-o", "addopts=",
        "-p", "no:quadrants",
        "-p", "laap_coding.core.risk_gate_plugin",
    ]
    args.extend(extra_args)
    return pytester.runpytest_subprocess(*args)


# ---------------------------------------------------------------------- #
# 1. RiskGatePlugin 类实例化测试
# ---------------------------------------------------------------------- #

class TestRiskGatePluginInstantiation:
    """RiskGatePlugin 实例化与初始状态测试。"""

    def test_plugin_instantiation(self):
        """RiskGatePlugin 可被实例化。"""
        plugin = RiskGatePlugin()
        assert plugin is not None

    def test_plugin_initial_state(self):
        """新实例的初始状态正确。"""
        plugin = RiskGatePlugin()
        assert plugin.risks is None
        assert plugin.gate_enabled is False
        assert plugin.gate_failed is False
        assert plugin.open_risk_keys == []

    def test_plugin_has_hooks(self):
        """插件类含 pytest_sessionstart 与 pytest_terminal_summary 方法。"""
        plugin = RiskGatePlugin()
        assert callable(getattr(plugin, "pytest_sessionstart", None))
        assert callable(getattr(plugin, "pytest_terminal_summary", None))

    def test_status_icon_map(self):
        """STATUS_ICON 含 resolved/partial/open 三种状态。"""
        plugin = RiskGatePlugin()
        assert "resolved" in RiskGatePlugin.STATUS_ICON
        assert "partial" in RiskGatePlugin.STATUS_ICON
        assert "open" in RiskGatePlugin.STATUS_ICON


# ---------------------------------------------------------------------- #
# 2. --risk-gate 命令行参数注册测试（用 pytester fixture）
# ---------------------------------------------------------------------- #

class TestRiskGateOptionRegistration:
    """--risk-gate 命令行参数注册测试。"""

    def test_option_appears_in_help(self, pytester):
        """--risk-gate 出现在 pytest --help 输出中。"""
        pytester.makepyfile("def test_dummy(): pass")
        result = _run_pytest(pytester, "--help")
        assert result.ret == 0
        assert "--risk-gate" in result.stdout.str()

    def test_option_default_false_when_not_specified(self, pytester):
        """未指定 --risk-gate 时，测试正常通过。"""
        pytester.makepyfile("def test_dummy(): assert True")
        result = _run_pytest(pytester)
        assert result.ret == 0


# ---------------------------------------------------------------------- #
# 3 & 5. 启用 --risk-gate 时若任一 open 风险，退出码非 0（mock 控制）
# ---------------------------------------------------------------------- #

class TestRiskGateOpenFails:
    """启用 --risk-gate 时，任一 open 风险使 pytest 退出码非 0。"""

    def test_single_open_risk_fails_gate(self, pytester):
        """单个 open 风险 → 退出码非 0。"""
        pytester.makepyfile("def test_dummy(): pass")
        _make_mock_conftest(pytester, _make_risks({1: "open"}))
        result = _run_pytest(pytester, "--risk-gate")
        assert result.ret != 0

    def test_multiple_open_risks_fail_gate(self, pytester):
        """多个 open 风险 → 退出码非 0。"""
        pytester.makepyfile("def test_dummy(): pass")
        _make_mock_conftest(pytester, _make_risks({1: "open", 3: "open", 5: "open"}))
        result = _run_pytest(pytester, "--risk-gate")
        assert result.ret != 0

    def test_all_open_risks_fail_gate(self, pytester):
        """全部 open 风险 → 退出码非 0。"""
        pytester.makepyfile("def test_dummy(): pass")
        _make_mock_conftest(pytester, _make_risks({i: "open" for i in range(1, 8)}))
        result = _run_pytest(pytester, "--risk-gate")
        assert result.ret != 0

    def test_open_risk_output_contains_failure_message(self, pytester):
        """open 风险时输出含 'Risk gate failed' 消息。"""
        pytester.makepyfile("def test_dummy(): pass")
        _make_mock_conftest(pytester, _make_risks({2: "open"}))
        result = _run_pytest(pytester, "--risk-gate")
        combined = result.stdout.str() + result.stderr.str()
        assert "Risk gate failed" in combined or "open risk" in combined


# ---------------------------------------------------------------------- #
# 4 & 5. 启用 --risk-gate 时若全部 resolved/partial，退出码 0（mock 控制）
# ---------------------------------------------------------------------- #

class TestRiskGateResolvedPartialPasses:
    """启用 --risk-gate 时，全部 resolved/partial（无 open）使 pytest 退出码 0。"""

    def test_all_resolved_passes_gate(self, pytester):
        """全部 resolved → 退出码 0。"""
        pytester.makepyfile("def test_dummy(): pass")
        _make_mock_conftest(pytester, _make_risks({}))
        result = _run_pytest(pytester, "--risk-gate")
        assert result.ret == 0

    def test_all_partial_passes_gate(self, pytester):
        """全部 partial（无 open）→ 退出码 0。"""
        pytester.makepyfile("def test_dummy(): pass")
        _make_mock_conftest(pytester, _make_risks({i: "partial" for i in range(1, 8)}))
        result = _run_pytest(pytester, "--risk-gate")
        assert result.ret == 0

    def test_mixed_resolved_partial_passes_gate(self, pytester):
        """resolved + partial 混合（无 open）→ 退出码 0。"""
        pytester.makepyfile("def test_dummy(): pass")
        _make_mock_conftest(
            pytester,
            _make_risks({1: "resolved", 2: "partial", 3: "resolved",
                         4: "partial", 5: "resolved", 6: "partial",
                         7: "resolved"}),
        )
        result = _run_pytest(pytester, "--risk-gate")
        assert result.ret == 0

    def test_partial_with_one_open_fails(self, pytester):
        """resolved + partial + 1 open → 退出码非 0。"""
        pytester.makepyfile("def test_dummy(): pass")
        _make_mock_conftest(
            pytester,
            _make_risks({1: "resolved", 2: "partial", 3: "open",
                         4: "resolved", 5: "partial", 6: "resolved",
                         7: "resolved"}),
        )
        result = _run_pytest(pytester, "--risk-gate")
        assert result.ret != 0


# ---------------------------------------------------------------------- #
# 6. 不启用 --risk-gate 时插件不干预
# ---------------------------------------------------------------------- #

class TestRiskGateDisabled:
    """不启用 --risk-gate 时插件不干预 pytest 行为。"""

    def test_no_risk_gate_option_passes(self, pytester):
        """未启用 --risk-gate 时，即使有 open 风险也正常通过。"""
        pytester.makepyfile("def test_dummy(): pass")
        _make_mock_conftest(pytester, _make_risks({1: "open"}))
        result = _run_pytest(pytester)  # 不传 --risk-gate
        assert result.ret == 0

    def test_no_risk_gate_no_intervention_output(self, pytester):
        """未启用 --risk-gate 时，输出中无 Risk Gate Report。"""
        pytester.makepyfile("def test_dummy(): pass")
        _make_mock_conftest(pytester, _make_risks({1: "open"}))
        result = _run_pytest(pytester)  # 不传 --risk-gate
        combined = result.stdout.str() + result.stderr.str()
        assert "Risk Gate Report" not in combined


# ---------------------------------------------------------------------- #
# 7. 插件 hook 直接调用测试（用 unittest.mock.patch 验证逻辑正确性）
# ---------------------------------------------------------------------- #

class TestRiskGatePluginHooksDirect:
    """直接调用插件 hook 方法，用 unittest.mock.patch 验证逻辑。

    这组测试不依赖 pytester 子进程，直接验证插件 hook 的行为逻辑。
    """

    def test_sessionstart_disabled_does_nothing(self):
        """gate_enabled=False 时 pytest_sessionstart 不调用 RiskDashboard。"""
        plugin = RiskGatePlugin()

        class FakeConfig:
            def getoption(self, name, default=None):
                return False

        class FakeSession:
            config = FakeConfig()

        with patch("laap_coding.core.risk_gate_plugin.RiskDashboard") as MockDashboard:
            plugin.pytest_sessionstart(FakeSession())
            MockDashboard.assert_not_called()

        assert plugin.gate_enabled is False
        assert plugin.risks is None

    def test_sessionstart_enabled_with_open_risks_calls_exit(self):
        """启用 --risk-gate 且有 open 风险时调用 pytest.exit(returncode=1)。"""
        plugin = RiskGatePlugin()
        fake_risks = _make_risks({1: "open"})

        class FakeConfig:
            def getoption(self, name, default=None):
                return True

        class FakeSession:
            config = FakeConfig()

        with patch("laap_coding.core.risk_gate_plugin.RiskDashboard") as MockDashboard:
            MockDashboard.return_value.get_all_risks.return_value = fake_risks
            with patch("laap_coding.core.risk_gate_plugin.pytest.exit") as mock_exit:
                plugin.pytest_sessionstart(FakeSession())
                mock_exit.assert_called_once()
                # 验证 returncode=1
                _, kwargs = mock_exit.call_args
                assert kwargs.get("returncode") == 1

        assert plugin.gate_failed is True
        assert "risk_1_database_scale" in plugin.open_risk_keys

    def test_sessionstart_enabled_with_resolved_does_not_exit(self):
        """启用 --risk-gate 且全部 resolved 时不调用 pytest.exit。"""
        plugin = RiskGatePlugin()
        fake_risks = _make_risks({})

        class FakeConfig:
            def getoption(self, name, default=None):
                return True

        class FakeSession:
            config = FakeConfig()

        with patch("laap_coding.core.risk_gate_plugin.RiskDashboard") as MockDashboard:
            MockDashboard.return_value.get_all_risks.return_value = fake_risks
            with patch("laap_coding.core.risk_gate_plugin.pytest.exit") as mock_exit:
                plugin.pytest_sessionstart(FakeSession())
                mock_exit.assert_not_called()

        assert plugin.gate_failed is False
        assert plugin.open_risk_keys == []
        assert plugin.risks is not None

    def test_sessionstart_enabled_with_partial_does_not_exit(self):
        """启用 --risk-gate 且全部 partial（无 open）时不调用 pytest.exit。"""
        plugin = RiskGatePlugin()
        fake_risks = _make_risks({i: "partial" for i in range(1, 8)})

        class FakeConfig:
            def getoption(self, name, default=None):
                return True

        class FakeSession:
            config = FakeConfig()

        with patch("laap_coding.core.risk_gate_plugin.RiskDashboard") as MockDashboard:
            MockDashboard.return_value.get_all_risks.return_value = fake_risks
            with patch("laap_coding.core.risk_gate_plugin.pytest.exit") as mock_exit:
                plugin.pytest_sessionstart(FakeSession())
                mock_exit.assert_not_called()

        assert plugin.gate_failed is False
        assert plugin.risks is not None

    def test_get_all_risks_called_when_gate_enabled(self):
        """启用 --risk-gate 时 RiskDashboard.get_all_risks 被调用。"""
        plugin = RiskGatePlugin()
        fake_risks = _make_risks({})

        class FakeConfig:
            def getoption(self, name, default=None):
                return True

        class FakeSession:
            config = FakeConfig()

        with patch("laap_coding.core.risk_gate_plugin.RiskDashboard") as MockDashboard:
            MockDashboard.return_value.get_all_risks.return_value = fake_risks
            with patch("laap_coding.core.risk_gate_plugin.pytest.exit"):
                plugin.pytest_sessionstart(FakeSession())
            MockDashboard.return_value.get_all_risks.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-p", "no:quadrants"])
