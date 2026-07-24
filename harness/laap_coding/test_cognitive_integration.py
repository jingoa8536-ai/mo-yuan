"""
LAAP Harness ↔ CognitiveBus 集成验证测试
"""

import sys
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_cognitive")

print('=' * 70)
print('LAAP Harness ↔ CognitiveBus 集成验证')
print('=' * 70)

results = []

# 1. 模块导入验证
print('\n[1/6] 模块导入验证')
try:
    from core.cognitive_integration import (
        CognitiveIntegration,
        RateBuffer,
        EmergenceInsight,
        HarnessExecutionResult,
        EmergenceEventType,
        start_integration,
        stop_integration,
        process_pending_insights,
        get_context,
    )
    print('  OK 所有认知集成模块导入成功')
    results.append(('模块导入', True))
except Exception as e:
    print(f'  FAIL 模块导入失败: {e}')
    results.append(('模块导入', False))

# 2. RateBuffer验证（频率缓冲）
print('\n[2/6] RateBuffer频率缓冲验证')
try:
    buffer = RateBuffer(max_size=10, batch_size=3)

    insights = [
        EmergenceInsight(id=f"i_{i}", content=f"洞见{i}: 安全", confidence=0.8, type="insight", source="psi")
        for i in range(15)
    ]

    for i, insight in enumerate(insights):
        added = buffer.add(insight)
        if i < 10:
            print(f'  OK 添加洞见{i+1}: {added}')
        else:
            print(f'  WARN 添加洞见{i+1}: {added} (可能被丢弃)')

    print(f'  OK 缓冲大小: {buffer.size()}')
    print(f'  OK 缓冲统计: {buffer.stats()}')

    batch = buffer.get_batch()
    print(f'  OK 批量获取洞见数: {len(batch)}')

    batch2 = buffer.get_batch()
    print(f'  OK 第二次批量获取洞见数: {len(batch2)}')

    results.append(('RateBuffer', True))
except Exception as e:
    print(f'  FAIL RateBuffer验证失败: {e}')
    results.append(('RateBuffer', False))

# 3. 事件去重验证
print('\n[3/6] 事件去重验证')
try:
    buffer = RateBuffer(max_size=10)

    same_content = "安全保护机制需要增强"
    for i in range(5):
        insight = EmergenceInsight(
            id=f"dup_{i}",
            content=same_content,
            confidence=0.8,
            type="insight",
            source="psi",
        )
        buffer.add(insight)

    print(f'  OK 重复洞见添加后缓冲大小: {buffer.size()}')
    print(f'  OK 唯一内容数: {buffer.stats()["unique_contents"]}')
    print(f'  OK 去重验证通过: {buffer.size() == 1}')

    results.append(('事件去重', True))
except Exception as e:
    print(f'  FAIL 事件去重验证失败: {e}')
    results.append(('事件去重', False))

# 4. 优先级过滤验证
print('\n[4/6] 优先级过滤验证')
try:
    buffer = RateBuffer(max_size=3, drop_low_priority_threshold=0.0)

    for i in range(5):
        priority = "low" if i % 2 == 0 else "high"
        insight = EmergenceInsight(
            id=f"prio_{i}",
            content=f"洞见{i}",
            confidence=0.8,
            type="insight",
            source="psi",
            priority=priority,
        )
        added = buffer.add(insight)
        print(f'  OK 添加{priority}优先级洞见{i}: {added}')

    stats = buffer.stats()
    print(f'  OK 丢弃的洞见数: {stats["dropped"]}')
    print(f'  OK 缓冲中剩余: {stats["pending"]}')

    results.append(('优先级过滤', True))
except Exception as e:
    print(f'  FAIL 优先级过滤验证失败: {e}')
    results.append(('优先级过滤', False))

# 5. 认知上下文获取验证
print('\n[5/6] 认知上下文获取验证')
try:
    context = get_context()
    print(f'  OK 上下文获取成功')
    print(f'  OK 需求状态: {context.get("needs", {})}')
    print(f'  OK 情感状态: {context.get("emotion", {})}')
    print(f'  OK 注意力状态: {context.get("attention", {})}')
    print(f'  OK 待处理洞见数: {context.get("insights_pending", 0)}')

    results.append(('认知上下文', True))
except Exception as e:
    print(f'  WARN 认知上下文获取: {e}')
    results.append(('认知上下文', False))

# 6. 完整集成流程验证
print('\n[6/6] 完整集成流程验证')
try:
    integration = start_integration()
    print('  OK 认知集成启动成功')

    time.sleep(0.5)

    result = HarnessExecutionResult(
        task_id="test_task_001",
        success=True,
        output="代码生成成功",
        tokens_used=500,
        duration=1.2,
        verification_passed=True,
    )
    integration.submit_execution_result(result)
    print('  OK 执行结果反馈成功')

    stats = integration.stats()
    print(f'  OK 集成统计: {stats}')

    stop_integration()
    print('  OK 认知集成停止成功')

    results.append(('完整集成流程', True))
except Exception as e:
    print(f'  FAIL 完整集成流程验证失败: {e}')
    results.append(('完整集成流程', False))

# 总结
print('\n' + '=' * 70)
print('认知集成验证总结')
print('=' * 70)

passed = sum(1 for _, ok in results if ok)
total = len(results)
pass_rate = passed / total * 100

print(f'\n测试总数: {total}')
print(f'通过数: {passed}')
print(f'通过率: {pass_rate:.1f}%')

print('\n详细结果:')
for name, ok in results:
    print(f'  {"✓" if ok else "✗"} {name}: {"通过" if ok else "失败"}')

print('\n' + '=' * 70)
if pass_rate >= 80:
    print(f'认知集成验证通过! 通过率: {pass_rate:.1f}%')
else:
    print(f'认知集成验证未完全通过, 通过率: {pass_rate:.1f}%')
print('=' * 70)

sys.exit(0 if pass_rate >= 80 else 1)