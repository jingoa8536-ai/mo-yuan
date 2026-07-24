import sys
sys.path.insert(0, 'd:\\LAAP\\harness')
from laap_coding.core.matching_engine import MatchingEngine
import time

engine = MatchingEngine()

# 测试 'cyberpunk landing page' 匹配
intent = {
    'tags': ['react', 'tailwind', 'ui', 'landing', 'dark', 'modern'],
    'style': 'modern-minimal',
    'tech': 'React + Tailwind'
}

start = time.time()
results = engine.match_intent(intent)
elapsed = time.time() - start

print(f'匹配结果数量: {len(results)}')
print(f'匹配耗时: {elapsed*1000:.2f} ms')
if results:
    print('首个结果结构:', list(results[0].keys()))
for r in results[:10]:
    print(f"  {r}")

# 检查首结果匹配度
if len(results) > 0 and results[0]['scores']['total_score'] >= 0.75:
    print('\n✓ 首结果匹配度 ≥0.75')
else:
    print('\n✗ 首结果匹配度 < 0.75')
    if results:
        print(f'  实际分数: {results[0]["scores"]["total_score"]}')

# 检查响应时间
if elapsed * 1000 <= 200:
    print('✓ 匹配响应时间 ≤200ms')
else:
    print('✗ 匹配响应时间 > 200ms')
