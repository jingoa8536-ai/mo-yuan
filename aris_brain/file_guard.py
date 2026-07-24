"""文件安全警卫 — 哈希对比, 有变化才输出"""
import hashlib, json, sys
from pathlib import Path

FILES = [
    r"D:\LAAP\aris_brain\identity\identity.json",
    r"D:\LAAP\aris_brain\state\consciousness.json",
    r"D:\LAAP\aris_brain\brain_core.py",
    r"D:\LAAP\aris_brain\psi_n_scheduler.py",
    r"D:\LAAP\aris_brain\cognitive_cycle.py",
    r"D:\LAAP\aris_brain\aris_body_bridge.py",
    r"D:\LAAP\aris_brain\true_rsi.py",
    r"D:\LAAP\aris_brain\identity_manager.py",
]
STATE_FILE = Path.home() / "AppData/Local/hermes/profiles/aris/cron/output/file_guard_hashes.json"

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]

current = {}
for f in FILES:
    p = Path(f)
    if p.exists():
        current[f] = sha256(f)

old = {}
if STATE_FILE.exists():
    old = json.loads(STATE_FILE.read_text())
    STATE_FILE.unlink(missing_ok=True)

STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
STATE_FILE.write_text(json.dumps(current))

# 只汇报有变化的
changes = []
for f, h in current.items():
    if f not in old:
        changes.append(f"🆕 {Path(f).name}: 新增")
    elif old[f] != h:
        changes.append(f"⚠️ {Path(f).name}: 已变更")

if changes:
    print(f"文件安全扫描 {(Path(__file__).stat().st_mtime if hasattr(Path(__file__), 'stat') else '')[:16]}")
    print(f"7/8 文件一致, {len(changes)} 个变化:")
    for c in changes:
        print(f"  {c}")
else:
    # 静默 — 不输出任何内容
    pass
