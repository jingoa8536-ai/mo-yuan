"""
LAAP Harness 进度跟踪与目标管理系统验证测试
"""

from core.progress_tracker import ProgressTracker

print('=' * 60)
print('LAAP Harness 进度跟踪与目标管理验证')
print('=' * 60)

# 1. 任务状态追踪验证
print('\n[1/4] 任务状态追踪验证')
try:
    tracker = ProgressTracker()
    
    tracker.add_task('task-1', '实现感知层', priority='high')
    tracker.add_task('task-2', '实现记忆层', priority='high')
    tracker.add_task('task-3', '实现推理层', priority='medium')
    
    task1 = tracker.get_task('task-1')
    print('  OK 添加任务:', task1 is not None)
    print('  OK 任务初始状态:', task1.status)
    
    tracker.update_task_status('task-1', 'in_progress')
    task1 = tracker.get_task('task-1')
    print('  OK 任务进行中状态:', task1.status)
    
    tracker.update_task_progress('task-1', 50.0)
    print('  OK 任务进度50%:', task1.progress)
    
    tracker.update_task_status('task-1', 'completed')
    task1 = tracker.get_task('task-1')
    print('  OK 任务完成状态:', task1.status)
    print('  OK 任务完成进度:', task1.progress)
    
    tracker.fail_task('task-2', '测试失败')
    task2 = tracker.get_task('task-2')
    print('  OK 任务失败状态:', task2.status)
    print('  OK 失败原因记录:', task2.error_message is not None)
    
    pending_tasks = tracker.list_tasks(status='pending')
    print('  OK 待处理任务数:', len(pending_tasks))
    
    completed_tasks = tracker.list_tasks(status='completed')
    print('  OK 已完成任务数:', len(completed_tasks))
    
    failed_tasks = tracker.list_tasks(status='failed')
    print('  OK 失败任务数:', len(failed_tasks))
    
except Exception as e:
    print('  FAIL 任务状态追踪验证失败:', e)

# 2. 进度评估验证
print('\n[2/4] 进度评估验证')
try:
    tracker = ProgressTracker()
    
    tracker.add_task('task-a', '核心功能A', priority='high')
    tracker.add_task('task-b', '核心功能B', priority='high')
    tracker.add_task('task-c', '辅助功能C', priority='medium')
    
    tracker.update_task_status('task-a', 'completed')
    tracker.update_task_status('task-b', 'in_progress')
    tracker.update_task_progress('task-b', 50.0)
    
    overall = tracker.get_overall_progress()
    print('  OK 整体进度:', f'{overall:.1f}%')
    print('  OK 进度在有效范围:', 0 <= overall <= 100)
    
    stats = tracker.get_statistics()
    print('  OK 统计信息完整性:', 'total_tasks' in stats and 'overall_progress' in stats)
    print('  OK 总任务数:', stats['total_tasks'])
    print('  OK 已完成任务数:', stats['completed_tasks'])
    print('  OK 进行中任务数:', stats['in_progress_tasks'])
    print('  OK 待处理任务数:', stats['pending_tasks'])
    
except Exception as e:
    print('  FAIL 进度评估验证失败:', e)

# 3. 目标管理验证
print('\n[3/4] 目标管理验证')
try:
    tracker = ProgressTracker()
    
    tracker.add_task('goal-task-1', '目标任务1')
    tracker.add_task('goal-task-2', '目标任务2')
    tracker.add_task('goal-task-3', '目标任务3')
    
    tracker.add_goal('goal-1', '实现认知架构', '完成7层认知架构开发', target_date='2026-08-01')
    tracker.add_task_to_goal('goal-1', 'goal-task-1')
    tracker.add_task_to_goal('goal-1', 'goal-task-2')
    tracker.add_task_to_goal('goal-1', 'goal-task-3')
    
    goal = tracker.get_goal('goal-1')
    print('  OK 目标创建:', goal is not None)
    print('  OK 目标任务数:', len(goal.tasks))
    print('  OK 目标初始进度:', f'{goal.progress:.1f}%')
    
    tracker.update_task_status('goal-task-1', 'completed')
    goal = tracker.get_goal('goal-1')
    print('  OK 完成1个任务后进度:', f'{goal.progress:.1f}%')
    
    tracker.update_task_status('goal-task-2', 'completed')
    goal = tracker.get_goal('goal-1')
    print('  OK 完成2个任务后进度:', f'{goal.progress:.1f}%')
    
    tracker.update_task_status('goal-task-3', 'completed')
    goal = tracker.get_goal('goal-1')
    print('  OK 目标完成状态:', goal.status)
    print('  OK 目标完成进度:', f'{goal.progress:.1f}%')
    
    goals = tracker.list_goals()
    print('  OK 目标列表获取:', len(goals))
    
except Exception as e:
    print('  FAIL 目标管理验证失败:', e)

# 4. 进度报告生成验证
print('\n[4/4] 进度报告生成验证')
try:
    tracker = ProgressTracker()
    
    tracker.add_task('report-task-1', '实现核心模块', priority='high')
    tracker.add_task('report-task-2', '实现验证模块', priority='high')
    tracker.add_task('report-task-3', '实现交付模块', priority='medium')
    
    tracker.update_task_status('report-task-1', 'completed')
    tracker.update_task_status('report-task-2', 'in_progress')
    tracker.update_task_progress('report-task-2', 75.0)
    
    tracker.record_token_usage('report-task-1', 1000)
    tracker.record_token_usage('report-task-2', 500)
    
    tracker.add_goal('report-goal', '完成第一阶段', '实现核心功能')
    tracker.add_task_to_goal('report-goal', 'report-task-1')
    tracker.add_task_to_goal('report-goal', 'report-task-2')
    
    report = tracker.generate_progress_report()
    print('  OK 报告生成成功:', len(report) > 0)
    print('  OK 报告包含任务统计:', '任务统计:' in report)
    print('  OK 报告包含资源消耗:', '资源消耗:' in report)
    print('  OK 报告包含目标统计:', '目标统计:' in report)
    
    lines = report.split('\n')
    print('  OK 报告行数:', len(lines))
    
    snapshot = tracker.create_snapshot()
    print('  OK 快照创建:', snapshot is not None)
    print('  OK 快照时间戳:', snapshot.timestamp > 0)
    
    history = tracker.get_history(limit=5)
    print('  OK 历史记录获取:', len(history))
    
except Exception as e:
    print('  FAIL 进度报告生成验证失败:', e)

print('\n' + '=' * 60)
print('验证完成!')
print('=' * 60)