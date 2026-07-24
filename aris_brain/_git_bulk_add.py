"""
git-bulk-add.py — 分批次 git add，避免单个大文件卡死
"""

import logging
logger = logging.getLogger(__name__)

import subprocess, os, sys, time
from pathlib import Path

REPO = Path("D:/LAAP")
os.chdir(str(REPO))

# Remove lock if exists
lock = REPO / ".git" / "index.lock"
if lock.exists():
    try:
        lock.unlink()
        logger.info("Removed stale lock")
        time.sleep(1)
    except:
        logger.info("Could not remove lock, trying force...")
        subprocess.run(["powershell", "-NoProfile", "-Command",
            "Get-Process git* | Stop-Process -Force; Start-Sleep 1; Remove-Item -Force 'D:/LAAP/.git/index.lock'"],
            capture_output=True, timeout=30)
        time.sleep(1)

# Check what's currently tracked vs new
result = subprocess.run(["git", "ls-files"], capture_output=True, text=True, timeout=30)
tracked = set(result.stdout.strip().split("\n"))

# Files to ADD (all untracked + changed)
batch_size = 500
all_files = []

# Walk and collect
for f in sorted(REPO.rglob("*")):
    if f.is_dir():
        continue
    rel = str(f.relative_to(REPO))
    # Skip ignored patterns
    skip_patterns = [".git/", "__pycache__", "node_modules", "build/", "laap-github/",
                     "xiaozhi-esp", "external_", "Live2D", "state/", ".venv/", "venv/",
                     ".egg-info", ".pytest_cache", ".safe_rollback", ".laap/",
                     "AFlow/", "code/", "Harnessing", "implementations/", "k8s/",
                     "benchmarks/", "models/", "_backup", "mobile_package",
                     "hs_err_pid", ".npz", ".pkl", ".npy", ".wav", ".mp3",
                     ".log", ".gz", ".db", "gateway_state", "memory/archive",
                     "episodic_memory.json", ".pypirc", ".env",
                     "aria_brain/nul"]
    if any(p in rel for p in skip_patterns):
        continue
    all_files.append(rel)

logger.info(f"Total files to add: {len(all_files)}")
batches = [all_files[i:i+batch_size] for i in range(0, len(all_files), batch_size)]
added = 0
for i, batch in enumerate(batches):
    try:
        r = subprocess.run(["git", "add"] + batch, capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            added += len(batch)
            if (i+1) % 10 == 0:
                logger.info(f"  batch {i+1}/{len(batches)}: {added}/{len(all_files)} added")
        else:
            err = r.stderr.strip()[:100] if r.stderr else "unknown"
            logger.error(f"  batch {i+1} FAILED: {err}")
    except subprocess.TimeoutExpired:
        logger.info(f"  batch {i+1} TIMEOUT, continuing...")
logger.info(f"\nDone: {added}/{len(all_files)} files added to index")
r2 = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, timeout=30)
staged = [l for l in r2.stdout.strip().split("\n") if l.startswith("A") or l.startswith("M")]
unstaged = [l for l in r2.stdout.strip().split("\n") if l.startswith(" ") or l.startswith("?")]
logger.info(f"Staged: {len(staged)}, Unstaged/untracked: {len(unstaged)}")