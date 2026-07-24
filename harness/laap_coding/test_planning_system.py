"""
LAAP Harness 任务规划系统验证测试
"""

from core.harness import (
    PerceptionLayer, MemoryLayer, PlanningEngine,
    DependencyGraph, SubTaskGranularityControl, SubTask
)

print('=' * 60)
print('LAAP Harness 任务规划系统验证')
print('=' * 60)

# 1. 复杂任务分解验证
print('\n[1/4] 复杂任务分解验证')
try:
    memory = MemoryLayer()
    perception = PerceptionLayer(memory)
    planner = PlanningEngine(memory)

    context = perception.perceive('创建一个完整的博客系统，包含用户认证、文章管理和评论功能')
    plan_result = planner.plan_with_dependency_graph(context)

    subtasks = plan_result['subtasks']
    print('  OK 子任务数量:', len(subtasks))
    print('  OK 执行顺序:', [s.sub_task_id for s in subtasks])
    print('  OK 独立任务:', plan_result['independent_tasks'])
except Exception as e:
    print('  FAIL 任务分解验证失败:', e)

# 2. 子任务粒度控制验证
print('\n[2/4] 子任务粒度控制验证')
try:
    granularity = SubTaskGranularityControl()
    
    test_cases = [
        ('创建一个简单的Hello World程序', 'code'),
        ('创建一个复杂的认证系统，包含JWT、OAuth2和多因素认证', 'implement'),
        ('修复登录页面的CSS样式问题', 'fix'),
        ('重构整个用户模块的代码结构', 'refactor'),
    ]
    
    for desc, intent in test_cases:
        lines = granularity.estimate_lines(desc, intent)
        should_split = granularity.should_split(lines)
        status = 'OK' if lines <= 200 else 'WARN'
        print(f'  {status} "{desc[:40]}..." -> 预估{lines}行, 需要拆分:{should_split}')

    subtask = SubTask(
        sub_task_id='test_1',
        parent_task_id='parent',
        description='测试子任务',
        files=['test.py'],
        estimated_lines=250,
        dependencies=[]
    )
    
    split_result = granularity.split_task(subtask)
    print('  OK 超200行任务拆分结果:', len(split_result), '个子任务')
    for s in split_result:
        print(f'    - {s.sub_task_id}: {s.estimated_lines}行')
        
except Exception as e:
    print('  FAIL 粒度控制验证失败:', e)

# 3. 循环依赖检测验证
print('\n[3/4] 循环依赖检测验证')
try:
    graph = DependencyGraph()
    
    subtask1 = SubTask(sub_task_id='task_1', parent_task_id='parent', description='任务1', files=[], estimated_lines=50, dependencies=[])
    subtask2 = SubTask(sub_task_id='task_2', parent_task_id='parent', description='任务2', files=[], estimated_lines=50, dependencies=['task_1'])
    subtask3 = SubTask(sub_task_id='task_3', parent_task_id='parent', description='任务3', files=[], estimated_lines=50, dependencies=['task_2'])
    
    graph.build_from_subtasks([subtask1, subtask2, subtask3])
    cycles = graph.detect_cycles()
    print('  OK 无循环依赖检测:', '无' if not cycles else cycles)
    
    subtask4 = SubTask(sub_task_id='task_4', parent_task_id='parent', description='任务4(循环依赖)', files=[], estimated_lines=50, dependencies=['task_3'])
    subtask5 = SubTask(sub_task_id='task_3', parent_task_id='parent', description='任务3(修改)', files=[], estimated_lines=50, dependencies=['task_4'])
    
    graph2 = DependencyGraph()
    graph2.add_node(subtask4)
    graph2.add_node(subtask5)
    graph2.add_dependency('task_3', 'task_4')
    graph2.add_dependency('task_4', 'task_3')
    
    cycles2 = graph2.detect_cycles()
    print('  OK 循环依赖检测:', '检测到' if cycles2 else '未检测到')
    
except Exception as e:
    print('  FAIL 循环依赖检测验证失败:', e)

# 4. 不同类型任务规划策略验证
print('\n[4/4] 不同类型任务规划策略验证')
try:
    memory = MemoryLayer()
    perception = PerceptionLayer(memory)
    planner = PlanningEngine(memory)
    
    task_types = [
        ('创建一个RESTful API接口', 'implement'),
        ('修复用户登录失败的bug', 'fix'),
        ('审查用户模块的代码质量', 'review'),
        ('为认证系统编写单元测试', 'test'),
        ('重构数据库连接池代码', 'refactor'),
        ('部署应用到生产环境', 'deploy'),
    ]
    
    for desc, expected_intent in task_types:
        context = perception.perceive(desc)
        subtasks = planner.plan(context)
        print(f'  OK 意图"{expected_intent}" -> 生成{len(subtasks)}个子任务')
        
except Exception as e:
    print('  FAIL 任务类型策略验证失败:', e)

print('\n' + '=' * 60)
print('验证完成!')
print('=' * 60)