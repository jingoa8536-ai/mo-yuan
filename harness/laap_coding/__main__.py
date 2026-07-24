"""
LAAP Coding — 独立入口点

  完全独立于 Hermes。不需要 Hermes venv，不需要 Hermes 配置。
  只需要 Python 3.11+ 和 LAAP 自己的模块。

用法：
  python -m laap_coding dev      交互式开发（带 TUI）
  python -m laap_coding status   引擎状态
  python -m laap_coding fix ...  修复 bug

pip 安装：
  cd D:/LAAP/harness
  pip install -e .
  laap-coding dev
"""

import sys
from pathlib import Path

# ── 路径配置 ──
# LAAP CLI 完全独立，只依赖以下路径
_HERE = Path(__file__).resolve().parent
_HARNESS_ROOT = _HERE.parent  # D:/LAAP/harness/
_LAAP_ROOT = _HARNESS_ROOT.parent  # D:/LAAP/

# 注册 LAAP 模块搜索路径
_PATHS = [
    str(_HERE),                           # laap_coding/
    str(_HERE / "core"),                   # laap_coding/core/
    str(_LAAP_ROOT / "laap_agent"),        # DevHarness + 工具模块
    str(_LAAP_ROOT / "aris_code_engine"),  # code_planner + executor
]

for p in _PATHS:
    if p not in sys.path:
        sys.path.insert(0, p)


def main():
    """CLI 入口 — 由 pip 安装的 laap-coding 命令调用。"""
    from laap_coding.__init__ import main as _main
    return _main()


if __name__ == "__main__":
    sys.exit(main())
