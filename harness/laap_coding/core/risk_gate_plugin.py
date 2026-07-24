"""
risk_gate_plugin.py — Pytest CI 风险门控插件
================================================

注册 `--risk-gate` 命令行选项，实现 spec H2「CI 风险门控」：

- 在 `pytest_sessionstart` 阶段调用 `RiskDashboard().get_all_risks()`
- 若任一风险 `status == "open"`，调用 `pytest.exit(..., returncode=1)` 使 CI 失败
- 若全部 `resolved` / `partial`，正常通过
- 在 `pytest_terminal_summary` 输出风险状态摘要报告

使用方式：
    python -m pytest --risk-gate -p laap_coding.core.risk_gate_plugin

或在 `conftest.py` 中通过 `pytest_plugins = ["laap_coding.core.risk_gate_plugin"]` 注册。
"""

import pytest

from laap_coding.core.risk_dashboard import RiskDashboard


class RiskGatePlugin:
    """Pytest 插件：CI 风险门控。

    启用 `--risk-gate` 时：
    1. `pytest_sessionstart` 阶段调用 `RiskDashboard().get_all_risks()`，
       若任一风险为 `open` 则 `pytest.exit(returncode=1)` 终止会话。
    2. `pytest_terminal_summary` 阶段输出 7 项风险的状态摘要。

    未启用 `--risk-gate` 时插件不干预 pytest 行为。
    """

    STATUS_ICON = {
        "resolved": "[OK]",
        "partial": "[WARN]",
        "open": "[FAIL]",
    }

    def __init__(self):
        self.risks = None
        self.gate_enabled = False
        self.gate_failed = False
        self.open_risk_keys = []

    # ------------------------------------------------------------------ #
    # Pytest hooks
    # ------------------------------------------------------------------ #

    def pytest_sessionstart(self, session):
        """会话开始：若启用 --risk-gate，检测风险状态。"""
        config = session.config
        try:
            self.gate_enabled = bool(config.getoption("--risk-gate", default=False))
        except (KeyError, ValueError):
            self.gate_enabled = False

        if not self.gate_enabled:
            return

        dashboard = RiskDashboard()
        self.risks = dashboard.get_all_risks()

        self.open_risk_keys = [
            key for key, entry in self.risks.items()
            if entry.get("status") == "open"
        ]

        if self.open_risk_keys:
            self.gate_failed = True
            message = (
                "Risk gate failed: {} open risk(s) detected [{}]".format(
                    len(self.open_risk_keys),
                    ", ".join(self.open_risk_keys),
                )
            )
            pytest.exit(message, returncode=1)

    def pytest_terminal_summary(self, terminalreporter, exitstatus, config):
        """终端摘要：输出风险状态报告。"""
        if not self.gate_enabled:
            return
        if self.risks is None:
            return

        terminalreporter.write_line("")
        terminalreporter.write_line("=== Risk Gate Report ===", bold=True)

        for key, entry in self.risks.items():
            status = entry.get("status", "unknown")
            icon = self.STATUS_ICON.get(status, "[?]")
            desc = entry.get("description", "")
            terminalreporter.write_line(
                "  {} {}: {} - {}".format(icon, key, status, desc)
            )

        total = len(self.risks)
        resolved = sum(1 for r in self.risks.values() if r.get("status") == "resolved")
        partial = sum(1 for r in self.risks.values() if r.get("status") == "partial")
        open_count = sum(1 for r in self.risks.values() if r.get("status") == "open")

        terminalreporter.write_line("")
        terminalreporter.write_line(
            "Summary: total={} resolved={} partial={} open={}".format(
                total, resolved, partial, open_count
            )
        )

        if self.gate_failed:
            terminalreporter.write_line(
                "Risk gate: FAILED (open risks detected)",
                red=True,
                bold=True,
            )
        else:
            terminalreporter.write_line(
                "Risk gate: PASSED",
                green=True,
                bold=True,
            )


# ---------------------------------------------------------------------- #
# 模块级 hook 函数：注册命令行选项与插件实例
# ---------------------------------------------------------------------- #

def pytest_addoption(parser):
    """注册 --risk-gate 命令行选项。"""
    parser.addoption(
        "--risk-gate",
        action="store_true",
        default=False,
        dest="risk_gate",
        help=(
            "Enable CI risk gate: call RiskDashboard.get_all_risks() at session "
            "start and fail pytest (returncode=1) if any risk is in 'open' status."
        ),
    )


def pytest_configure(config):
    """注册 RiskGatePlugin 实例到 pluginmanager。"""
    config.pluginmanager.register(RiskGatePlugin(), "risk-gate-plugin")
