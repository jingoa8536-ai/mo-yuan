"""
简化的认知集成测试
"""

import sys
import logging

logging.basicConfig(level=logging.INFO)

print('=' * 70)
print('简化认知集成测试')
print('=' * 70)

# 测试1: 导入
print('\n[1/3] 导入测试')
try:
    from core.harness import ConsciousnessHarness
    from core.cognitive_integration import (
        CognitiveIntegration,
        RateBuffer,
        EmergenceInsight,
        start_integration,
        stop_integration,
        process_pending_insights,
        get_context,
    )
    print('  OK 所有模块导入成功')
except Exception as e:
    print(f'  FAIL: {e}')
    sys.exit(1)

# 测试2: RateBuffer
print('\n[2/3] RateBuffer测试')
try:
    buffer = RateBuffer(max_size=5, batch_size=2)
    for i in range(5):
        insight = EmergenceInsight(id=f"i_{i}", content=f"test_{i}", confidence=0.8, type="insight", source="test")
        buffer.add(insight)
    batch = buffer.get_batch()
    print(f'  OK 批量获取洞见数: {len(batch)}')
except Exception as e:
    print(f'  FAIL: {e}')
    sys.exit(1)

# 测试3: 认知上下文
print('\n[3/3] 认知上下文测试')
try:
    context = get_context()
    print(f'  OK 认知上下文获取成功')
    print(f'  OK 需求: {context.get("needs")}')
    print(f'  OK 情感: {context.get("emotion")}')
except Exception as e:
    print(f'  FAIL: {e}')
    sys.exit(1)

print('\n' + '=' * 70)
print('所有测试通过!')
print('=' * 70)
sys.exit(0)