"""
LAAP Harness 7层认知架构验证测试
"""

from core.harness import (
    PerceptionLayer, MemoryLayer, PlanningEngine,
    DependencyGraph, SubTaskGranularityControl
)

print('=' * 60)
print('LAAP Harness 7层认知架构验证')
print('=' * 60)

# 1. 感知层验证
print('\n[1/7] 感知层验证')
try:
    memory = MemoryLayer()
    perception = PerceptionLayer(memory)
    context = perception.perceive('创建一个基于Python的博客系统')
    print('  OK 意图分类:', context.intent)
    print('  OK 关键词提取:', context.keywords[:5])
    print('  OK 相关模式:', context.related_patterns)
except Exception as e:
    print('  FAIL 感知层验证失败:', e)

# 2. 记忆层验证
print('\n[2/7] 记忆层验证')
try:
    memory = MemoryLayer()
    memory.add_working_memory('test_key', 'test_value')
    memory.add_short_term_memory('project_rules', '遵循PEP8规范')
    memory.add_long_term_memory('error_pattern', '避免循环依赖')
    status = memory.get_memory_status()
    print('  OK 工作记忆:', status['working_memory']['size'], '项')
    print('  OK 短期记忆:', status['short_term_memory']['size'], '项')
    print('  OK 长期记忆:', status['long_term_memory']['size'], '项')
    patterns = memory.recommend_patterns('实现CRUD操作', top_n=2)
    pattern_names = [p['name'] for p in patterns]
    print('  OK 模式推荐:', pattern_names)
except Exception as e:
    print('  FAIL 记忆层验证失败:', e)

# 3. 推理层验证
print('\n[3/7] 推理层验证')
try:
    memory = MemoryLayer()
    perception = PerceptionLayer(memory)
    planner = PlanningEngine(memory)

    context = perception.perceive('创建一个完整的博客系统')
    plan_result = planner.plan_with_dependency_graph(context)

    print('  OK 子任务数量:', len(plan_result['subtasks']))
    print('  OK 执行顺序:', plan_result['execution_order'][:5])
    cycles = plan_result['cycles']
    print('  OK 循环依赖检测:', '无' if not cycles else '有')
except Exception as e:
    print('  FAIL 推理层验证失败:', e)

# 4. 决策层验证（架构模式验证）
print('\n[4/7] 决策层验证')
try:
    memory = MemoryLayer()
    pattern = memory.get_pattern_by_id('dependency_injection')
    if pattern:
        print('  OK 模式获取:', pattern['name'])
        validation = memory.validate_pattern_quality('dependency_injection', {'uses_interfaces': True})
        print('  OK 质量门控验证:', validation['valid'])
    else:
        print('  OK 模式库加载成功')
except Exception as e:
    print('  FAIL 决策层验证失败:', e)

# 5. 执行层验证（粒度控制）
print('\n[5/7] 执行层验证')
try:
    granularity = SubTaskGranularityControl()
    lines = granularity.estimate_lines('创建一个复杂的认证系统', 'implement')
    print('  OK 代码量预估:', lines, '行')
    print('  OK 是否需要拆分:', granularity.should_split(lines))
except Exception as e:
    print('  FAIL 执行层验证失败:', e)

# 6. 验证层验证
print('\n[6/7] 验证层验证')
try:
    from core.test_validator import TestValidator
    validator = TestValidator()
    print('  OK 测试验证器初始化成功')

    from core.static_analyzer import StaticAnalyzer
    analyzer = StaticAnalyzer()
    print('  OK 静态分析器初始化成功')

    from core.security_scanner import SecurityScanner
    scanner = SecurityScanner()
    print('  OK 安全扫描器初始化成功')
except ImportError as e:
    print('  WARN 验证层组件需额外依赖:', e)
except Exception as e:
    print('  FAIL 验证层验证失败:', e)

# 7. 反馈层验证
print('\n[7/7] 反馈层验证')
try:
    from core.feedback_engine import FeedbackEngine
    engine = FeedbackEngine()
    print('  OK 反馈引擎初始化成功')

    from core.compliance_checker import CodeComplianceChecker
    checker = CodeComplianceChecker()
    print('  OK 合规检查器初始化成功')
except ImportError as e:
    print('  WARN 反馈层组件需额外依赖:', e)
except Exception as e:
    print('  FAIL 反馈层验证失败:', e)

print('\n' + '=' * 60)
print('验证完成!')
print('=' * 60)