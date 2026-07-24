"""
LAAP Coding CLI — python -m 入口。

用法：
  python -m harness.cli dev
  python -m harness.cli fix "ModuleNotFoundError"
"""

import sys
from pathlib import Path

# 确保能找到所有模块
HERE = Path(__file__).parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "laap_agent"))
sys.path.insert(0, str(HERE / "aris_code_engine"))

from cli import main

if __name__ == "__main__":
    sys.exit(main())
