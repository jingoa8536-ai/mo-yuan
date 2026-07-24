"""
laap_coding 测试配置（conftest.py）
=====================================

职责：
1. 将 `harness/` 加入 sys.path，确保 `laap_coding` 包可被导入。

注意：
- `pytest_plugins`（pytester / risk_gate_plugin）已迁移至顶层 `D:\\LAAP\\conftest.py`，
  避免在非顶层 conftest 中定义 `pytest_plugins`（pytest 9.0 已 deprecate 此用法）。
"""

import os
import sys

# 将 harness/ 目录加入 sys.path，使 `laap_coding` 包可被导入
_HARNESS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HARNESS_ROOT not in sys.path:
    sys.path.insert(0, _HARNESS_ROOT)
