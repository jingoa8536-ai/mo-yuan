#!/usr/bin/env python
"""
LAAP 仓库整理脚本 — 清理 + 开源准备

运行方式: python cleanup_laap.py

操作:
  1. 删除 Trae 生成的 app/task_*.py 空壳测试桩
  2. 删除 app/schemas.py（只有一行注释）
  3. 移动测试残留文件到 _archive/
  4. 检查并标记含隐私信息的文件
  5. 更新 .gitignore
"""

import os
import shutil
import glob
import re
from pathlib import Path

LAAP = Path("D:/LAAP")
ARCHIVE = LAAP / "_archive"

# ══════════════════════════════════════════════════
# 1. 清理 Trae 空壳文件
# ══════════════════════════════════════════════════

print("=" * 60)
print("Phase 1: 清理 Trae 空壳文件")
print("=" * 60)

# 删除 app/task_*.py (全部是 Trae 自动生成的 < 200 bytes 测试桩)
task_files = list(LAAP.glob("app/task_*.py"))
# 也包括 aris_brain/app/task_*.py
task_files += list(LAAP.glob("aris_brain/app/task_*.py"))

removed = 0
for f in task_files:
    size = f.stat().st_size
    if size < 200:  # 确认是空壳
        backup = ARCHIVE / "trae_stubs" / f.name
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(f), str(backup))
        print(f"  移至 _archive: {f.name} ({size} bytes)")
        removed += 1
    else:
        print(f"  保留 (非空壳): {f.name} ({size} bytes)")

# 清理 app/schemas.py (只有一行注释)
schemas = LAAP / "app" / "schemas.py"
if schemas.exists() and schemas.stat().st_size < 100:
    backup = ARCHIVE / "trae_stubs" / "schemas.py"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(schemas), str(backup))
    print(f"  移至 _archive: schemas.py ({schemas.stat().st_size} bytes)")
    removed += 1

# app/models.py 虽然是桩但可能有用，保留
# app/services.py 可能含有用代码，保留

print(f"  Total: {removed} files archived")

# ══════════════════════════════════════════════════
# 2. 检查隐私信息
# ══════════════════════════════════════════════════

print("\n" + "=" * 60)
print("Phase 2: 检查隐私信息")
print("=" * 60)

sensitive_patterns = [
    (r'sk-[a-zA-Z0-9]{20,}', 'API Key (sk-...)'),
    (r'FEISHU_APP_ID|cli_[a-zA-Z0-9]+', 'Feishu App ID'),
    (r'deepseek.*key|api_key.*=.*["\']', 'API Key config'),
    (r'["\'][a-zA-Z0-9+/=]{40,}["\']', 'Base64 secret'),
    (r'Lorry Jovens|黄俊华', 'Personal name'),
    (r'password|passwd|secret.*=', 'Credential'),
]

# Check key config files
check_files = [
    LAAP / ".env",
    LAAP / ".deepseek_key",
    LAAP / ".gitignore",
    LAAP / "pyproject.toml",
    LAAP / "config.yaml",
]

for f in check_files:
    if not f.exists():
        continue
    content = f.read_text(encoding="utf-8", errors="ignore")
    for pattern, desc in sensitive_patterns:
        matches = re.findall(pattern, content)
        if matches:
            print(f"  ⚠️ {f.name}: 发现 {desc}")

# ══════════════════════════════════════════════════
# 3. 更新 .gitignore
# ══════════════════════════════════════════════════

print("\n" + "=" * 60)
print("Phase 3: 写入 .gitignore (开源版)")
print("=" * 60)

GITIGNORE_CONTENT = """# LAAP .gitignore — 开源发布版

# ── 机密 ──
.env
.env.*
*.key
*secret*
*credential*
deepseek_key
config.yaml
*.pem
*.cert

# ── 个人路径 ──
D:/
C:/
Users/
*.local

# ── Python ──
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
*.so
*.pyd
*.dll

# ── 数据文件 ──
*.db
*.db-shm
*.db-wal
*.npz
*.pkl
*.pickle
state/
logs/
*.log
*.mp3
*.mp4
*.png
*.jpg
*.ico

# ── IDE/工具 ──
.trae/
.vscode/
.idea/
*.swp
*.swo
*~
.ruff_cache/
.pytest_cache/
.mypy_cache/

# ── 构建输出 ──
dist/
build/
*.exe
*.msi
target/

# ── 测试残留 ──
test_*.txt
_test_*
_benchmark*
final_verify.txt
psi_test_log.txt

# ── 大型文件 ──
*.pdf
*.zip
*.7z
*.rar
ngrok.zip
*.bin

# ── 系统 ──
Thumbs.db
.DS_Store
nul
EOF
"""

(LAAP / ".gitignore").write_text(GITIGNORE_CONTENT.strip(), encoding="utf-8")
print("  ✅ .gitignore 已更新")

# ══════════════════════════════════════════════════
# 4. 创建 LICENSE
# ══════════════════════════════════════════════════

print("\n" + "=" * 60)
print("Phase 4: 创建 LICENSE")
print("=" * 60)

LICENSE_CONTENT = """MIT License

Copyright (c) 2026 LAAP (Lorry's AGI Architecture Project)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
"""

(LAAP / "LICENSE").write_text(LICENSE_CONTENT.strip(), encoding="utf-8")
print("  ✅ LICENSE (MIT) 已创建")

# ══════════════════════════════════════════════════
# 5. 创建开源版 README
# ══════════════════════════════════════════════════

print("\n" + "=" * 60)
print("Phase 5: 创建 README.md")
print("=" * 60)

README_PATH = LAAP / "README.md"
README_CONTENT = """# LAAP — Language AGI Architecture Project

**LAAP** is an open-source framework for building digital lifeforms with:
- **Ψ-Semiotics**: Symbolic reasoning in high-dimensional semantic spaces
- **PSI Cognitive Cycle**: Emotion-driven autonomous behavior
- **Quantum Feature Kernels**: Zero-LLM reasoning in 16384D feature space
- **Harness Engine**: Zero-token frontend generation

## Quick Start

```bash
pip install -e .
python -c "from laap.agi.core import LAAPEngine; print('LAAP ready')"
```

## Architecture

```
User Input → IntentClassifier → Ψ-Semiotics → PSI Cycle → Response
                                   ↕
                           V12DenseKernel (16384D)
                                   ↕
                       Cognitive Bridge + Memory Store
```

## Modules

| Module | Directory | Description |
|--------|-----------|-------------|
| AGI Core | `laap/agi/` | World model, causal engine, cognitive bus |
| Ψ-Semiotics | `aris_brain/psi_semiotics/` | Symbolic reasoning engine |
| Harness | `harness/` | Zero-token UI generation framework |
| Cognitive Control | `laap/laap_tools/` | LLM control paths (logit bias, guided gen) |

## License

MIT
"""

README_PATH.write_text(README_CONTENT.strip(), encoding="utf-8")
print("  ✅ README.md 已创建")

print("\n" + "=" * 60)
print("  🧹 LAAP 整理完成")
print("=" * 60)
