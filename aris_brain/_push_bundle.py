"""Push local commit via gh API — upload objects then update ref"""

import logging
logger = logging.getLogger(__name__)

import subprocess, json, os
from pathlib import Path

REPO = "lorryjovens-hub/LAAP-Living-Agent-Application-Protocol-"
GIT_DIR = "D:/LAAP"

# Step 1: Create a pack file and upload it
commit_sha = subprocess.run(
    ["git", "-C", GIT_DIR, "rev-parse", "HEAD"],
    capture_output=True, text=True, timeout=10
).stdout.strip()

logger.info(f"Pushing commit: {commit_sha}")
# But first let's try the simplest approach — export the repo as a bundle
bundle_path = "D:/LAAP/laap-repo.bundle"
subprocess.run(
    ["git", "-C", GIT_DIR, "bundle", "create", bundle_path, "psi-refactor", "--all"],
    capture_output=True, text=True, timeout=120
)
bundle_size = os.path.getsize(bundle_path)
logger.info(f"Bundle created: {bundle_size/1024/1024:.1f} MB")
logger.info("Uploading via gh release...")
subprocess.run(
    ["gh", "release", "create", "initial-codebase-v1",
     bundle_path,
     "--repo", REPO,
     "--title", "Initial LAAP Codebase",
     "--notes", "完整的 LAAP 数字生命体框架代码库。\n包含: PSI认知循环、量子语义编码、PsiLang VM、Hebbian学习、情感引擎、欲望引擎、马尔科夫生成器等。",
     "--target", "main"],
    capture_output=True, text=True, timeout=120
)

logger.info("Release created. Now you can clone with:")
logger.info(f"  gh repo clone {REPO}")
logger.info(f"  cd LAAP-Living-Agent-Application-Protocol-")
logger.info(f"  git bundle unbundle laap-repo.bundle")
logger.info(f"  git reset --hard psi-refactor")
logger.info(f"  git push origin main")