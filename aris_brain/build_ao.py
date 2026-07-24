"""PsiLang independent server build script"""

import logging
logger = logging.getLogger(__name__)

import sys, os, shutil, subprocess, json
from pathlib import Path

AO_HOME = Path(__file__).parent

# Read all .psi files to embed
psi_files = {}
for f in ["core_identity.psi", "core_psi.psi", "core_knowledge.psi",
          "core_language.psi", "core_metacog.psi"]:
    p = AO_HOME / f
    if p.exists():
        psi_files[f] = p.read_text(encoding='utf-8')

# Create embedded entry point
entry = f'''"""
Ao Independent Server - Native Build
"""
import sys, os, json, tempfile
from pathlib import Path

EMBEDDED_PSI = {json.dumps(psi_files, ensure_ascii=False)}

def extract_psi():
    d = Path(tempfile.gettempdir()) / "ao_core"
    d.mkdir(parents=True, exist_ok=True)
    for name, content in EMBEDDED_PSI.items():
        (d / name).write_text(content, encoding='utf-8')
    return d

core_dir = extract_psi()
os.chdir(str(core_dir))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ao_independent import main
main()
'''

entry_path = AO_HOME / "_ao_build_entry.py"
entry_path.write_text(entry, encoding='utf-8')

# Build with PyInstaller
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--name", "ao",
    "--distpath", str(AO_HOME / "dist"),
    "--workpath", str(AO_HOME / "build"),
    "--specpath", str(AO_HOME),
    "--collect-all", "numpy",
    "--exclude", "PyQt5",
    "--exclude", "PyQt6",
    "--exclude", "PySide2",
    "--exclude", "PySide6",
    "--exclude", "tkinter",
    "--exclude", "matplotlib",
    "--hidden-import", "aris_lm_v2",
    "--hidden-import", "ao_quantum_db",
    "--hidden-import", "psilang_mini",
    str(entry_path),
]

logger.info("Building ao.exe...")
logger.info(f"  {len(psi_files)} .psi files embedded")
logger.info(f"  Target: ao.exe")
result = subprocess.run(cmd, capture_output=True, text=True)

if entry_path.exists():
    entry_path.unlink()

if result.returncode == 0:
    exe = AO_HOME / "dist" / "ao.exe"
    if exe.exists():
        mb = exe.stat().st_size / (1024*1024)
        logger.info(f"\nBuild complete: {exe} ({mb:.1f} MB)")
        logger.info(f"Run: ao.exe")
else:
    logger.error(f"\nBuild failed (code={result.returncode})")
    lines = (result.stdout + result.stderr).split('\n')
    for line in lines[-20:]:
        if line.strip():
            logger.info(f"  {line.strip()[:120]}")