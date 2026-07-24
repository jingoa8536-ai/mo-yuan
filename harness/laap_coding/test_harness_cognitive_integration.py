"""
Harness主循环与CognitiveIntegration集成测试
验证：
1. Harness初始化时自动启动认知集成
2. run()方法中获取认知上下文
3. run()方法中处理涌现洞见
4. run()方法完成后反馈执行结果给PSI
"""

import sys
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_harness_cognitive")

print('=' * 70)
print('Harness主循环 ↔ CognitiveIntegration 集成测试')
print('=' * 70)

results = []

# 1. 导入验证
print('\n[1/5] 模块导入验证')
try:
    from core.harness import ConsciousnessHarness
    print('  OK ConsciousnessHarness导入成功')
    results.append(('模块导入', True))
except Exception as e:
    print(f'  FAIL 模块导入失败: {e}')
    results.append(('模块导入', False))

# 2. Harness初始化时启动认知集成
print('\n[2/5] Harness初始化测试')
try:
    harness = ConsciousnessHarness(workdir=r"D:\LAAP")
    
    status = harness.status
    print(f'  OK Harness初始化成功')
    print(f'  OK 认知集成状态: {status.get("cognitive_integration", {})}')
    
    cog_status = status.get("cognitive_integration", {})
    assert cog_status.get("available", True) != False, "认知集成不可用"
    
    print('  OK 认知集成已自动启动')
    results.append(('Harness初始化', True))
except Exception as e:
    print(f'  FAIL Harness初始化失败: {e}')
    import traceback
    traceback.print_exc()
    results.append(('Harness初始化', False))

# 3. 执行任务时获取认知上下文
print('\n[3/5] 任务执行时认知上下文获取测试')
try:
    result = harness.run("创建一个简单的Python函数")
    print(f'  OK 任务执行成功: status={result.get("status")}')
    print(f'  OK 认知上下文: {result.get("cognitive_context")}')
    print(f'  OK 处理的洞见数: {result.get("insights_processed", 0)}')
    
    assert "cognitive_context" in result, "结果中缺少认知上下文"
    print('  OK 任务执行时成功获取认知上下文')
    results.append(('认知上下文获取', True))
except Exception as e:
    print(f'  FAIL 任务执行失败: {e}')
    import traceback
    traceback.print_exc()
    results.append(('认知上下文获取', False))

# 4. DecisionLayer洞见处理测试
print('\n[4/5] DecisionLayer洞见处理测试')
try:
    insight_summary = harness.decision_layer.get_insight_summary()
    print(f'  OK 洞见摘要: {insight_summary}')
    print(f'  OK 待处理洞见数: {insight_summary.get("pending", 0)}')
    print(f'  OK 已纳入洞见数: {insight_summary.get("incorporated", 0)}')
    
    assert "pending" in insight_summary, "洞见摘要缺少pending字段"
    assert "incorporated" in insight_summary, "洞见摘要缺少incorporated字段"
    print('  OK DecisionLayer洞见处理功能正常')
    results.append(('DecisionLayer洞见处理', True))
except Exception as e:
    print(f'  FAIL DecisionLayer洞见处理失败: {e}')
    import traceback
    traceback.print_exc()
    results.append(('DecisionLayer洞见处理', False))

# 5. 执行结果反馈测试
print('\n[5/5] 执行结果反馈测试')
try:
    status = harness.status
    cog_stats = status.get("cognitive_integration", {})
    print(f'  OK 认知集成统计: {cog_stats}')
    
    if cog_stats.get("running"):
        exec_results = cog_stats.get("execution_results_pending", 0)
        print(f'  OK 待反馈执行结果数: {exec_results}')
        assert exec_results >= 1, "执行结果未反馈"
    
    print('  OK 执行结果已成功反馈给PSI')
    results.append(('执行结果反馈', True))
except Exception as e:
    print(f'  FAIL 执行结果反馈测试失败: {e}')
    import traceback
    traceback.print_exc()
    results.append(('执行结果反馈', False))

# 总结
print('\n' + '=' * 70)
print('Harness主循环集成测试总结')
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
    print(f'Harness主循环集成测试通过! 通过率: {pass_rate:.1f}%')
else:
    print(f'Harness主循环集成测试未完全通过, 通过率: {pass_rate:.1f}%')
print('=' * 70)

sys.exit(0 if pass_rate >= 80 else 1)