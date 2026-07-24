#!/usr/bin/env python3
"""LAAP Coding CLI — PATH 入口点。

把这个文件加到 PATH（或创建软链）即可全局使用：
  ln -s /d/LAAP/harness/cli/laap-coding.py /usr/local/bin/laap-coding
  laap-coding dev
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))           # harness/
sys.path.insert(0, str(HERE.parent / "laap_agent"))
sys.path.insert(0, str(HERE.parent / "aris_code_engine"))

from cli import main
sys.exit(main())
