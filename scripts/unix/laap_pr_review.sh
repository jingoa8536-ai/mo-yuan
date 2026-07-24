#!/bin/bash
# LAAP PR Review — one-liner
# 用法: ./laap_pr_review.sh <repo> <pr_number>
# 示例: ./laap_pr_review.sh lorryjovens-hub/LAAP-Living-Agent-Application-Protocol- 1

REPO=${1:-lorryjovens-hub/LAAP-Living-Agent-Application-Protocol-}
PR=${2:-1}

echo "=== LAAP PR Review ==="
echo "仓库: $REPO"
echo "PR:   #$PR"
echo ""

cd /d/LAAP
unset PYTHONPATH

# 从 gh 获取 diff 并通过 API 发送审查
gh pr diff $PR --repo $REPO | python -c "
import sys
sys.path.insert(0, '.')
from laap.colony.pr_review import PRReviewEngine
diff = sys.stdin.read()
print(f'Diff 大小: {len(diff)} bytes')
engine = PRReviewEngine()
result = engine.review(diff, repo_path='.')
print()
print(PRReviewEngine.format_review_markdown(result))
print()
print(f'Inline comments: {len(PRReviewEngine.build_inline_comments(result))}')
print(f'Verdict: {result[\"verdict\"]}')
"
