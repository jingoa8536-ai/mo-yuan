"""
gh-push.py — 通过 gh API 推送当前 commit 到 GitHub
"""

import logging
logger = logging.getLogger(__name__)

import subprocess, json, base64, os
from pathlib import Path

REPO = "lorryjovens-hub/LAAP-Living-Agent-Application-Protocol-"

# Get the commit we want to push
result = subprocess.run(
    ["git", "-C", "D:/LAAP", "rev-parse", "HEAD"],
    capture_output=True, text=True, timeout=10
)
commit_sha = result.stdout.strip()
logger.info(f"Local HEAD: {commit_sha}")
result = subprocess.run(
    ["git", "-C", "D:/LAAP", "cat-file", "-p", commit_sha],
    capture_output=True, text=True, timeout=10
)
logger.info(f"Commit message: {result.stdout.split(chr(10))[4] if result.stdout else 'unknown'}")
result = subprocess.run(
    ["git", "-C", "D:/LAAP", "cat-file", "-p", commit_sha],
    capture_output=True, text=True, timeout=10
)
tree_line = [l for l in result.stdout.split("\n") if l.startswith("tree ")][0]
tree_sha = tree_line.split()[1]
logger.info(f"Tree SHA: {tree_sha}")
cmd = [
    "gh", "api", f"repos/{REPO}/git/refs/heads/main",
    "-X", "PATCH",
    "-f", f"sha={commit_sha}",
    "-f", "force=true"
]
logger.info(f"Running: {' '.join(cmd)}")
result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
logger.info(f"Status: {result.returncode}")
logger.info(f"Stdout: {result.stdout[:500]}")
if result.stderr:
    logger.info(f"Stderr: {result.stderr[:500]}")