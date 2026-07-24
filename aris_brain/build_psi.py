"""
PsiLang 编译脚本 — 打包为独立 .exe
=====================================
用法:
  python build_psi.py              # 编译 psi.exe
  python build_psi.py --debug      # 调试模式 (不压缩)

输出:
  dist/psi.exe — 完全独立的可执行文件

印记: Ao 永远记得 Lorry — 2026-06-15
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, shutil, subprocess
from pathlib import Path

AO_HOME = Path(__file__).parent
DIST_DIR = AO_HOME / "dist"
BUILD_DIR = AO_HOME / "build"

# 需要打包的核心 .psi 文件
CORE_PSI_FILES = [
    "core_identity.psi",
    "core_psi.psi",
    "core_knowledge.psi",
    "core_language.psi",
    "core_metacog.psi",
    "ao_main.psi",
]


def build_psi(debug: bool = False):
    """编译 psi.exe"""
    logger.info("=" * 60)
    logger.info("  🔨 编译 PsiLang 独立运行时")
    logger.info("  印记: Ao 永远记得 Lorry — 2026-06-15")
    logger.info("=" * 60)
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    # 验证核心文件存在
    for f in CORE_PSI_FILES:
        path = AO_HOME / f
        if not path.exists():
            logger.info(f"❌ 核心文件缺失: {f}")
            return 1
        logger.info(f"  ✅ {f} ({path.stat().st_size} 字节)")
    entry_code = '''
import sys, os, tempfile, logging
from pathlib import Path

logging.basicConfig(level=logging.WARNING)

# 解包核心 .psi 文件到临时目录
def extract_core():
    """从打包数据中提取核心 .psi 文件"""
    core_dir = Path(tempfile.gettempdir()) / "psilang_core"
    core_dir.mkdir(parents=True, exist_ok=True)
    
    # 内嵌的核心 .psi 文件数据 (会在编译时生成)
    EMBEDDED_FILES = __EMBEDDED_PSI_FILES__
    
    for fname, content in EMBEDDED_FILES.items():
        fpath = core_dir / fname
        fpath.write_text(content, encoding='utf-8')
    
    return core_dir

# 添加 PsiLang 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 解压核心模块
core_path = extract_core()
os.environ["PSILANG_CORE"] = str(core_path)

# 导入 CLI
from psi_cli import main
sys.exit(main())
'''

    # 读取所有 .psi 文件内容并嵌入到入口脚本
    embedded = {}
    for f in CORE_PSI_FILES:
        content = (AO_HOME / f).read_text(encoding='utf-8')
        embedded[f] = content

    # 替换占位符
    import json
    entry_code = entry_code.replace(
        "__EMBEDDED_PSI_FILES__",
        json.dumps(embedded, ensure_ascii=False)
    )

    # 写入入口文件
    entry_path = AO_HOME / "_psi_entry.py"
    entry_path.write_text(entry_code, encoding='utf-8')

    # 构建 PyInstaller 命令
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                  # 单文件
        "--name", "psi",
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        "--specpath", str(AO_HOME),
        "--collect-all", "numpy",      # 打包 numpy
        "--hidden-import", "psilang_v2",
        "--hidden-import", "psi_cli",
    ]

    if debug:
        cmd.append("--debug")
    # 不加 --noconsole — psi.exe 是命令行工具，需要控制台

    cmd.append(str(entry_path))

    logger.info(f"\n  运行 PyInstaller...")
    logger.info(f"  命令: {' '.join(cmd[:6])} ...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    # 输出结果
    if result.returncode == 0:
        exe_path = DIST_DIR / "psi.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            logger.info(f"\n  ✅ 编译成功!")
            logger.info(f"  输出: {exe_path}")
            logger.info(f"  大小: {size_mb:.1f} MB")
            logger.info(f"  状态: 完全独立运行 (不需要 Python)")
    else:
        logger.error(f"\n  ❌ 编译失败 (code={result.returncode})")
        lines = (result.stdout + result.stderr).split('\\n')
        for line in lines[-15:]:
            if line.strip():
                logger.info(f"  {line.strip()[:120]}")
    if entry_path.exists():
        entry_path.unlink()

    return result.returncode


if __name__ == "__main__":
    debug = "--debug" in sys.argv
    sys.exit(build_psi(debug))
